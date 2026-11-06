# -*- coding: utf-8 -*-
"""
test/test_order_desk_filter_bar_simplification.py
=================================================
Automated unit tests for Task #6:
1. 'FILTRES' text badge removed from taking horizontal line space.
2. Product count / stock info ('276 produits trouvés (4246 en stock)') removed from the filter bar line.
3. Redundant 'Toutes' button next to the color combobox removed.
4. 'Disponibles uniquement' text simplified and shortened to 'En stock'.
5. 'Actualiser' and 'Réinitialiser' buttons replaced by compact icon-only buttons.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QFrame

from ui.widgets.appliance_desks.order_desk_view import OrderDeskWidget


class TestOrderDeskFilterBarSimplification(unittest.TestCase):
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
                "Brand_Mark": "Bosch",
                "Product_Name": "Réfrigérateur NoFrost",
                "Category_Name": "Froid",
                "Color_Finish": "Inox",
                "Available_Theoretical_Qty": 10,
                "Unit_Price_TTC": 95000.0,
            }
        ]
        self.desk = OrderDeskWidget(data_manager=self.mock_dm)

    def tearDown(self):
        self.desk.deleteLater()
        self.app.processEvents()

    def test_no_filter_text_badge_taking_line_space(self):
        """Verifies that the word 'FILTRES' does not take horizontal space on the filter line."""
        filter_bar = self.desk.findChild(QFrame, "OrderTopFilterBar")
        self.assertIsNotNone(filter_bar)

        # Check all child QLabels in filter_bar: none of visible ones should say 'FILTRES'
        for lbl in filter_bar.findChildren(QLabel):
            if lbl.isVisibleTo(filter_bar):
                self.assertNotEqual(lbl.text().strip().upper(), "FILTRES")

    def test_no_catalog_count_badge_on_filter_line(self):
        """Verifies that the product count information is completely removed from the filter bar line."""
        # lbl_catalog_count_badge must not be visible on the filter line
        filter_bar = self.desk.findChild(QFrame, "OrderTopFilterBar")
        self.assertFalse(self.desk.lbl_catalog_count_badge.isVisibleTo(filter_bar))

        # Bottom summary bar remains responsible for metrics display
        self.assertIsNotNone(self.desk.catalog_bottom_bar)
        self.assertTrue(hasattr(self.desk, "lbl_total_quantity"))
        self.assertTrue(hasattr(self.desk, "lbl_total_value"))
        self.assertTrue(hasattr(self.desk, "lbl_count_info"))

    def test_no_toutes_button_next_to_color_filter(self):
        """Verifies that the redundant 'Toutes' button next to the color combobox is removed."""
        filter_bar = self.desk.findChild(QFrame, "OrderTopFilterBar")
        self.assertFalse(self.desk.color_preview_badge.isVisibleTo(filter_bar))

        # Color combo is directly accessible
        self.assertIsNotNone(self.desk.cbo_color)
        self.assertTrue(self.desk.cbo_color.isVisibleTo(filter_bar))

    def test_disponibles_uniquement_simplified_to_en_stock(self):
        """Verifies that 'Disponibles uniquement' is shortened and simplified to 'En stock'."""
        self.assertEqual(self.desk.chk_available_only.text(), "En stock")
        self.assertTrue(self.desk.chk_available_only.isChecked())
        self.assertIn("stock", self.desk.chk_available_only.toolTip().lower())

    def test_actualiser_and_reinitialiser_are_icon_only_buttons(self):
        """Verifies that 'Actualiser' and 'Réinitialiser' have no text and are compact icon buttons."""
        self.assertTrue(hasattr(self.desk, "btn_reset"))
        self.assertTrue(hasattr(self.desk, "btn_refresh"))

        # 1. Reset button: empty text, valid icon, compact size <= 36px
        self.assertEqual(self.desk.btn_reset.text(), "")
        self.assertFalse(self.desk.btn_reset.icon().isNull())
        self.assertLessEqual(self.desk.btn_reset.width(), 36)
        self.assertIn("réinitialiser", self.desk.btn_reset.toolTip().lower())

        # 2. Refresh button: empty text, valid icon, compact size <= 36px
        self.assertEqual(self.desk.btn_refresh.text(), "")
        self.assertFalse(self.desk.btn_refresh.icon().isNull())
        self.assertLessEqual(self.desk.btn_refresh.width(), 36)
        self.assertIn("actualiser", self.desk.btn_refresh.toolTip().lower())


if __name__ == "__main__":
    unittest.main()
