import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { initApiConnection } from "./lib/api";
import "./styles/globals.css";

// 先显示加载提示，窗口立即可见
const root = document.getElementById("root")!;
root.innerHTML = `
  <div style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:system-ui">
    <div style="text-align:center">
      <div style="width:40px;height:40px;border:3px solid #e5e7eb;border-top-color:#3b82f6;border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 16px"></div>
      <p style="color:#374151;font-size:16px;font-weight:500">正在初始化，准备资源中...</p>
      <p style="color:#9ca3af;font-size:13px;margin-top:8px">首次启动可能需要 10-20 秒</p>
    </div>
  </div>
  <style>@keyframes spin{to{transform:rotate(360deg)}}</style>
`;

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
      </div>
    `;
  });
