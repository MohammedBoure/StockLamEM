# -*- coding: utf-8 -*-
"""
Reusable enterprise workspace for managing Bon payments (Bons de Versement and
Bons de Paiement Livraison) with organized bon listing and direct per-row
add & edit payment actions.
"""

import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QEvent, QObject, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QBoxLayout,
    QButtonGroup,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStyledItemDelegate,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.formatting import format_money
from ui.icons import get_duotone_icon
from .bon_payments_dialogs import (
    BonPaymentAddDialog,
    BonPaymentsManageDialog,
    _resolve_bonds_manager,
)
from .bon_products_edit_dialog import BonProductsEditDialog

try:
    import qtawesome as qta
except ImportError:
    qta = None

logger = logging.getLogger("StockLam.UI.BonPaymentsWorkspace")


class BonStatusBadgeDelegate(QStyledItemDelegate):
    """Content-fitted status indicator preserving row selection and hairline dividers."""

    _PILL_STYLES = {
        "Partiel": (QColor("#FEF3C7"), QColor("#B45309")),
        "Non payé": (QColor("#FEE2E2"), QColor("#B91C1C")),
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

        # Preserve row bottom hairline divider
        painter.setPen(QPen(QColor("#F1F5F9"), 1))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())

        if text:
            font = QFont(option.font)
            font.setPointSize(9)
            font.setBold(True)
            painter.setFont(font)
            fm = QFontMetrics(font)

            if text == "Soldé":
                dot_d = 7
                gap = 6
                content_w = dot_d + gap + fm.horizontalAdvance(text)
                start_x = option.rect.x() + max(6, (option.rect.width() - content_w) // 2)
                cy = option.rect.center().y()

                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor("#16A34A"))
                painter.drawEllipse(start_x, cy - dot_d // 2, dot_d, dot_d)

                painter.setPen(QColor("#15803D"))
                text_rect = QRect(start_x + dot_d + gap, option.rect.y(), fm.horizontalAdvance(text) + 4, option.rect.height())
                painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, text)
            else:
                fill_col, text_col = self._PILL_STYLES.get(text, (QColor("#F1F5F9"), QColor("#475569")))
                pill_w = min(option.rect.width() - 12, fm.horizontalAdvance(text) + 20)
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


class BonPaymentsWorkspaceWidget(QWidget):
    """
    Organized Bon payment management workspace:
    - Summary metrics strip (Bons count, Total TTC, Total Paid, Remaining Due)
    - Fast live search + status chips (Tous / Reste à payer / Soldés)
    - Structured QTableWidget listing all bons with direct '+ Versement' & 'Modifier'
      buttons on every row.
    """

    paymentUpdated = Signal(int)

    def __init__(
        self,
        data_manager: Any = None,
        current_user: Optional[Dict[str, Any]] = None,
        bond_type: str = "BON_VERSEMENT",
        title: str = "Gestion des Bons de Versement",
        subtitle: str = "Suivi des bons de versement, ajout et modification directe des paiements",
        icon_name: str = "kpi_wallet",
        add_button_text: str = "Versement",
        add_dialog_title: str = "Ajouter un Versement",
        manage_dialog_title: str = "Gérer les Versements du Bon",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.data_manager = data_manager
        self.current_user = current_user or {}
        self.bond_type = (bond_type or "BON_VERSEMENT").strip().upper()
        self._title_text = title
        self._subtitle_text = subtitle
        self._icon_name = icon_name
        self._add_button_text = add_button_text
        self._add_dialog_title = add_dialog_title
        self._manage_dialog_title = manage_dialog_title

        self._bonds_mgr = _resolve_bonds_manager(data_manager)
        self._all_bons: List[Dict[str, Any]] = []
        self._filtered_bons: List[Dict[str, Any]] = []
        self._active_status_filter = "ALL"

        self._init_ui()
        self.refresh_bons()

    def _init_ui(self) -> None:
        self.setObjectName("BonPaymentsWorkspace")
        self.setStyleSheet(
            """
            QWidget#BonPaymentsWorkspace {
                background-color: #F8FAFC;
                color: #0F172A;
            }
            QWidget#BonPaymentsWorkspace QLabel {
                border: none;
                background: transparent;
            }
            QFrame#WorkspaceHeaderCard, QFrame#SummaryStatCard, QFrame#BonsTableCard {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 10px;
            }
            QFrame#ToolbarCard {
                background-color: #FFFFFF;
                border: none;
                border-bottom: 1px solid #E2E8F0;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }
            QFrame#BonsTableFooter {
                background-color: #F8FAFC;
                border: none;
                border-top: 1px solid #E2E8F0;
                border-bottom-left-radius: 10px;
                border-bottom-right-radius: 10px;
            }
            QLineEdit#SearchBonsInput {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 4px 12px;
                min-height: 28px;
                font-size: 13px;
                color: #0F172A;
            }
            QLineEdit#SearchBonsInput:focus {
                border: 1.5px solid #0E7471;
            }
            QTableWidget#BonsPaymentsTable {
                background-color: #FFFFFF;
                border: none;
                gridline-color: transparent;
                alternate-background-color: #F8FAFC;
                selection-background-color: #E6F4F1;
                selection-color: #0F172A;
            }
            QTableWidget#BonsPaymentsTable::item {
                padding: 4px 10px;
                border-bottom: 1px solid #F1F5F9;
                color: #0F172A;
            }
            QTableWidget#BonsPaymentsTable QHeaderView::section {
                background-color: #F8FAFC;
                color: #475569;
                font-weight: 700;
                font-size: 11px;
                padding: 6px 10px;
                border: none;
                border-bottom: 2px solid #0E7471;
                border-right: 1px solid #F1F5F9;
            }
            """
        )

        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(16, 14, 16, 14)
        self._root_layout.setSpacing(10)

        # 1. Header Card
        self.header_card = QFrame()
        self.header_card.setObjectName("WorkspaceHeaderCard")
        self._hdr_lay = QHBoxLayout(self.header_card)
        self._hdr_lay.setContentsMargins(14, 10, 14, 10)
        self._hdr_lay.setSpacing(10)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_duotone_icon(self._icon_name, 26).pixmap(26, 26))
        self._hdr_lay.addWidget(icon_lbl)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.lbl_title = QLabel(self._title_text)
        self.lbl_title.setStyleSheet("font-size: 17px; font-weight: 700; color: #0F172A;")
        self.lbl_title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.lbl_subtitle = QLabel(self._subtitle_text)
        self.lbl_subtitle.setStyleSheet("font-size: 12px; color: #64748B;")
        self.lbl_subtitle.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        title_col.addWidget(self.lbl_title)
        title_col.addWidget(self.lbl_subtitle)
        self._hdr_lay.addLayout(title_col, 1)

        self.btn_refresh = QPushButton("Actualiser")
        self.btn_refresh.setObjectName("BtnBonsRefresh")
        self.btn_refresh.setFixedHeight(34)
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setIcon(get_duotone_icon("refresh", 16))
        self.btn_refresh.setIconSize(QSize(16, 16))
        self.btn_refresh.setToolTip("Actualiser la liste des bons (F5 / Ctrl+R)")
        self.btn_refresh.setStyleSheet(
            """
            QPushButton#BtnBonsRefresh {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                color: #334155;
                font-size: 12px;
                font-weight: 600;
                padding: 0 12px;
            }
            QPushButton#BtnBonsRefresh:hover {
                background-color: #F8FAFC;
                border-color: #94A3B8;
                color: #0F172A;
            }
            QPushButton#BtnBonsRefresh:pressed { background-color: #F1F5F9; }
            """
        )
        self.btn_refresh.clicked.connect(self.refresh_bons)
        self._hdr_lay.addWidget(self.btn_refresh)
        self._root_layout.addWidget(self.header_card)

        # 2. Responsive KPI Summary Grid (4x1 on wide screens, 2x2 on narrow screens)
        self.kpi_grid = QGridLayout()
        self.kpi_grid.setSpacing(10)
        self.lbl_kpi_count, self.card_count = self._build_stat_card("Nombre de Bons", "0", "#0F172A")
        self.lbl_kpi_total, self.card_total = self._build_stat_card("Total TTC", "0,00 DA", "#0F172A")
        self.lbl_kpi_paid, self.card_paid = self._build_stat_card("Total Versé", "0,00 DA", "#0E7471")
        self.lbl_kpi_rem, self.card_rem = self._build_stat_card("Reste à Payer", "0,00 DA", "#D97706")
        self._kpi_cards = [self.card_count, self.card_total, self.card_paid, self.card_rem]
        self._kpi_is_grid_2x2: Optional[bool] = None
        self._apply_kpi_grid_layout(two_by_two=False)
        self._root_layout.addLayout(self.kpi_grid)

        # 3. Unified Table Card (Toolbar + Table/EmptyState + Footer)
        table_card = QFrame()
        table_card.setObjectName("BonsTableCard")
        tc_lay = QVBoxLayout(table_card)
        tc_lay.setContentsMargins(0, 0, 0, 0)
        tc_lay.setSpacing(0)

        toolbar = QFrame()
        toolbar.setObjectName("ToolbarCard")
        self._tb_lay = QBoxLayout(QBoxLayout.LeftToRight, toolbar)
        self._tb_lay.setContentsMargins(12, 8, 12, 8)
        self._tb_lay.setSpacing(8)

        self.txt_search = QLineEdit()
        self.txt_search.setObjectName("SearchBonsInput")
        self.txt_search.setFixedHeight(36)
        self.txt_search.setMinimumWidth(160)
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.setPlaceholderText("Rechercher par N° Bon, client, téléphone, facture...")
        if qta:
            self.txt_search.addAction(qta.icon("fa5s.search", color="#94A3B8"), QLineEdit.LeadingPosition)
        self.txt_search.textChanged.connect(self._apply_filters)
        self._tb_lay.addWidget(self.txt_search, 1)

        chips_row = QHBoxLayout()
        chips_row.setContentsMargins(0, 0, 0, 0)
        chips_row.setSpacing(6)
        self.filter_group = QButtonGroup(self)
        self.filter_group.setExclusive(True)

        self.btn_filter_all = self._create_filter_chip("Tous", "ALL", checked=True)
        self.btn_filter_pending = self._create_filter_chip("Reste à payer", "UNPAID_PARTIAL")
        self.btn_filter_paid = self._create_filter_chip("Soldés", "PAID")

        chips_row.addWidget(self.btn_filter_all)
        chips_row.addWidget(self.btn_filter_pending)
        chips_row.addWidget(self.btn_filter_paid)
        self._tb_lay.addLayout(chips_row)
        tc_lay.addWidget(toolbar)

        # 4. Bons Table
        self.bons_table = QTableWidget(0, 10)
        self.bons_table.setObjectName("BonsPaymentsTable")
        self.bons_table.setHorizontalHeaderLabels(
            [
                "N° Bon",
                "Date",
                "Client",
                "Facture",
                "Total TTC",
                "Payé",
                "Reste",
                "Statut",
                "Paiements",
                "Actions",
            ]
        )
        self.bons_table.verticalHeader().setVisible(False)
        self.bons_table.verticalHeader().setDefaultSectionSize(50)
        self.bons_table.horizontalHeader().setFixedHeight(38)
        self.bons_table.setAlternatingRowColors(True)
        self.bons_table.setShowGrid(False)
        self.bons_table.setWordWrap(False)
        self.bons_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.bons_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.bons_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.bons_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.bons_table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.bons_table.setItemDelegateForColumn(7, BonStatusBadgeDelegate(self.bons_table))
        self.bons_table.installEventFilter(self)

        header_alignments = {
            0: Qt.AlignLeft | Qt.AlignVCenter,
            1: Qt.AlignCenter,
            2: Qt.AlignLeft | Qt.AlignVCenter,
            3: Qt.AlignLeft | Qt.AlignVCenter,
            4: Qt.AlignRight | Qt.AlignVCenter,
            5: Qt.AlignRight | Qt.AlignVCenter,
            6: Qt.AlignRight | Qt.AlignVCenter,
            7: Qt.AlignCenter,
            8: Qt.AlignCenter,
            9: Qt.AlignCenter,
        }
        for col_idx, align in header_alignments.items():
            if self.bons_table.horizontalHeaderItem(col_idx) is not None:
                self.bons_table.horizontalHeaderItem(col_idx).setTextAlignment(align)

        hdr = self.bons_table.horizontalHeader()
        hdr.setMinimumSectionSize(60)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.Interactive)
        self.bons_table.setColumnWidth(2, 180)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(7, QHeaderView.Fixed)
        self.bons_table.setColumnWidth(7, 102)
        hdr.setSectionResizeMode(8, QHeaderView.Fixed)
        self.bons_table.setColumnWidth(8, 84)
        hdr.setSectionResizeMode(9, QHeaderView.Fixed)
        self.bons_table.setColumnWidth(9, 325)

        self.bons_table.cellDoubleClicked.connect(self._on_row_double_clicked)
        tc_lay.addWidget(self.bons_table, 1)

        # Empty State when search/filters return 0 bons
        self.bons_empty_state = QFrame()
        self.bons_empty_state.setObjectName("BonsEmptyState")
        self.bons_empty_state.setStyleSheet(
            """
            QFrame#BonsEmptyState {
                background-color: #FFFFFF;
                border: none;
            }
            QFrame#BonsEmptyState QLabel { border: none; background: transparent; }
            """
        )
        es_lay = QVBoxLayout(self.bons_empty_state)
        es_lay.setAlignment(Qt.AlignCenter)
        es_lay.setSpacing(10)

        es_icon = QLabel()
        es_icon.setAlignment(Qt.AlignCenter)
        es_icon.setPixmap(get_duotone_icon(self._icon_name, 40).pixmap(40, 40))
        es_lay.addWidget(es_icon)

        es_title = QLabel("Aucun bon trouvé")
        es_title.setAlignment(Qt.AlignCenter)
        es_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #0F172A;")
        es_lay.addWidget(es_title)

        es_desc = QLabel("Aucun bon ne correspond à votre recherche ou aux filtres sélectionnés.")
        es_desc.setAlignment(Qt.AlignCenter)
        es_desc.setStyleSheet("font-size: 12px; color: #64748B;")
        es_lay.addWidget(es_desc)

        self.btn_empty_reset = QPushButton("Réinitialiser les filtres")
        self.btn_empty_reset.setObjectName("BtnBonsEmptyReset")
        self.btn_empty_reset.setIcon(get_duotone_icon("refresh", 16))
        self.btn_empty_reset.setIconSize(QSize(16, 16))
        self.btn_empty_reset.setFixedHeight(34)
        self.btn_empty_reset.setCursor(Qt.PointingHandCursor)
        self.btn_empty_reset.setStyleSheet(
            """
            QPushButton#BtnBonsEmptyReset {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                color: #334155;
                font-size: 12px;
                font-weight: 700;
                padding: 0 14px;
            }
            QPushButton#BtnBonsEmptyReset:hover { background-color: #F8FAFC; border-color: #94A3B8; }
            """
        )
        self.btn_empty_reset.clicked.connect(self._reset_filters)
        es_lay.addWidget(self.btn_empty_reset, alignment=Qt.AlignCenter)
        self.bons_empty_state.setVisible(False)
        tc_lay.addWidget(self.bons_empty_state, 1)

        footer_bar = QFrame()
        footer_bar.setObjectName("BonsTableFooter")
        f_lay = QHBoxLayout(footer_bar)
        f_lay.setContentsMargins(14, 6, 14, 6)
        f_lay.setSpacing(10)

        self.lbl_footer_info = QLabel("0 bon(s) affiché(s)")
        self.lbl_footer_info.setStyleSheet("font-size: 12px; font-weight: 600; color: #475569;")
        f_lay.addWidget(self.lbl_footer_info)
        f_lay.addStretch(1)

        self.lbl_hints = QLabel("Double-clic : détails  •  F5 : actualiser  •  Échap : réinitialiser")
        self.lbl_hints.setStyleSheet("font-size: 11px; color: #94A3B8;")
        self.lbl_hints.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        f_lay.addWidget(self.lbl_hints, 1, Qt.AlignRight)
        tc_lay.addWidget(footer_bar)

        self._root_layout.addWidget(table_card, 1)

        self._shortcut_f5 = QShortcut(QKeySequence(Qt.Key_F5), self)
        self._shortcut_f5.setContext(Qt.WidgetWithChildrenShortcut)
        self._shortcut_f5.activated.connect(self.refresh_bons)

        self._shortcut_ctrl_r = QShortcut(QKeySequence("Ctrl+R"), self)
        self._shortcut_ctrl_r.setContext(Qt.WidgetWithChildrenShortcut)
        self._shortcut_ctrl_r.activated.connect(self.refresh_bons)

        self._shortcut_esc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self._shortcut_esc.setContext(Qt.WidgetWithChildrenShortcut)
        self._shortcut_esc.activated.connect(self._reset_filters)

    def _apply_kpi_grid_layout(self, two_by_two: bool) -> None:
        if self._kpi_is_grid_2x2 is two_by_two:
            return
        self._kpi_is_grid_2x2 = two_by_two
        for card in self._kpi_cards:
            self.kpi_grid.removeWidget(card)
        for col in range(4):
            self.kpi_grid.setColumnStretch(col, 0)
        if two_by_two:
            positions = [(0, 0), (0, 1), (1, 0), (1, 1)]
            for idx, (r, c) in enumerate(positions):
                self.kpi_grid.addWidget(self._kpi_cards[idx], r, c)
            self.kpi_grid.setColumnStretch(0, 1)
            self.kpi_grid.setColumnStretch(1, 1)
        else:
            for idx, card in enumerate(self._kpi_cards):
                self.kpi_grid.addWidget(card, 0, idx)
                self.kpi_grid.setColumnStretch(idx, 1)

    def _apply_responsive_layout(self) -> None:
        """Adapts KPI grid, toolbar wrapping, chrome density, and visible table columns to viewport size."""
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return

        compact_h = h < 680
        narrow_w = w < 880

        self._root_layout.setContentsMargins(
            10 if narrow_w else 16,
            8 if compact_h else 14,
            10 if narrow_w else 16,
            8 if compact_h else 14,
        )
        self._root_layout.setSpacing(8 if (compact_h or narrow_w) else 10)
        self._hdr_lay.setContentsMargins(
            12 if narrow_w else 14,
            7 if compact_h else 10,
            12 if narrow_w else 14,
            7 if compact_h else 10,
        )
        self.lbl_subtitle.setVisible(not (compact_h or narrow_w))
        self.lbl_hints.setVisible(w >= 1120)

        card_h = 58 if compact_h else 72
        for card in self._kpi_cards:
            card.setFixedHeight(card_h)

        self._apply_kpi_grid_layout(two_by_two=(w < 860))
        self._tb_lay.setDirection(QBoxLayout.TopToBottom if w < 900 else QBoxLayout.LeftToRight)

        self._adjust_table_columns()

    def _adjust_table_columns(self) -> None:
        """Hides low-priority columns on small screens and stretches Client without crushing it."""
        if not hasattr(self, "bons_table") or self.bons_table is None:
            return
        vp_w = self.bons_table.viewport().width()
        if vp_w <= 0:
            return

        # Progressive disclosure of secondary columns based on available table width
        self.bons_table.setColumnHidden(3, vp_w < 1220)  # Facture
        self.bons_table.setColumnHidden(8, vp_w < 1220)  # Paiements
        self.bons_table.setColumnHidden(1, vp_w < 1120)  # Date
        self.bons_table.setColumnHidden(5, vp_w < 1120)  # Payé
        self.bons_table.setColumnHidden(4, vp_w < 840)   # Total TTC (Reste remains visible)

        other_w = sum(
            self.bons_table.columnWidth(c)
            for c in range(self.bons_table.columnCount())
            if c != 2 and not self.bons_table.isColumnHidden(c)
        )
        min_client_w = 130 if vp_w < 1080 else 160
        target_client_w = max(min_client_w, vp_w - other_w)
        if self.bons_table.columnWidth(2) != target_client_w:
            self.bons_table.setColumnWidth(2, target_client_w)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is getattr(self, "bons_table", None) and event.type() == QEvent.Resize:
            self._adjust_table_columns()
        return super().eventFilter(watched, event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._apply_responsive_layout()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_responsive_layout()

    def _build_stat_card(self, label_text: str, value_text: str, color_hex: str):
        card = QFrame()
        card.setObjectName("SummaryStatCard")
        card.setMinimumWidth(120)
        card.setFixedHeight(72)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(2)

        lbl_name = QLabel(label_text)
        lbl_name.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: #64748B; letter-spacing: 0.3px;"
        )
        lbl_val = QLabel(value_text)
        lbl_val.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {color_hex};")

        lay.addWidget(lbl_name)
        lay.addWidget(lbl_val)
        return lbl_val, card

    def _create_filter_chip(self, label: str, code: str, checked: bool = False) -> QPushButton:
        btn = QPushButton(label)
        btn.setObjectName("BonsFilterChip")
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setFixedHeight(36)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            """
            QPushButton#BonsFilterChip {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                color: #334155;
                font-size: 12px;
                font-weight: 600;
                padding: 0px 14px;
                min-height: 36px;
                max-height: 36px;
            }
            QPushButton#BonsFilterChip:checked {
                background-color: #CCFBF1;
                border: 1.5px solid #0E7471;
                color: #0E7471;
                font-weight: 700;
            }
            QPushButton#BonsFilterChip:hover:!checked {
                background-color: #F8FAFC;
                border-color: #94A3B8;
            }
            """
        )
        btn.clicked.connect(lambda _=False, c=code: self._set_status_filter(c))
        self.filter_group.addButton(btn)
        return btn

    def _set_status_filter(self, code: str) -> None:
        self._active_status_filter = code
        self._apply_filters()

    def _reset_filters(self) -> None:
        self._active_status_filter = "ALL"
        if hasattr(self, "btn_filter_all"):
            self.btn_filter_all.setChecked(True)
        if hasattr(self, "txt_search"):
            self.txt_search.clear()
        self._apply_filters()
        if hasattr(self, "txt_search"):
            self.txt_search.setFocus()

    def refresh_bons(self) -> None:
        """Reloads bons of the configured Bond_Type from BondLifecycleManager."""
        if self._bonds_mgr is None:
            self._bonds_mgr = _resolve_bonds_manager(self.data_manager)

        raw_rows: Any = []
        if self._bonds_mgr is not None and hasattr(self._bonds_mgr, "get_bons_with_payments"):
            try:
                raw_rows = self._bonds_mgr.get_bons_with_payments(bond_type=self.bond_type)
            except Exception as err:
                logger.error(f"Failed loading bons for {self.bond_type}: {err}")
                raw_rows = []

        if isinstance(raw_rows, (list, tuple)):
            self._all_bons = [dict(r) for r in raw_rows]
        else:
            self._all_bons = []

        self._apply_filters()

    def _apply_filters(self) -> None:
        q = (self.txt_search.text() or "").strip().lower()
        sf = self._active_status_filter

        filtered: List[Dict[str, Any]] = []
        for bon in self._all_bons:
            state = str(bon.get("Payment_State") or "").upper()
            if not state:
                rem = float(bon.get("Remaining_Amount") or 0.0)
                paid = float(bon.get("Total_Paid") or 0.0)
                tot = float(bon.get("Total_Amount_TTC") or 0.0)
                state = "PAID" if (tot > 0 and rem <= 0.01) else ("PARTIAL" if paid > 0.01 else "UNPAID")

            if sf == "UNPAID_PARTIAL" and state == "PAID":
                continue
            if sf == "PAID" and state != "PAID":
                continue

            if q:
                haystack = " ".join(
                    str(bon.get(k) or "")
                    for k in (
                        "Order_Number",
                        "Invoice_No",
                        "Client_Name",
                        "Client_Phone",
                        "Delivery_Address",
                    )
                ).lower()
                if q not in haystack:
                    continue

            filtered.append(bon)

        self._filtered_bons = filtered
        self._update_kpis()
        self._populate_table()

    def _update_kpis(self) -> None:
        count = len(self._filtered_bons)
        sum_total = sum(float(b.get("Total_Amount_TTC") or 0.0) for b in self._filtered_bons)
        sum_paid = sum(float(b.get("Total_Paid") or 0.0) for b in self._filtered_bons)
        sum_rem = sum(float(b.get("Remaining_Amount") or 0.0) for b in self._filtered_bons)

        self.lbl_kpi_count.setText(str(count))
        self.lbl_kpi_total.setText(f"{format_money(sum_total)} DA")
        self.lbl_kpi_paid.setText(f"{format_money(sum_paid)} DA")
        self.lbl_kpi_rem.setText(f"{format_money(sum_rem)} DA")
        self.lbl_footer_info.setText(f"{count} bon(s) affiché(s)")

        # Update segmented filter chip counts across all loaded bons
        total_all = len(self._all_bons)
        pending_count = 0
        paid_count = 0
        for bon in self._all_bons:
            state = str(bon.get("Payment_State") or "").upper()
            if not state:
                rem = float(bon.get("Remaining_Amount") or 0.0)
                paid = float(bon.get("Total_Paid") or 0.0)
                tot = float(bon.get("Total_Amount_TTC") or 0.0)
                state = "PAID" if (tot > 0 and rem <= 0.01) else ("PARTIAL" if paid > 0.01 else "UNPAID")
            if state == "PAID":
                paid_count += 1
            else:
                pending_count += 1
        self.btn_filter_all.setText(f"Tous ({total_all})")
        self.btn_filter_pending.setText(f"Reste à payer ({pending_count})")
        self.btn_filter_paid.setText(f"Soldés ({paid_count})")

    def _populate_table(self) -> None:
        self.bons_table.setRowCount(0)
        has_rows = len(self._filtered_bons) > 0
        if hasattr(self, "bons_empty_state"):
            self.bons_table.setVisible(has_rows)
            self.bons_empty_state.setVisible(not has_rows)
        bold_font = QFont()
        bold_font.setBold(True)

        for row_idx, bon in enumerate(self._filtered_bons):
            self.bons_table.insertRow(row_idx)
            self.bons_table.setRowHeight(row_idx, 50)

            ord_num = str(bon.get("Order_Number") or f"#{bon.get('Order_ID', '')}")
            date_str = str(bon.get("Order_Date") or "")[:10]
            client_name = str(bon.get("Client_Name") or "Client Comptoir")
            phone = str(bon.get("Client_Phone") or "").strip()
            client_display = f"{client_name} ({phone})" if phone else client_name
            inv_no = str(bon.get("Invoice_No") or "En attente")

            total_ttc = float(bon.get("Total_Amount_TTC") or 0.0)
            total_paid = float(bon.get("Total_Paid") or 0.0)
            remaining = max(0.0, float(bon.get("Remaining_Amount") if bon.get("Remaining_Amount") is not None else max(0.0, total_ttc - total_paid)))
            pay_count = int(bon.get("Payments_Count") or 0)

            if total_ttc > 0.0 and remaining <= 0.01:
                status_text = "Soldé"
            elif total_paid > 0.01:
                status_text = "Partiel"
            else:
                status_text = "Non payé"

            it_num = QTableWidgetItem(ord_num)
            it_num.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            it_num.setFont(bold_font)

            it_date = QTableWidgetItem(date_str)
            it_date.setTextAlignment(Qt.AlignCenter)
            it_date.setForeground(QColor("#475569"))

            it_client = QTableWidgetItem(client_display)
            it_client.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            it_inv = QTableWidgetItem(inv_no)
            it_inv.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            if inv_no == "En attente":
                it_inv.setForeground(QColor("#64748B"))

            it_tot = QTableWidgetItem(f"{format_money(total_ttc)} DA")
            it_tot.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_tot.setFont(bold_font)

            it_paid = QTableWidgetItem(f"{format_money(total_paid)} DA")
            it_paid.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_paid.setFont(bold_font)
            it_paid.setForeground(QColor("#0E7471"))

            it_rem = QTableWidgetItem(f"{format_money(remaining)} DA")
            it_rem.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_rem.setFont(bold_font)
            it_rem.setForeground(QColor("#D97706") if remaining > 0.01 else QColor("#16A34A"))

            it_status = QTableWidgetItem(status_text)
            it_status.setTextAlignment(Qt.AlignCenter)

            it_count = QTableWidgetItem(f"{pay_count}")
            it_count.setTextAlignment(Qt.AlignCenter)

            self.bons_table.setItem(row_idx, 0, it_num)
            self.bons_table.setItem(row_idx, 1, it_date)
            self.bons_table.setItem(row_idx, 2, it_client)
            self.bons_table.setItem(row_idx, 3, it_inv)
            self.bons_table.setItem(row_idx, 4, it_tot)
            self.bons_table.setItem(row_idx, 5, it_paid)
            self.bons_table.setItem(row_idx, 6, it_rem)
            self.bons_table.setItem(row_idx, 7, it_status)
            self.bons_table.setItem(row_idx, 8, it_count)

            # Rich tooltip exposes full details even when secondary columns hide on small screens
            row_tooltip = (
                f"Bon : {ord_num}  |  Date : {date_str}\n"
                f"Client : {client_display}\n"
                f"Facture : {inv_no}  |  Paiements : {pay_count}\n"
                f"Total TTC : {format_money(total_ttc)} DA  |  Payé : {format_money(total_paid)} DA  |  Reste : {format_money(remaining)} DA"
            )
            for item in (it_num, it_date, it_client, it_inv, it_tot, it_paid, it_rem, it_status, it_count):
                item.setToolTip(row_tooltip)

            # Direct per-row action buttons: '+ <Versement>' and 'Modifier'
            action_cell = QWidget()
            action_cell.setStyleSheet("background: transparent;")
            a_lay = QHBoxLayout(action_cell)
            a_lay.setContentsMargins(4, 4, 4, 4)
            a_lay.setSpacing(6)
            a_lay.setAlignment(Qt.AlignVCenter)

            btn_add = QPushButton(f"+ {self._add_button_text}")
            btn_add.setObjectName("btn_row_add")
            btn_add.setFixedHeight(28)
            btn_add.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn_add.setCursor(Qt.PointingHandCursor)
            btn_add.setIcon(get_duotone_icon("payment_white", 16))
            btn_add.setIconSize(QSize(14, 14))
            btn_add.setEnabled(remaining > 0.01)
            if remaining > 0.01:
                btn_add.setToolTip("Ajouter une nouvelle tranche de paiement sur ce bon")
            elif total_ttc > 0.0:
                btn_add.setToolTip("Ce bon est déjà soldé (aucun reste à payer)")
            else:
                btn_add.setToolTip("Montant du bon nul (0,00 DA) — aucun paiement requis")
            btn_add.setStyleSheet(
                """
                QPushButton#btn_row_add {
                    background-color: #0E7471;
                    border: 1px solid #0E7471;
                    border-radius: 5px;
                    color: #FFFFFF;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 0px 10px;
                    min-height: 26px;
                    max-height: 26px;
                }
                QPushButton#btn_row_add:hover:enabled { background-color: #0A5C59; border-color: #0A5C59; }
                QPushButton#btn_row_add:disabled {
                    background-color: #F1F5F9;
                    color: #475569;
                    border: 1px solid #CBD5E1;
                }
                """
            )
            btn_add.clicked.connect(lambda _=False, b=bon: self.open_add_payment_for_bon(b))

            btn_edit = QPushButton("Modifier")
            btn_edit.setObjectName("btn_row_edit")
            btn_edit.setFixedHeight(28)
            btn_edit.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            btn_edit.setCursor(Qt.PointingHandCursor)
            btn_edit.setIcon(get_duotone_icon("edit", 14))
            btn_edit.setIconSize(QSize(14, 14))
            btn_edit.setToolTip("Voir et modifier les versements de ce bon")
            btn_edit.setStyleSheet(
                """
                QPushButton#btn_row_edit {
                    background-color: #FFFFFF;
                    border: 1px solid #CBD5E1;
                    border-radius: 5px;
                    color: #334155;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 0px 10px;
                    min-height: 26px;
                    max-height: 26px;
                }
                QPushButton#btn_row_edit:hover {
                    border-color: #94A3B8;
                    color: #0F172A;
                    background-color: #F8FAFC;
                }
                """
            )
            btn_edit.clicked.connect(lambda _=False, b=bon: self.open_manage_payments_for_bon(b))

            btn_edit_products = QPushButton("Produits")
            btn_edit_products.setObjectName("btn_row_edit_products")
            btn_edit_products.setIcon(get_duotone_icon("box_product", 14))
            btn_edit_products.setIconSize(QSize(14, 14))
            btn_edit_products.setFixedHeight(28)
            btn_edit_products.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            btn_edit_products.setCursor(Qt.PointingHandCursor)
            btn_edit_products.setToolTip("Modifier les produits, quantités et prix de ce bon")
            btn_edit_products.setStyleSheet(
                """
                QPushButton#btn_row_edit_products {
                    background-color: #FFFFFF;
                    border: 1px solid #0E7471;
                    border-radius: 5px;
                    color: #0E7471;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 0px 8px;
                    min-height: 26px;
                    max-height: 26px;
                }
                QPushButton#btn_row_edit_products:hover {
                    background-color: #CCFBF1;
                }
                """
            )
            btn_edit_products.clicked.connect(lambda _=False, b=bon: self.open_edit_products_for_bon(b))

            a_lay.addWidget(btn_add)
            a_lay.addWidget(btn_edit)
            a_lay.addWidget(btn_edit_products)
            self.bons_table.setCellWidget(row_idx, 9, action_cell)

        self._adjust_table_columns()

    def _on_row_double_clicked(self, row: int, _col: int) -> None:
        if 0 <= row < len(self._filtered_bons):
            self.open_manage_payments_for_bon(self._filtered_bons[row])

    def open_add_payment_for_bon(self, bon_data: Dict[str, Any]) -> bool:
        dlg = BonPaymentAddDialog(
            data_manager=self.data_manager,
            bon_data=bon_data,
            current_user=self.current_user,
            dialog_title=self._add_dialog_title,
            parent=self,
        )
        if dlg.exec() == QDialog.Accepted:
            order_id = int(bon_data.get("Order_ID") or 0)
            self.refresh_bons()
            self.paymentUpdated.emit(order_id)
            return True
        return False

    def open_manage_payments_for_bon(self, bon_data: Dict[str, Any]) -> bool:
        order_id = int(bon_data.get("Order_ID") or 0)
        dlg = BonPaymentsManageDialog(
            data_manager=self.data_manager,
            order_id=order_id,
            current_user=self.current_user,
            dialog_title=self._manage_dialog_title,
            parent=self,
        )
        dlg.exec()
        if dlg.has_changes:
            self.refresh_bons()
            self.paymentUpdated.emit(order_id)
            return True
        return False

    def open_edit_products_for_bon(self, bon_data: Dict[str, Any]) -> bool:
        order_id = int(bon_data.get("Order_ID") or 0)
        dlg = BonProductsEditDialog(
            data_manager=self.data_manager,
            bon_data=bon_data,
            current_user=self.current_user,
            parent=self,
        )
        if dlg.exec() == QDialog.Accepted and dlg.has_changes:
            self.refresh_bons()
            self.paymentUpdated.emit(order_id)
            return True
        return False
