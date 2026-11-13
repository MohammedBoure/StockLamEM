# UI Widgets — Service Après-Vente (`ui/widgets/sav`)

Dedicated UI module for the **SAV** navigation bar workspace (`Page 15`, `nav_sav`).

## Files and Purpose

- **`__init__.py`**: Package initializer exporting `SAVWorkspaceTab`, `SAVKanbanWidget`, `SAVReceptionDialog`, and `IrreparableDefectModal`.
- **`sav_workspace_view.py`**: Clean flat SAV & Repairs workspace (`SAVWorkspaceTab`) with underline stage tabs (`Toutes`, `Réception`, `Atelier`, `Prêts Restitution`, `Clôturés`, `Irréparables`) displaying inline counts directly in the tab bar (redundant KPI bar hidden), non-clipping table headers, RBAC enforcement, and minimal `SAVReceptionResolutionDialog`.
- **`sav_kanban_view.py`**: 4-stage SAV repair workflow dialogs and Kanban view (`SAVKanbanWidget`, minimalist distraction-free `SAVReceptionDialog` with scoped QSS, underline lookup tabs for Bon Rouge & client search, auto-sync product selection into the flat 2-column intake form, plus `IrreparableDefectModal` issuing virtual wallet credit with zero physical cash till impact).
