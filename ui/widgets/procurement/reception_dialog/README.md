# UI Widgets - Boîte de Dialogue de Réception (`ui/widgets/procurement/reception_dialog`)

Composants dédiés à la saisie et validation des réceptions de commandes (Bons de Réception).

## Fichiers et Rôles

- `__init__.py` : Expose `ReceptionDialog`.
- `reception_dialog.py` : Classe principale de la boîte de dialogue de réception.
- `reception_dialog_ui.py` : Mixin construisant l'interface graphique, les champs de saisie et les libellés avec indication des champs obligatoires (Produit, Qté, N° de Lot, Emplacement, Prix U HT).
- `reception_dialog_logic.py` : Mixin contenant la logique métier, les calculs de taxes et la validation stricte de l'intégralité des données de chaque lot reçu (Produit, Emplacement, Qté > 0, N° de Lot non vide, Prix d'achat HT > 0).
- `auto_select_widgets.py` : Widgets d'entrée avec sélection automatique du texte au focus.
