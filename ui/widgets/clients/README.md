# UI Widgets — Clients (`ui/widgets/clients`)

Dedicated UI module for the **Clients** navigation bar workspace (`Page 16`, `nav_clients`).

## Files and Purpose

- **`__init__.py`**: Package initializer exporting `ClientsTab`, `ClientStatementDialog`, `TransactionDetailsDialog`, and `ClientVersementsDialog`.
- **`clients_tab.py`**: Dedicated Clients directory workspace (`ClientsTab`) with database-level lazy loading (`BATCH_SIZE = 50`), debounced search, pricing tier badges (`Prix_1`–`Prix_4`), real-time debt vs credit ceiling highlighting, account statement trigger, and `Versements` quick action.
- **`client_statement_dialog.py`**: Interactive Client Account Statement (`ClientStatementDialog`) and non-modal multi-instance transaction breakdown (`TransactionDetailsDialog`) with ReportLab A4 PDF export.
- **`client_versements_dialog.py`**: Minimalist, container-free dialog (`ClientVersementsDialog`) displaying a client's current wallet balance (`Solde`, `Espèces`, `Avoir`) and chronological `Versement` transaction history.
