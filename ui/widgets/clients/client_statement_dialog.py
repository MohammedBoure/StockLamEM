# ui/widgets/master_data/client_statement_dialog.py

import os
import json
import logging
from datetime import datetime, date, timedelta
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDateEdit,
    QComboBox, QFrame, QMessageBox, QFileDialog, QSizePolicy,
    QWidget, QFormLayout
)
from PySide6.QtCore import Qt, QDate, QSize
from PySide6.QtGui import QFont, QColor, QBrush
from ui.formatting import format_money
from ui.icons import get_duotone_icon
from branding import get_logo_path

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


class TransactionDetailsDialog(QDialog):
    """
    Dialogue Non-Modal (Modalless) de consultation détaillée d'une opération financière.
    Permet à l'opérateur d'ouvrir plusieurs fenêtres simultanément, de les déplacer
    sur l'écran, et de consulter l'intégralité des lignes d'articles ou données de règlement
    sans bloquer la fenêtre principale du relevé de compte.
    """

    def __init__(self, data_manager, transaction: dict, client_info: dict = None, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.transaction = transaction or {}
        self.client_info = client_info or {}

        self.ref = self.transaction.get('reference') or 'Détail Opération'
        self.setWindowTitle(f"Détails de l'opération - {self.ref}")

        # Modalless (Non-modal): does NOT block parent, supports multiple simultaneous instances
        self.setModal(False)
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowMinMaxButtonsHint)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
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
        self.resize(800, 520)
        self.setMinimumSize(720, 420)
        self._init_ui()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(12)

        # 1. Header Bar
        header_frame = QFrame()
        header_frame.setStyleSheet("""
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
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(14, 10, 14, 10)
        h_layout.setSpacing(12)

        v_head = QVBoxLayout()
        v_head.setSpacing(2)
        lbl_title = QLabel(f"Pièce : {self.ref}")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #0E7471;")
        client_name = self.client_info.get('Client_Name') or "Client"
        op_date = self.transaction.get('date', '-')
        lbl_sub = QLabel(f"Client : {client_name}   |   Date : {op_date}")
        lbl_sub.setStyleSheet("font-size: 12px; color: #64748B; font-weight: 600;")
        v_head.addWidget(lbl_title)
        v_head.addWidget(lbl_sub)
        h_layout.addLayout(v_head, 1)

        # Type Badge
        op_type = self.transaction.get('type', 'Opération')
        lbl_badge = QLabel(f"  {op_type}  ")
        lbl_badge.setFixedHeight(28)
        lbl_badge.setStyleSheet("""
            background-color: #E6F4F1;
            color: #0E7471;
            font-size: 12px;
            font-weight: 700;
            border-radius: 4px;
            border: 1px solid #BCE3DC;
        """)
        h_layout.addWidget(lbl_badge)

        root_layout.addWidget(header_frame)

        # 2. Financial Summary Card
        summary_frame = QFrame()
        summary_frame.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        sum_layout = QHBoxLayout(summary_frame)
        sum_layout.setContentsMargins(14, 10, 14, 10)
        sum_layout.setSpacing(14)

        debit = self.transaction.get('debit', 0.0)
        credit = self.transaction.get('credit', 0.0)
        raw_amt = self.transaction.get('raw_amount') or (debit if debit > 0 else credit)
        is_nb = self.transaction.get('is_non_binding', False)

        def make_sum_metric(title, val_str, val_color):
            v = QVBoxLayout()
            v.setSpacing(2)
            lbl_t = QLabel(title.upper())
            lbl_t.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748B; letter-spacing: 0.5px;")
            lbl_val = QLabel(val_str)
            lbl_val.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {val_color};")
            v.addWidget(lbl_t)
            v.addWidget(lbl_val)
            return v

        if is_nb:
            sum_layout.addLayout(make_sum_metric("Montant Indicatif", f"{format_money(raw_amt)} DA", "#64748B"))
            sum_layout.addLayout(make_sum_metric("Statut Comptable", "Hors Bilan (Proforma)", "#D97706"))
        elif debit > 0:
            sum_layout.addLayout(make_sum_metric("Montant Facturé (TTC)", f"{format_money(debit)} DA", "#0284C7"))
            sum_layout.addLayout(make_sum_metric("Solde après pièce", f"{format_money(self.transaction.get('balance', 0.0))} DA", "#DC2626"))
        elif credit > 0:
            sum_layout.addLayout(make_sum_metric("Montant Encaissé", f"{format_money(credit)} DA", "#16A34A"))
            sum_layout.addLayout(make_sum_metric("Solde après pièce", f"{format_money(self.transaction.get('balance', 0.0))} DA", "#16A34A"))

        note_txt = self.transaction.get('notes', '-')
        sum_layout.addLayout(make_sum_metric("Observations / Réf", note_txt if note_txt else "-", "#334155"))
        sum_layout.addStretch(1)

        root_layout.addWidget(summary_frame)

        # 3. Specific Body Content: Invoices, Payments, or Orders
        doc_cat = self.transaction.get('doc_category')
        ref = self.ref
        invoice_data = None
        if doc_cat == 'invoice' or ref.startswith(('FAC-', 'BL-', 'DEV-', 'BC-')):
            invoice_data = self._fetch_invoice()

        if invoice_data and invoice_data.get('details'):
            # Articles Table
            lbl_items_title = QLabel("LIGNES D'ARTICLES ET PRODUITS DE LA PIÈCE")
            lbl_items_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748B; letter-spacing: 0.5px; border: none; background: transparent; margin-top: 4px;")
            root_layout.addWidget(lbl_items_title)

            table_items = QTableWidget()
            i_cols = ["N°", "Désignation Produit", "N° Lot", "Péremption", "Qté", "Prix Unit. HT", "Remise %", "Total TTC"]
            table_items.setColumnCount(len(i_cols))
            table_items.setHorizontalHeaderLabels(i_cols)
            table_items.setAlternatingRowColors(True)
            table_items.setSelectionBehavior(QTableWidget.SelectRows)
            table_items.setEditTriggers(QTableWidget.NoEditTriggers)
            table_items.verticalHeader().setVisible(False)
            table_items.verticalHeader().setDefaultSectionSize(34)
            table_items.setShowGrid(True)
            table_items.setStyleSheet("""
                QTableWidget {
                    background-color: #FFFFFF;
                    border: 1px solid #DDE3EA;
                    border-radius: 6px;
                    gridline-color: #E2E8F0;
                    font-size: 12px;
                    color: #1F2937;
                    alternate-background-color: #F8FAFC;
                }
                QHeaderView::section {
                    background-color: #F8FAFC;
                    color: #1F2937;
                    font-weight: 700;
                    font-size: 11px;
                    border: none;
                    border-bottom: 2px solid #0E7471;
                    border-right: 1px solid #E2E8F0;
                    padding: 6px 8px;
                }
            """)
            i_header = table_items.horizontalHeader()
            i_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
            i_header.setSectionResizeMode(1, QHeaderView.Stretch)
            for c_idx in [2, 3, 4, 5, 6, 7]:
                i_header.setSectionResizeMode(c_idx, QHeaderView.ResizeToContents)

            details = invoice_data.get('details', [])
            table_items.setRowCount(len(details))
            for idx, item in enumerate(details):
                p_name = item.get('Product_Name') or "Produit"
                lot = item.get('Lot_Number') or "-"
                exp = str(item.get('Expiry_Date') or "-")[:10]
                qty = float(item.get('Quantity') or 0.0)
                pu = float(item.get('Unit_Price_HT') or item.get('Price_HT') or 0.0)
                rem = float(item.get('Discount_Percent') or item.get('Discount') or 0.0)
                ttc = float(item.get('Total_TTC') or item.get('Total_Amount_TTC') or item.get('Total_Price_HT') or 0.0)

                it_no = QTableWidgetItem(str(idx + 1))
                it_no.setTextAlignment(Qt.AlignCenter)
                table_items.setItem(idx, 0, it_no)

                it_p = QTableWidgetItem(p_name)
                it_p.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
                table_items.setItem(idx, 1, it_p)

                it_lot = QTableWidgetItem(lot)
                it_lot.setTextAlignment(Qt.AlignCenter)
                table_items.setItem(idx, 2, it_lot)

                it_exp = QTableWidgetItem(exp)
                it_exp.setTextAlignment(Qt.AlignCenter)
                table_items.setItem(idx, 3, it_exp)

                it_qty = QTableWidgetItem(f"{qty:g}")
                it_qty.setTextAlignment(Qt.AlignCenter)
                it_qty.setFont(QFont("Segoe UI", 9, QFont.Bold))
                table_items.setItem(idx, 4, it_qty)

                it_pu = QTableWidgetItem(f"{format_money(pu)} DA")
                it_pu.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                table_items.setItem(idx, 5, it_pu)

                it_rem = QTableWidgetItem(f"{rem:g}%" if rem > 0 else "-")
                it_rem.setTextAlignment(Qt.AlignCenter)
                table_items.setItem(idx, 6, it_rem)

                it_ttc = QTableWidgetItem(f"{format_money(ttc)} DA")
                it_ttc.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                it_ttc.setFont(QFont("Segoe UI", 9, QFont.Bold))
                it_ttc.setForeground(QBrush(QColor("#0E7471")))
                table_items.setItem(idx, 7, it_ttc)

            root_layout.addWidget(table_items, 1)

        else:
            # Payment or General Operation Details Card
            detail_box = QFrame()
            detail_box.setStyleSheet("""
                QFrame {
                    background-color: #FFFFFF;
                    border: 1px solid #DDE3EA;
                    border-radius: 6px;
                }
                QLabel {
                    border: none;
                    background: transparent;
                }
            """)
            d_lay = QFormLayout(detail_box)
            d_lay.setContentsMargins(18, 14, 18, 14)
            d_lay.setSpacing(10)

            def make_dtag(t):
                lbl = QLabel(t)
                lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #64748B;")
                return lbl

            d_lay.addRow(make_dtag("Type d'opération :"), QLabel(f"<b>{self.transaction.get('type', '-')}</b>"))
            d_lay.addRow(make_dtag("Référence comptable :"), QLabel(f"<b>{self.ref}</b>"))
            d_lay.addRow(make_dtag("Date d'enregistrement :"), QLabel(str(self.transaction.get('date', '-'))))

            amt_val = credit if credit > 0 else debit
            lbl_amt = QLabel(f"{format_money(amt_val)} DA")
            lbl_amt.setStyleSheet("font-size: 15px; font-weight: 800; color: #16A34A;" if credit > 0 else "font-size: 15px; font-weight: 800; color: #0284C7;")
            d_lay.addRow(make_dtag("Montant de la transaction :"), lbl_amt)

            d_lay.addRow(make_dtag("Détails / Notes :"), QLabel(str(self.transaction.get('notes') or '-')))
            root_layout.addWidget(detail_box, 1)

        # 4. Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        if invoice_data:
            btn_print_inv = QPushButton("🖨️ Imprimer la Facture")
            btn_print_inv.setIcon(get_duotone_icon("print", 14))
            btn_print_inv.setIconSize(QSize(14, 14))
            btn_print_inv.setCursor(Qt.PointingHandCursor)
            btn_print_inv.setFixedHeight(36)
            btn_print_inv.setStyleSheet("""
                QPushButton {
                    background-color: #0E7471;
                    color: #FFFFFF;
                    font-weight: 700;
                    padding: 0 16px;
                    border-radius: 6px;
                    border: none;
                    font-size: 12px;
                }
                QPushButton:hover { background-color: #0A5C59; }
                QPushButton:pressed { background-color: #084846; }
            """)
            btn_print_inv.clicked.connect(lambda: self._print_invoice(invoice_data))
            btn_layout.addWidget(btn_print_inv)

        btn_layout.addStretch(1)

        btn_close = QPushButton("Fermer")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setFixedHeight(36)
        btn_close.setMinimumWidth(100)
        btn_close.setStyleSheet("""
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
        btn_close.clicked.connect(self.close)
        btn_layout.addWidget(btn_close)

        root_layout.addLayout(btn_layout)

    def _fetch_invoice(self):
        doc_id = self.transaction.get('doc_id')
        ref = self.ref
        try:
            if doc_id:
                return self.data_manager.sales.get_invoice_by_id(doc_id)
            with self.data_manager.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT Invoice_ID FROM Sales_Invoices WHERE Invoice_No = %s", (ref,))
                row = cursor.fetchone()
                if row:
                    return self.data_manager.sales.get_invoice_by_id(row['Invoice_ID'])
        except Exception as e:
            logging.error(f"Error fetching invoice details for {ref}: {e}")
        return None

    def _print_invoice(self, inv_data):
        try:
            if not HAS_REPORTLAB:
                QMessageBox.warning(self, "Erreur", "La bibliothèque 'reportlab' est manquante.")
                return
            invoice_id = inv_data.get('Invoice_ID')
            details_data = self.data_manager.sales.get_invoice_details_with_profit(invoice_id) if invoice_id else []
            client_name = inv_data.get('Client_Name') or self.client_info.get('Client_Name') or 'Client'
            raw_date = str(inv_data.get('Invoice_Date', ''))
            formatted_ref = inv_data.get('Invoice_No') or f"#{invoice_id}"
            safe_ref = "".join(c for c in str(formatted_ref) if c.isalnum() or c in ('-', '_'))
            default_name = f"Facture_{safe_ref}.pdf"
            path, _ = QFileDialog.getSaveFileName(self, "Enregistrer PDF", default_name, "PDF Files (*.pdf)")
            if not path:
                return
            doc = SimpleDocTemplate(path, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
            styles = getSampleStyleSheet()
            elements = [
                Paragraph(f"<b>FACTURE N°: {formatted_ref}</b>", styles["Title"]),
                Paragraph(f"<b>Client :</b> {client_name} &nbsp;&nbsp;&nbsp; <b>Date :</b> {raw_date}", styles["Normal"]),
                Spacer(1, 0.5 * cm),
            ]
            table_data = [["Désignation", "Qté", "Prix U. HT", "Total TTC"]]
            for item in details_data:
                table_data.append([
                    str(item.get('Product_Name', '-')),
                    str(item.get('Qty_Sold', 0)),
                    f"{float(item.get('Unit_Price_HT', 0)):,.2f}",
                    f"{float(item.get('Line_Total_TTC', 0)):,.2f}",
                ])
            t = Table(table_data, colWidths=[9.5 * cm, 2.0 * cm, 3.0 * cm, 3.5 * cm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0E7471")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ('PADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 0.4 * cm))
            tot_ttc = float(inv_data.get('Total_Amount_TTC', 0))
            elements.append(Paragraph(f"<b>TOTAL TTC : {tot_ttc:,.2f} DA</b>", styles["Heading3"]))
            doc.build(elements)
            if os.name == 'nt':
                os.startfile(path)
        except Exception as e:
            logging.error(f"Error printing invoice from details: {e}")


class ClientStatementDialog(QDialog):
    """
    Dialogue de Relevé de Compte Client (Customer Account Statement).
    Affiche l'historique financier complet (Factures, Règlements, Avoirs),
    calcule le solde initial, les mouvements et le solde progressif,
    et permet l'exportation PDF A4 formaté.
    """

    def __init__(self, data_manager, client_id: int, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.client_id = client_id
        self.client_manager = data_manager.clients
        self.ledger_data = {}
        self._open_detail_dialogs = []

        self.setWindowTitle("📄 Relevé de Compte Client - Grand Livre Auxiliaire")
        self.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        self.resize(1200, 780)
        self.setMinimumSize(950, 600)

        self.init_ui()
        self.apply_preset("this_month")

    def showEvent(self, event):
        super().showEvent(event)
        self.showMaximized()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # 1. Header Card (Nom du client & Coordonnées & Risque Crédit) - Clean open layout
        self.header_frame = QFrame()
        self.header_frame.setStyleSheet("""
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
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(14, 10, 14, 10)

        self.lbl_client_title = QLabel("Chargement du client...")
        self.lbl_client_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #0E7471;")
        header_layout.addWidget(self.lbl_client_title, 1)

        self.lbl_client_meta = QLabel("")
        self.lbl_client_meta.setStyleSheet("font-size: 12px; color: #475569; font-weight: 600;")
        header_layout.addWidget(self.lbl_client_meta)

        layout.addWidget(self.header_frame)

        # 2. Controls Toolbar (Dedicated Top Utility Bar with clean <label> texts)
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)

        lbl_p = QLabel("Période :")
        lbl_p.setStyleSheet("font-weight: 600; font-size: 12px; color: #475569; border: none; background: transparent;")
        filter_layout.addWidget(lbl_p)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems([
            "Ce mois",
            "Mois précédent",
            "Dernier trimestre",
            "30 derniers jours",
            "Cette année",
            "Tout l'historique",
            "Personnalisé"
        ])
        self.preset_combo.setFixedHeight(36)
        self.preset_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #DDE3EA;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 600;
                color: #1F2937;
                background-color: #FFFFFF;
            }
            QComboBox:focus { border: 1.5px solid #0E7471; }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 22px;
                border-left: 1px solid #DDE3EA;
                background-color: #F8FAFC;
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
            }
        """)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        filter_layout.addWidget(self.preset_combo)

        lbl_du = QLabel("Du :")
        lbl_du.setStyleSheet("font-weight: 600; font-size: 12px; color: #475569; border: none; background: transparent;")
        filter_layout.addWidget(lbl_du)

        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(QDate.currentDate().addMonths(-1))
        self.date_start.setFixedHeight(36)
        self.date_start.setStyleSheet("""
            QDateEdit {
                border: 1px solid #DDE3EA;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 600;
                color: #1F2937;
                background-color: #FFFFFF;
            }
            QDateEdit:focus { border: 1.5px solid #0E7471; }
        """)
        self.date_start.dateChanged.connect(self._on_date_changed)
        filter_layout.addWidget(self.date_start)

        lbl_au = QLabel("Au :")
        lbl_au.setStyleSheet("font-weight: 600; font-size: 12px; color: #475569; border: none; background: transparent;")
        filter_layout.addWidget(lbl_au)

        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDate(QDate.currentDate())
        self.date_end.setFixedHeight(36)
        self.date_end.setStyleSheet("""
            QDateEdit {
                border: 1px solid #DDE3EA;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 600;
                color: #1F2937;
                background-color: #FFFFFF;
            }
            QDateEdit:focus { border: 1.5px solid #0E7471; }
        """)
        self.date_end.dateChanged.connect(self._on_date_changed)
        filter_layout.addWidget(self.date_end)

        self.btn_refresh = QPushButton("Actualiser")
        self.btn_refresh.setIcon(get_duotone_icon("refresh", 14))
        self.btn_refresh.setIconSize(QSize(14, 14))
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setFixedHeight(36)
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #0E7471;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #0A5C59; }
            QPushButton:pressed { background-color: #084846; }
        """)
        self.btn_refresh.clicked.connect(self.load_ledger)
        filter_layout.addWidget(self.btn_refresh)

        filter_layout.addStretch(1)

        self.btn_print = QPushButton("Imprimer")
        self.btn_print.setIcon(get_duotone_icon("print", 14))
        self.btn_print.setIconSize(QSize(14, 14))
        self.btn_print.setCursor(Qt.PointingHandCursor)
        self.btn_print.setFixedHeight(36)
        self.btn_print.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #0E7471;
                border: 1.5px solid #0E7471;
                border-radius: 6px;
                padding: 0 16px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #E6F4F1; }
            QPushButton:pressed { background-color: #CCEBE5; }
        """)
        self.btn_print.clicked.connect(self.print_statement)
        filter_layout.addWidget(self.btn_print)

        self.btn_export_pdf = QPushButton("Exporter en PDF (A4)")
        self.btn_export_pdf.setIcon(get_duotone_icon("pdf", 14))
        self.btn_export_pdf.setIconSize(QSize(14, 14))
        self.btn_export_pdf.setCursor(Qt.PointingHandCursor)
        self.btn_export_pdf.setFixedHeight(36)
        self.btn_export_pdf.setStyleSheet("""
            QPushButton {
                background-color: #0E7471;
                color: #FFFFFF;
                font-weight: 700;
                padding: 0 18px;
                border: none;
                border-radius: 6px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #0A5C59; }
            QPushButton:pressed { background-color: #084846; }
        """)
        self.btn_export_pdf.clicked.connect(self.export_pdf)
        filter_layout.addWidget(self.btn_export_pdf)

        self.btn_top_close = QPushButton("✕ Fermer")
        self.btn_top_close.setCursor(Qt.PointingHandCursor)
        self.btn_top_close.setFixedHeight(36)
        self.btn_top_close.setStyleSheet("""
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
        self.btn_top_close.clicked.connect(self.accept)
        filter_layout.addWidget(self.btn_top_close)

        layout.addLayout(filter_layout)

        # 3. KPI Summary Cards (Flat, clean with strong contrast and smooth borders)
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(10)

        self.card_initial = self._create_kpi_card("Solde Antérieur", "0.00 DA", "#1E293B")
        self.card_debit = self._create_kpi_card("Total Débit (Factures & BL)", "0.00 DA", "#0284C7")
        self.card_credit = self._create_kpi_card("Total Crédit (Règlements)", "0.00 DA", "#16A34A")
        self.card_final = self._create_kpi_card("Nouveau Solde Dû", "0.00 DA", "#DC2626")

        kpi_layout.addWidget(self.card_initial)
        kpi_layout.addWidget(self.card_debit)
        kpi_layout.addWidget(self.card_credit)
        kpi_layout.addWidget(self.card_final)
        layout.addLayout(kpi_layout)

        # 4. Table du Grand Livre (Dense Data Table Spreadsheet)
        self.table = QTableWidget()
        cols = [
            "Date", "Type de Document", "Référence",
            "Débit (+)", "Crédit (-)", "Solde Progressif", "Notes", "Actions"
        ]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setShowGrid(True)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
                gridline-color: #E2E8F0;
                font-size: 12px;
                color: #1F2937;
                selection-background-color: #E6F4F1;
                selection-color: #1F2937;
                alternate-background-color: #F8FAFC;
            }
            QHeaderView::section {
                background-color: #F8FAFC;
                color: #1F2937;
                font-weight: 700;
                font-size: 12px;
                border: none;
                border-bottom: 2px solid #0E7471;
                border-right: 1px solid #E2E8F0;
                padding: 7px 10px;
            }
        """)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.Stretch)
        header.setSectionResizeMode(7, QHeaderView.Fixed)
        self.table.setColumnWidth(7, 95)

        self.table.horizontalHeaderItem(0).setTextAlignment(Qt.AlignCenter)
        self.table.horizontalHeaderItem(1).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeaderItem(2).setTextAlignment(Qt.AlignCenter)
        self.table.horizontalHeaderItem(3).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.horizontalHeaderItem(4).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.horizontalHeaderItem(5).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.horizontalHeaderItem(6).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeaderItem(7).setTextAlignment(Qt.AlignCenter)

        # Interactive double click row preview
        self.table.cellDoubleClicked.connect(lambda row, col: self.open_transaction_details(row))

        layout.addWidget(self.table, 1)

        # 5. Bottom Status and Legend (Single Unified Bar, duplicate bottom close button removed)
        bottom_layout = QHBoxLayout()
        lbl_legend = QLabel("💡 * Note : Double-cliquez sur une ligne ou cliquez sur 'Détails' pour ouvrir sa fiche complète. Les Devis et Bons de Commande brouillon sont répertoriés [Hors bilan] avec Débit 0,00 DA sans affecter le solde exigible.")
        lbl_legend.setStyleSheet("font-size: 11px; color: #64748B; font-style: italic; border: none; background: transparent;")
        bottom_layout.addWidget(lbl_legend)
        bottom_layout.addStretch(1)
        layout.addLayout(bottom_layout)

    def _create_kpi_card(self, title, default_val, text_color):
        frame = QFrame()
        frame.setStyleSheet("""
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
        l = QVBoxLayout(frame)
        l.setContentsMargins(14, 10, 14, 10)
        l.setSpacing(4)

        lbl_t = QLabel(title.upper())
        lbl_t.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748B; letter-spacing: 0.5px;")
        lbl_v = QLabel(default_val)
        lbl_v.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {text_color};")
        lbl_v.setObjectName("val")

        l.addWidget(lbl_t)
        l.addWidget(lbl_v)
        return frame

    def _update_card_val(self, frame, text):
        val_lbl = frame.findChild(QLabel, "val")
        if val_lbl:
            val_lbl.setText(text)

    def _on_date_changed(self):
        idx = self.preset_combo.findText("Personnalisé")
        if idx >= 0 and self.preset_combo.currentIndex() != idx:
            self.preset_combo.blockSignals(True)
            self.preset_combo.setCurrentIndex(idx)
            self.preset_combo.blockSignals(False)

    def _on_preset_changed(self, index):
        presets = ["this_month", "last_month", "last_quarter", "last_30_days", "this_year", "all", "custom"]
        if 0 <= index < len(presets):
            self.apply_preset(presets[index])

    def apply_preset(self, preset_key):
        if preset_key == "custom":
            self.load_ledger()
            return

        today = date.today()
        if preset_key == "this_month":
            start = date(today.year, today.month, 1)
            end = today
        elif preset_key == "last_month":
            first_this_month = date(today.year, today.month, 1)
            last_day_prev = first_this_month - timedelta(days=1)
            start = date(last_day_prev.year, last_day_prev.month, 1)
            end = last_day_prev
        elif preset_key == "last_quarter":
            curr_quarter = (today.month - 1) // 3 + 1
            if curr_quarter == 1:
                prev_quarter = 4
                year = today.year - 1
            else:
                prev_quarter = curr_quarter - 1
                year = today.year
            start_month = (prev_quarter - 1) * 3 + 1
            start = date(year, start_month, 1)
            end_month = start_month + 2
            if end_month in (1, 3, 5, 7, 8, 10, 12):
                end_day = 31
            elif end_month == 2:
                end_day = 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28
            else:
                end_day = 30
            end = date(year, end_month, end_day)
        elif preset_key == "last_30_days":
            start = today - timedelta(days=30)
            end = today
        elif preset_key == "this_year":
            start = date(today.year, 1, 1)
            end = today
        elif preset_key == "all":
            start = date(2020, 1, 1)
            end = today
        else:
            start = date(today.year, today.month, 1)
            end = today

        self.date_start.blockSignals(True)
        self.date_end.blockSignals(True)
        self.date_start.setDate(QDate(start.year, start.month, start.day))
        self.date_end.setDate(QDate(end.year, end.month, end.day))
        self.date_start.blockSignals(False)
        self.date_end.blockSignals(False)
        self.load_ledger()

    def _create_type_badge(self, type_label, is_non_binding):
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(4, 2, 4, 2)
        lbl = QLabel(type_label)
        if is_non_binding:
            bg, fg, bc = "#F1F5F9", "#64748B", "#CBD5E1"
        elif "Gros" in type_label or "Wholesale" in type_label:
            bg, fg, bc = "#E0F2FE", "#0369A1", "#BAE6FD"
        elif "BL" in type_label:
            bg, fg, bc = "#CCFBF1", "#0F766E", "#99F6E4"
        elif "Paiement" in type_label or "Règlement" in type_label:
            bg, fg, bc = "#DCFCE7", "#15803D", "#BBF7D0"
        elif "Avoir" in type_label:
            bg, fg, bc = "#F3E8FF", "#7E22CE", "#E9D5FF"
        else:
            bg, fg, bc = "#F0FDF4", "#0E7471", "#BCE3DC"

        lbl.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {bc};
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 700;
            }}
        """)
        lay.addWidget(lbl)
        lay.addStretch(1)
        return w

    def load_ledger(self):
        start_str = self.date_start.date().toString("yyyy-MM-dd")
        end_str = self.date_end.date().toString("yyyy-MM-dd")

        self.ledger_data = self.client_manager.get_client_ledger(
            self.client_id, start_date=start_str, end_date=end_str
        )

        client = self.ledger_data.get('client', {})
        name = client.get('Client_Name') or "Client inconnu"
        contact = client.get('Phone') or client.get('Contact_Person') or ""
        city = client.get('City') or ""
        tier = client.get('Price_Tier') or "Prix_1"
        limit = float(client.get('Credit_Limit') or 0.0)

        self.lbl_client_title.setText(f"👤 {name}")
        self.lbl_client_meta.setText(
            f"Tél: {contact} | Ville: {city} | Catégorie: {tier} | Plafond Crédit: {format_money(limit)} DA"
        )

        initial = float(self.ledger_data.get('initial_balance', 0.0))
        final = float(self.ledger_data.get('final_balance', 0.0))
        txs = self.ledger_data.get('transactions', [])

        total_debit = sum(t.get('debit', 0.0) for t in txs)
        total_credit = sum(t.get('credit', 0.0) for t in txs)

        self._update_card_val(self.card_initial, f"{format_money(initial)} DA")
        self._update_card_val(self.card_debit, f"{format_money(total_debit)} DA")
        self._update_card_val(self.card_credit, f"{format_money(total_credit)} DA")
        self._update_card_val(self.card_final, f"{format_money(final)} DA")

        # Color final balance
        val_lbl = self.card_final.findChild(QLabel, "val")
        if val_lbl:
            if final <= 0:
                val_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #16A34A;")
            elif limit > 0 and final > limit:
                val_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #DC2626;")
            else:
                val_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #D97706;")

        # Populate table
        self.table.setRowCount(0)
        for row_idx, t in enumerate(txs):
            self.table.insertRow(row_idx)

            # 0. Date
            date_item = QTableWidgetItem(t['date'])
            date_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 0, date_item)

            # 1. Type with colored badge
            type_label = t['type']
            is_non_binding = t.get('is_non_binding', False)
            if is_non_binding and "[Hors bilan]" not in type_label:
                type_label += " [Hors bilan]"

            badge_widget = self._create_type_badge(type_label, is_non_binding)
            self.table.setCellWidget(row_idx, 1, badge_widget)

            # 2. Reference
            ref_item = QTableWidgetItem(t['reference'])
            ref_item.setTextAlignment(Qt.AlignCenter)
            ref_item.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
            if is_non_binding:
                ref_item.setForeground(QColor("#64748B"))
            else:
                ref_item.setForeground(QColor("#0E7471"))
            self.table.setItem(row_idx, 2, ref_item)

            # 3. Débit (+)
            debit_val = t['debit']
            if is_non_binding:
                raw_amt = t.get('raw_amount', 0.0)
                debit_item = QTableWidgetItem("0,00 DA")
                debit_item.setToolTip(f"Montant indicatif : {format_money(raw_amt)} DA\nDevis / Commande proforma (Aucun impact financier sur le compte).")
                debit_item.setForeground(QColor("#94A3B8"))
                font = debit_item.font()
                font.setItalic(True)
                debit_item.setFont(font)
            else:
                debit_item = QTableWidgetItem(f"{format_money(debit_val)} DA" if debit_val > 0 else "-")
                if debit_val > 0:
                    debit_item.setForeground(QColor("#0284C7"))
                    debit_item.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
            debit_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row_idx, 3, debit_item)

            # 4. Crédit (-)
            credit_val = t['credit']
            credit_item = QTableWidgetItem(f"{format_money(credit_val)} DA" if credit_val > 0 else "-")
            credit_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if credit_val > 0:
                credit_item.setForeground(QColor("#16A34A"))
                credit_item.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
            self.table.setItem(row_idx, 4, credit_item)

            # 5. Solde Progressif
            bal_val = t['balance']
            bal_item = QTableWidgetItem(f"{format_money(bal_val)} DA")
            bal_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            bal_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            if bal_val > 0:
                bal_item.setForeground(QColor("#DC2626"))
            elif bal_val < 0:
                bal_item.setForeground(QColor("#16A34A"))
            else:
                bal_item.setForeground(QColor("#475569"))
            self.table.setItem(row_idx, 5, bal_item)

            # 6. Notes
            note_str = t.get('notes') or ""
            if is_non_binding and "Hors bilan" not in note_str:
                note_str = f"Document proforma (Non exigible) | {note_str}".strip(" |")
            note_item = QTableWidgetItem(note_str)
            note_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            if is_non_binding:
                note_item.setForeground(QColor("#64748B"))
            self.table.setItem(row_idx, 6, note_item)

            # 7. Actions Button (Modalless Preview)
            act_container = QWidget()
            act_container.setStyleSheet("background: transparent;")
            act_layout = QHBoxLayout(act_container)
            act_layout.setContentsMargins(4, 2, 4, 2)
            act_layout.setAlignment(Qt.AlignCenter)

            btn_view = QPushButton("Détails")
            btn_view.setIcon(get_duotone_icon("statement", 12))
            btn_view.setIconSize(QSize(12, 12))
            btn_view.setCursor(Qt.PointingHandCursor)
            btn_view.setFixedHeight(26)
            btn_view.setFixedWidth(78)
            btn_view.setStyleSheet("""
                QPushButton {
                    background-color: #0E7471;
                    color: #FFFFFF;
                    font-size: 11px;
                    font-weight: 700;
                    border-radius: 4px;
                    padding: 0 6px;
                    border: none;
                    white-space: nowrap;
                }
                QPushButton:hover { background-color: #0A5C59; }
                QPushButton:pressed { background-color: #084846; }
            """)
            btn_view.clicked.connect(lambda _, r=row_idx: self.open_transaction_details(r))
            act_layout.addWidget(btn_view)
            self.table.setCellWidget(row_idx, 7, act_container)

    def open_transaction_details(self, row_idx: int):
        """
        Ouvre un dialogue modalless (non-modal) affichant les détails réels de l'opération.
        Plusieurs fenêtres peuvent être ouvertes et comparées en même temps sans bloquer le relevé.
        """
        if row_idx < 0:
            return
        txs = self.ledger_data.get('transactions', [])
        if row_idx >= len(txs):
            return
        t = txs[row_idx]
        client_info = self.ledger_data.get('client', {})

        dlg = TransactionDetailsDialog(self.data_manager, t, client_info, parent=self)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

        # Conserver la référence pour éviter le garbage collection
        self._open_detail_dialogs.append(dlg)
        dlg.destroyed.connect(lambda: self._open_detail_dialogs.remove(dlg) if dlg in self._open_detail_dialogs else None)

    def print_statement(self):
        """Génère un PDF temporaire et l'ouvre directement pour impression."""
        import tempfile
        client = self.ledger_data.get('client', {})
        client_name = client.get('Client_Name') or "Client"
        safe_name = "".join(c for c in client_name if c.isalnum() or c in (' ', '_', '-')).strip()
        temp_dir = tempfile.gettempdir()
        temp_pdf = os.path.join(temp_dir, f"Releve_{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        if self._generate_pdf_file(temp_pdf):
            try:
                os.startfile(temp_pdf)
            except Exception as e:
                logging.error(f"Error opening statement PDF for printing: {e}")

    def export_pdf(self):
        client = self.ledger_data.get('client', {})
        client_name = client.get('Client_Name') or "Client"
        safe_name = "".join(c for c in client_name if c.isalnum() or c in (' ', '_', '-')).strip()
        default_filename = f"Releve_Compte_{safe_name}_{datetime.now().strftime('%Y%m%d')}.pdf"

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le relevé de compte PDF", default_filename, "Fichiers PDF (*.pdf)"
        )
        if not file_path:
            return

        if self._generate_pdf_file(file_path):
            reply = QMessageBox.information(
                self,
                "Export Réussi",
                f"Le relevé de compte a été exporté avec succès :\n{file_path}\n\nSouhaitez-vous l'ouvrir maintenant ?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                try:
                    os.startfile(file_path)
                except Exception as e:
                    logging.error(f"Error opening exported statement PDF: {e}")

    def _generate_pdf_file(self, file_path: str) -> bool:
        if not HAS_REPORTLAB:
            QMessageBox.warning(self, "Bibliothèque manquante", "La bibliothèque ReportLab n'est pas installée.")
            return False

        try:
            client = self.ledger_data.get('client', {})
            client_name = client.get('Client_Name') or "Client"

            doc = SimpleDocTemplate(
                file_path,
                pagesize=A4,
                leftMargin=1.5 * cm,
                rightMargin=1.5 * cm,
                topMargin=1.5 * cm,
                bottomMargin=1.5 * cm
            )

            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'DocTitle',
                parent=styles['Heading1'],
                fontSize=18,
                textColor=colors.HexColor('#0E7471'),
                spaceAfter=6,
                alignment=1
            )
            normal_style = styles['Normal']
            header_meta_style = ParagraphStyle(
                'HeaderMeta',
                parent=normal_style,
                fontSize=9,
                textColor=colors.HexColor('#475569')
            )

            story = []

            # 1. En-tête de l'entreprise
            company_settings = {}
            if hasattr(self.data_manager, 'company_settings'):
                company_settings = self.data_manager.company_settings.get_settings()

            company_name = company_settings.get('Company_Name') or "ENTREPRISE COMMERCIALE"
            company_phone = company_settings.get('Phone') or ""
            company_email = company_settings.get('Email') or ""
            company_address = company_settings.get('Address') or ""

            header_text = f"<b>{company_name}</b><br/>{company_address}<br/>Tél: {company_phone} | Email: {company_email}"

            story.append(Paragraph(header_text, header_meta_style))
            story.append(Spacer(1, 10))

            # 2. Titre du Relevé
            story.append(Paragraph("RELEVÉ DE COMPTE CLIENT (GRAND LIVRE AUXILIAIRE)", title_style))
            period_str = f"Période du <b>{self.date_start.date().toString('dd/MM/yyyy')}</b> au <b>{self.date_end.date().toString('dd/MM/yyyy')}</b>"
            story.append(Paragraph(period_str, ParagraphStyle('Center', parent=normal_style, alignment=1, fontSize=10)))
            story.append(Spacer(1, 12))

            # 3. Informations Client
            tax_id = client.get('Tax_ID_Number') or client.get('Tax_ID') or '-'
            rc = client.get('Commercial_Reg_No') or client.get('Commercial_Register') or '-'
            client_info = [
                [Paragraph(f"<b>Client :</b> {client_name}", normal_style),
                 Paragraph(f"<b>Catégorie Tarifaire :</b> {client.get('Price_Tier', 'Prix_1')}", normal_style)],
                [Paragraph(f"<b>Contact :</b> {client.get('Contact_Person', '-')}", normal_style),
                 Paragraph(f"<b>Téléphone :</b> {client.get('Phone', '-')}", normal_style)],
                [Paragraph(f"<b>NIF :</b> {tax_id}", normal_style),
                 Paragraph(f"<b>RC :</b> {rc}", normal_style)],
                [Paragraph(f"<b>Ville / Adresse :</b> {client.get('City') or client.get('Address') or '-'}", normal_style),
                 Paragraph(f"<b>Plafond de Crédit :</b> {format_money(float(client.get('Credit_Limit') or 0.0))} DA", normal_style)]
            ]
            t_client = Table(client_info, colWidths=[9.5 * cm, 8.5 * cm])
            t_client.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#DDE3EA')),
                ('PADDING', (0, 0), (-1, -1), 6),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
            ]))
            story.append(t_client)
            story.append(Spacer(1, 12))

            # 4. Tableau Récapitulatif KPI
            initial = float(self.ledger_data.get('initial_balance', 0.0))
            final = float(self.ledger_data.get('final_balance', 0.0))
            txs = self.ledger_data.get('transactions', [])
            total_debit = sum(t.get('debit', 0.0) for t in txs)
            total_credit = sum(t.get('credit', 0.0) for t in txs)

            kpi_data = [
                ["Solde Antérieur", "Total Débit (Factures & BL)", "Total Crédit (Règlements & Avoirs)", "Nouveau Solde Dû"],
                [f"{format_money(initial)} DA", f"{format_money(total_debit)} DA", f"{format_money(total_credit)} DA", f"{format_money(final)} DA"]
            ]
            t_kpi = Table(kpi_data, colWidths=[4.5 * cm, 4.5 * cm, 4.5 * cm, 4.5 * cm])
            t_kpi.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0E7471')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, 1), 10),
                ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#F1F5F9')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DDE3EA')),
                ('PADDING', (0, 0), (-1, -1), 5)
            ]))
            story.append(t_kpi)
            story.append(Spacer(1, 14))

            # 5. Détail des Écritures (Ledger Grid)
            ledger_header = ["Date", "Type Document", "Réf.", "Débit (DA)", "Crédit (DA)", "Solde Progressif (DA)"]
            ledger_table_data = [ledger_header]

            for t in txs:
                is_nb = t.get('is_non_binding', False)
                type_display = t['type'] + (" [Hors bilan]" if is_nb and "[Hors bilan]" not in t['type'] else "")
                d_str = "0.00" if is_nb else (format_money(t['debit']) if t['debit'] > 0 else "-")
                c_str = format_money(t['credit']) if t['credit'] > 0 else "-"
                b_str = format_money(t['balance'])
                ledger_table_data.append([
                    t['date'],
                    type_display,
                    t['reference'],
                    d_str,
                    c_str,
                    b_str
                ])

            t_ledger = Table(
                ledger_table_data,
                colWidths=[2.3 * cm, 4.7 * cm, 2.8 * cm, 2.7 * cm, 2.7 * cm, 2.8 * cm],
                repeatRows=1
            )
            t_ledger.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (2, -1), 'CENTER'),
                ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                ('PADDING', (0, 0), (-1, -1), 4),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')])
            ]))
            story.append(t_ledger)
            story.append(Spacer(1, 20))

            # 6. Mentions de clôture & Signatures
            sign_data = [
                [Paragraph("<b>Visa & Cachet de l'Entreprise :</b>", normal_style),
                 Paragraph("<b>Accusé de Réception Client :</b>", normal_style)]
            ]
            t_sign = Table(sign_data, colWidths=[9 * cm, 9 * cm])
            t_sign.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('PADDING', (0, 0), (-1, -1), 0)
            ]))
            story.append(t_sign)

            doc.build(story)
            return True

        except Exception as e:
            logging.error(f"Error generating statement PDF: {e}", exc_info=True)
            QMessageBox.critical(self, "Erreur PDF", f"Impossible de générer le document PDF :\n{str(e)}")
            return False
