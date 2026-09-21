# UI Widgets - Point de Vente Caisse POS (`ui/widgets/sales`)

Composants PySide6 pour le point de vente tactile au détail (POS), les règlements de caisse et les retours d'articles.

> **Note d'architecture :** La Vente en Gros B2B et l'Historique des Ventes disposent désormais de leurs propres dossiers dédiés sous `ui/widgets/` :
> - `ui/widgets/wholesale_sales/` : Interface B2B, tarification dynamique, gestion BL/BC/Factures et export PDF.
> - `ui/widgets/sales_history/` : Historique des ventes, suivi des créances (AR Aging), encaissements et détails de factures.

## Fichiers et Rôles

- `point_of_sale_tab.py` : Interface de caisse POS tactile optimisée pour l'espace :
  - Restriction stricte des recherches d'articles et de lots aux emplacements configurés en `Visibility = 'Public'` et `Allow_POS_Sales = True`.
  - Garde-fou code-barres (Barcode Guard) : interception instantanée avec alerte visuelle non-bloquante lors du scan d'un article situé dans un emplacement privé ou non autorisé au POS.
  - Barre supérieure ultra-fine avec net à payer dynamique, bouton d'actualisation F5, contrôles client/date/emplacement sur une ligne.
  - Panier multi-colonnes avec changement direct de l'emplacement de retrait, support complet des codes-barres multiples et favoris dynamiques illimités.
- `return_dialog.py` : Dialogue modal ergonomique `ReturnProductSelectionDialog` pour les retours d'articles sans facture :
  - Champ de recherche auto-focus avec capture immédiate des codes-barres et filtrage temps-réel.
  - Grille des résultats complète affichant Produit, Code-barres/SKU, N° Lot, Stock, Péremption, Prix Vente HT/TTC.
  - Configuration du retour : Quantité avec garde-fou, emplacement de destination (priorité automatique à la zone Quarantaine/Retour), motif du retour (liste déroulante normalisée) et mode de remboursement.
  - Traitement transactionnel atomique avec incrémentation du stock, écriture dans l'historique de mouvements et génération d'un Bon de Retour (Avoir) A4 ReportLab.
- `debts_management_tab.py` : Interface complète de gestion des créances et suivi des dettes clients (`DebtsManagementTab`) alignée à 100% sur le design system de StockLam :
  - Palette officielle : couleur pétrole de référence `#0E7471`, arrière-plan doux `#F4F6F8`, cartes blanches `#FFFFFF` avec bordures soignées `#DDE3EA`, rouge d'alerte `#DC2626` et vert de succès `#16A34A`.
  - 4 cartes KPI d'analyse supérieure : ligne d'accentuation haute de 3px, badges d'icônes circulaires réguliers (36x36px, rayon 18px) sur fond teinté doux, et typographie renforcée de fort contraste (22px, font-weight: 900).
  - Barre de filtrage standardisée à une hauteur de 38px : autocomplétion nom/téléphone (`SearchableClientComboBox`), sélecteur de statut de créance, seuil de dette en DA, bouton Actualiser plein pétrole (`#0E7471`) avec icône blanche et bouton Exporter CSV à encadrement élégant conforme à l'écran d'inventaire.
  - Table des Débiteurs et Table des Factures au format "Dense Data Table" : lignes compactes (hauteur 32px), quadrillage précis de cellules (`#E2E8F0`), montants monétaires rigoureusement alignés à droite, et boutons d'actions compacts de 24px de hauteur (Solder/Relevé, Encaisser/Imprimer).
  - Panneau de détail inférieur et état vide sans bordures discontinues : conteneur blanc épuré (`1px solid #DDE3EA`, rayon 8px) avec badge circulaire de 54px et messagerie contextuelle réactive (sélection client vs créances 100% soldées).
  - Dialogue de règlement global / acompte (`GlobalPaymentDialog`) avec ventilation FIFO ou acompte libre.
  - Dialogue d'audit d'intégrité comptable (`ClientDebtAuditDialog`).
- `searchable_client_combo.py` : Widget de sélection client avec autocomplétion instantanée (`SearchableClientComboBox`) :
  - Recherche bi-mode en temps réel par Nom du Client et par Numéro de Téléphone (`Qt.MatchContains`).
  - Formatage standardisé `Nom Client (Téléphone)` et conformité stylistique pétrole `#0E7471`.
- `pos_payment_dialog.py` : Dialogue de règlement multi-moyens pour le POS (espèces, carte, virement, crédit).
- `invoice_payment_dialog.py` : Dialogue d'encaissement et de règlement direct d'une facture client impayée ou échue avec enregistrement dans `Client_Payments`.
- `dialogs.py` : Dialogues auxiliaires de caisse (`ClientDialog`, `OpenSessionDialog`, `CloseSessionDialog`, `CashSessionDetailsDialog`, `QuickCashPaymentDialog`, `SelectBatchBarcodeDialog`, `EnterProductBarcodeDialog`).
- `touch_keypad.py` : Clavier tactile virtuel bi-mode compact et flottant (pavé numérique `123` et clavier complet `ABC`), partagé et synchronisé dynamiquement entre le Point de Vente Caisse (POS) et la Vente en Gros B2B (`WholesaleSalesTab`).
- `__init__.py` : Point d'entrée du package exportant `PointOfSaleTab`, `ReturnProductSelectionDialog`, `DebtsManagementTab`, et `SearchableClientComboBox`.

