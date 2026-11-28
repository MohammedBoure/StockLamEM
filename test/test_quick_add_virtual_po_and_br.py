# -*- coding: utf-8 -*-
"""
Unit tests for Ajouter Rapide -> Virtual Reference PO per Supplier +
Auto-merged/created Bon de Réception (Reception_Log) + PO-based Smart Barcodes +
Protected initial values on Stock Actuel direct edit.
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from database.inventory_batch_manager import InventoryBatchManager


class FakeQuickAddCursor:
    """In-memory mock cursor simulating Purchase_Orders, Reception_Log, and Inventory_Batches."""

    def __init__(self):
        self.purchase_orders = {}  # po_id -> dict
        self.receptions = {}       # br_id -> dict
        self.batches = {}          # batch_id -> dict
        self.next_br_id = 1
        self.next_batch_id = 1
        self.lastrowid = None
        self._last_result = []
        self.executed = []

    def execute(self, sql, params=None):
        sql_clean = " ".join(sql.split())
        self.executed.append((sql_clean, params))
        self._last_result = []

        if sql_clean.startswith("SELECT PO_ID FROM Purchase_Orders WHERE Supplier_ID = %s"):
            sid = params[0]
            matches = [
                po_id for po_id, po in self.purchase_orders.items()
                if po["Supplier_ID"] == sid and "[QUICK_ADD_REF]" in po["Notes"]
            ]
            if matches:
                self._last_result = [(max(matches),)]

        elif sql_clean.startswith("SELECT MAX(PO_ID) FROM Purchase_Orders"):
            prefix = params[0].rstrip("%")
            matches = [po_id for po_id in self.purchase_orders if str(po_id).startswith(prefix)]
            self._last_result = [(max(matches) if matches else None,)]

        elif sql_clean.startswith("INSERT INTO Purchase_Orders"):
            po_id, sid, notes, created_by = params
            self.purchase_orders[po_id] = {
                "PO_ID": po_id,
                "Supplier_ID": sid,
                "Notes": notes,
                "Created_By": created_by,
                "Total_Amount_HT": 0.0,
                "Total_Tax_Amount": 0.0,
                "Total_Amount_TTC": 0.0,
            }
            self.lastrowid = po_id

        elif sql_clean.startswith("SELECT BR_ID FROM Reception_Log WHERE Supplier_ID = %s AND Supplier_BL_Ref = %s"):
            sid, bl = params
            matches = [
                br_id for br_id, br in self.receptions.items()
                if br["Supplier_ID"] == sid and br["Supplier_BL_Ref"] == bl
            ]
            if matches:
                self._last_result = [(max(matches),)]

        elif "FROM Reception_Log WHERE Supplier_ID = %s AND PO_ID = %s" in sql_clean:
            sid, po_id = params
            today = datetime.now().strftime("%Y-%m-%d")
            matches = [
                br_id for br_id, br in self.receptions.items()
                if br["Supplier_ID"] == sid
                and br["PO_ID"] == po_id
                and not br["Supplier_BL_Ref"]
                and br["Date"] == today
            ]
            if matches:
                self._last_result = [(max(matches),)]

        elif sql_clean.startswith("INSERT INTO Reception_Log"):
            br_id = self.next_br_id
            self.next_br_id += 1
            if "Document_Type" in sql_clean and "'BL'" in sql_clean:
                po_id, sid, bl, u1, u2 = params
                doc_type = "BL"
            else:
                po_id, sid, u1, u2 = params
                bl = None
                doc_type = "None"
            self.receptions[br_id] = {
                "BR_ID": br_id,
                "PO_ID": po_id,
                "Supplier_ID": sid,
                "Supplier_BL_Ref": bl,
                "Document_Type": doc_type,
                "Date": datetime.now().strftime("%Y-%m-%d"),
                "Invoice_Total_HT": 0.0,
                "Invoice_Total_TVA": 0.0,
                "Invoice_Total_TTC": 0.0,
                "Total_Discount": 0.0,
            }
            self.lastrowid = br_id

        elif sql_clean.startswith("SELECT Internal_Barcode FROM Inventory_Batches WHERE PO_ID = %s"):
            po_id = params[0]
            prefix = params[1].rstrip("%")
            self._last_result = [
                (b["Internal_Barcode"],)
                for b in self.batches.values()
                if b["PO_ID"] == po_id and str(b["Internal_Barcode"]).startswith(prefix)
            ]

        elif sql_clean.startswith("SELECT Batch_ID FROM Inventory_Batches WHERE Internal_Barcode = %s"):
            bc = params[0]
            matches = [bid for bid, b in self.batches.items() if b["Internal_Barcode"] == bc]
            if matches:
                self._last_result = [(matches[0],)]

        elif sql_clean.startswith("INSERT INTO Inventory_Batches"):
            bid = self.next_batch_id
            self.next_batch_id += 1
            self.batches[bid] = {
                "Batch_ID": bid,
                "Product_ID": params[0],
                "Location_ID": params[1],
                "Lot_Number": params[2],
                "Quantity_Initial": params[4],
                "Quantity_Current": params[5],
                "PO_ID": params[6],
                "BR_ID": params[7],
                "Unit_Price_Received": params[8],
                "Supplier_ID": params[17],
                "Internal_Barcode": params[19],
            }
            self.lastrowid = bid

        elif sql_clean.startswith("UPDATE Reception_Log SET Invoice_Total_HT"):
            ht, tva, ttc, disc, br_id = params
            r = self.receptions[br_id]
            r["Invoice_Total_HT"] += ht
            r["Invoice_Total_TVA"] += tva
            r["Invoice_Total_TTC"] += ttc
            r["Total_Discount"] += disc

        elif sql_clean.startswith("UPDATE Purchase_Orders SET Total_Amount_HT"):
            ht, tva, ttc, po_id = params
            p = self.purchase_orders[po_id]
            p["Total_Amount_HT"] += ht
            p["Total_Tax_Amount"] += tva
            p["Total_Amount_TTC"] += ttc

        elif sql_clean.startswith("SHOW COLUMNS FROM Inventory_Batches"):
            self._last_result = [("ok",)]

        elif sql_clean.startswith("SELECT BR_ID, Product_ID FROM Inventory_Batches WHERE Batch_ID = %s"):
            bid = params[0]
            b = self.batches.get(bid)
            if b:
                self._last_result = [(b["BR_ID"], b["Product_ID"])]

    def fetchone(self):
        return self._last_result[0] if self._last_result else None

    def fetchall(self):
        return list(self._last_result)

    def close(self):
        pass


def _make_manager():
    cur = FakeQuickAddCursor()
    conn = MagicMock()
    conn.cursor.return_value = cur
    conn.is_connected.return_value = True
    db = MagicMock()
    db.get_raw_connection.return_value = conn
    return InventoryBatchManager(db), cur


def test_add_direct_batch_requires_supplier():
    mgr, _ = _make_manager()
    with pytest.raises(ValueError, match="Supplier_ID"):
        mgr.add_direct_batch({
            "Product_ID": 1,
            "Location_ID": 1,
            "Quantity": 2,
            "Unit_Price_HT": 1000.0,
        })


def test_quick_add_creates_virtual_po_merges_br_by_bl_or_same_day_and_keeps_po_barcodes():
    mgr, cur = _make_manager()

    # 1. Supplier 10, BL-001 -> creates PO + BR #1 + barcode <PO>001
    d1 = {
        "Product_ID": 1, "Location_ID": 1, "Supplier_ID": 10,
        "Quantity": 2, "Unit_Price_HT": 5000.0, "Selling_Price_HT": 6500.0,
        "BL_Number": "BL-001", "Expiry_Date": None,
    }
    assert mgr.add_direct_batch(d1, user_id=1) is True
    po_id = d1["PO_ID"]
    br_1 = d1["BR_ID"]
    assert d1["Generated_Barcode"] == f"{po_id}001"
    assert cur.receptions[br_1]["Document_Type"] == "BL"
    assert cur.receptions[br_1]["Supplier_BL_Ref"] == "BL-001"

    # 2. Same supplier 10, SAME BL-001 -> merges into BR #1, barcode <PO>002
    d2 = {
        "Product_ID": 2, "Location_ID": 1, "Supplier_ID": 10,
        "Quantity": 3, "Unit_Price_HT": 2000.0, "Selling_Price_HT": 3000.0,
        "BL_Number": "BL-001", "Expiry_Date": None,
    }
    assert mgr.add_direct_batch(d2, user_id=1) is True
    assert d2["PO_ID"] == po_id
    assert d2["BR_ID"] == br_1
    assert d2["Generated_Barcode"] == f"{po_id}002"
    assert cur.receptions[br_1]["Invoice_Total_HT"] == 16000.0

    # 3. Same supplier 10, same day, DIFFERENT BL-002 -> creates NEW BR #2, barcode <PO>003
    d3 = {
        "Product_ID": 3, "Location_ID": 1, "Supplier_ID": 10,
        "Quantity": 1, "Unit_Price_HT": 4000.0, "Selling_Price_HT": 5000.0,
        "BL_Number": "BL-002", "Expiry_Date": None,
    }
    assert mgr.add_direct_batch(d3, user_id=1) is True
    assert d3["PO_ID"] == po_id
    assert d3["BR_ID"] != br_1
    assert d3["Generated_Barcode"] == f"{po_id}003"

    # 4. Same supplier 10, same day, EMPTY BL -> creates BR #3 (Document_Type='None')
    d4 = {
        "Product_ID": 4, "Location_ID": 1, "Supplier_ID": 10,
        "Quantity": 1, "Unit_Price_HT": 1000.0, "Selling_Price_HT": 1500.0,
        "BL_Number": "", "Expiry_Date": None,
    }
    assert mgr.add_direct_batch(d4, user_id=1) is True
    br_empty = d4["BR_ID"]
    assert br_empty not in (br_1, d3["BR_ID"])
    assert cur.receptions[br_empty]["Document_Type"] == "None"
    assert d4["Generated_Barcode"] == f"{po_id}004"

    # 5. Same supplier 10, same day, EMPTY BL again -> merges into BR #3
    d5 = {
        "Product_ID": 5, "Location_ID": 1, "Supplier_ID": 10,
        "Quantity": 2, "Unit_Price_HT": 1500.0, "Selling_Price_HT": 2000.0,
        "BL_Number": "", "Expiry_Date": None,
    }
    assert mgr.add_direct_batch(d5, user_id=1) is True
    assert d5["BR_ID"] == br_empty
    assert d5["Generated_Barcode"] == f"{po_id}005"


def test_update_direct_batch_preserves_initial_values_when_linked_to_br():
    mgr, cur = _make_manager()

    d1 = {
        "Product_ID": 1, "Location_ID": 1, "Supplier_ID": 10,
        "Quantity": 5, "Unit_Price_HT": 5000.0, "Selling_Price_HT": 6500.0,
        "BL_Number": "BL-001", "Expiry_Date": None,
    }
    assert mgr.add_direct_batch(d1, user_id=1) is True

    cur.executed.clear()
    ok = mgr.update_direct_batch(1, {
        "Product_ID": 999,       # should NOT be updated
        "Location_ID": 2,        # operational -> allowed
        "Lot_Number": "LOT-NEW", # operational -> allowed
        "Expiry_Date": None,
        "Quantity": 99,          # should NOT be updated
        "Unit_Price_HT": 1.0,    # should NOT be updated
        "Selling_Price_HT": 7200.0,
        "Batch_Note": "Updated note",
        "External_Barcode": "",
        "Supplier_ID": 888,      # should NOT be updated
        "BL_Number": "BL-HACK",  # should NOT be updated
    }, user_id=1)
    assert ok is True

    update_sqls = [sql for sql, _ in cur.executed if sql.startswith("UPDATE Inventory_Batches")]
    assert len(update_sqls) == 1
    assert "Quantity_Initial" not in update_sqls[0]
    assert "Unit_Price_Received" not in update_sqls[0]
    assert "Supplier_ID" not in update_sqls[0]
    assert "BL_Number" not in update_sqls[0]
    assert "Selling_Price_HT" in update_sqls[0]
    assert "Location_ID" in update_sqls[0]
