# ui/widgets/dashboard/consumption_tab.py

import logging
from datetime import datetime, date
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                               QTableWidgetItem, QPushButton, QHeaderView, 
                               QComboBox, QLabel, QLineEdit, QMessageBox, 
                               QGroupBox, QAbstractItemView, QStyle, QFrame)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor

# استيراد المكونات المساعدة (تأكد من وجودها في مسارها الصحيح)
from .dialogs import BarcodeLineEdit, NumericSpinBox
from .location_tree_combo import LocationTreeComboBox
from ui.formatting import format_quantity, quantity_to_int
from ui.theme_tokens import (
    BRAND_TEAL, CARD_BG, BORDER_CONTROL, BORDER_HAIRLINE, TEXT_PRIMARY, TEXT_MUTED,
    STATUS_DANGER, CLEAN_TABLE_QSS, PRIMARY_CTA_QSS, SLATE_OUTLINE_QSS, scoped_card_qss,
)

class ConsumptionTab(QWidget):
    data_changed = Signal()

    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.location_manager = manager.locations
        self.inventory_pool = [] 
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # --- 1. منطقة الإدخال ---
        input_group = QGroupBox("Terminal de scan (Prêt pour la saisie)")
        input_group.setObjectName("ConsumptionScanGroup")
        input_group.setStyleSheet(f"""
            QGroupBox#ConsumptionScanGroup {{
                background-color: {CARD_BG};
                font-weight: 700;
                font-size: 13px;
                color: {BRAND_TEAL};
                border: 1px solid {BORDER_HAIRLINE};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 14px;
            }}
            QGroupBox#ConsumptionScanGroup::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }}
        """)
        input_layout = QHBoxLayout(input_group)

        self.barcode_input = BarcodeLineEdit()
        self.barcode_input.setPlaceholderText("Scannez ou saisissez le code-barres / N° de lot ici...")
        self.barcode_input.setMinimumHeight(48)
        self._barcode_base_qss = f"""
            QLineEdit {{
                font-size: 18px; font-weight: 700; background-color: #F8FAFC;
                border: 1px solid {BORDER_CONTROL}; border-radius: 6px;
                padding-left: 12px; color: {TEXT_PRIMARY};
            }}
            QLineEdit:focus {{ border: 1.5px solid {BRAND_TEAL}; background-color: {CARD_BG}; }}
        """
        self.barcode_input.setStyleSheet(self._barcode_base_qss)
        self.barcode_input.returnPressed.connect(self.process_scan)

        input_layout.addWidget(self.barcode_input)
        layout.addWidget(input_group)

        # --- 2. الجدول ---
        self.table = QTableWidget()
        cols = ["Produit", "N° Lot", "Lieu Actuel", "Action", "Destination", "Qté", "Suppr."]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(CLEAN_TABLE_QSS)
        layout.addWidget(self.table)

        # --- 3. شريط التحكم ---
        bottom_layout = QHBoxLayout()
        self.btn_clear = QPushButton("Vider la liste")
        self.btn_clear.setMinimumHeight(36)
        self.btn_clear.setStyleSheet(SLATE_OUTLINE_QSS)
        self.btn_clear.clicked.connect(lambda: self.table.setRowCount(0))
        
        self.btn_execute = QPushButton("Confirmer et exécuter tout")
        self.btn_execute.setMinimumHeight(42)
        self.btn_execute.setStyleSheet(PRIMARY_CTA_QSS)
        self.btn_execute.clicked.connect(self.execute_all)

        bottom_layout.addWidget(self.btn_clear)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_execute)
        layout.addLayout(bottom_layout)

        self.load_inventory_pool()

    def load_inventory_pool(self):
        """تحميل المخزون في الذاكرة لتسريع البحث"""
        try:
            self.inventory_pool = self.manager.batches.get_all_batches_with_details()
        except Exception as e:
            logging.error(f"Erreur chargement stock: {e}")

    def process_scan(self):
        """معالجة الباركود عند الضغط على Enter"""
        barcode = self.barcode_input.text().strip()
        if not barcode: return

        found_item = None
        # مقارنة مرنة (Case Insensitive)
        for b in self.inventory_pool:
            vals = [
                str(b.get('Internal_Barcode', '')).lower(),
                str(b.get('Barcode', '')).lower(),
                str(b.get('Lot_Number', '')).lower()
            ]
            if barcode.lower() in vals:
                found_item = b
                break
        
        if found_item:
            self.add_item_to_table(found_item)
            self.barcode_input.clear()
            self.barcode_input.setStyleSheet(self._barcode_base_qss.replace("#F8FAFC", "#E6F4F1")) 
            QTimer.singleShot(300, lambda: self.reset_input_style())
        else:
            self.barcode_input.setStyleSheet(self._barcode_base_qss.replace("#F8FAFC", "#FEF2F2"))
            QTimer.singleShot(500, lambda: self.reset_input_style())

    def reset_input_style(self):
        self.barcode_input.setStyleSheet(self._barcode_base_qss)

    def add_item_to_table(self, batch):
        """إضافة السلعة للجدول"""
        # 1. التحقق هل العنصر موجود مسبقاً لزيادة الكمية فقط
        for r in range(self.table.rowCount()):
            existing_data = self.table.item(r, 0).data(Qt.UserRole)
            # مقارنة بالـ Batch_ID للتأكد أنه نفس اللوت بالضبط
            if str(existing_data.get('Batch_ID')) == str(batch.get('Batch_ID')):
                spin = self.table.cellWidget(r, 5)
                if spin: 
                    current_val = spin.value()
                    max_val = spin.maximum()
                    if current_val < max_val:
                        spin.setValue(current_val + 1)
                    else:
                        QMessageBox.warning(self, "Stock Limite", "Quantité maximale atteinte pour ce lot.")
                self.table.selectRow(r)
                return

        # 2. إضافة صف جديد
        row = self.table.rowCount()
        self.table.insertRow(row)

        name_item = QTableWidgetItem(batch.get('Product_Name', 'Inconnu'))
        name_item.setData(Qt.UserRole, batch)
        self.table.setItem(row, 0, name_item)
        self.table.setItem(row, 1, QTableWidgetItem(str(batch.get('Lot_Number', ''))))
        self.table.setItem(row, 2, QTableWidgetItem(str(batch.get('Location_Name', '---'))))

        combo_action = QComboBox()
        combo_action.addItems(["Consommer (Sortie)", "Transférer (Lieu)"])
        combo_action.setStyleSheet(f"font-weight: 700; color: {BRAND_TEAL};")
        self.table.setCellWidget(row, 3, combo_action)

        dest_picker = LocationTreeComboBox(self.location_manager)
        dest_picker.setEnabled(False)
        dest_picker.setToolTip("Sélectionnez « Transférer (Lieu) » dans Action pour choisir une destination.")
        self.table.setCellWidget(row, 4, dest_picker)

        def _on_action_changed(t, p=dest_picker):
            is_tr = "Transférer" in t
            p.setEnabled(is_tr)
            p.setToolTip("" if is_tr else "Sélectionnez « Transférer (Lieu) » dans Action pour choisir une destination.")

        combo_action.currentTextChanged.connect(_on_action_changed)

        # إعداد حد الكمية
        try:
            max_qty = quantity_to_int(batch.get('Quantity_Current', 0))
        except:
            max_qty = 0
            
        qty_spin = NumericSpinBox()
        qty_spin.setRange(1, int(max_qty) if max_qty > 0 else 1)
        qty_spin.setValue(1)
        self.table.setCellWidget(row, 5, qty_spin)

        btn_del = QPushButton("✕")
        btn_del.setToolTip("Retirer cette ligne")
        btn_del.setStyleSheet(f"color: {STATUS_DANGER}; font-weight: 700; border: none; background: transparent;")
        btn_del.clicked.connect(lambda: self.table.removeRow(self.table.currentRow()))
        self.table.setCellWidget(row, 6, btn_del)

        self.table.scrollToBottom()

    # =========================================================================
    # CORE LOGIC FOR FEFO (First Expired First Out)
    # =========================================================================

    def parse_date(self, date_val):
        """
        تحويل ذكي للتواريخ من أي صيغة محتملة إلى datetime.date
        """
        if not date_val: 
            return None
            
        # 1. إذا كان كائن datetime (يحتوي على وقت)، استخرج التاريخ فقط
        if isinstance(date_val, datetime):
            return date_val.date()
            
        # 2. إذا كان كائن date جاهزاً
        if isinstance(date_val, date):
            return date_val
            
        # 3. إذا كان نصاً String (هنا تحدث معظم المشاكل)
        if isinstance(date_val, str):
            # إزالة المسافات وأي توقيت قد يكون ملحقاً (مثال: "2025-01-01 15:30:00")
            date_val_clean = date_val.split(" ")[0].strip()
            
            # محاولة الصيغة العالمية (SQL standard)
            try: return datetime.strptime(date_val_clean, "%Y-%m-%d").date()
            except: pass
            
            # محاولة الصيغة الفرنسية/الجزائرية
            try: return datetime.strptime(date_val_clean, "%d/%m/%Y").date()
            except: pass
            
            # محاولة صيغة أخرى
            try: return datetime.strptime(date_val_clean, "%d-%m-%Y").date()
            except: pass
            
        return None

    def get_oldest_batch(self, product_id, current_batch_id):
        """البحث عن أقدم دفعة صالحة لنفس المنتج (FEFO)"""
        oldest_batch = None
        oldest_date = None
        
        for b in self.inventory_pool:
            # 1. التحقق من تطابق المنتج (تحويل لسترينغ لضمان المطابقة)
            if str(b.get('Product_ID')) != str(product_id): 
                continue
                
            # 2. تجاهل الدفعة الحالية (التي تم مسحها)
            if str(b.get('Batch_ID')) == str(current_batch_id): 
                continue
            
            # 3. تجاهل الدفعات التي رصيدها صفر
            try:
                qty = quantity_to_int(b.get('Quantity_Current', 0))
                if qty <= 0: continue
            except: continue
            
            # 4. تحليل تاريخ الدفعة المرشحة
            raw_date = b.get('Expiry_Date')
            p_date = self.parse_date(raw_date)
            
            if not p_date: continue # تخطي إذا لم يوجد تاريخ

            # 5. مقارنة التواريخ للعثور على الأقدم (Min)
            if oldest_batch is None:
                oldest_batch = b
                oldest_date = p_date
            else:
                if p_date < oldest_date:
                    oldest_batch = b
                    oldest_date = p_date
                        
        return oldest_batch

    def check_fifo_and_get_target(self, current_batch):
        """
        التحقق وتوجيه المستخدم.
        Returns: (Should_Proceed: bool, Target_Batch: dict)
        """
        # 1. تحليل تاريخ الدفعة الحالية
        current_expiry = current_batch.get('Expiry_Date')
        current_date_obj = self.parse_date(current_expiry)
        
        # إذا الدفعة الحالية ليس لها تاريخ انتهاء، لا يمكننا فرض FEFO
        if not current_date_obj: 
            return True, current_batch
        
        # 2. البحث عن بديل أقدم
        oldest_batch = self.get_oldest_batch(current_batch.get('Product_ID'), current_batch.get('Batch_ID'))
        
        if oldest_batch:
            oldest_expiry = oldest_batch.get('Expiry_Date')
            oldest_date_obj = self.parse_date(oldest_expiry)
            
            # الشرط: هل التاريخ القديم أصغر (أقدم) من الحالي؟
            if oldest_date_obj and oldest_date_obj < current_date_obj:
                
                # إعداد التواريخ للعرض
                cur_str = current_date_obj.strftime("%d/%m/%Y")
                old_str = oldest_date_obj.strftime("%d/%m/%Y")
                
                msg = QMessageBox(self)
                msg.setWindowTitle("Alerte FEFO (Péremption)")
                msg.setIcon(QMessageBox.Warning)
                
                msg.setText("<b>Attention : Respect du FEFO</b>")
                info_text = (
                    f"<b>Lot scanné (plus récent) :</b><br>"
                    f"Lot : {current_batch.get('Lot_Number')} | Exp : <span style='color:{STATUS_DANGER}'>{cur_str}</span><br><br>"
                    
                    f"<b>Lot recommandé (expire bientôt) :</b><br>"
                    f"Lot : {oldest_batch.get('Lot_Number')} | Exp : <span style='color:{BRAND_TEAL}'>{old_str}</span><br>"
                    f"Emplacement : <b>{oldest_batch.get('Location_Name')}</b><br>"
                    f"Qté Dispo : {format_quantity(oldest_batch.get('Quantity_Current'))}"
                )
                msg.setInformativeText(info_text)
                
                btn_swap = msg.addButton("Utiliser le lot ancien (Recommandé)", QMessageBox.AcceptRole)
                btn_force = msg.addButton("Forcer ce lot", QMessageBox.ActionRole)
                btn_cancel = msg.addButton("Annuler", QMessageBox.RejectRole)
                
                msg.exec()
                
                if msg.clickedButton() == btn_swap:
                    return True, oldest_batch # استبدال تلقائي
                elif msg.clickedButton() == btn_force:
                    return True, current_batch # إصرار المستخدم
                else:
                    return False, None # إلغاء
                    
        return True, current_batch

    def execute_all(self):
        """تنفيذ جميع العمليات في الجدول"""
        if self.table.rowCount() == 0: return
        
        count = self.table.rowCount()
        confirm = QMessageBox.question(self, "Confirmation", f"Voulez-vous valider ces {count} opérations ?", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.No: return

        success_count = 0
        errors = []
        skipped_count = 0
        swapped_count = 0
        main_win = self.window()
        current_user = getattr(main_win, 'current_user', None)
        user_id = current_user.get('User_ID') if isinstance(current_user, dict) else None

        for r in range(self.table.rowCount()):
            # جلب البيانات
            item = self.table.item(r, 0)
            if not item: continue
            batch = item.data(Qt.UserRole)
            
            action = self.table.cellWidget(r, 3).currentText()
            qty = self.table.cellWidget(r, 5).value()
            
            try:
                if "Consommer" in action:
                    # ============ تطبيق منطق FEFO ============
                    should_proceed, target_batch = self.check_fifo_and_get_target(batch)
                    
                    if not should_proceed:
                        skipped_count += 1
                        continue 
                    
                    # التحقق هل تم التبديل
                    if str(target_batch.get('Batch_ID')) != str(batch.get('Batch_ID')):
                        swapped_count += 1
                        # التحقق من توفر الكمية في الدفعة الجديدة (القديمة زمنياً)
                        avail = quantity_to_int(target_batch.get('Quantity_Current', 0))
                        if qty > avail:
                            errors.append(f"Stock insuffisant sur le lot ancien ({format_quantity(avail)}) pour {target_batch.get('Product_Name')}")
                            continue

                    # تنفيذ الاستهلاك على target_batch (سواء كان الأصلي أو المستبدل)
                    res = self.manager.batches.direct_consume_batch_unit(
                        target_batch['Batch_ID'], qty, user_id=user_id
                    )
                
                else:
                    # التحويل (Transfer)
                    dest_id = self.table.cellWidget(r, 4).get_current_location_id()
                    if not dest_id:
                        errors.append(f"Destination manquante pour {batch.get('Product_Name')}")
                        continue
                    res = self.manager.batches.transfer_batch_location(
                        batch['Batch_ID'], dest_id, qty, user_id=user_id
                    )
                
                if res: success_count += 1
                else: errors.append(f"Erreur DB pour {batch.get('Product_Name')}")
                
            except Exception as e:
                logging.error(f"Execution Error: {e}")
                errors.append(f"Erreur technique: {str(e)}")

        # عرض التقرير النهائي
        summary = []
        if success_count > 0: summary.append(f"{success_count} opérations réussies.")
        if swapped_count > 0: summary.append(f"{swapped_count} lots échangés (FEFO).")
        if skipped_count > 0: summary.append(f"{skipped_count} opérations annulées.")
        
        final_msg = "\n".join(summary)
        if errors:
            final_msg += "\n\nErreurs :\n" + "\n".join(errors)
            QMessageBox.warning(self, "Résultat Partiel", final_msg)
        else:
            QMessageBox.information(self, "Succès", final_msg if final_msg else "Aucune opération.")
        
        # تحديث الواجهة والبيانات
        if not errors:
            self.table.setRowCount(0)
            
        self.load_inventory_pool() 
        self.data_changed.emit()

    def showEvent(self, event):
        super().showEvent(event)
        self.barcode_input.setFocus()
        self.load_inventory_pool()
