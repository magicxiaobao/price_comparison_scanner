# Whitepaper Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a product-marketing style software whitepaper workflow for the project, including Markdown source, screenshot assets, and a Python-based `.docx` export script.

**Architecture:** The work is split into five deliverables: content outline, screenshot asset pipeline, Markdown whitepaper source, Python export script, and final Word verification. The Markdown file is the single source of truth, screenshots are stored under a dedicated asset directory, and the export script produces a stable Word deliverable from local files.

**Tech Stack:** Markdown, Python 3.11+, `python-docx` or equivalent Word library, local image assets, existing project docs and running application UI.

**Execution Mode:** This plan is not executed directly by the current Leader session. The Leader session is responsible for issuing execution prompts to another agent, defining the task report format, and reviewing the returned task reports as a reviewer. The Leader session should not implement the plan tasks unless the user explicitly changes this rule.

---

## Delegated Execution Protocol

### Leader Responsibilities

- Break the plan into executable task packets
- Send a focused execution prompt for each packet to the implementation agent
- Require the implementation agent to follow the task report format exactly
- Review each returned report before releasing the next packet
- Reject incomplete, unverifiable, or off-scope reports

### Implementation Agent Responsibilities

- Execute only the assigned packet
- Report changed files, commands run, outputs, blockers, and verification results
- Avoid silently expanding scope
- Stop and report if required assumptions are invalid

### Reviewer Gate

The next task packet should be released only when the previous packet report is reviewed and accepted by the Leader session.

## Task Report Format

Every implementation task report must use the following Markdown structure:

````markdown
# Task Report

## Task
- Task ID:
- Task Name:
- Goal:

## Scope Completed
- Completed items:
- Explicitly not done:

## Files Changed
- `/absolute/path/to/file`

## Key Changes
- Change 1
- Change 2

## Commands Run
```bash
exact command 1
exact command 2
```

## Verification
- What was verified:
- Result:

## Evidence
- Key output summary:
- Screenshot or output path:

## Risks / Follow-ups
- Remaining risk 1
- Remaining follow-up 2

## Blockers
- None
````

## Reviewer Checklist

Each returned task report should be reviewed against the following checklist:

- The task scope matches the assigned packet
- The changed files are explicitly listed
- The commands run are explicitly listed
- The verification result is concrete, not vague
- Claims are supported by evidence paths or output summaries
- No silent scope expansion occurred
- Remaining risks and blockers are clearly stated

## Execution Prompt Template

Use the following prompt template when dispatching a task packet to another agent:

```markdown
你是白皮书实施代理，负责执行当前任务包，不负责重新规划整体方案。

请执行以下任务：

- Task ID: <填写>
- Task Name: <填写>
- Goal: <填写>
- Scope: <填写>
- In Scope Files: <填写>
- Out of Scope: <填写>
- Verification Requirement: <填写>

执行要求：

- 只处理当前任务包，不擅自扩展范围
- 若发现依赖缺失、环境问题或需求矛盾，停止实现并报告 blocker
- 输出必须严格遵循约定的 Task Report 格式
- 报告中必须列出修改文件、执行命令、验证结果和剩余风险

你完成后，只输出 Task Report，不要输出额外寒暄。
```

### Task 1: Create Whitepaper Workspace Structure

**Files:**
- Create: `docs/whitepaper/software-whitepaper.md`
- Create: `docs/whitepaper/assets/screenshots/README.md`
- Create: `dist/whitepaper/.gitkeep`

**Step 1: Create the target directories**

Run: `mkdir -p docs/whitepaper/assets/screenshots dist/whitepaper`
Expected: directories exist without errors

**Step 2: Create screenshot directory README**

Content requirements:

- Explain purpose of the screenshot directory
- Define naming convention
- Define image source priority: real UI first, design image second

**Step 3: Create Markdown whitepaper placeholder**

Include:

- Main title
- Chapter skeleton matching the approved design
- Placeholder sections for screenshots

**Step 4: Verify structure**

Run: `find docs/whitepaper -maxdepth 3 -type f | sort`
Expected: `software-whitepaper.md` and screenshot README are listed

**Step 5: Commit**

```bash
git add docs/whitepaper dist/whitepaper
git commit -m "docs: scaffold whitepaper workspace"
```

### Task 2: Produce Whitepaper Chapter Outline and Writing Skeleton

**Files:**
- Modify: `docs/whitepaper/software-whitepaper.md`

**Step 1: Write the chapter skeleton**

Add these sections in order:

- 产品概述
- 建设背景与业务痛点
- 产品定位与应用场景
- 核心功能总览
- 五阶段业务流程
- 关键产品亮点
- 系统架构与运行方式
- 数据安全与部署优势
- 典型界面展示
- 交付成果与验收价值
- 后续演进方向

**Step 2: Add writing guidance per section**

For each section, add 2-4 bullet placeholders describing:

- what the section should explain
- which existing docs are the likely source
- whether screenshots are required

**Step 3: Verify Markdown readability**

Run: `sed -n '1,260p' docs/whitepaper/software-whitepaper.md`
Expected: outline is complete and readable

**Step 4: Commit**

```bash
git add docs/whitepaper/software-whitepaper.md
git commit -m "docs: add whitepaper chapter outline"
```

### Task 3: Build the Screenshot Shot List

**Files:**
- Modify: `docs/whitepaper/assets/screenshots/README.md`

**Step 1: Add screenshot inventory table**

Include columns:

- file name
- target screen
- required app state
- source priority
- target whitepaper section

**Step 2: Define capture rules**

Include:

- fixed window size
- clean demo data
- consistent zoom and language
- avoid private or noisy data

**Step 3: Define fallback rule**

If a live screen cannot be reproduced in time:

- use `docs/design/ui/*/screen.png`
- mark it as design-sourced in the internal note

**Step 4: Verify**

Run: `sed -n '1,260p' docs/whitepaper/assets/screenshots/README.md`
Expected: screenshot plan is complete enough to execute without oral explanation

**Step 5: Commit**

```bash
git add docs/whitepaper/assets/screenshots/README.md
git commit -m "docs: define whitepaper screenshot plan"
```

### Task 4: Draft the Marketing Whitepaper Content

**Files:**
- Modify: `docs/whitepaper/software-whitepaper.md`

**Step 1: Write the first-pass content**

Requirements:

- Write for external readers
- Lead with value, not implementation
- Keep claims tied to implemented capability
- Mention OCR as experimental where applicable

**Step 2: Add image placeholders**

Insert images using relative paths, for example:

```markdown
![首页界面](./assets/screenshots/01-home.png)
```

**Step 3: Add figure captions**

For each important image, include one short explanatory sentence below the image.

**Step 4: Verify structure**

Run: `sed -n '1,320p' docs/whitepaper/software-whitepaper.md`
Expected: the file reads like a near-complete whitepaper rather than notes

**Step 5: Commit**

```bash
git add docs/whitepaper/software-whitepaper.md
git commit -m "docs: draft whitepaper content"
```

### Task 5: Capture and Store Screenshots

**Files:**
- Add: `docs/whitepaper/assets/screenshots/*.png`
- Modify: `docs/whitepaper/assets/screenshots/README.md`

**Step 1: Run the app in Web capture mode**

Recommended inputs:

- use the existing sample project or approved test dataset
- keep the UI language and state stable across captures
- run backend and frontend in development mode
- use Playwright to capture pure content screenshots from the web app, not browser chrome and not Tauri window frame

**Step 2: Capture each screenshot from the approved list**

Minimum expected files:

- `01-home.png`
- `02-create-project-dialog.png`
- `03-import-stage.png`
- `04-standardize-stage.png`
- `05-grouping-stage.png`
- `06-compliance-stage.png`
- `07-comparison-stage.png`
- `08-rule-management.png`
- `09-app-preferences.png`
- `10-export-result.png`

**Step 3: Record actual source**

For each image, note whether it came from:

- live web app capture via Playwright
- exported result capture
- design fallback

**Step 3.5: Apply capture standard**

Capture requirements:

- viewport size should be fixed, recommended `1600x1000`
- `deviceScaleFactor` should be fixed, recommended `2`
- screenshots should crop to pure application content when possible
- the same dataset and project state should be used across the full shot list
- browser UI, desktop wallpaper, and system chrome should not appear in the image

**Step 4: Verify files exist**

Run: `find docs/whitepaper/assets/screenshots -maxdepth 1 -type f | sort`
Expected: all planned screenshot files are present

**Step 5: Commit**

```bash
git add docs/whitepaper/assets/screenshots
git commit -m "docs: add whitepaper screenshots"
```

### Task 6: Implement Markdown-to-DOCX Export Script

**Files:**
- Create: `scripts/export_whitepaper_docx.py`
- Modify: `docs/whitepaper/software-whitepaper.md`

**Step 1: Choose the conversion approach**

Recommended approach:

- parse Markdown headings, paragraphs, image references, and simple tables
- generate Word using Python and local file paths

Keep scope narrow:

- do not attempt full Markdown spec coverage
- support only constructs used by the whitepaper

**Step 2: Implement the script**

Minimum features:

- input Markdown path
- output DOCX path
- heading mapping
- paragraph handling
- local image embedding
- simple table support or explicit graceful fallback

**Step 3: Add usage note**

Add a short usage block near the top of the script or in a docstring.

**Step 4: Verify export**

Run: `python scripts/export_whitepaper_docx.py`
Expected: `dist/whitepaper/software-whitepaper.docx` is generated without crashing

**Step 5: Commit**

```bash
git add scripts/export_whitepaper_docx.py docs/whitepaper/software-whitepaper.md
git commit -m "feat: add whitepaper docx export script"
```

### Task 7: Run Final Whitepaper Verification

**Files:**
- Output: `dist/whitepaper/software-whitepaper.docx`
- Modify if needed: `docs/whitepaper/software-whitepaper.md`
- Modify if needed: `scripts/export_whitepaper_docx.py`

**Step 1: Export the Word document**

Run: `python scripts/export_whitepaper_docx.py`
Expected: output docx exists

**Step 2: Verify final quality**

Check:

- all screenshots render
- heading levels are correct
- major tables are readable
- no broken image paths
- no placeholder text remains

**Step 3: Fix the highest-impact issues only**

Prefer:

- broken paths
- oversized images
- malformed headings

Avoid:

- spending time on fine typography before content is stable

**Step 4: Re-run export**

Run: `python scripts/export_whitepaper_docx.py`
Expected: revised docx is produced successfully

**Step 5: Commit**

```bash
git add docs/whitepaper/software-whitepaper.md scripts/export_whitepaper_docx.py dist/whitepaper/software-whitepaper.docx
git commit -m "docs: finalize whitepaper deliverable"
```

### Task 8: Prepare Delivery Notes

**Files:**
- Create: `docs/whitepaper/DELIVERY.md`

**Step 1: Record deliverable summary**

Include:

- final source file
- screenshot directory
- export command
- output path

**Step 2: Record known limitations**

Examples:

- OCR is experimental
- some images may be design fallback
- complex Markdown constructs are intentionally unsupported

**Step 3: Verify**

Run: `sed -n '1,220p' docs/whitepaper/DELIVERY.md`
Expected: another operator can deliver the whitepaper without extra verbal context

**Step 4: Commit**

```bash
git add docs/whitepaper/DELIVERY.md
git commit -m "docs: add whitepaper delivery notes"
```

### Task 9: Reviewer-Led Delivery Workflow

**Files:**
- Modify: `docs/plans/2026-03-31-whitepaper-implementation-plan.md`

**Step 1: Confirm execution boundary**

The Leader session should:

- not directly execute whitepaper implementation tasks
- act as reviewer and dispatcher
- release one task packet at a time unless the user approves parallel work

**Step 2: Use the execution prompt template**

For each task packet, generate a focused prompt using the template in this document.

**Step 3: Require the task report format**

Reject any report that omits:

- changed files
- commands run
- verification result
- blockers or residual risks

**Step 4: Review before continuing**

Only after the report is accepted should the next task packet be dispatched.
