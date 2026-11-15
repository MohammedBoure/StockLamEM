# -*- coding: utf-8 -*-
"""Tests for Task #8: Standalone Paiement Livraison management workspace and COD payment lifecycle."""

import os
import sys
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PYTEST_CURRENT_TEST"] = "1"

from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from database.bond_lifecycle_manager import BondLifecycleManager
from ui.widgets.paiement_livraison import PaiementLivraisonTab
from ui.widgets.versement import BonPaymentAddDialog, BonPaymentsManageDialog

app = QApplication.instance() or QApplication(sys.argv)


class _FakeLivraisonCursor:
    def __init__(self, state):
        self.state = state
        self.lastrowid = 1
        self._results = []

    def execute(self, query, params=None):
        sql = " ".join(query.split())
        params = params or ()

        if "FROM Sales_Orders_Theoretical WHERE Order_ID = %s FOR UPDATE" in sql:
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
        elif sql.startswith("UPDATE Sales_Invoices SET Amount_Remaining_Credit = %s, Status = %s, Delivery_Status = %s"):
            rem, st, dst, iid = params
            self.state["invoices"][int(iid)]["Amount_Remaining_Credit"] = rem
            self.state["invoices"][int(iid)]["Status"] = st
            self.state["invoices"][int(iid)]["Delivery_Status"] = dst
        elif sql.startswith("UPDATE Sales_Invoices SET Amount_Remaining_Credit = %s, Status = %s WHERE Invoice_ID = %s"):
            rem, st, iid = params
            self.state["invoices"][int(iid)]["Amount_Remaining_Credit"] = rem
            self.state["invoices"][int(iid)]["Status"] = st
        elif sql.startswith("UPDATE Sales_Orders_Theoretical SET Status = 'COMPLETED'"):
            self.state["orders"][int(params[0])]["Status"] = "COMPLETED"
        elif sql.startswith("UPDATE Clients SET Current_Debt"):
            self.state["debt_touched"] = True
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
        return _FakeLivraisonCursor(self.state)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


class TestPaiementLivraisonTab(unittest.TestCase):
    def tearDown(self):
        app.processEvents()

    def test_paiement_livraison_tab_mirrors_versement_for_bon_livraison(self):
        sample_bons = [
            {
                "Order_ID": 201,
                "Order_Number": "3-BLV-20261116-00201",
                "Client_ID": 15,
                "Client_Name": "EURL Maison",
                "Client_Phone": "0555001122",
                "Delivery_Address": "Alger Centre",
                "Bond_Type": "BON_LIVRAISON",
                "Total_Amount_TTC": 120000.0,
                "Total_Paid": 20000.0,
                "Remaining_Amount": 100000.0,
                "Payments_Count": 1,
                "Payment_State": "PARTIAL",
                "Order_Date": "2026-11-16 09:00:00",
                "Invoice_ID": 601,
                "Invoice_No": "BL-LIV-20261116-201",
            },
            {
                "Order_ID": 202,
                "Order_Number": "3-BLV-20261116-00202",
                "Client_ID": 16,
                "Client_Name": "Mme Salima",
                "Client_Phone": "0770334455",
                "Delivery_Address": "Blida",
                "Bond_Type": "BON_LIVRAISON",
                "Total_Amount_TTC": 80000.0,
                "Total_Paid": 80000.0,
                "Remaining_Amount": 0.0,
                "Payments_Count": 2,
                "Payment_State": "PAID",
                "Order_Date": "2026-11-15 16:20:00",
                "Invoice_ID": 602,
                "Invoice_No": "BL-LIV-20261116-202",
            },
        ]

        dm = MagicMock()
        dm.bonds = MagicMock()
        dm.bonds.get_bons_with_payments.return_value = sample_bons

        tab = PaiementLivraisonTab(data_manager=dm, current_user={"User_ID": 4})
        app.processEvents()

        dm.bonds.get_bons_with_payments.assert_called_with(bond_type="BON_LIVRAISON")
        self.assertEqual(tab.lbl_title.text(), "Gestion des Paiements Livraison")
        self.assertEqual(tab.bons_table.rowCount(), 2)
        self.assertEqual(tab.lbl_kpi_count.text(), "2")

        # Every row has '+ Paiement' and 'Modifier' buttons
        for r in range(2):
            cell = tab.bons_table.cellWidget(r, 9)
            add_btn = cell.findChild(QPushButton, "btn_row_add")
            edit_btn = cell.findChild(QPushButton, "btn_row_edit")
            self.assertEqual(add_btn.text(), "+ Paiement")
            self.assertEqual(edit_btn.text(), "Modifier")
            self.assertEqual(add_btn.isEnabled(), r == 0)

        # Search by delivery address works
        tab.txt_search.setText("Alger Centre")
        app.processEvents()
        self.assertEqual(tab.bons_table.rowCount(), 1)
        self.assertEqual(tab.bons_table.item(0, 0).text(), "3-BLV-20261116-00201")

        tab.deleteLater()

    def test_add_and_manage_dialogs_work_for_bon_livraison(self):
        dm = MagicMock()
        dm.bonds = MagicMock()
        dm.bonds.add_payment_to_bon.return_value = {"success": True}

        bon = {
            "Order_ID": 201,
            "Order_Number": "3-BLV-20261116-00201",
            "Client_Name": "EURL Maison",
            "Total_Amount_TTC": 120000.0,
            "Total_Paid": 20000.0,
            "Remaining_Amount": 100000.0,
        }
        add_dlg = BonPaymentAddDialog(
            data_manager=dm,
            bon_data=bon,
            current_user={"User_ID": 4},
            dialog_title="Ajouter un Paiement Livraison",
        )
        add_dlg.txt_amount.setValue(45000.0)
        add_dlg.method_buttons["CCP"].click()
        add_dlg.btn_save.click()
        app.processEvents()

        kw = dm.bonds.add_payment_to_bon.call_args.kwargs
        self.assertEqual(kw["order_id"], 201)
        self.assertEqual(kw["amount"], Decimal("45000.00"))
        self.assertEqual(kw["payment_method"], "CCP")
        add_dlg.deleteLater()

        dm.bonds.get_bon_payments.return_value = {
            "bon": {**bon, "Invoice_No": "BL-LIV-201"},
            "payments": [
                {
                    "entry_type": "CLIENT_PAYMENT",
                    "payment_id": 91,
                    "payment_date": "2026-11-16",
                    "amount": 45000.0,
                    "payment_method": "CCP",
                    "notes": "Paiement livraison",
                    "editable": True,
                    "deletable": True,
                }
            ],
        }
        dm.bonds.update_bon_payment.return_value = {"success": True}
        mgr_dlg = BonPaymentsManageDialog(
            data_manager=dm,
            order_id=201,
            dialog_title="Gérer les Paiements du Bon de Livraison",
        )
        row0 = mgr_dlg.table.cellWidget(0, 5)
        edit_btn = next(b for b in row0.findChildren(QPushButton) if b.text() == "Modifier")
        edit_btn.click()
        app.processEvents()

        mgr_dlg.edit_amount.setValue(50000.0)
        mgr_dlg.btn_save_edit.click()
        app.processEvents()
        self.assertEqual(dm.bonds.update_bon_payment.call_args.kwargs["new_amount"], Decimal("50000.00"))
        mgr_dlg.deleteLater()

    def test_backend_bon_livraison_cod_completion_without_client_debt_mutation(self):
        state = {
            "orders": {
                201: {
                    "Order_ID": 201,
                    "Order_Number": "3-BLV-20261116-00201",
                    "Client_ID": 15,
                    "Bond_Type": "BON_LIVRAISON",
                    "Total_Amount_TTC": Decimal("120000.00"),
                    "Status": "DISPATCHED_PENDING_COD",
                }
            },
            "invoices": {
                601: {
                    "Invoice_ID": 601,
                    "Invoice_No": "BL-LIV-20261116-201",
                    "Order_ID": 201,
                    "Client_ID": 15,
                    "Status": "Validated",
                    "Payment_Method": "Cash",
                    "Amount_Paid_Cash": Decimal("20000.00"),
                    "Amount_Paid_Card": Decimal("0.00"),
                    "Amount_Paid_Wallet": Decimal("0.00"),
                    "Amount_Remaining_Credit": Decimal("100000.00"),
                    "Delivery_Status": "OUT_FOR_DELIVERY",
                }
            },
            "payments": {},
            "next_pay_id": 900,
            "debt_touched": False,
        }
        mock_db = MagicMock(spec=["get_raw_connection"])
        mock_db.get_raw_connection.side_effect = lambda: _FakeConn(state)
        mgr = BondLifecycleManager(mock_db)

        res = mgr.add_payment_to_bon(
            order_id=201,
            amount=Decimal("100000.00"),
            payment_method="Cash",
            payment_date="2026-11-16",
            notes="Solde COD à la livraison",
            user_id=4,
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["remaining_amount"], 0.0)
        self.assertEqual(state["invoices"][601]["Status"], "Paid")
        self.assertEqual(state["invoices"][601]["Delivery_Status"], "DELIVERED_PAID")
        self.assertEqual(state["orders"][201]["Status"], "COMPLETED")
        self.assertFalse(state["debt_touched"])


if __name__ == "__main__":
    unittest.main()
