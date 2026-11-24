# -*- coding: utf-8 -*-
"""
ui/widgets/appliance_desks/dispatch_desk_view.py
================================================
Dispatch Desk UI (Bureau de Sortie & Magasin - مكتب الإخراج والمخزن).
Displays all Caisse-confirmed Bons (both pending/incomplete and completed) with
status & type filters. Opening any Bon launches the large DispatchBonScanDialog
where the storekeeper performs a fresh complete scan of all pre-selected products
and confirms to emit a Bon de Sortie or Bon Rouge.
"""

import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
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
from ui.hardware.raw_input_filter import MultiScannerHIDManager
from ui.icons import get_duotone_icon
from ui.widgets.appliance_desks._theme import (
    BORDER_SUBTLE,
    BRAND_TEAL,
    BRAND_TEAL_TINT,
    BUREAUX_TABLE_QSS,
    CARD_BG,
    FILTER_CHIP_QSS,
    INPUT_QSS,
    PRIMARY_CTA_QSS,
    SLATE_OUTLINE_QSS,
    TEXT_PRIMARY,
)
from ui.widgets.appliance_desks.dispatch_bon_scan_dialog import DispatchBonScanDialog

logger = logging.getLogger("StockLam.UI.DispatchDesk")


class DispatchDeskWidget(QWidget):
    """
    Sortie Magasin workspace listing pending and completed Bons with filters
    and launching the large DispatchBonScanDialog for fresh scanning & Bon de Sortie / Bon Rouge confirmation.
    """

    stockDispatched = Signal(str, list)

    def __init__(
        self,
        data_manager=None,
        hid_manager: Optional[MultiScannerHIDManager] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.data_manager = data_manager
        self.hid_manager = hid_manager or MultiScannerHIDManager()
        self.hid_manager.bind_scanner_to_session("SCANNER_DISPATCH", "DISPATCH_DESK_SESSION")
        self.hid_manager.register_session_callback(
            "DISPATCH_DESK_SESSION",
            lambda dev_id, code: self.process_scanned_barcode(code),
        )

        self._all_dispatch_orders: List[Dict[str, Any]] = []
        self._dispatch_orders: List[Dict[str, Any]] = []
        self._active_dialog: Optional[DispatchBonScanDialog] = None
        self._init_ui()
        self.refresh_dispatch_queue()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._focus_primary_input)

    def _focus_primary_input(self) -> None:
        if hasattr(self, "txt_order_search"):
            self.txt_order_search.setFocus()

    def _reset_order_filters(self) -> None:
        if hasattr(self, "btn_status_all"):
            self.btn_status_all.setChecked(True)
        if hasattr(self, "btn_filter_all"):
            self.btn_filter_all.setChecked(True)
        if hasattr(self, "txt_order_search"):
            self.txt_order_search.clear()
        self._apply_order_filters()
        self._focus_primary_input()

    def _init_ui(self) -> None:
        self.setObjectName("DispatchDeskRoot")
        self.setStyleSheet(f"QWidget#DispatchDeskRoot {{ background-color: {CARD_BG}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(10)

        # 1. Flat Top Header + Filters Section
        header = QFrame()
        header.setObjectName("DispatchHeaderCard")
        header.setStyleSheet(f"""
            QFrame#DispatchHeaderCard {{
                background-color: {CARD_BG};
                border: none;
                border-bottom: 1px solid {BORDER_SUBTLE};
            }}
            QFrame#DispatchHeaderCard QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        header_v = QVBoxLayout(header)
        header_v.setContentsMargins(4, 4, 4, 10)
        header_v.setSpacing(8)

        # Row 1: Title + Status Filter Chips + Refresh
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        ic = QLabel()
        ic.setPixmap(get_duotone_icon("barcode_scan", 18).pixmap(18, 18))
        top_row.addWidget(ic)

        lbl_title = QLabel("Sortie Magasin — Bons Confirmés")
        lbl_title.setStyleSheet(f"font-size: 14.5px; font-weight: 800; color: {TEXT_PRIMARY};")
        top_row.addWidget(lbl_title)

        top_row.addSpacing(8)

        # Status Filter Group: Tous / Non complétés (En attente) / Complétés
        self._status_filter_group = QButtonGroup(self)
        self._status_filter_group.setExclusive(True)

        self.btn_status_pending = QPushButton("En attente (0)")
        self.btn_status_completed = QPushButton("Complétés (0)")
        self.btn_status_all = QPushButton("Tous (0)")

        for btn, code, tip in [
            (self.btn_status_pending, "PENDING", "Bons confirmés en Caisse en attente de scan et sortie"),
            (self.btn_status_completed, "COMPLETED", "Bons déjà scannés et sortis (Bon de Sortie / Bon Rouge)"),
            (self.btn_status_all, "ALL", "Afficher tous les bons (en attente et complétés)"),
        ]:
            btn.setCheckable(True)
            btn.setFixedHeight(32)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(FILTER_CHIP_QSS)
            btn.setToolTip(tip)
            btn.setProperty("status_code", code)
            self._status_filter_group.addButton(btn)
            top_row.addWidget(btn)

        self.btn_status_pending.setChecked(True)
        self._status_filter_group.buttonClicked.connect(lambda _b: self._apply_order_filters())

        top_row.addStretch(1)

        self.lbl_status = QLabel("Double-cliquez sur un bon pour scanner")
        self.lbl_status.setStyleSheet(
            f"font-size: 11.5px; font-weight: 700; color: {BRAND_TEAL}; background-color: {BRAND_TEAL_TINT}; "
            f"border: none; border-radius: 6px; padding: 5px 10px;"
        )
        top_row.addWidget(self.lbl_status)

        btn_refresh = QPushButton("Actualiser")
        btn_refresh.setIcon(get_duotone_icon("refresh", 16))
        btn_refresh.setIconSize(QSize(16, 16))
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setFixedHeight(34)
        btn_refresh.setToolTip("Actualiser la liste des bons (F5 / Ctrl+R)")
        btn_refresh.setStyleSheet(SLATE_OUTLINE_QSS)
        btn_refresh.clicked.connect(self.refresh_dispatch_queue)
        top_row.addWidget(btn_refresh)
        header_v.addLayout(top_row)

        # Row 2: Type Filter Chips (Tous / PC / PL / CR) + Search Input
        f_layout = QHBoxLayout()
        f_layout.setSpacing(8)

        self._type_filter_group = QButtonGroup(self)
        self._type_filter_group.setExclusive(True)

        self.btn_filter_all = QPushButton("Tous types (0)")
        self.btn_filter_pc = QPushButton("PC (0)")
        self.btn_filter_pl = QPushButton("PL (0)")
        self.btn_filter_cr = QPushButton("CR (0)")

        for btn, code, tip in [
            (self.btn_filter_all, "ALL", "Afficher tous les types de bons"),
            (self.btn_filter_pc, "PC", "Paiement Complet / Versement (PC)"),
            (self.btn_filter_pl, "PL", "Paiement à la Livraison (PL)"),
            (self.btn_filter_cr, "CR", "Paiement à Crédit (CR)"),
        ]:
            btn.setCheckable(True)
            btn.setFixedHeight(32)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(FILTER_CHIP_QSS)
            btn.setToolTip(tip)
            btn.setProperty("filter_code", code)
            self._type_filter_group.addButton(btn)
            f_layout.addWidget(btn)

        self.btn_filter_all.setChecked(True)
        self._type_filter_group.buttonClicked.connect(lambda _b: self._apply_order_filters())

        self.txt_order_search = QLineEdit()
        self.txt_order_search.setFixedHeight(34)
        self.txt_order_search.setClearButtonEnabled(True)
        self.txt_order_search.setStyleSheet(INPUT_QSS)
        self.txt_order_search.setPlaceholderText(
            "Rechercher ou scanner N° Bon, N° Sortie, Client ou Téléphone..."
        )
        self.txt_order_search.textChanged.connect(self._apply_order_filters)
        self.txt_order_search.returnPressed.connect(self._on_search_enter)
        f_layout.addWidget(self.txt_order_search, stretch=1)
        header_v.addLayout(f_layout)
        layout.addWidget(header)

        # 2. Bons Table (Pending & Completed)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "N° Bon",
            "Type",
            "Client",
            "Date",
            "Articles",
            "Total TTC",
            "Statut Sortie",
            "Action",
        ])
        self.table.setStyleSheet(BUREAUX_TABLE_QSS)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.horizontalHeader().setFixedHeight(38)
        self.table.setShowGrid(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self._on_table_double_clicked)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(7, QHeaderView.Fixed)
        self.table.setColumnWidth(7, 155)
        layout.addWidget(self.table, 1)

        # Empty State
        self.dispatch_empty_state = QFrame()
        self.dispatch_empty_state.setObjectName("DispatchEmptyState")
        self.dispatch_empty_state.setStyleSheet(
            f"QFrame#DispatchEmptyState {{ background-color: {CARD_BG}; border: 1px solid {BORDER_SUBTLE}; border-radius: 6px; }}"
            "QFrame#DispatchEmptyState QLabel { border: none; background: transparent; }"
        )
        de_lay = QVBoxLayout(self.dispatch_empty_state)
        de_lay.setAlignment(Qt.AlignCenter)
        de_lay.setSpacing(10)

        de_icon = QLabel()
        de_icon.setAlignment(Qt.AlignCenter)
        de_icon.setPixmap(get_duotone_icon("truck_delivery", 40).pixmap(40, 40))
        de_lay.addWidget(de_icon)

        self.lbl_dispatch_empty_title = QLabel("Aucun bon trouvé")
        self.lbl_dispatch_empty_title.setAlignment(Qt.AlignCenter)
        self.lbl_dispatch_empty_title.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {TEXT_PRIMARY};")
        de_lay.addWidget(self.lbl_dispatch_empty_title)

        self.lbl_dispatch_empty_desc = QLabel(
            "Aucun bon ne correspond aux filtres sélectionnés (En attente / Complétés)."
        )
        self.lbl_dispatch_empty_desc.setAlignment(Qt.AlignCenter)
        self.lbl_dispatch_empty_desc.setStyleSheet("font-size: 12px; color: #64748B;")
        de_lay.addWidget(self.lbl_dispatch_empty_desc)

        self.btn_empty_reset = QPushButton("Afficher tous les bons")
        self.btn_empty_reset.setIcon(get_duotone_icon("refresh", 16))
        self.btn_empty_reset.setIconSize(QSize(16, 16))
        self.btn_empty_reset.setFixedHeight(34)
        self.btn_empty_reset.setCursor(Qt.PointingHandCursor)
        self.btn_empty_reset.setStyleSheet(SLATE_OUTLINE_QSS)
        self.btn_empty_reset.clicked.connect(self._reset_order_filters)
        de_lay.addWidget(self.btn_empty_reset, alignment=Qt.AlignCenter)
        self.dispatch_empty_state.setVisible(False)
        layout.addWidget(self.dispatch_empty_state, 1)

        # Shortcuts
        self._shortcut_f5 = QShortcut(QKeySequence(Qt.Key_F5), self)
        self._shortcut_f5.setContext(Qt.WidgetWithChildrenShortcut)
        self._shortcut_f5.activated.connect(self.refresh_dispatch_queue)

        self._shortcut_ctrl_r = QShortcut(QKeySequence("Ctrl+R"), self)
        self._shortcut_ctrl_r.setContext(Qt.WidgetWithChildrenShortcut)
        self._shortcut_ctrl_r.activated.connect(self.refresh_dispatch_queue)

        self._shortcut_esc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self._shortcut_esc.setContext(Qt.WidgetWithChildrenShortcut)
        self._shortcut_esc.activated.connect(self._reset_order_filters)

    def refresh_dispatch_queue(self) -> None:
        orders: List[Dict[str, Any]] = []
        if self.data_manager and hasattr(self.data_manager, "bonds"):
            try:
                orders = self.data_manager.bonds.get_dispatch_order_queue(include_completed=True) or []
            except TypeError:
                orders = self.data_manager.bonds.get_dispatch_order_queue() or []
            except Exception as err:
                logger.error(f"Error fetching dispatch queue: {err}")
                orders = []

        self._all_dispatch_orders = orders
        self._update_filter_counts()
        self._apply_order_filters()

    @staticmethod
    def _order_short_type(order: Dict[str, Any]) -> str:
        b_type = str(order.get("Bond_Type") or "BON_C").upper()
        if b_type == "BON_LIVRAISON":
            return "PL"
        if b_type == "BON_CREDIT":
            return "CR"
        return "PC"

    @staticmethod
    def _is_order_completed(order: Dict[str, Any]) -> bool:
        if "Is_Completed" in order:
            return bool(order.get("Is_Completed"))
        return str(order.get("Status") or "").upper() in ("COMPLETED", "DISPATCHED_PENDING_COD")

    def _update_filter_counts(self) -> None:
        orders = self._all_dispatch_orders
        pending_cnt = sum(1 for o in orders if not self._is_order_completed(o))
        completed_cnt = len(orders) - pending_cnt

        self.btn_status_pending.setText(f"En attente ({pending_cnt})")
        self.btn_status_completed.setText(f"Complétés ({completed_cnt})")
        self.btn_status_all.setText(f"Tous ({len(orders)})")

        pc_cnt = sum(1 for o in orders if self._order_short_type(o) == "PC")
        pl_cnt = sum(1 for o in orders if self._order_short_type(o) == "PL")
        cr_cnt = sum(1 for o in orders if self._order_short_type(o) == "CR")
        self.btn_filter_all.setText(f"Tous types ({len(orders)})")
        self.btn_filter_pc.setText(f"PC ({pc_cnt})")
        self.btn_filter_pl.setText(f"PL ({pl_cnt})")
        self.btn_filter_cr.setText(f"CR ({cr_cnt})")

    def _apply_order_filters(self) -> None:
        orders = self._all_dispatch_orders
        status_code = "ALL"
        if self._status_filter_group.checkedButton():
            status_code = str(self._status_filter_group.checkedButton().property("status_code") or "ALL")

        type_code = "ALL"
        if self._type_filter_group.checkedButton():
            type_code = str(self._type_filter_group.checkedButton().property("filter_code") or "ALL")

        q = self.txt_order_search.text().strip().lower()
        q_norm = q.replace("-", "").replace(" ", "")

        filtered: List[Dict[str, Any]] = []
        for o in orders:
            is_comp = self._is_order_completed(o)
            if status_code == "PENDING" and is_comp:
                continue
            if status_code == "COMPLETED" and not is_comp:
                continue

            short_t = self._order_short_type(o)
            if type_code != "ALL" and short_t != type_code:
                continue

            if q:
                ord_num = str(o.get("Order_Number") or "").lower()
                ord_norm = ord_num.replace("-", "").replace(" ", "")
                exit_num = str(o.get("Exit_Bond_Number") or "").lower()
                client_name = str(o.get("Client_Name") or "").lower()
                phone = str(o.get("Client_Phone") or o.get("Phone") or "").lower()
                phone_norm = phone.replace("-", "").replace(" ", "")
                if not (
                    q in ord_num
                    or (q_norm and q_norm in ord_norm)
                    or q in exit_num
                    or q in client_name
                    or q in phone
                    or (q_norm and q_norm in phone_norm)
                ):
                    continue
            filtered.append(o)

        self._dispatch_orders = filtered
        self._populate_bons_table()

    def _populate_bons_table(self) -> None:
        self.table.setRowCount(0)
        has_rows = len(self._dispatch_orders) > 0
        self.table.setVisible(has_rows)
        self.dispatch_empty_state.setVisible(not has_rows)

        bold_font = QFont("Segoe UI", 10, QFont.Bold)
        for row_idx, order in enumerate(self._dispatch_orders):
            self.table.insertRow(row_idx)
            is_comp = self._is_order_completed(order)
            short_t = self._order_short_type(order)
            ord_num = str(order.get("Order_Number") or f"#{order.get('Order_ID', '')}")
            client_name = str(order.get("Client_Name") or "Client Comptoir")
            phone = str(order.get("Client_Phone") or "").strip()
            client_disp = f"{client_name} ({phone})" if phone else client_name
            date_disp = str(order.get("Order_Date") or "")[:16]

            lines = order.get("lines") or []
            total_units = sum(int(l.get("Quantity_Ordered") or 0) for l in lines)
            disp_units = sum(int(l.get("Quantity_Dispatched") or 0) for l in lines)
            articles_disp = f"{disp_units}/{total_units} unité(s) ({len(lines)} réf)"
            total_ttc = float(order.get("Total_Amount_TTC") or 0.0)

            it_num = QTableWidgetItem(ord_num)
            it_num.setFont(bold_font)
            it_num.setData(Qt.UserRole, order)
            self.table.setItem(row_idx, 0, it_num)

            it_type = QTableWidgetItem(short_t)
            it_type.setTextAlignment(Qt.AlignCenter)
            it_type.setFont(bold_font)
            type_colors = {"PC": "#0F766E", "PL": "#B45309", "CR": "#1D4ED8"}
            it_type.setForeground(QColor(type_colors.get(short_t, "#334155")))
            self.table.setItem(row_idx, 1, it_type)

            self.table.setItem(row_idx, 2, QTableWidgetItem(client_disp))

            it_date = QTableWidgetItem(date_disp)
            it_date.setTextAlignment(Qt.AlignCenter)
            it_date.setForeground(QColor("#475569"))
            self.table.setItem(row_idx, 3, it_date)

            it_art = QTableWidgetItem(articles_disp)
            it_art.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 4, it_art)

            it_tot = QTableWidgetItem(f"{format_money(total_ttc)} DA")
            it_tot.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_tot.setFont(bold_font)
            self.table.setItem(row_idx, 5, it_tot)

            if is_comp:
                exit_no = str(order.get("Exit_Bond_Number") or "")
                doc_tag = "Bon Rouge" if order.get("Exit_Doc_Type") == "BON_ROUGE" else "Bon de Sortie"
                st_text = f"Complété • {doc_tag}" + (f" ({exit_no})" if exit_no else "")
                st_color = "#B91C1C" if order.get("Exit_Doc_Type") == "BON_ROUGE" else "#15803D"
            else:
                st_text = "En attente de scan"
                st_color = "#D97706"

            it_st = QTableWidgetItem(st_text)
            it_st.setTextAlignment(Qt.AlignCenter)
            it_st.setFont(QFont("Segoe UI", 9, QFont.Bold))
            it_st.setForeground(QColor(st_color))
            self.table.setItem(row_idx, 6, it_st)

            # Action Button Cell
            cell_w = QWidget()
            cell_lay = QHBoxLayout(cell_w)
            cell_lay.setContentsMargins(6, 4, 6, 4)
            cell_lay.setAlignment(Qt.AlignCenter)

            btn_open = QPushButton("Voir / PDF" if is_comp else "Scanner Bon")
            btn_open.setIcon(get_duotone_icon("print" if is_comp else "barcode_scan_white", 15))
            btn_open.setIconSize(QSize(15, 15))
            btn_open.setFixedHeight(32)
            btn_open.setCursor(Qt.PointingHandCursor)
            btn_open.setStyleSheet(SLATE_OUTLINE_QSS if is_comp else PRIMARY_CTA_QSS)
            btn_open.clicked.connect(lambda _=False, o=order: self.open_bon_scan_dialog(o))
            cell_lay.addWidget(btn_open)
            self.table.setCellWidget(row_idx, 7, cell_w)

    def _on_table_double_clicked(self, index) -> None:
        row = index.row()
        if 0 <= row < len(self._dispatch_orders):
            self.open_bon_scan_dialog(self._dispatch_orders[row])

    def _on_search_enter(self) -> None:
        if len(self._dispatch_orders) == 1:
            self.open_bon_scan_dialog(self._dispatch_orders[0])

    def open_bon_scan_dialog(self, order_data: Dict[str, Any]) -> None:
        dlg = DispatchBonScanDialog(self.data_manager, order_data, parent=self)
        self._active_dialog = dlg
        try:
            if dlg.exec() == DispatchBonScanDialog.Accepted and dlg.dispatch_result:
                ord_num = str(order_data.get("Order_Number") or "")
                codes = [
                    c
                    for st in dlg._line_states
                    for c in st.get("scanned_codes", [])
                ]
                self.stockDispatched.emit(ord_num, codes)
                self.refresh_dispatch_queue()
        finally:
            self._active_dialog = None

    def process_scanned_barcode(self, raw_scan: str) -> None:
        """Routes hardware HID barcode scanner input either to the active scan dialog or search bar."""
        clean = str(raw_scan or "").strip()
        if not clean:
            return
        if self._active_dialog is not None and self._active_dialog.isVisible():
            self._active_dialog.process_scan(clean)
            return
        self.txt_order_search.setText(clean)
        self._apply_order_filters()
        if len(self._dispatch_orders) == 1:
            self.open_bon_scan_dialog(self._dispatch_orders[0])
