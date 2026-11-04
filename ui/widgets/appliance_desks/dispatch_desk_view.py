# ui/widgets/appliance_desks/dispatch_desk_view.py
"""
Dispatch Desk UI (مكتب الإخراج والمخزن - Quai de Sortie / Dispatch Desk).
Responsible exclusivamente for:
- Scanning the literal product barcode and unique serial number (N° de Série) of the physical unit leaving the store.
- Validating serial state (IN_STOCK) and product model match against paid/authorized vouchers.
- Generating and printing the logistical Bon de Sortie (سند الخروج) with zero cash impact.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
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
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # 1. Top Order Selection Header
        header = QFrame()
        header.setStyleSheet("background: #FFFFFF; border: 1px solid #DDE3EA; border-radius: 8px; padding: 10px;")
        h_layout = QHBoxLayout(header)

        lbl_title = QLabel("📦 مكتب الإخراج والمخزن (Dispatch Desk - Bon de Sortie):")
        lbl_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        lbl_title.setStyleSheet("color: #0E7471; border: none;")
        h_layout.addWidget(lbl_title)

        self.cbo_orders = QComboBox()
        self.cbo_orders.currentIndexChanged.connect(self._on_order_changed)
        h_layout.addWidget(self.cbo_orders, stretch=1)

        btn_refresh = QPushButton("🔄 تحديث السندات المؤكدة")
        btn_refresh.setStyleSheet("background: #0E7471; color: white; font-weight: bold; padding: 6px 12px; border-radius: 6px;")
        btn_refresh.clicked.connect(self.refresh_dispatch_queue)
        h_layout.addWidget(btn_refresh)

        self.lbl_status = QLabel("ÉTAT: 🟢 جاهز للمسح الفعلي")
        self.lbl_status.setStyleSheet("color: #059669; font-weight: bold; border: none;")
        h_layout.addWidget(self.lbl_status)
        layout.addWidget(header)

        # 2. Expected Items Table Requiring Physical Serial Scan
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "المنتج المطلوب (Mark & Name)",
            "اللون (Coloure)",
            "الباركود المتوقع",
            "الرقم التسلسلي الممسوح (N° de Série)",
            "حالة التحقق",
            "وقت المسح",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        # 3. Real-Time Scan Feedback Monitor
        self.monitor_frame = QFrame()
        self.monitor_frame.setFixedHeight(74)
        self.monitor_frame.setStyleSheet("background: #1E293B; border-radius: 8px; border: 2px solid #475569;")
        m_layout = QVBoxLayout(self.monitor_frame)
        self.lbl_monitor_text = QLabel("بانتظار مسح الباركود والرقم التسلسلي الفريد (N° de Série) للقطعة الفعلية...")
        self.lbl_monitor_text.setAlignment(Qt.AlignCenter)
        self.lbl_monitor_text.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.lbl_monitor_text.setStyleSheet("color: #F8FAFC; border: none;")
        m_layout.addWidget(self.lbl_monitor_text)
        layout.addWidget(self.monitor_frame)

        # 4. Scanner Input Bar
        sim_box = QHBoxLayout()
        self.txt_scan_sim = QLineEdit()
        self.txt_scan_sim.setPlaceholderText("امسح أو أدخل الرقم التسلسلي الفريد للقطعة (N° de Série، مثل SN-BOSCH-001)...")
        self.txt_scan_sim.returnPressed.connect(self._handle_manual_scan)
        sim_box.addWidget(self.txt_scan_sim)

        btn_sim = QPushButton("⚡ تحقق وربط الرقم التسلسلي")
        btn_sim.setStyleSheet("background: #2563EB; color: white; padding: 9px 14px; font-weight: bold; border-radius: 6px;")
        btn_sim.clicked.connect(self._handle_manual_scan)
        sim_box.addWidget(btn_sim)
        layout.addLayout(sim_box)

        # 5. Finalize Bon de Sortie Button
        self.btn_dispatch = QPushButton("🖨️ تأكيد الخروج الفعلي وطباعة Bon de Sortie (سند خروج لوجستي - بدون أثر نقدي)")
        self.btn_dispatch.setEnabled(False)
        self.btn_dispatch.setStyleSheet(
            "background: #059669; color: white; font-size: 13px; font-weight: bold; padding: 12px; border-radius: 8px;"
        )
        self.btn_dispatch.clicked.connect(self._finalize_dispatch)
        layout.addWidget(self.btn_dispatch)

    def refresh_dispatch_queue(self) -> None:
        orders: List[Dict[str, Any]] = []
        if self.data_manager and hasattr(self.data_manager, "bonds"):
            orders = self.data_manager.bonds.get_dispatch_order_queue()

        if not orders and not (self.data_manager and hasattr(self.data_manager, "bonds")):
            orders = [
                {
                    "Order_ID": 42,
                    "Order_Number": "BC-0042",
                    "Invoice_ID": 101,
                    "Invoice_No": "FAC-C-0042",
                    "Client_Name": "Omar Belkacem",
                    "Bond_Type": "BON_C",
                    "Status": "PAID_PENDING_DISPATCH",
                    "lines": [
                        {
                            "Line_ID": 1,
                            "Product_ID": 101,
                            "Brand_Mark": "Bosch",
                            "Product_Name": "KGN39VLEB Combi 368L",
                            "Color_Finish": "Inox",
                            "Barcode": "4242005198030",
                            "Quantity_Ordered": 1,
                            "Quantity_Dispatched": 0,
                        },
                        {
                            "Line_ID": 2,
                            "Product_ID": 102,
                            "Brand_Mark": "LG",
                            "Product_Name": "F4J6TY0W DirectDrive 9kg",
                            "Color_Finish": "Blanc",
                            "Barcode": "8806098321092",
                            "Quantity_Ordered": 1,
                            "Quantity_Dispatched": 0,
                        },
                    ],
                }
            ]

        self._dispatch_orders = orders
        self.cbo_orders.clear()
        for ord_item in orders:
            label = (
                f"{ord_item.get('Order_Number')} | {ord_item.get('Client_Name')} "
                f"[{ord_item.get('Bond_Type')}] ({ord_item.get('Status')})"
            )
            self.cbo_orders.addItem(label, ord_item.get("Order_ID"))

        if not orders:
            self._active_order = None
            self._expected_items = []
            self._refresh_table()

    def _on_order_changed(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._dispatch_orders):
            self._active_order = None
            self._expected_items = []
            self._refresh_table()
            return

        ord_item = self._dispatch_orders[idx]
        self._active_order = ord_item
        self._expected_items = []
        for line in ord_item.get("lines", []):
            qty_rem = max(0, int(line.get("Quantity_Ordered") or 1) - int(line.get("Quantity_Dispatched") or 0))
            for _ in range(qty_rem):
                self._expected_items.append({
                    "order_line_id": int(line.get("Line_ID") or 1),
                    "product_id": int(line.get("Product_ID") or 101),
                    "model": f"{line.get('Brand_Mark', '')} {line.get('Product_Name', '')}".strip(),
                    "color": str(line.get("Color_Finish") or "Standard"),
                    "ean": str(line.get("Barcode") or "--"),
                    "serial": None,
                    "status": "PENDING",
                    "scanned_at": "--",
                })
        self.btn_dispatch.setEnabled(False)
        self._refresh_table()

    def _refresh_table(self) -> None:
        self.table.setRowCount(len(self._expected_items))
        for row, item in enumerate(self._expected_items):
            self.table.setItem(row, 0, QTableWidgetItem(item["model"]))
            self.table.setItem(row, 1, QTableWidgetItem(item["color"]))
            self.table.setItem(row, 2, QTableWidgetItem(item["ean"]))
            self.table.setItem(row, 3, QTableWidgetItem(item["serial"] or "-- بانتظار المسح --"))
            self.table.setItem(row, 4, QTableWidgetItem(item["status"]))
            self.table.setItem(row, 5, QTableWidgetItem(item["scanned_at"]))

    def process_scanned_barcode(self, raw_barcode: str) -> None:
        """Validates a scanned serial number and binds it to the next pending item slot."""
        cleaned = (raw_barcode or "").strip().upper()
        if not cleaned:
            return

        # 1. Check duplicate scan in current session
        for item in self._expected_items:
            if item["serial"] == cleaned:
                self._show_feedback(f"⚠️ تحذير: الرقم التسلسلي {cleaned} تم مسحه مسبقاً في هذا السند!", "#F59E0B")
                return

        # 2. If connected to DB, verify serial existence & status
        db_serial = None
        if self.data_manager and hasattr(self.data_manager, "serials"):
            db_serial = self.data_manager.serials.get_serial_details(cleaned)
            if db_serial:
                if db_serial.get("Status") != "IN_STOCK":
                    self._show_feedback(
                        f"🚫 مرفوض: الرقم التسلسلي {cleaned} ليس في المخزون (الحالة: {db_serial.get('Status')})",
                        "#EF4444",
                    )
                    return

        # 3. Bind to matching pending line
        for item in self._expected_items:
            if item["status"] == "PENDING":
                if db_serial and int(db_serial.get("Product_ID") or 0) != int(item["product_id"]):
                    continue
                item["serial"] = cleaned
                item["status"] = "VALIDÉ 🟢"
                item["scanned_at"] = datetime.now().strftime("%H:%M:%S")
                self._show_feedback(f"✅ تطابق صحيح: تم ربط الرقم التسلسلي {cleaned} بـ {item['model']}", "#10B981")
                self._refresh_table()
                self._check_completion()
                return

        self._show_feedback(f"❌ خطأ: الرقم التسلسلي {cleaned} لا يطابق أي منتج متبقٍ في السند!", "#EF4444")

    def _handle_manual_scan(self) -> None:
        text = self.txt_scan_sim.text()
        if text:
            self.process_scanned_barcode(text)
            self.txt_scan_sim.clear()

    def _show_feedback(self, message: str, color_hex: str) -> None:
        self.monitor_frame.setStyleSheet(f"background: {color_hex}; border-radius: 8px;")
        self.lbl_monitor_text.setText(message)

    def _check_completion(self) -> None:
        all_done = bool(self._expected_items) and all(
            item["status"] == "VALIDÉ 🟢" for item in self._expected_items
        )
        if all_done:
            self.btn_dispatch.setEnabled(True)
            self._show_feedback("🎉 تم التحقق من جميع الأرقام التسلسلية - جاهز لإصدار Bon de Sortie", "#059669")

    def _finalize_dispatch(self) -> None:
        if not self._expected_items:
            return
        try:
            payload = [
                {"order_line_id": item["order_line_id"], "serial_number": item["serial"]}
                for item in self._expected_items
                if item.get("serial")
            ]
            bond_no = "BS-SIM-001"
            if self.data_manager and hasattr(self.data_manager, "bonds") and self._active_order:
                uid = int((getattr(self.data_manager, "current_user", None) or {}).get("User_ID") or 1)
                res = self.data_manager.bonds.validate_and_dispatch_serials(
                    order_id=int(self._active_order.get("Order_ID") or 1),
                    invoice_id=int(self._active_order.get("Invoice_ID") or 1),
                    storekeeper_user_id=uid,
                    scanned_serial_numbers=payload,
                )
                bond_no = res.get("exit_bond_number", bond_no)

            serials_list = [item["serial"] for item in self._expected_items]
            self.stockDispatched.emit(bond_no, serials_list)
            QMessageBox.information(
                self,
                "تم إصدار Bon de Sortie",
                f"تم إصدار سند الخروج ({bond_no}) وتحديث المخزون الفعلي وحالة الأرقام التسلسلية إلى DISPATCHED.\n"
                "(سند لوجستي بدون أي تعامل نقدي).",
            )
            self.refresh_dispatch_queue()
        except Exception as err:
            QMessageBox.critical(self, "خطأ في إصدار Bon de Sortie", str(err))
