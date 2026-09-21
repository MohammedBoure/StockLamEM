import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QHeaderView, QDoubleSpinBox, QPushButton, QLabel, QAbstractItemView
    from PySide6.QtCore import Qt
    from ui.widgets.wholesale_sales.wholesale_sales_tab import WholesaleSalesTab
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False
    QApplication = None
    WholesaleSalesTab = None


class TestWholesaleUIImprovements(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if HAS_PYSIDE6:
            cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        if not HAS_PYSIDE6:
            self.skipTest("PySide6 not available")

        self.mock_dm = MagicMock()
        client_data = [
            {'Client_ID': 1, 'Client_Name': 'Grossiste Central', 'Price_Tier': 'Prix_2', 'Credit_Limit': 50000.0, 'Current_Balance': 10000.0}
        ]
        self.mock_dm.clients.get_all_clients.return_value = client_data
        self.mock_dm.clients.get_all_clients_with_balances.return_value = client_data
        self.mock_dm.batches.get_all_batches_with_details.return_value = [
            {
                'Batch_ID': 1,
                'Product_ID': 10,
                'Product_Name': 'Paracétamol 500mg',
                'Barcode': '6131234567890',
                'Lot_Number': 'LOT-001',
                'Quantity_Current': 100.0,
                'Selling_Price_HT': 100.0,
                'Selling_Price_HT_2': 90.0,
                'Selling_Price_HT_3': 80.0,
                'Selling_Price_HT_4': 70.0,
                'Selling_TVA_Percent': 19.0,
                'Location_Name': 'Entrepôt A'
            },
            {
                'Batch_ID': 2,
                'Product_ID': 20,
                'Product_Name': 'Amoxicilline 1g',
                'Barcode': '6139876543210',
                'Lot_Number': 'LOT-002A',
                'Quantity_Current': 50.0,
                'Selling_Price_HT': 200.0,
                'Selling_Price_HT_2': 180.0,
                'Location_Name': 'Entrepôt B'
            },
            {
                'Batch_ID': 3,
                'Product_ID': 20,
                'Product_Name': 'Amoxicilline 1g',
                'Barcode': '6139876543210',
                'Lot_Number': 'LOT-002B',
                'Quantity_Current': 30.0,
                'Selling_Price_HT': 200.0,
                'Selling_Price_HT_2': 180.0,
                'Location_Name': 'Entrepôt B'
            }
        ]
        self.tab = WholesaleSalesTab(self.mock_dm)

    def test_search_row_layout_expanded_without_quick_spinboxes(self):
        """Top search row contains expanded search_input, keypad and refresh buttons; quick spinboxes removed from layout."""
        self.assertIsNotNone(self.tab.search_input)
        self.assertEqual(self.tab.search_input.height(), 42)
        # Search input is in the layout
        self.assertFalse(self.tab.search_input.isHidden())
        # The quick qty and quick discount are NOT in the search row layout
        self.assertIsNone(self.tab.spin_quick_qty.parent())
        self.assertIsNone(self.tab.spin_quick_discount.parent())

    def test_instant_scan_product_addition(self):
        """Scanning a single-lot barcode immediately adds product to cart and clears search input."""
        self.assertEqual(self.tab.cart_table.rowCount(), 0)

        # Scan barcode
        self.tab.search_input.setText("6131234567890")
        self.tab._on_search_return()

        # Product was added immediately
        self.assertEqual(self.tab.cart_table.rowCount(), 1)
        # Search bar is cleared for next scan
        self.assertEqual(self.tab.search_input.text(), "")

        # Quantity in row is 1.0
        qty_spin = self.tab.cart_table.cellWidget(0, 9)
        self.assertEqual(qty_spin.value(), 1.0)

        # Scanning the same barcode again increments quantity to 2.0
        self.tab.search_input.setText("6131234567890")
        self.tab._on_search_return()
        self.assertEqual(self.tab.cart_table.rowCount(), 1)
        self.assertEqual(qty_spin.value(), 2.0)
        self.assertEqual(self.tab.search_input.text(), "")

    def test_table_horizontal_scroll_and_action_buttons(self):
        """Cart table supports smooth horizontal scroll with explicit column widths and 32x32 action buttons."""
        self.assertEqual(self.tab.cart_table.horizontalScrollBarPolicy(), Qt.ScrollBarAsNeeded)
        self.assertEqual(self.tab.cart_table.horizontalScrollMode(), QAbstractItemView.ScrollPerPixel)
        self.assertFalse(self.tab.cart_table.horizontalHeader().stretchLastSection())

        # Check column widths
        self.assertEqual(self.tab.cart_table.columnWidth(0), 84)
        self.assertEqual(self.tab.cart_table.columnWidth(1), 130)
        self.assertEqual(self.tab.cart_table.columnWidth(2), 260)

        # Add item and inspect action buttons
        batch = self.mock_dm.batches.get_all_batches_with_details.return_value[0]
        self.tab.add_batch_to_cart(batch, qty=1.0)
        action_widget = self.tab.cart_table.cellWidget(0, 0)
        self.assertIsNotNone(action_widget)

        btns = action_widget.findChildren(QPushButton)
        self.assertEqual(len(btns), 2)
        btn_del, btn_split = btns[0], btns[1]
        self.assertEqual(btn_del.width(), 32)
        self.assertEqual(btn_del.height(), 32)
        self.assertEqual(btn_split.width(), 32)
        self.assertEqual(btn_split.height(), 32)
        self.assertFalse(btn_del.icon().isNull())
        self.assertFalse(btn_split.icon().isNull())

    def test_compact_tier_warning_icon_and_dialog(self):
        """Interactive alert icon is visible only when Prix_1 is applied and opens modal dialog."""
        # Client default is Prix_2 -> Warning button should be hidden
        self.assertTrue(self.tab.btn_tier_warning.isHidden())

        # Switch to Prix_1 (Detail)
        idx_p1 = self.tab.cb_price_tier.findData("Prix_1")
        self.tab.cb_price_tier.setCurrentIndex(idx_p1)
        self.assertFalse(self.tab.btn_tier_warning.isHidden())

        # Clicking warning button opens modal dialog
        with patch.object(self.tab, '_show_tier_warning_dialog') as mock_show:
            self.tab.btn_tier_warning.click()
            mock_show.assert_called_once()

        # Switch back to Prix_2 -> Warning button is hidden again
        idx_p2 = self.tab.cb_price_tier.findData("Prix_2")
        self.tab.cb_price_tier.setCurrentIndex(idx_p2)
        self.assertTrue(self.tab.btn_tier_warning.isHidden())


if __name__ == "__main__":
    unittest.main()
