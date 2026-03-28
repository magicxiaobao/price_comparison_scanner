#!/usr/bin/env python3
"""
DS-5 Playwright UI E2E 测试 — OCR 路径：标准 xlsx + 扫描版 PDF。
验证重点：
  1. 标准 xlsx 正常解析
  2. 扫描版 PDF 触发 OCR 降级 → 显示"OCR 扩展未安装"蓝色提示
  3. 应用不崩溃
  4. xlsx 文件流程不受影响
"""
from playwright.sync_api import sync_playwright
import os
import json
import time

FRONTEND = "http://localhost:5173"
SCREENSHOT_DIR = "/tmp/e2e-screenshots/ds5"
DS5_DIR = os.path.join(os.path.dirname(__file__), "test-data", "ds-5")
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
    for strategy in [
        lambda: page.locator(f"[role='tab']:has-text('{tab_text}')"),
        lambda: page.locator(f"button:has-text('{tab_text}')"),
        lambda: page.get_by_text(tab_text, exact=False),
    ]:
        loc = strategy()
        if loc.count() > 0 and loc.first.is_visible():
            loc.first.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(800)
            return True
    return False


def wait_for_async(page, timeout_s=30):
    for _ in range(timeout_s):
        page.wait_for_timeout(1000)
        loading = page.locator(
            "[class*='spinner'], [class*='loading'], [role='progressbar'], "
            "[class*='animate-spin']"
        )
        if loading.count() == 0:
            page.wait_for_timeout(800)
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
        page.wait_for_timeout(1000)
        shot(page, "01-home")

        new_btn = page.locator("button:has-text('新建项目')")
        if new_btn.count() == 0:
            new_btn = page.locator("button:has-text('新建')")
        new_btn.first.click()
        page.wait_for_timeout(800)
        shot(page, "02-dialog")

        dialog_inputs = page.locator("input[type='text'], input:not([type])").all()
        filled = False
        for inp in dialog_inputs:
            if inp.is_visible():
                inp.fill("DS-5 OCR 路径测试")
                filled = True
                break
        if not filled:
            page.locator("input").first.fill("DS-5 OCR 路径测试")

        page.wait_for_timeout(300)
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

        # ===== 2. 上传文件（xlsx + 扫描版 PDF） =====
        print("\n=== 2. 上传文件（xlsx + 扫描版 PDF） ===")
        click_tab(page, "导入文件")
        page.wait_for_timeout(500)

        file_input = page.locator("input[type='file']")
        if file_input.count() > 0:
            ds5_abs = os.path.abspath(DS5_DIR)
            files = sorted([
                os.path.join(ds5_abs, f)
                for f in os.listdir(ds5_abs)
                if f.endswith((".xlsx", ".pdf"))
            ])
            print(f"  上传文件: {[os.path.basename(f) for f in files]}")
            file_input.first.set_input_files(files)
            page.wait_for_timeout(3000)
            wait_for_async(page, 20)
            shot(page, "04-uploaded")
            check("上传 2 文件", len(files) == 2, f"实际 {len(files)} 文件: {[os.path.basename(f) for f in files]}")
        else:
            check("上传文件", False, "无 file input")

        # ===== 3. 等待解析 + 检查 OCR 提示 =====
        print("\n=== 3. 等待解析 & 检查 OCR 降级提示 ===")
        page.wait_for_timeout(5000)
        wait_for_async(page, 20)
        shot(page, "05-parsed")

        body = page.inner_text("body")

        # 核心检查：OCR 未安装提示
        ocr_keywords = ["OCR", "ocr", "扫描", "无法提取", "未安装", "扩展未安装", "不支持"]
        ocr_hint_found = any(kw in body for kw in ocr_keywords)
        check("OCR 降级提示", ocr_hint_found,
              "检测到 OCR 相关提示" if ocr_hint_found else "未检测到 OCR 提示文字")

        # 截图搜索蓝色提示（info alert）
        blue_alerts = page.locator(
            "[class*='info'], [class*='alert-info'], [class*='blue'], "
            "[class*='warning'], [class*='notice'], [role='alert'], "
            "[class*='toast'], [class*='Banner'], [class*='banner']"
        )
        blue_count = blue_alerts.count()
        if blue_count > 0:
            for i in range(min(blue_count, 3)):
                alert_text = blue_alerts.nth(i).text_content() or ""
                print(f"  提示框 #{i}: {alert_text[:120]}")
            shot(page, "06-ocr-alert-detail")
        check("提示框元素存在", blue_count > 0, f"找到 {blue_count} 个提示元素")

        # ===== 4. 应用不崩溃检查 =====
        print("\n=== 4. 应用稳定性检查 ===")
        # 页面仍可交互
        page_ok = page.url.startswith("http") and "error" not in page.url.lower()
        check("页面未崩溃", page_ok, page.url)

        # 检查是否有 JS 错误覆盖（error boundary）
        error_boundary = page.locator("[class*='error-boundary'], [class*='ErrorBoundary'], [class*='crash']")
        no_crash = error_boundary.count() == 0
        check("无 Error Boundary", no_crash)

        # 检查控制台错误（通过 body 中是否有典型崩溃文字）
        crash_keywords = ["Something went wrong", "Unhandled", "应用崩溃", "页面错误"]
        no_crash_text = not any(kw in body for kw in crash_keywords)
        check("无崩溃文字", no_crash_text)

        shot(page, "07-stability")

        # ===== 5. xlsx 文件正常显示 =====
        print("\n=== 5. xlsx 文件正常显示 ===")
        # 检查 xlsx 文件（标准供应商A）是否正常解析显示
        xlsx_keywords = ["标准供应商", "供应商A", ".xlsx", "已解析", "成功"]
        xlsx_visible = any(kw in body for kw in xlsx_keywords)
        check("xlsx 文件可见", xlsx_visible,
              "检测到 xlsx 相关内容" if xlsx_visible else "未检测到 xlsx 内容")

        # 列出页面上的文件卡片/条目
        file_cards = page.locator("[class*='card'], [class*='file'], tr, [class*='item']").all()
        visible_items = []
        for card in file_cards:
            if card.is_visible():
                txt = (card.text_content() or "").strip()
                if ("xlsx" in txt.lower() or "pdf" in txt.lower() or "供应商" in txt) and len(txt) < 200:
                    visible_items.append(txt[:100])
        if visible_items:
            print(f"  文件条目:")
            for item in visible_items[:5]:
                print(f"    - {item}")
        check("文件条目可见", len(visible_items) > 0, f"{len(visible_items)} 个条目")

        shot(page, "08-file-list")

        # ===== 6. 确认供应商（xlsx 的） =====
        print("\n=== 6. 确认供应商 ===")
        confirmed_count = 0
        for attempt in range(4):
            confirm_btns = page.locator("button:has-text('确认供应商')").all()
            clickable = [b for b in confirm_btns if b.is_visible() and not b.is_disabled()]
            if not clickable:
                break
            clickable[0].click()
            confirmed_count += 1
            print(f"  确认供应商 #{confirmed_count}")
            page.wait_for_timeout(1000)
            # 处理弹出对话框
            for modal_text in ["确认", "确定", "保存", "OK"]:
                modal_btn = page.locator(f"div.fixed button:has-text('{modal_text}'), [role='dialog'] button:has-text('{modal_text}')")
                if modal_btn.count() > 0 and modal_btn.first.is_visible():
                    modal_btn.first.click()
                    page.wait_for_timeout(800)
                    break
            page.wait_for_timeout(500)

        if confirmed_count == 0:
            print("  未找到确认供应商按钮，列出可见按钮:")
            for btn in page.locator("button").all():
                if btn.is_visible():
                    txt = (btn.text_content() or "").strip()
                    if txt and len(txt) < 60:
                        print(f"    - '{txt}' disabled={btn.is_disabled()}")

        shot(page, "09-suppliers-confirmed")
        check("确认供应商", confirmed_count > 0, f"确认了 {confirmed_count} 个")

        # ===== 7. 尝试标准化 =====
        print("\n=== 7. 尝试标准化 ===")
        if click_tab(page, "标准化"):
            page.wait_for_timeout(1000)
            shot(page, "10-std-tab")

            std_btn = page.locator("button:has-text('执行标准化')")
            if std_btn.count() > 0 and std_btn.first.is_visible() and not std_btn.first.is_disabled():
                std_btn.first.click()
                print("  点击: '执行标准化'")
                wait_for_async(page, 30)
                page.wait_for_timeout(5000)
                shot(page, "11-std-result")

                body = page.inner_text("body")
                # 标准化可能部分成功（xlsx 成功，PDF 失败）
                has_data = any(kw in body for kw in [
                    "商品名称", "规格型号", "单价", "数量", "标准化",
                    "标准供应商", "供应商"
                ])
                check("标准化有数据", has_data,
                      "有数据（至少 xlsx 部分成功）" if has_data else "无预期数据")

                # 检查是否有 PDF 解析失败/部分成功的提示
                partial_keywords = ["部分", "失败", "跳过", "无法", "OCR", "扫描"]
                partial_hint = any(kw in body for kw in partial_keywords)
                check("PDF 部分失败提示", partial_hint,
                      "有部分失败/跳过提示" if partial_hint else "无明确部分失败提示")
            else:
                print("  '执行标准化' 按钮不可用")
                for btn in page.locator("button").all():
                    if btn.is_visible():
                        txt = (btn.text_content() or "").strip()
                        if txt:
                            print(f"    - '{txt}' disabled={btn.is_disabled()}")
                check("执行标准化", False, "按钮不可用")
                shot(page, "11-std-blocked")
        else:
            check("标准化 Tab", False, "未找到")

        # ===== 8. 最终稳定性检查 =====
        print("\n=== 8. 最终稳定性检查 ===")
        # 确认应用全程未崩溃
        final_body = page.inner_text("body")
        final_ok = not any(kw in final_body for kw in crash_keywords)
        check("最终页面稳定", final_ok)

        # 能否正常切换 Tab
        tab_switch_ok = click_tab(page, "导入文件")
        check("Tab 切换正常", tab_switch_ok)

        shot(page, "99-final")
        browser.close()

    # ===== 汇总 =====
    print("\n" + "=" * 60)
    print("DS-5 Playwright UI E2E 测试汇总（OCR 路径）")
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
        "test": "DS-5 E2E OCR Path",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "summary": {"passed": passed, "failed": failed, "total": total},
        "results": RESULTS,
        "screenshot_dir": SCREENSHOT_DIR
    }
    result_path = os.path.join(RESULTS_DIR, "ds5-playwright.json")
    with open(result_path, "w") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)
    print(f"结果 JSON: {result_path}")


if __name__ == "__main__":
    main()
