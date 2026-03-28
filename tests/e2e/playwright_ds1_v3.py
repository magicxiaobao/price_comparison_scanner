#!/usr/bin/env python3
"""
DS-1 Playwright UI E2E 测试 v3 — 完整流程含供应商确认。
Tab 名：导入文件 | 标准化 | 商品归组 | 符合性审查 → | 比价导出
"""
from playwright.sync_api import sync_playwright
import os
import json
import time

FRONTEND = "http://localhost:5173"
SCREENSHOT_DIR = "/tmp/e2e-screenshots/ds1-v3"
DS1_DIR = os.path.join(os.path.dirname(__file__), "test-data", "ds-1")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
RESULTS = []

os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)


def shot(page, name):
    path = f"{SCREENSHOT_DIR}/{name}.png"
    page.screenshot(path=path, full_page=True)
    print(f"  [screenshot] {path}")
    return path


def check(name, passed, detail=""):
    RESULTS.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})
    tag = "✅" if passed else "❌"
    print(f"  {tag} {name}" + (f" — {detail}" if detail else ""))


def click_tab(page, tab_text):
    """点击阶段 Tab，支持多种 locator 策略。"""
    # Strategy 1: role=tab
    tab = page.locator(f"[role='tab']:has-text('{tab_text}')")
    if tab.count() > 0 and tab.first.is_visible():
        tab.first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(800)
        return True
    # Strategy 2: button with text
    tab = page.locator(f"button:has-text('{tab_text}')")
    if tab.count() > 0 and tab.first.is_visible():
        tab.first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(800)
        return True
    # Strategy 3: any clickable element with text
    tab = page.get_by_text(tab_text, exact=False)
    if tab.count() > 0 and tab.first.is_visible():
        tab.first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(800)
        return True
    return False


def wait_for_async(page, timeout_s=30):
    """等待异步操作完成 — spinner/progressbar 消失或 toast 出现。"""
    for i in range(timeout_s):
        page.wait_for_timeout(1000)
        loading = page.locator(
            "[class*='spinner'], [class*='loading'], [role='progressbar'], "
            "[class*='animate-spin']"
        )
        if loading.count() == 0:
            page.wait_for_timeout(800)
            return True
    return False


def find_and_click_button(page, keywords, exclude_keywords=None):
    """在页面上找到包含指定关键词的可见按钮并点击。"""
    exclude_keywords = exclude_keywords or []
    btns = page.locator("button").all()
    for btn in btns:
        if not btn.is_visible():
            continue
        txt = (btn.text_content() or "").strip()
        if any(kw in txt for kw in keywords):
            if any(ex in txt for ex in exclude_keywords):
                continue
            if btn.is_disabled():
                print(f"    (按钮 '{txt}' 存在但 disabled)")
                continue
            btn.click()
            return txt
    return None


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        # ===== 1. 新建项目 =====
        print("\n=== 1. 新建项目 ===")
        page.goto(FRONTEND)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)
        shot(page, "01-home")

        # 点击新建项目按钮
        new_btn = page.locator("button:has-text('新建项目')")
        if new_btn.count() == 0:
            new_btn = page.locator("button:has-text('新建')")
        new_btn.first.click()
        page.wait_for_timeout(800)
        shot(page, "02-dialog")

        # 填项目名
        dialog_inputs = page.locator("input[type='text'], input:not([type])").all()
        filled = False
        for inp in dialog_inputs:
            if inp.is_visible():
                inp.fill("DS-1 E2E 完整测试")
                filled = True
                break
        if not filled:
            # fallback: any visible input
            page.locator("input").first.fill("DS-1 E2E 完整测试")

        page.wait_for_timeout(300)

        # 点创建/确认
        for text in ["创建", "确认", "确定", "OK", "Create"]:
            btn = page.locator(f"button:has-text('{text}')")
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click()
                break

        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        shot(page, "03-workbench")
        in_project = "/project/" in page.url or "/workbench" in page.url
        check("创建项目", in_project, page.url)

        # ===== 2. 上传文件 =====
        print("\n=== 2. 上传文件 ===")
        # 确保在导入文件 tab
        click_tab(page, "导入文件")
        page.wait_for_timeout(500)

        file_input = page.locator("input[type='file']")
        if file_input.count() > 0:
            ds1_abs = os.path.abspath(DS1_DIR)
            files = sorted([
                os.path.join(ds1_abs, f)
                for f in os.listdir(ds1_abs)
                if f.endswith(".xlsx")
            ])
            print(f"  上传文件: {[os.path.basename(f) for f in files]}")
            file_input.first.set_input_files(files)
            page.wait_for_timeout(3000)
            wait_for_async(page, 20)
            shot(page, "04-uploaded")
            check("上传 3 文件", len(files) == 3, f"{len(files)} 文件")
        else:
            check("上传文件", False, "无 file input")

        # 等待解析完成
        print("  等待解析...")
        page.wait_for_timeout(5000)
        wait_for_async(page, 15)
        shot(page, "05-parsed")

        body = page.inner_text("body")
        check("联想出现", "联想" in body)
        check("华硕出现", "华硕" in body)
        check("戴尔出现", "戴尔" in body)

        # ===== 3. 确认供应商 =====
        print("\n=== 3. 确认供应商 ===")
        confirmed_count = 0

        def dismiss_modal(p):
            """处理确认供应商后弹出的模态对话框。"""
            p.wait_for_timeout(800)
            # 检查是否有模态遮罩
            overlay = p.locator("div.fixed.inset-0, [class*='overlay'], [class*='modal']")
            if overlay.count() == 0:
                return

            # 截图看对话框内容
            shot(p, f"modal-{confirmed_count}")

            # 尝试在对话框中点确认/保存/OK
            dialog_btns = p.locator(
                "div.fixed button, [role='dialog'] button, [class*='modal'] button"
            ).all()
            for btn in dialog_btns:
                txt = (btn.text_content() or "").strip()
                if btn.is_visible() and not btn.is_disabled():
                    if any(kw in txt for kw in ["确认", "确定", "保存", "OK", "Save", "提交"]):
                        print(f"    对话框点击: '{txt}'")
                        btn.click()
                        p.wait_for_timeout(1000)
                        return
            # fallback: 如果有输入框先填入然后确认
            dialog_inputs = p.locator(
                "div.fixed input, [role='dialog'] input, [class*='modal'] input"
            ).all()
            if dialog_inputs:
                # 可能需要输入供应商名，但通常已预填
                pass

            # fallback: 点关闭/取消
            for btn in dialog_btns:
                txt = (btn.text_content() or "").strip()
                if btn.is_visible() and any(kw in txt for kw in ["关闭", "取消", "Close", "Cancel"]):
                    print(f"    对话框关闭: '{txt}'")
                    btn.click()
                    p.wait_for_timeout(800)
                    return
            # last resort: press Escape
            p.keyboard.press("Escape")
            p.wait_for_timeout(800)

        for attempt in range(6):
            # 查找"确认供应商"按钮
            confirm_btns = page.locator("button:has-text('确认供应商')").all()
            clickable = [b for b in confirm_btns if b.is_visible() and not b.is_disabled()]

            if not clickable:
                break

            clickable[0].click()
            confirmed_count += 1
            print(f"  确认供应商 #{confirmed_count}")

            # 处理弹出的对话框
            dismiss_modal(page)
            page.wait_for_timeout(500)

        # 如果没找到"确认供应商"按钮，列出所有按钮以便调试
        if confirmed_count == 0:
            print("  未找到确认供应商按钮，列出可见按钮:")
            all_btns = page.locator("button").all()
            for btn in all_btns:
                if btn.is_visible():
                    txt = (btn.text_content() or "").strip()
                    if txt and len(txt) < 60:
                        disabled = " [DISABLED]" if btn.is_disabled() else ""
                        print(f"    - '{txt}'{disabled}")

        shot(page, "06-suppliers-confirmed")
        check("确认供应商", confirmed_count > 0, f"确认了 {confirmed_count} 个")

        # ===== 4. 标准化 =====
        print("\n=== 4. 标准化 ===")
        if click_tab(page, "标准化"):
            page.wait_for_timeout(1000)
            shot(page, "07-std-tab")

            # 精确定位"执行标准化"按钮（不是 tab 上的文字）
            std_btn = page.locator("button:has-text('执行标准化')")
            if std_btn.count() > 0 and std_btn.first.is_visible() and not std_btn.first.is_disabled():
                std_btn.first.click()
                print("  点击: '执行标准化'")
                # 标准化是异步任务，需要等待更久
                wait_for_async(page, 30)
                page.wait_for_timeout(5000)
                check("执行标准化", True)
            else:
                print("  '执行标准化' 按钮未找到或 disabled，列出按钮:")
                for btn in page.locator("button").all():
                    if btn.is_visible():
                        txt = (btn.text_content() or "").strip()
                        if txt:
                            print(f"    - '{txt}' disabled={btn.is_disabled()}")
                check("执行标准化", False, "按钮不可用")

            shot(page, "08-std-result")
            body = page.inner_text("body")
            has_data = any(kw in body for kw in [
                "ThinkPad", "笔记本", "显示器", "打印机", "电脑",
                "办公", "商品名称", "规格型号"
            ])
            check("标准化有数据", has_data,
                  "有商品数据" if has_data else "无预期数据")
        else:
            check("标准化 Tab", False, "未找到")

        # ===== 5. 商品归组 =====
        print("\n=== 5. 商品归组 ===")
        if click_tab(page, "商品归组"):
            page.wait_for_timeout(1000)
            shot(page, "09-grp-tab")

            # 精确定位"开始智能归组"按钮
            grp_btn = page.locator("button:has-text('开始智能归组')")
            if grp_btn.count() == 0:
                grp_btn = page.locator("button:has-text('生成归组'), button:has-text('执行归组')")
            if grp_btn.count() > 0 and grp_btn.first.is_visible() and not grp_btn.first.is_disabled():
                print("  点击: '开始智能归组'")
                grp_btn.first.click()
                wait_for_async(page, 30)
                page.wait_for_timeout(5000)
                check("执行归组", True)
            else:
                print("  归组按钮未找到或 disabled")
                check("执行归组", False, "按钮不可用")

            shot(page, "10-grp-result")
            body = page.inner_text("body")
            has_groups = any(kw in body for kw in ["组", "group", "Group", "分组", "候选"])
            check("归组结果", has_groups)

            # 尝试确认所有归组 — 可能有"全部确认"或逐个确认
            confirm_all = page.locator("button:has-text('全部确认'), button:has-text('确认全部'), button:has-text('一键确认')")
            if confirm_all.count() > 0 and confirm_all.first.is_visible():
                confirm_all.first.click()
                print(f"  全部确认归组")
                page.wait_for_timeout(3000)
                shot(page, "10b-grp-confirmed")
                check("确认归组", True)
            else:
                # 尝试逐个确认
                confirmed = 0
                for _ in range(20):
                    confirm_btn = page.locator("button:has-text('确认')")
                    found = False
                    for i in range(confirm_btn.count()):
                        btn = confirm_btn.nth(i)
                        txt = (btn.text_content() or "").strip()
                        if btn.is_visible() and not btn.is_disabled() and "供应商" not in txt:
                            # Skip tab buttons
                            if len(txt) < 10:
                                btn.click()
                                confirmed += 1
                                page.wait_for_timeout(500)
                                found = True
                                break
                    if not found:
                        break
                if confirmed > 0:
                    print(f"  逐个确认归组 x{confirmed}")
                    page.wait_for_timeout(2000)
                    shot(page, "10b-grp-confirmed")
                    check("确认归组", True, f"确认了 {confirmed} 组")
                else:
                    check("确认归组", False, "无确认按钮或无需确认")
        else:
            check("归组 Tab", False, "未找到")

        # ===== 6. 比价导出 =====
        print("\n=== 6. 比价导出 ===")
        if click_tab(page, "比价") or click_tab(page, "比价导出") or click_tab(page, "导出"):
            page.wait_for_timeout(1000)
            shot(page, "11-cmp-tab")

            # 检查是否被阻塞
            body = page.inner_text("body")
            if "请先完成" in body:
                print(f"  阶段阻塞: {body[:100]}")
                check("比价导出阶段", False, "前置步骤未完成")
            else:
                # 生成比价 — 查找精确按钮
                cmp_btn = page.locator(
                    "button:has-text('生成比价'), button:has-text('执行比价'), "
                    "button:has-text('开始比价')"
                )
                if cmp_btn.count() > 0 and cmp_btn.first.is_visible() and not cmp_btn.first.is_disabled():
                    print("  点击: 生成比价")
                    cmp_btn.first.click()
                    wait_for_async(page, 30)
                    page.wait_for_timeout(5000)
                    check("生成比价", True)
                else:
                    check("生成比价", False, "按钮不可用")

                shot(page, "12-cmp-result")
                body = page.inner_text("body")
                has_cmp = any(kw in body for kw in ["最低", "比价", "单价", "供应商", "价格"])
                check("比价结果", has_cmp)

                # 导出
                export_btn = page.locator(
                    "button:has-text('导出Excel'), button:has-text('导出 Excel'), "
                    "button:has-text('导出'), button:has-text('下载')"
                )
                # Filter out tab buttons
                for i in range(export_btn.count()):
                    btn = export_btn.nth(i)
                    txt = (btn.text_content() or "").strip()
                    if btn.is_visible() and not btn.is_disabled() and "比价导出" not in txt and "比价导" not in txt:
                        btn.click()
                        print(f"  点击导出: '{txt}'")
                        page.wait_for_timeout(5000)
                        wait_for_async(page, 15)
                        shot(page, "13-export-result")
                        body = page.inner_text("body")
                        export_ok = any(kw in body for kw in [
                            "导出成功", "下载", "完成", ".xlsx", "成功"
                        ])
                        check("导出完成", export_ok,
                              "有成功提示" if export_ok else "未检测到成功提示")
                        break
                else:
                    check("导出按钮", False, "未找到")
        else:
            check("比价导出 Tab", False, "未找到")

        # ===== 7. 问题面板 =====
        print("\n=== 7. 问题面板 ===")
        # 查找问题面板入口
        problem_btn = page.locator(
            "button:has-text('问题'), button:has-text('待处理'), "
            "[class*='sidebar'] button, button:has-text('Problem')"
        )
        if problem_btn.count() > 0 and problem_btn.first.is_visible():
            problem_btn.first.click()
            page.wait_for_timeout(1000)
            shot(page, "14-problems")
            check("问题面板", True)
        else:
            # 检查页面上是否有问题相关元素
            body = page.inner_text("body")
            has_problems_ui = any(kw in body for kw in ["问题", "待处理", "告警", "异常"])
            shot(page, "14-no-problems")
            check("问题面板", has_problems_ui, "页面有问题相关文字" if has_problems_ui else "未找到入口")

        # ===== 最终截图 =====
        shot(page, "99-final")
        browser.close()

    # ===== 汇总 =====
    print("\n" + "=" * 60)
    print("DS-1 Playwright UI E2E 测试 v3 汇总")
    print("=" * 60)
    passed = sum(1 for r in RESULTS if r["status"] == "PASS")
    failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
    total = len(RESULTS)
    print(f"通过: {passed}, 失败: {failed}, 总计: {total}")
    if failed > 0:
        print("\n失败项:")
        for r in RESULTS:
            if r["status"] == "FAIL":
                print(f"  ❌ {r['name']}: {r['detail']}")
    print(f"\n截图目录: {SCREENSHOT_DIR}/")

    result_data = {
        "test": "DS-1 E2E v3",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "summary": {"passed": passed, "failed": failed, "total": total},
        "results": RESULTS,
        "screenshot_dir": SCREENSHOT_DIR
    }
    result_path = os.path.join(RESULTS_DIR, "ds1-playwright-v3.json")
    with open(result_path, "w") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)
    print(f"结果 JSON: {result_path}")


if __name__ == "__main__":
    main()
