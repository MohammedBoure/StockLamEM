# -*- coding: utf-8 -*-
"""
test/test_order_desk_ref_and_stock_only.py
==========================================
Unit tests for Task #9 (Bureaux -> 1. Commandes):
1. Out-of-stock products (physical <= 0 or available <= 0) are strictly hidden, and chk_available_only is hidden.
2. lbl_total_value (Valeur Totale) is hidden.
3. Both catalog table (col 3) and cart table (col 1) display 'Réf' instead of 'Couleur'.
"""

import os
import unittest
from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication

from ui.widgets.appliance_desks.order_desk_view import OrderDeskWidget


class TestOrderDeskRefAndStockOnly(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["PYTEST_CURRENT_TEST"] = "1"
        cls.app = QApplication.instance() or QApplication([])

    def _make_mock_data_manager(self):
        dm = MagicMock()
        dm.manufacturers.get_all_manufacturers.return_value = []
        dm.families.get_all_families.return_value = []
        dm.colors.get_all_colors.return_value = []
        dm.clients.get_all_clients.return_value = []
        dm.serials.get_catalog_with_theoretical_stock.return_value = [
            {
                "Product_ID": 1,
                "Brand_Mark": "Condor",
                "Product_Name": "Réfrigérateur 400L",
                "Category_Name": "Froid",
                "Barcode": "REF-CND-400",
                "Color_Finish": "Inox",
                "Physical_Stock_Qty": 5,
                "Available_Theoretical_Qty": 5,
                "Unit_Price_TTC": 65000.0,
            },
            {
                "Product_ID": 2,
                "Brand_Mark": "BrandX",
                "Product_Name": "Produit Épuisé Dispo",
                "Category_Name": "Froid",
                "Barcode": "REF-ZERO-AVAIL",
                "Color_Finish": "Blanc",
                "Physical_Stock_Qty": 2,
                "Available_Theoretical_Qty": 0,
                "Unit_Price_TTC": 20000.0,
            },
            {
                "Product_ID": 3,
                "Brand_Mark": "BrandY",
                "Product_Name": "Produit Épuisé Phys",
                "Category_Name": "Froid",
                "Barcode": "REF-ZERO-PHYS",
                "Color_Finish": "Noir",
                "Physical_Stock_Qty": 0,
                "Available_Theoretical_Qty": 3,
                "Unit_Price_TTC": 25000.0,
            },
        ]
        return dm

    def test_order_desk_hides_out_of_stock_and_total_value_and_shows_ref(self):
        dm = self._make_mock_data_manager()
        widget = OrderDeskWidget(dm)
        widget.refresh_catalog()

        # 1) Filter checkbox and total value label hidden
        self.assertTrue(widget.chk_available_only.isHidden())
        self.assertTrue(widget.lbl_total_value.isHidden())

        # 2) Only the in-stock product (both phys > 0 and avail > 0) is shown
        self.assertEqual(widget.table.rowCount(), 1)
        self.assertEqual(widget.table.horizontalHeaderItem(3).text(), "Réf")
        self.assertEqual(widget.table.item(0, 3).text(), "REF-CND-400")
        self.assertIsNone(widget.table.cellWidget(0, 3))

        # 3) Add to cart and verify cart_table col 1 header & cell show Réf
        prod = widget._catalog_filtered_items[0]
        widget._add_product_to_session(widget._active_session_id, prod)

        self.assertEqual(widget.cart_table.rowCount(), 1)
        self.assertEqual(widget.cart_table.horizontalHeaderItem(1).text(), "Réf")
        self.assertEqual(widget.cart_table.item(0, 1).text(), "REF-CND-400")
        self.assertIsNone(widget.cart_table.cellWidget(0, 1))

        widget.deleteLater()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
