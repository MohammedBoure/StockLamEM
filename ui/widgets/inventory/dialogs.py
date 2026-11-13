# ui/widgets/inventory/dialogs.py

import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QTextEdit, QComboBox, 
    QSpinBox, QHBoxLayout, QPushButton, QLabel, 
    QWidget, QMessageBox, QFrame, QTableWidget, QTableWidgetItem, 
    QHeaderView, QGroupBox, QAbstractItemView, QCheckBox, QDoubleSpinBox,
    QScrollArea, QGridLayout
)
from PySide6.QtCore import QDate, Qt, QTimer, QSize
from PySide6.QtGui import QColor, QFont

# استيراد BaseDialog
from ui.widgets.master_data.dialogs import BaseDialog
from ui.formatting import format_money, format_quantity, quantity_to_int
from decimal import Decimal

# استيراد LocationTreeComboBox
try:
    from .location_tree_combo import LocationTreeComboBox
except ImportError:
    from PySide6.QtWidgets import QComboBox as LocationTreeComboBox

# ==============================================================================
# Classes Utilitaires (أدوات مساعدة لحقول الإدخال)
# ==============================================================================

class BarcodeLineEdit(QLineEdit):
    """حقل إدخال يعالج أرقام لوحة المفاتيح الفرنسية (AZERTY)"""
    def keyPressEvent(self, event):
        azerty_map = {
            Qt.Key_Ampersand: "1", Qt.Key_Eacute: "2", Qt.Key_QuoteDbl: "3",
            Qt.Key_QuoteLeft: "4", Qt.Key_ParenLeft: "5", Qt.Key_Minus: "6",
            Qt.Key_Egrave: "7", Qt.Key_Underscore: "8", Qt.Key_Ccedilla: "9",
            Qt.Key_Agrave: "0"
        }
        if event.key() in azerty_map:
            self.insert(azerty_map[event.key()])
            event.accept()
        else:
            super().keyPressEvent(event)

class NumericSpinBox(QSpinBox):
    """SpinBox يحدد النص تلقائياً عند التركيز عليه"""
    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)

# ==============================================================================
# 1. Open Pack Dialog
# ==============================================================================
class OpenPackDialog(BaseDialog):
    def __init__(self, batch_data, location_manager, parent=None):
        super().__init__(f"Ouvrir un Nouveau Paquet - {batch_data.get('Product_Name')}", parent)
        self.batch = batch_data
        self.location_manager = location_manager
        
        self.selected_location_id = self.batch.get('Location_ID') 
        self.selected_location_name = self.batch.get('Location_Name', 'Inconnu')
        
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self.form_widget)
        
        self.lbl_batch = QLabel(str(self.batch.get('Lot_Number')))
        self.lbl_expiry = QLabel(str(self.batch.get('Expiry_Date')))
        
        stability_days = self.batch.get('Open_Vial_Stability_Days') or 30
        self.lbl_stability = QLabel(f"{stability_days} jours")
        
        expiry_raw = self.batch.get('Expiry_Date')
        original_expiry = QDate()
        if expiry_raw:
            if isinstance(expiry_raw, (datetime.date, datetime.datetime)):
                original_expiry = QDate(expiry_raw.year, expiry_raw.month, expiry_raw.day)
            elif isinstance(expiry_raw, str):
                try: original_expiry = QDate.fromString(expiry_raw[:10], "yyyy-MM-dd")
                except: pass

        calc_open_expiry = QDate.currentDate().addDays(int(stability_days))
        if original_expiry.isValid() and original_expiry < calc_open_expiry:
            calc_open_expiry = original_expiry
            
        self.lbl_open_expiry = QLabel(calc_open_expiry.toString("yyyy-MM-dd"))
        self.lbl_open_expiry.setStyleSheet("color: blue; font-weight: bold; font-size: 14px;")

        self.qty_spin = QSpinBox()
        max_qty = quantity_to_int(self.batch.get('Quantity_Current', 0))
        if max_qty == 0: max_qty = 1 
        self.qty_spin.setRange(1, max_qty)
        self.qty_spin.setValue(1)
        
        loc_container = QWidget()
        loc_layout = QHBoxLayout(loc_container)
        loc_layout.setContentsMargins(0, 0, 0, 0)
        
        self.loc_display = QLineEdit()
        self.loc_display.setReadOnly(True)
        self.loc_display.setText(self.selected_location_name) 
        self.loc_display.setPlaceholderText("Aucun emplacement sélectionné")
        
        self.btn_select_loc = QPushButton("Choisir...")
        self.btn_select_loc.setFixedWidth(80)
        self.btn_select_loc.clicked.connect(self.open_location_picker)
        
        loc_layout.addWidget(self.loc_display)
        loc_layout.addWidget(self.btn_select_loc)

        layout.addRow("N° de Lot (Lot):", self.lbl_batch)
        layout.addRow("Date d'Expiration Originale:", self.lbl_expiry)
        layout.addRow("Période de Stabilité:", self.lbl_stability)
        layout.addRow("Date d'Expiration Calculée:", self.lbl_open_expiry)
        layout.addRow("----------", QLabel())
        layout.addRow(f"Nombre à ouvrir (Max: {max_qty}):", self.qty_spin)
        layout.addRow("📍 Emplacement d'Utilisation:", loc_container)

    def open_location_picker(self):
        dlg = LocationTreeComboBox(self.location_manager, self)
        if dlg.exec():
            loc_id, loc_name = dlg.get_selected_location()
            if loc_id:
                self.selected_location_id = loc_id
                self.selected_location_name = loc_name
                self.loc_display.setText(loc_name)

    def get_data(self):
        return {
            "Batch_ID": self.batch.get('Batch_ID'),
            "Product_ID": self.batch.get('Product_ID'),
            "Qty_To_Open": self.qty_spin.value(),
            "Current_Location_ID": self.selected_location_id,
            "Calculated_Open_Expiry": self.lbl_open_expiry.text() 
        }

# ==============================================================================
# 2. Consumption Dialog 
# ==============================================================================
class ConsumptionDialog(BaseDialog):
    def __init__(self, container_data, parent=None):
        super().__init__("Enregistrement de Consommation (Test/QC)", parent)
        self.container = container_data
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self.form_widget)
        
        current_rem = quantity_to_int(self.container.get('Remaining_Usage_Qty', 0))
        unit = self.container.get('Usage_Unit', 'Test')
        
        self.lbl_info = QLabel(f"{self.container.get('Product_Name')} (Lot: {self.container.get('Lot_Number')})")
        
        self.usage_spin = QSpinBox()
        self.usage_spin.setRange(1, max(1, current_rem))
        self.usage_spin.setSuffix(f" {unit}")
        self.usage_spin.setValue(1)
        
        layout.addRow("Produit:", self.lbl_info)
        layout.addRow(f"Quantité Restante ({current_rem} {unit}):", self.usage_spin)

    def get_data(self):
        return {
            "Container_ID": self.container.get('Container_ID'),
            "Qty_Used": self.usage_spin.value()
        }

# ==============================================================================
# 3. Waste Dialog
# ==============================================================================
class WasteDialog(BaseDialog):
    def __init__(self, item_data, reasons_list, source_type='Batch', parent=None):
        super().__init__("Enregistrement de Mise au Rebut (Waste Report)", parent)
        self.item = item_data
        self.reasons = reasons_list
        self.source_type = source_type
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self.form_widget)
        
        if self.source_type == 'Batch':
            max_qty = quantity_to_int(self.item.get('Quantity_Current', 0))
            if max_qty == 0: max_qty = quantity_to_int(self.item.get('Current_Stock_Qty', 0))
            unit = "Boîte/Kit"
        else:
            max_qty = quantity_to_int(self.item.get('Remaining_Usage_Qty', 0))
            unit = self.item.get('Usage_Unit', 'Test')

        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, max(1, max_qty))
        self.qty_spin.setSuffix(f" {unit}")
        self.qty_spin.setValue(max_qty)
        
        self.reason_combo = QComboBox()
        for r in self.reasons:
            self.reason_combo.addItem(r.get('Reason_Name'), r.get('Reason_ID'))
            
        self.notes = QLineEdit()
        self.notes.setPlaceholderText("Notes additionnelles...")
        
        layout.addRow(f"Produit: {self.item.get('Product_Name')}", QLabel())
        layout.addRow(f"Quantité disponible ({max_qty}):", self.qty_spin)
        layout.addRow("Raison de la Mise au Rebut:", self.reason_combo)
        layout.addRow("Notes:", self.notes)

    def get_data(self):
        return {
            "Source_ID": self.item.get('Batch_ID') if self.source_type == 'Batch' else self.item.get('Container_ID'),
            "Source_Type": self.source_type,
            "Qty_Wasted": self.qty_spin.value(),
            "Reason_ID": self.reason_combo.currentData(),
            "Notes": self.notes.text()
        }
    
# ==============================================================================
# 4. Adjustment Dialog
# ==============================================================================
class AdjustmentDialog(BaseDialog):
    def __init__(self, batch_data, reasons_list, parent=None):
        super().__init__(f"Ajustement d'Inventaire (Correction) - {batch_data.get('Product_Name')}", parent)
        self.batch = batch_data
        self.reasons = reasons_list
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self.form_widget)
        
        current_qty = quantity_to_int(self.batch.get('Quantity_Current', 0))
        
        self.lbl_current = QLabel(format_quantity(current_qty))
        
        self.spin_new_qty = QSpinBox()
        self.spin_new_qty.setRange(0, 999999)
        self.spin_new_qty.setValue(current_qty)
        
        self.reason_combo = QComboBox()
        for r in self.reasons:
            self.reason_combo.addItem(r.get('Reason_Name'), r.get('Reason_ID'))
            
        self.notes = QLineEdit()
        self.notes.setPlaceholderText("Raison de la correction...")
        
        layout.addRow("Quantité Actuelle dans le Système:", self.lbl_current)
        layout.addRow("Quantité Physique (Nouvelle):", self.spin_new_qty)
        layout.addRow("Raison de la Correction:", self.reason_combo)
        layout.addRow("Notes:", self.notes)

    def get_data(self):
        current = quantity_to_int(self.lbl_current.text())
        new_val = self.spin_new_qty.value()
        diff = new_val - current
        
        return {
            "Batch_ID": self.batch.get('Batch_ID'),
            "Qty_Change": diff,
            "Reason_ID": self.reason_combo.currentData(),
            "Notes": self.notes.text()
        }

# ==============================================================================
# 5. Batch Details Dialog
# ==============================================================================
class BatchDetailsDialog(BaseDialog):
    """نافذة عرض تفاصيل المنتج والموقع (للقراءة فقط)"""
    def __init__(self, batch_data, parent=None):
        title = f"Détails du Lot : {batch_data.get('Lot_Number', '---')}"
        super().__init__(title, parent)
        self.batch = batch_data
        self.resize(750, 600)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self.form_widget)
        main_layout.setSpacing(15)

        def add_row(layout, label_text, value_text, is_bold=False, color=None):
            lbl_key = QLabel(f"<b>{label_text} :</b>")
            lbl_val = QLabel(str(value_text))
            style = "font-size: 14px;"
            if is_bold: style += " font-weight: bold;"
            if color: style += f" color: {color};"
            lbl_val.setStyleSheet(style)
            lbl_val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            layout.addRow(lbl_key, lbl_val)

        # 1. قسم المعلومات الأساسية
        grp_basic = QGroupBox("📦 Informations Produit")
        grp_basic.setStyleSheet("QGroupBox { font-weight: bold; color: #2c3e50; border: 1px solid #bdc3c7; border-radius: 5px; margin-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        layout_basic = QFormLayout(grp_basic)
        
        add_row(layout_basic, "Produit", self.batch.get('Product_Name', '---'), True, "#2c3e50")
        add_row(layout_basic, "Marque", self.batch.get('Manuf_Name') or self.batch.get('Brand_Name', '---'))
        add_row(layout_basic, "Code-Barres", self.batch.get('Internal_Barcode') or self.batch.get('Barcode', '---'))
        main_layout.addWidget(grp_basic)

        # 2. قسم المخزون والموقع
        grp_stock = QGroupBox("📍 Stock & Emplacement")
        grp_stock.setStyleSheet("QGroupBox { font-weight: bold; color: #007572; border: 1px solid #007572; border-radius: 5px; margin-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        layout_stock = QFormLayout(grp_stock)

        lbl_loc = QLabel(str(self.batch.get('Location_Name', 'Non défini')))
        lbl_loc.setStyleSheet("font-size: 16px; font-weight: bold; color: #2980b9; background-color: #eaf2f8; padding: 5px; border-radius: 4px;")
        layout_stock.addRow(QLabel("<b>EMPLACEMENT :</b>"), lbl_loc)

        add_row(layout_stock, "Quantite Actuelle", format_quantity(self.batch.get('Quantity_Current', 0)), True, "#27ae60")
        add_row(layout_stock, "Quantite Initiale", format_quantity(self.batch.get('Quantity_Initial', 0)))
        add_row(layout_stock, "N° Lot", self.batch.get('Lot_Number', '---'), True)
        
        exp_date = str(self.batch.get('Expiry_Date', '---'))
        color_exp = None
        if self.batch.get('Expiry_Date'):
            try:
                ed = datetime.datetime.strptime(exp_date[:10], "%Y-%m-%d").date()
                today = datetime.date.today()
                if ed < today: color_exp = "#c0392b"
                elif (ed - today).days <= 30: color_exp = "#e67e22"
            except: pass
            
        add_row(layout_stock, "Date Entrée (Système)", str(self.batch.get('Created_At', '---'))[:16])
        main_layout.addWidget(grp_stock)

        # 3. قسم المعلومات المالية والمراجع
        grp_financial = QGroupBox("💰 Données Financières & Références")
        grp_financial.setStyleSheet("QGroupBox { font-weight: bold; color: #7f8c8d; border: 1px solid #bdc3c7; border-radius: 5px; margin-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        layout_fin = QFormLayout(grp_financial)
        
        price_u = float(self.batch.get('Unit_Price_Received', 0))
        qty_curr = quantity_to_int(self.batch.get('Quantity_Current', 0))
        total_val = price_u * qty_curr

        add_row(layout_fin, "Prix d'Achat", format_money(price_u, 'DA'))
        add_row(layout_fin, "Valeur Totale (Stock Actuel)", format_money(total_val, 'DA'), True, "#2c3e50")

        layout_fin.addRow(QLabel("----------"), QLabel(""))
        add_row(layout_fin, "Réf. Bon de Commande (PO)", self.batch.get('PO_ID', '---'))
        add_row(layout_fin, "Réf. Bon de Réception (BR)", self.batch.get('BR_ID', '---'))
        main_layout.addWidget(grp_financial)

        hbox = QHBoxLayout()
        hbox.addStretch()
        main_layout.addLayout(hbox)

# ==============================================================================
# 6. Inventory Dispatch Dialog (الحل النهائي لمشكلة المسح الضوئي)
# ==============================================================================
class InventoryDispatchDialog(BaseDialog):
    def __init__(self, products_in_stock, location_manager, parent=None):
        super().__init__("Distributeur de Stock (Scan Rapide Auto)", parent)
        self.products = products_in_stock  
        self.location_manager = location_manager
        self.dispatch_data = [] 
        
        # --- المؤقت السحري (The Fix) ---
        self.scan_timer = QTimer()
        self.scan_timer.setSingleShot(True)
        self.scan_timer.timeout.connect(self.process_scan_buffer)

        self.resize(1200, 700)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self.form_widget)
        layout.setSpacing(15)

        # 1. منطقة المسح الضوئي
        search_frame = QFrame()
        search_frame.setStyleSheet("background: #ecf0f1; border-radius: 8px; padding: 10px;")
        search_layout = QHBoxLayout(search_frame)
        
        self.item_search = BarcodeLineEdit()
        self.item_search.setPlaceholderText("🔴 Scannez le code-barres ici (Entrée Auto)...")
        self.item_search.setMinimumHeight(60)
        self.item_search.setStyleSheet("""
            QLineEdit { 
                font-size: 22px; font-weight: bold; border: 2px solid #bdc3c7; 
                border-radius: 5px; padding-left: 10px; color: #2c3e50; background-color: white;
            }
            QLineEdit:focus { border: 2px solid #27ae60; background-color: #e8f8f5; }
        """)
        
        self.item_search.textChanged.connect(self.on_text_changed)
        
        btn_manual = QPushButton("🔎")
        btn_manual.setFixedWidth(50)
        btn_manual.setMinimumHeight(60)
        btn_manual.clicked.connect(self.process_scan_buffer)

        search_layout.addWidget(QLabel("<b>SCANNER :</b>"))
        search_layout.addWidget(self.item_search, 1)
        search_layout.addWidget(btn_manual)
        
        layout.addWidget(search_frame)

        # 2. الجدول
        self.stack_table = QTableWidget()
        cols = ["Produit", "Code-Barres", "Lot", "Emplacement", "Action", "Destination", "Qté", "Suppr."]
        self.stack_table.setColumnCount(len(cols))
        self.stack_table.setHorizontalHeaderLabels(cols)
        
        header = self.stack_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        
        self.stack_table.verticalHeader().setDefaultSectionSize(50)
        self.stack_table.setAlternatingRowColors(True)
        self.stack_table.setStyleSheet("QTableWidget::item { padding: 5px; font-size: 13px; }")
        
        layout.addWidget(self.stack_table)

        # 3. الأزرار السفلية
        btn_layout = QHBoxLayout()
        self.btn_process = QPushButton("🚀 Exécuter les opérations")
        self.btn_process.setMinimumHeight(55)
        self.btn_process.setStyleSheet("""
            QPushButton { background-color: #27ae60; color: white; font-weight: bold; font-size: 16px; border-radius: 8px; }
            QPushButton:hover { background-color: #219150; }
        """)
        self.btn_process.clicked.connect(self.process_all)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_process)
        layout.addLayout(btn_layout)

        QTimer.singleShot(100, self.item_search.setFocus)

    def on_text_changed(self, text):
        if not text: return
        self.scan_timer.start(200)

    def process_scan_buffer(self):
        barcode = self.item_search.text().strip().lower()
        if not barcode: return

        found_batch = None
        
        for b in self.products:
            internal = str(b.get('Internal_Barcode', '')).strip().lower()
            manuf = str(b.get('Barcode', '')).strip().lower()
            lot = str(b.get('Lot_Number', '')).strip().lower()

            if barcode == internal or barcode == manuf:
                found_batch = b
                break
            
            if barcode == lot and found_batch is None:
                found_batch = b
        
        if found_batch:
            self.add_batch_to_table(found_batch)
            self.flash_feedback(True)
            self.item_search.clear()
        else:
            self.flash_feedback(False)
            self.item_search.selectAll()

        self.item_search.setFocus()

    def add_batch_to_table(self, batch):
        for r in range(self.stack_table.rowCount()):
            existing_meta = self.stack_table.item(r, 0).data(Qt.UserRole)
            if existing_meta['Batch_ID'] == batch['Batch_ID']:
                qty_widget = self.stack_table.cellWidget(r, 6)
                curr = qty_widget.value()
                if curr < qty_widget.maximum():
                    qty_widget.setValue(curr + 1)
                    self.stack_table.selectRow(r)
                return

        row = self.stack_table.rowCount()
        self.stack_table.insertRow(row)

        name_item = QTableWidgetItem(f"{batch['Product_Name']}")
        name_item.setData(Qt.UserRole, batch)
        self.stack_table.setItem(row, 0, name_item)
        
        bc_display = batch.get('Internal_Barcode') or batch.get('Barcode') or '---'
        self.stack_table.setItem(row, 1, QTableWidgetItem(str(bc_display)))
        self.stack_table.setItem(row, 2, QTableWidgetItem(str(batch['Lot_Number'])))
        self.stack_table.setItem(row, 3, QTableWidgetItem(batch.get('Location_Name', '---')))

        combo_action = QComboBox()
        combo_action.addItems(["Consommation", "Transfert"])
        self.stack_table.setCellWidget(row, 4, combo_action)

        loc_picker = LocationTreeComboBox(self.location_manager)
        loc_picker.setEnabled(False)
        loc_picker.setStyleSheet("border: none; background: transparent; color: transparent;")
        self.stack_table.setCellWidget(row, 5, loc_picker)

        def toggle_loc(idx):
            is_transfer = (idx == 1)
            loc_picker.setEnabled(is_transfer)
            loc_picker.setStyleSheet("" if is_transfer else "border: none; background: transparent; color: transparent;")
        
        combo_action.currentIndexChanged.connect(toggle_loc)

        spin_qty = NumericSpinBox()
        max_q = quantity_to_int(batch['Quantity_Current'])
        spin_qty.setRange(1, max_q)
        spin_qty.setValue(1)
        self.stack_table.setCellWidget(row, 6, spin_qty)

        btn_del = QPushButton("✖")
        btn_del.setStyleSheet("color: red; border: none; font-weight: bold; font-size: 16px; background: transparent;")
        btn_del.clicked.connect(lambda: self.stack_table.removeRow(self.stack_table.currentRow()))
        self.stack_table.setCellWidget(row, 7, btn_del)

        self.stack_table.scrollToBottom()
        self.stack_table.selectRow(row)

    def flash_feedback(self, success=True):
        color = "#d5f5e3" if success else "#fadbd8"
        orig = self.item_search.styleSheet()
        self.item_search.setStyleSheet(orig + f" background-color: {color};")
        QTimer.singleShot(300, lambda: self.item_search.setStyleSheet(orig))

    def process_all(self):
        if self.stack_table.rowCount() == 0:
            return

        self.dispatch_data = []
        errors = []

        for r in range(self.stack_table.rowCount()):
            meta = self.stack_table.item(r, 0).data(Qt.UserRole)
            action = self.stack_table.cellWidget(r, 4).currentText()
            qty = self.stack_table.cellWidget(r, 6).value()
            
            dest_id = None
            if action == "Transfert":
                dest_id = self.stack_table.cellWidget(r, 5).get_current_location_id()
                if not dest_id:
                    errors.append(f"{meta['Product_Name']}: Destination manquante")
                    continue
            
            self.dispatch_data.append({
                "Batch_ID": meta['Batch_ID'],
                "Action": "Consume" if action == "Consommation" else "Transfer",
                "Qty": qty,
                "Dest_ID": dest_id
            })

        if errors:
            QMessageBox.warning(self, "Erreur", "\n".join(errors))
            return

        self.accept()

# ==============================================================================
# 7. Unpack & Transfer Dialog (Déconditionnement & Transfert en Unité Détail)
# ==============================================================================
# ==============================================================================
# 7. Unpack & Transfer Dialog (Déconditionnement & Transfert en Unité Détail)
# ==============================================================================
class UnpackTransferDialog(BaseDialog):
    """
    Dialogue de déconditionnement d'un lot en sous-unités de détail avec transfert vers un emplacement magasin/rayon.
    Mise en page optimisée en 2 colonnes (largeur) pour une parfaite lisibilité sur tous types d'écrans (y compris HD 1280x720).
    """
    def __init__(self, batch_data, location_manager, product_manager=None, batch_manager=None, parent=None):
        prod_name = batch_data.get('Product_Name', 'Produit')
        super().__init__(f"Déconditionnement et Transfert - {prod_name}", parent)
        self.batch = batch_data
        self.location_manager = location_manager
        self.product_manager = product_manager
        self.batch_manager = batch_manager

        # Charger la hiérarchie des unités et facteurs depuis Données de Base
        self.prod_units = self._load_product_units()

        self.resize(860, 520)
        self.setMinimumSize(780, 460)
        self.init_ui()

    def _load_product_units(self):
        prod_id = self.batch.get('Product_ID')
        p = None
        if self.product_manager and prod_id:
            try:
                p = self.product_manager.get_product_by_id(prod_id)
            except Exception:
                pass

        if not p:
            p = self.batch

        ordering_unit = str(p.get('Ordering_Unit') or 'Carton').strip()
        stock_unit = str(p.get('Stock_Unit') or 'Boîte').strip()

        try:
            stock_qty_per_order = float(p.get('Stock_Qty_Per_Order_Unit') or 1.0)
            if stock_qty_per_order <= 0:
                stock_qty_per_order = 1.0
        except Exception:
            stock_qty_per_order = 1.0

        usage_unit = str(p.get('Usage_Unit') or 'Pièce').strip()
        if not usage_unit or usage_unit.lower() in ('none', 'null'):
            usage_unit = 'Pièce'

        try:
            usage_qty_per_stock = float(p.get('Usage_Qty_Per_Stock_Unit') or 1.0)
            if usage_qty_per_stock <= 0:
                usage_qty_per_stock = 1.0
        except Exception:
            usage_qty_per_stock = 1.0

        return {
            'Ordering_Unit': ordering_unit,
            'Stock_Unit': stock_unit,
            'Stock_Qty_Per_Order_Unit': stock_qty_per_order,
            'Usage_Unit': usage_unit,
            'Usage_Qty_Per_Stock_Unit': usage_qty_per_stock
        }

    def init_ui(self):
        # Appliquer un thème blanc pur, épuré et moderne à l'ensemble du dialogue
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
            QScrollArea {
                background-color: #ffffff;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background-color: #ffffff;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                color: #007572;
                border: 1px solid #dcdfe6;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 14px;
                padding-bottom: 8px;
                padding-left: 10px;
                padding-right: 10px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 6px;
                background-color: #ffffff;
                color: #007572;
            }
            QLabel {
                font-size: 12px;
                color: #2c3e50;
                background-color: transparent;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                min-height: 34px;
                font-size: 12px;
                padding: 2px 8px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                background-color: #ffffff;
                color: #2c3e50;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1.5px solid #007572;
                background-color: #ffffff;
            }
            QCheckBox {
                background-color: transparent;
                font-size: 12px;
                color: #2c3e50;
            }
        """)

        self.form_widget.setStyleSheet("background-color: #ffffff;")

        # Conteneur avec scroll responsive pour s'adapter à toutes les résolutions (HD 1280x720, etc.)
        outer_layout = QVBoxLayout(self.form_widget)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background-color: #ffffff; border: none;")
        scroll.viewport().setStyleSheet("background-color: #ffffff; border: none;")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: #ffffff;")
        cols_layout = QHBoxLayout(content_widget)
        cols_layout.setSpacing(14)
        cols_layout.setContentsMargins(6, 4, 6, 4)

        # =====================================================================
        # COLONNE GAUCHE : Informations Lot Source & Destination
        # =====================================================================
        left_widget = QWidget()
        left_widget.setStyleSheet("background-color: #ffffff;")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # 1. Lot Source & Référentiel Produit
        src_group = QGroupBox("📦 Informations du Lot Source")
        src_layout = QFormLayout(src_group)
        src_layout.setVerticalSpacing(8)
        src_layout.setHorizontalSpacing(10)

        self.lbl_prod = QLabel(f"<b>{self.batch.get('Product_Name', '---')}</b>")
        self.lbl_lot = QLabel(f"{self.batch.get('Lot_Number', '---')} (Exp: {str(self.batch.get('Expiry_Date', '---'))[:10]})")
        self.lbl_curr_loc = QLabel(f"📍 {self.batch.get('Location_Name', 'Inconnu')}")

        self.current_source_unit = self.batch.get('Stock_Unit') or self.prod_units['Stock_Unit'] or 'Boîte'
        curr_stock = quantity_to_int(self.batch.get('Quantity_Current', 0))
        self.lbl_stock_avail = QLabel(f"<b style='color: #27ae60; font-size: 13px;'>{format_quantity(curr_stock)} {self.current_source_unit}</b>")

        src_layout.addRow("Produit :", self.lbl_prod)
        src_layout.addRow("N° de Lot :", self.lbl_lot)
        src_layout.addRow("Emplacement Actuel :", self.lbl_curr_loc)
        src_layout.addRow("Stock Disponible :", self.lbl_stock_avail)

        # Référentiel Données de Base (Badge compact)
        ou = self.prod_units['Ordering_Unit']
        su = self.prod_units['Stock_Unit']
        sq = self.prod_units['Stock_Qty_Per_Order_Unit']
        uu = self.prod_units['Usage_Unit']
        uq = self.prod_units['Usage_Qty_Per_Stock_Unit']

        ref_badge = QLabel(
            f"ℹ️ <b>Référentiel :</b> 1 {ou} = {sq:g} {su} &nbsp;|&nbsp; 1 {su} = {uq:g} {uu}"
        )
        ref_badge.setStyleSheet("background-color: #f0f7fb; border: 1px solid #d4e6f1; border-radius: 4px; padding: 5px 8px; color: #2471a3; font-size: 11px;")
        src_layout.addRow("", ref_badge)
        left_layout.addWidget(src_group)

        # 2. Emplacement Destination & Traçabilité
        dest_group = QGroupBox("📍 Destination et Traçabilité")
        dest_layout = QFormLayout(dest_group)
        dest_layout.setVerticalSpacing(8)
        dest_layout.setHorizontalSpacing(10)

        self.dest_combo = LocationTreeComboBox(self.location_manager)

        # Code-barres avec bouton Générer inline
        bc_container = QWidget()
        bc_layout = QHBoxLayout(bc_container)
        bc_layout.setContentsMargins(0, 0, 0, 0)
        bc_layout.setSpacing(6)

        self.inp_barcode = QLineEdit()
        self.inp_barcode.setPlaceholderText("Laisser vide pour auto-générer (EAN-13) ou saisir")
        self.inp_barcode.textChanged.connect(self._on_barcode_text_changed)

        self.btn_gen_barcode = QPushButton("⚡ Générer")
        self.btn_gen_barcode.setCursor(Qt.PointingHandCursor)
        self.btn_gen_barcode.setToolTip("Générer un code-barres EAN-13 interne unique")
        self.btn_gen_barcode.setStyleSheet("""
            QPushButton {
                min-height: 32px;
                padding: 0 12px;
                background-color: #007572;
                color: #ffffff;
                font-weight: bold;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #005a57;
            }
        """)
        self.btn_gen_barcode.clicked.connect(self._on_generate_barcode)

        bc_layout.addWidget(self.inp_barcode, 1)
        bc_layout.addWidget(self.btn_gen_barcode)

        self.lbl_barcode_status = QLabel("ℹ️ Un code EAN-13 unique sera généré automatiquement si vide.")
        self.lbl_barcode_status.setStyleSheet("color: #7f8c8d; font-size: 11px;")

        # Options d'impression
        print_container = QWidget()
        print_layout = QHBoxLayout(print_container)
        print_layout.setContentsMargins(0, 0, 0, 0)
        print_layout.setSpacing(8)

        self.cb_print = QCheckBox("🖨️ Imprimer l'étiquette")
        self.cb_print.setChecked(True)

        self.spin_copies = QSpinBox()
        self.spin_copies.setRange(1, 100)
        self.spin_copies.setValue(1)
        self.spin_copies.setSuffix(" copie(s)")
        self.spin_copies.setEnabled(self.cb_print.isChecked())
        self.cb_print.toggled.connect(self.spin_copies.setEnabled)

        print_layout.addWidget(self.cb_print)
        print_layout.addWidget(self.spin_copies)
        print_layout.addStretch()

        dest_layout.addRow("Emplacement Destination * :", self.dest_combo)
        dest_layout.addRow("Code-Barres Spécifique :", bc_container)
        dest_layout.addRow("", self.lbl_barcode_status)
        dest_layout.addRow("Impression :", print_container)
        left_layout.addWidget(dest_group)
        left_layout.addStretch()

        cols_layout.addWidget(left_widget, 1)

        # =====================================================================
        # COLONNE DROITE : Paramètres de Déconditionnement & Aperçu
        # =====================================================================
        right_widget = QWidget()
        right_widget.setStyleSheet("background-color: #ffffff;")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # 3. Paramètres de Déconditionnement
        decond_group = QGroupBox("⚙️ Ordre de Déconditionnement")
        decond_layout = QVBoxLayout(decond_group)
        decond_layout.setSpacing(8)

        # Modèle préconfiguré
        preset_row = QHBoxLayout()
        preset_row.setSpacing(8)
        lbl_preset = QLabel("Modèle Préconfiguré :")
        lbl_preset.setMinimumWidth(130)
        self.combo_preset = QComboBox()

        self.combo_preset.addItem(
            f"🧪 Vers Unité Détail ({uu}) — Ratio : 1 {su} = {uq:g} {uu}",
            {"target_unit": uu, "factor": uq, "source_unit": su}
        )
        if sq > 1 and su.lower() != ou.lower():
            self.combo_preset.addItem(
                f"📦 Vers Unité Stockage ({su}) — Ratio : 1 {ou} = {sq:g} {su}",
                {"target_unit": su, "factor": sq, "source_unit": ou}
            )
        if sq > 1 and uq > 1:
            direct_ratio = sq * uq
            self.combo_preset.addItem(
                f"⚡ Direct Commande ➔ Détail ({uu}) — Ratio : 1 {ou} = {direct_ratio:g} {uu}",
                {"target_unit": uu, "factor": direct_ratio, "source_unit": ou}
            )
        self.combo_preset.addItem("✏️ Saisie Personnalisée (Libre)", None)
        self.combo_preset.currentIndexChanged.connect(self._on_preset_changed)

        preset_row.addWidget(lbl_preset)
        preset_row.addWidget(self.combo_preset, 1)
        decond_layout.addLayout(preset_row)

        # Grille pour Quantité et Facteur côte à côte (Distribution en largeur !)
        grid_params = QGridLayout()
        grid_params.setHorizontalSpacing(12)
        grid_params.setVerticalSpacing(4)

        self.lbl_qty_to_unpack = QLabel(f"Quantité à Sortir ({self.current_source_unit}) * :")
        self.lbl_qty_to_unpack.setStyleSheet("font-weight: 500; font-size: 12px; color: #2c3e50;")

        self.spin_qty = QSpinBox()
        max_q = max(1, curr_stock)
        self.spin_qty.setRange(1, max_q)
        self.spin_qty.setValue(1)
        self.spin_qty.setSuffix(f" {self.current_source_unit}")
        self.spin_qty.valueChanged.connect(self._recalculate_preview)

        lbl_factor = QLabel("Facteur de Conversion (x) * :")
        lbl_factor.setStyleSheet("font-weight: 500; font-size: 12px; color: #2c3e50;")

        self.spin_factor = QDoubleSpinBox()
        self.spin_factor.setRange(0.01, 1000000.0)
        self.spin_factor.setDecimals(2)
        self.spin_factor.setValue(uq)
        self.spin_factor.setToolTip("Facteur pré-rempli modifiable manuellement.")
        self.spin_factor.valueChanged.connect(self._recalculate_preview)

        grid_params.addWidget(self.lbl_qty_to_unpack, 0, 0)
        grid_params.addWidget(lbl_factor, 0, 1)
        grid_params.addWidget(self.spin_qty, 1, 0)
        grid_params.addWidget(self.spin_factor, 1, 1)
        decond_layout.addLayout(grid_params)

        # Nom Unité Détail
        unit_row = QHBoxLayout()
        unit_row.setSpacing(8)
        lbl_target_unit = QLabel("Nom Unité Détail * :")
        lbl_target_unit.setMinimumWidth(130)
        self.inp_target_unit = QLineEdit(uu)
        self.inp_target_unit.setPlaceholderText("Ex: Pièce, Flacon, Sachet, Test...")
        self.inp_target_unit.textChanged.connect(self._recalculate_preview)
        unit_row.addWidget(lbl_target_unit)
        unit_row.addWidget(self.inp_target_unit, 1)
        decond_layout.addLayout(unit_row)

        right_layout.addWidget(decond_group)

        # 4. Aperçu du Résultat
        prev_group = QGroupBox("Aperçu du Résultat")
        prev_layout = QVBoxLayout(prev_group)
        prev_layout.setSpacing(6)

        prev_frame = QFrame()
        prev_frame.setObjectName("UnpackPreviewFrame")
        prev_frame.setStyleSheet("""
            QFrame#UnpackPreviewFrame {
                background-color: #eef9f6;
                border: none;
                border-left: 3px solid #007572;
                border-radius: 4px;
                padding: 8px;
            }
            QFrame#UnpackPreviewFrame QLabel {
                border: none;
                background: transparent;
            }
        """)
        pf_layout = QVBoxLayout(prev_frame)
        pf_layout.setSpacing(6)
        pf_layout.setContentsMargins(6, 6, 6, 6)

        self.lbl_result_qty = QLabel()
        self.lbl_result_qty.setStyleSheet("font-size: 13px; font-weight: bold; color: #117a65;")
        self.lbl_result_cost = QLabel()
        self.lbl_result_cost.setStyleSheet("font-size: 12px; color: #16a085; font-weight: 500;")
        self.lbl_result_remain = QLabel()
        self.lbl_result_remain.setStyleSheet("font-size: 12px; color: #566573;")

        pf_layout.addWidget(self.lbl_result_qty)
        pf_layout.addWidget(self.lbl_result_cost)
        pf_layout.addWidget(self.lbl_result_remain)
        prev_layout.addWidget(prev_frame)

        lbl_note = QLabel("ℹ️ <i>Le coût et le prix de vente unitaire sont automatiquement calculés et rattachés au nouveau lot magasin.</i>")
        lbl_note.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        lbl_note.setWordWrap(True)
        prev_layout.addWidget(lbl_note)

        right_layout.addWidget(prev_group)
        right_layout.addStretch()

        cols_layout.addWidget(right_widget, 1)

        scroll.setWidget(content_widget)
        outer_layout.addWidget(scroll)

        self._recalculate_preview()

    def _on_generate_barcode(self):
        new_bc = None
        if self.batch_manager and hasattr(self.batch_manager, 'generate_unique_barcode'):
            try:
                new_bc = self.batch_manager.generate_unique_barcode()
            except Exception as e:
                logging.error(f"Error generating unique barcode: {e}")

        if not new_bc:
            import time
            base = "200" + str(int(time.time()))[-9:]
            odds = sum(int(base[i]) for i in range(0, 12, 2))
            evens = sum(int(base[i]) for i in range(1, 12, 2))
            check = (10 - ((odds + (evens * 3)) % 10)) % 10
            new_bc = base + str(check)

        self.inp_barcode.setText(new_bc)

    def _on_barcode_text_changed(self, text):
        clean_code = text.strip()
        if not clean_code:
            self.lbl_barcode_status.setText("ℹ️ Un code EAN-13 unique sera généré automatiquement si vide.")
            self.lbl_barcode_status.setStyleSheet("color: #7f8c8d; font-size: 11px;")
            return

        if self.batch_manager and hasattr(self.batch_manager, 'is_barcode_available'):
            try:
                is_avail, err = self.batch_manager.is_barcode_available(clean_code)
                if is_avail:
                    self.lbl_barcode_status.setText("✅ Code-barres valide et disponible.")
                    self.lbl_barcode_status.setStyleSheet("color: #27ae60; font-size: 11px; font-weight: bold;")
                else:
                    self.lbl_barcode_status.setText(f"❌ {err}")
                    self.lbl_barcode_status.setStyleSheet("color: #c0392b; font-size: 11px; font-weight: bold;")
            except Exception as e:
                self.lbl_barcode_status.setText(f"⚠️ Erreur de validation: {e}")
                self.lbl_barcode_status.setStyleSheet("color: #e67e22; font-size: 11px;")

    def _on_preset_changed(self, index):
        data = self.combo_preset.currentData()
        if data:
            target_unit = data.get('target_unit', 'Pièce')
            factor = float(data.get('factor', 1.0))
            source_unit = data.get('source_unit', self.current_source_unit)

            self.current_source_unit = source_unit
            self.lbl_qty_to_unpack.setText(f"Quantité à Sortir ({source_unit}) * :")
            self.inp_target_unit.setText(target_unit)
            self.spin_factor.setValue(factor)
            self.spin_qty.setSuffix(f" {source_unit}")

            self._recalculate_preview()

    def _recalculate_preview(self):
        qty_src = self.spin_qty.value()
        factor = self.spin_factor.value()
        unit_tgt = self.inp_target_unit.text().strip() or "Unité"
        src_unit = self.current_source_unit

        target_total_qty = int(qty_src * factor)

        unit_price_src = float(self.batch.get('Unit_Price_Received', 0.0))
        target_unit_cost = unit_price_src / factor if factor > 0 else 0.0

        curr_stock = quantity_to_int(self.batch.get('Quantity_Current', 0))
        remaining = max(0, curr_stock - qty_src)

        self.lbl_result_qty.setText(f"🎯 <b>Nouveau Stock Détail :</b> {format_quantity(target_total_qty)} {unit_tgt} <i>(depuis {format_quantity(qty_src)} {src_unit})</i>")
        self.lbl_result_cost.setText(f"💰 <b>Coût Unitaire Déconditionné :</b> {format_money(target_unit_cost, 'DA')} / {unit_tgt}")
        self.lbl_result_remain.setText(f"📦 <b>Stock Restant Lot Parent :</b> {format_quantity(remaining)} {src_unit}")

    def accept(self):
        # 1. Validation de la quantité
        qty_to_unpack = self.spin_qty.value()
        curr_stock = quantity_to_int(self.batch.get('Quantity_Current', 0))
        if qty_to_unpack <= 0:
            QMessageBox.warning(self, "Validation", "La quantité à déconditionner doit être supérieure à zéro.")
            return
        if qty_to_unpack > curr_stock:
            QMessageBox.warning(self, "Validation", f"Stock insuffisant : {curr_stock} {self.current_source_unit} disponible(s).")
            return

        # 2. Validation du facteur de conversion
        if self.spin_factor.value() <= 0:
            QMessageBox.warning(self, "Validation", "Le facteur de conversion doit être strictement supérieur à zéro.")
            return

        # 3. Validation de l'unité cible
        unit_tgt = self.inp_target_unit.text().strip()
        if not unit_tgt:
            QMessageBox.warning(self, "Validation", "Veuillez renseigner le nom de l'unité de détail.")
            self.inp_target_unit.setFocus()
            return

        # 4. Validation de la destination
        dest_id = self.dest_combo.get_current_location_id()
        if not dest_id:
            QMessageBox.warning(self, "Validation", "Veuillez sélectionner un emplacement de destination valide.")
            return

        # 5. Validation du code-barres spécifique
        custom_bc = self.inp_barcode.text().strip()
        if custom_bc and self.batch_manager and hasattr(self.batch_manager, 'is_barcode_available'):
            is_avail, err = self.batch_manager.is_barcode_available(custom_bc)
            if not is_avail:
                QMessageBox.warning(self, "Code-Barres Indisponible", f"Impossible d'utiliser ce code-barres :<br><br>{err}")
                self.inp_barcode.setFocus()
                return

        super().accept()

    def get_data(self):
        return {
            'qty_to_unpack': self.spin_qty.value(),
            'conversion_factor': float(self.spin_factor.value()),
            'source_unit': self.current_source_unit,
            'target_unit': self.inp_target_unit.text().strip() or "Unité",
            'selling_price_ht': None,  # Automatiquement calculé et hérité depuis le produit d'origine
            'dest_id': self.dest_combo.get_current_location_id(),
            'custom_barcode': self.inp_barcode.text().strip() or None,
            'print_label': self.cb_print.isChecked(),
            'print_copies': self.spin_copies.value()
        }


# ==============================================================================
# 9. Price History Dialog
# ==============================================================================

class PriceHistoryDialog(QDialog):
    """نافذة سجل تتبع تعديلات أسعار البيع للوط أو المنتج"""

    def __init__(self, manager, parent=None, batch_id=None, product_id=None, product_name=""):
        super().__init__(parent)
        self.manager = manager
        self.batch_id = batch_id
        self.product_id = product_id
        self.product_name = product_name or "Produit"

        self.setWindowTitle(f"Historique des Prix - {self.product_name}")
        self.setModal(True)
        self.resize(880, 500)
        self.setStyleSheet("background-color: #ffffff;")

        self.init_ui()
        self.load_history()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        lbl_title = QLabel(f"📈 Historique des modifications de prix : <b>{self.product_name}</b>")
        lbl_title.setStyleSheet("font-size: 14px; color: #007572; padding: 4px 0;")
        layout.addWidget(lbl_title)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Date / Heure", "Utilisateur", "N° Lot", "Type de Prix",
            "Ancien Prix (DA)", "Nouveau Prix (DA)", "Écart (DA)", "Motif de Modification"
        ])
        header = self.table.horizontalHeader()
        for c in range(8):
            header.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.Stretch)

        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #dcdfe6;
                gridline-color: #f1f5f9;
                font-size: 12px;
                color: #2c3e50;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #2c3e50;
                font-weight: bold;
                font-size: 12px;
                border: none;
                border-bottom: 2px solid #007572;
                border-right: 1px solid #e2e8f0;
                padding: 6px 8px;
            }
        """)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_close = QPushButton("Fermer")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #007572;
                color: #ffffff;
                font-weight: bold;
                border-radius: 4px;
                padding: 6px 20px;
                min-height: 30px;
                border: none;
            }
            QPushButton:hover {
                background-color: #005a57;
            }
        """)
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)

    def load_history(self):
        try:
            logs = self.manager.batches.get_price_change_history(
                product_id=self.product_id,
                batch_id=self.batch_id,
                limit=200
            )
            self.table.setRowCount(0)
            if not logs:
                self.table.insertRow(0)
                item = QTableWidgetItem("Aucune modification de prix enregistrée pour ce produit / lot.")
                item.setTextAlignment(Qt.AlignCenter)
                item.setForeground(QColor("#7f8c8d"))
                self.table.setItem(0, 0, item)
                self.table.setSpan(0, 0, 1, 8)
                return

            for r, log in enumerate(logs):
                self.table.insertRow(r)
                dt_str = str(log.get('Changed_At', ''))[:19]
                user_str = log.get('Changed_By_Name') or "Système"
                lot_str = log.get('Lot_Number') or "---"
                price_type = log.get('Price_Type') or "Prix Vente"
                old_p = float(log.get('Old_Price') or 0.0)
                new_p = float(log.get('New_Price') or 0.0)
                diff = new_p - old_p
                reason = log.get('Reason') or "---"

                def _item(text, align=Qt.AlignLeft | Qt.AlignVCenter, color=None, bold=False):
                    it = QTableWidgetItem(str(text))
                    it.setTextAlignment(align)
                    if color:
                        it.setForeground(color)
                    if bold:
                        font = it.font()
                        font.setBold(True)
                        it.setFont(font)
                    return it

                self.table.setItem(r, 0, _item(dt_str))
                self.table.setItem(r, 1, _item(user_str))
                self.table.setItem(r, 2, _item(lot_str, align=Qt.AlignCenter))
                self.table.setItem(r, 3, _item(price_type, bold=True))
                self.table.setItem(r, 4, _item(format_money(old_p), align=Qt.AlignRight | Qt.AlignVCenter))
                self.table.setItem(r, 5, _item(format_money(new_p), align=Qt.AlignRight | Qt.AlignVCenter, bold=True))

                diff_color = QColor("#27ae60") if diff > 0 else (QColor("#c0392b") if diff < 0 else QColor("#7f8c8d"))
                diff_sign = "+" if diff > 0 else ""
                diff_str = f"{diff_sign}{format_money(diff)}"
                self.table.setItem(r, 6, _item(diff_str, align=Qt.AlignRight | Qt.AlignVCenter, color=diff_color, bold=True))
                self.table.setItem(r, 7, _item(reason))

        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Échec du chargement de l'historique : {e}")


# ==============================================================================
# 10. Modify Sales Prices Dialog
# ==============================================================================

class ModifySalesPricesDialog(QDialog):
    """حوار تعديل أسعار البيع (Prix Vente 1, 2, 3, 4 et TVA) مع احتساب الهامش والتدقيق"""

    def __init__(self, batch_data, manager, parent=None):
        super().__init__(parent)
        self.batch_data = batch_data
        self.manager = manager
        self.current_user = getattr(parent, 'current_user', None) if parent else None

        prod_name = batch_data.get('Product_Name', 'Produit')
        self.setWindowTitle(f"Ajustement des Prix de Vente - {prod_name}")
        self.setModal(True)
        self.resize(650, 520)
        self.setStyleSheet("background-color: #ffffff;")

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

        # 1. Product & Batch Summary Card
        card = QFrame()
        card.setObjectName("ModifyPriceBatchCard")
        card.setStyleSheet("""
            QFrame#ModifyPriceBatchCard {
                background-color: #f8fafc;
                border: none;
                border-bottom: 1px solid #E2E8F0;
                border-radius: 4px;
                padding: 8px;
            }
            QFrame#ModifyPriceBatchCard QLabel {
                font-size: 12px;
                color: #2c3e50;
                border: none;
                background: transparent;
            }
        """)
        card_layout = QGridLayout(card)
        card_layout.setContentsMargins(5, 5, 5, 5)
        card_layout.setSpacing(8)

        prod_name = self.batch_data.get('Product_Name', '---')
        lot_no = self.batch_data.get('Lot_Number', '---')
        stock_qty = format_quantity(self.batch_data.get('Quantity_Current', 0))
        unit_str = self.batch_data.get('Stock_Unit') or "Unité"

        # Coût d'achat pour calcul de marge
        self.unit_cost_ht = float(self.batch_data.get('Unit_Price_Received', 0.0) or 0.0)
        disc = float(self.batch_data.get('Discount_Percent', 0.0) or 0.0) / 100.0
        tax = float(self.batch_data.get('Tax_Rate_Percent', 0.0) or 0.0) / 100.0
        self.unit_cost_ttc = self.unit_cost_ht * (1 - disc) * (1 + tax)

        card_layout.addWidget(QLabel("<b>Produit :</b>"), 0, 0)
        card_layout.addWidget(QLabel(f"<b>{prod_name}</b>"), 0, 1, 1, 3)

        card_layout.addWidget(QLabel("<b>Lot :</b>"), 1, 0)
        card_layout.addWidget(QLabel(lot_no), 1, 1)

        card_layout.addWidget(QLabel("<b>Stock en cours :</b>"), 1, 2)
        card_layout.addWidget(QLabel(f"<b>{stock_qty} {unit_str}</b>"), 1, 3)

        card_layout.addWidget(QLabel("<b>Coût Achat HT :</b>"), 2, 0)
        card_layout.addWidget(QLabel(f"{format_money(self.unit_cost_ht)} DA"), 2, 1)

        card_layout.addWidget(QLabel("<b>Coût Achat TTC :</b>"), 2, 2)
        card_layout.addWidget(QLabel(f"{format_money(self.unit_cost_ttc)} DA"), 2, 3)

        main_layout.addWidget(card)

        # 2. Formulaire des Prix de Vente
        group_prices = QGroupBox("💲 Tarification et Prix de Vente (DA)")
        group_prices.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #007572;
                border: 1px solid #dcdfe6;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 14px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
                background-color: #ffffff;
            }
            QDoubleSpinBox, QComboBox, QLineEdit {
                background-color: #ffffff;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 4px 8px;
                min-height: 28px;
                font-size: 12px;
                color: #2c3e50;
            }
            QDoubleSpinBox:focus, QComboBox:focus, QLineEdit:focus {
                border: 1.5px solid #007572;
            }
        """)

        form_layout = QGridLayout(group_prices)
        form_layout.setContentsMargins(12, 12, 12, 12)
        form_layout.setSpacing(10)

        # Prix Vente 1 (Principal)
        form_layout.addWidget(QLabel("<b>Prix Vente 1 :</b>"), 0, 0)
        self.spin_p1 = QDoubleSpinBox()
        self.spin_p1.setRange(0.0, 99999999.99)
        self.spin_p1.setDecimals(2)
        self.spin_p1.setValue(float(self.batch_data.get('Selling_Price_HT', 0.0) or 0.0))
        self.spin_p1.setSuffix(" DA")
        self.spin_p1.valueChanged.connect(self._update_margin_label)
        form_layout.addWidget(self.spin_p1, 0, 1)

        self.lbl_margin = QLabel()
        self.lbl_margin.setStyleSheet("font-size: 11px; font-weight: bold;")
        form_layout.addWidget(self.lbl_margin, 0, 2)

        # TVA Vente (masquée — 0%)
        lbl_tva_v = QLabel("<b>TVA Vente :</b>")
        lbl_tva_v.setVisible(False)
        form_layout.addWidget(lbl_tva_v, 1, 0)
        self.spin_tva = QDoubleSpinBox()
        self.spin_tva.setRange(0.0, 100.0)
        self.spin_tva.setDecimals(2)
        self.spin_tva.setValue(0.0)
        self.spin_tva.setSuffix(" %")
        self.spin_tva.setVisible(False)
        form_layout.addWidget(self.spin_tva, 1, 1)

        # Prix Vente 2
        form_layout.addWidget(QLabel("Prix Vente 2 :"), 2, 0)
        self.spin_p2 = QDoubleSpinBox()
        self.spin_p2.setRange(0.0, 99999999.99)
        self.spin_p2.setDecimals(2)
        self.spin_p2.setValue(float(self.batch_data.get('Selling_Price_HT_2', 0.0) or 0.0))
        self.spin_p2.setSuffix(" DA")
        form_layout.addWidget(self.spin_p2, 2, 1)

        # Prix Vente 3
        form_layout.addWidget(QLabel("Prix Vente 3 (HT) :"), 3, 0)
        self.spin_p3 = QDoubleSpinBox()
        self.spin_p3.setRange(0.0, 99999999.99)
        self.spin_p3.setDecimals(2)
        self.spin_p3.setValue(float(self.batch_data.get('Selling_Price_HT_3', 0.0) or 0.0))
        self.spin_p3.setSuffix(" DA")
        form_layout.addWidget(self.spin_p3, 3, 1)

        # Prix Vente 4
        form_layout.addWidget(QLabel("Prix Vente 4 (HT) :"), 4, 0)
        self.spin_p4 = QDoubleSpinBox()
        self.spin_p4.setRange(0.0, 99999999.99)
        self.spin_p4.setDecimals(2)
        self.spin_p4.setValue(float(self.batch_data.get('Selling_Price_HT_4', 0.0) or 0.0))
        self.spin_p4.setSuffix(" DA")
        form_layout.addWidget(self.spin_p4, 4, 1)

        main_layout.addWidget(group_prices)

        # 3. Scope & Audit Reason
        group_audit = QGroupBox("📝 Audit & Portée de la Modification")
        group_audit.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #2c3e50;
                border: 1px solid #dcdfe6;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 14px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
                background-color: #ffffff;
            }
        """)
        audit_layout = QVBoxLayout(group_audit)
        audit_layout.setContentsMargins(12, 12, 12, 12)
        audit_layout.setSpacing(8)

        reason_layout = QHBoxLayout()
        reason_layout.addWidget(QLabel("<b>Motif :</b>"))
        self.combo_reason = QComboBox()
        self.combo_reason.setEditable(True)
        self.combo_reason.addItems([
            "Ajustement tarifaire périodique",
            "Hausse des tarifs fournisseur",
            "Réalignement sur le marché",
            "Offre promotionnelle",
            "Correction d'erreur de saisie",
            "Autre motif"
        ])
        reason_layout.addWidget(self.combo_reason, 1)
        audit_layout.addLayout(reason_layout)

        self.cb_all_batches = QCheckBox("Appliquer également ces nouveaux prix à TOUS les lots actifs de ce produit")
        self.cb_all_batches.setStyleSheet("font-weight: bold; color: #d35400; padding-top: 4px;")
        audit_layout.addWidget(self.cb_all_batches)

        main_layout.addWidget(group_audit)

        self._update_margin_label()

        # 4. Action Buttons
        btn_bar = QHBoxLayout()

        btn_history = QPushButton("🕒 Historique des prix")
        btn_history.setCursor(Qt.PointingHandCursor)
        btn_history.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc;
                color: #2c3e50;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 12px;
                min-height: 28px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
            }
        """)
        btn_history.clicked.connect(self.open_history_view)
        btn_bar.addWidget(btn_history)

        btn_bar.addStretch()

        btn_cancel = QPushButton("Annuler")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #495057;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 12px;
                min-height: 28px;
            }
            QPushButton:hover {
                background-color: #f8f9fa;
            }
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_bar.addWidget(btn_cancel)

        btn_save = QPushButton("💾 Enregistrer les prix")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #007572;
                color: #ffffff;
                font-weight: bold;
                border-radius: 4px;
                padding: 6px 20px;
                font-size: 12px;
                min-height: 28px;
                border: none;
            }
            QPushButton:hover {
                background-color: #005a57;
            }
        """)
        btn_save.clicked.connect(self.save_prices)
        btn_bar.addWidget(btn_save)

        main_layout.addLayout(btn_bar)

    def _update_margin_label(self):
        p1 = self.spin_p1.value()
        if self.unit_cost_ht > 0 and p1 > 0:
            margin_da = p1 - self.unit_cost_ht
            margin_pct = (margin_da / self.unit_cost_ht) * 100.0
            color = "#27ae60" if margin_da >= 0 else "#c0392b"
            sign = "+" if margin_da >= 0 else ""
            self.lbl_margin.setText(f"Marge: {sign}{format_money(margin_da)} DA ({sign}{margin_pct:.1f}%)")
            self.lbl_margin.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {color};")
        else:
            self.lbl_margin.setText("")

    def open_history_view(self):
        dlg = PriceHistoryDialog(
            manager=self.manager,
            parent=self,
            batch_id=self.batch_data.get('Batch_ID'),
            product_id=self.batch_data.get('Product_ID'),
            product_name=self.batch_data.get('Product_Name', '')
        )
        dlg.exec()

    def save_prices(self):
        user_id = getattr(self.current_user, 'get', lambda k, d=None: None)('User_ID') if self.current_user else None
        if not user_id and hasattr(self.parent(), 'window'):
            win = self.parent().window()
            if hasattr(win, 'current_user') and isinstance(win.current_user, dict):
                user_id = win.current_user.get('User_ID')

        new_prices = {
            'Selling_Price_HT': Decimal(str(self.spin_p1.value())),
            'Selling_Price_HT_2': Decimal(str(self.spin_p2.value())),
            'Selling_Price_HT_3': Decimal(str(self.spin_p3.value())),
            'Selling_Price_HT_4': Decimal(str(self.spin_p4.value())),
            'Selling_TVA_Percent': Decimal(str(self.spin_tva.value()))
        }

        update_all = self.cb_all_batches.isChecked()
        reason = self.combo_reason.currentText().strip()

        success, err, count = self.manager.batches.update_batch_sales_prices(
            batch_id=self.batch_data['Batch_ID'],
            new_prices=new_prices,
            update_all_product_batches=update_all,
            reason=reason,
            user_id=user_id
        )

        if success:
            msg = f"Prix de vente mis à jour avec succès pour {count} lot(s)."
            if update_all:
                msg += "\nLes tarifs du produit dans les Données de Base ont également été synchronisés."
            QMessageBox.information(self, "Succès", msg)
            super().accept()
        else:
            QMessageBox.critical(self, "Erreur", f"Échec de l'enregistrement des prix :\n{err}")


class AdminStockAuthDialog(QDialog):
    """Dialogue d'authentification Administrateur requis pour Sortie et Ajustement de stock."""

    def __init__(self, action_label: str, item_summary: str, data_manager=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Autorisation Administrateur — {action_label}")
        self.setFixedSize(440, 320)
        self.setStyleSheet("""
            QDialog { background-color: #FFFFFF; color: #1E293B; }
            QLabel { border: none; background: transparent; }
        """)
        self.data_manager = data_manager
        self.approved = False
        self.admin_user_id = None
        self._init_ui(action_label, item_summary)

    def _init_ui(self, action_label: str, item_summary: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        lbl_title = QLabel(f"Validation Administrateur Requise ({action_label})")
        lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #007572;")
        layout.addWidget(lbl_title)

        card = QFrame()
        card.setStyleSheet(
            "QFrame { background-color: #F8FAFC; border: 1px solid #DDE3EA; border-radius: 6px; }"
        )
        card_form = QFormLayout(card)
        card_form.setContentsMargins(12, 8, 12, 8)
        card_form.setSpacing(4)
        card_form.addRow(QLabel("Action :"), QLabel(f"<b>{action_label}</b>"))
        card_form.addRow(QLabel("Article :"), QLabel(f"<b>{item_summary}</b>"))
        layout.addWidget(card)

        lbl_u = QLabel("Identifiant Administrateur :")
        lbl_u.setStyleSheet("font-size: 12px; font-weight: 600; color: #475569;")
        layout.addWidget(lbl_u)
        self.txt_admin_user = QLineEdit("admin")
        self.txt_admin_user.setFixedHeight(34)
        layout.addWidget(self.txt_admin_user)

        lbl_p = QLabel("Mot de passe Administrateur :")
        lbl_p.setStyleSheet("font-size: 12px; font-weight: 600; color: #475569;")
        layout.addWidget(lbl_p)
        self.txt_password = QLineEdit()
        self.txt_password.setFixedHeight(34)
        self.txt_password.setEchoMode(QLineEdit.Password)
        self.txt_password.setPlaceholderText("Saisissez le mot de passe administrateur...")
        self.txt_password.returnPressed.connect(self._verify_credentials)
        layout.addWidget(self.txt_password)

        layout.addStretch()

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_cancel = QPushButton("Annuler")
        btn_cancel.setFixedHeight(36)
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_auth = QPushButton("Autoriser")
        btn_auth.setFixedHeight(36)
        btn_auth.setCursor(Qt.PointingHandCursor)
        btn_auth.setStyleSheet(
            "QPushButton { background-color: #007572; color: white; font-weight: bold; "
            "padding: 0 16px; border-radius: 5px; border: none; }"
            "QPushButton:hover { background-color: #005A57; }"
        )
        btn_auth.clicked.connect(self._verify_credentials)
        btn_box.addWidget(btn_auth)
        layout.addLayout(btn_box)

    def _verify_credentials(self) -> None:
        username = self.txt_admin_user.text().strip() or "admin"
        secret = self.txt_password.text().strip()
        if not secret:
            QMessageBox.warning(self, "Champ requis", "Veuillez saisir le mot de passe Administrateur.")
            self.txt_password.setFocus()
            return

        if self.data_manager and hasattr(self.data_manager, "users"):
            user = self.data_manager.users.authenticate(username, secret)
            if user and str(user.get("Role", "")).strip().lower() in ("admin", "administrateur"):
                self.approved = True
                self.admin_user_id = int(user.get("User_ID") or 1)
                self.accept()
                return

        QMessageBox.warning(
            self,
            "Accès Refusé",
            "Identifiant ou mot de passe administrateur invalide, ou compte sans privilèges Admin.",
        )
        self.txt_password.clear()
        self.txt_password.setFocus()


class DirectBonRetourDialog(QDialog):
    """نافذة مبسطة لإنشاء Bon de Retour / Avoir مباشرة من المخزون الحالي بخانة إدخال واحدة للكمية."""

    def __init__(self, batch_data: dict, parent=None):
        super().__init__(parent)
        self.batch_data = batch_data or {}
        self.setWindowTitle("Créer un Bon de Retour / Avoir")
        self.setFixedSize(430, 260)
        self.setStyleSheet("""
            QDialog { background-color: #FFFFFF; color: #1E293B; }
            QLabel { border: none; background: transparent; }
        """)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        lbl_title = QLabel("Bon de Retour Fournisseur (Avoir)")
        lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #007572;")
        layout.addWidget(lbl_title)

        card = QFrame()
        card.setStyleSheet(
            "QFrame { background-color: #F8FAFC; border: 1px solid #DDE3EA; border-radius: 6px; }"
        )
        form = QFormLayout(card)
        form.setContentsMargins(12, 10, 12, 10)
        form.setSpacing(6)

        prod_name = self.batch_data.get("Product_Name") or "---"
        sup_name = self.batch_data.get("Supplier_Name") or "---"
        br_id = self.batch_data.get("BR_ID")
        bl_ref = (
            self.batch_data.get("Supplier_BL_Ref")
            or self.batch_data.get("BL_Number")
            or self.batch_data.get("Supplier_Invoice_Ref")
            or (f"BR #{br_id}" if br_id else "---")
        )
        max_qty = max(1, quantity_to_int(self.batch_data.get("Quantity_Current", 1)))

        form.addRow(QLabel("Produit :"), QLabel(f"<b>{prod_name}</b>"))
        form.addRow(QLabel("Fournisseur :"), QLabel(f"<b>{sup_name}</b>"))
        form.addRow(QLabel("BL / Réception :"), QLabel(f"<b>{bl_ref}</b>"))
        layout.addWidget(card)

        qty_row = QHBoxLayout()
        qty_row.addWidget(QLabel(f"<b>Quantité à retourner (Max: {max_qty}) :</b>"))
        self.spin_qty_return = QSpinBox()
        self.spin_qty_return.setRange(1, max_qty)
        self.spin_qty_return.setValue(1)
        self.spin_qty_return.setFixedHeight(34)
        self.spin_qty_return.setMinimumWidth(110)
        qty_row.addWidget(self.spin_qty_return)
        layout.addLayout(qty_row)

        layout.addStretch()

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_cancel = QPushButton("Annuler")
        btn_cancel.setFixedHeight(36)
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_confirm = QPushButton("Confirmer le Retour")
        btn_confirm.setFixedHeight(36)
        btn_confirm.setCursor(Qt.PointingHandCursor)
        btn_confirm.setStyleSheet(
            "QPushButton { background-color: #007572; color: white; font-weight: bold; "
            "padding: 0 16px; border-radius: 5px; border: none; }"
            "QPushButton:hover { background-color: #005A57; }"
        )
        btn_confirm.clicked.connect(self.accept)
        btn_box.addWidget(btn_confirm)
        layout.addLayout(btn_box)

    def get_qty(self) -> int:
        return int(self.spin_qty_return.value())
