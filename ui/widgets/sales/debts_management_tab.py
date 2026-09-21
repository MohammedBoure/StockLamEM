# ui/widgets/sales/debts_management_tab.py

import csv
import logging
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame, QSplitter, QGroupBox,
    QMessageBox, QFileDialog, QDoubleSpinBox, QComboBox, QDialog,
    QFormLayout, QDateEdit, QLineEdit, QRadioButton, QButtonGroup, QMenu,
    QStackedWidget
)
from PySide6.QtCore import Qt, QDate, QSize
from PySide6.QtGui import QColor, QBrush, QFont, QAction, QIcon

from ui.icons import get_duotone_icon
from ui.formatting import format_money
from ui.widgets.sales.searchable_client_combo import SearchableClientComboBox
from ui.widgets.sales.invoice_payment_dialog import InvoicePaymentDialog
from ui.widgets.master_data.client_statement_dialog import ClientStatementDialog
from ui.widgets.sales_history.pdf_export import export_invoice_to_pdf


class GlobalPaymentDialog(QDialog):
    """
    Dialogue de règlement global / acompte client.
    Permet de solder la dette globale ou d'effectuer une avance libre,
    avec option de ventilation automatique FIFO sur les factures impayées.
    """

    def __init__(self, data_manager, client_data, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.client_data = client_data
        self.client_id = client_data.get('Client_ID')
        self.client_name = client_data.get('Client_Name') or f"Client #{self.client_id}"
        self.current_balance = float(client_data.get('Current_Balance') or 0.0)
        self.credit_limit = float(client_data.get('Credit_Limit') or 0.0)

        self.setWindowTitle(f"Règlement Global / Acompte - {self.client_name}")
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self.setModal(True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(True)

        pal = self.palette()
        pal.setColor(self.backgroundRole(), QColor("#FFFFFF"))
        self.setPalette(pal)

        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 8px;
            }
        """)
        self.resize(560, 560)
        self.setMinimumSize(520, 520)
        self._init_ui()

    def exec(self):
        parent_widget = self.parent()
        if parent_widget:
            self.raise_()
            self.activateWindow()
        return super().exec()

    def exec_(self):
        return self.exec()

    def _current_user_id(self):
        try:
            from database.system_logger import active_user_id
            return active_user_id.get()
        except Exception:
            return None

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header Title
        lbl_title = QLabel("Enregistrement d'un Règlement Global ou Acompte")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #0E7471; border: none; background: transparent;")
        layout.addWidget(lbl_title)

        # 1. Section Situation Financière du Client
        lbl_sec_client = QLabel("SITUATION FINANCIÈRE DU CLIENT")
        lbl_sec_client.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748B; letter-spacing: 0.5px; border: none; background: transparent; margin-top: 2px;")
        layout.addWidget(lbl_sec_client)

        summary_frame = QFrame()
        summary_frame.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        summary_layout = QFormLayout(summary_frame)
        summary_layout.setContentsMargins(14, 10, 14, 10)
        summary_layout.setSpacing(8)

        lbl_c_tag = QLabel("Client :")
        lbl_c_tag.setStyleSheet("font-size: 12px; font-weight: 600; color: #64748B; border: none; background: transparent;")
        lbl_client = QLabel(self.client_name)
        lbl_client.setStyleSheet("font-size: 13px; font-weight: 700; color: #1F2937; border: none; background: transparent;")
        summary_layout.addRow(lbl_c_tag, lbl_client)

        lbl_b_tag = QLabel("Solde Dû Actuel :")
        lbl_b_tag.setStyleSheet("font-size: 12px; font-weight: 600; color: #64748B; border: none; background: transparent;")
        lbl_bal = QLabel(f"{format_money(self.current_balance)} DA")
        lbl_bal.setStyleSheet("font-size: 14px; font-weight: 800; color: #DC2626; border: none; background: transparent;" if self.current_balance > 0 else "font-size: 14px; font-weight: 800; color: #16A34A; border: none; background: transparent;")
        summary_layout.addRow(lbl_b_tag, lbl_bal)

        lbl_l_tag = QLabel("Plafond de Crédit :")
        lbl_l_tag.setStyleSheet("font-size: 12px; font-weight: 600; color: #64748B; border: none; background: transparent;")
        lbl_limit = QLabel(f"{format_money(self.credit_limit)} DA" if self.credit_limit > 0 else "Illimité")
        lbl_limit.setStyleSheet("font-size: 12px; font-weight: 600; color: #1F2937; border: none; background: transparent;")
        summary_layout.addRow(lbl_l_tag, lbl_limit)

        layout.addWidget(summary_frame)

        # 2. Section Paramètres de Règlement
        lbl_sec_params = QLabel("PARAMÈTRES DE RÈGLEMENT")
        lbl_sec_params.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748B; letter-spacing: 0.5px; border: none; background: transparent; margin-top: 4px;")
        layout.addWidget(lbl_sec_params)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 2, 0, 2)
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        def make_form_label(text):
            lbl = QLabel(text)
            lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #475569; border: none; background: transparent;")
            return lbl

        # Payment Date
        self.edit_date = QDateEdit(QDate.currentDate())
        self.edit_date.setCalendarPopup(True)
        self.edit_date.setDisplayFormat("yyyy-MM-dd")
        self.edit_date.setFixedHeight(38)
        self.edit_date.setStyleSheet("""
            QDateEdit {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 13px;
                font-weight: 600;
                color: #1F2937;
            }
            QDateEdit QLineEdit {
                background: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
                font-size: 13px;
                font-weight: 600;
                color: #1F2937;
            }
            QDateEdit:focus {
                border: 1.5px solid #0E7471;
            }
            QDateEdit::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 28px;
                border-left: 1px solid #DDE3EA;
                background-color: #F8FAFC;
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
            }
        """)
        form_layout.addRow(make_form_label("Date de règlement :"), self.edit_date)

        # Amount
        amt_container = QHBoxLayout()
        amt_container.setSpacing(8)
        self.spin_amount = QDoubleSpinBox()
        self.spin_amount.setRange(0.01, 999999999.0)
        self.spin_amount.setDecimals(2)
        self.spin_amount.setSingleStep(500.0)
        self.spin_amount.setSuffix(" DA")
        initial_val = self.current_balance if self.current_balance > 0 else 1000.0
        self.spin_amount.setValue(initial_val)
        self.spin_amount.setFixedHeight(38)
        self.spin_amount.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #FFFFFF;
                border: 1.5px solid #0E7471;
                border-radius: 6px;
                padding: 2px 10px;
                font-size: 14px;
                font-weight: 800;
                color: #0E7471;
            }
            QDoubleSpinBox QLineEdit {
                background: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
                font-size: 14px;
                font-weight: 800;
                color: #0E7471;
            }
            QDoubleSpinBox:focus {
                border: 2px solid #0E7471;
            }
        """)
        amt_container.addWidget(self.spin_amount, 1)

        btn_full = QPushButton("Solder Tout")
        btn_full.setCursor(Qt.PointingHandCursor)
        btn_full.setFixedHeight(38)
        btn_full.setStyleSheet("""
            QPushButton {
                background-color: #E6F4F1;
                color: #0E7471;
                border: 1px solid #BCE3DC;
                border-radius: 6px;
                padding: 0 14px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #CCEBE5; }
            QPushButton:pressed { background-color: #B2DFD8; }
        """)
        btn_full.clicked.connect(lambda: self.spin_amount.setValue(max(0.01, self.current_balance)))
        amt_container.addWidget(btn_full)

        form_layout.addRow(make_form_label("Montant versé :"), amt_container)

        # Payment Method
        self.cb_method = QComboBox()
        methods = [
            ("Espèces", "Espèce"),
            ("Chèque", "Chèque"),
            ("Virement bancaire", "Virement"),
            ("Versement bancaire", "Versement"),
            ("Carte bancaire", "Carte")
        ]
        for label, val in methods:
            self.cb_method.addItem(label, val)
        self.cb_method.setFixedHeight(38)
        self.cb_method.setStyleSheet("""
            QComboBox {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
                padding: 2px 10px;
                font-size: 13px;
                font-weight: 600;
                color: #1F2937;
            }
            QComboBox:focus {
                border: 1.5px solid #0E7471;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 28px;
                border-left: 1px solid #DDE3EA;
                background-color: #F8FAFC;
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
            }
        """)
        form_layout.addRow(make_form_label("Mode de paiement :"), self.cb_method)

        # Allocation Mode
        alloc_vbox = QVBoxLayout()
        alloc_vbox.setSpacing(4)
        self.rb_fifo = QRadioButton("Ventilation automatique FIFO (imputer sur factures les plus anciennes)")
        self.rb_fifo.setChecked(True)
        self.rb_fifo.setStyleSheet("font-size: 12px; color: #0E7471; font-weight: 600; border: none; background: transparent;")

        self.rb_free = QRadioButton("Acompte libre non lettré (déduit directement du solde global)")
        self.rb_free.setStyleSheet("font-size: 12px; color: #475569; border: none; background: transparent;")

        self.btn_group_mode = QButtonGroup(self)
        self.btn_group_mode.addButton(self.rb_fifo, 1)
        self.btn_group_mode.addButton(self.rb_free, 2)

        alloc_vbox.addWidget(self.rb_fifo)
        alloc_vbox.addWidget(self.rb_free)
        form_layout.addRow(make_form_label("Mode d'imputation :"), alloc_vbox)

        input_style = """
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 13px;
                color: #1F2937;
            }
            QLineEdit:focus {
                border: 1.5px solid #0E7471;
            }
        """

        # Reference
        self.edit_ref = QLineEdit()
        self.edit_ref.setPlaceholderText("Ex: N° Chèque, Référence virement...")
        self.edit_ref.setFixedHeight(38)
        self.edit_ref.setStyleSheet(input_style)
        form_layout.addRow(make_form_label("Référence / N° Pièce :"), self.edit_ref)

        # Notes
        self.edit_notes = QLineEdit()
        self.edit_notes.setPlaceholderText("Observations ou remarques...")
        self.edit_notes.setFixedHeight(38)
        self.edit_notes.setStyleSheet(input_style)
        form_layout.addRow(make_form_label("Observations :"), self.edit_notes)

        layout.addLayout(form_layout)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.setContentsMargins(0, 8, 0, 0)

        btn_cancel = QPushButton("Annuler")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setFixedHeight(38)
        btn_cancel.setMinimumWidth(110)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #475569;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
                padding: 0 16px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #F8FAFC; border-color: #CBD5E1; color: #1E293B; }
            QPushButton:pressed { background-color: #F1F5F9; }
        """)
        btn_cancel.clicked.connect(self.reject)

        self.btn_submit = QPushButton("Valider le Règlement")
        self.btn_submit.setIcon(get_duotone_icon("payment_white", 16))
        self.btn_submit.setIconSize(QSize(16, 16))
        self.btn_submit.setCursor(Qt.PointingHandCursor)
        self.btn_submit.setFixedHeight(38)
        self.btn_submit.setMinimumWidth(180)
        self.btn_submit.setStyleSheet("""
            QPushButton {
                background-color: #0E7471;
                color: #FFFFFF;
                font-weight: 700;
                font-size: 13px;
                padding: 0 20px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #0A5C59; }
            QPushButton:pressed { background-color: #084846; }
        """)
        self.btn_submit.clicked.connect(self._validate_and_submit)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(self.btn_submit)
        layout.addLayout(btn_layout)

    def _validate_and_submit(self):
        amount = self.spin_amount.value()
        if amount <= 0:
            QMessageBox.warning(self, "Validation", "Veuillez saisir un montant supérieur à zéro.")
            return

        pay_date = self.edit_date.date().toString("yyyy-MM-dd")
        method = self.cb_method.currentData()
        ref = self.edit_ref.text().strip() or None
        notes = self.edit_notes.text().strip() or None
        auto_fifo = self.rb_fifo.isChecked()
        user_id = self._current_user_id()

        try:
            res = self.data_manager.client_payments.add_global_payment(
                client_id=self.client_id,
                payment_date=pay_date,
                amount=amount,
                payment_method=method,
                reference=ref,
                notes=notes,
                auto_allocate_fifo=auto_fifo,
                user_id=user_id
            )

            if res and res.get('success'):
                inv_count = len(res.get('invoices_affected') or [])
                alloc_amt = res.get('allocated_to_invoices', 0.0)
                free_amt = res.get('free_advance', 0.0)

                msg = f"Règlement de {format_money(amount)} DA validé avec succès !\n\n"
                if auto_fifo:
                    msg += f"• Montant lettré : {format_money(alloc_amt)} DA ({inv_count} factures affectées)\n"
                    if free_amt > 0:
                        msg += f"• Surplus en acompte libre : {format_money(free_amt)} DA\n"
                else:
                    msg += f"• Enregistré intégralement en acompte libre : {format_money(amount)} DA\n"

                QMessageBox.information(self, "Règlement Enregistré", msg)
                self.accept()
            else:
                QMessageBox.critical(self, "Erreur", "Échec de l'enregistrement du règlement.")
        except Exception as e:
            logging.error(f"Error submitting global payment: {e}", exc_info=True)
            QMessageBox.critical(self, "Erreur", f"Erreur lors de l'enregistrement : {e}")


class ClientDebtAuditDialog(QDialog):
    """
    Modal affichant l'audit d'intégrité comptable du solde d'un client.
    """

    def __init__(self, audit_result, parent=None):
        super().__init__(parent)
        self.audit = audit_result
        self.setWindowTitle(f"Audit Comptable - {self.audit.get('client_name', '')}")
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self.setModal(True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(True)

        pal = self.palette()
        pal.setColor(self.backgroundRole(), QColor("#FFFFFF"))
        self.setPalette(pal)

        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 8px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        self.resize(520, 440)
        self._init_ui()

    def exec(self):
        parent_widget = self.parent()
        if parent_widget:
            self.raise_()
            self.activateWindow()
        return super().exec()

    def exec_(self):
        return self.exec()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        is_balanced = self.audit.get('is_balanced', False)

        header_frame = QFrame()
        header_frame.setStyleSheet(
            "background-color: #DCFCE7; border: 1px solid #BBF7D0; border-radius: 6px; padding: 10px;"
            if is_balanced else
            "background-color: #FEE2E2; border: 1px solid #FECACA; border-radius: 6px; padding: 10px;"
        )
        h_layout = QVBoxLayout(header_frame)
        h_layout.setContentsMargins(0, 0, 0, 0)
        title_text = "INTÉGRITÉ COMPTABLE CONFORME" if is_balanced else "ÉCART DE SOLDE DÉTECTÉ"
        lbl_status = QLabel(title_text)
        lbl_status.setStyleSheet("font-size: 13px; font-weight: 800; color: #166534;" if is_balanced else "font-size: 13px; font-weight: 800; color: #991B1B;")
        h_layout.addWidget(lbl_status)
        layout.addWidget(header_frame)

        lbl_sec_rec = QLabel("DÉTAIL DE LA RÉCONCILIATION")
        lbl_sec_rec.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748B; letter-spacing: 0.5px; border: none; background: transparent; margin-top: 4px;")
        layout.addWidget(lbl_sec_rec)

        form_frame = QFrame()
        form_frame.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
                font-size: 12px;
            }
        """)
        form_layout = QFormLayout(form_frame)
        form_layout.setContentsMargins(14, 12, 14, 12)
        form_layout.setSpacing(8)

        def make_tag(t):
            l = QLabel(t)
            l.setStyleSheet("font-size: 12px; font-weight: 600; color: #64748B;")
            return l

        form_layout.addRow(make_tag("Client :"), QLabel(str(self.audit.get('client_name', ''))))
        form_layout.addRow(make_tag("Solde Actuel Enregistré :"), QLabel(f"{format_money(self.audit.get('current_balance', 0.0))} DA"))
        form_layout.addRow(make_tag("Solde Théorique Reconstitué :"), QLabel(f"{format_money(self.audit.get('expected_balance', 0.0))} DA"))

        discrepancy = self.audit.get('discrepancy', 0.0)
        lbl_disc = QLabel(f"{format_money(discrepancy)} DA")
        lbl_disc.setStyleSheet("font-weight: 800; color: #16A34A;" if abs(discrepancy) < 0.01 else "font-weight: 800; color: #DC2626;")
        form_layout.addRow(make_tag("Écart Net :"), lbl_disc)

        form_layout.addRow(make_tag("Total Facturé & BL (+) :"), QLabel(f"{format_money(self.audit.get('total_invoiced', 0.0))} DA ({self.audit.get('count_invoices', 0)} pièces)"))
        form_layout.addRow(make_tag("Total Encaissé & Règlements (-) :"), QLabel(f"{format_money(self.audit.get('total_paid', 0.0))} DA ({self.audit.get('count_payments', 0)} paiements)"))
        form_layout.addRow(make_tag("Total Avoirs / Retours (-) :"), QLabel(f"{format_money(self.audit.get('total_credit_notes', 0.0))} DA ({self.audit.get('count_credit_notes', 0)} avoirs)"))

        layout.addWidget(form_frame)

        btn_close = QPushButton("Fermer")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setFixedHeight(36)
        btn_close.setMinimumWidth(100)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #0E7471;
                color: #FFFFFF;
                font-weight: 700;
                padding: 0 18px;
                border-radius: 6px;
                border: none;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #0A5C59; }
        """)
        btn_close.clicked.connect(self.accept)

        h_btn = QHBoxLayout()
        h_btn.addStretch()
        h_btn.addWidget(btn_close)
        layout.addLayout(h_btn)


class DebtsManagementTab(QWidget):
    """
    Interface dédiée à la Gestion des Créances et Suivi des Dettes Clients.
    Fournit des KPIs en temps réel, un filtrage avancé, un tableau maître des débiteurs,
    un panneau de détail (drill-down) des factures impayées et des actions rapides
    (règlement global FIFO, relevé de compte, impression de facture, audit).
    """

    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.clients_summary = []
        self.selected_client_id = None
        self.setObjectName("DebtsManagementTab")
        self.setStyleSheet("QWidget#DebtsManagementTab { background-color: #F4F6F8; }")
        self._init_ui()
        self.refresh_all()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # 1. Top Compact Summary Bar
        self._build_summary_bar(main_layout)

        # 2. Filter Bar
        self._build_filter_bar(main_layout)

        # 3. Master-Detail Splitter
        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #E2E8F0;
                height: 4px;
                margin: 2px 0;
                border-radius: 2px;
            }
            QSplitter::handle:hover {
                background-color: #0E7471;
            }
        """)

        # Master Table (Clients débiteurs)
        self.master_container = QFrame()
        master_layout = QVBoxLayout(self.master_container)
        master_layout.setContentsMargins(0, 0, 0, 0)
        master_layout.setSpacing(6)

        header_master_layout = QHBoxLayout()
        header_master_layout.setContentsMargins(2, 0, 2, 0)
        header_master_layout.setSpacing(8)

        lbl_master_icon = QLabel()
        lbl_master_icon.setPixmap(get_duotone_icon("debts", 18).pixmap(18, 18))
        header_master_layout.addWidget(lbl_master_icon)

        lbl_master_header = QLabel("Répertoire des Clients Débiteurs")
        lbl_master_header.setStyleSheet("font-size: 13px; font-weight: 800; color: #1E293B; border: none; background: transparent;")
        header_master_layout.addWidget(lbl_master_header)
        header_master_layout.addStretch()

        master_layout.addLayout(header_master_layout)

        self.table_clients = QTableWidget()
        cols = [
            "ID", "Nom du Client", "Téléphone", "Plafond Crédit",
            "Total Facturé", "Total Encaissé", "Solde Dû Actuel",
            "Dernier Règlement", "Statut", "Actions"
        ]
        self.table_clients.setColumnCount(len(cols))
        self.table_clients.setHorizontalHeaderLabels(cols)
        self.table_clients.setColumnHidden(0, True)

        # Align headers properly
        self.table_clients.horizontalHeaderItem(1).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table_clients.horizontalHeaderItem(2).setTextAlignment(Qt.AlignCenter)
        self.table_clients.horizontalHeaderItem(3).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table_clients.horizontalHeaderItem(4).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table_clients.horizontalHeaderItem(5).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table_clients.horizontalHeaderItem(6).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table_clients.horizontalHeaderItem(7).setTextAlignment(Qt.AlignCenter)
        self.table_clients.horizontalHeaderItem(8).setTextAlignment(Qt.AlignCenter)
        self.table_clients.horizontalHeaderItem(9).setTextAlignment(Qt.AlignCenter)

        self.table_clients.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for col_idx in [2, 3, 4, 5, 6, 7, 8]:
            self.table_clients.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.ResizeToContents)
        self.table_clients.horizontalHeader().setSectionResizeMode(9, QHeaderView.Fixed)
        self.table_clients.setColumnWidth(9, 200)

        table_style = """
            QTableWidget {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
                gridline-color: #E2E8F0;
                selection-background-color: #E6F4F1;
                selection-color: #0F172A;
                alternate-background-color: #F8FAFC;
            }
            QHeaderView::section {
                background-color: #F8FAFC;
                color: #0F172A;
                font-weight: 700;
                font-size: 12px;
                padding: 7px 10px;
                border: none;
                border-bottom: 2px solid #0E7471;
                border-right: 1px solid #E2E8F0;
            }
        """
        self.table_clients.setStyleSheet(table_style)
        self.table_clients.verticalHeader().setDefaultSectionSize(38)
        self.table_clients.setShowGrid(True)
        self.table_clients.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_clients.setSelectionMode(QTableWidget.SingleSelection)
        self.table_clients.setAlternatingRowColors(True)
        self.table_clients.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_clients.itemSelectionChanged.connect(self._on_client_selection_changed)
        self.table_clients.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_clients.customContextMenuRequested.connect(self._show_client_context_menu)

        master_layout.addWidget(self.table_clients)
        self.splitter.addWidget(self.master_container)

        # Detail Panel (Factures impayées du client sélectionné)
        self.detail_container = QFrame()
        detail_layout = QVBoxLayout(self.detail_container)
        detail_layout.setContentsMargins(0, 6, 0, 0)
        detail_layout.setSpacing(6)

        detail_header_layout = QHBoxLayout()
        detail_header_layout.setContentsMargins(2, 0, 2, 0)
        detail_header_layout.setSpacing(8)

        lbl_detail_icon = QLabel()
        lbl_detail_icon.setPixmap(get_duotone_icon("sales_history", 18).pixmap(18, 18))
        detail_header_layout.addWidget(lbl_detail_icon)

        self.lbl_detail_title = QLabel("Factures & Créances Impayées : (Sélectionnez un client)")
        self.lbl_detail_title.setStyleSheet("font-size: 13px; font-weight: 800; color: #0E7471;")
        detail_header_layout.addWidget(self.lbl_detail_title)
        detail_header_layout.addStretch()

        self.btn_detail_global_pay = QPushButton("Règlement Global")
        self.btn_detail_global_pay.setIcon(get_duotone_icon("payment_white", 14))
        self.btn_detail_global_pay.setIconSize(QSize(14, 14))
        self.btn_detail_global_pay.setCursor(Qt.PointingHandCursor)
        self.btn_detail_global_pay.setFixedHeight(32)
        self.btn_detail_global_pay.setStyleSheet("""
            QPushButton {
                background-color: #0E7471;
                color: #FFFFFF;
                font-weight: 700;
                padding: 0 14px;
                border-radius: 6px;
                font-size: 12px;
                border: none;
            }
            QPushButton:hover { background-color: #0A5C59; }
            QPushButton:pressed { background-color: #084846; }
            QPushButton:disabled { background-color: #CBD5E1; color: #94A3B8; }
        """)
        self.btn_detail_global_pay.setEnabled(False)
        self.btn_detail_global_pay.clicked.connect(self._open_global_payment_dialog)
        detail_header_layout.addWidget(self.btn_detail_global_pay)

        self.btn_detail_statement = QPushButton("Relevé de Compte")
        self.btn_detail_statement.setIcon(get_duotone_icon("statement", 14))
        self.btn_detail_statement.setIconSize(QSize(14, 14))
        self.btn_detail_statement.setCursor(Qt.PointingHandCursor)
        self.btn_detail_statement.setFixedHeight(32)
        self.btn_detail_statement.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #0E7471;
                border: 1.5px solid #0E7471;
                font-weight: 700;
                padding: 0 14px;
                border-radius: 6px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #E6F4F1; border-color: #0A5C59; color: #0A5C59; }
            QPushButton:pressed { background-color: #CCEBE5; }
            QPushButton:disabled { border-color: #CBD5E1; color: #94A3B8; background-color: #F8FAFC; }
        """)
        self.btn_detail_statement.setEnabled(False)
        self.btn_detail_statement.clicked.connect(self._open_client_statement_dialog)
        detail_header_layout.addWidget(self.btn_detail_statement)

        detail_layout.addLayout(detail_header_layout)

        # Stacked widget for detail area (Index 0: Table, Index 1: Empty state)
        self.detail_stack = QStackedWidget()

        self.table_invoices = QTableWidget()
        inv_cols = [
            "Facture N°", "Date", "Date d'Échéance", "Retard (Jours)",
            "Total TTC", "Déjà Payé", "Reste à Payer", "Statut", "Actions"
        ]
        self.table_invoices.setColumnCount(len(inv_cols))
        self.table_invoices.setHorizontalHeaderLabels(inv_cols)

        self.table_invoices.horizontalHeaderItem(0).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table_invoices.horizontalHeaderItem(1).setTextAlignment(Qt.AlignCenter)
        self.table_invoices.horizontalHeaderItem(2).setTextAlignment(Qt.AlignCenter)
        self.table_invoices.horizontalHeaderItem(3).setTextAlignment(Qt.AlignCenter)
        self.table_invoices.horizontalHeaderItem(4).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table_invoices.horizontalHeaderItem(5).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table_invoices.horizontalHeaderItem(6).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table_invoices.horizontalHeaderItem(7).setTextAlignment(Qt.AlignCenter)
        self.table_invoices.horizontalHeaderItem(8).setTextAlignment(Qt.AlignCenter)

        self.table_invoices.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for c_idx in [1, 2, 3, 4, 5, 6, 7]:
            self.table_invoices.horizontalHeader().setSectionResizeMode(c_idx, QHeaderView.ResizeToContents)
        self.table_invoices.horizontalHeader().setSectionResizeMode(8, QHeaderView.Fixed)
        self.table_invoices.setColumnWidth(8, 200)
        self.table_invoices.setStyleSheet(table_style)
        self.table_invoices.verticalHeader().setDefaultSectionSize(38)
        self.table_invoices.setShowGrid(True)
        self.table_invoices.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_invoices.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_invoices.setAlternatingRowColors(True)

        self.detail_stack.addWidget(self.table_invoices)

        # Empty State Card (Clean single container, no dashed border)
        self.empty_invoices_card = QFrame()
        self.empty_invoices_card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 8px;
            }
        """)
        empty_layout = QVBoxLayout(self.empty_invoices_card)
        empty_layout.setAlignment(Qt.AlignCenter)
        empty_layout.setSpacing(10)

        self.lbl_empty_icon_container = QFrame()
        self.lbl_empty_icon_container.setFixedSize(54, 54)
        self.lbl_empty_icon_container.setStyleSheet("""
            QFrame {
                background-color: #E6F4F1;
                border: 1px solid #BCE3DC;
                border-radius: 27px;
            }
        """)
        icon_box_layout = QVBoxLayout(self.lbl_empty_icon_container)
        icon_box_layout.setContentsMargins(0, 0, 0, 0)
        icon_box_layout.setAlignment(Qt.AlignCenter)
        self.lbl_empty_icon = QLabel()
        self.lbl_empty_icon.setAlignment(Qt.AlignCenter)
        self.lbl_empty_icon.setPixmap(get_duotone_icon("client_select", 32).pixmap(32, 32))
        icon_box_layout.addWidget(self.lbl_empty_icon)

        empty_layout.addWidget(self.lbl_empty_icon_container, 0, Qt.AlignCenter)

        self.lbl_empty_title = QLabel("Sélectionnez un client")
        self.lbl_empty_title.setAlignment(Qt.AlignCenter)
        self.lbl_empty_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #1E293B;")
        empty_layout.addWidget(self.lbl_empty_title)

        self.lbl_empty_desc = QLabel("Cliquez sur un client dans la liste ci-dessus pour afficher ses factures impayées.")
        self.lbl_empty_desc.setAlignment(Qt.AlignCenter)
        self.lbl_empty_desc.setStyleSheet("font-size: 12px; color: #64748B; max-width: 420px;")
        self.lbl_empty_desc.setWordWrap(True)
        empty_layout.addWidget(self.lbl_empty_desc)

        self.detail_stack.addWidget(self.empty_invoices_card)
        self.detail_stack.setCurrentIndex(1)

        detail_layout.addWidget(self.detail_stack)
        self.splitter.addWidget(self.detail_container)

        self.splitter.setSizes([340, 320])
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        main_layout.addWidget(self.splitter, 1)

    def _build_summary_bar(self, parent_layout):
        summary_bar = QFrame()
        summary_bar.setObjectName("SummaryBarFrame")
        summary_bar.setFixedHeight(38)
        summary_bar.setStyleSheet("""
            QFrame#SummaryBarFrame {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        s_layout = QHBoxLayout(summary_bar)
        s_layout.setContentsMargins(16, 2, 16, 2)
        s_layout.setSpacing(18)

        def make_summary_item(tag_text, val_attr, color_hex):
            h = QHBoxLayout()
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(6)
            lbl_tag = QLabel(tag_text)
            lbl_tag.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748B; letter-spacing: 0.5px; border: none; background: transparent;")
            h.addWidget(lbl_tag)

            lbl_v = QLabel("0.00 DA")
            lbl_v.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {color_hex}; border: none; background: transparent;")
            h.addWidget(lbl_v)
            setattr(self, val_attr, lbl_v)
            return h

        def make_sep():
            sep = QFrame()
            sep.setFrameShape(QFrame.VLine)
            sep.setStyleSheet("color: #E2E8F0; max-width: 1px; max-height: 18px; border: none; background-color: #E2E8F0;")
            return sep

        # 1. Total Créances
        s_layout.addLayout(make_summary_item("TOTAL CRÉANCES :", "lbl_kpi_total_receivables", "#0E7471"))
        s_layout.addWidget(make_sep())

        # 2. Créances Échues
        s_layout.addLayout(make_summary_item("ÉCHUES / EN RETARD :", "lbl_kpi_overdue_receivables", "#DC2626"))
        s_layout.addWidget(make_sep())

        # 3. Clients Débiteurs
        s_layout.addLayout(make_summary_item("CLIENTS DÉBITEURS :", "lbl_kpi_debtor_count", "#D97706"))
        s_layout.addWidget(make_sep())

        # 4. Encaissé ce Mois
        s_layout.addLayout(make_summary_item("ENCAISSÉ CE MOIS :", "lbl_kpi_month_recovered", "#16A34A"))

        s_layout.addStretch(1)
        parent_layout.addWidget(summary_bar)

    _build_kpi_cards = _build_summary_bar

    def _build_filter_bar(self, parent_layout):
        filter_frame = QFrame()
        filter_frame.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 8px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        f_layout = QHBoxLayout(filter_frame)
        f_layout.setContentsMargins(12, 10, 12, 10)
        f_layout.setSpacing(14)

        def make_filter_col(label_text, widget):
            v = QVBoxLayout()
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(4)
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.5px; border: none; background: transparent;")
            v.addWidget(lbl)
            v.addWidget(widget)
            return v

        filter_input_style = """
            QComboBox, QDoubleSpinBox {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                color: #0F172A;
            }
            QComboBox:focus, QDoubleSpinBox:focus {
                border: 1.5px solid #0E7471;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left-width: 0px;
            }
        """

        # 1. Searchable Client Filter
        self.cb_client_filter = SearchableClientComboBox(self, placeholder="Rechercher nom ou tél...")
        self.cb_client_filter.setMinimumWidth(250)
        self.cb_client_filter.setFixedHeight(38)
        self.cb_client_filter.client_changed.connect(self._on_client_filter_changed)
        f_layout.addLayout(make_filter_col("Client", self.cb_client_filter))

        # 2. Status Filter
        self.cb_status_filter = QComboBox()
        self.cb_status_filter.setStyleSheet(filter_input_style)
        self.cb_status_filter.addItems([
            "Tous",
            "Dépassant le Plafond",
            "En Retard / Échues",
            "Actifs",
            "Soldés"
        ])
        self.cb_status_filter.setMinimumWidth(180)
        self.cb_status_filter.setFixedHeight(38)
        self.cb_status_filter.currentIndexChanged.connect(self.load_debtors_table)
        f_layout.addLayout(make_filter_col("Statut de Créance", self.cb_status_filter))

        # 3. Minimum Debt Threshold
        self.spin_min_debt = QDoubleSpinBox()
        self.spin_min_debt.setStyleSheet(filter_input_style)
        self.spin_min_debt.setRange(0.0, 99999999.0)
        self.spin_min_debt.setSingleStep(1000.0)
        self.spin_min_debt.setDecimals(2)
        self.spin_min_debt.setSuffix(" DA")
        self.spin_min_debt.setValue(0.0)
        self.spin_min_debt.setMinimumWidth(130)
        self.spin_min_debt.setFixedHeight(38)
        self.spin_min_debt.valueChanged.connect(self.load_debtors_table)
        f_layout.addLayout(make_filter_col("Seuil Minimum", self.spin_min_debt))

        f_layout.addStretch(1)

        # Buttons col (aligned with input height)
        v_btn = QVBoxLayout()
        v_btn.setContentsMargins(0, 0, 0, 0)
        v_btn.setSpacing(4)
        lbl_act = QLabel("Actions")
        lbl_act.setStyleSheet("font-size: 11px; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.5px;")
        v_btn.addWidget(lbl_act)

        h_btn_actions = QHBoxLayout()
        h_btn_actions.setContentsMargins(0, 0, 0, 0)
        h_btn_actions.setSpacing(8)

        btn_refresh = QPushButton("Actualiser")
        btn_refresh.setIcon(get_duotone_icon("refresh_white", 16))
        btn_refresh.setIconSize(QSize(16, 16))
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setFixedHeight(38)
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #0E7471;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0A5C59;
            }
            QPushButton:pressed {
                background-color: #084846;
            }
        """)
        btn_refresh.clicked.connect(self.refresh_all)
        h_btn_actions.addWidget(btn_refresh)

        btn_export = QPushButton("Exporter CSV")
        btn_export.setIcon(get_duotone_icon("export", 16))
        btn_export.setIconSize(QSize(16, 16))
        btn_export.setCursor(Qt.PointingHandCursor)
        btn_export.setFixedHeight(38)
        btn_export.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #0E7471;
                border: 1.5px solid #0E7471;
                border-radius: 6px;
                padding: 0 16px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #E6F4F1;
                border-color: #0A5C59;
                color: #0A5C59;
            }
            QPushButton:pressed {
                background-color: #CCEBE5;
            }
        """)
        btn_export.clicked.connect(self.export_csv)
        h_btn_actions.addWidget(btn_export)

        v_btn.addLayout(h_btn_actions)
        f_layout.addLayout(v_btn)

        parent_layout.addWidget(filter_frame)

    def refresh_all(self):
        """Recharge l'intégralité des données : KPIs, clients débiteurs et détail."""
        self.load_kpis()
        self._reload_client_combo_list()
        self.load_debtors_table()

    def load_kpis(self):
        try:
            analytics = self.data_manager.clients.get_debts_analytics()
            total_rec = analytics.get('total_receivables', 0.0)
            overdue_rec = analytics.get('overdue_receivables', 0.0)
            debtor_cnt = analytics.get('debtor_clients_count', 0)
            rec_month = analytics.get('recovered_this_month', 0.0)

            self.lbl_kpi_total_receivables.setText(f"{format_money(total_rec)} DA")
            self.lbl_kpi_overdue_receivables.setText(f"{format_money(overdue_rec)} DA")
            if overdue_rec > 0.009:
                self.lbl_kpi_overdue_receivables.setStyleSheet("font-size: 13px; font-weight: 800; color: #DC2626; border: none; background: transparent;")
            else:
                self.lbl_kpi_overdue_receivables.setStyleSheet("font-size: 13px; font-weight: 800; color: #0F172A; border: none; background: transparent;")

            self.lbl_kpi_debtor_count.setText(f"{debtor_cnt} client(s)")
            self.lbl_kpi_month_recovered.setText(f"{format_money(rec_month)} DA")
        except Exception as e:
            logging.error(f"Error loading debts KPIs: {e}")

    def _reload_client_combo_list(self):
        try:
            clients = self.data_manager.clients.get_all_clients()
            self.cb_client_filter.set_clients(clients)
        except Exception as e:
            logging.error(f"Error reloading clients combo list: {e}")

    def load_debtors_table(self):
        try:
            min_debt = self.spin_min_debt.value()
            filter_status = self.cb_status_filter.currentText()
            client_id = self.cb_client_filter.get_selected_client_id()

            summary = self.data_manager.clients.get_debtor_clients_summary(
                min_debt=min_debt,
                filter_status=filter_status
            )

            if client_id:
                summary = [c for c in summary if c.get('Client_ID') == client_id]

            self.clients_summary = summary
            self.table_clients.setSortingEnabled(False)
            self.table_clients.setRowCount(0)

            for row_idx, c in enumerate(summary):
                self.table_clients.insertRow(row_idx)

                # 0: ID
                c_id = c.get('Client_ID')
                it_id = QTableWidgetItem(str(c_id))
                it_id.setData(Qt.UserRole, c)
                self.table_clients.setItem(row_idx, 0, it_id)

                # 1: Nom du Client
                it_name = QTableWidgetItem(str(c.get('Client_Name') or ''))
                it_name.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.table_clients.setItem(row_idx, 1, it_name)

                # 2: Téléphone
                self.table_clients.setItem(row_idx, 2, QTableWidgetItem(str(c.get('Phone') or '-')))

                # 3: Plafond Crédit
                limit = float(c.get('Credit_Limit') or 0.0)
                it_limit = QTableWidgetItem(f"{format_money(limit)} DA" if limit > 0 else "Illimité")
                it_limit.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table_clients.setItem(row_idx, 3, it_limit)

                # 4: Total Facturé
                invoiced = float(c.get('total_invoiced') or 0.0)
                it_inv = QTableWidgetItem(f"{format_money(invoiced)} DA")
                it_inv.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table_clients.setItem(row_idx, 4, it_inv)

                # 5: Total Encaissé
                paid = float(c.get('total_paid') or 0.0)
                it_paid = QTableWidgetItem(f"{format_money(paid)} DA")
                it_paid.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table_clients.setItem(row_idx, 5, it_paid)

                # 6: Solde Dû Actuel
                bal = float(c.get('Current_Balance') or 0.0)
                it_bal = QTableWidgetItem(f"{format_money(bal)} DA")
                it_bal.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                it_bal.setFont(QFont("Segoe UI", 9, QFont.Bold))
                if bal > (limit if limit > 0 else 0) and bal > 0:
                    it_bal.setForeground(QBrush(QColor("#DC2626")))
                    it_bal.setBackground(QBrush(QColor("#FEE2E2")))
                elif bal > 0:
                    it_bal.setForeground(QBrush(QColor("#D97706")))
                else:
                    it_bal.setForeground(QBrush(QColor("#16A34A")))
                self.table_clients.setItem(row_idx, 6, it_bal)

                # 7: Dernier Règlement
                last_pay = str(c.get('Last_Payment_Date') or '-')
                it_pay = QTableWidgetItem(last_pay)
                it_pay.setTextAlignment(Qt.AlignCenter)
                self.table_clients.setItem(row_idx, 7, it_pay)

                # 8: Statut / Badge
                badge = c.get('Status_Badge', 'Normal')
                it_badge = QTableWidgetItem(badge)
                it_badge.setTextAlignment(Qt.AlignCenter)
                it_badge.setFont(QFont("Segoe UI", 8, QFont.Bold))
                if badge == "Plafond Dépassé":
                    it_badge.setBackground(QBrush(QColor("#FEE2E2")))
                    it_badge.setForeground(QBrush(QColor("#DC2626")))
                elif badge == "Alerte Retard":
                    it_badge.setBackground(QBrush(QColor("#FEF3C7")))
                    it_badge.setForeground(QBrush(QColor("#D97706")))
                elif badge == "Normal":
                    it_badge.setBackground(QBrush(QColor("#DCFCE7")))
                    it_badge.setForeground(QBrush(QColor("#16A34A")))
                else:
                    it_badge.setBackground(QBrush(QColor("#F1F5F9")))
                    it_badge.setForeground(QBrush(QColor("#475569")))
                self.table_clients.setItem(row_idx, 8, it_badge)

                # 9: Actions container (elegant 28px mini buttons with crisp borders)
                act_container = QWidget()
                act_container.setStyleSheet("background: transparent; border: none;")
                act_layout = QHBoxLayout(act_container)
                act_layout.setContentsMargins(4, 2, 4, 2)
                act_layout.setSpacing(6)
                act_layout.setAlignment(Qt.AlignCenter)

                btn_pay = QPushButton("Solder")
                btn_pay.setIcon(get_duotone_icon("payment_white", 12))
                btn_pay.setIconSize(QSize(12, 12))
                btn_pay.setCursor(Qt.PointingHandCursor)
                btn_pay.setMinimumWidth(84)
                btn_pay.setFixedHeight(28)
                btn_pay.setStyleSheet("""
                    QPushButton {
                        background-color: #0E7471;
                        color: #FFFFFF;
                        font-size: 11px;
                        font-weight: 700;
                        border: 1px solid #0E7471;
                        border-radius: 4px;
                        padding: 3px 8px;
                    }
                    QPushButton:hover { background-color: #0A5C59; border-color: #0A5C59; }
                    QPushButton:pressed { background-color: #084846; }
                """)
                btn_pay.clicked.connect(lambda _, client_row=c: self._open_global_payment_dialog(client_row))
                act_layout.addWidget(btn_pay)

                btn_stmt = QPushButton("Relevé")
                btn_stmt.setIcon(get_duotone_icon("statement", 12))
                btn_stmt.setIconSize(QSize(12, 12))
                btn_stmt.setCursor(Qt.PointingHandCursor)
                btn_stmt.setMinimumWidth(84)
                btn_stmt.setFixedHeight(28)
                btn_stmt.setStyleSheet("""
                    QPushButton {
                        background-color: #FFFFFF;
                        color: #0E7471;
                        font-size: 11px;
                        font-weight: 700;
                        border: 1px solid #DDE3EA;
                        border-radius: 4px;
                        padding: 3px 8px;
                    }
                    QPushButton:hover { background-color: #E6F4F1; border-color: #0E7471; }
                    QPushButton:pressed { background-color: #CCEBE5; }
                """)
                btn_stmt.clicked.connect(lambda _, client_row=c: self._open_client_statement_dialog(client_row))
                act_layout.addWidget(btn_stmt)

                self.table_clients.setCellWidget(row_idx, 9, act_container)

            self.table_clients.setSortingEnabled(True)

            # Re-select previously selected or first
            if summary:
                self.table_clients.selectRow(0)
            else:
                self._clear_detail_table()

        except Exception as e:
            logging.error(f"Error loading debtors table: {e}", exc_info=True)

    def _on_client_filter_changed(self, client_id):
        self.load_debtors_table()

    def _on_client_selection_changed(self):
        row = self.table_clients.currentRow()
        if row < 0:
            self._clear_detail_table()
            return

        it = self.table_clients.item(row, 0)
        if not it:
            self._clear_detail_table()
            return

        client_data = it.data(Qt.UserRole)
        if not client_data:
            self._clear_detail_table()
            return

        self.selected_client_id = client_data.get('Client_ID')
        self._load_detail_invoices(client_data)

    def _clear_detail_table(self):
        self.selected_client_id = None
        self.lbl_detail_title.setText("Factures & Créances Impayées : (Sélectionnez un client)")
        self.btn_detail_global_pay.setEnabled(False)
        self.btn_detail_statement.setEnabled(False)
        self.table_invoices.setRowCount(0)
        self.lbl_empty_icon_container.setStyleSheet("background-color: #E6F4F1; border: 1px solid #BCE3DC; border-radius: 27px;")
        self.lbl_empty_icon.setPixmap(get_duotone_icon("client_select", 32).pixmap(32, 32))
        self.lbl_empty_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #1E293B;")
        self.lbl_empty_title.setText("Sélectionnez un client")
        self.lbl_empty_desc.setText("Cliquez sur un client dans la liste ci-dessus pour afficher ses factures impayées.")
        self.detail_stack.setCurrentIndex(1)

    def _load_detail_invoices(self, client_data):
        c_id = client_data.get('Client_ID')
        c_name = client_data.get('Client_Name') or f"Client #{c_id}"
        bal = float(client_data.get('Current_Balance') or 0.0)

        self.lbl_detail_title.setText(f"Factures & Créances Impayées : {c_name} (Solde Total : {format_money(bal)} DA)")
        self.btn_detail_global_pay.setEnabled(True)
        self.btn_detail_statement.setEnabled(True)

        try:
            invoices = self.data_manager.clients.get_client_unpaid_invoices(c_id)
            if not invoices:
                self.table_invoices.setRowCount(0)
                self.lbl_empty_icon_container.setStyleSheet("background-color: #DCFCE7; border: 1px solid #BBF7D0; border-radius: 27px;")
                self.lbl_empty_icon.setPixmap(get_duotone_icon("success_circle", 32).pixmap(32, 32))
                self.lbl_empty_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #166534;")
                self.lbl_empty_title.setText("Aucune créance impayée pour ce client")
                self.lbl_empty_desc.setText(f"Toutes les factures de « {c_name} » sont entièrement soldées. La situation comptable est parfaitement à jour.")
                self.detail_stack.setCurrentIndex(1)
                return

            self.detail_stack.setCurrentIndex(0)
            self.table_invoices.setRowCount(0)

            for r_idx, inv in enumerate(invoices):
                self.table_invoices.insertRow(r_idx)

                # 0: Facture N°
                inv_no = inv.get('Invoice_No') or f"#{inv.get('Invoice_ID')}"
                it_no = QTableWidgetItem(inv_no)
                it_no.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.table_invoices.setItem(r_idx, 0, it_no)

                # 1: Date
                inv_date = str(inv.get('Invoice_Date') or '-')[:10]
                it_date = QTableWidgetItem(inv_date)
                it_date.setTextAlignment(Qt.AlignCenter)
                self.table_invoices.setItem(r_idx, 1, it_date)

                # 2: Date d'Échéance
                due_date = str(inv.get('Due_Date') or '-')[:10]
                it_due = QTableWidgetItem(due_date)
                it_due.setTextAlignment(Qt.AlignCenter)
                self.table_invoices.setItem(r_idx, 2, it_due)

                # 3: Retard (Jours)
                days = inv.get('Days_Overdue', 0)
                is_overdue = inv.get('Is_Overdue', False)
                it_retard = QTableWidgetItem(f"+{days} j" if days > 0 else "0 j")
                it_retard.setTextAlignment(Qt.AlignCenter)
                if is_overdue:
                    it_retard.setForeground(QBrush(QColor("#DC2626")))
                    it_retard.setBackground(QBrush(QColor("#FEE2E2")))
                    it_retard.setFont(QFont("Segoe UI", 9, QFont.Bold))
                else:
                    it_retard.setForeground(QBrush(QColor("#0284C7")))
                self.table_invoices.setItem(r_idx, 3, it_retard)

                # 4: Total TTC
                ttc = float(inv.get('Total_Amount_TTC') or 0.0)
                it_ttc = QTableWidgetItem(f"{format_money(ttc)} DA")
                it_ttc.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table_invoices.setItem(r_idx, 4, it_ttc)

                # 5: Déjà Payé
                paid = float(inv.get('Paid_Amount') or 0.0)
                it_paid = QTableWidgetItem(f"{format_money(paid)} DA")
                it_paid.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table_invoices.setItem(r_idx, 5, it_paid)

                # 6: Reste à Payer
                rem = float(inv.get('Remaining_Balance') or (ttc - paid))
                it_rem = QTableWidgetItem(f"{format_money(rem)} DA")
                it_rem.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                it_rem.setFont(QFont("Segoe UI", 9, QFont.Bold))
                it_rem.setForeground(QBrush(QColor("#DC2626")))
                self.table_invoices.setItem(r_idx, 6, it_rem)

                # 7: Statut
                it_status = QTableWidgetItem(str(inv.get('Status') or 'Validated'))
                it_status.setTextAlignment(Qt.AlignCenter)
                self.table_invoices.setItem(r_idx, 7, it_status)

                # 8: Actions Container (elegant 28px mini buttons with crisp borders)
                act_box = QWidget()
                act_box.setStyleSheet("background: transparent; border: none;")
                act_lay = QHBoxLayout(act_box)
                act_lay.setContentsMargins(4, 2, 4, 2)
                act_lay.setSpacing(6)
                act_lay.setAlignment(Qt.AlignCenter)

                btn_pay_inv = QPushButton("Encaisser")
                btn_pay_inv.setIcon(get_duotone_icon("payment_white", 12))
                btn_pay_inv.setIconSize(QSize(12, 12))
                btn_pay_inv.setCursor(Qt.PointingHandCursor)
                btn_pay_inv.setMinimumWidth(84)
                btn_pay_inv.setFixedHeight(28)
                btn_pay_inv.setStyleSheet("""
                    QPushButton {
                        background-color: #0E7471;
                        color: #FFFFFF;
                        font-weight: 700;
                        font-size: 11px;
                        border: 1px solid #0E7471;
                        border-radius: 4px;
                        padding: 3px 8px;
                    }
                    QPushButton:hover { background-color: #0A5C59; border-color: #0A5C59; }
                    QPushButton:pressed { background-color: #084846; }
                """)
                # Prepare invoice data dict for InvoicePaymentDialog
                inv_dict = {
                    'Invoice_ID': inv.get('Invoice_ID'),
                    'Invoice_No': inv_no,
                    'Client_ID': c_id,
                    'Client_Name': c_name,
                    'Total_Amount_TTC': ttc,
                    'Paid_Amount': paid,
                    'Invoice_Date': inv_date,
                    'Due_Date': due_date
                }
                btn_pay_inv.clicked.connect(lambda _, iv=inv_dict: self._open_invoice_payment(iv))
                act_lay.addWidget(btn_pay_inv)

                btn_print_inv = QPushButton("Imprimer")
                btn_print_inv.setIcon(get_duotone_icon("print", 12))
                btn_print_inv.setIconSize(QSize(12, 12))
                btn_print_inv.setCursor(Qt.PointingHandCursor)
                btn_print_inv.setMinimumWidth(84)
                btn_print_inv.setFixedHeight(28)
                btn_print_inv.setStyleSheet("""
                    QPushButton {
                        background-color: #FFFFFF;
                        color: #334155;
                        font-weight: 700;
                        font-size: 11px;
                        border: 1px solid #DDE3EA;
                        border-radius: 4px;
                        padding: 3px 8px;
                    }
                    QPushButton:hover { background-color: #F1F5F9; border-color: #CBD5E1; }
                    QPushButton:pressed { background-color: #E2E8F0; }
                """)
                btn_print_inv.clicked.connect(lambda _, iv=inv_dict: self._print_invoice(iv))
                act_lay.addWidget(btn_print_inv)

                self.table_invoices.setCellWidget(r_idx, 8, act_box)


        except Exception as e:
            logging.error(f"Error loading detail invoices: {e}", exc_info=True)

    def _open_global_payment_dialog(self, client_row=None):
        if not client_row:
            row = self.table_clients.currentRow()
            if row >= 0 and self.table_clients.item(row, 0):
                client_row = self.table_clients.item(row, 0).data(Qt.UserRole)

        if not client_row:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner un client.")
            return

        dlg = GlobalPaymentDialog(self.data_manager, client_row, self)
        if dlg.exec() == QDialog.Accepted:
            self.refresh_all()

    def _open_client_statement_dialog(self, client_row=None):
        if not client_row:
            row = self.table_clients.currentRow()
            if row >= 0 and self.table_clients.item(row, 0):
                client_row = self.table_clients.item(row, 0).data(Qt.UserRole)

        if not client_row:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner un client.")
            return

        c_id = client_row.get('Client_ID')
        dlg = ClientStatementDialog(self.data_manager, c_id, self)
        dlg.exec()

    def _open_invoice_payment(self, invoice_data):
        dlg = InvoicePaymentDialog(self.data_manager, invoice_data, self)
        if dlg.exec() == QDialog.Accepted:
            self.refresh_all()

    def _print_invoice(self, invoice_data):
        try:
            export_invoice_to_pdf(self.data_manager, invoice_data, self)
        except Exception as e:
            logging.error(f"Error printing invoice: {e}")
            QMessageBox.critical(self, "Erreur", f"Échec de l'impression de la facture : {e}")

    def _audit_client(self, client_row):
        c_id = client_row.get('Client_ID')
        audit_res = self.data_manager.clients.audit_client_debt_balance(c_id)
        dlg = ClientDebtAuditDialog(audit_res, self)
        dlg.exec()

    def _show_client_context_menu(self, pos):
        item = self.table_clients.itemAt(pos)
        if not item:
            return
        row = item.row()
        id_item = self.table_clients.item(row, 0)
        if not id_item:
            return
        client_data = id_item.data(Qt.UserRole)
        if not client_data:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
                color: #0F172A;
            }
            QMenu::item:selected {
                background-color: #0E7471;
                color: white;
            }
        """)

        act_pay = menu.addAction(get_duotone_icon("payment", 16), "Règlement Global / Acompte")
        act_pay.triggered.connect(lambda: self._open_global_payment_dialog(client_data))

        act_stmt = menu.addAction(get_duotone_icon("statement", 16), "Relevé de Compte Détaillé")
        act_stmt.triggered.connect(lambda: self._open_client_statement_dialog(client_data))

        act_audit = menu.addAction(get_duotone_icon("audit", 16), "Audit Intégrité Comptable")
        act_audit.triggered.connect(lambda: self._audit_client(client_data))

        menu.exec(self.table_clients.viewport().mapToGlobal(pos))

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exporter les Créances Clients", "creances_clients.csv", "CSV (*.csv)")
        if not path:
            return
        headers = [
            "ID Client", "Nom du Client", "Telephone", "Plafond Credit (DA)",
            "Total Facture (DA)", "Total Encaisse (DA)", "Solde Du Actuel (DA)",
            "Dernier Reglement", "Statut"
        ]
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle)
                writer.writerow(headers)
                for c in self.clients_summary:
                    writer.writerow([
                        c.get("Client_ID"),
                        c.get("Client_Name") or "-",
                        c.get("Phone") or "-",
                        c.get("Credit_Limit") or 0.0,
                        c.get("total_invoiced") or 0.0,
                        c.get("total_paid") or 0.0,
                        c.get("Current_Balance") or 0.0,
                        c.get("Last_Payment_Date") or "-",
                        c.get("Status_Badge") or "-"
                    ])
            QMessageBox.information(self, "Export", "Données des créances exportées avec succès.")
        except OSError as exc:
            QMessageBox.warning(self, "Export", f"Échec de l'exportation CSV : {exc}")
