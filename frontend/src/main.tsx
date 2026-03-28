import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { initApiConnection } from "./lib/api";
import "./styles/globals.css";

// 先显示加载提示，窗口立即可见
const root = document.getElementById("root")!;
root.innerHTML = `
  <div id="loading-screen" style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:system-ui;background:#fafafa">
    <div style="text-align:center;max-width:360px">
      <div style="margin:0 auto 20px;width:200px;height:6px;background:#e5e7eb;border-radius:3px;overflow:hidden">
        <div id="progress-bar" style="width:5%;height:100%;background:#3b82f6;border-radius:3px;transition:width 0.5s ease"></div>
      </div>
      <p id="progress-message" style="color:#374151;font-size:15px;font-weight:500">正在初始化，准备资源中...</p>
      <p style="color:#9ca3af;font-size:12px;margin-top:8px">首次启动需要加载资源，请稍候</p>
    </div>
  </div>
`;

// 监听 sidecar 启动进度事件（Tauri 模式）
(async () => {
  try {
    const { isTauri } = await import("@tauri-apps/api/core");
    if (isTauri()) {
      const { listen } = await import("@tauri-apps/api/event");
      await listen<{ step: string; message: string; progress: number }>("sidecar-progress", (event) => {
        const bar = document.getElementById("progress-bar");
        const msg = document.getElementById("progress-message");
        if (bar) bar.style.width = `${event.payload.progress}%`;
        if (msg) msg.textContent = event.payload.message;
      });
    }
  } catch {
    // 非 Tauri 环境，忽略
  }
})();

initApiConnection()
  .then(() => {
    ReactDOM.createRoot(root).render(
      <React.StrictMode>
        <App />
      </React.StrictMode>,
    );
  })
  .catch((err) => {
    root.innerHTML = `
      <div style="padding:48px;text-align:center;font-family:system-ui">
        <h2 style="color:#dc2626">后端服务连接失败</h2>
        <p style="color:#666">无法连接到后端 sidecar 服务，请重启应用。</p>
        <p style="color:#999;font-size:12px">${String(err)}</p>
        <button onclick="location.reload()" style="margin-top:16px;padding:8px 24px;border:1px solid #d1d5db;border-radius:6px;background:#f9fafb;cursor:pointer;font-size:14px">重试</button>
      </div>
    `;
  });
