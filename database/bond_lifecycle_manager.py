# database/bond_lifecycle_manager.py
"""
Bond Lifecycle & Multi-Desk Operational Workflow Manager.
Implements the complete cycle of the 6 Bonds across Order Desk, Caisse, and Dispatch Desk:
1. Bon C (بيع مباشر): Order Desk theoretical order -> Caisse cash/card/wallet validation.
2. Bon Crédit (أجل): Admin password/PIN authorization, credit limit check, optional partial Caisse downpayment or full credit.
3. Bon de Livraison (توصيل): Delivery order with optional Caisse advance payment before dispatch and COD settlement after delivery.
4. Versement (إيداع مالي): Real cash deposit into Client Wallet (enters physical Caisse, redeemable on future purchases).
5. Bon de Sortie (خروج): Logistical exit voucher after scanning physical barcode & N° de Série (zero cash impact).
6. Bon de Retour (إرجاع): Product return with anti-serial-swap check and Versement Virtuel into Client Wallet (zero Caisse drain).
"""

import hashlib
import logging
import random
import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

import mysql.connector

from .serial_tracking_manager import SerialTrackingManager

logger = logging.getLogger("StockLam.Backend.BondLifecycle")


class StateCollisionException(Exception):
    """Raised when a concurrent dispatch desk attempts to allocate a serial that is not IN_STOCK."""


class SplitPaymentMismatchException(ValueError):
    """Raised when split-tender payment instruments do not equal the invoice total TTC."""


class SecurityViolationException(PermissionError):
    """Raised on serial swap fraud, unauthorized credit approval, or prohibited cash till drain."""


def _verify_password_secret(provided_secret: str, stored_secret: str) -> bool:
    """
    Verifies an administrator password or PIN against a stored secret.
    Supports bcrypt hashes ($2a$, $2b$, $2y$), SHA-256 hex digests, and plain-text legacy passwords.
    """
    if not provided_secret or not stored_secret:
        return False
    provided_str = str(provided_secret)
    stored_str = str(stored_secret)

    if stored_str.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            import bcrypt
            return bcrypt.checkpw(provided_str.encode("utf-8"), stored_str.encode("utf-8"))
        except ImportError:
            pass

    sha256_hex = hashlib.sha256(provided_str.encode("utf-8")).hexdigest()
    if stored_str.lower() == sha256_hex.lower():
        return True

    return provided_str == stored_str


class BondLifecycleManager:
    """Orchestrates Order Desk, Caisse Settlement, Client Wallets, and Dispatch Exit Bonds."""

    def __init__(self, db_instance):
        self.db = db_instance

    def _get_connection(self):
        if hasattr(self.db, "get_raw_connection"):
            conn = self.db.get_raw_connection()
            if conn is not None:
                return conn
        if hasattr(self.db, "get_connection"):
            return self.db.get_connection()
        if hasattr(self.db, "cursor"):
            return self.db
        raise RuntimeError("No valid database connection provider found.")

    # =========================================================================
    # 1. ORDER DESK (مكتب الطلبات - البيع النظري)
    # =========================================================================

    def create_sales_order_draft(
        self,
        client_id: int,
        order_desk_user_id: int,
        items: List[Dict[str, Any]],
        payment_method_requested: str = "CASH",
        bond_type: str = "BON_C",
        scanner_session_id: Optional[str] = None,
        delivery_address: Optional[str] = None,
        delivery_phone: Optional[str] = None,
        delivery_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Creates a theoretical order at the Order Desk (Bon C, Bon Crédit request, or Bon de Livraison).
        Reserves quantity theoretically at the batch level (Theoretical_Reserved_Qty) via SELECT ... FOR UPDATE.
        Zero physical serial numbers are reserved or bound at this stage.
        """
        if not items:
            raise ValueError("Cannot create an order with an empty items list.")

        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if hasattr(conn, "start_transaction"):
                conn.start_transaction()

            normalized_bond = (bond_type or "BON_C").strip().upper()
            if normalized_bond not in ("BON_C", "BON_CREDIT", "BON_LIVRAISON"):
                normalized_bond = "BON_C"

            prefix_map = {
                "BON_C": "BC",
                "BON_CREDIT": "BCR",
                "BON_LIVRAISON": "BLV",
            }
            prefix = prefix_map[normalized_bond]
            order_num = f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{int(datetime.now().timestamp() * 1000) % 100000:05d}"

            total_ttc = sum(
                (Decimal(str(item["unit_price_ttc"])) * int(item["quantity"])).quantize(Decimal("0.01"))
                for item in items
            )
            total_ht = (total_ttc / Decimal("1.19")).quantize(Decimal("0.01"))

            cursor.execute(
                """
                INSERT INTO Sales_Orders_Theoretical (
                    Order_Number, Client_ID, Order_Desk_User_ID, Scanner_Session_ID,
                    Bond_Type, Total_Amount_HT, Total_Amount_TTC,
                    Status, Payment_Method_Requested,
                    Delivery_Address, Delivery_Phone, Delivery_Notes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'CONFIRMED_PENDING_PAYMENT', %s, %s, %s, %s)
                """,
                (
                    order_num,
                    int(client_id),
                    int(order_desk_user_id),
                    scanner_session_id,
                    normalized_bond,
                    total_ht,
                    total_ttc,
                    payment_method_requested,
                    delivery_address,
                    delivery_phone,
                    delivery_notes,
                ),
            )
            order_id = cursor.lastrowid

            line_sql = """
                INSERT INTO Sales_Order_Lines_Theoretical (
                    Order_ID, Product_ID, Requested_Color, Quantity_Ordered,
                    Unit_Price_HT, Tax_Rate, Unit_Price_TTC, Line_Total_TTC
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """

            for item in items:
                prod_id = int(item["product_id"])
                req_qty = int(item["quantity"])
                if req_qty <= 0:
                    raise ValueError("Ordered quantity must be greater than zero.")
                p_ttc = Decimal(str(item["unit_price_ttc"])).quantize(Decimal("0.01"))
                p_ht = (p_ttc / Decimal("1.19")).quantize(Decimal("0.01"))
                line_ttc = (p_ttc * req_qty).quantize(Decimal("0.01"))
                req_color = item.get("color") or item.get("coloure")

                # Lock active batches with SELECT ... FOR UPDATE
                cursor.execute(
                    """
                    SELECT Batch_ID, Quantity_Current, COALESCE(Theoretical_Reserved_Qty, 0) AS Theoretical_Reserved_Qty
                    FROM Inventory_Batches
                    WHERE Product_ID = %s AND Status IN ('Available', 'ACTIVE')
                    ORDER BY Batch_ID ASC
                    FOR UPDATE
                    """,
                    (prod_id,),
                )
                batches = cursor.fetchall() or []

                total_avail = sum(
                    int(b["Quantity_Current"]) - int(b.get("Theoretical_Reserved_Qty") or 0)
                    for b in batches
                )
                if total_avail < req_qty:
                    raise ValueError(
                        f"Insufficient theoretical stock for Product ID {prod_id}. "
                        f"Requested: {req_qty}, Available: {total_avail}"
                    )

                remaining_to_reserve = req_qty
                for b in batches:
                    batch_avail = int(b["Quantity_Current"]) - int(b.get("Theoretical_Reserved_Qty") or 0)
                    if batch_avail <= 0:
                        continue
                    alloc = min(remaining_to_reserve, batch_avail)
                    cursor.execute(
                        """
                        UPDATE Inventory_Batches
                        SET Theoretical_Reserved_Qty = COALESCE(Theoretical_Reserved_Qty, 0) + %s
                        WHERE Batch_ID = %s
                        """,
                        (alloc, b["Batch_ID"]),
                    )
                    remaining_to_reserve -= alloc
                    if remaining_to_reserve == 0:
                        break

                cursor.execute(
                    line_sql,
                    (order_id, prod_id, req_color, req_qty, p_ht, Decimal("19.00"), p_ttc, line_ttc),
                )

            conn.commit()
            return {
                "success": True,
                "order_id": order_id,
                "order_number": order_num,
                "bond_type": normalized_bond,
                "total_ttc": float(total_ttc),
                "scanner_session_id": scanner_session_id,
            }
        except Exception as err:
            conn.rollback()
            logger.error(f"Failed to create theoretical order draft: {err}")
            raise
        finally:
            cursor.close()
            if hasattr(self.db, "get_raw_connection"):
                conn.close()

    # =========================================================================
    # 2. CLIENT WALLET & VERSEMENT (الإيداع المالي الفعلي والرصيد الافتراضي)
    # =========================================================================

    def _get_or_create_wallet_locked(self, cursor, client_id: int) -> Dict[str, Any]:
        """Locks and fetches the client's wallet row, initializing it if absent."""
        cursor.execute(
            """
            SELECT Wallet_ID, Client_ID, Current_Balance,
                   COALESCE(Real_Deposit_Balance, 0.00) AS Real_Deposit_Balance,
                   COALESCE(Virtual_Credit_Balance, 0.00) AS Virtual_Credit_Balance
            FROM Client_Wallets
            WHERE Client_ID = %s
            FOR UPDATE
            """,
            (int(client_id),),
        )
        wallet = cursor.fetchone()
        if not wallet:
            cursor.execute(
                """
                INSERT INTO Client_Wallets (
                    Client_ID, Current_Balance, Real_Deposit_Balance, Virtual_Credit_Balance
                ) VALUES (%s, 0.00, 0.00, 0.00)
                """,
                (int(client_id),),
            )
            wallet_id = cursor.lastrowid
            return {
                "Wallet_ID": wallet_id,
                "Client_ID": int(client_id),
                "Current_Balance": Decimal("0.00"),
                "Real_Deposit_Balance": Decimal("0.00"),
                "Virtual_Credit_Balance": Decimal("0.00"),
            }
        return {
            "Wallet_ID": wallet["Wallet_ID"],
            "Client_ID": wallet["Client_ID"],
            "Current_Balance": Decimal(str(wallet.get("Current_Balance") or "0.00")),
            "Real_Deposit_Balance": Decimal(str(wallet.get("Real_Deposit_Balance") or "0.00")),
            "Virtual_Credit_Balance": Decimal(str(wallet.get("Virtual_Credit_Balance") or "0.00")),
        }

    def get_client_wallet(self, client_id: int) -> Dict[str, Any]:
        """Returns the current wallet balances (total, real deposit Versement, and virtual credit)."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT Wallet_ID, Client_ID, Current_Balance,
                           COALESCE(Real_Deposit_Balance, 0.00) AS Real_Deposit_Balance,
                           COALESCE(Virtual_Credit_Balance, 0.00) AS Virtual_Credit_Balance,
                           Total_Lifetime_Credited, Total_Lifetime_Debited, Wallet_Status
                    FROM Client_Wallets
                    WHERE Client_ID = %s
                    """,
                    (int(client_id),),
                )
                row = cursor.fetchone()
                if not row:
                    return {
                        "client_id": int(client_id),
                        "current_balance": 0.0,
                        "real_deposit_balance": 0.0,
                        "virtual_credit_balance": 0.0,
                        "status": "ACTIVE",
                    }
                return {
                    "wallet_id": row["Wallet_ID"],
                    "client_id": row["Client_ID"],
                    "current_balance": float(row.get("Current_Balance") or 0.0),
                    "real_deposit_balance": float(row.get("Real_Deposit_Balance") or 0.0),
                    "virtual_credit_balance": float(row.get("Virtual_Credit_Balance") or 0.0),
                    "status": row.get("Wallet_Status", "ACTIVE"),
                }
        except Exception as err:
            logger.error(f"Error fetching client wallet: {err}")
            return {
                "client_id": int(client_id),
                "current_balance": 0.0,
                "real_deposit_balance": 0.0,
                "virtual_credit_balance": 0.0,
                "status": "ACTIVE",
            }

    def record_real_versement(
        self,
        client_id: int,
        amount_cash: Decimal,
        cashier_user_id: int,
        cash_session_id: Optional[int] = None,
        notes: str = "Versement espèces en caisse",
    ) -> Dict[str, Any]:
        """
        Records a Versement (إيداع مالي فعلي):
        - Customer deposits real cash into their store account/wallet.
        - Enters the physical Caisse (POS_Cash_Sessions.Expected_Cash incremented).
        - Credits Client_Wallets (Current_Balance and Real_Deposit_Balance) for future purchases.
        """
        deposit = Decimal(str(amount_cash)).quantize(Decimal("0.01"))
        if deposit <= Decimal("0.00"):
            raise ValueError("Versement amount must be strictly positive.")

        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if hasattr(conn, "start_transaction"):
                conn.start_transaction()

            wallet = self._get_or_create_wallet_locked(cursor, client_id)
            bal_before = wallet["Current_Balance"]
            bal_after = (bal_before + deposit).quantize(Decimal("0.01"))
            real_after = (wallet["Real_Deposit_Balance"] + deposit).quantize(Decimal("0.01"))

            # 1. Update Physical Caisse session if active
            if cash_session_id:
                cursor.execute(
                    """
                    UPDATE POS_Cash_Sessions
                    SET Expected_Cash = COALESCE(Expected_Cash, 0.00) + %s
                    WHERE Cash_Session_ID = %s
                    """,
                    (deposit, int(cash_session_id)),
                )

            # 2. Record in Client_Payments as a Versement deposit
            cursor.execute(
                """
                INSERT INTO Client_Payments (
                    Client_ID, Invoice_ID, Payment_Date, Amount,
                    Payment_Method, Reference, Notes, Created_By
                ) VALUES (%s, NULL, CURDATE(), %s, 'Versement', %s, %s, %s)
                """,
                (
                    int(client_id),
                    deposit,
                    f"VERS-{int(datetime.now().timestamp())}",
                    notes,
                    int(cashier_user_id),
                ),
            )
            payment_id = cursor.lastrowid or 1

            # 3. Record Wallet Transaction (Affects_Physical_Caisse = TRUE)
            cursor.execute(
                """
                INSERT INTO Client_Wallet_Transactions (
                    Wallet_ID, Client_ID, Transaction_Type, Amount,
                    Balance_Before, Balance_After, Source_Document_Type,
                    Source_Document_ID, Authorized_By_User_ID,
                    Affects_Physical_Caisse, Cash_Session_ID, Transaction_Notes
                ) VALUES (%s, %s, 'REAL_CASH_VERSEMENT', %s, %s, %s, 'VERSEMENT_CAISSE', %s, %s, TRUE, %s, %s)
                """,
                (
                    wallet["Wallet_ID"],
                    int(client_id),
                    deposit,
                    bal_before,
                    bal_after,
                    payment_id,
                    int(cashier_user_id),
                    int(cash_session_id) if cash_session_id else None,
                    notes,
                ),
            )
            tx_id = cursor.lastrowid

            # 4. Update Client Wallet Balance
            cursor.execute(
                """
                UPDATE Client_Wallets
                SET Current_Balance = %s,
                    Real_Deposit_Balance = %s,
                    Total_Lifetime_Credited = COALESCE(Total_Lifetime_Credited, 0.00) + %s,
                    Last_Transaction_At = CURRENT_TIMESTAMP
                WHERE Wallet_ID = %s
                """,
                (bal_after, real_after, deposit, wallet["Wallet_ID"]),
            )

            conn.commit()
            return {
                "success": True,
                "transaction_id": tx_id,
                "payment_id": payment_id,
                "deposited_amount": float(deposit),
                "new_wallet_balance": float(bal_after),
                "affects_physical_caisse": True,
            }
        except Exception as err:
            conn.rollback()
            logger.error(f"Error recording real Versement: {err}")
            raise
        finally:
            cursor.close()
            if hasattr(self.db, "get_raw_connection"):
                conn.close()

    def _debit_client_wallet_locked(
        self,
        cursor,
        client_id: int,
        debit_amount: Decimal,
        invoice_id: int,
        user_id: int,
        notes: str = "Règlement achat via Portefeuille Client",
    ) -> Decimal:
        """Debits the client's wallet atomically inside an active transaction."""
        debit_dec = Decimal(str(debit_amount)).quantize(Decimal("0.01"))
        if debit_dec <= Decimal("0.00"):
            return Decimal("0.00")

        wallet = self._get_or_create_wallet_locked(cursor, client_id)
        bal_before = wallet["Current_Balance"]
        if bal_before < debit_dec:
            raise ValueError(
                f"Insufficient client wallet balance. Available: {bal_before}, Requested: {debit_dec}"
            )

        bal_after = (bal_before - debit_dec).quantize(Decimal("0.01"))
        # Consume virtual credit first, then real deposit balance
        virt_deduct = min(wallet["Virtual_Credit_Balance"], debit_dec)
        real_deduct = (debit_dec - virt_deduct).quantize(Decimal("0.01"))
        virt_after = (wallet["Virtual_Credit_Balance"] - virt_deduct).quantize(Decimal("0.01"))
        real_after = max(Decimal("0.00"), (wallet["Real_Deposit_Balance"] - real_deduct).quantize(Decimal("0.01")))

        cursor.execute(
            """
            INSERT INTO Client_Wallet_Transactions (
                Wallet_ID, Client_ID, Transaction_Type, Amount,
                Balance_Before, Balance_After, Source_Document_Type,
                Source_Document_ID, Authorized_By_User_ID,
                Affects_Physical_Caisse, Transaction_Notes
            ) VALUES (%s, %s, 'SALES_PURCHASE_DEBIT', %s, %s, %s, 'SALES_INVOICE', %s, %s, FALSE, %s)
            """,
            (
                wallet["Wallet_ID"],
                int(client_id),
                debit_dec,
                bal_before,
                bal_after,
                int(invoice_id),
                int(user_id),
                notes,
            ),
        )
        cursor.execute(
            """
            UPDATE Client_Wallets
            SET Current_Balance = %s,
                Virtual_Credit_Balance = %s,
                Real_Deposit_Balance = %s,
                Total_Lifetime_Debited = COALESCE(Total_Lifetime_Debited, 0.00) + %s,
                Last_Transaction_At = CURRENT_TIMESTAMP
            WHERE Wallet_ID = %s
            """,
            (bal_after, virt_after, real_after, debit_dec, wallet["Wallet_ID"]),
        )
        return bal_after

    # =========================================================================
    # 3. CAISSE DESK SETTLEMENTS (Bon C, Bon Crédit, Bon de Livraison, Bon de Retour)
    # =========================================================================

    def validate_bon_c_cash(
        self,
        order_id: int,
        cashier_user_id: int,
        cash_session_id: int,
        amount_paid_cash: Decimal,
        amount_paid_card: Decimal = Decimal("0.00"),
        amount_paid_wallet: Decimal = Decimal("0.00"),
    ) -> Dict[str, Any]:
        """
        Validates a Bon C (بيع مباشر) at the Caisse Desk.
        Supports pure cash or multi-tender split (Cash + Card + Client Wallet).
        Transitions order to PAID_PENDING_DISPATCH.
        """
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if hasattr(conn, "start_transaction"):
                conn.start_transaction()

            cursor.execute(
                """
                SELECT Order_ID, Client_ID, Total_Amount_TTC, Status
                FROM Sales_Orders_Theoretical
                WHERE Order_ID = %s
                FOR UPDATE
                """,
                (int(order_id),),
            )
            order = cursor.fetchone()
            if not order:
                raise ValueError("Order not found.")
            if order["Status"] != "CONFIRMED_PENDING_PAYMENT":
                raise ValueError(f"Order cannot be paid in current status: {order['Status']}")

            total_ttc = Decimal(str(order["Total_Amount_TTC"])).quantize(Decimal("0.01"))
            cash_dec = Decimal(str(amount_paid_cash or "0.00")).quantize(Decimal("0.01"))
            card_dec = Decimal(str(amount_paid_card or "0.00")).quantize(Decimal("0.01"))
            wallet_dec = Decimal(str(amount_paid_wallet or "0.00")).quantize(Decimal("0.01"))

            total_tendered = (cash_dec + card_dec + wallet_dec).quantize(Decimal("0.01"))
            if total_tendered < total_ttc:
                raise SplitPaymentMismatchException(
                    f"Paid amount ({total_tendered} DA) is less than total TTC ({total_ttc} DA)."
                )

            change_due = max(Decimal("0.00"), (total_tendered - total_ttc).quantize(Decimal("0.01")))
            net_cash_retained = max(Decimal("0.00"), (cash_dec - change_due).quantize(Decimal("0.01")))

            invoice_num = f"FAC-C-{datetime.now().strftime('%Y%m%d')}-{order_id}"
            total_ht = (total_ttc / Decimal("1.19")).quantize(Decimal("0.01"))
            total_tva = (total_ttc - total_ht).quantize(Decimal("0.01"))

            cursor.execute(
                """
                INSERT INTO Sales_Invoices (
                    Invoice_No, Order_ID, Client_ID, Invoice_Date, Status,
                    Total_Amount_HT, Total_TVA, Total_Amount_TTC,
                    Created_By, Cash_Session_ID, Payment_Method,
                    Bond_Settlement_Type, Amount_Paid_Cash, Amount_Paid_Card,
                    Amount_Paid_Wallet, Amount_Remaining_Credit
                ) VALUES (%s, %s, %s, CURDATE(), 'Paid', %s, %s, %s, %s, %s, 'Cash', 'BON_C_CASH', %s, %s, %s, 0.00)
                """,
                (
                    invoice_num,
                    int(order_id),
                    int(order["Client_ID"]),
                    total_ht,
                    total_tva,
                    total_ttc,
                    int(cashier_user_id),
                    int(cash_session_id) if cash_session_id else None,
                    net_cash_retained,
                    card_dec,
                    wallet_dec,
                ),
            )
            invoice_id = cursor.lastrowid

            # Debit client wallet if wallet balance was applied
            if wallet_dec > Decimal("0.00"):
                self._debit_client_wallet_locked(
                    cursor,
                    int(order["Client_ID"]),
                    wallet_dec,
                    invoice_id,
                    int(cashier_user_id),
                    f"Déduction portefeuille sur Bon C #{invoice_num}",
                )

            # Update physical cash session for net cash retained
            if cash_session_id and net_cash_retained > Decimal("0.00"):
                cursor.execute(
                    """
                    UPDATE POS_Cash_Sessions
                    SET Expected_Cash = COALESCE(Expected_Cash, 0.00) + %s,
                        Expected_Card = COALESCE(Expected_Card, 0.00) + %s
                    WHERE Cash_Session_ID = %s
                    """,
                    (net_cash_retained, card_dec, int(cash_session_id)),
                )

            cursor.execute(
                """
                UPDATE Sales_Orders_Theoretical
                SET Status = 'PAID_PENDING_DISPATCH'
                WHERE Order_ID = %s
                """,
                (int(order_id),),
            )

            conn.commit()
            return {
                "success": True,
                "invoice_id": invoice_id,
                "invoice_number": invoice_num,
                "net_cash_retained": float(net_cash_retained),
                "wallet_debited": float(wallet_dec),
                "change_due": float(change_due),
                "status": "PAID_PENDING_DISPATCH",
            }
        except Exception as err:
            conn.rollback()
            logger.error(f"Error validating Bon C: {err}")
            raise
        finally:
            cursor.close()
            if hasattr(self.db, "get_raw_connection"):
                conn.close()

    def authorize_bon_credit(
        self,
        order_id: int,
        cashier_user_id: int,
        cash_session_id: int,
        admin_user_id: int,
        admin_pin_or_pwd: str,
        admin_notes: str = "Accord superviseur Bon Crédit",
        terminal_ip: str = "127.0.0.1",
        downpayment_cash: Decimal = Decimal("0.00"),
        downpayment_wallet: Decimal = Decimal("0.00"),
        installments_count: int = 1,
    ) -> Dict[str, Any]:
        """
        Authorizes a Bon Crédit (بيع بالأجل) at the Caisse Desk.
        - Requires Administrator authentication (password/PIN verified against Admin user record).
        - Supports partial advance payment in Caisse (downpayment_cash / downpayment_wallet) OR 100% credit.
        - Enforces Client Credit_Limit ceiling against (Current_Debt + Remaining_Credit).
        - Logs immutable audit trail in Sales_Invoices_Credit_Approvals.
        """
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if hasattr(conn, "start_transaction"):
                conn.start_transaction()

            # 1. Verify Admin user & password/PIN
            cursor.execute(
                """
                SELECT User_ID, Username, Password, Role, Permissions
                FROM Users
                WHERE User_ID = %s AND Is_Active = 1
                """,
                (int(admin_user_id),),
            )
            admin = cursor.fetchone()
            if not admin:
                raise SecurityViolationException("Provided user is not an active Administrator.")

            role_str = str(admin.get("Role") or "").strip().lower()
            perms_raw = admin.get("Permissions") or {}
            if isinstance(perms_raw, str):
                import json
                try:
                    perms_raw = json.loads(perms_raw)
                except Exception:
                    perms_raw = {}

            has_credit_auth_perm = role_str == "admin" or bool(
                isinstance(perms_raw, dict) and perms_raw.get("CREDIT_ADMIN_AUTHORIZE")
            )
            if not has_credit_auth_perm:
                raise SecurityViolationException(
                    "Frontline cashiers are denied Bon Crédit authorization authority. Admin role required."
                )

            stored_pwd = admin.get("Password") or admin.get("Password_Hash") or ""
            if not _verify_password_secret(admin_pin_or_pwd, stored_pwd):
                raise SecurityViolationException("Invalid Administrator password or PIN.")

            # 2. Lock Order & Client Record (SELECT ... FOR UPDATE)
            cursor.execute(
                """
                SELECT o.Order_ID, o.Client_ID, o.Total_Amount_TTC, o.Status,
                       c.Credit_Limit, COALESCE(c.Current_Debt, 0.00) AS Current_Debt
                FROM Sales_Orders_Theoretical o
                JOIN Clients c ON o.Client_ID = c.Client_ID
                WHERE o.Order_ID = %s
                FOR UPDATE
                """,
                (int(order_id),),
            )
            res = cursor.fetchone()
            if not res:
                raise ValueError("Order or Client not found.")

            total_ttc = Decimal(str(res["Total_Amount_TTC"])).quantize(Decimal("0.01"))
            dp_cash = Decimal(str(downpayment_cash or "0.00")).quantize(Decimal("0.01"))
            dp_wallet = Decimal(str(downpayment_wallet or "0.00")).quantize(Decimal("0.01"))
            total_downpayment = (dp_cash + dp_wallet).quantize(Decimal("0.01"))

            if total_downpayment > total_ttc:
                raise SplitPaymentMismatchException("Downpayment cannot exceed order Total TTC.")

            remaining_credit = (total_ttc - total_downpayment).quantize(Decimal("0.01"))
            prior_debt = Decimal(str(res["Current_Debt"])).quantize(Decimal("0.01"))
            credit_limit = Decimal(str(res["Credit_Limit"])).quantize(Decimal("0.01"))
            new_total_debt = (prior_debt + remaining_credit).quantize(Decimal("0.01"))

            if new_total_debt > credit_limit:
                raise ValueError(
                    f"Credit ceiling exceeded. Limit: {credit_limit}, Prior Debt: {prior_debt}, "
                    f"Requested Credit: {remaining_credit}, New Total Debt: {new_total_debt}"
                )

            # 3. Create Bon Crédit Invoice
            inv_num = f"FAC-CR-{datetime.now().strftime('%Y%m%d')}-{order_id}"
            total_ht = (total_ttc / Decimal("1.19")).quantize(Decimal("0.01"))
            total_tva = (total_ttc - total_ht).quantize(Decimal("0.01"))

            cursor.execute(
                """
                INSERT INTO Sales_Invoices (
                    Invoice_No, Order_ID, Client_ID, Invoice_Date, Status,
                    Total_Amount_HT, Total_TVA, Total_Amount_TTC,
                    Created_By, Cash_Session_ID, Payment_Method,
                    Bond_Settlement_Type, Amount_Paid_Cash, Amount_Paid_Wallet,
                    Amount_Remaining_Credit
                ) VALUES (%s, %s, %s, CURDATE(), 'Validated', %s, %s, %s, %s, %s, 'Other', 'BON_CREDIT', %s, %s, %s)
                """,
                (
                    inv_num,
                    int(order_id),
                    int(res["Client_ID"]),
                    total_ht,
                    total_tva,
                    total_ttc,
                    int(cashier_user_id),
                    int(cash_session_id) if cash_session_id else None,
                    dp_cash,
                    dp_wallet,
                    remaining_credit,
                ),
            )
            invoice_id = cursor.lastrowid

            # 4. Debit wallet if downpayment_wallet > 0
            if dp_wallet > Decimal("0.00"):
                self._debit_client_wallet_locked(
                    cursor,
                    int(res["Client_ID"]),
                    dp_wallet,
                    invoice_id,
                    int(cashier_user_id),
                    f"Acompte portefeuille sur Bon Crédit #{inv_num}",
                )

            # 5. Update physical Caisse session if cash downpayment was paid
            if cash_session_id and dp_cash > Decimal("0.00"):
                cursor.execute(
                    """
                    UPDATE POS_Cash_Sessions
                    SET Expected_Cash = COALESCE(Expected_Cash, 0.00) + %s
                    WHERE Cash_Session_ID = %s
                    """,
                    (dp_cash, int(cash_session_id)),
                )

            # 6. Record immutable Admin Approval Audit Log
            auth_hash = hashlib.sha256(
                f"{order_id}:{admin_user_id}:{remaining_credit}:{datetime.now().isoformat()}".encode("utf-8")
            ).hexdigest()
            cursor.execute(
                """
                INSERT INTO Sales_Invoices_Credit_Approvals (
                    Invoice_ID, Order_ID, Client_ID, Admin_User_ID,
                    Authorization_Code_Hash, Client_Prior_Debt, Client_Credit_Limit,
                    Approved_Credit_Amount, Downpayment_Amount, Admin_Notes, Terminal_IP
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    invoice_id,
                    int(order_id),
                    int(res["Client_ID"]),
                    int(admin_user_id),
                    auth_hash,
                    prior_debt,
                    credit_limit,
                    remaining_credit,
                    total_downpayment,
                    admin_notes,
                    terminal_ip,
                ),
            )

            # 7. Update Client Outstanding Debt
            cursor.execute(
                """
                UPDATE Clients
                SET Current_Debt = COALESCE(Current_Debt, 0.00) + %s
                WHERE Client_ID = %s
                """,
                (remaining_credit, int(res["Client_ID"])),
            )

            # 8. Generate Payment Schedule Installments
            if remaining_credit > Decimal("0.00") and installments_count >= 1:
                inst_count = max(1, int(installments_count))
                base_inst = (remaining_credit / inst_count).quantize(Decimal("0.01"))
                allocated = Decimal("0.00")
                for idx in range(1, inst_count + 1):
                    amt = (remaining_credit - allocated) if idx == inst_count else base_inst
                    allocated += amt
                    due_dt = (date.today() + timedelta(days=30 * idx)).isoformat()
                    cursor.execute(
                        """
                        INSERT INTO Client_Payment_Schedules (
                            Invoice_ID, Client_ID, Installment_Number, Due_Date, Amount_Due, Status
                        ) VALUES (%s, %s, %s, %s, %s, 'PENDING')
                        """,
                        (invoice_id, int(res["Client_ID"]), idx, due_dt, amt),
                    )

            # 9. Advance Order to Dispatch Queue
            cursor.execute(
                """
                UPDATE Sales_Orders_Theoretical
                SET Status = 'APPROVED_CREDIT_PENDING_DISPATCH'
                WHERE Order_ID = %s
                """,
                (int(order_id),),
            )

            conn.commit()
            return {
                "success": True,
                "invoice_id": invoice_id,
                "invoice_number": inv_num,
                "approved_credit_amount": float(remaining_credit),
                "downpayment_paid": float(total_downpayment),
                "new_client_debt": float(new_total_debt),
                "status": "APPROVED_CREDIT_PENDING_DISPATCH",
            }
        except Exception as err:
            conn.rollback()
            logger.error(f"Error authorizing Bon Crédit: {err}")
            raise
        finally:
            cursor.close()
            if hasattr(self.db, "get_raw_connection"):
                conn.close()

    def validate_bon_livraison_advance(
        self,
        order_id: int,
        cashier_user_id: int,
        cash_session_id: Optional[int],
        advance_cash: Decimal = Decimal("0.00"),
        advance_wallet: Decimal = Decimal("0.00"),
    ) -> Dict[str, Any]:
        """
        Validates a Bon de Livraison (سند توصيل مع الدفع عند الاستلام) at the Caisse before dispatch.
        Allows recording an optional advance deposit (تسبيق مالي) in Caisse, unlocking the order for Dispatch,
        with the remaining balance to be settled upon delivery return.
        """
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if hasattr(conn, "start_transaction"):
                conn.start_transaction()

            cursor.execute(
                """
                SELECT Order_ID, Client_ID, Total_Amount_TTC, Status
                FROM Sales_Orders_Theoretical
                WHERE Order_ID = %s
                FOR UPDATE
                """,
                (int(order_id),),
            )
            order = cursor.fetchone()
            if not order:
                raise ValueError("Order not found.")

            total_ttc = Decimal(str(order["Total_Amount_TTC"])).quantize(Decimal("0.01"))
            adv_cash = Decimal(str(advance_cash or "0.00")).quantize(Decimal("0.01"))
            adv_wallet = Decimal(str(advance_wallet or "0.00")).quantize(Decimal("0.01"))
            total_advance = (adv_cash + adv_wallet).quantize(Decimal("0.01"))

            if total_advance > total_ttc:
                raise SplitPaymentMismatchException("Advance payment cannot exceed total order TTC.")

            remaining_cod = (total_ttc - total_advance).quantize(Decimal("0.01"))
            inv_num = f"BL-LIV-{datetime.now().strftime('%Y%m%d')}-{order_id}"
            total_ht = (total_ttc / Decimal("1.19")).quantize(Decimal("0.01"))
            total_tva = (total_ttc - total_ht).quantize(Decimal("0.01"))
            inv_status = "Paid" if remaining_cod == Decimal("0.00") else "Validated"

            cursor.execute(
                """
                INSERT INTO Sales_Invoices (
                    Invoice_No, Order_ID, Client_ID, Invoice_Date, Status,
                    Total_Amount_HT, Total_TVA, Total_Amount_TTC,
                    Created_By, Cash_Session_ID, Payment_Method,
                    Bond_Settlement_Type, Amount_Paid_Cash, Amount_Paid_Wallet,
                    Amount_Remaining_Credit, Delivery_Status
                ) VALUES (%s, %s, %s, CURDATE(), %s, %s, %s, %s, %s, %s, 'Cash', 'BON_LIVRAISON', %s, %s, %s, 'PENDING_DISPATCH')
                """,
                (
                    inv_num,
                    int(order_id),
                    int(order["Client_ID"]),
                    inv_status,
                    total_ht,
                    total_tva,
                    total_ttc,
                    int(cashier_user_id),
                    int(cash_session_id) if cash_session_id else None,
                    adv_cash,
                    adv_wallet,
                    remaining_cod,
                ),
            )
            invoice_id = cursor.lastrowid

            if adv_wallet > Decimal("0.00"):
                self._debit_client_wallet_locked(
                    cursor,
                    int(order["Client_ID"]),
                    adv_wallet,
                    invoice_id,
                    int(cashier_user_id),
                    f"Avance portefeuille sur Bon de Livraison #{inv_num}",
                )

            if cash_session_id and adv_cash > Decimal("0.00"):
                cursor.execute(
                    """
                    UPDATE POS_Cash_Sessions
                    SET Expected_Cash = COALESCE(Expected_Cash, 0.00) + %s
                    WHERE Cash_Session_ID = %s
                    """,
                    (adv_cash, int(cash_session_id)),
                )

            cursor.execute(
                """
                UPDATE Sales_Orders_Theoretical
                SET Status = 'APPROVED_LIVRAISON_PENDING_DISPATCH'
                WHERE Order_ID = %s
                """,
                (int(order_id),),
            )

            conn.commit()
            return {
                "success": True,
                "invoice_id": invoice_id,
                "invoice_number": inv_num,
                "advance_paid": float(total_advance),
                "remaining_on_delivery": float(remaining_cod),
                "status": "APPROVED_LIVRAISON_PENDING_DISPATCH",
            }
        except Exception as err:
            conn.rollback()
            logger.error(f"Error validating Bon de Livraison advance: {err}")
            raise
        finally:
            cursor.close()
            if hasattr(self.db, "get_raw_connection"):
                conn.close()

    def settle_bon_livraison_cod(
        self,
        invoice_id: int,
        cashier_user_id: int,
        cash_session_id: Optional[int],
        collected_cash: Decimal,
    ) -> Dict[str, Any]:
        """
        Completes the remaining payment of a Bon de Livraison after delivery to the customer (استكمال الباقي بعد التوصيل).
        """
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if hasattr(conn, "start_transaction"):
                conn.start_transaction()

            cursor.execute(
                """
                SELECT Invoice_ID, Order_ID, Client_ID, Amount_Paid_Cash, Amount_Remaining_Credit
                FROM Sales_Invoices
                WHERE Invoice_ID = %s
                FOR UPDATE
                """,
                (int(invoice_id),),
            )
            inv = cursor.fetchone()
            if not inv:
                raise ValueError("Delivery invoice not found.")

            rem_due = Decimal(str(inv.get("Amount_Remaining_Credit") or "0.00")).quantize(Decimal("0.01"))
            cash_in = Decimal(str(collected_cash)).quantize(Decimal("0.01"))
            if cash_in < rem_due:
                raise ValueError(f"Collected COD cash ({cash_in}) is less than remaining balance ({rem_due}).")

            cursor.execute(
                """
                UPDATE Sales_Invoices
                SET Status = 'Paid',
                    Amount_Paid_Cash = COALESCE(Amount_Paid_Cash, 0.00) + %s,
                    Amount_Remaining_Credit = 0.00,
                    Delivery_Status = 'DELIVERED_PAID'
                WHERE Invoice_ID = %s
                """,
                (rem_due, int(invoice_id)),
            )

            if cash_session_id and rem_due > Decimal("0.00"):
                cursor.execute(
                    """
                    UPDATE POS_Cash_Sessions
                    SET Expected_Cash = COALESCE(Expected_Cash, 0.00) + %s
                    WHERE Cash_Session_ID = %s
                    """,
                    (rem_due, int(cash_session_id)),
                )

            if inv.get("Order_ID"):
                cursor.execute(
                    """
                    UPDATE Sales_Orders_Theoretical
                    SET Status = 'COMPLETED'
                    WHERE Order_ID = %s
                    """,
                    (int(inv["Order_ID"]),),
                )

            conn.commit()
            return {
                "success": True,
                "invoice_id": int(invoice_id),
                "settled_cod_amount": float(rem_due),
                "delivery_status": "DELIVERED_PAID",
            }
        except Exception as err:
            conn.rollback()
            logger.error(f"Error settling Bon de Livraison COD: {err}")
            raise
        finally:
            cursor.close()
            if hasattr(self.db, "get_raw_connection"):
                conn.close()

    # =========================================================================
    # 4. DISPATCH DESK (مكتب إخراج السلع والمخزن - Bon de Sortie)
    # =========================================================================

    def validate_and_dispatch_serials(
        self,
        order_id: int,
        invoice_id: int,
        storekeeper_user_id: int,
        scanned_serial_numbers: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Executes physical serial assignment and issues a Bon de Sortie (سند الخروج) at the Dispatch Desk.
        - Uses pessimistic row-level locking (SELECT ... FOR UPDATE) on Product_Serials.
        - Prevents double-dispatch race conditions across concurrent loading docks (StateCollisionException).
        - Zero cash impact (strictly logistical).
        - Activates customer warranty clock and decrements physical & theoretical batch stock.
        """
        if not scanned_serial_numbers:
            raise ValueError("At least one scanned serial number is required to emit a Bon de Sortie.")

        max_retries = 3
        for attempt in range(max_retries):
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            try:
                if hasattr(conn, "start_transaction"):
                    conn.start_transaction()

                cursor.execute(
                    """
                    SELECT Order_ID, Status, Bond_Type, Client_ID
                    FROM Sales_Orders_Theoretical
                    WHERE Order_ID = %s
                    FOR UPDATE
                    """,
                    (int(order_id),),
                )
                order_row = cursor.fetchone()
                if order_row:
                    st = order_row.get("Status")
                    if st in ("CANCELLED", "REJECTED"):
                        raise SecurityViolationException(
                            f"Sortie physique non autorisée : La commande #{order_id} est annulée/rejetée ({st})."
                        )

                exit_num = f"BS-{datetime.now().strftime('%Y%m%d')}-{order_id}-{int(datetime.now().timestamp() * 1000) % 10000:04d}"
                gate_pass = f"GATE-{hashlib.sha1(exit_num.encode('utf-8')).hexdigest()[:12].upper()}"

                cursor.execute(
                    """
                    INSERT INTO Delivery_Exit_Bonds (
                        Exit_Bond_Number, Order_ID, Invoice_ID, Storekeeper_User_ID,
                        Security_Gate_Pass_Barcode, Exit_Status
                    ) VALUES (%s, %s, %s, %s, %s, 'VALIDATED_EXIT')
                    """,
                    (exit_num, int(order_id), int(invoice_id), int(storekeeper_user_id), gate_pass),
                )
                exit_bond_id = cursor.lastrowid

                seen_serials = set()
                for scan in scanned_serial_numbers:
                    line_id = int(scan["order_line_id"])
                    sn_clean = SerialTrackingManager.sanitize_serial_number(scan["serial_number"])
                    if sn_clean in seen_serials:
                        raise StateCollisionException(f"Duplicate scan of serial '{sn_clean}' in the same exit voucher.")
                    seen_serials.add(sn_clean)

                    # Lock theoretical order line
                    cursor.execute(
                        """
                        SELECT Product_ID, Quantity_Ordered, Quantity_Dispatched
                        FROM Sales_Order_Lines_Theoretical
                        WHERE Line_ID = %s
                        FOR UPDATE
                        """,
                        (line_id,),
                    )
                    line = cursor.fetchone()
                    if not line:
                        raise ValueError(f"Order line {line_id} not found.")

                    # Lock physical serial record with SELECT ... FOR UPDATE
                    cursor.execute(
                        """
                        SELECT Serial_ID, Product_ID, Batch_ID, Status
                        FROM Product_Serials
                        WHERE Serial_Number = %s
                        FOR UPDATE
                        """,
                        (sn_clean,),
                    )
                    serial_record = cursor.fetchone()

                    if not serial_record:
                        raise ValueError(f"Serial number '{sn_clean}' does not exist in master registry.")
                    if serial_record["Status"] != "IN_STOCK":
                        raise StateCollisionException(
                            f"Serial '{sn_clean}' is not IN_STOCK (Current Status: {serial_record['Status']})."
                        )
                    if int(serial_record["Product_ID"]) != int(line["Product_ID"]):
                        raise ValueError(
                            f"Model mismatch: Serial '{sn_clean}' belongs to Product {serial_record['Product_ID']}, "
                            f"expected Product {line['Product_ID']}."
                        )

                    serial_id = serial_record["Serial_ID"]
                    batch_id = serial_record["Batch_ID"]

                    # A. Bind serial to Delivery_Exit_Serials
                    cursor.execute(
                        """
                        INSERT INTO Delivery_Exit_Serials (
                            Exit_Bond_ID, Order_Line_ID, Product_ID, Serial_ID,
                            Scanned_Barcode, Scanned_By_User_ID
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (exit_bond_id, line_id, int(line["Product_ID"]), serial_id, sn_clean, int(storekeeper_user_id)),
                    )

                    # B. Update Serial Status to DISPATCHED and initiate warranty
                    cursor.execute(
                        """
                        UPDATE Product_Serials
                        SET Status = 'DISPATCHED',
                            Customer_Warranty_Start = CURRENT_DATE(),
                            Customer_Warranty_End = DATE_ADD(CURRENT_DATE(), INTERVAL 24 MONTH),
                            Original_Sales_Invoice_ID = %s
                        WHERE Serial_ID = %s
                        """,
                        (int(invoice_id), serial_id),
                    )

                    # C. Record Immutable Serial History
                    cursor.execute(
                        """
                        INSERT INTO Product_Serial_History (
                            Serial_ID, Previous_Status, New_Status, Voucher_Type,
                            Voucher_ID, Changed_By_User_ID, Action_Notes
                        ) VALUES (%s, 'IN_STOCK', 'DISPATCHED', 'BON_SORTIE', %s, %s, 'Exit Desk Physical Scan')
                        """,
                        (serial_id, exit_bond_id, int(storekeeper_user_id)),
                    )

                    # D. Decrement Physical & Theoretical Inventory on Batch
                    cursor.execute(
                        """
                        UPDATE Inventory_Batches
                        SET Quantity_Current = GREATEST(0, Quantity_Current - 1),
                            Theoretical_Reserved_Qty = GREATEST(0, COALESCE(Theoretical_Reserved_Qty, 1) - 1)
                        WHERE Batch_ID = %s
                        """,
                        (batch_id,),
                    )

                    # E. Increment line dispatched counter
                    cursor.execute(
                        """
                        UPDATE Sales_Order_Lines_Theoretical
                        SET Quantity_Dispatched = Quantity_Dispatched + 1
                        WHERE Line_ID = %s
                        """,
                        (line_id,),
                    )

                    # F. Record Physical Exit in Stock_Movement_Log (Traçabilité)
                    try:
                        cursor.execute(
                            "SELECT SUM(Quantity_Current) AS Total_Stock FROM Inventory_Batches WHERE Product_ID = %s",
                            (int(line["Product_ID"]),),
                        )
                        stk_row = cursor.fetchone()
                        stk_after = (stk_row.get("Total_Stock") if isinstance(stk_row, dict) else stk_row[0]) if stk_row else 0
                        cursor.execute(
                            """
                            INSERT INTO Stock_Movement_Log (
                                Product_ID, Batch_ID, Movement_Type, Qty_Change, Unit_Used,
                                Notes, User_ID, Transaction_Date, Stock_After
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s)
                            """,
                            (
                                int(line["Product_ID"]),
                                batch_id,
                                'Sale',
                                -1,
                                'Pièce',
                                f"Bon de Sortie {exit_num} - N° Série: {sn_clean} (Réf Commande #{order_id})",
                                int(storekeeper_user_id),
                                stk_after,
                            ),
                        )
                    except Exception as log_err:
                        logger.warning(f"Could not record Stock_Movement_Log for serial exit {sn_clean}: {log_err}")

                # Update order status (if Bon de Livraison still has COD remaining, mark DISPATCHED_PENDING_COD)
                cursor.execute(
                    """
                    SELECT Bond_Type FROM Sales_Orders_Theoretical WHERE Order_ID = %s
                    """,
                    (int(order_id),),
                )
                ord_row = cursor.fetchone()
                next_status = "COMPLETED"
                if ord_row and ord_row.get("Bond_Type") == "BON_LIVRAISON":
                    cursor.execute(
                        "SELECT Amount_Remaining_Credit FROM Sales_Invoices WHERE Invoice_ID = %s",
                        (int(invoice_id),),
                    )
                    inv_row = cursor.fetchone()
                    if inv_row and Decimal(str(inv_row.get("Amount_Remaining_Credit") or "0.00")) > Decimal("0.00"):
                        next_status = "DISPATCHED_PENDING_COD"

                cursor.execute(
                    """
                    UPDATE Sales_Orders_Theoretical
                    SET Status = %s
                    WHERE Order_ID = %s
                    """,
                    (next_status, int(order_id)),
                )

                conn.commit()
                return {
                    "success": True,
                    "exit_bond_id": exit_bond_id,
                    "exit_bond_number": exit_num,
                    "gate_pass": gate_pass,
                    "financial_impact": "NONE",
                    "order_status": next_status,
                }
            except mysql.connector.Error as db_err:
                conn.rollback()
                if getattr(db_err, "errno", None) in (1213, 1205) and attempt < max_retries - 1:
                    wait_sec = ((2 ** attempt) * 0.025) + random.uniform(0.0, 0.015)
                    time.sleep(wait_sec)
                    continue
                raise
            except Exception:
                conn.rollback()
                raise
            finally:
                cursor.close()
                if hasattr(self.db, "get_raw_connection"):
                    conn.close()

    # =========================================================================
    # 5. BON DE RETOUR & VERSEMENT VIRTUEL (إرجاع السلع مع حماية سيولة الصندوق)
    # =========================================================================

    def process_bon_retour(
        self,
        original_invoice_id: int,
        client_id: int,
        received_by_user_id: int,
        return_reason: str,
        returned_serials: List[Dict[str, Any]],
        verify_dispatched_on_invoice: bool = True,
    ) -> Dict[str, Any]:
        """
        Processes a Bon de Retour (سند إرجاع) and issues a Versement Virtuel into the customer's wallet.
        - Verifies that each returned serial was actually dispatched on the referenced invoice (prevents Serial Swap Fraud).
        - Updates physical serial state based on inspection:
          - LIKE_NEW_RESTOCK / MINOR_BLEMISH_RESTOCK -> IN_STOCK (and increments batch Quantity_Current)
          - DEFECTIVE_NEEDS_SAV -> IN_SAV
          - SCRAP_TOTAL_LOSS -> SCRAPPED
        - Strictly credits Client_Wallets (RETURN_VIRTUAL_CREDIT) with ZERO impact on physical Caisse (Δ Till_Balance = 0.00 DA).
        """
        if not returned_serials:
            raise ValueError("Bon de Retour requires at least one returned serial item.")

        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if hasattr(conn, "start_transaction"):
                conn.start_transaction()

            total_return_val = sum(
                Decimal(str(item["unit_credit_value"])).quantize(Decimal("0.01"))
                for item in returned_serials
            )
            ret_num = f"BR-RET-{datetime.now().strftime('%Y%m%d')}-{int(datetime.now().timestamp() * 1000) % 100000:05d}"

            cursor.execute(
                """
                INSERT INTO Return_Bonds (
                    Return_Bond_Number, Original_Invoice_ID, Client_ID,
                    Received_By_User_ID, Return_Reason, Total_Return_Value, Return_Status
                ) VALUES (%s, %s, %s, %s, %s, %s, 'APPROVED_VIRTUAL_CREDITED')
                """,
                (
                    ret_num,
                    int(original_invoice_id),
                    int(client_id),
                    int(received_by_user_id),
                    return_reason,
                    total_return_val,
                ),
            )
            return_bond_id = cursor.lastrowid

            for item in returned_serials:
                sn_clean = SerialTrackingManager.sanitize_serial_number(item["serial_number"])
                condition = item.get("inspection_condition", "LIKE_NEW_RESTOCK")
                unit_val = Decimal(str(item["unit_credit_value"])).quantize(Decimal("0.01"))

                cursor.execute(
                    """
                    SELECT Serial_ID, Product_ID, Batch_ID, Status, Original_Sales_Invoice_ID
                    FROM Product_Serials
                    WHERE Serial_Number = %s
                    FOR UPDATE
                    """,
                    (sn_clean,),
                )
                s_row = cursor.fetchone()
                if not s_row:
                    raise SecurityViolationException(f"Returned serial '{sn_clean}' does not exist in registry.")

                if verify_dispatched_on_invoice and s_row.get("Original_Sales_Invoice_ID") is not None:
                    if int(s_row["Original_Sales_Invoice_ID"]) != int(original_invoice_id):
                        raise SecurityViolationException(
                            f"Serial mismatch: Serial '{sn_clean}' was never dispatched on Invoice #{original_invoice_id}."
                        )

                if condition in ("LIKE_NEW_RESTOCK", "MINOR_BLEMISH_RESTOCK"):
                    new_serial_status = "IN_STOCK"
                    cursor.execute(
                        """
                        UPDATE Inventory_Batches
                        SET Quantity_Current = Quantity_Current + 1
                        WHERE Batch_ID = %s
                        """,
                        (s_row["Batch_ID"],),
                    )
                    # Record Return in Stock_Movement_Log (Traçabilité)
                    try:
                        cursor.execute(
                            "SELECT SUM(Quantity_Current) AS Total_Stock FROM Inventory_Batches WHERE Product_ID = %s",
                            (prod_id,),
                        )
                        stk_row = cursor.fetchone()
                        stk_after = (stk_row.get("Total_Stock") if isinstance(stk_row, dict) else stk_row[0]) if stk_row else 0
                        cursor.execute(
                            """
                            INSERT INTO Stock_Movement_Log (
                                Product_ID, Batch_ID, Movement_Type, Qty_Change, Unit_Used,
                                Notes, User_ID, Transaction_Date, Stock_After
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s)
                            """,
                            (
                                prod_id,
                                s_row["Batch_ID"],
                                'Sale_Return',
                                1,
                                'Pièce',
                                f"Bon de Retour {br_number} - N° Série: {sn_clean}",
                                int(storekeeper_user_id),
                                stk_after,
                            ),
                        )
                    except Exception as log_err:
                        logger.warning(f"Could not record Stock_Movement_Log for return {sn_clean}: {log_err}")
                elif condition == "DEFECTIVE_NEEDS_SAV":
                    new_serial_status = "IN_SAV"
                else:
                    new_serial_status = "SCRAPPED"

                cursor.execute(
                    """
                    UPDATE Product_Serials
                    SET Status = %s, Last_Inspected_At = CURRENT_TIMESTAMP
                    WHERE Serial_ID = %s
                    """,
                    (new_serial_status, s_row["Serial_ID"]),
                )

                cursor.execute(
                    """
                    INSERT INTO Return_Bond_Serials (
                        Return_Bond_ID, Serial_ID, Inspection_Condition, Unit_Credit_Value, Target_Batch_ID
                    ) VALUES (%s, %s, %s, %s, %s)
                    """,
                    (return_bond_id, s_row["Serial_ID"], condition, unit_val, s_row["Batch_ID"]),
                )

                cursor.execute(
                    """
                    INSERT INTO Product_Serial_History (
                        Serial_ID, Previous_Status, New_Status, Voucher_Type,
                        Voucher_ID, Changed_By_User_ID, Action_Notes
                    ) VALUES (%s, %s, %s, 'BON_RETOUR', %s, %s, %s)
                    """,
                    (
                        s_row["Serial_ID"],
                        s_row["Status"],
                        new_serial_status,
                        return_bond_id,
                        int(received_by_user_id),
                        f"Return condition: {condition}",
                    ),
                )

            # Issue Versement Virtuel into Client_Wallets (ZERO physical cash drawer impact!)
            wallet = self._get_or_create_wallet_locked(cursor, client_id)
            bal_before = wallet["Current_Balance"]
            bal_after = (bal_before + total_return_val).quantize(Decimal("0.01"))
            virt_after = (wallet["Virtual_Credit_Balance"] + total_return_val).quantize(Decimal("0.01"))

            cursor.execute(
                """
                INSERT INTO Client_Wallet_Transactions (
                    Wallet_ID, Client_ID, Transaction_Type, Amount,
                    Balance_Before, Balance_After, Source_Document_Type,
                    Source_Document_ID, Authorized_By_User_ID,
                    Affects_Physical_Caisse, Transaction_Notes
                ) VALUES (%s, %s, 'RETURN_VIRTUAL_CREDIT', %s, %s, %s, 'BON_RETOUR', %s, %s, FALSE, %s)
                """,
                (
                    wallet["Wallet_ID"],
                    int(client_id),
                    total_return_val,
                    bal_before,
                    bal_after,
                    return_bond_id,
                    int(received_by_user_id),
                    f"Versement Virtuel sur Bon de Retour {ret_num}",
                ),
            )
            wallet_tx_id = cursor.lastrowid

            cursor.execute(
                """
                UPDATE Client_Wallets
                SET Current_Balance = %s,
                    Virtual_Credit_Balance = %s,
                    Total_Lifetime_Credited = COALESCE(Total_Lifetime_Credited, 0.00) + %s,
                    Last_Transaction_At = CURRENT_TIMESTAMP
                WHERE Wallet_ID = %s
                """,
                (bal_after, virt_after, total_return_val, wallet["Wallet_ID"]),
            )

            cursor.execute(
                """
                UPDATE Return_Bonds
                SET Wallet_Credit_Transaction_ID = %s
                WHERE Return_Bond_ID = %s
                """,
                (wallet_tx_id, return_bond_id),
            )

            conn.commit()
            return {
                "success": True,
                "return_bond_id": return_bond_id,
                "return_bond_number": ret_num,
                "wallet_transaction_id": wallet_tx_id,
                "credited_virtual_amount": float(total_return_val),
                "new_wallet_balance": float(bal_after),
                "physical_till_delta": 0.0,
            }
        except Exception as err:
            conn.rollback()
            logger.error(f"Error processing Bon de Retour: {err}")
            raise
        finally:
            cursor.close()
            if hasattr(self.db, "get_raw_connection"):
                conn.close()

    # =========================================================================
    # 6. QUEUE QUERIES FOR CAISSE & DISPATCH DESKS
    # =========================================================================

    def get_caisse_order_queue(self) -> List[Dict[str, Any]]:
        """Returns orders awaiting payment/validation at the Caisse Desk."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT
                        o.Order_ID, o.Order_Number, o.Client_ID,
                        COALESCE(c.Client_Name, 'Client Comptoir') AS Client_Name,
                        COALESCE(c.Credit_Limit, 0.00) AS Credit_Limit,
                        COALESCE(c.Current_Debt, 0.00) AS Current_Debt,
                        o.Bond_Type, o.Total_Amount_HT, o.Total_Amount_TTC,
                        o.Status, o.Payment_Method_Requested, o.Order_Date,
                        o.Delivery_Address, o.Delivery_Phone
                    FROM Sales_Orders_Theoretical o
                    LEFT JOIN Clients c ON o.Client_ID = c.Client_ID
                    WHERE o.Status IN ('CONFIRMED_PENDING_PAYMENT', 'DISPATCHED_PENDING_COD')
                    ORDER BY o.Order_Date DESC
                    LIMIT 200
                    """
                )
                return cursor.fetchall() or []
        except Exception as err:
            logger.error(f"Error fetching Caisse order queue: {err}")
            return []

    def get_dispatch_order_queue(self) -> List[Dict[str, Any]]:
        """Returns paid or approved orders awaiting physical serial scan at the Dispatch Desk."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT
                        o.Order_ID, o.Order_Number, o.Client_ID,
                        COALESCE(c.Client_Name, 'Client Comptoir') AS Client_Name,
                        o.Bond_Type, o.Total_Amount_TTC, o.Status, o.Order_Date,
                        i.Invoice_ID, i.Invoice_No
                    FROM Sales_Orders_Theoretical o
                    LEFT JOIN Clients c ON o.Client_ID = c.Client_ID
                    LEFT JOIN Sales_Invoices i ON o.Order_ID = i.Order_ID
                    WHERE o.Status IN (
                        'PAID_PENDING_DISPATCH',
                        'APPROVED_CREDIT_PENDING_DISPATCH',
                        'APPROVED_LIVRAISON_PENDING_DISPATCH',
                        'PARTIALLY_DISPATCHED'
                    )
                    ORDER BY o.Updated_At DESC
                    LIMIT 200
                    """
                )
                orders = cursor.fetchall() or []
                for ord_item in orders:
                    cursor.execute(
                        """
                        SELECT
                            l.Line_ID, l.Product_ID, p.Product_Name,
                            COALESCE(p.Brand_Mark, '') AS Brand_Mark,
                            COALESCE(l.Requested_Color, p.Color_Finish, '') AS Color_Finish,
                            COALESCE(p.Barcode, '') AS Barcode,
                            l.Quantity_Ordered, l.Quantity_Dispatched, l.Unit_Price_TTC
                        FROM Sales_Order_Lines_Theoretical l
                        JOIN Products_Master p ON l.Product_ID = p.Product_ID
                        WHERE l.Order_ID = %s
                        """,
                        (ord_item["Order_ID"],),
                    )
                    ord_item["lines"] = cursor.fetchall() or []
                return orders
        except Exception as err:
            logger.error(f"Error fetching Dispatch order queue: {err}")
            return []


# Aliases matching docs service layer names
TheoreticalSalesService = BondLifecycleManager
CashierSettlementService = BondLifecycleManager
DispatchService = BondLifecycleManager
