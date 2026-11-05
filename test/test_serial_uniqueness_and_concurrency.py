# -*- coding: utf-8 -*-
"""
test/test_serial_uniqueness_and_concurrency.py
==============================================
Automated Test Suite for:
1. Product & Batch Management (Mark, Name, Categorie, Coloure, Extensible Attributes, Batches).
2. Global Composite Uniqueness & Sanitization of Serial Numbers (N° de Série).
3. Theoretical Sale vs. Physical Assignment Separation (Order Desk vs. Dispatch Desk).
4. Multi-Desk Concurrency & Pessimistic Locking (`StateCollisionException` when two Dispatch
   clerks attempt to scan the same physical N° de Série simultaneously).
"""

import os
import sys
import threading
from decimal import Decimal
import mysql.connector
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.serial_tracking_manager import SerialTrackingManager
from database.bond_lifecycle_manager import (
    BondLifecycleManager,
    StateCollisionException,
)


class StatefulMockDB:
    """
    Thread-safe in-memory database backing SerialTrackingManager and BondLifecycleManager
    to verify SQL transaction atomicity, row locking (`FOR UPDATE`), and uniqueness constraints.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self.products = {}
        self.batches = {}
        self.serials_by_id = {}
        self.serials_by_sn = {}
        self.composite_keys = {}
        self.serial_history = []
        self.orders = {}
        self.order_lines = {}
        self.invoices = {100: {"Invoice_ID": 100, "Amount_Remaining_Credit": Decimal("0.00")}}
        self.exit_bonds = {}
        self.exit_serials = []
        self.stock_movement_logs = []
        self._next_id = 1

    def alloc_id(self) -> int:
        val = self._next_id
        self._next_id += 1
        return val

    def get_raw_connection(self):
        return StatefulMockConnection(self)


class StatefulMockConnection:
    def __init__(self, db: StatefulMockDB):
        self.db = db
        self._locked = False

    def start_transaction(self):
        if not self._locked:
            self.db._lock.acquire()
            self._locked = True

    def cursor(self, dictionary: bool = True):
        return StatefulMockCursor(self.db)

    def commit(self):
        if self._locked:
            self.db._lock.release()
            self._locked = False

    def rollback(self):
        if self._locked:
            self.db._lock.release()
            self._locked = False

    def close(self):
        if self._locked:
            self.db._lock.release()
            self._locked = False


class StatefulMockCursor:
    def __init__(self, db: StatefulMockDB):
        self.db = db
        self.lastrowid = None
        self.rowcount = 0
        self._rows = []

    def execute(self, query: str, params=None):
        q = " ".join(query.strip().split())
        q_upper = q.upper()
        p = tuple(params or ())

        # 1. Insert Products_Master
        if q_upper.startswith("INSERT INTO PRODUCTS_MASTER"):
            pid = self.db.alloc_id()
            self.db.products[pid] = {
                "Product_ID": pid,
                "Product_Name": p[0],
                "Family_ID": p[1],
                "Manuf_ID": p[2],
                "Barcode": p[3],
                "Brand_Mark": p[4],
                "Category_Name": p[5],
                "Color_Finish": p[6],
                "Requires_Serial_Tracking": p[7],
                "Warranty_Months": p[8],
                "Default_Selling_Price_HT": p[9],
                "Selling_TVA_Percent": p[10],
                "Extensible_Attributes": p[11],
            }
            self.lastrowid = pid
            self.rowcount = 1
            return

        # 2. Insert Inventory_Batches
        if q_upper.startswith("INSERT INTO INVENTORY_BATCHES"):
            bid = self.db.alloc_id()
            self.db.batches[bid] = {
                "Batch_ID": bid,
                "Internal_Barcode": p[0],
                "Product_ID": int(p[1]),
                "Location_ID": int(p[2]),
                "Supplier_ID": p[3],
                "PO_ID": p[4],
                "Lot_Number": p[5],
                "Quantity_Initial": int(p[6]),
                "Quantity_Current": int(p[7]),
                "Theoretical_Reserved_Qty": 0,
                "Unit_Price_Received": p[8],
                "Freight_Customs_Allocation": p[9],
                "Tax_Rate_Percent": p[10],
                "Selling_Price_HT": p[11],
                "Selling_TVA_Percent": p[12],
                "Status": "Available",
                "Created_At": p[13],
            }
            self.lastrowid = bid
            self.rowcount = 1
            return

        # 3. Insert Product_Serials
        if q_upper.startswith("INSERT INTO PRODUCT_SERIALS"):
            prod_id, batch_id, sn, comp, loc_id = int(p[0]), int(p[1]), p[2], p[3], int(p[4])
            if comp in self.db.composite_keys or sn in self.db.serials_by_sn:
                raise mysql.connector.IntegrityError(
                    msg=f"Duplicate entry '{comp}' for key 'uk_serial_composite'",
                    errno=1062,
                )
            sid = self.db.alloc_id()
            rec = {
                "Serial_ID": sid,
                "Product_ID": prod_id,
                "Batch_ID": batch_id,
                "Serial_Number": sn,
                "Barcode_Serial_Composite": comp,
                "Status": "IN_STOCK",
                "Current_Location_ID": loc_id,
                "Original_Sales_Invoice_ID": None,
            }
            self.db.serials_by_id[sid] = rec
            self.db.serials_by_sn[sn] = rec
            self.db.composite_keys[comp] = sid
            self.lastrowid = sid
            self.rowcount = 1
            return

        # 4. Insert Product_Serial_History
        if q_upper.startswith("INSERT INTO PRODUCT_SERIAL_HISTORY"):
            hid = self.db.alloc_id()
            self.db.serial_history.append(p)
            self.lastrowid = hid
            self.rowcount = 1
            return

        # 5. Insert Sales_Orders_Theoretical
        if q_upper.startswith("INSERT INTO SALES_ORDERS_THEORETICAL"):
            oid = self.db.alloc_id()
            self.db.orders[oid] = {
                "Order_ID": oid,
                "Order_Number": p[0],
                "Client_ID": int(p[1]),
                "Order_Desk_User_ID": int(p[2]),
                "Scanner_Session_ID": p[3],
                "Bond_Type": p[4],
                "Total_Amount_HT": p[5],
                "Total_Amount_TTC": p[6],
                "Status": "CONFIRMED_PENDING_PAYMENT",
                "Payment_Method_Requested": p[7],
            }
            self.lastrowid = oid
            self.rowcount = 1
            return

        # 6. Select active batches FOR UPDATE during theoretical order
        if "SELECT BATCH_ID, QUANTITY_CURRENT" in q_upper and "FROM INVENTORY_BATCHES" in q_upper:
            prod_id = int(p[0])
            rows = [
                b.copy()
                for b in sorted(self.db.batches.values(), key=lambda x: x["Batch_ID"])
                if b["Product_ID"] == prod_id and b["Status"] in ("Available", "ACTIVE")
            ]
            self._rows = rows
            return

        # 7. Increment Theoretical_Reserved_Qty on batch
        if "SET THEORETICAL_RESERVED_QTY = COALESCE(THEORETICAL_RESERVED_QTY, 0) +" in q_upper:
            alloc, bid = int(p[0]), int(p[1])
            self.db.batches[bid]["Theoretical_Reserved_Qty"] += alloc
            self.rowcount = 1
            return

        # 8. Insert Sales_Order_Lines_Theoretical
        if q_upper.startswith("INSERT INTO SALES_ORDER_LINES_THEORETICAL"):
            lid = self.db.alloc_id()
            self.db.order_lines[lid] = {
                "Line_ID": lid,
                "Order_ID": int(p[0]),
                "Product_ID": int(p[1]),
                "Requested_Color": p[2],
                "Quantity_Ordered": int(p[3]),
                "Quantity_Dispatched": 0,
                "Unit_Price_HT": p[4],
                "Tax_Rate": p[5],
                "Unit_Price_TTC": p[6],
                "Line_Total_TTC": p[7],
            }
            self.lastrowid = lid
            self.rowcount = 1
            return

        # 9. Dispatch: Insert Delivery_Exit_Bonds
        if q_upper.startswith("INSERT INTO DELIVERY_EXIT_BONDS"):
            ebid = self.db.alloc_id()
            self.db.exit_bonds[ebid] = {
                "Exit_Bond_ID": ebid,
                "Exit_Bond_Number": p[0],
                "Order_ID": int(p[1]),
                "Invoice_ID": int(p[2]),
                "Storekeeper_User_ID": int(p[3]),
                "Security_Gate_Pass_Barcode": p[4],
                "Exit_Status": "VALIDATED_EXIT",
            }
            self.lastrowid = ebid
            self.rowcount = 1
            return

        # 10. Dispatch: Select Sales_Order_Lines_Theoretical FOR UPDATE
        if "FROM SALES_ORDER_LINES_THEORETICAL WHERE LINE_ID = %S FOR UPDATE" in q_upper:
            lid = int(p[0])
            line = self.db.order_lines.get(lid)
            self._rows = [line.copy()] if line else []
            return

        # 11. Dispatch: Select Product_Serials FOR UPDATE
        if "FROM PRODUCT_SERIALS WHERE SERIAL_NUMBER = %S FOR UPDATE" in q_upper:
            sn = p[0]
            s = self.db.serials_by_sn.get(sn)
            self._rows = [s.copy()] if s else []
            return

        # 12. Dispatch: Insert Delivery_Exit_Serials
        if q_upper.startswith("INSERT INTO DELIVERY_EXIT_SERIALS"):
            self.db.exit_serials.append(p)
            self.lastrowid = self.db.alloc_id()
            self.rowcount = 1
            return

        # 13. Dispatch: Update Product_Serials Status = 'DISPATCHED'
        if q_upper.startswith("UPDATE PRODUCT_SERIALS SET STATUS = 'DISPATCHED'"):
            inv_id, sid = int(p[0]), int(p[1])
            s = self.db.serials_by_id[sid]
            s["Status"] = "DISPATCHED"
            s["Original_Sales_Invoice_ID"] = inv_id
            self.rowcount = 1
            return

        # 14. Dispatch: Decrement Batch Quantity_Current & Theoretical_Reserved_Qty
        if "SET QUANTITY_CURRENT = GREATEST(0, QUANTITY_CURRENT - 1)" in q_upper:
            bid = int(p[0])
            b = self.db.batches[bid]
            b["Quantity_Current"] = max(0, b["Quantity_Current"] - 1)
            b["Theoretical_Reserved_Qty"] = max(0, b["Theoretical_Reserved_Qty"] - 1)
            self.rowcount = 1
            return

        # 15. Dispatch: Increment Quantity_Dispatched on Sales_Order_Lines_Theoretical
        if "SET QUANTITY_DISPATCHED = QUANTITY_DISPATCHED + 1" in q_upper:
            lid = int(p[0])
            self.db.order_lines[lid]["Quantity_Dispatched"] += 1
            self.rowcount = 1
            return

        # 16. Dispatch: Select from Sales_Orders_Theoretical
        if "FROM SALES_ORDERS_THEORETICAL WHERE ORDER_ID = %S" in q_upper:
            oid = int(p[0])
            ord_row = self.db.orders.get(oid)
            self._rows = [ord_row.copy()] if ord_row else []
            return

        # 16b. Total Stock Query for Stock_Movement_Log
        if "SELECT SUM(QUANTITY_CURRENT) AS TOTAL_STOCK FROM INVENTORY_BATCHES WHERE PRODUCT_ID = %S" in q_upper:
            pid = int(p[0])
            tot = sum(
                int(b["Quantity_Current"])
                for b in self.db.batches.values()
                if b["Product_ID"] == pid and b["Status"] in ("Available", "ACTIVE")
            )
            self._rows = [{"Total_Stock": tot}]
            return

        # 16c. Product Summary Query
        if "FROM PRODUCTS_MASTER P" in q_upper and "WHERE P.PRODUCT_ID = %S" in q_upper:
            pid = int(p[0])
            p_rec = self.db.products.get(pid)
            if not p_rec:
                self._rows = []
                return
            phys = sum(
                int(b["Quantity_Current"])
                for b in self.db.batches.values()
                if b["Product_ID"] == pid and b["Status"] in ("Available", "ACTIVE")
            )
            res = sum(
                int(b.get("Theoretical_Reserved_Qty") or 0)
                for b in self.db.batches.values()
                if b["Product_ID"] == pid and b["Status"] in ("Available", "ACTIVE")
            )
            serials_cnt = sum(
                1
                for s in self.db.serials_by_id.values()
                if s["Product_ID"] == pid and s["Status"] == "IN_STOCK"
            )
            row = {
                "Product_ID": pid,
                "Product_Name": p_rec.get("Product_Name", ""),
                "Brand_Mark": p_rec.get("Brand_Mark", ""),
                "Category_Name": p_rec.get("Category_Name", ""),
                "Color_Finish": p_rec.get("Color_Finish", ""),
                "Requires_Serial_Tracking": p_rec.get("Requires_Serial_Tracking", True),
                "Physical_Qty": phys,
                "Theoretical_Reserved_Qty": res,
                "Serials_In_Stock": serials_cnt,
            }
            self._rows = [row]
            return

        # 16d. Insert Stock_Movement_Log
        if q_upper.startswith("INSERT INTO STOCK_MOVEMENT_LOG"):
            mid = self.db.alloc_id()
            self.db.stock_movement_logs.append({
                "Movement_ID": mid,
                "Product_ID": int(p[0]),
                "Batch_ID": int(p[1]) if p[1] else None,
                "Movement_Type": str(p[2]),
                "Qty_Change": p[3],
                "Unit_Used": str(p[4]),
                "Notes": str(p[5]),
                "User_ID": int(p[6]) if p[6] else 1,
                "Stock_After": p[7],
            })
            self.lastrowid = mid
            self.rowcount = 1
            return

        # 17. Dispatch: Update Sales_Orders_Theoretical Status
        if q_upper.startswith("UPDATE SALES_ORDERS_THEORETICAL SET STATUS = %S WHERE ORDER_ID = %S"):
            st, oid = p[0], int(p[1])
            self.db.orders[oid]["Status"] = st
            self.rowcount = 1
            return

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def close(self):
        pass


def test_serial_sanitization_and_global_composite_uniqueness():
    """
    Verifies:
    1. Product creation with Mark, Name, Categorie, Coloure, and extensible JSON attributes.
    2. Batch arrival with distinct date, cost, and unique serial numbers (N° de Série).
    3. Sanitization of whitespace/newlines/lowercase and composite barcode key `<Product_ID>::<UPPER_SERIAL>`.
    4. Immediate `IntegrityError` (errno 1062) on duplicate serials within the same batch or across batches.
    """
    db = StatefulMockDB()
    serial_mgr = SerialTrackingManager(db)

    prod_res = serial_mgr.register_product_with_attributes(
        name="Réfrigérateur NoFrost 520L",
        mark="Samsung",
        categorie="Réfrigérateurs",
        coloure="Inox",
        barcode="8806090001112",
        selling_price_ht=Decimal("120000.00"),
        warranty_months=24,
        requires_serial=True,
        extra_attributes={"energy_class": "A+++", "inverter": True},
    )
    assert prod_res["success"] is True
    product_id = prod_res["product_id"]

    # Receive Batch 1 with 3 serials (testing sanitization of lowercase & control chars)
    batch1 = serial_mgr.register_batch_arrival(
        product_id=product_id,
        supplier_id=1,
        po_id=None,
        reception_date="2026-11-04",
        unit_cost_ht=Decimal("95000.00"),
        freight_customs=Decimal("2000.00"),
        serial_numbers=["  sn-sam-001\r\n", "SN-SAM-002", "sn-sam-003\t"],
        user_id=1,
        batch_number="LOT-2026-01",
    )
    assert batch1["success"] is True
    assert batch1["serials_count"] == 3
    assert batch1["landed_cost_ht"] == 97000.0
    assert f"{product_id}::SN-SAM-001" in db.composite_keys
    assert "SN-SAM-001" in db.serials_by_sn

    # Intra-batch duplicate serials must raise IntegrityError (errno 1062)
    with pytest.raises(mysql.connector.IntegrityError) as exc_info:
        serial_mgr.register_batch_arrival(
            product_id=product_id,
            supplier_id=1,
            po_id=None,
            reception_date="2026-11-05",
            unit_cost_ht=Decimal("96000.00"),
            freight_customs=Decimal("0.00"),
            serial_numbers=["SN-SAM-010", "sn-sam-010"],
            user_id=1,
        )
    assert exc_info.value.errno == 1062

    # Inter-batch duplicate serials ("SN-SAM-002" already in Batch 1) must raise IntegrityError
    with pytest.raises(mysql.connector.IntegrityError) as exc_info2:
        serial_mgr.register_batch_arrival(
            product_id=product_id,
            supplier_id=1,
            po_id=None,
            reception_date="2026-11-06",
            unit_cost_ht=Decimal("98000.00"),
            freight_customs=Decimal("0.00"),
            serial_numbers=["SN-SAM-002"],
            user_id=1,
        )
    assert exc_info2.value.errno == 1062


def test_theoretical_sale_vs_physical_serial_assignment_and_concurrency():
    """
    Verifies:
    1. Order Desk records theoretical order (`create_sales_order_draft`) reserving `Theoretical_Reserved_Qty`
       without locking any physical serial number (`Status` remains `IN_STOCK`).
    2. Dispatch Desk (`validate_and_dispatch_serials`) scans the physical serial (`N° de Série`),
       emits `Bon de Sortie` with `financial_impact == 'NONE'`, transitions serial to `DISPATCHED`,
       and decrements physical & theoretical batch stock.
    3. Multi-Desk Concurrency: When two Dispatch clerks simultaneously scan the SAME physical serial
       (`SN-LG-777`) for two separate orders, exactly ONE succeeds and ONE raises `StateCollisionException`.
    """
    db = StatefulMockDB()
    serial_mgr = SerialTrackingManager(db)
    bond_mgr = BondLifecycleManager(db)

    prod_res = serial_mgr.register_product_with_attributes(
        name="Climatiseur Dual Inverter 18000 BTU",
        mark="LG",
        categorie="Climatisation",
        coloure="Blanc",
        barcode="8801112223334",
        selling_price_ht=Decimal("82000.00"),
    )
    product_id = prod_res["product_id"]

    batch_res = serial_mgr.register_batch_arrival(
        product_id=product_id,
        supplier_id=1,
        po_id=None,
        reception_date="2026-11-04",
        unit_cost_ht=Decimal("68000.00"),
        freight_customs=Decimal("1000.00"),
        serial_numbers=["SN-LG-777", "SN-LG-778"],
        user_id=1,
        batch_number="LOT-LG-AC",
    )
    batch_id = batch_res["batch_id"]

    # Create two theoretical orders at Order Desk
    ord_a = bond_mgr.create_sales_order_draft(
        client_id=1,
        order_desk_user_id=2,
        items=[{"product_id": product_id, "quantity": 1, "unit_price_ttc": "98000.00", "coloure": "Blanc"}],
        bond_type="BON_C",
        scanner_session_id="SESSION_1",
    )
    ord_b = bond_mgr.create_sales_order_draft(
        client_id=2,
        order_desk_user_id=2,
        items=[{"product_id": product_id, "quantity": 1, "unit_price_ttc": "98000.00", "coloure": "Blanc"}],
        bond_type="BON_C",
        scanner_session_id="SESSION_2",
    )

    # Verify theoretical reservation vs physical stock before dispatch
    assert db.batches[batch_id]["Quantity_Current"] == 2
    assert db.batches[batch_id]["Theoretical_Reserved_Qty"] == 2
    assert db.serials_by_sn["SN-LG-777"]["Status"] == "IN_STOCK"
    assert db.serials_by_sn["SN-LG-778"]["Status"] == "IN_STOCK"

    line_a_id = [l["Line_ID"] for l in db.order_lines.values() if l["Order_ID"] == ord_a["order_id"]][0]
    line_b_id = [l["Line_ID"] for l in db.order_lines.values() if l["Order_ID"] == ord_b["order_id"]][0]

    # Simulate two Dispatch Desk threads scanning the SAME physical serial "SN-LG-777"
    barrier = threading.Barrier(2)
    successes = []
    collisions = []

    def dispatch_worker(order_id: int, line_id: int, clerk_id: int):
        barrier.wait()
        try:
            res = bond_mgr.validate_and_dispatch_serials(
                order_id=order_id,
                invoice_id=100,
                storekeeper_user_id=clerk_id,
                scanned_serial_numbers=[{"order_line_id": line_id, "serial_number": "SN-LG-777"}],
            )
            successes.append((order_id, res))
        except StateCollisionException as exc:
            collisions.append((order_id, line_id, exc))

    t1 = threading.Thread(target=dispatch_worker, args=(ord_a["order_id"], line_a_id, 301))
    t2 = threading.Thread(target=dispatch_worker, args=(ord_b["order_id"], line_b_id, 302))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Exactly ONE thread succeeds and ONE raises StateCollisionException
    assert len(successes) == 1
    assert len(collisions) == 1

    _, win_res = successes[0]
    assert win_res["success"] is True
    assert win_res["financial_impact"] == "NONE"
    assert win_res["exit_bond_number"].startswith("BS-")
    assert db.serials_by_sn["SN-LG-777"]["Status"] == "DISPATCHED"
    assert db.batches[batch_id]["Quantity_Current"] == 1
    assert db.batches[batch_id]["Theoretical_Reserved_Qty"] == 1

    # Second clerk scans the second physical unit "SN-LG-778" and completes Order B
    loser_order_id, loser_line_id, _ = collisions[0]
    res2 = bond_mgr.validate_and_dispatch_serials(
        order_id=loser_order_id,
        invoice_id=100,
        storekeeper_user_id=302,
        scanned_serial_numbers=[{"order_line_id": loser_line_id, "serial_number": "SN-LG-778"}],
    )
    assert res2["success"] is True
    assert db.serials_by_sn["SN-LG-778"]["Status"] == "DISPATCHED"
    assert db.batches[batch_id]["Quantity_Current"] == 0
    assert db.batches[batch_id]["Theoretical_Reserved_Qty"] == 0
