"""Unit and integration tests for Appliance Workflow and SAV integration into the User Permissions System.

Verifies Task #5 deliverables:
1. Presence of '10. BUREAUX_WORKFLOW', '11. SAV_WORKSPACE', and '7. TRACABILITE' enhancements in SYSTEM_PERMISSIONS.
2. UserDialog tree structure, natural ordering, and UserRole key assignment.
3. Role defaults for Administrateur, Responsable, and Technicien.
4. Permission serialization and round-trip via set_permissions and get_selected_permissions.
5. Navigation fallback resolution for nav_appliance_workflow and nav_sav.
6. RBAC desk gating in ApplianceWorkflowTab.
7. Granular action gating in SAVWorkspaceTab, CashierDeskWidget, OrderDeskWidget, and DispatchDeskWidget.
"""

import json
import os
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PYTEST_CURRENT_TEST"] = "1"

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTreeWidget, QTreeWidgetItem

_app = QApplication.instance() or QApplication([])

from ui.navigation_permissions import (
    NAVIGATION_PERMISSION_FALLBACKS,
    has_navigation_permission,
    has_permission,
)
from ui.widgets.users.user_management_tab import SYSTEM_PERMISSIONS, UserDialog
from ui.widgets.appliance_desks.appliance_workflow_tab import ApplianceWorkflowTab
from ui.widgets.sav.sav_workspace_view import SAVWorkspaceTab
from ui.widgets.appliance_desks.cashier_desk_view import CashierDeskWidget, AdminAuthModal
from ui.widgets.appliance_desks.order_desk_view import OrderDeskWidget
from ui.widgets.appliance_desks.dispatch_desk_view import DispatchDeskWidget


class UserPermissionsDefinitionTests(unittest.TestCase):
    """Verifies that all new operational desks and SAV permissions exist in SYSTEM_PERMISSIONS."""

    def test_bureaux_workflow_group_exists(self):
        self.assertIn("10. BUREAUX_WORKFLOW", SYSTEM_PERMISSIONS)
        group = SYSTEM_PERMISSIONS["10. BUREAUX_WORKFLOW"]
        self.assertIn("Bureaux & Workflow", group["label"])
        self.assertIn("perms", group)
        perms = group["perms"]

        expected_perms = [
            "nav_appliance_workflow",
            "tab_desk_order",
            "tab_desk_caisse",
            "tab_desk_dispatch",
            "act_order_create",
            "act_caisse_settle",
            "act_caisse_bon_credit_auth",
            "act_caisse_versement",
            "act_caisse_bon_retour",
            "act_dispatch_validate",
        ]
        for p in expected_perms:
            self.assertIn(p, perms, f"Missing permission {p} in 10. BUREAUX_WORKFLOW")

    def test_sav_workspace_group_exists(self):
        self.assertIn("11. SAV_WORKSPACE", SYSTEM_PERMISSIONS)
        group = SYSTEM_PERMISSIONS["11. SAV_WORKSPACE"]
        self.assertIn("Service Après-Vente", group["label"])
        self.assertIn("perms", group)
        perms = group["perms"]

        expected_perms = [
            "nav_sav",
            "tab_desk_sav",
            "act_sav_ticket_create",
            "act_sav_dispatch_tech",
            "act_sav_return_tech",
            "act_sav_deliver_client",
            "act_sav_declare_irreparable",
        ]
        for p in expected_perms:
            self.assertIn(p, perms, f"Missing permission {p} in 11. SAV_WORKSPACE")

    def test_tracabilite_group_contains_serial_registry(self):
        self.assertIn("7. TRACABILITE", SYSTEM_PERMISSIONS)
        perms = SYSTEM_PERMISSIONS["7. TRACABILITE"]["perms"]
        self.assertIn("tab_serial_registry", perms)
        self.assertIn("act_serial_audit", perms)


class UserDialogTreeAndRoleTests(unittest.TestCase):
    """Verifies UserDialog permissions tree structure and role default behavior."""

    def setUp(self):
        self.dialog = UserDialog()

    def tearDown(self):
        self.dialog.close()

    def test_tree_natural_order(self):
        """Checks that groups 10 and 11 appear after group 9, not after group 1."""
        top_labels = []
        for i in range(self.dialog.tree_perms.topLevelItemCount()):
            top_labels.append(self.dialog.tree_perms.topLevelItem(i).text(0))

        # Find indexes
        idx_dashboard = next(i for i, text in enumerate(top_labels) if "Tableau de Bord" in text)
        idx_settings = next(i for i, text in enumerate(top_labels) if "Paramètres" in text)
        idx_bureaux = next(i for i, text in enumerate(top_labels) if "Bureaux & Workflow" in text)
        idx_sav = next(i for i, text in enumerate(top_labels) if "Service Après-Vente" in text)

        self.assertLess(idx_dashboard, idx_settings)
        self.assertLess(idx_settings, idx_bureaux)
        self.assertLess(idx_bureaux, idx_sav)

    def test_admin_role_grants_all_new_permissions(self):
        self.dialog.role_combo.setCurrentText("Administrateur")
        perms = self.dialog.get_selected_permissions()

        self.assertTrue(perms.get("nav_appliance_workflow"))
        self.assertTrue(perms.get("tab_desk_order"))
        self.assertTrue(perms.get("tab_desk_caisse"))
        self.assertTrue(perms.get("tab_desk_dispatch"))
        self.assertTrue(perms.get("act_order_create"))
        self.assertTrue(perms.get("act_caisse_settle"))
        self.assertTrue(perms.get("act_caisse_bon_credit_auth"))
        self.assertTrue(perms.get("act_caisse_versement"))
        self.assertTrue(perms.get("act_caisse_bon_retour"))
        self.assertTrue(perms.get("act_dispatch_validate"))
        self.assertTrue(perms.get("nav_sav"))
        self.assertTrue(perms.get("tab_desk_sav"))
        self.assertTrue(perms.get("act_sav_ticket_create"))
        self.assertTrue(perms.get("act_sav_dispatch_tech"))
        self.assertTrue(perms.get("act_sav_return_tech"))
        self.assertTrue(perms.get("act_sav_deliver_client"))
        self.assertTrue(perms.get("act_sav_declare_irreparable"))
        self.assertTrue(perms.get("tab_serial_registry"))

    def test_responsable_role_grants_operational_workflow(self):
        self.dialog.role_combo.setCurrentText("Responsable")
        perms = self.dialog.get_selected_permissions()

        self.assertTrue(perms.get("nav_appliance_workflow"))
        self.assertTrue(perms.get("tab_desk_caisse"))
        self.assertTrue(perms.get("act_caisse_bon_credit_auth"))
        self.assertTrue(perms.get("nav_sav"))
        self.assertTrue(perms.get("act_sav_declare_irreparable"))

    def test_technicien_role_grants_targeted_workflow(self):
        self.dialog.role_combo.setCurrentText("Technicien")
        perms = self.dialog.get_selected_permissions()

        self.assertTrue(perms.get("nav_appliance_workflow"))
        self.assertTrue(perms.get("tab_desk_order"))
        self.assertTrue(perms.get("act_order_create"))
        self.assertTrue(perms.get("tab_desk_dispatch"))
        self.assertTrue(perms.get("act_dispatch_validate"))
        self.assertTrue(perms.get("nav_sav"))
        self.assertTrue(perms.get("tab_desk_sav"))
        self.assertTrue(perms.get("act_sav_ticket_create"))
        self.assertTrue(perms.get("act_sav_return_tech"))
        # Should not have admin caisse authorize
        self.assertFalse(perms.get("act_caisse_bon_credit_auth", False))

    def test_set_and_get_permissions_roundtrip(self):
        custom_perms = {
            "nav_appliance_workflow": True,
            "tab_desk_order": True,
            "act_order_create": True,
            "nav_sav": True,
            "act_sav_ticket_create": True,
        }
        self.dialog.set_permissions(custom_perms)
        selected = self.dialog.get_selected_permissions()

        self.assertTrue(selected.get("nav_appliance_workflow"))
        self.assertTrue(selected.get("tab_desk_order"))
        self.assertTrue(selected.get("act_order_create"))
        self.assertTrue(selected.get("nav_sav"))
        self.assertTrue(selected.get("act_sav_ticket_create"))
        self.assertFalse(selected.get("tab_desk_caisse", False))
        self.assertFalse(selected.get("tab_desk_dispatch", False))


class NavigationFallbackTests(unittest.TestCase):
    """Verifies that navigation permissions resolve correctly for new desks."""

    def test_nav_appliance_workflow_fallback_from_order_desk(self):
        user = {"Permissions": {"tab_desk_order": True}}
        self.assertTrue(has_navigation_permission(user, "nav_appliance_workflow"))

    def test_nav_appliance_workflow_fallback_from_caisse(self):
        user = {"Permissions": {"act_caisse_settle": True}}
        self.assertTrue(has_navigation_permission(user, "nav_appliance_workflow"))

    def test_nav_appliance_workflow_fallback_from_dispatch(self):
        user = {"Permissions": {"act_dispatch_validate": True}}
        self.assertTrue(has_navigation_permission(user, "nav_appliance_workflow"))

    def test_nav_sav_fallback_from_ticket_create(self):
        user = {"Permissions": {"act_sav_ticket_create": True}}
        self.assertTrue(has_navigation_permission(user, "nav_sav"))

    def test_nav_sav_explicit_deny_respected(self):
        user = {"Permissions": {"nav_sav": False, "act_sav_ticket_create": True}}
        self.assertFalse(has_navigation_permission(user, "nav_sav"))


class ApplianceWorkflowRBACDeskGatingTests(unittest.TestCase):
    """Verifies desk tab enabling/disabling in ApplianceWorkflowTab based on RBAC permissions."""

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

    def test_admin_permissions_enable_all_desks(self):
        widget = ApplianceWorkflowTab(
            db_manager=self.mock_db,
            user_permissions={"admin"},
            include_sav=False,
        )
        self.assertTrue(widget.desk_tabs.isTabEnabled(0))  # Order Desk
        self.assertTrue(widget.desk_tabs.isTabEnabled(1))  # Caisse Desk
        self.assertTrue(widget.desk_tabs.isTabEnabled(2))  # Dispatch Desk
        widget.deleteLater()

    def test_order_desk_only_permission(self):
        widget = ApplianceWorkflowTab(
            db_manager=self.mock_db,
            user_permissions={"nav_appliance_workflow", "tab_desk_order", "act_order_create"},
            include_sav=False,
        )
        self.assertTrue(widget.desk_tabs.isTabEnabled(0))
        self.assertFalse(widget.desk_tabs.isTabEnabled(1))
        self.assertFalse(widget.desk_tabs.isTabEnabled(2))
        widget.deleteLater()

    def test_caisse_desk_only_permission(self):
        widget = ApplianceWorkflowTab(
            db_manager=self.mock_db,
            user_permissions={"nav_appliance_workflow", "tab_desk_caisse", "act_caisse_settle"},
            include_sav=False,
        )
        self.assertFalse(widget.desk_tabs.isTabEnabled(0))
        self.assertTrue(widget.desk_tabs.isTabEnabled(1))
        self.assertFalse(widget.desk_tabs.isTabEnabled(2))
        widget.deleteLater()

    def test_dispatch_desk_only_permission(self):
        widget = ApplianceWorkflowTab(
            db_manager=self.mock_db,
            user_permissions={"nav_appliance_workflow", "tab_desk_dispatch", "act_dispatch_validate"},
            include_sav=False,
        )
        self.assertFalse(widget.desk_tabs.isTabEnabled(0))
        self.assertFalse(widget.desk_tabs.isTabEnabled(1))
        self.assertTrue(widget.desk_tabs.isTabEnabled(2))
        widget.deleteLater()


class SAVWorkspaceGatingTests(unittest.TestCase):
    """Verifies that SAVWorkspaceTab respects granular permissions for intake and stage actions."""

    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_db.sav = MagicMock()
        self.mock_db.sav.get_all_sav_tickets.return_value = []
        self.mock_db.sav.get_tickets_summary_counts.return_value = {}

    def test_sav_ticket_create_permission_gating(self):
        # User without intake permission
        user_no_intake = {
            "Role": "Technician",
            "Permissions": {"nav_sav": True, "act_sav_ticket_create": False},
        }
        tab_no = SAVWorkspaceTab(data_manager=self.mock_db, current_user=user_no_intake)
        self.assertFalse(tab_no.btn_intake.isEnabled())
        tab_no.deleteLater()

        # User with intake permission
        user_with_intake = {
            "Role": "Technician",
            "Permissions": {"nav_sav": True, "act_sav_ticket_create": True},
        }
        tab_yes = SAVWorkspaceTab(data_manager=self.mock_db, current_user=user_with_intake)
        self.assertTrue(tab_yes.btn_intake.isEnabled())
        tab_yes.deleteLater()

    def test_sav_stage_action_buttons_gating(self):
        ticket = {
            "SAV_Ticket_ID": 101,
            "Ticket_Number": "SAV-101",
            "Current_Stage": "SAV_RECEIVED",
            "Resolution_Status": "PENDING",
            "Client_Name": "Client Test",
            "Product_Name": "Appareil Test",
            "Reception_Date": "2026-11-06 10:00:00",
        }
        self.mock_db.sav.get_all_sav_tickets.return_value = [ticket]

        # User has ticket create but lacks dispatch tech
        user = {
            "Role": "Technician",
            "Permissions": {
                "nav_sav": True,
                "act_sav_ticket_create": True,
                "act_sav_dispatch_tech": False,
                "act_sav_declare_irreparable": False,
            },
        }
        tab = SAVWorkspaceTab(data_manager=self.mock_db, current_user=user)
        table = tab._stage_tables["SAV_RECEIVED"]
        self.assertEqual(table.rowCount(), 1)

        act_widget = table.cellWidget(0, 9)
        self.assertIsNotNone(act_widget)
        # Find "Envoi Atelier" and "Irréparable" buttons
        buttons = act_widget.findChildren(type(tab.btn_intake))
        btn_envoi = next((b for b in buttons if "Envoi Atelier" in b.text()), None)
        btn_irrep = next((b for b in buttons if "Irréparable" in b.text()), None)

        self.assertIsNotNone(btn_envoi)
        self.assertFalse(btn_envoi.isEnabled())
        self.assertIsNotNone(btn_irrep)
        self.assertFalse(btn_irrep.isEnabled())
        tab.deleteLater()


class CashierAndDeskActionGatingTests(unittest.TestCase):
    """Verifies that CashierDeskWidget, OrderDeskWidget, and DispatchDeskWidget enforce action permissions."""

    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_db.bonds = MagicMock()
        self.mock_db.bonds.get_caisse_pending_orders.return_value = []
        self.mock_db.bonds.get_dispatch_pending_orders.return_value = []
        self.mock_db.products = MagicMock()
        self.mock_db.products.get_all_products.return_value = []
        self.mock_db.manufacturers = MagicMock()
        self.mock_db.manufacturers.get_all_manufacturers.return_value = []
        self.mock_db.families = MagicMock()
        self.mock_db.families.get_all_families.return_value = []

    def test_admin_auth_modal_authorizes_supervisor_with_permission(self):
        mock_users = MagicMock()
        supervisor_user = {
            "User_ID": 42,
            "Role": "Responsable",
            "Permissions": {"act_caisse_bon_credit_auth": True},
        }
        mock_users.authenticate.return_value = supervisor_user
        self.mock_db.users = mock_users

        modal = AdminAuthModal(
            client_name="Client Test",
            requested_amount=15000.0,
            data_manager=self.mock_db,
        )
        modal.txt_admin_user.setText("responsable1")
        modal.txt_pin.setText("pass123")
        modal._verify_credentials()

        self.assertTrue(modal.approved)
        self.assertEqual(modal.admin_user_id, 42)
        modal.deleteLater()

    def test_caisse_settle_permission_blocks_unauthorized_user(self):
        user_no_settle = {
            "User_ID": 5,
            "Role": "Technician",
            "Permissions": {"act_caisse_settle": False},
        }
        self.mock_db.current_user = user_no_settle
        widget = CashierDeskWidget(data_manager=self.mock_db)

        with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn:
            widget._finalize_bon_c()
            mock_warn.assert_called_once()
            self.assertIn("autorisation", str(mock_warn.call_args))

        widget.deleteLater()

    def test_caisse_versement_permission_blocks_unauthorized_user(self):
        user_no_versement = {
            "User_ID": 5,
            "Role": "Technician",
            "Permissions": {"act_caisse_versement": False},
        }
        self.mock_db.current_user = user_no_versement
        widget = CashierDeskWidget(data_manager=self.mock_db)

        with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn:
            widget._open_versement_dialog()
            mock_warn.assert_called_once()
            self.assertIn("autorisation", str(mock_warn.call_args))

        widget.deleteLater()

    def test_order_desk_submit_blocks_unauthorized_user(self):
        user_no_create = {
            "User_ID": 8,
            "Role": "Technician",
            "Permissions": {"act_order_create": False},
        }
        self.mock_db.current_user = user_no_create
        widget = OrderDeskWidget(data_manager=self.mock_db)

        with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn:
            widget._submit_order("BON_C")
            mock_warn.assert_called_once()
            self.assertIn("autorisation", str(mock_warn.call_args))

        widget.deleteLater()

    def test_dispatch_desk_emit_sortie_blocks_unauthorized_user(self):
        user_no_dispatch = {
            "User_ID": 9,
            "Role": "Technician",
            "Permissions": {"act_dispatch_validate": False},
        }
        self.mock_db.current_user = user_no_dispatch
        widget = DispatchDeskWidget(data_manager=self.mock_db)

        with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn:
            widget._emit_bon_sortie()
            mock_warn.assert_called_once()
            self.assertIn("autorisation", str(mock_warn.call_args))

        widget.deleteLater()


if __name__ == "__main__":
    unittest.main()
