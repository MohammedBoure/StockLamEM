# database/serial_tracking_manager.py
"""
Serial Tracking & Appliance Batch Ingestion Manager.
Handles:
- Product attributes (Mark, Name, Categorie, Coloure, N° de Série, Extensible Attributes)
- Batch arrivals with distinct reception dates and landed costs
- Global serial number sanitization and composite uniqueness (<Product_ID>::<UPPER_SERIAL>)
- Theoretical stock calculation (Available = Physical - Theoretical_Reserved_Qty)
"""

import json
import logging
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

import mysql.connector

logger = logging.getLogger("StockLam.Backend.SerialService")


class SerialTrackingManager:
    """Manages appliance batches, unique serial numbers (N° de Série), and theoretical stock availability."""

    def __init__(self, db_instance):
        self.db = db_instance

    def _get_connection(self):
        """Obtains a raw transactional connection supporting both Database and mock objects."""
        if hasattr(self.db, "get_raw_connection"):
            conn = self.db.get_raw_connection()
            if conn is not None:
                return conn
        if hasattr(self.db, "get_connection"):
            return self.db.get_connection()
        if hasattr(self.db, "cursor"):
            return self.db
        raise RuntimeError("No valid database connection provider found.")

    @staticmethod
    def sanitize_serial_number(raw_serial: str) -> str:
        """
        Strips leading/trailing whitespace and control characters, converts to uppercase,
        and validates non-empty serial format.
        """
        if raw_serial is None:
            raise ValueError("Serial number cannot be None.")
        cleaned = re.sub(r"[\r\n\t\x00-\x1f\x7f]+", "", str(raw_serial)).strip().upper()
        if not cleaned:
            raise ValueError("Serial number cannot be empty after sanitization.")
        return cleaned

    @classmethod
    def build_composite_barcode(cls, product_id: int, raw_serial: str) -> str:
        """Builds the globally unique composite barcode key '<Product_ID>::<CLEAN_UPPER_SERIAL>'."""
        clean_sn = cls.sanitize_serial_number(raw_serial)
        return f"{int(product_id)}::{clean_sn}"

    def register_product_with_attributes(
        self,
        name: str,
        mark: str,
        categorie: str,
        coloure: str,
        barcode: Optional[str] = None,
        selling_price_ht: Decimal = Decimal("0.00"),
        tva_percent: Decimal = Decimal("19.00"),
        warranty_months: int = 24,
        requires_serial: bool = True,
        family_id: int = 1,
        manuf_id: int = 1,
        extra_attributes: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Registers a product with full electrical appliance attributes:
        Mark (العلامة التجارية), Name (الاسم), Categorie (الفئة), Coloure (اللون),
        and extensible JSON attributes.
        """
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if hasattr(conn, "start_transaction"):
                conn.start_transaction()

            ext_json = json.dumps(extra_attributes or {}, ensure_ascii=False)
            cursor.execute(
                """
                INSERT INTO Products_Master (
                    Product_Name, Family_ID, Manuf_ID, Barcode,
                    Brand_Mark, Category_Name, Color_Finish,
                    Requires_Serial_Tracking, Warranty_Months,
                    Default_Selling_Price_HT, Selling_TVA_Percent,
                    Extensible_Attributes, Is_Billable
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                """,
                (
                    name.strip(),
                    int(family_id),
                    int(manuf_id),
                    barcode.strip() if barcode else None,
                    mark.strip(),
                    categorie.strip(),
                    coloure.strip(),
                    bool(requires_serial),
                    int(warranty_months),
                    Decimal(str(selling_price_ht)),
                    Decimal(str(tva_percent)),
                    ext_json,
                ),
            )
            product_id = cursor.lastrowid
            conn.commit()
            return {
                "success": True,
                "product_id": product_id,
                "name": name.strip(),
                "mark": mark.strip(),
                "categorie": categorie.strip(),
                "coloure": coloure.strip(),
            }
        except Exception as err:
            conn.rollback()
            logger.error(f"Error registering appliance product: {err}")
            raise
        finally:
            cursor.close()
            if hasattr(self.db, "get_raw_connection"):
                conn.close()

    def register_batch_arrival(
        self,
        product_id: int,
        supplier_id: int,
        po_id: Optional[int],
        reception_date: str,
        unit_cost_ht: Decimal,
        freight_customs: Decimal,
        serial_numbers: List[str],
        user_id: int,
        location_id: int = 1,
        selling_price_ht: Optional[Decimal] = None,
        tax_rate: Decimal = Decimal("19.00"),
        batch_number: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Atomically records an arrival batch (with its specific date and cost)
        and provisions individual serialized units in Product_Serials.
        Enforces strict uniqueness on (Product_ID, Serial_Number) and Barcode_Serial_Composite.
        """
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if hasattr(conn, "start_transaction"):
                conn.start_transaction()

            qty_initial = len(serial_numbers)
            if qty_initial == 0:
                raise ValueError("Batch arrival requires at least one serial number.")

            # Sanitize and check for duplicates within the input list itself before DB insert
            sanitized_serials: List[str] = []
            seen_in_payload = set()
            for raw_sn in serial_numbers:
                sn_clean = self.sanitize_serial_number(raw_sn)
                if sn_clean in seen_in_payload:
                    raise mysql.connector.IntegrityError(
                        msg=f"Duplicate entry '{sn_clean}' in batch serial payload",
                        errno=1062,
                    )
                seen_in_payload.add(sn_clean)
                sanitized_serials.append(sn_clean)

            lot_num = batch_number or f"LOT-{datetime.now().strftime('%Y%m%d')}-P{product_id}-{int(datetime.now().timestamp())}"
            unit_cost_dec = Decimal(str(unit_cost_ht))
            freight_dec = Decimal(str(freight_customs or "0.00"))
            landed_ht = unit_cost_dec + freight_dec
            sell_ht = Decimal(str(selling_price_ht)) if selling_price_ht is not None else (landed_ht * Decimal("1.25"))

            cursor.execute(
                """
                INSERT INTO Inventory_Batches (
                    Internal_Barcode, Product_ID, Location_ID, Supplier_ID, PO_ID,
                    Lot_Number, Quantity_Initial, Quantity_Current, Theoretical_Reserved_Qty,
                    Unit_Price_Received, Freight_Customs_Allocation, Tax_Rate_Percent,
                    Selling_Price_HT, Selling_TVA_Percent, Status, Created_At
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, %s, %s, %s, %s, %s, 'Available', %s)
                """,
                (
                    lot_num,
                    int(product_id),
                    int(location_id),
                    int(supplier_id) if supplier_id else None,
                    int(po_id) if po_id else None,
                    lot_num,
                    qty_initial,
                    qty_initial,
                    unit_cost_dec,
                    freight_dec,
                    Decimal(str(tax_rate)),
                    sell_ht,
                    Decimal(str(tax_rate)),
                    reception_date or date.today().isoformat(),
                ),
            )
            batch_id = cursor.lastrowid

            insert_serial_sql = """
                INSERT INTO Product_Serials (
                    Product_ID, Batch_ID, Serial_Number, Barcode_Serial_Composite,
                    Status, Current_Location_ID
                ) VALUES (%s, %s, %s, %s, 'IN_STOCK', %s)
            """
            insert_hist_sql = """
                INSERT INTO Product_Serial_History (
                    Serial_ID, Previous_Status, New_Status, Voucher_Type,
                    Voucher_ID, To_Location_ID, Changed_By_User_ID, Action_Notes
                ) VALUES (%s, NULL, 'IN_STOCK', 'RECEPTION', %s, %s, %s, 'Batch arrival physical check-in')
            """

            created_serial_ids = []
            for sn_clean in sanitized_serials:
                composite_barcode = f"{int(product_id)}::{sn_clean}"
                cursor.execute(
                    insert_serial_sql,
                    (int(product_id), batch_id, sn_clean, composite_barcode, int(location_id)),
                )
                serial_id = cursor.lastrowid
                created_serial_ids.append(serial_id)

                cursor.execute(
                    insert_hist_sql,
                    (serial_id, batch_id, int(location_id), int(user_id)),
                )

            # Record Batch Receipt in Stock_Movement_Log (Traçabilité)
            try:
                cursor.execute(
                    "SELECT SUM(Quantity_Current) AS Total_Stock FROM Inventory_Batches WHERE Product_ID = %s",
                    (int(product_id),),
                )
                stk_row = cursor.fetchone()
                stk_after = (stk_row.get("Total_Stock") if isinstance(stk_row, dict) else stk_row[0]) if stk_row else qty_initial
                cursor.execute(
                    """
                    INSERT INTO Stock_Movement_Log (
                        Product_ID, Batch_ID, Movement_Type, Qty_Change, Unit_Used,
                        Notes, User_ID, Transaction_Date, Stock_After
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s)
                    """,
                    (
                        int(product_id),
                        batch_id,
                        'Purchase_Receive',
                        qty_initial,
                        'Pièce',
                        f"Réception Lot {lot_num} ({qty_initial} pièces avec N° de Série)",
                        int(user_id),
                        stk_after,
                    ),
                )
            except Exception as log_err:
                logger.warning(f"Could not record Stock_Movement_Log for batch {batch_id}: {log_err}")

            conn.commit()
            return {
                "success": True,
                "batch_id": batch_id,
                "batch_number": lot_num,
                "serials_count": qty_initial,
                "serial_ids": created_serial_ids,
                "landed_cost_ht": float(landed_ht),
            }
        except mysql.connector.Error as err:
            conn.rollback()
            logger.error(f"Database error registering batch arrival: {err}")
            raise
        except Exception as err:
            conn.rollback()
            logger.error(f"Error registering batch arrival: {err}")
            raise
        finally:
            cursor.close()
            if hasattr(self.db, "get_raw_connection"):
                conn.close()

    def get_catalog_with_theoretical_stock(
        self,
        search: str = "",
        brand_mark: str = "",
        category_name: str = "",
        color_finish: str = "",
        product_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Returns catalog items with theoretical stock metrics for the Order Desk:
        - Physical Stock (Quantity_Current)
        - Theoretical Reserved (Theoretical_Reserved_Qty)
        - Available Theoretical Stock (Quantity_Current - Theoretical_Reserved_Qty)
        No physical serial numbers are locked at the Order Desk.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                where_clauses = ["p.Deleted_At IS NULL"]
                params = []
                if product_id is not None:
                    where_clauses.append("p.Product_ID = %s")
                    params.append(int(product_id))

                query = f"""
                    SELECT
                        p.Product_ID,
                        p.Product_Name,
                        COALESCE(p.Brand_Mark, m.Manuf_Name, 'Générique') AS Brand_Mark,
                        COALESCE(p.Category_Name, pf.Family_Name, 'Électroménager') AS Category_Name,
                        COALESCE(p.Color_Finish, 'Standard') AS Color_Finish,
                        p.Barcode,
                        p.Warranty_Months,
                        p.Requires_Serial_Tracking,
                        COALESCE(p.Default_Selling_Price_HT, 0.00) AS Default_Selling_Price_HT,
                        COALESCE(p.Selling_TVA_Percent, 19.00) AS Selling_TVA_Percent,
                        COALESCE(SUM(CASE WHEN b.Status IN ('Available', 'ACTIVE') THEN b.Quantity_Current ELSE 0 END), 0) AS Physical_Qty,
                        COALESCE(SUM(CASE WHEN b.Status IN ('Available', 'ACTIVE') THEN COALESCE(b.Theoretical_Reserved_Qty, 0) ELSE 0 END), 0) AS Reserved_Qty,
                        COALESCE(MAX(b.Selling_Price_HT), p.Default_Selling_Price_HT, 0.00) AS Batch_Selling_Price_HT
                    FROM Products_Master p
                    LEFT JOIN Manufacturers m ON p.Manuf_ID = m.Manuf_ID
                    LEFT JOIN Product_Families pf ON p.Family_ID = pf.Family_ID
                    LEFT JOIN Inventory_Batches b ON p.Product_ID = b.Product_ID
                    WHERE {' AND '.join(where_clauses)}
                    GROUP BY p.Product_ID
                    ORDER BY p.Product_Name ASC
                """
                cursor.execute(query, tuple(params) if params else ())
                rows = cursor.fetchall() or []

                results = []
                s_term = (search or "").strip().lower()
                b_term = (brand_mark or "").strip().lower()
                c_term = (category_name or "").strip().lower()
                col_term = (color_finish or "").strip().lower()

                for r in rows:
                    mark_val = str(r.get("Brand_Mark") or "")
                    cat_val = str(r.get("Category_Name") or "")
                    col_val = str(r.get("Color_Finish") or "")
                    name_val = str(r.get("Product_Name") or "")
                    bc_val = str(r.get("Barcode") or "")

                    if s_term and not any(
                        s_term in field.lower()
                        for field in (name_val, mark_val, cat_val, col_val, bc_val)
                    ):
                        continue
                    if b_term and b_term != "tous" and b_term not in mark_val.lower():
                        continue
                    if c_term and c_term != "tous" and c_term not in cat_val.lower():
                        continue
                    if col_term and col_term != "tous" and col_term not in col_val.lower():
                        continue

                    phys = int(r.get("Physical_Qty") or 0)
                    res = int(r.get("Reserved_Qty") or 0)
                    avail = max(0, phys - res)
                    price_ht = Decimal(str(r.get("Batch_Selling_Price_HT") or r.get("Default_Selling_Price_HT") or "0.00"))
                    tva = Decimal(str(r.get("Selling_TVA_Percent") or "19.00"))
                    price_ttc = (price_ht * (Decimal("1.00") + (tva / Decimal("100.00")))).quantize(Decimal("0.01"))

                    r["Physical_Qty"] = phys
                    r["Reserved_Qty"] = res
                    r["Available_Theoretical_Qty"] = avail
                    r["Unit_Price_HT"] = float(price_ht)
                    r["Unit_Price_TTC"] = float(price_ttc)
                    results.append(r)

                return results
        except Exception as err:
            logger.error(f"Error fetching catalog with theoretical stock: {err}")
            return []

    def find_product_by_any_barcode(self, barcode: str) -> Optional[Dict[str, Any]]:
        """
        Universal barcode resolver for Order Desk theoretical lookups:
        Resolves an input barcode string against:
        1. Composite serial barcode (<Product_ID>::<SERIAL>)
        2. Products_Master Barcode field (exact match or comma-delimited element)
        3. Products_Master Product_ID
        4. Inventory_Batches Internal_Barcode or External_Barcode / Lot_Number
        5. Product_Serials Barcode_Serial_Composite or Serial_Number
        Returns full theoretical catalog details if found, or None.
        """
        if not barcode:
            return None
        clean_bc = str(barcode).strip()
        if not clean_bc:
            return None

        # 1. Composite barcode fast resolution: e.g. "101::SN9928"
        if "::" in clean_bc:
            parts = clean_bc.split("::", 1)
            if parts[0].isdigit():
                found = self.get_catalog_with_theoretical_stock(product_id=int(parts[0]))
                if found:
                    return found[0]

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)

                # 2. Check Products_Master directly
                cursor.execute(
                    """
                    SELECT Product_ID FROM Products_Master
                    WHERE Deleted_At IS NULL
                      AND (
                          Barcode = %s
                          OR FIND_IN_SET(%s, REPLACE(Barcode, ' ', '')) > 0
                          OR (Product_ID = %s AND %s REGEXP '^[0-9]+$')
                      )
                    LIMIT 1
                    """,
                    (clean_bc, clean_bc, clean_bc if clean_bc.isdigit() else 0, clean_bc),
                )
                row = cursor.fetchone()
                if row:
                    found = self.get_catalog_with_theoretical_stock(product_id=int(row["Product_ID"]))
                    if found:
                        return found[0]

                # 3. Check Inventory_Batches (Internal_Barcode, External_Barcode, Lot_Number)
                cursor.execute(
                    """
                    SELECT Product_ID FROM Inventory_Batches
                    WHERE Internal_Barcode = %s
                       OR External_Barcode = %s
                       OR Lot_Number = %s
                    ORDER BY Batch_ID DESC
                    LIMIT 1
                    """,
                    (clean_bc, clean_bc, clean_bc),
                )
                row = cursor.fetchone()
                if row:
                    found = self.get_catalog_with_theoretical_stock(product_id=int(row["Product_ID"]))
                    if found:
                        return found[0]

                # 4. Check Product_Serials (Serial_Number, Barcode_Serial_Composite)
                cursor.execute(
                    """
                    SELECT Product_ID FROM Product_Serials
                    WHERE Serial_Number = %s
                       OR Barcode_Serial_Composite = %s
                    ORDER BY Serial_ID DESC
                    LIMIT 1
                    """,
                    (clean_bc.upper(), clean_bc),
                )
                row = cursor.fetchone()
                if row:
                    found = self.get_catalog_with_theoretical_stock(product_id=int(row["Product_ID"]))
                    if found:
                        return found[0]

        except Exception as err:
            logger.error(f"Error finding product by barcode '{clean_bc}': {err}")

        return None

    def get_serial_details(self, serial_number: str) -> Optional[Dict[str, Any]]:
        """Looks up a specific physical serial number along with its product and batch metadata."""
        try:
            sn_clean = self.sanitize_serial_number(serial_number)
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT
                        ps.*,
                        p.Product_Name,
                        COALESCE(p.Brand_Mark, m.Manuf_Name, '') AS Brand_Mark,
                        COALESCE(p.Category_Name, pf.Family_Name, '') AS Category_Name,
                        COALESCE(p.Color_Finish, '') AS Color_Finish,
                        p.Barcode AS Product_Barcode,
                        b.Lot_Number,
                        b.Unit_Price_Received
                    FROM Product_Serials ps
                    JOIN Products_Master p ON ps.Product_ID = p.Product_ID
                    LEFT JOIN Manufacturers m ON p.Manuf_ID = m.Manuf_ID
                    LEFT JOIN Product_Families pf ON p.Family_ID = pf.Family_ID
                    LEFT JOIN Inventory_Batches b ON ps.Batch_ID = b.Batch_ID
                    WHERE ps.Serial_Number = %s
                    """,
                    (sn_clean,),
                )
                return cursor.fetchone()
        except Exception as err:
            logger.error(f"Error looking up serial '{serial_number}': {err}")
            return None

    def get_all_serials(self, product_id: Optional[int] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists registered serial numbers with optional product and status filters."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                clauses = ["1=1"]
                params: List[Any] = []
                if product_id:
                    clauses.append("ps.Product_ID = %s")
                    params.append(int(product_id))
                if status and status != "ALL":
                    clauses.append("ps.Status = %s")
                    params.append(status)

                query = f"""
                    SELECT
                        ps.*,
                        p.Product_Name,
                        COALESCE(p.Brand_Mark, m.Manuf_Name, '') AS Brand_Mark,
                        COALESCE(p.Category_Name, pf.Family_Name, '') AS Category_Name,
                        COALESCE(p.Color_Finish, '') AS Color_Finish,
                        b.Lot_Number
                    FROM Product_Serials ps
                    JOIN Products_Master p ON ps.Product_ID = p.Product_ID
                    LEFT JOIN Manufacturers m ON p.Manuf_ID = m.Manuf_ID
                    LEFT JOIN Product_Families pf ON p.Family_ID = pf.Family_ID
                    LEFT JOIN Inventory_Batches b ON ps.Batch_ID = b.Batch_ID
                    WHERE {' AND '.join(clauses)}
                    ORDER BY ps.Created_At DESC
                    LIMIT 500
                """
                cursor.execute(query, tuple(params))
                return cursor.fetchall() or []
        except Exception as err:
            logger.error(f"Error listing product serials: {err}")
            return []


    def get_product_stock_summary(self, product_id: int) -> Dict[str, Any]:
        """
        Returns accurate physical and theoretical stock breakdown directly linked for a product:
        - Physical_Qty: total physical units in warehouse (from active batches)
        - Theoretical_Reserved_Qty: units currently reserved by confirmed un-dispatched orders
        - Available_Theoretical_Qty: max(0, Physical_Qty - Theoretical_Reserved_Qty)
        - Serials_In_Stock: count of unique physical serials in IN_STOCK status
        - Requires_Serial_Tracking: boolean flag
        """
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT
                    p.Product_ID,
                    p.Product_Name,
                    COALESCE(p.Brand_Mark, '') AS Brand_Mark,
                    COALESCE(p.Category_Name, '') AS Category_Name,
                    COALESCE(p.Color_Finish, '') AS Color_Finish,
                    p.Requires_Serial_Tracking,
                    COALESCE(SUM(CASE WHEN b.Status IN ('Available', 'ACTIVE') THEN b.Quantity_Current ELSE 0 END), 0) AS Physical_Qty,
                    COALESCE(SUM(CASE WHEN b.Status IN ('Available', 'ACTIVE') THEN COALESCE(b.Theoretical_Reserved_Qty, 0) ELSE 0 END), 0) AS Theoretical_Reserved_Qty,
                    (
                        SELECT COUNT(*)
                        FROM Product_Serials ps
                        WHERE ps.Product_ID = p.Product_ID AND ps.Status = 'IN_STOCK'
                    ) AS Serials_In_Stock
                FROM Products_Master p
                LEFT JOIN Inventory_Batches b ON p.Product_ID = b.Product_ID
                WHERE p.Product_ID = %s
                GROUP BY p.Product_ID
                """,
                (int(product_id),),
            )
            row = cursor.fetchone()
            if not row:
                return {
                    "Product_ID": int(product_id),
                    "Physical_Qty": 0,
                    "Theoretical_Reserved_Qty": 0,
                    "Available_Theoretical_Qty": 0,
                    "Serials_In_Stock": 0,
                    "Requires_Serial_Tracking": False,
                }
            phys = int(row.get("Physical_Qty") or 0)
            res = int(row.get("Theoretical_Reserved_Qty") or 0)
            serials_cnt = int(row.get("Serials_In_Stock") or 0)
            row["Physical_Qty"] = phys
            row["Theoretical_Reserved_Qty"] = res
            row["Available_Theoretical_Qty"] = max(0, phys - res)
            row["Serials_In_Stock"] = serials_cnt
            return row
        except Exception as err:
            logger.error(f"Error getting stock summary for product {product_id}: {err}")
            return {
                "Product_ID": int(product_id),
                "Physical_Qty": 0,
                "Theoretical_Reserved_Qty": 0,
                "Available_Theoretical_Qty": 0,
                "Serials_In_Stock": 0,
                "Requires_Serial_Tracking": False,
            }
        finally:
            cursor.close()
            if hasattr(self.db, "get_raw_connection"):
                conn.close()

    def assert_product_exit_authorized(self, product_id: int, serial_number: Optional[str] = None) -> bool:
        """
        Guards physical exit: validates that an appliance product cannot leave stock
        unless processed through the Dispatch Desk (Bureau de Sortie) with an authorized exit voucher.
        Throws PermissionError if an unauthorized direct decrement is attempted.
        """
        summary = self.get_product_stock_summary(product_id)
        if summary.get("Requires_Serial_Tracking"):
            raise PermissionError(
                f"Sortie physique non autorisée : Le produit ID {product_id} "
                f"('{summary.get('Product_Name')}') exige un Bon de Sortie émis par le Bureau de Sortie "
                f"avec scan obligatoire du N° de Série."
            )
        return True


# Alias matching docs specification
SerialTrackingService = SerialTrackingManager
