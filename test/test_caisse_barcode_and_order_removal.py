# -*- coding: utf-8 -*-
"""
test/test_caisse_barcode_and_order_removal.py
=============================================
Unit tests for Task #5:
1. Standardized Bon numbering by type digit (1: Bon Comptant, 2: Bon Crédit, 3: Bon de Livraison).
2. Dedicated Barcode Scanner input and dynamic bon type detection badge in CashierDeskWidget.
3. Queue filtering and automatic row selection by barcode scan.
4. Order removal button ('Retirer Bon') and backend cancellation logic in BondLifecycleManager.
"""

from decimal import Decimal
import os
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from database.bond_lifecycle_manager import BondLifecycleManager
from ui.widgets.appliance_desks.cashier_desk_view import CashierDeskWidget


class TestCaisseBarcodeAndOrderRemoval(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["PYTEST_CURRENT_TEST"] = "1"
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.widget = CashierDeskWidget(data_manager=None)

    def tearDown(self):
        self.widget.deleteLater()
        self.app.processEvents()

    # =========================================================================
    # 1. BON NUMBERING STANDARD (1: Comptant, 2: Crédit, 3: Livraison)
    # =========================================================================

    def test_order_number_prefixes_by_bond_type(self):
        """Verifies that BondLifecycleManager assigns prefixes starting with 1, 2, and 3."""
        mock_db = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db.get_raw_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.lastrowid = 101

        # Simulate batch stock availability
        mock_cursor.fetchall.return_value = [
            {"Batch_ID": 1, "Quantity_Current": 10, "Theoretical_Reserved_Qty": 0}
        ]

        manager = BondLifecycleManager(mock_db)

        test_cases = [
            ("BON_C", "1-BC"),
            ("BON_CREDIT", "2-BCR"),
            ("BON_LIVRAISON", "3-BLV"),
        ]

        for b_type, expected_prefix in test_cases:
            res = manager.create_sales_order_draft(
                client_id=1,
                order_desk_user_id=1,
                items=[{"product_id": 10, "quantity": 1, "unit_price_ttc": "15000.00"}],
                bond_type=b_type,
            )
            order_num = res["order_number"]
            self.assertTrue(
                order_num.startswith(expected_prefix),
                f"Order number '{order_num}' for {b_type} must start with '{expected_prefix}'",
            )
            # Digit requirement: first character must match 1, 2, or 3
            first_digit = order_num[0]
            self.assertEqual(
                first_digit,
                expected_prefix[0],
                f"Order number must start with digit {expected_prefix[0]} for type {b_type}",
            )

    # =========================================================================
    # 2. BARCODE SCANNER INPUT & TYPE BADGE DETECTION
    # =========================================================================

    def test_scanner_ui_elements_exist(self):
        """Verifies that barcode scan input, type badge, find, and clear buttons exist."""
        self.assertIsNotNone(self.widget.txt_scan_bon)
        self.assertIsNotNone(self.widget.lbl_scan_type_badge)
        self.assertIsNotNone(self.widget.btn_scan_find)
        self.assertIsNotNone(self.widget.btn_clear_scan)
        self.assertIsNotNone(self.widget.btn_remove_bon)

    def test_scan_text_detection_and_badges(self):
        """Verifies that scanning or typing 1, 2, or 3 immediately detects and displays the type badge."""
        # Initial neutral state
        self.widget._reset_scan_filter()
        self.assertIn("Tous", self.widget.lbl_scan_type_badge.text())

        # 1 -> Bon Comptant
        self.widget.txt_scan_bon.setText("1-BC-20261106-00042")
        self.assertIn("1 : Bon Comptant", self.widget.lbl_scan_type_badge.text())

        # 2 -> Bon Crédit
        self.widget.txt_scan_bon.setText("2-BCR-20261106-00043")
        self.assertIn("2 : Bon Crédit", self.widget.lbl_scan_type_badge.text())

        # 3 -> Bon de Livraison
        self.widget.txt_scan_bon.setText("3-BLV-20261106-00044")
        self.assertIn("3 : Bon de Livraison", self.widget.lbl_scan_type_badge.text())

        # Single digit tests
        self.widget.txt_scan_bon.setText("1")
        self.assertIn("1 : Bon Comptant", self.widget.lbl_scan_type_badge.text())

        self.widget.txt_scan_bon.setText("2")
        self.assertIn("2 : Bon Crédit", self.widget.lbl_scan_type_badge.text())

        self.widget.txt_scan_bon.setText("3")
        self.assertIn("3 : Bon de Livraison", self.widget.lbl_scan_type_badge.text())

    def test_scan_queue_filtering_and_selection(self):
        """Verifies filtering queue rows and selecting matching bon upon scan."""
        # Ensure fresh queue with 3 distinct orders
        self.widget.refresh_queue()
        self.assertEqual(self.widget.queue_table.rowCount(), 3)

        # Filter by Bon Crédit digit '2'
        self.widget.txt_scan_bon.setText("2")
        # Row 0 (1-BC-0042) should be hidden, Row 1 (2-BCR-0043) visible, Row 2 (3-BLV-0044) hidden
        self.assertTrue(self.widget.queue_table.isRowHidden(0))
        self.assertFalse(self.widget.queue_table.isRowHidden(1))
        self.assertTrue(self.widget.queue_table.isRowHidden(2))

        # Reset filter
        self.widget._reset_scan_filter()
        self.assertEqual(self.widget.txt_scan_bon.text(), "")
        self.assertFalse(self.widget.queue_table.isRowHidden(0))
        self.assertFalse(self.widget.queue_table.isRowHidden(1))
        self.assertFalse(self.widget.queue_table.isRowHidden(2))

        # Scan exact barcode
        self.widget.txt_scan_bon.setText("3-BLV-0044")
        self.widget._on_bon_scanned()
        self.assertEqual(self.widget.queue_table.currentRow(), 2)
        self.assertIsNotNone(self.widget._selected_order)
        self.assertEqual(self.widget._selected_order["Order_Number"], "3-BLV-0044")
        self.assertEqual(self.widget._selected_order["Bond_Type"], "BON_LIVRAISON")

    # =========================================================================
    # 3. BON REMOVAL BUTTON ('Retirer Bon') & QUEUE REFRESH
    # =========================================================================

    def test_remove_selected_bon_ui_action(self):
        """Verifies that clicking 'Retirer Bon' with confirmation removes the order from Caisse."""
        self.widget.refresh_queue()
        self.assertEqual(self.widget.queue_table.rowCount(), 3)

        # Select row 0 (1-BC-0042)
        self.widget.queue_table.selectRow(0)
        self.assertEqual(self.widget._selected_order["Order_ID"], 42)

        # Mock confirmation question to accept Yes, and info modal
        with patch("ui.widgets.appliance_desks.cashier_desk_view.QMessageBox.question", return_value=QMessageBox.Yes), \
             patch("ui.widgets.appliance_desks.cashier_desk_view.QMessageBox.information") as mock_info:
            self.widget._remove_selected_bon()
            mock_info.assert_called_once()

        # The order should now be removed from the table
        self.assertEqual(self.widget.queue_table.rowCount(), 2)
        order_numbers = [
            self.widget.queue_table.item(r, 0).text()
            for r in range(self.widget.queue_table.rowCount())
        ]
        self.assertNotIn("1-BC-0042", order_numbers)

    # =========================================================================
    # 4. BACKEND CANCEL / REMOVE LOGIC IN BOND_LIFECYCLE_MANAGER
    # =========================================================================

    def test_cancel_or_remove_caisse_order_backend(self):
        """Verifies that cancel_or_remove_caisse_order releases theoretical reservation and sets CANCELLED."""
        mock_db = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db.get_raw_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock order in CONFIRMED_PENDING_PAYMENT status
        mock_cursor.fetchone.side_effect = [
            {
                "Order_ID": 50,
                "Order_Number": "1-BC-20261106-99999",
                "Client_ID": 10,
                "Bond_Type": "BON_C",
                "Total_Amount_TTC": Decimal("50000.00"),
                "Status": "CONFIRMED_PENDING_PAYMENT",
            }
        ]
        # Mock order lines
        mock_cursor.fetchall.side_effect = [
            [{"Line_ID": 1, "Product_ID": 200, "Quantity_Ordered": 2}],
            # Active batches for product 200
            [{"Batch_ID": 501, "Theoretical_Reserved_Qty": 5}],
        ]

        manager = BondLifecycleManager(mock_db)
        res = manager.cancel_or_remove_caisse_order(
            order_id=50,
            user_id=1,
            reason="Retrait client au guichet",
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["order_id"], 50)
        self.assertEqual(res["status"], "CANCELLED")

        # Verify that an UPDATE to Inventory_Batches and Sales_Orders_Theoretical occurred
        executed_sqls = [call[0][0] for call in mock_cursor.execute.call_args_list]
        self.assertTrue(any("UPDATE Inventory_Batches" in sql for sql in executed_sqls))
        self.assertTrue(any("UPDATE Sales_Orders_Theoretical" in sql for sql in executed_sqls))
        mock_conn.commit.assert_called_once()

    def test_cancel_or_remove_caisse_order_rejects_already_paid(self):
        """Verifies that cancel_or_remove_caisse_order raises error if order is already paid/dispatched."""
        mock_db = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db.get_raw_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = {
            "Order_ID": 51,
            "Order_Number": "1-BC-PAID",
            "Client_ID": 10,
            "Bond_Type": "BON_C",
            "Total_Amount_TTC": Decimal("50000.00"),
            "Status": "PAID_PENDING_DISPATCH",
        }

        manager = BondLifecycleManager(mock_db)
        with self.assertRaises(ValueError) as ctx:
            manager.cancel_or_remove_caisse_order(order_id=51, user_id=1)
        self.assertIn("PAID_PENDING_DISPATCH", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
