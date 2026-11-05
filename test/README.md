# Automated Verification Suites & Integration Test Harness (`test/`)

## 1. Executive Summary & Scope

The `test/` directory contains the authoritative automated test harness, integration suites, and hardware concurrency simulations for the **StockLamPlus** enterprise management platform. 

This test suite enforces strict software quality gatekeeping across:
- **Backend Domain Logic & Schema Evolution**: Multi-tier batch management (`Inventory_Batches`), wholesale B2B pricing tiers, debt ledger FIFO reconciliation, unit conversion pipelines, and document numbering sequences.
- **High-Value Domestic Appliance Retail Validation**: Global serial number uniqueness, multi-desk concurrent scan race condition mitigation, physical till isolation during customer returns (`Bon de Retour`), dual-custody `Bon Crédit` administrative approvals, and 4-stage After-Sales Service (SAV) engine workflows.
- **Hardware Isolation & Multi-Scanner Concurrency**: RawInput/HID character buffering tests preventing keystroke interleaving across multiple barcode scanners attached to a single workstation.
- **Client UI & Desktop Interaction**: Qt-based UI regression testing, touch keypad dialog ergonomics, compact debt summary KPIs, and lazy-loading sales history tables.
- **Mobile REST API**: Comprehensive integration tests verifying handheld inventory mobile scanner endpoints, batch transfers, and offline-first counting sessions.

---

## 2. Itemized Breakdown of Test Files & Harness Modules

### 2.1. Specialized Appliance Retail, Concurrency & Security Gatekeeping
- **[`docs/analysis_testing_and_validation_matrix.md`](file:///home/pluto/projects/StockLamPlus/docs/analysis_testing_and_validation_matrix.md)**:
  - *Scope*: Master validation matrix, mathematical proof of physical cash drawer isolation, threat modeling, and acceptance criteria.
- **`test_serial_uniqueness_and_concurrency.py`**:
  - *Scope*: Validates global uniqueness constraints (`(Product_ID, Serial_Number)` and `Barcode_Serial_Composite`) across supplier consignments; simulates high-concurrency race conditions where two loading desks attempt to scan the identical serial number simultaneously.
- **`test_financial_isolation_and_bon_credit.py`**:
  - *Scope*: Proves that customer product returns (`Bon de Retour`) and SAV irreparable compensations strictly credit client virtual wallets (`Client_Wallets`) with zero impact on the physical cash drawer ($\Delta \text{Till\_Balance} \equiv 0.00\text{ DA}$); tests bcrypt-based administrative authentication and credit ceiling boundaries for `Bon Crédit`.
- **`test_multiscanner_hid_concurrency.py`**:

- **`test_order_desk_task1_enhancements.py`**:
  - *Scope*: Verifies Task #1 enhancements in Order Desk (`OrderDeskWidget`): universal barcode recognition across product, batch, and serial barcodes with auto-addition to cart; cart stores strictly theoretical products without literal serial registration; category column width >= 160px with tooltips; increased action button heights under Total TTC (`Bon Comptant` >= 44px, `Bon Crédit` / `Bon de Livraison` >= 40px); movable horizontal separator (`QSplitter`) with persistent position memory via `QSettings`; interactive `ColorBadgeWidget` displaying visual color swatches and tooltips with hex codes; elegant session close button management (hidden when only 1 session, custom styled when > 1); and removal of redundant "Associer Scanner USB" button from the session bar.
- **`test_product_colors_and_bon_comptant.py`**:
  - *Scope*: Verifies Task #5 deliverables: renaming of Bon C to Bon Comptant across Order Desk and Cashier Desk UI, full CRUD and active filtering in ProductColorManager, and UI integration of ProductColorsTab within Master Data (Données de base).
- **`test_batch_reception_path_restriction.py`**:
  - *Scope*: Verifies Task #6 deliverables: strict restriction of batch reception and registration to only two authorized paths (Achats & Entrées, and Stock & Magasin), blocking of additions from other desks (Bureaux & SAV), and mandatory complete product/batch data validation.
### 2.2. Core Financial, Billing & Debt Management
- **[`test_debts_management.py`](file:///home/pluto/projects/StockLamPlus/test/test_debts_management.py)**:
  - *Scope*: Verifies client balance calculation audits, FIFO settlement distribution of global payments, free downpayments (*acomptes libres*), `nav_debts` navigation permissions, autocomplete client dropdowns (`SearchableClientComboBox`), and debt UI dialog ergonomics (`ClientStatementDialog`, non-modal `TransactionDetailsDialog`).
- **[`test_billing_unit_price_ttc.py`](file:///home/pluto/projects/StockLamPlus/test/test_billing_unit_price_ttc.py)**:
  - *Scope*: Tests automatic unit acquisition price calculation (TTC) for transfer line items and delivery notes (`get_batch_unit_price_ttc`), tax/discount overrides, and dynamic fallback calculations.
- **[`test_wholesale_refactoring.py`](file:///home/pluto/projects/StockLamPlus/test/test_wholesale_refactoring.py)**:
  - *Scope*: Verifies accounting segregation ensuring quotes (*Devis*) and draft sales orders (*Bon de Commande*) are strictly excluded from client ledger debt totals, and validates dynamic B2B pricing tier selection.
- **[`test_wholesale_b2b_features.py`](file:///home/pluto/projects/StockLamPlus/test/test_wholesale_b2b_features.py)**:
  - *Scope*: Validates wholesale document sequential numbering, multi-tier volume discounts, and credit limit ceilings.

### 2.3. Inventory Management, Batch Allocation & Unit Conversion
- **[`test_inventory_count_manager.py`](file:///home/pluto/projects/StockLamPlus/test/test_inventory_count_manager.py)**:
  - *Scope*: Validates physical inventory counting session lifecycles, discrepancy detection, theoretical vs. physical stock adjustments, and frozen inventory auditing.
- **[`test_lot_split_dialog.py`](file:///home/pluto/projects/StockLamPlus/test/test_lot_split_dialog.py)**:
  - *Scope*: Unit tests for the multi-lot allocation modal (`MultiLotSelectionDialog`), ensuring solid opaque dialog background, dynamic vertical sizing, FIFO pre-allocation, spinbox padding, and F10 validation hotkeys.
- **[`test_wholesale_retail_migration.py`](file:///home/pluto/projects/StockLamPlus/test/test_wholesale_retail_migration.py)**:
  - *Scope*: Verifies idempotent DDL migration scripts for unified depot/shelf inventory structures, location visibility flags (`Private` vs. `Public`), and parent-child batch links.

### 2.4. POS, UI Components & Peripheral Integration
- **[`test_inventory_mobile_api.py`](file:///home/pluto/projects/StockLamPlus/test/test_inventory_mobile_api.py)**:
  - *Scope*: Integration tests for the mobile Flutter REST backend (authentication, batch lookups, offline barcode sync, internal movement requests).
- **[`test_inventory_count_ui.py`](file:///home/pluto/projects/StockLamPlus/test/test_inventory_count_ui.py)**:
  - *Scope*: Qt GUI test cases for inventory count sessions, table filtering, and batch reconciliation.
- **[`test_touch_keypad_support.py`](file:///home/pluto/projects/StockLamPlus/test/test_touch_keypad_support.py)**:
  - *Scope*: Tests the shared on-screen touch virtual keypad (`TouchKeypadDialog`), tactile numeric inputs, and POS checkout ergonomics.
- **[`test_wholesale_ui_improvements.py`](file:///home/pluto/projects/StockLamPlus/test/test_wholesale_ui_improvements.py)**:
  - *Scope*: Tests the redesigned B2B sales tab (`WholesaleSalesTab`), direct barcode search bar, fluid horizontal table scrolling, and pricing alert dialogs.
- **[`test_sales_history_widget.py`](file:///home/pluto/projects/StockLamPlus/test/test_sales_history_widget.py)**:
  - *Scope*: Validates sales history lazy-loading on scroll, KPI summary bar calculations (transaction counts, purchase cost, turnover, gross margin), and unified bottom action bars.
- **[`test_ui_formatting.py`](file:///home/pluto/projects/StockLamPlus/test/test_ui_formatting.py)**:
  - *Scope*: Tests currency and numeric formatting utilities (thousands space separation, decimal commas, quantity rounding).
- **[`test_navigation_permissions.py`](file:///home/pluto/projects/StockLamPlus/test/test_navigation_permissions.py)**:
  - *Scope*: Tests role-based sidebar and action bar permissions (`nav_pos`, `nav_sales`, `nav_debts`, `nav_inventory`).
- **[`test_receipt_config.py`](file:///home/pluto/projects/StockLamPlus/test/test_receipt_config.py)**:
  - *Scope*: Tests receipt printer layout, paper size configurations (80mm vs. 58mm thermal), and receipt header/footer templates.
- **[`test_theme_and_settings_fixes.py`](file:///home/pluto/projects/StockLamPlus/test/test_theme_and_settings_fixes.py)**:
  - *Scope*: Verifies separation of settings tabs (Experimental Laboratory vs. Auto Backup) and visual alignment fixes.
- **[`test_local_settings.py`](file:///home/pluto/projects/StockLamPlus/test/test_local_settings.py)**:
  - *Scope*: Tests local client preference persistence and workstation device configurations.
- **[`test_pos_terminal_manager.py`](file:///home/pluto/projects/StockLamPlus/test/test_pos_terminal_manager.py)**:
  - *Scope*: Validates POS workstation binding, cash drawer port communication, and terminal licensing.
- **[`test_history_widget.py`](file:///home/pluto/projects/StockLamPlus/test/test_history_widget.py)**:
  - *Scope*: Tests audit trail history logging and user action tracking.

---

## 3. Step-by-Step Test Execution Instructions

### 3.1. Environment Setup
Activate the certified Python environment:
```bash
source /home/pluto/Desktop/venv/ai/bin/activate
cd /home/pluto/projects/StockLamPlus
```

### 3.2. Running Full Test Suite
To run all automated test suites with standard verbosity:
```bash
pytest -v
```

### 3.3. Running Specialized Validation Suites
To run specific domain test suites:

- **Appliance Concurrency & Race Tests**:
  ```bash
  pytest -v test/test_serial_uniqueness_and_concurrency.py
  ```
- **Financial & Cashier Isolation Tests**:
  ```bash
  pytest -v test/test_financial_isolation_and_bon_credit.py
  ```
- **Hardware Multi-Scanner HID Stress Tests**:
  ```bash
  pytest -v test/test_multiscanner_hid_concurrency.py
  ```
- **Debts & Accounting Reconciliation Tests**:
  ```bash
  pytest -v test/test_debts_management.py
  ```
- **Mobile Inventory API Integration Tests**:
  ```bash
  pytest -v test/test_inventory_mobile_api.py
  ```

---

## 4. Critical Edge Cases, Validation Boundaries & Dependencies

1. **Pessimistic Concurrency Invariant**:
   - In multi-desk dispatch environments, rows in `Product_Serials` must be selected with `FOR UPDATE`.
   - When a collision occurs, the secondary desk must receive a clean `StateCollisionException` and never complete a duplicate exit voucher.
2. **Strict Cash Drawer Isolation Firewall**:
   - Customer returns (`Bon de Retour`) and irreparable SAV defect settlements (`Versement Virtuel`) must update `Client_Wallets` exclusively.
   - Physical cash drawers (`POS_Cash_Sessions`) must experience $\Delta \text{Till\_Balance} \equiv 0.00\text{ DA}$.
3. **Hardware Keystroke Interleaving**:
   - USB barcode scanners sharing a single workstation must be decoupled via OS RawInput/HID handle separation.
   - Keystrokes must be buffered in device-isolated queues to prevent garbled barcodes.
4. **Administrative Dual-Custody Approval**:
   - `Bon Crédit` term sales require cryptographic bcrypt verification of manager credentials and hard checks against client credit limits.

---

## 5. Maintenance Mandate
This `README.md` must be dynamically updated whenever new test modules, fixtures, or verification scripts are introduced. All documentation must strictly adhere to the English language requirement.
