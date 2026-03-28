#!/usr/bin/env python3
"""
DS-1 E2E API 自动化检查脚本 v2。
修正为实际 API 路径（从 openapi.json / 路由表确认）。
"""
import json
import time
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

BASE = "http://127.0.0.1:17396"
RESULTS: list[dict[str, Any]] = []


def api(method: str, path: str, data: Any = None, files: dict | None = None) -> tuple[int, Any]:
    url = f"{BASE}{path}"
    if files:
        import mimetypes
        boundary = "----E2EBoundary"
        body = b""
        for field_name, (fname, fdata) in files.items():
            ct = mimetypes.guess_type(fname)[0] or "application/octet-stream"
            body += f"--{boundary}\r\n".encode()
            body += f'Content-Disposition: form-data; name="{field_name}"; filename="{fname}"\r\n'.encode()
            body += f"Content-Type: {ct}\r\n\r\n".encode()
            body += fdata + b"\r\n"
        body += f"--{boundary}--\r\n".encode()
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    elif data is not None:
        body_bytes = json.dumps(data).encode()
        req = urllib.request.Request(url, data=body_bytes, method=method)
        req.add_header("Content-Type", "application/json")
    else:
        req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw


def check(name: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    RESULTS.append({"name": name, "status": status, "detail": detail})
    icon = "✅" if passed else "❌"
    print(f"  {icon} {name}" + (f" — {detail}" if detail else ""))


def wait_task(task_id: str, timeout: int = 60) -> dict:
    for _ in range(timeout * 2):
        code, resp = api("GET", f"/api/tasks/{task_id}/status")
        if code != 200:
            time.sleep(0.5)
            continue
        st = resp.get("status")
        if st in ("completed", "failed"):
            return resp
        time.sleep(0.5)
    return {"status": "timeout"}


def get_task_id(resp: Any) -> str | None:
    """从响应中提取 task_id（兼容 task_id 和 taskId）。"""
    if isinstance(resp, dict):
        return resp.get("task_id") or resp.get("taskId")
    return None


def main():
    ds1_dir = Path("tests/e2e/test-data/ds-1")
    if not ds1_dir.exists():
        print("ERROR: DS-1 测试数据不存在")
        sys.exit(1)

    # ===== 0. Health =====
    print("\n=== 0. 健康检查 ===")
    code, resp = api("GET", "/api/health")
    check("health API", code == 200 and resp.get("status") == "ok", f"{code} {resp}")

    # ===== 1. 创建项目 =====
    print("\n=== 1. 创建项目 ===")
    code, proj = api("POST", "/api/projects", {"name": "DS-1 E2E 测试", "description": "IT办公设备标准场景"})
    check("创建项目", code == 200 and "id" in proj, f"{code}")
    if code != 200:
        print(f"FATAL: {proj}")
        sys.exit(1)
    pid = proj["id"]
    print(f"  项目ID: {pid}")

    # ===== 2. 上传文件（POST /api/projects/{pid}/files）=====
    print("\n=== 2. 上传文件 ===")
    upload_task_ids = []
    for fname in sorted(os.listdir(ds1_dir)):
        fpath = ds1_dir / fname
        with open(fpath, "rb") as f:
            fdata = f.read()
        code, resp = api("POST", f"/api/projects/{pid}/files", files={"file": (fname, fdata)})
        tid = get_task_id(resp)
        success = code == 200 and tid is not None
        check(f"上传 {fname}", success, f"{code}, task={tid[:8] if tid else 'N/A'}...")
        if tid:
            upload_task_ids.append(tid)

    # ===== 3. 等待解析完成 =====
    print("\n=== 3. 等待文件解析 ===")
    for tid in upload_task_ids:
        result = wait_task(tid, timeout=30)
        check(f"解析 {tid[:8]}...", result.get("status") == "completed", result.get("status", "?"))

    # ===== 4. 查看文件列表 =====
    print("\n=== 4. 文件列表 ===")
    code, files = api("GET", f"/api/projects/{pid}/files")
    file_count = len(files) if isinstance(files, list) else 0
    check("获取文件列表", code == 200 and file_count == 3, f"{code}, 文件数={file_count}")
    if isinstance(files, list):
        for f in files:
            tables = f.get("tables", [])
            print(f"    {f['original_filename']} — 供应商: {f.get('supplier_name','?')}, 表格: {len(tables)}")

    # ===== 5. 选择表格（PUT /api/tables/{table_id}/toggle-selection）=====
    print("\n=== 5. 选择表格 ===")
    code, all_tables = api("GET", f"/api/projects/{pid}/tables")
    if code == 200 and isinstance(all_tables, list):
        for t in all_tables:
            tid_t = t.get("id") or t.get("table_id")
            if tid_t and not t.get("selected", False):
                c2, r2 = api("PUT", f"/api/tables/{tid_t}/toggle-selection")
                check(f"选择表格 {t.get('sheet_name','?')}", c2 == 200, f"{c2}")
            else:
                check(f"表格 {t.get('sheet_name','?')} 已选中", True, "skip")
    else:
        check("获取表格列表", False, f"{code}")

    # ===== 6. 标准化（POST /api/projects/{pid}/standardize）=====
    print("\n=== 6. 标准化 ===")
    code, resp = api("POST", f"/api/projects/{pid}/standardize")
    tid = get_task_id(resp)
    if code == 200 and tid:
        check("触发标准化", True, f"task={tid[:8]}...")
        result = wait_task(tid, timeout=60)
        check("标准化完成", result.get("status") == "completed", result.get("status", "?"))
    else:
        check("触发标准化", False, f"{code} {str(resp)[:200]}")

    # 查看标准化行
    code, rows = api("GET", f"/api/projects/{pid}/standardized-rows")
    row_count = len(rows) if isinstance(rows, list) else 0
    check("获取标准化行", code == 200 and row_count > 0, f"{code}, {row_count} 行")

    # 查看列映射信息
    code, mappings = api("GET", f"/api/projects/{pid}/column-mapping-info")
    check("获取列映射信息", code == 200, f"{code}")
    if code == 200 and isinstance(mappings, list):
        auto_mapped = sum(1 for m in mappings if m.get("mapped_field"))
        total = len(mappings)
        print(f"    映射情况: {auto_mapped}/{total} 列已映射")

    # ===== 7. 归组 =====
    print("\n=== 7. 归组 ===")
    code, resp = api("POST", f"/api/projects/{pid}/grouping/generate")
    tid = get_task_id(resp)
    if code == 200 and tid:
        check("触发归组", True, f"task={tid[:8]}...")
        result = wait_task(tid, timeout=60)
        check("归组完成", result.get("status") == "completed", result.get("status", "?"))
    elif code == 200:
        check("触发归组", True, "同步完成")
    else:
        check("触发归组", False, f"{code} {str(resp)[:200]}")

    # 查看归组结果
    code, groups = api("GET", f"/api/projects/{pid}/groups")
    group_count = len(groups) if isinstance(groups, list) else 0
    check("获取归组列表", code == 200 and group_count > 0, f"{code}, {group_count} 组")
    if isinstance(groups, list):
        for g in groups:
            members = g.get("members", [])
            print(f"    {g.get('group_name','?')} — 置信度: {g.get('confidence_level','?')}, 成员: {len(members)}")

    # 逐个确认归组（PUT /api/groups/{gid}/confirm）
    print("\n=== 7b. 确认归组 ===")
    if isinstance(groups, list):
        for g in groups:
            gid = g.get("id") or g.get("group_id")
            if gid:
                c2, r2 = api("PUT", f"/api/groups/{gid}/confirm")
                check(f"确认组 {g.get('group_name','?')[:10]}", c2 == 200, f"{c2}")

    # ===== 8. 比价 =====
    print("\n=== 8. 比价 ===")
    code, resp = api("POST", f"/api/projects/{pid}/comparison/generate")
    tid = get_task_id(resp)
    if code == 200 and tid:
        check("触发比价", True, f"task={tid[:8]}...")
        result = wait_task(tid, timeout=60)
        check("比价完成", result.get("status") == "completed", result.get("status", "?"))
    elif code == 200:
        check("触发比价", True, "同步完成")
    else:
        check("触发比价", False, f"{code} {str(resp)[:200]}")

    # 查看比价结果
    code, comparison = api("GET", f"/api/projects/{pid}/comparison")
    check("获取比价结果", code == 200, f"{code}")
    if code == 200 and isinstance(comparison, dict):
        items = comparison.get("items") or comparison.get("groups") or comparison.get("comparison_items") or []
        if isinstance(items, list):
            print(f"    比价项数: {len(items)}")
            for it in items[:3]:
                print(f"      {json.dumps(it, ensure_ascii=False)[:150]}")

    # ===== 9. 导出 =====
    print("\n=== 9. 导出 ===")
    code, resp = api("POST", f"/api/projects/{pid}/export")
    tid = get_task_id(resp)
    if code == 200 and tid:
        check("触发导出", True, f"task={tid[:8]}...")
        result = wait_task(tid, timeout=60)
        check("导出完成", result.get("status") == "completed", result.get("status", "?"))
        if result.get("result"):
            print(f"    导出结果: {json.dumps(result['result'], ensure_ascii=False)[:300]}")
    elif code == 200:
        check("触发导出", True, "同步完成")
    else:
        check("触发导出", False, f"{code} {str(resp)[:200]}")

    # ===== 10. Problems =====
    print("\n=== 10. 问题清单 ===")
    code, problems = api("GET", f"/api/projects/{pid}/problems")
    check("获取问题清单", code == 200, f"{code}, {len(problems) if isinstance(problems, list) else '?'} 组")

    # ===== 汇总 =====
    print("\n" + "=" * 60)
    print("DS-1 API 联调汇总")
    print("=" * 60)
    passed = sum(1 for r in RESULTS if r["status"] == "PASS")
    failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
    print(f"通过: {passed}, 失败: {failed}, 总计: {len(RESULTS)}")
    if failed > 0:
        print("\n失败项:")
        for r in RESULTS:
            if r["status"] == "FAIL":
                print(f"  ❌ {r['name']}: {r['detail']}")

    with open("tests/e2e/results/ds1-api-results.json", "w") as f:
        json.dump({"project_id": pid, "results": RESULTS, "summary": {"passed": passed, "failed": failed}}, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: tests/e2e/results/ds1-api-results.json")


if __name__ == "__main__":
    os.makedirs("tests/e2e/results", exist_ok=True)
    main()
