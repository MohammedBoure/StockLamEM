# ui/widgets/inventory/tabs_batches/_ui.py
"""
بناء واجهة المستخدم: فلاتر، الجدول، شريط الأدوات السفلي
"""

from PySide6.QtWidgets import (
    QVBoxLayout, QTableWidget, QHeaderView,
    QFrame, QLabel, QLineEdit, QPushButton, QHBoxLayout,
    QGroupBox, QComboBox, QDateEdit, QCheckBox, QAbstractItemView
)
from PySide6.QtCore import Qt, QDate, QSize
from PySide6.QtGui import QFont, QKeySequence, QShortcut

from ui.icons import get_duotone_icon
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
    layout.addWidget(_build_table(self), 1)
    layout.addWidget(_build_empty_state(self), 1)
    layout.addWidget(_build_bottom_bar(self))

    self._shortcut_f5 = QShortcut(QKeySequence(Qt.Key_F5), self)
    self._shortcut_f5.setContext(Qt.WidgetWithChildrenShortcut)
    self._shortcut_f5.activated.connect(self.load_data)

    self._shortcut_ctrl_r = QShortcut(QKeySequence("Ctrl+R"), self)
    self._shortcut_ctrl_r.setContext(Qt.WidgetWithChildrenShortcut)
    self._shortcut_ctrl_r.activated.connect(self.load_data)

    self._shortcut_esc = QShortcut(QKeySequence(Qt.Key_Escape), self)
    self._shortcut_esc.setContext(Qt.WidgetWithChildrenShortcut)
    self._shortcut_esc.activated.connect(self.reset_filters)

    self.table.doubleClicked.connect(self.show_batch_details)


# ---------------------------------------------------------------------------
# منطقة الفلاتر
# ---------------------------------------------------------------------------

def _build_filter_group(self):
    filter_group = QGroupBox("Recherche & Filtres")

    main_filter_layout = QHBoxLayout(filter_group)
    main_filter_layout.setContentsMargins(10, 14, 10, 10)

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
    self.search_input.setPlaceholderText("Rechercher produit, référence, code-barres, n° lot...")
    self.search_input.setClearButtonEnabled(True)
    self.search_input.returnPressed.connect(self.load_data)
    self.search_input.textChanged.connect(self.apply_filters_local)

    self.loc_filter = LocationTreeComboBox(self.manager.locations)
    self.loc_filter.setPlaceholderText("Emplacement")
    self.loc_filter.setMinimumWidth(180)
    self.loc_filter.currentIndexChanged.connect(self.apply_filters_local)

    row1.addWidget(self.search_input)
    row1.addWidget(self.loc_filter)
    left_layout.addLayout(row1)

    # الصف 2: القوائم المنسدلة
    row2 = QHBoxLayout()

    self.combo_family = QComboBox()
    self.combo_family.addItem("Familles", None)
    self.combo_family.setMinimumWidth(125)
    self.populate_families()
    self.combo_family.currentIndexChanged.connect(self.apply_filters_local)

    self.combo_manuf = QComboBox()
    self.combo_manuf.addItem("Marques", None)
    self.combo_manuf.setMinimumWidth(125)
    self.populate_manufacturers()
    self.combo_manuf.currentIndexChanged.connect(self.apply_filters_local)

    self.combo_automate = QComboBox()
    self.combo_automate.addItem("Automates", None)
    self.combo_automate.setMinimumWidth(125)
    self.populate_automates()
    self.combo_automate.currentIndexChanged.connect(self.apply_filters_local)
    self.combo_automate.setVisible(False)

    self.combo_supplier = QComboBox()
    self.combo_supplier.addItem("Fournisseurs", None)
    self.combo_supplier.setMinimumWidth(130)
    self.populate_suppliers()
    self.combo_supplier.currentIndexChanged.connect(self.apply_filters_local)

    self.combo_status = QComboBox()
    from ui.icons import get_duotone_icon
    status_items = [
        ("Tous (>0)", "inventory"),
        ("En Stock", "kpi_recovered"),
        ("Faible (Seuil)", "alert_warning"),
        ("Épuisé (Qté=0)", "kpi_overdue"),
        ("Rebuts / Pertes", "waste_bin"),
    ]
    for st_label, st_icon in status_items:
        self.combo_status.addItem(get_duotone_icon(st_icon, 15), st_label)
    self.combo_status.setMinimumWidth(145)
    self.combo_status.setCurrentIndex(1)
    self.combo_status.currentIndexChanged.connect(self.load_data)

    self.combo_priority_group = QComboBox()
    self.combo_priority_group.addItem(get_duotone_icon("tag_family", 15), "Groupes Vente", None)
    self.combo_priority_group.setMinimumWidth(135)
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
    btn_refresh.setFixedWidth(104)
    btn_refresh.setCursor(Qt.PointingHandCursor)
    btn_refresh.setIcon(get_duotone_icon("refresh", 14))
    btn_refresh.setIconSize(QSize(14, 14))
    btn_refresh.setToolTip("Actualiser le stock (F5 / Ctrl+R)")
    btn_refresh.setStyleSheet(
        "QPushButton { background-color: #ffffff; color: #334155; font-weight: 600; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 10px; min-height: 28px; }"
        "QPushButton:hover { background-color: #f8fafc; border-color: #94a3b8; color: #0f172a; }"
    )
    btn_refresh.clicked.connect(self.load_data)

    btn_reset = QPushButton("Réinitialiser")
    btn_reset.setFixedWidth(104)
    btn_reset.setCursor(Qt.PointingHandCursor)
    btn_reset.setToolTip("Réinitialiser les filtres (Échap)")
    btn_reset.setStyleSheet(
        "QPushButton { background-color: #ffffff; color: #475569; font-weight: 600; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 10px; min-height: 28px; }"
        "QPushButton:hover { background-color: #f8fafc; border-color: #94a3b8; color: #0f172a; }"
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
        "Groupe Vente", "Réf", "Qté Dispo"
    ]
    self.table.setColumnCount(len(cols))
    self.table.setHorizontalHeaderLabels(cols)
    for m_col in (3, 4, 5, 6, 19, 20, 21):
        hdr_it = self.table.horizontalHeaderItem(m_col)
        if hdr_it is not None:
            hdr_it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    for qty_col in (1, 9, 25):
        hdr_it = self.table.horizontalHeaderItem(qty_col)
        if hdr_it is not None:
            hdr_it.setTextAlignment(Qt.AlignCenter)
    self.table.setColumnHidden(3, True)   # Prix U. HT non requis
    self.table.setColumnHidden(8, True)   # Date Exp. non requise
    self.table.setColumnHidden(15, True)  # Automate non requis

    header = self.table.horizontalHeader()
    for c in range(len(cols)):
        header.setSectionResizeMode(c, QHeaderView.ResizeToContents)
    # Place Qté Dispo visually right beside Stock (Actuel) while keeping logical indices 0..24 intact
    header.moveSection(25, 2)

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


def _build_empty_state(self):
    empty_frame = QFrame()
    empty_frame.setObjectName("BatchesEmptyState")
    empty_frame.setStyleSheet(
        """
        QFrame#BatchesEmptyState {
            background-color: #FFFFFF;
            border: 1px solid #DCDFE6;
            border-radius: 6px;
        }
        QFrame#BatchesEmptyState QLabel {
            border: none;
            background: transparent;
        }
        """
    )
    lay = QVBoxLayout(empty_frame)
    lay.setAlignment(Qt.AlignCenter)
    lay.setSpacing(10)

    icon_lbl = QLabel()
    icon_lbl.setAlignment(Qt.AlignCenter)
    icon_lbl.setPixmap(get_duotone_icon("inventory", 40).pixmap(40, 40))
    lay.addWidget(icon_lbl)

    title = QLabel("Aucun lot trouvé")
    title.setAlignment(Qt.AlignCenter)
    title.setStyleSheet("font-size: 14px; font-weight: 800; color: #1E293B;")
    lay.addWidget(title)

    desc = QLabel("Aucun lot en stock ne correspond aux filtres ou à la recherche en cours.")
    desc.setAlignment(Qt.AlignCenter)
    desc.setStyleSheet("font-size: 12px; color: #64748B;")
    lay.addWidget(desc)

    self.btn_empty_reset = QPushButton("Réinitialiser les filtres")
    self.btn_empty_reset.setObjectName("BtnBatchesEmptyReset")
    self.btn_empty_reset.setIcon(get_duotone_icon("refresh", 16))
    self.btn_empty_reset.setIconSize(QSize(16, 16))
    self.btn_empty_reset.setFixedHeight(32)
    self.btn_empty_reset.setCursor(Qt.PointingHandCursor)
    self.btn_empty_reset.setStyleSheet(
        """
        QPushButton#BtnBatchesEmptyReset {
            background-color: #FFFFFF;
            color: #334155;
            border: 1px solid #CBD5E1;
            border-radius: 6px;
            padding: 0 14px;
            font-size: 12px;
            font-weight: 700;
        }
        QPushButton#BtnBatchesEmptyReset:hover { background-color: #F8FAFC; border-color: #94A3B8; }
        """
    )
    self.btn_empty_reset.clicked.connect(self.reset_filters)
    lay.addWidget(self.btn_empty_reset, alignment=Qt.AlignCenter)

    empty_frame.setVisible(False)
    self.batches_empty_state = empty_frame
    return empty_frame


# ---------------------------------------------------------------------------
# الشريط السفلي
# ---------------------------------------------------------------------------

def _build_bottom_bar(self):
    bottom_frame = QFrame()
    bottom_frame.setObjectName("BatchesBottomBar")
    self.bottom_frame = bottom_frame
    bottom_frame.setStyleSheet("""
        QFrame#BatchesBottomBar {
            background-color: #f8fafc;
            border-top: 1px solid #cbd5e1;
            border-radius: 0px;
        }
    """)
    bottom_bar = QHBoxLayout(bottom_frame)
    bottom_bar.setContentsMargins(10, 8, 10, 8)
    bottom_bar.setSpacing(8)

    self.lbl_total_value = QLabel("Total Filtré : 0,00 DA")
    self.lbl_total_value.setFont(QFont("Segoe UI", 11, QFont.Bold))
    self.lbl_total_value.setStyleSheet(
        "color: #0E7471; font-weight: 800; padding: 4px 8px; background: transparent; border: none;"
    )
    bottom_bar.addWidget(self.lbl_total_value)

    self.lbl_total_quantity = QLabel("Stock disponible affiché : 0")
    self.lbl_total_quantity.setFont(QFont("Segoe UI", 11, QFont.Bold))
    self.lbl_total_quantity.setStyleSheet(
        "color: #0F172A; font-weight: 700; padding: 4px 8px; background: transparent; border: none;"
    )
    bottom_bar.addWidget(self.lbl_total_quantity)

    self.lbl_count_info = QLabel("0 éléments")
    self.lbl_count_info.setStyleSheet(
        "color: #64748B; font-weight: 600; font-size: 11.5px; margin-left: 4px;"
    )
    bottom_bar.addWidget(self.lbl_count_info)
    bottom_bar.addStretch()

    def _primary_btn(label, slot):
        b = QPushButton(label)
        b.setCursor(Qt.PointingHandCursor)
        b.setFixedHeight(32)
        b.setStyleSheet(
            "QPushButton { background-color: #0E7471; color: #FFFFFF; font-weight: 700; border: none; border-radius: 5px; padding: 0 14px; font-size: 12px; }"
            "QPushButton:hover { background-color: #0A5C59; }"
        )
        b.clicked.connect(slot)
        return b

    def _outline_btn(label, slot, icon_name=None, danger=False):
        b = QPushButton(label)
        b.setCursor(Qt.PointingHandCursor)
        b.setFixedHeight(32)
        if icon_name:
            b.setIcon(get_duotone_icon(icon_name, 14))
            b.setIconSize(QSize(14, 14))
        if danger:
            b.setStyleSheet(
                "QPushButton { background-color: #FFFFFF; color: #DC2626; font-weight: 600; border: 1px solid #FCA5A5; border-radius: 5px; padding: 0 11px; font-size: 12px; }"
                "QPushButton:hover { background-color: #FEF2F2; border-color: #DC2626; }"
            )
        else:
            b.setStyleSheet(
                "QPushButton { background-color: #FFFFFF; color: #334155; font-weight: 600; border: 1px solid #CBD5E1; border-radius: 5px; padding: 0 11px; font-size: 12px; }"
                "QPushButton:hover { background-color: #F1F5F9; border-color: #94A3B8; color: #0F172A; }"
            )
        b.clicked.connect(slot)
        return b

    bottom_bar.addWidget(_primary_btn("+ Ajout Rapide", self.open_quick_add))
    bottom_bar.addWidget(_outline_btn("Éditer", self.open_quick_edit, icon_name="edit"))
    self.btn_sales_price = _outline_btn("Prix de Vente", self.open_modify_sales_prices, icon_name="payment")
    bottom_bar.addWidget(self.btn_sales_price)
    bottom_bar.addWidget(_outline_btn("Sortie", self.direct_use_process))
    bottom_bar.addWidget(_outline_btn("Ajustement", self.adjust_stock))
    bottom_bar.addWidget(_outline_btn("Rebut", self.waste_batch, icon_name="trash", danger=True))
    bottom_bar.addWidget(_outline_btn("Étiquette", self.print_batch_label, icon_name="print"))

    line_sep = QFrame()
    line_sep.setFrameShape(QFrame.VLine)
    line_sep.setFrameShadow(QFrame.Sunken)
    line_sep.setStyleSheet("color: #cbd5e1;")
    bottom_bar.addWidget(line_sep)

    bottom_bar.addWidget(_outline_btn("Excel", self.export_to_excel, icon_name="export"))
    bottom_bar.addWidget(_outline_btn("PDF", self.export_to_pdf, icon_name="export"))

    return bottom_frame
