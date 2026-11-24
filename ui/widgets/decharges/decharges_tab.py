# -*- coding: utf-8 -*-
"""
ui/widgets/decharges/decharges_tab.py
=====================================
Dedicated Décharges navbar workspace allowing users to record financial outflows
from any available source (Cash, BaridiMob, TPE, CCP) categorized by Types de Décharges
(managed in Données de Base) and automatically synchronized to Treasury_Movements.
"""

from typing import Any, Dict, List, Optional

from PySide6.QtCore import QDate, QSize, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
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

from database.decharge_manager import DechargeManager
from ui.formatting import format_money
from ui.icons import apply_button_icon, get_duotone_icon

SOURCE_TILES = [
    ("Cash", "Espèces", "pay_cash"),
    ("BaridiMob", "BaridiMob", "pay_baridimob"),
    ("TPE", "TPE", "pay_tpe"),
    ("CCP", "CCP", "pay_ccp"),
]


class DechargeCreateDialog(QDialog):
    """Clean, simple dialog to record a new Décharge (no quick-add chips)."""

    def __init__(
        self,
        decharge_mgr: DechargeManager,
        current_user: Optional[Dict[str, Any]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._mgr = decharge_mgr
        self.current_user = current_user or {}
        self.result_data: Optional[Dict[str, Any]] = None

        self.setWindowTitle("Nouvelle Décharge (Sortie Financière)")
        self.setModal(True)
        self.resize(520, 460)
        self._init_ui()

    def _init_ui(self) -> None:
        self.setObjectName("DechargeModalDialog")
        self.setStyleSheet(
            """
            QDialog#DechargeModalDialog { background-color: #F8FAFC; color: #0F172A; }
            QDialog#DechargeModalDialog QLabel { border: none; background: transparent; }
            QFrame#DchCard {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 10px;
            }
            QDialog#DechargeModalDialog QLineEdit,
            QDialog#DechargeModalDialog QComboBox,
            QDialog#DechargeModalDialog QDoubleSpinBox,
            QDialog#DechargeModalDialog QDateEdit {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 5px 10px;
                min-height: 34px;
                font-size: 13px;
                color: #0F172A;
            }
            QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QDateEdit:focus {
                border: 1.5px solid #0E7471;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        # Header
        hdr = QFrame()
        hdr.setObjectName("DchCard")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(14, 10, 14, 10)
        hl.setSpacing(10)
        ic = QLabel()
        ic.setPixmap(get_duotone_icon("return_arrow", 24).pixmap(24, 24))
        hl.addWidget(ic)
        tc = QVBoxLayout()
        tc.setSpacing(2)
        t = QLabel("Enregistrer une Décharge")
        t.setStyleSheet("font-size: 16px; font-weight: 800; color: #B91C1C;")
        s = QLabel("Sortie financière enregistrée automatiquement dans la Trésorerie (حركة المال)")
        s.setStyleSheet("font-size: 12px; color: #64748B;")
        tc.addWidget(t)
        tc.addWidget(s)
        hl.addLayout(tc, 1)
        root.addWidget(hdr)

        # Form Card
        card = QFrame()
        card.setObjectName("DchCard")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.setSpacing(12)

        lbl_src = QLabel("Source financière (Compte débité) :")
        lbl_src.setStyleSheet("font-size: 12px; font-weight: 700; color: #334155;")
        cl.addWidget(lbl_src)

        src_row = QHBoxLayout()
        src_row.setSpacing(8)
        self.src_group = QButtonGroup(self)
        self.src_group.setExclusive(True)
        for idx, (code, label, icon_name) in enumerate(SOURCE_TILES):
            btn = QPushButton(label)
            btn.setObjectName("DchSrcTile")
            btn.setCheckable(True)
            btn.setChecked(idx == 0)
            btn.setFixedHeight(38)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setIcon(get_duotone_icon(icon_name, 18))
            btn.setIconSize(QSize(18, 18))
            btn.setProperty("source_code", code)
            btn.setStyleSheet(
                """
                QPushButton#DchSrcTile {
                    background-color: #FFFFFF; border: 1.5px solid #CBD5E1; border-radius: 7px;
                    color: #334155; font-size: 12px; font-weight: 700; padding: 0 8px;
                }
                QPushButton#DchSrcTile:checked {
                    background-color: #FEF2F2; border: 2px solid #DC2626; color: #B91C1C;
                }
                QPushButton#DchSrcTile:hover:!checked { background-color: #F8FAFC; }
                """
            )
            self.src_group.addButton(btn)
            src_row.addWidget(btn, 1)
        cl.addLayout(src_row)

        form = QFormLayout()
        form.setSpacing(10)

        self.cbo_type = QComboBox()
        types = self._mgr.get_all_types(only_active=True) if self._mgr else []
        for tp in types:
            self.cbo_type.addItem(get_duotone_icon("tag_family", 15), str(tp["Type_Name"]), int(tp["Type_ID"]))
        form.addRow("Type de Décharge * :", self.cbo_type)

        self.spin_amount = QDoubleSpinBox()
        self.spin_amount.setRange(0.0, 999_999_999.99)
        self.spin_amount.setDecimals(2)
        self.spin_amount.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_amount.setSuffix(" DA")
        self.spin_amount.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.spin_amount.setStyleSheet("QDoubleSpinBox { font-size: 17px; font-weight: 800; color: #0F172A; min-height: 38px; }")
        self.spin_amount.valueChanged.connect(self._validate)
        form.addRow("Montant (DA) * :", self.spin_amount)

        self.txt_beneficiary = QLineEdit()
        self.txt_beneficiary.setPlaceholderText("Bénéficiaire / Personne / Organisme")
        form.addRow("Bénéficiaire :", self.txt_beneficiary)

        self.txt_reason = QLineEdit()
        self.txt_reason.setPlaceholderText("Motif / Description (optionnel — utilise le Type par défaut)")
        form.addRow("Motif :", self.txt_reason)

        row_meta = QHBoxLayout()
        row_meta.setSpacing(8)
        self.dt_date = QDateEdit(QDate.currentDate())
        self.dt_date.setCalendarPopup(True)
        self.dt_date.setDisplayFormat("yyyy-MM-dd")
        self.txt_ref = QLineEdit()
        self.txt_ref.setPlaceholderText("N° Pièce / Reçu (optionnel)")
        row_meta.addWidget(self.dt_date)
        row_meta.addWidget(self.txt_ref, 1)
        form.addRow("Date & Réf. :", row_meta)

        cl.addLayout(form)
        root.addWidget(card)

        self.lbl_hint = QLabel("")
        self.lbl_hint.setStyleSheet("font-size: 12px; font-weight: 600; color: #B45309;")
        root.addWidget(self.lbl_hint)

        # Footer
        btns = QHBoxLayout()
        btns.setSpacing(10)
        btns.addStretch(1)

        btn_cancel = QPushButton("Annuler")
        apply_button_icon(btn_cancel, "close_slate", 15)
        btn_cancel.setFixedHeight(38)
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet(
            "QPushButton { background:#FFFFFF; border:1px solid #CBD5E1; border-radius:6px; "
            "color:#334155; font-size:13px; font-weight:600; padding:0 18px; }"
            "QPushButton:hover { background:#F1F5F9; }"
        )
        btn_cancel.clicked.connect(self.reject)

        self.btn_submit = QPushButton("Valider la Décharge")
        apply_button_icon(self.btn_submit, "check_white", 15)
        self.btn_submit.setFixedHeight(38)
        self.btn_submit.setCursor(Qt.PointingHandCursor)
        self.btn_submit.setStyleSheet(
            """
            QPushButton {
                background-color: #DC2626; border: none; border-radius: 6px;
                color: #FFFFFF; font-size: 13px; font-weight: 700; padding: 0 22px;
            }
            QPushButton:hover:enabled { background-color: #B91C1C; }
            QPushButton:disabled { background-color: #E2E8F0; color: #64748B; }
            """
        )
        self.btn_submit.clicked.connect(self._submit)

        btns.addWidget(btn_cancel)
        btns.addWidget(self.btn_submit)
        root.addLayout(btns)

        self._validate()
        self.spin_amount.setFocus()
        self.spin_amount.selectAll()

    def _selected_source(self) -> str:
        btn = self.src_group.checkedButton()
        return str(btn.property("source_code") or "Cash") if btn else "Cash"

    def _validate(self) -> None:
        amt = float(self.spin_amount.value() or 0.0)
        has_type = self.cbo_type.count() > 0
        ok = amt > 0.0 and has_type
        self.btn_submit.setEnabled(ok)
        if not has_type:
            self.lbl_hint.setText("Ajoutez d'abord un Type de Décharge dans Données de Base.")
            self.btn_submit.setToolTip("Aucun type de décharge configuré.")
        elif amt <= 0.0:
            self.lbl_hint.setText("Saisissez un montant supérieur à 0,00 DA pour valider.")
            self.btn_submit.setToolTip("Montant requis (> 0 DA).")
        else:
            self.lbl_hint.setText("")
            self.btn_submit.setToolTip("Enregistrer la décharge et débiter la trésorerie")

    def _submit(self) -> None:
        type_id = self.cbo_type.currentData()
        amt = float(self.spin_amount.value() or 0.0)
        if not type_id or amt <= 0.0:
            return
        try:
            uid = int(self.current_user.get("User_ID") or 1) if isinstance(self.current_user, dict) else 1
            dt_val = self.dt_date.date().toString("yyyy-MM-dd")
            today = QDate.currentDate().toString("yyyy-MM-dd")
            self.result_data = self._mgr.create_decharge(
                type_id=int(type_id),
                payment_method=self._selected_source(),
                amount=amt,
                reason=self.txt_reason.text().strip(),
                beneficiary=self.txt_beneficiary.text().strip(),
                reference=self.txt_ref.text().strip(),
                decharge_date=None if dt_val == today else dt_val,
                user_id=uid,
            )
            self.accept()
        except Exception as err:
            QMessageBox.critical(self, "Erreur Décharge", str(err))


class DechargesTab(QWidget):
    """Main Décharges sidebar workspace synced with Treasury_Movements."""

    def __init__(self, data_manager: Any, current_user: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.current_user = current_user or {}
        self._mgr = getattr(data_manager, "decharges", None)
        if self._mgr is None and getattr(data_manager, "db", None) is not None:
            self._mgr = DechargeManager(data_manager.db)
        self._rows: List[Dict[str, Any]] = []
        self._init_ui()
        self.refresh_data()

    def _init_ui(self) -> None:
        self.setObjectName("DechargesWorkspace")
        self.setStyleSheet(
            """
            QWidget#DechargesWorkspace { background-color: #F8FAFC; }
            QFrame#DchPanel {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 10px;
            }
            QFrame#DchPanel QLabel { border: none; background: transparent; }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        # Header
        hdr = QFrame()
        hdr.setObjectName("DchPanel")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(14, 10, 14, 10)
        hl.setSpacing(12)

        ic = QLabel()
        ic.setFixedSize(36, 36)
        ic.setAlignment(Qt.AlignCenter)
        ic.setPixmap(get_duotone_icon("return_arrow", 22).pixmap(22, 22))
        ic.setStyleSheet("background-color: #FEF2F2; border-radius: 8px;")
        hl.addWidget(ic)

        tc = QVBoxLayout()
        tc.setSpacing(2)
        t = QLabel("Décharges & Sorties Financières")
        t.setStyleSheet("font-size: 16px; font-weight: 800; color: #0F172A;")
        s = QLabel("Enregistrement des décharges par type et source financière — synchronisé avec la Trésorerie")
        s.setStyleSheet("font-size: 12px; color: #64748B;")
        tc.addWidget(t)
        tc.addWidget(s)
        hl.addLayout(tc, 1)

        btn_new = QPushButton("Nouvelle Décharge")
        apply_button_icon(btn_new, "plus_white", 16)
        btn_new.setFixedHeight(38)
        btn_new.setCursor(Qt.PointingHandCursor)
        btn_new.setStyleSheet(
            "QPushButton { background:#DC2626; color:#FFFFFF; border:none; border-radius:6px; "
            "font-size:13px; font-weight:700; padding:0 16px; }"
            "QPushButton:hover { background:#B91C1C; }"
        )
        btn_new.clicked.connect(self.open_create_dialog)
        hl.addWidget(btn_new)

        btn_ref = QPushButton("Actualiser")
        apply_button_icon(btn_ref, "refresh", 15)
        btn_ref.setFixedHeight(38)
        btn_ref.setCursor(Qt.PointingHandCursor)
        btn_ref.setStyleSheet(
            "QPushButton { background:#FFFFFF; color:#334155; border:1px solid #CBD5E1; border-radius:6px; "
            "font-size:12.5px; font-weight:600; padding:0 14px; }"
            "QPushButton:hover { background:#F1F5F9; }"
        )
        btn_ref.clicked.connect(self.refresh_data)
        hl.addWidget(btn_ref)
        root.addWidget(hdr)

        # KPI Row
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(10)
        self.lbl_kpi_total, c1 = self._make_kpi("TOTAL DÉCHARGES", "0,00 DA", "#DC2626", "waste_bin")
        self.lbl_kpi_count, c2 = self._make_kpi("OPÉRATIONS", "0", "#0F172A", "order_doc")
        self.lbl_kpi_cash, c3 = self._make_kpi("ESPÈCES (CASH)", "0,00 DA", "#0E7471", "pay_cash")
        self.lbl_kpi_bank, c4 = self._make_kpi("CCP / BARIDIMOB / TPE", "0,00 DA", "#2563EB", "pay_ccp")
        for c in (c1, c2, c3, c4):
            kpi_row.addWidget(c, 1)
        root.addLayout(kpi_row)

        # Filter Bar
        flt_card = QFrame()
        flt_card.setObjectName("DchPanel")
        fl = QHBoxLayout(flt_card)
        fl.setContentsMargins(12, 8, 12, 8)
        fl.setSpacing(8)

        self.dt_from = QDateEdit(QDate.currentDate().addMonths(-1))
        self.dt_from.setCalendarPopup(True)
        self.dt_from.setDisplayFormat("yyyy-MM-dd")
        self.dt_from.setFixedHeight(34)
        self.dt_from.dateChanged.connect(self.refresh_data)

        self.dt_to = QDateEdit(QDate.currentDate())
        self.dt_to.setCalendarPopup(True)
        self.dt_to.setDisplayFormat("yyyy-MM-dd")
        self.dt_to.setFixedHeight(34)
        self.dt_to.dateChanged.connect(self.refresh_data)

        self.cbo_type_filter = QComboBox()
        self.cbo_type_filter.setFixedHeight(34)
        self.cbo_type_filter.setMinimumWidth(160)
        self.cbo_type_filter.currentIndexChanged.connect(self.refresh_data)

        self.cbo_src_filter = QComboBox()
        self.cbo_src_filter.setFixedHeight(34)
        self.cbo_src_filter.addItem(get_duotone_icon("filter", 15), "Toutes sources", "ALL")
        for code, lbl, ic_n in SOURCE_TILES:
            self.cbo_src_filter.addItem(get_duotone_icon(ic_n, 15), lbl, code)
        self.cbo_src_filter.currentIndexChanged.connect(self.refresh_data)

        self.txt_search = QLineEdit()
        self.txt_search.setFixedHeight(34)
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.setPlaceholderText("Rechercher code, bénéficiaire, motif, réf...")
        self.txt_search.textChanged.connect(self.refresh_data)

        fl.addWidget(QLabel("Du:"))
        fl.addWidget(self.dt_from)
        fl.addWidget(QLabel("Au:"))
        fl.addWidget(self.dt_to)
        fl.addWidget(self.cbo_type_filter)
        fl.addWidget(self.cbo_src_filter)
        fl.addWidget(self.txt_search, 1)
        root.addWidget(flt_card)

        # Table
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "Code", "Date", "Type de Décharge", "Source",
            "Bénéficiaire", "Motif", "Montant (DA)", "Action"
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.horizontalHeader().setFixedHeight(36)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setStyleSheet(
            """
            QTableWidget {
                background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px;
                gridline-color: #F1F5F9; font-size: 12.5px; color: #0F172A;
            }
            QHeaderView::section {
                background-color: #F8FAFC; color: #334155; font-weight: 700; font-size: 12px;
                border: none; border-bottom: 2px solid #0E7471; padding: 6px 8px;
            }
            """
        )
        hdr_tbl = self.table.horizontalHeader()
        hdr_tbl.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr_tbl.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr_tbl.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr_tbl.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr_tbl.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hdr_tbl.setSectionResizeMode(5, QHeaderView.Stretch)
        hdr_tbl.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        hdr_tbl.setSectionResizeMode(7, QHeaderView.Fixed)
        self.table.setColumnWidth(7, 96)
        root.addWidget(self.table, 1)

    def _make_kpi(self, title: str, val: str, color: str, icon_name: str):
        card = QFrame()
        card.setObjectName("DchPanel")
        card.setFixedHeight(74)
        lay = QHBoxLayout(card)
        lay.setContentsMargins(14, 10, 14, 10)
        tc = QVBoxLayout()
        tc.setSpacing(2)
        lk = QLabel(title)
        lk.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748B;")
        lv = QLabel(val)
        lv.setStyleSheet(f"font-size: 17px; font-weight: 800; color: {color};")
        tc.addWidget(lk)
        tc.addWidget(lv)
        lay.addLayout(tc, 1)
        ic = QLabel()
        ic.setFixedSize(36, 36)
        ic.setAlignment(Qt.AlignCenter)
        ic.setPixmap(get_duotone_icon(icon_name, 20).pixmap(20, 20))
        ic.setStyleSheet(f"background-color: {color}15; border-radius: 18px;")
        lay.addWidget(ic)
        return lv, card

    def _sync_type_filter(self) -> None:
        if not self._mgr:
            return
        cur_data = self.cbo_type_filter.currentData()
        self.cbo_type_filter.blockSignals(True)
        self.cbo_type_filter.clear()
        self.cbo_type_filter.addItem(get_duotone_icon("tag_family", 15), "Tous les types", None)
        for tp in self._mgr.get_all_types(only_active=False):
            self.cbo_type_filter.addItem(str(tp["Type_Name"]), int(tp["Type_ID"]))
        idx = self.cbo_type_filter.findData(cur_data)
        if idx >= 0:
            self.cbo_type_filter.setCurrentIndex(idx)
        self.cbo_type_filter.blockSignals(False)

    def refresh_data(self) -> None:
        self._sync_type_filter()
        if not self._mgr:
            return
        rows = self._mgr.get_decharges(
            type_id=self.cbo_type_filter.currentData(),
            payment_method=self.cbo_src_filter.currentData(),
            start_date=self.dt_from.date().toString("yyyy-MM-dd"),
            end_date=self.dt_to.date().toString("yyyy-MM-dd"),
            search=self.txt_search.text().strip() or None,
        )
        self._rows = rows

        total = sum(float(r.get("Amount") or 0.0) for r in rows)
        cash = sum(float(r.get("Amount") or 0.0) for r in rows if r.get("Payment_Method") == "Cash")
        bank = total - cash
        self.lbl_kpi_total.setText(f"{format_money(total)} DA")
        self.lbl_kpi_count.setText(str(len(rows)))
        self.lbl_kpi_cash.setText(f"{format_money(cash)} DA")
        self.lbl_kpi_bank.setText(f"{format_money(bank)} DA")

        self.table.setRowCount(0)
        bold = QFont("Segoe UI", 9.5, QFont.Bold)
        for r_idx, r in enumerate(rows):
            self.table.insertRow(r_idx)
            it_code = QTableWidgetItem(str(r.get("Decharge_Code") or ""))
            it_code.setFont(bold)
            self.table.setItem(r_idx, 0, it_code)

            it_dt = QTableWidgetItem(str(r.get("Decharge_Date") or "")[:16])
            it_dt.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r_idx, 1, it_dt)

            self.table.setItem(r_idx, 2, QTableWidgetItem(str(r.get("Type_Name") or "")))

            it_src = QTableWidgetItem(str(r.get("Payment_Method") or "Cash"))
            it_src.setTextAlignment(Qt.AlignCenter)
            it_src.setFont(bold)
            self.table.setItem(r_idx, 3, it_src)

            self.table.setItem(r_idx, 4, QTableWidgetItem(str(r.get("Beneficiary") or "—")))
            self.table.setItem(r_idx, 5, QTableWidgetItem(str(r.get("Reason") or "")))

            it_amt = QTableWidgetItem(f"- {format_money(float(r.get('Amount') or 0.0))} DA")
            it_amt.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_amt.setFont(bold)
            it_amt.setForeground(QColor("#DC2626"))
            self.table.setItem(r_idx, 6, it_amt)

            btn_del = QPushButton("Annuler")
            apply_button_icon(btn_del, "trash", 14)
            btn_del.setFixedHeight(28)
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.setStyleSheet(
                "QPushButton { background:#FFFFFF; border:1px solid #FCA5A5; border-radius:4px; "
                "color:#B91C1C; font-size:11px; font-weight:700; padding:0 6px; }"
                "QPushButton:hover { background:#FEF2F2; }"
            )
            btn_del.clicked.connect(lambda _=False, did=int(r["Decharge_ID"]), code=r["Decharge_Code"]: self._cancel_decharge(did, code))
            wrap = QWidget()
            wl = QHBoxLayout(wrap)
            wl.setContentsMargins(4, 4, 4, 4)
            wl.addWidget(btn_del)
            self.table.setCellWidget(r_idx, 7, wrap)

    def open_create_dialog(self) -> None:
        if not self._mgr:
            return
        dlg = DechargeCreateDialog(self._mgr, current_user=self.current_user, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.refresh_data()

    def _cancel_decharge(self, decharge_id: int, code: str) -> None:
        ans = QMessageBox.question(
            self,
            "Annuler la Décharge",
            f"Voulez-vous annuler la décharge {code} ?\nLe mouvement correspondant en Trésorerie sera également annulé.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ans == QMessageBox.Yes:
            uid = int(self.current_user.get("User_ID") or 1) if isinstance(self.current_user, dict) else 1
            if self._mgr.cancel_decharge(decharge_id, user_id=uid):
                self.refresh_data()
