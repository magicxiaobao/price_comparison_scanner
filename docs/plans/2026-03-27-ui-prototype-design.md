# UI Prototype Design Brief

> Scope: Frontend UI prototype direction for the MVP desktop workbench
> Source of truth: `docs/requirements/PRD-MVP-v1.md`
> Approved on: 2026-03-27

## 1. Design Objective

Produce a desktop-style UI prototype for the "三方比价支出依据扫描工具" MVP that matches the PRD's five-stage workbench model and supports later frontend implementation with the existing React + Tauri + Tailwind stack.

This prototype is not a marketing website and not a generic CRUD admin panel. It is an audit-oriented workbench for high-control, traceable, exception-aware review work.

## 2. Design Positioning

### Visual tone

- Professional audit tool baseline
- Stronger data-workbench visual expression is allowed
- Still must feel like a desktop app, not a mobile-first web page
- Dense but readable
- Serious, stable, evidence-first

### Explicitly desired qualities

- Clear stage progression
- Strong status visibility
- High information density
- Fast scanning of unresolved issues
- Traceability and evidence surfaced as first-class UI objects
- Suitable for 1280-1600px desktop workspace widths

### Explicitly avoid

- SaaS landing-page aesthetics
- Large decorative empty areas
- Overuse of floating cards
- Mobile-style vertical stacking as the default layout
- Hidden critical status inside deep dialogs
- Over-designed gradients or "dashboard for dashboard's sake"

## 3. Product Form To Prototype

The PRD defines the product as a five-stage workbench, not a locked wizard.

The prototype must reflect:

1. Users can move across 5 stages
2. Upstream changes can invalidate downstream stages
3. Problems are aggregated across stages
4. Manual confirmation is central to the workflow
5. Export is allowed even with marked issues, but issues must remain visible

## 4. Core IA

The prototype must include three top-level surfaces:

1. Home
2. Project Workbench
3. Rule Management

The Project Workbench must be treated as the product core and receive most of the design effort.

## 5. Workbench Frame Requirements

The workbench should use a persistent desktop layout:

- Top project header
- Stage navigation bar
- Main stage workspace
- Persistent problem panel
- Context detail region for evidence / traceability / issue detail

### Recommended frame

- Header: project name, stage summary, save state, primary export action
- Stage nav: 5 stages with status badges (`pending`, `completed`, `dirty`, `skipped`)
- Main region: current stage task surface
- Right rail: problem panel, counts, stage jump links
- Side drawer or bottom detail panel: evidence detail, source location, traceability, change log

## 6. Page and State Deliverables

The UI prototype must contain at least these screens:

1. Home
2. Workbench shell
3. Import stage
4. Standardize stage
5. Grouping stage
6. Compliance stage
7. Comparison and export stage
8. Rule management

For each key workbench stage, show at least:

- Default state
- Pending-problem state
- Dirty / invalidated state

## 7. Stage-Specific Design Requirements

### 7.1 Home

Purpose:

- Create new project
- Resume recent projects
- Open rule management

Requirements:

- Keep this page light and utilitarian
- Recent projects table should expose supplier count, current stage, dirty/completed cue, updated time
- Avoid giving home more visual weight than the workbench

### 7.2 Import Stage

Must emphasize the file-processing pipeline:

- Upload
- Parsing progress
- Supplier confirmation
- Table selection
- Ready-for-next-step summary

Must visually distinguish:

- Structured extraction
- OCR / experimental parsing
- Failed parse / manual fallback recommendation

### 7.3 Standardize Stage

This is the first heavy data screen and should establish the product's table language.

Required structure:

- Upper area: column mapping confirmation
- Lower area: standardized editable table
- Side/context cues: low-confidence fields, unmapped fields, rule conflicts, required-field missing

Must surface:

- Original column -> standard field mapping
- Hit rule / match type
- manual edit state
- field-level confidence and unresolved status

### 7.4 Grouping Stage

The UI must make users feel they are reviewing candidate group decisions, not browsing raw rows.

Required structure:

- Candidate groups list
- Unconfirmed items / exceptions bucket
- Group detail pane
- Actions: confirm, split, merge, mark non-comparable

Must distinguish:

- High confidence candidate
- Medium confidence candidate needing review
- Hard-stop constraints like unit mismatch / model conflict / brand conflict

### 7.5 Compliance Stage

This stage is optional and the prototype must reflect that clearly.

Two entry states are required:

- No requirement standard entered: guidance state with "add/import requirements" and "skip this step"
- Requirements present: compliance matrix state

Matrix state requirements:

- Suppliers on one axis
- Requirements on the other
- Strong color semantics for `符合 / 部分符合 / 不符合 / 无法判断`
- Evidence panel reachable from a cell
- Manual confirmation and "acceptable" action visible

### 7.6 Comparison and Export Stage

This page must answer, at a glance:

- Can this item be compared?
- What is the all-in lowest price?
- What is the valid lowest price?
- Why is an item blocked or risky?
- Is the project export-ready?

Required content:

- grouped comparison table
- all-in lowest price
- valid lowest price
- average / spread
- compliance summary
- exception markers
- export summary and warnings

## 8. Persistent Problem Panel

The problem panel is a core object, not a secondary widget.

It must:

- Aggregate unresolved issues across stages
- Show counts by type
- Indicate severity
- Jump users to the relevant stage
- Clearly show the empty state: all issues resolved, ready to export

Important issue groups include:

- unconfirmed supplier names
- unmapped fields
- rule conflicts
- low-confidence unconfirmed fields
- unit mismatch
- tax-basis anomalies
- unconfirmed grouping
- required field missing
- unconfirmed compliance matches
- mandatory requirements unmet
- unclear requirement matches
- partial matches not yet accepted

## 9. Desktop-App Behavior Requirements

Because implementation uses web frontend technology but the product is a desktop app, the prototype must align with desktop habits:

- Horizontal layouts are preferred over long mobile stacks
- Tables, panes, drawers, split views, and detail panels should be used heavily
- Important context should stay visible while editing
- Avoid frequent full-page navigation
- Progress, failure, dirty state, and task completion should look like tool software feedback

## 10. Visual System Requirements

### Color use

- `completed`: green
- `dirty`: orange
- `warning`: yellow
- `error / conclusion blocked`: red
- `skipped`: gray
- `current stage / active context`: controlled blue or teal accent

### Typography and spacing

- Use compact, desktop-friendly spacing
- Prioritize scanability over spacious web layouts
- Headings should support structure, not decoration

### Data presentation

- Tables and matrix views are the visual backbone
- Use highlights, badges, stripes, pinned columns, and row states carefully
- Do not hide key metadata such as confidence, source, or manual override

## 11. Constraints From Current Repo

The prototype must be compatible with the current frontend direction:

- `frontend/src/app/project-workbench.tsx` is already the stage container entry
- Existing stages already started: import and standardize
- Current stack uses React 19, Tailwind 4, TanStack Table, dnd-kit, Zustand, Tauri

Design should therefore prefer:

- A workbench shell that can host incremental stage implementation
- Reusable layout primitives
- Patterns implementable without introducing a heavyweight design system dependency

## 12. Deliverables Required From The UI Agent

The assigned UI agent must deliver:

1. A complete workbench shell concept before polishing individual screens
2. Key screen prototypes for all major stages
3. A lightweight component inventory
4. State annotations for normal / issue / dirty cases
5. Short rationale for major layout choices

Suggested component inventory:

- stage navigation
- problem panel
- status badge set
- dirty banner
- evidence drawer
- editable data table
- matrix cell states
- exception banner
- export readiness summary

## 13. Review Checklist For Leader

Review against these gates:

1. Does the workbench clearly read as a five-stage desktop workflow rather than a web wizard?
2. Are `dirty` propagation and unresolved problems visually first-class?
3. Are evidence, source location, manual confirmation, and traceability surfaced prominently?
4. Is the optional compliance stage handled correctly in both skipped and active modes?
5. Can users tell when a comparison conclusion is blocked and why?
6. Is the visual density appropriate for a desktop tool?
7. Can the design reasonably map to the current React/Tauri frontend structure?
8. Does the prototype avoid generic SaaS styling?

## 14. Recommendation To Implementation Team

Prototype the workbench frame first, then the data-heavy stages, then the home and rule management pages. If the frame is wrong, the whole product will feel wrong even if individual pages are polished.
