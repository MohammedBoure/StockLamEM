# -*- coding: utf-8 -*-
"""
Modal dialogs for Treasury operations:
- TreasuryOperationDialog: Record Entrée (IN) or Sortie (OUT) by payment method
- TreasuryTransferDialog: Internal transfer between payment methods (e.g. Cash -> CCP)
- TreasuryMovementDetailsDialog: Read-only audit details for any movement row
"""

from typing import Any, Dict, Optional

from PySide6.QtCore import QDate, QSize, Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from database.treasury_manager import ENTRY_CATEGORIES, EXIT_CATEGORIES
from ui.formatting import format_money
from ui.icons import get_duotone_icon

PAYMENT_METHOD_TILES = [
    ("Cash", "Espèces", "pay_cash"),
    ("BaridiMob", "BaridiMob", "pay_baridimob"),
    ("TPE", "TPE", "pay_tpe"),
    ("CCP", "CCP", "pay_ccp"),
]


def _resolve_treasury_manager(data_manager: Any):
    if data_manager is None:
        return None
    mgr = getattr(data_manager, "treasury", None)
    if mgr is not None:
        return mgr
    db = getattr(data_manager, "db", None)
    if db is not None:
        try:
            from database.treasury_manager import TreasuryManager

            return TreasuryManager(db)
        except Exception:
            return None
    return None


def _build_payment_strip(
    parent: QWidget,
    default_method: str = "Cash",
    on_changed=None,
) -> tuple[QFrame, QButtonGroup, Dict[str, QPushButton]]:
    strip = QFrame(parent)
    strip.setObjectName("TreasuryMethodStrip")
    lay = QHBoxLayout(strip)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)

    group = QButtonGroup(parent)
    group.setExclusive(True)
    buttons: Dict[str, QPushButton] = {}

    for code, label, icon_name in PAYMENT_METHOD_TILES:
        btn = QPushButton(label)
        btn.setObjectName("TreasuryMethodTile")
        btn.setCheckable(True)
        btn.setFixedHeight(38)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setIcon(get_duotone_icon(icon_name, 18))
        btn.setIconSize(QSize(18, 18))
        btn.setProperty("payment_code", code)
        btn.setStyleSheet(
            """
            QPushButton#TreasuryMethodTile {
                background-color: #FFFFFF;
                border: 1.5px solid #CBD5E1;
                border-radius: 7px;
                color: #334155;
                font-size: 12px;
                font-weight: 700;
                padding: 0 10px;
            }
            QPushButton#TreasuryMethodTile:checked {
                background-color: #E6F4F1;
                border: 2px solid #0E7471;
                color: #0E7471;
            }
            QPushButton#TreasuryMethodTile:hover:!checked {
                background-color: #F8FAFC;
                border-color: #94A3B8;
            }
            """
        )
        group.addButton(btn)
        buttons[code] = btn
        lay.addWidget(btn, 1)

    target = default_method if default_method in buttons else "Cash"
    buttons[target].setChecked(True)
    if on_changed is not None:
        group.buttonClicked.connect(lambda _b: on_changed())
    return strip, group, buttons


_DIALOG_BASE_QSS = """
QDialog {
    background-color: #F8FAFC;
    color: #0F172A;
}
QDialog QLabel {
    border: none;
    background: transparent;
}
QFrame#DialogCard {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
}
QLineEdit, QComboBox, QDoubleSpinBox, QDateEdit {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 5px 10px;
    min-height: 32px;
    font-size: 13px;
    color: #0F172A;
}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QDateEdit:focus {
    border: 1.5px solid #0E7471;
}
"""


class TreasuryOperationDialog(QDialog):
    """Focused modal dialog to record an Entrée (IN) or Sortie (OUT) operation."""

    def __init__(
        self,
        data_manager: Any,
        direction: str = "IN",
        balances_by_method: Optional[Dict[str, float]] = None,
        current_user: Optional[Dict[str, Any]] = None,
        default_method: str = "Cash",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.data_manager = data_manager
        self._treasury_mgr = _resolve_treasury_manager(data_manager)
        self.direction = "OUT" if str(direction).upper() == "OUT" else "IN"
        self.balances_by_method = dict(balances_by_method or {})
        self.current_user = current_user or {}
        self._default_method = default_method if default_method in ("Cash", "BaridiMob", "TPE", "CCP") else "Cash"
        self.result_data: Optional[Dict[str, Any]] = None

        is_in = self.direction == "IN"
        self.setWindowTitle("Nouvelle Entrée en Trésorerie (دخول)" if is_in else "Nouvelle Sortie de Trésorerie (خروج)")
        self.setModal(True)
        self.resize(540, 520)
        self._init_ui()
        self._center_on_parent()

    def _center_on_parent(self) -> None:
        p = self.parentWidget()
        if p is not None and p.isVisible():
            geo = p.frameGeometry()
            self.move(geo.center().x() - self.width() // 2, geo.center().y() - self.height() // 2)

    def _selected_method(self) -> str:
        btn = self.method_group.checkedButton()
        return str(btn.property("payment_code") or "Cash") if btn else "Cash"

    def _init_ui(self) -> None:
        self.setStyleSheet(_DIALOG_BASE_QSS)
        is_in = self.direction == "IN"
        accent = "#0E7471" if is_in else "#DC2626"

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Header banner
        hdr_card = QFrame()
        hdr_card.setObjectName("DialogCard")
        hdr_lay = QHBoxLayout(hdr_card)
        hdr_lay.setContentsMargins(14, 10, 14, 10)
        hdr_lay.setSpacing(10)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_duotone_icon("treasury", 26).pixmap(26, 26))
        hdr_lay.addWidget(icon_lbl)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_t = QLabel("Enregistrer une Entrée (دخول)" if is_in else "Enregistrer une Sortie (خروج)")
        lbl_t.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {accent};")
        lbl_s = QLabel(
            "Alimentation de caisse, apport ou encaissement divers"
            if is_in
            else "Dépense, retrait, paiement fournisseur ou décaissement"
        )
        lbl_s.setStyleSheet("font-size: 12px; color: #64748B;")
        title_box.addWidget(lbl_t)
        title_box.addWidget(lbl_s)
        hdr_lay.addLayout(title_box, 1)
        root.addWidget(hdr_card)

        # Main Form Card
        form_card = QFrame()
        form_card.setObjectName("DialogCard")
        f_lay = QVBoxLayout(form_card)
        f_lay.setContentsMargins(14, 14, 14, 14)
        f_lay.setSpacing(10)

        lbl_m = QLabel("Mode de paiement / Compte concerné :")
        lbl_m.setStyleSheet("font-size: 12px; font-weight: 700; color: #334155;")
        f_lay.addWidget(lbl_m)

        strip, self.method_group, self.method_buttons = _build_payment_strip(
            self, default_method=self._default_method, on_changed=self._update_balance_preview
        )
        f_lay.addWidget(strip)

        # Live balance preview strip
        self.balance_preview = QFrame()
        self.balance_preview.setStyleSheet(
            "QFrame { background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 7px; }"
        )
        bp_lay = QHBoxLayout(self.balance_preview)
        bp_lay.setContentsMargins(12, 8, 12, 8)
        self.lbl_cur_bal = QLabel("Solde actuel : 0,00 DA")
        self.lbl_cur_bal.setStyleSheet("font-size: 12px; font-weight: 700; color: #475569;")
        self.lbl_new_bal = QLabel("Nouveau solde prévu : 0,00 DA")
        self.lbl_new_bal.setStyleSheet(f"font-size: 12px; font-weight: 800; color: {accent};")
        bp_lay.addWidget(self.lbl_cur_bal)
        bp_lay.addStretch(1)
        bp_lay.addWidget(self.lbl_new_bal)
        f_lay.addWidget(self.balance_preview)

        # Amount + quick chips
        amt_lbl = QLabel("Montant (DA) * :")
        amt_lbl.setStyleSheet("font-size: 12px; font-weight: 700; color: #334155;")
        f_lay.addWidget(amt_lbl)

        self.spin_amount = QDoubleSpinBox()
        self.spin_amount.setRange(0.0, 999_999_999.99)
        self.spin_amount.setDecimals(2)
        self.spin_amount.setSingleStep(500.0)
        self.spin_amount.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_amount.setSuffix(" DA")
        self.spin_amount.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.spin_amount.setStyleSheet(
            "QDoubleSpinBox { font-size: 17px; font-weight: 800; color: #0F172A; min-height: 38px; }"
        )
        self.spin_amount.valueChanged.connect(self._update_balance_preview)
        f_lay.addWidget(self.spin_amount)

        chips_row = QHBoxLayout()
        chips_row.setSpacing(6)
        for inc in (1000, 5000, 10000, 50000):
            chip = QPushButton(f"+{inc:,}".replace(",", " "))
            chip.setFixedHeight(28)
            chip.setCursor(Qt.PointingHandCursor)
            chip.setStyleSheet(
                """
                QPushButton {
                    background-color: #F1F5F9; border: 1px solid #CBD5E1; border-radius: 5px;
                    color: #334155; font-size: 11px; font-weight: 700; padding: 0 8px;
                }
                QPushButton:hover { background-color: #E2E8F0; color: #0F172A; }
                """
            )
            chip.clicked.connect(lambda _=False, v=inc: self.spin_amount.setValue(self.spin_amount.value() + v))
            chips_row.addWidget(chip)
        f_lay.addLayout(chips_row)

        # Fields
        form = QFormLayout()
        form.setSpacing(8)

        self.cbo_category = QComboBox()
        self.cbo_category.setEditable(True)
        self.cbo_category.addItems(list(ENTRY_CATEGORIES if is_in else EXIT_CATEGORIES))
        form.addRow("Catégorie :", self.cbo_category)

        self.txt_reason = QLineEdit()
        self.txt_reason.setPlaceholderText(
            "Ex : Fond de caisse matin, apport gérant..."
            if is_in
            else "Ex : Facture électricité, retrait patron, transport..."
        )
        self.txt_reason.textChanged.connect(self._validate_inline)
        form.addRow("Motif / Libellé * :", self.txt_reason)

        row_extra = QHBoxLayout()
        row_extra.setSpacing(8)
        self.txt_counterparty = QLineEdit()
        self.txt_counterparty.setPlaceholderText("Tiers / Bénéficiaire (optionnel)")
        self.txt_reference = QLineEdit()
        self.txt_reference.setPlaceholderText("N° Pièce / Reçu (optionnel)")
        row_extra.addWidget(self.txt_counterparty, 1)
        row_extra.addWidget(self.txt_reference, 1)
        form.addRow("Tiers / Réf. :", row_extra)

        row_dt = QHBoxLayout()
        row_dt.setSpacing(8)
        self.dt_movement = QDateEdit(QDate.currentDate())
        self.dt_movement.setCalendarPopup(True)
        self.dt_movement.setDisplayFormat("yyyy-MM-dd")
        self.txt_notes = QLineEdit()
        self.txt_notes.setPlaceholderText("Notes complémentaires...")
        row_dt.addWidget(self.dt_movement)
        row_dt.addWidget(self.txt_notes, 1)
        form.addRow("Date & Notes :", row_dt)

        f_lay.addLayout(form)

        self.lbl_warning = QLabel("")
        self.lbl_warning.setWordWrap(True)
        self.lbl_warning.setStyleSheet("font-size: 11.5px; font-weight: 700; color: #B45309;")
        self.lbl_warning.setVisible(False)
        f_lay.addWidget(self.lbl_warning)

        root.addWidget(form_card)

        # Footer buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_cancel = QPushButton("Annuler")
        btn_cancel.setFixedHeight(38)
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet(
            """
            QPushButton {
                background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 6px;
                color: #334155; font-size: 13px; font-weight: 600; padding: 0 18px;
            }
            QPushButton:hover { background-color: #F1F5F9; }
            """
        )
        btn_cancel.clicked.connect(self.reject)

        self.btn_submit = QPushButton("Valider l'Entrée" if is_in else "Valider la Sortie")
        self.btn_submit.setObjectName("BtnTreasurySubmit")
        self.btn_submit.setFixedHeight(38)
        self.btn_submit.setCursor(Qt.PointingHandCursor)
        btn_bg = "#0E7471" if is_in else "#DC2626"
        btn_hover = "#0A5C59" if is_in else "#B91C1C"
        self.btn_submit.setStyleSheet(
            f"""
            QPushButton#BtnTreasurySubmit {{
                background-color: {btn_bg}; border: none; border-radius: 6px;
                color: #FFFFFF; font-size: 13px; font-weight: 700; padding: 0 22px;
            }}
            QPushButton#BtnTreasurySubmit:hover:enabled {{ background-color: {btn_hover}; }}
            QPushButton#BtnTreasurySubmit:disabled {{
                background-color: #F1F5F9; color: #475569; border: 1px solid #CBD5E1;
            }}
            """
        )
        self.btn_submit.clicked.connect(self._submit)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(self.btn_submit)
        root.addLayout(btn_row)

        self._update_balance_preview()
        self.spin_amount.setFocus()
        self.spin_amount.selectAll()

    def _update_balance_preview(self) -> None:
        method = self._selected_method()
        cur = float(self.balances_by_method.get(method, 0.0) or 0.0)
        amt = float(self.spin_amount.value() or 0.0)
        projected = cur + amt if self.direction == "IN" else cur - amt

        self.lbl_cur_bal.setText(f"Solde actuel ({method}) : {format_money(cur)} DA")
        self.lbl_new_bal.setText(f"Nouveau solde prévu : {format_money(projected)} DA")
        if self.direction == "OUT" and amt > cur + 0.01:
            self.lbl_warning.setText(
                f"Attention : la sortie ({format_money(amt)} DA) dépasse le solde actuel de {method} ({format_money(cur)} DA)."
            )
            self.lbl_warning.setVisible(True)
        else:
            self.lbl_warning.setVisible(False)
        self._validate_inline()

    def _validate_inline(self) -> None:
        amt = float(self.spin_amount.value() or 0.0)
        reason = (self.txt_reason.text() or "").strip()
        ok = amt > 0.0 and bool(reason)
        self.btn_submit.setEnabled(ok)
        if amt <= 0.0:
            self.btn_submit.setToolTip("Saisissez un montant strictement supérieur à 0,00 DA.")
        elif not reason:
            self.btn_submit.setToolTip("Saisissez le motif / libellé de l'opération.")
        else:
            self.btn_submit.setToolTip("Enregistrer l'opération dans le journal de trésorerie")

    def _submit(self) -> None:
        if self._treasury_mgr is None:
            QMessageBox.critical(self, "Erreur", "Gestionnaire de trésorerie indisponible.")
            return
        amt = float(self.spin_amount.value() or 0.0)
        reason = (self.txt_reason.text() or "").strip()
        if amt <= 0 or not reason:
            self._validate_inline()
            return

        method = self._selected_method()
        cur = float(self.balances_by_method.get(method, 0.0) or 0.0)
        if self.direction == "OUT" and amt > cur + 0.01:
            reply = QMessageBox.question(
                self,
                "Solde insuffisant",
                f"Le montant de sortie ({format_money(amt)} DA) dépasse le solde actuel de {method} ({format_money(cur)} DA).\n"
                "Voulez-vous tout de même enregistrer cette sortie ?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        self.btn_submit.setEnabled(False)
        try:
            uid = int(self.current_user.get("User_ID") or 1) if isinstance(self.current_user, dict) else 1
            dt_val = self.dt_movement.date().toString("yyyy-MM-dd")
            today_str = QDate.currentDate().toString("yyyy-MM-dd")
            movement_dt = None if dt_val == today_str else f"{dt_val} 12:00:00"
            self.result_data = self._treasury_mgr.record_movement(
                direction=self.direction,
                payment_method=method,
                amount=amt,
                reason=reason,
                category=self.cbo_category.currentText().strip(),
                reference=self.txt_reference.text().strip(),
                counterparty=self.txt_counterparty.text().strip(),
                notes=self.txt_notes.text().strip(),
                movement_date=movement_dt,
                user_id=uid,
            )
            self.accept()
        except Exception as exc:
            self.btn_submit.setEnabled(True)
            QMessageBox.critical(self, "Erreur Trésorerie", str(exc))


class TreasuryTransferDialog(QDialog):
    """Modal dialog for internal transfer between payment methods (e.g. Cash -> CCP)."""

    def __init__(
        self,
        data_manager: Any,
        balances_by_method: Optional[Dict[str, float]] = None,
        current_user: Optional[Dict[str, Any]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.data_manager = data_manager
        self._treasury_mgr = _resolve_treasury_manager(data_manager)
        self.balances_by_method = dict(balances_by_method or {})
        self.current_user = current_user or {}
        self.result_data: Optional[Dict[str, Any]] = None

        self.setWindowTitle("Transfert Interne de Trésorerie")
        self.setModal(True)
        self.resize(500, 420)
        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet(_DIALOG_BASE_QSS)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        hdr = QFrame()
        hdr.setObjectName("DialogCard")
        hl = QVBoxLayout(hdr)
        hl.setContentsMargins(14, 10, 14, 10)
        hl.setSpacing(2)
        t = QLabel("Transfert Interne entre Comptes")
        t.setStyleSheet("font-size: 16px; font-weight: 800; color: #0E7471;")
        s = QLabel("Déplacer un montant d'un mode de paiement vers un autre (ex : Cash → CCP)")
        s.setStyleSheet("font-size: 12px; color: #64748B;")
        hl.addWidget(t)
        hl.addWidget(s)
        root.addWidget(hdr)

        card = QFrame()
        card.setObjectName("DialogCard")
        form = QFormLayout(card)
        form.setContentsMargins(14, 14, 14, 14)
        form.setSpacing(10)

        self.cbo_from = QComboBox()
        self.cbo_to = QComboBox()
        for code, label, icon_name in PAYMENT_METHOD_TILES:
            bal = float(self.balances_by_method.get(code, 0.0) or 0.0)
            txt = f"{code} ({format_money(bal)} DA)"
            self.cbo_from.addItem(get_duotone_icon(icon_name, 16), txt, code)
            self.cbo_to.addItem(get_duotone_icon(icon_name, 16), txt, code)
        self.cbo_from.setCurrentIndex(0)  # Cash
        self.cbo_to.setCurrentIndex(3)    # CCP
        self.cbo_from.currentIndexChanged.connect(self._validate_inline)
        self.cbo_to.currentIndexChanged.connect(self._validate_inline)

        form.addRow("Compte source (De) :", self.cbo_from)
        form.addRow("Compte destination (Vers) :", self.cbo_to)

        self.spin_amount = QDoubleSpinBox()
        self.spin_amount.setRange(0.0, 999_999_999.99)
        self.spin_amount.setDecimals(2)
        self.spin_amount.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_amount.setSuffix(" DA")
        self.spin_amount.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.spin_amount.setStyleSheet("QDoubleSpinBox { font-size: 16px; font-weight: 800; min-height: 36px; }")
        self.spin_amount.valueChanged.connect(self._validate_inline)
        form.addRow("Montant à transférer * :", self.spin_amount)

        self.txt_reason = QLineEdit("Versement caisse vers compte")
        self.txt_reason.textChanged.connect(self._validate_inline)
        form.addRow("Motif * :", self.txt_reason)

        self.txt_ref = QLineEdit()
        self.txt_ref.setPlaceholderText("N° bordereau / référence (optionnel)")
        form.addRow("Référence :", self.txt_ref)

        self.lbl_error = QLabel("")
        self.lbl_error.setWordWrap(True)
        self.lbl_error.setStyleSheet("font-size: 11.5px; font-weight: 700; color: #B45309;")
        self.lbl_error.setVisible(False)
        form.addRow("", self.lbl_error)

        root.addWidget(card)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        btn_cancel = QPushButton("Annuler")
        btn_cancel.setFixedHeight(38)
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet(
            "QPushButton { background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 6px; padding: 0 18px; font-weight: 600; }"
        )
        btn_cancel.clicked.connect(self.reject)

        self.btn_submit = QPushButton("Exécuter le Transfert")
        self.btn_submit.setObjectName("BtnTransferSubmit")
        self.btn_submit.setFixedHeight(38)
        self.btn_submit.setCursor(Qt.PointingHandCursor)
        self.btn_submit.setStyleSheet(
            """
            QPushButton#BtnTransferSubmit {
                background-color: #0E7471; border: none; border-radius: 6px;
                color: #FFFFFF; font-size: 13px; font-weight: 700; padding: 0 20px;
            }
            QPushButton#BtnTransferSubmit:hover:enabled { background-color: #0A5C59; }
            QPushButton#BtnTransferSubmit:disabled {
                background-color: #F1F5F9; color: #475569; border: 1px solid #CBD5E1;
            }
            """
        )
        self.btn_submit.clicked.connect(self._submit)
        btns.addStretch(1)
        btns.addWidget(btn_cancel)
        btns.addWidget(self.btn_submit)
        root.addLayout(btns)

        self._validate_inline()
        self.spin_amount.setFocus()

    def _validate_inline(self) -> None:
        src = str(self.cbo_from.currentData() or "Cash")
        dst = str(self.cbo_to.currentData() or "CCP")
        amt = float(self.spin_amount.value() or 0.0)
        reason = (self.txt_reason.text() or "").strip()
        src_bal = float(self.balances_by_method.get(src, 0.0) or 0.0)

        if src == dst:
            self.lbl_error.setText("Le compte source et le compte destination doivent être différents.")
            self.lbl_error.setVisible(True)
            self.btn_submit.setEnabled(False)
            self.btn_submit.setToolTip("Sélectionnez deux comptes différents.")
            return

        if amt > src_bal + 0.01:
            self.lbl_error.setText(
                f"Attention : le montant dépasse le solde actuel de {src} ({format_money(src_bal)} DA)."
            )
            self.lbl_error.setVisible(True)
        else:
            self.lbl_error.setVisible(False)

        ok = amt > 0.0 and bool(reason)
        self.btn_submit.setEnabled(ok)
        if amt <= 0.0:
            self.btn_submit.setToolTip("Saisissez un montant supérieur à 0,00 DA.")
        elif not reason:
            self.btn_submit.setToolTip("Le motif du transfert est requis.")
        else:
            self.btn_submit.setToolTip(f"Transférer {format_money(amt)} DA de {src} vers {dst}")

    def _submit(self) -> None:
        if self._treasury_mgr is None:
            return
        src = str(self.cbo_from.currentData() or "Cash")
        dst = str(self.cbo_to.currentData() or "CCP")
        amt = float(self.spin_amount.value() or 0.0)
        reason = (self.txt_reason.text() or "").strip()
        if src == dst or amt <= 0 or not reason:
            return
        self.btn_submit.setEnabled(False)
        try:
            uid = int(self.current_user.get("User_ID") or 1) if isinstance(self.current_user, dict) else 1
            self.result_data = self._treasury_mgr.record_transfer(
                from_method=src,
                to_method=dst,
                amount=amt,
                reason=reason,
                reference=self.txt_ref.text().strip(),
                user_id=uid,
            )
            self.accept()
        except Exception as exc:
            self.btn_submit.setEnabled(True)
            QMessageBox.critical(self, "Erreur Transfert", str(exc))


class TreasuryMovementDetailsDialog(QDialog):
    """Read-only modal displaying full audit metadata for a financial movement."""

    def __init__(self, movement: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.movement = dict(movement or {})
        self.setWindowTitle(f"Détails Mouvement — {self.movement.get('movement_code', '')}")
        self.setModal(True)
        self.resize(460, 380)
        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet(_DIALOG_BASE_QSS)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        card = QFrame()
        card.setObjectName("DialogCard")
        form = QFormLayout(card)
        form.setContentsMargins(16, 14, 16, 14)
        form.setSpacing(8)

        direction = str(self.movement.get("direction") or "IN").upper()
        amt = float(self.movement.get("amount") or 0.0)
        sign = "+" if direction == "IN" else "-"
        color = "#16A34A" if direction == "IN" else "#DC2626"

        lbl_amt = QLabel(f"{sign}{format_money(amt)} DA")
        lbl_amt.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {color};")
        form.addRow("Montant :", lbl_amt)

        fields = [
            ("Référence / Pièce :", self.movement.get("reference") or self.movement.get("movement_code") or "—"),
            ("Date & Heure :", self.movement.get("timestamp") or "—"),
            ("Sens :", "Entrée (+)" if direction == "IN" else "Sortie (-)"),
            ("Mode de Paiement :", self.movement.get("payment_method") or "Cash"),
            ("Origine / Catégorie :", self.movement.get("category") or "—"),
            ("Libellé / Motif :", self.movement.get("reason") or "—"),
            ("Tiers / Client :", self.movement.get("counterparty") or "—"),
            ("Solde après op. :", f"{format_money(float(self.movement.get('display_balance_after') or 0.0))} DA"),
            ("Opérateur :", self.movement.get("operator") or "Système"),
            ("Notes :", self.movement.get("notes") or "—"),
        ]
        for label, val in fields:
            lbl = QLabel(str(val))
            lbl.setWordWrap(True)
            lbl.setStyleSheet("font-size: 12.5px; font-weight: 600; color: #0F172A;")
            form.addRow(label, lbl)

        root.addWidget(card)

        btn_close = QPushButton("Fermer")
        btn_close.setFixedHeight(36)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet(
            "QPushButton { background: #0E7471; color: #FFFFFF; border: none; border-radius: 6px; padding: 0 20px; font-weight: 700; }"
        )
        btn_close.clicked.connect(self.accept)
        root.addWidget(btn_close, alignment=Qt.AlignRight)
