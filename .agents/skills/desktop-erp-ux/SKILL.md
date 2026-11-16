---
name: desktop-erp-ux
description: "Desktop ERP & POS User Experience (UX) skill for StockLam (PySide6). Use when designing or reviewing user flows, cashier/payment screens, inventory tables, search/filter bars, keyboard shortcuts, empty/loading states, or error prevention."
---

# Desktop ERP & POS UX Skill

Token-efficient UX guidelines tailored for **StockLam** desktop workflows (Caisse, Paiement Livraison, Stock & Magasin, Commandes). Read only the reference file needed for your current task.

## 1. Progressive Disclosure (Read On Demand)

| Task / Screen Type | Reference File to Read |
| :--- | :--- |
| Cashier (`Caisse`), payment panels, wallet (`Portefeuille`), barcode input, or destructive confirmations | `./references/pos-and-cashier-ux.md` |
| Inventory/order tables, search bars, filter chips, empty states, or row actions | `./references/data-tables-and-filters.md` |

## 2. Universal Desktop UX Rules (Always Active)

1. **Keyboard-First & Zero Dead Clicks**: Every primary screen must auto-focus its main input (scanner/search) on open, support `Enter` to submit/filter, `Esc` to clear/cancel, and `F5`/`Ctrl+R` to refresh.
2. **One Canonical Location Per Action**: Never duplicate the same action button in two places on the same screen (e.g., two `Actualiser` buttons, or repeating `Versement` in a footer when a sidebar tab/card already handles it).
3. **Explain Disabled States**: Any disabled action button (`+ Paiement`, `Valider`, etc.) must include a `setToolTip(...)` explaining *why* it is disabled.
4. **Prevent Errors Inline**: Validate numeric/payment inputs inline before submission; reserve modal confirmations for destructive actions (`Retirer Bon`, `Annuler`, `Supprimer`) naming the exact document ID.
5. **Never Leave Blank Voids**: Empty tables and collapsed/asymmetric panels must display helpful empty-state guidance or balanced proportions rather than 60%+ dead whitespace.
