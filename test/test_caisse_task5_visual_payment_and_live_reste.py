# -*- coding: utf-8 -*-
"""
test/test_caisse_task5_visual_payment_and_live_reste.py
=======================================================
Unit tests for Task #5 (Bureaux -> 2. Caisse):
1. Unified Bon labels in Caisse matching Commandes:
   - Paiement complet, Paiement à crédit, Paiement à la livraison, Versement
2. Prominent oversized Montant hero readout (lbl_total_montant).
3. Real-time interactive Reste calculation updating immediately as cash input changes.
4. Horizontal visual icon strip replacing QComboBox for payment methods
   (Cash, BaridiMob, TPE, CCP) with clickable duotone vector icons.
"""

import os
import sys
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication, QComboBox, QFrame, QMessageBox

from ui.widgets.appliance_desks.cashier_desk_view import CashierDeskWidget
from ui.widgets.appliance_desks.order_desk_view import OrderDeskWidget


class TestCaisseTask5VisualPaymentAndLiveReste(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["PYTEST_CURRENT_TEST"] = "1"
        cls.app = QApplication.instance() or QApplication([])

    def _make_dm(self):
        dm = MagicMock()
        dm.current_user = {"User_ID": 1, "Username": "caissier", "Role": "Admin"}
        dm.clients.get_all_clients.return_value = []
        dm.manufacturers.get_all_manufacturers.return_value = []
        dm.families.get_all_families.return_value = []
        dm.colors.get_all_colors.return_value = []
        dm.serials.get_catalog_with_theoretical_stock.return_value = []
        dm.bonds.get_client_wallet.return_value = {
            "current_balance": 10000.0,
            "real_deposit_balance": 10000.0,
            "virtual_credit_balance": 0.0,
        }
        dm.bonds.get_caisse_order_queue.return_value = [
            {
                "Order_ID": 201,
                "Order_Number": "1-BC-0201",
                "Client_ID": 1,
                "Client_Name": "Client Alpha",
                "Bond_Type": "BON_C",
                "Total_Amount_TTC": 60000.0,
                "Status": "CONFIRMED_PENDING_PAYMENT",
                "lines": [],
            },
            {
                "Order_ID": 202,
                "Order_Number": "2-BCR-0202",
                "Client_ID": 2,
                "Client_Name": "Client Beta",
                "Bond_Type": "BON_CREDIT",
                "Total_Amount_TTC": 85000.0,
                "Status": "CONFIRMED_PENDING_PAYMENT",
                "lines": [],
            },
            {
                "Order_ID": 203,
                "Order_Number": "3-BLV-0203",
                "Client_ID": 3,
                "Client_Name": "Client Gamma",
                "Bond_Type": "BON_LIVRAISON",
                "Total_Amount_TTC": 45000.0,
                "Status": "CONFIRMED_PENDING_PAYMENT",
                "lines": [],
            },
            {
                "Order_ID": 204,
                "Order_Number": "4-VRS-0204",
                "Client_ID": 4,
                "Client_Name": "Client Delta",
                "Bond_Type": "BON_VERSEMENT",
                "Total_Amount_TTC": 25000.0,
                "Status": "CONFIRMED_PENDING_PAYMENT",
                "lines": [],
            },
        ]
        return dm

    def test_unified_bon_names_match_commandes(self):
        dm = self._make_dm()
        order_desk = OrderDeskWidget(dm)
        caisse = CashierDeskWidget(dm)
        try:
            expected_names = [
                order_desk.btn_bon_c.text(),
                order_desk.btn_credit.text(),
                order_desk.btn_livraison.text(),
                order_desk.btn_versement.text(),
            ]
            self.assertEqual(
                expected_names,
                [
                    "Paiement complet",
                    "Paiement à crédit",
                    "Paiement à la livraison",
                    "Versement",
                ],
            )

            # Filter chips in Caisse use the exact Commandes names
            self.assertEqual(caisse.btn_filter_bc.text(), "Paiement complet (1)")
            self.assertEqual(caisse.btn_filter_credit.text(), "Paiement à crédit (1)")
            self.assertEqual(caisse.btn_filter_bl.text(), "Paiement à la livraison (1)")
            self.assertEqual(caisse.btn_filter_vrs.text(), "Versement (1)")

            # Queue table column 2 ('Type de Bon') displays the exact Commandes names
            col_types = [caisse.queue_table.item(r, 2).text() for r in range(caisse.queue_table.rowCount())]
            self.assertEqual(col_types, expected_names)

            # Selected type pill & primary buttons align with Commandes names
            for row, expected_name in enumerate(expected_names):
                caisse.queue_table.selectRow(row)
                caisse._on_order_selected()
                self.assertEqual(caisse.lbl_order_type_pill.text(), expected_name)
        finally:
            order_desk.deleteLater()
            caisse.deleteLater()

    def test_prominent_montant_display_and_live_reste_calculation(self):
        dm = self._make_dm()
        caisse = CashierDeskWidget(dm)
        try:
            # Prominent large Montant label
            self.assertTrue(hasattr(caisse, "lbl_total_montant"))
            self.assertIn("font-size: 26px", caisse.lbl_total_montant.styleSheet())

            # Select BON_CREDIT (85 000 DA) -> initial txt_cash = 0 -> Reste = 85 000,00 DA
            caisse.queue_table.selectRow(1)
            caisse._on_order_selected()
            self.assertIn("85", caisse.lbl_total_montant.text())
            self.assertIn("85", caisse.lbl_rem_due.text())
            self.assertAlmostEqual(caisse._remaining_after_payment, 85000.0, places=2)

            # Type partial cash -> Reste updates immediately without any button click
            caisse.txt_cash.setText("25000")
            self.assertAlmostEqual(caisse._remaining_after_payment, 60000.0, places=2)
            self.assertIn("60", caisse.lbl_rem_due.text())

            # Combine with wallet deduction (10 000 DA) -> Reste = 50 000,00 DA
            caisse.cb_wallet.setChecked(True)
            self.assertAlmostEqual(caisse._remaining_after_payment, 50000.0, places=2)
            self.assertIn("50", caisse.lbl_rem_due.text())

            # Pay full remaining -> Reste = 0,00 DA & change due shown when overpaid
            caisse.txt_cash.setText("80000")
            self.assertAlmostEqual(caisse._remaining_after_payment, 0.0, places=2)
            self.assertIn("0", caisse.lbl_rem_due.text())
            self.assertFalse(caisse.lbl_change_due.isHidden())
            self.assertIn("Monnaie", caisse.lbl_change_due.text())

            # Empty/cleared cash input resets Reste cleanly to net_due (75 000)
            caisse.txt_cash.setText("")
            self.assertAlmostEqual(caisse._remaining_after_payment, 75000.0, places=2)
        finally:
            caisse.deleteLater()

    def test_horizontal_icon_payment_method_strip_replaces_combobox(self):
        dm = self._make_dm()
        caisse = CashierDeskWidget(dm)
        try:
            self.assertFalse(hasattr(caisse, "cbo_payment_method"))
            self.assertEqual(caisse.findChildren(QComboBox), [])

            strip = caisse.findChild(QFrame, "CaissePaymentMethodStrip")
            self.assertIsNotNone(strip)
            self.assertEqual(list(caisse.payment_method_buttons.keys()), ["Cash", "BaridiMob", "TPE", "CCP"])

            for code, btn in caisse.payment_method_buttons.items():
                self.assertTrue(btn.isCheckable())
                self.assertFalse(btn.icon().isNull(), f"Payment button {code} missing visual icon")
                self.assertGreaterEqual(btn.height(), 40)

            self.assertEqual(caisse.selected_payment_method(), "Cash")
            caisse.payment_method_buttons["BaridiMob"].click()
            self.assertEqual(caisse.selected_payment_method(), "BaridiMob")

            # Verify selected method propagates cleanly into Bon C settlement call
            caisse.queue_table.selectRow(0)
            caisse._on_order_selected()
            caisse.txt_cash.setText("60000")
            with patch("ui.widgets.appliance_desks.cashier_desk_view.QMessageBox.information"):
                caisse._finalize_bon_c()

            dm.bonds.validate_bon_c_cash.assert_called_once()
            _, kwargs = dm.bonds.validate_bon_c_cash.call_args
            self.assertEqual(kwargs["payment_method"], "BaridiMob")
            self.assertEqual(kwargs["amount_paid_card"], Decimal("60000"))
        finally:
            caisse.deleteLater()


if __name__ == "__main__":
    unittest.main()
