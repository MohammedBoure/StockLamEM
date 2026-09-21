# Tests Unitaires (`test`)

Suite de tests automatisés vérifiant le bon fonctionnement des modules backend, des APIs mobiles et des utilitaires de formatage.

## Fichiers et Rôles

- `__init__.py` : Initialisation du package de tests.
- `test_ui_formatting.py` : Validation du formatage monétaire (espace milliers, virgule décimale) et des quantités.
- `test_inventory_mobile_api.py` : Tests d'intégration de l'API REST mobile (sessions, scans, consommations, transferts).
- `test_inventory_count_manager.py` : Tests du gestionnaire de sessions d'inventaire physique.
- `test_inventory_count_ui.py` : Tests de l'interface graphique de comptage d'inventaire.
- `test_local_settings.py` : Tests du stockage des préférences locales.
- `test_navigation_permissions.py` : Tests du contrôle d'accès et des permissions de navigation.
- `test_receipt_config.py` : Tests de configuration des reçus et tickets.
- `test_history_widget.py` : Tests de la vue d'historique et de traçabilité.
- `test_theme_and_settings_fixes.py` : Tests de séparation des onglets de paramètres (Laboratoire et Sauvegarde Automatique) et corrections visuelles (tailles de champs dates, code-barres).
- `test_wholesale_retail_migration.py` : Tests de validation unitaire de la migration de schéma idempotent pour le commerce de gros et détail.
- `test_wholesale_b2b_features.py` : Tests des fonctionnalités de vente en gros B2B (génération de numéros de documents, paliers de prix, plafonds de crédit).
- `test_touch_keypad_support.py` : Tests du pavé tactile/clavier virtuel partagé (`TouchKeypadDialog`), ergonomie tactile et intégration complète avec la Vente en Gros et le POS.
- `test_wholesale_refactoring.py` : Tests de validation de la ségrégation comptable (exclusion des devis et commandes brouillons des soldes et grands livres clients) et de la résolution automatique des paliers de prix B2B.
- `test_debts_management.py` : Tests des méthodes d'audit comptable du solde client, de ventilation FIFO des règlements globaux, des acomptes libres, des permissions de navigation `nav_debts`, de l'autocomplétion nom/téléphone (`SearchableClientComboBox`), et des tests d'interface utilisateur (`TestDebtsManagementUI` : bandeau de synthèse compact 48px, hauteurs d'entrées et absence d'overlay des dialogues, et calibrage des boutons d'actions).
- `test_sales_history_widget.py` : Tests de l'interface d'historique des ventes (`SalesHistoryTab`), chargement incrémental/lazy loading sur défilement, calculs métriques (nombre d'opérations, coût d'achat, total ventes, bénéfice) et barre inférieure unifiée.
- `test_lot_split_dialog.py` : Tests unitaires de la boîte de dialogue de répartition multi-lots (`MultiLotSelectionDialog`) : fond blanc solide 100% opaque sans overlay ni cadre noir, pré-allocation et algorithme FIFO, réinitialisation, ajustement manuel des spinboxes numériques (32px, texte centré), largeur sans troncature du bouton de validation ("Valider la Répartition (F10 / Enter)"), mise à jour dynamique des cartes de synthèse et validation de sortie.
- `test_wholesale_ui_improvements.py` : Tests unitaires de la refonte ergonomique de l'interface Vente en Gros B2B (`WholesaleSalesTab`) : barre de recherche code-barres élargie avec scan direct, suppression des champs rapides Qté/Remise en en-tête, défilement horizontal fluide de la grille panier, boutons d'action stylisés 32x32px et icône d'alerte tarifaire interactive avec pop-up modal.
