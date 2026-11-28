# `pyside6-ui` Skill Directory

Universal, domain-agnostic UI/UX architecture and design system guidelines for **any PySide6 / Qt for Python desktop application** (business tools, dashboards, developer utilities, data managers, editors, scientific/monitoring apps, or enterprise software). Built around timeless UX laws, Model/View performance, and progressive disclosure.

## Directory Structure

- **`SKILL.md`**: Core universal UX laws, adaptable design tokens, PySide6 architectural rules, pre-flight quality gate, and progressive disclosure routing.
- **`references/README.md`**: Quick index for on-demand reference modules.
- **`references/design-system-and-qss.md`**: Token architecture (Light & Dark themes), QSS selector conventions, HiDPI/Fusion setup, leakage prevention, and structural primitives (`PageHeader`, `CardFrame`, `StatCard`, `StatusBadge`).
- **`references/navigation-and-shell.md`**: Application shell patterns (sidebar + `QStackedWidget`, tabbed workspaces, `QDockWidget`/toolbars), splitters, window state persistence, and action placement.
- **`references/data-tables-and-filters.md`**: High-performance `QTableView` Model/View architecture, column sizing, locale-aware numeric/date formatting, debounced search, segmented filter pills, and empty/loading states.
- **`references/forms-dialogs-and-feedback.md`**: Three-zone `QDialog` blueprints, responsive forms, inline validation, master-detail drawers, safe destructive confirmations, and non-blocking overlay toasts.
- **`references/accessibility-i18n-and-async.md`**: Keyboard-first ergonomics, accessibility (`accessibleName`, contrast), internationalization & RTL (`Qt.RightToLeft`), and non-blocking `QThreadPool` responsiveness.
- **`assets/base-theme.qss`**: Standalone starter stylesheet used only when bootstrapping a new PySide6 project that lacks an existing theme module.
