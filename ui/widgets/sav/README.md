# UI Widgets — Service Après-Vente (`ui/widgets/sav`)

Dedicated UI module for the **SAV** navigation bar workspace (`Page 15`, `nav_sav`).

## Files and Purpose

- **`__init__.py`**: Package initializer exporting `SAVWorkspaceTab`, `SAVKanbanWidget`, `SAVReceptionDialog`, and `IrreparableDefectModal`.
- **`sav_workspace_view.py`**: Multi-tab SAV & Repairs workspace (`SAVWorkspaceTab`) organizing repair tickets across dedicated stage tabs (`Toutes les Demandes`, `Réception Client`, `En Atelier`, `Prêt pour Restitution`, `Clôturés & Livrés`, `Appareils Irréparables`) with live KPI counters and RBAC enforcement.
- **`sav_kanban_view.py`**: 4-stage SAV repair workflow dialogs and Kanban view (`SAVKanbanWidget`, `SAVReceptionDialog` with live `N° de Série` auto-lookup, and `IrreparableDefectModal` issuing virtual wallet credit with zero physical cash till impact).
