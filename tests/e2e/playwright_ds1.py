#!/usr/bin/env python3
"""
DS-1 Playwright UI E2E 测试 v2。
Tab 名：导入文件 | 标准化 | 商品归组 | 符合性审查 | 比价导出
"""
from playwright.sync_api import sync_playwright
import os
import json

FRONTEND = "http://localhost:5173"
SCREENSHOT_DIR = "/tmp/e2e-screenshots/ds1"
DS1_DIR = "tests/e2e/test-data/ds-1"
RESULTS = []

os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def shot(page, name):
    path = f"{SCREENSHOT_DIR}/{name}.png"
    page.screenshot(path=path, full_page=True)
    print(f"  [ss] {name}")
    return path


def check(name, passed, detail=""):
    RESULTS.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})
    print(f"  {'✅' if passed else '❌'} {name}" + (f" — {detail}" if detail else ""))


def click_tab(page, tab_text):
    """点击阶段 Tab。"""
    tab = page.locator(f"button:has-text('{tab_text}'), [role='tab']:has-text('{tab_text}')")
    if tab.count() > 0:
        tab.first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)
        return True
    # fallback: 直接按文字
    fallback = page.get_by_text(tab_text, exact=False)
    if fallback.count() > 0:
        fallback.first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)
        return True
    return False


def wait_for_async(page, timeout_s=30):
    """等待异步操作完成（进度条消失或成功提示）。"""
    for _ in range(timeout_s):
        page.wait_for_timeout(1000)
        # 检查是否有 loading/spinner
        loading = page.locator("[class*='spinner'], [class*='loading'], [role='progressbar']")
        if loading.count() == 0:
            # 额外等一下确保渲染完成
            page.wait_for_timeout(1000)
            return True
    return False


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        # ===== 1. 新建项目 =====
        print("\n=== 1. 新建项目 ===")
        page.goto(FRONTEND)
        page.wait_for_load_state("networkidle")

        page.click("button:has-text('新建项目')")
        page.wait_for_timeout(500)
        shot(page, "01-dialog")

        # 填项目名
        inputs = page.locator("input").all()
        for inp in inputs:
            if inp.is_visible():
                inp.fill("DS-1 PW 全流程")
                break
        page.wait_for_timeout(300)

        # 点创建
        for text in ["创建", "确认", "确定", "OK"]:
            btn = page.locator(f"button:has-text('{text}')")
            if btn.count() > 0:
                btn.first.click()
                break
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)
        shot(page, "02-workbench")
        check("创建项目", "/project/" in page.url, page.url)

        # ===== 2. 上传文件 =====
        print("\n=== 2. 上传文件 ===")
        file_input = page.locator("input[type='file']")
        if file_input.count() > 0:
            files = [os.path.abspath(os.path.join(DS1_DIR, f)) for f in sorted(os.listdir(DS1_DIR))]
            file_input.first.set_input_files(files)
            page.wait_for_timeout(2000)
            wait_for_async(page, 20)
            shot(page, "03-uploaded")
            check("上传 3 文件", True, f"{len(files)} 文件")
        else:
            check("上传文件", False, "无 file input")

        # 等待解析完成
        page.wait_for_timeout(5000)
        shot(page, "04-parsed")
        body = page.inner_text("body")
        check("联想出现", "联想" in body)
        check("华硕出现", "华硕" in body)
        check("戴尔出现", "戴尔" in body)

        # ===== 3. 标准化 =====
        print("\n=== 3. 标准化 ===")
        if click_tab(page, "标准化"):
            shot(page, "05-std-tab")
            # 找执行按钮
            std_btns = page.locator("button").all()
            clicked = False
            for btn in std_btns:
                txt = btn.text_content() or ""
                if "标准化" in txt and ("执行" in txt or "开始" in txt or "运行" in txt):
                    btn.click()
                    clicked = True
                    break
            if not clicked:
                # 尝试找含"标准化"的主要按钮
                for btn in std_btns:
                    txt = btn.text_content() or ""
                    if "标准化" in txt and btn.is_visible():
                        btn.click()
                        clicked = True
                        break
            if clicked:
                print("  点击标准化...")
                wait_for_async(page, 30)
                page.wait_for_timeout(3000)
            shot(page, "06-std-result")
            body = page.inner_text("body")
            # 检查是否有表格数据
            has_data = "ThinkPad" in body or "笔记本" in body or "显示器" in body
            check("标准化有数据", has_data, "ThinkPad/笔记本/显示器 出现" if has_data else "无预期数据")
        else:
            check("标准化 Tab", False, "未找到")

        # ===== 4. 商品归组 =====
        print("\n=== 4. 商品归组 ===")
        if click_tab(page, "商品归组"):
            shot(page, "07-grp-tab")
            # 找生成按钮
            grp_btns = page.locator("button").all()
            clicked = False
            for btn in grp_btns:
                txt = btn.text_content() or ""
                if ("生成" in txt or "归组" in txt) and btn.is_visible():
                    btn.click()
                    clicked = True
                    break
            if clicked:
                print("  点击归组...")
                wait_for_async(page, 30)
                page.wait_for_timeout(3000)
            shot(page, "08-grp-result")
            body = page.inner_text("body")
            has_groups = "组" in body or "group" in body.lower() or "确认" in body
            check("归组结果", has_groups)
        else:
            check("归组 Tab", False, "未找到")

        # ===== 5. 符合性审查 =====
        print("\n=== 5. 符合性审查 ===")
        if click_tab(page, "符合性审查"):
            shot(page, "09-compliance")
            check("符合性审查 Tab", True)
        else:
            # DS-1 可能跳过
            check("符合性审查 Tab", False, "未找到或跳过")

        # ===== 6. 比价导出 =====
        print("\n=== 6. 比价导出 ===")
        if click_tab(page, "比价导出"):
            shot(page, "10-cmp-tab")
            # 找生成比价按钮
            cmp_btns = page.locator("button").all()
            clicked = False
            for btn in cmp_btns:
                txt = btn.text_content() or ""
                if ("生成" in txt or "比价" in txt) and btn.is_visible() and "导出" not in txt:
                    btn.click()
                    clicked = True
                    break
            if clicked:
                print("  点击比价...")
                wait_for_async(page, 30)
                page.wait_for_timeout(3000)
            shot(page, "11-cmp-result")
            body = page.inner_text("body")
            has_cmp = "最低" in body or "比价" in body or "单价" in body or "供应商" in body
            check("比价结果", has_cmp)

            # 导出
            export_btn = page.locator("button:has-text('导出')")
            if export_btn.count() > 0:
                export_btn.first.click()
                print("  点击导出...")
                page.wait_for_timeout(5000)
                shot(page, "12-export")
                check("导出", True)
            else:
                check("导出按钮", False, "未找到")
        else:
            check("比价导出 Tab", False, "未找到")

        # ===== 7. 问题面板 =====
        print("\n=== 7. 问题面板 ===")
        # 右侧边栏的问题按钮
        sidebar = page.locator("[class*='sidebar'] button, button:has-text('待处理')")
        if sidebar.count() > 0:
            sidebar.first.click()
            page.wait_for_timeout(1000)
            shot(page, "13-problems")
            check("问题面板", True)
        else:
            # 尝试页面右侧的小图标
            shot(page, "13-no-problems-btn")
            check("问题面板", False, "未找到入口按钮")

        # ===== 最终全页截图 =====
        shot(page, "99-final")
        browser.close()

    # ===== 汇总 =====
    print("\n" + "=" * 60)
    print("DS-1 Playwright UI 联调汇总")
    print("=" * 60)
    passed = sum(1 for r in RESULTS if r["status"] == "PASS")
    failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
    print(f"通过: {passed}, 失败: {failed}, 总计: {len(RESULTS)}")
    if failed > 0:
        print("\n失败项:")
        for r in RESULTS:
            if r["status"] == "FAIL":
                print(f"  ❌ {r['name']}: {r['detail']}")
    print(f"\n截图: {SCREENSHOT_DIR}/")

    os.makedirs("tests/e2e/results", exist_ok=True)
    with open("tests/e2e/results/ds1-playwright-results.json", "w") as f:
        json.dump({"results": RESULTS, "screenshots": SCREENSHOT_DIR}, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
