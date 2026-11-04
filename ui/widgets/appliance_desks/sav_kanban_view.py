# ui/widgets/appliance_desks/sav_kanban_view.py
"""
SAV / Réparation 4-Stage Kanban & Workflow UI (نظام مصلحة ما بعد البيع والإصلاح).
Tracks every repair ticket across 4 strict stages:
1. استقبال المنتج من الزبون (SAV_RECEIVED - Bon de Réparation)
2. إرسال المنتج للمصلح (SAV_SENT_TO_TECH)
3. العودة من المصلح (SAV_RETURNED_FROM_TECH - التحقق من حالة الإصلاح)
4. تسليم المنتج للزبون (SAV_CLOSED_DELIVERED - خروج السلعة وإغلاق التذكرة)
And implements the Irreparable Defect Mechanism (آلية عدم إمكانية الإصلاح):
- Issues an automated Versement Virtuel into the customer's wallet without affecting Caisse cash liquidity.
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from ui.icons import get_duotone_icon

INPUT_STYLE = """
    QLineEdit, QComboBox, QDoubleSpinBox {
        background-color: #FFFFFF;
        border: 1px solid #CBD5E1;
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 9.5pt;
        color: #0F172A;
        min-height: 20px;
    }
    QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {
        border: 1.5px solid #0E7471;
    }
"""


class IrreparableDefectModal(QDialog):
    """
    Irreparable appliance compensation dialog (آلية عدم إمكانية الإصلاح).
    Credits the customer's virtual wallet (Versement Virtuel) with zero physical cash drawer impact.
    """

    def __init__(
        self,
        ticket_id: str,
        client_name: str,
        appliance_model: str,
        purchase_price: float,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("آلية عدم إمكانية الإصلاح - تعويض Versement Virtuel")
        self.setFixedSize(520, 420)
        self.setStyleSheet(
            "QDialog { background-color: #FFFFFF; color: #0F172A; }"
            "QLabel { border: none; background: transparent; color: #1E293B; }"
            + INPUT_STYLE
        )
        self.compensation_confirmed = False
        self.compensation_amount = purchase_price
        self._base_price = purchase_price
        self._init_ui(ticket_id, client_name, appliance_model, purchase_price)

    def _init_ui(self, ticket_id: str, client_name: str, model: str, price: float) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        lbl_header = QLabel("تعذر إصلاح العطل - تعويض برصيد افتراضي (Versement Virtuel)")
        lbl_header.setFont(QFont("Segoe UI", 11, QFont.Bold))
        lbl_header.setStyleSheet("color: #DC2626;")
        layout.addWidget(lbl_header)

        details_frame = QFrame()
        details_frame.setObjectName("DetailsCard")
        details_frame.setStyleSheet(
            "QFrame#DetailsCard { background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; }"
        )
        d_layout = QVBoxLayout(details_frame)
        d_layout.setContentsMargins(12, 10, 12, 10)
        details = QLabel(
            f"تذكرة الصيانة: <b>{ticket_id}</b> | الزبون: <b>{client_name}</b><br>"
            f"المنتج: <b>{model}</b><br>"
            f"سعر الشراء الأصلي: <b>{price:,.2f} DA</b>"
        )
        d_layout.addWidget(details)
        layout.addWidget(details_frame)

        layout.addWidget(QLabel("سياسة احتساب التعويض:"))
        self.cbo_policy = QComboBox()
        self.cbo_policy.addItems([
            "تعويض كامل 100% (تحت الضمان)",
            "تعويض 80% (خصم استهلاك 20%)",
            "تعويض تجاري 50%",
        ])
        self.cbo_policy.currentIndexChanged.connect(self._update_policy_amount)
        layout.addWidget(self.cbo_policy)

        notice_box = QFrame()
        notice_box.setObjectName("LiquidityNotice")
        notice_box.setStyleSheet(
            "QFrame#LiquidityNotice { background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 6px; }"
        )
        n_layout = QVBoxLayout(notice_box)
        n_layout.setContentsMargins(12, 10, 12, 10)
        n_title = QLabel("<b>حماية سيولة الصندوق (Caisse Liquidity Guardrail):</b>")
        n_title.setStyleSheet("color: #166534;")
        n_layout.addWidget(n_title)
        n_desc = QLabel(
            "يتم إصدار <b>Versement Virtuel</b> يُضاف لمحفظة الزبون لشراء بديل دون سحب أي نقد من الـ Caisse (0.00 DA)."
        )
        n_desc.setWordWrap(True)
        n_desc.setStyleSheet("color: #15803D;")
        n_layout.addWidget(n_desc)
        layout.addWidget(notice_box)

        self.lbl_credit_amt = QLabel(f"المبلغ المضاف لمحفظة الزبون: {price:,.2f} DA")
        self.lbl_credit_amt.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.lbl_credit_amt.setStyleSheet("color: #0E7471; margin: 4px 0;")
        layout.addWidget(self.lbl_credit_amt)

        btn_box = QHBoxLayout()
        btn_cancel = QPushButton("إلغاء")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet(
            "QPushButton { background: #F1F5F9; color: #334155; font-weight: bold; padding: 8px 16px; border: 1px solid #CBD5E1; border-radius: 6px; }"
        )
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_confirm = QPushButton("إصدار Versement Virtuel وإغلاق التذكرة (SCRAPPED)")
        btn_confirm.setIcon(get_duotone_icon("credit_card", "#FFFFFF", "#CCFBF1", size=16))
        btn_confirm.setCursor(Qt.PointingHandCursor)
        btn_confirm.setStyleSheet(
            "QPushButton { background: #0E7471; color: white; font-weight: bold; padding: 8px 16px; border: none; border-radius: 6px; }"
            "QPushButton:hover { background: #0A5E5C; }"
        )
        btn_confirm.clicked.connect(self._confirm_credit)
        btn_box.addWidget(btn_confirm)

        layout.addLayout(btn_box)

    def _update_policy_amount(self, idx: int) -> None:
        factors = [1.0, 0.8, 0.5]
        factor = factors[idx] if 0 <= idx < len(factors) else 1.0
        self.compensation_amount = round(self._base_price * factor, 2)
        self.lbl_credit_amt.setText(f"المبلغ المضاف لمحفظة الزبون: {self.compensation_amount:,.2f} DA")

    def _confirm_credit(self) -> None:
        self.compensation_confirmed = True
        self.accept()


class SAVReceptionDialog(QDialog):
    """Stage 1 Intake Dialog: Receives defective product from customer and emits Bon de Réparation."""

    def __init__(self, data_manager=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("المرحلة 1: استقبال منتج للصيانة وإصدار Bon de Réparation")
        self.setFixedSize(480, 340)
        self.setStyleSheet(
            "QDialog { background-color: #FFFFFF; color: #0F172A; }"
            "QLabel { border: none; background: transparent; color: #334155; font-weight: 600; }"
            + INPUT_STYLE
        )
        self.data_manager = data_manager
        self.created_ticket: Optional[Dict[str, Any]] = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        form = QGridLayout()
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(10)

        form.addWidget(QLabel("الرقم التسلسلي للقطعة (N° de Série):"), 0, 0)
        self.txt_serial = QLineEdit()
        self.txt_serial.setPlaceholderText("امسح الرقم التسلسلي...")
        form.addWidget(self.txt_serial, 0, 1)

        form.addWidget(QLabel("وصف العطل المصرح به:"), 1, 0)
        self.txt_symptom = QLineEdit("توقف التبريد / عطل في اللوحة الإلكترونية")
        form.addWidget(self.txt_symptom, 1, 1)

        form.addWidget(QLabel("الحالة الظاهرية للسلعة:"), 2, 0)
        self.txt_cosmetic = QLineEdit("حالة جيدة بدون خدوش خارجية")
        form.addWidget(self.txt_cosmetic, 2, 1)

        form.addWidget(QLabel("الملحقات المرفقة:"), 3, 0)
        self.txt_acc = QLineEdit("كابل الطاقة + دليل الضمان")
        form.addWidget(self.txt_acc, 3, 1)

        layout.addLayout(form)
        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("إلغاء")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet(
            "QPushButton { background: #F1F5F9; color: #334155; font-weight: bold; padding: 8px 16px; border: 1px solid #CBD5E1; border-radius: 6px; }"
        )
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_ok = QPushButton("إصدار Bon de Réparation واستلام القطعة")
        btn_ok.setIcon(get_duotone_icon("wrench_sav", "#FFFFFF", "#CCFBF1", size=16))
        btn_ok.setCursor(Qt.PointingHandCursor)
        btn_ok.setStyleSheet(
            "QPushButton { background: #0E7471; color: white; font-weight: bold; padding: 8px 16px; border: none; border-radius: 6px; }"
            "QPushButton:hover { background: #0A5E5C; }"
        )
        btn_ok.clicked.connect(self._submit)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    def _submit(self) -> None:
        sn = self.txt_serial.text().strip()
        if not sn:
            QMessageBox.warning(self, "تنبيه", "يرجى إدخال الرقم التسلسلي للقطعة.")
            return
        try:
            if self.data_manager and hasattr(self.data_manager, "sav"):
                uid = int((getattr(self.data_manager, "current_user", None) or {}).get("User_ID") or 1)
                self.created_ticket = self.data_manager.sav.check_in_reception(
                    serial_number=sn,
                    symptom=self.txt_symptom.text().strip(),
                    cosmetic_condition=self.txt_cosmetic.text().strip(),
                    accessories=self.txt_acc.text().strip(),
                    received_by_user_id=uid,
                )
            else:
                self.created_ticket = {
                    "ticket_id": 899,
                    "ticket_number": "SAV-2026-0899",
                    "bon_reparation_barcode": "BREP-2026-0899",
                    "serial_number": sn,
                    "symptom": self.txt_symptom.text().strip(),
                }
            self.accept()
        except Exception as err:
            QMessageBox.critical(self, "خطأ في تسجيل Bon de Réparation", str(err))


class SAVKanbanWidget(QWidget):
    """Four-Stage Kanban Pipeline View for After-Sales Appliance Repairs (SAV / Réparation)."""

    def __init__(self, data_manager=None, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self._columns: Dict[str, QWidget] = {}
        self.setStyleSheet(
            """
            QFrame#SAVTopBar, QFrame#KanbanCol {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
            }
            QFrame#SAVTicketCard {
                background-color: #F8FAFC;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
                color: #1E293B;
            }
            """
        )
        self._init_ui()
        self.refresh_tickets()

    def _init_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        # Top Action Bar
        top_bar = QFrame()
        top_bar.setObjectName("SAVTopBar")
        tb_layout = QHBoxLayout(top_bar)
        tb_layout.setContentsMargins(14, 10, 14, 10)
        tb_layout.setSpacing(10)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_duotone_icon("wrench_sav", "#0E7471", "#99F6E4", size=20).pixmap(QSize(20, 20)))
        tb_layout.addWidget(icon_lbl)

        lbl_title = QLabel("نظام مصلحة ما بعد البيع والإصلاح (SAV / Réparation - 4 مراحل تتبع)")
        lbl_title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        lbl_title.setStyleSheet("color: #0F172A;")
        tb_layout.addWidget(lbl_title)
        tb_layout.addStretch()

        btn_new_sav = QPushButton("+ استقبال منتج وإصدار Bon de Réparation")
        btn_new_sav.setCursor(Qt.PointingHandCursor)
        btn_new_sav.setStyleSheet(
            "QPushButton { background: #0E7471; color: white; font-weight: bold; padding: 7px 14px; border: none; border-radius: 6px; }"
            "QPushButton:hover { background: #0A5E5C; }"
        )
        btn_new_sav.clicked.connect(self._open_reception_dialog)
        tb_layout.addWidget(btn_new_sav)

        btn_refresh = QPushButton("تحديث اللوحة")
        btn_refresh.setIcon(get_duotone_icon("refresh", "#0E7471", "#99F6E4", size=14))
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setStyleSheet(
            "QPushButton { background: #F8FAFC; color: #334155; font-weight: 600; padding: 7px 12px; border: 1px solid #CBD5E1; border-radius: 6px; }"
            "QPushButton:hover { background: #F1F5F9; border-color: #0E7471; color: #0E7471; }"
        )
        btn_refresh.clicked.connect(self.refresh_tickets)
        tb_layout.addWidget(btn_refresh)
        root_layout.addWidget(top_bar)

        # 4-Column Kanban Board
        board_layout = QHBoxLayout()
        board_layout.setSpacing(10)

        col1 = self._create_kanban_column("1. استقبال المنتج (Bon de Réparation)", "#0E7471")
        col2 = self._create_kanban_column("2. إرسال للمصلح (Envoi Technicien)", "#475569")
        col3 = self._create_kanban_column("3. العودة من المصلح (Retour & Diagnostic)", "#0E7471")
        col4 = self._create_kanban_column("4. تسليم للزبون / تعويض (Clôture)", "#15803D")

        self._columns = {
            "SAV_RECEIVED": col1,
            "SAV_SENT_TO_TECH": col2,
            "SAV_RETURNED_FROM_TECH": col3,
            "SAV_CLOSED_DELIVERED": col4,
        }

        board_layout.addWidget(col1)
        board_layout.addWidget(col2)
        board_layout.addWidget(col3)
        board_layout.addWidget(col4)
        root_layout.addLayout(board_layout, stretch=1)

    def _create_kanban_column(self, title: str, accent_color: str) -> QWidget:
        col = QFrame()
        col.setObjectName("KanbanCol")
        c_layout = QVBoxLayout(col)
        c_layout.setContentsMargins(10, 10, 10, 10)
        c_layout.setSpacing(8)

        header = QLabel(title)
        header.setFont(QFont("Segoe UI", 9, QFont.Bold))
        header.setStyleSheet(
            f"color: {accent_color}; padding-bottom: 6px; border-bottom: 2px solid {accent_color};"
        )
        c_layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        cards_layout = QVBoxLayout(scroll_content)
        cards_layout.setContentsMargins(0, 4, 0, 4)
        cards_layout.setSpacing(8)
        cards_layout.addStretch()
        scroll.setWidget(scroll_content)
        c_layout.addWidget(scroll)
        return col

    def _clear_column_cards(self, col: QWidget) -> None:
        scroll = col.findChild(QScrollArea)
        if not scroll:
            return
        layout = scroll.widget().layout()
        while layout.count() > 1:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def refresh_tickets(self) -> None:
        for col in self._columns.values():
            self._clear_column_cards(col)

        tickets: List[Dict[str, Any]] = []
        if self.data_manager and hasattr(self.data_manager, "sav"):
            tickets = self.data_manager.sav.get_all_sav_tickets()

        if not tickets and not (self.data_manager and hasattr(self.data_manager, "sav")):
            tickets = [
                {
                    "SAV_Ticket_ID": 814,
                    "Ticket_Number": "SAV-0814",
                    "Client_Name": "Omar Belkacem",
                    "Product_Name": "LG F4J6TY0W (Lave-linge)",
                    "Serial_Number": "SN-LG-884102",
                    "Customer_Stated_Symptom": "Cuve fissurée",
                    "Current_Stage": "SAV_RECEIVED",
                    "Resolution_Status": "PENDING_EVALUATION",
                },
                {
                    "SAV_Ticket_ID": 811,
                    "Ticket_Number": "SAV-0811",
                    "Client_Name": "Khaled D.",
                    "Product_Name": "Samsung RT46 (Frigo)",
                    "Serial_Number": "SN-SAM-11902",
                    "Customer_Stated_Symptom": "Fuite Gaz R600a",
                    "Current_Stage": "SAV_SENT_TO_TECH",
                    "Resolution_Status": "PENDING_EVALUATION",
                },
                {
                    "SAV_Ticket_ID": 809,
                    "Ticket_Number": "SAV-0809",
                    "Client_Name": "Yacine B.",
                    "Product_Name": "Brandt BXP6555X (Four)",
                    "Serial_Number": "SN-BRD-4410",
                    "Customer_Stated_Symptom": "Carte PCB Remplacée",
                    "Current_Stage": "SAV_RETURNED_FROM_TECH",
                    "Resolution_Status": "REPAIRED",
                },
                {
                    "SAV_Ticket_ID": 802,
                    "Ticket_Number": "SAV-0802",
                    "Client_Name": "Salim T.",
                    "Product_Name": "Midea 12k Split",
                    "Serial_Number": "SN-MID-7721",
                    "Customer_Stated_Symptom": "Test Banc Conforme",
                    "Current_Stage": "SAV_CLOSED_DELIVERED",
                    "Resolution_Status": "REPAIRED",
                },
            ]

        for t in tickets:
            stage = str(t.get("Current_Stage") or "SAV_RECEIVED")
            col = self._columns.get(stage, self._columns["SAV_RECEIVED"])
            self._add_ticket_card(col, t)

    def _add_ticket_card(self, column: QWidget, t: Dict[str, Any]) -> None:
        scroll = column.findChild(QScrollArea)
        container = scroll.widget()
        layout = container.layout()

        card = QFrame()
        card.setObjectName("SAVTicketCard")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(10, 10, 10, 10)
        c_layout.setSpacing(6)

        ticket_no = str(t.get("Ticket_Number") or "")
        client = str(t.get("Client_Name") or "")
        model = str(t.get("Product_Name") or "")
        serial_no = str(t.get("Serial_Number") or "")
        symptom = str(t.get("Customer_Stated_Symptom") or "")
        stage = str(t.get("Current_Stage") or "SAV_RECEIVED")
        tid = int(t.get("SAV_Ticket_ID") or 0)

        t_lbl = QLabel(f"<b>{ticket_no}</b> — {client}")
        t_lbl.setStyleSheet("color: #0E7471; font-size: 9.5pt;")
        c_layout.addWidget(t_lbl)

        prod_lbl = QLabel(f"المنتج: <b>{model}</b> ({serial_no})")
        prod_lbl.setWordWrap(True)
        prod_lbl.setStyleSheet("color: #334155; font-size: 9pt;")
        c_layout.addWidget(prod_lbl)

        sym_lbl = QLabel(f"العطل: {symptom}")
        sym_lbl.setWordWrap(True)
        sym_lbl.setStyleSheet("color: #64748B; font-size: 8.5pt;")
        c_layout.addWidget(sym_lbl)

        if stage == "SAV_RECEIVED":
            btn_send = QPushButton("2. إرسال للمصلح")
            btn_send.setCursor(Qt.PointingHandCursor)
            btn_send.setStyleSheet(
                "QPushButton { background: #FFFFFF; color: #334155; font-weight: 600; padding: 6px; border: 1px solid #CBD5E1; border-radius: 5px; }"
                "QPushButton:hover { background: #F1F5F9; border-color: #0E7471; color: #0E7471; }"
            )
            btn_send.clicked.connect(lambda checked=False, x=tid: self._advance_to_tech(x))
            c_layout.addWidget(btn_send)
        elif stage == "SAV_SENT_TO_TECH":
            btn_ret = QPushButton("3. تسجيل العودة من المصلح")
            btn_ret.setCursor(Qt.PointingHandCursor)
            btn_ret.setStyleSheet(
                "QPushButton { background: #FFFFFF; color: #0E7471; font-weight: 600; padding: 6px; border: 1px solid #0E7471; border-radius: 5px; }"
                "QPushButton:hover { background: #F0FDFA; }"
            )
            btn_ret.clicked.connect(lambda checked=False, x=tid: self._advance_from_tech(x))
            c_layout.addWidget(btn_ret)
        elif stage == "SAV_RETURNED_FROM_TECH":
            btn_deliver = QPushButton("4. تسليم المنتج للزبون وإغلاق التذكرة")
            btn_deliver.setCursor(Qt.PointingHandCursor)
            btn_deliver.setStyleSheet(
                "QPushButton { background: #0E7471; color: white; font-weight: bold; padding: 6px; border: none; border-radius: 5px; }"
                "QPushButton:hover { background: #0A5E5C; }"
            )
            btn_deliver.clicked.connect(lambda checked=False, x=tid: self._deliver_to_client(x))
            c_layout.addWidget(btn_deliver)

            btn_irrep = QPushButton("تعذر الإصلاح -> Versement Virtuel")
            btn_irrep.setCursor(Qt.PointingHandCursor)
            btn_irrep.setStyleSheet(
                "QPushButton { background: #FEF2F2; color: #DC2626; font-weight: 600; padding: 6px; border: 1px solid #FECACA; border-radius: 5px; }"
                "QPushButton:hover { background: #FEE2E2; }"
            )
            btn_irrep.clicked.connect(
                lambda checked=False, x=tid, tk=ticket_no, cl=client, md=model: self._trigger_irreparable_modal(x, tk, cl, md)
            )
            c_layout.addWidget(btn_irrep)

        layout.insertWidget(layout.count() - 1, card)

    def _open_reception_dialog(self) -> None:
        dlg = SAVReceptionDialog(self.data_manager, self)
        if dlg.exec() == QDialog.Accepted and dlg.created_ticket:
            bon = dlg.created_ticket.get("bon_reparation_barcode", "")
            QMessageBox.information(
                self,
                "Bon de Réparation",
                f"تم استلام المنتج من الزبون وإصدار وصل الاستلام ({bon}).",
            )
            self.refresh_tickets()

    def _advance_to_tech(self, ticket_id: int) -> None:
        try:
            if self.data_manager and hasattr(self.data_manager, "sav") and ticket_id:
                uid = int((getattr(self.data_manager, "current_user", None) or {}).get("User_ID") or 1)
                self.data_manager.sav.dispatch_to_technician(ticket_id, None, uid)
            self.refresh_tickets()
        except Exception as err:
            QMessageBox.critical(self, "خطأ", str(err))

    def _advance_from_tech(self, ticket_id: int) -> None:
        diag, ok = QInputDialog.getText(
            self,
            "العودة من المصلح",
            "أدخل تقرير الفحص وحالة الإصلاح:",
            text="تم استبدال القطعة وفحص الجهاز بنجاح",
        )
        if not ok:
            return
        try:
            if self.data_manager and hasattr(self.data_manager, "sav") and ticket_id:
                uid = int((getattr(self.data_manager, "current_user", None) or {}).get("User_ID") or 1)
                self.data_manager.sav.record_technician_return(ticket_id, "REPAIRED", diag, uid)
            self.refresh_tickets()
        except Exception as err:
            QMessageBox.critical(self, "خطأ", str(err))

    def _deliver_to_client(self, ticket_id: int) -> None:
        try:
            if self.data_manager and hasattr(self.data_manager, "sav") and ticket_id:
                uid = int((getattr(self.data_manager, "current_user", None) or {}).get("User_ID") or 1)
                self.data_manager.sav.deliver_repaired_to_client(ticket_id, uid)
            QMessageBox.information(self, "تسليم المنتج", "تم تسليم المنتج للزبون وإغلاق تذكرة الصيانة.")
            self.refresh_tickets()
        except Exception as err:
            QMessageBox.critical(self, "خطأ", str(err))

    def _trigger_irreparable_modal(self, ticket_id: int, ticket_no: str, client: str, model: str) -> None:
        modal = IrreparableDefectModal(ticket_no, client, model, 88000.0, self)
        if modal.exec() == QDialog.Accepted and modal.compensation_confirmed:
            try:
                if self.data_manager and hasattr(self.data_manager, "sav") and ticket_id:
                    uid = int((getattr(self.data_manager, "current_user", None) or {}).get("User_ID") or 1)
                    self.data_manager.sav.process_irreparable_compensation(
                        sav_ticket_id=ticket_id,
                        admin_user_id=uid,
                        compensation_amount=Decimal(str(modal.compensation_amount)),
                        notes="تعويض آلي بسبب عدم إمكانية الإصلاح",
                    )
                QMessageBox.information(
                    self,
                    "تم تعويض الزبون (Versement Virtuel)",
                    f"تم إضافة {modal.compensation_amount:,.2f} DA كرصيد افتراضي (Versement Virtuel) لحساب {client}.\n"
                    "تم تحويل حالة الرقم التسلسلي إلى SCRAPPED وإغلاق التذكرة دون التأثير على سيولة الـ Caisse.",
                )
                self.refresh_tickets()
            except Exception as err:
                QMessageBox.critical(self, "خطأ في التعويض", str(err))
