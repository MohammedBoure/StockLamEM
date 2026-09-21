# ui/widgets/sales/invoice_payment_dialog.py

import logging
from datetime import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QDateEdit, QDoubleSpinBox, QLineEdit, QPushButton,
    QFrame, QMessageBox, QFormLayout
)
from PySide6.QtCore import Qt, QDate, QSize
from PySide6.QtGui import QColor

from ui.formatting import format_money
from ui.icons import get_duotone_icon


class InvoicePaymentDialog(QDialog):
    """
    Dialogue d'encaissement et de règlement pour une facture de vente (POS ou Vente en Gros).
    Enregistre le règlement dans Client_Payments et met à jour le statut de la facture.
    """

    def __init__(self, data_manager, invoice_data, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.invoice_data = invoice_data
        
        self.invoice_id = invoice_data.get('Invoice_ID')
        self.client_id = invoice_data.get('Client_ID')
        self.total_ttc = float(invoice_data.get('Total_Amount_TTC') or 0.0)
        self.paid_amount = float(invoice_data.get('Paid_Amount') or 0.0)
        self.remaining_balance = max(0.0, self.total_ttc - self.paid_amount)
        
        doc_ref = invoice_data.get('Invoice_No') or f"#{self.invoice_id}"
        self.setWindowTitle(f"Encaisser Paiement - Facture {doc_ref}")
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
        self.resize(520, 520)
        self.setMinimumSize(480, 480)
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
        lbl_title = QLabel("Enregistrement d'un Règlement de Facture")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #0E7471; border: none; background: transparent;")
        layout.addWidget(lbl_title)

        # 1. Section Détails de la Facture
        lbl_sec_invoice = QLabel("DÉTAILS DE LA FACTURE")
        lbl_sec_invoice.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748B; letter-spacing: 0.5px; border: none; background: transparent; margin-top: 2px;")
        layout.addWidget(lbl_sec_invoice)

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

        def make_tag(t):
            l = QLabel(t)
            l.setStyleSheet("font-size: 12px; font-weight: 600; color: #64748B; border: none; background: transparent;")
            return l

        client_name = self.invoice_data.get('Client_Name') or "Client Comptoir"
        doc_ref = self.invoice_data.get('Invoice_No') or f"#{self.invoice_id}"
        inv_date = str(self.invoice_data.get('Invoice_Date') or self.invoice_data.get('Event_Date') or "-")
        due_date = str(self.invoice_data.get('Due_Date') or "-")

        lbl_client = QLabel(client_name)
        lbl_client.setStyleSheet("font-size: 13px; font-weight: 700; color: #1F2937; border: none; background: transparent;")
        summary_layout.addRow(make_tag("Client :"), lbl_client)

        lbl_doc = QLabel(doc_ref)
        lbl_doc.setStyleSheet("font-size: 12px; font-weight: 700; color: #0E7471; border: none; background: transparent;")
        summary_layout.addRow(make_tag("Facture N° :"), lbl_doc)

        lbl_dates = QLabel(f"{inv_date}  (Échéance : {due_date})")
        lbl_dates.setStyleSheet("font-size: 12px; color: #475569; border: none; background: transparent;")
        summary_layout.addRow(make_tag("Date / Échéance :"), lbl_dates)

        lbl_total = QLabel(f"{format_money(self.total_ttc)} DA  (Déjà réglé : {format_money(self.paid_amount)} DA)")
        lbl_total.setStyleSheet("font-size: 12px; font-weight: 600; color: #334155; border: none; background: transparent;")
        summary_layout.addRow(make_tag("Montant Facturé :"), lbl_total)

        lbl_balance = QLabel(f"{format_money(self.remaining_balance)} DA")
        lbl_balance.setStyleSheet("font-size: 14px; font-weight: 800; color: #DC2626; border: none; background: transparent;" if self.remaining_balance > 0 else "font-size: 14px; font-weight: 800; color: #16A34A; border: none; background: transparent;")
        summary_layout.addRow(make_tag("Reste à Payer :"), lbl_balance)

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

        # Date de paiement
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

        # Montant avec bouton Solder
        amt_container = QHBoxLayout()
        amt_container.setSpacing(8)

        self.spin_amount = QDoubleSpinBox()
        self.spin_amount.setRange(0.01, 999999999.0)
        self.spin_amount.setDecimals(2)
        self.spin_amount.setSingleStep(100.0)
        self.spin_amount.setSuffix(" DA")
        initial_val = self.remaining_balance if self.remaining_balance > 0 else self.total_ttc
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

        btn_solder = QPushButton("Solder")
        btn_solder.setCursor(Qt.PointingHandCursor)
        btn_solder.setFixedHeight(38)
        btn_solder.setStyleSheet("""
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
        btn_solder.clicked.connect(lambda: self.spin_amount.setValue(max(0.01, self.remaining_balance)))
        amt_container.addWidget(btn_solder)

        form_layout.addRow(make_form_label("Montant versé :"), amt_container)

        # Mode de paiement
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

        # Reference
        self.edit_ref = QLineEdit()
        self.edit_ref.setPlaceholderText("Ex: N° Chèque, Référence virement...")
        self.edit_ref.setFixedHeight(38)
        self.edit_ref.setStyleSheet("""
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
        """)
        form_layout.addRow(make_form_label("Référence / N° Pièce :"), self.edit_ref)

        # Notes
        self.edit_notes = QLineEdit()
        self.edit_notes.setPlaceholderText("Remarques ou observations...")
        self.edit_notes.setFixedHeight(38)
        self.edit_notes.setStyleSheet("""
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
        """)
        form_layout.addRow(make_form_label("Observations :"), self.edit_notes)

        layout.addLayout(form_layout)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        btn_cancel = QPushButton("Annuler")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setFixedHeight(38)
        btn_cancel.setMinimumWidth(100)
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

        if not self.client_id:
            QMessageBox.warning(
                self, "Client non défini",
                "Cette facture n'est pas rattachée à un compte client spécifique.\n"
                "Le règlement direct est réservé aux clients enregistrés."
            )
            return

        pay_date = self.edit_date.date().toString("yyyy-MM-dd")
        method = self.cb_method.currentData()
        ref = self.edit_ref.text().strip() or None
        notes = self.edit_notes.text().strip() or None
        user_id = self._current_user_id()

        try:
            payment_id = self.data_manager.client_payments.add_payment(
                client_id=self.client_id,
                payment_date=pay_date,
                amount=amount,
                payment_method=method,
                reference=ref,
                notes=notes,
                invoice_id=self.invoice_id,
                user_id=user_id
            )

            if payment_id:
                QMessageBox.information(
                    self, "Succès",
                    f"Règlement de {format_money(amount)} DA enregistré avec succès (Réf: #{payment_id})."
                )
                self.accept()
            else:
                QMessageBox.critical(self, "Erreur", "Échec de l'enregistrement du règlement en base de données.")
        except Exception as e:
            logging.error(f"Error saving invoice payment: {e}", exc_info=True)
            QMessageBox.critical(self, "Erreur", f"Erreur lors de l'enregistrement: {e}")
