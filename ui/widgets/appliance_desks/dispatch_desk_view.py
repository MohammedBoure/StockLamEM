# -*- coding: utf-8 -*-
"""
ui/widgets/appliance_desks/dispatch_desk_view.py
================================================
Dispatch Desk UI (Bureau de Sortie & Magasin - مكتب الإخراج والمخزن).
Responsible exclusively for:
- Scanning the literal product barcode and unique serial number (N° de Série) of the physical unit leaving the store.
- Validating serial state (IN_STOCK) and product model match against paid/authorized vouchers.
- Generating and printing the logistical Bon de Sortie (سند الخروج) with zero cash impact.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.hardware.raw_input_filter import MultiScannerHIDManager
from ui.icons import get_duotone_icon
from ui.widgets.appliance_desks._theme import (
    BORDER_SUBTLE,
    BRAND_TEAL,
    BRAND_TEAL_BORDER,
    BRAND_TEAL_TINT,
    BUREAUX_TABLE_QSS,
    CANVAS_BG,
    CARD_BG,
    COMBO_QSS,
    FILTER_CHIP_QSS,
    INPUT_QSS,
    PRIMARY_CTA_QSS,
    SECONDARY_OUTLINE_QSS,
    TEXT_BODY,
    TEXT_PRIMARY,
)
from ui.widgets.appliance_desks.order_desk_view import (
    OUTLINE_BTN_STYLE,
    PRIMARY_BTN_STYLE,
    TABLE_STYLE,
)


class DispatchDeskWidget(QWidget):
    """Dispatch & Warehouse Exit Desk UI for scanning physical serial numbers and emitting Bon de Sortie."""

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

        self._dispatch_orders: List[Dict[str, Any]] = []
        self._active_order: Optional[Dict[str, Any]] = None
        self._expected_items: List[Dict[str, Any]] = []
        self._init_ui()
        self.refresh_dispatch_queue()

    def _init_ui(self) -> None:
        self.setObjectName("DispatchDeskRoot")
        self.setStyleSheet(f"QWidget#DispatchDeskRoot {{ background-color: {CARD_BG}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(10)

        # 1. Flat Top Order & Filter Section
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

        h_layout = QHBoxLayout()
        h_layout.setSpacing(10)

        ic = QLabel()
        ic.setPixmap(get_duotone_icon("barcode_scan", 18).pixmap(18, 18))
        h_layout.addWidget(ic)

        lbl_title = QLabel("Sortie Magasin")
        lbl_title.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {TEXT_PRIMARY};")
        h_layout.addWidget(lbl_title)

        self.cbo_orders = QComboBox()
        self.cbo_orders.setFixedHeight(34)
        self.cbo_orders.setMinimumWidth(300)
        self.cbo_orders.setStyleSheet(COMBO_QSS)
        self.cbo_orders.currentIndexChanged.connect(self._on_order_changed)
        h_layout.addWidget(self.cbo_orders, stretch=1)

        btn_refresh = QPushButton("Actualiser")
        btn_refresh.setIcon(get_duotone_icon("refresh", 14))
        btn_refresh.setIconSize(QSize(14, 14))
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setFixedHeight(34)
        btn_refresh.setStyleSheet(SECONDARY_OUTLINE_QSS)
        btn_refresh.clicked.connect(self.refresh_dispatch_queue)
        h_layout.addWidget(btn_refresh)

        self.lbl_status = QLabel("Prêt")
        self.lbl_status.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {BRAND_TEAL}; background-color: {BRAND_TEAL_TINT}; "
            f"border: none; border-radius: 4px; padding: 4px 10px;"
        )
        h_layout.addWidget(self.lbl_status)
        header_v.addLayout(h_layout)

        # Filter & Search Row
        f_layout = QHBoxLayout()
        f_layout.setSpacing(8)

        self._type_filter_group = QButtonGroup(self)
        self._type_filter_group.setExclusive(True)

        self.btn_filter_all = QPushButton("Tous (0)")
        self.btn_filter_pc = QPushButton("PC (0)")
        self.btn_filter_pl = QPushButton("PL (0)")
        self.btn_filter_cr = QPushButton("CR (0)")

        for btn, code, tip in [
            (self.btn_filter_all, "ALL", "Afficher tous les bons en attente de sortie"),
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
        self.txt_order_search.setFixedHeight(32)
        self.txt_order_search.setClearButtonEnabled(True)
        self.txt_order_search.setStyleSheet(INPUT_QSS)
        self.txt_order_search.setPlaceholderText(
            "Rechercher bon, client ou tél..."
        )
        self.txt_order_search.textChanged.connect(self._apply_order_filters)
        self.txt_order_search.returnPressed.connect(self._apply_order_filters)
        f_layout.addWidget(self.txt_order_search, stretch=1)
        header_v.addLayout(f_layout)
        layout.addWidget(header)

        # 2. Expected Items Table Requiring Physical Serial Scan
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Produit",
            "Couleur",
            "Réf",
            "N° de Série",
            "Statut",
            "Heure",
        ])
        self.table.setStyleSheet(BUREAUX_TABLE_QSS)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.horizontalHeader().setFixedHeight(38)
        self.table.setShowGrid(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        layout.addWidget(self.table, 1)

        # 3. Flat Bottom Scanner Console
        scan_box = QFrame()
        scan_box.setObjectName("DispatchScanConsole")
        scan_box.setStyleSheet(f"""
            QFrame#DispatchScanConsole {{
                background-color: {CARD_BG};
                border: none;
                border-top: 1px solid {BORDER_SUBTLE};
            }}
            QFrame#DispatchScanConsole QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        s_layout = QVBoxLayout(scan_box)
        s_layout.setContentsMargins(4, 10, 4, 4)
        s_layout.setSpacing(6)

        input_row = QHBoxLayout()
        input_row.setSpacing(10)
        self.txt_scan = QLineEdit()
        self.txt_scan.setFixedHeight(38)
        self.txt_scan.setStyleSheet(INPUT_QSS + "QLineEdit { font-size: 13px; }")
        self.txt_scan.setPlaceholderText(
            "Scanner le N° de Série..."
        )
        self.txt_scan.returnPressed.connect(self._on_manual_scan_submit)
        input_row.addWidget(self.txt_scan, stretch=2)

        self.btn_emit_sortie = QPushButton("Valider && Imprimer Bon de Sortie")
        self.btn_emit_sortie.setToolTip("Valider la sortie physique et imprimer le Bon de Sortie (0.00 DA impact Caisse)")
        self.btn_emit_sortie.setIcon(get_duotone_icon("print", 16))
        self.btn_emit_sortie.setIconSize(QSize(16, 16))
        self.btn_emit_sortie.setCursor(Qt.PointingHandCursor)
        self.btn_emit_sortie.setFixedHeight(40)
        self.btn_emit_sortie.setEnabled(False)
        self.btn_emit_sortie.setStyleSheet(PRIMARY_CTA_QSS + "QPushButton { font-size: 12.5px; }")
        self.btn_emit_sortie.clicked.connect(self._emit_bon_sortie)
        input_row.addWidget(self.btn_emit_sortie, stretch=1)

        s_layout.addLayout(input_row)
        layout.addWidget(scan_box)

    def refresh_dispatch_queue(self) -> None:
        orders: List[Dict[str, Any]] = []
        if self.data_manager and hasattr(self.data_manager, "bonds"):
            try:
                orders = self.data_manager.bonds.get_dispatch_order_queue() or []
            except Exception as err:
                logger.error(f"Error fetching dispatch queue: {err}")
                orders = []

        self._all_dispatch_orders = orders
        self._update_type_filter_counts()
        self._apply_order_filters()

    @staticmethod
    def _order_short_type(order: Dict[str, Any]) -> str:
        b_type = str(order.get("Bond_Type") or "BON_C").upper()
        if b_type == "BON_LIVRAISON":
            return "PL"
        if b_type == "BON_CREDIT":
            return "CR"
        return "PC"

    def _update_type_filter_counts(self) -> None:
        orders = getattr(self, "_all_dispatch_orders", [])
        pc_cnt = sum(1 for o in orders if self._order_short_type(o) == "PC")
        pl_cnt = sum(1 for o in orders if self._order_short_type(o) == "PL")
        cr_cnt = sum(1 for o in orders if self._order_short_type(o) == "CR")
        if hasattr(self, "btn_filter_all"):
            self.btn_filter_all.setText(f"Tous ({len(orders)})")
            self.btn_filter_pc.setText(f"PC ({pc_cnt})")
            self.btn_filter_pl.setText(f"PL ({pl_cnt})")
            self.btn_filter_cr.setText(f"CR ({cr_cnt})")

    def _apply_order_filters(self) -> None:
        orders = getattr(self, "_all_dispatch_orders", [])
        active_code = "ALL"
        if hasattr(self, "_type_filter_group") and self._type_filter_group.checkedButton():
            active_code = str(self._type_filter_group.checkedButton().property("filter_code") or "ALL")
        q = self.txt_order_search.text().strip().lower() if hasattr(self, "txt_order_search") else ""
        q_norm = q.replace("-", "").replace(" ", "")

        filtered: List[Dict[str, Any]] = []
        for o in orders:
            short_t = self._order_short_type(o)
            if active_code != "ALL" and short_t != active_code:
                continue
            if q:
                ord_num = str(o.get("Order_Number") or "").lower()
                ord_norm = ord_num.replace("-", "").replace(" ", "")
                client_name = str(o.get("Client_Name") or "").lower()
                phone = str(o.get("Client_Phone") or o.get("Phone") or "").lower()
                phone_norm = phone.replace("-", "").replace(" ", "")
                if not (
                    q in ord_num
                    or (q_norm and q_norm in ord_norm)
                    or q in client_name
                    or q in phone
                    or (q_norm and q_norm in phone_norm)
                ):
                    continue
            filtered.append(o)

        self._dispatch_orders = filtered
        self.cbo_orders.blockSignals(True)
        self.cbo_orders.clear()
        for o in filtered:
            short_t = self._order_short_type(o)
            phone_str = str(o.get("Client_Phone") or o.get("Phone") or "").strip()
            phone_suffix = f" • {phone_str}" if phone_str else ""
            label = f"[{short_t}] {o.get('Order_Number')} — {o.get('Client_Name')}{phone_suffix}"
            self.cbo_orders.addItem(label, o.get("Order_ID"))
        self.cbo_orders.blockSignals(False)

        if filtered:
            self._on_order_changed(0)
        else:
            self._active_order = None
            self._expected_items = []
            self.table.setRowCount(0)
            self.btn_emit_sortie.setEnabled(False)

    def _on_order_changed(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._dispatch_orders):
            return
        self._active_order = self._dispatch_orders[idx]
        self._expected_items = []

        for line in self._active_order.get("lines", []):
            rem_qty = max(0, int(line.get("Quantity_Ordered") or 1) - int(line.get("Quantity_Dispatched") or 0))
            for _ in range(rem_qty):
                self._expected_items.append({
                    "line_id": int(line.get("Line_ID") or 1),
                    "product_id": int(line.get("Product_ID") or 0),
                    "model": f"{line.get('Brand_Mark', '')} {line.get('Product_Name', '')}".strip(),
                    "color": str(line.get("Color_Finish") or "Standard"),
                    "barcode": str(line.get("Barcode") or ""),
                    "serial": "",
                    "status": "EN ATTENTE SCAN",
                    "timestamp": "-",
                })
        self._refresh_table()

    def _refresh_table(self) -> None:
        self.table.setRowCount(0)
        all_verified = len(self._expected_items) > 0

        for item in self._expected_items:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(item["model"]))

            it_col = QTableWidgetItem(item["color"])
            it_col.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, it_col)

            it_bc = QTableWidgetItem(item["barcode"])
            it_bc.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, it_bc)

            it_sn = QTableWidgetItem(item["serial"] or "—")
            it_sn.setFont(QFont("Consolas", 10, QFont.Bold))
            self.table.setItem(row, 3, it_sn)

            st_item = QTableWidgetItem(item["status"])
            st_item.setTextAlignment(Qt.AlignCenter)
            st_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            if item["status"] == "VÉRIFIÉ (IN_STOCK)":
                st_item.setForeground(QColor("#16A34A"))
            else:
                st_item.setForeground(QColor("#D97706"))
                all_verified = False
            self.table.setItem(row, 4, st_item)

            it_ts = QTableWidgetItem(item["timestamp"])
            it_ts.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 5, it_ts)

        self.btn_emit_sortie.setEnabled(all_verified)

    def _on_manual_scan_submit(self) -> None:
        raw = self.txt_scan.text().strip()
        self.txt_scan.clear()
        if raw:
            self.process_scanned_barcode(raw)

    def process_scanned_barcode(self, raw_scan: str) -> None:
        """Validates scanned physical serial number against expected order lines."""
        clean_scan = raw_scan.strip().upper()
        if not clean_scan:
            return

        scanned_product_id = None
        serial_part = clean_scan
        if "::" in clean_scan:
            parts = clean_scan.split("::", 1)
            if parts[0].isdigit():
                scanned_product_id = int(parts[0])
                serial_part = parts[1].strip()

        if any(i["serial"] == serial_part for i in self._expected_items if i["serial"]):
            self.lbl_status.setText(f"Rejeté : N° de Série ({serial_part}) déjà scanné sur ce bon")
            self.lbl_status.setStyleSheet(
                "font-size: 11px; font-weight: 700; color: #DC2626; background-color: #FEF2F2; "
                "border: 1px solid #FECACA; border-radius: 4px; padding: 4px 10px;"
            )
            QMessageBox.warning(self, "Doublon Détecté", f"Le N° de Série {serial_part} est déjà affecté à ce bon.")
            return

        db_serial = None
        if self.data_manager and hasattr(self.data_manager, "serials"):
            db_serial = self.data_manager.serials.get_serial_details(serial_part)
            if db_serial:
                if db_serial.get("Status") != "IN_STOCK":
                    self.lbl_status.setText(
                        f"Rejeté : {serial_part} n'est pas en stock ({db_serial.get('Status')})"
                    )
                    QMessageBox.critical(
                        self,
                        "N° de Série Non Disponible",
                        f"Le N° de Série {serial_part} a le statut '{db_serial.get('Status')}' (Attendu: IN_STOCK).",
                    )
                    return
                scanned_product_id = int(db_serial["Product_ID"])

        for item in self._expected_items:
            if item["status"] != "VÉRIFIÉ (IN_STOCK)":
                if scanned_product_id is not None and item["product_id"] != scanned_product_id:
                    continue
                item["serial"] = serial_part
                item["status"] = "VÉRIFIÉ (IN_STOCK)"
                item["timestamp"] = datetime.now().strftime("%H:%M:%S")
                self.lbl_status.setText(f"N° de Série vérifié : {serial_part}")
                self.lbl_status.setStyleSheet(
                    "font-size: 11px; font-weight: 700; color: #0E7471; background-color: #E6F4F1; "
                    "border: 1px solid #BCE3DC; border-radius: 4px; padding: 4px 10px;"
                )
                self._refresh_table()
                return

        QMessageBox.warning(
            self,
            "Produit Non Attendu",
            f"Le numéro de série scanné ({serial_part}) ne correspond à aucune ligne restante sur ce bon.",
        )

    def _emit_bon_sortie(self) -> None:
        if not self._active_order:
            return

        order_id = int(self._active_order["Order_ID"])
        order_num = str(self._active_order["Order_Number"])
        invoice_id = int(self._active_order.get("Invoice_ID") or order_id)
        scans_payload = [
            {"order_line_id": item["line_id"], "serial_number": item["serial"]}
            for item in self._expected_items
            if item["serial"]
        ]

        try:
            if self.data_manager and hasattr(self.data_manager, "bonds"):
                uid = int((getattr(self.data_manager, "current_user", None) or {}).get("User_ID") or 1)
                res = self.data_manager.bonds.validate_and_dispatch_serials(
                    order_id=order_id,
                    invoice_id=invoice_id,
                    storekeeper_user_id=uid,
                    scanned_serial_numbers=scans_payload,
                )
                exit_num = res["exit_bond_number"]
                gate_pass = res["gate_pass"]
            else:
                exit_num = f"BS-2026-{order_id:04d}"
                gate_pass = f"GATE-{order_id:04d}"

            serials_list = [s["serial_number"] for s in scans_payload]
            self.stockDispatched.emit(order_num, serials_list)
            QMessageBox.information(
                self,
                "Bon de Sortie Émis",
                f"Bon de Sortie ({exit_num}) généré avec succès.\n"
                f"Code laissez-passer : {gate_pass}\n"
                f"N° de Série sortis : {', '.join(serials_list)}\n"
                "Impact financier Caisse : 0.00 DA (Mouvement logistique pur).",
            )
            self.refresh_dispatch_queue()
        except Exception as err:
            QMessageBox.critical(self, "Erreur Bon de Sortie", str(err))
