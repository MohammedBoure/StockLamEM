# -*- coding: utf-8 -*-
"""
test/test_cashier_wallet_and_simplified_buttons.py
==================================================
Test suite verifying Task #3:
1. Simplified button & label texts in Bureau Caisse & Règlements:
   - 'Versement' (previously 'Enregistrer un Versement Client (Dépôt Espèces)')
   - 'Versement Virtuel' (previously 'Émettre Bon de Retour (Versement Virtuel)')
   - 'Valider Bon Comptant' (previously 'Valider Bon Comptant (Encaissement Direct -> Sortie)')
   - 'Valider Bon de Livraison' (previously 'Valider Bon de Livraison (Acompte / Solde COD)')
   - 'Validation Caisse' (previously 'Console d'Encaissement & Validation Caisse')
2. Dedicated Versement Wallet Consultation:
   - 'Solde Versement' button in ops_bar
   - 'Détails Solde' button in CustomerWalletCard
   - ClientWalletDialog with 3 KPI metric cards (Real Versement, Virtual Versement, Total) and audit table
   - BondLifecycleManager.get_client_wallet_transactions integration
"""

import os
import sys
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from ui.widgets.appliance_desks.cashier_desk_view import CashierDeskWidget, ClientWalletDialog
from database.bond_lifecycle_manager import BondLifecycleManager


# Ensure QApplication instance
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)


class TestCashierWalletAndSimplifiedButtons(unittest.TestCase):

    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_dm = MagicMock()
        self.mock_dm.bonds = BondLifecycleManager(self.mock_db)
        self.mock_dm.clients = MagicMock()
        self.mock_dm.clients.get_all_clients.return_value = [
            {"Client_ID": 1, "Client_Name": "Amine Benali", "Phone": "0555112233"},
            {"Client_ID": 2, "Client_Name": "Kamel Hamidi", "Phone": "0661445566"},
        ]

    def tearDown(self):
        app.processEvents()

    def test_simplified_button_and_header_labels(self):
        """Verifies all button texts and headers in CashierDeskWidget are streamlined."""
        desk = CashierDeskWidget(data_manager=self.mock_dm)

        # 1. Versement button
        self.assertTrue(hasattr(desk, "btn_versement"))
        self.assertEqual(desk.btn_versement.text(), "Versement")
        self.assertGreaterEqual(desk.btn_versement.height(), 44)

        # 2. Versement Virtuel button
        self.assertTrue(hasattr(desk, "btn_retour"))
        self.assertEqual(desk.btn_retour.text(), "Versement Virtuel")
        self.assertGreaterEqual(desk.btn_retour.height(), 44)

        # 3. Solde Versement consultation button in ops_bar
        self.assertTrue(hasattr(desk, "btn_wallet_balance"))
        self.assertEqual(desk.btn_wallet_balance.text(), "Solde Versement")
        self.assertGreaterEqual(desk.btn_wallet_balance.height(), 44)

        # 4. Valider Bon Comptant
        self.assertTrue(hasattr(desk, "btn_val_bon_c"))
        self.assertEqual(desk.btn_val_bon_c.text(), "Valider Bon Comptant")
        self.assertGreaterEqual(desk.btn_val_bon_c.height(), 46)

        # 5. Valider Bon de Livraison
        self.assertTrue(hasattr(desk, "btn_val_livraison"))
        self.assertEqual(desk.btn_val_livraison.text(), "Valider Bon de Livraison")
        self.assertGreaterEqual(desk.btn_val_livraison.height(), 42)

        # 6. Validation Caisse header
        headers = [lbl.text() for lbl in desk.findChildren(QLabel)]
        self.assertIn("Validation Caisse", headers)

        # 7. Details Solde button in right wallet panel
        self.assertTrue(hasattr(desk, "btn_inspect_wallet"))
        self.assertEqual(desk.btn_inspect_wallet.text(), "Détails Solde")

        desk.deleteLater()
        app.processEvents()

    def test_client_wallet_dialog_metrics_and_transactions(self):
        """Verifies ClientWalletDialog properly reflects real versement and virtual credit amounts."""
        sample_wallet = {
            "wallet_id": 10,
            "client_id": 1,
            "current_balance": 35000.0,
            "real_deposit_balance": 20000.0,
            "virtual_credit_balance": 15000.0,
            "status": "ACTIVE",
        }
        sample_txs = [
            {
                "Transaction_ID": 101,
                "Transaction_Type": "REAL_CASH_VERSEMENT",
                "Amount": 20000.0,
                "Balance_Before": 0.0,
                "Balance_After": 20000.0,
                "Source_Document_Type": "VERSEMENT_CAISSE",
                "Transaction_Notes": "Dépôt espèces initial",
                "Created_At": "2026-11-06 10:00:00",
            },
            {
                "Transaction_ID": 102,
                "Transaction_Type": "RETURN_VIRTUAL_CREDIT",
                "Amount": 15000.0,
                "Balance_Before": 20000.0,
                "Balance_After": 35000.0,
                "Source_Document_Type": "BON_RETOUR",
                "Transaction_Notes": "Avoir sur retour BR-001",
                "Created_At": "2026-11-06 10:30:00",
            },
        ]

        with patch.object(self.mock_dm.bonds, "get_client_wallet", return_value=sample_wallet), \
             patch.object(self.mock_dm.bonds, "get_client_wallet_transactions", return_value=sample_txs):

            dlg = ClientWalletDialog(data_manager=self.mock_dm, default_client_id=1)

            # 1. ComboBox contains clients
            self.assertEqual(dlg.cbo_clients.count(), 2)
            self.assertEqual(dlg.cbo_clients.currentData(), 1)

            # 2. Metric cards reflect wallet values
            real_txt = dlg.card_real.findChild(QLabel, "lbl_kpi_val").text()
            self.assertIn("20", real_txt)
            self.assertIn("DA", real_txt)

            virt_txt = dlg.card_virt.findChild(QLabel, "lbl_kpi_val").text()
            self.assertIn("15", virt_txt)
            self.assertIn("DA", virt_txt)

            tot_txt = dlg.card_tot.findChild(QLabel, "lbl_kpi_val").text()
            self.assertIn("35", tot_txt)
            self.assertIn("DA", tot_txt)

            # 3. Transaction table populated with 2 rows
            self.assertEqual(dlg.table_tx.rowCount(), 2)
            self.assertIn("Versement Espèces", dlg.table_tx.item(0, 1).text())
            self.assertIn("20", dlg.table_tx.item(0, 2).text())
            self.assertIn("Avoir", dlg.table_tx.item(1, 1).text())
            self.assertIn("15", dlg.table_tx.item(1, 2).text())

            dlg.deleteLater()
            app.processEvents()

    def test_bond_lifecycle_manager_get_client_wallet_transactions(self):
        """Verifies BondLifecycleManager.get_client_wallet_transactions queries database correctly."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "Transaction_ID": 1,
                "Transaction_Type": "REAL_CASH_VERSEMENT",
                "Amount": Decimal("5000.00"),
                "Balance_Before": Decimal("0.00"),
                "Balance_After": Decimal("5000.00"),
                "Source_Document_Type": "VERSEMENT_CAISSE",
                "Source_Document_ID": 10,
                "Affects_Physical_Caisse": 1,
                "Transaction_Notes": "Test note",
                "Created_At": "2026-11-06 09:00:00",
            }
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn_ctx = MagicMock()
        mock_conn_ctx.__enter__.return_value = mock_conn
        self.mock_db.get_db_connection.return_value = mock_conn_ctx

        mgr = BondLifecycleManager(self.mock_db)
        txs = mgr.get_client_wallet_transactions(client_id=1, limit=10)

        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0]["Transaction_Type"], "REAL_CASH_VERSEMENT")
        self.assertEqual(txs[0]["Amount"], Decimal("5000.00"))

    def test_no_tpe_fields_in_caisse_reglements(self):
        """Verifies Task #4: No TPE / Carte CIB fields exist in Caisse & Règlements."""
        desk = CashierDeskWidget(data_manager=self.mock_dm)

        # 1. txt_tpe attribute does not exist on desk
        self.assertFalse(hasattr(desk, "txt_tpe"))

        # 2. No label mentions TPE or Carte CIB
        all_labels = [lbl.text() for lbl in desk.findChildren(QLabel)]
        for text in all_labels:
            self.assertNotIn("TPE", text)
            self.assertNotIn("Carte CIB", text)

        # 3. Cash input is present and functional
        self.assertTrue(hasattr(desk, "txt_cash"))

        desk.deleteLater()
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
