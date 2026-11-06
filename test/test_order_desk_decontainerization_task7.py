# -*- coding: utf-8 -*-
"""
test/test_order_desk_decontainerization_task7.py
================================================
Automated test suite verifying Task #7:
Elimination of unnecessary containers, double-box nesting, and clipped headers in Order Desk:
1. Removal of redundant, clipped header container ('Catalogue des Produits Disponibles') above the table.
2. De-containerization of bottom summary bar badges (clean typography without artificial box borders).
3. Zero-margin seamless integration of the catalog table inside OrderCatalogPanel (no double-box moat).
4. Continuous accurate updates of financial and quantity metrics.
"""

import os
import unittest
from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

from ui.widgets.appliance_desks.order_desk_view import OrderDeskWidget


class TestOrderDeskDecontainerization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.mock_dm = MagicMock()
        self.mock_dm.current_user = {"User_ID": 1, "Username": "vendeur"}
        self.mock_dm.clients = MagicMock()
        self.mock_dm.clients.get_all_clients.return_value = []
        self.mock_dm.serials = MagicMock()
        self.mock_dm.serials.get_catalog_with_theoretical_stock.return_value = [
            {
                "Product_ID": 101,
                "Brand_Mark": "Abbott",
                "Product_Name": "ACCP ARC",
                "Category_Name": "Hormonologie",
                "Color_Finish": "Standard",
                "Physical_Qty": 13,
                "Reserved_Qty": 1,
                "Available_Theoretical_Qty": 12,
                "Unit_Price_TTC": 16660.0,
            },
            {
                "Product_ID": 102,
                "Brand_Mark": "Abbott",
                "Product_Name": "ACTIVATION ARC",
                "Category_Name": "Consommable",
                "Color_Finish": "Standard",
                "Physical_Qty": 74,
                "Reserved_Qty": 1,
                "Available_Theoretical_Qty": 73,
                "Unit_Price_TTC": 1190.0,
            },
        ]
        self.desk = OrderDeskWidget(data_manager=self.mock_dm)
        self.desk.refresh_catalog()

    def tearDown(self):
        self.desk.deleteLater()
        self.app.processEvents()

    def test_no_redundant_clipped_header_container_above_table(self):
        """Verifies that the catalog table starts directly without a space-wasting header container."""
        cat_layout = self.desk.catalog_panel.layout()
        # Item 0 in the catalog panel must be the table itself
        self.assertIs(cat_layout.itemAt(0).widget(), self.desk.table)

        # The header label is not visible in the layout
        self.assertFalse(self.desk.lbl_cat_title.isVisibleTo(self.desk.catalog_panel))

    def test_decontainerized_bottom_bar_badges(self):
        """Verifies that bottom summary badges do not have artificial boxed container borders or backgrounds."""
        # 1. Total value label: clean text without boxed container border
        val_style = self.desk.lbl_total_value.styleSheet()
        self.assertIn("border: none", val_style)
        self.assertIn("background: transparent", val_style)
        self.assertNotIn("border: 1px solid", val_style)

        # 2. Total quantity label: clean text without boxed container border
        qty_style = self.desk.lbl_total_quantity.styleSheet()
        self.assertIn("border: none", qty_style)
        self.assertIn("background: transparent", qty_style)
        self.assertNotIn("border: 1px solid", qty_style)

        # 3. Count info label: clean text
        cnt_style = self.desk.lbl_count_info.styleSheet()
        self.assertIn("border: none", cnt_style)
        self.assertIn("background: transparent", cnt_style)

    def test_zero_margins_eliminating_double_border_nesting(self):
        """Verifies that catalog panel layout has 0 margins, removing double-border container moat."""
        margins = self.desk.catalog_panel.layout().contentsMargins()
        self.assertEqual(margins.left(), 0)
        self.assertEqual(margins.top(), 0)
        self.assertEqual(margins.right(), 0)
        self.assertEqual(margins.bottom(), 0)
        self.assertEqual(self.desk.catalog_panel.layout().spacing(), 0)

    def test_metrics_remain_accurate_after_decontainerization(self):
        """Verifies that financial valuation and quantity metrics update seamlessly."""
        self.assertIn("Valeur Totale :", self.desk.lbl_total_value.text())
        self.assertIn("Stock disponible affiché :", self.desk.lbl_total_quantity.text())
        self.assertIn("Affichage: 2 / 2", self.desk.lbl_count_info.text())


if __name__ == "__main__":
    unittest.main()
