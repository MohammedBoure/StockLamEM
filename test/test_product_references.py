# -*- coding: utf-8 -*-
"""
test/test_product_references.py
===============================
Unit tests for the Product_References (Réf) feature:
1. Permission `tab_data_references` registered in SYSTEM_PERMISSIONS, schema_initializer,
   and navigation_permissions, and controllable in UserDialog.
2. ProductReferenceManager validation & uniqueness / primary rules.
3. ProductReferencesTab displays & filters Réf rows linked to products.
4. OrderDeskWidget prioritizes `Primary_Ref` over `Barcode` in the Réf column.
"""

import os
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from database.base.schema_initializer import _ALL_PERMISSIONS
from database.product_reference_manager import ProductReferenceManager
from ui.navigation_permissions import NAVIGATION_PERMISSION_FALLBACKS, has_navigation_permission, has_permission
from ui.widgets.appliance_desks.order_desk_view import OrderDeskWidget
from ui.widgets.master_data.product_references_tab import ProductReferencesTab
from ui.widgets.users.user_management_tab import SYSTEM_PERMISSIONS, UserDialog


class TestProductReferencesFeature(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["PYTEST_CURRENT_TEST"] = "1"
        cls.app = QApplication.instance() or QApplication([])

    def test_permission_registered_and_controllable_in_user_dialog(self):
        self.assertIn("tab_data_references", SYSTEM_PERMISSIONS["2. DONNEES_DE_BASE"]["perms"])
        self.assertIn("tab_data_references", _ALL_PERMISSIONS)
        self.assertIn("tab_data_references", NAVIGATION_PERMISSION_FALLBACKS["nav_data"])
        self.assertTrue(
            has_navigation_permission({"Permissions": {"tab_data_references": True}}, "nav_data")
        )

        dlg = UserDialog()
        try:
            dlg.role_combo.setCurrentText("Administrateur")
            self.assertTrue(dlg.get_selected_permissions().get("tab_data_references"))

            # Uncheck tab_data_references explicitly
            for i in range(dlg.tree_perms.topLevelItemCount()):
                grp = dlg.tree_perms.topLevelItem(i)
                for j in range(grp.childCount()):
                    child = grp.child(j)
                    if child.data(0, Qt.UserRole) == "tab_data_references":
                        child.setCheckState(0, Qt.Unchecked)

            perms = dlg.get_selected_permissions()
            self.assertIn("tab_data_references", perms)
            self.assertFalse(perms["tab_data_references"])
            self.assertFalse(has_permission({"Role": "Admin", "Permissions": perms}, "tab_data_references"))
        finally:
            dlg.close()

    def test_manager_normalize_and_duplicate_guard(self):
        self.assertEqual(ProductReferenceManager.normalize_ref_code("  REF-001  "), "REF-001")
        with self.assertRaises(ValueError):
            ProductReferenceManager.normalize_ref_code("   ")
        with self.assertRaises(ValueError):
            ProductReferenceManager.normalize_ref_code("X" * 101)

        fake_cursor = MagicMock()
        fake_cursor.fetchone.side_effect = [
            {"cnt": 1},  # _ensure_table count
            {"Ref_ID": 5, "Product_Name": "TV 55"},  # duplicate check inside add_reference
        ]
        fake_conn = MagicMock()
        fake_conn.cursor.return_value = fake_cursor

        fake_db = MagicMock()

        @contextmanager
        def _ctx():
            yield fake_conn

        fake_db.get_db_connection = _ctx
        ProductReferenceManager._schema_checked = False
        mgr = ProductReferenceManager(fake_db)
        with self.assertRaises(ValueError):
            mgr.add_reference(product_id=10, ref_code="REF-DUP")

    def test_references_tab_lists_and_filters_refs(self):
        dm = MagicMock()
        dm.product_refs.get_all_references.return_value = [
            {
                "Ref_ID": 1,
                "Product_ID": 10,
                "Ref_Code": "KGN39VLEB",
                "Product_Name": "Réfrigérateur Bosch",
                "Brand_Mark": "Bosch",
                "Is_Primary": True,
                "Notes": "Réf fabricant",
            },
            {
                "Ref_ID": 2,
                "Product_ID": 10,
                "Ref_Code": "SUP-BOSCH-99",
                "Product_Name": "Réfrigérateur Bosch",
                "Brand_Mark": "Bosch",
                "Is_Primary": False,
                "Notes": "Réf fournisseur",
            },
        ]
        tab = ProductReferencesTab(dm)
        try:
            self.assertEqual(tab.table.rowCount(), 2)
            self.assertEqual(tab.table.item(0, 1).text(), "KGN39VLEB")
            self.assertEqual(tab.table.item(0, 4).text(), "Principale")

            tab.txt_search.setText("SUP-BOSCH")
            self.assertEqual(tab.table.rowCount(), 1)
            self.assertEqual(tab.table.item(0, 1).text(), "SUP-BOSCH-99")
        finally:
            tab.deleteLater()

    def test_order_desk_displays_primary_ref_instead_of_barcode(self):
        dm = MagicMock()
        dm.manufacturers.get_all_manufacturers.return_value = []
        dm.families.get_all_families.return_value = []
        dm.colors.get_all_colors.return_value = []
        dm.clients.get_all_clients.return_value = []
        dm.serials.get_catalog_with_theoretical_stock.return_value = [
            {
                "Product_ID": 1,
                "Brand_Mark": "Bosch",
                "Product_Name": "Réfrigérateur 400L",
                "Category_Name": "Froid",
                "Barcode": "6130000000012",
                "Primary_Ref": "KGN39VLEB",
                "All_Refs": "KGN39VLEB | SUP-99",
                "Color_Finish": "Inox",
                "Physical_Stock_Qty": 5,
                "Available_Theoretical_Qty": 5,
                "Unit_Price_TTC": 65000.0,
            }
        ]
        widget = OrderDeskWidget(dm)
        try:
            self.assertEqual(widget.table.rowCount(), 1)
            self.assertEqual(widget.table.item(0, 3).text(), "KGN39VLEB")
            self.assertIn("SUP-99", widget.table.item(0, 3).toolTip())
        finally:
            widget.deleteLater()


if __name__ == "__main__":
    unittest.main()
