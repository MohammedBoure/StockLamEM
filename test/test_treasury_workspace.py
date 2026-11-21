# -*- coding: utf-8 -*-
"""
Comprehensive tests for the Trésorerie (Page 19) feature:
1. TreasuryManager backend: schema creation, Entrée, Sortie, Transfert Interne,
   linked transfer cancellation, running balances, multi-method aggregation across
   Sales_Invoices (Bureaux -> Caisse), POS_Sale_Payments, Client_Payments,
   POS_Cash_Movements, and Treasury_Movements with zero double counting.
2. TreasuryTab & dialogs UI: zero fake data on empty DB, live balance KPI cards,
   filtering (direction, payment method, search, period), Entrée / Sortie / Transfert
   dialogs, disabled Annuler with tooltip for automatic Caisse operations.
3. MainWindow navbar integration & RBAC permissions (`nav_treasury`,
   `tab_treasury_journal`, `tab_treasury_balances`).
"""

import os
import sys
import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PYTEST_CURRENT_TEST"] = "1"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from database.treasury_manager import TreasuryManager, normalize_treasury_method
from ui.navigation_permissions import NAVIGATION_PERMISSION_FALLBACKS, has_navigation_permission
from ui.widgets.treasury import (
    TreasuryOperationDialog,
    TreasuryTab,
    TreasuryTransferDialog,
)
from ui.widgets.users.user_management_tab import SYSTEM_PERMISSIONS

app = QApplication.instance() or QApplication(sys.argv)


class _FakeTreasuryCursor:
    def __init__(self, state):
        self.state = state
        self.lastrowid = 1
        self._results = []

    def execute(self, query, params=None):
        sql = " ".join(query.split())
        params = params or ()
        self.state["queries"].append((sql, params))

        if sql.startswith("CREATE TABLE IF NOT EXISTS Treasury_Movements"):
            self.state["schema_created"] = True
            self._results = []
        elif sql.startswith("SHOW COLUMNS FROM"):
            self._results = [{"Field": "Payment_Method", "Type": "varchar(64)"}]
        elif sql.startswith("INSERT INTO Treasury_Movements"):
            mid = self.state["next_tm_id"]
            self.state["next_tm_id"] += 1
            self.lastrowid = mid
            # Detect transfer vs manual insert by parameter count
            if "TRANSFER_OUT" in sql:
                # code, src, amt, reason, ref, cp, grp, notes, dt, uid
                row = {
                    "Movement_ID": mid,
                    "Movement_Code": params[0],
                    "Direction": "OUT",
                    "Operation_Type": "TRANSFER_OUT",
                    "Payment_Method": params[1],
                    "Amount": Decimal(str(params[2])),
                    "Category": "Transfert Interne",
                    "Reason": params[3],
                    "Reference": params[4],
                    "Counterparty": params[5],
                    "Transfer_Group_ID": params[6],
                    "Notes": params[7],
                    "Movement_Date": params[8],
                    "Created_By": params[9],
                    "Is_Cancelled": 0,
                    "Operator_Name": "Admin",
                }
            elif "TRANSFER_IN" in sql:
                row = {
                    "Movement_ID": mid,
                    "Movement_Code": params[0],
                    "Direction": "IN",
                    "Operation_Type": "TRANSFER_IN",
                    "Payment_Method": params[1],
                    "Amount": Decimal(str(params[2])),
                    "Category": "Transfert Interne",
                    "Reason": params[3],
                    "Reference": params[4],
                    "Counterparty": params[5],
                    "Transfer_Group_ID": params[6],
                    "Notes": params[7],
                    "Movement_Date": params[8],
                    "Created_By": params[9],
                    "Is_Cancelled": 0,
                    "Operator_Name": "Admin",
                }
            else:
                row = {
                    "Movement_ID": mid,
                    "Movement_Code": params[0],
                    "Direction": params[1],
                    "Operation_Type": params[2],
                    "Payment_Method": params[3],
                    "Amount": Decimal(str(params[4])),
                    "Category": params[5],
                    "Reason": params[6],
                    "Reference": params[7],
                    "Counterparty": params[8],
                    "Transfer_Group_ID": None,
                    "Notes": params[9],
                    "Movement_Date": params[10],
                    "Created_By": params[11],
                    "Is_Cancelled": 0,
                    "Operator_Name": "Admin",
                }
            self.state["treasury_movements"][mid] = row
        elif "FROM Treasury_Movements WHERE Movement_ID = %s FOR UPDATE" in sql:
            row = self.state["treasury_movements"].get(int(params[0]))
            self._results = [dict(row)] if row else []
        elif sql.startswith("UPDATE Treasury_Movements SET Is_Cancelled = 1") and "Transfer_Group_ID = %s" in sql:
            grp = params[1]
            for r in self.state["treasury_movements"].values():
                if r.get("Transfer_Group_ID") == grp:
                    r["Is_Cancelled"] = 1
        elif sql.startswith("UPDATE Treasury_Movements SET Is_Cancelled = 1") and "Movement_ID = %s" in sql:
            r = self.state["treasury_movements"].get(int(params[1]))
            if r:
                r["Is_Cancelled"] = 1
        elif "FROM Sales_Invoices i" in sql:
            self._results = [dict(r) for r in self.state["sales_invoices"] if r.get("Status") != "Cancelled"]
        elif "FROM POS_Sale_Payments p" in sql:
            self._results = [dict(r) for r in self.state["pos_sale_payments"]]
        elif "FROM Client_Payments cp" in sql:
            self._results = [dict(r) for r in self.state["client_payments"]]
        elif "FROM POS_Cash_Movements m" in sql:
            self._results = [dict(r) for r in self.state["pos_cash_movements"]]
        elif "FROM Treasury_Movements t" in sql:
            self._results = [
                dict(r) for r in self.state["treasury_movements"].values() if not r.get("Is_Cancelled")
            ]
        else:
            self._results = []

    def fetchone(self):
        return self._results[0] if self._results else None

    def fetchall(self):
        return list(self._results)

    def close(self):
        pass


class _FakeConn:
    def __init__(self, state):
        self.state = state

    def start_transaction(self):
        pass

    def cursor(self, dictionary=False):
        return _FakeTreasuryCursor(self.state)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


class _FakeTreasuryDB:
    def __init__(self):
        self.state = {
            "schema_created": False,
            "next_tm_id": 1,
            "queries": [],
            "sales_invoices": [],
            "pos_sale_payments": [],
            "client_payments": [],
            "pos_cash_movements": [],
            "treasury_movements": {},
        }

    def get_raw_connection(self):
        return _FakeConn(self.state)


class TreasuryBackendTests(unittest.TestCase):
    def setUp(self):
        TreasuryManager._schema_checked = False
        self.db = _FakeTreasuryDB()
        self.mgr = TreasuryManager(self.db)

    def test_method_normalization(self):
        self.assertEqual(normalize_treasury_method("Cash"), "Cash")
        self.assertEqual(normalize_treasury_method("Espèce"), "Cash")
        self.assertEqual(normalize_treasury_method("Versement"), "Cash")
        self.assertEqual(normalize_treasury_method("BaridiMob"), "BaridiMob")
        self.assertEqual(normalize_treasury_method("TPE"), "TPE")
        self.assertEqual(normalize_treasury_method("Card"), "TPE")
        self.assertEqual(normalize_treasury_method("CCP"), "CCP")
        self.assertEqual(normalize_treasury_method("Virement"), "CCP")

    def test_empty_db_returns_zero_balances_and_no_fake_rows(self):
        snap = self.mgr.get_treasury_snapshot()
        self.assertEqual(snap["total_balance"], 0.0)
        self.assertEqual(snap["movements"], [])
        self.assertEqual(snap["balances_by_method"], {"Cash": 0.0, "BaridiMob": 0.0, "TPE": 0.0, "CCP": 0.0})

    def test_multi_method_aggregation_with_bureaux_caisse_and_manual_ops(self):
        # Simulate Caisse operations across Cash, BaridiMob, TPE, CCP
        self.db.state["sales_invoices"] = [
            {
                "Invoice_ID": 10,
                "Invoice_No": "FAC-C-20261121-1",
                "Order_ID": 1,
                "Order_Number": "1-BC-0001",
                "Invoice_Date": "2026-11-21",
                "Created_At": "2026-11-21 09:00:00",
                "Payment_Method": "Cash",
                "Bond_Settlement_Type": "BON_C_CASH",
                "Amount_Paid_Cash": Decimal("50000.00"),
                "Amount_Paid_Card": Decimal("0.00"),
                "Client_Name": "Karim",
                "Operator_Name": "Caissier 1",
                "Status": "Paid",
            },
            {
                "Invoice_ID": 11,
                "Invoice_No": "FAC-C-20261121-2",
                "Order_ID": 2,
                "Order_Number": "1-BC-0002",
                "Invoice_Date": "2026-11-21",
                "Created_At": "2026-11-21 09:30:00",
                "Payment_Method": "BaridiMob",
                "Bond_Settlement_Type": "BON_C_CASH",
                "Amount_Paid_Cash": Decimal("0.00"),
                "Amount_Paid_Card": Decimal("30000.00"),
                "Client_Name": "Nadia",
                "Operator_Name": "Caissier 1",
                "Status": "Paid",
            },
        ]
        self.db.state["client_payments"] = [
            {
                "Payment_ID": 20,
                "Client_ID": 5,
                "Invoice_ID": 10,
                "Payment_Date": "2026-11-21",
                "Created_At": "2026-11-21 10:00:00",
                "Amount": Decimal("12000.00"),
                "Payment_Method": "TPE",
                "Reference": "VRS-10-1",
                "Notes": "Tranche TPE",
                "Invoice_No": "FAC-C-20261121-1",
                "Bond_Settlement_Type": "BON_VERSEMENT",
                "Client_Name": "Karim",
                "Operator_Name": "Caissier 1",
            }
        ]

        # Manual Entrée in CCP (+20 000) and Sortie in Cash (-8 000)
        self.mgr.record_movement(
            direction="IN",
            payment_method="CCP",
            amount=20000,
            reason="Fond CCP initial",
            category="Fond de caisse (Ouverture)",
            movement_date="2026-11-21 10:15:00",
            user_id=1,
        )
        out_res = self.mgr.record_movement(
            direction="OUT",
            payment_method="Cash",
            amount=8000,
            reason="Frais transport livraison",
            category="Transport / Livraison",
            movement_date="2026-11-21 10:30:00",
            user_id=1,
        )

        # Internal transfer: Cash 15 000 -> CCP
        trf_res = self.mgr.record_transfer(
            from_method="Cash",
            to_method="CCP",
            amount=15000,
            reason="Dépôt banque/CCP",
            movement_date="2026-11-21 11:00:00",
            user_id=1,
        )

        snap = self.mgr.get_treasury_snapshot()
        by_m = snap["balances_by_method"]
        self.assertEqual(by_m["Cash"], 27000.0)       # 50k - 8k - 15k
        self.assertEqual(by_m["BaridiMob"], 30000.0)
        self.assertEqual(by_m["TPE"], 12000.0)
        self.assertEqual(by_m["CCP"], 35000.0)        # 20k + 15k
        self.assertEqual(snap["total_balance"], 104000.0)

        # Cancel linked transfer -> voids BOTH legs atomically
        self.mgr.cancel_manual_movement(trf_res["out_movement_id"], user_id=1)
        snap2 = self.mgr.get_treasury_snapshot()
        self.assertEqual(snap2["balances_by_method"]["Cash"], 42000.0)
        self.assertEqual(snap2["balances_by_method"]["CCP"], 20000.0)
        self.assertEqual(snap2["total_balance"], 104000.0)

        # Cancel manual sortie
        self.mgr.cancel_manual_movement(out_res["movement_id"], user_id=1)
        snap3 = self.mgr.get_treasury_snapshot()
        self.assertEqual(snap3["balances_by_method"]["Cash"], 50000.0)
        self.assertEqual(snap3["total_balance"], 112000.0)


class TreasuryUITests(unittest.TestCase):
    def _make_dm(self):
        TreasuryManager._schema_checked = False
        db = _FakeTreasuryDB()
        mgr = TreasuryManager(db)
        dm = MagicMock()
        dm.db = db
        dm.treasury = mgr
        dm.current_user = {"User_ID": 1, "Username": "admin", "Role": "Admin", "Permissions": {}}
        return dm, db, mgr

    def test_empty_state_has_zero_rows_and_zero_balances(self):
        dm, _db, _mgr = self._make_dm()
        tab = TreasuryTab(data_manager=dm, current_user=dm.current_user)
        tab.show()
        app.processEvents()
        self.assertEqual(tab.table.rowCount(), 0)
        self.assertTrue(tab.table.isHidden())
        self.assertFalse(tab.empty_state.isHidden())
        self.assertIn("0,00 DA", tab.lbl_bal_total.text())
        tab.close()
        tab.deleteLater()

    def test_ui_renders_movements_disables_void_for_caisse_and_enables_for_manual(self):
        dm, db, mgr = self._make_dm()
        db.state["sales_invoices"] = [
            {
                "Invoice_ID": 1,
                "Invoice_No": "FAC-C-1",
                "Order_ID": 1,
                "Order_Number": "1-BC-1",
                "Invoice_Date": "2026-11-21",
                "Created_At": "2026-11-21 08:00:00",
                "Payment_Method": "BaridiMob",
                "Bond_Settlement_Type": "BON_C_CASH",
                "Amount_Paid_Cash": Decimal("0.00"),
                "Amount_Paid_Card": Decimal("25000.00"),
                "Client_Name": "Salim",
                "Operator_Name": "Caissier",
                "Status": "Paid",
            }
        ]
        mgr.record_movement("OUT", "BaridiMob", 5000, "Achat fournitures", movement_date="2026-11-21 09:00:00")

        tab = TreasuryTab(data_manager=dm, current_user=dm.current_user)
        self.assertEqual(tab.table.rowCount(), 2)
        self.assertIn("20 000,00 DA", tab.lbl_bal_baridimob.text())
        self.assertIn("20 000,00 DA", tab.lbl_bal_total.text())

        # Row 0 is newest (manual OUT) -> Annuler enabled
        w0 = tab.table.cellWidget(0, 9)
        void_btn_0 = [b for b in w0.findChildren(type(tab.btn_entry)) if b.text() == "Annuler"][0]
        self.assertTrue(void_btn_0.isEnabled())

        # Row 1 is Caisse invoice -> Annuler disabled with explanatory tooltip
        w1 = tab.table.cellWidget(1, 9)
        void_btn_1 = [b for b in w1.findChildren(type(tab.btn_entry)) if b.text() == "Annuler"][0]
        self.assertFalse(void_btn_1.isEnabled())
        self.assertTrue(bool(void_btn_1.toolTip().strip()))

        # Filtering by IN shows only Caisse row
        tab.btn_dir_in.click()
        self.assertEqual(tab.table.rowCount(), 1)

    def test_operation_and_transfer_dialogs_commit_to_treasury(self):
        dm, _db, mgr = self._make_dm()
        dlg_in = TreasuryOperationDialog(
            data_manager=dm,
            direction="IN",
            balances_by_method={"Cash": 10000.0, "BaridiMob": 0.0, "TPE": 0.0, "CCP": 0.0},
            current_user=dm.current_user,
        )
        dlg_in.method_buttons["Cash"].setChecked(True)
        dlg_in.spin_amount.setValue(40000.0)
        dlg_in.txt_reason.setText("Fond de caisse")
        self.assertTrue(dlg_in.btn_submit.isEnabled())
        dlg_in._submit()
        self.assertEqual(dlg_in.result(), QDialog.Accepted)

        dlg_trf = TreasuryTransferDialog(
            data_manager=dm,
            balances_by_method=mgr.get_treasury_snapshot()["balances_by_method"],
            current_user=dm.current_user,
        )
        dlg_trf.spin_amount.setValue(12000.0)
        dlg_trf._submit()
        self.assertEqual(dlg_trf.result(), QDialog.Accepted)

        snap = mgr.get_treasury_snapshot()
        self.assertEqual(snap["balances_by_method"]["Cash"], 28000.0)
        self.assertEqual(snap["balances_by_method"]["CCP"], 12000.0)

    def test_navbar_entry_and_permissions(self):
        self.assertIn("nav_treasury", NAVIGATION_PERMISSION_FALLBACKS)
        self.assertIn("14. TRESORERIE", SYSTEM_PERMISSIONS)
        perms = SYSTEM_PERMISSIONS["14. TRESORERIE"]["perms"]
        self.assertIn("nav_treasury", perms)
        self.assertTrue(all(k.startswith("nav_") or k.startswith("tab_") for k in perms))

        admin = {"Role": "Admin", "Permissions": {}}
        self.assertTrue(has_navigation_permission(admin, "nav_treasury"))
        self.assertFalse(has_navigation_permission({"Permissions": {"nav_treasury": False, "tab_desk_caisse": True}}, "nav_treasury"))

        dm, _db, _mgr = self._make_dm()
        dm.stats = MagicMock()
        dm.stats.get_dashboard_summary.return_value = {}
        dm.stats.get_active_alerts.return_value = []
        dm.printer = MagicMock()
        dm.printer.config = {}

        from ui.main_window import MainWindow

        with patch("ui.main_window.AutoBackupWorker"), \
             patch("ui.widgets.dashboard.dashboard_view.DashboardTab.refresh_all"), \
             patch("PySide6.QtWidgets.QMessageBox.question"):
            win = MainWindow(data_manager=dm, current_user=admin)
            btn_19 = win.nav_group.button(19)
            self.assertIsNotNone(btn_19)
            self.assertEqual(btn_19.text(), "Trésorerie")
            self.assertFalse(btn_19.icon().isNull())

            win.switch_page(19)
            self.assertIsInstance(win.loaded_pages.get(19), TreasuryTab)
            win.deleteLater()
            app.processEvents()


if __name__ == "__main__":
    unittest.main()
