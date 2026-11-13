# -*- coding: utf-8 -*-
"""
test/test_order_desk_inline_edit_session.py
============================================
Unit tests for Task #12 (Bureaux -> 1. Commandes):
1. Accessing existing editable bons from OrderDeskBonsDialog(inline_edit=True)
   emits editBonRequested and closes without opening OrderBonEditDialog.
2. Opening a bon in OrderDeskWidget creates a new session named 'تعديل'
   with pre-filled client, delivery address, and cart lines.
3. Editing session data and submitting calls update_sales_order_draft with
   the updated data and closes the edit session cleanly.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QMessageBox

from ui.widgets.appliance_desks.order_bons_dialog import OrderDeskBonsDialog
from ui.widgets.appliance_desks.order_desk_view import OrderDeskWidget


class TestOrderDeskInlineEditSession(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["PYTEST_CURRENT_TEST"] = "1"
        cls.app = QApplication.instance() or QApplication([])

    def _make_mock_data_manager(self):
        dm = MagicMock()
        dm.current_user = {"User_ID": 7, "Username": "desk1"}
        dm.manufacturers.get_all_manufacturers.return_value = []
        dm.families.get_all_families.return_value = []
        dm.colors.get_all_colors.return_value = []
        dm.clients.get_all_clients.return_value = [
            {"Client_ID": 1, "Client_Name": "Client Comptoir", "Phone": "", "Price_Tier": 1},
            {"Client_ID": 15, "Client_Name": "SARL Atlas", "Phone": "0550112233", "Price_Tier": 1},
        ]
        dm.serials.get_catalog_with_theoretical_stock.return_value = [
            {
                "Product_ID": 10,
                "Brand_Mark": "Condor",
                "Product_Name": "TV 55 Pouces",
                "Category_Name": "Image",
                "Barcode": "REF-TV-55",
                "Color_Finish": "Noir",
                "Physical_Stock_Qty": 5,
                "Available_Theoretical_Qty": 5,
                "Unit_Price_TTC": 75000.0,
            },
            {
                "Product_ID": 11,
                "Brand_Mark": "Brand",
                "Product_Name": "Machine à Laver 8kg",
                "Category_Name": "Lavage",
                "Barcode": "REF-ML-8K",
                "Color_Finish": "Blanc",
                "Physical_Stock_Qty": 4,
                "Available_Theoretical_Qty": 4,
                "Unit_Price_TTC": 55000.0,
            },
        ]
        dm.bonds.get_order_lines.return_value = [
            {
                "Product_ID": 10,
                "Product_Name": "TV 55 Pouces",
                "Brand_Mark": "Condor",
                "Barcode": "REF-TV-55",
                "Color_Finish": "Noir",
                "Quantity_Ordered": 2,
                "Unit_Price_TTC": 75000.0,
            }
        ]
        dm.bonds.update_sales_order_draft.return_value = {
            "success": True,
            "order_id": 42,
            "order_number": "1-BC-2026-0042",
            "bond_type": "BON_CREDIT",
            "total_ttc": 205000.0,
        }
        return dm

    def test_bons_dialog_inline_edit_emits_signal_without_modal_edit_dialog(self):
        dm = self._make_mock_data_manager()
        sample_bon = {
            "Order_ID": 42,
            "Order_Number": "1-BC-2026-0042",
            "Client_ID": 15,
            "Client_Name": "SARL Atlas",
            "Bond_Type": "BON_C",
            "Status": "CONFIRMED_PENDING_PAYMENT",
            "Total_Amount_TTC": 150000.0,
            "lines": [],
        }
        dm.bonds.get_order_desk_bons.return_value = [sample_bon]

        dlg = OrderDeskBonsDialog(data_manager=dm, inline_edit=True)
        received = []
        dlg.editBonRequested.connect(received.append)
        try:
            dlg.table.selectRow(0)
            with patch("ui.widgets.appliance_desks.order_bons_dialog.OrderBonEditDialog") as mock_modal:
                dlg._edit_selected()
                mock_modal.assert_not_called()
            self.assertEqual(len(received), 1)
            self.assertEqual(received[0]["Order_ID"], 42)
        finally:
            dlg.deleteLater()

    def test_open_bon_in_edit_session_modify_and_submit(self):
        dm = self._make_mock_data_manager()
        widget = OrderDeskWidget(dm)
        try:
            sample_bon = {
                "Order_ID": 42,
                "Order_Number": "1-BC-2026-0042",
                "Client_ID": 15,
                "Client_Name": "SARL Atlas",
                "Bond_Type": "BON_C",
                "Status": "CONFIRMED_PENDING_PAYMENT",
                "Delivery_Address": "Alger Centre",
            }
            edit_sid = widget.open_bon_in_edit_session(sample_bon)
            self.assertEqual(widget._active_session_id, edit_sid)
            self.assertIn("تعديل", widget._sessions[edit_sid]["label"])

            idx = widget.session_tab_bar.currentIndex()
            self.assertIn("تعديل", widget.session_tab_bar.tabText(idx))
            self.assertEqual(widget.txt_delivery_addr.text(), "Alger Centre")
            self.assertEqual(len(widget._sessions[edit_sid]["cart"]), 1)

            # Re-opening the same bon focuses the existing edit session
            same_sid = widget.open_bon_in_edit_session(sample_bon)
            self.assertEqual(same_sid, edit_sid)

            # Modify session: add second product & update delivery address
            widget._add_product_to_session(edit_sid, dm.serials.get_catalog_with_theoretical_stock.return_value[1])
            widget.txt_delivery_addr.setText("Oran")
            widget._sessions[edit_sid]["delivery_address"] = "Oran"

            with patch.object(QMessageBox, "information"):
                widget.btn_credit.click()

            dm.bonds.update_sales_order_draft.assert_called_once()
            kwargs = dm.bonds.update_sales_order_draft.call_args.kwargs
            self.assertEqual(kwargs["order_id"], 42)
            self.assertEqual(kwargs["client_id"], 15)
            self.assertEqual(kwargs["bond_type"], "BON_CREDIT")
            self.assertEqual(kwargs["delivery_address"], "Oran")
            self.assertEqual(len(kwargs["items"]), 2)
            self.assertNotIn(edit_sid, widget._sessions)
        finally:
            widget.deleteLater()


if __name__ == "__main__":
    unittest.main()
