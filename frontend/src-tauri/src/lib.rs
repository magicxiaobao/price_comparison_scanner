use std::fs;
use std::sync::Mutex;
use std::time::Duration;

use serde::Serialize;
use tauri::{AppHandle, Manager, Runtime};
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandChild;

struct SidecarState {
    port: u16,
    token: String,
    #[allow(dead_code)]
    pid: u32,
    child: Option<CommandChild>,
}

#[derive(Serialize)]
struct SidecarInfo {
    port: u16,
    token: String,
}

fn find_available_port() -> Result<u16, String> {
    let base_port: u16 = 17396;
    for offset in 0..10 {
        let port = base_port + offset;
        match std::net::TcpListener::bind(format!("127.0.0.1:{}", port)) {
            Ok(_listener) => return Ok(port),
            Err(_) => continue,
        }
    }
    Err("所有端口 17396-17405 均被占用".into())
}

fn start_sidecar<R: Runtime>(app: &AppHandle<R>) -> Result<SidecarState, String> {
    let token = uuid::Uuid::new_v4().to_string();
    let port = find_available_port()?;

    let (mut rx, child) = app
        .shell()
        .sidecar("binaries/backend")
        .map_err(|e| format!("创建 sidecar 命令失败: {}", e))?
        .args([
            "--host",
            "127.0.0.1",
            "--port",
            &port.to_string(),
            "--token",
            &token,
        ])
        .spawn()
        .map_err(|e| format!("启动 sidecar 失败: {}", e))?;

    let pid = child.pid();

    // Write PID file
    if let Some(app_data) = app.path().app_data_dir().ok() {
        let _ = fs::create_dir_all(&app_data);
        let pid_path = app_data.join(".sidecar.pid");
        let _ = fs::write(&pid_path, pid.to_string());
    }

    // Spawn a background task to drain sidecar stdout/stderr so the pipe doesn't block
    tauri::async_runtime::spawn(async move {
        use tauri_plugin_shell::process::CommandEvent;
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    let text = String::from_utf8_lossy(&line);
                    eprintln!("[sidecar stdout] {}", text);
                }
                CommandEvent::Stderr(line) => {
                    let text = String::from_utf8_lossy(&line);
                    eprintln!("[sidecar stderr] {}", text);
                }
                CommandEvent::Terminated(payload) => {
                    eprintln!("[sidecar] terminated: {:?}", payload);
                    break;
                }
                CommandEvent::Error(err) => {
                    eprintln!("[sidecar] error: {}", err);
                    break;
                }
                _ => {}
            }
        }
    });

    // Wait for health check (up to 10 seconds, polling every 500ms)
    let health_url = format!("http://127.0.0.1:{}/api/health", port);
    let health_token = format!("Bearer {}", token);

    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| format!("创建 tokio runtime 失败: {}", e))?;

    let ready = rt.block_on(async {
        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(2))
            .build()
            .unwrap();

        for _ in 0..20 {
            tokio::time::sleep(Duration::from_millis(500)).await;
            match client
                .get(&health_url)
                .header("Authorization", &health_token)
                .send()
                .await
            {
                Ok(resp) if resp.status().is_success() => return true,
                _ => continue,
            }
        }
        false
    });

    if !ready {
        return Err("Sidecar 启动超时（10 秒内未响应 health API）".into());
    }

    Ok(SidecarState {
        port,
        token,
        pid,
        child: Some(child),
    })
}

fn cleanup_sidecar<R: Runtime>(app: &AppHandle<R>, state: &Mutex<Option<SidecarState>>) {
    let mut guard = state.lock().unwrap();
    if let Some(mut sidecar) = guard.take() {
        // 1. Send POST /api/shutdown
        let shutdown_url = format!("http://127.0.0.1:{}/api/shutdown", sidecar.port);
        let token = format!("Bearer {}", sidecar.token);

        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build();

        if let Ok(rt) = rt {
            rt.block_on(async {
                let client = reqwest::Client::builder()
                    .timeout(Duration::from_secs(3))
                    .build()
                    .unwrap();
                let _ = client
                    .post(&shutdown_url)
                    .header("Authorization", &token)
                    .send()
                    .await;
                // Wait up to 3 seconds for graceful shutdown
                tokio::time::sleep(Duration::from_secs(3)).await;
            });
        }

        // 2. Force kill if still alive
        if let Some(child) = sidecar.child.take() {
            let _ = child.kill();
        }

        // 3. Delete PID file
        if let Some(app_data) = app.path().app_data_dir().ok() {
            let pid_path = app_data.join(".sidecar.pid");
            let _ = fs::remove_file(&pid_path);
        }
    }
}

#[tauri::command]
fn get_sidecar_info(
    state: tauri::State<'_, Mutex<Option<SidecarState>>>,
) -> Result<SidecarInfo, String> {
    let guard = state.lock().unwrap();
    match guard.as_ref() {
        Some(s) => Ok(SidecarInfo {
            port: s.port,
            token: s.token.clone(),
        }),
        None => Err("Sidecar 尚未启动".into()),
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .manage(Mutex::new(None::<SidecarState>))
        .invoke_handler(tauri::generate_handler![get_sidecar_info])
        .setup(|app| {
            let handle = app.handle().clone();
            match start_sidecar(&handle) {
                Ok(state) => {
                    let managed: tauri::State<Mutex<Option<SidecarState>>> = handle.state();
                    let mut guard = managed.lock().unwrap();
                    *guard = Some(state);
                    eprintln!("[sidecar] 启动成功");
                }
                Err(e) => {
                    eprintln!("[sidecar] 启动失败: {}", e);
                }
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                let app = window.app_handle();
                let state: tauri::State<Mutex<Option<SidecarState>>> = app.state();
                cleanup_sidecar(app, state.inner());
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
