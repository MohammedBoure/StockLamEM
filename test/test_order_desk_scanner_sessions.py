# -*- coding: utf-8 -*-
"""
test/test_order_desk_scanner_sessions.py
========================================
Unit tests for Task #10 (Bureaux -> 1. Commandes):
1. Each session can be bound to a specific barcode scanner with a distinctive tab name.
2. Workers can create direct-search sessions (unbound) and close/remove them.
3. Scanner binding enforces uniqueness across sessions on the same device.
4. Receiving an event in an inactive session highlights the session tab button color,
   and switching to that session clears the highlight.
"""

import os
import unittest
from unittest.mock import MagicMock

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from ui.widgets.appliance_desks.order_desk_view import OrderDeskWidget


class TestOrderDeskScannerSessions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["PYTEST_CURRENT_TEST"] = "1"
        cls.app = QApplication.instance() or QApplication([])

    def _make_mock_data_manager(self):
        dm = MagicMock()
        dm.manufacturers.get_all_manufacturers.return_value = []
        dm.families.get_all_families.return_value = []
        dm.colors.get_all_colors.return_value = []
        dm.clients.get_all_clients.return_value = []
        dm.serials.get_catalog_with_theoretical_stock.return_value = [
            {
                "Product_ID": 1,
                "Brand_Mark": "Condor",
                "Product_Name": "Réfrigérateur 400L",
                "Category_Name": "Froid",
                "Barcode": "1234567890123",
                "Color_Finish": "Inox",
                "Physical_Stock_Qty": 5,
                "Available_Theoretical_Qty": 5,
                "Unit_Price_TTC": 65000.0,
            }
        ]
        dm.serials.resolve_barcode_scan.return_value = {
            "found": True,
            "product_id": 1,
            "product_name": "Réfrigérateur 400L",
            "barcode": "1234567890123",
        }
        return dm

    def _find_tab_index(self, widget: OrderDeskWidget, sid: str) -> int:
        for i in range(widget.session_tab_bar.count()):
            if widget.session_tab_bar.tabData(i) == sid:
                return i
        return -1

    def test_direct_search_session_create_and_remove(self):
        dm = self._make_mock_data_manager()
        widget = OrderDeskWidget(dm)
        try:
            initial_count = len(widget._sessions)
            sid2 = widget._create_new_session()
            self.assertEqual(len(widget._sessions), initial_count + 1)
            self.assertIsNone(widget._sessions[sid2]["scanner_id"])

            idx2 = self._find_tab_index(widget, sid2)
            self.assertGreaterEqual(idx2, 0)
            self.assertIn("🔍 Recherche", widget.session_tab_bar.tabText(idx2))

            widget._close_session_by_id(sid2)
            self.assertNotIn(sid2, widget._sessions)
            self.assertEqual(len(widget._sessions), initial_count)
        finally:
            widget.deleteLater()

    def test_bind_scanner_distinct_name_and_uniqueness(self):
        dm = self._make_mock_data_manager()
        widget = OrderDeskWidget(dm)
        try:
            sid1 = widget._active_session_id
            sid2 = widget._create_new_session()

            ok1, _ = widget.bind_scanner_to_session(sid1, "SCAN-1")
            self.assertTrue(ok1)
            idx1 = self._find_tab_index(widget, sid1)
            tab_text_1 = widget.session_tab_bar.tabText(idx1)
            self.assertIn("📷 Scanner [SCAN-1]", tab_text_1)

            # Attempting to bind the same scanner to another session must fail
            ok2, msg2 = widget.bind_scanner_to_session(sid2, "SCAN-1")
            self.assertFalse(ok2)
            self.assertTrue(len(msg2) > 0)
            self.assertIsNone(widget._sessions[sid2]["scanner_id"])

            # Binding a different scanner to sid2 succeeds
            ok3, _ = widget.bind_scanner_to_session(sid2, "SCAN-2")
            self.assertTrue(ok3)
            idx2 = self._find_tab_index(widget, sid2)
            self.assertIn("📷 Scanner [SCAN-2]", widget.session_tab_bar.tabText(idx2))

            # Unbinding SCAN-1 from sid1 frees it for sid2
            widget.unbind_scanner_from_session(sid1)
            self.assertIsNone(widget._sessions[sid1]["scanner_id"])
            self.assertIn("🔍 Recherche", widget.session_tab_bar.tabText(idx1))

            ok4, _ = widget.bind_scanner_to_session(sid2, "SCAN-1")
            self.assertTrue(ok4)
            self.assertEqual(widget._sessions[sid2]["scanner_id"], "SCAN-1")
        finally:
            widget.deleteLater()

    def test_session_event_changes_tab_color_and_resets_on_focus(self):
        dm = self._make_mock_data_manager()
        widget = OrderDeskWidget(dm)
        try:
            sid1 = widget._active_session_id
            widget.bind_scanner_to_session(sid1, "SCAN-A")

            sid2 = widget._create_new_session()
            idx2 = self._find_tab_index(widget, sid2)
            widget.session_tab_bar.setCurrentIndex(idx2)
            self.assertEqual(widget._active_session_id, sid2)

            # Trigger scanner event on inactive sid1
            widget._on_scanner_input_for_session(sid1, "SCAN-A", "1234567890123")
            self.assertTrue(widget._sessions[sid1]["has_event"])

            idx1 = self._find_tab_index(widget, sid1)
            self.assertEqual(
                widget.session_tab_bar.tabTextColor(idx1),
                QColor("#D97706"),
            )

            # Switching to sid1 clears the event highlight
            widget.session_tab_bar.setCurrentIndex(idx1)
            self.assertFalse(widget._sessions[sid1]["has_event"])
            self.assertEqual(
                widget.session_tab_bar.tabTextColor(idx1),
                QColor("#495057"),
            )
        finally:
            widget.deleteLater()


if __name__ == "__main__":
    unittest.main()
