# UI Widgets - Boîte de Dialogue de Réception (`ui/widgets/procurement/reception_dialog`)

Composants dédiés à la saisie et validation des réceptions de commandes (Bons de Réception).

## Fichiers et Rôles

- `__init__.py` : Expose `ReceptionDialog`.
- `reception_dialog.py` : Classe principale de la boîte de dialogue de réception.
- `reception_dialog_ui.py` : Mixin construisant l'interface graphique épurée (sélecteur de fournisseur `cb_supplier` en mode BL Direct sans BC, Produit avec affichage et filtrage par `Réf`, sélecteur de référence `cb_ref` avec bouton `+` (`btn_add_ref`) permettant d'ajouter directement une nouvelle `Réf` au produit sélectionné, Couleur / Finition `cb_color` avec aperçu visuel direct `lbl_color_swatch`, Unité, Qté, Emplacement, Prix U, Remise par article, `Remise Bon` globale `%`/`DZD`; champs Lot, Date Exp. et TVA masqués) et le tableau des articles reçus intégrant la colonne 'Couleur'.
- `reception_dialog_logic.py` : Mixin contenant la logique métier, le chargement/ajout des références (`_load_product_references`, `on_add_ref_clicked`) et persistance de `Ref_Code`, la gestion des couleurs d'appareils (chargement via `ProductColorManager`, pré-sélection automatique au choix du produit, mise à jour dynamique du swatch, assignation en table et en base), le calcul des remises par ligne (`%` et `DZD`) et de la remise globale sur le bon (`Bon_Discount_Value` / `Bon_Discount_Type`), le calcul sans TVA (0% par défaut), l'auto-génération transparente du `Lot_Number` (lot optionnel) sans date d'expiration requise, et la validation des données de réception (Produit, Emplacement, Qté > 0, Prix d'achat > 0).
- `auto_select_widgets.py` : Widgets d'entrée avec sélection automatique du texte au focus.
