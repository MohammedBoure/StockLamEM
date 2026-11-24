# -*- coding: utf-8 -*-
"""
database/decharge_manager.py
============================
Manages Décharge Types (Données de Base -> Types de Décharges) and Décharge
financial outflow operations linked directly to Treasury_Movements (حركة المال).
"""

import logging
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from database.treasury_manager import TreasuryManager, normalize_treasury_method

logger = logging.getLogger("StockLam.Database.DechargeManager")

DEFAULT_DECHARGE_TYPES = [
    ("Loyer", "Loyer du local commercial ou dépôt"),
    ("Électricité & Eau", "Factures Sonelgaz / SEAAL / Eau"),
    ("Salaires & Avances", "Rémunérations et avances du personnel"),
    ("Transport & Livraison", "Frais de transport, carburant et livraisons"),
    ("Fournitures & Bureau", "Consommables de bureau et emballage"),
    ("Maintenance & Réparation", "Entretien du local et équipements"),
    ("Divers", "Autres dépenses et sorties de caisse"),
]


class DechargeManager:
    """Handles CRUD for Decharge_Types and Decharges with automatic Treasury sync."""

    def __init__(self, db_instance):
        self.db = db_instance
        self._schema_ready = False
        self._ensure_schema()

    def _get_connection(self):
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
        if conn is not None and hasattr(self.db, "get_raw_connection"):
            try:
                conn.close()
            except Exception:
                pass

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        conn = self._get_connection()
        if conn is None:
            return
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS Decharge_Types (
                    Type_ID INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    Type_Name VARCHAR(120) NOT NULL UNIQUE,
                    Description VARCHAR(255) NULL,
                    Is_Active TINYINT(1) NOT NULL DEFAULT 1,
                    Created_At DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS Decharges (
                    Decharge_ID BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    Decharge_Code VARCHAR(64) NOT NULL UNIQUE,
                    Type_ID INT UNSIGNED NOT NULL,
                    Payment_Method VARCHAR(32) NOT NULL DEFAULT 'Cash',
                    Amount DECIMAL(15, 2) NOT NULL,
                    Beneficiary VARCHAR(150) NULL,
                    Reason VARCHAR(255) NOT NULL,
                    Reference VARCHAR(120) NULL,
                    Notes TEXT NULL,
                    Decharge_Date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    Treasury_Movement_ID BIGINT UNSIGNED NULL,
                    Status ENUM('ACTIVE', 'CANCELLED') NOT NULL DEFAULT 'ACTIVE',
                    Created_By INT UNSIGNED NULL,
                    Created_At DATETIME DEFAULT CURRENT_TIMESTAMP,
                    KEY idx_decharge_date (Decharge_Date),
                    KEY idx_decharge_type (Type_ID),
                    KEY idx_decharge_method (Payment_Method),
                    CONSTRAINT fk_decharge_type FOREIGN KEY (Type_ID) REFERENCES Decharge_Types(Type_ID) ON UPDATE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute("SELECT COUNT(*) AS cnt FROM Decharge_Types")
            row = cursor.fetchone() or {}
            if int(row.get("cnt") or 0) == 0:
                for t_name, t_desc in DEFAULT_DECHARGE_TYPES:
                    cursor.execute(
                        "INSERT IGNORE INTO Decharge_Types (Type_Name, Description, Is_Active) VALUES (%s, %s, 1)",
                        (t_name, t_desc),
                    )
            if hasattr(conn, "commit"):
                conn.commit()
            self._schema_ready = True
        except Exception as err:
            logger.error(f"Error ensuring Decharges schema: {err}")
            try:
                if hasattr(conn, "rollback"):
                    conn.rollback()
            except Exception:
                pass
        finally:
            cursor.close()
            self._close_conn(conn)

    # =========================================================================
    # 1. DECHARGE TYPES (Données de Base)
    # =========================================================================

    def get_all_types(self, only_active: bool = False) -> List[Dict[str, Any]]:
        self._ensure_schema()
        conn = self._get_connection()
        if conn is None:
            return []
        cursor = conn.cursor(dictionary=True)
        try:
            sql = "SELECT Type_ID, Type_Name, COALESCE(Description, '') AS Description, Is_Active, Created_At FROM Decharge_Types"
            if only_active:
                sql += " WHERE Is_Active = 1"
            sql += " ORDER BY Type_Name ASC"
            cursor.execute(sql)
            return cursor.fetchall() or []
        except Exception as err:
            logger.error(f"Error fetching decharge types: {err}")
            return []
        finally:
            cursor.close()
            self._close_conn(conn)

    def add_type(self, name: str, description: str = "") -> Dict[str, Any]:
        self._ensure_schema()
        clean_name = str(name or "").strip()
        if not clean_name:
            raise ValueError("Le nom du type de décharge est obligatoire.")
        conn = self._get_connection()
        if conn is None:
            raise RuntimeError("Connexion base de données indisponible.")
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "INSERT INTO Decharge_Types (Type_Name, Description, Is_Active) VALUES (%s, %s, 1)",
                (clean_name[:120], str(description or "").strip()[:255] or None),
            )
            tid = cursor.lastrowid
            if hasattr(conn, "commit"):
                conn.commit()
            return {"success": True, "Type_ID": tid, "Type_Name": clean_name}
        except Exception as err:
            if hasattr(conn, "rollback"):
                conn.rollback()
            raise err
        finally:
            cursor.close()
            self._close_conn(conn)

    def update_type(self, type_id: int, name: str, description: str = "", is_active: bool = True) -> bool:
        self._ensure_schema()
        clean_name = str(name or "").strip()
        if not clean_name:
            raise ValueError("Le nom du type de décharge est obligatoire.")
        conn = self._get_connection()
        if conn is None:
            return False
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE Decharge_Types
                SET Type_Name = %s, Description = %s, Is_Active = %s
                WHERE Type_ID = %s
                """,
                (clean_name[:120], str(description or "").strip()[:255] or None, 1 if is_active else 0, int(type_id)),
            )
            if hasattr(conn, "commit"):
                conn.commit()
            return True
        except Exception as err:
            if hasattr(conn, "rollback"):
                conn.rollback()
            raise err
        finally:
            cursor.close()
            self._close_conn(conn)

    def delete_type(self, type_id: int) -> bool:
        self._ensure_schema()
        conn = self._get_connection()
        if conn is None:
            return False
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT COUNT(*) AS cnt FROM Decharges WHERE Type_ID = %s", (int(type_id),))
            row = cursor.fetchone() or {}
            if int(row.get("cnt") or 0) > 0:
                cursor.execute("UPDATE Decharge_Types SET Is_Active = 0 WHERE Type_ID = %s", (int(type_id),))
            else:
                cursor.execute("DELETE FROM Decharge_Types WHERE Type_ID = %s", (int(type_id),))
            if hasattr(conn, "commit"):
                conn.commit()
            return True
        except Exception as err:
            if hasattr(conn, "rollback"):
                conn.rollback()
            raise err
        finally:
            cursor.close()
            self._close_conn(conn)

    # =========================================================================
    # 2. DECHARGE OPERATIONS (Synced to Treasury_Movements)
    # =========================================================================

    def create_decharge(
        self,
        type_id: int,
        payment_method: str,
        amount: Any,
        reason: str = "",
        beneficiary: str = "",
        reference: str = "",
        notes: str = "",
        decharge_date: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        self._ensure_schema()
        try:
            amt = Decimal(str(amount)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError("Montant invalide.")
        if amt <= Decimal("0.00"):
            raise ValueError("Le montant de la décharge doit être strictement supérieur à 0,00 DA.")

        method_norm = normalize_treasury_method(payment_method)
        dt_str = decharge_date or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if len(dt_str) == 10:
            dt_str = f"{dt_str} {datetime.now().strftime('%H:%M:%S')}"

        # Resolve type name
        type_name = "Décharge"
        conn_lookup = self._get_connection()
        if conn_lookup is not None:
            cur_l = conn_lookup.cursor(dictionary=True)
            try:
                cur_l.execute("SELECT Type_Name FROM Decharge_Types WHERE Type_ID = %s", (int(type_id),))
                tr = cur_l.fetchone()
                if not tr:
                    raise ValueError("Type de décharge introuvable.")
                type_name = str(tr["Type_Name"])
            finally:
                cur_l.close()
                self._close_conn(conn_lookup)

        reason_clean = str(reason or "").strip() or f"Décharge — {type_name}"
        code = f"DCH-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        # 1. Record outflow in Treasury_Movements (حركة المال)
        treasury_mgr = TreasuryManager(self.db)
        tr_res = treasury_mgr.record_movement(
            direction="OUT",
            payment_method=method_norm,
            amount=float(amt),
            reason=reason_clean,
            category=f"Décharge: {type_name}",
            reference=str(reference or "").strip() or code,
            counterparty=str(beneficiary or "").strip(),
            notes=str(notes or "").strip(),
            operation_type="DECHARGE",
            movement_date=dt_str,
            user_id=user_id,
        )
        tr_mov_id = tr_res.get("movement_id")

        # 2. Insert Decharge record linked to Treasury_Movement_ID
        conn = self._get_connection()
        if conn is None:
            raise RuntimeError("Connexion base de données indisponible.")
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                INSERT INTO Decharges (
                    Decharge_Code, Type_ID, Payment_Method, Amount,
                    Beneficiary, Reason, Reference, Notes,
                    Decharge_Date, Treasury_Movement_ID, Status, Created_By
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVE', %s)
                """,
                (
                    code,
                    int(type_id),
                    method_norm,
                    amt,
                    str(beneficiary or "").strip()[:150] or None,
                    reason_clean[:255],
                    str(reference or "").strip()[:120] or None,
                    str(notes or "").strip() or None,
                    dt_str,
                    tr_mov_id,
                    int(user_id) if user_id else None,
                ),
            )
            dch_id = cursor.lastrowid
            if hasattr(conn, "commit"):
                conn.commit()
            return {
                "success": True,
                "decharge_id": dch_id,
                "decharge_code": code,
                "treasury_movement_id": tr_mov_id,
                "amount": float(amt),
                "payment_method": method_norm,
                "type_name": type_name,
            }
        except Exception as err:
            if hasattr(conn, "rollback"):
                conn.rollback()
            raise err
        finally:
            cursor.close()
            self._close_conn(conn)

    def get_decharges(
        self,
        type_id: Optional[int] = None,
        payment_method: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search: Optional[str] = None,
        include_cancelled: bool = False,
    ) -> List[Dict[str, Any]]:
        self._ensure_schema()
        conn = self._get_connection()
        if conn is None:
            return []
        cursor = conn.cursor(dictionary=True)
        try:
            sql = """
                SELECT
                    d.Decharge_ID, d.Decharge_Code, d.Type_ID,
                    COALESCE(t.Type_Name, 'Décharge') AS Type_Name,
                    d.Payment_Method, d.Amount,
                    COALESCE(d.Beneficiary, '') AS Beneficiary,
                    d.Reason,
                    COALESCE(d.Reference, '') AS Reference,
                    COALESCE(d.Notes, '') AS Notes,
                    d.Decharge_Date, d.Treasury_Movement_ID, d.Status,
                    COALESCE(NULLIF(u.Full_Name, ''), u.Username, 'Système') AS Operator_Name
                FROM Decharges d
                LEFT JOIN Decharge_Types t ON d.Type_ID = t.Type_ID
                LEFT JOIN Users u ON d.Created_By = u.User_ID
                WHERE 1=1
            """
            params: List[Any] = []
            if not include_cancelled:
                sql += " AND d.Status = 'ACTIVE'"
            if type_id:
                sql += " AND d.Type_ID = %s"
                params.append(int(type_id))
            if payment_method and payment_method != "ALL":
                sql += " AND d.Payment_Method = %s"
                params.append(payment_method)
            if start_date:
                sql += " AND DATE(d.Decharge_Date) >= %s"
                params.append(start_date)
            if end_date:
                sql += " AND DATE(d.Decharge_Date) <= %s"
                params.append(end_date)
            if search:
                term = f"%{search.strip().lower()}%"
                sql += """ AND (
                    LOWER(d.Decharge_Code) LIKE %s OR
                    LOWER(COALESCE(t.Type_Name, '')) LIKE %s OR
                    LOWER(COALESCE(d.Beneficiary, '')) LIKE %s OR
                    LOWER(COALESCE(d.Reason, '')) LIKE %s OR
                    LOWER(COALESCE(d.Reference, '')) LIKE %s
                )"""
                params.extend([term, term, term, term, term])
            sql += " ORDER BY d.Decharge_Date DESC, d.Decharge_ID DESC LIMIT 500"
            cursor.execute(sql, tuple(params))
            return cursor.fetchall() or []
        except Exception as err:
            logger.error(f"Error fetching decharges: {err}")
            return []
        finally:
            cursor.close()
            self._close_conn(conn)

    def cancel_decharge(self, decharge_id: int, user_id: Optional[int] = None) -> bool:
        self._ensure_schema()
        conn = self._get_connection()
        if conn is None:
            return False
        cursor = conn.cursor(dictionary=True)
        tr_mov_id = None
        try:
            cursor.execute(
                "SELECT Decharge_ID, Treasury_Movement_ID, Status FROM Decharges WHERE Decharge_ID = %s",
                (int(decharge_id),),
            )
            row = cursor.fetchone()
            if not row or row.get("Status") == "CANCELLED":
                return False
            tr_mov_id = row.get("Treasury_Movement_ID")
            cursor.execute("UPDATE Decharges SET Status = 'CANCELLED' WHERE Decharge_ID = %s", (int(decharge_id),))
            if hasattr(conn, "commit"):
                conn.commit()
        except Exception as err:
            if hasattr(conn, "rollback"):
                conn.rollback()
            logger.error(f"Error cancelling decharge #{decharge_id}: {err}")
            return False
        finally:
            cursor.close()
            self._close_conn(conn)

        if tr_mov_id:
            try:
                TreasuryManager(self.db).cancel_manual_movement(int(tr_mov_id), user_id=user_id)
            except Exception as err:
                logger.warning(f"Could not cancel linked treasury movement #{tr_mov_id}: {err}")
        return True
