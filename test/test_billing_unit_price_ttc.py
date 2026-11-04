import os
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from ui.widgets.billing.invoice_editor import InvoiceEditorWidget
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False


@unittest.skipUnless(HAS_PYSIDE6, "PySide6 is not installed in the current environment")
class TestBillingUnitPriceTTC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if HAS_PYSIDE6:
            cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.mock_manager = MagicMock()
        self.editor = InvoiceEditorWidget(self.mock_manager)

    def tearDown(self):
        if hasattr(self, 'editor') and self.editor:
            self.editor.deleteLater()

    def test_calculate_ttc_with_tva(self):
        batch = {
            "Product_ID": 10,
            "Unit_Price_Received": 1000.0,
            "Tax_Rate_Percent": 19.0,
            "Discount_Percent": 0.0,
        }
        ttc = self.editor.get_batch_unit_price_ttc(batch)
        self.assertEqual(ttc, 1190.0)

    def test_calculate_ttc_with_discount_and_tva(self):
        batch = {
            "Product_ID": 10,
            "Unit_Price_Received": 100.0,
            "Tax_Rate_Percent": 19.0,
            "Discount_Percent": 10.0,
        }
        # 100 * (1 - 0.10) * (1 + 0.19) = 90 * 1.19 = 107.1
        ttc = self.editor.get_batch_unit_price_ttc(batch)
        self.assertEqual(ttc, 107.1)

    def test_calculate_ttc_zero_tva(self):
        batch = {
            "Product_ID": 10,
            "Unit_Price_Received": 250.0,
            "Tax_Rate_Percent": 0.0,
            "Discount_Percent": 0.0,
        }
        ttc = self.editor.get_batch_unit_price_ttc(batch)
        self.assertEqual(ttc, 250.0)

    def test_calculate_ttc_fallback_to_other_batch(self):
        self.editor.batches_cache = [
            {
                "Product_ID": 15,
                "Batch_ID": 1,
                "Unit_Price_Received": 500.0,
                "Tax_Rate_Percent": 19.0,
                "Discount_Percent": 0.0,
            }
        ]
        # Batch 2 has 0 price
        batch = {
            "Product_ID": 15,
            "Batch_ID": 2,
            "Unit_Price_Received": 0.0,
            "Tax_Rate_Percent": 0.0,
            "Discount_Percent": 0.0,
        }
        ttc = self.editor.get_batch_unit_price_ttc(batch)
        # Should fall back to batch 1: 500 * 1.19 = 595.0
        self.assertEqual(ttc, 595.0)

    def test_add_batch_to_invoice_billable_uses_ttc(self):
        self.editor.is_loading_transfer = True  # prevent saving header
        batch = {
            "Product_ID": 20,
            "Batch_ID": 101,
            "Product_Name": "Reagent A",
            "Barcode": "BC123",
            "Quantity_Current": 10,
            "Unit_Price_Received": 200.0,
            "Tax_Rate_Percent": 19.0,
            "Discount_Percent": 0.0,
            "Is_Billable": True,
        }
        self.editor.batches_cache = [batch]
        res = self.editor.add_batch_to_invoice(batch, initial_qty=2)
        self.assertTrue(res)

        # Price widget is in column 3
        sb_price = self.editor.table.cellWidget(0, 3)
        self.assertIsNotNone(sb_price)
        self.assertEqual(sb_price.value(), 238.0)  # 200 * 1.19 = 238.0
        self.assertTrue(sb_price.isEnabled())

    def test_add_batch_to_invoice_non_billable_disabled_price(self):
        self.editor.is_loading_transfer = True
        batch = {
            "Product_ID": 21,
            "Batch_ID": 102,
            "Product_Name": "Reagent Free",
            "Barcode": "BC999",
            "Quantity_Current": 5,
            "Unit_Price_Received": 200.0,
            "Tax_Rate_Percent": 19.0,
            "Discount_Percent": 0.0,
            "Is_Billable": False,
        }
        self.editor.batches_cache = [batch]
        res = self.editor.add_batch_to_invoice(batch, initial_qty=1)
        self.assertTrue(res)

        sb_price = self.editor.table.cellWidget(0, 3)
        self.assertIsNotNone(sb_price)
        self.assertEqual(sb_price.value(), 0.0)
        self.assertFalse(sb_price.isEnabled())


if __name__ == "__main__":
    unittest.main()
