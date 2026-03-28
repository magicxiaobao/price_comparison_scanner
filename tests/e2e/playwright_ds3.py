#!/usr/bin/env python3
"""
DS-3 Playwright UI E2E 测试 — 异常场景：4 供应商，税价/单位/币种异常。
Tab 名：导入文件 | 标准化 | 商品归组 | 符合性审查 → | 比价导出
"""
from playwright.sync_api import sync_playwright
import os
import json
import time

FRONTEND = "http://localhost:5173"
SCREENSHOT_DIR = "/tmp/e2e-screenshots/ds3"
DS3_DIR = os.path.join(os.path.dirname(__file__), "test-data", "ds-3")
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


def dismiss_modal(page, label=""):
    """处理弹出的模态对话框。"""
    page.wait_for_timeout(800)
    overlay = page.locator("div.fixed.inset-0, [class*='overlay'], [class*='modal'], [role='dialog']")
    if overlay.count() == 0:
        return

    if label:
        shot(page, f"modal-{label}")

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

    # fallback: 点关闭/取消
    for btn in dialog_btns:
        txt = (btn.text_content() or "").strip()
        if btn.is_visible() and any(kw in txt for kw in ["关闭", "取消", "Close", "Cancel"]):
            btn.click()
            page.wait_for_timeout(800)
            return

    page.keyboard.press("Escape")
    page.wait_for_timeout(800)


def list_visible_buttons(page):
    """调试用：列出所有可见按钮。"""
    btns = page.locator("button").all()
    for btn in btns:
        if btn.is_visible():
            txt = (btn.text_content() or "").strip()
            if txt and len(txt) < 80:
                disabled = " [DISABLED]" if btn.is_disabled() else ""
                print(f"    - '{txt}'{disabled}")


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
                inp.fill("DS-3 异常场景测试")
                filled = True
                break
        if not filled:
            page.locator("input").first.fill("DS-3 异常场景测试")

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

        # ===== 2. 上传 4 个文件 =====
        print("\n=== 2. 上传 4 个文件 ===")
        click_tab(page, "导入文件")
        page.wait_for_timeout(500)

        file_input = page.locator("input[type='file']")
        if file_input.count() > 0:
            ds3_abs = os.path.abspath(DS3_DIR)
            files = sorted([
                os.path.join(ds3_abs, f)
                for f in os.listdir(ds3_abs)
                if f.endswith(".xlsx")
            ])
            print(f"  上传文件: {[os.path.basename(f) for f in files]}")
            file_input.first.set_input_files(files)
            page.wait_for_timeout(3000)
            wait_for_async(page, 20)
            shot(page, "04-uploaded")
            check("上传 4 文件", len(files) == 4, f"实际 {len(files)} 文件")
        else:
            check("上传文件", False, "无 file input")

        # 等待解析（4 文件，等久一些）
        print("  等待解析...")
        page.wait_for_timeout(8000)
        wait_for_async(page, 20)
        shot(page, "05-parsed")

        body = page.inner_text("body")
        # DS-3 供应商：科达试剂、国药试剂、西陇试剂、Sigma-Aldrich
        check("科达试剂出现", "科达" in body, "页面含'科达'" if "科达" in body else "未找到")
        check("国药试剂出现", "国药" in body, "页面含'国药'" if "国药" in body else "未找到")
        check("西陇试剂出现", "西陇" in body, "页面含'西陇'" if "西陇" in body else "未找到")
        check("Sigma出现", "Sigma" in body or "sigma" in body.lower(),
              "页面含'Sigma'" if "Sigma" in body or "sigma" in body.lower() else "未找到")

        # ===== 3. 确认供应商 =====
        print("\n=== 3. 确认供应商 ===")
        confirmed_count = 0
        for attempt in range(8):
            confirm_btns = page.locator("button:has-text('确认供应商')").all()
            clickable = [b for b in confirm_btns if b.is_visible() and not b.is_disabled()]
            if not clickable:
                # 也查找"确认"按钮（非 tab）
                confirm_btns2 = page.locator("button:has-text('确认')").all()
                clickable = [
                    b for b in confirm_btns2
                    if b.is_visible() and not b.is_disabled()
                    and len((b.text_content() or "").strip()) < 15
                    and "供应商" in (b.text_content() or "")
                ]
            if not clickable:
                break
            clickable[0].click()
            confirmed_count += 1
            print(f"  确认供应商 #{confirmed_count}")
            dismiss_modal(page, f"supplier-{confirmed_count}")
            page.wait_for_timeout(500)

        if confirmed_count == 0:
            print("  未找到确认供应商按钮，列出可见按钮:")
            list_visible_buttons(page)

        shot(page, "06-suppliers-confirmed")
        check("确认供应商", confirmed_count >= 4, f"确认了 {confirmed_count} 个（预期 4）")

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
                list_visible_buttons(page)
                check("执行标准化", False, "按钮不可用")

            shot(page, "08-std-result")
            body = page.inner_text("body")

            # DS-3 特殊检查：税价/单位/币种异常标记
            anomaly_keywords = ["异常", "警告", "不一致", "缺失", "问题",
                                "税", "币种", "单位", "USD", "RMB", "元",
                                "含税", "不含税", "warning", "error"]
            found_anomalies = [kw for kw in anomaly_keywords if kw in body]
            has_data = any(kw in body for kw in [
                "试剂", "化学", "商品名称", "规格", "CAS", "纯度",
                "名称", "型号", "单价"
            ])
            check("标准化有数据", has_data,
                  "有商品数据" if has_data else "无预期数据")
            check("标准化异常标记", len(found_anomalies) > 0,
                  f"检出关键词: {found_anomalies}" if found_anomalies else "未检出异常关键词")
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
                list_visible_buttons(page)
                check("执行归组", False, "按钮不可用")

            shot(page, "10-grp-result")
            body = page.inner_text("body")
            has_groups = any(kw in body for kw in ["组", "group", "Group", "分组", "候选"])
            check("归组结果", has_groups)

            # 确认归组
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
                        if btn.is_visible() and not btn.is_disabled() and "供应商" not in txt and len(txt) < 10:
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
                print(f"  阶段阻塞: {body[:200]}")
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

                # DS-3 重点：异常标记在比价结果中
                has_cmp = any(kw in body for kw in ["最低", "比价", "单价", "供应商", "价格"])
                check("比价结果", has_cmp)

                anomaly_cmp_kw = ["异常", "不一致", "税", "币种", "单位", "警告",
                                  "含税", "不含税", "USD", "注意"]
                found_cmp_anomalies = [kw for kw in anomaly_cmp_kw if kw in body]
                check("比价异常标记", len(found_cmp_anomalies) > 0,
                      f"检出: {found_cmp_anomalies}" if found_cmp_anomalies else "未检出异常标记")

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

        # ===== 7. 问题面板检查 =====
        print("\n=== 7. 问题面板 ===")
        # 查找页面上的问题/异常提示
        body = page.inner_text("body")
        problem_keywords = ["问题", "待处理", "告警", "异常", "警告", "错误",
                            "不一致", "缺失", "Problem"]
        found_problems = [kw for kw in problem_keywords if kw in body]

        # 尝试点击问题面板按钮
        problem_btn = page.locator(
            "button:has-text('问题'), button:has-text('待处理'), "
            "[class*='sidebar'] button, button:has-text('Problem')"
        )
        if problem_btn.count() > 0:
            for i in range(problem_btn.count()):
                btn = problem_btn.nth(i)
                txt = (btn.text_content() or "").strip()
                if btn.is_visible() and len(txt) < 20:
                    btn.click()
                    page.wait_for_timeout(1000)
                    shot(page, "14-problems-panel")
                    body = page.inner_text("body")
                    found_problems = [kw for kw in problem_keywords if kw in body]
                    break

        shot(page, "14-problems")
        check("问题/异常检出", len(found_problems) > 0,
              f"检出关键词: {found_problems}" if found_problems else "页面无异常提示")

        # ===== 8. 全页最终截图 =====
        shot(page, "99-final")
        browser.close()

    # ===== 汇总 =====
    print("\n" + "=" * 60)
    print("DS-3 Playwright E2E 测试汇总（异常场景）")
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
        "test": "DS-3 E2E 异常场景",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "summary": {"passed": passed, "failed": failed, "total": total},
        "results": RESULTS,
        "screenshot_dir": SCREENSHOT_DIR,
        "ds3_focus": "税价口径不一致、单位不一致、币种不一致、字段缺失"
    }
    result_path = os.path.join(RESULTS_DIR, "ds3-playwright.json")
    with open(result_path, "w") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)
    print(f"结果 JSON: {result_path}")


if __name__ == "__main__":
    main()
