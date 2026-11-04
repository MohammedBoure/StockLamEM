# Billing / Delivery & Return Notes Module (`ui/widgets/billing/`)

This package manages external transactions, delivery notes (Bons de Livraison - BL), and return notes (Bons de Retour - BR). It is unified directly with the central **Clients** directory while maintaining transparent fallback compatibility with legacy external partners (`External_Partners`).

## Files and Purpose

- **`billing_tab.py`**: Main container widget (`BillingTab`) managing the stacked view between the list view (`InvoicesListWidget`) and the transaction editor (`InvoiceEditorWidget`).
- **`invoices_list.py`**: Tabbed interface (`InvoicesListWidget`) separating **Bons de Livraison** and **Bons de Retour** into dedicated tabs with client filtering, specialized toolbars, search filters, context menus, deletion with stock restoration, and professional PDF export (with client fiscal identification and delivery stamps).
- **`invoice_editor.py`**: Comprehensive editor (`InvoiceEditorWidget`) for creating and modifying delivery notes (BL) and return notes (Bon de Retour) with client directory lookup, barcode scanning, batch allocation, automatic TTC unit cost population (`P.U (TTC)`) reflecting full acquisition cost, and sales price calculation.
