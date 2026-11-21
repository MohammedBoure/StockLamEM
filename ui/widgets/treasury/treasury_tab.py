# -*- coding: utf-8 -*-
"""
Treasury & Multi-Method Cashbook Workspace (`Page 19 : Trésorerie`).
Displays live balances across Cash, BaridiMob, TPE, and CCP, the complete unified
financial journal (Bureaux Caisse, Versements, Livraison, POS & Manual Entries),
and provides Entrée (دخول), Sortie (خروج), and Transfert Interne operations.
"""

import csv
import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QDate, QEvent, QObject, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QBoxLayout,
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.formatting import format_money
from ui.icons import get_duotone_icon
from ui.navigation_permissions import has_permission
from .treasury_dialogs import (
    PAYMENT_METHOD_TILES,
    TreasuryMovementDetailsDialog,
    TreasuryOperationDialog,
    TreasuryTransferDialog,
    _resolve_treasury_manager,
)

try:
    import qtawesome as qta
except ImportError:
    qta = None

logger = logging.getLogger("StockLam.UI.TreasuryTab")


class TreasuryDirectionDelegate(QStyledItemDelegate):
    """Pill badge delegate for Entrée / Sortie / Transfert direction column."""

    _STYLES = {
        "Entrée": (QColor("#DCFCE7"), QColor("#15803D")),
        "Sortie": (QColor("#FEE2E2"), QColor("#B91C1C")),
        "Transfert": (QColor("#DBEAFE"), QColor("#1D4ED8")),
    }

    def paint(self, painter: QPainter, option, index) -> None:
        text = str(index.data(Qt.DisplayRole) or "").strip()
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        if option.state & QStyle.State_Selected:
            bg = QColor("#E6F4F1")
        elif index.row() % 2 == 1:
            bg = QColor("#F8FAFC")
        else:
            bg = QColor("#FFFFFF")
        painter.fillRect(option.rect, bg)

        painter.setPen(QPen(QColor("#F1F5F9"), 1))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())

        if text:
            font = QFont(option.font)
            font.setPointSize(9)
            font.setBold(True)
            painter.setFont(font)
            fm = QFontMetrics(font)

            key = "Transfert" if "Transfert" in text else ("Entrée" if "Entrée" in text else "Sortie")
            fill_col, text_col = self._STYLES.get(key, (QColor("#F1F5F9"), QColor("#475569")))
            pill_w = min(option.rect.width() - 10, fm.horizontalAdvance(text) + 18)
            pill_h = 22
            pill_x = option.rect.x() + (option.rect.width() - pill_w) // 2
            pill_y = option.rect.y() + (option.rect.height() - pill_h) // 2
            pill_rect = QRect(pill_x, pill_y, pill_w, pill_h)

            painter.setPen(Qt.NoPen)
            painter.setBrush(fill_col)
            painter.drawRoundedRect(pill_rect, 11, 11)

            painter.setPen(text_col)
            painter.drawText(pill_rect, Qt.AlignCenter, text)

        painter.restore()


class TreasuryTab(QWidget):
    """Main Trésorerie page for live multi-method balances, full journal, and Entrée/Sortie."""

    movementRecorded = Signal()

    def __init__(
        self,
        data_manager: Any = None,
        current_user: Optional[Dict[str, Any]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.data_manager = data_manager
        self.current_user = current_user or (getattr(data_manager, "current_user", None) or {})
        self._treasury_mgr = _resolve_treasury_manager(data_manager)

        self._snapshot: Dict[str, Any] = {
            "total_balance": 0.0,
            "balances_by_method": {m: 0.0 for m, _, _ in PAYMENT_METHOD_TILES},
            "method_summaries": [],
            "movements": [],
            "total_count": 0,
            "filtered_count": 0,
            "period_in": 0.0,
            "period_out": 0.0,
            "period_net": 0.0,
        }
        self._active_direction = "ALL"
        self._active_method = "ALL"

        self._init_ui()
        self.refresh_data()

    def _init_ui(self) -> None:
        self.setObjectName("TreasuryWorkspace")
        self.setStyleSheet(
            """
            QWidget#TreasuryWorkspace {
                background-color: #F8FAFC;
                color: #0F172A;
            }
            QWidget#TreasuryWorkspace QLabel {
                border: none;
                background: transparent;
            }
            QFrame#TreasuryHeaderCard, QFrame#TreasuryStatCard, QFrame#TreasuryTableCard, QFrame#TreasurySummaryCard {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 10px;
            }
            QFrame#TreasuryToolbar {
                background-color: #FFFFFF;
                border: none;
                border-bottom: 1px solid #E2E8F0;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }
            QFrame#TreasuryPeriodStrip {
                background-color: #F8FAFC;
                border: none;
                border-bottom: 1px solid #E2E8F0;
            }
            QFrame#TreasuryFooter {
                background-color: #F8FAFC;
                border: none;
                border-top: 1px solid #E2E8F0;
                border-bottom-left-radius: 10px;
                border-bottom-right-radius: 10px;
            }
            QLineEdit#TreasurySearchInput, QComboBox#TreasuryPeriodCombo, QDateEdit#TreasuryDateInput {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 4px 10px;
                min-height: 30px;
                font-size: 12.5px;
                color: #0F172A;
            }
            QLineEdit#TreasurySearchInput:focus, QComboBox#TreasuryPeriodCombo:focus, QDateEdit#TreasuryDateInput:focus {
                border: 1.5px solid #0E7471;
            }
            QTableWidget#TreasuryTable {
                background-color: #FFFFFF;
                border: none;
                gridline-color: transparent;
                alternate-background-color: #F8FAFC;
                selection-background-color: #E6F4F1;
                selection-color: #0F172A;
            }
            QTableWidget#TreasuryTable::item {
                padding: 4px 8px;
                border-bottom: 1px solid #F1F5F9;
                color: #0F172A;
            }
            QTableWidget#TreasuryTable QHeaderView::section {
                background-color: #F8FAFC;
                color: #475569;
                font-weight: 700;
                font-size: 11px;
                padding: 6px 8px;
                border: none;
                border-bottom: 2px solid #0E7471;
                border-right: 1px solid #F1F5F9;
            }
            QTabWidget#TreasurySubTabs::pane {
                border: none;
                background: transparent;
            }
            QTabWidget#TreasurySubTabs QTabBar::tab {
                background: transparent;
                color: #64748B;
                font-size: 13px;
                font-weight: 700;
                padding: 8px 16px;
                border: none;
                border-bottom: 2px solid transparent;
            }
            QTabWidget#TreasurySubTabs QTabBar::tab:selected {
                color: #0E7471;
                border-bottom: 2.5px solid #0E7471;
            }
            QTabWidget#TreasurySubTabs QTabBar::tab:hover:!selected {
                color: #0F172A;
            }
            """
        )

        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(16, 14, 16, 14)
        self._root_layout.setSpacing(10)

        # 1. Header Card with Canonical Action Buttons
        self.header_card = QFrame()
        self.header_card.setObjectName("TreasuryHeaderCard")
        self._hdr_lay = QHBoxLayout(self.header_card)
        self._hdr_lay.setContentsMargins(14, 10, 14, 10)
        self._hdr_lay.setSpacing(8)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_duotone_icon("treasury", 26).pixmap(26, 26))
        self._hdr_lay.addWidget(icon_lbl)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.lbl_title = QLabel("Trésorerie & Journal de Caisse")
        self.lbl_title.setStyleSheet("font-size: 17px; font-weight: 700; color: #0F172A;")
        self.lbl_title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.lbl_subtitle = QLabel(
            "Solde actuel par mode de paiement, historique complet des flux Caisse et opérations Entrée / Sortie"
        )
        self.lbl_subtitle.setStyleSheet("font-size: 12px; color: #64748B;")
        self.lbl_subtitle.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        title_col.addWidget(self.lbl_title)
        title_col.addWidget(self.lbl_subtitle)
        self._hdr_lay.addLayout(title_col, 1)

        self.btn_entry = QPushButton("+ Entrée")
        self.btn_entry.setObjectName("BtnTreasuryEntry")
        self.btn_entry.setFixedHeight(34)
        self.btn_entry.setCursor(Qt.PointingHandCursor)
        self.btn_entry.setIcon(get_duotone_icon("payment_white", 16))
        self.btn_entry.setIconSize(QSize(15, 15))
        self.btn_entry.setToolTip("Enregistrer une Entrée d'argent (دخول / Alimentation)")
        self.btn_entry.setStyleSheet(
            """
            QPushButton#BtnTreasuryEntry {
                background-color: #0E7471; border: none; border-radius: 6px;
                color: #FFFFFF; font-size: 12.5px; font-weight: 700; padding: 0 14px;
            }
            QPushButton#BtnTreasuryEntry:hover { background-color: #0A5C59; }
            """
        )
        self.btn_entry.clicked.connect(lambda: self.open_operation_dialog("IN"))
        self._hdr_lay.addWidget(self.btn_entry)

        self.btn_exit = QPushButton("- Sortie")
        self.btn_exit.setObjectName("BtnTreasuryExit")
        self.btn_exit.setFixedHeight(34)
        self.btn_exit.setCursor(Qt.PointingHandCursor)
        self.btn_exit.setToolTip("Enregistrer une Sortie d'argent (خروج / Dépense / Retrait)")
        self.btn_exit.setStyleSheet(
            """
            QPushButton#BtnTreasuryExit {
                background-color: #FFFFFF; border: 1.5px solid #DC2626; border-radius: 6px;
                color: #DC2626; font-size: 12.5px; font-weight: 700; padding: 0 14px;
            }
            QPushButton#BtnTreasuryExit:hover { background-color: #FEF2F2; border-color: #B91C1C; }
            """
        )
        self.btn_exit.clicked.connect(lambda: self.open_operation_dialog("OUT"))
        self._hdr_lay.addWidget(self.btn_exit)

        self.btn_transfer = QPushButton("⇄ Transfert")
        self.btn_transfer.setObjectName("BtnTreasuryTransfer")
        self.btn_transfer.setFixedHeight(34)
        self.btn_transfer.setCursor(Qt.PointingHandCursor)
        self.btn_transfer.setToolTip("Transfert interne entre modes de paiement (ex : Cash → CCP)")
        self.btn_transfer.setStyleSheet(
            """
            QPushButton#BtnTreasuryTransfer {
                background-color: #FFFFFF; border: 1.5px solid #0E7471; border-radius: 6px;
                color: #0E7471; font-size: 12.5px; font-weight: 700; padding: 0 12px;
            }
            QPushButton#BtnTreasuryTransfer:hover { background-color: #E6F4F1; }
            """
        )
        self.btn_transfer.clicked.connect(self.open_transfer_dialog)
        self._hdr_lay.addWidget(self.btn_transfer)

        self.btn_export = QPushButton("Exporter CSV")
        self.btn_export.setObjectName("BtnTreasuryExport")
        self.btn_export.setFixedHeight(34)
        self.btn_export.setCursor(Qt.PointingHandCursor)
        self.btn_export.setIcon(get_duotone_icon("export", 15))
        self.btn_export.setIconSize(QSize(15, 15))
        self.btn_export.setToolTip("Exporter les mouvements affichés au format CSV")
        self.btn_export.setStyleSheet(
            """
            QPushButton#BtnTreasuryExport {
                background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 6px;
                color: #334155; font-size: 12px; font-weight: 600; padding: 0 12px;
            }
            QPushButton#BtnTreasuryExport:hover { background-color: #F8FAFC; border-color: #94A3B8; }
            """
        )
        self.btn_export.clicked.connect(self.export_csv)
        self._hdr_lay.addWidget(self.btn_export)

        self.btn_refresh = QPushButton("Actualiser")
        self.btn_refresh.setObjectName("BtnTreasuryRefresh")
        self.btn_refresh.setFixedHeight(34)
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setIcon(get_duotone_icon("refresh", 15))
        self.btn_refresh.setIconSize(QSize(15, 15))
        self.btn_refresh.setToolTip("Actualiser les soldes et mouvements (F5 / Ctrl+R)")
        self.btn_refresh.setStyleSheet(
            """
            QPushButton#BtnTreasuryRefresh {
                background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 6px;
                color: #334155; font-size: 12px; font-weight: 600; padding: 0 12px;
            }
            QPushButton#BtnTreasuryRefresh:hover { background-color: #F8FAFC; border-color: #94A3B8; }
            """
        )
        self.btn_refresh.clicked.connect(self.refresh_data)
        self._hdr_lay.addWidget(self.btn_refresh)
        self._root_layout.addWidget(self.header_card)

        # 2. Live Balances Grid (Total + Cash + BaridiMob + TPE + CCP)
        self.kpi_grid = QGridLayout()
        self.kpi_grid.setSpacing(10)
        self.lbl_bal_total, self.card_total = self._build_balance_card(
            "Solde Total Actuel", "0,00 DA", "#0E7471", "treasury", is_hero=True
        )
        self.lbl_bal_cash, self.card_cash = self._build_balance_card(
            "Cash (Espèces)", "0,00 DA", "#0F172A", "pay_cash"
        )
        self.lbl_bal_baridimob, self.card_baridimob = self._build_balance_card(
            "BaridiMob", "0,00 DA", "#0F172A", "pay_baridimob"
        )
        self.lbl_bal_tpe, self.card_tpe = self._build_balance_card(
            "TPE (Carte)", "0,00 DA", "#0F172A", "pay_tpe"
        )
        self.lbl_bal_ccp, self.card_ccp = self._build_balance_card(
            "CCP", "0,00 DA", "#0F172A", "pay_ccp"
        )
        self._balance_labels = {
            "Cash": self.lbl_bal_cash,
            "BaridiMob": self.lbl_bal_baridimob,
            "TPE": self.lbl_bal_tpe,
            "CCP": self.lbl_bal_ccp,
        }
        self._kpi_cards = [
            self.card_total,
            self.card_cash,
            self.card_baridimob,
            self.card_tpe,
            self.card_ccp,
        ]
        self._kpi_compact_grid: Optional[bool] = None
        self._apply_kpi_grid(compact=False)
        self._root_layout.addLayout(self.kpi_grid)

        # 3. Sub-tabs (Journal & Opérations | Synthèse par Mode de Paiement)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("TreasurySubTabs")
        self.tabs.setDocumentMode(True)

        self.page_journal = self._build_journal_page()
        self.page_summary = self._build_summary_page()

        show_journal = not self.current_user or has_permission(self.current_user, "tab_treasury_journal")
        show_summary = not self.current_user or has_permission(self.current_user, "tab_treasury_balances")
        if show_journal or not show_summary:
            self.tabs.addTab(self.page_journal, "1. Journal & Opérations")
        if show_summary:
            self.tabs.addTab(self.page_summary, "2. Synthèse par Mode de Paiement")

        self._root_layout.addWidget(self.tabs, 1)

        # Shortcuts
        self._shortcut_f5 = QShortcut(QKeySequence(Qt.Key_F5), self)
        self._shortcut_f5.setContext(Qt.WidgetWithChildrenShortcut)
        self._shortcut_f5.activated.connect(self.refresh_data)

        self._shortcut_ctrl_r = QShortcut(QKeySequence("Ctrl+R"), self)
        self._shortcut_ctrl_r.setContext(Qt.WidgetWithChildrenShortcut)
        self._shortcut_ctrl_r.activated.connect(self.refresh_data)

        self._shortcut_esc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self._shortcut_esc.setContext(Qt.WidgetWithChildrenShortcut)
        self._shortcut_esc.activated.connect(self._reset_filters)

    def _build_balance_card(
        self,
        title: str,
        value_text: str,
        value_color: str,
        icon_name: str,
        is_hero: bool = False,
    ) -> tuple[QLabel, QFrame]:
        card = QFrame()
        card.setObjectName("TreasuryStatCard")
        card.setMinimumWidth(130)
        card.setFixedHeight(74)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if is_hero:
            card.setStyleSheet(
                """
                QFrame#TreasuryStatCard {
                    background-color: #F0FDFA;
                    border: 1.5px solid #0E7471;
                    border-radius: 10px;
                }
                """
            )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(3)

        top = QHBoxLayout()
        top.setSpacing(6)
        ic = QLabel()
        ic.setPixmap(get_duotone_icon(icon_name, 16).pixmap(16, 16))
        lbl_name = QLabel(title)
        lbl_name.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {'#0E7471' if is_hero else '#64748B'};"
        )
        top.addWidget(ic)
        top.addWidget(lbl_name, 1)
        lay.addLayout(top)

        lbl_val = QLabel(value_text)
        lbl_val.setStyleSheet(f"font-size: 17px; font-weight: 800; color: {value_color};")
        lay.addWidget(lbl_val)
        return lbl_val, card

    def _create_chip(self, label: str, code: str, group: QButtonGroup, callback, checked: bool = False) -> QPushButton:
        btn = QPushButton(label)
        btn.setObjectName("TreasuryFilterChip")
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setFixedHeight(32)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            """
            QPushButton#TreasuryFilterChip {
                background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 6px;
                color: #334155; font-size: 11.5px; font-weight: 600; padding: 0 11px;
            }
            QPushButton#TreasuryFilterChip:checked {
                background-color: #CCFBF1; border: 1.5px solid #0E7471;
                color: #0E7471; font-weight: 700;
            }
            QPushButton#TreasuryFilterChip:hover:!checked {
                background-color: #F8FAFC; border-color: #94A3B8;
            }
            """
        )
        btn.clicked.connect(lambda _=False, c=code: callback(c))
        group.addButton(btn)
        return btn

    def _build_journal_page(self) -> QWidget:
        page = QWidget()
        p_lay = QVBoxLayout(page)
        p_lay.setContentsMargins(0, 4, 0, 0)
        p_lay.setSpacing(0)

        card = QFrame()
        card.setObjectName("TreasuryTableCard")
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(0)

        # Toolbar (Search + Direction Chips + Method Chips + Period)
        toolbar = QFrame()
        toolbar.setObjectName("TreasuryToolbar")
        tb_root = QVBoxLayout(toolbar)
        tb_root.setContentsMargins(12, 8, 12, 8)
        tb_root.setSpacing(8)

        row1 = QBoxLayout(QBoxLayout.LeftToRight)
        row1.setSpacing(8)
        self._tb_row1 = row1

        self.txt_search = QLineEdit()
        self.txt_search.setObjectName("TreasurySearchInput")
        self.txt_search.setFixedHeight(32)
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.setPlaceholderText("Rechercher par réf., motif, tiers, client, opérateur...")
        if qta:
            self.txt_search.addAction(qta.icon("fa5s.search", color="#94A3B8"), QLineEdit.LeadingPosition)
        self.txt_search.textChanged.connect(self._on_filter_changed)
        row1.addWidget(self.txt_search, 1)

        self.cbo_period = QComboBox()
        self.cbo_period.setObjectName("TreasuryPeriodCombo")
        self.cbo_period.setFixedHeight(32)
        self.cbo_period.addItem("Tout l'historique", "ALL")
        self.cbo_period.addItem("Aujourd'hui", "TODAY")
        self.cbo_period.addItem("7 derniers jours", "WEEK")
        self.cbo_period.addItem("Ce mois", "MONTH")
        self.cbo_period.addItem("Période personnalisée", "CUSTOM")
        self.cbo_period.currentIndexChanged.connect(self._on_period_changed)
        row1.addWidget(self.cbo_period)

        self.custom_dates_box = QWidget()
        cd_lay = QHBoxLayout(self.custom_dates_box)
        cd_lay.setContentsMargins(0, 0, 0, 0)
        cd_lay.setSpacing(4)
        self.dt_from = QDateEdit(QDate.currentDate().addDays(-30))
        self.dt_from.setObjectName("TreasuryDateInput")
        self.dt_from.setCalendarPopup(True)
        self.dt_from.setDisplayFormat("yyyy-MM-dd")
        self.dt_from.dateChanged.connect(self._on_filter_changed)
        self.dt_to = QDateEdit(QDate.currentDate())
        self.dt_to.setObjectName("TreasuryDateInput")
        self.dt_to.setCalendarPopup(True)
        self.dt_to.setDisplayFormat("yyyy-MM-dd")
        self.dt_to.dateChanged.connect(self._on_filter_changed)
        cd_lay.addWidget(QLabel("Du"))
        cd_lay.addWidget(self.dt_from)
        cd_lay.addWidget(QLabel("Au"))
        cd_lay.addWidget(self.dt_to)
        self.custom_dates_box.setVisible(False)
        row1.addWidget(self.custom_dates_box)
        tb_root.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(6)
        self.dir_group = QButtonGroup(self)
        self.dir_group.setExclusive(True)
        self.btn_dir_all = self._create_chip("Tous", "ALL", self.dir_group, self._set_direction_filter, checked=True)
        self.btn_dir_in = self._create_chip("Entrées (+)", "IN", self.dir_group, self._set_direction_filter)
        self.btn_dir_out = self._create_chip("Sorties (-)", "OUT", self.dir_group, self._set_direction_filter)
        self.btn_dir_trf = self._create_chip("Transferts", "TRANSFER", self.dir_group, self._set_direction_filter)
        for b in (self.btn_dir_all, self.btn_dir_in, self.btn_dir_out, self.btn_dir_trf):
            row2.addWidget(b)

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #E2E8F0;")
        row2.addWidget(sep)

        self.method_filter_group = QButtonGroup(self)
        self.method_filter_group.setExclusive(True)
        self.method_filter_buttons: Dict[str, QPushButton] = {}
        for code, label in (("ALL", "Tous modes"), ("Cash", "Cash"), ("BaridiMob", "BaridiMob"), ("TPE", "TPE"), ("CCP", "CCP")):
            btn = self._create_chip(label, code, self.method_filter_group, self._set_method_filter, checked=(code == "ALL"))
            self.method_filter_buttons[code] = btn
            row2.addWidget(btn)
        row2.addStretch(1)
        tb_root.addLayout(row2)
        c_lay.addWidget(toolbar)

        # Period summary strip
        period_strip = QFrame()
        period_strip.setObjectName("TreasuryPeriodStrip")
        ps_lay = QHBoxLayout(period_strip)
        ps_lay.setContentsMargins(14, 6, 14, 6)
        ps_lay.setSpacing(18)

        self.lbl_period_in = QLabel("Entrées : +0,00 DA")
        self.lbl_period_in.setStyleSheet("font-size: 12px; font-weight: 700; color: #16A34A;")
        self.lbl_period_out = QLabel("Sorties : -0,00 DA")
        self.lbl_period_out.setStyleSheet("font-size: 12px; font-weight: 700; color: #DC2626;")
        self.lbl_period_net = QLabel("Flux net : 0,00 DA")
        self.lbl_period_net.setStyleSheet("font-size: 12px; font-weight: 800; color: #0F172A;")
        ps_lay.addWidget(self.lbl_period_in)
        ps_lay.addWidget(self.lbl_period_out)
        ps_lay.addWidget(self.lbl_period_net)
        ps_lay.addStretch(1)
        c_lay.addWidget(period_strip)

        # Movements Table
        self.table = QTableWidget(0, 10)
        self.table.setObjectName("TreasuryTable")
        self.table.setHorizontalHeaderLabels(
            [
                "Date / Heure",
                "Référence",
                "Sens",
                "Mode",
                "Origine / Catégorie",
                "Motif / Tiers",
                "Montant",
                "Solde",
                "Opérateur",
                "Actions",
            ]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.horizontalHeader().setFixedHeight(36)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setItemDelegateForColumn(2, TreasuryDirectionDelegate(self.table))
        self.table.installEventFilter(self)

        aligns = {
            0: Qt.AlignCenter,
            1: Qt.AlignLeft | Qt.AlignVCenter,
            2: Qt.AlignCenter,
            3: Qt.AlignCenter,
            4: Qt.AlignLeft | Qt.AlignVCenter,
            5: Qt.AlignLeft | Qt.AlignVCenter,
            6: Qt.AlignRight | Qt.AlignVCenter,
            7: Qt.AlignRight | Qt.AlignVCenter,
            8: Qt.AlignLeft | Qt.AlignVCenter,
            9: Qt.AlignCenter,
        }
        for col, al in aligns.items():
            if self.table.horizontalHeaderItem(col):
                self.table.horizontalHeaderItem(col).setTextAlignment(al)

        hdr = self.table.horizontalHeader()
        hdr.setMinimumSectionSize(60)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 92)
        hdr.setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 88)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.Interactive)
        self.table.setColumnWidth(5, 220)
        hdr.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(9, QHeaderView.Fixed)
        self.table.setColumnWidth(9, 170)

        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        c_lay.addWidget(self.table, 1)

        # Empty State
        self.empty_state = QFrame()
        self.empty_state.setObjectName("TreasuryEmptyState")
        self.empty_state.setStyleSheet("QFrame#TreasuryEmptyState { background: #FFFFFF; border: none; }")
        es_lay = QVBoxLayout(self.empty_state)
        es_lay.setAlignment(Qt.AlignCenter)
        es_lay.setSpacing(10)

        es_icon = QLabel()
        es_icon.setAlignment(Qt.AlignCenter)
        es_icon.setPixmap(get_duotone_icon("treasury", 40).pixmap(40, 40))
        es_lay.addWidget(es_icon)

        es_title = QLabel("Aucun mouvement financier trouvé")
        es_title.setAlignment(Qt.AlignCenter)
        es_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #0F172A;")
        es_lay.addWidget(es_title)

        es_desc = QLabel("Les règlements Caisse et vos opérations Entrée / Sortie apparaîtront ici.")
        es_desc.setAlignment(Qt.AlignCenter)
        es_desc.setStyleSheet("font-size: 12px; color: #64748B;")
        es_lay.addWidget(es_desc)

        self.btn_empty_reset = QPushButton("Réinitialiser les filtres")
        self.btn_empty_reset.setFixedHeight(32)
        self.btn_empty_reset.setCursor(Qt.PointingHandCursor)
        self.btn_empty_reset.setIcon(get_duotone_icon("refresh", 14))
        self.btn_empty_reset.setStyleSheet(
            "QPushButton { background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 6px; padding: 0 12px; font-weight: 600; }"
        )
        self.btn_empty_reset.clicked.connect(self._reset_filters)
        es_lay.addWidget(self.btn_empty_reset, alignment=Qt.AlignCenter)
        self.empty_state.setVisible(False)
        c_lay.addWidget(self.empty_state, 1)

        # Footer
        footer = QFrame()
        footer.setObjectName("TreasuryFooter")
        f_lay = QHBoxLayout(footer)
        f_lay.setContentsMargins(14, 6, 14, 6)
        self.lbl_footer_info = QLabel("0 mouvement(s) affiché(s)")
        self.lbl_footer_info.setStyleSheet("font-size: 12px; font-weight: 600; color: #475569;")
        self.lbl_hints = QLabel("Double-clic : détails  •  F5 : actualiser  •  Échap : réinitialiser")
        self.lbl_hints.setStyleSheet("font-size: 11px; color: #94A3B8;")
        f_lay.addWidget(self.lbl_footer_info)
        f_lay.addStretch(1)
        f_lay.addWidget(self.lbl_hints)
        c_lay.addWidget(footer)

        p_lay.addWidget(card, 1)
        return page

    def _build_summary_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(10)

        card = QFrame()
        card.setObjectName("TreasurySummaryCard")
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(0)

        self.summary_table = QTableWidget(0, 8)
        self.summary_table.setObjectName("TreasuryTable")
        self.summary_table.setHorizontalHeaderLabels(
            [
                "Mode de Paiement",
                "Solde Actuel",
                "Entrées Aujourd'hui",
                "Sorties Aujourd'hui",
                "Entrées Ce Mois",
                "Sorties Ce Mois",
                "Nb Mouvements",
                "Opérations Rapides",
            ]
        )
        self.summary_table.verticalHeader().setVisible(False)
        self.summary_table.verticalHeader().setDefaultSectionSize(52)
        self.summary_table.horizontalHeader().setFixedHeight(38)
        self.summary_table.setAlternatingRowColors(True)
        self.summary_table.setShowGrid(False)
        self.summary_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.summary_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        shdr = self.summary_table.horizontalHeader()
        shdr.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 7):
            shdr.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        shdr.setSectionResizeMode(7, QHeaderView.Fixed)
        self.summary_table.setColumnWidth(7, 210)

        c_lay.addWidget(self.summary_table, 1)
        lay.addWidget(card, 1)
        return page

    def _apply_kpi_grid(self, compact: bool) -> None:
        if self._kpi_compact_grid is compact:
            return
        self._kpi_compact_grid = compact
        for card in self._kpi_cards:
            self.kpi_grid.removeWidget(card)
        for col in range(5):
            self.kpi_grid.setColumnStretch(col, 0)
        if compact:
            positions = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1)]
            for idx, (r, c) in enumerate(positions):
                self.kpi_grid.addWidget(self._kpi_cards[idx], r, c)
            for col in range(3):
                self.kpi_grid.setColumnStretch(col, 1)
        else:
            for idx, card in enumerate(self._kpi_cards):
                self.kpi_grid.addWidget(card, 0, idx)
                self.kpi_grid.setColumnStretch(idx, 1)

    def _apply_responsive_layout(self) -> None:
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return
        compact_h = h < 680
        narrow_w = w < 1020
        self._apply_kpi_grid(compact=narrow_w)
        self.lbl_subtitle.setVisible(not (compact_h or narrow_w))
        self.lbl_hints.setVisible(w >= 1100)
        for card in self._kpi_cards:
            card.setFixedHeight(62 if compact_h else 74)
        self._adjust_table_columns()

    def _adjust_table_columns(self) -> None:
        if not hasattr(self, "table") or self.table is None:
            return
        vp_w = self.table.viewport().width()
        if vp_w <= 0:
            return
        self.table.setColumnHidden(8, vp_w < 1180)  # Opérateur
        self.table.setColumnHidden(4, vp_w < 1020)  # Origine / Catégorie
        self.table.setColumnHidden(1, vp_w < 860)   # Référence
        other_w = sum(
            self.table.columnWidth(c)
            for c in range(self.table.columnCount())
            if c != 5 and not self.table.isColumnHidden(c)
        )
        target_reason_w = max(160, vp_w - other_w)
        if self.table.columnWidth(5) != target_reason_w:
            self.table.setColumnWidth(5, target_reason_w)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is getattr(self, "table", None) and event.type() == QEvent.Resize:
            self._adjust_table_columns()
        return super().eventFilter(watched, event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._apply_responsive_layout()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_responsive_layout()

    def _active_date_range(self) -> tuple[Optional[str], Optional[str]]:
        mode = str(self.cbo_period.currentData() or "ALL")
        today = QDate.currentDate()
        if mode == "TODAY":
            d = today.toString("yyyy-MM-dd")
            return d, d
        if mode == "WEEK":
            return today.addDays(-6).toString("yyyy-MM-dd"), today.toString("yyyy-MM-dd")
        if mode == "MONTH":
            return today.toString("yyyy-MM-01"), today.toString("yyyy-MM-dd")
        if mode == "CUSTOM":
            return self.dt_from.date().toString("yyyy-MM-dd"), self.dt_to.date().toString("yyyy-MM-dd")
        return None, None

    def _on_period_changed(self) -> None:
        is_custom = str(self.cbo_period.currentData() or "ALL") == "CUSTOM"
        self.custom_dates_box.setVisible(is_custom)
        self.refresh_data()

    def _set_direction_filter(self, code: str) -> None:
        self._active_direction = code
        self.refresh_data()

    def _set_method_filter(self, code: str) -> None:
        self._active_method = code
        self.refresh_data()

    def _on_filter_changed(self) -> None:
        self.refresh_data()

    def _reset_filters(self) -> None:
        self._active_direction = "ALL"
        self._active_method = "ALL"
        self.btn_dir_all.setChecked(True)
        self.method_filter_buttons["ALL"].setChecked(True)
        self.cbo_period.blockSignals(True)
        self.cbo_period.setCurrentIndex(0)
        self.cbo_period.blockSignals(False)
        self.custom_dates_box.setVisible(False)
        self.txt_search.blockSignals(True)
        self.txt_search.clear()
        self.txt_search.blockSignals(False)
        self.refresh_data()
        self.txt_search.setFocus()

    def refresh_data(self) -> None:
        if self._treasury_mgr is None:
            self._treasury_mgr = _resolve_treasury_manager(self.data_manager)

        start_d, end_d = self._active_date_range()
        search_q = (self.txt_search.text() or "").strip()

        snap: Any = None
        if self._treasury_mgr is not None and hasattr(self._treasury_mgr, "get_treasury_snapshot"):
            try:
                snap = self._treasury_mgr.get_treasury_snapshot(
                    start_date=start_d,
                    end_date=end_d,
                    payment_method=self._active_method,
                    direction=self._active_direction,
                    search=search_q,
                )
            except Exception as exc:
                logger.error(f"Failed loading treasury snapshot: {exc}")
                snap = None

        if isinstance(snap, dict):
            self._snapshot = snap
        else:
            self._snapshot = {
                "total_balance": 0.0,
                "balances_by_method": {m: 0.0 for m, _, _ in PAYMENT_METHOD_TILES},
                "method_summaries": [],
                "movements": [],
                "total_count": 0,
                "filtered_count": 0,
                "period_in": 0.0,
                "period_out": 0.0,
                "period_net": 0.0,
            }

        self._render_kpis()
        self._render_journal_table()
        self._render_summary_table()

    def _render_kpis(self) -> None:
        tot = float(self._snapshot.get("total_balance") or 0.0)
        self.lbl_bal_total.setText(f"{format_money(tot)} DA")
        self.lbl_bal_total.setStyleSheet(
            f"font-size: 17px; font-weight: 800; color: {'#DC2626' if tot < -0.01 else '#0E7471'};"
        )
        by_m = self._snapshot.get("balances_by_method") or {}
        for code, lbl in self._balance_labels.items():
            val = float(by_m.get(code, 0.0) or 0.0)
            lbl.setText(f"{format_money(val)} DA")
            lbl.setStyleSheet(
                f"font-size: 17px; font-weight: 800; color: {'#DC2626' if val < -0.01 else '#0F172A'};"
            )

        pin = float(self._snapshot.get("period_in") or 0.0)
        pout = float(self._snapshot.get("period_out") or 0.0)
        pnet = float(self._snapshot.get("period_net") or 0.0)
        self.lbl_period_in.setText(f"Entrées : +{format_money(pin)} DA")
        self.lbl_period_out.setText(f"Sorties : -{format_money(pout)} DA")
        net_sign = "+" if pnet > 0.01 else ""
        net_col = "#0E7471" if pnet >= -0.01 else "#DC2626"
        self.lbl_period_net.setText(f"Flux net : {net_sign}{format_money(pnet)} DA")
        self.lbl_period_net.setStyleSheet(f"font-size: 12px; font-weight: 800; color: {net_col};")

        fcount = len(self._snapshot.get("movements") or [])
        tcount = int(self._snapshot.get("total_count") or fcount)
        self.lbl_footer_info.setText(f"{fcount} mouvement(s) affiché(s) sur {tcount}")

    def _render_journal_table(self) -> None:
        movs: List[Dict[str, Any]] = list(self._snapshot.get("movements") or [])
        self.table.setRowCount(0)
        has_rows = len(movs) > 0
        self.table.setVisible(has_rows)
        self.empty_state.setVisible(not has_rows)

        bold = QFont()
        bold.setBold(True)

        for r_idx, mov in enumerate(movs):
            self.table.insertRow(r_idx)
            self.table.setRowHeight(r_idx, 44)

            ts = str(mov.get("timestamp") or "")[:16]
            ref = str(mov.get("reference") or mov.get("movement_code") or "—")
            direction = str(mov.get("direction") or "IN").upper()
            is_trf = bool(mov.get("is_transfer"))
            dir_text = "Transfert" if is_trf else ("Entrée" if direction == "IN" else "Sortie")
            pm = str(mov.get("payment_method") or "Cash")
            cat = str(mov.get("category") or "—")
            reason = str(mov.get("reason") or "")
            cp = str(mov.get("counterparty") or "").strip()
            motif_txt = f"{reason}  •  {cp}" if cp and cp != "—" else reason
            amt = float(mov.get("amount") or 0.0)
            bal = float(mov.get("display_balance_after") or 0.0)
            op = str(mov.get("operator") or "Système")

            it_dt = QTableWidgetItem(ts)
            it_dt.setTextAlignment(Qt.AlignCenter)
            it_dt.setForeground(QColor("#475569"))

            it_ref = QTableWidgetItem(ref)
            it_ref.setFont(bold)

            it_dir = QTableWidgetItem(dir_text)
            it_dir.setTextAlignment(Qt.AlignCenter)

            it_pm = QTableWidgetItem(pm)
            it_pm.setTextAlignment(Qt.AlignCenter)
            it_pm.setFont(bold)

            it_cat = QTableWidgetItem(cat)
            it_motif = QTableWidgetItem(motif_txt)

            sign = "+" if direction == "IN" else "-"
            it_amt = QTableWidgetItem(f"{sign}{format_money(amt)} DA")
            it_amt.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_amt.setFont(bold)
            it_amt.setForeground(QColor("#16A34A" if direction == "IN" else "#DC2626"))

            it_bal = QTableWidgetItem(f"{format_money(bal)} DA")
            it_bal.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_bal.setFont(bold)
            it_bal.setForeground(QColor("#DC2626" if bal < -0.01 else "#0F172A"))

            it_op = QTableWidgetItem(op)
            it_op.setForeground(QColor("#475569"))

            for c_idx, item in enumerate((it_dt, it_ref, it_dir, it_pm, it_cat, it_motif, it_amt, it_bal, it_op)):
                item.setToolTip(f"{ts} | {pm} | {cat}\n{motif_txt}\nMontant : {sign}{format_money(amt)} DA")
                self.table.setItem(r_idx, c_idx, item)

            # Action cell
            act_w = QWidget()
            act_w.setStyleSheet("background: transparent;")
            a_lay = QHBoxLayout(act_w)
            a_lay.setContentsMargins(4, 4, 4, 4)
            a_lay.setSpacing(6)

            btn_det = QPushButton("Détails")
            btn_det.setFixedHeight(26)
            btn_det.setCursor(Qt.PointingHandCursor)
            btn_det.setStyleSheet(
                """
                QPushButton {
                    background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 5px;
                    color: #334155; font-size: 11px; font-weight: 600; padding: 0 8px;
                }
                QPushButton:hover { background: #F8FAFC; border-color: #94A3B8; }
                """
            )
            btn_det.clicked.connect(lambda _=False, m=mov: self._open_details(m))

            btn_void = QPushButton("Annuler")
            btn_void.setFixedHeight(26)
            btn_void.setCursor(Qt.PointingHandCursor)
            is_manual = bool(mov.get("is_manual")) and mov.get("movement_id") is not None
            btn_void.setEnabled(is_manual)
            btn_void.setToolTip(
                f"Annuler l'opération manuelle {mov.get('movement_code')}"
                if is_manual
                else "Opération issue de la Caisse / Versement : modifiable depuis le module d'origine"
            )
            btn_void.setStyleSheet(
                """
                QPushButton {
                    background: #FFFFFF; border: 1px solid #FECACA; border-radius: 5px;
                    color: #DC2626; font-size: 11px; font-weight: 600; padding: 0 8px;
                }
                QPushButton:hover:enabled { background: #FEF2F2; border-color: #DC2626; }
                QPushButton:disabled {
                    background: #F1F5F9; color: #475569; border: 1px solid #CBD5E1;
                }
                """
            )
            btn_void.clicked.connect(lambda _=False, m=mov: self._cancel_manual_movement(m))

            a_lay.addWidget(btn_det)
            a_lay.addWidget(btn_void)
            self.table.setCellWidget(r_idx, 9, act_w)

        self._adjust_table_columns()

    def _render_summary_table(self) -> None:
        summaries: List[Dict[str, Any]] = list(self._snapshot.get("method_summaries") or [])
        if not summaries:
            summaries = [
                {
                    "payment_method": code,
                    "balance": 0.0,
                    "today_in": 0.0,
                    "today_out": 0.0,
                    "month_in": 0.0,
                    "month_out": 0.0,
                    "count": 0,
                }
                for code, _, _ in PAYMENT_METHOD_TILES
            ]

        self.summary_table.setRowCount(0)
        bold = QFont()
        bold.setBold(True)
        icon_map = {code: ic for code, _, ic in PAYMENT_METHOD_TILES}

        tot_bal = tot_tin = tot_tout = tot_min = tot_mout = 0.0
        tot_cnt = 0

        for idx, ms in enumerate(summaries):
            self.summary_table.insertRow(idx)
            self.summary_table.setRowHeight(idx, 52)
            code = str(ms.get("payment_method") or "Cash")
            bal = float(ms.get("balance") or 0.0)
            tin = float(ms.get("today_in") or 0.0)
            tout = float(ms.get("today_out") or 0.0)
            min_v = float(ms.get("month_in") or 0.0)
            mout_v = float(ms.get("month_out") or 0.0)
            cnt = int(ms.get("count") or 0)

            tot_bal += bal
            tot_tin += tin
            tot_tout += tout
            tot_min += min_v
            tot_mout += mout_v
            tot_cnt += cnt

            it_m = QTableWidgetItem(code)
            it_m.setIcon(get_duotone_icon(icon_map.get(code, "pay_cash"), 18))
            it_m.setFont(bold)

            it_bal = QTableWidgetItem(f"{format_money(bal)} DA")
            it_bal.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_bal.setFont(bold)
            it_bal.setForeground(QColor("#DC2626" if bal < -0.01 else "#0E7471"))

            it_tin = QTableWidgetItem(f"+{format_money(tin)} DA")
            it_tin.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_tin.setForeground(QColor("#16A34A"))

            it_tout = QTableWidgetItem(f"-{format_money(tout)} DA")
            it_tout.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_tout.setForeground(QColor("#DC2626"))

            it_min = QTableWidgetItem(f"+{format_money(min_v)} DA")
            it_min.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            it_mout = QTableWidgetItem(f"-{format_money(mout_v)} DA")
            it_mout.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            it_cnt = QTableWidgetItem(str(cnt))
            it_cnt.setTextAlignment(Qt.AlignCenter)

            for c_idx, item in enumerate((it_m, it_bal, it_tin, it_tout, it_min, it_mout, it_cnt)):
                self.summary_table.setItem(idx, c_idx, item)

            op_w = QWidget()
            op_w.setStyleSheet("background: transparent;")
            op_lay = QHBoxLayout(op_w)
            op_lay.setContentsMargins(4, 4, 4, 4)
            op_lay.setSpacing(6)

            b_in = QPushButton("+ Entrée")
            b_in.setFixedHeight(28)
            b_in.setCursor(Qt.PointingHandCursor)
            b_in.setStyleSheet(
                "QPushButton { background: #0E7471; color: #FFFFFF; border: none; border-radius: 5px; font-size: 11px; font-weight: 700; padding: 0 10px; }"
            )
            b_in.clicked.connect(lambda _=False, m=code: self.open_operation_dialog("IN", default_method=m))

            b_out = QPushButton("- Sortie")
            b_out.setFixedHeight(28)
            b_out.setCursor(Qt.PointingHandCursor)
            b_out.setStyleSheet(
                "QPushButton { background: #FFFFFF; color: #DC2626; border: 1px solid #DC2626; border-radius: 5px; font-size: 11px; font-weight: 700; padding: 0 10px; }"
            )
            b_out.clicked.connect(lambda _=False, m=code: self.open_operation_dialog("OUT", default_method=m))

            op_lay.addWidget(b_in)
            op_lay.addWidget(b_out)
            self.summary_table.setCellWidget(idx, 7, op_w)

        # Total row
        tot_idx = self.summary_table.rowCount()
        self.summary_table.insertRow(tot_idx)
        self.summary_table.setRowHeight(tot_idx, 46)
        total_cells = [
            ("TOTAL TRÉSORERIE", Qt.AlignLeft | Qt.AlignVCenter, "#0F172A"),
            (f"{format_money(tot_bal)} DA", Qt.AlignRight | Qt.AlignVCenter, "#0E7471"),
            (f"+{format_money(tot_tin)} DA", Qt.AlignRight | Qt.AlignVCenter, "#16A34A"),
            (f"-{format_money(tot_tout)} DA", Qt.AlignRight | Qt.AlignVCenter, "#DC2626"),
            (f"+{format_money(tot_min)} DA", Qt.AlignRight | Qt.AlignVCenter, "#0F172A"),
            (f"-{format_money(tot_mout)} DA", Qt.AlignRight | Qt.AlignVCenter, "#0F172A"),
            (str(tot_cnt), Qt.AlignCenter, "#0F172A"),
            ("—", Qt.AlignCenter, "#64748B"),
        ]
        for c_idx, (txt, al, col_hex) in enumerate(total_cells):
            it = QTableWidgetItem(txt)
            it.setTextAlignment(al)
            it.setFont(bold)
            it.setForeground(QColor(col_hex))
            it.setBackground(QColor("#F1F5F9"))
            self.summary_table.setItem(tot_idx, c_idx, it)

    def _on_row_double_clicked(self, row: int, _col: int) -> None:
        movs = self._snapshot.get("movements") or []
        if 0 <= row < len(movs):
            self._open_details(movs[row])

    def _open_details(self, movement: Dict[str, Any]) -> None:
        dlg = TreasuryMovementDetailsDialog(movement, parent=self)
        dlg.exec()

    def _cancel_manual_movement(self, movement: Dict[str, Any]) -> None:
        mov_id = movement.get("movement_id")
        if mov_id is None or self._treasury_mgr is None:
            return
        code = str(movement.get("movement_code") or f"#{mov_id}")
        amt = float(movement.get("amount") or 0.0)
        reply = QMessageBox.question(
            self,
            "Confirmation d'annulation",
            f"Voulez-vous vraiment annuler le mouvement {code} ({format_money(amt)} DA) ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            uid = int(self.current_user.get("User_ID") or 1) if isinstance(self.current_user, dict) else 1
            self._treasury_mgr.cancel_manual_movement(int(mov_id), user_id=uid)
            self.refresh_data()
            self.movementRecorded.emit()
        except Exception as exc:
            QMessageBox.critical(self, "Erreur Annulation", str(exc))

    def open_operation_dialog(self, direction: str = "IN", default_method: str = "Cash") -> bool:
        dlg = TreasuryOperationDialog(
            data_manager=self.data_manager,
            direction=direction,
            balances_by_method=self._snapshot.get("balances_by_method"),
            current_user=self.current_user,
            default_method=default_method,
            parent=self,
        )
        if dlg.exec() == QDialog.Accepted:
            self.refresh_data()
            self.movementRecorded.emit()
            return True
        return False

    def open_transfer_dialog(self) -> bool:
        dlg = TreasuryTransferDialog(
            data_manager=self.data_manager,
            balances_by_method=self._snapshot.get("balances_by_method"),
            current_user=self.current_user,
            parent=self,
        )
        if dlg.exec() == QDialog.Accepted:
            self.refresh_data()
            self.movementRecorded.emit()
            return True
        return False

    def export_csv(self) -> None:
        movs = list(self._snapshot.get("movements") or [])
        if not movs:
            QMessageBox.information(self, "Export CSV", "Aucun mouvement à exporter.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter le Journal de Trésorerie",
            f"tresorerie_{QDate.currentDate().toString('yyyyMMdd')}.csv",
            "Fichiers CSV (*.csv)",
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                writer = csv.writer(fh, delimiter=";")
                writer.writerow(
                    ["Date", "Référence", "Sens", "Mode", "Catégorie", "Motif", "Tiers", "Montant", "Solde", "Opérateur"]
                )
                for m in movs:
                    amt = float(m.get("amount") or 0.0)
                    signed = amt if m.get("direction") == "IN" else -amt
                    writer.writerow(
                        [
                            m.get("timestamp", ""),
                            m.get("reference") or m.get("movement_code") or "",
                            m.get("direction", ""),
                            m.get("payment_method", ""),
                            m.get("category", ""),
                            m.get("reason", ""),
                            m.get("counterparty", ""),
                            f"{signed:.2f}",
                            f"{float(m.get('display_balance_after') or 0.0):.2f}",
                            m.get("operator", ""),
                        ]
                    )
            QMessageBox.information(self, "Export CSV", f"Journal exporté avec succès :\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Erreur Export", str(exc))
