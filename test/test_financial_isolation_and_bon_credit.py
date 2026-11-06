# -*- coding: utf-8 -*-
"""
test/test_financial_isolation_and_bon_credit.py
===============================================
Automated Test Suite for:
1. Caisse & 6 Bond Types Lifecycle (`Bon C`, `Bon Crédit`, `Bon de Livraison`, `Versement`, `Bon de Retour`).
2. Strict Financial Isolation: `Bon de Retour` and `SAV Irreparable` issue virtual credits
   (`Versement Virtuel`) in `Client_Wallets` with ZERO physical Caisse liquidity change
   (Delta Expected_Cash == 0.00 DA), whereas real `Versement` deposits increase physical Caisse.
3. `Bon Crédit` Admin Password/PIN verification & Credit Limit Ceiling enforcement.
4. 4-Stage SAV / Réparation state machine (`SAV_RECEIVED` -> `SAV_SENT_TO_TECH` ->
   `SAV_RETURNED_FROM_TECH` -> `SAV_CLOSED_DELIVERED`) and Irreparable compensation.
"""

import hashlib
import os
import sys
from datetime import date, timedelta
from decimal import Decimal
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.bond_lifecycle_manager import (
    BondLifecycleManager,
    SecurityViolationException,
    SplitPaymentMismatchException,
)
from database.sav_workflow_manager import SAVWorkflowManager


class FinancialAndSAVMockDB:
    def __init__(self):
        self.cash_sessions = {
            1: {
                "Cash_Session_ID": 1,
                "Expected_Cash": Decimal("50000.00"),
                "Expected_Card": Decimal("0.00"),
            }
        }
        self.users = {
            1: {
                "User_ID": 1,
                "Username": "admin",
                "Password": hashlib.sha256(b"AdminPass2026").hexdigest(),
                "Role": "Admin",
                "Permissions": {"CREDIT_ADMIN_AUTHORIZE": True},
                "Is_Active": 1,
            },
            5: {
                "User_ID": 5,
                "Username": "caissier1",
                "Password": "CashierPassword",
                "Role": "Cashier_Desk",
                "Permissions": {"CAISSE_SETTLE_CASH": True},
                "Is_Active": 1,
            },
        }
        self.clients = {
            10: {
                "Client_ID": 10,
                "Client_Name": "أحمد بن علي",
                "Credit_Limit": Decimal("100000.00"),
                "Current_Debt": Decimal("20000.00"),
            }
        }
        self.wallets = {}
        self.wallet_txs = []
        self.orders = {
            101: {
                "Order_ID": 101,
                "Client_ID": 10,
                "Bond_Type": "BON_C",
                "Total_Amount_TTC": Decimal("40000.00"),
                "Status": "CONFIRMED_PENDING_PAYMENT",
            },
            201: {
                "Order_ID": 201,
                "Client_ID": 10,
                "Bond_Type": "BON_CREDIT",
                "Total_Amount_TTC": Decimal("60000.00"),
                "Status": "CONFIRMED_PENDING_PAYMENT",
            },
            202: {
                "Order_ID": 202,
                "Client_ID": 10,
                "Bond_Type": "BON_CREDIT",
                "Total_Amount_TTC": Decimal("150000.00"),  # Exceeds remaining 80k limit
                "Status": "CONFIRMED_PENDING_PAYMENT",
            },
            301: {
                "Order_ID": 301,
                "Client_ID": 10,
                "Bond_Type": "BON_LIVRAISON",
                "Total_Amount_TTC": Decimal("75000.00"),
                "Status": "CONFIRMED_PENDING_PAYMENT",
            },
        }
        self.invoices = {}
        self.credit_approvals = []
        self.payment_schedules = []
        self.batches = {50: {"Batch_ID": 50, "Quantity_Current": 5}}
        self.serials_by_sn = {
            "SN-BRANDT-500": {
                "Serial_ID": 500,
                "Product_ID": 1,
                "Batch_ID": 50,
                "Serial_Number": "SN-BRANDT-500",
                "Status": "DISPATCHED",
                "Original_Client_ID": 10,
                "Original_Sales_Invoice_ID": 900,
                "Customer_Warranty_End": (date.today() + timedelta(days=365)).isoformat(),
            }
        }
        self.serials_by_id = {500: self.serials_by_sn["SN-BRANDT-500"]}
        self.return_bonds = {}
        self.sav_tickets = {}
        self.sav_history = []
        self._next_id = 1000

    def alloc_id(self) -> int:
        val = self._next_id
        self._next_id += 1
        return val

    def get_raw_connection(self):
        return FinancialMockConn(self)


class FinancialMockConn:
    def __init__(self, db: FinancialAndSAVMockDB):
        self.db = db

    def start_transaction(self):
        pass

    def cursor(self, dictionary: bool = True):
        return FinancialMockCursor(self.db)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


class FinancialMockCursor:
    def __init__(self, db: FinancialAndSAVMockDB):
        self.db = db
        self.lastrowid = None
        self.rowcount = 0
        self._rows = []

    def execute(self, query: str, params=None):
        q = " ".join(query.strip().split())
        q_upper = q.upper()
        p = tuple(params or ())

        # Client lookup
        if "FROM CLIENTS WHERE CLIENT_ID = %S" in q_upper:
            cid = int(p[0])
            c = self.db.clients.get(cid)
            self._rows = [c.copy()] if c else []
            return

        # Wallet queries
        if "FROM CLIENT_WALLETS WHERE CLIENT_ID = %S FOR UPDATE" in q_upper:
            cid = int(p[0])
            w = self.db.wallets.get(cid)
            self._rows = [w.copy()] if w else []
            return

        if q_upper.startswith("INSERT INTO CLIENT_WALLETS"):
            cid = int(p[0])
            wid = self.db.alloc_id()
            self.db.wallets[cid] = {
                "Wallet_ID": wid,
                "Client_ID": cid,
                "Current_Balance": Decimal("0.00"),
                "Real_Deposit_Balance": Decimal("0.00"),
                "Virtual_Credit_Balance": Decimal("0.00"),
            }
            self.lastrowid = wid
            self.rowcount = 1
            return

        if q_upper.startswith("UPDATE CLIENT_WALLETS SET CURRENT_BALANCE = %S, REAL_DEPOSIT_BALANCE = %S"):
            bal, real_b, _, wid = Decimal(str(p[0])), Decimal(str(p[1])), p[2], int(p[3])
            for w in self.db.wallets.values():
                if w["Wallet_ID"] == wid:
                    w["Current_Balance"] = bal
                    w["Real_Deposit_Balance"] = real_b
            self.rowcount = 1
            return

        if q_upper.startswith("UPDATE CLIENT_WALLETS SET CURRENT_BALANCE = %S, VIRTUAL_CREDIT_BALANCE = %S, REAL_DEPOSIT_BALANCE = %S"):
            bal, virt_b, real_b, _, wid = (
                Decimal(str(p[0])),
                Decimal(str(p[1])),
                Decimal(str(p[2])),
                p[3],
                int(p[4]),
            )
            for w in self.db.wallets.values():
                if w["Wallet_ID"] == wid:
                    w["Current_Balance"] = bal
                    w["Virtual_Credit_Balance"] = virt_b
                    w["Real_Deposit_Balance"] = real_b
            self.rowcount = 1
            return

        if q_upper.startswith("UPDATE CLIENT_WALLETS SET CURRENT_BALANCE = %S, VIRTUAL_CREDIT_BALANCE = %S, TOTAL_LIFETIME_CREDITED"):
            bal, virt_b, _, wid = Decimal(str(p[0])), Decimal(str(p[1])), p[2], int(p[3])
            for w in self.db.wallets.values():
                if w["Wallet_ID"] == wid:
                    w["Current_Balance"] = bal
                    w["Virtual_Credit_Balance"] = virt_b
            self.rowcount = 1
            return

        if q_upper.startswith("INSERT INTO CLIENT_WALLET_TRANSACTIONS"):
            tx_id = self.db.alloc_id()
            self.db.wallet_txs.append({"Transaction_ID": tx_id, "params": p, "query": q})
            self.lastrowid = tx_id
            self.rowcount = 1
            return

        if q_upper.startswith("INSERT INTO CLIENT_PAYMENTS"):
            self.lastrowid = self.db.alloc_id()
            self.rowcount = 1
            return

        # POS_Cash_Sessions (Physical Caisse Till)
        if q_upper.startswith("UPDATE POS_CASH_SESSIONS"):
            if len(p) == 3:
                cash_in, card_in, sid = Decimal(str(p[0])), Decimal(str(p[1])), int(p[2])
                self.db.cash_sessions[sid]["Expected_Cash"] += cash_in
                self.db.cash_sessions[sid]["Expected_Card"] += card_in
            elif len(p) == 2:
                cash_in, sid = Decimal(str(p[0])), int(p[1])
                self.db.cash_sessions[sid]["Expected_Cash"] += cash_in
            self.rowcount = 1
            return

        # Order lookup FOR UPDATE
        if "FROM SALES_ORDERS_THEORETICAL WHERE ORDER_ID = %S FOR UPDATE" in q_upper:
            oid = int(p[0])
            o = self.db.orders.get(oid)
            self._rows = [o.copy()] if o else []
            return

        # Order + Client lookup FOR UPDATE (Bon Crédit)
        if "FROM SALES_ORDERS_THEORETICAL O JOIN CLIENTS C ON O.CLIENT_ID = C.CLIENT_ID WHERE O.ORDER_ID = %S FOR UPDATE" in q_upper:
            oid = int(p[0])
            o = self.db.orders.get(oid)
            if o:
                c = self.db.clients[o["Client_ID"]]
                merged = o.copy()
                merged.update(c)
                self._rows = [merged]
            else:
                self._rows = []
            return

        # Users lookup (Admin Auth)
        if "FROM USERS WHERE USER_ID = %S AND IS_ACTIVE = 1" in q_upper:
            uid = int(p[0])
            u = self.db.users.get(uid)
            self._rows = [u.copy()] if u else []
            return

        # Insert Sales_Invoices (excluding Sales_Invoices_Credit_Approvals)
        if q_upper.startswith("INSERT INTO SALES_INVOICES ("):
            inv_id = self.db.alloc_id()
            # Map fields for Bon C, Bon Crédit, and Bon de Livraison
            self.db.invoices[inv_id] = {
                "Invoice_ID": inv_id,
                "Invoice_No": p[0],
                "Order_ID": int(p[1]),
                "Client_ID": int(p[2]),
                "Amount_Paid_Cash": Decimal(str(p[-3])),
                "Amount_Remaining_Credit": Decimal(str(p[-1])),
                "Status": "Validated",
            }
            self.lastrowid = inv_id
            self.rowcount = 1
            return

        if "FROM SALES_INVOICES WHERE INVOICE_ID = %S FOR UPDATE" in q_upper:
            inv_id = int(p[0])
            inv = self.db.invoices.get(inv_id)
            self._rows = [inv.copy()] if inv else []
            return

        if q_upper.startswith("UPDATE SALES_INVOICES SET STATUS = 'PAID'"):
            rem_paid, inv_id = Decimal(str(p[0])), int(p[1])
            inv = self.db.invoices[inv_id]
            inv["Status"] = "Paid"
            inv["Amount_Paid_Cash"] += rem_paid
            inv["Amount_Remaining_Credit"] = Decimal("0.00")
            inv["Delivery_Status"] = "DELIVERED_PAID"
            self.rowcount = 1
            return

        if q_upper.startswith("UPDATE SALES_ORDERS_THEORETICAL SET STATUS ="):
            if len(p) == 1:
                oid = int(p[0])
                if "PAID_PENDING_DISPATCH" in q_upper:
                    self.db.orders[oid]["Status"] = "PAID_PENDING_DISPATCH"
                elif "APPROVED_CREDIT_PENDING_DISPATCH" in q_upper:
                    self.db.orders[oid]["Status"] = "APPROVED_CREDIT_PENDING_DISPATCH"
                elif "APPROVED_LIVRAISON_PENDING_DISPATCH" in q_upper:
                    self.db.orders[oid]["Status"] = "APPROVED_LIVRAISON_PENDING_DISPATCH"
                elif "COMPLETED" in q_upper:
                    self.db.orders[oid]["Status"] = "COMPLETED"
            self.rowcount = 1
            return

        if q_upper.startswith("INSERT INTO SALES_INVOICES_CREDIT_APPROVALS"):
            self.db.credit_approvals.append(p)
            self.lastrowid = self.db.alloc_id()
            self.rowcount = 1
            return

        if q_upper.startswith("UPDATE CLIENTS SET CURRENT_DEBT = COALESCE(CURRENT_DEBT, 0.00) + %S"):
            rem_credit, cid = Decimal(str(p[0])), int(p[1])
            self.db.clients[cid]["Current_Debt"] += rem_credit
            self.rowcount = 1
            return

        if q_upper.startswith("INSERT INTO CLIENT_PAYMENT_SCHEDULES"):
            self.db.payment_schedules.append(p)
            self.lastrowid = self.db.alloc_id()
            self.rowcount = 1
            return

        # Bon de Retour queries
        if q_upper.startswith("INSERT INTO RETURN_BONDS"):
            rbid = self.db.alloc_id()
            self.db.return_bonds[rbid] = {"Return_Bond_ID": rbid, "Return_Bond_Number": p[0]}
            self.lastrowid = rbid
            self.rowcount = 1
            return

        if "FROM PRODUCT_SERIALS WHERE SERIAL_NUMBER = %S FOR UPDATE" in q_upper:
            sn = p[0]
            s = self.db.serials_by_sn.get(sn)
            self._rows = [s.copy()] if s else []
            return

        if "UPDATE INVENTORY_BATCHES SET QUANTITY_CURRENT = QUANTITY_CURRENT + 1" in q_upper:
            bid = int(p[0])
            self.db.batches[bid]["Quantity_Current"] += 1
            self.rowcount = 1
            return

        if q_upper.startswith("UPDATE PRODUCT_SERIALS SET STATUS = %S, LAST_INSPECTED_AT"):
            new_st, sid = p[0], int(p[1])
            self.db.serials_by_id[sid]["Status"] = new_st
            self.rowcount = 1
            return

        if q_upper.startswith("INSERT INTO RETURN_BOND_SERIALS") or q_upper.startswith("UPDATE RETURN_BONDS"):
            self.lastrowid = self.db.alloc_id()
            self.rowcount = 1
            return

        if q_upper.startswith("INSERT INTO PRODUCT_SERIAL_HISTORY"):
            self.lastrowid = self.db.alloc_id()
            self.rowcount = 1
            return

        # SAV 4-Stage Queries
        if q_upper.startswith("INSERT INTO SAV_TICKETS"):
            tid = self.db.alloc_id()
            self.db.sav_tickets[tid] = {
                "SAV_Ticket_ID": tid,
                "Ticket_Number": p[0],
                "Bon_Reparation_Barcode": p[1],
                "Serial_ID": int(p[2]),
                "Product_ID": int(p[3]),
                "Client_ID": int(p[4]),
                "Current_Stage": "SAV_RECEIVED",
                "Resolution_Status": "PENDING_EVALUATION",
            }
            self.lastrowid = tid
            self.rowcount = 1
            return

        if q_upper.startswith("UPDATE PRODUCT_SERIALS SET STATUS = 'IN_SAV'"):
            sid = int(p[0])
            self.db.serials_by_id[sid]["Status"] = "IN_SAV"
            self.rowcount = 1
            return

        if q_upper.startswith("UPDATE PRODUCT_SERIALS SET STATUS = 'DISPATCHED' WHERE SERIAL_ID = %S"):
            sid = int(p[0])
            self.db.serials_by_id[sid]["Status"] = "DISPATCHED"
            self.rowcount = 1
            return

        if q_upper.startswith("UPDATE PRODUCT_SERIALS SET STATUS = 'SCRAPPED' WHERE SERIAL_ID = %S"):
            sid = int(p[0])
            self.db.serials_by_id[sid]["Status"] = "SCRAPPED"
            self.rowcount = 1
            return

        if "FROM SAV_TICKETS WHERE SAV_TICKET_ID = %S FOR UPDATE" in q_upper:
            tid = int(p[0])
            t = self.db.sav_tickets.get(tid)
            self._rows = [t.copy()] if t else []
            return

        if "SET CURRENT_STAGE = 'SAV_SENT_TO_TECH'" in q_upper:
            tech_id, tid = p[0], int(p[1])
            self.db.sav_tickets[tid]["Current_Stage"] = "SAV_SENT_TO_TECH"
            self.db.sav_tickets[tid]["Assigned_Technician_ID"] = tech_id
            self.rowcount = 1
            return

        if "SET CURRENT_STAGE = 'SAV_RETURNED_FROM_TECH'" in q_upper:
            res_st, diag, _, _, _, tid = p
            t = self.db.sav_tickets[int(tid)]
            t["Current_Stage"] = "SAV_RETURNED_FROM_TECH"
            t["Resolution_Status"] = res_st
            t["Diagnostic_Summary"] = diag
            self.rowcount = 1
            return

        if "SET CURRENT_STAGE = 'SAV_CLOSED_DELIVERED', RESOLUTION_STATUS = 'REPAIRED'" in q_upper:
            _, tid = p[0], int(p[1])
            t = self.db.sav_tickets[tid]
            t["Current_Stage"] = "SAV_CLOSED_DELIVERED"
            t["Resolution_Status"] = "REPAIRED"
            self.rowcount = 1
            return

        if "SET CURRENT_STAGE = 'SAV_CLOSED_DELIVERED', RESOLUTION_STATUS = 'IRREPARABLE'" in q_upper:
            tx_id, tid = p[0], int(p[1])
            t = self.db.sav_tickets[tid]
            t["Current_Stage"] = "SAV_CLOSED_DELIVERED"
            t["Resolution_Status"] = "IRREPARABLE"
            t["Irreparable_Wallet_Transaction_ID"] = tx_id
            self.rowcount = 1
            return

        if q_upper.startswith("INSERT INTO SAV_TICKET_HISTORY"):
            self.db.sav_history.append(p)
            self.lastrowid = self.db.alloc_id()
            self.rowcount = 1
            return

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def close(self):
        pass


def test_bon_de_retour_and_sav_irreparable_zero_physical_caisse_impact():
    """
    Verifies the core financial firewall:
    1. Real `Versement` (`record_real_versement`) increases physical Caisse (`Expected_Cash`)
       and credits `Client_Wallets.Real_Deposit_Balance`.
    2. `Bon de Retour` (`process_bon_retour`) credits `Client_Wallets.Virtual_Credit_Balance`
       (`Versement Virtuel`) while keeping physical Caisse strictly unchanged (`physical_till_delta == 0.0`).
    3. `Bon C` settlement (`validate_bon_c_cash`) consumes Virtual Credit first, then Real Deposit,
       and only adds physical cash paid to `Expected_Cash`.
    4. Anti-Serial-Swap Fraud: Attempting to return a serial number that was not dispatched on the
       referenced invoice raises `SecurityViolationException`.
    """
    db = FinancialAndSAVMockDB()
    bond_mgr = BondLifecycleManager(db)

    assert db.cash_sessions[1]["Expected_Cash"] == Decimal("50000.00")

    # 1. Customer deposits 10,000 DA real cash via Versement
    v_res = bond_mgr.record_real_versement(
        client_id=10,
        amount_cash=Decimal("10000.00"),
        cashier_user_id=5,
        cash_session_id=1,
    )
    assert v_res["success"] is True
    assert v_res["affects_physical_caisse"] is True
    assert db.cash_sessions[1]["Expected_Cash"] == Decimal("60000.00")
    assert db.wallets[10]["Real_Deposit_Balance"] == Decimal("10000.00")

    # 2. Anti-Serial-Swap test: Returning SN-BRANDT-500 against wrong invoice #888 -> SecurityViolationException
    with pytest.raises(SecurityViolationException, match="Serial mismatch"):
        bond_mgr.process_bon_retour(
            original_invoice_id=888,
            client_id=10,
            received_by_user_id=5,
            return_reason="محاولة إرجاع بفاتورة غير مطابقة",
            returned_serials=[
                {
                    "serial_number": "SN-BRANDT-500",
                    "inspection_condition": "LIKE_NEW_RESTOCK",
                    "unit_credit_value": "15000.00",
                }
            ],
            verify_dispatched_on_invoice=True,
        )

    # 3. Valid Bon de Retour on Invoice #900 for 15,000 DA -> Versement Virtuel with ZERO Caisse drain
    till_before_return = db.cash_sessions[1]["Expected_Cash"]
    ret_res = bond_mgr.process_bon_retour(
        original_invoice_id=900,
        client_id=10,
        received_by_user_id=5,
        return_reason="إرجاع سليم واستبدال برصيد افتراضي",
        returned_serials=[
            {
                "serial_number": "SN-BRANDT-500",
                "inspection_condition": "LIKE_NEW_RESTOCK",
                "unit_credit_value": "15000.00",
            }
        ],
        verify_dispatched_on_invoice=True,
    )
    assert ret_res["success"] is True
    assert ret_res["physical_till_delta"] == 0.0
    assert db.cash_sessions[1]["Expected_Cash"] == till_before_return
    assert db.wallets[10]["Virtual_Credit_Balance"] == Decimal("15000.00")
    assert db.wallets[10]["Current_Balance"] == Decimal("25000.00")
    assert db.serials_by_sn["SN-BRANDT-500"]["Status"] == "IN_STOCK"
    assert db.batches[50]["Quantity_Current"] == 6

    # 4. Settle Bon C (Order #101, 40,000 DA TTC) using 25,000 DA Wallet + 15,000 DA Cash
    bon_c_res = bond_mgr.validate_bon_c_cash(
        order_id=101,
        cashier_user_id=5,
        cash_session_id=1,
        amount_paid_cash=Decimal("15000.00"),
        amount_paid_card=Decimal("0.00"),
        amount_paid_wallet=Decimal("25000.00"),
    )
    assert bon_c_res["success"] is True
    assert bon_c_res["status"] == "PAID_PENDING_DISPATCH"
    assert db.cash_sessions[1]["Expected_Cash"] == Decimal("75000.00")  # 60,000 + 15,000
    assert db.wallets[10]["Current_Balance"] == Decimal("0.00")
    assert db.wallets[10]["Virtual_Credit_Balance"] == Decimal("0.00")
    assert db.wallets[10]["Real_Deposit_Balance"] == Decimal("0.00")


def test_bon_credit_admin_auth_and_credit_limit_enforcement():
    """
    Verifies `Bon Crédit` (`authorize_bon_credit`):
    1. Cashier without Admin role cannot authorize (`SecurityViolationException`).
    2. Wrong Admin password raises `SecurityViolationException`.
    3. Order exceeding client's credit ceiling raises `ValueError`.
    4. Valid Admin password approves `Bon Crédit` with partial downpayment, logs audit hash,
       increments client debt, and generates installment schedules.
    """
    db = FinancialAndSAVMockDB()
    bond_mgr = BondLifecycleManager(db)

    # 1. Non-admin user (#5) attempting to authorize -> SecurityViolationException
    with pytest.raises(SecurityViolationException, match="Admin role required"):
        bond_mgr.authorize_bon_credit(
            order_id=201,
            cashier_user_id=5,
            cash_session_id=1,
            admin_user_id=5,
            admin_pin_or_pwd="CashierPassword",
        )

    # 2. Admin user (#1) with wrong password -> SecurityViolationException
    with pytest.raises(SecurityViolationException, match="Invalid Administrator password"):
        bond_mgr.authorize_bon_credit(
            order_id=201,
            cashier_user_id=5,
            cash_session_id=1,
            admin_user_id=1,
            admin_pin_or_pwd="WrongPass",
        )

    # 3. Order #202 (150,000 DA) exceeds client's remaining credit limit (100k limit - 20k debt = 80k)
    with pytest.raises(ValueError, match="Credit ceiling exceeded"):
        bond_mgr.authorize_bon_credit(
            order_id=202,
            cashier_user_id=5,
            cash_session_id=1,
            admin_user_id=1,
            admin_pin_or_pwd="AdminPass2026",
        )

    # 4. Valid Admin approval on Order #201 (60,000 DA total, 15,000 DA cash downpayment -> 45,000 DA credit)
    res = bond_mgr.authorize_bon_credit(
        order_id=201,
        cashier_user_id=5,
        cash_session_id=1,
        admin_user_id=1,
        admin_pin_or_pwd="AdminPass2026",
        downpayment_cash=Decimal("15000.00"),
        installments_count=3,
    )
    assert res["success"] is True
    assert res["approved_credit_amount"] == 45000.0
    assert res["downpayment_paid"] == 15000.0
    assert res["new_client_debt"] == 65000.0
    assert res["status"] == "APPROVED_CREDIT_PENDING_DISPATCH"
    assert db.cash_sessions[1]["Expected_Cash"] == Decimal("65000.00")
    assert len(db.credit_approvals) == 1
    assert len(db.payment_schedules) == 3


def test_bon_de_livraison_advance_and_cod_settlement():
    """
    Verifies `Bon de Livraison`:
    1. Advance deposit (`validate_bon_livraison_advance`) records advance in Caisse before dispatch.
    2. Final COD settlement (`settle_bon_livraison_cod`) collects remaining balance after delivery.
    """
    db = FinancialAndSAVMockDB()
    bond_mgr = BondLifecycleManager(db)

    adv = bond_mgr.validate_bon_livraison_advance(
        order_id=301,
        cashier_user_id=5,
        cash_session_id=1,
        advance_cash=Decimal("25000.00"),
    )
    assert adv["success"] is True
    assert adv["advance_paid"] == 25000.0
    assert adv["remaining_on_delivery"] == 50000.0
    assert adv["status"] == "APPROVED_LIVRAISON_PENDING_DISPATCH"
    assert db.cash_sessions[1]["Expected_Cash"] == Decimal("75000.00")

    cod = bond_mgr.settle_bon_livraison_cod(
        invoice_id=adv["invoice_id"],
        cashier_user_id=5,
        cash_session_id=1,
        collected_cash=Decimal("50000.00"),
    )
    assert cod["success"] is True
    assert cod["settled_cod_amount"] == 50000.0
    assert cod["delivery_status"] == "DELIVERED_PAID"
    assert db.cash_sessions[1]["Expected_Cash"] == Decimal("125000.00")
    assert db.orders[301]["Status"] == "COMPLETED"


def test_sav_four_stage_pipeline_and_irreparable_virtual_versement():
    """
    Verifies the 4-Stage SAV / Réparation workflow (`SAVWorkflowManager`):
    1. Stage 1 (`check_in_reception`): Emits `Bon de Réparation` (`BREP-...`), sets serial to `IN_SAV`.
    2. Out-of-order transition from Stage 1 directly to Stage 3 or Stage 4 raises `ValueError`.
    3. Stage 2 (`dispatch_to_technician`): Advances to `SAV_SENT_TO_TECH`.
    4. Stage 3 (`record_technician_return`): Advances to `SAV_RETURNED_FROM_TECH`.
    5. Stage 4B (`process_irreparable_compensation`): Issues `Versement Virtuel` into `Client_Wallets`,
       marks serial as `SCRAPPED`, closes ticket (`SAV_CLOSED_DELIVERED`), and keeps physical Caisse
       strictly unchanged (`physical_till_delta == 0.0`).
    """
    db = FinancialAndSAVMockDB()
    sav_mgr = SAVWorkflowManager(db)

    # Stage 1: Receive defective appliance from customer
    st1 = sav_mgr.check_in_reception(
        serial_number="SN-BRANDT-500",
        symptom="توقف المحرك عن الدوران",
        cosmetic_condition="سليم خارجياً",
        accessories="خرطوم التصريف",
        received_by_user_id=4,
    )
    assert st1["success"] is True
    assert st1["current_stage"] == "SAV_RECEIVED"
    assert st1["bon_reparation_barcode"].startswith("BREP-")
    ticket_id = st1["ticket_id"]
    assert db.serials_by_sn["SN-BRANDT-500"]["Status"] == "IN_SAV"

    # Attempt illegal skip from Stage 1 directly to Stage 4 -> ValueError
    with pytest.raises(ValueError, match="Cannot deliver ticket before return from technician"):
        sav_mgr.deliver_repaired_to_client(sav_ticket_id=ticket_id, user_id=4)

    # Stage 2: Dispatch to technician
    st2 = sav_mgr.dispatch_to_technician(sav_ticket_id=ticket_id, technician_id=10, user_id=4)
    assert st2["success"] is True
    assert st2["current_stage"] == "SAV_SENT_TO_TECH"

    # Stage 3: Technician return & diagnostic
    st3 = sav_mgr.record_technician_return(
        sav_ticket_id=ticket_id,
        resolution_status="IRREPARABLE",
        diagnostic_summary="تلف كلي في البطاقة الأم والضاغط",
        user_id=4,
    )
    assert st3["success"] is True
    assert st3["current_stage"] == "SAV_RETURNED_FROM_TECH"
    assert st3["resolution_status"] == "IRREPARABLE"

    # Stage 4B: Irreparable compensation -> Versement Virtuel with ZERO Caisse impact
    till_before = db.cash_sessions[1]["Expected_Cash"]
    comp = sav_mgr.process_irreparable_compensation(
        sav_ticket_id=ticket_id,
        admin_user_id=1,
        compensation_amount=Decimal("42000.00"),
    )
    assert comp["success"] is True
    assert comp["physical_till_delta"] == 0.0
    assert comp["serial_status"] == "SCRAPPED"
    assert comp["new_wallet_balance"] == 42000.0
    assert db.cash_sessions[1]["Expected_Cash"] == till_before
    assert db.wallets[10]["Virtual_Credit_Balance"] == Decimal("42000.00")
    assert db.serials_by_sn["SN-BRANDT-500"]["Status"] == "SCRAPPED"
    assert db.sav_tickets[ticket_id]["Current_Stage"] == "SAV_CLOSED_DELIVERED"
