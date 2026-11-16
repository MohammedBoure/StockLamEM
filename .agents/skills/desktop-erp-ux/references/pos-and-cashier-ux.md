# POS & Cashier UX (`Caisse` / `Encaissement`)

## 1. Scanner & Queue Flow
- **Auto-Focus**: Keep focus on `Scanner N° Bon ou client...` when entering `Caisse` or immediately after completing an encaissement.
- **Enter to Select**: Pressing `Enter` with an exact bon number should immediately select that bon in the queue and load it in `Encaissement` (move focus to `Montant Reçu` only if payment is pending).
- **Queue Density**: When the queue has few items, avoid stretching an empty table down to force a distant footer bar; keep queue actions close to the queue header or compact at the bottom.

## 2. Payment Panel (`Encaissement`)
- **Clear Status Feedback**: If the selected bon is already paid (`Reste : 0,00 DA`), clearly disable payment inputs/mode buttons and show *one* clear status banner/button explaining the next step (`Payé — Attente Sortie Magasin`), rather than leaving active-looking `Exact` / `+1 000` buttons that do nothing.
- **Uniform Quick-Amount Presets**: Keep preset buttons (`+1 000`, `+2 000`, `+5 000`, `+10 000`, `0 DA`) equal width in a single row.
- **Wallet (`Portefeuille Client`)**: Ensure `Utiliser le solde portefeuille` checkbox is visually crisp and automatically disabled with a tooltip if balance is `0,00 DA`.

## 3. Destructive & Financial Confirmations
- `Retirer Bon` must open a confirmation dialog naming the bon (`N° Bon` + client name) before removing it from the queue.
- Never allow accidental double-clicks on payment submission: disable the submit button while the transaction commits.
