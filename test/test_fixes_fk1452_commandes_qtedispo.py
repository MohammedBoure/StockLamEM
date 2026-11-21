# -*- coding: utf-8 -*-
"""
Regression tests for:
1. FK 1452 prevention on Sales_Invoices.Cash_Session_ID (`_resolve_cash_session_id`
   in BondLifecycleManager & `_resolve_active_cash_session_id` in CashierDeskWidget).
2. Stock Actuel (`BatchesTab`) `Qté Dispo` column (col 25, visually section 2)
   displaying `Quantity_Current - Theoretical_Reserved_Qty` and clean UI.
"""

import os
import sys
import unittest
from decimal import Decimal
from unittest.mock import MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PYTEST_CURRENT_TEST"] = "1"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication

from database.bond_lifecycle_manager import BondLifecycleManager
from ui.widgets.appliance_desks.cashier_desk_view import _resolve_active_cash_session_id
from ui.widgets.inventory.tabs_batches import BatchesTab

app = QApplication.instance() or QApplication([])


class _FKCheckCursor:
    def __init__(self, sessions_in_db):
        self.sessions = list(sessions_in_db)
        self.lastrowid = 99
        self._rows = []

    def execute(self, query, params=None):
        sql = " ".join(query.split())
        params = params or ()
        if sql.startswith("SELECT COUNT(*) AS cnt FROM POS_Cash_Sessions WHERE Cash_Session_ID = %s"):
            cid = int(params[0])
            cnt = sum(1 for s in self.sessions if int(s["Cash_Session_ID"]) == cid)
            self._rows = [{"cnt": cnt}]
        elif "SELECT Cash_Session_ID FROM POS_Cash_Sessions WHERE Status = 'Open'" in sql:
            open_s = [s for s in self.sessions if s.get("Status") == "Open"]
            self._rows = [{"Cash_Session_ID": open_s[0]["Cash_Session_ID"]}] if open_s else []
        else:
            self._rows = []

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class CashSessionFKTests(unittest.TestCase):
    def test_missing_session_id_1_falls_back_to_none_when_no_open_session(self):
        mgr = BondLifecycleManager(MagicMock())
        cur = _FKCheckCursor(sessions_in_db=[])
        resolved = mgr._resolve_cash_session_id(cur, 1)
        self.assertIsNone(resolved)

    def test_missing_session_id_1_falls_back_to_active_open_session(self):
        mgr = BondLifecycleManager(MagicMock())
        cur = _FKCheckCursor(sessions_in_db=[{"Cash_Session_ID": 7, "Status": "Open"}])
        resolved = mgr._resolve_cash_session_id(cur, 1)
        self.assertEqual(resolved, 7)

    def test_existing_session_id_is_preserved(self):
        mgr = BondLifecycleManager(MagicMock())
        cur = _FKCheckCursor(sessions_in_db=[{"Cash_Session_ID": 3, "Status": "Open"}])
        resolved = mgr._resolve_cash_session_id(cur, 3)
        self.assertEqual(resolved, 3)

    def test_ui_helper_resolves_open_session_or_none(self):
        dm_empty = MagicMock()
        dm_empty.cash_sessions.get_any_open_session.return_value = None
        self.assertIsNone(_resolve_active_cash_session_id(dm_empty, 1))

        dm_open = MagicMock()
        dm_open.cash_sessions.get_any_open_session.return_value = {"Cash_Session_ID": 12}
        self.assertEqual(_resolve_active_cash_session_id(dm_open, 1), 12)


class StockActuelQteDispoTests(unittest.TestCase):
    def test_batches_tab_displays_qte_dispo_column_and_visual_position(self):
        mgr = MagicMock()
        mgr.families.get_all_families.return_value = []
        mgr.manufacturers.get_all_manufacturers.return_value = []
        mgr.automates.get_all_automates.return_value = []
        mgr.suppliers.get_all_suppliers.return_value = []
        mgr.locations.get_all_locations_flat.return_value = []
        mgr.batches.get_priority_groups_summary.return_value = []
        mgr.batches.get_all_batches_with_details.return_value = [
            {
                "Batch_ID": 1,
                "Product_ID": 10,
                "Product_Name": "Réfrigérateur 400L",
                "Quantity_Current": 10,
                "Theoretical_Reserved_Qty": 3,
                "Available_Qty": 7,
                "Stock_Unit": "U",
                "Unit_Price_Received": 50000.0,
                "Selling_Price_HT": 65000.0,
                "Lot_Number": "LOT-1",
                "Internal_Barcode": "100000000001",
                "Location_ID": 1,
                "Location_Name": "Dépôt",
                "Created_At": "2026-11-21",
            },
            {
                "Batch_ID": 2,
                "Product_ID": 11,
                "Product_Name": "Cuisinière 5 Feux",
                "Quantity_Current": 5,
                "Theoretical_Reserved_Qty": 5,
                "Stock_Unit": "U",
                "Unit_Price_Received": 30000.0,
                "Selling_Price_HT": 42000.0,
                "Lot_Number": "LOT-2",
                "Internal_Barcode": "100000000002",
                "Location_ID": 1,
                "Location_Name": "Dépôt",
                "Created_At": "2026-11-21",
            },
        ]

        tab = BatchesTab(mgr)
        tab.load_data()
        try:
            self.assertEqual(tab.table.horizontalHeaderItem(25).text(), "Qté Dispo")
            self.assertEqual(tab.table.horizontalHeader().visualIndex(25), 2)
            self.assertEqual(tab.table.rowCount(), 2)
            self.assertEqual(tab.table.item(0, 1).text(), "10")
            self.assertEqual(tab.table.item(0, 25).text(), "7")
            self.assertEqual(tab.table.item(1, 1).text(), "5")
            self.assertEqual(tab.table.item(1, 25).text(), "0")
        finally:
            tab.close()
            tab.deleteLater()


if __name__ == "__main__":
    unittest.main()
