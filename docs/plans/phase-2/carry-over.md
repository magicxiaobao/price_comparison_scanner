# Phase 2 Carry-Over：Phase 1 遗留项承接

> 本文档收录 Phase 1 审查（R1-R5）及用户复核中确认的非阻塞遗留项。
> 按影响程度分为三级，Phase 2 执行时依此决定处理时机。

---

## 1. 必带项（Phase 2 开工前或对应 Wave 中必须修复）

| ID | 描述 | 影响 | 处理时机 | 状态 |
|----|------|------|----------|------|
| **B4** | `python-multipart` 未列入 `backend/requirements.txt` 正式依赖 | 缺少时 FastAPI 的 `UploadFile` 路由注册报错，后端无法启动 | **Preflight 验证** | ✅ 已修复 — `requirements.txt:3` 已有 `python-multipart==0.0.20`，Preflight 时确认在位即可 |
| **B2** | `api/tasks.py:8-9` 的 `get_task_status` 缺少 `response_model=TaskStatusResponse` | openapi.json 中该路由响应 schema 为空对象 `{}`，前端无法从契约获取字段定义 | **Preflight** | 待修 |
| **B3** | `db/table_repo.py:26-51` 返回的 `raw_data` 是 JSON 字符串而非 JSON 对象（存入 `json.dumps` 但读出未 `json.loads`） | Phase 2 标准化引擎直接消费此数据，依赖框架隐式转换不可靠 | **Preflight** | 待修 |
| **F1** | `supplier-confirm-dialog.tsx:23` 的 `useState(suggestedName)` 仅首次渲染取值，缺少 `useEffect` 同步 prop 变化 | 组件保持 mounted 时重开对话框显示旧名称，用户可能确认错误的供应商名称 | **Preflight** | 待修 |

---

## 2. 建议顺手处理（不阻塞开工，但建议在 Phase 2 各 Wave 中穿插修复）

| ID | 描述 | 影响 | 建议时机 |
|----|------|------|----------|
| **B1** | `TaskInfo` 改为 `@dataclass` + `get_status()` 返回浅拷贝 | 调用方在锁外修改内部引用存在竞态隐患，当前路径可控 | 后端任意 Wave 中顺手改 |
| **F2** | `startPolling` 的 catch 块为空，轮询失败时用户无感知 | 长时间网络断开时 UI 静默 | 前端任意 Wave 中顺手改 |
| **F3** | 汇总信息用 `confirmedFiles` 代替 `uniqueSuppliers.size`，语义不同 | 两个文件同一供应商时计数偏差 | 前端任意 Wave 中顺手改 |

---

## 3. 仅记录，不纳入本轮验收

| ID | 描述 | 说明 |
|----|------|------|
| **B5** | PDF 测试断言可加强为 `assert len(results) == 1` | 提升 pdfplumber 行为退化检测，非功能缺陷 |
| **L1** | Word 合并单元格不做特殊处理（python-docx 产生重复单元格） | MVP 已知限制，后续 Phase 评估 |
| **L2** | 三种解析器空白检测代码路径不同但行为一致 | 记录备忘，无功能影响 |
| **L3** | `FileService` 每次方法调用创建新 `Database` 实例 | 少量性能开销，MVP 可接受 |

---

## 来源追溯

| ID | 审查轮次 | 原始发现者 |
|----|----------|-----------|
| B1 | R1 | reviewer |
| B2 | R1 + R3 | reviewer |
| B3 | R3 | reviewer |
| B4 | R3 | reviewer |
| B5 | R2 | reviewer |
| F1 | 用户复核 P2 | 用户 |
| F2 | R4 | reviewer |
| F3 | R5 | reviewer |
| L1 | R2 | reviewer |
| L2 | R2 | reviewer |
| L3 | R3 | reviewer |
