# Design System, QSS Architecture & Structural Primitives

## 1. Centralized Theme & QSS Strategy

- **Single Source of Truth**: Keep color tokens and QSS rules in one centralized theme module (or load `./assets/base-theme.qss` when starting a brand-new project) and apply them once at the `QApplication` level using `app.setStyle("Fusion")` for consistent cross-platform rendering.
- **OS Color Scheme & Palette Isolation**: On Windows 11 / macOS with OS Dark Mode active, Qt 6.5+ injects a dark system `QPalette` (dark surfaces, white text) that causes invisible white text in `QTableView` and dark backgrounds in `QDialog`, `QScrollArea` bodies, `QTabBar`, and `QSplitter::handle` under a Light QSS theme. Always:
  1. Call `app.styleHints().setColorScheme(Qt.ColorScheme.Light)` (or `.Dark` matching the active theme, guarded with `hasattr(app.styleHints(), "setColorScheme")`).
  2. Explicitly style `color` and `background-color` on `QDialog`, `QMessageBox`, `QMenu`, `QTableView`/`QTableWidget` (and `::item`), `QTabWidget::pane`, `QTabBar::tab`, `QSplitter::handle`, and `QComboBox QAbstractItemView`.
- **Light & Dark Theme Readiness**: Define semantic color tokens (`canvas`, `surface`, `subtle`, `border`, `text_primary`, `text_secondary`, `accent`) in a dictionary or dataclass and generate/swap the QSS from those tokens rather than hardcoding hex values inside widget classes.
- **Prevent QSS Selector Leakage & Specificity Collisions**:
  - Never apply broad descendant rules like `QFrame { border: 1px solid ...; }` on container widgets, or they will leak into child dialogs, popups, and combo-box dropdowns.
  - Scope styles using explicit `setObjectName(...)` roles (`PageCanvas`, `Card`, `SubtlePanel`, `PageTitle`, `PageSubtitle`, `SectionTitle`, `FieldLabel`, `ErrorText`, `PrimaryButton`, `DangerButton`, `FilterPill`) and strict child/ID selectors (`QFrame#Card`, `QPushButton#PrimaryButton`).
  - **Table Cell Widget & Item Padding Guard**: App-level descendant rules like `QTableWidget QLineEdit` (specificity 2) override unscoped `QLineEdit` (specificity 1) on embedded cell widgets, and `QTableWidget::item { padding: 8px; }` shrinks the inner cell-widget rect vertically and horizontally—crushing or clipping inputs and buttons. Always target embedded cell widgets by `#ObjectName` (`QLineEdit#CellPriceInput { min-height: 26px; padding: 2px 6px; }`), keep `defaultSectionSize >= 44`, and scope compact cell padding (`QTableWidget#MyTable::item { padding: 4px 6px; }`).
- **Dynamic State Properties**: For runtime states such as validation errors (`widget.setProperty("invalid", True)`) or active selection (`widget.setProperty("active", True)`), always force Qt to recalculate styles:
  ```python
  widget.style().unpolish(widget)
  widget.style().polish(widget)
  ```
- **HiDPI & Crisp Icons**: Enable Qt's default HiDPI scaling (built-in in PySide6) and prefer SVG/vector icons rendered at `devicePixelRatio` over fixed-size raster bitmaps.
- **Custom Vector Indicators for Styled Controls (`QCheckBox`, `QComboBox`, `QSpinBox`)**: Styling `border` or `background-color` on these widgets in QSS disables native OS indicator painting—producing solid colored checkboxes without a checkmark, crude fallback triangles, and clipped black separator lines. Always provide crisp SVG `image: url(...)` assets for `QCheckBox::indicator:checked`, `QComboBox::down-arrow`, `QSpinBox::up-arrow`, and `QSpinBox::down-arrow`, and set `border: none; background: transparent;` on `::drop-down`, `::up-button`, and `::down-button`.
- **Slim Modern Scrollbars**: Style vertical/horizontal `QScrollBar` handles (`8px` wide/tall, rounded `4px`, subtle handle, zero arrow buttons) so dense tables, trees, and lists stay uncluttered.

## 2. Reusable Structural Primitives

Compose screens from predictable, reusable building blocks:

- **`PageHeader`**:
  - Horizontal bar at the top of a view.
  - Left side: Vertical stack of `PageTitle` (`20px` Bold) and optional `PageSubtitle` (`13px` secondary text).
  - Right side: Horizontal action group (`8px` spacing) with secondary actions (`Refresh`, `Export`, `Settings`) and at most **one** `PrimaryButton` (`+ New Item`).
- **`CardFrame`**:
  - `QFrame` (`objectName="Card"`) with elevated surface fill, `1px` hairline border, `10px` radius, `16px` inner padding, and `12px` vertical spacing.
- **`StatCard` / `KpiCard` Strip**:
  - Row of 3 to 4 equal-stretch summary cards (`min-height: 84px`) for overview/dashboard views.
  - Top line: Uppercase muted label (`11px` Bold).
  - Bottom line: Bold tabular metric (`20px–24px` Bold) paired with an optional trend/status badge.
- **`StatusBadge`**:
  - Compact capsule `QLabel` (`border-radius: 11px`, `padding: 3px 10px`, `font-size: 11px`, `font-weight: 700`) mapped to semantic tokens (Success, Warning, Danger, Info, Neutral).

## 3. Spatial & Alignment Discipline

- **Margins & Gaps**: Use `20px–24px` outer page margins and `16px` vertical gaps between major sections (`PageHeader`, `StatCard` strip, main `CardFrame`).
- **No Floating Orphan Controls**: Every button, search box, or filter must belong to a structured `PageHeader`, toolbar, or `CardFrame`.
- **Visual Hierarchy & Outline Discipline**:
  - Differentiate primary, secondary, and destructive actions clearly—never place two filled primary-colored buttons in the same view/action group.
  - Reserve the filled `PrimaryButton` accent strictly for the **main commit/create CTA** (e.g., `Save`, `+ New Item`, `Complete Payment`)—**never** style passive utility actions (`Refresh`, `Reset`, `Filter`) with the primary accent fill.
  - Default secondary/utility actions to neutral slate (`#CBD5E1` border, `#334155` text), reserving accent-colored outlines for at most 1–2 contextual actions so borders never compete (`Outline Overload`).
  - When a panel offers multiple submission modes (e.g., cash/credit/delivery), use **one** Primary CTA paired with a compact segmented mode selector or secondary menu rather than stacking 3–4 full-width and half-width outlined action buttons.
