# ui/widgets/wholesale_sales/wholesale_sales_tab.py

import logging
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QMessageBox, QDoubleSpinBox, QDateEdit, QFrame,
    QCompleter, QSizePolicy, QCheckBox, QDialog, QScrollBar
)
from PySide6.QtCore import Qt, QDate, QStringListModel, QPoint, QSize
from PySide6.QtGui import QFont, QKeySequence, QShortcut, QColor, QIcon, QPixmap

from ui.formatting import format_money
from branding import get_logo_path
from ui.icons import get_duotone_icon, get_trash_icon, get_warning_icon, get_edit_lots_icon
from ui.widgets.sales.dialogs import ClientDialog
from ui.widgets.master_data.client_statement_dialog import ClientStatementDialog
from ui.widgets.sales.touch_keypad import TouchKeypadDialog
from .pdf_export import export_wholesale_document_pdf
from .lot_split_dialog import MultiLotSelectionDialog
from .supervisor_override_dialog import SupervisorOverrideDialog


class WholesaleSalesTab(QWidget):
    """
    Module de Vente en Gros et Demi-Gros (B2B).
    Fonctionne indépendamment des sessions de caisse POS (aucun terminal/session de caisse requis).
    Prend en charge :
    - Devis / Proforma (aucun mouvement de stock)
    - Bon de Commande (aucun mouvement de stock)
    - Bon de Livraison (déduction atomique du stock d'entrepôt)
    - Facture de Vente en Gros (déduction atomique du stock et comptabilisation)
    - Résolution dynamique de la grille tarifaire (Prix 1 à Prix 4) selon le client.
    - Pavé numérique et clavier tactile virtuel bi-mode (TouchKeypadDialog).
    """

    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.cart_items = []
        self.batches_cache = []
        self.search_map = {}
        self.barcode_map = {}
        self.product_batches_map = {}
        self.pending_batch = None
        self.touch_keypad = None

        self.init_ui()
        self.load_initial_data()
        self._install_shortcuts()

    def init_ui(self):
        self.setObjectName("WholesaleSalesTab")
        self.setStyleSheet("""
            QWidget#WholesaleSalesTab {
                background-color: #F4F6F8;
            }
        """)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(12)

        # 1. Client & Credit Dashboard Header Card
        client_card = self._build_client_card()
        root_layout.addWidget(client_card)

        # 2. Document Meta Controls (Type, Dates, Échéances, Paiement)
        meta_card = self._build_meta_card()
        root_layout.addWidget(meta_card)

        # 3. Search & Quick Barcode Row
        search_row = self._build_search_row()
        root_layout.addLayout(search_row)

        # 4. Cart Grid Table (Dense Data Table with Horizontal Scroll)
        self.cart_table = self._build_cart_table()
        root_layout.addWidget(self.cart_table, 1)

        # 5. Bottom Financial Summary & Actions
        bottom_bar = self._build_bottom_bar()
        root_layout.addLayout(bottom_bar)

    def _build_client_card(self):
        card = QFrame()
        card.setObjectName("ClientCard")
        card.setStyleSheet("""
            QFrame#ClientCard {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 8px;
            }
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(16)

        # 1. Block Client B2B
        v_client = QVBoxLayout()
        v_client.setSpacing(4)
        lbl_c = QLabel("CLIENT B2B *")
        lbl_c.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748B; letter-spacing: 0.5px; border: none; background: transparent;")

        h_client = QHBoxLayout()
        h_client.setSpacing(6)

        self.cb_client = QComboBox()
        self.cb_client.setFixedHeight(38)
        self.cb_client.setMinimumWidth(260)
        self.cb_client.setEditable(True)
        self.cb_client.setStyleSheet("""
            QComboBox {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 600;
                color: #1F2937;
            }
            QComboBox:focus { border: 1.5px solid #0E7471; }
        """)
        if self.cb_client.completer():
            self.cb_client.completer().setFilterMode(Qt.MatchContains)
            self.cb_client.completer().setCaseSensitivity(Qt.CaseInsensitive)
        self.cb_client.currentIndexChanged.connect(self._on_client_changed)
        h_client.addWidget(self.cb_client, 1)

        self.btn_new_client = QPushButton("➕ Nouveau")
        self.btn_new_client.setCursor(Qt.PointingHandCursor)
        self.btn_new_client.setFixedHeight(38)
        self.btn_new_client.setStyleSheet("""
            QPushButton {
                background-color: #F8FAFC;
                color: #1F2937;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
                font-weight: 700;
                padding: 0 12px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #E2E8F0; }
        """)
        self.btn_new_client.clicked.connect(self._create_quick_client)
        h_client.addWidget(self.btn_new_client)

        self.btn_client_statement = QPushButton("📄 Relevé")
        self.btn_client_statement.setCursor(Qt.PointingHandCursor)
        self.btn_client_statement.setFixedHeight(38)
        self.btn_client_statement.setStyleSheet("""
            QPushButton {
                background-color: #0E7471;
                color: #FFFFFF;
                font-weight: 700;
                border: none;
                border-radius: 6px;
                padding: 0 14px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #0A5C59; }
        """)
        self.btn_client_statement.clicked.connect(self._open_client_statement)
        h_client.addWidget(self.btn_client_statement)

        v_client.addWidget(lbl_c)
        v_client.addLayout(h_client)
        layout.addLayout(v_client, 2)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setStyleSheet("color: #E2E8F0; max-width: 1px;")
        layout.addWidget(sep1)

        # 2. Block Grille Tarifaire
        v_tier = QVBoxLayout()
        v_tier.setSpacing(4)
        lbl_tier = QLabel("GRILLE TARIFAIRE (F3)")
        lbl_tier.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748B; letter-spacing: 0.5px; border: none; background: transparent;")

        h_tier = QHBoxLayout()
        h_tier.setSpacing(6)

        self.cb_price_tier = QComboBox()
        self.cb_price_tier.addItem("Prix 1 (Détail)", "Prix_1")
        self.cb_price_tier.addItem("Prix 2 (Demi-Gros)", "Prix_2")
        self.cb_price_tier.addItem("Prix 3 (Gros)", "Prix_3")
        self.cb_price_tier.addItem("Prix 4 (Super-Gros)", "Prix_4")
        self.cb_price_tier.setFixedHeight(38)
        self.cb_price_tier.setMinimumWidth(160)
        self.cb_price_tier.setStyleSheet("""
            QComboBox {
                background-color: #FFFFFF;
                border: 1.5px solid #0E7471;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 700;
                color: #0E7471;
            }
        """)
        self.cb_price_tier.currentIndexChanged.connect(self._on_price_tier_changed)
        h_tier.addWidget(self.cb_price_tier)

        # Compact interactive red alert icon (Tooltip / Modal Dialog)
        self.btn_tier_warning = QPushButton()
        self.btn_tier_warning.setIcon(get_warning_icon(20))
        self.btn_tier_warning.setIconSize(QSize(20, 20))
        self.btn_tier_warning.setFixedSize(38, 38)
        self.btn_tier_warning.setCursor(Qt.PointingHandCursor)
        self.btn_tier_warning.setToolTip("⚠️ Alerte tarifaire : Tarif Détail (Prix 1) appliqué ! Cliquez pour ouvrir les détails.")
        self.btn_tier_warning.setStyleSheet("""
            QPushButton {
                background-color: #FEE2E2;
                border: 1.5px solid #FCA5A5;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #FECACA;
                border-color: #EF4444;
            }
            QPushButton:pressed {
                background-color: #F87171;
            }
        """)
        self.btn_tier_warning.clicked.connect(self._show_tier_warning_dialog)
        self.btn_tier_warning.hide()
        h_tier.addWidget(self.btn_tier_warning)

        # Keep lbl_tier_warning as hidden label attribute for backwards-compatibility
        self.lbl_tier_warning = QLabel()
        self.lbl_tier_warning.hide()

        v_tier.addWidget(lbl_tier)
        v_tier.addLayout(h_tier)
        layout.addLayout(v_tier)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setStyleSheet("color: #E2E8F0; max-width: 1px;")
        layout.addWidget(sep2)

        # 3. Block Situation Crédit Client
        v_credit = QVBoxLayout()
        v_credit.setSpacing(4)
        lbl_credit = QLabel("SITUATION CRÉDIT CLIENT")
        lbl_credit.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748B; letter-spacing: 0.5px; border: none; background: transparent;")

        h_kpis = QHBoxLayout()
        h_kpis.setSpacing(8)

        self.lbl_credit_limit = QLabel("Plafond : 0.00 DA")
        self.lbl_credit_limit.setFixedHeight(38)
        self.lbl_credit_limit.setStyleSheet("background-color: #F8FAFC; border: 1px solid #DDE3EA; border-radius: 6px; padding: 0 12px; font-size: 12px; font-weight: 600; color: #475569;")

        self.lbl_current_balance = QLabel("Solde Dû : 0.00 DA")
        self.lbl_current_balance.setFixedHeight(38)
        self.lbl_current_balance.setStyleSheet("background-color: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 6px; padding: 0 12px; font-size: 12px; font-weight: 700; color: #16A34A;")

        self.lbl_available_credit = QLabel("Disponible : 0.00 DA")
        self.lbl_available_credit.setFixedHeight(38)
        self.lbl_available_credit.setStyleSheet("background-color: #E6F4F1; border: 1px solid #BCE3DC; border-radius: 6px; padding: 0 12px; font-size: 12px; font-weight: 700; color: #0E7471;")

        h_kpis.addWidget(self.lbl_credit_limit)
        h_kpis.addWidget(self.lbl_current_balance)
        h_kpis.addWidget(self.lbl_available_credit)

        v_credit.addWidget(lbl_credit)
        v_credit.addLayout(h_kpis)
        layout.addLayout(v_credit)

        return card

    def _show_tier_warning_dialog(self):
        """Ouvre une fenêtre modale élégante affichant les détails complets de l'avertissement tarifaire."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Avertissement Tarifaire - Vente en Gros B2B")
        dlg.setModal(True)
        dlg.setMinimumWidth(480)
        dlg.setAttribute(Qt.WA_StyledBackground, True)
        dlg.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 10px;
            }
        """)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(16)

        # Header with warning icon and title
        h_header = QHBoxLayout()
        h_header.setSpacing(12)
        lbl_icon = QLabel()
        lbl_icon.setPixmap(get_warning_icon(36).pixmap(36, 36))
        lbl_title = QLabel("Attention : Tarif Détail Appliqué")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #DC2626;")
        h_header.addWidget(lbl_icon)
        h_header.addWidget(lbl_title, 1)
        lay.addLayout(h_header)

        # Body message card
        msg_frame = QFrame()
        msg_frame.setStyleSheet("""
            QFrame {
                background-color: #FEF2F2;
                border: 1px solid #FECACA;
                border-radius: 8px;
                padding: 12px 14px;
            }
        """)
        v_msg = QVBoxLayout(msg_frame)
        v_msg.setSpacing(8)

        lbl_desc = QLabel(
            "Le document de vente en gros en cours utilise actuellement la grille <b>Prix 1 (Détail)</b>.<br><br>"
            "<b>Impact commercial :</b><br>"
            "• Ce palier correspond aux tarifs grand public du point de vente (POS).<br>"
            "• Aucune tarification préférentielle grossiste ou demi-gros n'est appliquée à ces articles.<br><br>"
            "<b>Conseil :</b> Pour appliquer les prix négociés, vous pouvez basculer sur <b>Prix 2 (Demi-Gros)</b>, "
            "<b>Prix 3 (Gros)</b> ou <b>Prix 4 (Super-Gros)</b> à l'aide de la touche de raccourci <b>F3</b>."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("font-size: 12px; color: #1F2937; line-height: 1.4;")
        v_msg.addWidget(lbl_desc)
        lay.addWidget(msg_frame)

        # Buttons
        h_btns = QHBoxLayout()
        h_btns.setSpacing(10)
        h_btns.addStretch(1)

        btn_switch_p2 = QPushButton("Basculer vers Prix 2 (Demi-Gros)")
        btn_switch_p2.setCursor(Qt.PointingHandCursor)
        btn_switch_p2.setFixedHeight(38)
        btn_switch_p2.setStyleSheet("""
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
        """)
        def on_switch():
            idx = self.cb_price_tier.findData("Prix_2")
            if idx >= 0:
                self.cb_price_tier.setCurrentIndex(idx)
            dlg.accept()

        btn_switch_p2.clicked.connect(on_switch)

        btn_close = QPushButton("Garder Prix 1")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setFixedHeight(38)
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
        """)
        btn_close.clicked.connect(dlg.reject)

        h_btns.addWidget(btn_close)
        h_btns.addWidget(btn_switch_p2)
        lay.addLayout(h_btns)

        dlg.exec()

    def _build_meta_card(self):
        card = QFrame()
        card.setObjectName("MetaCard")
        card.setStyleSheet("""
            QFrame#MetaCard {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 8px;
            }
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(16)

        # 1. Document Type
        v_doc = QVBoxLayout()
        v_doc.setSpacing(4)
        lbl_dt = QLabel("TYPE DE DOCUMENT")
        lbl_dt.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748B; letter-spacing: 0.5px; border: none; background: transparent;")

        self.cb_doc_type = QComboBox()
        self.cb_doc_type.addItem("Facture de Vente", "Facture")
        self.cb_doc_type.addItem("Bon de Livraison (BL)", "Bon de Livraison")
        self.cb_doc_type.addItem("Bon de Commande (BC)", "Bon de Commande")
        self.cb_doc_type.addItem("Devis / Facture Proforma", "Devis")
        self.cb_doc_type.setFixedHeight(38)
        self.cb_doc_type.setStyleSheet("""
            QComboBox {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 600;
                color: #1F2937;
            }
            QComboBox:focus { border: 1.5px solid #0E7471; }
        """)
        self.cb_doc_type.currentIndexChanged.connect(self._on_doc_type_changed)
        v_doc.addWidget(lbl_dt)
        v_doc.addWidget(self.cb_doc_type)
        layout.addLayout(v_doc)

        # 2. Date de Document
        v_date = QVBoxLayout()
        v_date.setSpacing(4)
        lbl_do = QLabel("DATE D'ÉMISSION")
        lbl_do.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748B; letter-spacing: 0.5px; border: none; background: transparent;")

        self.date_order = QDateEdit()
        self.date_order.setCalendarPopup(True)
        self.date_order.setDate(QDate.currentDate())
        self.date_order.setFixedHeight(38)
        self.date_order.setStyleSheet("""
            QDateEdit {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 600;
                color: #1F2937;
            }
            QDateEdit:focus { border: 1.5px solid #0E7471; }
        """)
        v_date.addWidget(lbl_do)
        v_date.addWidget(self.date_order)
        layout.addLayout(v_date)

        # 3. Date d'échéance & raccourcis
        v_due = QVBoxLayout()
        v_due.setSpacing(4)
        lbl_dd = QLabel("DATE D'ÉCHÉANCE")
        lbl_dd.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748B; letter-spacing: 0.5px; border: none; background: transparent;")

        h_due = QHBoxLayout()
        h_due.setSpacing(6)

        self.date_due = QDateEdit()
        self.date_due.setCalendarPopup(True)
        self.date_due.setDate(QDate.currentDate().addDays(30))
        self.date_due.setFixedHeight(38)
        self.date_due.setStyleSheet("""
            QDateEdit {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 600;
                color: #1F2937;
            }
            QDateEdit:focus { border: 1.5px solid #0E7471; }
        """)
        h_due.addWidget(self.date_due)

        btn_15 = QPushButton("+15j")
        btn_30 = QPushButton("+30j")
        btn_60 = QPushButton("+60j")
        btn_eom = QPushButton("Fin Mois")
        for b in (btn_15, btn_30, btn_60, btn_eom):
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(38)
            b.setStyleSheet("""
                QPushButton {
                    background-color: #F8FAFC;
                    border: 1px solid #DDE3EA;
                    border-radius: 6px;
                    font-size: 11px;
                    padding: 0 8px;
                    font-weight: 700;
                    color: #475569;
                }
                QPushButton:hover {
                    background-color: #E6F4F1;
                    border-color: #0E7471;
                    color: #0E7471;
                }
            """)

        btn_15.clicked.connect(lambda: self.date_due.setDate(self.date_order.date().addDays(15)))
        btn_30.clicked.connect(lambda: self.date_due.setDate(self.date_order.date().addDays(30)))
        btn_60.clicked.connect(lambda: self.date_due.setDate(self.date_order.date().addDays(60)))
        btn_eom.clicked.connect(self._set_end_of_month_due_date)

        h_due.addWidget(btn_15)
        h_due.addWidget(btn_30)
        h_due.addWidget(btn_60)
        h_due.addWidget(btn_eom)

        v_due.addWidget(lbl_dd)
        v_due.addLayout(h_due)
        layout.addLayout(v_due)

        # 4. Mode de Paiement
        v_pay = QVBoxLayout()
        v_pay.setSpacing(4)
        lbl_pm = QLabel("MODE DE PAIEMENT")
        lbl_pm.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748B; letter-spacing: 0.5px; border: none; background: transparent;")

        self.cb_payment_method = QComboBox()
        self.cb_payment_method.addItem("À terme / Crédit Client", "Credit")
        self.cb_payment_method.addItem("Espèce", "Cash")
        self.cb_payment_method.addItem("Chèque Bancaire", "Card")
        self.cb_payment_method.addItem("Virement Bancaire", "Transfer")
        self.cb_payment_method.addItem("Versement", "Versement")
        self.cb_payment_method.setFixedHeight(38)
        self.cb_payment_method.setStyleSheet("""
            QComboBox {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 600;
                color: #1F2937;
            }
            QComboBox:focus { border: 1.5px solid #0E7471; }
        """)
        v_pay.addWidget(lbl_pm)
        v_pay.addWidget(self.cb_payment_method)
        layout.addLayout(v_pay)

        layout.addStretch(1)
        return card

    def _set_end_of_month_due_date(self):
        curr = self.date_order.date().toPython()
        next_month = curr.replace(day=28) + timedelta(days=4)
        last_day = next_month - timedelta(days=next_month.day)
        self.date_due.setDate(QDate(last_day.year, last_day.month, last_day.day))

    def _build_search_row(self):
        layout = QHBoxLayout()
        layout.setSpacing(10)

        # Expanded Ergonomic Barcode Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Scanner un code-barres (EAN-13), saisir une désignation ou un N° de lot (F1 / Ctrl+F)...")
        self.search_input.setFixedHeight(42)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #FFFFFF;
                border: 2px solid #0E7471;
                border-radius: 6px;
                padding: 0 14px;
                font-size: 13px;
                font-weight: 600;
                color: #1F2937;
            }
            QLineEdit:focus {
                background-color: #F0FDF4;
                border-color: #0E7471;
            }
        """)

        self.completer = QCompleter(self)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        self.search_input.setCompleter(self.completer)
        self.completer.activated.connect(self._on_search_selected)
        self.search_input.returnPressed.connect(self._on_search_return)

        # Keep spin_quick_qty and spin_quick_discount as attributes for headless testing and fallback
        self.spin_quick_qty = QDoubleSpinBox()
        self.spin_quick_qty.setRange(0.01, 999999.0)
        self.spin_quick_qty.setValue(1.0)
        self.spin_quick_qty.setDecimals(2)

        self.spin_quick_discount = QDoubleSpinBox()
        self.spin_quick_discount.setRange(0.0, 100.0)
        self.spin_quick_discount.setValue(0.0)
        self.spin_quick_discount.setDecimals(2)

        self.btn_add_to_cart = QPushButton("Ajouter")

        # Pavé Tactile helper button
        self.btn_keypad_search = QPushButton("🔢")
        self.btn_keypad_search.setCursor(Qt.PointingHandCursor)
        self.btn_keypad_search.setFixedHeight(42)
        self.btn_keypad_search.setFixedWidth(46)
        self.btn_keypad_search.setToolTip("Ouvrir le pavé tactile / clavier virtuel")
        self.btn_keypad_search.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #0E7471;
                font-weight: 700;
                font-size: 16px;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #E6F4F1;
                border-color: #0E7471;
            }
        """)
        self.btn_keypad_search.clicked.connect(self.toggle_touch_keypad)

        # Actualiser Stock button
        self.btn_refresh = QPushButton("Actualiser Stock")
        self.btn_refresh.setIcon(get_duotone_icon("refresh", 16))
        self.btn_refresh.setIconSize(QSize(16, 16))
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setFixedHeight(42)
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #1F2937;
                font-weight: 700;
                padding: 0 16px;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #F8FAFC;
                border-color: #CBD5E1;
            }
        """)
        self.btn_refresh.clicked.connect(self.load_initial_data)

        layout.addWidget(self.search_input, 1)
        layout.addWidget(self.btn_keypad_search)
        layout.addWidget(self.btn_refresh)

        return layout

    def _build_cart_table(self):
        table = QTableWidget()
        cols = [
            "Action", "Code-Barres", "Désignation Produit", "N° Lot", "Péremption",
            "Emplacement", "Stock Dispo", "Prix Unit. HT", "Échantillon", "Quantité", "Remise %",
            "Total HT", "TVA %", "Total TTC"
        ]
        table.setColumnCount(len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(44)
        table.verticalHeader().setMinimumSectionSize(40)

        # Smooth horizontal and vertical scrolling (overflow-x: auto)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
        table.setVerticalScrollMode(QTableWidget.ScrollPerPixel)

        table.setStyleSheet("""
            QTableWidget {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 8px;
                gridline-color: #E2E8F0;
                font-size: 12px;
                color: #1F2937;
                selection-background-color: #E6F4F1;
                selection-color: #0E7471;
            }
            QTableWidget::item {
                border-bottom: 1px solid #E2E8F0;
                padding: 4px 6px;
                color: #1F2937;
            }
            QTableWidget::item:alternate {
                background-color: #F8FAFC;
            }
            QTableWidget::item:selected {
                background-color: #E6F4F1;
                color: #0E7471;
            }
            QHeaderView::section {
                background-color: #F8FAFC;
                color: #1F2937;
                font-weight: 700;
                font-size: 12px;
                border: none;
                border-bottom: 2px solid #0E7471;
                border-right: 1px solid #E2E8F0;
                padding: 8px 6px;
            }
            QScrollBar:horizontal {
                border: none;
                background: #F1F5F9;
                height: 10px;
                border-radius: 5px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #CBD5E1;
                min-width: 30px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #94A3B8;
            }
            QScrollBar:vertical {
                border: none;
                background: #F1F5F9;
                width: 10px;
                border-radius: 5px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #CBD5E1;
                min-height: 30px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94A3B8;
            }
        """)

        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(60)

        # Set specific widths for each column to support smooth horizontal scrolling
        column_widths = {
            0: 84,   # Action (2 buttons: 32px each + padding)
            1: 130,  # Code-Barres
            2: 260,  # Désignation Produit (Interactive)
            3: 110,  # N° Lot
            4: 110,  # Péremption
            5: 120,  # Emplacement
            6: 95,   # Stock Dispo
            7: 115,  # Prix Unit. HT
            8: 85,   # Échantillon
            9: 105,  # Quantité
            10: 95,  # Remise %
            11: 120, # Total HT
            12: 75,  # TVA %
            13: 125  # Total TTC
        }
        for col_idx, width in column_widths.items():
            if col_idx == 0:
                header.setSectionResizeMode(col_idx, QHeaderView.Fixed)
            else:
                header.setSectionResizeMode(col_idx, QHeaderView.Interactive)
            table.setColumnWidth(col_idx, width)

        return table

    def _build_bottom_bar(self):
        layout = QHBoxLayout()
        layout.setSpacing(12)

        # Left Actions
        self.btn_clear = QPushButton("Vider le Panier")
        self.btn_clear.setIcon(get_trash_icon(16))
        self.btn_clear.setIconSize(QSize(16, 16))
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.setFixedHeight(40)
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #DC2626;
                border: 1px solid #FECACA;
                border-radius: 6px;
                padding: 0 16px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #FEE2E2;
                border-color: #EF4444;
            }
        """)
        self.btn_clear.clicked.connect(self.clear_cart)
        layout.addWidget(self.btn_clear)

        # Pavé Tactile / Clavier Virtuel
        self.btn_keypad = QPushButton("🔢 Pavé Tactile")
        self.btn_keypad.setCursor(Qt.PointingHandCursor)
        self.btn_keypad.setFixedHeight(40)
        self.btn_keypad.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #0E7471;
                font-weight: 700;
                font-size: 12px;
                border: 1px solid #0E7471;
                border-radius: 6px;
                padding: 0 16px;
            }
            QPushButton:hover { background-color: #E6F4F1; }
        """)
        self.btn_keypad.clicked.connect(self.toggle_touch_keypad)
        layout.addWidget(self.btn_keypad)

        layout.addStretch(1)

        # Financial Summary Panel (Pill Cards)
        self.lbl_summary_ht = QLabel("Total HT : 0,00 DA")
        self.lbl_summary_ht.setFixedHeight(40)
        self.lbl_summary_ht.setStyleSheet("""
            background-color: #FFFFFF;
            border: 1px solid #DDE3EA;
            border-radius: 6px;
            padding: 0 14px;
            font-size: 12px;
            color: #475569;
            font-weight: 700;
        """)

        self.lbl_summary_remise = QLabel("Remise : 0,00 DA")
        self.lbl_summary_remise.setFixedHeight(40)
        self.lbl_summary_remise.setStyleSheet("""
            background-color: #FFFBEB;
            border: 1px solid #FDE68A;
            border-radius: 6px;
            padding: 0 14px;
            font-size: 12px;
            color: #B45309;
            font-weight: 700;
        """)

        self.lbl_summary_tva = QLabel("TVA : 0,00 DA")
        self.lbl_summary_tva.setFixedHeight(40)
        self.lbl_summary_tva.setStyleSheet("""
            background-color: #FFFFFF;
            border: 1px solid #DDE3EA;
            border-radius: 6px;
            padding: 0 14px;
            font-size: 12px;
            color: #475569;
            font-weight: 700;
        """)

        self.lbl_summary_net_ttc = QLabel("NET À PAYER : 0,00 DA")
        self.lbl_summary_net_ttc.setFixedHeight(40)
        self.lbl_summary_net_ttc.setStyleSheet("""
            background-color: #0E7471;
            color: #FFFFFF;
            padding: 0 20px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 800;
            letter-spacing: 0.5px;
        """)

        layout.addWidget(self.lbl_summary_ht)
        layout.addWidget(self.lbl_summary_remise)
        layout.addWidget(self.lbl_summary_tva)
        layout.addWidget(self.lbl_summary_net_ttc)

        # Commit Buttons
        self.btn_save_document = QPushButton("Valider le Document (F10)")
        self.btn_save_document.setIcon(get_duotone_icon("payment_white", 16))
        self.btn_save_document.setIconSize(QSize(16, 16))
        self.btn_save_document.setCursor(Qt.PointingHandCursor)
        self.btn_save_document.setFixedHeight(40)
        self.btn_save_document.setStyleSheet("""
            QPushButton {
                background-color: #16A34A;
                color: #FFFFFF;
                font-weight: 700;
                font-size: 13px;
                padding: 0 22px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #15803D; }
            QPushButton:pressed { background-color: #166534; }
        """)
        self.btn_save_document.clicked.connect(self.validate_wholesale_sale)
        layout.addWidget(self.btn_save_document)

        return layout

    def toggle_touch_keypad(self):
        """Affiche ou masque le dialogue animé et déplaçable du pavé tactile."""
        if not hasattr(self, 'touch_keypad') or self.touch_keypad is None:
            self.touch_keypad = TouchKeypadDialog(parent=self)
        if self.touch_keypad.isVisible():
            self.touch_keypad.hide()
        else:
            anchor_btn = getattr(self, 'btn_keypad', None) or getattr(self, 'btn_keypad_search', None)
            if anchor_btn and anchor_btn.isVisible():
                btn_pos = anchor_btn.mapToGlobal(QPoint(0, 0))
                x = max(20, btn_pos.x() - 50)
                y = max(20, btn_pos.y() - 380)
            else:
                x = max(20, self.mapToGlobal(QPoint(0, 0)).x() + 100)
                y = max(20, self.mapToGlobal(QPoint(0, 0)).y() + 100)
            self.touch_keypad.show_animated(QPoint(x, y))

    def hideEvent(self, event):
        if hasattr(self, 'touch_keypad') and self.touch_keypad and self.touch_keypad.isVisible():
            self.touch_keypad.hide()
        super().hideEvent(event)

    def _install_shortcuts(self):
        # F1 or Ctrl+F: Focus Search Input
        self._shortcut_f1 = QShortcut(QKeySequence("F1"), self)
        self._shortcut_f1.activated.connect(self._focus_search)
        self._shortcut_ctrl_f = QShortcut(QKeySequence("Ctrl+F"), self)
        self._shortcut_ctrl_f.activated.connect(self._focus_search)

        # F2: Focus Client Selector
        self._shortcut_f2 = QShortcut(QKeySequence("F2"), self)
        self._shortcut_f2.activated.connect(self._focus_client)

        # F3: Cycle / Focus Price Tier
        self._shortcut_f3 = QShortcut(QKeySequence("F3"), self)
        self._shortcut_f3.activated.connect(self._cycle_price_tier)

        # F10: Validate and Commit Document
        self._shortcut_f10 = QShortcut(QKeySequence("F10"), self)
        self._shortcut_f10.activated.connect(self.validate_wholesale_sale)

        # Delete / Suppr: Remove selected cart line with confirmation
        self._shortcut_del = QShortcut(QKeySequence(Qt.Key_Delete), self)
        self._shortcut_del.activated.connect(self._delete_selected_cart_row)

    def _focus_search(self):
        self.search_input.setFocus()
        self.search_input.selectAll()

    def _focus_client(self):
        self.cb_client.setFocus()
        self.cb_client.showPopup()

    def _cycle_price_tier(self):
        next_idx = (self.cb_price_tier.currentIndex() + 1) % self.cb_price_tier.count()
        self.cb_price_tier.setCurrentIndex(next_idx)

    def _delete_selected_cart_row(self):
        row = self.cart_table.currentRow()
        if row >= 0:
            self._prompt_remove_row(row)

    def load_initial_data(self):
        # 1. Load Clients
        self.cb_client.blockSignals(True)
        self.cb_client.clear()
        try:
            if hasattr(self.data_manager.clients, 'get_all_clients_with_balances'):
                clients = self.data_manager.clients.get_all_clients_with_balances()
            else:
                clients = self.data_manager.clients.get_all_clients()

            for c in clients:
                cname = c.get('Client_Name')
                city = c.get('City') or ''
                display_text = f"{cname} ({city})" if city else cname
                self.cb_client.addItem(display_text, c)
        except Exception as e:
            logging.error(f"Error loading clients for wholesale: {e}")
        self.cb_client.blockSignals(False)

        if self.cb_client.count() > 0:
            self._on_client_changed(0)

        # 2. Load Inventory Batches (Stock > 0 from all locations)
        self.batches_cache = []
        self.search_map = {}
        self.barcode_map = {}
        self.product_batches_map = {}
        try:
            self.batches_cache = self.data_manager.batches.get_all_batches_with_details()
            suggestions = []
            for b in self.batches_cache:
                pid = b.get("Product_ID")
                if pid:
                    if pid not in self.product_batches_map:
                        self.product_batches_map[pid] = []
                    self.product_batches_map[pid].append(b)

                codes = self._extract_barcodes(b)
                code_str = " / ".join(codes) if codes else "-"
                lot = b.get("Lot_Number") or "---"
                qty = b.get("Quantity_Current") or 0
                sugg = f"[{code_str}] {b.get('Product_Name', '')} | Lot: {lot} | Stock: {qty} ({b.get('Location_Name', '-')})"
                suggestions.append(sugg)
                self.search_map[sugg] = b
                for c in codes:
                    norm = self._normalize_code(c)
                    if norm:
                        self.barcode_map[norm] = b

            self.completer.setModel(QStringListModel(suggestions))
        except Exception as e:
            logging.error(f"Error loading batches for wholesale: {e}")

    def _extract_barcodes(self, batch):
        codes = []
        for key in ("Internal_Barcode", "External_Barcode", "Barcode"):
            val = str(batch.get(key) or "").strip()
            if val and val.lower() not in {"none", "null", "---"} and val not in codes:
                codes.append(val)
        return codes

    def _normalize_code(self, val):
        return str(val or "").strip().lower().replace(" ", "").replace("-", "")

    def _get_current_client(self):
        idx = self.cb_client.currentIndex()
        if idx >= 0:
            return self.cb_client.itemData(idx)
        return None

    def _get_current_price_tier(self) -> str:
        if hasattr(self, 'cb_price_tier') and self.cb_price_tier.currentIndex() >= 0:
            return self.cb_price_tier.currentData() or 'Prix_1'
        client = self._get_current_client()
        return client.get('Price_Tier') if client else 'Prix_1'

    def _update_tier_warning(self, tier: str):
        if tier == 'Prix_1':
            if hasattr(self, 'btn_tier_warning'):
                self.btn_tier_warning.show()
            if hasattr(self, 'lbl_tier_warning'):
                self.lbl_tier_warning.setText("⚠️ Tarif Détail (Prix 1) appliqué à un client B2B !")
                self.lbl_tier_warning.show()
        else:
            if hasattr(self, 'btn_tier_warning'):
                self.btn_tier_warning.hide()
            if hasattr(self, 'lbl_tier_warning'):
                self.lbl_tier_warning.setText("")
                self.lbl_tier_warning.hide()

    def _on_price_tier_changed(self, index):
        tier = self._get_current_price_tier()
        self._update_tier_warning(tier)
        self._reapply_client_prices_to_cart()

    def _on_client_changed(self, index):
        client = self._get_current_client()
        if not client:
            return

        tier = client.get('Price_Tier') or 'Prix_1'
        self.cb_price_tier.blockSignals(True)
        tier_idx = self.cb_price_tier.findData(tier)
        if tier_idx >= 0:
            self.cb_price_tier.setCurrentIndex(tier_idx)
        self.cb_price_tier.blockSignals(False)

        self._update_tier_warning(tier)

        limit = float(client.get('Credit_Limit') or 0.0)
        self.lbl_credit_limit.setText(f"Plafond : {format_money(limit)} DA")

        bal = float(client.get('Current_Balance') or 0.0)
        self.lbl_current_balance.setText(f"Solde Dû : {format_money(bal)} DA")

        if bal <= 0:
            self.lbl_current_balance.setStyleSheet("background-color: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 6px; padding: 0 12px; font-size: 12px; font-weight: 700; color: #16A34A;")
        elif limit > 0 and bal <= limit:
            self.lbl_current_balance.setStyleSheet("background-color: #FEFCE8; border: 1px solid #FDE68A; border-radius: 6px; padding: 0 12px; font-size: 12px; font-weight: 700; color: #D97706;")
        else:
            self.lbl_current_balance.setStyleSheet("background-color: #FEF2F2; border: 1px solid #FECACA; border-radius: 6px; padding: 0 12px; font-size: 12px; font-weight: 700; color: #DC2626;")

        avail = max(0.0, limit - bal) if limit > 0 else 0.0
        self.lbl_available_credit.setText(f"Disponible : {format_money(avail)} DA")

        # Recalculate price tiers for existing cart rows
        self._reapply_client_prices_to_cart()

    def _on_doc_type_changed(self, index):
        doc_type = self.cb_doc_type.currentData()
        if doc_type in ('Devis', 'Bon de Commande'):
            self.btn_save_document.setText(f"Enregistrer le {doc_type} (F10)")
            self.btn_save_document.setStyleSheet("""
                QPushButton {
                    background-color: #0284C7;
                    color: #FFFFFF;
                    font-weight: 700;
                    font-size: 13px;
                    padding: 0 22px;
                    border-radius: 6px;
                    border: none;
                }
                QPushButton:hover { background-color: #0369A1; }
                QPushButton:pressed { background-color: #075985; }
            """)
        else:
            self.btn_save_document.setText("Valider & Déduire le Stock (F10)")
            self.btn_save_document.setStyleSheet("""
                QPushButton {
                    background-color: #16A34A;
                    color: #FFFFFF;
                    font-weight: 700;
                    font-size: 13px;
                    padding: 0 22px;
                    border-radius: 6px;
                    border: none;
                }
                QPushButton:hover { background-color: #15803D; }
                QPushButton:pressed { background-color: #166534; }
            """)

    def _resolve_price_tier(self, batch, price_tier: str) -> float:
        """Résout le prix unitaire HT selon le palier tarifaire du client."""
        p1 = float(batch.get('Selling_Price_HT') or 0.0)
        p2 = float(batch.get('Selling_Price_HT_2') or 0.0)
        p3 = float(batch.get('Selling_Price_HT_3') or 0.0)
        p4 = float(batch.get('Selling_Price_HT_4') or 0.0)

        if price_tier == 'Prix_4':
            return p4 or p3 or p2 or p1 or 0.0
        elif price_tier == 'Prix_3':
            return p3 or p2 or p1 or 0.0
        elif price_tier == 'Prix_2':
            return p2 or p1 or 0.0
        else:
            return p1 or 0.0

    def _reapply_client_prices_to_cart(self):
        tier = self._get_current_price_tier()

        for row in range(self.cart_table.rowCount()):
            item_prod = self.cart_table.item(row, 2)
            if not item_prod:
                continue
            batch = item_prod.data(Qt.UserRole)
            if not batch:
                continue

            cell_sample = self.cart_table.cellWidget(row, 8)
            chk_sample = None
            if cell_sample:
                chk_sample = cell_sample.findChild(QCheckBox) if not isinstance(cell_sample, QCheckBox) else cell_sample
            if chk_sample and chk_sample.isChecked():
                continue

            resolved_p = self._resolve_price_tier(batch, tier)
            spin_price = self.cart_table.cellWidget(row, 7)
            if spin_price:
                spin_price.setValue(resolved_p)
        self.calculate_totals()

    def _on_quick_qty_return(self):
        self._commit_pending_item()

    def _commit_pending_item(self):
        if hasattr(self, 'pending_batch') and self.pending_batch:
            batch = self.pending_batch
            qty = self.spin_quick_qty.value() if hasattr(self, 'spin_quick_qty') else 1.0
            discount = self.spin_quick_discount.value() if hasattr(self, 'spin_quick_discount') else 0.0
            self.add_batch_to_cart(batch, qty=qty, discount=discount)
            self.pending_batch = None
            self.search_input.clear()
            self.search_input.setFocus()
        else:
            self._on_search_return()

    def _on_search_selected(self, text):
        batch = self.search_map.get(text)
        if batch:
            self._handle_product_found(batch)

    def _on_search_return(self):
        text = self.search_input.text().strip()
        if not text:
            return

        batch = self.search_map.get(text)
        if not batch:
            norm = self._normalize_code(text)
            batch = self.barcode_map.get(norm)

        if not batch:
            lowered = text.lower()
            matches = [
                b for b in self.batches_cache
                if lowered in str(b.get("Product_Name", "")).lower()
                or lowered in str(b.get("Lot_Number", "")).lower()
            ]
            if len(matches) == 1:
                batch = matches[0]
            elif len(matches) > 1:
                first_pid = matches[0].get('Product_ID')
                if all(b.get('Product_ID') == first_pid for b in matches):
                    self._open_lot_split_dialog(matches[0].get('Product_Name', ''), matches, requested_qty=1.0)
                    return
                else:
                    batch = matches[0]

        if batch:
            self._handle_product_found(batch)
        else:
            QMessageBox.warning(self, "Recherche", "Aucun produit ou lot correspondant trouvé.")
            self.search_input.selectAll()
            self.search_input.setFocus()

    def _handle_product_found(self, batch):
        """Ajoute immédiatement le produit au panier sur scan ou ouvre la répartition multi-lots."""
        pid = batch.get('Product_ID')
        all_batches = self.product_batches_map.get(pid, [])
        if len(all_batches) > 1:
            self._open_lot_split_dialog(batch.get('Product_Name', ''), all_batches, requested_qty=1.0)
        else:
            self.add_batch_to_cart(batch, qty=1.0, discount=0.0)
            self.search_input.clear()
            self.pending_batch = None
            self.search_input.setFocus()

    def _open_lot_split_dialog(self, product_name, batches, requested_qty=1.0):
        tier = self._get_current_price_tier()
        dlg = MultiLotSelectionDialog(
            parent=self,
            product_name=product_name,
            batches=batches,
            requested_qty=requested_qty,
            price_tier=tier,
            resolve_price_fn=self._resolve_price_tier
        )
        if dlg.exec() and dlg.allocations:
            for b, qty in dlg.allocations:
                self.add_batch_to_cart(b, qty=qty, discount=0.0)
            self.search_input.clear()
            self.pending_batch = None
            self.search_input.setFocus()

    def _open_split_from_cart_row(self, batch):
        if not batch:
            return
        pid = batch.get('Product_ID')
        pbatches = self.product_batches_map.get(pid, [])
        if not pbatches:
            pbatches = [batch]
        req_qty = 1.0
        batch_id = batch.get('Batch_ID')
        for r in range(self.cart_table.rowCount()):
            item_p = self.cart_table.item(r, 2)
            existing = item_p.data(Qt.UserRole) if item_p else None
            if existing and existing.get('Batch_ID') == batch_id:
                spin_q = self.cart_table.cellWidget(r, 9)
                if spin_q:
                    req_qty = spin_q.value()
                break
        self._open_lot_split_dialog(batch.get('Product_Name', ''), pbatches, requested_qty=req_qty)

    def _prompt_remove_row(self, row_or_btn):
        if isinstance(row_or_btn, int):
            row = row_or_btn
        else:
            row = -1
            for r in range(self.cart_table.rowCount()):
                cell_w = self.cart_table.cellWidget(r, 0)
                if cell_w and (cell_w == row_or_btn or cell_w.isAncestorOf(row_or_btn)):
                    row = r
                    break
        if row < 0 or row >= self.cart_table.rowCount():
            return

        item_p = self.cart_table.item(row, 2)
        pname = item_p.text() if item_p else "ce produit"
        item_l = self.cart_table.item(row, 3)
        lot = item_l.text() if item_l else "-"

        res = QMessageBox.question(
            self,
            "Supprimer la Ligne",
            f"Êtes-vous sûr de vouloir retirer '{pname}' (Lot: {lot}) du panier ?",
            QMessageBox.Yes | QMessageBox.No
        )
        if res == QMessageBox.Yes:
            self.cart_table.removeRow(row)
            self.calculate_totals()

    def add_batch_to_cart(self, batch, qty=1.0, discount=0.0, is_sample=False):
        # Check if already in cart
        batch_id = batch.get('Batch_ID')
        for r in range(self.cart_table.rowCount()):
            item_p = self.cart_table.item(r, 2)
            existing = item_p.data(Qt.UserRole) if item_p else None
            if existing and existing.get('Batch_ID') == batch_id:
                spin_q = self.cart_table.cellWidget(r, 9)
                if spin_q:
                    spin_q.setValue(spin_q.value() + qty)
                self.calculate_totals()
                return

        row = self.cart_table.rowCount()
        self.cart_table.insertRow(row)

        tier = self._get_current_price_tier()
        unit_price = self._resolve_price_tier(batch, tier)
        max_stock = float(batch.get('Quantity_Current') or batch.get('Current_Stock') or 0.0)

        # 0. Actions Container (Delete 🗑️ + Edit/Split Lots 📦)
        action_widget = QWidget()
        action_widget.setStyleSheet("background: transparent;")
        action_layout = QHBoxLayout(action_widget)
        action_layout.setContentsMargins(4, 4, 4, 4)
        action_layout.setSpacing(6)
        action_layout.setAlignment(Qt.AlignCenter)

        btn_del = QPushButton()
        btn_del.setIcon(get_trash_icon(15))
        btn_del.setIconSize(QSize(15, 15))
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.setFixedSize(32, 32)
        btn_del.setToolTip("Supprimer cette ligne du panier (Suppr)")
        btn_del.setStyleSheet("""
            QPushButton {
                background-color: #FEE2E2;
                border: 1px solid #FECACA;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #FCA5A5;
                border-color: #EF4444;
            }
            QPushButton:pressed {
                background-color: #DC2626;
            }
        """)
        btn_del.clicked.connect(lambda _, b=btn_del: self._prompt_remove_row(b))
        action_layout.addWidget(btn_del)

        btn_split = QPushButton()
        btn_split.setIcon(get_edit_lots_icon(15))
        btn_split.setIconSize(QSize(15, 15))
        btn_split.setCursor(Qt.PointingHandCursor)
        btn_split.setFixedSize(32, 32)
        btn_split.setToolTip("Modifier / Répartir sur d'autres lots (Multi-Lots)")
        btn_split.setStyleSheet("""
            QPushButton {
                background-color: #E6F4F1;
                border: 1px solid #BCE3DC;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #C1E7E0;
                border-color: #0E7471;
            }
            QPushButton:pressed {
                background-color: #0E7471;
            }
        """)
        btn_split.clicked.connect(lambda _, b=batch: self._open_split_from_cart_row(b))
        action_layout.addWidget(btn_split)

        self.cart_table.setCellWidget(row, 0, action_widget)

        # 1. Barcode
        codes = self._extract_barcodes(batch)
        item_bc = QTableWidgetItem(codes[0] if codes else "-")
        item_bc.setTextAlignment(Qt.AlignCenter)
        item_bc.setForeground(QColor("#1F2937"))
        self.cart_table.setItem(row, 1, item_bc)

        # 2. Product Name
        item_name = QTableWidgetItem(batch.get('Product_Name', ''))
        item_name.setData(Qt.UserRole, batch)
        item_name.setForeground(QColor("#1F2937"))
        item_name.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        self.cart_table.setItem(row, 2, item_name)

        # 3. Lot
        item_lot = QTableWidgetItem(str(batch.get('Lot_Number') or '---'))
        item_lot.setTextAlignment(Qt.AlignCenter)
        item_lot.setForeground(QColor("#1F2937"))
        self.cart_table.setItem(row, 3, item_lot)

        # 4. Expiry with badges
        exp = str(batch.get('Expiry_Date') or '')
        item_exp = QTableWidgetItem(exp if exp else "---")
        item_exp.setTextAlignment(Qt.AlignCenter)
        if exp and exp not in ("None", "null", "---"):
            try:
                exp_date = datetime.strptime(exp[:10], "%Y-%m-%d").date()
                days_left = (exp_date - datetime.now().date()).days
                if days_left < 0:
                    item_exp.setForeground(QColor("#DC2626"))
                    item_exp.setBackground(QColor("#FEE2E2"))
                    item_exp.setFont(QFont("Segoe UI", 9, QFont.Bold))
                    item_exp.setToolTip(f"Lot périmé depuis {abs(days_left)} jour(s) !")
                elif days_left <= 60:
                    item_exp.setForeground(QColor("#D97706"))
                    item_exp.setBackground(QColor("#FEF3C7"))
                    item_exp.setFont(QFont("Segoe UI", 9, QFont.Bold))
                    item_exp.setToolTip(f"Péremption proche : reste {days_left} jour(s)")
                else:
                    item_exp.setForeground(QColor("#1F2937"))
            except Exception:
                item_exp.setForeground(QColor("#1F2937"))
        else:
            item_exp.setForeground(QColor("#64748B"))
        self.cart_table.setItem(row, 4, item_exp)

        # 5. Location
        loc = batch.get('Location_Name') or '-'
        item_loc = QTableWidgetItem(loc)
        item_loc.setTextAlignment(Qt.AlignCenter)
        item_loc.setForeground(QColor("#1F2937"))
        self.cart_table.setItem(row, 5, item_loc)

        # 6. Stock Dispo (Right aligned)
        item_stk = QTableWidgetItem(f"{max_stock:g}")
        item_stk.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        item_stk.setFont(QFont("Segoe UI", 9, QFont.Bold))
        if max_stock <= 0:
            item_stk.setForeground(QColor("#DC2626"))
            item_stk.setBackground(QColor("#FEE2E2"))
        else:
            item_stk.setForeground(QColor("#1F2937"))
        self.cart_table.setItem(row, 6, item_stk)

        # 7. Unit Price HT (Editable SpinBox)
        spin_p = QDoubleSpinBox()
        spin_p.setRange(0.0, 99999999.0)
        spin_p.setValue(0.0 if is_sample else unit_price)
        spin_p.setDecimals(2)
        spin_p.setButtonSymbols(QDoubleSpinBox.NoButtons)
        spin_p.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        spin_p.setFixedHeight(34)
        spin_p.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 4px;
                font-weight: 700;
                font-size: 12px;
                color: #1F2937;
                padding: 2px 6px;
            }
            QDoubleSpinBox:focus {
                border: 1.5px solid #0E7471;
                background-color: #FFFFFF;
            }
        """)
        spin_p.valueChanged.connect(self.calculate_totals)
        self.cart_table.setCellWidget(row, 7, spin_p)

        # 8. Échantillon / Gratuité Checkbox
        chk_sample_widget = QWidget()
        chk_sample_widget.setStyleSheet("background: transparent;")
        chk_sample_lay = QHBoxLayout(chk_sample_widget)
        chk_sample_lay.setContentsMargins(0, 0, 0, 0)
        chk_sample_lay.setAlignment(Qt.AlignCenter)
        chk_sample = QCheckBox()
        chk_sample.setChecked(is_sample)
        chk_sample.setToolTip("Cocher s'il s'agit d'un échantillon promotionnel ou d'une gratuité commerciale (Prix 0.00 DA autorisé)")
        chk_sample.toggled.connect(self.calculate_totals)
        chk_sample_lay.addWidget(chk_sample)
        self.cart_table.setCellWidget(row, 8, chk_sample_widget)

        # 9. Qty Sold (SpinBox with stepper buttons)
        spin_q = QDoubleSpinBox()
        spin_q.setRange(0.01, max_stock if max_stock > 0 else 999999.0)
        spin_q.setValue(min(qty, max_stock if max_stock > 0 else qty))
        spin_q.setDecimals(2)
        spin_q.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        spin_q.setFixedHeight(34)
        spin_q.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #FFFFFF;
                border: 1px solid #0E7471;
                border-radius: 4px;
                font-weight: 700;
                font-size: 12px;
                color: #0E7471;
                padding: 2px 6px;
            }
            QDoubleSpinBox:focus {
                border: 2px solid #0E7471;
                background-color: #E6F4F1;
            }
            QDoubleSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 16px;
                border-left: 1px solid #BCE3DC;
                border-bottom: 1px solid #BCE3DC;
                background-color: #F8FAFC;
                border-top-right-radius: 3px;
            }
            QDoubleSpinBox::up-button:hover {
                background-color: #E6F4F1;
            }
            QDoubleSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 16px;
                border-left: 1px solid #BCE3DC;
                background-color: #F8FAFC;
                border-bottom-right-radius: 3px;
            }
            QDoubleSpinBox::down-button:hover {
                background-color: #E6F4F1;
            }
        """)
        spin_q.valueChanged.connect(self.calculate_totals)
        self.cart_table.setCellWidget(row, 9, spin_q)

        # 10. Discount % (SpinBox)
        spin_d = QDoubleSpinBox()
        spin_d.setRange(0.0, 100.0)
        spin_d.setValue(discount)
        spin_d.setDecimals(2)
        spin_d.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        spin_d.setSuffix(" %")
        spin_d.setFixedHeight(34)
        spin_d.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #FFFFFF;
                border: 1px solid #D97706;
                border-radius: 4px;
                font-weight: 700;
                font-size: 12px;
                color: #B45309;
                padding: 2px 6px;
            }
            QDoubleSpinBox:focus {
                border: 2px solid #D97706;
                background-color: #FFFBEB;
            }
            QDoubleSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 16px;
                border-left: 1px solid #FDE68A;
                border-bottom: 1px solid #FDE68A;
                background-color: #FFFBEB;
                border-top-right-radius: 3px;
            }
            QDoubleSpinBox::up-button:hover {
                background-color: #FEF3C7;
            }
            QDoubleSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 16px;
                border-left: 1px solid #FDE68A;
                background-color: #FFFBEB;
                border-bottom-right-radius: 3px;
            }
            QDoubleSpinBox::down-button:hover {
                background-color: #FEF3C7;
            }
        """)
        spin_d.valueChanged.connect(self.calculate_totals)
        self.cart_table.setCellWidget(row, 10, spin_d)

        # 11. Total HT
        item_tht = QTableWidgetItem("0.00 DA")
        item_tht.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        item_tht.setForeground(QColor("#1F2937"))
        item_tht.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        self.cart_table.setItem(row, 11, item_tht)

        # 12. TVA %
        tva_pct = float(batch.get('Selling_TVA_Percent') or 0.0)
        item_tva = QTableWidgetItem(f"{tva_pct:.1f}%")
        item_tva.setData(Qt.UserRole, tva_pct)
        item_tva.setTextAlignment(Qt.AlignCenter)
        item_tva.setForeground(QColor("#475569"))
        self.cart_table.setItem(row, 12, item_tva)

        # 13. Total TTC
        item_ttc = QTableWidgetItem("0.00 DA")
        item_ttc.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        item_ttc.setFont(QFont("Segoe UI", 9, QFont.Bold))
        item_ttc.setForeground(QColor("#0E7471"))
        self.cart_table.setItem(row, 13, item_ttc)

        self.calculate_totals()

    def clear_cart(self):
        self.cart_table.setRowCount(0)
        self.calculate_totals()

    def calculate_totals(self):
        grand_ht = 0.0
        grand_remise = 0.0
        grand_tva = 0.0
        grand_ttc = 0.0

        for r in range(self.cart_table.rowCount()):
            spin_p = self.cart_table.cellWidget(r, 7)
            cell_sample = self.cart_table.cellWidget(r, 8)
            spin_q = self.cart_table.cellWidget(r, 9)
            spin_d = self.cart_table.cellWidget(r, 10)
            item_tva = self.cart_table.item(r, 12)

            if not (spin_p and spin_q and spin_d):
                continue

            is_sample = False
            if cell_sample:
                box = cell_sample.findChild(QCheckBox) if not isinstance(cell_sample, QCheckBox) else cell_sample
                if box and box.isChecked():
                    is_sample = True

            if is_sample:
                spin_p.blockSignals(True)
                spin_p.setValue(0.0)
                spin_p.setEnabled(False)
                spin_p.blockSignals(False)
                spin_d.blockSignals(True)
                spin_d.setValue(0.0)
                spin_d.setEnabled(False)
                spin_d.blockSignals(False)
                price = 0.0
                remise_pct = 0.0
            else:
                spin_p.setEnabled(True)
                spin_d.setEnabled(True)
                price = spin_p.value()
                remise_pct = spin_d.value()

            qty = spin_q.value()
            tva_pct = float(item_tva.data(Qt.UserRole) or 0.0) if item_tva else 0.0

            raw_ht = price * qty
            discount_amount = raw_ht * (remise_pct / 100.0)
            net_ht = raw_ht - discount_amount
            tva_amount = net_ht * (tva_pct / 100.0)
            line_ttc = net_ht + tva_amount

            grand_ht += net_ht
            grand_remise += discount_amount
            grand_tva += tva_amount
            grand_ttc += line_ttc

            # Update row cells with right-aligned formatted text
            item_tht = self.cart_table.item(r, 11)
            if item_tht:
                item_tht.setText(f"{format_money(net_ht)} DA")
            item_ttc = self.cart_table.item(r, 13)
            if item_ttc:
                item_ttc.setText(f"{format_money(line_ttc)} DA")

        self.lbl_summary_ht.setText(f"Total HT : {format_money(grand_ht)} DA")
        self.lbl_summary_remise.setText(f"Remise : {format_money(grand_remise)} DA")
        self.lbl_summary_tva.setText(f"TVA : {format_money(grand_tva)} DA")
        self.lbl_summary_net_ttc.setText(f"NET À PAYER : {format_money(grand_ttc)} DA")

    def _collect_cart_items(self):
        items = []
        for r in range(self.cart_table.rowCount()):
            item_p = self.cart_table.item(r, 2)
            if not item_p:
                continue
            batch = item_p.data(Qt.UserRole)
            if not batch:
                continue

            spin_p = self.cart_table.cellWidget(r, 7)
            cell_sample = self.cart_table.cellWidget(r, 8)
            spin_q = self.cart_table.cellWidget(r, 9)
            spin_d = self.cart_table.cellWidget(r, 10)
            item_tva = self.cart_table.item(r, 12)

            is_sample = False
            if cell_sample:
                box = cell_sample.findChild(QCheckBox) if not isinstance(cell_sample, QCheckBox) else cell_sample
                if box and box.isChecked():
                    is_sample = True

            tva_pct = float(item_tva.data(Qt.UserRole) or 0.0) if item_tva else 0.0

            items.append({
                'batch_id': batch['Batch_ID'],
                'product_id': batch['Product_ID'],
                'product_name': batch.get('Product_Name', ''),
                'lot_number': batch.get('Lot_Number', ''),
                'expiry_date': str(batch.get('Expiry_Date') or ''),
                'qty_sold': spin_q.value(),
                'unit_price_ht': 0.0 if is_sample else spin_p.value(),
                'discount_percent': 0.0 if is_sample else spin_d.value(),
                'tva_percent': tva_pct,
                'is_sample': is_sample
            })
        return items

    def _get_current_user_id(self):
        try:
            main_window = self.window()
            user = getattr(main_window, 'current_user', None)
            if isinstance(user, dict):
                return user.get('User_ID') or user.get('id')
        except Exception:
            pass
        return None

    def validate_wholesale_sale(self):
        client = self._get_current_client()
        if not client:
            QMessageBox.warning(self, "Client", "Veuillez sélectionner un client B2B.")
            return

        client_id = client['Client_ID']
        cart_items = self._collect_cart_items()
        if not cart_items:
            QMessageBox.warning(self, "Panier", "Le panier est vide. Veuillez ajouter des produits.")
            return

        # 1. Zero-price entry guard
        for it in cart_items:
            if it['unit_price_ht'] <= 0.0 and not it.get('is_sample', False):
                QMessageBox.critical(
                    self,
                    "Prix Unitaire Nul Interdit (Bloquant)",
                    f"Le produit '{it.get('product_name')}' (Lot: {it.get('lot_number', '-')}) a un prix de vente unitaire HT nul (0,00 DA).\n\n"
                    "Conformément aux règles comptables et fiscales de vente en gros, un prix nul est bloquant.\n\n"
                    "👉 Veuillez renseigner un prix unitaire valide, ou cochez 'Échantillon' si ce produit est offert gracieusement."
                )
                return

        doc_type = self.cb_doc_type.currentData()
        order_date_str = self.date_order.date().toString("yyyy-MM-dd")
        due_date_str = self.date_due.date().toString("yyyy-MM-dd")
        payment_method = self.cb_payment_method.currentData()

        # 2. Credit Limit & Overdue Risk Hard Lock
        limit = float(client.get('Credit_Limit') or 0.0)
        curr_bal = float(client.get('Current_Balance') or 0.0)
        grand_ttc = sum(
            (it['qty_sold'] * it['unit_price_ht'] * (1 - it['discount_percent'] / 100.0)) * (1 + it['tva_percent'] / 100.0)
            for it in cart_items
        )
        projected_bal = curr_bal + grand_ttc

        override_notes = ""
        if payment_method == 'Credit' and limit > 0 and projected_bal > limit:
            diff = projected_bal - limit
            dlg = SupervisorOverrideDialog(
                parent=self,
                data_manager=self.data_manager,
                client_name=client.get('Client_Name', ''),
                credit_limit=limit,
                current_balance=curr_bal,
                document_amount=grand_ttc,
                projected_balance=projected_bal,
                excess_amount=diff
            )
            if not dlg.exec() or not dlg.approved:
                # Blocked without supervisor clearance
                return

            info = dlg.get_override_info()
            sup_user = info.get('supervisor_user') or {}
            sup_name = sup_user.get('Username') or sup_user.get('Full_Name') or 'Superviseur'
            override_notes = f"[DÉROGATION CRÉDIT : Autorisée par {sup_name} | Motif: {info['reason']}]"

        # Execute Document Creation
        doc_notes = f"{override_notes}".strip() or None
        success, result = self.data_manager.sales.create_wholesale_document(
            client_id=client_id,
            doc_type=doc_type,
            order_date=order_date_str,
            due_date=due_date_str,
            cart_items=cart_items,
            payment_method=payment_method,
            notes=doc_notes,
            user_id=self._get_current_user_id()
        )

        if not success:
            QMessageBox.critical(self, "Erreur", f"Échec de l'enregistrement du document :\n{result.get('message')}")
            return

        doc_no = result.get('doc_no')
        invoice_id = result.get('invoice_id')
        deducted = result.get('stock_deducted')

        msg = f"Document '{doc_no}' ({doc_type}) enregistré avec succès !"
        if deducted:
            msg += "\n\n• Le stock correspondant a été déduit atomiquement."
        else:
            msg += "\n\n• Document enregistré en brouillon (aucun mouvement de stock)."

        if override_notes:
            msg += f"\n\n• {override_notes}"

        # Prompt for PDF generation
        reply = QMessageBox.information(
            self,
            "Validation Réussie",
            f"{msg}\n\nSouhaitez-vous générer et imprimer le document PDF (A4) maintenant ?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            export_wholesale_document_pdf(
                self.data_manager,
                invoice_id=invoice_id,
                doc_no=doc_no,
                doc_type=doc_type,
                client=client,
                cart_items=cart_items,
                order_date_str=order_date_str,
                due_date_str=due_date_str,
                parent_widget=self
            )

        self.clear_cart()
        self.load_initial_data()

    def _create_quick_client(self):
        dlg = ClientDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            if data:
                cid = self.data_manager.clients.add_client(**data)
                if cid:
                    self.load_initial_data()
                    for idx in range(self.cb_client.count()):
                        c = self.cb_client.itemData(idx)
                        if isinstance(c, dict) and c.get('Client_ID') == cid:
                            self.cb_client.setCurrentIndex(idx)
                            break

    def _open_client_statement(self):
        client = self._get_current_client()
        if not client:
            QMessageBox.warning(self, "Client", "Veuillez sélectionner un client B2B.")
            return
        dlg = ClientStatementDialog(self.data_manager, client['Client_ID'], self)
        dlg.exec()
