# -*- coding: utf-8 -*-
"""
ui/widgets/appliance_desks/appliance_workflow_tab.py
====================================================
Unified Multi-Desk Operational Workflow Hub:
1. Bureau des Commandes (Order Desk) - Theoretical orders & Multi-Scanner / Multi-Session
2. Bureau Caisse (Caisse Desk) - Bon C, Bon Crédit (Admin Auth), Bon de Livraison, Versement, Bon de Retour
3. Bureau de Sortie (Dispatch Desk) - Physical barcode & N° de Série scanning -> Bon de Sortie
4. Service Après-Vente (SAV / Réparation) - 4-stage pipeline & Irreparable Versement Virtuel
5. Lots & N° de Série (Batches & Serials) - Mark, Name, Categorie, Coloure, Batch Serials
"""

import logging
from typing import Optional, Set

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ui.hardware.raw_input_filter import MultiScannerHIDManager
from ui.icons import get_duotone_icon
from ui.widgets.appliance_desks.cashier_desk_view import CashierDeskWidget
from ui.widgets.appliance_desks.dispatch_desk_view import DispatchDeskWidget
from ui.widgets.appliance_desks.order_desk_view import OrderDeskWidget
from ui.widgets.appliance_desks.sav_kanban_view import SAVKanbanWidget

logger = logging.getLogger(__name__)


class ApplianceWorkflowTab(QWidget):
    """
    Main Operational Workflow Container connecting Order Desk, Caisse, Dispatch Desk,
    SAV 4-Stage Pipeline, and Product/Batch Serial Registry with RBAC enforcement
    and Multi-Scanner HID routing.
    """

    def __init__(
        self,
        db_manager=None,
        data_manager=None,
        user_manager=None,
        current_user_id: int = 1,
        user_permissions: Optional[Set[str]] = None,
        hid_manager: Optional[MultiScannerHIDManager] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.data_manager = data_manager or db_manager
        self.db_manager = self.data_manager
        self.user_manager = user_manager or getattr(self.data_manager, "users", None)
        self.current_user_id = current_user_id
        self.user_permissions = user_permissions
        self.hid_manager = hid_manager or MultiScannerHIDManager()

        self.setObjectName("ApplianceWorkflowTab")
        self.setStyleSheet("QWidget#ApplianceWorkflowTab { background-color: #F4F6F8; }")
        self._build_ui()
        self._connect_cross_desk_signals()
        self.apply_rbac_permissions(self.user_permissions)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Top Compact Enterprise Header Bar
        banner_frame = QFrame()
        banner_frame.setObjectName("WorkflowBannerFrame")
        banner_frame.setFixedHeight(46)
        banner_frame.setStyleSheet("""
            QFrame#WorkflowBannerFrame {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        banner_layout = QHBoxLayout(banner_frame)
        banner_layout.setContentsMargins(14, 0, 14, 0)
        banner_layout.setSpacing(10)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_duotone_icon("pos", 20).pixmap(20, 20))
        banner_layout.addWidget(icon_lbl)

        title_lbl = QLabel(
            "Flux Opérationnel Multi-Bureaux  |  Commandes  •  Caisse  •  Sortie Magasin  •  SAV & Réparation"
        )
        title_lbl.setStyleSheet("font-size: 13px; font-weight: 800; color: #1E293B;")
        banner_layout.addWidget(title_lbl)
        banner_layout.addStretch()

        self.refresh_all_btn = QPushButton("Actualiser les Bureaux")
        self.refresh_all_btn.setIcon(get_duotone_icon("refresh", 14))
        self.refresh_all_btn.setIconSize(QSize(14, 14))
        self.refresh_all_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_all_btn.setFixedHeight(32)
        self.refresh_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #0E7471;
                border: 1px solid #B2DFDB;
                border-radius: 6px;
                padding: 0 12px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #E6F4F1;
                border-color: #0E7471;
            }
        """)
        self.refresh_all_btn.clicked.connect(self.refresh_all_desks)
        banner_layout.addWidget(self.refresh_all_btn)
        layout.addWidget(banner_frame)

        # Sub-Desk Tabs
        self.desk_tabs = QTabWidget()
        self.desk_tabs.setIconSize(QSize(16, 16))
        self.desk_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #DDE3EA;
                background: #F4F6F8;
                border-radius: 6px;
                top: -1px;
            }
            QTabBar::tab {
                background: #ECEFF1;
                color: #475569;
                border: 1px solid #DDE3EA;
                border-bottom: none;
                padding: 7px 12px;
                margin-right: 3px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-size: 12px;
                font-weight: 700;
            }
            QTabBar::tab:selected {
                background: #FFFFFF;
                color: #0E7471;
                border-top: 3px solid #0E7471;
            }
            QTabBar::tab:hover:!selected {
                background: #E2E8F0;
                color: #1E293B;
            }
        """)

        self.order_desk = OrderDeskWidget(
            data_manager=self.data_manager,
            hid_manager=self.hid_manager,
            parent=self,
        )
        self.cashier_desk = CashierDeskWidget(
            data_manager=self.data_manager,
            parent=self,
        )
        self.dispatch_desk = DispatchDeskWidget(
            data_manager=self.data_manager,
            hid_manager=self.hid_manager,
            parent=self,
        )
        self.sav_desk = SAVKanbanWidget(
            data_manager=self.data_manager,
            parent=self,
        )
        self.batch_registry_desk = None

        self.desk_tabs.addTab(
            self.order_desk,
            get_duotone_icon("pos", 18),
            "1. Commandes (Order Desk)",
        )
        self.desk_tabs.addTab(
            self.cashier_desk,
            get_duotone_icon("payment", 18),
            "2. Caisse && Règlements",
        )
        self.desk_tabs.addTab(
            self.dispatch_desk,
            get_duotone_icon("barcode_scan", 18),
            "3. Sortie Magasin (Dispatch)",
        )
        self.desk_tabs.addTab(
            self.sav_desk,
            get_duotone_icon("wrench_sav", 18),
            "4. Service Après-Vente (SAV)",
        )

        layout.addWidget(self.desk_tabs, 1)

    def _connect_cross_desk_signals(self) -> None:
        """Connect operational lifecycle transitions across desks in real time."""
        self.order_desk.bonCGenerated.connect(self._on_order_created)
        self.order_desk.bonCreditRequested.connect(self._on_order_created)
        self.order_desk.bonLivraisonGenerated.connect(self._on_order_created)
        self.cashier_desk.orderSettled.connect(self._on_caisse_settled)
        self.dispatch_desk.stockDispatched.connect(self._on_dispatch_completed)

    def _on_order_created(self, payload: dict) -> None:
        self.cashier_desk.refresh_queue()
        if self.batch_registry_desk:
            self.batch_registry_desk.refresh_products()

    def _on_caisse_settled(self, order_num: str, bond_type: str) -> None:
        self.dispatch_desk.refresh_dispatch_queue()
        self.order_desk.refresh_catalog()

    def _on_dispatch_completed(self, order_num: str, serials_list: list) -> None:
        self.order_desk.refresh_catalog()
        if self.batch_registry_desk:
            self.batch_registry_desk.refresh_products()
            if hasattr(self.batch_registry_desk, "refresh_traceability"):
                self.batch_registry_desk.refresh_traceability()

    def _on_catalog_updated(self) -> None:
        self.order_desk.refresh_catalog()
        if self.batch_registry_desk and hasattr(self.batch_registry_desk, "refresh_traceability"):
            self.batch_registry_desk.refresh_traceability()

    def refresh_all_desks(self) -> None:
        self.order_desk.refresh_catalog()
        self.cashier_desk.refresh_queue()
        self.dispatch_desk.refresh_dispatch_queue()
        self.sav_desk.refresh_tickets()
        if self.batch_registry_desk:
            self.batch_registry_desk.refresh_products()
            if hasattr(self.batch_registry_desk, "refresh_traceability"):
                self.batch_registry_desk.refresh_traceability()

    def apply_rbac_permissions(self, permissions: Optional[Set[str]] = None) -> None:
        """
        Restrict access to each desk tab according to the user's RBAC permissions
        (Order Desk, Caisse, Dispatch/Warehouse, SAV/Repair).
        """
        if permissions is None:
            return
        self.user_permissions = set(permissions)

        if "admin" in self.user_permissions or "*" in self.user_permissions:
            for idx in range(self.desk_tabs.count()):
                self.desk_tabs.setTabEnabled(idx, True)
            return

        desk_perm_rules = [
            (0, {"ORDER_DESK_CREATE", "desk.order.create_bon_c", "desk.order.create_bon_livraison", "desk.order.request_bon_credit", "nav_sales"}),
            (1, {"CAISSE_SETTLE_CASH", "CREDIT_ADMIN_AUTHORIZE", "RETURN_BOND_PROCESS", "desk.cashier.settle_bon_c", "desk.cashier.record_versement", "desk.cashier.issue_bon_retour", "nav_treasury"}),
            (2, {"DISPATCH_SCAN_SERIAL", "desk.dispatch.scan_serial_out", "desk.dispatch.print_bon_sortie", "nav_inventory"}),
            (3, {"SAV_MANAGE_STAGES", "SAV_IRREPARABLE_CREDIT", "desk.sav.receive_item", "desk.sav.send_to_repairer", "desk.sav.return_from_repairer", "desk.sav.deliver_to_client"}),
        ]

        any_specific_perm = any(
            bool(self.user_permissions & rule_perms) for _, rule_perms in desk_perm_rules
        )
        if not any_specific_perm:
            return

        first_enabled = None
        for tab_idx, allowed_set in desk_perm_rules:
            allowed = bool(self.user_permissions & allowed_set)
            self.desk_tabs.setTabEnabled(tab_idx, allowed)
            if allowed and first_enabled is None:
                first_enabled = tab_idx

        if first_enabled is not None and not self.desk_tabs.isTabEnabled(self.desk_tabs.currentIndex()):
            self.desk_tabs.setCurrentIndex(first_enabled)
