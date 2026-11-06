# -*- coding: utf-8 -*-
"""
test/test_caisse_bon_articles_and_fk_guard.py
==============================================
Unit tests for Bon Purchased Articles Display & Foreign Key Guard in Caisse:
1. `BondLifecycleManager.get_order_lines(order_id)` and `get_caisse_order_queue` line retrieval.
2. `BondLifecycleManager.record_real_versement` client existence guard (preventing FK 1452).
3. `OrderArticlesDialog` modal UI with detailed product rows, brands, colors, quantities and TTC prices.
4. `CashierDeskWidget`:
   - `btn_view_articles` dynamic state & item count formatting.
   - Double-click on queue table rows opens `OrderArticlesDialog`.
   - `_open_versement_dialog` safe client selection from `clients.get_all_clients()`.
"""

from decimal import Decimal
import os
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from database.bond_lifecycle_manager import BondLifecycleManager
from ui.widgets.appliance_desks.cashier_desk_view import (
    CashierDeskWidget,
    OrderArticlesDialog,
    VersementDialog,
)


class TestCaisseBonArticlesAndFKGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["PYTEST_CURRENT_TEST"] = "1"
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.mock_data_manager = MagicMock()
        self.mock_data_manager.current_user = {"Role": "Admin", "User_ID": 1}
        self.widget = CashierDeskWidget(data_manager=self.mock_data_manager)

    def tearDown(self):
        self.widget.deleteLater()
        self.app.processEvents()

    # =========================================================================
    # 1. BACKEND: LINES RETRIEVAL & FK 1452 CLIENT EXISTENCE GUARD
    # =========================================================================

    def test_get_order_lines_backend(self):
        """Verifies get_order_lines queries Sales_Order_Lines_Theoretical and Products_Master."""
        mock_db = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db.get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            {
                "Line_ID": 10,
                "Product_ID": 101,
                "Product_Name": "Réfrigérateur NoFrost",
                "Brand_Mark": "BEKO",
                "Color_Finish": "Inox",
                "Barcode": "613000111",
                "Quantity_Ordered": 2,
                "Quantity_Dispatched": 0,
                "Unit_Price_TTC": 75000.0,
                "Line_Total_TTC": 150000.0,
            }
        ]

        manager = BondLifecycleManager(mock_db)
        lines = manager.get_order_lines(42)

        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["Product_Name"], "Réfrigérateur NoFrost")
        self.assertEqual(lines[0]["Quantity_Ordered"], 2)

    def test_record_real_versement_raises_value_error_on_missing_client(self):
        """Verifies record_real_versement checks client existence and raises ValueError instead of throwing MySQL FK 1452."""
        mock_db = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db.get_raw_connection.return_value = mock_conn
        mock_db.get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate client NOT found in Clients table
        mock_cursor.fetchone.return_value = None

        manager = BondLifecycleManager(mock_db)
        with self.assertRaises(ValueError) as ctx:
            manager.record_real_versement(
                client_id=9999,
                amount_cash=Decimal("5000.00"),
                cashier_user_id=1,
            )

        self.assertIn("9999", str(ctx.exception))
        self.assertIn("n'existe pas", str(ctx.exception))

    # =========================================================================
    # 2. MODAL DIALOG: OrderArticlesDialog
    # =========================================================================

    def test_order_articles_dialog_population(self):
        """Verifies OrderArticlesDialog displays header info and product line columns."""
        order_data = {
            "Order_ID": 55,
            "Order_Number": "1-BC-0055",
            "Client_Name": "Mourad Hamidi",
            "Client_Phone": "0555123456",
            "Bond_Type": "BON_C",
            "Total_Amount_TTC": 85000.0,
            "Order_Date": "2026-11-06 14:00:00",
        }
        lines = [
            {
                "Line_ID": 1,
                "Product_ID": 202,
                "Product_Name": "Machine à Laver 8kg",
                "Brand_Mark": "LG",
                "Color_Finish": "Blanc",
                "Barcode": "8806087",
                "Quantity_Ordered": 1,
                "Unit_Price_TTC": 85000.0,
                "Line_Total_TTC": 85000.0,
            }
        ]

        dlg = OrderArticlesDialog(order_data, lines=lines)
        self.assertEqual(dlg.table.rowCount(), 1)
        self.assertEqual(dlg.table.item(0, 1).text(), "8806087")
        self.assertEqual(dlg.table.item(0, 2).text(), "Machine à Laver 8kg")
        self.assertEqual(dlg.table.item(0, 3).text(), "LG")
        self.assertEqual(dlg.table.item(0, 4).text(), "Blanc")
        self.assertEqual(dlg.table.item(0, 5).text(), "1")
        self.assertIn("85", dlg.table.item(0, 6).text())
        self.assertIn("85", dlg.table.item(0, 7).text())
        dlg.deleteLater()

    # =========================================================================
    # 3. CASHIER DESK VIEW: BUTTON, SELECTION & DOUBLE-CLICK
    # =========================================================================

    def test_btn_view_articles_state_and_count(self):
        """Verifies that btn_view_articles enables and displays item counts when an order is selected."""
        # Initial state without selection
        self.widget._selected_order = None
        self.widget.queue_table.setCurrentCell(-1, -1)
        self.widget._on_order_selected()
        self.assertFalse(self.widget.btn_view_articles.isEnabled())

        # Simulate selected order with lines
        sample_order = {
            "Order_ID": 77,
            "Order_Number": "1-BC-0077",
            "Client_ID": 12,
            "Client_Name": "Karim Meziane",
            "Bond_Type": "BON_C",
            "Total_Amount_TTC": 120000.0,
            "lines": [
                {
                    "Product_ID": 1,
                    "Product_Name": "Téléviseur 55 UHD",
                    "Brand_Mark": "Samsung",
                    "Color_Finish": "Noir",
                    "Quantity_Ordered": 2,
                    "Unit_Price_TTC": 60000.0,
                    "Line_Total_TTC": 120000.0,
                }
            ],
        }
        self.widget._orders_queue = [sample_order]
        self.widget.queue_table.setRowCount(1)
        it = self.widget.queue_table.item(0, 0)
        from PySide6.QtWidgets import QTableWidgetItem
        it_num = QTableWidgetItem("1-BC-0077")
        it_num.setData(Qt.UserRole, 77)
        self.widget.queue_table.setItem(0, 0, it_num)
        self.widget.queue_table.selectRow(0)
        self.widget._on_order_selected()

        self.assertTrue(self.widget.btn_view_articles.isEnabled())
        self.assertIn("1", self.widget.btn_view_articles.text())
        self.assertIn("article", self.widget.lbl_selected_info.text())

    @patch.object(OrderArticlesDialog, "exec")
    def test_double_click_queue_table_triggers_dialog(self, mock_exec):
        """Verifies that double clicking any cell in the queue table launches OrderArticlesDialog."""
        sample_order = {
            "Order_ID": 88,
            "Order_Number": "2-BCR-0088",
            "Client_ID": 15,
            "Client_Name": "Société Alpha",
            "Bond_Type": "BON_CREDIT",
            "Total_Amount_TTC": 240000.0,
            "lines": [],
        }
        self.widget._selected_order = sample_order
        self.widget._on_table_cell_double_clicked(0, 0)
        mock_exec.assert_called_once()

    def test_versement_dialog_client_selection_and_projection(self):
        """Verifies VersementDialog populates clients, fetches wallet, and calculates projected balance."""
        mock_dm = MagicMock()
        mock_dm.clients.get_all_clients.return_value = [
            {"Client_ID": 42, "Client_Name": "Client Valide", "Phone": "0550112233"},
            {"Client_ID": 99, "Client_Name": "Autre Client", "Phone": ""},
        ]
        mock_dm.bonds.get_client_wallet.return_value = {
            "current_balance": 15000.0,
            "real_deposit_balance": 10000.0,
            "virtual_credit_balance": 5000.0,
        }

        dlg = VersementDialog(data_manager=mock_dm, default_client_id=42)
        self.assertEqual(dlg.cbo_client.count(), 2)
        self.assertEqual(dlg.cbo_client.currentData(), 42)
        self.assertIn("15", dlg.lbl_current_bal.text())
        self.assertTrue(dlg.btn_confirm.isEnabled())

        # Test projected balance with 20,000 DA deposit
        dlg.spin_amount.setValue(20000.0)
        self.assertIn("35", dlg.lbl_projected.text())
        dlg.deleteLater()

    def test_versement_dialog_empty_clients_disables_confirm(self):
        """Verifies VersementDialog disables confirmation when no clients exist, preventing FK 1452."""
        mock_dm = MagicMock()
        mock_dm.clients.get_all_clients.return_value = []

        dlg = VersementDialog(data_manager=mock_dm)
        self.assertEqual(dlg.cbo_client.count(), 0)
        self.assertFalse(dlg.btn_confirm.isEnabled())
        self.assertFalse(dlg.lbl_no_client_warn.isHidden())
        dlg.deleteLater()

    @patch.object(VersementDialog, "exec")
    def test_open_versement_dialog_launches_modal(self, mock_exec):
        """Verifies clicking versement opens the VersementDialog modal."""
        mock_exec.return_value = 0
        self.widget._can_do = MagicMock(return_value=True)
        self.widget._open_versement_dialog()
        mock_exec.assert_called_once()


if __name__ == "__main__":
    unittest.main()
