# -*- coding: utf-8 -*-
"""Tests verifying Versement and Paiement Livraison sidebar entries and permissions."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PYTEST_CURRENT_TEST"] = "1"

from PySide6.QtWidgets import QApplication

from database.client_manager import ClientManager
from ui.navigation_permissions import (
    NAVIGATION_PERMISSION_FALLBACKS,
    has_navigation_permission,
)
from ui.widgets.paiement_livraison import PaiementLivraisonTab
from ui.widgets.users.user_management_tab import SYSTEM_PERMISSIONS
from ui.widgets.versement import VersementTab

app = QApplication.instance() or QApplication(sys.argv)


class TestNavbarVersementAndPaiementLivraison(unittest.TestCase):
    def setUp(self):
        self.mock_dm = MagicMock()
        self.mock_dm.clients = ClientManager(MagicMock())
        self.admin_user = {"Role": "Admin", "Permissions": {}}

    def tearDown(self):
        app.processEvents()

    def test_permissions_and_fallbacks_registered(self):
        self.assertIn("nav_versement", NAVIGATION_PERMISSION_FALLBACKS)
        self.assertIn("nav_paiement_livraison", NAVIGATION_PERMISSION_FALLBACKS)
        self.assertIn("12. VERSEMENT", SYSTEM_PERMISSIONS)
        self.assertIn("13. PAIEMENT_LIVRAISON", SYSTEM_PERMISSIONS)
        self.assertIn("nav_versement", SYSTEM_PERMISSIONS["12. VERSEMENT"]["perms"])
        self.assertIn(
            "nav_paiement_livraison",
            SYSTEM_PERMISSIONS["13. PAIEMENT_LIVRAISON"]["perms"],
        )

        self.assertTrue(has_navigation_permission(self.admin_user, "nav_versement"))
        self.assertTrue(
            has_navigation_permission(self.admin_user, "nav_paiement_livraison")
        )
        self.assertTrue(
            has_navigation_permission({"Permissions": {"tab_desk_caisse": True}}, "nav_versement")
        )
        self.assertTrue(
            has_navigation_permission(
                {"Permissions": {"tab_desk_dispatch": True}}, "nav_paiement_livraison"
            )
        )
        self.assertFalse(
            has_navigation_permission(
                {"Permissions": {"nav_versement": False, "tab_desk_caisse": True}},
                "nav_versement",
            )
        )
        self.assertFalse(
            has_navigation_permission(
                {"Permissions": {"nav_paiement_livraison": False, "tab_desk_caisse": True}},
                "nav_paiement_livraison",
            )
        )

    def test_navbar_buttons_and_page_switching(self):
        from ui.main_window import MainWindow

        with patch("ui.main_window.AutoBackupWorker"), \
             patch("ui.widgets.dashboard.dashboard_view.DashboardTab.refresh_all"), \
             patch("PySide6.QtWidgets.QMessageBox.question"):
            with patch.object(
                self.mock_dm.clients, "get_all_clients_with_balances", return_value=[]
            ):
                win = MainWindow(data_manager=self.mock_dm, current_user=self.admin_user)

                btn_17 = win.nav_group.button(17)
                btn_18 = win.nav_group.button(18)

                self.assertIsNotNone(btn_17)
                self.assertEqual(btn_17.text(), "Versement")
                self.assertFalse(btn_17.icon().isNull())
                self.assertIn("Versement", btn_17.toolTip())

                self.assertIsNotNone(btn_18)
                self.assertEqual(btn_18.text(), "Paiement Livraison")
                self.assertFalse(btn_18.icon().isNull())
                self.assertIn("Livraison", btn_18.toolTip())

                win.switch_page(17)
                self.assertIsInstance(win.content_area.currentWidget(), VersementTab)

                win.switch_page(18)
                self.assertIsInstance(
                    win.content_area.currentWidget(), PaiementLivraisonTab
                )

                win.toggle_sidebar_compact()
                self.assertEqual(btn_17.text(), "")
                self.assertEqual(btn_18.text(), "")
                win.toggle_sidebar_compact()
                self.assertEqual(btn_17.text(), "Versement")
                self.assertEqual(btn_18.text(), "Paiement Livraison")

                win.deleteLater()
                app.processEvents()


if __name__ == "__main__":
    unittest.main()
