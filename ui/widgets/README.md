# UI Widgets (`ui/widgets`)

Ce dossier regroupe l'ensemble des modules d'interface graphique PySide6 de l'application bureautique.
Conformément à l'architecture modulaire 1-pour-1 de la barre de navigation latérale (`MainWindow.buttons_info`), **chaque bouton de la barre de navigation possède son propre sous-dossier dédié** dans `ui/widgets/` (aucun fichier `.py` isolé à la racine).

## Sous-Dossiers Dédiés (Barre de Navigation)

- `dashboard/` (`Page 0 : Tableau de Bord`) : Tableaux de bord, indicateurs clés de performance (`DashboardTab`, `OverviewTab`, `KPICardsSection`), graphiques de flux (`ChartsSection`), analyses statistiques (`statistics_tabs.py`), analyses de consommation (`analysis_view.py`) et prédictions IA (`ai_analytics_tab.py`).
- `inventory/` (`Page 1 : Stock & Magasin`) : Gestion des stocks, mouvements, transferts internes et gestion avancée des lots (`tabs_batches`).
- `procurement/` (`Page 2 : Achats & Entrées`) : Gestion des approvisionnements, bons de réception et entrées fournisseurs.
- `master_data/` (`Page 3 : Données de Base`) : Référentiels de base (fournisseurs, produits, familles, couleurs/finitions, emplacements, fabricants, automates, caisses).
- `billing/` (`Page 4 : Facturation Générale`) : Gestion de la facturation générale, devis et éditeurs de factures.
- `users/` (`Page 5 : Utilisateurs`) : Gestion des comptes utilisateurs (`UserManagementTab`, `UserDialog`), des rôles et de la matrice complète des autorisations RBAC.
- `reclamation/` (`Page 6 : Réclamations`) : Suivi et gestion des retours/réclamations fournisseurs (`ReclamationTab`).
- `history/` (`Page 7 : Traçabilité`) : Vue de traçabilité complète des mouvements de stock internes et externes (`MovementHistoryTab`) avec audit rapide par `N° de Série` et suivi des `Bon de Sortie` et `Bon de Retour`.
- `settings/` (`Page 8 : Paramètres`) : Paramètres de configuration système, imprimantes et sauvegardes automatiques (`SettingsWidget`).
- `inventaire/` (`Page 9 : Inventaire Physique`) : Sessions de comptage d'inventaire physique, détection des écarts et ajustements (`InventoryCountTab`).
- `sales/` (`Page 10 : Caisse POS`) : Interface de caisse tactile au détail POS (`PointOfSaleTab`), paiements directs et retours sans facture (`ReturnProductSelectionDialog`).
- `wholesale_sales/` (`Page 11 : Vente en Gros B2B`) : Interface de Vente en Gros B2B (`WholesaleSalesTab`), tarification dynamique (Prix 1 à 4), documents commerciaux (BL, BC, Devis, Facture) et export ReportLab PDF.
- `sales_history/` (`Page 12 : Historique Ventes`) : Historique complet des ventes (`SalesHistoryTab`), encaissement rapide et gestion détaillée des lignes de facture (`SaleDetailsDialog`).
- `debts/` (`Page 13 : Créances Clients`) : Interface dédiée de gestion des créances et suivi des dettes clients (`DebtsManagementTab`), règlements globaux FIFO (`GlobalPaymentDialog`) et audit d'intégrité comptable (`ClientDebtAuditDialog`).
- `appliance_desks/` (`Page 14 : Bureaux`) : Flux opérationnel multi-bureaux épuré (`ApplianceWorkflowTab`, `OrderDeskWidget`, `CashierDeskWidget`, `DispatchDeskWidget`, `SerialBatchRegistryWidget`) gérant la séparation vente théorique / sortie physique par `N° de Série`, le cycle des Bons (`Bon Comptant`, `Bon Crédit`, `Bon de Livraison`, `Versement`, `Bon de Sortie`, `Bon de Retour`) et le routage multi-scanner HID.
- `sav/` (`Page 15 : SAV`) : Espace de travail dédié au Service Après-Vente et Réparations (`SAVWorkspaceTab`, `SAVKanbanWidget`) en 4 étapes avec compensation par `Versement Virtuel` pour appareils irréparables.
- `clients/` (`Page 16 : Clients`) : Répertoire des Clients (`ClientsTab`) avec chargement dynamique (Lazy Loading), suivi des plafonds de crédit, relevé de compte (`ClientStatementDialog`) et consultation épurée des versements et du solde portefeuille (`ClientVersementsDialog`).
