"""
reception_dialog_logic.py
--------------------------
Mixin يحتوي على كل المنطق الوظيفي لـ ReceptionDialog:
  - حساب المجاميع
  - التحقق من الرأس
  - إضافة / تعديل / حذف السطور
  - توليد الباركود
  - تحميل البيانات
  - إدارة حالة الحقول
"""
import logging
import random
from datetime import datetime

from PySide6.QtWidgets import QMessageBox, QInputDialog
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor

from ..bulk_barcode_selection_dialog import BulkBarcodeSelectionDialog
from ui.formatting import format_money, format_quantity, quantity_to_int


class ReceptionDialogLogicMixin:
    """Mixin يُضاف إلى ReceptionDialog لإدارة المنطق الوظيفي."""

    # ------------------------------------------------------------------ #
    #  إعداد الاتصالات                                                    #
    # ------------------------------------------------------------------ #
    def setup_connections(self):
        self.cb_product.currentIndexChanged.connect(self.on_product_selected)
        if hasattr(self, 'btn_add_ref'):
            self.btn_add_ref.clicked.connect(self.on_add_ref_clicked)
        if hasattr(self, 'cb_color'):
            self.cb_color.currentIndexChanged.connect(self._update_color_swatch)
            self.cb_color.editTextChanged.connect(self._update_color_swatch)

        for w in [self.inp_qty, self.inp_remise]:
            w.valueChanged.connect(self.calculate_live_item_ttc)
        self.cb_remise_type.currentIndexChanged.connect(self.calculate_live_item_ttc)

        if hasattr(self, 'inp_bon_remise'):
            self.inp_bon_remise.valueChanged.connect(self.on_bon_remise_changed)
        if hasattr(self, 'cb_bon_remise_type'):
            self.cb_bon_remise_type.currentIndexChanged.connect(self.on_bon_remise_changed)
        
        self.inp_price.valueChanged.connect(self.on_ht_changed)
        self.inp_price_ttc.valueChanged.connect(self.on_ttc_changed)
        self.chk_tva.stateChanged.connect(self.on_tva_toggled)

        self.btn_validate_ref.clicked.connect(self.validate_header_and_create)
        self.btn_unlock_header.clicked.connect(self.enable_header_editing)

        self.btn_add.clicked.connect(self.add_item_to_table)
        self.btn_modify.clicked.connect(self.load_item_for_edit)
        self.btn_delete.clicked.connect(self.delete_selected_row)
        self.btn_print.clicked.connect(self.print_selected_labels)
        self.btn_print_all.clicked.connect(self.open_bulk_print_dialog)

        self.table_items.cellDoubleClicked.connect(self.load_item_for_edit)

    # ------------------------------------------------------------------ #
    #  اختيار المنتج & الحساب الفوري                                     #
    # ------------------------------------------------------------------ #

    def _load_colors(self):
        self._colors_map = {}
        if not hasattr(self, 'cb_color'):
            return
        self.cb_color.blockSignals(True)
        self.cb_color.clear()
        self.cb_color.addItem("--- Standard / Non définie ---", {"Color_Name": "", "Color_Code": "#CBD5E1"})

        colors_list = []
        color_mgr = None
        if hasattr(self.manager, 'colors') and self.manager.colors:
            color_mgr = self.manager.colors
        elif hasattr(self.manager, 'db') and self.manager.db:
            try:
                from database.product_color_manager import ProductColorManager
                color_mgr = ProductColorManager(self.manager.db)
            except Exception:
                pass

        if not color_mgr and self.parent():
            p_mgr = getattr(self.parent(), 'manager', None)
            if p_mgr:
                if hasattr(p_mgr, 'colors') and p_mgr.colors:
                    color_mgr = p_mgr.colors
                elif hasattr(p_mgr, 'db') and p_mgr.db:
                    try:
                        from database.product_color_manager import ProductColorManager
                        color_mgr = ProductColorManager(p_mgr.db)
                    except Exception:
                        pass

        if color_mgr and hasattr(color_mgr, 'get_all_colors'):
            try:
                colors_list = color_mgr.get_all_colors(active_only=True)
            except Exception as e:
                logging.debug(f"Could not load colors in ReceptionDialog: {e}")

        if not colors_list:
            from database.product_color_manager import DEFAULT_PRODUCT_COLORS
            colors_list = [
                {"Color_Name": name, "Color_Code": code, "Description": desc}
                for name, code, desc in DEFAULT_PRODUCT_COLORS
            ]

        from PySide6.QtGui import QPixmap, QPainter, QBrush, QPen, QColor, QIcon

        for c in colors_list:
            name = str(c.get('Color_Name', '')).strip()
            code = str(c.get('Color_Code', '#CBD5E1')).strip()
            if not name:
                continue
            self._colors_map[name.lower()] = code

            pixmap = QPixmap(14, 14)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QBrush(QColor(code)))
            border_qcol = QColor("#94A3B8" if code.upper() in ("#FFFFFF", "#FDFBF7", "#F5F5DC") else "#475569")
            painter.setPen(QPen(border_qcol, 1))
            painter.drawRoundedRect(0, 0, 13, 13, 3, 3)
            painter.end()

            self.cb_color.addItem(QIcon(pixmap), name, {"Color_Name": name, "Color_Code": code})

        self.cb_color.blockSignals(False)
        self._update_color_swatch()

    def _update_color_swatch(self):
        if not hasattr(self, 'cb_color') or not hasattr(self, 'lbl_color_swatch'):
            return
        color_text = self.cb_color.currentText().strip()
        data = self.cb_color.currentData()
        hex_code = "#CBD5E1"

        if isinstance(data, dict) and data.get("Color_Code"):
            hex_code = data.get("Color_Code")
        elif hasattr(self, '_colors_map') and color_text.lower() in self._colors_map:
            hex_code = self._colors_map[color_text.lower()]
        elif color_text.startswith("#") and len(color_text) in (4, 7):
            hex_code = color_text
        elif color_text:
            try:
                from ui.widgets.appliance_desks.order_desk_view import COLOR_PALETTE
                hex_code = COLOR_PALETTE.get(color_text.lower(), "#CBD5E1")
            except Exception:
                hex_code = "#CBD5E1"

        border_col = "#94A3B8" if hex_code.upper() in ("#FFFFFF", "#FDFBF7", "#F5F5DC") else "rgba(0,0,0,0.25)"
        self.lbl_color_swatch.setStyleSheet(
            f"background-color: {hex_code}; border: 1px solid {border_col}; border-radius: 4px;"
        )
        display_name = color_text if not color_text.startswith("---") else "Standard / Non définie"
        self.lbl_color_swatch.setToolTip(f"Couleur / Finition : {display_name}\nCode Hex : {hex_code}")

    def set_selected_color(self, color_name: str):
        if not hasattr(self, 'cb_color'):
            return
        if not color_name:
            self.cb_color.setCurrentIndex(0)
            self._update_color_swatch()
            return

        c_clean = str(color_name).strip()
        found = False
        for i in range(self.cb_color.count()):
            item_text = self.cb_color.itemText(i)
            item_data = self.cb_color.itemData(i)
            cand_name = item_data.get("Color_Name") if isinstance(item_data, dict) else item_text
            if str(cand_name).strip().lower() == c_clean.lower() or str(item_text).strip().lower() == c_clean.lower():
                self.cb_color.setCurrentIndex(i)
                found = True
                break

        if not found:
            self.cb_color.setCurrentText(c_clean)
        self._update_color_swatch()

    def _load_product_references(self, product_data, selected_ref=None):
        """Charge les références (Réf) disponibles pour le produit sélectionné."""
        if not hasattr(self, 'cb_ref'):
            return
        self.cb_ref.blockSignals(True)
        self.cb_ref.clear()

        if not product_data:
            self.cb_ref.addItem("--- Réf ---", "")
            self.cb_ref.setEnabled(False)
            if hasattr(self, 'btn_add_ref'):
                self.btn_add_ref.setEnabled(False)
            self.cb_ref.blockSignals(False)
            return

        inputs_unlocked = self.cb_product.isEnabled()
        self.cb_ref.setEnabled(inputs_unlocked)
        if hasattr(self, 'btn_add_ref'):
            self.btn_add_ref.setEnabled(inputs_unlocked)

        pid = product_data.get('Product_ID')
        refs = []
        ref_mgr = getattr(self.manager, 'product_refs', None)
        if not ref_mgr and hasattr(self.manager, 'db') and self.manager.db:
            try:
                from database.product_reference_manager import ProductReferenceManager
                ref_mgr = ProductReferenceManager(self.manager.db)
            except Exception:
                ref_mgr = None

        if ref_mgr and hasattr(ref_mgr, 'get_references_for_product') and pid:
            try:
                refs = ref_mgr.get_references_for_product(pid) or []
            except Exception as e:
                logging.debug(f"Could not load product references: {e}")

        seen = set()
        for r in refs:
            code = str(r.get('Ref_Code') or '').strip()
            if not code or code in seen:
                continue
            seen.add(code)
            label = f"{code} (Principale)" if r.get('Is_Primary') else code
            self.cb_ref.addItem(label, code)

        if not seen:
            raw_all = str(product_data.get('All_Refs') or '').strip()
            if raw_all:
                for part in raw_all.split('|'):
                    code = part.strip()
                    if code and code not in seen:
                        seen.add(code)
                        self.cb_ref.addItem(code, code)
            else:
                fallback_code = str(
                    product_data.get('Primary_Ref')
                    or product_data.get('Manuf_Cat_No')
                    or ''
                ).strip()
                if fallback_code:
                    seen.add(fallback_code)
                    self.cb_ref.addItem(fallback_code, fallback_code)

        if not seen:
            self.cb_ref.addItem("--- Aucune Réf ---", "")

        if selected_ref:
            target = str(selected_ref).strip()
            idx = self.cb_ref.findData(target)
            if idx < 0 and target:
                if self.cb_ref.count() == 1 and self.cb_ref.itemData(0) == "":
                    self.cb_ref.clear()
                self.cb_ref.addItem(target, target)
                idx = self.cb_ref.findData(target)
            if idx >= 0:
                self.cb_ref.setCurrentIndex(idx)

        self.cb_ref.blockSignals(False)

    def on_add_ref_clicked(self):
        """Ajoute une nouvelle Réf directement au produit actuellement sélectionné."""
        p = self.cb_product.currentData()
        if not p:
            QMessageBox.warning(self, "Produit requis", "Veuillez d'abord sélectionner un produit.")
            return

        new_ref, ok = QInputDialog.getText(
            self,
            "Nouvelle Référence (Réf)",
            f"Ajouter une nouvelle Réf pour « {p.get('Product_Name', '')} » :"
        )
        if not ok:
            return

        new_ref = str(new_ref or '').strip()
        if not new_ref:
            return

        ref_mgr = getattr(self.manager, 'product_refs', None)
        if not ref_mgr and hasattr(self.manager, 'db') and self.manager.db:
            try:
                from database.product_reference_manager import ProductReferenceManager
                ref_mgr = ProductReferenceManager(self.manager.db)
            except Exception:
                ref_mgr = None

        if not ref_mgr or not hasattr(ref_mgr, 'add_reference'):
            QMessageBox.warning(self, "Indisponible", "Le gestionnaire de références n'est pas disponible.")
            return

        try:
            ref_mgr.add_reference(p['Product_ID'], new_ref)
        except Exception as exc:
            QMessageBox.warning(self, "Erreur Réf", str(exc))
            return

        self._load_product_references(p, selected_ref=new_ref)

    def on_product_selected(self):
        p = self.cb_product.currentData()
        self.cb_unit_type.clear()
        if not p:
            self.set_selected_color("")
            self._load_product_references(None)
            return
        col = p.get('Color_Finish') or ''
        self.set_selected_color(col)
        self._load_product_references(p)
        self.cb_unit_type.addItem(p.get('Stock_Unit', 'U'), 1.0)
        if p.get('Ordering_Unit') and p['Ordering_Unit'] != p.get('Stock_Unit'):
            self.cb_unit_type.addItem(p['Ordering_Unit'], float(p.get('Stock_Qty_Per_Order_Unit', 1.0)))

    def on_ht_changed(self):
        try:
            self.inp_price_ttc.blockSignals(True)
            tva_rate = 0.19 if hasattr(self, 'chk_tva') and self.chk_tva.isChecked() else 0.0
            ttc = self.inp_price.value() * (1 + tva_rate)
            self.inp_price_ttc.setValue(ttc)
        finally:
            self.inp_price_ttc.blockSignals(False)
        self.calculate_live_item_ttc()

    def on_ttc_changed(self):
        try:
            self.inp_price.blockSignals(True)
            tva_rate = 0.19 if hasattr(self, 'chk_tva') and self.chk_tva.isChecked() else 0.0
            ht = self.inp_price_ttc.value() / (1 + tva_rate)
            self.inp_price.setValue(ht)
        finally:
            self.inp_price.blockSignals(False)
        self.calculate_live_item_ttc()
        
    def on_tva_toggled(self):
        self.on_ht_changed()

    def calculate_live_item_ttc(self):
        try:
            if not hasattr(self, 'inp_qty') or not self.inp_qty:
                return
            qty      = float(self.inp_qty.value())
            price    = self.inp_price.value()
            rem_val  = self.inp_remise.value()
            rem_type = self.cb_remise_type.currentText()
            factor   = float(self.cb_unit_type.currentData() or 1.0)

            base_ht = qty * factor * price
            rem_amt = base_ht * (rem_val / 100) if rem_type == "%" else rem_val
            net_ht  = base_ht - rem_amt
            tax     = net_ht * 0.19 if self.chk_tva.isChecked() else 0
            ttc     = net_ht + tax

            self.lbl_item_ttc.setText(f"Total : {format_money(ttc, 'DA')}")

            if factor > 1:
                p_data  = self.cb_product.currentData()
                stock_u = p_data.get('Stock_Unit', 'U') if p_data else 'U'
                self.lbl_conversion_logic.setText(
                    f"💡 {format_quantity(qty)} {self.cb_unit_type.currentText()} = {format_quantity(qty * factor)} {stock_u} en stock."
                )
            else:
                self.lbl_conversion_logic.setText("💡 Saisie directe en unité de stockage.")
        except RuntimeError:
            pass

    # ------------------------------------------------------------------ #
    #  إدارة رأس الفاتورة                                                 #
    # ------------------------------------------------------------------ #
    def enable_header_editing(self):
        """إعادة فتح حقول الرأس للتعديل."""
        self.invoice_ref.setReadOnly(False)
        self.bl_ref.setReadOnly(False)
        self.reception_date.setReadOnly(False)
        if hasattr(self, 'cb_supplier') and not self.po_data.get('PO_ID'):
            self.cb_supplier.setEnabled(True)

        self.btn_validate_ref.setText(" Enregistrer")
        self.btn_validate_ref.setEnabled(True)
        self.btn_validate_ref.setStyleSheet("""
            QPushButton {
                background-color: #2980b9;
                color: white;
                font-weight: bold;
                padding: 6px 15px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #3498db; }
        """)
        self.btn_unlock_header.setVisible(False)
        self.toggle_inputs_state(False)
        self.invoice_ref.setFocus()

    def validate_header_and_create(self):
        """التحقق من الرأس، الحفظ، ثم فتح حقول المنتجات."""
        inv_ref = self.invoice_ref.text().strip()
        bl_ref  = self.bl_ref.text().strip()

        supplier_id = self.po_data.get('Supplier_ID')
        if not self.po_data.get('PO_ID') and hasattr(self, 'cb_supplier'):
            supplier_id = self.cb_supplier.currentData()
            if not supplier_id:
                QMessageBox.warning(
                    self, "Données manquantes",
                    "Veuillez sélectionner un fournisseur avant de valider."
                )
                self.cb_supplier.setFocus()
                return False
            self.po_data['Supplier_ID'] = supplier_id
            self.po_data['Supplier_Name'] = self.cb_supplier.currentText().strip()

        if not inv_ref and not bl_ref:
            QMessageBox.warning(
                self, "Données manquantes",
                "Veuillez saisir au moins une référence (Facture ou BL) avant de valider."
            )
            self.invoice_ref.setFocus()
            return False

        try:
            self.btn_validate_ref.setEnabled(False)
            self.btn_validate_ref.repaint()

            u_id = self.get_current_user_id()
            mgr  = self.manager.reception if hasattr(self.manager, 'reception') else self.manager

            header_data = {
                "PO_ID":                self.po_data.get('PO_ID'),
                "Supplier_ID":          supplier_id,
                "Supplier_Invoice_Ref": inv_ref,
                "Supplier_BL_Ref":      bl_ref,
                "Reception_Date":       self.reception_date.date().toPyDate(),
                "Created_By":           u_id
            }

            if not self.br_id:
                new_id = mgr.create_new_reception_header(header_data)
                if not new_id:
                    self.btn_validate_ref.setEnabled(True)
                    QMessageBox.critical(self, "Erreur Doublon", "Cette référence existe déjà.")
                    return False
                self.br_id = new_id
            else:
                mgr.update_reception_header_info(self.br_id, header_data)

            # تحديث حالة PO
            self.invoice_ref.setReadOnly(True)
            self.bl_ref.setReadOnly(True)
            self.reception_date.setReadOnly(True)
            if hasattr(self, 'cb_supplier'):
                self.cb_supplier.setEnabled(False)

            self.btn_validate_ref.setText(" Validé")
            self.btn_validate_ref.setStyleSheet(
                "background-color: #27ae60; color: white; font-weight: bold; border: none;"
            )
            self.btn_unlock_header.setVisible(True)
            self.toggle_inputs_state(True)
            self.cb_product.setFocus()
            return True

        except Exception as e:
            logging.error(f"Validation error: {e}")
            self.btn_validate_ref.setEnabled(True)
            QMessageBox.critical(self, "Erreur Système", str(e))
            return False

    # ------------------------------------------------------------------ #
    #  إدارة حالة الحقول                                                  #
    # ------------------------------------------------------------------ #
    def toggle_inputs_state(self, enabled: bool):
        widgets_to_toggle = [self.cb_product, self.cb_unit_type, self.inp_qty]
        if hasattr(self, 'cb_color'):
            widgets_to_toggle.append(self.cb_color)
        for w in widgets_to_toggle + [
            self.inp_lot, self.inp_expiry, self.cb_location,
            self.inp_price, self.inp_price_ttc, self.inp_remise, self.cb_remise_type,
            self.chk_tva, self.inp_observation,
            self.btn_add, self.btn_modify, self.btn_delete, self.btn_print,
            self.table_items,
        ]:
            w.setEnabled(enabled)
        has_prod = bool(self.cb_product.currentData())
        if hasattr(self, 'cb_ref'):
            self.cb_ref.setEnabled(enabled and has_prod)
        if hasattr(self, 'btn_add_ref'):
            self.btn_add_ref.setEnabled(enabled and has_prod)

    # ------------------------------------------------------------------ #
    #  المجاميع                                                            #
    # ------------------------------------------------------------------ #
    def on_bon_remise_changed(self):
        self.update_totals()
        if getattr(self, 'br_id', None):
            mgr = self.manager.reception if hasattr(self.manager, 'reception') else self.manager
            if hasattr(mgr, 'update_bon_discount'):
                val = self.inp_bon_remise.value() if hasattr(self, 'inp_bon_remise') else 0.0
                d_type = self.cb_bon_remise_type.currentText() if hasattr(self, 'cb_bon_remise_type') else '%'
                mgr.update_bon_discount(self.br_id, val, d_type)

    def update_totals(self):
        self.total_ht_val    = 0.0
        self.total_tva_val   = 0.0
        self.total_remise_val= 0.0
        self.bon_remise_amt  = 0.0
        self.total_ttc_val   = 0.0

        items_disc = 0.0
        for r in range(self.table_items.rowCount()):
            item = self.table_items.item(r, 0)
            if not item:
                continue
            meta = item.data(Qt.UserRole)
            if not meta:
                continue

            qty      = float(meta.get('Qty_Received', 0))
            price    = float(meta.get('Unit_Price_Received', 0.0))
            disc_amt = float(meta.get('Discount_Val', 0.0))
            tax_rate = float(meta.get('Tax_Rate_Percent', 0)) / 100.0

            line_ht     = qty * price
            line_net_ht = line_ht - disc_amt
            line_tva    = line_net_ht * tax_rate

            self.total_ht_val  += line_ht
            items_disc         += disc_amt
            self.total_tva_val += line_tva

        items_net_ht = max(0.0, self.total_ht_val - items_disc)
        bon_val = float(self.inp_bon_remise.value()) if hasattr(self, 'inp_bon_remise') else 0.0
        bon_type = self.cb_bon_remise_type.currentText() if hasattr(self, 'cb_bon_remise_type') else "%"
        if bon_type == "%":
            bon_disc_amt = items_net_ht * (bon_val / 100.0)
        else:
            bon_disc_amt = min(bon_val, items_net_ht)

        self.bon_remise_amt   = max(0.0, bon_disc_amt)
        self.total_remise_val = items_disc + self.bon_remise_amt
        self.total_ttc_val    = max(0.0, (self.total_ht_val - self.total_remise_val) + self.total_tva_val)

        self.lbl_total_ht.setText(format_money(self.total_ht_val, 'DA'))
        self.lbl_total_remise.setText(format_money(self.total_remise_val, 'DA'))
        self.lbl_total_tva.setText(format_money(self.total_tva_val, 'DA'))
        self.lbl_total_ttc.setText(format_money(self.total_ttc_val, 'DA'))

    # ------------------------------------------------------------------ #
    #  تحميل البيانات (وضع التعديل)                                      #
    # ------------------------------------------------------------------ #
    def load_reception_data(self):
        """تحميل بيانات الاستقبال في وضع التعديل."""
        if not self.reception_data or not self.reception_data.get('Header'):
            return

        if self.br_id:
            self.invoice_ref.setReadOnly(True)
            self.bl_ref.setReadOnly(True)
            self.reception_date.setReadOnly(True)
            if hasattr(self, 'cb_supplier'):
                self.cb_supplier.setEnabled(False)

            self.btn_validate_ref.setText(" Validé")
            self.btn_validate_ref.setEnabled(False)
            self.btn_validate_ref.setStyleSheet(
                "background-color: #27ae60; color: white; font-weight: bold; border: none;"
            )
            self.btn_unlock_header.setVisible(True)

        self.table_items.setSortingEnabled(False)

        header  = self.reception_data['Header']
        if hasattr(self, 'cb_supplier') and not self.po_data.get('PO_ID'):
            sup_id = header.get('Supplier_ID')
            if sup_id is not None:
                idx_sup = self.cb_supplier.findData(sup_id)
                if idx_sup >= 0:
                    self.cb_supplier.setCurrentIndex(idx_sup)
            if self.br_id:
                self.cb_supplier.setEnabled(False)
        inv_ref = header.get('Supplier_Invoice_Ref') or ''
        self.invoice_ref.setText(inv_ref)
        self.bl_ref.setText(header.get('Supplier_BL_Ref') or '')

        if header.get('Reception_Date'):
            r_date = header['Reception_Date']
            try:
                if isinstance(r_date, str):
                    qdate = QDate.fromString(r_date[:10], "yyyy-MM-dd")
                    if qdate.isValid():
                        self.reception_date.setDate(qdate)
                elif hasattr(r_date, 'year'):
                    self.reception_date.setDate(QDate(r_date.year, r_date.month, r_date.day))
            except Exception:
                pass

        if hasattr(self, 'inp_bon_remise') and hasattr(self, 'cb_bon_remise_type'):
            bon_val = float(header.get('Bon_Discount_Value') or 0.0)
            bon_type = header.get('Bon_Discount_Type') or '%'
            self.inp_bon_remise.blockSignals(True)
            self.cb_bon_remise_type.blockSignals(True)
            self.inp_bon_remise.setValue(bon_val)
            idx_bon_type = self.cb_bon_remise_type.findText(bon_type)
            if idx_bon_type >= 0:
                self.cb_bon_remise_type.setCurrentIndex(idx_bon_type)
            self.inp_bon_remise.blockSignals(False)
            self.cb_bon_remise_type.blockSignals(False)

        self.table_items.setRowCount(0)

        for batch in self.reception_data.get('Batches', []):
            row = self.table_items.rowCount()
            self.table_items.insertRow(row)

            qty      = float(batch.get('Quantity_Initial', 0))
            price    = float(batch.get('Unit_Price_Received', 0))
            tax_pct  = float(batch.get('Tax_Rate_Percent', 0))
            disc_pct = float(batch.get('Discount_Percent', 0))

            base_ht   = qty * price
            disc_amt  = base_ht * (disc_pct / 100)
            net_ht    = base_ht - disc_amt
            tva_amt   = net_ht * (tax_pct / 100)
            total_ttc = net_ht + tva_amt
            pu_ttc    = (total_ttc / qty) if qty > 0 else 0

            meta = {
                'Batch_ID':             batch.get('Batch_ID'),
                'Product_ID':           batch.get('Product_ID'),
                'Location_ID':          batch.get('Location_ID'),
                'Location_Name':        batch.get('Location_Name', '---'),
                'Lot_Number':           batch.get('Lot_Number', 'N/A'),
                'Expiry_Date':          str(batch.get('Expiry_Date', '')),
                'Ref_Code':             batch.get('Ref_Code') or batch.get('Primary_Ref') or '',
                'Color_Finish':         batch.get('Color_Finish', ''),
                'Qty_Received':         qty,
                'Unit_Price_Received':  price,
                'Discount_Val':         disc_amt,
                'Discount_Percent':     disc_pct,
                'Tax_Rate_Percent':     tax_pct,
                'Internal_Barcode':     batch.get('Internal_Barcode', '---'),
                'Line_Note':            batch.get('Reception_Note', ''),
                'Unit_Label':           batch.get('Stock_Unit', 'U'),
                'factor':               1.0
            }

            display_values = [
                batch.get('Product_Name', '---'),
                meta.get('Color_Finish') or '---',
                batch.get('Internal_Barcode', '---'),
                batch.get('Stock_Unit', 'U'),
                format_quantity(qty),
                meta['Lot_Number'],
                meta['Expiry_Date'],
                batch.get('Location_Name', '---'),
                format_money(price, 'DA'),
                format_money(disc_amt, 'DA'),
                format_money(net_ht, 'DA'),
                format_money(tva_amt, 'DA'),
                format_money(pu_ttc, 'DA'),
                format_money(total_ttc, 'DA')
            ]

            from PySide6.QtWidgets import QTableWidgetItem
            for col, value in enumerate(display_values):
                cell = QTableWidgetItem(str(value))
                cell.setTextAlignment(Qt.AlignCenter)
                self.table_items.setItem(row, col, cell)

            self.table_items.item(row, 0).setData(Qt.UserRole, meta)

        self.update_totals()
        self.table_items.setSortingEnabled(True)

    def load_items_from_db(self):
        """تحديث الجدول من قاعدة البيانات مباشرة لضمان المزامنة."""
        if not hasattr(self, 'br_id') or not self.br_id:
            return
        reception_mgr = self.manager.reception if hasattr(self.manager, 'reception') else self.manager
        details = reception_mgr.get_reception_full_details(self.br_id)
        if details:
            self.reception_data = details
            self.load_reception_data()

    # ------------------------------------------------------------------ #
    #  إضافة / تعديل / حذف                                               #
    # ------------------------------------------------------------------ #
    def add_item_to_table(self):
        """إضافة أو تعديل سطر في الجدول وقاعدة البيانات."""
        try:
            if not self.br_id:
                QMessageBox.warning(
                    self, "Action Requise",
                    "Veuillez valider l'en-tête (Bouton Valider) avant d'ajouter des produits."
                )
                self.invoice_ref.setFocus()
                return

            p_data = self.cb_product.currentData()
            loc_id = self.cb_location.get_current_location_id()

            if not p_data:
                QMessageBox.warning(self, "Données Incomplètes", "Veuillez sélectionner un produit valide.")
                self.cb_product.setFocus()
                return

            if loc_id is None:
                QMessageBox.warning(self, "Données Incomplètes", "Veuillez sélectionner un emplacement de stockage.")
                self.cb_location.setFocus()
                return

            qty = float(self.inp_qty.value())
            if qty <= 0:
                QMessageBox.warning(self, "Données Incomplètes", "La quantité reçue doit être strictement supérieure à zéro.")
                self.inp_qty.setFocus()
                return

            lot_num = self.inp_lot.text().strip()
            if not lot_num or lot_num.upper() in ["N/A", "NONE", "NULL", ""]:
                # Lot optionnel : génération automatique d'un identifiant interne pour respecter la contrainte DB NOT NULL
                lot_num = f"LOT-{datetime.now().strftime('%y%m%d%H%M%S')}"

            buy_price = float(self.inp_price.value())
            if buy_price <= 0:
                QMessageBox.warning(
                    self, "Données Incomplètes",
                    "Le prix unitaire d'achat HT doit être renseigné et strictement supérieur à zéro."
                )
                self.inp_price.setFocus()
                return

            u_id   = self.get_current_user_id()
            mgr    = self.manager.reception if hasattr(self.manager, 'reception') else self.manager

            factor       = float(self.cb_unit_type.currentData() or 1.0)
            effective_qty= qty * factor

            if self.current_editing_row != -1:
                old_meta       = self.table_items.item(self.current_editing_row, 0).data(Qt.UserRole)
                barcode_to_save= old_meta.get('Internal_Barcode')
            else:
                barcode_to_save= self.generate_internal_barcode()

            current_po_id = self.po_data.get('PO_ID')

            chosen_color = self.cb_color.currentText().strip() if hasattr(self, 'cb_color') else ""
            if chosen_color.startswith("---"):
                chosen_color = ""

            base_line_ht = effective_qty * buy_price
            rem_input = float(self.inp_remise.value())
            if self.cb_remise_type.currentText() == "%":
                disc_pct = rem_input
            else:
                disc_pct = min(100.0, (rem_input / base_line_ht) * 100.0) if base_line_ht > 0 else 0.0

            chosen_ref = (self.cb_ref.currentData() or '').strip() if hasattr(self, 'cb_ref') else ""

            line_data = {
                "BR_ID":               self.br_id,
                "PO_ID":               current_po_id,
                "Product_ID":          p_data['Product_ID'],
                "Location_ID":         loc_id,
                "Ref_Code":            chosen_ref,
                "Color_Finish":        chosen_color,
                "Quantity_Initial":    effective_qty,
                "Quantity_Current":    effective_qty,
                "Unit_Price_Received": buy_price,
                "Tax_Rate_Percent":    19.0 if self.chk_tva.isChecked() else 0.0,
                "Discount_Percent":    disc_pct,
                "Lot_Number":          lot_num,
                "Expiry_Date":         None,
                "Batch_Note":          self.inp_observation.text().strip(),
                "Internal_Barcode":    barcode_to_save,
                "Created_By":          u_id
            }

            if self.current_editing_row != -1:
                meta = self.table_items.item(self.current_editing_row, 0).data(Qt.UserRole)
                success, msg = mgr.update_reception_line(meta['Batch_ID'], line_data)
            else:
                success, msg = mgr.add_reception_line(line_data)

            if success:
                mgr._recalculate_reception_totals(self.br_id)
                self.load_items_from_db()
                self.clear_inputs()
            else:
                QMessageBox.critical(self, "Erreur", msg)

        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))

    def load_item_for_edit(self):
        try:
            row = self.table_items.currentRow()
            if row < 0:
                QMessageBox.warning(self, "Attention", "Veuillez sélectionner une ligne.")
                return

            item_0 = self.table_items.item(row, 0)
            if not item_0:
                return
            meta = item_0.data(Qt.UserRole)
            if not meta:
                return

            p_id = meta.get('Product_ID')
            for i in range(self.cb_product.count()):
                p_data = self.cb_product.itemData(i)
                if p_data and p_data.get('Product_ID') == p_id:
                    self.cb_product.setCurrentIndex(i)
                    break

            factor      = float(meta.get('factor', 1.0))
            qty_display = quantity_to_int(float(meta.get('Qty_Received', 0)) / factor)
            self.inp_qty.setValue(qty_display)

            idx_unit = self.cb_unit_type.findText(meta.get('Unit_Label', ''))
            if idx_unit >= 0:
                self.cb_unit_type.setCurrentIndex(idx_unit)

            col = meta.get('Color_Finish')
            p_curr = self.cb_product.currentData()
            if not col and p_curr:
                col = p_curr.get('Color_Finish')
            self.set_selected_color(col or "")
            self._load_product_references(p_curr, selected_ref=meta.get('Ref_Code') or '')

            self.chk_tva.setChecked(float(meta.get('Tax_Rate_Percent', 0)) > 0)
            self.inp_price.setValue(float(meta.get('Unit_Price_Received', 0.0)))

            if float(meta.get('Discount_Percent', 0)) > 0:
                self.cb_remise_type.setCurrentText("%")
                self.inp_remise.setValue(float(meta['Discount_Percent']))
            else:
                self.cb_remise_type.setCurrentText("DZD")
                self.inp_remise.setValue(float(meta.get('Discount_Val', 0.0)))

            self.inp_lot.setText(str(meta.get('Lot_Number', '')))
            exp_date_str = str(meta.get('Expiry_Date', ''))
            if exp_date_str and exp_date_str not in ['None', 'N/A', '']:
                q_date = QDate.fromString(exp_date_str, "yyyy-MM-dd")
                if q_date.isValid():
                    self.inp_expiry.setDate(q_date)

            location_name = meta.get('Location_Name', '---')
            if meta.get('Location_ID'):
                if not self.select_location_id(meta['Location_ID']):
                    self.cb_location.setCurrentText(location_name)
            else:
                self.cb_location.setCurrentText(location_name)

            self.inp_observation.setText(str(meta.get('Line_Note', '')))

            self.current_editing_row = row
            self.btn_add.setText("💾 Enregistrer Modif.")
            self.btn_add.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold;")
            self.calculate_live_item_ttc()

        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur de chargement: {str(e)}")

    def delete_selected_row(self):
        row = self.table_items.currentRow()
        if row < 0:
            return

        item_0 = self.table_items.item(row, 0)
        meta   = item_0.data(Qt.UserRole)
        batch_id = meta.get('Batch_ID')
        if not batch_id:
            return

        if QMessageBox.question(
            self, "Confirmation",
            "Supprimer définitivement ce produit du stock ?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            mgr = self.get_reception_mgr()
            success, msg = mgr.delete_reception_line(batch_id)
            if success:
                mgr._recalculate_reception_totals(self.br_id)
                self.load_items_from_db()
            else:
                QMessageBox.warning(self, "Action Impossible", msg)

    # ------------------------------------------------------------------ #
    #  الطباعة                                                             #
    # ------------------------------------------------------------------ #
    def print_selected_labels(self):
        rows = set(index.row() for index in self.table_items.selectedIndexes())
        if not rows:
            return
        for row in rows:
            meta         = self.table_items.item(row, 0).data(Qt.UserRole)
            product_name = (meta.get('Product_Name') if meta else None) or self.table_items.item(row, 0).text()
            barcode_val  = (meta.get('Internal_Barcode') if meta else None) or self.table_items.item(row, 2).text()
            lot          = (meta.get('Lot_Number') if meta else None) or self.table_items.item(row, 5).text()
            expiry       = (meta.get('Expiry_Date') if meta else None) or self.table_items.item(row, 6).text()
            qty          = int(meta.get('Qty_Received', 1))
            copies, ok   = QInputDialog.getInt(self, "Impression", f"Copies pour {product_name}", qty, 1, 1000)
            if ok:
                self.printer.print_label(product_name, barcode_val, lot, expiry, copies)

    def open_bulk_print_dialog(self):
        """فتح نافذة الطباعة الجماعية."""
        if self.table_items.rowCount() == 0:
            QMessageBox.information(self, "Info", "La liste est vide.")
            return

        items_to_process = []
        for row in range(self.table_items.rowCount()):
            item_0 = self.table_items.item(row, 0)
            if not item_0:
                continue
            meta = item_0.data(Qt.UserRole)
            if meta:
                meta['Product_Name'] = item_0.text()
                items_to_process.append(meta)

        dlg = BulkBarcodeSelectionDialog(items_to_process, self)
        if dlg.exec():
            selected     = dlg.get_items_to_print()
            total_labels = 0
            for index, item in enumerate(selected):
                qty    = int(item.get('Qty_Received', 1))
                name   = item.get('Product_Name', 'Inconnu')
                barcode= item.get('Internal_Barcode', '')
                lot    = item.get('Lot_Number', '')
                expiry = str(item.get('Expiry_Date', ''))
                if qty > 0:
                    self.printer.print_label(name, barcode, lot, expiry, qty)
                    total_labels += qty
                if index < len(selected) - 1:
                    self.printer.print_label("----------------", "   ", "---", "---", 1)

            QMessageBox.information(
                self, "Terminé", f"Ordre d'impression envoyé pour {total_labels} étiquettes."
            )

    # ------------------------------------------------------------------ #
    #  مساعدات                                                             #
    # ------------------------------------------------------------------ #
    def select_location_id(self, location_id):
        try:
            if location_id is None:
                return False
            for i in range(self.cb_location.count()):
                if self.cb_location.itemData(i) == location_id:
                    self.cb_location.setCurrentIndex(i)
                    return True
            return False
        except Exception:
            return False

    def get_reception_mgr(self):
        return self.manager.reception if hasattr(self.manager, 'reception') else self.manager

    def get_current_user_id(self):
        u_id          = None
        parent_widget = self.parent()
        while parent_widget:
            if hasattr(parent_widget, 'current_user') and isinstance(parent_widget.current_user, dict):
                u_id = parent_widget.current_user.get('User_ID')
                break
            parent_widget = parent_widget.parent()
        if u_id is None and hasattr(self.manager, 'current_user_id'):
            u_id = self.manager.current_user_id
        return u_id

    def is_barcode_exists_in_table(self, barcode):
        for row in range(self.table_items.rowCount()):
            item = self.table_items.item(row, 2)
            if item and item.text() == barcode:
                return True
            meta_item = self.table_items.item(row, 0)
            if meta_item:
                meta = meta_item.data(Qt.UserRole)
                if meta and meta.get('Internal_Barcode') == barcode:
                    return True
        return False

    def generate_internal_barcode(self):
        batch_mgr = self.manager.batches if hasattr(self.manager, 'batches') else None
        if not batch_mgr:
            from database.inventory_batch_manager import InventoryBatchManager
            batch_mgr = InventoryBatchManager(self.manager.db)

        po_id = self.po_data.get('PO_ID') or 0
        if hasattr(batch_mgr, 'get_barcode_prefix_for_po'):
            base_prefix = batch_mgr.get_barcode_prefix_for_po(po_id)
        else:
            base_prefix = str(po_id)

        if self.br_id and hasattr(batch_mgr, 'get_next_reception_barcode'):
            next_barcode = batch_mgr.get_next_reception_barcode(self.br_id, po_id=po_id)
        else:
            next_barcode = batch_mgr.get_next_smart_barcode(po_id)

        if hasattr(batch_mgr, 'extract_smart_barcode_serial'):
            serial = batch_mgr.extract_smart_barcode_serial(next_barcode, base_prefix) or 0
        else:
            serial = int(str(next_barcode)[len(base_prefix):])

        while self.is_barcode_exists_in_table(next_barcode):
            serial      += 1
            next_barcode = f"{base_prefix}{str(serial).zfill(3)}"
        return next_barcode

    def clear_inputs(self):
        self.cb_product.setCurrentIndex(0)
        self._load_product_references(None)
        self.cb_unit_type.clear()
        self.cb_location.setCurrentIndex(0)
        self.inp_lot.clear()
        self.inp_qty.setValue(1)
        self.inp_price.setValue(0.0)
        self.inp_price_ttc.setValue(0.0)
        self.inp_remise.setValue(0.0)
        self.inp_observation.clear()
        self.inp_expiry.setDate(QDate.currentDate().addYears(2))
        self.chk_tva.setChecked(False)
        self.current_editing_row = -1
        self.btn_add.setText(" Ajouter")
        self.btn_add.setStyleSheet("")
        self.cb_product.setFocus()

    def is_input_dirty(self):
        return (
            self.cb_product.currentIndex() > 0 or
            self.inp_lot.text().strip() != "" or
            self.inp_price.value() > 0
        )

    def get_reception_data(self):
        if self.table_items.rowCount() == 0:
            return None

        invoice_ref = self.invoice_ref.text().strip()
        bl_ref      = self.bl_ref.text().strip()

        doc_type = "None"
        if invoice_ref and bl_ref: doc_type = "Both"
        elif invoice_ref:          doc_type = "Facture"
        elif bl_ref:               doc_type = "BL"

        items = []
        for r in range(self.table_items.rowCount()):
            meta = self.table_items.item(r, 0).data(Qt.UserRole)
            if meta:
                items.append(meta)

        self.update_totals()

        header_data = {
            "BR_ID":               self.br_id,
            "PO_ID":               self.po_data.get('PO_ID'),
            "Supplier_ID":         self.po_data.get('Supplier_ID'),
            "Supplier_Invoice_Ref":invoice_ref or None,
            "Supplier_BL_Ref":     bl_ref or None,
            "Document_Type":       doc_type,
            "Reception_Date":      self.reception_date.date().toPyDate(),
            "Invoice_Total_HT":    round(self.total_ht_val, 2),
            "Invoice_Total_TVA":   round(self.total_tva_val, 2),
            "Invoice_Total_TTC":   round(self.total_ttc_val, 2),
            "Total_Discount":      round(self.total_remise_val, 2)
        }
        return header_data, items

    def highlight_target_row(self):
        if not self.target_batch_id:
            return
        found_row = -1
        for row in range(self.table_items.rowCount()):
            item = self.table_items.item(row, 0)
            if not item:
                continue
            meta = item.data(Qt.UserRole)
            if meta and meta.get('Batch_ID') == self.target_batch_id:
                found_row = row
                break

        if found_row != -1:
            from PySide6.QtWidgets import QAbstractItemView
            self.table_items.selectRow(found_row)
            self.table_items.scrollToItem(
                self.table_items.item(found_row, 0),
                QAbstractItemView.PositionAtCenter
            )
            green_brush = QColor("#d4edda")
            for col in range(self.table_items.columnCount()):
                cell = self.table_items.item(found_row, col)
                if cell:
                    cell.setBackground(green_brush)
                    f = cell.font()
                    f.setBold(True)
                    cell.setFont(f)
