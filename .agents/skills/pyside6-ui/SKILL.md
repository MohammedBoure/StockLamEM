---
name: pyside6-ui
description: "Universal PySide6 / Qt for Python UI/UX architecture and design system skill for any desktop application. Always use when designing, building, refactoring, styling, or reviewing PySide6 windows, navigation shells, QSS themes, dashboards, data tables, search/filter bars, CRUD forms, modal dialogs, async responsiveness, RTL/i18n, or keyboard workflows."
---

# Universal PySide6 UI/UX Architecture Skill

Design and build clean, responsive, human-centered desktop interfaces in **PySide6** for **any application domain**. Always inspect the target project's existing theme, widgets, and conventions first—integrate naturally with them rather than overwriting existing abstractions. Load only the specific reference file(s) needed for the current task.

## 1. Progressive Disclosure Routing (Read On Demand)

- **Theming, QSS stylesheets, Light/Dark mode, HiDPI, or layout primitives** → Read `./references/design-system-and-qss.md`
- **Main window architecture, sidebars, tabs, docks, splitters, or dashboards** → Read `./references/navigation-and-shell.md`
- **Data tables, lists, trees, search bars, filters, or empty/loading states** → Read `./references/data-tables-and-filters.md`
- **Modal dialogs (`QDialog`), forms, detail drawers, validation, or toast/progress feedback** → Read `./references/forms-dialogs-and-feedback.md`
- **Keyboard shortcuts, accessibility, i18n/RTL layouts, or background threading** → Read `./references/accessibility-i18n-and-async.md`
- **Bootstrapping a brand-new PySide6 app with no existing theme** → Optionally reference `./assets/base-theme.qss`

## 2. Universal UX Laws (Applied to Desktop UI)

1. **Jakob's Law**: Match established desktop conventions (`Ctrl+S` save, `Ctrl+F` search, `Esc` cancel/clear, `F5` refresh, standard menu/toolbar placement) so users feel immediately fluent.
2. **Fitts's Law**: Keep primary actions large enough (`>= 36px` height, `>= 42px` for touch/high-frequency workflows) and anchored near where the user's attention already is; avoid forcing long mouse travel for repeated actions.
3. **Hick's Law & Progressive Disclosure**: Limit visible choices at any moment. Group secondary options into drawers, tabs, or overflow menus instead of crowding every control onto one screen.
4. **Miller's Law & Gestalt Proximity**: Chunk related controls into clean visual groups (`CardFrame`) with consistent spacing (`8px` within a group, `16px–24px` between groups) so users scan structure effortlessly.
5. **Doherty Threshold (`< 400ms` Perceived Response)**: Never freeze the Qt event loop. Run I/O, network, and heavy computation off the main thread (`QThreadPool` / `QRunnable`) and show immediate loading or progress feedback.
6. **Error Prevention & Safe Recovery**: Validate inline before submission, disable impossible actions with clear tooltips explaining why, and require explicit confirmation only for destructive or irreversible operations.

## 3. Default Design System Tokens (Adaptable)

*If the project already defines a palette, typography, or spacing system, follow the project's tokens. Otherwise, use these clean, high-contrast defaults:*

- **Accent & Focus**:
  - Primary Accent: `#0F766E` (Hover: `#0D5F59`, Pressed: `#0A4A45`, Soft Tint: `#CCFBF1` / `#F0FDFA`) — or adapt to the app's brand hue.
  - Focus Ring: `2px solid` primary accent on all interactive inputs and buttons.
- **Neutral Surface Hierarchy (Light / Dark)**:
  - App Canvas: `#F8FAFC` (Light) / `#0F172A` (Dark)
  - Elevated Surface / Card: `#FFFFFF` (Light) / `#1E293B` (Dark)
  - Subtle Secondary Surface (Headers, Footers, Zebra): `#F1F5F9` (Light) / `#334155` (Dark)
  - Hairline Border / Divider: `#E2E8F0` (Light) / `#334155` (Dark)
  - Default Input Border: `#CBD5E1` (Light) / `#475569` (Dark)
- **Typography & Ink Hierarchy**:
  - Primary Text: `#0F172A` (Light) / `#F8FAFC` (Dark)
  - Secondary / Label Text: `#475569` (Light) / `#CBD5E1` (Dark)
  - Muted / Disabled Text: `#94A3B8` (Light) / `#64748B` (Dark)
  - Font Stack: `"Segoe UI", "Inter", "Cairo", system-ui, sans-serif` (cleanly supports Latin, Arabic, and multilingual UIs).
  - Type Scale: Page Title `20px` Bold, Section Title `15px` SemiBold, Body/Cell `13px` Regular, Label/Caption `12px` Medium, Hero Metric `22px–26px` Bold.
- **Semantic Status Tokens**:
  - Success: Text `#15803D`, Fill `#DCFCE7` (Dark: `#4ADE80` / `#14532D`)
  - Warning: Text `#B45309`, Fill `#FEF3C7` (Dark: `#FBBF24` / `#451A03`)
  - Danger: Text `#B91C1C`, Fill `#FEE2E2` (Dark: `#F87171` / `#450A0A`)
  - Info: Text `#0369A1`, Fill `#E0F2FE` (Dark: `#38BDF8` / `#0C4A6E`)
- **Spacing & Geometry**:
  - Spacing Scale: `4px` (tight), `8px` (related elements), `12px` (toolbar/form gap), `16px` (card padding), `20px–24px` (page margins).
  - Control Heights: Standard Inputs/Buttons `36px`, High-Frequency/Touch Controls `42px+`, Table Header `38px`, Table Row `>= 42px`.
  - Border Radii: Controls `6px`, Cards/Panels `10px`, Modals `12px`, Status Pills `11px`.

## 4. Non-Negotiable PySide6 Engineering Rules

1. **Adapt to Existing Codebase First**: Reuse existing theme constants, base widgets, and helpers before introducing new abstractions.
2. **Clean Spatial Grouping**: Use `QFrame` cards (`1px` hairline border, subtle surface contrast) or `QSplitter` panes instead of heavy nested `QGroupBox` borders.
3. **Model/View & Clean Cell Editing**: Use `QTableView` / `QTreeView` with `QAbstractItemModel` (`QAbstractTableModel`), `QSortFilterProxyModel`, and `QStyledItemDelegate`. Avoid populating `QTableWidget` cells with permanent per-row `QComboBox`, `QLineEdit`, or `QSpinBox` widgets—render clean locale-formatted text and open an editor only on click/double-click (`QStyledItemDelegate`), while supporting direct keyboard numeric entry for quantities.
4. **Semantic QSS & Specificity Isolation**: Style via `setObjectName(...)` roles (`PrimaryButton`, `DangerButton`, `Card`, `PageTitle`) and dynamic properties (`[invalid="true"]` with `unpolish()`/`polish()`) rather than scattering raw `setStyleSheet(...)` strings. Always use `#ObjectName` selectors on embedded cell/toolbar widgets so app-level descendant rules (e.g., `QTableWidget QLineEdit`, `QTableWidget::item { padding }`) cannot crush or clip them.
5. **Responsive Layouts & Pane-Scoped Toolbars**: Never call `setFixedSize()` on windows, cards, or tables. Rely on layouts, stretch factors, `QSizePolicy`, and `QScrollArea`. In `QSplitter` multi-pane layouts, keep each pane's search/filter toolbar inside the pane it controls rather than spanning full-width above unrelated sibling panes.
6. **Explain Disabled States & Validate Inline**: Every `setEnabled(False)` call MUST include `setToolTip(...)` explaining why it is disabled. Validate inputs inline with helper error labels—never interrupt typing with `QMessageBox` or chain sequential modal popups (`Dialog A -> Dialog B`) for a single submit action.
7. **One Canonical Action & Button Hierarchy**: Never duplicate the same action across parent tab corners and child toolbars, or top bars and footers. Reserve **one** filled Primary CTA per panel strictly for the main commit/create action (never for `Refresh` / `Reset`), keep secondary/utility actions in neutral slate (max 1–2 outlined accents), and avoid stacking 3–4 competing mode buttons or orphan full-width bars.
8. **Keyboard-First & Non-Blocking Feedback**: Set initial focus in `showEvent()`, wire `setTabOrder()`, support `Enter`/`Esc`, and use non-blocking overlay toasts or status bars for routine confirmations—reserving modal dialogs for destructive confirmations.
9. **Restrained, Content-Fitted Status Badges**: Never stretch table status pills to a wide uniform fixed width or flood every healthy row with heavy saturated badges. Fit pill width dynamically to `QFontMetrics.horizontalAdvance(text) + padding`, keep routine healthy states visually quiet (e.g., subtle `7px` status dot + crisp text) so warnings/errors pop immediately, and preserve row selection and bottom hairline dividers inside custom `QStyledItemDelegate.paint()` overrides.

## 5. Pre-Flight Quality Gate

Before finalizing any PySide6 UI implementation, verify:
- Does every view have clear visual hierarchy (`PageHeader` or structured workspace bar) with at most one filled Primary commit CTA, neutral utility buttons (including `Refresh`), and no duplicate actions across tab corners and child toolbars?
- Do all interactive controls share uniform heights (`>= 36px`), clear hover/focus states, and sufficient color contrast?
- Are numeric/monetary columns consistently locale-formatted and right-aligned across both display and edit cells, with no permanent per-row `QComboBox`/`QLineEdit` clutter?
- Are table status badges sized to their text, visually calm on healthy rows, and aligned seamlessly with row selection and dividers?
- Do empty, sparse (1–3 row), zero-match, and loading states avoid dead whitespace voids that push summary totals or primary CTAs far away from the data?
- Are active session/target contexts (e.g., selected client or mode) visible inline before submission without chaining multiple modal dialogs?
- Does every disabled control explain itself via `setToolTip()`?
- Are long-running tasks offloaded from the UI thread so the window never freezes?
