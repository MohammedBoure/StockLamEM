# UI Widgets - Boîte de Dialogue de Réception (`ui/widgets/procurement/reception_dialog`)

Composants dédiés à la saisie et validation des réceptions de commandes (Bons de Réception).

## Fichiers et Rôles

- `__init__.py` : Expose `ReceptionDialog`.
- `reception_dialog.py` : Classe principale de la boîte de dialogue de réception.
- `reception_dialog_ui.py` : Mixin construisant l'interface graphique épurée (Produit, Couleur / Finition `cb_color` avec aperçu visuel direct `lbl_color_swatch`, Unité, Qté, Emplacement, Prix U, Remise; champs Lot, Date Exp. et TVA masqués) et le tableau des articles reçus intégrant la colonne 'Couleur'.
- `reception_dialog_logic.py` : Mixin contenant la logique métier, la gestion des couleurs d'appareils (chargement via `ProductColorManager`, pré-sélection automatique au choix du produit, mise à jour dynamique du swatch, assignation en table et en base), le calcul sans TVA (0% par défaut), l'auto-génération transparente du `Lot_Number` sans date d'expiration requise, et la validation des données de réception (Produit, Emplacement, Qté > 0, Prix d'achat > 0).
- `auto_select_widgets.py` : Widgets d'entrée avec sélection automatique du texte au focus.
