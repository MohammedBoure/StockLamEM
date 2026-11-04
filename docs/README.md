# Technical Documentation & Architectural Specifications (`docs/`)

This directory serves as the centralized repository for system architectural blueprints, database migration plans, technical specifications, and historical migration logs for the **StockLamPlus** enterprise management platform.

---

## 1. Directory Architectural Role & Scope

The `docs/` module maintains the authoritative system specifications that govern:
- **Core Inventory & Multi-tier Logistics**: Unified batch tracking (`Inventory_Batches`), warehouse vs. showroom separation (`Private` vs. `Public` locations), and unit transformation pipelines.
- **High-Value Appliance Retail Systems**: Comprehensive backend and frontend specifications for electrical home appliance stores (*Magasins d'Électroménager*), serial number tracking (`Product_Serials`), theoretical vs. actual stock designation, four-desk operational segregation (Order Desk, Cashier, Dispatch Quai, SAV Repair Desk), and virtual store wallet settlements.
- **Database Migrations & Evolution**: Safe DDL execution scripts, schema evolution documentation, legacy data reconciliation protocols, and audit logs.
- **Peripheral & Mobile Integrations**: Single-PC multi-scanner concurrency, USB Raw Input routing, mobile barcode scanning specifications, and POS device interfaces.

---

## 2. Itemized Breakdown of Directory Files

### 2.1. Core Architecture & Specialized Industry Blueprints
- **[`analysis_frontend_hardware_workflow.md`](file:///home/pluto/projects/StockLamPlus/docs/analysis_frontend_hardware_workflow.md)**:
  - *Purpose*: Production-grade technical architecture, UI/UX specification, and hardware integration blueprints for retail home electrical appliance stores (*Magasin d'Électroménager*).
  - *Key Concepts*:
    - **Single-PC Multi-Scanner Concurrency**: Technical resolution of USB HID keyboard crosstalk using the Windows Raw Input API (`RegisterRawInputDevices`, `WM_INPUT`, `RIDI_DEVICENAME`, `RAWKEYBOARD`) and PySide6 native event filter (`WindowsRawInputFilter` subclassing `QAbstractNativeEventFilter`). Features unique physical device handle disambiguation, inter-keystroke timer burst buffering, and focus-independent dispatching via Qt signals. Cross-platform Linux architecture using `evdev` exclusive device grab (`EVIOCGRAB`) and `udev` hotplug monitoring.
    - **Three-Desk Operational Segregation**:
      - *Order Desk (`OrderDeskWidget`)*: Faceted filtering by Brand, Category, Color finish, Energy class, and Wattage. Two-tier inventory display (Showroom Expo vs. High-Bay Pallet Warehouse). Theoretical stock reservation with zero physical serial binding. Generation of temporary `Bon C` and `Bon Crédit` requests with thermal dispatch tickets.
      - *Cashier Desk (`CashierDeskWidget`)*: Real-time incoming order queue, multi-tender payment settlement (Cash, Card/TPE, Virtual Wallet). Client virtual store credit wallet (*Versement Virtuel*) inspection and automatic deduction. Dual-custody `AdminAuthModal` requiring supervisor PIN/password for term credit approval. Issuance of official invoice and Logistics Exit Token (`Bon de Sortie Token`).
      - *Dispatch Desk (`DispatchDeskWidget`)*: High-speed barcode and serial number scanning screen for warehousemen. Real-time integrity validation of scanned serial against expected product model, landed cost batch, and active state. Visual and audio feedback matrix (Green chime for match, yellow warning for duplicates, red harsh buzzer for mismatches). Gate pass (`Bon de Sortie`) and warranty certificate generation.
    - **SAV / Repair 4-Stage Kanban Pipeline (`SAVKanbanWidget`)**:
      - 4-stage visual pipeline: Reception (intake inspection, defect taxonomy, `Bon de Réparation` printing) $\rightarrow$ Technician Dispatch (workshop assignment) $\rightarrow$ Technician Return (diagnostic logging, bench test evaluation) $\rightarrow$ Customer Delivery (load test, digital signature).
      - Irreparable Defect Settlement Modal (`IrreparableDefectModal`): Automated mathematical calculation of residual value based on usage duration and warranty terms. Liquidity guardrail crediting customer Virtual Wallet (*Versement Virtuel*) to protect store cash till from depletion.
    - **Design Tokens & Theme**: Complete high-contrast professional dark mode QSS design system tokens (`@surface-base`, `@accent-brand`, `@status-success`, `@status-error`) optimized for retail showrooms and industrial dock monitors.
    - **Edge Cases & Security**: Mitigation blueprints for mid-burst scanner disconnects, barcode injection attacks, double-selling race conditions, dock serial collisions, and cashier bypass attempts.

- **[`analysis_backend_electrical_store.md`](file:///home/pluto/projects/StockLamPlus/docs/analysis_backend_electrical_store.md)**:
  - *Purpose*: Production-grade technical architecture and schema specification for retail electrical home appliance stores (*Magasin d'Électroménager*).
  - *Key Concepts*:
    - Batch management tracking landed cost ($PUMP$), arrival timestamps, customs/freight allocations, and supplier warranties.
    - Product attributes: Brand hierarchy (`Product_Brands`), appliance categorization (`Product_Categories`), finish/color, energy efficiency class, power wattage, and volumetric capacity.
    - Unique serial numbers (`Product_Serials`) tracking 6 lifecycle states: `IN_STOCK`, `RESERVED`, `DISPATCHED`, `RETURNED`, `IN_SAV`, `SCRAPPED` with complete immutable history ledger (`Product_Serial_History`).
    - Separation of Theoretical Allocation (*Désignation Théorique* at Order Desk) and Actual Physical Designation (*Désignation Réelle* at Dispatch Exit Desk).
    - Multi-role RBAC permissions matrix covering Sales, Cashier, Logistics, SAV, and Admin.
    - Bond lifecycle: Cash validation (`Bon C`), Admin-authorized term credit with credit limits and amortization schedule (`Bon Crédit`), Logistical gate pass without cash impact (`Bon de Sortie`), and non-cash customer store credit returns (`Bon de Retour`).
    - 4-Stage After-Sales Service (SAV) engine (`SAV_RECEIVED` $\rightarrow$ `SAV_SENT_TO_TECH` $\rightarrow$ `SAV_RETURNED_FROM_TECH` $\rightarrow$ `SAV_CLOSED_DELIVERED`) with automated virtual wallet compensation for irreparable defects.
    - Complete MySQL 8.0+ / InnoDB DDL schemas, constraints, foreign keys, indexes, and transactional Python service layer architectures.

- **[`architecture_depot_rayon_gros_detail.md`](file:///home/pluto/projects/StockLamPlus/docs/architecture_depot_rayon_gros_detail.md)**:
  - *Purpose*: Architectural design for unified multi-tier inventory management across wholesale warehouses (*Dépôt Gros*) and retail showroom shelving (*Rayon Détail*).
  - *Key Concepts*: Single unified inventory model in `Inventory_Batches` combined with location visibility flags (`Private` vs. `Public`), 3-unit product triad (Ordering, Storage, and Usage units), Direct transfer vs. Unpacking/Extraction transfers, and internal stock transfer documentation.

- **[`database_migration_plan_gros_detail.md`](file:///home/pluto/projects/StockLamPlus/docs/database_migration_plan_gros_detail.md)**:
  - *Purpose*: Relational schema evolution plan, DDL definitions, and migration procedures enabling multi-tier depot/shelf inventory segmentation.
  - *Key Concepts*: Schema alterations for `Locations.Visibility`, `Inventory_Batches.Parent_Batch_ID`, creation of `Internal_Transfers` and `Internal_Transfer_Details` tables, and rollback safety procedures.

- **[`ui_ux_redesign_inventory_sales.md`](file:///home/pluto/projects/StockLamPlus/docs/ui_ux_redesign_inventory_sales.md)**:
  - *Purpose*: Comprehensive UI/UX guide for desktop client interfaces across inventory and sales modules.
  - *Key Concepts*: Interaction patterns for `UnpackingTransferDialog`, wholesale B2B order entry grids, retail POS cash checkout layouts, barcode printing automation, and responsive table views.

### 2.2. Peripheral & Integration Documentation
- **[`mobile_inventory_scanner.md`](file:///home/pluto/projects/StockLamPlus/docs/mobile_inventory_scanner.md)**:
  - *Purpose*: Specifications for the handheld Flutter mobile scanning client used for warehouse inventory counts, batch lookups, and shelf auditing.
  - *Key Concepts*: Offline-first scanning buffer, REST sync endpoints, conflict resolution policies during concurrent counting sessions.

- **[`pos-migration-verification.md`](file:///home/pluto/projects/StockLamPlus/docs/pos-migration-verification.md)**:
  - *Purpose*: Verification checklists, acceptance test criteria, and automated verification procedures for POS database schema migrations and cash session balance continuity.

### 2.3. System Comparison & Gap Analysis
- **[`stocklam_feature_gap_report.md`](file:///home/pluto/projects/StockLamPlus/docs/stocklam_feature_gap_report.md)**:
  - *Purpose*: Gap analysis matrix comparing legacy GstockSW4 features against the modernized StockLamPlus platform.
  - *Key Concepts*: Container management (`Active_Containers`), dynamic multi-lot allocations, multi-currency purchasing, and POS session tracking.

### 2.4. Historical Migration Chronology
- **[`stocklam_migration_20260714_15.md`](file:///home/pluto/projects/StockLamPlus/docs/stocklam_migration_20260714_15.md)**: Milestone report covering core schema unification, foreign key alignment, and sales document numbering sequences.
- **[`stocklam_migration_20260714_27.md`](file:///home/pluto/projects/StockLamPlus/docs/stocklam_migration_20260714_27.md)**: Logistics migration log detailing active shipping containers, supplier tracking, and packaging unit definitions.
- **[`stocklam_migration_20260802_20.md`](file:///home/pluto/projects/StockLamPlus/docs/stocklam_migration_20260802_20.md)**: Financial settlement migration log covering supplier and client credit notes, installment ledgers, and cash movement tracking.
- **[`stocklam_migration_20260909.md`](file:///home/pluto/projects/StockLamPlus/docs/stocklam_migration_20260909.md)**: Migration report on inventory count conflict resolution engines, vertical batch numbering, vector SVG icons, and numeric decimal sorting.

---

## 3. Exposed Interfaces, Schemas & Data Flows

### 3.1. Inventory Calculation Flows
- **Weighted Average Landed Cost ($PUMP$)**:
  $$\text{Landed\_Cost\_HT} = \text{Unit\_Purchase\_Cost\_HT} + \text{Freight\_Customs\_Allocation}$$
  $$\text{Unit\_Cost\_TTC} = \text{Landed\_Cost\_HT} \times \left(1 + \frac{\text{Tax\_Rate}}{100}\right)$$
- **Theoretical Stock Availability Formula**:
  $$\text{Available\_Stock} = \text{Quantity\_Current} - \text{Theoretical\_Reserved\_Qty}$$
- **Customer Virtual Wallet Settlement**:
  $$\text{Balance}_{\text{new}} = \text{Balance}_{\text{old}} + \text{Return\_Credit\_Amount} + \text{SAV\_Compensation\_Amount} - \text{Purchase\_Debit\_Amount}$$

### 3.2. Lifecycle State Machines
- **Serial Asset State Engine**:
  $$\text{IN\_STOCK} \xrightarrow{\text{Order}} \text{RESERVED} \xrightarrow{\text{Scan Out}} \text{DISPATCHED} \xrightarrow{\text{Return}} \text{RETURNED} \xrightarrow{\text{Restock}} \text{IN\_STOCK}$$
  $$\text{DISPATCHED} \xrightarrow{\text{SAV Ticket}} \text{IN\_SAV} \xrightarrow{\text{Irreparable}} \text{SCRAPPED}$$
- **SAV 4-Stage Repair Lifecycle**:
  $$\text{SAV\_RECEIVED} \xrightarrow{\text{Manifest}} \text{SAV\_SENT\_TO\_TECH} \xrightarrow{\text{Diagnostic}} \text{SAV\_RETURNED\_FROM\_TECH} \xrightarrow{\text{Restitution}} \text{SAV\_CLOSED\_DELIVERED}$$

---

## 4. Dependencies, Environment Variables & Configuration

The technical architectures documented herein rely on the backend database configuration defined in the application root `.env` file:

| Environment Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `DB_HOST` | Database host server hostname or IP address | `localhost` |
| `DB_PORT` | MySQL / MariaDB listener port | `3306` |
| `DB_USER` | Database authentication username | `root` / `stocklam_user` |
| `DB_PASSWORD` | Database user password | `********` |
| `DB_NAME` | Primary schema identifier | `stocklam_plus` |
| `DB_CONNECT_TIMEOUT` | Connection pool handshake timeout in seconds | `5` |

---

## 5. Implementation Caveats & Critical Edge Cases

1. **Hardware Scanning Concurrency**: Handheld barcode scanners operating across separate workstations must never race on the same `Product_Serials` record. All state transition operations must acquire a pessimistic row lock (`SELECT ... FOR UPDATE`) inside an isolated transaction.
2. **Strict Cash Drawer Isolation**: Frontline cashiers are strictly barred from issuing cash refunds for returned goods. All returns must route to the customer's virtual wallet (`Client_Wallets`) to prevent cash drawer depletion (*assèchement de caisse*) and till theft.
3. **Admin Credential Overrides**: Any `Bon Crédit` transaction requires cryptographic verification of administrative credentials. Stored credentials must utilize bcrypt hashing, and every override event must be permanently logged in `Sales_Invoices_Credit_Approvals`.
