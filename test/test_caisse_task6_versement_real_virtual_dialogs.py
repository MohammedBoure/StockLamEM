# -*- coding: utf-8 -*-
"""
test/test_caisse_task6_versement_real_virtual_dialogs.py
========================================================
Unit & Integration tests for Task #6 (Bureaux -> 2. Caisse):
1. Simple, direct Versement button (btn_use_versement) in Caisse checkout console.
2. Sequential dialog flow:
   - Dialog #1 (VersementTypeChoiceDialog): Choose between Versement Réel and Versement Virtuel.
   - Dialog #2 (VersementAmountApplyDialog): Enter deduction amount while viewing client's
     live remaining balance (الباقي).
3. CashierDeskWidget wallet deduction & settlement propagation (wallet_source="REAL" / "VIRTUAL").
4. BondLifecycleManager._debit_client_wallet_locked source isolation ("REAL" vs "VIRTUAL").
"""

import os
import sys
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication, QDialog

from database.bond_lifecycle_manager import BondLifecycleManager
from ui.widgets.appliance_desks.caisse_versement_flow_dialogs import (
    VersementAmountApplyDialog,
    VersementTypeChoiceDialog,
)
from ui.widgets.appliance_desks.cashier_desk_view import CashierDeskWidget


class _DummyCursor:
    def __init__(self, wallet_row):
        self.wallet_row = wallet_row
        self.executed = []
        self.lastrowid = 1

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return dict(self.wallet_row)


class TestCaisseTask6VersementRealVirtualDialogs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["PYTEST_CURRENT_TEST"] = "1"
        cls.app = QApplication.instance() or QApplication([])

    def _make_dm(self):
        dm = MagicMock()
        dm.current_user = {"User_ID": 1, "Username": "caissier", "Role": "Admin"}
        dm.clients.get_all_clients.return_value = []
        dm.bonds.get_client_wallet.return_value = {
            "current_balance": 45000.0,
            "real_deposit_balance": 20000.0,
            "virtual_credit_balance": 25000.0,
        }
        dm.bonds.get_caisse_order_queue.return_value = [
            {
                "Order_ID": 301,
                "Order_Number": "1-BC-0301",
                "Client_ID": 7,
                "Client_Name": "Karim Mansouri",
                "Bond_Type": "BON_C",
                "Total_Amount_TTC": 50000.0,
                "Status": "CONFIRMED_PENDING_PAYMENT",
                "lines": [],
            }
        ]
        return dm

    def test_type_choice_dialog_returns_real_or_virtual(self):
        dlg_real = VersementTypeChoiceDialog("Karim Mansouri", real_balance=20000.0, virtual_balance=25000.0)
        try:
            self.assertIn("Versement Réel", dlg_real.btn_real.text())
            self.assertIn("Versement Virtuel", dlg_real.btn_virtual.text())
            dlg_real.btn_real.click()
            self.assertEqual(dlg_real.result(), QDialog.Accepted)
            self.assertEqual(dlg_real.selected_type, "REAL")
        finally:
            dlg_real.deleteLater()

        dlg_virt = VersementTypeChoiceDialog("Karim Mansouri", real_balance=20000.0, virtual_balance=25000.0)
        try:
            dlg_virt.btn_virtual.click()
            self.assertEqual(dlg_virt.result(), QDialog.Accepted)
            self.assertEqual(dlg_virt.selected_type, "VIRTUAL")
        finally:
            dlg_virt.deleteLater()

    def test_amount_apply_dialog_displays_live_client_remaining_balance_and_validates(self):
        dlg = VersementAmountApplyDialog(
            client_name="Karim Mansouri",
            versement_type="REAL",
            available_balance=20000.0,
            order_due=50000.0,
        )
        try:
            # Default Max fills 20 000 DA -> client remaining = 0,00 DA
            self.assertIn("Solde client restant", dlg.lbl_client_remaining.text())
            self.assertIn("0", dlg.lbl_client_remaining.text())
            self.assertTrue(dlg.btn_confirm.isEnabled())

            # Entering 12 000 DA shows client remaining = 8 000,00 DA immediately
            dlg.txt_amount.setText("12000")
            self.assertIn("8", dlg.lbl_client_remaining.text())
            self.assertIn("38", dlg.lbl_order_remaining.text())
            self.assertTrue(dlg.btn_confirm.isEnabled())

            # Entering amount > available balance disables confirm and shows error
            dlg.txt_amount.setText("30000")
            self.assertFalse(dlg.btn_confirm.isEnabled())
            self.assertFalse(dlg.lbl_error.isHidden())

            # Back to valid 12 000 DA and confirm
            dlg.txt_amount.setText("12000")
            dlg.btn_confirm.click()
            self.assertEqual(dlg.result(), QDialog.Accepted)
            self.assertAlmostEqual(dlg.applied_amount, 12000.0, places=2)
        finally:
            dlg.deleteLater()

    def test_caisse_sequential_versement_flow_real_and_virtual_settlement(self):
        dm = self._make_dm()
        caisse = CashierDeskWidget(data_manager=dm)
        try:
            self.assertTrue(hasattr(caisse, "btn_use_versement"))
            self.assertEqual(caisse.btn_use_versement.text(), "Versement")

            caisse.queue_table.selectRow(0)
            caisse._on_order_selected()

            # Simulate sequential clicks: (1) Versement Réel -> (2) 12 000 DA
            def _fake_type_exec(dlg_self):
                dlg_self.btn_real.click()
                return QDialog.Accepted

            def _fake_amt_exec(dlg_self):
                dlg_self.txt_amount.setText("12000")
                dlg_self.btn_confirm.click()
                return QDialog.Accepted

            with patch.object(VersementTypeChoiceDialog, "exec", _fake_type_exec), \
                 patch.object(VersementAmountApplyDialog, "exec", _fake_amt_exec):
                caisse.btn_use_versement.click()

            self.assertTrue(caisse.cb_wallet.isChecked())
            self.assertEqual(caisse._custom_wallet_source, "REAL")
            self.assertAlmostEqual(caisse._get_wallet_deduction(), 12000.0, places=2)
            self.assertFalse(caisse.applied_versement_row.isHidden())
            self.assertIn("Versement Réel", caisse.lbl_applied_versement.text())
            self.assertAlmostEqual(caisse._current_remaining_due, 38000.0, places=2)
            self.assertEqual(caisse.txt_cash.text(), "38000")

            with patch("ui.widgets.appliance_desks.cashier_desk_view.QMessageBox.information"):
                caisse._finalize_bon_c()

            dm.bonds.validate_bon_c_cash.assert_called_once()
            _, kwargs = dm.bonds.validate_bon_c_cash.call_args
            self.assertEqual(kwargs["amount_paid_wallet"], Decimal("12000.0"))
            self.assertEqual(kwargs["amount_paid_cash"], Decimal("38000.0"))
            self.assertEqual(kwargs["wallet_source"], "REAL")

            # Reset and run Virtual Versement flow (15 000 DA)
            dm.bonds.validate_bon_c_cash.reset_mock()
            caisse.queue_table.selectRow(0)
            caisse._on_order_selected()

            def _fake_virt_exec(dlg_self):
                dlg_self.btn_virtual.click()
                return QDialog.Accepted

            def _fake_virt_amt_exec(dlg_self):
                dlg_self.txt_amount.setText("15000")
                dlg_self.btn_confirm.click()
                return QDialog.Accepted

            with patch.object(VersementTypeChoiceDialog, "exec", _fake_virt_exec), \
                 patch.object(VersementAmountApplyDialog, "exec", _fake_virt_amt_exec):
                caisse.btn_use_versement.click()

            self.assertEqual(caisse._custom_wallet_source, "VIRTUAL")
            self.assertAlmostEqual(caisse._get_wallet_deduction(), 15000.0, places=2)
            self.assertIn("Versement Virtuel", caisse.lbl_applied_versement.text())

            with patch("ui.widgets.appliance_desks.cashier_desk_view.QMessageBox.information"):
                caisse._finalize_bon_c()

            _, v_kwargs = dm.bonds.validate_bon_c_cash.call_args
            self.assertEqual(v_kwargs["amount_paid_wallet"], Decimal("15000.0"))
            self.assertEqual(v_kwargs["wallet_source"], "VIRTUAL")

            # Clearing applied versement restores zero wallet deduction
            caisse.btn_clear_applied_versement.click()
            self.assertIsNone(caisse._custom_wallet_source)
            self.assertFalse(caisse.cb_wallet.isChecked())
            self.assertAlmostEqual(caisse._get_wallet_deduction(), 0.0, places=2)
        finally:
            caisse.deleteLater()

    def test_backend_debit_wallet_respects_real_vs_virtual_source(self):
        mgr = BondLifecycleManager(MagicMock())

        # Case 1: REAL only debits Real_Deposit_Balance (20000 -> 8000), Virtual stays 25000
        cur_real = _DummyCursor({
            "Wallet_ID": 10,
            "Client_ID": 7,
            "Current_Balance": Decimal("45000.00"),
            "Real_Deposit_Balance": Decimal("20000.00"),
            "Virtual_Credit_Balance": Decimal("25000.00"),
        })
        mgr._debit_client_wallet_locked(
            cur_real, 7, Decimal("12000.00"), invoice_id=100, user_id=1, wallet_source="REAL"
        )
        update_sql, update_params = cur_real.executed[-1]
        self.assertIn("UPDATE Client_Wallets", update_sql)
        # params: (bal_after, virt_after, real_after, debit_dec, wallet_id)
        self.assertEqual(update_params[0], Decimal("33000.00"))
        self.assertEqual(update_params[1], Decimal("25000.00"))
        self.assertEqual(update_params[2], Decimal("8000.00"))

        # Case 2: VIRTUAL only debits Virtual_Credit_Balance (25000 -> 10000), Real stays 20000
        cur_virt = _DummyCursor({
            "Wallet_ID": 10,
            "Client_ID": 7,
            "Current_Balance": Decimal("45000.00"),
            "Real_Deposit_Balance": Decimal("20000.00"),
            "Virtual_Credit_Balance": Decimal("25000.00"),
        })
        mgr._debit_client_wallet_locked(
            cur_virt, 7, Decimal("15000.00"), invoice_id=101, user_id=1, wallet_source="VIRTUAL"
        )
        _, v_params = cur_virt.executed[-1]
        self.assertEqual(v_params[0], Decimal("30000.00"))
        self.assertEqual(v_params[1], Decimal("10000.00"))
        self.assertEqual(v_params[2], Decimal("20000.00"))

        # Case 3: Exceeding specific source balance raises ValueError even if total balance suffices
        with self.assertRaises(ValueError):
            mgr._debit_client_wallet_locked(
                cur_real, 7, Decimal("22000.00"), invoice_id=102, user_id=1, wallet_source="REAL"
            )


if __name__ == "__main__":
    unittest.main()
