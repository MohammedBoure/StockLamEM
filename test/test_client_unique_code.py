# -*- coding: utf-8 -*-
"""
test/test_client_unique_code.py
===============================
Unit tests for Task #1 (Clients):
1. O(1) bijective unique pseudo-random client number generator (>= 4 digits) with zero collisions.
2. ClientManager persistence (`add_client`) & search (`get_clients_paged`) by `Client_Code`.
3. ClientsTab UI column (`N° Client`), styling, and search placeholder.
4. ClientDialog UI display of unique `N° Client` (edit mode vs add mode).
"""

import os
import time
import unittest
from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication

from database.client_manager import ClientManager, generate_unique_client_code
from ui.widgets.clients.clients_tab import ClientsTab
from ui.widgets.master_data.dialogs import ClientDialog


class TestClientUniqueCode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["PYTEST_CURRENT_TEST"] = "1"
        cls.app = QApplication.instance() or QApplication([])

    # =========================================================================
    # 1. ALGORITHM: O(1) UNIQUE RANDOM >= 4-DIGIT NUMBER GENERATOR
    # =========================================================================

    def test_generate_unique_client_code_min_4_digits_and_bijective(self):
        """Verifies >= 4 digits, strict global uniqueness across 12,000 IDs, and tier expansion to 5 digits."""
        seen = set()
        t0 = time.perf_counter()
        codes = [generate_unique_client_code(i) for i in range(1, 12001)]
        elapsed = time.perf_counter() - t0

        for idx, code in enumerate(codes, start=1):
            self.assertTrue(code.isdigit())
            self.assertGreaterEqual(len(code), 4)
            self.assertGreaterEqual(int(code), 1000)
            if idx <= 9000:
                self.assertEqual(len(code), 4)
            else:
                self.assertEqual(len(code), 5)
            seen.add(code)

        self.assertEqual(len(seen), 12000, "Collision detected in bijective client code generator")
        self.assertLess(elapsed, 0.5, f"O(1) generation should be instant, took {elapsed:.3f}s")

    def test_generate_unique_client_code_non_sequential(self):
        """Verifies consecutive client IDs produce shuffled, non-sequential codes."""
        first_ten = [int(generate_unique_client_code(i)) for i in range(1, 11)]
        diffs = {abs(first_ten[i + 1] - first_ten[i]) for i in range(len(first_ten) - 1)}
        self.assertNotIn(1, diffs, "Generated codes must not be sequential (+1)")

    def test_generate_unique_client_code_invalid_id(self):
        """Verifies non-positive IDs raise ValueError."""
        with self.assertRaises(ValueError):
            generate_unique_client_code(0)
        with self.assertRaises(ValueError):
            generate_unique_client_code(-5)

    # =========================================================================
    # 2. BACKEND: ClientManager PERSISTENCE & SEARCH
    # =========================================================================

    def test_add_client_persists_generated_client_code(self):
        """Verifies add_client computes and updates Client_Code in O(1) after INSERT."""
        mock_db = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db.get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.lastrowid = 42

        mgr = ClientManager(mock_db)
        cid = mgr.add_client(name="Client Electro Test")

        self.assertEqual(cid, 42)
        expected_code = generate_unique_client_code(42)
        update_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "UPDATE Clients SET Client_Code" in c.args[0]
        ]
        self.assertEqual(len(update_calls), 1)
        self.assertEqual(update_calls[0].args[1], (expected_code, 42))

    def test_get_clients_paged_searches_by_client_code(self):
        """Verifies searching by unique Client_Code returns the matching client."""
        mock_db = MagicMock()
        mgr = ClientManager(mock_db)

        sample = [
            {"Client_ID": 1, "Client_Name": "Alpha", "Phone": "0550", "Credit_Limit": 0, "Current_Balance": 0},
            {"Client_ID": 2, "Client_Name": "Beta", "Phone": "0660", "Credit_Limit": 0, "Current_Balance": 0},
        ]
        target_code = generate_unique_client_code(2)

        mgr.get_all_clients_with_balances = MagicMock(return_value=sample)
        res = mgr.get_clients_paged(search_text=target_code, offset=0, limit=50)

        self.assertEqual(res["total_count"], 1)
        self.assertEqual(res["items"][0]["Client_Name"], "Beta")
        self.assertEqual(res["items"][0]["Client_Code"], target_code)

    # =========================================================================
    # 3. UI & UX: ClientsTab & ClientDialog
    # =========================================================================

    def test_clients_tab_displays_unique_code_column_and_search(self):
        """Verifies ClientsTab shows 'N° Client' column at index 2 and filters by Client_Code."""
        mock_dm = MagicMock()
        mgr = ClientManager(MagicMock())
        sample = [
            {"Client_ID": 1, "Client_Name": "SARL Lumière", "Phone": "0555112233", "Credit_Limit": 0, "Current_Balance": 0},
            {"Client_ID": 2, "Client_Name": "EURL Électro", "Phone": "0666445566", "Credit_Limit": 0, "Current_Balance": 0},
        ]
        mgr.get_all_clients_with_balances = MagicMock(return_value=sample)
        mock_dm.clients = mgr

        tab = ClientsTab(mock_dm)
        self.assertEqual(tab.clients_table.columnCount(), 12)
        self.assertEqual(tab.clients_table.horizontalHeaderItem(1).text(), "Nom du Client")
        self.assertEqual(tab.clients_table.horizontalHeaderItem(2).text(), "N° Client")
        self.assertIn("N° Client", tab.search_input.placeholderText())

        expected_code_1 = generate_unique_client_code(1)
        self.assertEqual(tab.clients_table.item(0, 1).text(), "SARL Lumière")
        self.assertEqual(tab.clients_table.item(0, 2).text(), expected_code_1)
        self.assertGreaterEqual(len(tab.clients_table.item(0, 2).text()), 4)

        # Filter by Client_Code of client #2
        expected_code_2 = generate_unique_client_code(2)
        tab.search_input.setText(expected_code_2)
        tab.load_clients_data(reset=True)
        self.assertEqual(tab.clients_table.rowCount(), 1)
        self.assertEqual(tab.clients_table.item(0, 1).text(), "EURL Électro")
        self.assertEqual(tab.clients_table.item(0, 2).text(), expected_code_2)

        tab.deleteLater()
        self.app.processEvents()

    def test_client_dialog_displays_client_code_in_add_and_edit_modes(self):
        """Verifies ClientDialog shows auto-gen hint in add mode and unique code in edit mode."""
        dlg_add = ClientDialog()
        self.assertIn("automatiquement", dlg_add.lbl_client_code.text())
        dlg_add.deleteLater()

        dlg_edit = ClientDialog(data={"Client_ID": 7, "Client_Name": "Client Sept"})
        self.assertEqual(dlg_edit.lbl_client_code.text(), generate_unique_client_code(7))
        dlg_edit.deleteLater()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
