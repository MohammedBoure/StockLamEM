# -*- coding: utf-8 -*-
"""
database/treasury_manager.py
============================
Treasury & Multi-Method Cashbook Manager (Trésorerie & Flux Financiers).

Aggregates all real financial inflows/outflows across:
- Bureaux -> Caisse settlements (`Sales_Invoices` via Cash, BaridiMob, TPE, CCP)
- Direct POS sales (`POS_Sale_Payments` when not already tracked on `Sales_Invoices`)
- Client installments & real cash deposits (`Client_Payments`: Versement, Paiement Livraison, Règlements)
- POS Cash Drawer adjustments (`POS_Cash_Movements`)
- Manual Treasury operations (`Treasury_Movements`: Entrée, Sortie, Transfert Interne)

Note: Virtual client wallet credits (`Bon de Retour`, `SAV Irréparable`) have zero
physical liquidity impact (`Affects_Physical_Caisse = FALSE`) and are excluded.
"""

from datetime import date, datetime
from decimal import Decimal
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("StockLam.Backend.Treasury")

CANONICAL_PAYMENT_METHODS: Tuple[str, ...] = ("Cash", "BaridiMob", "TPE", "CCP")

_METHOD_ALIASES: Dict[str, str] = {
    "cash": "Cash",
    "espece": "Cash",
    "espèce": "Cash",
    "especes": "Cash",
    "espèces": "Cash",
    "versement": "Cash",
    "baridimob": "BaridiMob",
    "baridi_mob": "BaridiMob",
    "tpe": "TPE",
    "card": "TPE",
    "carte": "TPE",
    "cib": "TPE",
    "ccp": "CCP",
    "transfer": "CCP",
    "virement": "CCP",
    "cheque": "CCP",
    "chèque": "CCP",
}

ENTRY_CATEGORIES: Tuple[str, ...] = (
    "Fond de caisse (Ouverture)",
    "Apport exploitant / Associé",
    "Encaissement divers",
    "Remboursement reçu",
    "Régularisation (+)",
)

EXIT_CATEGORIES: Tuple[str, ...] = (
    "Dépense / Charges",
    "Retrait / Versement Banque",
    "Paiement Fournisseur",
    "Salaire / Avance employé",
    "Transport / Livraison",
    "Remboursement Client",
    "Régularisation (-)",
)


def normalize_treasury_method(method: Optional[str]) -> str:
    """Maps any payment method label to one of Cash, BaridiMob, TPE, CCP."""
    raw = str(method or "").strip()
    if not raw:
        return "Cash"
    return _METHOD_ALIASES.get(raw.lower(), "Cash")


def _to_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0.00")).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def _to_iso_datetime(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d 00:00:00")
    s = str(value).strip()
    if len(s) == 10:
        return f"{s} 00:00:00"
    return s[:19].replace("T", " ")


class TreasuryManager:
    """Manages treasury accounts by payment method and the unified financial ledger."""

    _schema_checked = False

    def __init__(self, db_instance):
        self.db = db_instance
        self._ensure_schema()

    def _get_connection(self):
        if self.db is None:
            return None
        if hasattr(self.db, "get_raw_connection"):
            conn = self.db.get_raw_connection()
            if conn is not None:
                return conn
        if hasattr(self.db, "get_connection"):
            return self.db.get_connection()
        if hasattr(self.db, "cursor"):
            return self.db
        return None

    def _close_conn(self, conn) -> None:
        if conn is not None and hasattr(self.db, "get_raw_connection") and hasattr(conn, "close"):
            try:
                conn.close()
            except Exception:
                pass

    def _ensure_schema(self) -> None:
        if TreasuryManager._schema_checked or self.db is None:
            return
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            if conn is None or not hasattr(conn, "cursor"):
                return
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS Treasury_Movements (
                    Movement_ID BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    Movement_Code VARCHAR(64) NOT NULL UNIQUE,
                    Direction ENUM('IN', 'OUT') NOT NULL,
                    Operation_Type VARCHAR(32) NOT NULL DEFAULT 'MANUAL_IN',
                    Payment_Method VARCHAR(64) NOT NULL DEFAULT 'Cash',
                    Amount DECIMAL(15, 2) NOT NULL,
                    Category VARCHAR(100) NULL,
                    Reason VARCHAR(255) NOT NULL,
                    Reference VARCHAR(120) NULL,
                    Counterparty VARCHAR(150) NULL,
                    Transfer_Group_ID VARCHAR(64) NULL,
                    Notes TEXT NULL,
                    Movement_Date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    Created_By INT UNSIGNED NULL,
                    Is_Cancelled BOOLEAN NOT NULL DEFAULT FALSE,
                    Cancelled_By INT UNSIGNED NULL,
                    Cancelled_At DATETIME NULL,
                    Created_At DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_tm_date (Movement_Date),
                    INDEX idx_tm_method (Payment_Method),
                    INDEX idx_tm_dir (Direction),
                    INDEX idx_tm_transfer (Transfer_Group_ID)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )

            # Ensure Sales_Invoices.Payment_Method and Client_Payments.Payment_Method
            # can store BaridiMob / TPE / CCP without MySQL ENUM truncation.
            for tbl in ("Sales_Invoices", "Client_Payments"):
                try:
                    cursor.execute(f"SHOW COLUMNS FROM {tbl} LIKE 'Payment_Method'")
                    col = cursor.fetchone()
                    if isinstance(col, dict):
                        ctype = str(col.get("Type") or "").lower()
                        if ctype.startswith("enum(") and "baridimob" not in ctype:
                            cursor.execute(
                                f"ALTER TABLE {tbl} MODIFY COLUMN Payment_Method VARCHAR(64) NOT NULL DEFAULT 'Cash'"
                            )
                except Exception as col_err:
                    logger.debug(f"Payment_Method column check skipped on {tbl}: {col_err}")

            if hasattr(conn, "commit"):
                conn.commit()
            TreasuryManager._schema_checked = True
        except Exception as exc:
            logger.debug(f"Treasury schema check skipped: {exc}")
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            self._close_conn(conn)

    # =========================================================================
    # WRITE OPERATIONS (Entrée, Sortie, Transfert, Annulation)
    # =========================================================================

    def record_movement(
        self,
        direction: str,
        payment_method: str,
        amount: Any,
        reason: str,
        category: str = "",
        reference: str = "",
        counterparty: str = "",
        notes: str = "",
        operation_type: Optional[str] = None,
        movement_date: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Records a manual cash/bank/mobile inflow (Entrée) or outflow (Sortie)."""
        dir_norm = str(direction or "").strip().upper()
        if dir_norm not in ("IN", "OUT"):
            raise ValueError("Le sens du mouvement doit être 'IN' (Entrée) ou 'OUT' (Sortie).")

        amt = _to_decimal(amount)
        if amt <= Decimal("0.00"):
            raise ValueError("Le montant doit être strictement supérieur à 0,00 DA.")

        reason_clean = str(reason or "").strip()
        if not reason_clean:
            raise ValueError("Le motif / libellé de l'opération est obligatoire.")

        method_norm = normalize_treasury_method(payment_method)
        op_type = (operation_type or ("MANUAL_IN" if dir_norm == "IN" else "MANUAL_OUT")).strip().upper()
        cat_clean = str(category or "").strip()[:100]
        ref_clean = str(reference or "").strip()[:120]
        cp_clean = str(counterparty or "").strip()[:150]
        notes_clean = str(notes or "").strip()

        if movement_date:
            dt_str = _to_iso_datetime(movement_date)
        else:
            dt_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        prefix = "TR-IN" if dir_norm == "IN" else "TR-OUT"
        code = f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        conn = self._get_connection()
        if conn is None:
            raise RuntimeError("Connexion base de données indisponible.")
        cursor = conn.cursor(dictionary=True)
        try:
            if hasattr(conn, "start_transaction") and not getattr(conn, "in_transaction", False):
                conn.start_transaction()
            cursor.execute(
                """
                INSERT INTO Treasury_Movements (
                    Movement_Code, Direction, Operation_Type, Payment_Method,
                    Amount, Category, Reason, Reference, Counterparty,
                    Notes, Movement_Date, Created_By
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    code,
                    dir_norm,
                    op_type,
                    method_norm,
                    amt,
                    cat_clean or None,
                    reason_clean[:255],
                    ref_clean or None,
                    cp_clean or None,
                    notes_clean or None,
                    dt_str,
                    int(user_id) if user_id else None,
                ),
            )
            mov_id = cursor.lastrowid
            if hasattr(conn, "commit"):
                conn.commit()
            return {
                "success": True,
                "movement_id": mov_id,
                "movement_code": code,
                "direction": dir_norm,
                "payment_method": method_norm,
                "amount": float(amt),
            }
        except Exception as exc:
            if hasattr(conn, "rollback"):
                conn.rollback()
            logger.error(f"Error recording treasury movement: {exc}")
            raise
        finally:
            cursor.close()
            self._close_conn(conn)

    def record_transfer(
        self,
        from_method: str,
        to_method: str,
        amount: Any,
        reason: str = "Transfert interne de trésorerie",
        reference: str = "",
        notes: str = "",
        movement_date: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Atomically transfers funds from one payment method account to another."""
        src = normalize_treasury_method(from_method)
        dst = normalize_treasury_method(to_method)
        if src == dst:
            raise ValueError("Le compte source et le compte destination doivent être différents.")

        amt = _to_decimal(amount)
        if amt <= Decimal("0.00"):
            raise ValueError("Le montant du transfert doit être strictement supérieur à 0,00 DA.")

        reason_clean = str(reason or "").strip() or f"Transfert {src} -> {dst}"
        ref_clean = str(reference or "").strip()[:120]
        notes_clean = str(notes or "").strip()
        dt_str = _to_iso_datetime(movement_date) if movement_date else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        group_id = f"TRF-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"

        conn = self._get_connection()
        if conn is None:
            raise RuntimeError("Connexion base de données indisponible.")
        cursor = conn.cursor(dictionary=True)
        try:
            if hasattr(conn, "start_transaction") and not getattr(conn, "in_transaction", False):
                conn.start_transaction()

            code_out = f"{group_id}-OUT"
            code_in = f"{group_id}-IN"
            uid = int(user_id) if user_id else None

            cursor.execute(
                """
                INSERT INTO Treasury_Movements (
                    Movement_Code, Direction, Operation_Type, Payment_Method,
                    Amount, Category, Reason, Reference, Counterparty,
                    Transfer_Group_ID, Notes, Movement_Date, Created_By
                ) VALUES (%s, 'OUT', 'TRANSFER_OUT', %s, %s, 'Transfert Interne', %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    code_out,
                    src,
                    amt,
                    f"{reason_clean} ({src} → {dst})"[:255],
                    ref_clean or group_id,
                    f"Vers {dst}",
                    group_id,
                    notes_clean or None,
                    dt_str,
                    uid,
                ),
            )
            out_id = cursor.lastrowid

            cursor.execute(
                """
                INSERT INTO Treasury_Movements (
                    Movement_Code, Direction, Operation_Type, Payment_Method,
                    Amount, Category, Reason, Reference, Counterparty,
                    Transfer_Group_ID, Notes, Movement_Date, Created_By
                ) VALUES (%s, 'IN', 'TRANSFER_IN', %s, %s, 'Transfert Interne', %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    code_in,
                    dst,
                    amt,
                    f"{reason_clean} ({src} → {dst})"[:255],
                    ref_clean or group_id,
                    f"Depuis {src}",
                    group_id,
                    notes_clean or None,
                    dt_str,
                    uid,
                ),
            )
            in_id = cursor.lastrowid

            if hasattr(conn, "commit"):
                conn.commit()
            return {
                "success": True,
                "transfer_group_id": group_id,
                "out_movement_id": out_id,
                "in_movement_id": in_id,
                "from_method": src,
                "to_method": dst,
                "amount": float(amt),
            }
        except Exception as exc:
            if hasattr(conn, "rollback"):
                conn.rollback()
            logger.error(f"Error recording treasury transfer: {exc}")
            raise
        finally:
            cursor.close()
            self._close_conn(conn)

    def cancel_manual_movement(self, movement_id: int, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Voids a manual treasury movement (and its linked transfer pair if applicable)."""
        conn = self._get_connection()
        if conn is None:
            raise RuntimeError("Connexion base de données indisponible.")
        cursor = conn.cursor(dictionary=True)
        try:
            if hasattr(conn, "start_transaction") and not getattr(conn, "in_transaction", False):
                conn.start_transaction()

            cursor.execute(
                """
                SELECT Movement_ID, Movement_Code, Transfer_Group_ID, Is_Cancelled
                FROM Treasury_Movements
                WHERE Movement_ID = %s
                FOR UPDATE
                """,
                (int(movement_id),),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError("Mouvement introuvable.")
            if row.get("Is_Cancelled"):
                raise ValueError("Ce mouvement est déjà annulé.")

            uid = int(user_id) if user_id else None
            grp = row.get("Transfer_Group_ID")
            if grp:
                cursor.execute(
                    """
                    UPDATE Treasury_Movements
                    SET Is_Cancelled = 1, Cancelled_By = %s, Cancelled_At = NOW()
                    WHERE Transfer_Group_ID = %s AND Is_Cancelled = 0
                    """,
                    (uid, grp),
                )
            else:
                cursor.execute(
                    """
                    UPDATE Treasury_Movements
                    SET Is_Cancelled = 1, Cancelled_By = %s, Cancelled_At = NOW()
                    WHERE Movement_ID = %s
                    """,
                    (uid, int(movement_id)),
                )

            if hasattr(conn, "commit"):
                conn.commit()
            return {
                "success": True,
                "movement_id": int(movement_id),
                "movement_code": row.get("Movement_Code"),
                "transfer_group_id": grp,
            }
        except Exception as exc:
            if hasattr(conn, "rollback"):
                conn.rollback()
            logger.error(f"Error cancelling treasury movement #{movement_id}: {exc}")
            raise
        finally:
            cursor.close()
            self._close_conn(conn)

    # =========================================================================
    # READ / AGGREGATION (Balances & Full Financial Journal)
    # =========================================================================

    def _safe_fetch_all(self, cursor, sql: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        try:
            cursor.execute(sql, params)
            return cursor.fetchall() or []
        except Exception as exc:
            logger.debug(f"Treasury query skipped ({exc}): {sql[:80]}")
            return []

    def _collect_all_raw_movements(self) -> List[Dict[str, Any]]:
        """Collects all non-cancelled financial inflows/outflows across the database."""
        movements: List[Dict[str, Any]] = []
        conn = self._get_connection()
        if conn is None or not hasattr(conn, "cursor"):
            return movements

        cursor = conn.cursor(dictionary=True)
        try:
            # 1. Sales_Invoices initial Caisse / Bon settlements
            inv_rows = self._safe_fetch_all(
                cursor,
                """
                SELECT
                    i.Invoice_ID,
                    i.Invoice_No,
                    i.Order_ID,
                    i.Invoice_Date,
                    i.Created_At,
                    i.Payment_Method,
                    i.Bond_Settlement_Type,
                    COALESCE(i.Amount_Paid_Cash, 0.00) AS Amount_Paid_Cash,
                    COALESCE(i.Amount_Paid_Card, 0.00) AS Amount_Paid_Card,
                    o.Order_Number,
                    COALESCE(c.Client_Name, 'Client Comptoir') AS Client_Name,
                    COALESCE(u.Full_Name, u.Username, 'Système') AS Operator_Name
                FROM Sales_Invoices i
                LEFT JOIN Sales_Orders_Theoretical o ON i.Order_ID = o.Order_ID
                LEFT JOIN Clients c ON i.Client_ID = c.Client_ID
                LEFT JOIN Users u ON i.Created_By = u.User_ID
                WHERE i.Status != 'Cancelled'
                  AND (COALESCE(i.Amount_Paid_Cash, 0.00) > 0 OR COALESCE(i.Amount_Paid_Card, 0.00) > 0)
                """,
            )
            settlement_labels = {
                "BON_C_CASH": "Caisse — Paiement complet",
                "BON_VERSEMENT": "Caisse — Bon Versement",
                "BON_LIVRAISON": "Caisse — Paiement Livraison",
                "BON_CREDIT": "Caisse — Acompte Crédit",
                "BON_WALLET_AVOIR": "Caisse — Portefeuille",
                "BON_MIXED": "Caisse — Mixte",
            }
            for row in inv_rows:
                cash_amt = float(row.get("Amount_Paid_Cash") or 0.0)
                card_amt = float(row.get("Amount_Paid_Card") or 0.0)
                raw_pm = str(row.get("Payment_Method") or "").strip()
                bst = str(row.get("Bond_Settlement_Type") or "").strip().upper()
                origin_label = settlement_labels.get(bst, "Caisse — Encaissement Vente")
                ts = _to_iso_datetime(row.get("Created_At") or row.get("Invoice_Date"))
                inv_no = str(row.get("Invoice_No") or f"FAC-{row.get('Invoice_ID')}")
                ord_no = str(row.get("Order_Number") or "").strip()
                ref_display = f"{inv_no}" if not ord_no else f"{inv_no} ({ord_no})"
                client_name = str(row.get("Client_Name") or "Client Comptoir")
                op_name = str(row.get("Operator_Name") or "Système")

                if cash_amt > 0.009:
                    if card_amt <= 0.009 and raw_pm in ("BaridiMob", "TPE", "CCP"):
                        pm_cash = raw_pm
                    else:
                        pm_cash = "Cash"
                    movements.append(
                        {
                            "uid": f"INV-CASH-{row['Invoice_ID']}",
                            "movement_id": None,
                            "movement_code": inv_no,
                            "timestamp": ts,
                            "direction": "IN",
                            "operation_type": bst or "SALE_INVOICE",
                            "payment_method": pm_cash,
                            "raw_payment_method": raw_pm or pm_cash,
                            "amount": round(cash_amt, 2),
                            "category": origin_label,
                            "reason": f"Encaissement {ord_no or inv_no}",
                            "reference": ref_display,
                            "counterparty": client_name,
                            "notes": f"Règlement initial ({pm_cash})",
                            "operator": op_name,
                            "is_manual": False,
                            "is_transfer": False,
                            "source_table": "Sales_Invoices",
                            "source_id": int(row["Invoice_ID"]),
                        }
                    )

                if card_amt > 0.009:
                    pm_card = raw_pm if raw_pm in ("BaridiMob", "TPE", "CCP") else "TPE"
                    movements.append(
                        {
                            "uid": f"INV-CARD-{row['Invoice_ID']}",
                            "movement_id": None,
                            "movement_code": inv_no,
                            "timestamp": ts,
                            "direction": "IN",
                            "operation_type": bst or "SALE_INVOICE",
                            "payment_method": pm_card,
                            "raw_payment_method": raw_pm or pm_card,
                            "amount": round(card_amt, 2),
                            "category": origin_label,
                            "reason": f"Encaissement {ord_no or inv_no}",
                            "reference": ref_display,
                            "counterparty": client_name,
                            "notes": f"Règlement électronique ({pm_card})",
                            "operator": op_name,
                            "is_manual": False,
                            "is_transfer": False,
                            "source_table": "Sales_Invoices",
                            "source_id": int(row["Invoice_ID"]),
                        }
                    )

            # 2. Direct POS sales from POS_Sale_Payments where Sales_Invoices has 0 initial cash/card
            pos_rows = self._safe_fetch_all(
                cursor,
                """
                SELECT
                    p.Payment_ID,
                    p.Invoice_ID,
                    p.Payment_Method,
                    p.Amount,
                    p.Reference,
                    p.Created_At,
                    i.Invoice_No,
                    i.Invoice_Date,
                    COALESCE(c.Client_Name, 'Client Comptoir') AS Client_Name,
                    COALESCE(u.Full_Name, u.Username, 'Système') AS Operator_Name
                FROM POS_Sale_Payments p
                JOIN Sales_Invoices i ON i.Invoice_ID = p.Invoice_ID
                LEFT JOIN Clients c ON i.Client_ID = c.Client_ID
                LEFT JOIN Users u ON COALESCE(p.Created_By, i.Created_By) = u.User_ID
                WHERE i.Status != 'Cancelled'
                  AND COALESCE(i.Amount_Paid_Cash, 0.00) = 0
                  AND COALESCE(i.Amount_Paid_Card, 0.00) = 0
                  AND p.Payment_Method NOT IN ('Credit', 'Versement')
                  AND p.Amount > 0
                """,
            )
            for row in pos_rows:
                amt = float(row.get("Amount") or 0.0)
                if amt <= 0.009:
                    continue
                raw_pm = str(row.get("Payment_Method") or "Cash")
                pm = normalize_treasury_method(raw_pm)
                inv_no = str(row.get("Invoice_No") or f"FAC-{row.get('Invoice_ID')}")
                movements.append(
                    {
                        "uid": f"POS-PAY-{row['Payment_ID']}",
                        "movement_id": None,
                        "movement_code": inv_no,
                        "timestamp": _to_iso_datetime(row.get("Created_At") or row.get("Invoice_Date")),
                        "direction": "IN",
                        "operation_type": "POS_PAYMENT",
                        "payment_method": pm,
                        "raw_payment_method": raw_pm,
                        "amount": round(amt, 2),
                        "category": "Vente POS",
                        "reason": f"Paiement facture {inv_no}",
                        "reference": str(row.get("Reference") or inv_no),
                        "counterparty": str(row.get("Client_Name") or "Client Comptoir"),
                        "notes": f"Mode POS : {raw_pm}",
                        "operator": str(row.get("Operator_Name") or "Système"),
                        "is_manual": False,
                        "is_transfer": False,
                        "source_table": "POS_Sale_Payments",
                        "source_id": int(row["Payment_ID"]),
                    }
                )

            # 3. Client_Payments (subsequent Versement / Livraison tranches + standalone Versements)
            cp_rows = self._safe_fetch_all(
                cursor,
                """
                SELECT
                    cp.Payment_ID,
                    cp.Client_ID,
                    cp.Invoice_ID,
                    cp.Payment_Date,
                    cp.Created_At,
                    cp.Amount,
                    cp.Payment_Method,
                    cp.Reference,
                    cp.Notes,
                    i.Invoice_No,
                    i.Bond_Settlement_Type,
                    COALESCE(c.Client_Name, 'Client') AS Client_Name,
                    COALESCE(u.Full_Name, u.Username, 'Système') AS Operator_Name
                FROM Client_Payments cp
                LEFT JOIN Sales_Invoices i ON cp.Invoice_ID = i.Invoice_ID
                LEFT JOIN Clients c ON cp.Client_ID = c.Client_ID
                LEFT JOIN Users u ON cp.Created_By = u.User_ID
                WHERE (cp.Invoice_ID IS NULL OR i.Status != 'Cancelled')
                  AND cp.Amount > 0
                """,
            )
            for row in cp_rows:
                amt = float(row.get("Amount") or 0.0)
                if amt <= 0.009:
                    continue
                raw_pm = str(row.get("Payment_Method") or "Cash")
                pm = normalize_treasury_method(raw_pm)
                bst = str(row.get("Bond_Settlement_Type") or "").upper()
                if raw_pm.lower() == "versement" and not row.get("Invoice_ID"):
                    cat = "Caisse — Dépôt Versement"
                elif bst == "BON_LIVRAISON":
                    cat = "Paiement Livraison (Tranche)"
                elif bst == "BON_VERSEMENT":
                    cat = "Versement (Tranche)"
                else:
                    cat = "Règlement Client"

                ref = str(row.get("Reference") or row.get("Invoice_No") or f"PAY-{row['Payment_ID']}")
                ts = _to_iso_datetime(row.get("Created_At") or row.get("Payment_Date"))
                movements.append(
                    {
                        "uid": f"CP-{row['Payment_ID']}",
                        "movement_id": None,
                        "movement_code": ref,
                        "timestamp": ts,
                        "direction": "IN",
                        "operation_type": "CLIENT_PAYMENT",
                        "payment_method": pm,
                        "raw_payment_method": raw_pm,
                        "amount": round(amt, 2),
                        "category": cat,
                        "reason": str(row.get("Notes") or cat),
                        "reference": ref,
                        "counterparty": str(row.get("Client_Name") or "Client"),
                        "notes": str(row.get("Notes") or ""),
                        "operator": str(row.get("Operator_Name") or "Système"),
                        "is_manual": False,
                        "is_transfer": False,
                        "source_table": "Client_Payments",
                        "source_id": int(row["Payment_ID"]),
                    }
                )

            # 4. POS_Cash_Movements (legacy POS drawer cash in / out / refund)
            pcm_rows = self._safe_fetch_all(
                cursor,
                """
                SELECT
                    m.Movement_ID,
                    m.Movement_Type,
                    m.Amount,
                    m.Reason,
                    m.Reference,
                    m.Created_At,
                    COALESCE(u.Full_Name, u.Username, 'Système') AS Operator_Name
                FROM POS_Cash_Movements m
                LEFT JOIN Users u ON m.Created_By = u.User_ID
                WHERE m.Amount > 0
                """,
            )
            for row in pcm_rows:
                amt = float(row.get("Amount") or 0.0)
                if amt <= 0.009:
                    continue
                mtype = str(row.get("Movement_Type") or "Cash_In")
                direction = "IN" if mtype == "Cash_In" else "OUT"
                cat = "Caisse POS — Entrée" if direction == "IN" else (
                    "Caisse POS — Remboursement" if mtype == "Refund" else "Caisse POS — Sortie"
                )
                ref = str(row.get("Reference") or f"POSM-{row['Movement_ID']}")
                movements.append(
                    {
                        "uid": f"PCM-{row['Movement_ID']}",
                        "movement_id": None,
                        "movement_code": ref,
                        "timestamp": _to_iso_datetime(row.get("Created_At")),
                        "direction": direction,
                        "operation_type": mtype.upper(),
                        "payment_method": "Cash",
                        "raw_payment_method": "Cash",
                        "amount": round(amt, 2),
                        "category": cat,
                        "reason": str(row.get("Reason") or cat),
                        "reference": ref,
                        "counterparty": "Tiroir Caisse POS",
                        "notes": "",
                        "operator": str(row.get("Operator_Name") or "Système"),
                        "is_manual": False,
                        "is_transfer": False,
                        "source_table": "POS_Cash_Movements",
                        "source_id": int(row["Movement_ID"]),
                    }
                )

            # 5. Treasury_Movements (Manual Entrée, Sortie, Transfert Interne)
            tm_rows = self._safe_fetch_all(
                cursor,
                """
                SELECT
                    t.Movement_ID,
                    t.Movement_Code,
                    t.Direction,
                    t.Operation_Type,
                    t.Payment_Method,
                    t.Amount,
                    t.Category,
                    t.Reason,
                    t.Reference,
                    t.Counterparty,
                    t.Transfer_Group_ID,
                    t.Notes,
                    t.Movement_Date,
                    t.Created_At,
                    COALESCE(u.Full_Name, u.Username, 'Système') AS Operator_Name
                FROM Treasury_Movements t
                LEFT JOIN Users u ON t.Created_By = u.User_ID
                WHERE t.Is_Cancelled = 0
                """,
            )
            for row in tm_rows:
                amt = float(row.get("Amount") or 0.0)
                if amt <= 0.009:
                    continue
                direction = str(row.get("Direction") or "IN").upper()
                op_type = str(row.get("Operation_Type") or "MANUAL_IN").upper()
                pm = normalize_treasury_method(row.get("Payment_Method"))
                is_transfer = op_type in ("TRANSFER_IN", "TRANSFER_OUT") or bool(row.get("Transfer_Group_ID"))
                default_cat = "Transfert Interne" if is_transfer else ("Entrée Manuelle" if direction == "IN" else "Sortie Manuelle")
                movements.append(
                    {
                        "uid": f"TM-{row['Movement_ID']}",
                        "movement_id": int(row["Movement_ID"]),
                        "movement_code": str(row.get("Movement_Code") or f"TR-{row['Movement_ID']}"),
                        "timestamp": _to_iso_datetime(row.get("Movement_Date") or row.get("Created_At")),
                        "direction": direction,
                        "operation_type": op_type,
                        "payment_method": pm,
                        "raw_payment_method": str(row.get("Payment_Method") or pm),
                        "amount": round(amt, 2),
                        "category": str(row.get("Category") or default_cat),
                        "reason": str(row.get("Reason") or ""),
                        "reference": str(row.get("Reference") or row.get("Movement_Code") or ""),
                        "counterparty": str(row.get("Counterparty") or "—"),
                        "transfer_group_id": row.get("Transfer_Group_ID"),
                        "notes": str(row.get("Notes") or ""),
                        "operator": str(row.get("Operator_Name") or "Système"),
                        "is_manual": True,
                        "is_transfer": is_transfer,
                        "source_table": "Treasury_Movements",
                        "source_id": int(row["Movement_ID"]),
                    }
                )
        finally:
            cursor.close()
            self._close_conn(conn)

        return movements

    def get_treasury_snapshot(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        payment_method: str = "ALL",
        direction: str = "ALL",
        search: str = "",
    ) -> Dict[str, Any]:
        """
        Computes:
        - Live balances by payment method & global total (all-time)
        - Running balance per movement (chronological ASC, returned newest-first DESC)
        - Filtered movements list & period summary totals
        - Per-method summary metrics (Today / This Month / Count / Last Movement)
        """
        all_movs = self._collect_all_raw_movements()

        # Sort chronologically ascending to compute exact running balances
        all_movs.sort(key=lambda m: (m.get("timestamp") or "", str(m.get("uid") or "")))

        balances_by_method: Dict[str, float] = {m: 0.0 for m in CANONICAL_PAYMENT_METHODS}
        global_running = 0.0

        today_str = date.today().strftime("%Y-%m-%d")
        month_prefix = date.today().strftime("%Y-%m")

        method_stats: Dict[str, Dict[str, Any]] = {
            m: {
                "payment_method": m,
                "balance": 0.0,
                "today_in": 0.0,
                "today_out": 0.0,
                "month_in": 0.0,
                "month_out": 0.0,
                "total_in": 0.0,
                "total_out": 0.0,
                "count": 0,
                "last_timestamp": "",
            }
            for m in CANONICAL_PAYMENT_METHODS
        }

        for mov in all_movs:
            pm = mov["payment_method"]
            if pm not in balances_by_method:
                pm = "Cash"
                mov["payment_method"] = pm
            amt = float(mov["amount"] or 0.0)
            signed = amt if mov["direction"] == "IN" else -amt

            global_running = round(global_running + signed, 2)
            balances_by_method[pm] = round(balances_by_method[pm] + signed, 2)

            mov["running_balance_global"] = global_running
            mov["running_balance_method"] = balances_by_method[pm]

            ms = method_stats[pm]
            ms["balance"] = balances_by_method[pm]
            ms["count"] += 1
            ts = str(mov.get("timestamp") or "")
            ms["last_timestamp"] = ts
            day_part = ts[:10]
            month_part = ts[:7]
            if mov["direction"] == "IN":
                ms["total_in"] = round(ms["total_in"] + amt, 2)
                if day_part == today_str:
                    ms["today_in"] = round(ms["today_in"] + amt, 2)
                if month_part == month_prefix:
                    ms["month_in"] = round(ms["month_in"] + amt, 2)
            else:
                ms["total_out"] = round(ms["total_out"] + amt, 2)
                if day_part == today_str:
                    ms["today_out"] = round(ms["today_out"] + amt, 2)
                if month_part == month_prefix:
                    ms["month_out"] = round(ms["month_out"] + amt, 2)

        total_balance = round(sum(balances_by_method.values()), 2)

        # Apply UI filters
        pm_filter = str(payment_method or "ALL").strip()
        dir_filter = str(direction or "ALL").strip().upper()
        q = str(search or "").strip().lower()
        sd = str(start_date or "").strip()[:10]
        ed = str(end_date or "").strip()[:10]

        filtered: List[Dict[str, Any]] = []
        period_in = 0.0
        period_out = 0.0

        for mov in reversed(all_movs):  # newest first
            day_part = str(mov.get("timestamp") or "")[:10]
            if sd and day_part and day_part < sd:
                continue
            if ed and day_part and day_part > ed:
                continue
            if pm_filter != "ALL" and mov["payment_method"] != pm_filter:
                continue
            if dir_filter == "IN" and (mov["direction"] != "IN" or mov.get("is_transfer")):
                continue
            if dir_filter == "OUT" and (mov["direction"] != "OUT" or mov.get("is_transfer")):
                continue
            if dir_filter == "TRANSFER" and not mov.get("is_transfer"):
                continue

            if q:
                haystack = " ".join(
                    str(mov.get(k) or "")
                    for k in (
                        "movement_code",
                        "reference",
                        "category",
                        "reason",
                        "counterparty",
                        "operator",
                        "payment_method",
                        "notes",
                    )
                ).lower()
                if q not in haystack:
                    continue

            # Show method running balance when filtered to one payment method,
            # otherwise global treasury running balance.
            mov["display_balance_after"] = (
                mov["running_balance_method"]
                if pm_filter != "ALL"
                else mov["running_balance_global"]
            )
            filtered.append(mov)

            if not mov.get("is_transfer") or pm_filter != "ALL":
                if mov["direction"] == "IN":
                    period_in = round(period_in + float(mov["amount"] or 0.0), 2)
                else:
                    period_out = round(period_out + float(mov["amount"] or 0.0), 2)

        return {
            "total_balance": total_balance,
            "balances_by_method": balances_by_method,
            "method_summaries": [method_stats[m] for m in CANONICAL_PAYMENT_METHODS],
            "movements": filtered,
            "total_count": len(all_movs),
            "filtered_count": len(filtered),
            "period_in": period_in,
            "period_out": period_out,
            "period_net": round(period_in - period_out, 2),
        }
