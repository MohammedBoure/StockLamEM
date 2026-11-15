# Module `ui/widgets/versement/`

Espace dédié à l'entrée **Versement** de la barre de navigation latérale (`Page 17 : Versement`, `nav_versement`), ainsi qu'aux composants réutilisables de suivi et modification directe des paiements par bon.

## Fichiers
- `__init__.py` : Exporte `VersementTab`, `BonPaymentsWorkspaceWidget`, `BonPaymentAddDialog`, et `BonPaymentsManageDialog`.
- `versement_tab.py` : Vue principale `VersementTab` configurant `BonPaymentsWorkspaceWidget` pour les bons de type `BON_VERSEMENT`.
- `bon_payments_workspace.py` : Espace générique réutilisable `BonPaymentsWorkspaceWidget` affichant les indicateurs clés, la recherche/filtres par statut et le tableau structuré de tous les bons avec actions directes par ligne (`+ Versement` et `Modifier`).
- `bon_payments_dialogs.py` : Fenêtres modales `BonPaymentAddDialog` (ajout rapide d'une tranche avec choix visuel du mode de paiement et bouton `Tout Solder`) et `BonPaymentsManageDialog` (liste des versements d'un bon avec édition inline directe et suppression).
- `README.md` : Documentation de ce répertoire.
