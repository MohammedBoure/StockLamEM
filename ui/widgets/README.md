# UI Widgets (`ui/widgets`)

Ce dossier regroupe l'ensemble des modules d'interface graphique PySide6 de l'application bureautique.

## Sous-Dossiers Spécialisés

- `wholesale_sales/` : Interface de Vente en Gros B2B (`WholesaleSalesTab`), tarification dynamique (Prix 1 à 4), documents commerciaux (BL, BC, Devis, Facture) et export ReportLab PDF.
- `appliance_desks/` : Interface multi-bureaux pour magasins d'électroménager (`ApplianceWorkflowTab`, `OrderDeskWidget`, `CashierDeskWidget`, `DispatchDeskWidget`, `SAVKanbanWidget`, `SerialBatchRegistryWidget`) gérant la séparation vente théorique / sortie physique par N° de Série, les 6 types de Bons (`Bon C`, `Bon Crédit`, `Bon de Livraison`, `Versement`, `Bon de Sortie`, `Bon de Retour`), le SAV en 4 étapes et le multi-scanner HID.
- `sales_history/` : Historique complet des ventes (`SalesHistoryTab`), suivi des créances et vieillissement de dette (AR Aging), encaissement rapide et gestion détaillée des lignes de facture (`SaleDetailsDialog`).
- `sales/` : Interface de caisse tactile au détail POS (`PointOfSaleTab`), paiements directs et retours sans facture (`ReturnProductSelectionDialog`).
- `billing/` : Gestion de la facturation générale, devis et éditeurs de factures.
- `dashboard/` : Tableaux de bord, indicateurs clés de performance (KPIs) et graphiques statistiques.
- `inventory/` : Gestion des stocks, mouvements, inventaires physiques et gestion avancée des lots (`tabs_batches`).
- `master_data/` : Référentiels de base (clients, fournisseurs, produits, familles, emplacements, fabricants, automates).
- `procurement/` : Gestion des approvisionnements, réceptions de commandes et réclamations.
- `reclamation/` : Suivi et gestion des retours/réclamations fournisseurs.
- `settings/` : Paramètres de configuration système, imprimantes et sauvegardes automatiques.

## Fichiers Racine

- `analysis_view.py` : Vue d'analyse détaillée de la consommation et des mouvements de stock.
- `history.py` : Vue de traçabilité complète des mouvements de stock internes et externes (`MovementHistoryTab`) avec barre d'audit rapide par `N° de Série` (`Product_Serials` / `Product_Serial_History`) et suivi des `Bon de Sortie` et `Bon de Retour`.
- `user_management_tab.py` : Gestion des comptes utilisateurs, des rôles et de la matrice complète des autorisations (incluant les Bureaux Opérationnels `10. BUREAUX_WORKFLOW` et le Service Après-Vente `11. SAV_WORKSPACE`).
- `ai_analytics_tab.py` : Module d'analyses prédictives et d'intelligence artificielle.
