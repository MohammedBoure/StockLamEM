from datetime import datetime
import logging
import qtawesome as qta
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QDateEdit,
    QPushButton, QFrame, QDoubleSpinBox, QCompleter, QCheckBox, QMessageBox, QLineEdit,
    QGridLayout, QGroupBox, QInputDialog
)
from PySide6.QtCore import Qt, QDate, QLocale
from PySide6.QtGui import QFont, QPixmap, QPainter, QBrush, QPen, QColor, QIcon

from ui.widgets.procurement.reception_dialog.auto_select_widgets import (
    AutoSelectSpinBox, AutoSelectDoubleSpinBox, AutoSelectLineEdit
)
from ui.widgets.inventory.location_tree_combo import LocationTreeComboBox

class QuickAddDialog(QDialog):
    def __init__(self, manager, parent=None, batch_data=None):
        super().__init__(parent)
        self.manager = manager
        self.batch_data = batch_data

        if batch_data:
            self.setWindowTitle("Modification Rapide (Détaillée)")
        else:
            self.setWindowTitle("Ajout Rapide au Stock (Détaillé)")

        self.setMinimumWidth(800)

        self.product_defaults = {}

        self._build_ui()
        self._setup_connections()
        self._load_products()

        if batch_data:
            self.btn_add.setText(" Enregistrer")
            self.chk_print.setChecked(False)
            self._prefill_data()

    def _prefill_data(self):
        d = self.batch_data

        # Product
        for i in range(self.cb_product.count()):
            p = self.cb_product.itemData(i)
            if p and p['Product_ID'] == d.get('Product_ID'):
                self.cb_product.setCurrentIndex(i)
                break

        # Location
        self.cb_location.select_location_id(d.get('Location_ID'))

        # Supplier
        supp_id = d.get('Supplier_ID')
        if supp_id:
            for i in range(self.cb_supplier.count()):
                if self.cb_supplier.itemData(i) == supp_id:
                    self.cb_supplier.setCurrentIndex(i)
                    break

        # Qty
        self.inp_qty.setValue(float(d.get('Quantity_Initial', 1)))

        # Lot, Exp
        self.inp_lot.setText(d.get('Lot_Number', ''))

        exp = d.get('Expiry_Date')
        from PySide6.QtCore import QDate
        if exp and str(exp).strip() and str(exp) != 'None':
            # handle str or date obj
            if isinstance(exp, str):
                parts = exp.split('-')
                if len(parts) == 3:
                    self.inp_expiry.setDate(QDate(int(parts[0]), int(parts[1]), int(parts[2])))
            else:
                self.inp_expiry.setDate(QDate(exp.year, exp.month, exp.day))

        # Prices
        self.inp_price.setValue(float(d.get('Unit_Price_Received') or 0))
        self.inp_remise.setValue(float(d.get('Discount_Percent') or 0))
        self.cb_remise_type.setCurrentText('%')
        self.chk_tva.setChecked(float(d.get('Tax_Rate_Percent') or 0) > 0)

        self.inp_sell_price.setValue(float(d.get('Selling_Price_HT') or 0))
        self.inp_sell_price_2.setValue(float(d.get('Selling_Price_HT_2') or 0))
        self.inp_sell_price_3.setValue(float(d.get('Selling_Price_HT_3') or 0))
        self.inp_sell_price_4.setValue(float(d.get('Selling_Price_HT_4') or 0))
        self.chk_sell_tva.setChecked(float(d.get('Selling_TVA_Percent') or 0) > 0)

        # Pre-select Color
        col = d.get('Color_Finish')
        if not col:
            p = self.cb_product.currentData()
            if p:
                col = p.get('Color_Finish')
        if col:
            self.set_selected_color(col)

        # Pre-select Réf
        existing_ref = d.get('Ref_Code') or d.get('Primary_Ref') or ''
        if self.cb_product.currentData():
            self._load_product_references(self.cb_product.currentData(), selected_ref=existing_ref)

        self.inp_observation.setText(d.get('Reception_Note') or d.get('Batch_Note') or '')
        self.inp_barcode.setText(d.get('External_Barcode') or '')
        if hasattr(self, 'inp_bl_number'):
            self.inp_bl_number.setText(d.get('BL_Number') or d.get('Supplier_BL_Ref') or '')

        self.calculate_live_item_ttc()
        self.calculate_live_sell_ttc()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)

        lbl_header = QLabel("Ajout Rapide d'un Produit")
        lbl_header.setFont(QFont("Arial", 14, QFont.Bold))
        lbl_header.setStyleSheet("color: #2980b9; padding-bottom: 5px;")
        lbl_header.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(lbl_header)

        # ---------------------------------------------------------
        # Product & Location Group
        # ---------------------------------------------------------
        grp_prod = QGroupBox("Produit et Emplacement")
        grp_prod.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #bdc3c7; border-radius: 4px; margin-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }")
        lay_prod = QGridLayout(grp_prod)
        lay_prod.setSpacing(10)

        self.cb_product = QComboBox()
        self.cb_product.setEditable(True)
        self.cb_product.setInsertPolicy(QComboBox.NoInsert)
        self.cb_product.setLineEdit(AutoSelectLineEdit())
        prod_completer = self.cb_product.completer()
        prod_completer.setFilterMode(Qt.MatchContains)
        prod_completer.setCaseSensitivity(Qt.CaseInsensitive)
        prod_completer.setCompletionMode(QCompleter.PopupCompletion)
        prod_completer.popup().setMinimumWidth(450)

        self.cb_unit_type = QComboBox()
        self.cb_unit_type.setMinimumWidth(100)

        self.cb_location = LocationTreeComboBox(self.manager.locations)
        self.cb_supplier = QComboBox()
        self.cb_supplier.setEditable(True)
        self.cb_supplier.completer().setFilterMode(Qt.MatchContains)
        self.cb_supplier.setLineEdit(AutoSelectLineEdit())

        lay_prod.addWidget(QLabel("Produit * :"), 0, 0)
        lay_prod.addWidget(self.cb_product, 0, 1, 1, 3)
        lay_prod.addWidget(QLabel("Unité :"), 0, 4)
        lay_prod.addWidget(self.cb_unit_type, 0, 5)

        lay_prod.addWidget(QLabel("Emplacement * :"), 1, 0)
        lay_prod.addWidget(self.cb_location, 1, 1, 1, 2)

        lay_prod.addWidget(QLabel("Fournisseur * :"), 1, 3)
        lay_prod.addWidget(self.cb_supplier, 1, 4, 1, 2)

        # Row 2: Color / Finish
        self.cb_color = QComboBox()
        self.cb_color.setEditable(True)
        self.cb_color.setInsertPolicy(QComboBox.NoInsert)
        if self.cb_color.completer():
            self.cb_color.completer().setFilterMode(Qt.MatchContains)
        self.cb_color.setLineEdit(AutoSelectLineEdit())
        if self.cb_color.lineEdit():
            self.cb_color.lineEdit().setPlaceholderText("Sélectionner ou saisir une couleur/finition")

        self.lbl_color_swatch = QLabel()
        self.lbl_color_swatch.setFixedSize(28, 26)
        self.lbl_color_swatch.setStyleSheet(
            "background-color: #CBD5E1; border: 1px solid #94A3B8; border-radius: 4px;"
        )
        self.lbl_color_swatch.setToolTip("Aperçu de la couleur sélectionnée")

        lay_color = QHBoxLayout()
        lay_color.setSpacing(8)
        lay_color.setContentsMargins(0, 0, 0, 0)
        lay_color.addWidget(self.cb_color, 1)
        lay_color.addWidget(self.lbl_color_swatch, 0)

        lay_prod.addWidget(QLabel("Couleur / Finition :"), 2, 0)
        lay_prod.addLayout(lay_color, 2, 1, 1, 2)

        # Row 2 (right): Réf du produit + bouton '+'
        self.cb_ref = QComboBox()
        self.cb_ref.setEnabled(False)
        self.cb_ref.addItem("--- Sélectionnez un produit ---", "")

        self.btn_add_ref = QPushButton("+")
        self.btn_add_ref.setFixedSize(28, 26)
        self.btn_add_ref.setCursor(Qt.PointingHandCursor)
        self.btn_add_ref.setEnabled(False)
        self.btn_add_ref.setToolTip("Ajouter une nouvelle Réf pour le produit sélectionné")
        self.btn_add_ref.setStyleSheet(
            "QPushButton { background-color: #e6f4f1; color: #007572; border: 1px solid #007572; "
            "border-radius: 4px; font-weight: bold; font-size: 14px; padding: 0px; margin: 0px; }"
            "QPushButton:hover { background-color: #007572; color: white; }"
            "QPushButton:disabled { background-color: #f1f5f9; color: #94a3b8; border-color: #cbd5e1; }"
        )

        lay_ref = QHBoxLayout()
        lay_ref.setSpacing(6)
        lay_ref.setContentsMargins(0, 0, 0, 0)
        lay_ref.addWidget(self.cb_ref, 1)
        lay_ref.addWidget(self.btn_add_ref, 0)

        lay_prod.addWidget(QLabel("Réf :"), 2, 3)
        lay_prod.addLayout(lay_ref, 2, 4, 1, 2)

        lbl_color_hint = QLabel("Finition électroménager (Inox, Blanc, Noir, Silver...)")
        lbl_color_hint.setStyleSheet("color: #7f8c8d; font-size: 11px; font-style: italic;")
        lay_prod.addWidget(lbl_color_hint, 3, 1, 1, 5)

        main_layout.addWidget(grp_prod)

        # ---------------------------------------------------------
        # Quantities & Dates Group
        # ---------------------------------------------------------
        grp_qty = QGroupBox("Quantité, Lot et Validité")
        grp_qty.setStyleSheet(grp_prod.styleSheet())
        lay_qty = QHBoxLayout(grp_qty)
        lay_qty.setSpacing(15)

        self.inp_qty = AutoSelectSpinBox()
        self.inp_qty.setRange(0, 999999)
        self.inp_qty.setValue(1)

        self.inp_lot = AutoSelectLineEdit()
        self.inp_lot.setPlaceholderText("N° de lot (optionnel)")

        self.inp_expiry = QDateEdit(QDate.currentDate().addYears(2))
        self.inp_expiry.setCalendarPopup(True)

        self.inp_barcode = AutoSelectLineEdit()
        self.inp_barcode.setPlaceholderText("Scanner ou saisir (Optionnel)")

        lay_qty.addWidget(QLabel("Quantité * :"))
        lay_qty.addWidget(self.inp_qty)
        lay_qty.addWidget(QLabel("Lot * :"))
        lay_qty.addWidget(self.inp_lot)
        lbl_exp = QLabel("Exp * :")
        lbl_exp.setVisible(False)
        self.inp_expiry.setVisible(False)
        lay_qty.addWidget(lbl_exp)
        lay_qty.addWidget(self.inp_expiry)
        lay_qty.addWidget(QLabel("Code Barre Ext :"))
        lay_qty.addWidget(self.inp_barcode)

        main_layout.addWidget(grp_qty)

        # ---------------------------------------------------------
        # Purchase Prices Group
        # ---------------------------------------------------------
        grp_achat = QGroupBox("Prix d'Achat")
        grp_achat.setStyleSheet(grp_prod.styleSheet())
        lay_achat = QGridLayout(grp_achat)
        lay_achat.setSpacing(10)

        self.inp_price = AutoSelectDoubleSpinBox()
        self.inp_price.setRange(0, 99999999.99)
        self.inp_price.setDecimals(2)
        self.inp_price.setGroupSeparatorShown(True)

        self.inp_price_ttc = AutoSelectDoubleSpinBox()
        self.inp_price_ttc.setRange(0, 99999999.99)
        self.inp_price_ttc.setDecimals(2)
        self.inp_price_ttc.setGroupSeparatorShown(True)

        self.inp_remise = AutoSelectDoubleSpinBox()
        self.inp_remise.setRange(0, 99999999.99)
        self.inp_remise.setDecimals(2)

        self.cb_remise_type = QComboBox()
        self.cb_remise_type.addItems(["%", "DA"])

        self.chk_tva = QCheckBox("TVA 19%")
        self.chk_tva.setChecked(False)
        self.chk_tva.setVisible(False)

        self.lbl_item_ttc = QLabel("Total : 0.00 DA")
        self.lbl_item_ttc.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 14px;")

        lay_achat.addWidget(QLabel("Prix d'Achat :"), 0, 0)
        lay_achat.addWidget(self.inp_price, 0, 1)
        lbl_prix_ttc = QLabel("Prix TTC:")
        lbl_prix_ttc.setVisible(False)
        self.inp_price_ttc.setVisible(False)
        lay_achat.addWidget(lbl_prix_ttc, 0, 2)
        lay_achat.addWidget(self.inp_price_ttc, 0, 3)

        lay_achat.addWidget(QLabel("Remise:"), 1, 0)
        lay_rem = QHBoxLayout()
        lay_rem.addWidget(self.inp_remise)
        lay_rem.addWidget(self.cb_remise_type)
        lay_achat.addLayout(lay_rem, 1, 1)

        lay_achat.addWidget(self.chk_tva, 1, 2)
        lay_achat.addWidget(self.lbl_item_ttc, 1, 3, alignment=Qt.AlignRight)

        main_layout.addWidget(grp_achat)

        # ---------------------------------------------------------
        # Selling Prices Group
        # ---------------------------------------------------------
        grp_vente = QGroupBox("Prix de Vente")
        grp_vente.setStyleSheet(grp_prod.styleSheet())
        lay_vente = QGridLayout(grp_vente)
        lay_vente.setSpacing(10)

        self.inp_sell_price = AutoSelectDoubleSpinBox()
        self.inp_sell_price_2 = AutoSelectDoubleSpinBox()
        self.inp_sell_price_3 = AutoSelectDoubleSpinBox()
        self.inp_sell_price_4 = AutoSelectDoubleSpinBox()

        for sp in [self.inp_sell_price, self.inp_sell_price_2, self.inp_sell_price_3, self.inp_sell_price_4]:
            sp.setRange(0, 99999999.99)
            sp.setDecimals(2)
            sp.setGroupSeparatorShown(True)

        self.chk_sell_tva = QCheckBox("TVA Vente 19%")
        self.chk_sell_tva.setChecked(False)
        self.chk_sell_tva.setVisible(False)

        self.lbl_sell_ttc = QLabel("Prix Vente : 0.00 DA")
        self.lbl_sell_ttc.setStyleSheet("color: #27ae60; font-weight: bold; font-size: 14px;")
        self.lbl_sell_ttc.setVisible(False)

        lay_vente.addWidget(QLabel("Vente 1 :"), 0, 0)
        lay_vente.addWidget(self.inp_sell_price, 0, 1)
        lay_vente.addWidget(QLabel("Vente 2 :"), 0, 2)
        lay_vente.addWidget(self.inp_sell_price_2, 0, 3)

        lay_vente.addWidget(QLabel("Vente 3 :"), 1, 0)
        lay_vente.addWidget(self.inp_sell_price_3, 1, 1)
        lay_vente.addWidget(QLabel("Vente 4 :"), 1, 2)
        lay_vente.addWidget(self.inp_sell_price_4, 1, 3)

        lay_vente.addWidget(self.chk_sell_tva, 2, 0, 1, 2)
        lay_vente.addWidget(self.lbl_sell_ttc, 2, 2, 1, 2, alignment=Qt.AlignRight)

        main_layout.addWidget(grp_vente)

        # ---------------------------------------------------------
        # Observation & Actions
        # ---------------------------------------------------------
        lay_obs = QHBoxLayout()
        self.inp_bl_number = AutoSelectLineEdit()
        self.inp_bl_number.setPlaceholderText("N° Bon de Livraison (Optionnel)")
        self.inp_observation = AutoSelectLineEdit()
        self.inp_observation.setPlaceholderText("Observation (Optionnel)")
        lay_obs.addWidget(QLabel("N° BL (Opt.):"))
        lay_obs.addWidget(self.inp_bl_number, 1)
        lay_obs.addWidget(QLabel("Observation:"))
        lay_obs.addWidget(self.inp_observation, 2)
        main_layout.addLayout(lay_obs)

        self.chk_print = QCheckBox("Imprimer l'étiquette après l'ajout")
        self.chk_print.setChecked(True)
        self.chk_print.setStyleSheet("color: #8e44ad; font-weight: bold;")
        main_layout.addWidget(self.chk_print)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(line)

        btns = QHBoxLayout()
        btns.addStretch()

        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_add = QPushButton(" Ajouter")
        self.btn_add.setIcon(qta.icon('fa5s.plus', color='white'))
        self.btn_add.setStyleSheet("""
            QPushButton {
                background-color: #27ae60; color: white; font-weight: bold; padding: 6px 15px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #2ecc71; }
        """)
        self.btn_add.clicked.connect(self.validate_and_accept)

        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_add)
        main_layout.addLayout(btns)

    def _setup_connections(self):
        self.cb_product.currentIndexChanged.connect(self.on_product_selected)
        self.btn_add_ref.clicked.connect(self.on_add_ref_clicked)
        self.cb_color.currentIndexChanged.connect(self._update_color_swatch)
        self.cb_color.editTextChanged.connect(self._update_color_swatch)

        # Calculate TTC for purchase
        self.inp_price.valueChanged.connect(lambda: self.on_price_changed('ht'))
        self.inp_price_ttc.valueChanged.connect(lambda: self.on_price_changed('ttc'))
        self.inp_remise.valueChanged.connect(self.calculate_live_item_ttc)
        self.cb_remise_type.currentIndexChanged.connect(self.calculate_live_item_ttc)
        self.chk_tva.toggled.connect(self.calculate_live_item_ttc)
        self.inp_qty.valueChanged.connect(self.calculate_live_item_ttc)

        # Calculate TTC for sell
        self.inp_sell_price.valueChanged.connect(self.calculate_live_sell_ttc)
        self.chk_sell_tva.toggled.connect(self.calculate_live_sell_ttc)

        self.cb_unit_type.currentIndexChanged.connect(self.on_unit_type_changed)

    def _load_products(self):
        all_products = self.manager.products.get_all_products()
        self.cb_product.addItem("--- Sélectionnez un produit ---", None)
        for p in all_products:
            brand = p.get('Manuf_Name') or "---"
            ref = p.get('All_Refs') or p.get('Primary_Ref') or p.get('Manuf_Cat_No') or p.get('Reference') or p.get('Product_Code') or p.get('Barcode') or "---"
            self.cb_product.addItem(f"{p['Product_Name']}  |  Réf: {ref}  ({brand})", p)

        # Load Suppliers
        self.cb_supplier.addItem("--- Sans Fournisseur ---", None)
        try:
            conn = self.manager.db.get_raw_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT Supplier_ID, Supplier_Name FROM Suppliers WHERE Deleted_At IS NULL ORDER BY Supplier_Name")
            for row in cursor.fetchall():
                self.cb_supplier.addItem(row['Supplier_Name'], row['Supplier_ID'])
            conn.close()
        except:
            pass

        # Load Colors / Finishes
        self._load_colors()


    def _load_colors(self):
        self._colors_map = {}
        self.cb_color.blockSignals(True)
        self.cb_color.clear()
        self.cb_color.addItem("--- Non définie / Standard ---", {"Color_Name": "", "Color_Code": "#CBD5E1"})

        colors_list = []
        color_mgr = getattr(self.manager, 'colors', None)
        if not color_mgr and hasattr(self.manager, 'db') and self.manager.db:
            try:
                from database.product_color_manager import ProductColorManager
                color_mgr = ProductColorManager(self.manager.db)
            except Exception:
                color_mgr = None

        if color_mgr and hasattr(color_mgr, 'get_all_colors'):
            try:
                colors_list = color_mgr.get_all_colors(active_only=True)
            except Exception as e:
                logging.debug(f"Could not load colors via manager: {e}")

        if not colors_list:
            from database.product_color_manager import DEFAULT_PRODUCT_COLORS
            colors_list = [
                {"Color_Name": name, "Color_Code": code, "Description": desc}
                for name, code, desc in DEFAULT_PRODUCT_COLORS
            ]

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
        self.cb_ref.blockSignals(True)
        self.cb_ref.clear()

        if not product_data:
            self.cb_ref.addItem("--- Sélectionnez un produit ---", "")
            self.cb_ref.setEnabled(False)
            self.btn_add_ref.setEnabled(False)
            self.cb_ref.blockSignals(False)
            return

        self.cb_ref.setEnabled(True)
        self.btn_add_ref.setEnabled(True)

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
            self.inp_price.setValue(0)
            self.inp_sell_price.setValue(0)
            self.set_selected_color("")
            self._load_product_references(None)
            return

        # Pre-select product color finish if present
        color = p.get('Color_Finish') or ''
        self.set_selected_color(color)
        self._load_product_references(p)

        # Units
        self.cb_unit_type.addItem(p.get('Base_Unit_Name', 'Unité'), 1)
        if p.get('Package_Unit_Name') and p.get('Units_per_Package'):
            self.cb_unit_type.addItem(p['Package_Unit_Name'], int(p['Units_per_Package']))

        self.chk_tva.setChecked(False)
        self.chk_sell_tva.setChecked(False)

        self.inp_sell_price.setValue(float(p.get('Default_Selling_Price_HT', 0)))

        self.calculate_live_item_ttc()
        self.calculate_live_sell_ttc()

    def on_unit_type_changed(self):
        pass

    def on_price_changed(self, source='ht'):
        if not self.cb_product.currentData(): return
        self.inp_price.blockSignals(True)
        self.inp_price_ttc.blockSignals(True)

        tva = 1.19 if self.chk_tva.isChecked() else 1.0
        if source == 'ht':
            ht = self.inp_price.value()
            self.inp_price_ttc.setValue(ht * tva)
        else:
            ttc = self.inp_price_ttc.value()
            self.inp_price.setValue(ttc / tva)

        self.inp_price.blockSignals(False)
        self.inp_price_ttc.blockSignals(False)
        self.calculate_live_item_ttc()

    def calculate_live_item_ttc(self):
        ht = self.inp_price.value()
        remise = self.inp_remise.value()

        if self.cb_remise_type.currentText() == '%':
            ht = ht * (1 - remise / 100.0)
        else:
            ht = ht - remise

        if ht < 0: ht = 0

        tva = 1.19 if self.chk_tva.isChecked() else 1.0
        ttc = ht * tva
        qty = self.inp_qty.value()

        factor = self.cb_unit_type.currentData() or 1
        total = ttc * (qty * factor)

        self.lbl_item_ttc.setText(f"TTC Total : {total:,.2f} DA")

    def calculate_live_sell_ttc(self):
        ht = self.inp_sell_price.value()
        tva = 1.19 if self.chk_sell_tva.isChecked() else 1.0
        ttc = ht * tva
        self.lbl_sell_ttc.setText(f"TTC Vente : {ttc:,.2f} DA")

    def validate_and_accept(self):
        p_data = self.cb_product.currentData()
        loc_id = self.cb_location.get_current_location_id()
        supplier_id = self.cb_supplier.currentData()
        lot_number = self.inp_lot.text().strip()
        qty = self.inp_qty.value()
        buy_price = self.inp_price.value()
        sell_price = self.inp_sell_price.value()

        if not p_data:
            QMessageBox.warning(self, "Données Incomplètes", "Veuillez sélectionner un produit valide.")
            self.cb_product.setFocus()
            return

        if loc_id is None:
            QMessageBox.warning(self, "Données Incomplètes", "Veuillez sélectionner un emplacement de stockage.")
            self.cb_location.setFocus()
            return

        if not supplier_id:
            QMessageBox.warning(self, "Données Incomplètes", "Veuillez sélectionner le fournisseur du produit (obligatoire).")
            self.cb_supplier.setFocus()
            return

        if qty <= 0:
            QMessageBox.warning(self, "Données Incomplètes", "La quantité doit être strictement supérieure à zéro.")
            self.inp_qty.setFocus()
            return

        if buy_price <= 0:
            QMessageBox.warning(self, "Données Incomplètes", "Le prix d'achat HT unitaire doit être renseigné et supérieur à 0.")
            self.inp_price.setFocus()
            return

        if sell_price <= 0:
            QMessageBox.warning(self, "Données Incomplètes", "Le prix de vente HT (Vente 1) doit être renseigné et supérieur à 0.")
            self.inp_sell_price.setFocus()
            return

        self.accept()

    def get_data(self):
        p_data = self.cb_product.currentData()
        factor = self.cb_unit_type.currentData() or 1
        effective_qty = self.inp_qty.value() * factor

        remise = self.inp_remise.value()
        if self.cb_remise_type.currentText() == 'DA':
            # convert DA to percentage relative to price
            base_price = self.inp_price.value()
            discount_pct = (remise / base_price * 100) if base_price > 0 else 0
        else:
            discount_pct = remise

        chosen_color = self.cb_color.currentText().strip()
        if chosen_color.startswith("---"):
            chosen_color = ""

        raw_lot = self.inp_lot.text().strip()
        if not raw_lot or raw_lot.upper() in ("N/A", "NONE", "NULL"):
            raw_lot = f"LOT-{datetime.now().strftime('%y%m%d%H%M%S')}"

        return {
            'Product_ID': p_data['Product_ID'],
            'Product_Name': p_data['Product_Name'],
            'Location_ID': self.cb_location.get_current_location_id(),
            'Ref_Code': (self.cb_ref.currentData() or '').strip(),
            'Color_Finish': chosen_color,
            'Quantity': effective_qty,
            'Lot_Number': raw_lot,
            'Expiry_Date': None,
            'Unit_Price_HT': self.inp_price.value(),
            'Discount_Percent': discount_pct,
            'Tax_Rate_Percent': 0.0,

            'Selling_Price_HT': self.inp_sell_price.value(),
            'Selling_Price_HT_2': self.inp_sell_price_2.value(),
            'Selling_Price_HT_3': self.inp_sell_price_3.value(),
            'Selling_Price_HT_4': self.inp_sell_price_4.value(),
            'Selling_TVA_Percent': 0.0,

            'Batch_Note': self.inp_observation.text().strip(),
            'BL_Number': self.inp_bl_number.text().strip(),
            'External_Barcode': self.inp_barcode.text().strip(),

            'Supplier_ID': self.cb_supplier.currentData(),
            'Print_Label': self.chk_print.isChecked(),
        }
