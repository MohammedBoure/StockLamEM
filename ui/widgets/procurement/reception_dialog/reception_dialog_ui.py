"""
reception_dialog_ui.py
----------------------
Mixin يحتوي على دوال بناء الواجهة:
  - create_widgets()
  - init_ui()
"""
import qtawesome as qta
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QDateEdit,
    QTreeWidget, QTreeWidgetItem, QSpinBox, QPushButton,
    QFrame, QHeaderView, QCheckBox, QCompleter, QAbstractItemView,
    QDoubleSpinBox,QTableWidget
)
from PySide6.QtCore import Qt, QDate, QLocale
from PySide6.QtGui import QFont, QPixmap, QPainter, QBrush, QPen, QColor, QIcon

from .auto_select_widgets import AutoSelectLineEdit, AutoSelectSpinBox, AutoSelectDoubleSpinBox
from ..location_tree_combo import LocationTreeComboBox


class ReceptionDialogUIMixin:
    """Mixin يُضاف إلى ReceptionDialog لبناء الواجهة فقط."""

    def create_widgets(self):
        self.invoice_ref = AutoSelectLineEdit()
        self.invoice_ref.setPlaceholderText("Ex: FACT-2024-001")

        self.bl_ref = AutoSelectLineEdit()
        self.bl_ref.setPlaceholderText("Ex: BL-2024-001")

        self.btn_validate_ref = QPushButton(" Valider & Verrouiller")
        self.btn_validate_ref.setIcon(qta.icon('fa5s.check-circle', color='white'))
        self.btn_validate_ref.setCursor(Qt.PointingHandCursor)
        self.btn_validate_ref.setToolTip("Valider les références pour commencer")
        self.btn_validate_ref.setStyleSheet("""
            QPushButton {
                background-color: #2980b9;
                color: white;
                font-weight: bold;
                padding: 6px 15px;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #3498db; }
            QPushButton:disabled {
                background-color: #27ae60;
                color: white;
                border: 1px solid #2ecc71;
            }
        """)

        self.btn_unlock_header = QPushButton("")
        self.btn_unlock_header.setIcon(qta.icon('fa5s.pen', color='white'))
        self.btn_unlock_header.setToolTip("Modifier les informations de l'en-tête")
        self.btn_unlock_header.setCursor(Qt.PointingHandCursor)
        self.btn_unlock_header.setVisible(False)
        self.btn_unlock_header.setFixedSize(30, 30)
        self.btn_unlock_header.setStyleSheet("""
            QPushButton {
                background-color: #f39c12;
                color: white;
                border-radius: 4px;
                padding: 4px;
            }
            QPushButton:hover { background-color: #d35400; }
        """)

        self.reception_date = QDateEdit(QDate.currentDate())
        self.reception_date.setCalendarPopup(True)

        self.cb_supplier = QComboBox()
        self.cb_supplier.setEditable(True)
        self.cb_supplier.setInsertPolicy(QComboBox.NoInsert)
        self.cb_supplier.setMinimumWidth(220)
        sup_completer = self.cb_supplier.completer()
        sup_completer.setFilterMode(Qt.MatchContains)
        sup_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.cb_supplier.addItem("--- Choisir un Fournisseur ---", None)
        suppliers_list = []
        sup_mgr = getattr(self.manager, 'suppliers', None)
        if not sup_mgr and self.parent() and hasattr(self.parent(), 'manager'):
            sup_mgr = getattr(self.parent().manager, 'suppliers', None)
        if sup_mgr and hasattr(sup_mgr, 'get_all_suppliers'):
            try:
                suppliers_list = sup_mgr.get_all_suppliers() or []
            except Exception:
                suppliers_list = []
        for s in suppliers_list:
            s_id = s.get('Supplier_ID')
            s_name = s.get('Supplier_Name')
            if s_id is not None and s_name:
                self.cb_supplier.addItem(s_name, s_id)
        init_sup_id = self.po_data.get('Supplier_ID')
        init_sup_name = self.po_data.get('Supplier_Name')
        if init_sup_id is not None:
            idx_sup = self.cb_supplier.findData(init_sup_id)
            if idx_sup < 0 and init_sup_name:
                self.cb_supplier.addItem(init_sup_name, init_sup_id)
                idx_sup = self.cb_supplier.findData(init_sup_id)
            if idx_sup >= 0:
                self.cb_supplier.setCurrentIndex(idx_sup)
        self.cb_supplier.setVisible(not bool(self.po_data.get('PO_ID')))

        self.cb_product = QComboBox()
        self.cb_product.setEditable(True)
        self.cb_product.setInsertPolicy(QComboBox.NoInsert)
        completer = self.cb_product.completer()
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.popup().setMinimumWidth(420)

        all_products = []
        if hasattr(self, 'manager') and hasattr(self.manager, 'products'):
            try:
                all_products = self.manager.products.get_all_products()
            except Exception:
                pass
        elif hasattr(self, 'manager') and hasattr(self.manager, 'db'):
            try:
                from database.product_manager import ProductManager
                all_products = ProductManager(self.manager.db).get_all_products()
            except Exception:
                pass
        if not all_products:
            tab_parent = self.parent()
            if tab_parent and hasattr(tab_parent, 'manager'):
                if hasattr(tab_parent.manager, 'products'):
                    all_products = tab_parent.manager.products.get_all_products()
                elif hasattr(tab_parent.manager, 'db'):
                    try:
                        from database.product_manager import ProductManager
                        all_products = ProductManager(tab_parent.manager.db).get_all_products()
                    except Exception:
                        pass

        self.cb_product.addItem("", None)
        for p in all_products:
            brand = p.get('Manuf_Name') or "---"
            ref = p.get('All_Refs') or p.get('Primary_Ref') or p.get('Manuf_Cat_No') or p.get('Reference') or p.get('Product_Code') or p.get('Barcode') or "---"
            self.cb_product.addItem(f"{p['Product_Name']}  |  Réf: {ref}  ({brand})", p)

        # Product Color / Finish
        self.cb_color = QComboBox()
        self.cb_color.setEditable(True)
        self.cb_color.setInsertPolicy(QComboBox.NoInsert)
        if self.cb_color.completer():
            self.cb_color.completer().setFilterMode(Qt.MatchContains)
        self.cb_color.setLineEdit(AutoSelectLineEdit())
        if self.cb_color.lineEdit():
            self.cb_color.lineEdit().setPlaceholderText("Couleur / Finition")

        self.lbl_color_swatch = QLabel()
        self.lbl_color_swatch.setFixedSize(26, 24)
        self.lbl_color_swatch.setStyleSheet(
            "background-color: #CBD5E1; border: 1px solid #94A3B8; border-radius: 4px;"
        )
        self.lbl_color_swatch.setToolTip("Aperçu visuel de la couleur")
        if hasattr(self, '_load_colors'):
            self._load_colors()

        self.cb_unit_type = QComboBox()
        self.inp_qty = AutoSelectSpinBox()
        self.inp_qty.setRange(0, 999999)
        self.inp_lot = AutoSelectLineEdit()
        self.inp_lot.setPlaceholderText("Optionnel")
        self.inp_lot.setVisible(False)
        self.inp_expiry = QDateEdit(QDate.currentDate().addYears(2))
        self.inp_expiry.setVisible(False)
        self.cb_location = LocationTreeComboBox(self.location_manager)

        self.inp_price = AutoSelectDoubleSpinBox()
        self.inp_price.setRange(0, 99999999.99)
        self.inp_price.setDecimals(2)
        self.inp_price.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.inp_price.setLocale(QLocale.c())
        self.inp_price.setGroupSeparatorShown(True)
        
        self.inp_price_ttc = AutoSelectDoubleSpinBox()
        self.inp_price_ttc.setRange(0, 99999999.99)
        self.inp_price_ttc.setDecimals(2)
        self.inp_price_ttc.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.inp_price_ttc.setLocale(QLocale.c())
        self.inp_price_ttc.setGroupSeparatorShown(True)

        self.inp_remise = AutoSelectDoubleSpinBox()
        self.inp_remise.setRange(0, 99999999.99)
        self.inp_remise.setDecimals(2)
        self.inp_remise.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.inp_remise.setLocale(QLocale.c())
        self.inp_remise.setGroupSeparatorShown(True)

        self.cb_remise_type = QComboBox()
        self.cb_remise_type.addItems(["%", "DZD"])

        self.inp_bon_remise = QDoubleSpinBox()
        self.inp_bon_remise.setRange(0, 999999999)
        self.inp_bon_remise.setDecimals(2)
        self.inp_bon_remise.setMinimumWidth(95)
        self.inp_bon_remise.setToolTip("Remise globale appliquée sur l'ensemble du bon")
        self.cb_bon_remise_type = QComboBox()
        self.cb_bon_remise_type.addItems(["%", "DZD"])
        self.cb_bon_remise_type.setFixedWidth(60)

        self.chk_tva = QCheckBox("TVA 19%")
        self.chk_tva.setChecked(False)
        self.chk_tva.setVisible(False)
        self.inp_observation = AutoSelectLineEdit()
        self.lbl_item_ttc = QLabel("Total : 0,00 DA")
        self.lbl_conversion_logic = QLabel("")

        self.btn_add    = QPushButton(qta.icon('fa5s.plus',      color='white'), " Ajouter")
        self.btn_modify = QPushButton(qta.icon('fa5s.edit',      color='white'), " Modifier")
        self.btn_delete = QPushButton(qta.icon('fa5s.trash-alt', color='white'), " Supprimer")
        self.btn_print  = QPushButton(qta.icon('fa5s.print',     color='white'), " Imprimer")

        self.btn_print_all = QPushButton(qta.icon('fa5s.copy', color='white'), " Imprimer Tout")
        self.btn_print_all.setToolTip("Imprimer les étiquettes pour tous les articles de la liste")
        self.btn_print_all.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold;")

        # إعداد الجدول
        self.table_items = QTableWidget() 
        self.table_items.setColumnCount(15)
        
        headers = [
            "Produit", "Couleur", "Code", "Unité", "Qté", "Lot", "Date Exp",
            "Stock", "Prix U", "Remise", "Prix HT", "TVA (DA)",
            "P.U TTC", "Total TTC", "Meta"
        ]
        
        self.table_items.setHorizontalHeaderLabels(headers)
        
        self.table_items.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_items.setAlternatingRowColors(True)
        self.table_items.setSortingEnabled(True)
        
        # --- الإصلاح هنا: استخدام horizontalHeader() بدلاً من header() ---
        h_header = self.table_items.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.ResizeToContents)
        h_header.setSectionResizeMode(0, QHeaderView.Stretch) # تمديد عمود اسم المنتج
        
        self.table_items.setColumnHidden(5, True)   # Masquer Lot (non requis)
        self.table_items.setColumnHidden(6, True)   # Masquer Date Exp (non requise)
        self.table_items.setColumnHidden(11, True)  # Masquer TVA (non requise)
        self.table_items.setColumnHidden(12, True)  # Masquer P.U TTC redondant
        self.table_items.setColumnHidden(14, True)  # إخفاء عمود Meta

        self.lbl_total_ht     = QLabel("0,00 DA")
        self.lbl_total_remise = QLabel("0,00 DA")
        self.lbl_total_tva    = QLabel("0,00 DA")
        self.lbl_total_tva.setVisible(False)
        self.lbl_total_ttc    = QLabel("0,00 DA")
        self.lbl_conversion_logic.setStyleSheet(
            "color: #7f8c8d; font-style: italic; font-size: 12px;"
        )

    def init_ui(self):
        main_layout = QVBoxLayout(self.form_widget)
        main_layout.setContentsMargins(10, 5, 10, 5)
        main_layout.setSpacing(8)

        is_direct_bl = not bool(self.po_data.get('PO_ID'))
        if is_direct_bl:
            header_text = "<b>Mode:</b> Bon de Livraison Direct (Sans Bon de Commande)"
            border_color = "#27ae60"
        else:
            header_text = (
                f"<b>Fournisseur:</b> {self.po_data.get('Supplier_Name', 'N/A')} "
                f"| <b>N°BC:</b> #{self.po_data.get('PO_ID', 'N/A')}"
            )
            border_color = "#3498db"

        header_info = QLabel(header_text)
        header_info.setStyleSheet(
            f"font-size: 14px; color: #2c3e50; background: #ecf0f1; "
            f"padding: 8px; border-radius: 4px; border-left: 4px solid {border_color};"
        )
        main_layout.addWidget(header_info)

        top_layout = QHBoxLayout()
        if is_direct_bl:
            top_layout.addWidget(QLabel("<b>Fournisseur:</b>"))
            top_layout.addWidget(self.cb_supplier)
            top_layout.addSpacing(10)
        top_layout.addWidget(QLabel("<b>Date:</b>"))
        top_layout.addWidget(self.reception_date)
        top_layout.addSpacing(15)
        top_layout.addWidget(QLabel("<b>Facture:</b>"))
        top_layout.addWidget(self.invoice_ref)
        top_layout.addWidget(QLabel("<b>BL:</b>"))
        top_layout.addWidget(self.bl_ref)
        top_layout.addSpacing(10)
        top_layout.addWidget(self.btn_validate_ref)
        top_layout.addWidget(self.btn_unlock_header)
        main_layout.addLayout(top_layout)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(line)

        entry_layout = QVBoxLayout()
        entry_layout.setSpacing(5)

        lay_col = QHBoxLayout()
        lay_col.setSpacing(6)
        lay_col.setContentsMargins(0, 0, 0, 0)
        lay_col.addWidget(self.cb_color, 1)
        lay_col.addWidget(self.lbl_color_swatch, 0)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("<b>Produit:</b>"))
        row1.addWidget(self.cb_product, 3)
        row1.addWidget(QLabel("<b>Couleur:</b>"))
        row1.addLayout(lay_col, 2)
        row1.addWidget(QLabel("<b>Unité:</b>"))
        row1.addWidget(self.cb_unit_type, 1)
        row1.addWidget(QLabel("<b>Qté:</b>"))
        row1.addWidget(self.inp_qty, 1)
        entry_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("<b>Stock:</b>"))
        row2.addWidget(self.cb_location, 2)
        row2.addWidget(QLabel("<b>Prix U:</b>"))
        row2.addWidget(self.inp_price, 2)
        row2.addWidget(QLabel("<b>Remise:</b>"))
        row2.addWidget(self.inp_remise, 1)
        row2.addWidget(self.cb_remise_type, 1)
        row2.addWidget(self.lbl_item_ttc)
        row2.addWidget(QLabel("<b>Réclamation:</b>"))
        row2.addWidget(self.inp_observation, 3)
        entry_layout.addLayout(row2)

        entry_layout.addWidget(self.lbl_conversion_logic)
        main_layout.addLayout(entry_layout)

        ctrl_bar  = QHBoxLayout()
        fin_layout = QHBoxLayout()
        fin_layout.addWidget(QLabel("<b>Total HT:</b>"))
        fin_layout.addWidget(self.lbl_total_ht)
        fin_layout.addWidget(QLabel("<b>Remise Bon:</b>"))
        fin_layout.addWidget(self.inp_bon_remise)
        fin_layout.addWidget(self.cb_bon_remise_type)
        fin_layout.addWidget(QLabel("<b>Remise Totale:</b>"))
        fin_layout.addWidget(self.lbl_total_remise)
        fin_layout.addWidget(QLabel("<b style='color: #007572;'>Total Net:</b>"))
        self.lbl_total_ttc.setStyleSheet("font-weight: bold; color: #007572;")
        fin_layout.addWidget(self.lbl_total_ttc)
        ctrl_bar.addLayout(fin_layout)

        ctrl_bar.addStretch(1)
        ctrl_bar.addWidget(self.btn_add)
        ctrl_bar.addWidget(self.btn_modify)
        ctrl_bar.addWidget(self.btn_delete)
        ctrl_bar.addWidget(self.btn_print)
        ctrl_bar.addWidget(self.btn_print_all)
        main_layout.addLayout(ctrl_bar)

        main_layout.addWidget(self.table_items, 1)
        
        self.table_items.horizontalHeader().setSortIndicator(2, Qt.DescendingOrder)