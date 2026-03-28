import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { initApiConnection } from "./lib/api";
import "./styles/globals.css";

initApiConnection()
  .then(() => {
    ReactDOM.createRoot(document.getElementById("root")!).render(
      <React.StrictMode>
        <App />
      </React.StrictMode>,
    );
  })
  .catch((err) => {
    const root = document.getElementById("root");
    if (root) {
      root.innerHTML = `
        <div style="padding:48px;text-align:center;font-family:system-ui">
          <h2>后端服务连接失败</h2>
          <p style="color:#666">无法连接到后端 sidecar 服务，请重启应用。</p>
          <p style="color:#999;font-size:12px">${String(err)}</p>
        </div>
      `;
    }
  });
