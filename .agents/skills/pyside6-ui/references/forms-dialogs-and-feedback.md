# Forms, Modal Dialogs, Detail Drawers & Feedback (PySide6)

## 1. Three-Zone Modal Dialog Architecture (`QDialog`)

Structure create/edit/settings dialogs as a clean three-zone vertical layout (`contentsMargins=0`, `spacing=0`):

1. **Modal Header (Elevated surface, bottom `1px` border, padding `16px 20px`)**:
   - Left: Bold title (`16px`, e.g., `"Create Item"`, `"Preferences"`) and optional short subtitle.
   - Right: Subtle close button (`×`, bound to `Esc`).
2. **Scrollable Form Body (`QScrollArea`, `widgetResizable=True`, padding `20px`)**:
   - Use a responsive 2-column `QGridLayout` (`16px` horizontal gap, `14px` vertical gap) for medium/large forms, or a single-column `QVBoxLayout` for compact dialogs (`< 4` fields).
   - Always call `grid.setColumnStretch(0, 1)` and `grid.setColumnStretch(1, 1)` on 2-column forms so `QComboBox` / `QSpinBox` columns never shrink to 25% width next to `QLineEdit` columns, and size the dialog proportionally to its content (`420px–520px` height) to avoid dead vertical whitespace.
   - Place `FieldLabel` (`12px` SemiBold) **above** each input (`4px` vertical gap) so labels never clip across languages or RTL/LTR switches.
   - Span full width (`columnSpan=2`) for multi-line text areas, file pickers, or wide descriptions.
3. **Sticky Modal Footer (Subtle secondary surface, top `1px` border, padding `12px 20px`)**:
   - Right-aligned action row (`addStretch()` on the left) with secondary `Cancel` (`Esc`) and primary `Save` / `Apply` (`PrimaryButton`, `Ctrl+S`).

## 2. Inline Field Validation

- Never interrupt typing with `QMessageBox` popups for missing or invalid inputs.
- Pair each validated input with a small `ErrorText` `QLabel` (`11px`, hidden by default).
- When validation fails on blur or submit:
  1. Set `widget.setProperty("invalid", True)` and refresh style via `unpolish()` / `polish()`.
  2. Show concise, actionable error messages on all invalid fields simultaneously (e.g., `"Port must be between 1 and 65535."`).
  3. Move focus to the first invalid input.
- Clear the `invalid` state as soon as the user corrects the input.

## 3. Master-Detail Split Drawers

For inspecting records or properties without losing list context:
- Use a horizontal `QSplitter` (`childrenCollapsible=False`) pairing the main view (`~65%`) with a `CardFrame` detail drawer (`~35%`, `min-width: 320px`, `max-width: 480px`).
- Organize the drawer into: Header (Item title + `StatusBadge` + close `×`), compact key-value metadata grid, main content/preview area, and a bottom contextual action bar.

## 4. Safe Destructive Confirmations, Inline Context & Non-Blocking Feedback

- **No Chained Sequential Modal Dialogs**: Never force a user through two or more back-to-back modal popups on a single submit click (e.g., `SelectClientDialog -> ConfirmPaymentDialog`). Surface key session/order context (such as active client, delivery mode, or payment option) **inline** in the workspace panel before submission, or consolidate required fields into one clean three-zone confirmation dialog only when confirmation is genuinely needed.
- **Destructive Actions**: Reserve modal confirmation dialogs (`QMessageBox` or custom 3-zone confirm dialog) strictly for irreversible/destructive actions (`Delete`, `Discard Changes`, `Reset`). Explicitly name the target item/count, style the destructive button with `DangerButton`, and keep `Cancel` focused by default.
- **Overlay Toast Notifications**: Replace blocking `QMessageBox.information` popups for routine confirmations (`"Saved"`, `"Export complete"`, `"Filters reset"`) with a floating `ToastNotification` frame anchored to the bottom-right (or bottom-left in RTL) of the active window (`20px` margin), featuring a `4px` semantic accent bar, `150ms` fade-in, `3000ms` auto-dismiss, and click-to-dismiss.
- **Progress Feedback**: For multi-step or long operations, show an inline progress bar (`QProgressBar`) with a `Cancel` button rather than freezing the window.
