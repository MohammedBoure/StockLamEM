# -*- coding: utf-8 -*-
"""
test/test_navbar_short_names.py
===============================
Tests verifying Task #2:
- Shorter labels in the left navigation bar for:
  * Page 14: 'Bureaux' (previously 'Bureaux Opérationnels')
  * Page 15: 'SAV' (previously 'Service Après-Vente (SAV)')
- Reduced horizontal sidebar width (240px instead of 260px) to maximize screen workspace.
- Preserved informative tooltips in both expanded and compact states.
"""

import sys
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from database.client_manager import ClientManager


# Ensure QApplication instance
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)


class TestNavbarShortNames(unittest.TestCase):

    def setUp(self):
        self.mock_dm = MagicMock()
        self.mock_dm.clients = ClientManager(MagicMock())
        self.admin_user = {"Role": "Admin", "Permissions": {}}

    def tearDown(self):
        app.processEvents()

    def test_navbar_buttons_14_and_15_short_names_and_tooltips(self):
        """Verifies buttons 14 and 15 have short labels and informative tooltips."""
        from ui.main_window import MainWindow

        with patch("ui.main_window.AutoBackupWorker"), \
             patch("ui.widgets.dashboard.dashboard_view.DashboardTab.refresh_all"), \
             patch("PySide6.QtWidgets.QMessageBox.question"):
            with patch.object(self.mock_dm.clients, "get_all_clients_with_balances", return_value=[]):
                win = MainWindow(data_manager=self.mock_dm, current_user=self.admin_user)

                # 1. Sidebar full width is optimized to 240px
                self.assertEqual(win.sidebar_full_width, 240)
                self.assertEqual(win.sidebar_container.width(), 240)

                # 2. Page 14 button text is 'Bureaux' and has descriptive tooltip
                btn_14 = win.nav_group.button(14)
                self.assertIsNotNone(btn_14)
                self.assertEqual(btn_14.text(), "Bureaux")
                self.assertIn("Bureaux Opérationnels", btn_14.toolTip())

                # 3. Page 15 button text is 'SAV' and has descriptive tooltip
                btn_15 = win.nav_group.button(15)
                self.assertIsNotNone(btn_15)
                self.assertEqual(btn_15.text(), "SAV")
                self.assertIn("Service Après-Vente", btn_15.toolTip())

                # 4. Toggle sidebar to compact mode
                win.toggle_sidebar_compact()
                self.assertFalse(win.is_sidebar_expanded)
                self.assertEqual(btn_14.text(), "")
                self.assertIn("Bureaux Opérationnels", btn_14.toolTip())
                self.assertEqual(btn_15.text(), "")
                self.assertIn("Service Après-Vente", btn_15.toolTip())

                # 5. Toggle sidebar back to expanded mode
                win.toggle_sidebar_compact()
                self.assertTrue(win.is_sidebar_expanded)
                self.assertEqual(btn_14.text(), "Bureaux")
                self.assertIn("Bureaux Opérationnels", btn_14.toolTip())
                self.assertEqual(btn_15.text(), "SAV")
                self.assertIn("Service Après-Vente", btn_15.toolTip())

                win.deleteLater()
                app.processEvents()


if __name__ == "__main__":
    unittest.main()
