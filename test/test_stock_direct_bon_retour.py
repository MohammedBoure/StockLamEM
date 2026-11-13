# -*- coding: utf-8 -*-
"""
test/test_stock_direct_bon_retour.py
====================================
Unit tests for Task #8 (Stock & Magasin -> 1. Stock Actuel -> Bon de Retour / Avoir):
1. DirectBonRetourDialog displays Fournisseur & BL info and has a single quantity input field (1..max_qty).
2. BatchesTab context menu exposes 'Créer Bon de Retour / Avoir'.
3. BatchesTab.create_direct_bon_retour creates a linked supplier credit note (BR_ID + Supplier_ID + Batch_ID)
   via manager.credit_notes.create_credit_note and refreshes the table.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QLineEdit, QMenu, QMessageBox, QSpinBox, QTableWidgetItem

from ui.widgets.inventory.dialogs import DirectBonRetourDialog
from ui.widgets.inventory.tabs_batches import BatchesTab


class TestStockDirectBonRetour(unittest.TestCase):
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
        mgr.credit_notes.create_credit_note.return_value = (True, "Avoir enregistré (ID: 12)")
        return mgr

    def test_direct_bon_retour_dialog_single_qty_input_and_info(self):
        batch = {
            "Batch_ID": 42,
            "Product_ID": 10,
            "Product_Name": "Cuisinière 5 Feux",
            "Supplier_ID": 5,
            "Supplier_Name": "Fournisseur Alpha",
            "BR_ID": 77,
            "Supplier_BL_Ref": "BL-2026-077",
            "Quantity_Current": 8,
        }
        dlg = DirectBonRetourDialog(batch)

        # Verify only ONE editable input (spin_qty_return)
        spin_boxes = dlg.findChildren(QSpinBox)
        line_edits = dlg.findChildren(QLineEdit)
        self.assertEqual(len(spin_boxes), 1)
        # Note: QSpinBox internally owns one QLineEdit child; ensure no standalone QLineEdit exists
        self.assertEqual(len(line_edits), 1)
        self.assertEqual(dlg.spin_qty_return.minimum(), 1)
        self.assertEqual(dlg.spin_qty_return.maximum(), 8)

        labels_text = " ".join(lbl.text() for lbl in dlg.findChildren(QLabel))
        self.assertIn("Fournisseur Alpha", labels_text)
        self.assertIn("BL-2026-077", labels_text)

        dlg.spin_qty_return.setValue(3)
        self.assertEqual(dlg.get_qty(), 3)

        dlg.deleteLater()
        self.app.processEvents()

    def test_context_menu_contains_bon_retour_action(self):
        mgr = self._make_mock_manager()
        tab = BatchesTab(mgr)
        tab.table.setRowCount(1)
        item = QTableWidgetItem("Cuisinière 5 Feux")
        item.setData(Qt.UserRole, {
            "Batch_ID": 42,
            "Product_ID": 10,
            "Product_Name": "Cuisinière 5 Feux",
            "Supplier_ID": 5,
            "BR_ID": 77,
            "Quantity_Current": 5,
        })
        tab.table.setItem(0, 0, item)

        captured_labels = []

        class FakeMenu(QMenu):
            def exec(self, *_args, **_kwargs):
                captured_labels.extend(a.text() for a in self.actions() if a.text())
                return None

        with patch("ui.widgets.inventory.tabs_batches._actions.get_current_role", return_value="Admin"), \
             patch("ui.widgets.inventory.tabs_batches._context_menu.QMenu", FakeMenu):
            rect = tab.table.visualItemRect(item)
            tab.show_context_menu(rect.center())

        self.assertTrue(any("Bon de Retour" in lbl for lbl in captured_labels))

        tab.deleteLater()
        self.app.processEvents()

    def test_create_direct_bon_retour_creates_linked_avoir(self):
        mgr = self._make_mock_manager()
        tab = BatchesTab(mgr)
        batch_data = {
            "Batch_ID": 42,
            "Product_ID": 10,
            "Product_Name": "Cuisinière 5 Feux",
            "Lot_Number": "LOT-42",
            "Supplier_ID": 5,
            "Supplier_Name": "Fournisseur Alpha",
            "BR_ID": 77,
            "Supplier_BL_Ref": "BL-2026-077",
            "Quantity_Current": 8,
            "Unit_Price_Received": 10000.0,
            "Discount_Percent": 10.0,
        }

        with patch("ui.widgets.inventory.tabs_batches._actions.DirectBonRetourDialog") as mock_dlg_cls, \
             patch.object(QMessageBox, "information") as mock_info:
            dlg_inst = MagicMock()
            dlg_inst.exec.return_value = QDialog.Accepted
            dlg_inst.get_qty.return_value = 2
            mock_dlg_cls.return_value = dlg_inst

            tab.create_direct_bon_retour(batch_data)

            mgr.credit_notes.create_credit_note.assert_called_once()
            header_arg, items_arg = mgr.credit_notes.create_credit_note.call_args[0]
            self.assertEqual(header_arg["Supplier_ID"], 5)
            self.assertEqual(header_arg["BR_ID"], 77)
            self.assertEqual(header_arg["Type"], "Return_Goods")
            self.assertAlmostEqual(header_arg["Total_Amount_TTC"], 18000.0, places=2)
            self.assertEqual(len(items_arg), 1)
            self.assertEqual(items_arg[0]["Batch_ID"], 42)
            self.assertEqual(items_arg[0]["Qty_Returned"], 2)
            self.assertAlmostEqual(items_arg[0]["Unit_Price"], 9000.0, places=2)
            mock_info.assert_called_once()

        tab.deleteLater()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
