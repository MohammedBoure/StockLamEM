# Database Migrations (`database/migrations`)

This directory contains standalone, reproducible SQL migration scripts for schema upgrades, architectural evolution, and data migrations.

## Files and Purpose

- **`20260914_wholesale_retail_migration.sql`**: Idempotent SQL migration script introducing wholesale and retail schema support across `Locations` (visibility & POS allowance), `Inventory_Batches` (parent batch linkage & batch type), `Sales_Invoices` (sale classification & due date), and `Clients` (price tier & credit limit).
- **`20261104_appliance_store_workflow.sql`**: Idempotent SQL migration script introducing the Electrical Appliance Store workflow: product attributes (`Brand_Mark`, `Category_Name`, `Color_Finish`, `Requires_Serial_Tracking`), unique serial tracking (`Product_Serials`, `Product_Serial_History`), theoretical vs. physical stock reservation (`Sales_Orders_Theoretical`, `Theoretical_Reserved_Qty`), 6 bond types (`Bon C`, `Bon Crédit`, `Bon de Livraison`, `Versement`, `Bon de Sortie`, `Bon de Retour`), client wallets (`Client_Wallets`, `Client_Wallet_Transactions`), 4-stage SAV repair lifecycle (`SAV_Tickets`, `SAV_Ticket_History`, `SAV_Technicians`), and multi-scanner session bindings (`Workstation_Scanner_Bindings`).
