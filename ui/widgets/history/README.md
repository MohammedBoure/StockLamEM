# UI Widgets — Traçabilité (`ui/widgets/history`)

Dedicated UI module for the **Traçabilité** navigation bar workspace (`Page 7`, `nav_history`).

## Files and Purpose

- **`__init__.py`**: Package initializer exporting `MovementHistoryTab` and `MovementDetailsDialog`.
- **`movement_history_tab.py`**: Comprehensive stock movement traceability workspace (`MovementHistoryTab`) with date/type/search filters, rapid `N° de Série` lifecycle audit bar (`Product_Serials` / `Product_Serial_History`), `Bon de Sortie` and `Bon de Retour` tracking, and detailed movement inspection (`MovementDetailsDialog`).
