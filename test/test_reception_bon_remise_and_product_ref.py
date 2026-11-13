# -*- coding: utf-8 -*-
"""
test/test_reception_bon_remise_and_product_ref.py
================================================
Unit tests for Task #3 (Achats & Entrées -> Bons de Réceptions):
1. Product dropdown displays Réf (Barcode/Reference) alongside Product_Name and filters via MatchContains.
2. Per-item Remise works for both '%' and 'DZD' when adding a line.
3. Bon-level Remise Bon ('%' and 'DZD') updates totals live, loads from header, and persists via manager.
4. ReceptionLogManager._recalculate_reception_totals & update_bon_discount compute combined item + bon discounts.
"""

import os
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from database.reception_log_manager import ReceptionLogManager
from ui.widgets.procurement.reception_dialog.reception_dialog import ReceptionDialog


class TestReceptionBonRemiseAndProductRef(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["PYTEST_CURRENT_TEST"] = "1"
        cls.app = QApplication.instance() or QApplication([])

    def _make_dialog(self, products=None, reception_data=None):
        mock_mgr = MagicMock()
        mock_mgr.products.get_all_products.return_value = products or [
            {"Product_ID": 10, "Product_Name": "Cuisinière 5 Feux", "Barcode": "REF-CUI-500", "Manuf_Name": "BrandA", "Stock_Unit": "U"},
            {"Product_ID": 11, "Product_Name": "Cuisinière 5 Feux", "Barcode": "REF-CUI-900", "Manuf_Name": "BrandB", "Stock_Unit": "U"},
        ]
        mock_mgr.locations = MagicMock()
        mock_mgr.reception = MagicMock()
        mock_mgr.reception.add_reception_line.return_value = (True, "OK")
        mock_mgr.reception.get_reception_full_details.return_value = reception_data or {
            "Header": {
                "BR_ID": 77,
                "Supplier_Invoice_Ref": "FAC-77",
                "Bon_Discount_Value": 0.0,
                "Bon_Discount_Type": "%",
            },
            "Batches": [],
        }

        dlg = ReceptionDialog(
            po_data={"PO_ID": 1, "Supplier_Name": "Fournisseur Test", "Supplier_ID": 1},
            locations_list=[{"Location_ID": 1, "Location_Name": "Dépôt A"}],
            location_manager=mock_mgr.locations,
            manager=mock_mgr,
            printer_manager=MagicMock(),
            reception_data=reception_data,
        )
        return dlg, mock_mgr

    def test_product_selector_shows_ref_and_matches_contains(self):
        dlg, _ = self._make_dialog()

        items_text = [dlg.cb_product.itemText(i) for i in range(1, dlg.cb_product.count())]
        self.assertEqual(len(items_text), 2)
        self.assertIn("Cuisinière 5 Feux", items_text[0])
        self.assertIn("Réf: REF-CUI-500", items_text[0])
        self.assertIn("Réf: REF-CUI-900", items_text[1])

        completer = dlg.cb_product.completer()
        self.assertEqual(completer.filterMode(), Qt.MatchContains)
        self.assertEqual(completer.caseSensitivity(), Qt.CaseInsensitive)

        completer.setCompletionPrefix("Cuisinière")
        matches = []
        for r in range(completer.completionModel().rowCount()):
            matches.append(completer.completionModel().index(r, 0).data())
        self.assertEqual(len(matches), 2)
        self.assertTrue(any("REF-CUI-500" in m for m in matches))
        self.assertTrue(any("REF-CUI-900" in m for m in matches))

        dlg.deleteLater()
        self.app.processEvents()

    def test_per_item_remise_percent_and_dzd_saved_correctly(self):
        with patch.object(QMessageBox, "warning", side_effect=AssertionError("Unexpected QMessageBox.warning")), \
             patch.object(QMessageBox, "critical", side_effect=AssertionError("Unexpected QMessageBox.critical")):
            dlg, mock_mgr = self._make_dialog()
            dlg.br_id = 77
            dlg.cb_product.setCurrentIndex(1)
            dlg.cb_location.get_current_location_id = MagicMock(return_value=1)
            dlg.generate_internal_barcode = MagicMock(return_value="BC-77-001")

            # 1) DZD discount: 2 * 1000 = 2000 HT, 500 DZD discount => 25%
            dlg.inp_qty.setValue(2)
            dlg.inp_price.setValue(1000.0)
            dlg.cb_remise_type.setCurrentText("DZD")
            dlg.inp_remise.setValue(500.0)
            dlg.add_item_to_table()

            args, _ = mock_mgr.reception.add_reception_line.call_args
            self.assertAlmostEqual(args[0]["Discount_Percent"], 25.0, places=2)

            # 2) % discount: 15%
            dlg.cb_product.setCurrentIndex(1)
            dlg.inp_qty.setValue(1)
            dlg.inp_price.setValue(1000.0)
            dlg.cb_remise_type.setCurrentText("%")
            dlg.inp_remise.setValue(15.0)
            dlg.add_item_to_table()

            args2, _ = mock_mgr.reception.add_reception_line.call_args
            self.assertAlmostEqual(args2[0]["Discount_Percent"], 15.0, places=2)

            dlg.deleteLater()
            self.app.processEvents()

    def test_bon_level_remise_percent_and_dzd_updates_totals_and_persists(self):
        reception_data = {
            "Header": {
                "BR_ID": 77,
                "Supplier_Invoice_Ref": "FAC-77",
                "Bon_Discount_Value": 10.0,
                "Bon_Discount_Type": "%",
            },
            "Batches": [
                {
                    "Batch_ID": 1,
                    "Product_ID": 10,
                    "Product_Name": "Cuisinière 5 Feux",
                    "Quantity_Initial": 2,
                    "Unit_Price_Received": 1000.0,
                    "Tax_Rate_Percent": 0.0,
                    "Discount_Percent": 10.0,  # 2000 HT -> 200 item disc -> 1800 net
                    "Internal_Barcode": "BC-77-001",
                    "Stock_Unit": "U",
                }
            ],
        }
        dlg, mock_mgr = self._make_dialog(reception_data=reception_data)
        dlg.br_id = 77
        dlg.load_reception_data()

        # Loaded 10% bon discount on 1800 net = 180; total discount = 200 + 180 = 380; total net = 1620
        self.assertAlmostEqual(dlg.total_ht_val, 2000.0, places=2)
        self.assertAlmostEqual(dlg.bon_remise_amt, 180.0, places=2)
        self.assertAlmostEqual(dlg.total_remise_val, 380.0, places=2)
        self.assertAlmostEqual(dlg.total_ttc_val, 1620.0, places=2)

        # Switch bon discount to 300 DZD
        dlg.cb_bon_remise_type.setCurrentText("DZD")
        dlg.inp_bon_remise.setValue(300.0)
        self.app.processEvents()

        self.assertAlmostEqual(dlg.bon_remise_amt, 300.0, places=2)
        self.assertAlmostEqual(dlg.total_remise_val, 500.0, places=2)
        self.assertAlmostEqual(dlg.total_ttc_val, 1500.0, places=2)
        mock_mgr.reception.update_bon_discount.assert_called_with(77, 300.0, "DZD")

        dlg.deleteLater()
        self.app.processEvents()

    def test_recalculate_reception_totals_includes_bon_discount(self):
        fake_cursor = MagicMock()
        fake_cursor.fetchone.side_effect = [
            {"Field": "Bon_Discount_Value"},  # SHOW COLUMNS Bon_Discount_Value
            {"Field": "Bon_Discount_Type"},   # SHOW COLUMNS Bon_Discount_Type
            {"PO_ID": None, "Bon_Discount_Value": 10.0, "Bon_Discount_Type": "%"},  # SELECT Reception_Log
        ]
        fake_cursor.fetchall.return_value = [
            {"Quantity_Initial": 2, "Unit_Price_Received": 1000.0, "Tax_Rate_Percent": 0.0, "Discount_Percent": 10.0}
        ]

        fake_conn = MagicMock()
        fake_conn.cursor.return_value = fake_cursor

        @contextmanager
        def fake_get_db_connection():
            yield fake_conn

        fake_db = MagicMock()
        fake_db.get_db_connection = fake_get_db_connection

        mgr = ReceptionLogManager(fake_db)
        mgr._recalculate_reception_totals(77)

        # Verify UPDATE Reception_Log received: t_ht=2000, t_tva=0, t_ttc=1620, t_disc=380, status='Completed', br_id=77
        update_calls = [
            c for c in fake_cursor.execute.call_args_list
            if "UPDATE Reception_Log" in c[0][0]
        ]
        self.assertEqual(len(update_calls), 1)
        params = update_calls[0][0][1]
        self.assertAlmostEqual(params[0], 2000.0, places=2)
        self.assertAlmostEqual(params[1], 0.0, places=2)
        self.assertAlmostEqual(params[2], 1620.0, places=2)
        self.assertAlmostEqual(params[3], 380.0, places=2)
        self.assertEqual(params[4], "Completed")
        self.assertEqual(params[5], 77)


if __name__ == "__main__":
    unittest.main()
