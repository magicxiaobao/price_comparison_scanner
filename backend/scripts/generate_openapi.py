#!/usr/bin/env python
"""
OpenAPI 契约自动生成脚本。
每次后端 API 路由变更后必须运行此脚本并提交 docs/api/openapi.json。

用法：
    cd backend
    python scripts/generate_openapi.py

输出：
    ../docs/api/openapi.json
"""
import json
import os
import sys
from pathlib import Path

# 确保 backend 目录在 import path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app  # noqa: E402


def main() -> None:
    spec = app.openapi()
    output_path = Path(__file__).parent.parent.parent / "docs" / "api" / "openapi.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 原子写入
    tmp_path = output_path.with_suffix(".tmp")
    data = json.dumps(spec, indent=2, ensure_ascii=False)
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    tmp_path.replace(output_path)

    # 汇总信息
    paths = list(spec.get("paths", {}).keys())
    print(f"✓ 已生成 openapi.json: {len(paths)} 个路径")
    for p in sorted(paths):
        methods = list(spec["paths"][p].keys())
        print(f"  {', '.join(m.upper() for m in methods):12s} {p}")


if __name__ == "__main__":
    main()
