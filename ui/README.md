# UI Directory (`ui/`)

This directory contains the user interface components, styling, and navigation architecture for the application.

## Files and Purpose

- **`__init__.py`**: Module initialization for the `ui` package.
- **`formatting.py`**: Common formatting helper functions for prices, currency, quantities, and dates across the UI.
- **`icons.py`**: Icon generation helpers, cached vector icon utilities, and 2D flat dual-tone SVG icons aligned with the StockLam `#0E7471` brand palette for navigation, KPI dashboards, empty states, table actions, and wholesale multi-lot operations (`fifo_alloc`, `refresh`).
- **`login_dialog.py`**: Authentication and login dialog handling user credential validation and session initialization.
- **`main_window.py`**: Main application window managing the animated collapsible sidebar navigation, page routing/switching, permissions-based menu visibility, mnemonic accelerator escaping, and header layout.
- **`styles.qss`**: Comprehensive Qt Style Sheet (QSS) defining colors, fonts, margins, tables, buttons, and modern SaaS theme styling.
- **`widgets/`**: Subdirectory containing modular UI view tabs (Dashboard, Master Data, Procurement, Inventory, History, Settings, Users, Debts, etc.).
