"""
Price Comparison Scanner — OpenAPI MCP Server

监听后端自动导出的 openapi.json 文件，通过 watchdog 实时检测变化并重载。
为前端开发和团队协作提供接口契约查询服务。

环境变量：
  OPENAPI_PATH — openapi.json 文件路径（默认 项目根目录/docs/api/openapi.json）
"""

import atexit
import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from fastmcp import FastMCP
except ModuleNotFoundError:

    class FastMCP:  # type: ignore[no-redef]
        def __init__(self, *_a: Any, **_kw: Any) -> None:
            pass

        def tool(self):
            def _d(fn):
                return fn

            return _d

        def run(self) -> None:
            raise RuntimeError("fastmcp is not installed. Run `uv sync` first.")


try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except ModuleNotFoundError:
    FileSystemEventHandler = object  # type: ignore[assignment]
    Observer = None  # type: ignore[assignment]


# ─── 配置 ───
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OPENAPI_PATH = str(_PROJECT_ROOT / "docs" / "api" / "openapi.json")
OPENAPI_PATH = Path(os.getenv("OPENAPI_PATH", DEFAULT_OPENAPI_PATH))

# ─── 全局缓存 ───
_CACHE_LOCK = threading.RLock()
_SPEC_VERSION: Tuple[bool, int, int] = (False, -1, -1)
_SPEC: Dict[str, Any] = {}
_OPS: List[Dict[str, Any]] = []
_SCHEMA_INDEX: Dict[str, Any] = {}
_TAGS: List[str] = []
_WATCHER: Optional[Any] = None
_WATCHER_INITIALIZED = False

mcp = FastMCP("price-comparison-openapi")


# ─── 文件加载 ───


def _load_openapi() -> Dict[str, Any]:
    """从文件读取 OpenAPI JSON。"""
    if not OPENAPI_PATH.exists():
        return {"openapi": "3.0.0", "paths": {}, "components": {"schemas": {}}}
    data = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    return data


def _get_file_version() -> Tuple[bool, int, int]:
    """获取文件版本戳 (exists, mtime_ns, size)。"""
    try:
        stat = OPENAPI_PATH.stat()
        return True, stat.st_mtime_ns, stat.st_size
    except (FileNotFoundError, OSError):
        return False, 0, 0


# ─── 操作解析 ───


def _iter_operations(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """将 paths 扁平化为操作列表。"""
    ops: List[Dict[str, Any]] = []
    paths = spec.get("paths", {}) or {}

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, op in path_item.items():
            method_l = str(method).lower()
            if method_l not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            if not isinstance(op, dict):
                continue
            ops.append(
                {
                    "method": method_l.upper(),
                    "path": path,
                    "operationId": op.get("operationId"),
                    "summary": op.get("summary"),
                    "description": op.get("description"),
                    "tags": op.get("tags", []) or [],
                    "parameters": op.get("parameters", []) or [],
                    "requestBody": op.get("requestBody"),
                    "responses": op.get("responses", {}) or {},
                }
            )
    return ops


# ─── 搜索 ───


def _tokenize(text: str) -> List[str]:
    return [t for t in "".join(ch if ch.isalnum() else " " for ch in text).lower().split() if t]


def _search_ops(
    ops: List[Dict[str, Any]], query: str, tag: Optional[str] = None, limit: int = 20
) -> List[Dict[str, Any]]:
    q_tokens = set(_tokenize(query))
    results: List[Tuple[int, Dict[str, Any]]] = []

    for op in ops:
        if tag and tag not in op.get("tags", []):
            continue

        hay = " ".join(
            [
                op.get("method", ""),
                op.get("path", ""),
                str(op.get("operationId") or ""),
                str(op.get("summary") or ""),
                str(op.get("description") or ""),
                " ".join(op.get("tags", []) or []),
            ]
        )
        hay_tokens = set(_tokenize(hay))
        score = len(q_tokens & hay_tokens)

        if query.lower() in op.get("path", "").lower():
            score += 3
        operation_id = str(op.get("operationId") or "")
        if operation_id and query.lower() in operation_id.lower():
            score += 3

        if score > 0:
            results.append(
                (
                    score,
                    {
                        "method": op.get("method"),
                        "path": op.get("path"),
                        "operationId": op.get("operationId"),
                        "summary": op.get("summary"),
                        "tags": op.get("tags", []),
                        "score": score,
                    },
                )
            )

    results.sort(key=lambda x: x[0], reverse=True)
    return [r[1] for r in results[: max(1, min(limit, 100))]]


# ─── 缓存管理 ───


def _init_cache(force: bool = False) -> bool:
    """
    重载缓存。force=False 时仅在版本戳变化时重载。
    返回 True 表示成功重载。
    """
    global _SPEC, _OPS, _SCHEMA_INDEX, _TAGS, _SPEC_VERSION
    with _CACHE_LOCK:
        current_version = _get_file_version()
        if not force and current_version == _SPEC_VERSION:
            return False

        try:
            spec = _load_openapi()
        except Exception as exc:
            print(f"[WARN] Failed to reload OpenAPI spec from {OPENAPI_PATH}: {exc}")
            return False

        ops = _iter_operations(spec)
        components = spec.get("components", {}) or {}
        schemas = components.get("schemas", {}) or {}
        schema_index = schemas if isinstance(schemas, dict) else {}

        tag_set = set()
        for op in ops:
            for tag in op.get("tags", []):
                tag_set.add(str(tag))

        _SPEC = spec
        _OPS = ops
        _SCHEMA_INDEX = schema_index
        _TAGS = sorted(tag_set)
        _SPEC_VERSION = current_version
        return True


# ─── 文件监听 (watchdog) ───


class _OpenApiChangeHandler(FileSystemEventHandler):  # type: ignore[misc]
    def __init__(self, target_file: Path) -> None:
        super().__init__()
        self._target = target_file.resolve()

    def _is_target(self, file_path: str) -> bool:
        try:
            return Path(file_path).resolve() == self._target
        except Exception:
            return False

    def _reload_if_target(self, file_path: str) -> None:
        if self._is_target(file_path):
            _init_cache(force=True)

    def on_modified(self, event: Any) -> None:
        if not getattr(event, "is_directory", False):
            self._reload_if_target(getattr(event, "src_path", ""))

    def on_created(self, event: Any) -> None:
        if not getattr(event, "is_directory", False):
            self._reload_if_target(getattr(event, "src_path", ""))

    def on_deleted(self, event: Any) -> None:
        if not getattr(event, "is_directory", False):
            self._reload_if_target(getattr(event, "src_path", ""))

    def on_moved(self, event: Any) -> None:
        if getattr(event, "is_directory", False):
            return
        self._reload_if_target(getattr(event, "src_path", ""))
        self._reload_if_target(getattr(event, "dest_path", ""))


def _stop_file_watcher() -> None:
    global _WATCHER
    if _WATCHER is None:
        return
    _WATCHER.stop()
    _WATCHER.join(timeout=2)
    _WATCHER = None


def _start_file_watcher() -> bool:
    global _WATCHER
    if Observer is None:
        return False
    if _WATCHER is not None:
        return True

    try:
        watch_dir = OPENAPI_PATH.resolve().parent
        if not watch_dir.exists():
            watch_dir.mkdir(parents=True, exist_ok=True)

        observer = Observer()
        observer.schedule(_OpenApiChangeHandler(OPENAPI_PATH), path=str(watch_dir), recursive=False)
        observer.start()
        _WATCHER = observer
        atexit.register(_stop_file_watcher)
        return True
    except Exception as exc:
        print(f"[WARN] Failed to start OpenAPI watcher: {exc}")
        return False


def _ensure_watcher_initialized() -> None:
    global _WATCHER_INITIALIZED
    if _WATCHER_INITIALIZED:
        return
    _WATCHER_INITIALIZED = True
    _start_file_watcher()


# 启动时加载
_init_cache(force=True)


# ─── MCP Tools ───


@mcp.tool()
def reload_spec() -> str:
    """强制重新加载 openapi.json 到内存缓存。后端 API 变更后调用此工具刷新。"""
    _ensure_watcher_initialized()
    if _init_cache(force=True):
        with _CACHE_LOCK:
            n = len(_OPS)
        return f"已重新加载，共 {n} 个 API 操作。文件: {OPENAPI_PATH}"
    return f"加载失败，请确认文件存在: {OPENAPI_PATH}"


@mcp.tool()
def list_tags() -> List[str]:
    """列出所有 API 标签（对应后端 router 分组）。"""
    _ensure_watcher_initialized()
    _init_cache(force=False)
    with _CACHE_LOCK:
        return list(_TAGS)


@mcp.tool()
def list_operations(tag: Optional[str] = None) -> List[Dict[str, str]]:
    """列出所有 API 操作的摘要。可按 tag 过滤。返回 method、path、summary。"""
    _ensure_watcher_initialized()
    _init_cache(force=False)
    with _CACHE_LOCK:
        ops = list(_OPS)

    result = []
    for op in ops:
        if tag and tag not in op.get("tags", []):
            continue
        result.append(
            {
                "method": op["method"],
                "path": op["path"],
                "summary": op.get("summary") or "",
                "tags": ", ".join(op.get("tags", [])),
            }
        )
    return result


@mcp.tool()
def search_operations(query: str, tag: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    """按关键字搜索 API 操作。搜索范围: method/path/operationId/summary/description/tags。"""
    _ensure_watcher_initialized()
    _init_cache(force=False)
    with _CACHE_LOCK:
        ops = list(_OPS)
    return _search_ops(ops, query=query, tag=tag, limit=limit)


@mcp.tool()
def get_operation(method: str, path: str) -> Dict[str, Any]:
    """获取完整的 API 操作定义，包含 parameters、requestBody、responses。用于前后端接口对接。"""
    _ensure_watcher_initialized()
    _init_cache(force=False)
    m = method.strip().upper()
    with _CACHE_LOCK:
        ops = list(_OPS)

    for op in ops:
        if op["method"] == m and op["path"] == path:
            return op
    return {"error": "NOT_FOUND", "method": m, "path": path}


@mcp.tool()
def get_schema(name: str) -> Dict[str, Any]:
    """获取 components.schemas 中的数据模型定义。用于了解请求/响应的数据结构。"""
    _ensure_watcher_initialized()
    _init_cache(force=False)
    key = name.strip()
    with _CACHE_LOCK:
        schema = _SCHEMA_INDEX.get(key)
    if schema is None:
        with _CACHE_LOCK:
            candidates = [k for k in _SCHEMA_INDEX if key.lower() in k.lower()]
        if candidates:
            return {"error": "NOT_FOUND", "hint": f"类似的 schema: {', '.join(candidates[:5])}"}
        return {"error": "NOT_FOUND", "schema": key}
    return {"name": key, "schema": schema}


@mcp.tool()
def list_schemas() -> List[str]:
    """列出所有可用的数据模型名称 (components.schemas)。"""
    _ensure_watcher_initialized()
    _init_cache(force=False)
    with _CACHE_LOCK:
        return sorted(_SCHEMA_INDEX.keys())


@mcp.tool()
def get_api_summary() -> Dict[str, Any]:
    """获取 API 概览：标题、版本、操作数量、标签分布。用于快速了解后端接口全貌。"""
    _ensure_watcher_initialized()
    _init_cache(force=False)
    with _CACHE_LOCK:
        info = _SPEC.get("info", {})
        ops = list(_OPS)
        schema_count = len(_SCHEMA_INDEX)

    tag_counts: Dict[str, int] = {}
    for op in ops:
        for t in op.get("tags", []):
            tag_counts[t] = tag_counts.get(t, 0) + 1

    return {
        "title": info.get("title", ""),
        "version": info.get("version", ""),
        "total_operations": len(ops),
        "total_schemas": schema_count,
        "tags": tag_counts,
        "source": str(OPENAPI_PATH),
    }


if __name__ == "__main__":
    _ensure_watcher_initialized()
    mcp.run()
