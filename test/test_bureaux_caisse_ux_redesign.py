# -*- coding: utf-8 -*-
"""
test/test_bureaux_caisse_ux_redesign.py
=======================================
Verification suite for the Bureaux & Caisse UX and Theme Overhaul:
1. Shared design tokens in ui/widgets/appliance_desks/_theme.py.
2. CashierDeskWidget POS UX:
   - Resizable QSplitter (non-collapsible).
   - Live queue summary pill & quick type filter chips (Tous, Comptant, Crédit, Livraison, Versement).
   - Exact amount button (btn_exact_cash) & live change/shortfall indicator (lbl_change_due).
   - Active bon type pill (lbl_order_type_pill) & Enter-key validation shortcut.
3. ApplianceWorkflowTab de-containerized borderless pane & live Caisse tab badge.
4. DispatchDeskWidget & OrderDeskWidget clean labels without emojis/clutter.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication, QSplitter

from ui.widgets.appliance_desks._theme import (
    BOND_TYPE_BADGES,
    BRAND_TEAL,
    BUREAUX_TABLE_QSS,
    CANVAS_BG,
)
from ui.widgets.appliance_desks.appliance_workflow_tab import ApplianceWorkflowTab
from ui.widgets.appliance_desks.cashier_desk_view import CashierDeskWidget
from ui.widgets.appliance_desks.dispatch_desk_view import DispatchDeskWidget
from ui.widgets.appliance_desks.order_desk_view import OrderDeskWidget


class TestBureauxCaisseUXRedesign(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["PYTEST_CURRENT_TEST"] = "1"
        cls.app = QApplication.instance() or QApplication([])

    def _make_mock_dm(self):
        dm = MagicMock()
        dm.current_user = {"User_ID": 1, "Username": "caissier", "Role": "Admin"}
        dm.clients.get_all_clients.return_value = [
            {"Client_ID": 1, "Client_Name": "Client Comptoir", "Phone": "0550000000"}
        ]
        dm.manufacturers.get_all_manufacturers.return_value = []
        dm.families.get_all_families.return_value = []
        dm.colors.get_all_colors.return_value = []
        dm.serials.get_catalog_with_theoretical_stock.return_value = []
        dm.bonds.get_client_wallet.return_value = {
            "current_balance": 20000.0,
            "real_deposit_balance": 15000.0,
            "virtual_credit_balance": 5000.0,
        }
        dm.bonds.get_caisse_order_queue.return_value = [
            {
                "Order_ID": 101,
                "Order_Number": "1-BC-0101",
                "Client_ID": 1,
                "Client_Name": "Client A",
                "Bond_Type": "BON_C",
                "Total_Amount_TTC": 50000.0,
                "Status": "CONFIRMED_PENDING_PAYMENT",
                "lines": [],
            },
            {
                "Order_ID": 102,
                "Order_Number": "2-BCR-0102",
                "Client_ID": 2,
                "Client_Name": "Client B",
                "Bond_Type": "BON_CREDIT",
                "Total_Amount_TTC": 80000.0,
                "Status": "CONFIRMED_PENDING_PAYMENT",
                "lines": [],
            },
            {
                "Order_ID": 103,
                "Order_Number": "3-BLV-0103",
                "Client_ID": 3,
                "Client_Name": "Client C",
                "Bond_Type": "BON_LIVRAISON",
                "Total_Amount_TTC": 30000.0,
                "Status": "CONFIRMED_PENDING_PAYMENT",
                "lines": [],
            },
        ]
        dm.bonds.get_dispatch_order_queue.return_value = []
        return dm

    def test_theme_tokens_consistent(self):
        self.assertEqual(BRAND_TEAL, "#007572")
        self.assertEqual(CANVAS_BG, "#F5F7FA")
        self.assertIn("#E6F4F1", BUREAUX_TABLE_QSS)
        self.assertIn("BON_C", BOND_TYPE_BADGES)
        self.assertIn("BON_VERSEMENT", BOND_TYPE_BADGES)

    def test_caisse_splitter_chips_and_summary(self):
        dm = self._make_mock_dm()
        desk = CashierDeskWidget(data_manager=dm)
        try:
            splitter = desk.findChild(QSplitter, "CaisseMainSplitter")
            self.assertIsNotNone(splitter)
            self.assertFalse(splitter.childrenCollapsible())

            # Summary pill & chip counts
            self.assertIn("3 bons", desk.lbl_queue_summary.text())
            self.assertEqual(desk.btn_filter_all.text(), "Tous (3)")
            self.assertEqual(desk.btn_filter_bc.text(), "Comptant (1)")
            self.assertEqual(desk.btn_filter_credit.text(), "Crédit (1)")
            self.assertEqual(desk.btn_filter_bl.text(), "Livraison (1)")
            self.assertEqual(desk.btn_filter_vrs.text(), "Versement (0)")

            # Click Comptant chip -> only row 0 visible
            desk.btn_filter_bc.click()
            self.assertFalse(desk.queue_table.isRowHidden(0))
            self.assertTrue(desk.queue_table.isRowHidden(1))
            self.assertTrue(desk.queue_table.isRowHidden(2))

            # Reset restores all
            desk._reset_scan_filter()
            self.assertFalse(desk.queue_table.isRowHidden(0))
            self.assertFalse(desk.queue_table.isRowHidden(1))
            self.assertFalse(desk.queue_table.isRowHidden(2))
        finally:
            desk.deleteLater()

    def test_caisse_exact_cash_change_due_and_type_pill(self):
        dm = self._make_mock_dm()
        desk = CashierDeskWidget(data_manager=dm)
        try:
            desk.queue_table.selectRow(0)
            desk._on_order_selected()

            # Type pill reflects Bon Comptant
            self.assertFalse(desk.lbl_order_type_pill.isHidden())
            self.assertEqual(desk.lbl_order_type_pill.text(), "Bon Comptant")

            # Check wallet deduction + Exact button
            desk.cb_wallet.setChecked(True)
            desk.btn_exact_cash.click()
            self.assertEqual(desk.txt_cash.text(), "30000")

            # Cash > remaining due shows Monnaie à rendre
            desk._add_cash_increment(5000)
            self.assertEqual(desk.txt_cash.text(), "35000")
            self.assertFalse(desk.lbl_change_due.isHidden())
            self.assertIn("Monnaie", desk.lbl_change_due.text())

            # Cash < remaining due for BON_C shows Manquant
            desk.txt_cash.setText("20000")
            self.assertFalse(desk.lbl_change_due.isHidden())
            self.assertIn("Manquant", desk.lbl_change_due.text())

            # Enter triggers primary validation cleanly
            with patch.object(desk, "_finalize_bon_c") as mock_fin:
                desk._trigger_primary_validation()
                mock_fin.assert_called_once()
        finally:
            desk.deleteLater()

    def test_workflow_badges_and_emoji_free_controls(self):
        dm = self._make_mock_dm()
        wf = ApplianceWorkflowTab(data_manager=dm)
        try:
            c_idx = wf.desk_tabs.indexOf(wf.cashier_desk)
            self.assertEqual(wf.desk_tabs.tabText(c_idx), "2. Caisse (3)")
            self.assertEqual(wf.order_desk.btn_bind_scanner.text(), "Scanner")
            self.assertNotIn("Impact Caisse", wf.dispatch_desk.btn_emit_sortie.text())
            self.assertNotIn("محفظة", wf.cashier_desk.btn_wallet_balance.toolTip())
        finally:
            wf.deleteLater()


if __name__ == "__main__":
    unittest.main()
