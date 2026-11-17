# -*- coding: utf-8 -*-
"""
Reusable enterprise workspace for managing Bon payments (Bons de Versement and
Bons de Paiement Livraison) with organized bon listing and direct per-row
add & edit payment actions.
"""

import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
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

logger = logging.getLogger("StockLam.UI.BonPaymentsWorkspace")


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
            QLabel {
                border: none;
                background: transparent;
            }
            QFrame#WorkspaceHeaderCard, QFrame#SummaryStatCard, QFrame#ToolbarCard {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 10px;
            }
            QLineEdit#SearchBonsInput {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 13px;
                color: #0F172A;
            }
            QLineEdit#SearchBonsInput:focus {
                border: 1.5px solid #0E7471;
            }
            QTableWidget#BonsPaymentsTable {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                gridline-color: #F1F5F9;
                alternate-background-color: #F8FAFC;
                selection-background-color: #E6F4F1;
                selection-color: #0F172A;
            }
            QTableWidget#BonsPaymentsTable QHeaderView::section {
                background-color: #F8FAFC;
                color: #0F172A;
                font-weight: 700;
                font-size: 12px;
                padding: 6px 10px;
                border: none;
                border-bottom: 2px solid #0E7471;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        # 1. Header Card
        header_card = QFrame()
        header_card.setObjectName("WorkspaceHeaderCard")
        hdr_lay = QHBoxLayout(header_card)
        hdr_lay.setContentsMargins(16, 12, 16, 12)
        hdr_lay.setSpacing(12)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_duotone_icon(self._icon_name, 28).pixmap(28, 28))
        hdr_lay.addWidget(icon_lbl)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.lbl_title = QLabel(self._title_text)
        self.lbl_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #0F172A;")
        self.lbl_subtitle = QLabel(self._subtitle_text)
        self.lbl_subtitle.setStyleSheet("font-size: 12px; color: #64748B;")
        title_col.addWidget(self.lbl_title)
        title_col.addWidget(self.lbl_subtitle)
        hdr_lay.addLayout(title_col, 1)

        self.btn_refresh = QPushButton("Actualiser")
        self.btn_refresh.setFixedHeight(36)
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setIcon(get_duotone_icon("refresh", 16))
        self.btn_refresh.setIconSize(QSize(16, 16))
        self.btn_refresh.setToolTip("Actualiser la liste des bons (F5 / Ctrl+R)")
        self.btn_refresh.setStyleSheet(
            """
            QPushButton {
                background-color: #FFFFFF;
                border: 1.5px solid #0E7471;
                border-radius: 6px;
                color: #0E7471;
                font-size: 12px;
                font-weight: 700;
                padding: 0 14px;
            }
            QPushButton:hover { background-color: #E6F4F1; }
            """
        )
        self.btn_refresh.clicked.connect(self.refresh_bons)
        hdr_lay.addWidget(self.btn_refresh)
        root.addWidget(header_card)

        # 2. Compact Proportional KPI Summary Strip
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)
        self.lbl_kpi_count, card_count = self._build_stat_card("Nombre de Bons", "0", "#0F172A")
        self.lbl_kpi_total, card_total = self._build_stat_card("Total TTC", "0,00 DA", "#0F172A")
        self.lbl_kpi_paid, card_paid = self._build_stat_card("Total Versé", "0,00 DA", "#0E7471")
        self.lbl_kpi_rem, card_rem = self._build_stat_card("Reste à Payer", "0,00 DA", "#D97706")
        kpi_row.addWidget(card_count)
        kpi_row.addWidget(card_total)
        kpi_row.addWidget(card_paid)
        kpi_row.addWidget(card_rem)
        kpi_row.addStretch(1)
        root.addLayout(kpi_row)

        # 3. Filter & Search Toolbar
        toolbar = QFrame()
        toolbar.setObjectName("ToolbarCard")
        tb_lay = QHBoxLayout(toolbar)
        tb_lay.setContentsMargins(12, 10, 12, 10)
        tb_lay.setSpacing(10)

        self.txt_search = QLineEdit()
        self.txt_search.setObjectName("SearchBonsInput")
        self.txt_search.setFixedHeight(36)
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.setPlaceholderText("Rechercher par N° Bon, client, téléphone, facture...")
        self.txt_search.textChanged.connect(self._apply_filters)
        tb_lay.addWidget(self.txt_search, 1)

        self.filter_group = QButtonGroup(self)
        self.filter_group.setExclusive(True)

        self.btn_filter_all = self._create_filter_chip("Tous", "ALL", checked=True)
        self.btn_filter_pending = self._create_filter_chip("Reste à payer", "UNPAID_PARTIAL")
        self.btn_filter_paid = self._create_filter_chip("Soldés", "PAID")

        tb_lay.addWidget(self.btn_filter_all)
        tb_lay.addWidget(self.btn_filter_pending)
        tb_lay.addWidget(self.btn_filter_paid)
        root.addWidget(toolbar)

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
        self.bons_table.verticalHeader().setDefaultSectionSize(46)
        self.bons_table.horizontalHeader().setFixedHeight(38)
        self.bons_table.setAlternatingRowColors(True)
        self.bons_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.bons_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        for col_idx in (4, 5, 6):
            if self.bons_table.horizontalHeaderItem(col_idx) is not None:
                self.bons_table.horizontalHeaderItem(col_idx).setTextAlignment(
                    Qt.AlignRight | Qt.AlignVCenter
                )

        hdr = self.bons_table.horizontalHeader()
        hdr.setMinimumSectionSize(75)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(9, QHeaderView.Fixed)
        self.bons_table.setColumnWidth(9, 230)

        self.bons_table.cellDoubleClicked.connect(self._on_row_double_clicked)
        root.addWidget(self.bons_table, 1)

        # Empty State when search/filters return 0 bons
        self.bons_empty_state = QFrame()
        self.bons_empty_state.setObjectName("BonsEmptyState")
        self.bons_empty_state.setStyleSheet(
            """
            QFrame#BonsEmptyState {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
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
        root.addWidget(self.bons_empty_state, 1)

        self._shortcut_f5 = QShortcut(QKeySequence(Qt.Key_F5), self)
        self._shortcut_f5.setContext(Qt.WidgetWithChildrenShortcut)
        self._shortcut_f5.activated.connect(self.refresh_bons)

        self._shortcut_ctrl_r = QShortcut(QKeySequence("Ctrl+R"), self)
        self._shortcut_ctrl_r.setContext(Qt.WidgetWithChildrenShortcut)
        self._shortcut_ctrl_r.activated.connect(self.refresh_bons)

        self._shortcut_esc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self._shortcut_esc.setContext(Qt.WidgetWithChildrenShortcut)
        self._shortcut_esc.activated.connect(self._reset_filters)

        # Empty/footer info label
        self.lbl_footer_info = QLabel("0 bon(s) affiché(s)")
        self.lbl_footer_info.setStyleSheet("font-size: 12px; color: #64748B;")
        root.addWidget(self.lbl_footer_info)

    def _build_stat_card(self, label_text: str, value_text: str, color_hex: str):
        card = QFrame()
        card.setObjectName("SummaryStatCard")
        card.setMinimumWidth(165)
        card.setMaximumWidth(250)
        card.setFixedHeight(68)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(2)

        lbl_name = QLabel(label_text)
        lbl_name.setStyleSheet(
            "font-size: 10.5px; font-weight: 700; color: #64748B; letter-spacing: 0.3px;"
        )
        lbl_val = QLabel(value_text)
        lbl_val.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {color_hex};")

        lay.addWidget(lbl_name)
        lay.addWidget(lbl_val)
        return lbl_val, card

    def _create_filter_chip(self, label: str, code: str, checked: bool = False) -> QPushButton:
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setFixedHeight(36)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            """
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                color: #334155;
                font-size: 12px;
                font-weight: 600;
                padding: 0 12px;
            }
            QPushButton:checked {
                background-color: #E6F4F1;
                border: 1.5px solid #0E7471;
                color: #0E7471;
                font-weight: 700;
            }
            QPushButton:hover:!checked { background-color: #F8FAFC; }
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
            self.bons_table.setRowHeight(row_idx, 46)

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
                status_color = QColor("#16A34A")
            elif total_paid > 0.01:
                status_text = "Partiel"
                status_color = QColor("#D97706")
            else:
                status_text = "Non payé"
                status_color = QColor("#DC2626")

            it_num = QTableWidgetItem(ord_num)
            it_num.setFont(bold_font)
            it_date = QTableWidgetItem(date_str)
            it_client = QTableWidgetItem(client_display)
            it_inv = QTableWidgetItem(inv_no)

            it_tot = QTableWidgetItem(format_money(total_ttc))
            it_tot.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_tot.setFont(bold_font)

            it_paid = QTableWidgetItem(format_money(total_paid))
            it_paid.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_paid.setFont(bold_font)
            it_paid.setForeground(QColor("#0E7471"))

            it_rem = QTableWidgetItem(format_money(remaining))
            it_rem.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_rem.setFont(bold_font)
            it_rem.setForeground(QColor("#D97706") if remaining > 0.01 else QColor("#16A34A"))

            it_status = QTableWidgetItem(status_text)
            it_status.setTextAlignment(Qt.AlignCenter)
            it_status.setFont(bold_font)
            it_status.setForeground(status_color)

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

            # Direct per-row action buttons: '+ <Versement>' and 'Modifier'
            action_cell = QWidget()
            action_cell.setStyleSheet("background: transparent;")
            a_lay = QHBoxLayout(action_cell)
            a_lay.setContentsMargins(6, 8, 6, 8)
            a_lay.setSpacing(6)

            btn_add = QPushButton(f"+ {self._add_button_text}")
            btn_add.setObjectName("btn_row_add")
            btn_add.setFixedHeight(28)
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
                QPushButton {
                    background-color: #0E7471;
                    border: 1px solid #0E7471;
                    border-radius: 5px;
                    color: #FFFFFF;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 2px 10px;
                }
                QPushButton:hover:enabled { background-color: #0A5C59; border-color: #0A5C59; }
                QPushButton:disabled {
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
            btn_edit.setCursor(Qt.PointingHandCursor)
            btn_edit.setIcon(get_duotone_icon("edit", 14))
            btn_edit.setIconSize(QSize(14, 14))
            btn_edit.setToolTip("Voir et modifier les versements de ce bon")
            btn_edit.setStyleSheet(
                """
                QPushButton {
                    background-color: #FFFFFF;
                    border: 1px solid #CBD5E1;
                    border-radius: 5px;
                    color: #0F172A;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 2px 10px;
                }
                QPushButton:hover {
                    border-color: #0E7471;
                    color: #0E7471;
                    background-color: #E6F4F1;
                }
                """
            )
            btn_edit.clicked.connect(lambda _=False, b=bon: self.open_manage_payments_for_bon(b))

            a_lay.addWidget(btn_add)
            a_lay.addWidget(btn_edit)
            self.bons_table.setCellWidget(row_idx, 9, action_cell)

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
