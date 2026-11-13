# -*- coding: utf-8 -*-
"""
test/test_stock_actuel_simplified.py
====================================
Unit tests for Task #5 (Stock & Magasin -> 1. Stock Actuel):
1. BatchesTab hides TVA/Prix U. HT, Date Expiration filter/column, and Automate filter/column,
   and renames Prix U. TTC to Prix d'Achat (preserved across apply_role_permissions).
2. QuickAddDialog hides Expiry Date, TVA checkboxes, and Prix TTC, defaulting Expiry_Date=None and TVA=0%.
3. ModifySalesPricesDialog hides TVA Vente and sets it to 0%.
"""

import os
import unittest
from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication

from ui.widgets.inventory.dialogs import ModifySalesPricesDialog
from ui.widgets.inventory.tabs_batches import BatchesTab
from ui.widgets.inventory.tabs_batches.quick_add_dialog import QuickAddDialog


class TestStockActuelSimplified(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["PYTEST_CURRENT_TEST"] = "1"
        cls.app = QApplication.instance() or QApplication([])

    def _make_mock_manager(self):
        mgr = MagicMock()
        mgr.families.get_all_families.return_value = []
        mgr.manufacturers.get_all_manufacturers.return_value = []
        mgr.automates.get_all_automates.return_value = []
        mgr.suppliers.get_all_suppliers.return_value = [{"Supplier_ID": 1, "Supplier_Name": "Fournisseur A"}]
        mgr.locations.get_all_locations_flat.return_value = [{"Location_ID": 1, "Location_Name": "Dépôt A"}]
        mgr.products.get_all_products.return_value = [
            {"Product_ID": 10, "Product_Name": "Lave-Linge 8KG", "Stock_Unit": "U", "Tax_Rate_Percent": 19.0, "Selling_TVA_Percent": 19.0}
        ]
        mgr.batches.get_all_batches_detailed.return_value = []
        mgr.batches.get_priority_groups_summary.return_value = []
        return mgr

    def test_batches_tab_hides_prix_ht_expiry_and_automate(self):
        mgr = self._make_mock_manager()
        tab = BatchesTab(mgr)

        self.assertTrue(tab.combo_automate.isHidden())
        self.assertTrue(tab.chk_date_filter.isHidden())
        self.assertTrue(tab.date_from.isHidden())
        self.assertTrue(tab.date_to.isHidden())

        self.assertEqual(tab.table.horizontalHeaderItem(4).text(), "Prix d'Achat")
        self.assertTrue(tab.table.isColumnHidden(3))   # Prix U. HT
        self.assertTrue(tab.table.isColumnHidden(8))   # Date Exp.
        self.assertTrue(tab.table.isColumnHidden(15))  # Automate

        # Re-applying Admin permissions must NOT unhide Prix U. HT
        tab.apply_role_permissions("Admin")
        self.assertTrue(tab.table.isColumnHidden(3))
        self.assertFalse(tab.table.isColumnHidden(4))

        tab.deleteLater()
        self.app.processEvents()

    def test_quick_add_dialog_hides_expiry_tva_and_returns_zero_tva(self):
        mgr = self._make_mock_manager()
        dlg = QuickAddDialog(mgr)

        self.assertTrue(dlg.inp_expiry.isHidden())
        self.assertTrue(dlg.chk_tva.isHidden())
        self.assertTrue(dlg.chk_sell_tva.isHidden())
        self.assertTrue(dlg.inp_price_ttc.isHidden())

        dlg.cb_product.setCurrentIndex(1)
        self.assertFalse(dlg.chk_tva.isChecked())
        self.assertFalse(dlg.chk_sell_tva.isChecked())

        dlg.cb_location.get_current_location_id = MagicMock(return_value=1)
        dlg.cb_supplier.setCurrentIndex(1)
        dlg.inp_lot.setText("LOT-01")
        dlg.inp_qty.setValue(5)
        dlg.inp_price.setValue(45000.0)
        dlg.inp_sell_price.setValue(52000.0)

        data = dlg.get_data()
        self.assertIsNone(data["Expiry_Date"])
        self.assertEqual(data["Tax_Rate_Percent"], 0.0)
        self.assertEqual(data["Selling_TVA_Percent"], 0.0)
        self.assertEqual(data["Unit_Price_HT"], 45000.0)

        dlg.deleteLater()
        self.app.processEvents()

    def test_modify_sales_prices_dialog_hides_tva(self):
        mgr = self._make_mock_manager()
        batch_data = {
            "Batch_ID": 1,
            "Product_Name": "Lave-Linge 8KG",
            "Unit_Price_Received": 45000.0,
            "Selling_Price_HT": 52000.0,
            "Selling_TVA_Percent": 19.0,
        }
        dlg = ModifySalesPricesDialog(batch_data, mgr)
        self.assertTrue(dlg.spin_tva.isHidden())
        self.assertEqual(dlg.spin_tva.value(), 0.0)

        dlg.deleteLater()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
