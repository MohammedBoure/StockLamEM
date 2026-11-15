"""Targeted tests for Stock Actuel Réf column and QuickAddDialog Réf selector + '+' button."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ui.widgets.inventory.tabs_batches import BatchesTab
from ui.widgets.inventory.tabs_batches.quick_add_dialog import QuickAddDialog
from database.inventory_batch_manager import InventoryBatchManager


def _get_qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_mock_manager():
    mgr = MagicMock()
    mgr.batches = MagicMock()
    mgr.products = MagicMock()
    mgr.locations = MagicMock()
    mgr.locations.get_all_locations.return_value = [
        {"Location_ID": 1, "Location_Name": "Magasin A", "Parent_ID": None}
    ]
    mgr.locations.get_location_hierarchy.return_value = [
        {"Location_ID": 1, "Location_Name": "Magasin A", "Parent_ID": None}
    ]
    mgr.colors = MagicMock()
    mgr.colors.get_all_colors.return_value = []
    mgr.db = MagicMock()
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    conn.cursor.return_value = cursor
    mgr.db.get_raw_connection.return_value = conn

    mgr.products.get_all_products.return_value = [
        {
            "Product_ID": 10,
            "Product_Name": "Lampe LED 12W",
            "Manuf_Name": "Philips",
            "Manuf_Cat_No": "REF-A1",
            "Primary_Ref": "REF-A1",
            "All_Refs": "REF-A1",
            "Base_Unit_Name": "Unité",
            "Default_Selling_Price_HT": 1500.0,
        },
        {
            "Product_ID": 20,
            "Product_Name": "Spot Encastrable",
            "Manuf_Name": "Osram",
            "Manuf_Cat_No": "",
            "Primary_Ref": "",
            "All_Refs": "",
            "Base_Unit_Name": "Unité",
            "Default_Selling_Price_HT": 800.0,
        },
    ]

    single_refs = {10: "REF-A1", 20: ""}

    def _set_ref(pid, code):
        clean = str(code or "").strip()
        if not clean:
            raise ValueError("Réf vide")
        for other_pid, other_code in single_refs.items():
            if other_pid != pid and other_code == clean:
                raise ValueError("Réf déjà utilisée")
        single_refs[pid] = clean
        return clean

    mgr.products.set_product_ref.side_effect = _set_ref

    mgr.batches.get_all_batches_with_details.return_value = [
        {
            "Batch_ID": 1,
            "Product_ID": 10,
            "Product_Name": "Lampe LED 12W",
            "Quantity_Current": 5,
            "Quantity_Initial": 5,
            "Stock_Unit": "Unité",
            "Unit_Price_Received": 1000.0,
            "Selling_Price_HT": 1500.0,
            "Lot_Number": "LOT-01",
            "Internal_Barcode": "2000000000011",
            "Location_ID": 1,
            "Location_Name": "Magasin A",
            "Family_Name": "Éclairage",
            "Manuf_Name": "Philips",
            "Supplier_Name": "Fournisseur X",
            "Ref_Code": "REF-A2",
            "Primary_Ref": "REF-A1",
            "All_Refs": "REF-A1 | REF-A2",
            "Created_At": "2026-11-13",
        }
    ]
    return mgr


class TestStockActuelRefAndQuickAdd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = _get_qapp()

    def test_stock_actuel_displays_ref_column_and_filters_by_ref(self):
        mgr = _make_mock_manager()
        tab = BatchesTab(mgr)
        tab.load_data()

        headers = [tab.table.horizontalHeaderItem(i).text() for i in range(tab.table.columnCount())]
        self.assertEqual(headers[24], "Réf")
        self.assertEqual(tab.table.rowCount(), 1)
        self.assertEqual(tab.table.item(0, 24).text(), "REF-A2")
        self.assertIn("REF-A1 | REF-A2", tab.table.item(0, 24).toolTip())

        tab.search_input.setText("REF-A2")
        tab.apply_filters_local()
        self.assertEqual(tab.table.rowCount(), 1)

        tab.search_input.setText("REF-NOT-FOUND")
        tab.apply_filters_local()
        self.assertEqual(tab.table.rowCount(), 0)
        tab.close()

    def test_quick_add_ref_dropdown_and_plus_button(self):
        mgr = _make_mock_manager()
        dlg = QuickAddDialog(mgr)

        self.assertFalse(dlg.cb_ref.isEnabled())
        self.assertFalse(dlg.btn_add_ref.isEnabled())

        # Select product 10 (has single Réf REF-A1)
        dlg.cb_product.setCurrentIndex(1)
        self.assertTrue(dlg.cb_ref.isEnabled())
        self.assertTrue(dlg.btn_add_ref.isEnabled())
        self.assertEqual(dlg.cb_ref.count(), 1)
        self.assertEqual(dlg.cb_ref.itemData(0), "REF-A1")
        self.assertEqual(dlg.get_data()["Ref_Code"], "REF-A1")

        # Click '+' to update the single Réf on product 10
        with patch(
            "ui.widgets.inventory.tabs_batches.quick_add_dialog.QInputDialog.getText",
            return_value=("REF-NEW-99", True),
        ):
            dlg.btn_add_ref.click()

        mgr.products.set_product_ref.assert_called_once_with(10, "REF-NEW-99")
        self.assertEqual(dlg.cb_ref.count(), 1)
        self.assertEqual(dlg.cb_ref.currentData(), "REF-NEW-99")
        self.assertEqual(dlg.get_data()["Ref_Code"], "REF-NEW-99")
        dlg.close()

    def test_quick_add_prefills_existing_ref_on_edit(self):
        mgr = _make_mock_manager()
        dlg = QuickAddDialog(
            mgr,
            batch_data={
                "Product_ID": 10,
                "Location_ID": 1,
                "Quantity_Initial": 4,
                "Lot_Number": "LOT-9",
                "Ref_Code": "REF-A2",
            },
        )
        self.assertEqual(dlg.cb_ref.currentData(), "REF-A2")
        dlg.close()

    def test_batch_manager_persists_ref_code_on_add_and_update(self):
        db = MagicMock()
        conn = MagicMock()
        cursor = MagicMock()
        cursor.lastrowid = 55
        cursor.fetchone.side_effect = [
            ("BL_Number",),   # add: SHOW COLUMNS BL_Number
            ("Ref_Code",),    # add: SHOW COLUMNS Ref_Code
            None,             # add: SELECT Barcode
            ("BL_Number",),   # update: SHOW COLUMNS BL_Number
            ("Ref_Code",),    # update: SHOW COLUMNS Ref_Code
            None,             # update: SELECT Barcode
        ]
        conn.cursor.return_value = cursor
        db.get_raw_connection.return_value = conn

        ib_mgr = InventoryBatchManager(db)
        ib_mgr.generate_ean13_for_batch = MagicMock(return_value="2000000000557")

        ok_add = ib_mgr.add_direct_batch({
            "Product_ID": 10,
            "Location_ID": 1,
            "Lot_Number": "LOT-55",
            "Expiry_Date": None,
            "Quantity": 3,
            "Unit_Price_HT": 100.0,
            "BL_Number": "BL-1",
            "Ref_Code": "REF-A2",
        }, user_id=1)
        self.assertTrue(ok_add)

        executed_sqls = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertTrue(any("UPDATE Inventory_Batches SET Ref_Code = %s WHERE Batch_ID = %s" in s for s in executed_sqls))

        ok_upd = ib_mgr.update_direct_batch(55, {
            "Product_ID": 10,
            "Location_ID": 1,
            "Lot_Number": "LOT-55",
            "Expiry_Date": None,
            "Quantity": 3,
            "Unit_Price_HT": 100.0,
            "BL_Number": "BL-1",
            "Ref_Code": "REF-A1",
        }, user_id=1)
        self.assertTrue(ok_upd)


if __name__ == "__main__":
    unittest.main()
