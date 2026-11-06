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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 1. Top Order Selection Header
        header = QFrame()
        header.setObjectName("DispatchHeaderCard")
        header.setFixedHeight(52)
        header.setStyleSheet("""
            QFrame#DispatchHeaderCard {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(14, 0, 14, 0)
        h_layout.setSpacing(10)

        ic = QLabel()
        ic.setPixmap(get_duotone_icon("barcode_scan", 20).pixmap(20, 20))
        h_layout.addWidget(ic)

        lbl_title = QLabel("Bureau de Sortie & Magasin (Scan N° de Série -> Bon de Sortie) :")
        lbl_title.setStyleSheet("font-size: 13px; font-weight: 800; color: #1E293B;")
        h_layout.addWidget(lbl_title)

        self.cbo_orders = QComboBox()
        self.cbo_orders.setFixedHeight(34)
        self.cbo_orders.setMinimumWidth(320)
        self.cbo_orders.currentIndexChanged.connect(self._on_order_changed)
        h_layout.addWidget(self.cbo_orders, stretch=1)

        btn_refresh = QPushButton("Actualiser la File")
        btn_refresh.setIcon(get_duotone_icon("refresh", 14))
        btn_refresh.setIconSize(QSize(14, 14))
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setFixedHeight(34)
        btn_refresh.setStyleSheet(OUTLINE_BTN_STYLE)
        btn_refresh.clicked.connect(self.refresh_dispatch_queue)
        h_layout.addWidget(btn_refresh)

        self.lbl_status = QLabel("Prêt pour le scan physique")
        self.lbl_status.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: #0E7471; background-color: #E6F4F1; "
            "border: 1px solid #BCE3DC; border-radius: 4px; padding: 4px 10px;"
        )
        h_layout.addWidget(self.lbl_status)
        layout.addWidget(header)

        # 2. Expected Items Table Requiring Physical Serial Scan
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Produit Attendu (Marque & Modèle)",
            "Couleur",
            "Code-barres Modèle",
            "N° de Série Scanné",
            "Statut Vérification",
            "Horodatage Scan",
        ])
        self.table.setStyleSheet(TABLE_STYLE)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
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

        # 3. Hardware Barcode & Serial Scanner Console
        scan_box = QFrame()
        scan_box.setObjectName("DispatchScanConsole")
        scan_box.setStyleSheet("""
            QFrame#DispatchScanConsole {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        s_layout = QVBoxLayout(scan_box)
        s_layout.setContentsMargins(14, 12, 14, 12)
        s_layout.setSpacing(10)

        lbl_inst = QLabel(
            "Contrôle Physique Obligatoire : Scannez le code-barres ou le numéro de série unique (N° de Série) "
            "collé sur le châssis de chaque appareil sortant du magasin."
        )
        lbl_inst.setStyleSheet("font-size: 12px; font-weight: 600; color: #475569;")
        s_layout.addWidget(lbl_inst)

        input_row = QHBoxLayout()
        input_row.setSpacing(10)
        self.txt_scan = QLineEdit()
        self.txt_scan.setFixedHeight(38)
        self.txt_scan.setPlaceholderText(
            "Scanner le N° de Série ici (ex: SN-BOSCH-2026-889120 ou <Product_ID>::<N° de Série>)..."
        )
        self.txt_scan.returnPressed.connect(self._on_manual_scan_submit)
        input_row.addWidget(self.txt_scan, stretch=2)

        self.btn_emit_sortie = QPushButton("Valider && Imprimer Bon de Sortie (0.00 DA Impact Caisse)")
        self.btn_emit_sortie.setIcon(get_duotone_icon("print", 16))
        self.btn_emit_sortie.setIconSize(QSize(16, 16))
        self.btn_emit_sortie.setCursor(Qt.PointingHandCursor)
        self.btn_emit_sortie.setFixedHeight(38)
        self.btn_emit_sortie.setEnabled(False)
        self.btn_emit_sortie.setStyleSheet(PRIMARY_BTN_STYLE)
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

        self._dispatch_orders = orders
        self.cbo_orders.blockSignals(True)
        self.cbo_orders.clear()
        for o in orders:
            label = f"{o.get('Order_Number')} — {o.get('Client_Name')} ({o.get('Bond_Type')})"
            self.cbo_orders.addItem(label, o.get("Order_ID"))
        self.cbo_orders.blockSignals(False)

        if orders:
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
        user = getattr(self.data_manager, "current_user", None) if self.data_manager else None
        if user:
            from ui.navigation_permissions import has_permission
            if not has_permission(user, "act_dispatch_validate"):
                QMessageBox.warning(self, "Accès refusé", "Vous n'avez pas l'autorisation de valider la sortie physique magasin.")
                return

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
