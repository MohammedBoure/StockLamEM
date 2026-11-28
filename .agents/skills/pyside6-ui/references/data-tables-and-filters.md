# Data Tables, Trees, Search Bars, Filters & Empty States (PySide6)

## 1. Unified Search & Filter Toolbar

Place search and filter controls inside the top area of the data view's `CardFrame`, separated from the table header by a subtle divider or spacing:

- **Debounced Search Input**:
  - Configure `QLineEdit` with a clear, specific placeholder (`"Search by name, ID, or tag..."`) and `setClearButtonEnabled(True)`.
  - Prevent placeholder truncation when pairing a search `QLineEdit` with `addStretch(1)`: always set an explicit `setMinimumWidth(...)` (e.g., `240px–280px`, or `QFontMetrics` placeholder width + `56px` padding) or assign a layout stretch (`addWidget(search, 1)` with `setMaximumWidth(380)`), because Qt's default `QLineEdit` width collapses to ~`130px` beside a stretch spacer.
  - Use a single-shot `QTimer` (`250ms`) on `textChanged` so proxy filtering or async queries run smoothly after typing pauses.
  - Connect `returnPressed` to cancel the timer and filter immediately; handle `Qt.Key_Escape` to clear the search text and restore focus.
- **Segmented Filter Pills**:
  - Group checkable `QPushButton`s (`objectName="FilterPill"`) inside an exclusive `QButtonGroup` for high-frequency status/category filters.
  - Display live counts in pill labels when helpful (e.g., `All (124)`, `Active (98)`, `Archived (26)`).
  - For more than 5 filter categories or multi-criteria filtering, use a compact `QComboBox` or expandable filter popover instead of wrapping dozens of pills.

## 2. `QTableView` / `QTreeView` Model-View Architecture

- **Strict Model/View Separation**: Use `QTableView` (or `QTreeView` for hierarchical data) backed by `QAbstractTableModel` / `QAbstractItemModel` and `QSortFilterProxyModel`.
- **Standard Table Ergonomics**:
  - Enable alternating row colors (`setAlternatingRowColors(True)`), single or multi-row selection (`SelectRows`), column sorting (`setSortingEnabled(True)`), `NoEditTriggers` (unless inline editing is explicitly intended), hidden vertical header, `38px` header height, and `>= 42px` row height.
- **Column Sizing Strategy**:
  - Assign `QHeaderView.ResizeMode.Stretch` to the primary descriptive column (e.g., `Title`, `Name`, `Description`) so the table fills 100% of its container width with zero dead margin.
  - Use `ResizeToContents` or `Fixed` with explicit minimum widths (`90px–140px`) on IDs, dates, numbers, status badges, and action columns.
- **Locale-Aware Alignment & Formatting**:
  - Return `Qt.AlignRight | Qt.AlignVCenter` in `TextAlignmentRole` for all numeric, currency, duration, and quantity columns so decimal points/units align vertically.
  - Format numbers, dates, and currencies using `QLocale` or the project's configured locale rather than hardcoding a single region's format.
- **Clean Row Interaction**:
  - **No Permanent Per-Row `QComboBox` or `QLineEdit` Clutter**: Avoid embedding live `QComboBox`, `QLineEdit`, or `QSpinBox` widgets in every row of a table—they create visual noise, raw unformatted numbers (`16660` beside `16 660,00 DA`), tab-order traps, and QSS cascade clipping. Render values as clean, locale-formatted right-aligned text (`16 660,00 DA`) and activate an inline `QStyledItemDelegate` editor on click/double-click/`F2` (keeping `+/-` quantity steppers clickable *and* allowing direct keyboard numeric entry for multi-unit quantities).
  - When embedding compact action buttons inside cells (`+`, `-`, `Trash`), assign a dedicated `#ObjectName` (e.g., `QPushButton#CellIconBtn`) and set **explicit** `min-width`/`max-width`/`min-height`/`max-height` in QSS matching the intended button size (`>= 28x28px` for `+/-` steppers, `>= 32x30px` with `16x16` icon for delete/row action buttons) and `padding: 0px;`—**never** use `min-width: 0px; min-height: 0px;` in QSS (which overrides `setFixedSize()` and shrinks buttons to ~`18x20px`). Scope compact item padding (`QTableWidget#Id::item { padding: 4px 6px; }`) inside `>= 48px` rows so `36px` toolbar button padding or `8px` cell padding does not clip button borders.
  - Size every column containing embedded widgets so `columnWidth >= totalWidgetWidth + horizontalItemPadding` (e.g., `>= 112px` for a `− qty +` stepper with two `28px` buttons, `>= 68px` for `"Suppr."`), and disable `wordWrap` on single-line currency columns (`setWordWrap(False)`) with enough width (`>= 135px`) so amounts never wrap or truncate with `...`.
  - **Status Badge Design Discipline (`StatusBadgeDelegate`)**:
    - **Content-Fitted Pill Width**: Compute width dynamically via `min(option.rect.width() - 12, QFontMetrics(font).horizontalAdvance(text) + 22)`—never draw wide fixed-width capsules that leave short words (`Out`, `Paid`, `نفد`) swimming in empty space.
    - **Signal-Over-Noise (Quiet Healthy States)**: Avoid turning a status column into a loud wall of bright green pills. Render routine/healthy states (`In Stock`, `Paid`, `متوفر`, `مدفوعة`) with a subtle `7px` semantic dot + calm text, reserving soft tinted pills for warnings and critical alerts (`Low Stock`, `Expired`, `Out of Stock`).
    - **Selection & Divider Continuity**: In `paint()`, draw the row's normal/alternating/selected background across `option.rect` *and* preserve the bottom `1px` row hairline divider so the status cell blends smoothly with sibling columns instead of looking like an isolated sticker.
  - Bind `doubleClicked` (and `Enter` key) to open the primary detail/edit view, and provide a clean `QMenu` context menu (`customContextMenuRequested`) for secondary row actions.
  - If a row action button is rendered and disabled, set a `setToolTip(...)` explaining why.

## 3. Empty, Zero-Match & Loading States (`QStackedWidget`)

Wrap the data view inside a `QStackedWidget` with three dedicated states so users never stare at an unexplained blank grid:

1. **Active Data View**: The `QTableView`/`QTreeView` paired with an optional compact footer bar (row count, selection summary, or column totals).
2. **Empty / Zero-Match View**: Centered vertical layout (`min-height: 240px`) with a subtle icon, clear title (`"No matching results"` or `"No items yet"`), concise helper text, and one clear recovery button (`"Reset Filters"` or `"+ Create Item"`).
3. **Loading View**: Centered progress indicator (`QProgressBar` indeterminate or spinner) and `"Loading data..."` label while background workers fetch records.
