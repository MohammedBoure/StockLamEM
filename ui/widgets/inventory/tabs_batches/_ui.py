# ui/widgets/inventory/tabs_batches/_ui.py
"""
بناء واجهة المستخدم: فلاتر، الجدول، شريط الأدوات السفلي
"""

from PySide6.QtWidgets import (
    QVBoxLayout, QTableWidget, QHeaderView,
    QFrame, QLabel, QLineEdit, QPushButton, QHBoxLayout,
    QGroupBox, QComboBox, QDateEdit, QCheckBox, QAbstractItemView
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont

from ..location_tree_combo import LocationTreeComboBox
from ._table import BatchesVerticalHeader


def build_ui(self):
    """تهيئة كامل الواجهة بتصميم أبيض ناصع وعصري وربطها بـ self"""
    self.setStyleSheet("""
        QWidget#BatchesTabRoot {
            background-color: #ffffff;
        }
        QGroupBox {
            font-weight: bold;
            color: #007572;
            border: 1px solid #dcdfe6;
            border-radius: 6px;
            margin-top: 6px;
            background-color: #ffffff;
            padding-top: 14px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 6px;
            background-color: #ffffff;
            color: #007572;
        }
        QLineEdit, QComboBox, QDateEdit {
            background-color: #ffffff;
            border: 1px solid #ced4da;
            border-radius: 4px;
            padding: 2px 8px;
            min-height: 28px;
            height: 28px;
            font-size: 12px;
            color: #2c3e50;
        }
        QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
            border: 1.5px solid #007572;
            background-color: #ffffff;
        }
        QCheckBox {
            background-color: transparent;
            font-size: 12px;
            color: #2c3e50;
        }
        QLabel {
            background-color: transparent;
            font-size: 12px;
            color: #2c3e50;
        }
        QTableWidget {
            background-color: #ffffff;
            border: 1px solid #dcdfe6;
            gridline-color: #f1f5f9;
            font-size: 12px;
            color: #2c3e50;
            selection-background-color: #e6f4f1;
            selection-color: #007572;
        }
        QHeaderView::section {
            background-color: #f8fafc;
            color: #2c3e50;
            font-weight: bold;
            font-size: 12px;
            border: none;
            border-bottom: 2px solid #007572;
            border-right: 1px solid #e2e8f0;
            padding: 5px 8px;
        }
    """)
    self.setObjectName("BatchesTabRoot")

    layout = QVBoxLayout(self)
    layout.setSpacing(6)
    layout.setContentsMargins(6, 6, 6, 6)

    layout.addWidget(_build_filter_group(self))
    layout.addWidget(_build_table(self))
    layout.addWidget(_build_bottom_bar(self))

    self.table.doubleClicked.connect(self.show_batch_details)


# ---------------------------------------------------------------------------
# منطقة الفلاتر
# ---------------------------------------------------------------------------

def _build_filter_group(self):
    filter_group = QGroupBox("🔍 Recherche & Filtres Avancés")

    main_filter_layout = QHBoxLayout(filter_group)
    main_filter_layout.setContentsMargins(10, 15, 10, 10)

    left_layout = _build_left_filters(self)
    main_filter_layout.addLayout(left_layout, 2)

    line = QFrame()
    line.setFrameShape(QFrame.VLine)
    line.setFrameShadow(QFrame.Sunken)
    main_filter_layout.addWidget(line)

    right_layout = _build_right_filters(self)
    main_filter_layout.addLayout(right_layout, 1)

    return filter_group


def _build_left_filters(self):
    left_layout = QVBoxLayout()
    left_layout.setSpacing(8)

    # الصف 1: بحث نصي + موقع
    row1 = QHBoxLayout()
    self.search_input = QLineEdit()
    self.search_input.setPlaceholderText("🔎 Produit, Code-barres, Lot...")
    self.search_input.setClearButtonEnabled(True)
    self.search_input.returnPressed.connect(self.load_data)
    self.search_input.textChanged.connect(self.apply_filters_local)

    self.loc_filter = LocationTreeComboBox(self.manager.locations)
    self.loc_filter.setPlaceholderText("📍 Emplacement")
    self.loc_filter.setMinimumWidth(180)
    self.loc_filter.currentIndexChanged.connect(self.apply_filters_local)

    row1.addWidget(self.search_input)
    row1.addWidget(self.loc_filter)
    left_layout.addLayout(row1)

    # الصف 2: القوائم المنسدلة
    row2 = QHBoxLayout()

    self.combo_family = QComboBox()
    self.combo_family.addItem("📁 Familles", None)
    self.combo_family.setMinimumWidth(125)
    self.populate_families()
    self.combo_family.currentIndexChanged.connect(self.apply_filters_local)

    self.combo_manuf = QComboBox()
    self.combo_manuf.addItem("🏭 Marques", None)
    self.combo_manuf.setMinimumWidth(125)
    self.populate_manufacturers()
    self.combo_manuf.currentIndexChanged.connect(self.apply_filters_local)

    self.combo_automate = QComboBox()
    self.combo_automate.addItem("⚙️ Automates", None)
    self.combo_automate.setMinimumWidth(125)
    self.populate_automates()
    self.combo_automate.currentIndexChanged.connect(self.apply_filters_local)
    self.combo_automate.setVisible(False)

    self.combo_supplier = QComboBox()
    self.combo_supplier.addItem("🚚 Fournisseurs", None)
    self.combo_supplier.setMinimumWidth(130)
    self.populate_suppliers()
    self.combo_supplier.currentIndexChanged.connect(self.apply_filters_local)

    self.combo_status = QComboBox()
    self.combo_status.addItems([
        "📋 Tous (>0)", "✅ En Stock", "⚠️ Faible (Seuil)",
        "⭕ Épuisé (Qté=0)", "🗑️ Rebuts / Pertes"
    ])
    self.combo_status.setMinimumWidth(130)
    self.combo_status.setCurrentIndex(1)
    self.combo_status.currentIndexChanged.connect(self.load_data)

    self.combo_priority_group = QComboBox()
    self.combo_priority_group.addItem("⭐ Groupes Vente", None)
    self.combo_priority_group.setMinimumWidth(130)
    self.combo_priority_group.currentIndexChanged.connect(self.apply_filters_local)

    row2.addWidget(self.combo_family)
    row2.addWidget(self.combo_manuf)
    row2.addWidget(self.combo_automate)
    row2.addWidget(self.combo_supplier)
    row2.addWidget(self.combo_status)
    row2.addWidget(self.combo_priority_group)
    left_layout.addLayout(row2)

    return left_layout


def _build_right_filters(self):
    right_layout = QVBoxLayout()
    right_layout.setSpacing(5)

    # فلتر تاريخ الانتهاء (مخفي حسب طلب العميل)
    exp_layout = QHBoxLayout()
    self.chk_date_filter = QCheckBox("Date Expiration:")
    self.chk_date_filter.setStyleSheet("font-weight: bold; color: #c0392b;")
    self.chk_date_filter.setChecked(False)
    self.chk_date_filter.stateChanged.connect(self.toggle_date_filter)

    self.date_from = QDateEdit(QDate.currentDate())
    self.date_from.setCalendarPopup(True)
    self.date_from.setEnabled(False)
    self.date_from.setFixedWidth(135)
    self.date_from.dateChanged.connect(self.apply_filters_local)

    self.date_to = QDateEdit(QDate.currentDate().addYears(1))
    self.date_to.setCalendarPopup(True)
    self.date_to.setEnabled(False)
    self.date_to.setFixedWidth(135)
    self.date_to.dateChanged.connect(self.apply_filters_local)

    lbl_exp_du = QLabel("Du:")
    lbl_exp_au = QLabel("Au:")
    for w in (self.chk_date_filter, lbl_exp_du, self.date_from, lbl_exp_au, self.date_to):
        w.setVisible(False)
    exp_layout.addWidget(self.chk_date_filter)
    exp_layout.addStretch()
    exp_layout.addWidget(lbl_exp_du)
    exp_layout.addWidget(self.date_from)
    exp_layout.addWidget(lbl_exp_au)
    exp_layout.addWidget(self.date_to)

    # فلتر تاريخ الدخول
    ent_layout = QHBoxLayout()
    self.chk_entry_filter = QCheckBox("Date Entrée:")
    self.chk_entry_filter.setStyleSheet("font-weight: bold; color: #2980b9;")
    self.chk_entry_filter.setChecked(False)
    self.chk_entry_filter.stateChanged.connect(self.toggle_entry_filter)

    self.date_in_from = QDateEdit(QDate.currentDate().addMonths(-1))
    self.date_in_from.setCalendarPopup(True)
    self.date_in_from.setEnabled(False)
    self.date_in_from.setFixedWidth(135)
    self.date_in_from.dateChanged.connect(self.apply_filters_local)

    self.date_in_to = QDateEdit(QDate.currentDate())
    self.date_in_to.setCalendarPopup(True)
    self.date_in_to.setEnabled(False)
    self.date_in_to.setFixedWidth(135)
    self.date_in_to.dateChanged.connect(self.apply_filters_local)

    ent_layout.addWidget(self.chk_entry_filter)
    ent_layout.addStretch()
    ent_layout.addWidget(QLabel("Du:"))
    ent_layout.addWidget(self.date_in_from)
    ent_layout.addWidget(QLabel("Au:"))
    ent_layout.addWidget(self.date_in_to)

    right_layout.addLayout(exp_layout)
    right_layout.addLayout(ent_layout)

    # أزرار الإجراءات
    reset_layout = QHBoxLayout()

    self.chk_reclamation = QCheckBox("Réclamations Uniquement")
    self.chk_reclamation.setStyleSheet("font-weight: bold; color: #d35400;")
    self.chk_reclamation.setChecked(False)
    self.chk_reclamation.stateChanged.connect(self.apply_filters_local)
    reset_layout.addWidget(self.chk_reclamation)

    reset_layout.addStretch()

    btn_refresh = QPushButton("Actualiser")
    btn_refresh.setFixedWidth(100)
    btn_refresh.setCursor(Qt.PointingHandCursor)
    btn_refresh.setStyleSheet(
        "background-color: #007572; color: white; font-weight: bold; border-radius: 4px; padding: 4px 10px; border: none; min-height: 28px;"
    )
    btn_refresh.clicked.connect(self.load_data)

    btn_reset = QPushButton("Réinitialiser")
    btn_reset.setFixedWidth(100)
    btn_reset.setCursor(Qt.PointingHandCursor)
    btn_reset.setStyleSheet(
        "background-color: #ffffff; color: #495057; border: 1px solid #ced4da; border-radius: 4px; padding: 4px 10px; min-height: 28px;"
    )
    btn_reset.clicked.connect(self.reset_filters)

    reset_layout.addWidget(btn_refresh)
    reset_layout.addWidget(btn_reset)
    right_layout.addLayout(reset_layout)

    return right_layout


# ---------------------------------------------------------------------------
# الجدول
# ---------------------------------------------------------------------------

def _build_table(self):
    self.table = QTableWidget()
    self.table.setVerticalHeader(BatchesVerticalHeader(self.table))

    # ترتيب الأعمدة: الأولوية الأولى للمنتج والمخزون والوحدة والأسعار الأساسية (HT, TTC, Valeur, Vente 1)، تليها بيانات اللوط والتصنيفات، ثم أسعار البيع 2 و 3 و 4 قبل الشكاوى
    cols = [
        "Désignation Produit", "Stock (Actuel)", "Unité", "Prix U. HT", "Prix d'Achat",
        "Valeur (DA)", "Prix Vente 1", "N° Lot", "Date Exp.", "Qté Init.",
        "Code-Barres", "Code Ext", "Emplacement", "Famille", "Marque",
        "Automate", "Fournisseur", "Ref PO", "Date Entrée",
        "Prix Vente 2", "Prix Vente 3", "Prix Vente 4", "Réclamation",
        "Groupe Vente", "Réf"
    ]
    self.table.setColumnCount(len(cols))
    self.table.setHorizontalHeaderLabels(cols)
    self.table.setColumnHidden(3, True)   # Prix U. HT non requis
    self.table.setColumnHidden(8, True)   # Date Exp. non requise
    self.table.setColumnHidden(15, True)  # Automate non requis

    header = self.table.horizontalHeader()
    for c in range(len(cols)):
        header.setSectionResizeMode(c, QHeaderView.ResizeToContents)

    self.table.setWordWrap(True)
    self.table.setSortingEnabled(False)
    self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
    self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
    self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    self.table.setAlternatingRowColors(True)
    self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
    self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
    self.table.setStyleSheet("""
        QTableWidget {
            background-color: #ffffff;
            border: 1px solid #dcdfe6;
            gridline-color: #f1f5f9;
            font-size: 12px;
            color: #2c3e50;
            selection-background-color: #e6f4f1;
            selection-color: #007572;
        }
        QHeaderView::section {
            background-color: #f8fafc;
            color: #2c3e50;
            font-weight: bold;
            font-size: 12px;
            border: none;
            border-bottom: 2px solid #007572;
            border-right: 1px solid #e2e8f0;
            padding: 5px 8px;
        }
        QScrollBar:horizontal {
            border: 1px solid #cbd5e1;
            background: #f1f5f9;
            height: 18px;
            margin: 0px 22px 0px 22px;
        }
        QScrollBar::handle:horizontal {
            background: #007572;
            min-width: 40px;
            border-radius: 0px;
        }
        QScrollBar::handle:horizontal:hover {
            background: #005a57;
        }
        QScrollBar::handle:horizontal:pressed {
            background: #003d3a;
        }
        QScrollBar::add-line:horizontal {
            border: 1px solid #cbd5e1;
            background: #e2e8f0;
            width: 22px;
            subcontrol-position: right;
            subcontrol-origin: margin;
        }
        QScrollBar::sub-line:horizontal {
            border: 1px solid #cbd5e1;
            background: #e2e8f0;
            width: 22px;
            subcontrol-position: left;
            subcontrol-origin: margin;
        }
        QScrollBar::add-line:horizontal:hover, QScrollBar::sub-line:horizontal:hover {
            background: #cbd5e1;
        }
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
            background: #f8fafc;
        }
        QScrollBar:vertical {
            border: 1px solid #cbd5e1;
            background: #f1f5f9;
            width: 16px;
            margin: 20px 0px 20px 0px;
        }
        QScrollBar::handle:vertical {
            background: #007572;
            min-height: 35px;
            border-radius: 0px;
        }
        QScrollBar::handle:vertical:hover {
            background: #005a57;
        }
        QScrollBar::handle:vertical:pressed {
            background: #003d3a;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            border: 1px solid #cbd5e1;
            background: #e2e8f0;
            height: 20px;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: #f8fafc;
        }
    """)
    self.table.setContextMenuPolicy(Qt.CustomContextMenu)
    self.table.customContextMenuRequested.connect(self.show_context_menu)

    header.setSectionsClickable(True)
    header.setSortIndicatorShown(False)
    header.sectionClicked.connect(self.on_header_clicked)

    self.table.verticalScrollBar().valueChanged.connect(self.on_scroll_value_changed)
    self.table.verticalHeader().sectionClicked.connect(self.on_vertical_header_clicked)
    self.table.cellClicked.connect(self.on_cell_clicked)

    return self.table


# ---------------------------------------------------------------------------
# الشريط السفلي
# ---------------------------------------------------------------------------

def _build_bottom_bar(self):
    bottom_frame = QFrame()
    self.bottom_frame = bottom_frame
    bottom_frame.setStyleSheet("""
        QFrame {
            background-color: #f8fafc;
            border-top: 2px solid #cbd5e1;
            border-radius: 0px;
        }
    """)
    bottom_bar = QHBoxLayout(bottom_frame)
    bottom_bar.setContentsMargins(6, 6, 6, 6)
    bottom_bar.setSpacing(8)

    self.lbl_total_value = QLabel("Valeur Totale : 0,00 DA")
    self.lbl_total_value.setFont(QFont("Arial", 11, QFont.Bold))
    self.lbl_total_value.setStyleSheet("""
        QLabel {
            color: #007572; border: 1px solid #a3e4d7; border-radius: 4px;
            padding: 6px 12px; background-color: #e8f8f5;
        }
    """)
    bottom_bar.addWidget(self.lbl_total_value)

    self.lbl_total_quantity = QLabel("Stock disponible affiché : 0")
    self.lbl_total_quantity.setFont(QFont("Arial", 11, QFont.Bold))
    self.lbl_total_quantity.setStyleSheet("""
        QLabel {
            color: #1e8449; border: 1px solid #82e0aa; border-radius: 4px;
            padding: 6px 12px; background-color: #eafaf1;
        }
    """)
    bottom_bar.addWidget(self.lbl_total_quantity)

    self.lbl_count_info = QLabel("0 éléments")
    self.lbl_count_info.setStyleSheet(
        "color: #7f8c8d; font-weight: bold; margin-left: 10px;"
    )
    bottom_bar.addWidget(self.lbl_count_info)
    bottom_bar.addStretch()

    btn_style = (
        "QPushButton { font-weight: bold; border-radius: 4px; "
        "padding: 6px 14px; font-size: 12px; min-height: 28px; }"
    )

    def _btn(label, color, slot):
        b = QPushButton(label)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet(btn_style + f"background-color: {color}; color: white; border: none;")
        b.clicked.connect(slot)
        return b

    bottom_bar.addWidget(_btn("➕ Ajout Rapide", "#8e44ad", self.open_quick_add))
    bottom_bar.addWidget(_btn("📝 Éditer",       "#2980b9", self.open_quick_edit))
    self.btn_sales_price = _btn("💲 Prix de Vente", "#16a085", self.open_modify_sales_prices)
    bottom_bar.addWidget(self.btn_sales_price)
    bottom_bar.addWidget(_btn("⚡ Sortie",      "#27ae60", self.direct_use_process))
    bottom_bar.addWidget(_btn("✏️ Ajustement",  "#f39c12", self.adjust_stock))
    bottom_bar.addWidget(_btn("🗑️ Rebut",       "#c0392b", self.waste_batch))
    bottom_bar.addWidget(_btn("🖨️ Étiquette",   "#34495e", self.print_batch_label))

    line_sep = QFrame()
    line_sep.setFrameShape(QFrame.VLine)
    line_sep.setFrameShadow(QFrame.Sunken)
    line_sep.setStyleSheet("color: #e2e8f0;")
    bottom_bar.addWidget(line_sep)

    bottom_bar.addWidget(_btn("📗 Excel", "#217346", self.export_to_excel))
    bottom_bar.addWidget(_btn("📕 PDF",   "#e74c3c", self.export_to_pdf))

    return bottom_frame
