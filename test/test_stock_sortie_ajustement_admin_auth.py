# -*- coding: utf-8 -*-
"""
test/test_stock_sortie_ajustement_admin_auth.py
===============================================
Unit tests for Task #7 (Stock & Magasin -> 1. Stock Actuel):
1. AdminStockAuthDialog validates Admin credentials and rejects non-admin roles.
2. BatchesTab.direct_use_process (Sortie) requires Admin authentication before consuming stock.
3. BatchesTab.adjust_stock (Ajustement) requires Admin authentication before adjusting stock.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QInputDialog, QMessageBox, QTableWidgetItem

from ui.widgets.inventory.dialogs import AdminStockAuthDialog
from ui.widgets.inventory.tabs_batches import BatchesTab


class TestStockSortieAjustementAdminAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["PYTEST_CURRENT_TEST"] = "1"
        cls.app = QApplication.instance() or QApplication([])

    def _make_mock_manager(self):
        mgr = MagicMock()
        mgr.families.get_all_families.return_value = []
        mgr.manufacturers.get_all_manufacturers.return_value = []
        mgr.automates.get_all_automates.return_value = []
        mgr.suppliers.get_all_suppliers.return_value = []
        mgr.locations.get_all_locations_flat.return_value = []
        mgr.batches.get_all_batches_detailed.return_value = []
        mgr.batches.get_priority_groups_summary.return_value = []
        mgr.waste_reasons.get_all_reasons.return_value = [{"Reason_ID": 1, "Reason_Name": "Inventaire"}]
        return mgr

    def _make_tab_with_one_row(self, mgr):
        tab = BatchesTab(mgr)
        tab.table.setRowCount(1)
        item = QTableWidgetItem("Réfrigérateur 400L")
        item.setData(Qt.UserRole, {
            "Batch_ID": 42,
            "Product_ID": 10,
            "Product_Name": "Réfrigérateur 400L",
            "Lot_Number": "LOT-42",
            "Quantity_Current": 10,
        })
        tab.table.setItem(0, 0, item)
        tab.table.selectRow(0)
        return tab

    def test_admin_stock_auth_dialog_rejects_non_admin_and_accepts_admin(self):
        mgr = self._make_mock_manager()
        dlg = AdminStockAuthDialog("Sortie de Stock", "Réfrigérateur 400L", data_manager=mgr)

        # Non-admin role must be rejected
        mgr.users.authenticate.return_value = {"User_ID": 3, "Username": "caissier", "Role": "Caissier"}
        dlg.txt_admin_user.setText("caissier")
        dlg.txt_password.setText("1234")
        with patch.object(QMessageBox, "warning") as mock_warn:
            dlg._verify_credentials()
            mock_warn.assert_called_once()
        self.assertFalse(dlg.approved)

        # Admin role must be accepted
        mgr.users.authenticate.return_value = {"User_ID": 7, "Username": "admin", "Role": "Admin"}
        dlg.txt_admin_user.setText("admin")
        dlg.txt_password.setText("secret")
        dlg._verify_credentials()
        self.assertTrue(dlg.approved)
        self.assertEqual(dlg.admin_user_id, 7)

        dlg.deleteLater()
        self.app.processEvents()

    def test_sortie_requires_admin_auth(self):
        mgr = self._make_mock_manager()
        tab = self._make_tab_with_one_row(mgr)

        with patch("ui.widgets.inventory.tabs_batches._actions.check_fefo_compliance", return_value=True), \
             patch("ui.widgets.inventory.tabs_batches._actions.AdminStockAuthDialog") as mock_auth_cls, \
             patch.object(QInputDialog, "getInt", return_value=(2, True)) as mock_get_int:
            # 1) Rejected / cancelled -> blocked
            auth_rejected = MagicMock()
            auth_rejected.exec.return_value = QDialog.Rejected
            auth_rejected.approved = False
            mock_auth_cls.return_value = auth_rejected

            tab.direct_use_process()
            mock_get_int.assert_not_called()
            mgr.batches.direct_consume_batch_unit.assert_not_called()

            # 2) Approved -> proceeds with admin_user_id
            auth_ok = MagicMock()
            auth_ok.exec.return_value = QDialog.Accepted
            auth_ok.approved = True
            auth_ok.admin_user_id = 7
            mock_auth_cls.return_value = auth_ok

            tab.direct_use_process()
            mock_get_int.assert_called_once()
            mgr.batches.direct_consume_batch_unit.assert_called_once_with(42, 2, user_id=7)

        tab.deleteLater()
        self.app.processEvents()

    def test_ajustement_requires_admin_auth(self):
        mgr = self._make_mock_manager()
        tab = self._make_tab_with_one_row(mgr)

        with patch("ui.widgets.inventory.tabs_batches._actions.AdminStockAuthDialog") as mock_auth_cls, \
             patch("ui.widgets.inventory.tabs_batches._actions.AdjustmentDialog") as mock_adj_cls:
            # 1) Rejected / cancelled -> blocked
            auth_rejected = MagicMock()
            auth_rejected.exec.return_value = QDialog.Rejected
            auth_rejected.approved = False
            mock_auth_cls.return_value = auth_rejected

            tab.adjust_stock()
            mock_adj_cls.assert_not_called()
            mgr.batches.adjust_batch_quantity.assert_not_called()

            # 2) Approved -> proceeds with admin_user_id
            auth_ok = MagicMock()
            auth_ok.exec.return_value = QDialog.Accepted
            auth_ok.approved = True
            auth_ok.admin_user_id = 7
            mock_auth_cls.return_value = auth_ok

            adj_inst = MagicMock()
            adj_inst.exec.return_value = QDialog.Accepted
            adj_inst.get_data.return_value = {"Batch_ID": 42, "Qty_Change": -1, "Reason_ID": 1}
            mock_adj_cls.return_value = adj_inst

            tab.adjust_stock()
            mock_adj_cls.assert_called_once()
            mgr.batches.adjust_batch_quantity.assert_called_once_with(42, -1, "Adjustment", 1, 7)

        tab.deleteLater()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
