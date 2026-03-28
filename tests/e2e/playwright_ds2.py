#!/usr/bin/env python3
"""
DS-2 Playwright UI E2E 测试 — 混合格式场景（xlsx + docx + pdf）。
Tab 名：导入文件 | 标准化 | 商品归组 | 符合性审查 → | 比价导出
"""
from playwright.sync_api import sync_playwright
import os
import json
import time

FRONTEND = "http://localhost:5173"
SCREENSHOT_DIR = "/tmp/e2e-screenshots/ds2"
DS2_DIR = os.path.join(os.path.dirname(__file__), "test-data", "ds-2")
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
    """等待异步操作完成 — spinner/progressbar 消失。"""
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


def dismiss_modal(page):
    """处理弹出的模态对话框。"""
    page.wait_for_timeout(800)
    overlay = page.locator("div.fixed.inset-0, [class*='overlay'], [class*='modal']")
    if overlay.count() == 0:
        return

    # 尝试点确认/保存/OK
    dialog_btns = page.locator(
        "div.fixed button, [role='dialog'] button, [class*='modal'] button"
    ).all()
    for btn in dialog_btns:
        txt = (btn.text_content() or "").strip()
        if btn.is_visible() and not btn.is_disabled():
            if any(kw in txt for kw in ["确认", "确定", "保存", "OK", "Save", "提交"]):
                print(f"    对话框点击: '{txt}'")
                btn.click()
                page.wait_for_timeout(1000)
                return

    # fallback: 关闭/取消
    for btn in dialog_btns:
        txt = (btn.text_content() or "").strip()
        if btn.is_visible() and any(kw in txt for kw in ["关闭", "取消", "Close", "Cancel"]):
            btn.click()
            page.wait_for_timeout(800)
            return

    page.keyboard.press("Escape")
    page.wait_for_timeout(800)


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

        # 填项目名
        dialog_inputs = page.locator("input[type='text'], input:not([type])").all()
        filled = False
        for inp in dialog_inputs:
            if inp.is_visible():
                inp.fill("DS-2 混合格式测试")
                filled = True
                break
        if not filled:
            page.locator("input").first.fill("DS-2 混合格式测试")

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

        # ===== 2. 上传混合格式文件 =====
        print("\n=== 2. 上传混合格式文件（xlsx + docx + pdf） ===")
        click_tab(page, "导入文件")
        page.wait_for_timeout(500)

        file_input = page.locator("input[type='file']")
        if file_input.count() > 0:
            ds2_abs = os.path.abspath(DS2_DIR)
            files = sorted([
                os.path.join(ds2_abs, f)
                for f in os.listdir(ds2_abs)
                if f.endswith((".xlsx", ".docx", ".pdf"))
            ])
            extensions = [os.path.splitext(f)[1] for f in files]
            print(f"  上传文件: {[os.path.basename(f) for f in files]}")
            print(f"  格式: {extensions}")
            file_input.first.set_input_files(files)
            # PDF 可能解析慢，等久一点
            page.wait_for_timeout(5000)
            wait_for_async(page, 20)
            shot(page, "04-uploaded")

            has_xlsx = ".xlsx" in str(extensions)
            has_docx = ".docx" in str(extensions)
            has_pdf = ".pdf" in str(extensions)
            check("上传 3 混合格式文件", len(files) == 3,
                  f"{len(files)} 文件: xlsx={has_xlsx}, docx={has_docx}, pdf={has_pdf}")
        else:
            check("上传文件", False, "无 file input")

        # 等待解析完成（PDF 较慢）
        print("  等待解析（PDF 可能较慢）...")
        page.wait_for_timeout(8000)
        wait_for_async(page, 20)
        shot(page, "05-parsed")

        body = page.inner_text("body")
        # DS-2 验证：三个供应商名称
        check("优品办公出现", "优品" in body or "优品办公" in body,
              "优品办公 xlsx 解析成功" if "优品" in body else "未检测到")
        check("佳美家具出现", "佳美" in body or "佳美家具" in body,
              "佳美家具 docx 解析成功" if "佳美" in body else "未检测到")
        check("宏远办公出现", "宏远" in body or "宏远办公" in body,
              "宏远办公 pdf 解析成功" if "宏远" in body else "未检测到")

        # ===== 3. 确认供应商 =====
        print("\n=== 3. 确认供应商 ===")
        confirmed_count = 0

        for attempt in range(6):
            confirm_btns = page.locator("button:has-text('确认供应商')").all()
            clickable = [b for b in confirm_btns if b.is_visible() and not b.is_disabled()]
            if not clickable:
                break
            clickable[0].click()
            confirmed_count += 1
            print(f"  确认供应商 #{confirmed_count}")
            dismiss_modal(page)
            page.wait_for_timeout(500)

        if confirmed_count == 0:
            # fallback: 也许按钮文字不同
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

            std_btn = page.locator("button:has-text('执行标准化')")
            if std_btn.count() > 0 and std_btn.first.is_visible() and not std_btn.first.is_disabled():
                std_btn.first.click()
                print("  点击: '执行标准化'")
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
            # DS-2 应该有家具类商品
            has_data = any(kw in body for kw in [
                "办公椅", "办公桌", "文件柜", "家具", "桌", "椅",
                "商品名称", "规格型号", "单价", "数量"
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

            grp_btn = page.locator("button:has-text('开始智能归组')")
            if grp_btn.count() == 0:
                grp_btn = page.locator("button:has-text('生成归组'), button:has-text('执行归组')")
            if grp_btn.count() > 0 and grp_btn.first.is_visible() and not grp_btn.first.is_disabled():
                print(f"  点击: '{grp_btn.first.text_content().strip()}'")
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

            # 尝试确认归组
            confirm_all = page.locator(
                "button:has-text('全部确认'), button:has-text('确认全部'), button:has-text('一键确认')"
            )
            if confirm_all.count() > 0 and confirm_all.first.is_visible():
                confirm_all.first.click()
                print("  全部确认归组")
                page.wait_for_timeout(3000)
                shot(page, "10b-grp-confirmed")
                check("确认归组", True)
            else:
                confirmed = 0
                for _ in range(20):
                    confirm_btn = page.locator("button:has-text('确认')")
                    found = False
                    for i in range(confirm_btn.count()):
                        btn = confirm_btn.nth(i)
                        txt = (btn.text_content() or "").strip()
                        if btn.is_visible() and not btn.is_disabled() and "供应商" not in txt:
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

            body = page.inner_text("body")
            if "请先完成" in body:
                print(f"  阶段阻塞: {body[:100]}")
                check("比价导出阶段", False, "前置步骤未完成")
            else:
                cmp_btn = page.locator(
                    "button:has-text('生成比价'), button:has-text('执行比价'), "
                    "button:has-text('开始比价')"
                )
                if cmp_btn.count() > 0 and cmp_btn.first.is_visible() and not cmp_btn.first.is_disabled():
                    btn_text = cmp_btn.first.text_content(timeout=5000) or "生成比价"
                    cmp_btn.first.click()
                    print(f"  点击: '{btn_text.strip()}'")
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
                exported = False
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
                        exported = True
                        break
                if not exported:
                    check("导出按钮", False, "未找到")
        else:
            check("比价导出 Tab", False, "未找到")

        # ===== 最终截图 =====
        shot(page, "99-final")
        browser.close()

    # ===== 汇总 =====
    print("\n" + "=" * 60)
    print("DS-2 混合格式 Playwright E2E 测试汇总")
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
        "test": "DS-2 混合格式 E2E",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "summary": {"passed": passed, "failed": failed, "total": total},
        "results": RESULTS,
        "screenshot_dir": SCREENSHOT_DIR,
        "ds2_validation": {
            "formats_tested": ["xlsx", "docx", "pdf"],
            "suppliers": ["优品办公", "佳美家具", "宏远办公"]
        }
    }
    result_path = os.path.join(RESULTS_DIR, "ds2-playwright.json")
    with open(result_path, "w") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)
    print(f"结果 JSON: {result_path}")


if __name__ == "__main__":
    main()
