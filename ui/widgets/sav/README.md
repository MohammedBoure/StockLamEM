# UI Widgets — Service Après-Vente (`ui/widgets/sav`)

Dedicated UI module for the **SAV** navigation bar workspace (`Page 15`, `nav_sav`).

## Files and Purpose

- **`__init__.py`**: Package initializer exporting `SAVWorkspaceTab`, `SAVKanbanWidget`, `SAVReceptionDialog`, and `IrreparableDefectModal`.
- **`sav_workspace_view.py`**: Multi-tab SAV & Repairs workspace (`SAVWorkspaceTab`) organizing repair tickets across dedicated stage tabs (`Toutes les Demandes`, `Réception Client`, `En Atelier`, `Prêt pour Restitution`, `Clôturés & Livrés`, `Appareils Irréparables`) with live KPI counters, RBAC enforcement, and `SAVReceptionResolutionDialog` (Task #16) supporting good-condition restock + negative Caisse refund (`GOOD_RESTOCK_CASH_REFUND`), damaged-product negative Caisse refund (`DAMAGED_CASH_REFUND`), damaged-product virtual wallet versement with zero Caisse impact (`DAMAGED_VIRTUAL_VERSEMENT`), or workshop dispatch (`Envoi Atelier`).
- **`sav_kanban_view.py`**: 4-stage SAV repair workflow dialogs and Kanban view (`SAVKanbanWidget`, screen-sized `SAVReceptionDialog` with two lookup modes — Option 1: direct Bon Rouge lookup via `find_bon_by_bon_rouge`; Option 2: client search by phone/first name/last name via `search_client_bons` and product filtering to add physical items directly to Réception — plus `IrreparableDefectModal` issuing virtual wallet credit with zero physical cash till impact).
