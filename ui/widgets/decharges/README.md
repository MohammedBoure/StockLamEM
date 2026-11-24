# Module `ui/widgets/decharges/`

Espace dédié à l'entrée **Décharges** de la barre de navigation latérale (`Page 20`, `nav_decharges`), permettant d'enregistrer les sorties financières (décharges) par type (configuré dans `Données de Base → Types de Décharges`) et par source (`Cash`, `BaridiMob`, `TPE`, `CCP`) avec synchronisation automatique dans le journal de **Trésorerie** (`Treasury_Movements`).

## Fichiers
- `__init__.py` : Exporte `DechargesTab` et `DechargeCreateDialog`.
- `decharges_tab.py` : Vue principale `DechargesTab` (cartes KPI, filtres par date/type/source/recherche, tableau des décharges, annulation) et dialogue `DechargeCreateDialog` pour enregistrer une nouvelle décharge.
- `README.md` : Documentation de ce répertoire.
