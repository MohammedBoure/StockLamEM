# -*- coding: utf-8 -*-
"""
ui/widgets/appliance_desks/sav_workspace_view.py
=================================================
Dedicated Multi-Tab Service Après-Vente (SAV) & Réparations Workspace.
Separates each repair ticket status (حالة طلب) into its own full-screen dedicated tab:
  - Tab 0: 📋 Toutes les Demandes (Global overview)
  - Tab 1: 📥 1. Réception Client (Dépôt) [SAV_RECEIVED]
  - Tab 2: 🔧 2. En Atelier / Réparateur [SAV_SENT_TO_TECH]
  - Tab 3: ✅ 3. Prêt pour Restitution [SAV_RETURNED_FROM_TECH]
  - Tab 4: 📦 4. Clôturés & Livrés [SAV_CLOSED_DELIVERED]
  - Tab 5: ⚠️ 5. Appareils Irréparables [IRREPARABLE_COMPENSATED]
"""

from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.formatting import format_money
from ui.icons import get_duotone_icon
from .sav_kanban_view import IrreparableDefectModal, SAVReceptionDialog

logger = logging.getLogger("StockLamPlus.SAVWorkspace")

TABLE_STYLE = """
    QTableWidget {
        background-color: #FFFFFF;
        border: 1px solid #CBD5E1;
        border-radius: 6px;
        gridline-color: #F1F5F9;
        font-size: 11px;
        color: #1E293B;
        selection-background-color: #E6F4F1;
        selection-color: #007572;
    }
    QHeaderView::section {
        background-color: #F8FAFC;
        color: #334155;
        font-size: 11px;
        font-weight: 700;
        border: none;
        border-bottom: 2px solid #007572;
        border-right: 1px solid #E2E8F0;
        padding: 6px 8px;
    }
"""


class ActionCellWidget(QWidget):
    """Container widget embedding stage-specific action buttons cleanly inside table cells."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(4, 2, 4, 2)
        self.layout.setSpacing(6)
        self.layout.setAlignment(Qt.AlignCenter)

    def add_action_button(self, text: str, color: str, callback, tooltip: str = "") -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(28)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip(tooltip or text)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #FFFFFF;
                color: {color};
                border: 1.2px solid {color};
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {color};
                color: #FFFFFF;
            }}
            QPushButton:pressed {{
                background-color: {color};
            }}
        """)
        btn.clicked.connect(callback)
        self.layout.addWidget(btn)
        return btn


class SAVWorkspaceTab(QWidget):
    """
    Dedicated Multi-Tab Workspace for After-Sales Service & Repair (SAV / Réparation).
    Decoupled from Bureaux into its own dedicated Left Navigation Bar button.
    Provides a separate full-screen tab for each ticket status.
    """

    ticketUpdated = Signal(int, str)

    def __init__(self, data_manager=None, current_user=None, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.current_user = current_user or {}
        self._all_tickets: List[Dict[str, Any]] = []
        self._stage_tables: Dict[str, QTableWidget] = {}
        self._stage_counts: Dict[str, int] = {}

        self.setObjectName("SAVWorkspaceTabRoot")
        self.setStyleSheet("""
            QWidget#SAVWorkspaceTabRoot {
                background-color: #F4F6F8;
            }
            QTabWidget#SAVTabWidget::pane {
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                background-color: #FFFFFF;
                top: -1px;
            }
            QTabBar#SAVTabBar::tab {
                background-color: #E2E8F0;
                color: #475569;
                font-weight: 700;
                font-size: 11px;
                padding: 6px 14px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                border: 1px solid #CBD5E1;
                border-bottom: none;
                min-height: 26px;
            }
            QTabBar#SAVTabBar::tab:selected {
                background-color: #007572;
                color: #FFFFFF;
                border-color: #007572;
            }
            QTabBar#SAVTabBar::tab:hover:!selected {
                background-color: #CBD5E1;
                color: #1E293B;
            }
        """)

        self._init_ui()
        self.refresh_tickets()

    def _init_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        # 1. Top Header & Action Console
        top_bar = self._create_top_header()
        root_layout.addWidget(top_bar)

        # 2. Global KPI Summary Badges Bar
        kpi_bar = self._create_kpi_bar()
        root_layout.addWidget(kpi_bar)

        # 3. Main Multi-Tab Widget (One dedicated tab per request status)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("SAVTabWidget")
        self.tabs.tabBar().setObjectName("SAVTabBar")
        self.tabs.setIconSize(QSize(16, 16))

        self.tab_all = self._create_stage_tab_widget(None, "Toutes les Demandes SAV")
        self.tab_received = self._create_stage_tab_widget("SAV_RECEIVED", "1. Réception Client (Dépôt)")
        self.tab_sent_to_tech = self._create_stage_tab_widget("SAV_SENT_TO_TECH", "2. En Atelier / Réparateur")
        self.tab_returned = self._create_stage_tab_widget("SAV_RETURNED_FROM_TECH", "3. Prêt pour Restitution")
        self.tab_closed = self._create_stage_tab_widget("SAV_CLOSED_DELIVERED", "4. Clôturés & Livrés")
        self.tab_irreparable = self._create_stage_tab_widget("IRREPARABLE", "5. Appareils Irréparables")

        self.tabs.addTab(self.tab_all, get_duotone_icon("wrench_sav", 16), "📋 Toutes les Demandes")
        self.tabs.addTab(self.tab_received, get_duotone_icon("barcode_scan", 16), "📥 1. Réception (Dépôt)")
        self.tabs.addTab(self.tab_sent_to_tech, get_duotone_icon("services", 16), "🔧 2. En Atelier")
        self.tabs.addTab(self.tab_returned, get_duotone_icon("check_circle", 16), "✅ 3. Prêts Restitution")
        self.tabs.addTab(self.tab_closed, get_duotone_icon("truck_delivery", 16), "📦 4. Clôturés & Livrés")
        self.tabs.addTab(self.tab_irreparable, get_duotone_icon("alert_warning", 16), "⚠️ 5. Irréparables")

        root_layout.addWidget(self.tabs, 1)

    def _create_top_header(self) -> QWidget:
        header_card = QFrame()
        header_card.setObjectName("SAVHeaderCard")
        header_card.setFixedHeight(56)
        header_card.setStyleSheet("""
            QFrame#SAVHeaderCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #F0FDFA, stop:0.04 #FFFFFF, stop:0.96 #FFFFFF, stop:1 #F8FAFC);
                border: 1px solid #CBD5E1;
                border-left: 5px solid #007572;
                border-radius: 8px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(14, 0, 14, 0)
        h_layout.setSpacing(10)

        ico = QLabel()
        ico.setPixmap(get_duotone_icon("wrench_sav", 24).pixmap(24, 24))
        h_layout.addWidget(ico)

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        title_col.setAlignment(Qt.AlignVCenter)
        lbl_title = QLabel("Service Après-Vente (SAV) & Réparations")
        lbl_title.setStyleSheet("font-size: 13.5px; font-weight: 800; color: #007572;")
        lbl_sub = QLabel("Suivi rigoureux du cycle de vie des pannes, réparations et garanties par état de demande")
        lbl_sub.setStyleSheet("font-size: 10.5px; font-weight: 600; color: #64748B;")
        title_col.addWidget(lbl_title)
        title_col.addWidget(lbl_sub)
        h_layout.addLayout(title_col)

        h_layout.addStretch()

        # Instant search across all tickets
        self.txt_global_search = QLineEdit()
        self.txt_global_search.setPlaceholderText("Rechercher ticket, N° série, client, appareil...")
        self.txt_global_search.setClearButtonEnabled(True)
        self.txt_global_search.setFixedHeight(34)
        self.txt_global_search.setFixedWidth(260)
        self.txt_global_search.setStyleSheet("""
            QLineEdit {
                background-color: #FFFFFF;
                border: 1.5px solid #CBD5E1;
                border-radius: 6px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 600;
                color: #1E293B;
            }
            QLineEdit:focus {
                border-color: #007572;
            }
        """)
        self.txt_global_search.textChanged.connect(self._on_search_changed)
        h_layout.addWidget(self.txt_global_search)

        # Primary Action: Check-in defective product
        btn_intake = QPushButton("+ Réceptionner Appareil (Bon de Réparation)")
        btn_intake.setIcon(get_duotone_icon("wrench_sav", 16))
        btn_intake.setIconSize(QSize(16, 16))
        btn_intake.setCursor(Qt.PointingHandCursor)
        btn_intake.setFixedHeight(36)
        btn_intake.setStyleSheet("""
            QPushButton {
                background-color: #007572;
                color: #FFFFFF;
                font-weight: 700;
                font-size: 11.5px;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background-color: #005A57;
            }
            QPushButton:pressed {
                background-color: #003D3A;
            }
        """)
        btn_intake.clicked.connect(self._open_reception_dialog)
        h_layout.addWidget(btn_intake)

        # Refresh button
        btn_refresh = QPushButton("Actualiser")
        btn_refresh.setIcon(get_duotone_icon("refresh", 14))
        btn_refresh.setIconSize(QSize(14, 14))
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setFixedHeight(36)
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #007572;
                font-weight: 700;
                font-size: 11.5px;
                border: 1.5px solid #007572;
                border-radius: 6px;
                padding: 0 12px;
            }
            QPushButton:hover {
                background-color: #E6F4F1;
            }
        """)
        btn_refresh.clicked.connect(self.refresh_tickets)
        h_layout.addWidget(btn_refresh)

        return header_card

    def _create_kpi_bar(self) -> QWidget:
        kpi_frame = QFrame()
        kpi_frame.setFixedHeight(38)
        kpi_frame.setStyleSheet("QFrame { background: transparent; border: none; }")
        layout = QHBoxLayout(kpi_frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        def make_badge(title: str, color: str, bg: str, border: str) -> QLabel:
            lbl = QLabel(f"{title} : 0")
            lbl.setFixedHeight(32)
            lbl.setStyleSheet(f"""
                QLabel {{
                    background-color: {bg};
                    color: {color};
                    border: 1px solid {border};
                    border-radius: 6px;
                    padding: 0 12px;
                    font-size: 11px;
                    font-weight: 700;
                }}
            """)
            return lbl

        self.lbl_kpi_total = make_badge("Total Demandes", "#1E293B", "#FFFFFF", "#CBD5E1")
        self.lbl_kpi_received = make_badge("📥 En Dépôt", "#007572", "#E6F4F1", "#A7F3D0")
        self.lbl_kpi_sent = make_badge("🔧 En Atelier", "#D97706", "#FFFBEB", "#FDE68A")
        self.lbl_kpi_returned = make_badge("✅ Prêts Restitution", "#0284C7", "#F0F9FF", "#BAE6FD")
        self.lbl_kpi_closed = make_badge("📦 Clôturés", "#16A34A", "#F0FDF4", "#BBF7D0")
        self.lbl_kpi_irreparable = make_badge("⚠️ Irréparables (Avoir)", "#DC2626", "#FEF2F2", "#FECACA")

        layout.addWidget(self.lbl_kpi_total)
        layout.addWidget(self.lbl_kpi_received)
        layout.addWidget(self.lbl_kpi_sent)
        layout.addWidget(self.lbl_kpi_returned)
        layout.addWidget(self.lbl_kpi_closed)
        layout.addWidget(self.lbl_kpi_irreparable)
        layout.addStretch()

        return kpi_frame

    def _create_stage_tab_widget(self, stage_filter: Optional[str], stage_title: str) -> QWidget:
        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(10, 10, 10, 10)
        c_layout.setSpacing(8)

        # Table configuration
        table = QTableWidget(0, 10)
        table.setHorizontalHeaderLabels([
            "N° Ticket",
            "Code Bon",
            "Client",
            "Désignation Produit",
            "N° de Série",
            "Garantie",
            "Symptôme / Panne",
            "Technicien / Atelier",
            "Date Réception",
            "Actions",
        ])
        table.setStyleSheet(TABLE_STYLE)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(44)
        table.horizontalHeader().setFixedHeight(36)
        table.horizontalHeader().setMinimumSectionSize(40)
        table.setShowGrid(True)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        h = table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Interactive)
        table.setColumnWidth(0, 120)  # Ticket Number
        h.setSectionResizeMode(1, QHeaderView.Interactive)
        table.setColumnWidth(1, 120)  # Bon Barcode
        h.setSectionResizeMode(2, QHeaderView.Interactive)
        table.setColumnWidth(2, 140)  # Client
        h.setSectionResizeMode(3, QHeaderView.Interactive)
        table.setColumnWidth(3, 200)  # Product
        h.setSectionResizeMode(4, QHeaderView.Interactive)
        table.setColumnWidth(4, 130)  # Serial Number
        h.setSectionResizeMode(5, QHeaderView.Fixed)
        table.setColumnWidth(5, 105)  # Warranty badge
        h.setSectionResizeMode(6, QHeaderView.Interactive)
        table.setColumnWidth(6, 180)  # Symptom
        h.setSectionResizeMode(7, QHeaderView.Interactive)
        table.setColumnWidth(7, 130)  # Technician
        h.setSectionResizeMode(8, QHeaderView.Fixed)
        table.setColumnWidth(8, 100)  # Date
        h.setSectionResizeMode(9, QHeaderView.Fixed)
        table.setColumnWidth(9, 210)  # Actions

        c_layout.addWidget(table, 1)

        key = stage_filter or "ALL"
        self._stage_tables[key] = table
        return container

    def refresh_tickets(self) -> None:
        """Loads SAV tickets strictly from backend (no fake/mock fallback data) and refreshes all stage tables & KPIs."""
        tickets: List[Dict[str, Any]] = []
        if self.data_manager and hasattr(self.data_manager, "sav"):
            try:
                tickets = self.data_manager.sav.get_all_sav_tickets() or []
            except Exception as err:
                logger.error(f"Error fetching SAV tickets: {err}")
                tickets = []

        self._all_tickets = tickets
        self._update_all_stage_views()

    def _update_all_stage_views(self) -> None:
        """Filters tickets and updates all 6 stage table views along with counts & KPI badges."""
        search_txt = self.txt_global_search.text().strip().lower() if hasattr(self, "txt_global_search") else ""

        counts = {
            "ALL": 0,
            "SAV_RECEIVED": 0,
            "SAV_SENT_TO_TECH": 0,
            "SAV_RETURNED_FROM_TECH": 0,
            "SAV_CLOSED_DELIVERED": 0,
            "IRREPARABLE": 0,
        }

        for stage_key, table in self._stage_tables.items():
            filtered = []
            for t in self._all_tickets:
                stage = str(t.get("Current_Stage") or t.get("Status") or "")
                res = str(t.get("Resolution_Status") or t.get("Resolution") or "")

                is_irrep = "IRREPARABLE" in res or "SCRAPPED" in res or "IRREPARABLE" in stage
                matches_stage = False

                if stage_key == "ALL":
                    matches_stage = True
                elif stage_key == "IRREPARABLE":
                    matches_stage = is_irrep
                elif stage_key == stage and not is_irrep:
                    matches_stage = True

                if not matches_stage:
                    continue

                if search_txt:
                    num = str(t.get("Ticket_Number") or t.get("SAV_Ticket_ID") or t.get("Ticket_ID") or "").lower()
                    bon = str(t.get("Bon_Reparation_Barcode") or t.get("Bon_Number") or "").lower()
                    sn = str(t.get("Serial_Number") or "").lower()
                    prod = str(t.get("Product_Name") or "").lower()
                    client = str(t.get("Client_Name") or "").lower()
                    tech = str(t.get("Technician_Name") or "").lower()
                    symp = str(t.get("Customer_Stated_Symptom") or t.get("Reported_Defect") or "").lower()
                    if not any(search_txt in f for f in (num, bon, sn, prod, client, tech, symp)):
                        continue

                filtered.append(t)

            counts[stage_key] = len(filtered)
            self._populate_table(table, filtered, stage_key)

        self._stage_counts = counts

        # Update KPI Header Badges
        self.lbl_kpi_total.setText(f"Total Demandes : {len(self._all_tickets)}")
        self.lbl_kpi_received.setText(f"📥 En Dépôt : {counts.get('SAV_RECEIVED', 0)}")
        self.lbl_kpi_sent.setText(f"🔧 En Atelier : {counts.get('SAV_SENT_TO_TECH', 0)}")
        self.lbl_kpi_returned.setText(f"✅ Prêts Restitution : {counts.get('SAV_RETURNED_FROM_TECH', 0)}")
        self.lbl_kpi_closed.setText(f"📦 Clôturés : {counts.get('SAV_CLOSED_DELIVERED', 0)}")
        self.lbl_kpi_irreparable.setText(f"⚠️ Irréparables (Avoir) : {counts.get('IRREPARABLE', 0)}")

        # Update Tab Titles with Live Badges
        if hasattr(self, "tabs"):
            self.tabs.setTabText(0, f"📋 Toutes les Demandes ({counts.get('ALL', 0)})")
            self.tabs.setTabText(1, f"📥 1. Réception ({counts.get('SAV_RECEIVED', 0)})")
            self.tabs.setTabText(2, f"🔧 2. En Atelier ({counts.get('SAV_SENT_TO_TECH', 0)})")
            self.tabs.setTabText(3, f"✅ 3. Prêts Restitution ({counts.get('SAV_RETURNED_FROM_TECH', 0)})")
            self.tabs.setTabText(4, f"📦 4. Clôturés ({counts.get('SAV_CLOSED_DELIVERED', 0)})")
            self.tabs.setTabText(5, f"⚠️ 5. Irréparables ({counts.get('IRREPARABLE', 0)})")

    def _populate_table(self, table: QTableWidget, tickets: List[Dict[str, Any]], stage_context: str) -> None:
        table.setRowCount(0)
        table.setRowCount(len(tickets))

        for row, t in enumerate(tickets):
            t_num = str(t.get("Ticket_Number") or f"SAV-{t.get('SAV_Ticket_ID') or t.get('Ticket_ID')}")
            b_code = str(t.get("Bon_Reparation_Barcode") or t.get("Bon_Number") or f"BREP-{t.get('SAV_Ticket_ID') or t.get('Ticket_ID')}")
            client = str(t.get("Client_Name") or "Client SAV")
            prod = str(t.get("Product_Name") or "")
            brand = str(t.get("Brand_Mark") or "")
            sn = str(t.get("Serial_Number") or "")
            is_warr = bool(t.get("Is_Under_Warranty") or str(t.get("Warranty_Status")).upper() == "IN_WARRANTY")
            symp = str(t.get("Customer_Stated_Symptom") or t.get("Reported_Defect") or "")
            tech = str(t.get("Technician_Name") or "Non assigné")
            dt_raw = str(t.get("Reception_Date") or "")[:16]

            # 0. N° Ticket
            it_num = QTableWidgetItem(t_num)
            it_num.setFont(QFont("Segoe UI", 9, QFont.Bold))
            it_num.setForeground(QColor("#007572"))
            table.setItem(row, 0, it_num)

            # 1. Code Bon
            it_bon = QTableWidgetItem(b_code)
            it_bon.setFont(QFont("Courier New", 9, QFont.Bold))
            table.setItem(row, 1, it_bon)

            # 2. Client
            it_client = QTableWidgetItem(client)
            table.setItem(row, 2, it_client)

            # 3. Produit
            p_display = f"{brand} {prod}".strip() if brand and brand not in prod else prod
            it_prod = QTableWidgetItem(p_display)
            it_prod.setToolTip(p_display)
            table.setItem(row, 3, it_prod)

            # 4. N° de Série
            it_sn = QTableWidgetItem(sn)
            it_sn.setFont(QFont("Courier New", 9, QFont.Bold))
            it_sn.setForeground(QColor("#0F172A"))
            table.setItem(row, 4, it_sn)

            # 5. Garantie Badge
            w_text = "✔ Garantie" if is_warr else "Hors Garantie"
            w_color = "#16A34A" if is_warr else "#64748B"
            it_warr = QTableWidgetItem(w_text)
            it_warr.setTextAlignment(Qt.AlignCenter)
            it_warr.setFont(QFont("Segoe UI", 8, QFont.Bold))
            it_warr.setForeground(QColor(w_color))
            table.setItem(row, 5, it_warr)

            # 6. Symptôme
            it_symp = QTableWidgetItem(symp)
            it_symp.setToolTip(symp)
            table.setItem(row, 6, it_symp)

            # 7. Technicien
            it_tech = QTableWidgetItem(tech)
            table.setItem(row, 7, it_tech)

            # 8. Date Réception
            it_dt = QTableWidgetItem(dt_raw)
            it_dt.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 8, it_dt)

            # 9. Context-sensitive Action Cell
            act_widget = ActionCellWidget()
            stage = str(t.get("Current_Stage") or "")
            res = str(t.get("Resolution_Status") or "")
            is_irrep = "IRREPARABLE" in res or "SCRAPPED" in res

            if is_irrep:
                act_widget.add_action_button(
                    "💰 Avoir Portefeuille",
                    "#DC2626",
                    lambda checked=False, t_copy=t: self._show_ticket_details(t_copy),
                    "Afficher les détails de la compensation portefeuille",
                )
            elif stage == "SAV_RECEIVED":
                act_widget.add_action_button(
                    "📤 Envoi Atelier",
                    "#D97706",
                    lambda checked=False, t_copy=t: self._open_dispatch_dialog(t_copy),
                    "Affecter et envoyer l'appareil au technicien ou atelier",
                )
                act_widget.add_action_button(
                    "⚠️ Irréparable",
                    "#DC2626",
                    lambda checked=False, t_copy=t: self._declare_irreparable(t_copy),
                    "Constater l'irréparabilité et émettre un avoir portefeuille",
                )
            elif stage == "SAV_SENT_TO_TECH":
                act_widget.add_action_button(
                    "📥 Retour Réparation",
                    "#0284C7",
                    lambda checked=False, t_copy=t: self._open_return_dialog(t_copy),
                    "Enregistrer le retour de l'appareil réparé",
                )
                act_widget.add_action_button(
                    "⚠️ Irréparable",
                    "#DC2626",
                    lambda checked=False, t_copy=t: self._declare_irreparable(t_copy),
                    "Appareil non réparable",
                )
            elif stage == "SAV_RETURNED_FROM_TECH":
                act_widget.add_action_button(
                    "📦 Remise au Client",
                    "#16A34A",
                    lambda checked=False, t_copy=t: self._deliver_to_client(t_copy),
                    "Restituer l'appareil réparé au client et clôturer le ticket",
                )
                act_widget.add_action_button(
                    "⚠️ Irréparable",
                    "#DC2626",
                    lambda checked=False, t_copy=t: self._declare_irreparable(t_copy),
                    "Constat irréparable avant remise",
                )
            elif stage == "SAV_CLOSED_DELIVERED":
                act_widget.add_action_button(
                    "📄 Fiche Clôture",
                    "#16A34A",
                    lambda checked=False, t_copy=t: self._show_ticket_details(t_copy),
                    "Consulter l'historique de clôture du ticket",
                )

            # Global "Bon" receipt print button available on all active cards
            act_widget.add_action_button(
                "🖨️ Bon",
                "#64748B",
                lambda checked=False, t_copy=t: self._print_bon_reparation(t_copy),
                "Imprimer / Afficher le Bon de Réparation SAV",
            )

            table.setCellWidget(row, 9, act_widget)

    def _on_search_changed(self, text: str) -> None:
        self._update_all_stage_views()

    def _open_reception_dialog(self) -> None:
        dlg = SAVReceptionDialog(data_manager=self.data_manager, parent=self)
        if dlg.exec() == QDialog.Accepted and dlg.created_ticket:
            QMessageBox.information(
                self,
                "Réception SAV Enregistrée",
                f"Appareil réceptionné avec succès !\n"
                f"• Ticket : {dlg.created_ticket.get('ticket_number')}\n"
                f"• Code Bon : {dlg.created_ticket.get('bon_reparation_barcode')}\n"
                f"• N° Série : {dlg.created_ticket.get('serial_number')}",
            )
            self.refresh_tickets()
            self.tabs.setCurrentIndex(1)  # Focus on Réception tab

    def _open_dispatch_dialog(self, ticket: Dict[str, Any]) -> None:
        t_id = ticket.get("SAV_Ticket_ID") or ticket.get("Ticket_ID") or ticket.get("ticket_id")
        tech_name, ok = QInputDialog.getText(
            self,
            "Envoi au Technicien",
            f"Ticket {ticket.get('Ticket_Number')} :\nNom du réparateur / Atelier technique :",
            QLineEdit.Normal,
            "Atelier Central Alger",
        )
        if not ok or not tech_name.strip():
            return

        try:
            if self.data_manager and hasattr(self.data_manager, "sav"):
                u_id = int((self.current_user or {}).get("User_ID") or 1)
                self.data_manager.sav.dispatch_to_technician(
                    sav_ticket_id=int(t_id),
                    technician_id=None,
                    user_id=u_id,
                    notes=f"Affecté à {tech_name.strip()}",
                )
            else:
                ticket["Current_Stage"] = "SAV_SENT_TO_TECH"
                ticket["Technician_Name"] = tech_name.strip()

            QMessageBox.information(
                self,
                "Envoi Effectué",
                f"L'appareil a été transféré au réparateur '{tech_name.strip()}'.",
            )
            self.refresh_tickets()
            self.tabs.setCurrentIndex(2)  # Focus on En Atelier tab
        except Exception as err:
            QMessageBox.critical(self, "Erreur Envoi", str(err))

    def _open_return_dialog(self, ticket: Dict[str, Any]) -> None:
        t_id = ticket.get("SAV_Ticket_ID") or ticket.get("Ticket_ID") or ticket.get("ticket_id")
        diag, ok = QInputDialog.getText(
            self,
            "Retour de Réparation",
            f"Ticket {ticket.get('Ticket_Number')} :\nDiagnostic & Travaux effectués :",
            QLineEdit.Normal,
            "Réparation effectuée avec succès — Tests fonctionnels validés",
        )
        if not ok or not diag.strip():
            return

        try:
            if self.data_manager and hasattr(self.data_manager, "sav"):
                u_id = int((self.current_user or {}).get("User_ID") or 1)
                self.data_manager.sav.record_technician_return(
                    sav_ticket_id=int(t_id),
                    resolution_status="REPAIRED",
                    diagnostic_summary=diag.strip(),
                    user_id=u_id,
                )
            else:
                ticket["Current_Stage"] = "SAV_RETURNED_FROM_TECH"
                ticket["Resolution_Status"] = "REPAIRED"

            QMessageBox.information(
                self,
                "Retour Enregistré",
                "L'appareil réparé est désormais prêt pour restitution au client.",
            )
            self.refresh_tickets()
            self.tabs.setCurrentIndex(3)  # Focus on Prêts tab
        except Exception as err:
            QMessageBox.critical(self, "Erreur Retour", str(err))

    def _deliver_to_client(self, ticket: Dict[str, Any]) -> None:
        t_id = ticket.get("SAV_Ticket_ID") or ticket.get("Ticket_ID") or ticket.get("ticket_id")
        reply = QMessageBox.question(
            self,
            "Restitution au Client",
            f"Confirmez-vous la remise de l'appareil réparé au client {ticket.get('Client_Name')} ?\n"
            f"Ticket : {ticket.get('Ticket_Number')}\nN° Série : {ticket.get('Serial_Number')}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            if self.data_manager and hasattr(self.data_manager, "sav"):
                u_id = int((self.current_user or {}).get("User_ID") or 1)
                self.data_manager.sav.deliver_repaired_to_client(
                    sav_ticket_id=int(t_id),
                    user_id=u_id,
                )
            else:
                ticket["Current_Stage"] = "SAV_CLOSED_DELIVERED"
                ticket["Resolution_Status"] = "REPAIRED"

            QMessageBox.information(
                self,
                "Ticket Clôturé",
                "L'appareil a été remis au client. Le ticket SAV est maintenant clôturé avec succès.",
            )
            self.refresh_tickets()
            self.tabs.setCurrentIndex(4)  # Focus on Clôturés tab
        except Exception as err:
            QMessageBox.critical(self, "Erreur Restitution", str(err))

    def _declare_irreparable(self, ticket: Dict[str, Any]) -> None:
        t_id = ticket.get("SAV_Ticket_ID") or ticket.get("Ticket_ID") or ticket.get("ticket_id")
        price = float(ticket.get("Purchase_Price") or ticket.get("Unit_Price_TTC") or 80000.0)

        dlg = IrreparableDefectModal(
            ticket_id=str(ticket.get("Ticket_Number") or t_id),
            client_name=str(ticket.get("Client_Name") or "Client"),
            appliance_model=str(ticket.get("Product_Name") or "Appareil"),
            purchase_price=price,
            parent=self,
        )
        if dlg.exec() == QDialog.Accepted and dlg.compensation_confirmed:
            try:
                if self.data_manager and hasattr(self.data_manager, "sav"):
                    u_id = int((self.current_user or {}).get("User_ID") or 1)
                    self.data_manager.sav.process_irreparable_compensation(
                        sav_ticket_id=int(t_id),
                        admin_user_id=u_id,
                        compensation_amount=Decimal(str(dlg.compensation_amount)),
                    )
                else:
                    ticket["Current_Stage"] = "SAV_CLOSED_DELIVERED"
                    ticket["Resolution_Status"] = "IRREPARABLE_COMPENSATED"

                QMessageBox.information(
                    self,
                    "Avoir Portefeuille Émis",
                    f"Constat d'irréparabilité validé !\n"
                    f"Un versement virtuel de {format_money(dlg.compensation_amount)} DA "
                    f"a été crédité sur le portefeuille du client sans aucun impact sur la caisse physique.",
                )
                self.refresh_tickets()
                self.tabs.setCurrentIndex(5)  # Focus on Irréparables tab
            except Exception as err:
                QMessageBox.critical(self, "Erreur Constat Irréparable", str(err))

    def _print_bon_reparation(self, ticket: Dict[str, Any]) -> None:
        QMessageBox.information(
            self,
            "Bon de Réparation SAV",
            f"----------------------------------------\n"
            f"BON DE RÉPARATION — SAV\n"
            f"----------------------------------------\n"
            f"N° Ticket : {ticket.get('Ticket_Number')}\n"
            f"Code-barres : {ticket.get('Bon_Reparation_Barcode')}\n"
            f"Client : {ticket.get('Client_Name')}\n"
            f"Appareil : {ticket.get('Product_Name')}\n"
            f"N° Série : {ticket.get('Serial_Number')}\n"
            f"Garantie : {'Sous Garantie' if ticket.get('Is_Under_Warranty') else 'Hors Garantie'}\n"
            f"Symptôme : {ticket.get('Customer_Stated_Symptom')}\n"
            f"Date : {str(ticket.get('Reception_Date'))[:16]}\n"
            f"----------------------------------------\n"
            f"(Document prêt pour impression thermique ou PDF)",
        )

    def _show_ticket_details(self, ticket: Dict[str, Any]) -> None:
        QMessageBox.information(
            self,
            f"Fiche Ticket {ticket.get('Ticket_Number')}",
            f"Détails complets du Ticket SAV :\n\n"
            f"• N° Ticket : {ticket.get('Ticket_Number')}\n"
            f"• Code Bon : {ticket.get('Bon_Reparation_Barcode')}\n"
            f"• Client : {ticket.get('Client_Name')}\n"
            f"• Appareil : {ticket.get('Product_Name')}\n"
            f"• N° Série : {ticket.get('Serial_Number')}\n"
            f"• État Actuel : {ticket.get('Current_Stage')}\n"
            f"• Statut Résolution : {ticket.get('Resolution_Status')}\n"
            f"• Technicien : {ticket.get('Technician_Name')}\n"
            f"• Panne / Symptôme : {ticket.get('Customer_Stated_Symptom')}\n"
            f"• Date Réception : {str(ticket.get('Reception_Date'))[:16]}",
        )
