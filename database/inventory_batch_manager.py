# database/inventory_batch_manager.py

import mysql.connector
import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from decimal import Decimal

from .system_logger import log_methods

@log_methods()
class InventoryBatchManager:
    """
    إدارة عمليات جدول دفعات المخزون (Inventory_Batches).
    """

    def __init__(self, db_instance):
        from .stock_movement_log_manager import StockMovementLogManager  # Add this import

        self.db = db_instance
        self.stock_movement_log = StockMovementLogManager(db_instance)

    @staticmethod
    def get_barcode_prefix_for_po(po_id):
        """
        Return the legacy reception barcode prefix.

        PO_ID already contains the two-digit year and the annual order number
        (example: 2618 for order 18 in 2026). Reception barcodes therefore use
        PO_ID + a zero-padded serial: 2618001, 2618002, ...
        """
        po_text = str(po_id or "").strip()
        if po_text and po_text != "0":
            return po_text
        return datetime.now().strftime('%y')

    @staticmethod
    def extract_smart_barcode_serial(barcode, prefix):
        barcode_text = str(barcode or "")
        prefix_text = str(prefix or "")
        if not prefix_text or not barcode_text.startswith(prefix_text):
            return None

        serial_text = barcode_text[len(prefix_text):]
        if not serial_text.isdigit():
            return None
        return int(serial_text)


    def _create_inventory_batch_legacy(self, product_id, br_id, lot_number, expiry_date,
                               initial_stock_qty, location_id, date_received,
                               po_id=None, unit_price=0.0, tax_rate=0.0, discount=0.0,
                               item_index=1, internal_barcode=None):
        """
        تم دمج التعريفين في تعريف واحد قوي.
        """
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor()

            final_barcode = internal_barcode
            if not final_barcode:
                prefix = self.get_barcode_prefix_for_po(po_id) if po_id else (f"BR{br_id}-" if br_id else "STK")
                final_barcode = self.generate_smart_barcode(prefix, item_index)

            # التحقق من وجود نفس الباركود في نفس الموقع لدمج الكمية
            cursor.execute("""
                SELECT Batch_ID FROM Inventory_Batches
                WHERE Internal_Barcode = %s AND Location_ID = %s
            """, (final_barcode, location_id))

            existing = cursor.fetchone()
            if existing:
                logging.info(f"Mise à jour quantité pour code {final_barcode} loc {location_id}.")
                cursor.execute("""
                    UPDATE Inventory_Batches
                    SET Quantity_Current = Quantity_Current + %s, Quantity_Initial = Quantity_Initial + %s
                    WHERE Batch_ID = %s
                """, (initial_stock_qty, initial_stock_qty, existing[0]))
                batch_id = existing[0]
            else:
                query = """
                    INSERT INTO Inventory_Batches
                    (Product_ID, Location_ID, Lot_Number, Expiry_Date,
                    Quantity_Initial, Quantity_Current, PO_ID, BR_ID, Status, Created_At,
                    Unit_Price_Received, Tax_Rate_Percent, Discount_Percent, Internal_Barcode)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Available', %s, %s, %s, %s, %s)
                """
                params = (product_id, location_id, lot_number, expiry_date,
                        initial_stock_qty, initial_stock_qty, po_id, br_id,
                        date_received, unit_price, tax_rate, discount, final_barcode)

                cursor.execute(query, params)
                batch_id = cursor.lastrowid

            conn.commit()
            return batch_id

        except mysql.connector.Error as err:
            if conn: conn.rollback()
            logging.error(f"Database error in create_inventory_batch: {err}")
            return None
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()

    def _get_next_smart_barcode_legacy(self, po_id):
        """
        تبحث في قاعدة البيانات عن آخر باركود لهذا الطلب وتعطي الرقم التالي مباشرة.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                # نبحث عن الباركودات التي تبدأ برقم الـ PO
                query = "SELECT MAX(Internal_Barcode) FROM Inventory_Batches WHERE Internal_Barcode LIKE %s"
                cursor.execute(query, (f"{po_id}%",))
                last_barcode = cursor.fetchone()[0]

                if last_barcode:
                    # إذا وجدنا مثلاً 252003، نستخرج 003 ونزيده 1
                    try:
                        # طول po_id مثلا 252 (3 أرقام)، نأخذ ما بعده
                        prefix_len = len(str(po_id))
                        last_serial = int(last_barcode[prefix_len:])
                        new_serial = last_serial + 1
                    except ValueError:
                        new_serial = 1
                else:
                    new_serial = 1

                return self.generate_smart_barcode(po_id, new_serial)
        except Exception as e:
            logging.error(f"Error getting next barcode: {e}")
            return f"{po_id}001"

    def _get_next_reception_barcode_legacy(self, br_id):
        """
        Generate a barcode in the scope of one reception voucher.

        A PO can have multiple BRs. Keeping the serial scoped to BR_ID prevents
        two reception vouchers for the same PO from competing for the same
        barcode sequence.
        """
        prefix = f"BR{br_id}-"

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT Internal_Barcode
                    FROM Inventory_Batches
                    WHERE BR_ID = %s AND Internal_Barcode LIKE %s
                    """,
                    (br_id, f"{prefix}%")
                )

                max_serial = 0
                for row in cursor.fetchall():
                    barcode = row[0]
                    if not barcode:
                        continue
                    try:
                        serial = int(str(barcode)[len(prefix):])
                        max_serial = max(max_serial, serial)
                    except (TypeError, ValueError):
                        continue

                next_serial = max_serial + 1
                next_barcode = self.generate_smart_barcode(prefix, next_serial)

                while self.is_barcode_exists_in_db(next_barcode):
                    next_serial += 1
                    next_barcode = self.generate_smart_barcode(prefix, next_serial)

                return next_barcode

        except Exception as e:
            logging.error(f"Error getting next reception barcode: {e}")
            return self.generate_smart_barcode(prefix, 1)

    def get_next_smart_barcode(self, po_id):
        """Return the next legacy barcode for a purchase order: PO_ID + 001."""
        prefix = self.get_barcode_prefix_for_po(po_id)
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT Internal_Barcode FROM Inventory_Batches WHERE Internal_Barcode LIKE %s",
                    (f"{prefix}%",)
                )

                max_serial = 0
                for row in cursor.fetchall():
                    barcode = row[0] if row else None
                    serial = self.extract_smart_barcode_serial(barcode, prefix)
                    if serial is not None:
                        max_serial = max(max_serial, serial)

                next_serial = max_serial + 1
                next_barcode = self.generate_smart_barcode(prefix, next_serial)
                while self.is_barcode_exists_in_db(next_barcode):
                    next_serial += 1
                    next_barcode = self.generate_smart_barcode(prefix, next_serial)
                return next_barcode

        except Exception as e:
            logging.error(f"Error getting next barcode: {e}")
            return self.generate_smart_barcode(prefix, 1)

    def get_next_reception_barcode(self, br_id, po_id=None):
        """
        Return the next barcode for a reception while preserving the old shape.

        The serial is first based on existing rows in the current BR, then it
        skips any value already used anywhere in Inventory_Batches. This keeps
        BR editing stable and prevents collisions across multiple BRs for the
        same PO.
        """
        prefix = None
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                if not po_id and br_id:
                    cursor.execute("SELECT PO_ID FROM Reception_Log WHERE BR_ID = %s", (br_id,))
                    row = cursor.fetchone()
                    po_id = row[0] if row else None

                prefix = self.get_barcode_prefix_for_po(po_id) if po_id else f"BR{br_id}-"
                cursor.execute(
                    """
                    SELECT Internal_Barcode
                    FROM Inventory_Batches
                    WHERE BR_ID = %s AND Internal_Barcode LIKE %s
                    """,
                    (br_id, f"{prefix}%")
                )

                max_serial = 0
                for row in cursor.fetchall():
                    barcode = row[0] if row else None
                    serial = self.extract_smart_barcode_serial(barcode, prefix)
                    if serial is not None:
                        max_serial = max(max_serial, serial)

                next_serial = max_serial + 1
                next_barcode = self.generate_smart_barcode(prefix, next_serial)
                while self.is_barcode_exists_in_db(next_barcode):
                    next_serial += 1
                    next_barcode = self.generate_smart_barcode(prefix, next_serial)
                return next_barcode

        except Exception as e:
            logging.error(f"Error getting next reception barcode: {e}")
            if not prefix:
                prefix = self.get_barcode_prefix_for_po(po_id) if po_id else f"BR{br_id}-"
            return self.generate_smart_barcode(prefix, 1)

    def is_barcode_exists_in_db(self, barcode):
        """التحقق مما إذا كان الباركود موجوداً في قاعدة البيانات"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT COUNT(*) FROM Inventory_Batches WHERE Internal_Barcode = %s"
                cursor.execute(query, (barcode,))
                count = cursor.fetchone()[0]
                return count > 0
        except Exception as e:
            logging.error(f"Error checking barcode existence: {e}")
            return True # نفترض وجوده لتجنب الأخطاء

    def update_batch_location_status(self, batch_id: int, location_id: Optional[int] = None, new_status: Optional[str] = None) -> bool:
        updates = []
        params = []

        if location_id is not None:
            updates.append("Location_ID = %s")
            params.append(location_id)

        if new_status is not None:
            valid_statuses = ['Available', 'Quarantined', 'Expired', 'Depleted']
            if new_status not in valid_statuses:
                logging.error(f"Invalid status '{new_status}' provided for batch {batch_id}.")
                return False
            updates.append("Status = %s")
            params.append(new_status)

        if not updates:
            return False

        params.append(batch_id)
        query = f"UPDATE Inventory_Batches SET {', '.join(updates)} WHERE Batch_ID = %s"

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                return cursor.rowcount > 0
        except mysql.connector.Error as e:
            logging.error(f"Error updating batch {batch_id}: {e}")
            raise

    def get_batches_by_product_id(self, product_id: int, min_qty: int = 1) -> List[Dict]:
        """جلب الدفعات مع معالجة حذر لأسماء الأعمدة."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT
                        b.Batch_ID, b.Product_ID, b.Location_ID, b.Lot_Number,
                        b.Expiry_Date, b.Quantity_Initial, b.Quantity_Current,
                        b.Unit_Price_Received, b.Internal_Barcode, b.Status,
                        l.Location_Name, p.Product_Name, p.Stock_Unit
                    FROM Inventory_Batches b
                    JOIN Products_Master p ON b.Product_ID = p.Product_ID
                    LEFT JOIN Locations l ON b.Location_ID = l.Location_ID
                    WHERE b.Product_ID = %s AND b.Quantity_Current >= %s
                    ORDER BY b.Expiry_Date ASC
                """
                cursor.execute(query, (product_id, min_qty))
                return cursor.fetchall()
        except mysql.connector.Error as e:
            logging.error(f"Error fetching batches: {e}")
            return []

    def adjust_batch_quantity(self, batch_id: int, quantity_change: int, movement_type: str,
                               reason_id: Optional[int] = None, user_id: Optional[int] = None) -> bool:
        try:
            change = Decimal(str(quantity_change))
            with self.db.get_db_connection() as conn:
                conn.autocommit = False
                cursor = conn.cursor(dictionary=True)

                cursor.execute(
                    """
                    SELECT b.Product_ID, b.Quantity_Current, p.Stock_Unit
                    FROM Inventory_Batches b
                    LEFT JOIN Products_Master p ON b.Product_ID = p.Product_ID
                    WHERE b.Batch_ID = %s
                    FOR UPDATE
                    """,
                    (batch_id,)
                )
                res = cursor.fetchone()
                if not res:
                    conn.rollback()
                    return False
                product_id = res['Product_ID']
                new_quantity = Decimal(str(res['Quantity_Current'])) + change
                if new_quantity < 0:
                    conn.rollback()
                    return False

                cursor.execute("""
                    UPDATE Inventory_Batches
                    SET Quantity_Current = %s,
                        Status = CASE
                            WHEN %s = 0 THEN 'Depleted'
                            WHEN Status = 'Depleted' THEN 'Available'
                            ELSE Status
                        END
                    WHERE Batch_ID = %s
                """, (new_quantity, new_quantity, batch_id))

                movement_id = self.stock_movement_log.create_movement_log(
                    product_id=product_id,
                    movement_type=movement_type,
                    qty_change=change,
                    unit_used=res.get('Stock_Unit') or 'Unit',
                    batch_id=batch_id,
                    reason_id=reason_id,
                    user_id=user_id,
                    external_cursor=cursor
                )
                if not movement_id:
                    conn.rollback()
                    return False

                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error in adjust_batch_quantity: {e}")
            return False


    def get_batches_by_po_id(self, po_id: int) -> List[Dict]:
        """
        جلب جميع الباتشات المرتبطة بطلب شراء معين.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                # تم التحديث لجلب البيانات المالية أيضاً
                query = """
                    SELECT
                        Product_ID,
                        Quantity_Initial AS Received_Qty,
                        Lot_Number,
                        Expiry_Date,
                        Location_ID,
                        Unit_Price_Received,
                        Tax_Rate_Percent,
                        Discount_Percent
                    FROM Inventory_Batches
                    WHERE PO_ID = %s
                """
                cursor.execute(query, (po_id,))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error fetching batches for PO {po_id}: {e}")
            return []

    def open_pack_transaction(self, data: Dict, user_id: Optional[int] = None) -> bool:
        conn = None
        cursor = None
        try:
            qty_to_open = Decimal(str(data.get('Qty_To_Open', 0)))
            if qty_to_open <= 0:
                return False

            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("""
                SELECT b.Product_ID, b.Quantity_Current, b.Expiry_Date, b.Location_ID,
                       p.Open_Vial_Stability_Days, p.Stock_Unit
                FROM Inventory_Batches b
                JOIN Products_Master p ON b.Product_ID = p.Product_ID
                WHERE b.Batch_ID = %s
                FOR UPDATE
            """, (data['Batch_ID'],))
            batch = cursor.fetchone()
            if not batch or Decimal(str(batch['Quantity_Current'])) < qty_to_open:
                conn.rollback()
                return False

            open_expiry = data.get('Calculated_Open_Expiry')
            if not open_expiry:
                official_expiry = batch.get('Expiry_Date')
                if isinstance(official_expiry, datetime):
                    official_expiry = official_expiry.date()
                elif isinstance(official_expiry, str):
                    try:
                        official_expiry = datetime.strptime(official_expiry[:10], "%Y-%m-%d").date()
                    except ValueError:
                        official_expiry = None

                stability_days = int(batch.get('Open_Vial_Stability_Days') or 30)
                calculated_expiry = date.today() + timedelta(days=stability_days)
                open_expiry = min(official_expiry, calculated_expiry) if official_expiry else calculated_expiry

            # خصم من المخزن المغلق
            new_parent_qty = Decimal(str(batch['Quantity_Current'])) - qty_to_open
            parent_status = 'Depleted' if new_parent_qty <= 0 else batch.get('Status', 'Available')
            cursor.execute("""
                UPDATE Inventory_Batches
                SET Quantity_Current = %s,
                    Status = %s
                WHERE Batch_ID = %s
            """, (new_parent_qty, parent_status, data['Batch_ID']))

            # إنشاء الحاوية المفتوحة (المنطق المختصر)
            cursor.execute("""
                INSERT INTO Active_Containers
                (Parent_Batch_ID, Product_ID, Date_Opened, Open_Expiration_Date,
                 Initial_Usage_Qty, Remaining_Usage_Qty, Current_Location_ID, Status)
                VALUES (%s, %s, NOW(), %s, %s, %s, %s, 'In_Use')
            """, (
                data['Batch_ID'],
                batch['Product_ID'],
                open_expiry,
                qty_to_open,
                qty_to_open,
                data.get('Current_Location_ID') or batch.get('Location_ID')
            ))
            container_id = cursor.lastrowid

            # [التصحيح]: تسجيل الحركة مع User_ID
            movement_id = self.stock_movement_log.create_movement_log(
                product_id=batch['Product_ID'],
                movement_type='Open_Pack',
                qty_change=-abs(qty_to_open),
                unit_used=batch.get('Stock_Unit') or 'Stock_Unit',
                batch_id=data['Batch_ID'],
                container_id=container_id,
                user_id=user_id,
                notes="Ouverture de paquet",
                external_cursor=cursor
            )
            if not movement_id:
                conn.rollback()
                return False

            conn.commit(); return True
        except Exception as e:
            if conn: conn.rollback()
            logging.error(f"Error in open_pack_transaction: {e}", exc_info=True)
            return False
        finally:
            if conn and conn.is_connected():
                if cursor:
                    cursor.close()
                conn.close()

    def direct_consume_batch_unit(self, batch_id: int, qty: int = 1, user_id: Optional[int] = None, notes: Optional[str] = None) -> bool:
        """
        تم تصحيح الخطأ Ambiguous Product_ID هنا عن طريق تحديد b.Product_ID
        """
        qty_to_consume = Decimal(str(qty))
        if qty_to_consume <= 0:
            return False

        try:
            with self.db.get_db_connection() as conn:
                conn.autocommit = False
                cursor = conn.cursor()

                # تصحيح SQL: تحديد p أو b لمنع الغموض
                query = """
                    SELECT b.Product_ID, b.Quantity_Current, b.Status, p.Stock_Unit
                    FROM Inventory_Batches b
                    JOIN Products_Master p ON b.Product_ID = p.Product_ID
                    WHERE b.Batch_ID = %s
                    FOR UPDATE
                """
                cursor.execute(query, (batch_id,))
                res = cursor.fetchone()

                if not res:
                    logging.warning(f"Batch {batch_id} not found.")
                    conn.rollback()
                    return False

                product_id, current_qty, current_status, unit_used = res
                current_qty = Decimal(str(current_qty))
                if current_qty < qty_to_consume:
                    logging.warning(f"Insufficient quantity in batch {batch_id}")
                    conn.rollback()
                    return False

                # تنفيذ عملية الخصم
                new_qty = current_qty - qty_to_consume
                new_status = 'Depleted' if new_qty <= 0 else current_status
                update_query = """
                    UPDATE Inventory_Batches
                    SET Quantity_Current = %s,
                        Status = %s
                    WHERE Batch_ID = %s
                """
                cursor.execute(update_query, (new_qty, new_status, batch_id))

                if cursor.rowcount == 0:
                    logging.warning(f"Insufficient quantity in batch {batch_id}")
                    conn.rollback()
                    return False

                # تسجيل الحركة في السجل
                movement_id = self.stock_movement_log.create_movement_log(
                    product_id=product_id,
                    movement_type='Patient_Test',
                    qty_change=-abs(qty_to_consume),
                    unit_used=unit_used if unit_used else 'Unit',
                    batch_id=batch_id,
                    user_id=user_id,
                    notes=notes or "Consommation Directe",
                    external_cursor=cursor
                )
                if not movement_id:
                    conn.rollback()
                    return False

                conn.commit()
                return True

        except Exception as e:
            logging.error(f"Error in direct_consume_batch_unit: {e}", exc_info=True)
            return False

    def _transfer_barcode_for_location(self, cursor, source_barcode, source_batch_id, target_location_id):
        stem = str(source_barcode or f"B{source_batch_id}").strip() or f"B{source_batch_id}"
        base = f"{stem}-L{target_location_id}"
        candidate = base[:50]
        serial = 1

        cursor.execute(
            """
            SELECT Internal_Barcode
            FROM Inventory_Batches
            WHERE Internal_Barcode = %s AND Location_ID = %s
            LIMIT 1
            """,
            (candidate, target_location_id)
        )
        existing_target = cursor.fetchone()
        if existing_target:
            if isinstance(existing_target, dict):
                return existing_target['Internal_Barcode']
            return existing_target[0]

        while True:
            cursor.execute(
                "SELECT Batch_ID FROM Inventory_Batches WHERE Internal_Barcode = %s LIMIT 1",
                (candidate,)
            )
            if not cursor.fetchone():
                return candidate

            suffix = f"-{serial}"
            candidate = f"{base[:50 - len(suffix)]}{suffix}"
            serial += 1

    def transfer_batch_location(self, batch_id: int, new_location_id: int, qty: int, user_id: Optional[int] = None) -> bool:
        """
        نقل كمية من موقع لآخر مع الحفاظ على الكود بار الأصلي والكمية الابتدائية.
        """
        if qty <= 0:
            return False

        try:
            with self.db.get_db_connection() as conn:
                conn.autocommit = False # بدء المعاملة
                cursor = conn.cursor(dictionary=True)

                try:
                    # 1. جلب البيانات الأصلية وقفل السطر
                    cursor.execute("""
                        SELECT b.*, p.Stock_Unit
                        FROM Inventory_Batches b
                        JOIN Products_Master p ON b.Product_ID = p.Product_ID
                        WHERE b.Batch_ID = %s FOR UPDATE
                    """, (batch_id,))

                    original = cursor.fetchone()

                    if not original or float(original['Quantity_Current']) < qty:
                        logging.warning("Transfert échoué: Quantité insuffisante.")
                        conn.rollback()
                        return False

                    if int(original['Location_ID']) == int(new_location_id):
                        conn.rollback()
                        return False

                    # تعديل: استخدام الكود بار الأصلي مباشرة دون إضافة لاحقة الموقع
                    target_barcode = original['Internal_Barcode']
                    unit_label = original.get('Stock_Unit', 'U')

                    # 2. خصم الكمية من المصدر
                    source_new_qty = Decimal(str(original['Quantity_Current'])) - Decimal(str(qty))
                    source_status = 'Depleted' if source_new_qty <= 0 else original.get('Status', 'Available')
                    cursor.execute("""
                        UPDATE Inventory_Batches
                        SET Quantity_Current = %s,
                            Status = %s
                        WHERE Batch_ID = %s
                    """, (source_new_qty, source_status, batch_id))

                    # 3. معالجة الوجهة (دمج أو إنشاء)
                    cursor.execute("""
                        SELECT Batch_ID
                        FROM Inventory_Batches
                        WHERE Internal_Barcode = %s AND Location_ID = %s
                        LIMIT 1 FOR UPDATE
                    """, (target_barcode, new_location_id))

                    target_batch = cursor.fetchone()
                    final_target_id = None

                    if target_batch:
                        # دمج الكمية إذا كان المنتج موجوداً مسبقاً بنفس الكود بار في الموقع الجديد
                        final_target_id = target_batch['Batch_ID']
                        cursor.execute("""
                            UPDATE Inventory_Batches
                            SET Quantity_Current = Quantity_Current + %s,
                                Status = CASE WHEN Status = 'Depleted' THEN 'Available' ELSE Status END
                            WHERE Batch_ID = %s
                        """, (qty, final_target_id))
                    else:
                        insert_query = """
                            INSERT INTO Inventory_Batches
                            (Product_ID, Location_ID, Lot_Number, Expiry_Date, Quantity_Initial,
                            Quantity_Current, PO_ID, BR_ID, Status, Internal_Barcode,
                            Unit_Price_Received, Tax_Rate_Percent, Discount_Percent, Created_At)
                            VALUES (%s, %s, %s, %s, 0, %s, %s, %s, 'Available', %s, %s, %s, %s, NOW())
                        """
                        params = (
                            original['Product_ID'],
                            new_location_id,
                            original['Lot_Number'],
                            original['Expiry_Date'],
                            qty,  # هذه تعود لـ Quantity_Current
                            original['PO_ID'],
                            original['BR_ID'],
                            target_barcode,
                            original['Unit_Price_Received'],
                            original['Tax_Rate_Percent'],
                            original['Discount_Percent']
                        )

                        cursor.execute(insert_query, params)
                        final_target_id = cursor.lastrowid

                    # 4. تسجيل الحركة في السجل
                    source_movement_id = self.stock_movement_log.create_movement_log(
                        product_id=original['Product_ID'],
                        movement_type='Transfer',
                        qty_change=Decimal(str(-abs(qty))),
                        unit_used=unit_label,
                        batch_id=batch_id,
                        user_id=user_id,
                        notes=f"Transfert: Loc {original['Location_ID']} -> {new_location_id}",
                        external_cursor=cursor
                    )

                    target_movement_id = self.stock_movement_log.create_movement_log(
                        product_id=original['Product_ID'],
                        movement_type='Transfer',
                        qty_change=Decimal(str(qty)),
                        unit_used=unit_label,
                        batch_id=final_target_id,
                        user_id=user_id,
                        notes=f"Transfert: Loc {original['Location_ID']} -> {new_location_id}",
                        external_cursor=cursor
                    )
                    if not source_movement_id or not target_movement_id:
                        conn.rollback()
                        return False

                    conn.commit()
                    return True

                except Exception as inner_e:
                    conn.rollback()
                    logging.error(f"SQL Error in transfer: {inner_e}")
                    raise inner_e
                finally:
                    cursor.close()

        except Exception as e:
            logging.error(f"Critical Error in transfer_batch_location: {e}", exc_info=True)
            return False

    def create_inventory_batch(self, product_id, br_id, lot_number, expiry_date,
                               initial_stock_qty, location_id, date_received,
                               po_id=None, unit_price=0.0, tax_rate=0.0, discount=0.0,
                               item_index=1, internal_barcode=None, batch_id_override=None):
        """
        تم تحديث هذه الدالة لتكون آمنة مع القيود الجديدة.
        تقوم بإدراج دفعة جديدة، وإذا تم تمرير internal_barcode، تستخدمه.
        """
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor()

            # 1. توليد الباركود إذا لم يكن موجوداً
            prefix = self.get_barcode_prefix_for_po(po_id) if po_id else (f"BR{br_id}-" if br_id else "STK")
            final_barcode = internal_barcode
            barcode_was_provided = bool(final_barcode)
            if not final_barcode:
                # دالة التوليد (تأكد من وجودها)
                final_barcode = self.generate_smart_barcode(prefix, item_index)

            cursor.execute("""
                SELECT Batch_ID, Location_ID
                FROM Inventory_Batches
                WHERE Internal_Barcode = %s
                LIMIT 1
            """, (final_barcode,))
            barcode_owner = cursor.fetchone()
            if barcode_owner and int(barcode_owner[1]) != int(location_id) and not barcode_was_provided:
                next_serial = item_index + 1
                while True:
                    candidate = self.generate_smart_barcode(prefix, next_serial)
                    cursor.execute(
                        "SELECT Batch_ID FROM Inventory_Batches WHERE Internal_Barcode = %s LIMIT 1",
                        (candidate,)
                    )
                    if not cursor.fetchone():
                        final_barcode = candidate
                        break
                    next_serial += 1

            # 2. التحقق مما إذا كان الباركود موجوداً في نفس الموقع (لتجنب الخطأ)
            cursor.execute("""
                SELECT Batch_ID FROM Inventory_Batches
                WHERE Internal_Barcode = %s AND Location_ID = %s
            """, (final_barcode, location_id))

            existing = cursor.fetchone()
            if existing:
                # إذا وجدنا نفس الباركود في نفس الموقع، ندمج الكمية (في حالة الاستلام المتكرر)
                logging.info(f"Reception: Code-barres {final_barcode} existe déjà dans Loc {location_id}. Mise à jour de la quantité.")
                cursor.execute("""
                    UPDATE Inventory_Batches
                    SET Quantity_Current = Quantity_Current + %s, Quantity_Initial = Quantity_Initial + %s
                    WHERE Batch_ID = %s
                """, (initial_stock_qty, initial_stock_qty, existing[0]))
                batch_id = existing[0]
            else:
                # إنشاء سطر جديد
                query = """
                    INSERT INTO Inventory_Batches
                    (Product_ID, Location_ID, Lot_Number, Expiry_Date,
                    Quantity_Initial, Quantity_Current, PO_ID, BR_ID, Status, Created_At,
                    Unit_Price_Received, Tax_Rate_Percent, Discount_Percent, Internal_Barcode)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Available', %s, %s, %s, %s, %s)
                """
                params = (product_id, location_id, lot_number, expiry_date,
                        initial_stock_qty, initial_stock_qty, po_id, br_id,
                        date_received, unit_price, tax_rate, discount, final_barcode)

                cursor.execute(query, params)
                batch_id = cursor.lastrowid

            conn.commit()
            return batch_id

        except mysql.connector.Error as err:
            if conn: conn.rollback()
            logging.error(f"Database error in create_inventory_batch: {err}")
            return None
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()

    @staticmethod
    def generate_ean13_for_batch(batch_id: int) -> str:
        """
        Generates an EAN-13 barcode using prefix '200' + 9-digit Batch_ID + check digit.
        """
        prefix = "200"
        padded_id = str(batch_id).zfill(9)
        base = prefix + padded_id

        odds = sum(int(base[i]) for i in range(0, 12, 2))
        evens = sum(int(base[i]) for i in range(1, 12, 2))
        total = odds + (evens * 3)
        check_digit = (10 - (total % 10)) % 10

        return base + str(check_digit)

    def is_barcode_available(self, barcode: str, exclude_batch_id: Optional[int] = None) -> Tuple[bool, Optional[str]]:
        """
        Vérifie si le code-barres est libre et non assigné à un autre lot ou produit.
        """
        clean_code = str(barcode or '').strip()
        if not clean_code:
            return False, "Le code-barres ne peut pas être vide."

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)

                # 1. Vérifier Inventory_Batches
                query_batch = """
                    SELECT b.Batch_ID, b.Lot_Number, p.Product_Name, b.Quantity_Current
                    FROM Inventory_Batches b
                    JOIN Products_Master p ON b.Product_ID = p.Product_ID
                    WHERE (b.Internal_Barcode = %s OR b.External_Barcode = %s)
                """
                params = [clean_code, clean_code]
                if exclude_batch_id:
                    query_batch += " AND b.Batch_ID != %s"
                    params.append(exclude_batch_id)
                query_batch += " LIMIT 1"
                cursor.execute(query_batch, tuple(params))
                match_batch = cursor.fetchone()
                if match_batch:
                    return False, f"Code-barres déjà utilisé par le lot '{match_batch['Lot_Number']}' du produit '{match_batch['Product_Name']}'."

                # 2. Vérifier Products_Master
                cursor.execute("SELECT Product_ID, Product_Name FROM Products_Master WHERE Barcode = %s LIMIT 1", (clean_code,))
                match_prod = cursor.fetchone()
                if match_prod:
                    return False, f"Code-barres déjà attribué au produit maître '{match_prod['Product_Name']}'."

                return True, None
        except Exception as e:
            logging.error(f"Error checking barcode availability: {e}")
            return False, f"Erreur lors de la vérification du code-barres: {e}"

    def generate_unique_barcode(self, prefix: str = "200") -> str:
        """
        Génère un code-barres EAN-13 interne unique, valide et garanti sans collision.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COALESCE(MAX(Batch_ID), 0) FROM Inventory_Batches")
                row = cursor.fetchone()
                max_id = row[0] if row else 1000
        except Exception:
            max_id = 1000

        counter = max_id + 1
        for _ in range(10000):
            padded = str(counter).zfill(9)
            base = prefix[:3] + padded[-9:]
            odds = sum(int(base[i]) for i in range(0, 12, 2))
            evens = sum(int(base[i]) for i in range(1, 12, 2))
            total = odds + (evens * 3)
            check_digit = (10 - (total % 10)) % 10
            candidate = base + str(check_digit)

            is_avail, _ = self.is_barcode_available(candidate)
            if is_avail:
                return candidate
            counter += 1

        import time
        ts = str(int(time.time()))[-9:]
        base = prefix[:3] + ts
        odds = sum(int(base[i]) for i in range(0, 12, 2))
        evens = sum(int(base[i]) for i in range(1, 12, 2))
        total = odds + (evens * 3)
        check_digit = (10 - (total % 10)) % 10
        return base + str(check_digit)

    def _ensure_bl_number_column(self, cursor) -> bool:
        """التأكد من وجود عمود رقم وصل التسليم (BL_Number) في جدول Inventory_Batches."""
        try:
            cursor.execute("SHOW COLUMNS FROM Inventory_Batches LIKE 'BL_Number'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE Inventory_Batches ADD COLUMN BL_Number VARCHAR(100) NULL")
            return True
        except Exception:
            return False

    def add_direct_batch(self, data: dict, user_id: int = None) -> bool:
        """
        Adds a batch directly to inventory without a Reception (BR) or Purchase Order (PO).
        Generates robust EAN-13 barcode after insert. Enforces complete product & batch data.
        """
        if not data.get('Product_ID'):
            raise ValueError("Product_ID est obligatoire pour enregistrer un lot.")
        if not data.get('Location_ID'):
            raise ValueError("Location_ID est obligatoire pour enregistrer un lot.")
        if not data.get('Lot_Number') or str(data.get('Lot_Number')).strip().upper() in ['N/A', 'NONE', 'NULL', '']:
            raise ValueError("Lot_Number valide est obligatoire pour assurer la traçabilité.")
        if float(data.get('Quantity', 0)) <= 0:
            raise ValueError("La quantité doit être strictement positive.")
        if float(data.get('Unit_Price_HT', 0)) <= 0:
            raise ValueError("Le prix d'achat HT unitaire doit être supérieur à zéro.")

        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor()

            query = """
                INSERT INTO Inventory_Batches
                (Product_ID, Location_ID, Lot_Number, Expiry_Date,
                 Quantity_Initial, Quantity_Current, Status, Created_At,
                 Unit_Price_Received, Tax_Rate_Percent, Discount_Percent,
                 Selling_Price_HT, Selling_Price_HT_2, Selling_Price_HT_3, Selling_Price_HT_4,
                 Selling_TVA_Percent, Reception_Note, Supplier_ID, External_Barcode, Internal_Barcode)
                VALUES (%s, %s, %s, %s, %s, %s, 'Available', NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'TMP')
            """

            params = (
                data['Product_ID'], data['Location_ID'], data['Lot_Number'], data['Expiry_Date'],
                data['Quantity'], data['Quantity'],
                data.get('Unit_Price_HT', 0.0), data.get('Tax_Rate_Percent', 19.0), data.get('Discount_Percent', 0.0),
                data.get('Selling_Price_HT', 0.0), data.get('Selling_Price_HT_2', 0.0),
                data.get('Selling_Price_HT_3', 0.0), data.get('Selling_Price_HT_4', 0.0),
                data.get('Selling_TVA_Percent', 19.0), data.get('Batch_Note', ''),
                data.get('Supplier_ID'), data.get('External_Barcode', '').strip()
            )

            cursor.execute(query, params)
            batch_id = cursor.lastrowid

            final_barcode = self.generate_ean13_for_batch(batch_id)
            cursor.execute("UPDATE Inventory_Batches SET Internal_Barcode = %s WHERE Batch_ID = %s", (final_barcode, batch_id))

            bl_number = str(data.get('BL_Number') or '').strip()
            if bl_number and self._ensure_bl_number_column(cursor):
                cursor.execute("UPDATE Inventory_Batches SET BL_Number = %s WHERE Batch_ID = %s", (bl_number, batch_id))

            cursor.execute("""
                INSERT INTO Stock_Movement_Log
                (Product_ID, Batch_ID, Movement_Type, Qty_Change, Unit_Used, User_ID, Notes)
                VALUES (%s, %s, 'Purchase_Receive', %s, 'Unité', %s, 'Ajout rapide direct')
            """, (data['Product_ID'], batch_id, data['Quantity'], user_id))

            ext_barcode = data.get('External_Barcode', '').strip()
            if ext_barcode:
                cursor.execute("SELECT Barcode FROM Products_Master WHERE Product_ID = %s", (data['Product_ID'],))
                res = cursor.fetchone()
                existing_barcodes = res[0] if res and res[0] else ''
                barcodes_list = [b.strip() for b in existing_barcodes.split(',')] if existing_barcodes else []
                if ext_barcode not in barcodes_list:
                    barcodes_list.append(ext_barcode)
                    new_barcodes_str = ','.join(barcodes_list)
                    cursor.execute("UPDATE Products_Master SET Barcode = %s WHERE Product_ID = %s",
                                   (new_barcodes_str, data['Product_ID']))

            color_finish = str(data.get('Color_Finish') or '').strip()
            if color_finish:
                cursor.execute(
                    "UPDATE Products_Master SET Color_Finish = %s WHERE Product_ID = %s",
                    (color_finish, data['Product_ID'])
                )
                try:
                    cursor.execute(
                        "INSERT IGNORE INTO Product_Colors (Color_Name, Color_Code, Description, Is_Active) VALUES (%s, '#CBD5E1', 'Ajouté via Ajout Rapide', TRUE)",
                        (color_finish,)
                    )
                except Exception:
                    pass

            conn.commit()
            data['Generated_Barcode'] = final_barcode
            return True

        except Exception as e:
            if conn: conn.rollback()
            import logging
            logging.error(f"Database error in add_direct_batch: {e}")
            return False
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()

    def update_direct_batch(self, batch_id: int, data: dict, user_id: int = None) -> bool:
        """
        Updates an existing directly-added batch (BR_ID is NULL).
        """
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor()

            # Optional validation: check if BR_ID is NULL
            cursor.execute("SELECT BR_ID FROM Inventory_Batches WHERE Batch_ID = %s", (batch_id,))
            res = cursor.fetchone()
            if res and res[0] is not None:
                raise ValueError("Cannot edit a batch associated with a Reception Log (BR_ID is not NULL).")

            query = """
                UPDATE Inventory_Batches SET
                Product_ID = %s, Location_ID = %s, Lot_Number = %s, Expiry_Date = %s,
                Quantity_Initial = %s, Quantity_Current = %s,
                Unit_Price_Received = %s, Tax_Rate_Percent = %s, Discount_Percent = %s,
                Selling_Price_HT = %s, Selling_Price_HT_2 = %s, Selling_Price_HT_3 = %s, Selling_Price_HT_4 = %s,
                Selling_TVA_Percent = %s, Reception_Note = %s, Supplier_ID = %s, External_Barcode = %s
                WHERE Batch_ID = %s
            """

            params = (
                data['Product_ID'], data['Location_ID'], data['Lot_Number'], data['Expiry_Date'],
                data['Quantity'], data['Quantity'],
                data.get('Unit_Price_HT', 0.0), data.get('Tax_Rate_Percent', 19.0), data.get('Discount_Percent', 0.0),
                data.get('Selling_Price_HT', 0.0), data.get('Selling_Price_HT_2', 0.0),
                data.get('Selling_Price_HT_3', 0.0), data.get('Selling_Price_HT_4', 0.0),
                data.get('Selling_TVA_Percent', 19.0), data.get('Batch_Note', ''), data.get('Supplier_ID'),
                data.get('External_Barcode', '').strip(),
                batch_id
            )

            cursor.execute(query, params)

            bl_number = str(data.get('BL_Number') or '').strip()
            if 'BL_Number' in data and self._ensure_bl_number_column(cursor):
                cursor.execute(
                    "UPDATE Inventory_Batches SET BL_Number = %s WHERE Batch_ID = %s",
                    (bl_number or None, batch_id)
                )

            cursor.execute("""
                INSERT INTO Stock_Movement_Log
                (Product_ID, Batch_ID, Movement_Type, Qty_Change, Unit_Used, User_ID, Notes)
                VALUES (%s, %s, 'Adjustment', 0, 'Unité', %s, 'Modification complète du lot direct')
            """, (data['Product_ID'], batch_id, user_id))

            ext_barcode = data.get('External_Barcode', '').strip()
            if ext_barcode:
                cursor.execute("SELECT Barcode FROM Products_Master WHERE Product_ID = %s", (data['Product_ID'],))
                res = cursor.fetchone()
                existing_barcodes = res[0] if res and res[0] else ''
                barcodes_list = [b.strip() for b in existing_barcodes.split(',')] if existing_barcodes else []
                if ext_barcode not in barcodes_list:
                    barcodes_list.append(ext_barcode)
                    new_barcodes_str = ','.join(barcodes_list)
                    cursor.execute("UPDATE Products_Master SET Barcode = %s WHERE Product_ID = %s",
                                   (new_barcodes_str, data['Product_ID']))

            color_finish = str(data.get('Color_Finish') or '').strip()
            if color_finish:
                cursor.execute(
                    "UPDATE Products_Master SET Color_Finish = %s WHERE Product_ID = %s",
                    (color_finish, data['Product_ID'])
                )
                try:
                    cursor.execute(
                        "INSERT IGNORE INTO Product_Colors (Color_Name, Color_Code, Description, Is_Active) VALUES (%s, '#CBD5E1', 'Ajouté via Ajout Rapide', TRUE)",
                        (color_finish,)
                    )
                except Exception:
                    pass

            conn.commit()
            return True

        except Exception as e:
            if conn: conn.rollback()
            import logging
            logging.error(f"Database error in update_direct_batch: {e}")
            return False
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()

    @staticmethod
    def generate_smart_barcode(prefix, item_serial):
        """
        توليد باركود يعتمد على المعرف (PO_ID) + تسلسل.
        مثال: PO 252, Item 1 -> 252001
        """
        try:
            serial_formatted = str(item_serial).zfill(3)
            return f"{prefix}{serial_formatted}"
        except:
            current_year = datetime.now().strftime('%y')
            return f"{current_year}{item_serial}"


    def process_full_reception(self, header_data, items, user_id=None):
        """
        معالجة عملية استلام كاملة مع تسجيل معرف المستخدم.
        """
        from .reception_log_manager import ReceptionLogManager
        return ReceptionLogManager(self.db).process_full_reception(
            header_data, items, user_id=user_id
        )

    def get_all_batches_with_details(self, include_zero_stock=False) -> List[Dict]:
        """
        جلب جميع الدفعات مع تفاصيل المنتج والمورد (تم تصحيح جلب اسم المورد).
        """
        try:
            with self.db.get_db_connection() as conn:
                # التأكد من تحديث البيانات
                if conn.is_connected():
                    conn.commit()

                cursor = conn.cursor(dictionary=True)

                # شرط استبعاد المنتجات المحذوفة
                where_clauses = ["P.Deleted_At IS NULL"]

                if not include_zero_stock:
                    where_clauses.append("B.Quantity_Current > 0")

                where_str = " WHERE " + " AND ".join(where_clauses)

                # --- التعديل الجوهري في الاستعلام (JOIN) ---
                # نربط مع Reception_Log (RL) ثم مع Suppliers (S) لضمان ظهور المورد
                query = f"""
                    SELECT
                        B.Batch_ID,
                        B.Product_ID,
                        P.Is_Billable,
                        P.POS_Priority_Group,
                        B.Internal_Barcode,
                        B.External_Barcode,
                        P.Product_Name,
                        P.Manuf_Cat_No,
                        F.Family_Name,
                        P.Family_ID,
                        P.Color_Finish,
                        IFNULL(A.Automate_Name, 'Général') AS Automate_Name,
                        M.Manuf_Name,

                        -- جلب اسم المورد بدقة: الأولوية للمربوط بالاستلام، ثم المربوط بالطلب
                        COALESCE(S_DIR.Supplier_Name, S_RL.Supplier_Name, S_PO.Supplier_Name, '---') AS Supplier_Name,
                        COALESCE(B.Supplier_ID, RL.Supplier_ID, PO.Supplier_ID) AS Supplier_ID,

                        P.Manuf_ID,
                        P.Preferred_Automate_ID,
                        P.Minimum_Stock_Level,
                        P.Alert_Before_Expiry_Days,
                        B.Lot_Number,
                        B.Expiry_Date,
                        B.Quantity_Current,
                        (
                            SELECT SUM(IB2.Quantity_Initial)
                            FROM Inventory_Batches IB2
                            WHERE IB2.Internal_Barcode = B.Internal_Barcode
                        ) AS Quantity_Initial,
                        B.Quantity_Initial AS Reception_Quantity_Initial,
                        B.Unit_Price_Received,
                        B.Tax_Rate_Percent,
                        B.Discount_Percent,
                        B.Selling_Price_HT,
                        B.Selling_Price_HT_2,
                        B.Selling_Price_HT_3,
                        B.Selling_Price_HT_4,
                        B.Selling_TVA_Percent,
                        P.Stock_Unit,
                        P.Ordering_Unit,
                        P.Stock_Qty_Per_Order_Unit,
                        P.Usage_Unit,
                        P.Usage_Qty_Per_Stock_Unit,
                        P.Barcode,
                        L.Location_Name,
                        L.Visibility,
                        L.Allow_POS_Sales,
                        B.Location_ID,
                        B.Parent_Batch_ID,
                        B.Batch_Type,
                        B.PO_ID,
                        B.BR_ID,
                        B.Status,
                        (
                            SELECT COALESCE(SUM(ABS(SML.Qty_Change)), 0)
                            FROM Stock_Movement_Log SML
                            WHERE SML.Batch_ID = B.Batch_ID AND SML.Movement_Type = 'Waste'
                        ) AS Quantity_Wasted,
                        EXISTS(
                            SELECT 1 FROM Stock_Movement_Log SML_W
                            WHERE SML_W.Batch_ID = B.Batch_ID AND SML_W.Movement_Type = 'Waste'
                        ) AS Has_Waste,
                        B.Created_At AS Date_Received,
                        B.Reception_Note
                    FROM
                        Inventory_Batches B
                    INNER JOIN
                        Products_Master P ON B.Product_ID = P.Product_ID
                    LEFT JOIN
                        Product_Families F ON P.Family_ID = F.Family_ID
                    LEFT JOIN
                        Manufacturers M ON P.Manuf_ID = M.Manuf_ID
                    LEFT JOIN
                        Automates A ON P.Preferred_Automate_ID = A.Automate_ID
                    LEFT JOIN
                        Locations L ON B.Location_ID = L.Location_ID

                    -- الربط مع سجل الاستلام لجلب المورد
                    LEFT JOIN
                        Reception_Log RL ON B.BR_ID = RL.BR_ID
                    LEFT JOIN
                        Suppliers S_RL ON RL.Supplier_ID = S_RL.Supplier_ID

                    -- الربط مع أمر الشراء (كخطة بديلة)
                    LEFT JOIN
                        Purchase_Orders PO ON B.PO_ID = PO.PO_ID
                    LEFT JOIN
                        Suppliers S_PO ON PO.Supplier_ID = S_PO.Supplier_ID
                    LEFT JOIN
                        Suppliers S_DIR ON B.Supplier_ID = S_DIR.Supplier_ID

                    {where_str}

                    ORDER BY
                        B.Quantity_Current > 0 DESC,
                        P.Product_Name ASC,
                        B.Expiry_Date ASC;
                """

                cursor.execute(query)
                return cursor.fetchall()

        except Exception as e:
            logging.error(f"Error fetching all batches with details: {e}")
            return []

    def get_product_pricing_info(self):
        """
        جلب معلومات التسعير لكل منتج بناءً على المخزون الحالي.
        يحسب متوسط السعر المرجح (CUMP) للدفعات المتوفرة.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT
                        Product_ID,
                        SUM(Quantity_Current * Unit_Price_Received) / NULLIF(SUM(Quantity_Current), 0) as Avg_Price
                    FROM Inventory_Batches
                    WHERE Quantity_Current > 0
                    GROUP BY Product_ID
                """
                cursor.execute(query)
                return {row['Product_ID']: row['Avg_Price'] for row in cursor.fetchall()}
        except Exception as e:
            logging.error(f"Error calculating product pricing: {e}")
            return {}

    def get_products_stock_levels(self) -> Dict[int, float]:
        """
        جلب إجمالي المخزون المتوفر لكل منتج (مجموع الكميات في الدفعات الحالية).
        Returns: {Product_ID: Total_Quantity}
        """
        stock_map = {}
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                # نجمع الكميات للدفعات التي بها رصيد فقط
                query = """
                    SELECT Product_ID, SUM(Quantity_Current)
                    FROM Inventory_Batches
                    WHERE Quantity_Current > 0
                    GROUP BY Product_ID
                """
                cursor.execute(query)
                results = cursor.fetchall()

                for row in results:
                    # row[0] = Product_ID, row[1] = Sum(Quantity)
                    stock_map[row[0]] = float(row[1])

        except Exception as e:
            logging.error(f"Error fetching stock levels: {e}")

        return stock_map

    def unpack_and_transfer_batch(
        self,
        batch_id: int,
        new_location_id: int,
        qty_to_unpack: int,
        conversion_factor: float,
        target_unit: str = "Unité",
        custom_barcode: Optional[str] = None,
        custom_selling_price_ht: Optional[Decimal] = None,
        source_unit: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Déconditionne une quantité de lot parent (ex: Carton/Boîte) en sous-unités de détail (ex: Pièce/Flacon),
        l'affecte à un emplacement de destination, recalcule le prix unitaire et journalise le mouvement.
        Prend en compte les unités et facteurs définis dans les Données de Base (Produits), tout en permettant
        l'intervention et la personnalisation par l'utilisateur.
        """
        if qty_to_unpack <= 0:
            return False, "La quantité à déconditionner doit être supérieure à 0.", None
        if conversion_factor <= 0:
            return False, "Le facteur de conversion doit être supérieur à 0.", None

        try:
            with self.db.get_db_connection() as conn:
                conn.autocommit = False
                cursor = conn.cursor(dictionary=True)

                try:
                    # 1. Verrouiller et récupérer le lot parent avec toutes les unités du produit et son emplacement
                    cursor.execute("""
                        SELECT b.*, p.Product_Name, p.Barcode AS Product_Barcode, p.Stock_Unit, p.Ordering_Unit,
                               p.Stock_Qty_Per_Order_Unit, p.Usage_Unit, p.Usage_Qty_Per_Stock_Unit,
                               COALESCE(loc_src.Location_Name, CONCAT('Emplacement #', b.Location_ID)) AS Source_Location_Name
                        FROM Inventory_Batches b
                        JOIN Products_Master p ON b.Product_ID = p.Product_ID
                        LEFT JOIN Locations loc_src ON b.Location_ID = loc_src.Location_ID
                        WHERE b.Batch_ID = %s FOR UPDATE
                    """, (batch_id,))

                    source = cursor.fetchone()
                    if not source:
                        conn.rollback()
                        return False, "Lot source introuvable.", None

                    cursor.execute("SELECT Location_Name FROM Locations WHERE Location_ID = %s", (new_location_id,))
                    loc_target_row = cursor.fetchone()
                    target_location_name = (
                        loc_target_row.get('Location_Name') if loc_target_row and loc_target_row.get('Location_Name')
                        else f"Emplacement #{new_location_id}"
                    )

                    curr_stock = float(source.get('Quantity_Current', 0))
                    if curr_stock < qty_to_unpack:
                        conn.rollback()
                        return False, f"Stock insuffisant (Disponible: {curr_stock}, Demandé: {qty_to_unpack}).", None

                    # 2. Calcul des quantités et coûts résultants
                    conv_dec = Decimal(str(conversion_factor))
                    target_qty = int(Decimal(str(qty_to_unpack)) * conv_dec)
                    unit_price_src = Decimal(str(source.get('Unit_Price_Received', 0.0)))
                    target_unit_price = (unit_price_src / conv_dec).quantize(Decimal('0.01'))

                    resolved_source_unit = (
                        source_unit.strip() if source_unit and source_unit.strip()
                        else (source.get('Stock_Unit') or source.get('Ordering_Unit') or 'Boîte')
                    )

                    # 3. Déduire du lot source
                    source_new_qty = Decimal(str(source['Quantity_Current'])) - Decimal(str(qty_to_unpack))
                    source_status = 'Depleted' if source_new_qty <= 0 else source.get('Status', 'Available')
                    cursor.execute("""
                        UPDATE Inventory_Batches
                        SET Quantity_Current = %s,
                            Status = %s
                        WHERE Batch_ID = %s
                    """, (source_new_qty, source_status, batch_id))

                    # 4. Calcul du prix de vente HT de l'unité déconditionnée
                    if custom_selling_price_ht is not None and Decimal(str(custom_selling_price_ht)) > Decimal('0.00'):
                        target_selling_ht = Decimal(str(custom_selling_price_ht)).quantize(Decimal('0.01'))
                    else:
                        selling_ht = Decimal(str(source.get('Selling_Price_HT', 0.0)))
                        target_selling_ht = (selling_ht / conv_dec).quantize(Decimal('0.01')) if selling_ht > 0 else Decimal('0.00')

                    # Insertion du nouveau lot détail : Reception_Note et BR_ID sont explicitement NULL pour NE PAS créer de fausse réclamation
                    insert_query = """
                        INSERT INTO Inventory_Batches
                        (Product_ID, Location_ID, Lot_Number, Expiry_Date,
                         Quantity_Initial, Quantity_Current, Status, Created_At,
                         Unit_Price_Received, Tax_Rate_Percent, Discount_Percent,
                         Selling_Price_HT, Selling_Price_HT_2, Selling_Price_HT_3, Selling_Price_HT_4,
                         Selling_TVA_Percent, Reception_Note, Supplier_ID, External_Barcode, Internal_Barcode, PO_ID, BR_ID,
                         Parent_Batch_ID, Batch_Type)
                        VALUES (%s, %s, %s, %s, %s, %s, 'Available', NOW(), %s, %s, %s, %s, %s, %s, %s, %s, NULL, %s, %s, 'TMP', NULL, NULL, %s, 'Extracted_Retail')
                    """

                    cursor.execute(insert_query, (
                        source['Product_ID'],
                        new_location_id,
                        source['Lot_Number'],
                        source['Expiry_Date'],
                        target_qty,
                        target_qty,
                        target_unit_price,
                        source.get('Tax_Rate_Percent', 0.0),
                        source.get('Discount_Percent', 0.0),
                        target_selling_ht,
                        Decimal('0.00'),
                        Decimal('0.00'),
                        Decimal('0.00'),
                        source.get('Selling_TVA_Percent', 0.0),
                        source.get('Supplier_ID'),
                        source.get('External_Barcode', ''),
                        batch_id,
                    ))
                    new_batch_id = cursor.lastrowid

                    # 5. Définir le code-barres interne (vérification stricte de collision)
                    if custom_barcode and custom_barcode.strip():
                        final_barcode = custom_barcode.strip()
                        is_avail, err_bc = self.is_barcode_available(final_barcode)
                        if not is_avail:
                            conn.rollback()
                            return False, f"Code-barres invalide ou déjà utilisé : {err_bc}", None
                    else:
                        final_barcode = self.generate_unique_barcode()

                    cursor.execute("UPDATE Inventory_Batches SET Internal_Barcode = %s WHERE Batch_ID = %s", (final_barcode, new_batch_id))

                    # 6. Journaliser le mouvement double avec détails complets sur le produit et code-barres source
                    source_barcode = (
                        source.get('Internal_Barcode') or
                        source.get('External_Barcode') or
                        source.get('Product_Barcode') or
                        'Non spécifié'
                    )
                    source_loc_name = source.get('Source_Location_Name') or 'Non spécifié'

                    # A. Sortie du lot parent
                    note_source = (
                        f"Déconditionnement : Sortie de {qty_to_unpack} {resolved_source_unit} "
                        f"du produit '{source['Product_Name']}' (Lot #{source['Lot_Number']}, Code-barres: {source_barcode}) "
                        f"vers {target_location_name} (Nouveau code-barres: {final_barcode}). "
                        f"Ratio: 1 {resolved_source_unit} = {conversion_factor} {target_unit} (+{target_qty} {target_unit})."
                    )
                    self.stock_movement_log.create_movement_log(
                        product_id=source['Product_ID'],
                        movement_type='Transfer',
                        qty_change=Decimal(str(-abs(qty_to_unpack))),
                        unit_used=resolved_source_unit,
                        batch_id=batch_id,
                        user_id=user_id,
                        notes=note_source,
                        external_cursor=cursor
                    )

                    # B. Entrée du lot détail
                    note_target = (
                        f"Déconditionnement : Entrée de +{target_qty} {target_unit} (Nouveau code-barres: {final_barcode}) "
                        f"issu du produit '{source['Product_Name']}' (Lot #{source['Lot_Number']}, "
                        f"Code-barres source: {source_barcode}, Emplacement source: {source_loc_name}). "
                        f"Déduit du parent: -{qty_to_unpack} {resolved_source_unit} vers {target_location_name}. "
                        f"Ratio: 1 {resolved_source_unit} = {conversion_factor} {target_unit}."
                    )
                    self.stock_movement_log.create_movement_log(
                        product_id=source['Product_ID'],
                        movement_type='Transfer',
                        qty_change=Decimal(str(target_qty)),
                        unit_used=target_unit,
                        batch_id=new_batch_id,
                        user_id=user_id,
                        notes=note_target,
                        external_cursor=cursor
                    )

                    conn.commit()
                    return True, None, {
                        'batch_id': new_batch_id,
                        'barcode': final_barcode,
                        'qty': target_qty,
                        'product_name': source['Product_Name'],
                        'lot_number': source['Lot_Number'],
                        'expiry_date': source['Expiry_Date'],
                        'unit': target_unit,
                        'unit_price_received': target_unit_price,
                        'selling_price_ht': target_selling_ht
                    }

                except Exception as inner_e:
                    conn.rollback()
                    logging.error(f"SQL Error in unpack_and_transfer_batch: {inner_e}", exc_info=True)
                    return False, str(inner_e), None
                finally:
                    cursor.close()

        except Exception as e:
            logging.error(f"Critical Error in unpack_and_transfer_batch: {e}", exc_info=True)
            return False, str(e), None

    def extract_retail_batch(
        self,
        parent_batch_id: int,
        extracted_qty: float,
        retail_product_id: Optional[int] = None,
        target_location_id: Optional[int] = None,
        user_id: Optional[int] = None,
        custom_barcode: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extrait une quantité d'un lot parent (vrac / gros) pour créer un sous-lot de détail (Extracted_Retail).
        Garantit l'atomicité de la transaction et journalise le mouvement dans Stock_Movement_Log avec 'BULK_EXTRACTION'.
        """
        if extracted_qty <= 0:
            return {"success": False, "message": "La quantité extraite doit être supérieure à zéro."}

        try:
            with self.db.get_db_connection() as conn:
                conn.autocommit = False
                cursor = conn.cursor(dictionary=True)
                try:
                    # 1. Verrouiller et récupérer le lot parent
                    cursor.execute("""
                        SELECT b.*, p.Product_Name, p.Stock_Unit, p.Usage_Unit
                        FROM Inventory_Batches b
                        JOIN Products_Master p ON b.Product_ID = p.Product_ID
                        WHERE b.Batch_ID = %s FOR UPDATE
                    """, (parent_batch_id,))
                    parent = cursor.fetchone()
                    if not parent:
                        conn.rollback()
                        return {"success": False, "message": f"Lot parent #{parent_batch_id} introuvable."}

                    parent_stock = float(parent.get('Quantity_Current') or 0.0)
                    if parent_stock < extracted_qty:
                        conn.rollback()
                        return {
                            "success": False,
                            "message": f"Stock parent insuffisant (Disponible: {parent_stock}, Demandé: {extracted_qty})."
                        }

                    # Résolution des cibles
                    resolved_product_id = retail_product_id if retail_product_id is not None else parent['Product_ID']
                    resolved_location_id = target_location_id if target_location_id is not None else parent['Location_ID']

                    # 2. Déduction du stock parent
                    new_parent_qty = Decimal(str(parent['Quantity_Current'])) - Decimal(str(extracted_qty))
                    new_parent_status = 'Depleted' if new_parent_qty <= 0 else parent.get('Status', 'Available')
                    cursor.execute("""
                        UPDATE Inventory_Batches
                        SET Quantity_Current = %s, Status = %s
                        WHERE Batch_ID = %s
                    """, (new_parent_qty, new_parent_status, parent_batch_id))

                    # 3. Code-barres pour le lot extrait
                    if custom_barcode and custom_barcode.strip():
                        child_barcode = custom_barcode.strip()
                    else:
                        child_barcode = self.generate_unique_barcode()

                    # 4. Insertion du nouveau lot enfant
                    insert_query = """
                        INSERT INTO Inventory_Batches
                        (Parent_Batch_ID, Batch_Type, Product_ID, Location_ID, Lot_Number, Expiry_Date,
                         Quantity_Initial, Quantity_Current, Status, Created_At,
                         Unit_Price_Received, Tax_Rate_Percent, Discount_Percent,
                         Selling_Price_HT, Selling_Price_HT_2, Selling_Price_HT_3, Selling_Price_HT_4,
                         Selling_TVA_Percent, Reception_Note, Supplier_ID, External_Barcode, Internal_Barcode)
                        VALUES (%s, 'Extracted_Retail', %s, %s, %s, %s, %s, %s, 'Available', NOW(),
                                %s, %s, %s, %s, %s, %s, %s, %s, NULL, %s, %s, %s)
                    """
                    cursor.execute(insert_query, (
                        parent_batch_id,
                        resolved_product_id,
                        resolved_location_id,
                        parent.get('Lot_Number') or '',
                        parent.get('Expiry_Date'),
                        Decimal(str(extracted_qty)),
                        Decimal(str(extracted_qty)),
                        parent.get('Unit_Price_Received', 0.0),
                        parent.get('Tax_Rate_Percent', 0.0),
                        parent.get('Discount_Percent', 0.0),
                        parent.get('Selling_Price_HT', 0.0),
                        parent.get('Selling_Price_HT_2', 0.0),
                        parent.get('Selling_Price_HT_3', 0.0),
                        parent.get('Selling_Price_HT_4', 0.0),
                        parent.get('Selling_TVA_Percent', 0.0),
                        parent.get('Supplier_ID'),
                        parent.get('External_Barcode', ''),
                        child_barcode
                    ))
                    child_batch_id = cursor.lastrowid

                    # 5. Journalisation des mouvements dans Stock_Movement_Log
                    unit_used = parent.get('Usage_Unit') or parent.get('Stock_Unit') or 'Unité'
                    note_parent = f"Extraction détail vers lot #{child_batch_id} (Quantité: {extracted_qty})"
                    note_child = f"Extrait du lot parent #{parent_batch_id} (Quantité: {extracted_qty})"

                    try:
                        self.stock_movement_log.create_movement_log(
                            product_id=parent['Product_ID'],
                            movement_type='BULK_EXTRACTION',
                            qty_change=Decimal(str(-abs(extracted_qty))),
                            unit_used=unit_used,
                            batch_id=parent_batch_id,
                            user_id=user_id,
                            notes=note_parent,
                            external_cursor=cursor
                        )
                        self.stock_movement_log.create_movement_log(
                            product_id=resolved_product_id,
                            movement_type='BULK_EXTRACTION',
                            qty_change=Decimal(str(extracted_qty)),
                            unit_used=unit_used,
                            batch_id=child_batch_id,
                            user_id=user_id,
                            notes=note_child,
                            external_cursor=cursor
                        )
                    except Exception as log_err:
                        logging.warning(f"BULK_EXTRACTION movement log fallback to Transfer: {log_err}")
                        self.stock_movement_log.create_movement_log(
                            product_id=parent['Product_ID'],
                            movement_type='Transfer',
                            qty_change=Decimal(str(-abs(extracted_qty))),
                            unit_used=unit_used,
                            batch_id=parent_batch_id,
                            user_id=user_id,
                            notes=f"[BULK_EXTRACTION] {note_parent}",
                            external_cursor=cursor
                        )
                        self.stock_movement_log.create_movement_log(
                            product_id=resolved_product_id,
                            movement_type='Transfer',
                            qty_change=Decimal(str(extracted_qty)),
                            unit_used=unit_used,
                            batch_id=child_batch_id,
                            user_id=user_id,
                            notes=f"[BULK_EXTRACTION] {note_child}",
                            external_cursor=cursor
                        )

                    conn.commit()
                    return {
                        "success": True,
                        "parent_batch_id": parent_batch_id,
                        "child_batch_id": child_batch_id,
                        "barcode": child_barcode,
                        "extracted_qty": float(extracted_qty),
                        "parent_remaining_qty": float(new_parent_qty),
                        "retail_product_id": resolved_product_id,
                        "target_location_id": resolved_location_id
                    }

                except Exception as inner_e:
                    conn.rollback()
                    logging.error(f"Error in extract_retail_batch: {inner_e}", exc_info=True)
                    return {"success": False, "message": str(inner_e)}
                finally:
                    cursor.close()
        except Exception as e:
            logging.error(f"Database error in extract_retail_batch: {e}", exc_info=True)
            return {"success": False, "message": str(e)}

    def update_batch_sales_prices(
        self,
        batch_id: int,
        new_prices: dict,
        update_all_product_batches: bool = False,
        reason: str = "",
        user_id: Optional[int] = None
    ) -> Tuple[bool, Optional[str], int]:
        """
        Met à jour les prix de vente d'un lot et optionnellement de tous les lots actifs du même produit.
        Enregistre chaque variation de prix dans la table d'audit Price_Change_Log.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                try:
                    # 1. Récupérer le lot cible
                    cursor.execute("""
                        SELECT b.*, p.Product_Name
                        FROM Inventory_Batches b
                        JOIN Products_Master p ON b.Product_ID = p.Product_ID
                        WHERE b.Batch_ID = %s FOR UPDATE
                    """, (batch_id,))
                    batch = cursor.fetchone()
                    if not batch:
                        conn.rollback()
                        return False, "Lot introuvable.", 0

                    product_id = batch['Product_ID']
                    lot_number = batch['Lot_Number']

                    # 2. Identifier les lots à modifier
                    if update_all_product_batches:
                        cursor.execute("""
                            SELECT Batch_ID, Lot_Number,
                                   Selling_Price_HT, Selling_Price_HT_2, Selling_Price_HT_3, Selling_Price_HT_4, Selling_TVA_Percent
                            FROM Inventory_Batches
                            WHERE Product_ID = %s AND Status != 'Depleted'
                            FOR UPDATE
                        """, (product_id,))
                        target_batches = cursor.fetchall()
                    else:
                        target_batches = [batch]

                    price_keys = [
                        ('Selling_Price_HT', 'Prix Vente 1'),
                        ('Selling_Price_HT_2', 'Prix Vente 2'),
                        ('Selling_Price_HT_3', 'Prix Vente 3'),
                        ('Selling_Price_HT_4', 'Prix Vente 4'),
                        ('Selling_TVA_Percent', 'TVA Vente %')
                    ]

                    for tb in target_batches:
                        tb_id = tb['Batch_ID']
                        tb_lot = tb.get('Lot_Number') or lot_number

                        # Vérifier chaque prix et enregistrer l'historique si changement
                        for key, label in price_keys:
                            if key in new_prices and new_prices[key] is not None:
                                old_val = Decimal(str(tb.get(key) or 0.0)).quantize(Decimal('0.01'))
                                new_val = Decimal(str(new_prices[key])).quantize(Decimal('0.01'))

                                if old_val != new_val:
                                    cursor.execute("""
                                        INSERT INTO Price_Change_Log
                                        (Product_ID, Batch_ID, Lot_Number, Price_Type, Old_Price, New_Price, Reason, Changed_By_User_ID, Changed_At)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                                    """, (
                                        product_id, tb_id, tb_lot, label, old_val, new_val,
                                        reason.strip() if reason else "Ajustement tarifaire",
                                        user_id
                                    ))

                        # Mettre à jour le lot
                        cursor.execute("""
                            UPDATE Inventory_Batches
                            SET Selling_Price_HT = %s,
                                Selling_Price_HT_2 = %s,
                                Selling_Price_HT_3 = %s,
                                Selling_Price_HT_4 = %s,
                                Selling_TVA_Percent = %s
                            WHERE Batch_ID = %s
                        """, (
                            Decimal(str(new_prices.get('Selling_Price_HT', tb.get('Selling_Price_HT', 0.0)))),
                            Decimal(str(new_prices.get('Selling_Price_HT_2', tb.get('Selling_Price_HT_2', 0.0)))),
                            Decimal(str(new_prices.get('Selling_Price_HT_3', tb.get('Selling_Price_HT_3', 0.0)))),
                            Decimal(str(new_prices.get('Selling_Price_HT_4', tb.get('Selling_Price_HT_4', 0.0)))),
                            Decimal(str(new_prices.get('Selling_TVA_Percent', tb.get('Selling_TVA_Percent', 0.0)))),
                            tb_id
                        ))

                    # 3. Si mise à jour globale, synchroniser également Products_Master
                    if update_all_product_batches:
                        cursor.execute("""
                            UPDATE Products_Master
                            SET Default_Selling_Price_HT = %s,
                                Selling_Price_HT_2 = %s,
                                Selling_Price_HT_3 = %s,
                                Selling_Price_HT_4 = %s
                            WHERE Product_ID = %s
                        """, (
                            Decimal(str(new_prices.get('Selling_Price_HT', 0.0))),
                            Decimal(str(new_prices.get('Selling_Price_HT_2', 0.0))),
                            Decimal(str(new_prices.get('Selling_Price_HT_3', 0.0))),
                            Decimal(str(new_prices.get('Selling_Price_HT_4', 0.0))),
                            product_id
                        ))

                    conn.commit()
                    return True, None, len(target_batches)

                except Exception as inner_e:
                    conn.rollback()
                    logging.error(f"SQL Error in update_batch_sales_prices: {inner_e}", exc_info=True)
                    return False, str(inner_e), 0
                finally:
                    cursor.close()

        except Exception as e:
            logging.error(f"Critical Error in update_batch_sales_prices: {e}", exc_info=True)
            return False, str(e), 0

    def get_price_change_history(
        self,
        product_id: Optional[int] = None,
        batch_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Récupère l'historique d'audit des modifications de prix de vente.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT pcl.*, p.Product_Name,
                           COALESCE(u.Full_Name, u.Username, 'Système') AS Changed_By_Name
                    FROM Price_Change_Log pcl
                    JOIN Products_Master p ON pcl.Product_ID = p.Product_ID
                    LEFT JOIN Users u ON pcl.Changed_By_User_ID = u.User_ID
                    WHERE 1=1
                """
                params = []
                if batch_id:
                    query += " AND (pcl.Batch_ID = %s OR pcl.Product_ID = (SELECT Product_ID FROM Inventory_Batches WHERE Batch_ID = %s LIMIT 1))"
                    params.extend([batch_id, batch_id])
                elif product_id:
                    query += " AND pcl.Product_ID = %s"
                    params.append(product_id)

                query += " ORDER BY pcl.Changed_At DESC, pcl.Log_ID DESC LIMIT %s"
                params.append(limit)

                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
                cursor.close()
                return rows
        except Exception as e:
            logging.error(f"Error fetching price change history: {e}", exc_info=True)
            return []

    def update_batch_external_barcode(self, batch_id: int, external_barcode: str) -> Tuple[bool, str]:
        """Met à jour le code-barres externe d'un lot d'inventaire."""
        external_barcode = str(external_barcode or "").strip()
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE Inventory_Batches SET External_Barcode = %s WHERE Batch_ID = %s",
                    (external_barcode if external_barcode else None, batch_id)
                )
                conn.commit()
                logging.info(f"Lot {batch_id}: Code-barres externe mis à jour: '{external_barcode}'")
                return True, external_barcode
        except Exception as e:
            logging.error(f"Erreur update_batch_external_barcode: {e}", exc_info=True)
            return False, str(e)



