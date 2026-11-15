# UI Widgets — Traçabilité (`ui/widgets/history`)

Dedicated UI module for the **Traçabilité** navigation bar workspace (`Page 7`, `nav_history`).

## Files and Purpose

- **`__init__.py`**: Package initializer exporting `MovementHistoryTab` and `MovementDetailsDialog`.
- **`movement_history_tab.py`**: Comprehensive stock movement traceability workspace (`MovementHistoryTab`) with date/type filters, a unified search & barcode/serial scan input (`search_input` `BarcodeLineEdit` handling both hardware scanner scans and manual text filtering with an inline `serial_audit_banner`), `Bon de Sortie` and `Bon de Retour` tracking, and detailed movement inspection (`MovementDetailsDialog`).
