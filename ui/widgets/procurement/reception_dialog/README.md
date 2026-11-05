# UI Widgets - Boîte de Dialogue de Réception (`ui/widgets/procurement/reception_dialog`)

Composants dédiés à la saisie et validation des réceptions de commandes (Bons de Réception).

## Fichiers et Rôles

- `__init__.py` : Expose `ReceptionDialog`.
- `reception_dialog.py` : Classe principale de la boîte de dialogue de réception.
- `reception_dialog_ui.py` : Mixin construisant l'interface graphique, les champs de saisie (Produit, Couleur / Finition `cb_color` avec aperçu visuel direct `lbl_color_swatch`, Qté, N° de Lot, Emplacement, Prix U HT) et le tableau des articles reçus intégrant la colonne 'Couleur'.
- `reception_dialog_logic.py` : Mixin contenant la logique métier, la gestion des couleurs d'appareils (chargement via `ProductColorManager`, pré-sélection automatique au choix du produit, mise à jour dynamique du swatch, assignation en table et en base), les calculs de taxes et la validation stricte de l'intégralité des données de chaque lot reçu (Produit, Emplacement, Qté > 0, N° de Lot non vide, Prix d'achat HT > 0).
- `auto_select_widgets.py` : Widgets d'entrée avec sélection automatique du texte au focus.
