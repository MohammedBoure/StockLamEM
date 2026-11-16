# Data Tables, Filters & Empty States

## 1. Search & Filter Ergonomics
- **Live Debounced Search + `Enter`**: Filter locally or trigger debounced queries (`250ms`) as the user types, and always support `Enter` for immediate search and `Esc` to clear.
- **Segmented Status Filters**: Use mutually exclusive filter pills (`Tous`, `Reste à payer`, `Soldés`) with clear active state (`#0E7471` fill or strong indicator) and live counts where helpful.

## 2. Scannability & Row Actions
- **Right-Align All Monetary Columns**: `TOTAL TTC`, `PAYÉ`, `RESTE`, `PRIX TTC` must always be right-aligned for rapid vertical comparison.
- **No Per-Row Dropdown Clutter**: Never place `QComboBox` widgets inside every table row; keep cells scannable and use a single `+` / `Modifier` action or double-click detail view.
- **Readable Row Actions**: Ensure row height (`>= 44px`) accommodates action buttons (`+ Paiement`, `Modifier`) with zero border clipping, and set `setToolTip(...)` on disabled row actions.

## 3. Empty & Filtered-Out States
- When search/filters match 0 rows, display a centered message (`"Aucun résultat pour les filtres actuels"`) with a single `"Réinitialiser les filtres"` button so the user is never stuck looking at a blank table.
