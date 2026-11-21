# Module `ui/widgets/treasury/`

Espace dédié à l'entrée **Trésorerie** de la barre de navigation latérale (`Page 19 : Trésorerie`, `nav_treasury`), centralisant les soldes par mode de paiement (`Cash`, `BaridiMob`, `TPE`, `CCP`), l'historique complet des flux financiers issus de `Bureaux -> Caisse` / `Versement` / `Paiement Livraison`, et les opérations manuelles d'entrée (`Entrée`), de sortie (`Sortie`) et de transfert interne (`Transfert`).

## Fichiers
- `__init__.py` : Exporte `TreasuryTab`, `TreasuryOperationDialog`, `TreasuryTransferDialog`, `TreasuryMovementDetailsDialog`, et `_resolve_treasury_manager`.
- `treasury_tab.py` : Vue principale `TreasuryTab` avec cartes de solde en temps réel, onglet `1. Journal & Opérations` (filtres par période, sens, mode de paiement, recherche, export CSV, annulation des opérations manuelles) et onglet `2. Synthèse par Mode de Paiement`.
- `treasury_dialogs.py` : Fenêtres modales `TreasuryOperationDialog` (`+ Entrée` / `- Sortie` avec aperçu du solde en direct), `TreasuryTransferDialog` (transfert interne entre comptes) et `TreasuryMovementDetailsDialog` (détails en lecture seule).
- `README.md` : Documentation de ce répertoire.
