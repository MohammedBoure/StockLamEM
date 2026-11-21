# ui/widgets/procurement/barcode_summary_dialog.py

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                               QPushButton, QHBoxLayout, QLabel, QHeaderView, 
                               QSpinBox, QAbstractSpinBox, QMessageBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
import logging
from ui.theme_tokens import (
    STATUS_SUCCESS, STATUS_WARN, PRIMARY_CTA_QSS, SLATE_OUTLINE_QSS, CLEAN_TABLE_QSS, scoped_dialog_qss,
)

class BarcodeSummaryDialog(QDialog):
    def __init__(self, batches_data, manager, parent=None):
        super().__init__(parent)
        self.setObjectName("BarcodeSummaryDialog")
        self.setWindowTitle("Étiquettes de Code-barres Générées")
        self.resize(900, 600)
        self.setStyleSheet(scoped_dialog_qss("BarcodeSummaryDialog"))
        self.batches_data = batches_data
        self.manager = manager # نحتاج المدير للوصول للطابعة
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # --- Header ---
        lbl_info = QLabel("Réception enregistrée avec succès.\n"
                          "Voici les codes-barres internes générés. Vérifiez le nombre de copies et imprimez.")
        lbl_info.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {STATUS_SUCCESS}; margin-bottom: 10px;")
        layout.addWidget(lbl_info)

        # --- Table ---
        self.table = QTableWidget()
        self.table.setStyleSheet(CLEAN_TABLE_QSS)
        # الأعمدة: المنتج، الوت، الباركود، الكمية المستلمة، عدد النسخ للطباعة
        cols = ["Produit", "Lot", "Code-barres (Interne)", "Qté Reçue", "Copies à Imprimer"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        
        # تنسيق الجدول
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch) # Product Name
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(3, 100)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(4, 120)

        # زيادة ارتفاع السطر
        self.table.verticalHeader().setDefaultSectionSize(45)
        
        layout.addWidget(self.table)

        # --- Fill Data ---
        self.table.setRowCount(len(self.batches_data))
        for row, item in enumerate(self.batches_data):
            # 1. Product Name
            self.table.setItem(row, 0, QTableWidgetItem(str(item['Product_Name'])))
            
            # 2. Lot
            self.table.setItem(row, 1, QTableWidgetItem(str(item['Lot_Number'])))
            
            # 3. Barcode (Styled)
            bc_item = QTableWidgetItem(str(item['Internal_Barcode']))
            bc_item.setFont(QFont("Consolas", 12, QFont.Bold))
            bc_item.setForeground(QColor("#d35400")) # Orange code
            bc_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, bc_item)
            
            # 4. Qty Received (Read Only)
            qty_item = QTableWidgetItem(str(item['Qty']))
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            qty_item.setFlags(Qt.ItemFlag.ItemIsEnabled) # غير قابل للتعديل
            self.table.setItem(row, 3, qty_item)

            # 5. Copies (SpinBox Full Cell)
            sb_copies = QSpinBox()
            sb_copies.setRange(1, 1000)
            # افتراضياً نطبع نسخة لكل قطعة مستلمة، يمكنك تغييرها لـ 1 إذا أردت ملصق واحد للدفعة
            sb_copies.setValue(int(item['Qty'])) 
            sb_copies.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # --- الستايل المطلوب: ملء الخانة بدون حواف ---
            sb_copies.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            sb_copies.setStyleSheet("background: transparent; border: none; font-weight: bold; font-size: 14px;")
            
            self.table.setCellWidget(row, 4, sb_copies)

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        
        btn_print = QPushButton("Imprimer Étiquettes")
        btn_print.setMinimumHeight(36)
        btn_print.setStyleSheet(PRIMARY_CTA_QSS)
        btn_print.clicked.connect(self.print_labels)
        
        btn_close = QPushButton("Fermer")
        btn_close.setMinimumHeight(34)
        btn_close.setStyleSheet(SLATE_OUTLINE_QSS)
        btn_close.clicked.connect(self.accept)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_print)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def print_labels(self):
        """تنفيذ أمر الطباعة لكل سطر مع حماية من أخطاء الفهارس"""
        try:
            printer = self.manager.printer
            success_count = 0
            
            if not printer.config.get('selected_printer'):
                QMessageBox.warning(self, "Erreur", "Aucune imprimante sélectionnée.")
                return

            for row in range(self.table.rowCount()):
                p_name = self.table.item(row, 0).text()
                lot = self.table.item(row, 1).text()
                # الباركود الآن في العمود رقم 3
                barcode = self.table.item(row, 3).text()
                
                # تصحيح: استخدام Expiry_Date (المفتاح القادم من reception_dialog)
                expiry = self.batches_data[row].get('Expiry_Date')
                
                # جلب الودجت من العمود الصحيح (رقم 5) لتجنب NoneType Error
                copies_widget = self.table.cellWidget(row, 5)
                
                if copies_widget is None:
                    logging.error(f"Widget missing at row {row}, col 5")
                    continue
                    
                copies = copies_widget.value()
                
                if copies > 0:
                    success, msg = printer.print_label(
                        product_name=p_name,
                        barcode_data=barcode,
                        lot_number=lot,
                        expiry_date=expiry,
                        copies=copies
                    )
                    if success: success_count += 1

            if success_count > 0:
                QMessageBox.information(self, "Impression", f"Impression lancée pour {success_count} lots.")
                self.accept()
            else:
                QMessageBox.warning(self, "Attention", "Aucune étiquette n'a été imprimée.")

        except Exception as e:
            logging.error(f"Print Dialog Error: {e}", exc_info=True)
            QMessageBox.critical(self, "Erreur Critique", str(e))