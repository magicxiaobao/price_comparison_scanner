use std::fs;
use std::sync::Mutex;
use std::time::{Duration, Instant};

use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager, Runtime};
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandChild;

const HEARTBEAT_INTERVAL_SECS: u64 = 5;
const HEARTBEAT_TIMEOUT_SECS: u64 = 3;
const MAX_CONSECUTIVE_FAILURES: u32 = 3;
const MAX_RESTARTS_PER_WINDOW: u32 = 3;
const RESTART_WINDOW_SECS: u64 = 60;

struct SidecarState {
    port: u16,
    token: String,
    #[allow(dead_code)]
    pid: u32,
    child: Option<CommandChild>,
    // Hardening fields
    restart_count: u32,
    restart_window_start: Instant,
    safe_mode: bool,
}

#[derive(Serialize, Clone)]
struct SidecarInfo {
    port: u16,
    token: String,
    #[serde(rename = "safeMode")]
    safe_mode: bool,
}

#[derive(Serialize, Clone)]
struct SidecarRestartedPayload {
    port: u16,
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

fn port_available(port: u16) -> bool {
    std::net::TcpListener::bind(format!("127.0.0.1:{}", port)).is_ok()
}

/// Clean up orphan sidecar process from a previous session.
/// Reads .sidecar.pid, sends SIGTERM, waits 1s, sends SIGKILL if still alive.
fn cleanup_orphan<R: Runtime>(app: &AppHandle<R>) {
    let app_data = match app.path().app_data_dir().ok() {
        Some(d) => d,
        None => return,
    };
    let pid_path = app_data.join(".sidecar.pid");
    if !pid_path.exists() {
        return;
    }

    if let Ok(content) = fs::read_to_string(&pid_path) {
        if let Ok(old_pid) = content.trim().parse::<u32>() {
            kill_pid(old_pid);
        }
    }
    let _ = fs::remove_file(&pid_path);
}

/// Attempt to kill a process: SIGTERM → wait 1s → SIGKILL
fn kill_pid(pid: u32) {
    #[cfg(unix)]
    {
        use std::thread;
        unsafe {
            // Check if process exists
            if libc::kill(pid as i32, 0) != 0 {
                return;
            }
            // SIGTERM
            libc::kill(pid as i32, libc::SIGTERM);
            thread::sleep(Duration::from_secs(1));
            // If still alive, SIGKILL
            if libc::kill(pid as i32, 0) == 0 {
                libc::kill(pid as i32, libc::SIGKILL);
            }
        }
    }
    #[cfg(windows)]
    {
        // On Windows, use taskkill
        let _ = std::process::Command::new("taskkill")
            .args(["/PID", &pid.to_string(), "/F"])
            .output();
    }
    let _ = pid; // suppress unused warning on non-unix/non-windows
}

fn start_sidecar<R: Runtime>(app: &AppHandle<R>) -> Result<SidecarState, String> {
    // Clean up orphan process before starting
    cleanup_orphan(app);

    let token = uuid::Uuid::new_v4().to_string();
    let port = find_available_port()?;

    start_sidecar_with(app, port, &token)
}

/// Start sidecar with specific port and token. Used by both initial start and restart.
fn start_sidecar_with<R: Runtime>(
    app: &AppHandle<R>,
    port: u16,
    token: &str,
) -> Result<SidecarState, String> {
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
            token,
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
        token: token.to_string(),
        pid,
        child: Some(child),
        restart_count: 0,
        restart_window_start: Instant::now(),
        safe_mode: false,
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

/// Spawn the heartbeat loop that monitors sidecar health and auto-restarts on failure.
fn spawn_heartbeat_loop<R: Runtime + 'static>(app: AppHandle<R>) {
    tauri::async_runtime::spawn(async move {
        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(HEARTBEAT_TIMEOUT_SECS))
            .build()
            .unwrap();

        let mut consecutive_failures: u32 = 0;

        loop {
            tokio::time::sleep(Duration::from_secs(HEARTBEAT_INTERVAL_SECS)).await;

            // Read current state
            let state_mutex: tauri::State<'_, Mutex<Option<SidecarState>>> = app.state();
            let (port, token, safe_mode) = {
                let guard = state_mutex.lock().unwrap();
                match guard.as_ref() {
                    Some(s) => (s.port, s.token.clone(), s.safe_mode),
                    None => continue, // No sidecar running
                }
            };

            // Already in safe mode, stop heartbeat
            if safe_mode {
                eprintln!("[heartbeat] safe mode active, stopping heartbeat loop");
                break;
            }

            let health_url = format!("http://127.0.0.1:{}/api/health", port);
            let auth = format!("Bearer {}", token);

            let ok = match client
                .get(&health_url)
                .header("Authorization", &auth)
                .send()
                .await
            {
                Ok(resp) => resp.status().is_success(),
                Err(_) => false,
            };

            if ok {
                consecutive_failures = 0;
                continue;
            }

            consecutive_failures += 1;
            eprintln!(
                "[heartbeat] health check failed ({}/{})",
                consecutive_failures, MAX_CONSECUTIVE_FAILURES
            );

            if consecutive_failures < MAX_CONSECUTIVE_FAILURES {
                continue;
            }

            // 3 consecutive failures — attempt restart
            eprintln!("[heartbeat] {} consecutive failures, attempting restart", consecutive_failures);

            let should_safe_mode = {
                let mut guard = state_mutex.lock().unwrap();
                let sidecar = match guard.as_mut() {
                    Some(s) => s,
                    None => continue,
                };

                // Reset restart window if expired
                if sidecar.restart_window_start.elapsed() > Duration::from_secs(RESTART_WINDOW_SECS) {
                    sidecar.restart_count = 0;
                    sidecar.restart_window_start = Instant::now();
                }

                if sidecar.restart_count >= MAX_RESTARTS_PER_WINDOW {
                    sidecar.safe_mode = true;
                    true
                } else {
                    sidecar.restart_count += 1;
                    false
                }
            };

            if should_safe_mode {
                eprintln!("[heartbeat] restart limit reached, entering safe mode");
                let _ = app.emit("sidecar-safe-mode", ());
                break;
            }

            // Kill old process
            {
                let mut guard = state_mutex.lock().unwrap();
                if let Some(sidecar) = guard.as_mut() {
                    if let Some(child) = sidecar.child.take() {
                        let _ = child.kill();
                    }
                }
            }

            // Determine port for restart
            let (old_token, new_port) = {
                let guard = state_mutex.lock().unwrap();
                let sidecar = guard.as_ref().unwrap();
                let new_port = if port_available(sidecar.port) {
                    sidecar.port
                } else {
                    match find_available_port() {
                        Ok(p) => p,
                        Err(e) => {
                            eprintln!("[heartbeat] no available port: {}", e);
                            // Enter safe mode
                            drop(guard);
                            let mut guard = state_mutex.lock().unwrap();
                            if let Some(s) = guard.as_mut() {
                                s.safe_mode = true;
                            }
                            let _ = app.emit("sidecar-safe-mode", ());
                            break;
                        }
                    }
                };
                (sidecar.token.clone(), new_port)
            };

            // Restart sidecar
            match start_sidecar_with(&app, new_port, &old_token) {
                Ok(new_state) => {
                    let restarted_port = new_state.port;
                    {
                        let mut guard = state_mutex.lock().unwrap();
                        if let Some(old) = guard.as_mut() {
                            // Preserve restart tracking from old state
                            let restart_count = old.restart_count;
                            let restart_window_start = old.restart_window_start;
                            *old = SidecarState {
                                restart_count,
                                restart_window_start,
                                ..new_state
                            };
                        }
                    }
                    consecutive_failures = 0;
                    eprintln!("[heartbeat] sidecar restarted on port {}", restarted_port);
                    let _ = app.emit(
                        "sidecar-restarted",
                        SidecarRestartedPayload { port: restarted_port },
                    );
                }
                Err(e) => {
                    eprintln!("[heartbeat] restart failed: {}", e);
                    // Will retry on next heartbeat cycle
                }
            }
        }
    });
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
            safe_mode: s.safe_mode,
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

                    // Start heartbeat monitoring loop
                    spawn_heartbeat_loop(handle.clone());
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
