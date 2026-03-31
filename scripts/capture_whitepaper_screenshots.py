"""
白皮书截图采集脚本
目标：采集 10 张白皮书截图，输出到 docs/whitepaper/assets/screenshots/
规格：1600x1000 视口，deviceScaleFactor=2，纯内容截图
"""

import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page

# ── 配置 ──────────────────────────────────────────────────────────────────────
BASE_URL = "http://localhost:5173"
OUT_DIR = Path("docs/whitepaper/assets/screenshots")

# 有全量已完成阶段数据的项目 ID（比价完成）
PROJECT_ID = "4caeb548-09c2-4000-8738-94c95d81e77f"

VIEWPORT = {"width": 1600, "height": 1000}
DEVICE_SCALE = 2

# ── 辅助函数 ─────────────────────────────────────────────────────────────────


def shot(page: Page, name: str):
    """保存截图到目标目录"""
    dest = OUT_DIR / name
    page.screenshot(path=str(dest))
    size = dest.stat().st_size
    print(f"  ✓  {name}  ({size // 1024} KB)")


def wait(page: Page, ms: int = 1500):
    page.wait_for_timeout(ms)


def navigate(page: Page, url: str):
    page.goto(url)
    page.wait_for_load_state("networkidle")
    wait(page, 1200)


def click_stage_tab(page: Page, label: str):
    """点击工作台阶段导航标签"""
    page.get_by_text(label, exact=True).first.click()
    page.wait_for_load_state("networkidle")
    wait(page, 1500)


# ── 主流程 ────────────────────────────────────────────────────────────────────


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=DEVICE_SCALE,
            locale="zh-CN",
        )
        page = context.new_page()

        # ── 01: 首页 / 最近项目列表 ────────────────────────────────────────────
        print("[01] 首页")
        navigate(page, f"{BASE_URL}/#/")
        shot(page, "01-home.png")

        # ── 02: 新建项目弹窗 ────────────────────────────────────────────────────
        print("[02] 新建项目弹窗")
        navigate(page, f"{BASE_URL}/#/")
        # 点击新建项目按钮
        page.get_by_text("新建项目").first.click()
        wait(page, 800)
        shot(page, "02-create-project-dialog.png")
        # 关闭弹窗（按 Escape）
        page.keyboard.press("Escape")
        wait(page, 400)

        # ── 03~07: 工作台各阶段 ────────────────────────────────────────────────
        print("[03-07] 工作台阶段截图")
        navigate(page, f"{BASE_URL}/#/project/{PROJECT_ID}")

        # 03: 导入文件阶段
        print("[03] 导入文件")
        click_stage_tab(page, "导入文件")
        shot(page, "03-import-stage.png")

        # 04: 标准化阶段
        print("[04] 标准化")
        click_stage_tab(page, "标准化")
        shot(page, "04-standardize-stage.png")

        # 05: 商品归组阶段
        print("[05] 商品归组")
        click_stage_tab(page, "商品归组")
        shot(page, "05-grouping-stage.png")

        # 06: 符合性审查阶段
        print("[06] 符合性审查")
        click_stage_tab(page, "符合性审查")
        shot(page, "06-compliance-stage.png")

        # 07: 比价导出阶段
        print("[07] 比价导出")
        click_stage_tab(page, "比价导出")
        shot(page, "07-comparison-stage.png")

        # ── 08: 规则管理 ───────────────────────────────────────────────────────
        print("[08] 规则管理")
        navigate(page, f"{BASE_URL}/#/rules")
        shot(page, "08-rule-management.png")

        # ── 09: 应用设置 ───────────────────────────────────────────────────────
        print("[09] 应用设置")
        navigate(page, f"{BASE_URL}/#/preferences")
        shot(page, "09-app-preferences.png")

        # ── 10: 导出结果 ───────────────────────────────────────────────────────
        print("[10] 导出结果")
        navigate(page, f"{BASE_URL}/#/project/{PROJECT_ID}")
        click_stage_tab(page, "比价导出")
        # 点击导出按钮，截取导出成功提示或结果状态
        export_btn = page.get_by_text("导出底稿").first
        if export_btn.is_visible():
            export_btn.click()
            wait(page, 2000)
        shot(page, "10-export-result.png")

        browser.close()

    print("\n全部截图采集完成。")
    files = list(OUT_DIR.glob("*.png"))
    print(f"共 {len(files)} 个 PNG 文件：")
    for f in sorted(files):
        print(f"  {f.name}  {f.stat().st_size // 1024} KB")


if __name__ == "__main__":
    os.chdir(Path(__file__).parent.parent)
    main()
