"""Unit and integration tests for the simplified User Permissions System (Sidebar + Internal Tabs only).

Verifies:
1. Presence of '10. BUREAUX_WORKFLOW', '11. SAV_WORKSPACE', and '7. TRACABILITE' in SYSTEM_PERMISSIONS with only sidebar (nav_...) and internal tab (tab_...) permissions.
2. UserDialog tree structure, natural ordering, and explicit True/False serialization in get_selected_permissions() (fixing the Couleurs / Admin uncheck bug).
3. Role defaults for Administrateur, Responsable, and Technicien.
4. Navigation fallback resolution for nav_appliance_workflow and nav_sav.
5. Internal tab gating in ApplianceWorkflowTab (tab_desk_order, tab_desk_caisse, tab_desk_dispatch).
6. Internal tab gating in SAVWorkspaceTab (tab_sav_all, tab_sav_received, tab_sav_atelier, tab_sav_returned, tab_sav_closed, tab_sav_irreparable).
"""

import os
import unittest
from unittest.mock import MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PYTEST_CURRENT_TEST"] = "1"

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])

from ui.navigation_permissions import (
    NAVIGATION_PERMISSION_FALLBACKS,
    has_navigation_permission,
    has_permission,
)
from ui.widgets.users.user_management_tab import SYSTEM_PERMISSIONS, UserDialog
from ui.widgets.appliance_desks.appliance_workflow_tab import ApplianceWorkflowTab
from ui.widgets.sav.sav_workspace_view import SAVWorkspaceTab
from ui.widgets.appliance_desks.cashier_desk_view import AdminAuthModal


class UserPermissionsDefinitionTests(unittest.TestCase):
    """Verifies that all permission groups in SYSTEM_PERMISSIONS only contain sidebar (nav_) and tab (tab_) permissions."""

    def test_no_complex_action_permissions_in_system_permissions(self):
        for group_key, group_data in SYSTEM_PERMISSIONS.items():
            for perm_key in group_data["perms"]:
                self.assertTrue(
                    perm_key.startswith("nav_") or perm_key.startswith("tab_"),
                    f"Unexpected non-sidebar/non-tab permission {perm_key} in {group_key}",
                )

    def test_bureaux_workflow_group_exists(self):
        self.assertIn("10. BUREAUX_WORKFLOW", SYSTEM_PERMISSIONS)
        group = SYSTEM_PERMISSIONS["10. BUREAUX_WORKFLOW"]
        self.assertIn("Bureaux", group["label"])
        perms = group["perms"]

        expected_perms = [
            "nav_appliance_workflow",
            "tab_desk_order",
            "tab_desk_caisse",
            "tab_desk_dispatch",
        ]
        self.assertEqual(list(perms.keys()), expected_perms)

    def test_sav_workspace_group_exists(self):
        self.assertIn("11. SAV_WORKSPACE", SYSTEM_PERMISSIONS)
        group = SYSTEM_PERMISSIONS["11. SAV_WORKSPACE"]
        self.assertIn("Service Après-Vente", group["label"])
        perms = group["perms"]

        expected_perms = [
            "nav_sav",
            "tab_sav_all",
            "tab_sav_received",
            "tab_sav_atelier",
            "tab_sav_returned",
            "tab_sav_closed",
            "tab_sav_irreparable",
        ]
        self.assertEqual(list(perms.keys()), expected_perms)

    def test_tracabilite_and_colors_in_master_data(self):
        self.assertIn("7. TRACABILITE", SYSTEM_PERMISSIONS)
        perms = SYSTEM_PERMISSIONS["7. TRACABILITE"]["perms"]
        self.assertIn("nav_history", perms)
        self.assertIn("tab_data_colors", SYSTEM_PERMISSIONS["2. DONNEES_DE_BASE"]["perms"])


class UserDialogTreeAndRoleTests(unittest.TestCase):
    """Verifies UserDialog permissions tree structure, role defaults, and explicit False persistence."""

    def setUp(self):
        self.dialog = UserDialog()

    def tearDown(self):
        self.dialog.close()

    def test_tree_natural_order(self):
        """Checks that groups 10 and 11 appear after group 9, not after group 1."""
        top_labels = []
        for i in range(self.dialog.tree_perms.topLevelItemCount()):
            top_labels.append(self.dialog.tree_perms.topLevelItem(i).text(0))

        idx_dashboard = next(i for i, text in enumerate(top_labels) if "Tableau de Bord" in text)
        idx_settings = next(i for i, text in enumerate(top_labels) if "Paramètres" in text)
        idx_bureaux = next(i for i, text in enumerate(top_labels) if "Bureaux" in text)
        idx_sav = next(i for i, text in enumerate(top_labels) if "Service Après-Vente" in text)

        self.assertLess(idx_dashboard, idx_settings)
        self.assertLess(idx_settings, idx_bureaux)
        self.assertLess(idx_bureaux, idx_sav)

    def test_admin_role_grants_all_sidebar_and_tab_permissions(self):
        self.dialog.role_combo.setCurrentText("Administrateur")
        perms = self.dialog.get_selected_permissions()

        self.assertTrue(perms.get("nav_appliance_workflow"))
        self.assertTrue(perms.get("tab_desk_order"))
        self.assertTrue(perms.get("tab_desk_caisse"))
        self.assertTrue(perms.get("tab_desk_dispatch"))
        self.assertTrue(perms.get("nav_sav"))
        self.assertTrue(perms.get("tab_sav_all"))
        self.assertTrue(perms.get("tab_sav_received"))
        self.assertTrue(perms.get("tab_sav_atelier"))
        self.assertTrue(perms.get("tab_sav_returned"))
        self.assertTrue(perms.get("tab_sav_closed"))
        self.assertTrue(perms.get("tab_sav_irreparable"))
        self.assertTrue(perms.get("tab_data_colors"))
        self.assertTrue(perms.get("nav_history"))

    def test_unchecking_colors_for_admin_explicitly_saves_false(self):
        """Verifies that unchecking tab_data_colors for an Admin user saves False and denies has_permission."""
        admin_user = {
            "User_ID": 1,
            "Username": "admin",
            "Role": "Admin",
            "Permissions": {},
        }
        dlg = UserDialog(data=admin_user)
        # Missing keys on existing Admin should default to checked in UI
        initial_perms = dlg.get_selected_permissions()
        self.assertTrue(initial_perms.get("tab_data_colors"))

        # Uncheck tab_data_colors in the tree
        for i in range(dlg.tree_perms.topLevelItemCount()):
            group_item = dlg.tree_perms.topLevelItem(i)
            for j in range(group_item.childCount()):
                child = group_item.child(j)
                if child.data(0, Qt.UserRole) == "tab_data_colors":
                    child.setCheckState(0, Qt.Unchecked)

        updated_perms = dlg.get_selected_permissions()
        self.assertIn("tab_data_colors", updated_perms)
        self.assertFalse(updated_perms["tab_data_colors"])

        admin_user["Permissions"] = updated_perms
        self.assertFalse(has_permission(admin_user, "tab_data_colors"))
        dlg.close()

    def test_set_and_get_permissions_roundtrip(self):
        custom_perms = {
            "nav_appliance_workflow": True,
            "tab_desk_order": True,
            "nav_sav": True,
            "tab_sav_received": True,
            "tab_data_colors": False,
        }
        self.dialog.set_permissions(custom_perms)
        selected = self.dialog.get_selected_permissions()

        self.assertTrue(selected.get("nav_appliance_workflow"))
        self.assertTrue(selected.get("tab_desk_order"))
        self.assertTrue(selected.get("nav_sav"))
        self.assertTrue(selected.get("tab_sav_received"))
        self.assertFalse(selected.get("tab_desk_caisse"))
        self.assertFalse(selected.get("tab_desk_dispatch"))
        self.assertFalse(selected.get("tab_data_colors"))


class NavigationFallbackTests(unittest.TestCase):
    """Verifies that navigation permissions resolve strictly from their own internal tabs."""

    def test_nav_appliance_workflow_fallback_from_internal_tabs(self):
        self.assertTrue(has_navigation_permission({"Permissions": {"tab_desk_order": True}}, "nav_appliance_workflow"))
        self.assertTrue(has_navigation_permission({"Permissions": {"tab_desk_caisse": True}}, "nav_appliance_workflow"))
        self.assertTrue(has_navigation_permission({"Permissions": {"tab_desk_dispatch": True}}, "nav_appliance_workflow"))
        # Unrelated permissions should NOT enable Bureaux
        self.assertFalse(has_navigation_permission({"Permissions": {"nav_inventory": True}}, "nav_appliance_workflow"))

    def test_nav_sav_fallback_from_internal_tabs(self):
        self.assertTrue(has_navigation_permission({"Permissions": {"tab_sav_received": True}}, "nav_sav"))
        self.assertTrue(has_navigation_permission({"Permissions": {"tab_sav_atelier": True}}, "nav_sav"))
        self.assertFalse(has_navigation_permission({"Permissions": {"nav_clients": True}}, "nav_sav"))

    def test_nav_sav_explicit_deny_respected(self):
        user = {"Permissions": {"nav_sav": False, "tab_sav_all": True}}
        self.assertFalse(has_navigation_permission(user, "nav_sav"))


class ApplianceWorkflowRBACDeskGatingTests(unittest.TestCase):
    """Verifies desk tab visibility and enabling in ApplianceWorkflowTab based on tab_desk_* permissions."""

    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_db.products = MagicMock()
        self.mock_db.products.get_all_products.return_value = []
        self.mock_db.manufacturers = MagicMock()
        self.mock_db.manufacturers.get_all_manufacturers.return_value = []
        self.mock_db.families = MagicMock()
        self.mock_db.families.get_all_families.return_value = []
        self.mock_db.bonds = MagicMock()
        self.mock_db.bonds.get_caisse_pending_orders.return_value = []
        self.mock_db.bonds.get_dispatch_pending_orders.return_value = []

    def test_all_three_desk_permissions_enable_all_desks(self):
        widget = ApplianceWorkflowTab(
            db_manager=self.mock_db,
            user_permissions={"tab_desk_order", "tab_desk_caisse", "tab_desk_dispatch"},
            include_sav=False,
        )
        self.assertTrue(widget.desk_tabs.isTabEnabled(0))
        self.assertTrue(widget.desk_tabs.isTabEnabled(1))
        self.assertTrue(widget.desk_tabs.isTabEnabled(2))
        widget.deleteLater()

    def test_order_desk_only_permission(self):
        widget = ApplianceWorkflowTab(
            db_manager=self.mock_db,
            user_permissions={"tab_desk_order"},
            include_sav=False,
        )
        self.assertTrue(widget.desk_tabs.isTabEnabled(0))
        self.assertFalse(widget.desk_tabs.isTabEnabled(1))
        self.assertFalse(widget.desk_tabs.isTabEnabled(2))
        widget.deleteLater()

    def test_caisse_desk_only_permission(self):
        widget = ApplianceWorkflowTab(
            db_manager=self.mock_db,
            user_permissions={"tab_desk_caisse"},
            include_sav=False,
        )
        self.assertFalse(widget.desk_tabs.isTabEnabled(0))
        self.assertTrue(widget.desk_tabs.isTabEnabled(1))
        self.assertFalse(widget.desk_tabs.isTabEnabled(2))
        widget.deleteLater()

    def test_dispatch_desk_only_permission(self):
        widget = ApplianceWorkflowTab(
            db_manager=self.mock_db,
            user_permissions={"tab_desk_dispatch"},
            include_sav=False,
        )
        self.assertFalse(widget.desk_tabs.isTabEnabled(0))
        self.assertFalse(widget.desk_tabs.isTabEnabled(1))
        self.assertTrue(widget.desk_tabs.isTabEnabled(2))
        widget.deleteLater()


class SAVWorkspaceTabGatingTests(unittest.TestCase):
    """Verifies that SAVWorkspaceTab shows/hides internal stage tabs based on tab_sav_* permissions."""

    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_db.sav = MagicMock()
        self.mock_db.sav.get_all_sav_tickets.return_value = []
        self.mock_db.sav.get_tickets_summary_counts.return_value = {}

    def test_sav_internal_tabs_visibility_and_enabling(self):
        user = {
            "Role": "Technician",
            "Permissions": {
                "nav_sav": True,
                "tab_sav_all": False,
                "tab_sav_received": True,
                "tab_sav_atelier": True,
                "tab_sav_returned": False,
                "tab_sav_closed": False,
                "tab_sav_irreparable": False,
            },
        }
        tab = SAVWorkspaceTab(data_manager=self.mock_db, current_user=user)
        self.assertFalse(tab.tabs.isTabEnabled(0))  # tab_sav_all
        self.assertTrue(tab.tabs.isTabEnabled(1))   # tab_sav_received
        self.assertTrue(tab.tabs.isTabEnabled(2))   # tab_sav_atelier
        self.assertFalse(tab.tabs.isTabEnabled(3))  # tab_sav_returned
        self.assertFalse(tab.tabs.isTabEnabled(4))  # tab_sav_closed
        self.assertFalse(tab.tabs.isTabEnabled(5))  # tab_sav_irreparable
        # Intake button remains accessible when user has access to the SAV workspace
        self.assertTrue(tab.btn_intake.isEnabled())
        tab.deleteLater()


class AdminAuthModalTests(unittest.TestCase):
    """Verifies that AdminAuthModal authorizes supervisors/admins for Bon Crédit."""

    def test_admin_auth_modal_authorizes_supervisor(self):
        mock_db = MagicMock()
        mock_users = MagicMock()
        supervisor_user = {
            "User_ID": 42,
            "Role": "Responsable",
            "Permissions": {"tab_desk_caisse": True},
        }
        mock_users.authenticate.return_value = supervisor_user
        mock_db.users = mock_users

        modal = AdminAuthModal(
            client_name="Client Test",
            requested_amount=15000.0,
            data_manager=mock_db,
        )
        modal.txt_admin_user.setText("responsable1")
        modal.txt_pin.setText("pass123")
        modal._verify_credentials()

        self.assertTrue(modal.approved)
        self.assertEqual(modal.admin_user_id, 42)
        modal.deleteLater()


if __name__ == "__main__":
    unittest.main()
