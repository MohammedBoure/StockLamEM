# Navigation, Application Shell & Workspace Architecture

Choose the `QMainWindow` shell pattern that fits the application's workflow complexity rather than forcing one layout on every program.

## 1. Choosing the Right Shell Pattern

1. **Sidebar + `QStackedWidget` (Multi-Section Apps, Dashboards, Data Managers)**:
   - Left navigation rail (`200px–240px` expanded, optional `56px` icon-only collapsed mode) containing grouped navigation items (`QButtonGroup` with checkable `NavItem` buttons) and an optional bottom footer (Settings, Theme Toggle, User/Version).
   - Right main area: `QStackedWidget` hosting lazy-loaded or cached page views inside a `PageCanvas`.
2. **Tabbed Workspace (`QTabWidget` with `documentMode=True`) (Browsers, Multi-Document Editors, Query Tools)**:
   - Use closable/movable tabs when users work on multiple independent documents or sessions in parallel.
   - Provide an empty-state welcome screen when all tabs are closed.
3. **Tool / IDE / Studio Shell (`QMenuBar` + `QToolBar` + `QDockWidget`) (Editors, Scientific/Media/CAD Tools)**:
   - Use `QDockWidget` panels for inspectors, file trees, console logs, and property editors so users can dock, float, or toggle panels freely.
   - Keep `QToolBar` icons crisp, grouped with `addSeparator()`, and paired with tooltips showing keyboard shortcuts (e.g., `"Save (Ctrl+S)"`).

## 2. Multi-Pane Workspaces (`QSplitter`)

- Use `QSplitter` (`childrenCollapsible=False` unless intentional) for master-detail lists, side-by-side editors/previews, or log panes.
- Set sensible `setSizes([...])` ratios and minimum widths on panes so neither side collapses into an unreadable sliver.
- **Pane-Scoped Toolbars (Gestalt Proximity)**: Never place a pane-specific search/filter bar full-width across the top of a `QSplitter` where it spans visually above an unrelated sibling pane (e.g., a catalog search bar sitting above a cart panel). Mount each pane's search, filter, and utility buttons inside the pane they control.
- **Sparse Table & Action Proximity (No Dead Whitespace Voids)**: In split views where a side table often holds only 1–3 rows (e.g., an active cart or selection list), do not let an oversized empty table body push the summary card and primary CTA 400px+ down to the bottom edge. Keep the table compact or proportional, display inline session/client context right above or below the list, and anchor totals/actions near the user's focus.

## 3. Responsive Multi-Screen Sizing & `QSettings` Persistence

- **Screen-Aware Initial Sizing**: Never hardcode oversized `resize(...)` or large `setMinimumSize(...)` values that overflow `1280×720` / `1366×768` laptops or `125%–150%` HiDPI displays. Compute initial dimensions from `QGuiApplication.primaryScreen().availableGeometry()` (e.g., `min(1220, int(avail.width() * 0.86))` × `min(760, int(avail.height() * 0.86))`), and keep `minimumSize` modest (`~760×520` for main windows, `~400×320` for dialogs) so OS half-screen snapping works cleanly.
- **Responsive Breakpoints & Scrollable Pages**:
  - Override `resizeEvent()` on `QMainWindow` to auto-collapse the navigation sidebar (`~58px` icon rail) when window width drops below `1020px`, reclaiming horizontal space for tables and split views.
  - Wrap dense dashboards, settings pages, and multi-card layouts in a borderless `QScrollArea` (`widgetResizable=True`) so short viewports never clip controls.
  - Never call `setFixedWidth()` on content panels or cards—rely on stretch factors and `QSplitter` with reasonable `minimumWidth` (`260px–320px`).
- **Window & Layout State Persistence (`QSettings`)**:
  - Persist and restore `QMainWindow.saveGeometry()` / `restoreGeometry()`, `saveState()` / `restoreState()` (for docks/toolbars), and `QSplitter.saveState()` / `restoreState()` using `QSettings` on close and startup.
  - Always guard `restoreGeometry()` against disconnected/changed monitor setups and clamp window bounds to `availableGeometry()` so windows never open off-screen or larger than the current display.

## 4. Canonical Action Placement (Zero Duplication)

- **Top-Right (`PageHeader` or `QTabWidget::cornerWidget`)**: Primary view-level creation/global actions (`+ New`, `Import`, `Export`). If a global `Refresh` lives in a tab bar's corner widget, **never** place a second `Refresh` button inside the child tab's filter bar directly beneath it.
- **Card / Table Toolbar**: Context-local search, filters, and view toggles scoped strictly to that table/pane.
- **Detail Drawer / Inspector**: Contextual actions for the currently selected item (`Edit`, `Duplicate`, `Delete`).
- **Modal Footer**: Dialog-level commit/cancel actions (`Cancel` on left/secondary, `Save` on far right).
- **Status Bar (`QStatusBar`)**: Passive, transient system state (connection status, item count, background task progress, zoom level)—never critical errors.
