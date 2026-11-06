# Module Historique des Ventes (`ui/widgets/sales_history`)

Ce dossier regroupe l'interface utilisateur et les composants dédiés à la consultation, au filtrage et à la gestion des opérations de vente, factures et sessions de caisse.

## Fichiers et Rôles

- `sales_history_tab.py` : Interface principale de l'historique (`SalesHistoryTab`). Comprend une barre de filtres responsive à deux niveaux avec sélecteur client autocomplété par Nom et Téléphone (`SearchableClientComboBox`), filtres par période, caisse, statut, moyen de paiement, suivi du vieillissement de dette / factures échues (AR Aging), chargement progressif / lazy loading au défilement (identique à l'interface Traçabilité), barre inférieure unifiée sur une seule ligne fine synthétisant l'état du chargement, le nombre d'opérations de vente, le total des sorties au coût d'achat, le total des entrées (ventes TTC) et le calcul du bénéfice sous contrôle des autorisations, ainsi que les raccourcis d'encaissement direct et de retours sans facture.
- `sale_details_dialog.py` : Fenêtre modale (`SaleDetailsDialog`) affichant le détail des articles d'une facture de vente (y compris les lignes théoriques issues des `Bureaux` et les `N° de Série` expédiés via `Bon de Sortie`) avec actions d'annulation, ajustement des quantités, restitution de stock et retours partiels.
- `pdf_export.py` : Moteur d'exportation PDF ReportLab (`export_invoice_to_pdf`) produisant des factures de vente conformes et prêtes à l'impression.
- `__init__.py` : Point d'entrée du package exportant `SalesHistoryTab`, `SaleDetailsDialog` et `export_invoice_to_pdf`.
