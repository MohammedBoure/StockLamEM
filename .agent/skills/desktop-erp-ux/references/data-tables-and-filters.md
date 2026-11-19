# Data Tables, Filters & Empty States

## 1. Search & Filter Ergonomics
- **Pane-Scoped Search & Filters**: In split views (`Catalogue` | `Panier`), mount the catalog search/filter bar strictly above the catalog table—never stretch it across the top of the sibling `Panier` panel. Never duplicate a parent tab-corner `Actualiser` button inside the filter bar, and keep `Actualiser` in neutral slate rather than filled Primary teal.
- **Live Debounced Search + `Enter`**: Filter locally or trigger debounced queries (`250ms`) as the user types, and always support `Enter` for immediate search and `Esc` to clear.
- **Segmented Status Filters**: Use mutually exclusive filter pills (`Tous`, `Reste à payer`, `Soldés`) with clear active state (`#0E7471` fill or strong indicator) and live counts where helpful.

## 2. Scannability & Row Actions
- **Right-Align All Monetary Columns**: `TOTAL TTC`, `PAYÉ`, `RESTE`, `PRIX TTC`, `PRIX U.` must always be right-aligned and consistently formatted (`16 660,00 DA`) for rapid vertical comparison.
- **No Permanent Per-Row `QComboBox` or `QLineEdit` Clutter**: Never place permanent `QComboBox` or raw unformatted `QLineEdit` widgets inside every table row; keep cells scannable as formatted text and open an inline `QStyledItemDelegate` editor on click/double-click, or use a single `+` / `Modifier` action.
- **Readable Row Actions**: Ensure row height (`>= 44px`), `setWordWrap(False)`, and column widths fit headers and cell buttons cleanly (`Suppr.` >= `64px`, `Total TTC` >= `135px`) using `#ObjectName` QSS scoping (`QTableWidget#Id::item { padding: 4px 6px; }`) with zero border clipping, and set `setToolTip(...)` on disabled row actions.

## 3. Empty & Filtered-Out States
- When search/filters match 0 rows, display a centered message (`"Aucun résultat pour les filtres actuels"`) with a single `"Réinitialiser les filtres"` button so the user is never stuck looking at a blank table.
