# -*- coding: utf-8 -*-
"""
test/test_clients_lazy_loading_and_navigation.py
================================================
Tests for:
1. Dedicated 'Clients' Navigation Bar button (Page 16, nav_clients).
2. Removal of Clients from Données de Base (MasterDataTabs).
3. ClientManager.get_clients_paged database-level pagination & search.
4. ClientsTab Lazy Loading on scroll and manual load more.
5. Navigation permissions fallbacks and role-based access.
"""

import sys
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt

from ui.navigation_permissions import has_navigation_permission, has_permission, NAVIGATION_PERMISSION_FALLBACKS
from database.client_manager import ClientManager


# Ensure QApplication instance
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)


class TestClientsLazyLoadingAndNavigation(unittest.TestCase):

    def setUp(self):
        self.mock_db = MagicMock()
        self.client_manager = ClientManager(self.mock_db)

        # Generate 120 sample client records for lazy loading tests
        self.sample_clients = []
        for i in range(1, 121):
            self.sample_clients.append({
                "Client_ID": i,
                "Client_Name": f"Client Test {i:03d}",
                "Contact_Person": f"Contact {i}",
                "Phone": f"0555{i:06d}",
                "Email": f"client{i}@test.com",
                "City": "Alger" if i % 2 == 0 else "Oran",
                "Price_Tier": "Prix_1" if i % 3 == 0 else "Prix_2",
                "Credit_Limit": 100000.0,
                "Current_Balance": 25000.0 if i % 4 == 0 else 0.0,
                "Tax_ID_Number": f"NIF{i:05d}",
                "Commercial_Reg_No": f"RC{i:05d}"
            })

    def test_navigation_permission_fallbacks(self):
        """Verify nav_clients fallback to tab_clients and granular actions."""
        self.assertIn("nav_clients", NAVIGATION_PERMISSION_FALLBACKS)
        self.assertIn("tab_clients", NAVIGATION_PERMISSION_FALLBACKS["nav_clients"])

        # Fallback grant from tab_clients
        user_with_tab = {"Permissions": {"tab_clients": True}}
        self.assertTrue(has_navigation_permission(user_with_tab, "nav_clients"))

        # Direct grant
        user_direct = {"Permissions": {"nav_clients": True}}
        self.assertTrue(has_navigation_permission(user_direct, "nav_clients"))

        # Explicit deny overrides fallback
        user_denied = {"Permissions": {"nav_clients": False, "tab_clients": True}}
        self.assertFalse(has_navigation_permission(user_denied, "nav_clients"))

        # Admin user
        admin_user = {"Role": "Admin", "Permissions": {}}
        self.assertTrue(has_navigation_permission(admin_user, "nav_clients"))

    def test_client_manager_get_clients_paged_fallback_and_pagination(self):
        """Verify get_clients_paged pagination slices and counts correctly."""
        with patch.object(self.client_manager, "get_all_clients_with_balances", return_value=self.sample_clients):
            # Page 1 (offset=0, limit=50)
            res1 = self.client_manager.get_clients_paged(search_text=None, offset=0, limit=50)
            self.assertEqual(len(res1["items"]), 50)
            self.assertEqual(res1["total_count"], 120)
            self.assertTrue(res1["has_more"])
            self.assertEqual(res1["items"][0]["Client_Name"], "Client Test 001")
            self.assertEqual(res1["items"][49]["Client_Name"], "Client Test 050")

            # Page 2 (offset=50, limit=50)
            res2 = self.client_manager.get_clients_paged(search_text=None, offset=50, limit=50)
            self.assertEqual(len(res2["items"]), 50)
            self.assertEqual(res2["items"][0]["Client_Name"], "Client Test 051")
            self.assertTrue(res2["has_more"])

            # Page 3 (offset=100, limit=50) -> only 20 remaining
            res3 = self.client_manager.get_clients_paged(search_text=None, offset=100, limit=50)
            self.assertEqual(len(res3["items"]), 20)
            self.assertFalse(res3["has_more"])
            self.assertEqual(res3["items"][-1]["Client_Name"], "Client Test 120")

    def test_client_manager_get_clients_paged_search(self):
        """Verify get_clients_paged filters by search term."""
        with patch.object(self.client_manager, "get_all_clients_with_balances", return_value=self.sample_clients):
            res = self.client_manager.get_clients_paged(search_text="Test 007", offset=0, limit=50)
            self.assertEqual(len(res["items"]), 1)
            self.assertEqual(res["total_count"], 1)
            self.assertEqual(res["items"][0]["Client_Name"], "Client Test 007")
            self.assertFalse(res["has_more"])

    def test_clients_tab_lazy_loading(self):
        """Verify ClientsTab loads 50 clients initially and appends on load_more_clients."""
        from ui.widgets.clients.clients_tab import ClientsTab

        mock_dm = MagicMock()
        mock_dm.clients = self.client_manager

        with patch.object(self.client_manager, "get_all_clients_with_balances", return_value=self.sample_clients):
            tab = ClientsTab(mock_dm)

            # Initial load: exactly 50 rows in the table
            self.assertEqual(tab.clients_table.rowCount(), 50)
            self.assertEqual(tab._current_offset, 50)
            self.assertEqual(tab._total_count, 120)
            self.assertTrue(tab._has_more)
            self.assertIn("50 / 120", tab.lbl_counter.text())
            self.assertFalse(tab.btn_load_more.isHidden())

            # Load second batch: 50 more rows -> total 100
            tab.load_more_clients()
            self.assertEqual(tab.clients_table.rowCount(), 100)
            self.assertEqual(tab._current_offset, 100)
            self.assertTrue(tab._has_more)
            self.assertIn("100 / 120", tab.lbl_counter.text())

            # Load final batch: 20 more rows -> total 120
            tab.load_more_clients()
            self.assertEqual(tab.clients_table.rowCount(), 120)
            self.assertEqual(tab._current_offset, 120)
            self.assertFalse(tab._has_more)
            self.assertIn("120 / 120", tab.lbl_counter.text())
            self.assertTrue(tab.btn_load_more.isHidden())

    def test_clients_tab_search_resets_and_lazy_loads(self):
        """Verify typing in search input filters results and resets offset."""
        from ui.widgets.clients.clients_tab import ClientsTab

        mock_dm = MagicMock()
        mock_dm.clients = self.client_manager

        with patch.object(self.client_manager, "get_all_clients_with_balances", return_value=self.sample_clients):
            tab = ClientsTab(mock_dm)
            self.assertEqual(tab.clients_table.rowCount(), 50)

            # Perform search for specific client
            tab.search_input.setText("Test 042")
            tab.load_clients_data(reset=True)

            self.assertEqual(tab.clients_table.rowCount(), 1)
            self.assertEqual(tab.clients_table.item(0, 1).text(), "Client Test 042")
            self.assertIn("1 / 1", tab.lbl_counter.text())

            # Clear search
            tab.search_input.setText("")
            tab.load_clients_data(reset=True)
            self.assertEqual(tab.clients_table.rowCount(), 50)
            self.assertIn("50 / 120", tab.lbl_counter.text())

    def test_clients_removed_from_master_data_tabs(self):
        """Verify MasterDataTabs no longer includes the Clients tab in its tabs widget."""
        from ui.widgets.master_data.master_data_tabs import MasterDataTabs

        mock_dm = MagicMock()
        master_tabs = MasterDataTabs(mock_dm)

        # Confirm no tab in QTabWidget is named "Clients"
        tab_names = [master_tabs.tabs.tabText(i) for i in range(master_tabs.tabs.count())]
        self.assertNotIn("Clients", tab_names)
        self.assertIsNone(master_tabs.tab_clients)

    def test_main_window_has_clients_button_and_page_16(self):
        """Verify MainWindow defines button 16 ('Clients') and loads ClientsTab on page 16."""
        from ui.main_window import MainWindow

        mock_dm = MagicMock()
        mock_dm.clients = self.client_manager

        with patch("ui.main_window.AutoBackupWorker"), \
             patch("ui.widgets.dashboard.dashboard_view.DashboardTab.refresh_all"), \
             patch("PySide6.QtWidgets.QMessageBox.question"):
            with patch.object(self.client_manager, "get_all_clients_with_balances", return_value=[]):
                admin_user = {"Role": "Admin", "Permissions": {}}
                win = MainWindow(data_manager=mock_dm, current_user=admin_user)

                # 1. Nav button 16 exists with text "Clients"
                btn_clients = win.nav_group.button(16)
                self.assertIsNotNone(btn_clients)
                self.assertEqual(btn_clients.text(), "Clients")
                self.assertFalse(btn_clients.isHidden())

                # 2. Switching to page 16 loads ClientsTab
                win.switch_page(16)
                current_widget = win.content_area.currentWidget()
                from ui.widgets.clients.clients_tab import ClientsTab
                self.assertIsInstance(current_widget, ClientsTab)

                # 3. Page 1 (Master Data) does not contain a "Clients" tab
                win.switch_page(1)
                master_data_widget = win.content_area.currentWidget()
                tab_names = [master_data_widget.tabs.tabText(i) for i in range(master_data_widget.tabs.count())]
                self.assertNotIn("Clients", tab_names)

                win.deleteLater()
                app.processEvents()

    def tearDown(self):
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
