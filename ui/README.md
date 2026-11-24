# UI Directory (`ui/`)

This directory contains the user interface components, styling, and navigation architecture for the application.

## Files and Purpose

- **`__init__.py`**: Module initialization for the `ui` package.
- **`formatting.py`**: Common formatting helper functions for prices, currency, quantities, and dates across the UI.
- **`icons.py`**: Icon generation helpers (`get_duotone_icon`, `apply_button_icon`), cached vector icon utilities, and 87 2D flat dual-tone SVG icons aligned with the StockLam `#0E7471` brand palette covering navigation, all workspace sub-tabs (Dashboard, Master Data, Procurement, Inventory, Settings), KPI cards (`profit_chart`, `consumption`, `valuation`, `waste_bin`, `trophy_best`), empty states, CRUD/action buttons (`plus_white`, `save_white`, `check_white`, `close_slate`, `pdf_doc`), multi-desk appliance workflows (`barcode_scan`, `wrench_sav`, `truck_delivery`, `shield_admin`, `return_arrow`), Caisse payment methods, and Trésorerie.
- **`login_dialog.py`**: Authentication and login dialog handling user credential validation and session initialization.
- **`main_window.py`**: Main application window managing the animated collapsible sidebar navigation (optimized 240px width with concise labels such as `Bureaux` and `SAV`), page routing/switching, permissions-based menu visibility, mnemonic accelerator escaping, Multi-Desk Appliance & SAV workflow integration, and header layout.
- **`navigation_permissions.py`**: Permission and navigation fallback helpers (`has_permission`, `has_navigation_permission`, `NAVIGATION_PERMISSION_FALLBACKS`).
- **`styles.qss`**: Comprehensive Qt Style Sheet (QSS) defining colors, fonts, margins, tables, buttons, and modern SaaS theme styling.
- **`theme_tokens.py`**: Single source of truth for StockLam Enterprise UI tokens (`BRAND_TEAL`, `CANVAS_BG`, `CARD_BG`, `SUBTLE_BG`, `BORDER_*`, `STATUS_*`), reusable button/table/input/subtab stylesheets (`PRIMARY_CTA_QSS`, `SECONDARY_OUTLINE_QSS`, `SLATE_OUTLINE_QSS`, `DANGER_OUTLINE_QSS`, `AMBER_OUTLINE_QSS`, `CLEAN_TABLE_QSS`, `FLAT_SUBTABS_QSS`), `#ObjectName`-scoped container helpers (`scoped_card_qss`, `scoped_banner_qss`, `scoped_dialog_qss`), and `set_enabled_with_reason`.
- **`hardware/`**: Subdirectory containing Windows Raw Input (`WM_INPUT`) multi-scanner HID isolation and session routing (`MultiScannerHIDManager`, `WindowsRawInputFilter`).
- **`widgets/`**: Subdirectory containing modular UI view tabs (Dashboard, Master Data, Procurement, Inventory, History, Settings, Users, Debts, Appliance Desks & SAV, etc.).
