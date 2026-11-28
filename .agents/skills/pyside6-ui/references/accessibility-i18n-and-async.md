# Keyboard Navigation, Accessibility, i18n/RTL & Async Responsiveness

## 1. Keyboard-First Ergonomics & Focus Lifecycle

- **Initial Focus**: Override `showEvent()` on pages and dialogs to focus the primary input (e.g., search field, first form field) so users can start typing immediately without clicking.
- **Logical Tab Order**: Explicitly call `QWidget.setTabOrder(a, b)` on complex forms and multi-pane views so `Tab` / `Shift+Tab` never jumps erratically.
- **Universal Shortcuts**:
  - `Ctrl+F`: Focus primary search/filter input.
  - `Ctrl+S`: Save / apply in forms and editors.
  - `F5` / `Ctrl+R`: Refresh current view data.
  - `Enter`: Submit active form/search or open selected row.
  - `Esc`: Clear active search/selection, or close active drawer/modal.
- **Shortcut Discoverability**: Include shortcuts in button/action tooltips (`"Refresh (F5)"`) and `QAction` menus.

## 2. Accessibility & Visual Clarity

- **Accessible Metadata**: Set `setAccessibleName(...)` and `setAccessibleDescription(...)` on icon-only buttons, custom painted widgets, and status indicators.
- **Color Independence**: Never rely on color alone to convey state—pair semantic colors with text labels (`StatusBadge`) or distinct icons.
- **Contrast & Legibility**: Maintain strong contrast (`>= 4.5:1` for normal text, `>= 3:1` for large text/UI borders) in both Light and Dark themes.
- **Visible Focus Indicators**: Never remove focus outlines (`outline: none` without a replacement border) on keyboard-focusable controls.

## 3. Internationalization (i18n) & Right-to-Left (RTL) Support

- **Translation Readiness**: Wrap user-facing strings in `self.tr(...)` or `QCoreApplication.translate(...)`. Avoid concatenating translated fragments (`"Delete " + name`); use format placeholders (`self.tr("Delete {0}?").format(name)`).
- **Flexible Sizing for Translated Text**: Never hardcode tight pixel widths on buttons or labels—use `min-width` + padding and `QSizePolicy.Preferred` / `MinimumExpanding` so longer translations (e.g., German, French, Arabic) never clip. For `QLineEdit` / `QComboBox` inputs placed next to `addStretch(1)` in toolbars, always set `setMinimumWidth(240)` (or give the input a stretch factor) so placeholders and labels are never crushed to ~`130px`.
- **RTL Layout Discipline (`Qt.RightToLeft`)**:
  - Use `QBoxLayout`, `QGridLayout`, and `QFormLayout` rather than manual `move()`/`setGeometry()` coordinates so Qt mirrors layouts automatically when `app.setLayoutDirection(Qt.RightToLeft)` is active.
  - Anchor overlay toasts and directional icons relative to `layoutDirection()` rather than hardcoding left/right offsets.
  - **SpinBox / ComboBox Arrow Clearance in RTL**: Avoid large symmetric horizontal `padding` (e.g., `padding: 0 10px`) on `QSpinBox` and `QDoubleSpinBox` under `Qt.RightToLeft` with native Windows styling, as the up/down arrows will overlap the numeric text; pair `app.setStyle("Fusion")` with compact padding (`padding: 2px 6px`).

## 4. Non-Blocking Async & Threading (Doherty Threshold)

- **Never Block the Main GUI Thread**: Database queries, network requests, file parsing, and heavy computation must run off the main thread.
- **Recommended PySide6 Pattern**:
  - Use `QThreadPool.globalInstance()` with `QRunnable` + a `QObject` signals helper (`finished`, `error`, `progress`), or `QThread` + worker object for long-lived streams.
  - Update UI widgets **only** on the main thread via Qt signals/slots—never mutate widgets directly from a worker thread.
- **Prevent Double-Submission**: Disable the triggering button (with a clear label like `"Saving..."` and tooltip) when an async action starts, and re-enable it inside a `finally` / signal handler when done.
