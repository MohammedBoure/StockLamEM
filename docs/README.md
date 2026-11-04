# Technical Documentation & Architectural Specifications (`docs/`)

This directory serves as the centralized repository for system architectural blueprints, database migration plans, technical specifications, and historical migration logs for the **StockLamPlus** enterprise management platform.

---

## 1. Directory Architectural Role & Scope

The `docs/` module maintains the authoritative system specifications that govern:
- **Core Inventory & Multi-tier Logistics**: Unified batch tracking (`Inventory_Batches`), warehouse vs. showroom separation (`Private` vs. `Public` locations), and unit transformation pipelines.
- **High-Value Appliance Retail Systems**: Comprehensive specifications for domestic electrical appliance stores (*Magasins d'Électroménager*), serial number tracking (`Product_Serials`), theoretical vs. actual stock designation, four-desk operational segregation (Order Desk, Cashier, Dispatch Quai, SAV Repair Desk), and virtual store wallet settlements.
- **Quality Gatekeeping, Testing & Validation**: Concurrency stress harnesses, pessimistic row locking, financial liquidity defense (prohibiting return-induced cash drawer drain), dual-custody administrative authorization, and multi-scanner HID device separation.
- **Database Migrations & Evolution**: Safe DDL execution scripts, schema evolution documentation, legacy data reconciliation protocols, and audit logs.
- **Peripheral & Mobile Integrations**: Mobile barcode scanning specifications, dual-input hardware concurrency, and POS device interfaces.

---

## 2. Itemized Breakdown of Directory Files

### 2.1. Quality Gatekeeping & Validation Matrices
- **[`analysis_testing_and_validation_matrix.md`](file:///home/pluto/projects/StockLamPlus/docs/analysis_testing_and_validation_matrix.md)**:
  - *Purpose*: Authoritative Quality Gatekeeper testing, concurrency, and financial audit matrix for domestic electrical appliance store retail (*Magasin d'Électroménager*).
  - *Key Concepts*:
    - Global serial uniqueness validation across batches, suppliers, and re-imported SKUs with composite uniqueness keys and sanitization.
    - Multi-desk simultaneous scan race condition prevention via pessimistic row-level locking (`SELECT ... FOR UPDATE`), transaction isolation (`REPEATABLE READ`), and deadlock jittered backoff.
    - Financial till isolation firewall: Mathematical proof that customer returns (`Bon de Retour`) and irreparable SAV defect settlements (`Versement Virtuel`) strictly credit `Client_Wallets` with exactly zero impact on the physical cash drawer ($\Delta \text{Till\_Balance} \equiv 0.00\text{ DA}$).
    - Dual-custody administrative authorization security verification for `Bon Crédit` with bcrypt password authentication, credit ceiling checks, and immutable approval logging.
    - Multi-scanner hardware concurrency and character interleaving prevention via low-level OS RawInput/HID character buffering.
    - 4-Stage SAV state machine verification and customer wallet credit automation on irreparable units.
    - Concrete automated `pytest` test suites, fixtures (`conftest_appliance.py`), and pre-merge gatekeeper acceptance criteria.

### 2.2. Core Architecture & Specialized Industry Blueprints
- **[`architecture_depot_rayon_gros_detail.md`](file:///home/pluto/projects/StockLamPlus/docs/architecture_depot_rayon_gros_detail.md)**:
  - *Purpose*: Architectural design for unified multi-tier inventory management across wholesale warehouses (*Dépôt Gros*) and retail showroom shelving (*Rayon Détail*).
  - *Key Concepts*: Single unified inventory model in `Inventory_Batches` combined with location visibility flags (`Private` vs. `Public`), 3-unit product triad (Ordering, Storage, and Usage units), Direct transfer vs. Unpacking/Extraction transfers, and internal stock transfer documentation.

- **[`database_migration_plan_gros_detail.md`](file:///home/pluto/projects/StockLamPlus/docs/database_migration_plan_gros_detail.md)**:
  - *Purpose*: Relational schema evolution plan, DDL definitions, and migration procedures enabling multi-tier depot/shelf inventory segmentation.
  - *Key Concepts*: Schema alterations for `Locations.Visibility`, `Inventory_Batches.Parent_Batch_ID`, creation of `Internal_Transfers` and `Internal_Transfer_Details` tables, and rollback safety procedures.

- **[`ui_ux_redesign_inventory_sales.md`](file:///home/pluto/projects/StockLamPlus/docs/ui_ux_redesign_inventory_sales.md)**:
  - *Purpose*: Comprehensive UI/UX guide for desktop client interfaces across inventory and sales modules.
  - *Key Concepts*: Interaction patterns for `UnpackingTransferDialog`, wholesale B2B order entry grids, retail POS cash checkout layouts, barcode printing automation, and responsive table views.

### 2.3. Peripheral & Integration Documentation
- **[`mobile_inventory_scanner.md`](file:///home/pluto/projects/StockLamPlus/docs/mobile_inventory_scanner.md)**:
  - *Purpose*: Specifications for the handheld Flutter mobile scanning client used for warehouse inventory counts, batch lookups, and shelf auditing.
  - *Key Concepts*: Offline-first scanning buffer, REST sync endpoints, conflict resolution policies during concurrent counting sessions.

- **[`pos-migration-verification.md`](file:///home/pluto/projects/StockLamPlus/docs/pos-migration-verification.md)**:
  - *Purpose*: Verification checklists, acceptance test criteria, and automated verification procedures for POS database schema migrations and cash session balance continuity.

### 2.4. System Comparison & Gap Analysis
- **[`stocklam_feature_gap_report.md`](file:///home/pluto/projects/StockLamPlus/docs/stocklam_feature_gap_report.md)**:
  - *Purpose*: Gap analysis matrix comparing legacy GstockSW4 features against the modernized StockLamPlus platform.
  - *Key Concepts*: Container management (`Active_Containers`), dynamic multi-lot allocations, multi-currency purchasing, and POS session tracking.

### 2.5. Historical Migration Chronology
- **[`stocklam_migration_20260714_15.md`](file:///home/pluto/projects/StockLamPlus/docs/stocklam_migration_20260714_15.md)**: Milestone report covering core schema unification, foreign key alignment, and sales document numbering sequences.
- **[`stocklam_migration_20260714_27.md`](file:///home/pluto/projects/StockLamPlus/docs/stocklam_migration_20260714_27.md)**: Logistics migration log detailing active shipping containers, supplier tracking, and packaging unit definitions.
- **[`stocklam_migration_20260802_20.md`](file:///home/pluto/projects/StockLamPlus/docs/stocklam_migration_20260802_20.md)**: Financial settlement migration log covering supplier and client credit notes, installment ledgers, and cash movement tracking.
- **[`stocklam_migration_20260909.md`](file:///home/pluto/projects/StockLamPlus/docs/stocklam_migration_20260909.md)**: Migration report on inventory count conflict resolution engines, vertical batch numbering, vector SVG icons, and numeric decimal sorting.

---

## 3. Maintenance Mandate
This `README.md` must be dynamically maintained in English whenever architectural specifications, database migration scripts, or validation matrices are added or revised.
