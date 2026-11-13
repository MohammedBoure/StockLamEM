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
- `caisses_tab.py` : Gestion et contrôle des caisses (Terminaux POS), statut actif/inactif et suivi du nombre de sessions.
- `product_references_tab.py` : Gestion des codes `Réf` multiples par produit (`ProductReferencesTab`, `ReferenceDialog`), distincts du code-barres (`Barcode`), avec unicité globale, sélection du produit, définition de la `Réf` principale et contrôle d'accès via la permission `tab_data_references` dans Utilisateurs.
- `product_colors_tab.py` : Gestion et référencement des couleurs/finitions des appareils électroménagers (`ProductColorsTab`) :
  - Visualisation des échantillons de couleur avec pastilles chromatiques (`ColorPreviewWidget`), nom, code Hexadécimal et statut.
  - Filtrage en temps réel par désignation ou code hexadécimal.
  - Dialogue modal d'ajout et modification (`ColorDialog`) avec sélecteur graphique interactif `QColorDialog`, validation du format Hex `#RRGGBB` et gestion de l'activation.
- `dialogs.py` : Boîtes de dialogue de saisie et de modification des entités de base :
  - `LocationDialog` : Contrôles de visibilité (Public / Privé) et case à cocher "Autoriser la vente POS" avec règle stricte d'intégrité (vente POS impossible sur emplacement privé).
  - `ClientDialog` : Sélection de la catégorie tarifaire (`Prix_1` à `Prix_4`) et saisie du plafond de crédit (`Credit_Limit`).
