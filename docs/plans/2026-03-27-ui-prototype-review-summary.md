# UI Prototype Review Summary

> Review date: 2026-03-27
> Reviewed against: `docs/requirements/PRD-MVP-v1.md`
> Reviewed against: `docs/plans/2026-03-27-ui-prototype-design.md`

## Verdict

The prototype direction is **approved with constraints**.

It is strong enough to proceed into implementation planning because it correctly centers the product as a desktop-style five-stage workbench and gives first-class weight to problem tracking, dirty-state visibility, evidence access, and data-heavy review screens.

However, implementation planning must explicitly constrain layout complexity and define responsive fallback rules for narrower desktop widths. Several design choices should be treated as implementation decisions still pending validation, not as fixed facts.

## Gate Review

### 1. Five-stage desktop workbench fidelity

**Pass**

The proposed shell clearly uses a persistent project header, stage navigation, main workspace, problem panel, and detail region. This is aligned with the PRD's stage-workbench model rather than a locked wizard.

### 2. Problem panel as a first-class object

**Pass**

The proposal correctly treats the problem panel as a persistent work object and navigation surface rather than a passive reminder. This aligns with the PRD's cross-stage unresolved issue model.

### 3. Dirty-state visibility as a first-class object

**Pass**

The design explicitly places dirty state in both stage navigation and stage-level banners. This is compatible with the PRD's invalidation propagation model.

### 4. Evidence, traceability, and manual confirmation prominence

**Pass**

The prototype consistently keeps evidence and traceability close to the primary workflow through drawers/panels and ties them to concrete objects such as matrix cells, issues, and table rows.

### 5. Optional compliance stage handling

**Pass**

The prototype correctly distinguishes the "no requirement standard" guidance state from the matrix state and preserves the optional nature of the stage.

### 6. Comparison-stage decision clarity

**Pass with caution**

The proposal correctly emphasizes all-in lowest price, valid lowest price, block reasons, and export readiness. This matches the PRD.

The caution is that this stage can become visually overloaded if summary cards, exception details, side summaries, and large result tables all compete for first-screen priority.

### 7. Desktop-app fit

**Pass**

The proposal consistently favors fixed shells, split panes, data tables, and local context views. It reads like a desktop tool rather than a responsive web-first page set.

### 8. Fit with current repo structure

**Pass with implementation constraints**

The shell can map to the current `frontend/src/app/project-workbench.tsx` container and planned components such as stage navigation, dirty banners, compliance stage, and problem panel.

The main implementation constraint is sequencing: the workbench shell and shared layout primitives must likely be introduced before later stage UIs are layered in.

## Approved Directions

The following directions are approved for implementation planning:

1. Persistent two-level top structure:
   - project header
   - stage navigation
2. Right-side persistent problem panel with collapsible behavior
3. Drawer/panel-based evidence and traceability presentation
4. High-density table language for standardization and comparison
5. Candidate-list plus detail-pane model for grouping
6. Optional-state plus matrix-state model for compliance
7. Explicit export readiness summary on the comparison page

## Required Constraints For Implementation Planning

These constraints must be carried into the next implementation plan:

1. Define a minimum supported desktop width and fallback behavior for narrower windows
2. Keep the right problem panel collapsible by default when space gets tight
3. Choose one evidence panel pattern for MVP:
   - right drawer, or
   - bottom drawer
   Do not implement both in MVP
4. Limit the number of simultaneous summary cards on the comparison page
5. Fix table behavior rules early:
   - pinned columns
   - horizontal scrolling
   - max visible metadata columns before overflow
6. Treat grouping-stage information density as a controlled risk and design for progressive disclosure
7. Keep rule management separate from workbench flow in MVP, except for lightweight entry points such as "save as global rule"

## Open Risks To Track

1. At narrower desktop widths, a permanent right rail plus dense tables may collapse the core workspace too aggressively.
2. Compliance matrix width could become difficult to use near the PRD's upper supplier count guidance.
3. Comparison-stage content may compete too heavily for above-the-fold priority.
4. Grouping-stage list density may become cognitively heavy without careful filtering and grouping.
5. Existing import and standardize components may need structural adaptation once the shell is introduced.

## Recommendation

Proceed to the next step: convert this approved prototype direction into a frontend implementation plan centered on:

1. workbench shell and shared layout primitives first
2. problem panel and stage navigation second
3. stage-by-stage migration of existing and planned stage UIs third

Do not start by polishing page visuals in isolation. The structural shell is now the highest-leverage implementation target.
