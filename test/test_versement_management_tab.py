# -*- coding: utf-8 -*-
"""Tests for Task #7: Standalone Versement management workspace and backend methods."""

import os
import sys
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PYTEST_CURRENT_TEST"] = "1"

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QPushButton

from database.bond_lifecycle_manager import BondLifecycleManager
from ui.widgets.versement import (
    BonPaymentAddDialog,
    BonPaymentsManageDialog,
    VersementTab,
)

app = QApplication.instance() or QApplication(sys.argv)


class _FakeVersementCursor:
    def __init__(self, state):
        self.state = state
        self.lastrowid = 1
        self._results = []

    def execute(self, query, params=None):
        sql = " ".join(query.split())
        self.state["queries"].append((sql, params))
        params = params or ()

        if "SELECT o.Order_ID, o.Order_Number, o.Client_ID" in sql and "WHERE o.Bond_Type = %s" in sql:
            self._results = list(self.state.get("queue_rows", []))
        elif "FROM Sales_Orders_Theoretical WHERE Order_ID = %s FOR UPDATE" in sql:
            oid = int(params[0])
            order = self.state["orders"].get(oid)
            self._results = [dict(order)] if order else []
        elif "FROM Sales_Invoices WHERE Order_ID = %s AND Status != 'Cancelled' LIMIT 1 FOR UPDATE" in sql:
            oid = int(params[0])
            inv = next(
                (v for v in self.state["invoices"].values() if int(v["Order_ID"]) == oid and v["Status"] != "Cancelled"),
                None,
            )
            self._results = [dict(inv)] if inv else []
        elif "SELECT COALESCE(SUM(Amount), 0.00) AS Sub_Total FROM Client_Payments WHERE Invoice_ID = %s" in sql:
            iid = int(params[0])
            tot = sum(Decimal(str(p["Amount"])) for p in self.state["payments"].values() if int(p["Invoice_ID"]) == iid)
            self._results = [{"Sub_Total": tot}]
        elif "INSERT INTO Sales_Invoices" in sql:
            new_id = self.state["next_inv_id"]
            self.state["next_inv_id"] += 1
            self.lastrowid = new_id
            self.state["invoices"][new_id] = {
                "Invoice_ID": new_id,
                "Invoice_No": params[0],
                "Order_ID": int(params[1]),
                "Client_ID": int(params[2]),
                "Invoice_Date": params[3],
                "Status": params[4],
                "Total_Amount_TTC": params[7],
                "Payment_Method": params[10],
                "Amount_Paid_Cash": params[12],
                "Amount_Paid_Card": params[13],
                "Amount_Paid_Wallet": Decimal("0.00"),
                "Amount_Remaining_Credit": params[14],
                "Delivery_Status": params[15],
            }
        elif "INSERT INTO Client_Payments" in sql:
            new_pid = self.state["next_pay_id"]
            self.state["next_pay_id"] += 1
            self.lastrowid = new_pid
            self.state["payments"][new_pid] = {
                "Payment_ID": new_pid,
                "Client_ID": int(params[0]),
                "Invoice_ID": int(params[1]),
                "Payment_Date": params[2],
                "Amount": Decimal(str(params[3])),
                "Payment_Method": params[4],
                "Reference": params[5],
                "Notes": params[6],
            }
        elif "SELECT Payment_ID, Amount FROM Client_Payments WHERE Payment_ID = %s AND Invoice_ID = %s FOR UPDATE" in sql:
            pid, iid = int(params[0]), int(params[1])
            row = self.state["payments"].get(pid)
            self._results = [dict(row)] if row and int(row["Invoice_ID"]) == iid else []
        elif sql.startswith("UPDATE Client_Payments SET Amount = %s"):
            amt, method, pdate, notes, pid = params
            row = self.state["payments"][int(pid)]
            row["Amount"] = Decimal(str(amt))
            row["Payment_Method"] = method
            row["Payment_Date"] = pdate
            row["Notes"] = notes
        elif sql.startswith("DELETE FROM Client_Payments WHERE Payment_ID = %s"):
            self.state["payments"].pop(int(params[0]), None)
        elif sql.startswith("UPDATE Sales_Invoices SET Amount_Remaining_Credit = %s, Status = %s WHERE Invoice_ID = %s"):
            rem, st, iid = params
            self.state["invoices"][int(iid)]["Amount_Remaining_Credit"] = rem
            self.state["invoices"][int(iid)]["Status"] = st
        elif sql.startswith("UPDATE Sales_Invoices SET Amount_Remaining_Credit = %s, Status = %s, Delivery_Status = %s"):
            rem, st, dst, iid = params
            self.state["invoices"][int(iid)]["Amount_Remaining_Credit"] = rem
            self.state["invoices"][int(iid)]["Status"] = st
            self.state["invoices"][int(iid)]["Delivery_Status"] = dst
        elif sql.startswith("UPDATE Sales_Invoices SET Amount_Paid_Cash = %s"):
            cash_c, card_c, pm, rem, st, iid = params
            inv = self.state["invoices"][int(iid)]
            inv["Amount_Paid_Cash"] = cash_c
            inv["Amount_Paid_Card"] = card_c
            inv["Payment_Method"] = pm
            inv["Amount_Remaining_Credit"] = rem
            inv["Status"] = st
        elif sql.startswith("UPDATE Sales_Orders_Theoretical SET Status = %s"):
            st, oid = params
            self.state["orders"][int(oid)]["Status"] = st
        elif sql.startswith("UPDATE Clients SET Current_Debt"):
            amt, cid = Decimal(str(params[0])), int(params[1])
            if "+ %s" in sql:
                self.state["debts"][cid] = self.state["debts"].get(cid, Decimal("0.00")) + amt
            else:
                self.state["debts"][cid] = max(Decimal("0.00"), self.state["debts"].get(cid, Decimal("0.00")) - amt)
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
        self.committed = False

    def start_transaction(self):
        pass

    def cursor(self, dictionary=False):
        return _FakeVersementCursor(self.state)

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TestVersementManagementTab(unittest.TestCase):
    def tearDown(self):
        app.processEvents()

    def test_versement_tab_displays_bons_kpis_filters_and_per_row_buttons(self):
        sample_bons = [
            {
                "Order_ID": 101,
                "Order_Number": "4-VRS-20261116-00101",
                "Client_ID": 10,
                "Client_Name": "SARL Electro",
                "Client_Phone": "0550123456",
                "Bond_Type": "BON_VERSEMENT",
                "Total_Amount_TTC": 100000.0,
                "Total_Paid": 30000.0,
                "Remaining_Amount": 70000.0,
                "Payments_Count": 1,
                "Payment_State": "PARTIAL",
                "Order_Date": "2026-11-16 10:00:00",
                "Invoice_ID": 501,
                "Invoice_No": "FAC-VRS-20261116-101",
            },
            {
                "Order_ID": 102,
                "Order_Number": "4-VRS-20261116-00102",
                "Client_ID": 11,
                "Client_Name": "Mme Amina",
                "Client_Phone": "0661998877",
                "Bond_Type": "BON_VERSEMENT",
                "Total_Amount_TTC": 50000.0,
                "Total_Paid": 50000.0,
                "Remaining_Amount": 0.0,
                "Payments_Count": 2,
                "Payment_State": "PAID",
                "Order_Date": "2026-11-15 15:30:00",
                "Invoice_ID": 502,
                "Invoice_No": "FAC-VRS-20261116-102",
            },
        ]

        dm = MagicMock()
        dm.bonds = MagicMock()
        dm.bonds.get_bons_with_payments.return_value = sample_bons

        tab = VersementTab(data_manager=dm, current_user={"User_ID": 1})
        app.processEvents()

        dm.bonds.get_bons_with_payments.assert_called_with(bond_type="BON_VERSEMENT")
        self.assertEqual(tab.bons_table.rowCount(), 2)
        self.assertEqual(tab.lbl_kpi_count.text(), "2")
        self.assertIn("150", tab.lbl_kpi_total.text())
        self.assertIn("80", tab.lbl_kpi_paid.text())
        self.assertIn("70", tab.lbl_kpi_rem.text())

        # Every row has direct '+ Versement' and 'Modifier' buttons
        for r in range(2):
            cell = tab.bons_table.cellWidget(r, 9)
            self.assertIsNotNone(cell)
            add_btn = cell.findChild(QPushButton, "btn_row_add")
            edit_btn = cell.findChild(QPushButton, "btn_row_edit")
            self.assertIsNotNone(add_btn)
            self.assertIsNotNone(edit_btn)
            self.assertEqual(add_btn.text(), "+ Versement")
            self.assertEqual(edit_btn.text(), "Modifier")
            self.assertEqual(add_btn.isEnabled(), r == 0)

        # Filter by pending vs paid & search
        tab.btn_filter_pending.click()
        app.processEvents()
        self.assertEqual(tab.bons_table.rowCount(), 1)
        self.assertEqual(tab.bons_table.item(0, 0).text(), "4-VRS-20261116-00101")

        tab.btn_filter_paid.click()
        app.processEvents()
        self.assertEqual(tab.bons_table.rowCount(), 1)
        self.assertEqual(tab.bons_table.item(0, 0).text(), "4-VRS-20261116-00102")

        tab.btn_filter_all.click()
        tab.txt_search.setText("Electro")
        app.processEvents()
        self.assertEqual(tab.bons_table.rowCount(), 1)
        self.assertEqual(tab.bons_table.item(0, 0).text(), "4-VRS-20261116-00101")

        tab.deleteLater()

    def test_add_payment_dialog_validation_and_submission(self):
        dm = MagicMock()
        dm.bonds = MagicMock()
        dm.bonds.add_payment_to_bon.return_value = {"success": True, "amount_added": 25000.0}

        bon = {
            "Order_ID": 101,
            "Order_Number": "4-VRS-20261116-00101",
            "Client_Name": "SARL Electro",
            "Total_Amount_TTC": 100000.0,
            "Total_Paid": 30000.0,
            "Remaining_Amount": 70000.0,
        }
        dlg = BonPaymentAddDialog(data_manager=dm, bon_data=bon, current_user={"User_ID": 7})
        app.processEvents()

        # Default amount pre-filled to remaining due
        self.assertEqual(dlg.txt_amount.value(), 70000.0)
        self.assertTrue(dlg.btn_save.isEnabled())

        # Overpayment blocked cleanly
        dlg.txt_amount.setValue(90000.0)
        app.processEvents()
        self.assertFalse(dlg.btn_save.isEnabled())
        self.assertFalse(dlg.lbl_error.isHidden())

        # Valid installment via BaridiMob
        dlg.txt_amount.setValue(25000.0)
        dlg.method_buttons["BaridiMob"].click()
        dlg.txt_notes.setText("Tranche 2")
        app.processEvents()
        self.assertTrue(dlg.btn_save.isEnabled())

        dlg.btn_save.click()
        app.processEvents()
        dm.bonds.add_payment_to_bon.assert_called_once()
        kw = dm.bonds.add_payment_to_bon.call_args.kwargs
        self.assertEqual(kw["order_id"], 101)
        self.assertEqual(kw["amount"], Decimal("25000.00"))
        self.assertEqual(kw["payment_method"], "BaridiMob")
        self.assertEqual(kw["notes"], "Tranche 2")
        self.assertEqual(kw["user_id"], 7)

        dlg.deleteLater()

    def test_manage_payments_dialog_edit_and_delete(self):
        dm = MagicMock()
        dm.bonds = MagicMock()
        dm.bonds.get_bon_payments.return_value = {
            "bon": {
                "Order_ID": 101,
                "Order_Number": "4-VRS-20261116-00101",
                "Client_Name": "SARL Electro",
                "Invoice_No": "FAC-VRS-101",
                "Total_Amount_TTC": 100000.0,
                "Total_Paid": 60000.0,
                "Remaining_Amount": 40000.0,
            },
            "payments": [
                {
                    "entry_type": "INVOICE_INITIAL",
                    "payment_id": None,
                    "payment_date": "2026-11-15",
                    "amount": 35000.0,
                    "payment_method": "Cash",
                    "notes": "Paiement initial Caisse",
                    "editable": True,
                    "deletable": False,
                },
                {
                    "entry_type": "CLIENT_PAYMENT",
                    "payment_id": 88,
                    "payment_date": "2026-11-16",
                    "amount": 25000.0,
                    "payment_method": "BaridiMob",
                    "notes": "Tranche 2",
                    "editable": True,
                    "deletable": True,
                },
            ],
        }
        dm.bonds.update_bon_payment.return_value = {"success": True}
        dm.bonds.delete_bon_payment.return_value = {"success": True}

        dlg = BonPaymentsManageDialog(data_manager=dm, order_id=101)
        app.processEvents()

        self.assertEqual(dlg.table.rowCount(), 2)
        self.assertTrue(dlg.edit_card.isHidden())

        # Edit second row (CLIENT_PAYMENT #88)
        row1_widget = dlg.table.cellWidget(1, 5)
        edit_btn = next(b for b in row1_widget.findChildren(QPushButton) if b.text() == "Modifier")
        edit_btn.click()
        app.processEvents()

        self.assertFalse(dlg.edit_card.isHidden())
        self.assertEqual(dlg.edit_amount.value(), 25000.0)

        dlg.edit_amount.setValue(30000.0)
        dlg.edit_notes.setText("Tranche 2 ajustée")
        dlg.btn_save_edit.click()
        app.processEvents()

        dm.bonds.update_bon_payment.assert_called_once()
        ukw = dm.bonds.update_bon_payment.call_args.kwargs
        self.assertEqual(ukw["order_id"], 101)
        self.assertEqual(ukw["entry_type"], "CLIENT_PAYMENT")
        self.assertEqual(ukw["payment_id"], 88)
        self.assertEqual(ukw["new_amount"], Decimal("30000.00"))
        self.assertTrue(dlg.has_changes)

        # Delete second row with mocked confirmation
        row1_widget = dlg.table.cellWidget(1, 5)
        del_btn = next(b for b in row1_widget.findChildren(QPushButton) if b.text() == "")
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            del_btn.click()
            app.processEvents()

        dm.bonds.delete_bon_payment.assert_called_once_with(101, 88)
        dlg.deleteLater()

    def test_backend_bon_payment_lifecycle_add_update_delete(self):
        state = {
            "orders": {
                101: {
                    "Order_ID": 101,
                    "Order_Number": "4-VRS-20261116-00101",
                    "Client_ID": 10,
                    "Bond_Type": "BON_VERSEMENT",
                    "Total_Amount_TTC": Decimal("100000.00"),
                    "Status": "CONFIRMED_PENDING_PAYMENT",
                }
            },
            "invoices": {},
            "payments": {},
            "debts": {10: Decimal("0.00")},
            "next_inv_id": 500,
            "next_pay_id": 800,
            "queries": [],
        }
        mock_db = MagicMock(spec=["get_raw_connection", "get_db_connection"])
        mock_db.get_raw_connection.side_effect = lambda: _FakeConn(state)
        mock_db.get_db_connection.side_effect = lambda: _FakeConn(state)
        mgr = BondLifecycleManager(mock_db)

        # 1. First payment creates Sales_Invoices + moves status + sets debt remainder
        res1 = mgr.add_payment_to_bon(
            order_id=101,
            amount=Decimal("40000.00"),
            payment_method="Cash",
            payment_date="2026-11-16",
            notes="Acompte 1",
            user_id=2,
        )
        self.assertTrue(res1["success"])
        self.assertEqual(res1["remaining_amount"], 60000.0)
        self.assertEqual(state["orders"][101]["Status"], "PAID_PENDING_DISPATCH")
        self.assertEqual(state["debts"][10], Decimal("60000.00"))

        # 2. Second payment inserts Client_Payments + decreases remaining & debt
        res2 = mgr.add_payment_to_bon(
            order_id=101,
            amount=Decimal("25000.00"),
            payment_method="BaridiMob",
            payment_date="2026-11-16",
            notes="Acompte 2",
            user_id=2,
        )
        self.assertEqual(res2["remaining_amount"], 35000.0)
        self.assertEqual(state["debts"][10], Decimal("35000.00"))
        pid = res2["payment_id"]
        self.assertIsNotNone(pid)

        # 3. Update second payment up to 35000 -> remaining drops to 25000
        res_upd = mgr.update_bon_payment(
            order_id=101,
            entry_type="CLIENT_PAYMENT",
            payment_id=pid,
            new_amount=Decimal("35000.00"),
            payment_method="CCP",
            payment_date="2026-11-16",
            notes="Ajusté",
        )
        self.assertEqual(res_upd["remaining_amount"], 25000.0)
        self.assertEqual(state["debts"][10], Decimal("25000.00"))

        # 4. Over-limit edit raises ValueError
        with self.assertRaises(ValueError):
            mgr.update_bon_payment(
                order_id=101,
                entry_type="CLIENT_PAYMENT",
                payment_id=pid,
                new_amount=Decimal("70000.00"),
            )

        # 5. Delete second payment -> remaining returns to 60000
        res_del = mgr.delete_bon_payment(order_id=101, payment_id=pid)
        self.assertEqual(res_del["remaining_amount"], 60000.0)
        self.assertEqual(state["debts"][10], Decimal("60000.00"))

    def test_ensure_bond_enum_schema_adds_bon_versement_when_missing(self):
        executed = []

        class _EnumCursor:
            def __init__(self):
                self._row = None

            def execute(self, sql, params=None):
                executed.append((sql, params))
                if sql.startswith("SHOW COLUMNS FROM Sales_Orders_Theoretical LIKE") and params == ("Bond_Type",):
                    self._row = {"Type": "enum('BON_C','BON_CREDIT','BON_LIVRAISON')"}
                elif sql.startswith("SHOW COLUMNS FROM Sales_Orders_Theoretical LIKE") and params == ("Payment_Method_Requested",):
                    self._row = {"Type": "enum('CASH','CREDIT','LIVRAISON_COD','CARD','WALLET_AVOIR','MIXED')"}
                elif sql.startswith("SHOW COLUMNS FROM Sales_Invoices LIKE") and params == ("Bond_Settlement_Type",):
                    self._row = {"Type": "enum('BON_C_CASH','BON_CREDIT','BON_LIVRAISON','BON_WALLET_AVOIR','BON_MIXED')"}
                else:
                    self._row = None

            def fetchone(self):
                return self._row

        mgr = BondLifecycleManager(MagicMock())
        cur = _EnumCursor()
        mgr._ensure_bond_enum_schema(cur)

        alters = [s for s, _ in executed if s.startswith("ALTER TABLE")]
        self.assertEqual(len(alters), 3)
        self.assertTrue(any("Bond_Type" in s and "'BON_VERSEMENT'" in s for s in alters))
        self.assertTrue(any("Payment_Method_Requested" in s and "'VERSEMENT'" in s for s in alters))
        self.assertTrue(any("Bond_Settlement_Type" in s and "'BON_VERSEMENT'" in s for s in alters))
        self.assertTrue(mgr._enum_schema_verified)

        # Cached on subsequent calls
        before_len = len(executed)
        mgr._ensure_bond_enum_schema(cur)
        self.assertEqual(len(executed), before_len)


if __name__ == "__main__":
    unittest.main()
