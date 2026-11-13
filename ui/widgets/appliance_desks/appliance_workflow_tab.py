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
from ui.widgets.appliance_desks._theme import (
    BORDER_CONTROL,
    BORDER_SUBTLE,
    BRAND_TEAL,
    CANVAS_BG,
    CARD_BG,
    PRIMARY_CTA_QSS,
    SUBTLE_BG,
    TEXT_BODY,
    TEXT_PRIMARY,
)
from ui.widgets.appliance_desks.cashier_desk_view import CashierDeskWidget
from ui.widgets.appliance_desks.dispatch_desk_view import DispatchDeskWidget
from ui.widgets.appliance_desks.order_desk_view import OrderDeskWidget
from ui.widgets.sav.sav_kanban_view import SAVKanbanWidget

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
        include_sav: bool = False,
    ):
        super().__init__(parent)
        self.include_sav = include_sav
        self.data_manager = data_manager or db_manager
        self.db_manager = self.data_manager
        self.user_manager = user_manager or getattr(self.data_manager, "users", None)
        self.current_user_id = current_user_id
        self.user_permissions = user_permissions
        self.hid_manager = hid_manager or MultiScannerHIDManager()

        self.setObjectName("ApplianceWorkflowTab")
        self.setStyleSheet(f"QWidget#ApplianceWorkflowTab {{ background-color: {CANVAS_BG}; }}")
        self._build_ui()
        self._connect_cross_desk_signals()
        self._sync_desk_tab_badges()
        self.apply_rbac_permissions(self.user_permissions)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(0)

        # Flat underline sub-desk tabs matching global/SAV clean aesthetic
        self.desk_tabs = QTabWidget(self)
        self.desk_tabs.setDocumentMode(True)
        self.desk_tabs.setIconSize(QSize(16, 16))
        self.desk_tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                border-top: 1px solid #DCDFE6;
                background: {CARD_BG};
                top: -1px;
                padding-top: 6px;
            }}
            QTabBar::tab {{
                background: transparent;
                color: {TEXT_BODY};
                border: none;
                border-bottom: 2px solid transparent;
                padding: 8px 16px;
                margin-right: 6px;
                font-size: 12.5px;
                font-weight: 700;
                min-height: 20px;
            }}
            QTabBar::tab:selected {{
                background: transparent;
                color: {BRAND_TEAL};
                border-bottom: 2px solid {BRAND_TEAL};
            }}
            QTabBar::tab:hover:!selected {{
                background: {SUBTLE_BG};
                color: {TEXT_PRIMARY};
                border-bottom: 2px solid #CED4DA;
            }}
        """)

        corner_frame = QWidget(self.desk_tabs)
        corner_frame.setObjectName("WorkflowCornerWidget")
        corner_frame.setStyleSheet("background: transparent; border: none; border-color: #DCDFE6;")
        corner_layout = QHBoxLayout(corner_frame)
        corner_layout.setContentsMargins(0, 0, 2, 5)
        corner_layout.setSpacing(6)

        self.refresh_all_btn = QPushButton("Actualiser")
        self.refresh_all_btn.setIcon(get_duotone_icon("refresh_white", 13))
        self.refresh_all_btn.setIconSize(QSize(13, 13))
        self.refresh_all_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_all_btn.setFixedHeight(30)
        self.refresh_all_btn.setToolTip("Actualiser tous les bureaux (Commandes, Caisse, Sortie Magasin)")
        self.refresh_all_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {BRAND_TEAL};
                color: #FFFFFF;
                font-weight: 700;
                border: none;
                border-radius: 4px;
                padding: 0 14px;
                font-size: 11.5px;
            }}
            QPushButton:hover {{ background-color: #005A57; }}
            QPushButton:pressed {{ background-color: #003D3A; }}
        """)
        self.refresh_all_btn.clicked.connect(self.refresh_all_desks)
        corner_layout.addWidget(self.refresh_all_btn)
        self.desk_tabs.setCornerWidget(corner_frame, Qt.TopRightCorner)

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
        self.batch_registry_desk = None

        self.desk_tabs.addTab(
            self.order_desk,
            get_duotone_icon("pos", 18),
            "1. Commandes",
        )
        self.desk_tabs.addTab(
            self.cashier_desk,
            get_duotone_icon("payment", 18),
            "2. Caisse",
        )
        self.desk_tabs.addTab(
            self.dispatch_desk,
            get_duotone_icon("barcode_scan", 18),
            "3. Sortie Magasin",
        )
        if getattr(self, "include_sav", False):
            self.sav_desk = SAVKanbanWidget(
                data_manager=self.data_manager,
                parent=self,
            )
            self.desk_tabs.addTab(
                self.sav_desk,
                get_duotone_icon("wrench_sav", 18),
                "4. Service Après-Vente (SAV)",
            )
        else:
            self.sav_desk = None

        layout.addWidget(self.desk_tabs, 1)

    def _connect_cross_desk_signals(self) -> None:
        """Connect operational lifecycle transitions across desks in real time."""
        self.order_desk.bonCGenerated.connect(self._on_order_created)
        self.order_desk.bonCreditRequested.connect(self._on_order_created)
        self.order_desk.bonLivraisonGenerated.connect(self._on_order_created)
        self.cashier_desk.orderSettled.connect(self._on_caisse_settled)
        if hasattr(self.cashier_desk, "queueUpdated"):
            self.cashier_desk.queueUpdated.connect(self._sync_desk_tab_badges)
        self.dispatch_desk.stockDispatched.connect(self._on_dispatch_completed)
        self.desk_tabs.currentChanged.connect(self._on_desk_tab_changed)

    def _on_desk_tab_changed(self, idx: int) -> None:
        w = self.desk_tabs.widget(idx)
        if w is self.cashier_desk:
            self._sync_desk_tab_badges()
            if hasattr(self.cashier_desk, "txt_scan_bon"):
                self.cashier_desk.txt_scan_bon.setFocus()
        elif w is self.dispatch_desk and hasattr(self.dispatch_desk, "txt_scan"):
            self._sync_desk_tab_badges()
            self.dispatch_desk.txt_scan.setFocus()

    def _sync_desk_tab_badges(self) -> None:
        """Displays live pending counts directly on Caisse and Sortie Magasin tab labels."""
        if not hasattr(self, "desk_tabs"):
            return
        c_count = len(getattr(self.cashier_desk, "_orders_queue", []) or [])
        c_idx = self.desk_tabs.indexOf(self.cashier_desk)
        if c_idx >= 0:
            self.desk_tabs.setTabText(c_idx, f"2. Caisse ({c_count})" if c_count > 0 else "2. Caisse")

        d_count = len(getattr(self.dispatch_desk, "_all_dispatch_orders", getattr(self.dispatch_desk, "_dispatch_orders", [])) or [])
        d_idx = self.desk_tabs.indexOf(self.dispatch_desk)
        if d_idx >= 0:
            self.desk_tabs.setTabText(d_idx, f"3. Sortie Magasin ({d_count})" if d_count > 0 else "3. Sortie Magasin")

    def _on_order_created(self, payload: dict) -> None:
        self.cashier_desk.refresh_queue()
        if self.batch_registry_desk:
            self.batch_registry_desk.refresh_products()
        self._sync_desk_tab_badges()

    def _on_caisse_settled(self, order_num: str, bond_type: str) -> None:
        self.dispatch_desk.refresh_dispatch_queue()
        self.order_desk.refresh_catalog()
        self._sync_desk_tab_badges()

    def _on_dispatch_completed(self, order_num: str, serials_list: list) -> None:
        self.order_desk.refresh_catalog()
        if self.batch_registry_desk:
            self.batch_registry_desk.refresh_products()
            if hasattr(self.batch_registry_desk, "refresh_traceability"):
                self.batch_registry_desk.refresh_traceability()
        self._sync_desk_tab_badges()

    def _on_catalog_updated(self) -> None:
        self.order_desk.refresh_catalog()
        if self.batch_registry_desk and hasattr(self.batch_registry_desk, "refresh_traceability"):
            self.batch_registry_desk.refresh_traceability()

    def refresh_all_desks(self) -> None:
        self.order_desk.refresh_catalog()
        self.cashier_desk.refresh_queue()
        self.dispatch_desk.refresh_dispatch_queue()
        if getattr(self, "sav_desk", None) is not None:
            self.sav_desk.refresh_tickets()
        if self.batch_registry_desk:
            self.batch_registry_desk.refresh_products()
            if hasattr(self.batch_registry_desk, "refresh_traceability"):
                self.batch_registry_desk.refresh_traceability()
        self._sync_desk_tab_badges()

    def apply_rbac_permissions(self, permissions: Optional[Set[str]] = None) -> None:
        """
        Restrict access to each desk tab according to the user's tab permissions
        (tab_desk_order, tab_desk_caisse, tab_desk_dispatch).
        """
        if permissions is None:
            return
        self.user_permissions = set(permissions)

        if "admin" in self.user_permissions or "*" in self.user_permissions:
            for idx in range(self.desk_tabs.count()):
                self.desk_tabs.setTabEnabled(idx, True)
                self.desk_tabs.setTabVisible(idx, True)
            return

        desk_perm_rules = [
            (0, {"tab_desk_order"}),
            (1, {"tab_desk_caisse"}),
            (2, {"tab_desk_dispatch"}),
        ]
        if getattr(self, "include_sav", False) and getattr(self, "sav_desk", None) is not None:
            desk_perm_rules.append((3, {"tab_desk_sav", "nav_sav"}))

        first_enabled = None
        for tab_idx, allowed_set in desk_perm_rules:
            allowed = bool(self.user_permissions & allowed_set)
            self.desk_tabs.setTabEnabled(tab_idx, allowed)
            self.desk_tabs.setTabVisible(tab_idx, allowed)
            if allowed and first_enabled is None:
                first_enabled = tab_idx

        if first_enabled is not None and not self.desk_tabs.isTabEnabled(self.desk_tabs.currentIndex()):
            self.desk_tabs.setCurrentIndex(first_enabled)
