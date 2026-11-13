# -*- coding: utf-8 -*-
"""
test/test_reception_direct_bl.py
================================
Unit tests for Task #4 (Achats & Entrées -> Bons de Réceptions):
1. ReceptionHistoryTab provides a '+ Nouveau BL Direct' button to create a BL without a Bon de Commande (PO_ID=None).
2. ReceptionDialog in direct BL mode displays a supplier selector (cb_supplier), requires a supplier, and creates the header with PO_ID=None.
3. generate_internal_barcode handles PO_ID=None cleanly.
4. ReceptionHistoryTab displays 'Direct (Sans BC)' for receptions without a PO_ID.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QMessageBox

from ui.widgets.procurement.reception_dialog.reception_dialog import ReceptionDialog
from ui.widgets.procurement.reception_history_tab import ReceptionHistoryTab


class TestReceptionDirectBL(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["PYTEST_CURRENT_TEST"] = "1"
        cls.app = QApplication.instance() or QApplication([])

    def _make_mock_manager(self):
        mgr = MagicMock()
        mgr.suppliers.get_all_suppliers.return_value = [
            {"Supplier_ID": 5, "Supplier_Name": "Fournisseur Alpha"},
            {"Supplier_ID": 9, "Supplier_Name": "Fournisseur Beta"},
        ]
        mgr.products.get_all_products.return_value = [
            {"Product_ID": 10, "Product_Name": "Réfrigérateur 400L", "Barcode": "REF-400", "Stock_Unit": "U"}
        ]
        mgr.locations.get_all_locations_flat.return_value = [
            {"Location_ID": 1, "Location_Name": "Dépôt A"}
        ]
        mgr.reception.create_new_reception_header.return_value = 88
        mgr.reception.get_all_receptions.return_value = []
        mgr.batches.get_barcode_prefix_for_po.return_value = "0"
        mgr.batches.get_next_reception_barcode.return_value = "0001"
        mgr.batches.get_next_smart_barcode.return_value = "0001"
        mgr.batches.extract_smart_barcode_serial.return_value = 1
        return mgr

    def test_direct_bl_dialog_requires_supplier_and_creates_header_without_po(self):
        mgr = self._make_mock_manager()
        dlg = ReceptionDialog(
            po_data={"PO_ID": None, "Supplier_ID": None, "Supplier_Name": None},
            locations_list=[{"Location_ID": 1, "Location_Name": "Dépôt A"}],
            location_manager=mgr.locations,
            manager=mgr,
            printer_manager=MagicMock(),
        )

        self.assertFalse(dlg.cb_supplier.isHidden())
        self.assertIn("BL Direct", dlg.windowTitle())
        self.assertGreaterEqual(dlg.cb_supplier.count(), 3)

        # Missing supplier should warn and return False
        dlg.bl_ref.setText("BL-DIRECT-001")
        with patch.object(QMessageBox, "warning") as mock_warn:
            res = dlg.validate_header_and_create()
            self.assertFalse(res)
            mock_warn.assert_called_once()

        # Select supplier and validate
        idx = dlg.cb_supplier.findData(9)
        self.assertGreater(idx, 0)
        dlg.cb_supplier.setCurrentIndex(idx)

        with patch.object(QMessageBox, "warning", side_effect=AssertionError("Unexpected warning")), \
             patch.object(QMessageBox, "critical", side_effect=AssertionError("Unexpected critical")):
            res = dlg.validate_header_and_create()
            self.assertTrue(res)

        self.assertEqual(dlg.br_id, 88)
        self.assertFalse(dlg.cb_supplier.isEnabled())
        header_arg = mgr.reception.create_new_reception_header.call_args[0][0]
        self.assertIsNone(header_arg["PO_ID"])
        self.assertEqual(header_arg["Supplier_ID"], 9)
        self.assertEqual(header_arg["Supplier_BL_Ref"], "BL-DIRECT-001")

        # Barcode generation works with PO_ID=None (normalized to 0)
        bc = dlg.generate_internal_barcode()
        self.assertEqual(bc, "0001")
        mgr.batches.get_next_reception_barcode.assert_called_with(88, po_id=0)

        dlg.deleteLater()
        self.app.processEvents()

    def test_reception_history_tab_direct_bl_button_and_display(self):
        mgr = self._make_mock_manager()
        mgr.reception.get_all_receptions.return_value = [
            {
                "BR_ID": 88,
                "PO_ID": None,
                "Supplier_ID": 9,
                "Supplier_Name": "Fournisseur Beta",
                "Supplier_Invoice_Ref": None,
                "Supplier_BL_Ref": "BL-DIRECT-001",
                "Reception_Date": "2026-11-13",
                "Invoice_Total_HT": 10000.0,
                "Invoice_Total_TVA": 0.0,
                "Total_Discount": 0.0,
                "Invoice_Total_TTC": 10000.0,
                "Status": "Completed",
            }
        ]

        tab = ReceptionHistoryTab(mgr)
        tab.date_from.setDate(tab.date_from.date().addYears(-1))
        tab.date_to.setDate(tab.date_to.date().addYears(1))
        tab.load_data()

        self.assertTrue(hasattr(tab, "btn_new_direct_bl"))
        self.assertEqual(tab.table.rowCount(), 1)
        self.assertEqual(tab.table.item(0, 8).text(), "Direct (Sans BC)")

        with patch("ui.widgets.procurement.reception_history_tab.ReceptionDialog") as mock_dlg_cls:
            mock_dlg = MagicMock()
            mock_dlg.exec.return_value = 0
            mock_dlg.br_id = None
            mock_dlg_cls.return_value = mock_dlg

            tab.btn_new_direct_bl.click()
            mock_dlg_cls.assert_called_once()
            _, kwargs = mock_dlg_cls.call_args
            self.assertIsNone(kwargs["po_data"]["PO_ID"])
            self.assertIs(kwargs["manager"], mgr)

        tab.deleteLater()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
