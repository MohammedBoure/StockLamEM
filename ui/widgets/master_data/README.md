# UI Widgets - Données de Base (`ui/widgets/master_data`)

Ce dossier regroupe les interfaces de gestion des référentiels de données du laboratoire et de l'ERP commercial.

## Fichiers et Rôles

- `master_data_tabs.py` : Onglet principal organisant les sous-onglets de données de base.
- `products_tab.py` : Gestion du catalogue des produits et réactifs, avec affichage du groupe prioritaire de caisse (Liste N°).
- `suppliers_tab.py` : Gestion des fournisseurs et contacts.
- `manufacturers_tab.py` : Gestion des fabricants et marques.
- `automates_tab.py` : Gestion des automates de laboratoire.
- `locations_tab.py` : Gestion hiérarchique des emplacements de stockage (armoires, frigos, bacs) avec colonnes "Visibilité" (Public / Privé) et "Vente POS" (Oui / Non).
- `location_types_manager.py` : Gestion des types d'emplacements.
- `product_families_tab.py` : Gestion des familles de produits.
- `packaging_units_tab.py` : Gestion des unités de conditionnement et facteurs de conversion.
- `waste_reasons_tab.py` : Gestion des motifs de mise au rebut / perte.
- `external_partners_tab.py` : Gestion des partenaires et sous-traitants externes.
- `clients_tab.py` : Espace de travail dédié au Répertoire des Clients (`ClientsTab`), migré hors des Données de Base vers un bouton dédié dans la barre de navigation (Page 16, permission `nav_clients`, icône `clients`) :
  - Chargement dynamique par lot (Lazy Loading) à la demande et au défilement vertical (`BATCH_SIZE = 50`), éliminant tout blocage de l'interface lors du traitement de milliers de clients.
  - Recherche instantanée avec temporisation (Debounce 250ms) et réinitialisation automatique du curseur de pagination.
  - Badge d'état dynamique de chargement (`X / Y clients`) et bouton manuel "Charger plus..." en bas de tableau.
  - Colonnes "Catégorie" (Prix 1 à 4), "Plafond Crédit" et "Solde Actuel" en temps réel.
  - Badge styling et coloration QBrush : Vert pastel lorsque Solde $\le$ Plafond de Crédit, et Rouge pastel en cas de dépassement (Solde > Plafond).
  - Bouton d'action (`Versements`, `Relevé de Compte`) et menu contextuel sur clic droit : Relevé de Compte, Versements & Solde, Modifier, Supprimer.
- `client_versements_dialog.py` : Dialogue épuré et minimaliste (`ClientVersementsDialog`) accessible depuis l'onglet `Clients`, permettant de consulter en un coup d'œil le solde portefeuille actuel du client (`Solde`, `Espèces`, `Avoir`) et l'historique chronologique de tous ses versements sans surcharge de conteneurs.
- `client_statement_dialog.py` : Dialogue interactif de Relevé de Compte Client ("Extrait de Compte") et consultation détaillée modalless :
  - En-tête épuré et libellés textuels ouverts (`<label>`) au-dessus des contrôles sans aucun encadrement parasite ni apparence de faux boutons.
  - Cartes KPI synthétiques planes et contrastées (Solde Antérieur, Total Débit, Total Crédit, Nouveau Solde Dû) avec bordures douces régulières (`#DDE3EA`, rayon 8px) et typographie renforcée de fort contraste.
  - Grand livre chronologique au format spreadsheet professionnel : quadrillage régulier de cellules (`#E2E8F0`), badges colorés distinctifs par type d'opération (Facture, BL, Règlement, Paiement caisse, Avoir, Hors bilan), solde progressif et alignement strict à droite en chiffres tabulaires `,0.00 DA`.
  - Lignes d'opérations interactives (au double-clic ou via le bouton dédié "Détails") ouvrant une fenêtre détaillée `TransactionDetailsDialog`.
  - Fenêtres de détail non-modales (Modalless Dialogs) : indépendantes, déplaçables et multi-instances, permettant à l'utilisateur d'ouvrir et de comparer plusieurs factures ou règlements simultanément sans bloquer l'interface parent.
  - Barre d'outils utilitaire supérieure unifiée dans les tons pétrole `#0E7471` (Actualiser, Imprimer, Exporter PDF, Fermer) avec suppression du bouton fermer redondant en bas.
  - Ségrégation comptable stricte : les devis et commandes brouillons (`DEV-`, `BC-`) apparaissent marqués `[Hors bilan]` en gris avec débit nul sans altérer le solde progressif ni le solde antérieur.
  - Export PDF A4 ReportLab et impression directe unifiée avec en-tête d'entreprise, coordonnées fiscales du client (NIF, RC), récapitulatif KPI et tableau chronologique.
- `caisses_tab.py` : Gestion et contrôle des caisses (Terminaux POS), statut actif/inactif et suivi du nombre de sessions.
- `product_colors_tab.py` : Gestion et référencement des couleurs/finitions des appareils électroménagers (`ProductColorsTab`) :
  - Visualisation des échantillons de couleur avec pastilles chromatiques (`ColorPreviewWidget`), nom, code Hexadécimal et statut.
  - Filtrage en temps réel par désignation ou code hexadécimal.
  - Dialogue modal d'ajout et modification (`ColorDialog`) avec sélecteur graphique interactif `QColorDialog`, validation du format Hex `#RRGGBB` et gestion de l'activation.
- `dialogs.py` : Boîtes de dialogue de saisie et de modification des entités de base :
  - `LocationDialog` : Contrôles de visibilité (Public / Privé) et case à cocher "Autoriser la vente POS" avec règle stricte d'intégrité (vente POS impossible sur emplacement privé).
  - `ClientDialog` : Sélection de la catégorie tarifaire (`Prix_1` à `Prix_4`) et saisie du plafond de crédit (`Credit_Limit`).
