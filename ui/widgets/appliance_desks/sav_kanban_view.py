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
        self.setWindowTitle("Appareil Irréparable — Compensation Versement Virtuel")
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

        lbl_header = QLabel("Constat d'Irréparabilité — Avoir Portefeuille (Versement Virtuel)")
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
            f"Ticket SAV : <b>{ticket_id}</b>  |  Client : <b>{client_name}</b><br>"
            f"Appareil : <b>{model}</b><br>"
            f"Prix d'achat initial : <b>{price:,.2f} DA</b>"
        )
        d_layout.addWidget(details)
        layout.addWidget(details_frame)

        layout.addWidget(QLabel("Barème de compensation applicable :"))
        self.cbo_policy = QComboBox()
        self.cbo_policy.addItems([
            "Compensation intégrale 100% (Sous Garantie)",
            "Compensation 80% (Décote vétusté 20%)",
            "Geste commercial 50%",
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
        n_title = QLabel("<b>Protection de Trésorerie Caisse (Liquidity Guardrail) :</b>")
        n_title.setStyleSheet("color: #166534;")
        n_layout.addWidget(n_title)
        n_desc = QLabel(
            "Émission d'un <b>Versement Virtuel</b> crédité sur le portefeuille client pour l'achat d'un produit de remplacement, "
            "sans aucun décaissement espèces en Caisse (0.00 DA)."
        )
        n_desc.setWordWrap(True)
        n_desc.setStyleSheet("color: #15803D;")
        n_layout.addWidget(n_desc)
        layout.addWidget(notice_box)

        self.lbl_credit_amt = QLabel(f"Montant crédité au portefeuille client : {price:,.2f} DA")
        self.lbl_credit_amt.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.lbl_credit_amt.setStyleSheet("color: #0E7471; margin: 4px 0;")
        layout.addWidget(self.lbl_credit_amt)

        btn_box = QHBoxLayout()
        btn_cancel = QPushButton("Annuler")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet(
            "QPushButton { background: #F1F5F9; color: #334155; font-weight: bold; min-height: 0px; padding: 8px 16px; border: 1px solid #CBD5E1; border-radius: 6px; }"
        )
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_confirm = QPushButton("Émettre Versement Virtuel && Réformer (SCRAPPED)")
        btn_confirm.setIcon(get_duotone_icon("payment_white", 16))
        btn_confirm.setCursor(Qt.PointingHandCursor)
        btn_confirm.setStyleSheet(
            "QPushButton { background: #0E7471; color: white; font-weight: bold; min-height: 0px; padding: 8px 16px; border: none; border-radius: 6px; }"
            "QPushButton:hover { background: #0A5E5C; }"
        )
        btn_confirm.clicked.connect(self._confirm_credit)
        btn_box.addWidget(btn_confirm)

        layout.addLayout(btn_box)

    def _update_policy_amount(self, idx: int) -> None:
        factors = [1.0, 0.8, 0.5]
        factor = factors[idx] if 0 <= idx < len(factors) else 1.0
        self.compensation_amount = round(self._base_price * factor, 2)
        self.lbl_credit_amt.setText(f"Montant crédité au portefeuille client : {self.compensation_amount:,.2f} DA")

    def _confirm_credit(self) -> None:
        self.compensation_confirmed = True
        self.accept()


class SAVReceptionDialog(QDialog):
    """Stage 1 Intake Dialog: Receives defective product from customer and emits Bon de Réparation."""

    def __init__(self, data_manager=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Étape 1 : Réception SAV & Émission Bon de Réparation")
        self.setFixedSize(500, 340)
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

        form.addWidget(QLabel("N° de Série de l'appareil :"), 0, 0)
        self.txt_serial = QLineEdit()
        self.txt_serial.setPlaceholderText("Scanner ou saisir le N° de Série...")
        form.addWidget(self.txt_serial, 0, 1)

        form.addWidget(QLabel("Panne / Symptôme déclaré :"), 1, 0)
        self.txt_symptom = QLineEdit("Arrêt refroidissement / Défaut carte électronique")
        form.addWidget(self.txt_symptom, 1, 1)

        form.addWidget(QLabel("État cosmétique à réception :"), 2, 0)
        self.txt_cosmetic = QLineEdit("Bon état général, aucune rayure externe")
        form.addWidget(self.txt_cosmetic, 2, 1)

        form.addWidget(QLabel("Accessoires déposés :"), 3, 0)
        self.txt_acc = QLineEdit("Câble d'alimentation + Certificat de garantie")
        form.addWidget(self.txt_acc, 3, 1)

        layout.addLayout(form)
        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Annuler")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet(
            "QPushButton { background: #F1F5F9; color: #334155; font-weight: bold; min-height: 0px; padding: 8px 16px; border: 1px solid #CBD5E1; border-radius: 6px; }"
        )
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_ok = QPushButton("Émettre Bon de Réparation && Réceptionner")
        btn_ok.setIcon(get_duotone_icon("wrench_sav", 16))
        btn_ok.setCursor(Qt.PointingHandCursor)
        btn_ok.setStyleSheet(
            "QPushButton { background: #0E7471; color: white; font-weight: bold; min-height: 0px; padding: 8px 16px; border: none; border-radius: 6px; }"
            "QPushButton:hover { background: #0A5E5C; }"
        )
        btn_ok.clicked.connect(self._submit)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    def _submit(self) -> None:
        sn = self.txt_serial.text().strip()
        if not sn:
            QMessageBox.warning(self, "Champ requis", "Veuillez saisir le N° de Série de l'appareil.")
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
            QMessageBox.critical(self, "Erreur Bon de Réparation", str(err))


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
                border: 1px solid #DDE3EA;
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
        top_bar.setFixedHeight(52)
        tb_layout = QHBoxLayout(top_bar)
        tb_layout.setContentsMargins(14, 0, 14, 0)
        tb_layout.setSpacing(10)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_duotone_icon("wrench_sav", 20).pixmap(QSize(20, 20)))
        tb_layout.addWidget(icon_lbl)

        lbl_title = QLabel("Service Après-Vente & Réparation (SAV — Suivi 4 Étapes & Garantie)")
        lbl_title.setStyleSheet("font-size: 13px; font-weight: 800; color: #0F172A;")
        tb_layout.addWidget(lbl_title)
        tb_layout.addStretch()

        btn_new_sav = QPushButton("+ Réceptionner Appareil (Bon de Réparation)")
        btn_new_sav.setCursor(Qt.PointingHandCursor)
        btn_new_sav.setFixedHeight(34)
        btn_new_sav.setStyleSheet(
            "QPushButton { background: #0E7471; color: white; font-weight: 700; font-size: 12px; min-height: 0px; padding: 4px 14px; border: none; border-radius: 6px; }"
            "QPushButton:hover { background: #0A5E5C; }"
        )
        btn_new_sav.clicked.connect(self._open_reception_dialog)
        tb_layout.addWidget(btn_new_sav)

        btn_refresh = QPushButton("Actualiser")
        btn_refresh.setIcon(get_duotone_icon("refresh", 14))
        btn_refresh.setIconSize(QSize(14, 14))
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setFixedHeight(34)
        btn_refresh.setStyleSheet(
            "QPushButton { background: #FFFFFF; color: #0E7471; font-weight: 700; font-size: 12px; min-height: 0px; padding: 4px 12px; border: 1.5px solid #0E7471; border-radius: 6px; }"
            "QPushButton:hover { background: #E6F4F1; }"
        )
        btn_refresh.clicked.connect(self.refresh_tickets)
        tb_layout.addWidget(btn_refresh)
        root_layout.addWidget(top_bar)

        # 4-Column Kanban Board
        board_layout = QHBoxLayout()
        board_layout.setSpacing(10)

        col1 = self._create_kanban_column("1. Réception Client (Bon de Réparation)", "#0E7471")
        col2 = self._create_kanban_column("2. Envoi Technicien / Atelier", "#D97706")
        col3 = self._create_kanban_column("3. Retour & Diagnostic", "#0284C7")
        col4 = self._create_kanban_column("4. Remise Client / Clôture", "#16A34A")

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
        col.setProperty("accentColor", accent_color)
        c_layout = QVBoxLayout(col)
        c_layout.setContentsMargins(12, 12, 12, 12)
        c_layout.setSpacing(10)

        header = QLabel(title)
        header.setStyleSheet(
            f"font-size: 12px; font-weight: 800; color: {accent_color}; "
            f"padding-bottom: 8px; border-bottom: 2px solid {accent_color};"
        )
        c_layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        cards_layout = QVBoxLayout(scroll_content)
        cards_layout.setContentsMargins(0, 2, 0, 2)
        cards_layout.setSpacing(10)
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
            try:
                tickets = self.data_manager.sav.get_all_sav_tickets() or []
            except Exception as err:
                logger.error(f"Error fetching SAV tickets: {err}")
                tickets = []

        for t in tickets:
            stage = str(t.get("Current_Stage") or "SAV_RECEIVED")
            col = self._columns.get(stage, self._columns["SAV_RECEIVED"])
            self._add_ticket_card(col, t)

    def _add_ticket_card(self, column: QWidget, t: Dict[str, Any]) -> None:
        scroll = column.findChild(QScrollArea)
        container = scroll.widget()
        layout = container.layout()
        accent = column.property("accentColor") or "#0E7471"

        card = QFrame()
        card.setObjectName("SAVTicketCard")
        card.setStyleSheet(
            f"""
            QFrame#SAVTicketCard {{
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-left: 3px solid {accent};
                border-radius: 6px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
            """
        )
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(12, 10, 12, 10)
        c_layout.setSpacing(6)

        ticket_no = str(t.get("Ticket_Number") or "")
        client = str(t.get("Client_Name") or "")
        model = str(t.get("Product_Name") or "")
        serial_no = str(t.get("Serial_Number") or "")
        symptom = str(t.get("Customer_Stated_Symptom") or "")
        stage = str(t.get("Current_Stage") or "SAV_RECEIVED")
        tid = int(t.get("SAV_Ticket_ID") or 0)

        top_row = QHBoxLayout()
        t_lbl = QLabel(f"<b>{ticket_no}</b> — {client}")
        t_lbl.setStyleSheet("color: #0F172A; font-size: 12px;")
        top_row.addWidget(t_lbl)
        top_row.addStretch()

        sn_badge = QLabel(serial_no)
        sn_badge.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 10px; font-weight: 700; "
            "color: #0E7471; background-color: #E6F4F1; border-radius: 3px; padding: 2px 6px;"
        )
        top_row.addWidget(sn_badge)
        c_layout.addLayout(top_row)

        prod_lbl = QLabel(f"Appareil : <b>{model}</b>")
        prod_lbl.setWordWrap(True)
        prod_lbl.setStyleSheet("color: #334155; font-size: 11.5px;")
        c_layout.addWidget(prod_lbl)

        sym_lbl = QLabel(f"Diagnostic / Panne : {symptom}")
        sym_lbl.setWordWrap(True)
        sym_lbl.setStyleSheet("color: #64748B; font-size: 11px;")
        c_layout.addWidget(sym_lbl)

        if stage == "SAV_RECEIVED":
            btn_send = QPushButton("Transférer vers Technicien (Étape 2)")
            btn_send.setCursor(Qt.PointingHandCursor)
            btn_send.setFixedHeight(30)
            btn_send.setStyleSheet(
                "QPushButton { background: #FFFFFF; color: #334155; font-weight: 700; font-size: 11px; min-height: 0px; padding: 4px 8px; border: 1px solid #CBD5E1; border-radius: 5px; }"
                "QPushButton:hover { background: #F1F5F9; border-color: #0E7471; color: #0E7471; }"
            )
            btn_send.clicked.connect(lambda checked=False, x=tid: self._advance_to_tech(x))
            c_layout.addWidget(btn_send)
        elif stage == "SAV_SENT_TO_TECH":
            btn_ret = QPushButton("Enregistrer Retour Technicien (Étape 3)")
            btn_ret.setCursor(Qt.PointingHandCursor)
            btn_ret.setFixedHeight(30)
            btn_ret.setStyleSheet(
                "QPushButton { background: #FFFFFF; color: #0E7471; font-weight: 700; font-size: 11px; min-height: 0px; padding: 4px 8px; border: 1px solid #0E7471; border-radius: 5px; }"
                "QPushButton:hover { background: #F0FDFA; }"
            )
            btn_ret.clicked.connect(lambda checked=False, x=tid: self._advance_from_tech(x))
            c_layout.addWidget(btn_ret)
        elif stage == "SAV_RETURNED_FROM_TECH":
            btn_deliver = QPushButton("Remettre au Client && Clôturer (Étape 4)")
            btn_deliver.setCursor(Qt.PointingHandCursor)
            btn_deliver.setFixedHeight(30)
            btn_deliver.setStyleSheet(
                "QPushButton { background: #0E7471; color: white; font-weight: 700; font-size: 11px; min-height: 0px; padding: 4px 8px; border: none; border-radius: 5px; }"
                "QPushButton:hover { background: #0A5E5C; }"
            )
            btn_deliver.clicked.connect(lambda checked=False, x=tid: self._deliver_to_client(x))
            c_layout.addWidget(btn_deliver)

            btn_irrep = QPushButton("Irréparable -> Émettre Versement Virtuel")
            btn_irrep.setCursor(Qt.PointingHandCursor)
            btn_irrep.setFixedHeight(28)
            btn_irrep.setStyleSheet(
                "QPushButton { background: #FEF2F2; color: #DC2626; font-weight: 700; font-size: 11px; min-height: 0px; padding: 4px 8px; border: 1px solid #FECACA; border-radius: 5px; }"
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
