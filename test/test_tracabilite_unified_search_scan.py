# -*- coding: utf-8 -*-
"""Tests for Task #9: Unified Scan & Search input in Traçabilité (MovementHistoryTab)."""

import os
import sys
import unittest
from unittest.mock import MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PYTEST_CURRENT_TEST"] = "1"

from PySide6.QtWidgets import QApplication, QLineEdit

from ui.widgets.history import MovementHistoryTab
from ui.widgets.inventory.dialogs import BarcodeLineEdit

app = QApplication.instance() or QApplication(sys.argv)


class TestTracabiliteUnifiedSearchScan(unittest.TestCase):
    def tearDown(self):
        app.processEvents()

    def test_single_unified_barcode_search_input_exists(self):
        dm = MagicMock()
        dm.movement.get_movements_count.return_value = 0
        dm.movement.get_movements_log.return_value = []
        dm.serials.get_serial_details.return_value = None

        tab = MovementHistoryTab(dm)
        app.processEvents()

        self.assertFalse(hasattr(tab, "serial_audit_input"))
        self.assertFalse(hasattr(tab, "btn_verify_serial"))
        self.assertIsInstance(tab.search_input, BarcodeLineEdit)

        # Exclude QDateEdit internal QLineEdit children when counting standalone inputs
        standalone_line_edits = [
            w for w in tab.findChildren(BarcodeLineEdit)
        ]
        self.assertEqual(len(standalone_line_edits), 1)
        self.assertIs(standalone_line_edits[0], tab.search_input)
        self.assertIn("scanner", tab.search_input.placeholderText().lower())
        self.assertTrue(tab.serial_audit_banner.isHidden())
        tab.deleteLater()

    def test_scan_return_pressed_and_manual_search_work_through_single_input(self):
        dm = MagicMock()
        dm.movement.get_movements_count.return_value = 1
        dm.movement.get_movements_log.return_value = [
            {
                "Movement_ID": 10,
                "Transaction_Date": "2026-11-16 11:00:00",
                "Product_Name": "Réfrigérateur LG",
                "Batch_Barcode": "6130001122334",
                "Lot_Number": "LOT-LG-01",
                "Movement_Type": "Sale",
                "Qty_Change": -1,
                "Stock_After": 3,
                "Location_Name": "Magasin",
                "Operator_Name": "Admin",
                "Notes": "Bon de Sortie BS-10",
            }
        ]
        dm.serials.get_serial_details.side_effect = lambda sn: (
            {
                "Serial_Number": "SN-LG-9988",
                "Product_Name": "Réfrigérateur LG",
                "Brand_Mark": "LG",
                "Color_Finish": "Inox",
                "Lot_Number": "LOT-LG-01",
                "Status": "DISPATCHED",
                "Original_Client_Name": "Ahmed",
                "Original_Invoice_No": "FAC-BC-010",
            }
            if sn == "SN-LG-9988"
            else None
        )

        tab = MovementHistoryTab(dm)
        app.processEvents()

        # 1. Barcode scan (text + returnPressed) on unified search_input audits serial AND reloads logs
        tab.search_input.setText("SN-LG-9988")
        tab.search_input.returnPressed.emit()
        app.processEvents()

        dm.serials.get_serial_details.assert_called_with("SN-LG-9988")
        self.assertFalse(tab.serial_audit_banner.isHidden())
        self.assertIn("Réfrigérateur LG", tab.lbl_serial_audit_result.text())
        self.assertEqual(tab.table.rowCount(), 1)
        self.assertEqual(
            dm.movement.get_movements_log.call_args.kwargs.get("search_text"),
            "SN-LG-9988",
        )

        # 2. Clearing search hides audit banner cleanly
        tab.search_input.setText("")
        app.processEvents()
        self.assertTrue(tab.serial_audit_banner.isHidden())

        # 3. Manual typing of a product name runs debounced filter without error banner
        tab.search_input.setText("LG")
        tab._on_debounced_search()
        app.processEvents()
        self.assertTrue(tab.serial_audit_banner.isHidden())
        self.assertEqual(
            dm.movement.get_movements_log.call_args.kwargs.get("search_text"),
            "LG",
        )

        tab.deleteLater()


if __name__ == "__main__":
    unittest.main()
