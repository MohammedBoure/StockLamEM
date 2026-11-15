# -*- coding: utf-8 -*-
"""
test/test_product_references.py
===============================
Regression tests for Task #1 (Données de Base - Marque & Single Product Réf):
1. `Fabricants` renamed to `Marque` across permissions, Master Data UI labels, and MainWindow tabs.
2. `Références` tab (`tab_data_references`), `ProductReferencesTab`, and `ProductReferenceManager` removed.
3. Each product directly holds one single unique Réf (`Manuf_Cat_No`) validated in ProductManager,
   editable in ProductDialog, visible in ProductsTab, and used by OrderDeskWidget.
"""

import os
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import LabDataManager
from database.base.schema_initializer import _ALL_PERMISSIONS
from database.product_manager import ProductManager
from ui.navigation_permissions import NAVIGATION_PERMISSION_FALLBACKS
from ui.widgets.appliance_desks.order_desk_view import OrderDeskWidget
from ui.widgets.master_data.dialogs import ProductDialog
from ui.widgets.master_data.manufacturers_tab import ManufacturersTab
from ui.widgets.master_data.master_data_tabs import MasterDataTabs
from ui.widgets.master_data.products_tab import ProductsTab
from ui.widgets.users.user_management_tab import SYSTEM_PERMISSIONS, UserDialog


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestSingleProductRefAndMarque(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["PYTEST_CURRENT_TEST"] = "1"
        cls.app = QApplication.instance() or QApplication([])

    def test_marque_renamed_and_references_tab_removed(self):
        perms_map = SYSTEM_PERMISSIONS["2. DONNEES_DE_BASE"]["perms"]
        self.assertEqual(perms_map["tab_data_manufacturers"], "Marque")
        self.assertNotIn("tab_data_references", perms_map)
        self.assertNotIn("tab_data_references", _ALL_PERMISSIONS)
        self.assertNotIn("tab_data_references", NAVIGATION_PERMISSION_FALLBACKS["nav_data"])

        self.assertFalse((PROJECT_ROOT / "ui" / "widgets" / "master_data" / "product_references_tab.py").exists())
        self.assertFalse((PROJECT_ROOT / "database" / "product_reference_manager.py").exists())

        main_window_src = (PROJECT_ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn('addTab(widget.tab_manufacturers, "Marque")', main_window_src)
        self.assertNotIn("tab_data_references", main_window_src)
        self.assertNotIn("tab_references", main_window_src)

        dlg = UserDialog()
        try:
            dlg.role_combo.setCurrentText("Administrateur")
            selected = dlg.get_selected_permissions()
            self.assertNotIn("tab_data_references", selected)
            self.assertTrue(selected.get("tab_data_manufacturers"))
        finally:
            dlg.close()

    def test_master_data_tabs_and_marque_labels(self):
        dm = MagicMock()
        dm.manufacturers.get_all_manufacturers.return_value = [
            {"Manuf_ID": 1, "Manuf_Name": "Bosch", "Country": "Allemagne", "Website": "https://bosch.com"}
        ]
        dm.products.search_products.return_value = []
        dm.automates.get_all_automates.return_value = []
        dm.families.get_all_families.return_value = []
        dm.packaging_units.get_all_units.return_value = []
        dm.suppliers.get_all_suppliers.return_value = []
        dm.partners.get_all_partners.return_value = []
        dm.locations.get_all_locations.return_value = []
        dm.waste_reasons.get_all_reasons.return_value = []
        dm.pos_terminals.get_all_pos.return_value = []
        dm.colors.get_all_colors.return_value = []

        tab_manuf = ManufacturersTab(dm.manufacturers)
        try:
            self.assertEqual(tab_manuf.search_input.placeholderText(), "Rechercher une marque...")
            headers = [
                tab_manuf.table.horizontalHeaderItem(i).text()
                for i in range(tab_manuf.table.columnCount())
            ]
            self.assertEqual(headers[1], "Nom de la Marque")
        finally:
            tab_manuf.deleteLater()

        with patch.object(QMessageBox, "critical"), patch.object(QMessageBox, "warning"), patch.object(QMessageBox, "information"):
            master = MasterDataTabs(dm)
            try:
                self.assertFalse(hasattr(master, "tab_references"))
                self.assertTrue(hasattr(master, "tab_manufacturers"))
            finally:
                master.deleteLater()

        db_init_src = (PROJECT_ROOT / "database" / "__init__.py").read_text(encoding="utf-8")
        self.assertNotIn("ProductReferenceManager", db_init_src)
        self.assertNotIn("product_refs", db_init_src)
        self.assertFalse(hasattr(LabDataManager, "product_refs"))

    def test_product_manager_single_ref_normalization_and_uniqueness(self):
        self.assertEqual(ProductManager.normalize_ref_code("  REF-001  "), "REF-001")
        self.assertIsNone(ProductManager.normalize_ref_code("   ", allow_empty=True))
        with self.assertRaises(ValueError):
            ProductManager.normalize_ref_code("   ", allow_empty=False)
        with self.assertRaises(ValueError):
            ProductManager.normalize_ref_code("X" * 101)

        fake_cursor = MagicMock()
        fake_cursor.fetchone.return_value = {"Product_ID": 5, "Product_Name": "TV 55"}
        fake_conn = MagicMock()
        fake_conn.cursor.return_value = fake_cursor
        fake_db = MagicMock()

        @contextmanager
        def _ctx():
            yield fake_conn

        fake_db.get_db_connection = _ctx
        mgr = ProductManager(fake_db)
        with self.assertRaises(ValueError):
            mgr.set_product_ref(product_id=10, ref_code="REF-DUP")

    def test_product_dialog_and_tab_handle_single_ref(self):
        manufacturers = [{"Manuf_ID": 1, "Manuf_Name": "Bosch"}]
        automates = []
        families = [{"Family_ID": 2, "Family_Name": "Froid"}]
        units = [{"Unit_Name": "Unité"}]

        dlg = ProductDialog(
            manufacturers,
            automates,
            families,
            units,
            data={
                "Product_ID": 10,
                "Product_Name": "Réfrigérateur Bosch",
                "Manuf_Cat_No": "KGN39VLEB",
                "Family_ID": 2,
                "Manuf_ID": 1,
            },
        )
        try:
            self.assertEqual(dlg.ref_input.text(), "KGN39VLEB")
            dlg.ref_input.setText("KGN49AIAT")
            payload = dlg.get_data()
            self.assertEqual(payload["Manuf_Cat_No"], "KGN49AIAT")
        finally:
            dlg.close()

        dm = MagicMock()
        dm.automates.get_all_automates.return_value = []
        dm.products.search_products.return_value = [
            {
                "Product_ID": 10,
                "Product_Name": "Réfrigérateur Bosch",
                "Primary_Ref": "KGN39VLEB",
                "Manuf_Cat_No": "KGN39VLEB",
                "Family_Name": "Froid",
                "Manuf_Name": "Bosch",
                "Stock_Unit": "Unité",
                "Ordering_Unit": "Unité",
                "Minimum_Stock_Level": 2,
                "Storage_Temp_Req": "Sec",
                "Preferred_Automate_ID": None,
                "Show_In_Alerts": False,
                "POS_Priority_Group": None,
            }
        ]
        tab = ProductsTab(dm)
        try:
            self.assertEqual(tab.table.horizontalHeaderItem(2).text(), "Réf")
            self.assertEqual(tab.table.item(0, 2).text(), "KGN39VLEB")
        finally:
            tab.deleteLater()

    def test_order_desk_displays_single_primary_ref(self):
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
                "All_Refs": "KGN39VLEB",
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
        finally:
            widget.deleteLater()


if __name__ == "__main__":
    unittest.main()
