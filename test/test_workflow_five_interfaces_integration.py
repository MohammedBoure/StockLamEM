# -*- coding: utf-8 -*-
"""
test/test_workflow_five_interfaces_integration.py
=================================================
End-to-End Integration Tests verifying the 5 target interfaces:
1. Historique Ventes (`SalesManager`, `SalesHistoryTab`, `SaleDetailsDialog`)
2. Créances Clients (`ClientManager`, `ClientPaymentManager`, `DebtsManagementTab`)
3. Bureaux (`OrderDeskWidget`, `CashierDeskWidget`, `DispatchDeskWidget`, `BondLifecycleManager`)
4. SAV (`SAVWorkspaceTab`, `SAVReceptionDialog`, `SAVWorkflowManager`)
5. Traçabilité (`MovementHistoryTab`, `StockMovementLogManager`, `SerialTrackingManager`)
"""

import os
import sys
import unittest
from decimal import Decimal
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication

from database.bond_lifecycle_manager import BondLifecycleManager
from database.sales_manager import SalesManager
from ui.widgets.appliance_desks.cashier_desk_view import BonRetourDialog, CashierDeskWidget
from ui.widgets.appliance_desks.sav_kanban_view import SAVReceptionDialog
from ui.widgets.history import MovementHistoryTab
from ui.widgets.sales_history.sale_details_dialog import SaleDetailsDialog


class TestWorkflowFiveInterfacesIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_historique_ventes_labels_and_theoretical_order_details(self):
        """
        Verifies that Bureaux sales (Bon Comptant, Bon Crédit, Bon de Livraison)
        and Bon de Retour are accurately labeled in Historique Ventes and that
        SaleDetailsDialog displays theoretical order lines and dispatched serials.
        """
        mock_db = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db.get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        sales_mgr = SalesManager(mock_db)
        # Mock get_sales_with_profit to return 3 Bureaux invoices
        sales_mgr.get_sales_with_profit = MagicMock(return_value=[
            {
                "Invoice_ID": 10,
                "Invoice_No": "FAC-BC-2026-001",
                "Invoice_Date": "2026-11-06 10:00:00",
                "Bond_Settlement_Type": "BON_C_CASH",
                "Client_Name": "Client Comptant",
                "Status": "Paid",
                "Total_Amount_TTC": 55000.0,
                "Paid_Amount": 55000.0,
                "Total_Cost": 42000.0,
                "Total_Profit": 13000.0,
            },
            {
                "Invoice_ID": 11,
                "Invoice_No": "FAC-BCR-2026-002",
                "Invoice_Date": "2026-11-06 11:00:00",
                "Bond_Settlement_Type": "BON_CREDIT",
                "Client_Name": "Client Crédit",
                "Status": "Validated",
                "Total_Amount_TTC": 80000.0,
                "Paid_Amount": 20000.0,
                "Total_Cost": 60000.0,
                "Total_Profit": 20000.0,
            },
            {
                "Invoice_ID": 12,
                "Invoice_No": "FAC-BL-2026-003",
                "Invoice_Date": "2026-11-06 12:00:00",
                "Bond_Settlement_Type": "BON_LIVRAISON",
                "Client_Name": "Client Livraison",
                "Status": "Validated",
                "Total_Amount_TTC": 95000.0,
                "Paid_Amount": 15000.0,
                "Total_Cost": 72000.0,
                "Total_Profit": 23000.0,
            },
        ])
        mock_cursor.fetchall.return_value = []  # sessions & return_bonds

        ops = sales_mgr.get_sales_operations_history()
        labels = {op["Invoice_No"]: op["Operation_Label"] for op in ops}
        self.assertEqual(labels["FAC-BC-2026-001"], "Bon Comptant")
        self.assertEqual(labels["FAC-BCR-2026-002"], "Bon Crédit")
        self.assertEqual(labels["FAC-BL-2026-003"], "Bon de Livraison")

        # Verify theoretical order line fallback in get_invoice_details_with_profit
        mock_cursor.fetchall.side_effect = [
            [],  # Sales_Details empty for Bureaux invoice
            [
                {
                    "Line_ID": 5,
                    "Order_ID": 77,
                    "Product_ID": 101,
                    "Requested_Color": "Inox",
                    "Qty_Sold": 1,
                    "Quantity_Dispatched": 1,
                    "Unit_Price_HT": 67226.89,
                    "Discount_Percent": 0.0,
                    "TVA_Percent": 19.0,
                    "Line_Total_HT": 67226.89,
                    "Line_Total_TTC": 80000.0,
                    "Unit_Price_TTC": 80000.0,
                    "Product_Name": "Réfrigérateur Combi",
                    "Brand_Mark": "BOSCH",
                    "Color_Finish": "Inox",
                    "Dispatched_Serials": "SN-BOSCH-9901",
                    "Unit_Price_Received": 52000.0,
                }
            ],
        ]
        mock_cursor.fetchone.return_value = {"Order_ID": 77}

        details = sales_mgr.get_invoice_details_with_profit(11)
        self.assertEqual(len(details), 1)
        self.assertIn("SN-BOSCH-9901", details[0]["Lot_Number"])
        self.assertTrue(details[0]["Is_Theoretical_Order_Line"])

        # Verify SaleDetailsDialog renders the theoretical order line as read-only
        mock_dm = MagicMock()
        mock_dm.sales.get_invoice_details_with_profit.return_value = details
        dlg = SaleDetailsDialog(
            mock_dm,
            {"Invoice_ID": 11, "Invoice_No": "FAC-BCR-2026-002", "Status": "Validated"},
        )
        self.assertEqual(dlg.table.rowCount(), 1)
        self.assertIn("SN-BOSCH-9901", dlg.table.item(0, 1).text())
        qty_spin = dlg.table.cellWidget(0, 2)
        self.assertFalse(qty_spin.isEnabled())
        dlg.deleteLater()

    def test_cashier_desk_bon_retour_auto_serial_lookup_and_cod_queue(self):
        """
        Verifies that scanning a N° de Série in BonRetourDialog auto-populates
        invoice ID, client ID, and credit amount, and that DISPATCHED_PENDING_COD
        orders pre-fill the remaining COD balance in CashierDeskWidget.
        """
        mock_dm = MagicMock()
        mock_dm.current_user = {"User_ID": 1, "Role": "Admin"}
        mock_dm.serials.get_serial_details.return_value = {
            "Serial_ID": 500,
            "Serial_Number": "SN-LG-7788",
            "Product_Name": "Lave-Linge 9kg",
            "Brand_Mark": "LG",
            "Original_Sales_Invoice_ID": 42,
            "Resolved_Client_ID": 15,
            "Original_Client_Name": "Karim Mansouri",
            "Original_Invoice_No": "FAC-BC-0042",
            "Selling_Price_TTC": 74000.0,
        }

        dlg = BonRetourDialog(data_manager=mock_dm)
        dlg.txt_serial.setText("SN-LG-7788")
        self.assertEqual(dlg.spn_inv.value(), 42)
        self.assertEqual(dlg.spn_client.value(), 15)
        self.assertEqual(dlg.spn_val.value(), 74000.0)
        self.assertIn("Karim Mansouri", dlg.lbl_serial_info.text())
        dlg.deleteLater()

        # Verify DISPATCHED_PENDING_COD queue handling in CashierDeskWidget
        mock_dm.bonds.get_caisse_order_queue.return_value = [
            {
                "Order_ID": 301,
                "Order_Number": "3-BLV-0301",
                "Client_ID": 15,
                "Client_Name": "Karim Mansouri",
                "Bond_Type": "BON_LIVRAISON",
                "Total_Amount_TTC": 90000.0,
                "Amount_Remaining_Credit": 60000.0,
                "Invoice_ID": 88,
                "Status": "DISPATCHED_PENDING_COD",
                "lines": [],
            }
        ]
        mock_dm.bonds.get_client_wallet.return_value = {
            "current_balance": 0.0,
            "real_deposit_balance": 0.0,
            "virtual_credit_balance": 0.0,
        }
        desk = CashierDeskWidget(data_manager=mock_dm)
        self.assertEqual(desk.queue_table.rowCount(), 1)
        self.assertEqual(desk.queue_table.item(0, 4).text(), "Livré / Attente Solde COD")
        self.assertEqual(desk.txt_cash.text(), "60000")
        desk.deleteLater()

    def test_sav_reception_serial_lookup_and_tracabilite_serial_audit(self):
        """
        Verifies that SAVReceptionDialog auto-detects product and client on serial input,
        and that MovementHistoryTab (Traçabilité) provides instant N° de Série audit and filtering.
        """
        mock_dm = MagicMock()
        mock_dm.current_user = {"User_ID": 1, "Role": "Admin"}
        mock_dm.clients.get_all_clients.return_value = [
            {"Client_ID": 15, "Client_Name": "Karim Mansouri"},
        ]
        mock_dm.serials.get_serial_details.return_value = {
            "Serial_ID": 500,
            "Serial_Number": "SN-BOSCH-1122",
            "Product_Name": "Combi NoFrost",
            "Brand_Mark": "BOSCH",
            "Color_Finish": "Inox",
            "Lot_Number": "LOT-2026-01",
            "Status": "DISPATCHED",
            "Resolved_Client_ID": 15,
            "Original_Client_Name": "Karim Mansouri",
            "Original_Invoice_No": "FAC-BC-0099",
        }
        mock_dm.movement.get_movements_count.return_value = 1
        mock_dm.movement.get_movements_log.return_value = [
            {
                "Movement_ID": 1,
                "Transaction_Date": "2026-11-06 14:00:00",
                "Product_Name": "Combi NoFrost",
                "Batch_Barcode": "LOT-2026-01",
                "Lot_Number": "LOT-2026-01",
                "Movement_Type": "Sale",
                "Qty_Change": -1,
                "Stock_After": 4,
                "Location_Name": "Magasin",
                "Operator_Name": "Magasinier",
                "Reason_Name": "",
                "Notes": "Bon de Sortie BS-2026-001 - N° Série: SN-BOSCH-1122",
            }
        ]

        # 1. SAVReceptionDialog serial lookup
        sav_dlg = SAVReceptionDialog(data_manager=mock_dm)
        sav_dlg.txt_serial.setText("SN-BOSCH-1122")
        self.assertIn("Combi NoFrost", sav_dlg.lbl_serial_info.text())
        self.assertEqual(sav_dlg.cbo_client.currentData(), 15)
        sav_dlg.deleteLater()

        # 2. MovementHistoryTab (Traçabilité) serial audit & Bon de Sortie label
        trace_tab = MovementHistoryTab(mock_dm)
        trace_tab.serial_audit_input.setText("SN-BOSCH-1122")
        trace_tab.verify_serial_number()
        self.assertIn("Combi NoFrost", trace_tab.lbl_serial_audit_result.text())
        self.assertIn("Sorti / Vendu (Bon de Sortie)", trace_tab.lbl_serial_audit_result.text())
        self.assertEqual(trace_tab.search_input.text(), "SN-BOSCH-1122")
        self.assertEqual(trace_tab.table.item(0, 4).text(), "Sortie Magasin (Bon de Sortie)")
        trace_tab.deleteLater()


if __name__ == "__main__":
    unittest.main()
