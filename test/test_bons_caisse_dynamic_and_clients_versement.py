# -*- coding: utf-8 -*-
"""
Automated tests verifying:
1. SQL schema column fixes (no Unit_Cost_Landed, Total_Credit_Issued, or c.Phone_Number).
2. Dynamic Bon-type action buttons in CashierDeskWidget (BC, BCréde, BL advance vs 0 DA COD).
3. Ironclad rule keeping unclosed BLs visible in both Order Desk Bons and Caisse queue until COMPLETED.
4. Order Desk Bons du Jour dialog (view, edit via OrderBonEditDialog, and PDF export via export_order_bon_to_pdf).
5. ClientsTab 'Versements' button and minimalist ClientVersementsDialog.
"""

import inspect
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from decimal import Decimal
import pathlib
from PySide6.QtWidgets import QApplication, QPushButton

from database.bond_lifecycle_manager import BondLifecycleManager
from database.sales_manager import SalesManager
from database.serial_tracking_manager import SerialTrackingManager
from ui.widgets.appliance_desks.bon_pdf_export import export_order_bon_to_pdf
from ui.widgets.appliance_desks.cashier_desk_view import CashierDeskWidget, ClientWalletDialog
from ui.widgets.appliance_desks.order_bons_dialog import OrderBonEditDialog, OrderDeskBonsDialog
from ui.widgets.appliance_desks.order_desk_view import OrderDeskWidget
from ui.widgets.clients.client_versements_dialog import ClientVersementsDialog
from ui.widgets.clients.clients_tab import ClientsTab


class TestBonsCaisseDynamicAndClientsVersement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_no_invalid_sql_columns_in_managers(self):
        """Verifies removed non-existent DB columns never appear in SQL queries."""
        sales_src = inspect.getsource(SalesManager)
        serial_src = inspect.getsource(SerialTrackingManager.get_serial_details)
        bonds_src = inspect.getsource(BondLifecycleManager)

        self.assertNotIn("ib.Unit_Cost_Landed", sales_src)
        self.assertNotIn("b.Unit_Cost_Landed", serial_src)
        self.assertNotIn("Total_Credit_Issued", sales_src)
        self.assertIn("Total_Return_Value", sales_src)
        self.assertNotIn("c.Phone_Number", bonds_src)

    def test_caisse_dynamic_buttons_by_bon_type_and_bl_options(self):
        """
        Verifies Caisse shows ONLY the relevant button(s) for BC, BCréde, and BL
        (advance now vs 0 DA COD on delivery, plus post-advance/COD settlement).
        """
        dm = MagicMock()
        dm.current_user = {"User_ID": 1, "Role": "Admin"}
        dm.bonds.get_client_wallet.return_value = {
            "current_balance": 10000.0,
            "real_deposit_balance": 10000.0,
            "virtual_credit_balance": 0.0,
        }
        dm.bonds.get_caisse_order_queue.return_value = [
            {
                "Order_ID": 1,
                "Order_Number": "1-BC-0001",
                "Client_ID": 1,
                "Client_Name": "Client BC",
                "Bond_Type": "BON_C",
                "Total_Amount_TTC": 45000.0,
                "Status": "CONFIRMED_PENDING_PAYMENT",
                "lines": [{"Product_Name": "Frigo", "Quantity_Ordered": 1, "Unit_Price_TTC": 45000.0}],
            },
            {
                "Order_ID": 2,
                "Order_Number": "2-BCR-0002",
                "Client_ID": 2,
                "Client_Name": "Client Crédit",
                "Bond_Type": "BON_CREDIT",
                "Total_Amount_TTC": 60000.0,
                "Status": "CONFIRMED_PENDING_PAYMENT",
                "lines": [],
            },
            {
                "Order_ID": 3,
                "Order_Number": "3-BLV-0003",
                "Client_ID": 3,
                "Client_Name": "Client BL Nouveau",
                "Bond_Type": "BON_LIVRAISON",
                "Total_Amount_TTC": 80000.0,
                "Status": "CONFIRMED_PENDING_PAYMENT",
                "lines": [],
            },
            {
                "Order_ID": 4,
                "Order_Number": "3-BLV-0004",
                "Client_ID": 3,
                "Client_Name": "Client BL En Cours",
                "Bond_Type": "BON_LIVRAISON",
                "Total_Amount_TTC": 80000.0,
                "Amount_Paid_So_Far": 20000.0,
                "Amount_Remaining_Credit": 60000.0,
                "Invoice_ID": 55,
                "Status": "APPROVED_LIVRAISON_PENDING_DISPATCH",
                "lines": [],
            },
        ]

        desk = CashierDeskWidget(data_manager=dm)

        # Row 0: BON_C -> ONLY btn_val_bon_c is visible
        desk.queue_table.selectRow(0)
        desk._on_order_selected()
        self.assertFalse(desk.btn_val_bon_c.isHidden())
        self.assertTrue(desk.btn_val_credit.isHidden())
        self.assertTrue(desk.btn_val_livraison.isHidden())
        self.assertTrue(desk.btn_val_livraison_cod_later.isHidden())
        self.assertTrue(desk.btn_view_articles.isEnabled())

        # Row 1: BON_CREDIT -> ONLY btn_val_credit is visible
        desk.queue_table.selectRow(1)
        desk._on_order_selected()
        self.assertTrue(desk.btn_val_bon_c.isHidden())
        self.assertFalse(desk.btn_val_credit.isHidden())
        self.assertTrue(desk.btn_val_livraison.isHidden())
        self.assertTrue(desk.btn_val_livraison_cod_later.isHidden())

        # Row 2: New BON_LIVRAISON -> BOTH advance & 0 DA COD buttons are visible
        desk.queue_table.selectRow(2)
        desk._on_order_selected()
        self.assertTrue(desk.btn_val_bon_c.isHidden())
        self.assertTrue(desk.btn_val_credit.isHidden())
        self.assertFalse(desk.btn_val_livraison.isHidden())
        self.assertFalse(desk.btn_val_livraison_cod_later.isHidden())

        # Row 3: Unclosed BON_LIVRAISON (already validated with advance, awaiting completion) -> settle button visible
        desk.queue_table.selectRow(3)
        desk._on_order_selected()
        self.assertFalse(desk.btn_val_livraison.isHidden())
        self.assertTrue(desk.btn_val_livraison_cod_later.isHidden())
        self.assertEqual(desk.txt_cash.text(), "60000")

        desk.deleteLater()

    def test_unclosed_bl_remains_visible_in_caisse_and_order_desk_queries(self):
        """Verifies SQL queries for both Caisse and Order Desk keep unclosed BLs visible until COMPLETED."""
        caisse_sql = inspect.getsource(BondLifecycleManager.get_caisse_order_queue)
        order_bons_sql = inspect.getsource(BondLifecycleManager.get_order_desk_bons)

        self.assertIn("o.Bond_Type = 'BON_LIVRAISON'", caisse_sql)
        self.assertIn("NOT IN ('COMPLETED', 'CANCELLED')", caisse_sql)
        self.assertIn("o.Bond_Type = 'BON_LIVRAISON'", order_bons_sql)
        self.assertIn("NOT IN ('COMPLETED', 'CANCELLED')", order_bons_sql)

    def test_order_desk_bons_du_jour_edit_and_pdf_export(self):
        """Verifies OrderDeskWidget Bons du Jour button, editing dialog, and PDF generation."""
        dm = MagicMock()
        dm.current_user = {"User_ID": 1, "Role": "Admin"}
        dm.serials.get_catalog_with_theoretical_stock.return_value = []
        dm.clients.get_all_clients.return_value = [{"Client_ID": 1, "Client_Name": "Karim Mansouri", "Phone": "0550112233"}]
        sample_bon = {
            "Order_ID": 77,
            "Order_Number": "3-BLV-20261106-00077",
            "Client_ID": 1,
            "Client_Name": "Karim Mansouri",
            "Bond_Type": "BON_LIVRAISON",
            "Order_Date": "2026-11-05 14:30:00",
            "Total_Amount_TTC": 92000.0,
            "Amount_Paid_So_Far": 20000.0,
            "Amount_Remaining_Credit": 72000.0,
            "Status": "APPROVED_LIVRAISON_PENDING_DISPATCH",
            "Delivery_Address": "Alger Centre",
            "lines": [
                {
                    "Product_ID": 10,
                    "Product_Name": "Lave-Vaisselle",
                    "Brand_Mark": "BOSCH",
                    "Color_Finish": "Inox",
                    "Quantity_Ordered": 1,
                    "Quantity_Dispatched": 0,
                    "Unit_Price_TTC": 92000.0,
                    "Line_Total_TTC": 92000.0,
                }
            ],
        }
        dm.bonds.get_order_desk_bons.return_value = [sample_bon]
        dm.bonds.update_sales_order_draft.return_value = {
            "success": True,
            "order_id": 77,
            "order_number": "3-BLV-20261106-00077",
            "bond_type": "BON_LIVRAISON",
            "total_ttc": 184000.0,
        }

        order_desk = OrderDeskWidget(data_manager=dm)
        self.assertTrue(hasattr(order_desk, "btn_daily_bons"))

        bons_dlg = OrderDeskBonsDialog(data_manager=dm)
        self.assertEqual(bons_dlg.table.rowCount(), 1)
        bons_dlg.table.selectRow(0)
        self.assertTrue(bons_dlg.btn_pdf.isEnabled())
        self.assertTrue(bons_dlg.btn_edit.isEnabled())

        # Verify Edit Dialog updates quantity and submits to backend
        edit_dlg = OrderBonEditDialog(data_manager=dm, order_data=sample_bon)
        edit_dlg._on_qty_changed(0, 2)
        edit_dlg._save_changes()
        dm.bonds.update_sales_order_draft.assert_called_once()

        # Verify PDF Export creates a non-empty PDF file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            pdf_path = tmp.name
        try:
            generated = export_order_bon_to_pdf(dm, sample_bon, output_path=pdf_path)
            self.assertEqual(generated, pdf_path)
            self.assertTrue(os.path.exists(pdf_path))
            self.assertGreater(os.path.getsize(pdf_path), 500)
        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)

        edit_dlg.deleteLater()
        bons_dlg.deleteLater()
        order_desk.deleteLater()

    def test_clients_tab_versements_button_and_dialog(self):
        """Verifies ClientsTab exposes the Versements button and ClientVersementsDialog renders balance & history."""
        dm = MagicMock()
        dm.clients.get_clients_paged.return_value = (
            [{"Client_ID": 5, "Client_Name": "Yacine Boudiaf", "Phone": "0661001122", "Credit_Limit": 100000.0, "Current_Balance": 0.0}],
            1,
        )
        dm.clients.get_all_clients.return_value = [
            {"Client_ID": 5, "Client_Name": "Yacine Boudiaf", "Phone": "0661001122"}
        ]
        dm.bonds.get_client_wallet.return_value = {
            "current_balance": 45000.0,
            "real_deposit_balance": 30000.0,
            "virtual_credit_balance": 15000.0,
        }
        dm.bonds.get_client_wallet_transactions.return_value = [
            {
                "Transaction_ID": 1,
                "Transaction_Type": "REAL_CASH_VERSEMENT",
                "Amount": 30000.0,
                "Balance_After": 30000.0,
                "Transaction_Notes": "Dépôt espèces",
                "Created_At": "2026-11-06 09:15:00",
            },
            {
                "Transaction_ID": 2,
                "Transaction_Type": "RETURN_VIRTUAL_CREDIT",
                "Amount": 15000.0,
                "Balance_After": 45000.0,
                "Transaction_Notes": "BR-009",
                "Created_At": "2026-11-06 11:20:00",
            },
        ]

        tab = ClientsTab(data_manager=dm)
        self.assertTrue(hasattr(tab, "btn_versements"))
        self.assertEqual(tab.btn_versements.text(), "Versements")

        dlg = ClientVersementsDialog(data_manager=dm, client_id=5)
        self.assertIn("45", dlg.lbl_balance_summary.text())
        self.assertEqual(dlg.table.rowCount(), 2)
        self.assertIn("Versement Espèces", dlg.table.item(0, 1).text())

        dlg.deleteLater()
        tab.deleteLater()

    def test_every_navbar_interface_has_dedicated_folder_in_ui_widgets(self):
        """Verifies every navbar workspace has its own folder under ui/widgets/ and zero loose .py files remain."""
        widgets_dir = pathlib.Path(__file__).resolve().parent.parent / "ui" / "widgets"
        expected_navbar_folders = {
            "dashboard",            # 0: Tableau de Bord
            "master_data",          # 1: Données de Base
            "clients",              # 16: Clients
            "procurement",          # 2: Achats & Entrées
            "inventory",            # 3: Stock & Magasin
            "reclamation",          # 8: Réclamations
            "appliance_desks",      # 14: Bureaux
            "versement",            # 17: Versement
            "paiement_livraison",   # 18: Paiement Livraison
            "sav",                  # 15: SAV
            "history",              # 7: Traçabilité
            "users",                # 5: Utilisateurs
            "settings",             # 4: Paramètres
        }
        actual_dirs = {p.name for p in widgets_dir.iterdir() if p.is_dir() and not p.name.startswith("__")}
        self.assertEqual(actual_dirs, expected_navbar_folders)
        loose_py_files = [p.name for p in widgets_dir.glob("*.py") if p.name != "__init__.py"]
        self.assertEqual(loose_py_files, [])

    def test_visual_fixes_and_bl_advance_overpayment_change(self):
        """Verifies ClientWalletDialog QFrame scoping, OrderDesk column/button fixes, and BL advance overpayment handling."""
        dm = MagicMock()
        dm.clients.get_all_clients.return_value = [{"Client_ID": 1, "Client_Name": "Client A", "Phone": "0550"}]
        dm.bonds.get_client_wallet.return_value = {
            "current_balance": 0.0,
            "real_deposit_balance": 0.0,
            "virtual_credit_balance": 0.0,
        }
        dm.bonds.get_client_wallet_transactions.return_value = []
        dm.serials.get_catalog_with_theoretical_stock.return_value = []

        w_dlg = ClientWalletDialog(data_manager=dm, default_client_id=1)
        for card in (w_dlg.card_real, w_dlg.card_virt, w_dlg.card_tot):
            self.assertTrue(bool(card.objectName()))
            self.assertIn(f"QFrame#{card.objectName()}", card.styleSheet())
            self.assertIn("border: none", card.styleSheet())
        w_dlg.deleteLater()

        desk = OrderDeskWidget(data_manager=dm)
        self.assertGreaterEqual(desk.table.columnWidth(4), 56)
        self.assertGreaterEqual(desk.table.columnWidth(5), 60)
        new_sess_btn = next(b for b in desk.findChildren(QPushButton) if "Nouvelle Session" in b.text())
        self.assertTrue(new_sess_btn.icon().isNull())
        desk.deleteLater()

        # Verify validate_bon_livraison_advance caps cash at Total TTC and returns change_due without raising
        from test.test_financial_isolation_and_bon_credit import FinancialAndSAVMockDB
        mock_db = FinancialAndSAVMockDB()
        bond_mgr = BondLifecycleManager(mock_db)
        res = bond_mgr.validate_bon_livraison_advance(
            order_id=301,  # Total TTC = 75,000.00 DA
            cashier_user_id=5,
            cash_session_id=1,
            advance_cash=Decimal("80000.00"),
            advance_wallet=Decimal("0.00"),
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["advance_paid"], 75000.0)
        self.assertEqual(res["change_due"], 5000.0)
        self.assertEqual(res["remaining_on_delivery"], 0.0)


if __name__ == "__main__":
    unittest.main()
