# UI Directory (`ui/`)

This directory contains the user interface components, styling, and navigation architecture for the application.

## Files and Purpose

- **`__init__.py`**: Module initialization for the `ui` package.
- **`formatting.py`**: Common formatting helper functions for prices, currency, quantities, and dates across the UI.
- **`icons.py`**: Icon generation helpers, cached vector icon utilities, and 2D flat dual-tone SVG icons aligned with the StockLam `#0E7471` brand palette for navigation, KPI dashboards, empty states, table actions, wholesale multi-lot operations (`fifo_alloc`, `refresh`), B2B wholesale interfaces (`alert_warning`, `edit_lots`), and multi-desk appliance workflows (`barcode_scan`, `wrench_sav`, `truck_delivery`, `shield_admin`, `return_arrow`).
- **`login_dialog.py`**: Authentication and login dialog handling user credential validation and session initialization.
- **`main_window.py`**: Main application window managing the animated collapsible sidebar navigation, page routing/switching, permissions-based menu visibility, mnemonic accelerator escaping, Multi-Desk Appliance & SAV workflow integration, and header layout.
- **`navigation_permissions.py`**: Permission and navigation fallback helpers (`has_permission`, `has_navigation_permission`, `NAVIGATION_PERMISSION_FALLBACKS`).
- **`styles.qss`**: Comprehensive Qt Style Sheet (QSS) defining colors, fonts, margins, tables, buttons, and modern SaaS theme styling.
- **`hardware/`**: Subdirectory containing Windows Raw Input (`WM_INPUT`) multi-scanner HID isolation and session routing (`MultiScannerHIDManager`, `WindowsRawInputFilter`).
- **`widgets/`**: Subdirectory containing modular UI view tabs (Dashboard, Master Data, Procurement, Inventory, History, Settings, Users, Debts, Appliance Desks & SAV, etc.).
