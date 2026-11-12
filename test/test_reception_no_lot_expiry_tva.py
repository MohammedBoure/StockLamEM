# -*- coding: utf-8 -*-
"""
test/test_reception_no_lot_expiry_tva.py
========================================
Unit tests for Task #2 (Achats & Entrées -> Bons de Réceptions):
1. Lot and Expiry Date inputs & columns are hidden and optional (auto-handled).
2. TVA checkbox, summary label, and table column are hidden and defaulted to 0%.
3. ReceptionHistoryTab hides the Total TVA column.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from ui.widgets.procurement.reception_dialog.reception_dialog import ReceptionDialog
from ui.widgets.procurement.reception_history_tab import ReceptionHistoryTab


class TestReceptionNoLotExpiryTVA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["PYTEST_CURRENT_TEST"] = "1"
        cls.app = QApplication.instance() or QApplication([])

    def test_reception_dialog_hides_lot_expiry_and_tva(self):
        mock_mgr = MagicMock()
        mock_mgr.products.get_all_products.return_value = [
            {"Product_ID": 10, "Product_Name": "Réfrigérateur 400L", "Base_Unit_Name": "U"}
        ]
        mock_mgr.locations = MagicMock()
        mock_mgr.reception = MagicMock()

        dlg = ReceptionDialog(
            po_data={"PO_ID": 1, "Supplier_Name": "Fournisseur Test", "Supplier_ID": 1},
            locations_list=[],
            location_manager=mock_mgr.locations,
            manager=mock_mgr,
            printer_manager=MagicMock(),
        )

        # Inputs hidden and TVA unchecked by default
        self.assertTrue(dlg.inp_lot.isHidden())
        self.assertTrue(dlg.inp_expiry.isHidden())
        self.assertTrue(dlg.chk_tva.isHidden())
        self.assertFalse(dlg.chk_tva.isChecked())
        self.assertTrue(dlg.lbl_total_tva.isHidden())

        # Table columns hidden: 5 (Lot), 6 (Date Exp), 11 (TVA), 12 (P.U TTC)
        self.assertTrue(dlg.table_items.isColumnHidden(5))
        self.assertTrue(dlg.table_items.isColumnHidden(6))
        self.assertTrue(dlg.table_items.isColumnHidden(11))
        self.assertTrue(dlg.table_items.isColumnHidden(12))

        dlg.deleteLater()
        self.app.processEvents()

    def test_add_item_without_lot_expiry_or_tva_succeeds(self):
        mock_mgr = MagicMock()
        mock_mgr.products.get_all_products.return_value = []
        mock_mgr.locations = MagicMock()
        mock_mgr.reception = MagicMock()
        mock_mgr.reception.add_reception_line.return_value = (True, "OK")

        dlg = ReceptionDialog(
            po_data={"PO_ID": 1, "Supplier_Name": "Fournisseur Test", "Supplier_ID": 1},
            locations_list=[],
            location_manager=mock_mgr.locations,
            manager=mock_mgr,
            printer_manager=MagicMock(),
        )
        dlg.br_id = 55
        dlg.load_items_from_db = MagicMock()

        prod_data = {"Product_ID": 10, "Product_Name": "Cuisinière 5 Feux", "Stock_Unit": "U"}
        dlg.cb_product.addItem("Cuisinière 5 Feux", prod_data)
        dlg.cb_product.setCurrentIndex(dlg.cb_product.count() - 1)
        dlg.inp_qty.setValue(3)
        dlg.inp_price.setValue(45000.0)
        dlg.inp_lot.setText("")  # Explicitly empty

        with patch.object(dlg.cb_location, "get_current_location_id", return_value=2):
            dlg.add_item_to_table()

        self.assertTrue(mock_mgr.reception.add_reception_line.called)
        payload = mock_mgr.reception.add_reception_line.call_args[0][0]
        self.assertTrue(payload["Lot_Number"].startswith("LOT-"))
        self.assertIsNone(payload["Expiry_Date"])
        self.assertEqual(payload["Tax_Rate_Percent"], 0.0)

        dlg.deleteLater()
        self.app.processEvents()

    def test_reception_history_tab_hides_tva_column(self):
        mock_dm = MagicMock()
        mock_dm.reception.get_all_receptions.return_value = []
        tab = ReceptionHistoryTab(mock_dm)
        self.assertTrue(tab.table.isColumnHidden(5))
        tab.deleteLater()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
