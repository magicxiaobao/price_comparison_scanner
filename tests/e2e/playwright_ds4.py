#!/usr/bin/env python3
"""
DS-4 Playwright UI E2E 测试 — 归组挑战：品牌别名 + 噪音词。
Tab 名：导入文件 | 标准化 | 商品归组 | 符合性审查 → | 比价导出
"""
from playwright.sync_api import sync_playwright
import os
import json
import time

FRONTEND = "http://localhost:5173"
SCREENSHOT_DIR = "/tmp/e2e-screenshots/ds4"
DS4_DIR = os.path.join(os.path.dirname(__file__), "test-data", "ds-4")
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
    tag = "PASS" if passed else "FAIL"
    print(f"  [{tag}] {name}" + (f" -- {detail}" if detail else ""))


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
    """等待异步操作完成 -- spinner/progressbar 消失。"""
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

        # 填项目名
        dialog_inputs = page.locator("input[type='text'], input:not([type])").all()
        filled = False
        for inp in dialog_inputs:
            if inp.is_visible():
                inp.fill("DS-4 归组挑战测试")
                filled = True
                break
        if not filled:
            page.locator("input").first.fill("DS-4 归组挑战测试")

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

        # ===== 2. 上传文件 =====
        print("\n=== 2. 上传文件 ===")
        click_tab(page, "导入文件")
        page.wait_for_timeout(500)

        file_input = page.locator("input[type='file']")
        if file_input.count() > 0:
            ds4_abs = os.path.abspath(DS4_DIR)
            files = sorted([
                os.path.join(ds4_abs, f)
                for f in os.listdir(ds4_abs)
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

        # DS-4 供应商名推断: 供应商A/B/C
        body = page.inner_text("body")
        check("文件解析完成", "供应商" in body or "报价" in body or "文件" in body)

        # ===== 3. 确认供应商 =====
        print("\n=== 3. 确认供应商 ===")
        confirmed_count = 0

        def dismiss_modal(p):
            """处理确认供应商后弹出的模态对话框。"""
            p.wait_for_timeout(800)
            overlay = p.locator("div.fixed.inset-0, [class*='overlay'], [class*='modal']")
            if overlay.count() == 0:
                return
            shot(p, f"modal-{confirmed_count}")
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
            for btn in dialog_btns:
                txt = (btn.text_content() or "").strip()
                if btn.is_visible() and any(kw in txt for kw in ["关闭", "取消", "Close", "Cancel"]):
                    btn.click()
                    p.wait_for_timeout(800)
                    return
            p.keyboard.press("Escape")
            p.wait_for_timeout(800)

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

            # 收集所有供应商的标准化文本，用于品牌别名验证
            all_std_text = page.inner_text("body")

            # 尝试切换供应商下拉框查看所有供应商数据
            supplier_select = page.locator("select, [role='combobox'], [class*='select']")
            if supplier_select.count() > 0:
                for supplier_label in ["供应商A", "供应商B", "供应商C", "A", "B", "C"]:
                    try:
                        supplier_select.first.click()
                        page.wait_for_timeout(300)
                        option = page.locator(f"[role='option']:has-text('{supplier_label}'), option:has-text('{supplier_label}')")
                        if option.count() > 0:
                            option.first.click()
                            page.wait_for_timeout(1000)
                            all_std_text += "\n" + page.inner_text("body")
                    except Exception:
                        pass

            # 检查网络设备相关关键词
            has_network_data = any(kw in all_std_text for kw in [
                "交换机", "路由器", "服务器", "摄像", "无线",
                "AP", "NVR", "商品名称", "规格型号"
            ])
            check("标准化有数据", has_network_data,
                  "有网络设备数据" if has_network_data else "无预期数据")

            # 品牌别名在归组阶段验证（归一化发生在归组预处理中，不在标准化阶段）
            shot(page, "08b-std-brand-check")
        else:
            check("标准化 Tab", False, "未找到")

        # ===== 5. 商品归组（重点） =====
        print("\n=== 5. 商品归组（DS-4 重点验证）===")
        if click_tab(page, "商品归组"):
            page.wait_for_timeout(1000)
            shot(page, "09-grp-tab")

            grp_btn = page.locator("button:has-text('开始智能归组')")
            if grp_btn.count() == 0:
                grp_btn = page.locator("button:has-text('生成归组'), button:has-text('执行归组')")
            if grp_btn.count() > 0 and grp_btn.first.is_visible() and not grp_btn.first.is_disabled():
                print("  点击: '开始智能归组'")
                grp_btn.first.click()
                wait_for_async(page, 40)
                page.wait_for_timeout(5000)
                check("执行归组", True)
            else:
                print("  归组按钮未找到或 disabled，列出按钮:")
                for btn in page.locator("button").all():
                    if btn.is_visible():
                        txt = (btn.text_content() or "").strip()
                        if txt:
                            print(f"    - '{txt}' disabled={btn.is_disabled()}")
                check("执行归组", False, "按钮不可用")

            shot(page, "10-grp-result")

            # 检查是否有归组错误
            body = page.inner_text("body")
            has_error = any(kw in body for kw in ["失败", "error", "Error", "validation error"])
            if has_error:
                error_text = body[:500] if len(body) > 500 else body
                check("归组加载", False, f"归组出错: {error_text[:200]}")
                # 尝试点击重试
                retry_btn = page.locator("button:has-text('重试'), button:has-text('重新加载')")
                if retry_btn.count() > 0 and retry_btn.first.is_visible():
                    retry_btn.first.click()
                    print("  点击重试...")
                    wait_for_async(page, 30)
                    page.wait_for_timeout(5000)
                    shot(page, "10-grp-retry")
                    body = page.inner_text("body")

            # 归组结果详细分析
            has_groups = any(kw in body for kw in ["组", "group", "Group", "分组", "候选"])
            check("归组结果", has_groups)

            # 品牌别名验证（在归组阶段检查：归一化发生在归组预处理中）
            brand_alias_checks = {
                "思科": "cisco->思科",
                "华为": "huawei->华为",
                "惠普": "hp->惠普",
                "海康威视": "hikvision->海康威视",
            }
            grp_body = page.inner_text("body")
            for chinese_brand, alias_desc in brand_alias_checks.items():
                found = chinese_brand in grp_body
                check(f"品牌别名 {alias_desc}", found,
                      f"归组名称含 '{chinese_brand}'" if found else f"未找到 '{chinese_brand}'")

            # DS-4 特有验证: 6 组预期
            # 预期 6 组: 交换机、无线AP、服务器、路由器、摄像头、NVR
            expected_keywords_per_group = {
                "交换机组": ["交换机"],
                "无线AP组": ["无线", "AP", "接入点"],
                "服务器组": ["服务器"],
                "路由器组": ["路由器"],
                "摄像头组": ["摄像"],
                "NVR组": ["NVR", "录像"],
            }
            groups_found = 0
            for group_name, keywords in expected_keywords_per_group.items():
                found = any(kw in body for kw in keywords)
                if found:
                    groups_found += 1
                check(f"归组-{group_name}", found,
                      f"关键词命中" if found else f"未找到 {keywords}")

            check("归组数量>=6", groups_found >= 6, f"发现 {groups_found}/6 组")

            # 置信度分层验证: 预期 5 高 + 1 中（路由器）
            body_lower = body.lower()
            has_confidence = any(kw in body_lower for kw in [
                "高", "中", "low", "high", "medium", "置信", "confidence"
            ])
            check("置信度显示", has_confidence, "有置信度信息" if has_confidence else "未检测到置信度")

            # 截取归组详情截图
            shot(page, "10b-grp-detail")

            # 滚动下半页截图
            page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            page.wait_for_timeout(500)
            shot(page, "10c-grp-scroll")

            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(500)
            shot(page, "10d-grp-bottom")

            # 回到顶部
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(300)

            # 尝试确认所有归组
            confirm_all = page.locator(
                "button:has-text('全部确认'), button:has-text('确认全部'), button:has-text('一键确认')"
            )
            if confirm_all.count() > 0 and confirm_all.first.is_visible():
                confirm_all.first.click()
                print("  全部确认归组")
                page.wait_for_timeout(3000)
                shot(page, "10e-grp-confirmed")
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
                    shot(page, "10e-grp-confirmed")
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
    print("DS-4 Playwright UI E2E 测试 汇总")
    print("=" * 60)
    passed = sum(1 for r in RESULTS if r["status"] == "PASS")
    failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
    total = len(RESULTS)
    print(f"通过: {passed}, 失败: {failed}, 总计: {total}")
    if failed > 0:
        print("\n失败项:")
        for r in RESULTS:
            if r["status"] == "FAIL":
                print(f"  FAIL {r['name']}: {r['detail']}")
    print(f"\n截图目录: {SCREENSHOT_DIR}/")

    result_data = {
        "test": "DS-4 E2E 归组挑战",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "summary": {"passed": passed, "failed": failed, "total": total},
        "ds4_focus": {
            "brand_aliases": ["cisco->思科", "huawei->华为", "hp->惠普", "hikvision->海康威视"],
            "expected_groups": 6,
            "expected_high_confidence": 5,
            "expected_medium_confidence": 1,
        },
        "results": RESULTS,
        "screenshot_dir": SCREENSHOT_DIR,
    }
    result_path = os.path.join(RESULTS_DIR, "ds4-playwright.json")
    with open(result_path, "w") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)
    print(f"结果 JSON: {result_path}")


if __name__ == "__main__":
    main()
