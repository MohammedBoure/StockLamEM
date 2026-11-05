# -*- coding: utf-8 -*-
"""
ui/widgets/appliance_desks/serial_batch_view.py
===============================================
Product & Batch Serial Registry Desk (إدارة المنتجات والدفعات والأرقام التسلسلية).
Implements Section 1 of the Electrical Appliance Store specification:
- Product attributes: Mark (العلامة التجارية), Name (الاسم), Categorie (الفئة),
  Coloure (اللون), Warranty Months, and Extensible JSON Attributes.
- Batch Entry (إدارة الدفعات): Enter goods in batches with distinct arrival dates,
  purchase costs, selling prices, and individual unique Serial Numbers (N° de Série).
"""

import json
import logging
from decimal import Decimal
from typing import Optional

from PySide6.QtCore import QDate, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from ui.icons import get_duotone_icon

logger = logging.getLogger(__name__)

TABLE_STYLE = """
    QTableWidget {
        background-color: #FFFFFF;
        alternate-background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 6px;
        gridline-color: #F1F5F9;
        color: #1E293B;
        font-size: 9.5pt;
        selection-background-color: #CCFBF1;
        selection-color: #0F172A;
    }
    QTableWidget::item {
        padding: 4px 8px;
        border: none;
    }
    QHeaderView::section {
        background-color: #F8FAFC;
        color: #0F172A;
        font-weight: bold;
        font-size: 9pt;
        padding: 6px 8px;
        border: none;
        border-bottom: 2px solid #0E7471;
        border-right: 1px solid #E2E8F0;
    }
"""

INPUT_STYLE = """
    QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QDateEdit, QPlainTextEdit {
        background-color: #FFFFFF;
        border: 1px solid #CBD5E1;
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 9.5pt;
        color: #0F172A;
    }
    QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus, QDateEdit:focus, QPlainTextEdit:focus {
        border: 1.5px solid #0E7471;
    }
"""


class SerialBatchRegistryWidget(QWidget):
    """
    UI Widget for registering Appliance Products (Mark, Name, Categorie, Coloure)
    and receiving Inventory Batches with unique Serial Numbers (N° de Série).
    """

    catalog_updated = Signal()

    def __init__(
        self,
        data_manager=None,
        db_manager=None,
        current_user_id: int = 1,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.data_manager = data_manager or db_manager
        self.db_manager = self.data_manager
        self.current_user_id = current_user_id
        self.setStyleSheet(
            """
            QFrame#ProductCard, QFrame#BatchCard, QFrame#CatalogCard {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
                color: #334155;
                font-size: 12px;
                font-weight: 600;
            }
            QCheckBox {
                color: #334155;
                font-weight: 600;
                font-size: 12px;
                spacing: 6px;
            }
            """
            + INPUT_STYLE
        )
        self._trace_cache = []
        self._build_ui()
        self.refresh_products()
        self.refresh_traceability()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        self.inner_tabs = QTabWidget()
        self.inner_tabs.setIconSize(QSize(16, 16))
        self.inner_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #DDE3EA;
                background: #F8FAFC;
                border-radius: 6px;
                top: -1px;
            }
            QTabBar::tab {
                background: #ECEFF1;
                color: #475569;
                border: 1px solid #DDE3EA;
                border-bottom: none;
                padding: 7px 14px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-size: 11.5px;
                font-weight: 700;
            }
            QTabBar::tab:selected {
                background: #FFFFFF;
                color: #007572;
                border-top: 3px solid #007572;
            }
            QTabBar::tab:hover:!selected {
                background: #E2E8F0;
                color: #1E293B;
            }
        """)

        # Tab 1: Lots & Products
        tab_lots = QWidget()
        tab_lots_layout = QVBoxLayout(tab_lots)
        tab_lots_layout.setContentsMargins(8, 8, 8, 8)
        tab_lots_layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        # Left Panel: Create / Update Appliance Product (Compact 2-Column Grid)
        product_group = QFrame()
        product_group.setObjectName("ProductCard")
        pg_layout = QVBoxLayout(product_group)
        pg_layout.setContentsMargins(14, 12, 14, 12)
        pg_layout.setSpacing(8)

        pg_title = QLabel("1. Référentiel Produit Électroménager (Mark, Name, Categorie, Coloure)")
        pg_title.setStyleSheet(
            "font-size: 12.5px; font-weight: 800; color: #0F172A; "
            "padding-bottom: 6px; border-bottom: 2px solid #0E7471;"
        )
        pg_layout.addWidget(pg_title)

        p_grid = QGridLayout()
        p_grid.setVerticalSpacing(8)
        p_grid.setHorizontalSpacing(10)

        p_grid.addWidget(QLabel("Marque (Mark) :"), 0, 0)
        self.mark_input = QLineEdit()
        self.mark_input.setFixedHeight(32)
        self.mark_input.setPlaceholderText("Ex: Samsung, LG, Bosch, Brandt...")
        p_grid.addWidget(self.mark_input, 0, 1)

        p_grid.addWidget(QLabel("Désignation (Name) :"), 0, 2)
        self.name_input = QLineEdit()
        self.name_input.setFixedHeight(32)
        self.name_input.setPlaceholderText("Ex: Lave-linge 9kg EcoBubble")
        p_grid.addWidget(self.name_input, 0, 3)

        p_grid.addWidget(QLabel("Catégorie (Categorie) :"), 1, 0)
        self.category_input = QLineEdit()
        self.category_input.setFixedHeight(32)
        self.category_input.setPlaceholderText("Ex: Lave-linge, Réfrigérateurs...")
        p_grid.addWidget(self.category_input, 1, 1)

        p_grid.addWidget(QLabel("Couleur (Coloure) :"), 1, 2)
        self.color_input = QLineEdit()
        self.color_input.setFixedHeight(32)
        self.color_input.setPlaceholderText("Ex: Inox, Blanc, Noir, Silver...")
        p_grid.addWidget(self.color_input, 1, 3)

        p_grid.addWidget(QLabel("Code-barres Modèle :"), 2, 0)
        self.barcode_input = QLineEdit()
        self.barcode_input.setFixedHeight(32)
        self.barcode_input.setPlaceholderText("EAN / UPC Modèle")
        p_grid.addWidget(self.barcode_input, 2, 1)

        p_grid.addWidget(QLabel("Garantie (Mois) :"), 2, 2)
        self.warranty_spin = QSpinBox()
        self.warranty_spin.setFixedHeight(32)
        self.warranty_spin.setRange(0, 120)
        self.warranty_spin.setValue(24)
        self.warranty_spin.setSuffix(" mois")
        p_grid.addWidget(self.warranty_spin, 2, 3)

        p_grid.addWidget(QLabel("Prix Achat Réf. :"), 3, 0)
        self.buy_price_spin = QDoubleSpinBox()
        self.buy_price_spin.setFixedHeight(32)
        self.buy_price_spin.setRange(0.0, 100_000_000.0)
        self.buy_price_spin.setDecimals(2)
        self.buy_price_spin.setSuffix(" DA")
        p_grid.addWidget(self.buy_price_spin, 3, 1)

        p_grid.addWidget(QLabel("Prix Vente TTC :"), 3, 2)
        self.sell_price_spin = QDoubleSpinBox()
        self.sell_price_spin.setFixedHeight(32)
        self.sell_price_spin.setRange(0.0, 100_000_000.0)
        self.sell_price_spin.setDecimals(2)
        self.sell_price_spin.setSuffix(" DA")
        p_grid.addWidget(self.sell_price_spin, 3, 3)

        p_grid.addWidget(QLabel("Attributs JSON :"), 4, 0)
        self.ext_attrs_input = QLineEdit()
        self.ext_attrs_input.setFixedHeight(32)
        self.ext_attrs_input.setPlaceholderText('{"energy": "A+++", "power_w": 2000}')
        p_grid.addWidget(self.ext_attrs_input, 4, 1, 1, 3)

        pg_layout.addLayout(p_grid)

        chk_row = QHBoxLayout()
        self.requires_serial_chk = QCheckBox("Exiger un N° de Série unique au Bureau de Sortie")
        self.requires_serial_chk.setChecked(True)
        chk_row.addWidget(self.requires_serial_chk)
        chk_row.addStretch()

        self.save_product_btn = QPushButton("+ Enregistrer le Produit")
        self.save_product_btn.setCursor(Qt.PointingHandCursor)
        self.save_product_btn.setFixedHeight(34)
        self.save_product_btn.setStyleSheet(
            "QPushButton { background-color: #0E7471; color: white; font-weight: 700; font-size: 12px; min-height: 0px; padding: 4px 16px; border: none; border-radius: 6px; }"
            "QPushButton:hover { background-color: #0A5E5C; }"
        )
        self.save_product_btn.clicked.connect(self._on_create_product)
        chk_row.addWidget(self.save_product_btn)
        pg_layout.addLayout(chk_row)

        top_row.addWidget(product_group, stretch=1)

        # Right Panel: Receive Batch with Serials
        batch_group = QFrame()
        batch_group.setObjectName("BatchCard")
        batch_layout = QVBoxLayout(batch_group)
        batch_layout.setContentsMargins(14, 12, 14, 12)
        batch_layout.setSpacing(8)

        bg_title = QLabel("2. Réception de Lot (Batch) & Numéros de Série (N° de Série)")
        bg_title.setStyleSheet(
            "font-size: 12.5px; font-weight: 800; color: #0F172A; "
            "padding-bottom: 6px; border-bottom: 2px solid #0E7471;"
        )
        batch_layout.addWidget(bg_title)

        b_grid = QGridLayout()
        b_grid.setVerticalSpacing(8)
        b_grid.setHorizontalSpacing(10)

        b_grid.addWidget(QLabel("Produit :"), 0, 0)
        self.product_combo = QComboBox()
        self.product_combo.setFixedHeight(32)
        b_grid.addWidget(self.product_combo, 0, 1, 1, 3)

        b_grid.addWidget(QLabel("N° Lot (Batch) :"), 1, 0)
        self.batch_number_input = QLineEdit()
        self.batch_number_input.setFixedHeight(32)
        self.batch_number_input.setPlaceholderText("Ex: BATCH-2026-11-A")
        b_grid.addWidget(self.batch_number_input, 1, 1)

        b_grid.addWidget(QLabel("Date Réception :"), 1, 2)
        self.received_date_edit = QDateEdit(QDate.currentDate())
        self.received_date_edit.setFixedHeight(32)
        self.received_date_edit.setCalendarPopup(True)
        self.received_date_edit.setDisplayFormat("yyyy-MM-dd")
        b_grid.addWidget(self.received_date_edit, 1, 3)

        b_grid.addWidget(QLabel("Coût Unitaire HT :"), 2, 0)
        self.batch_cost_spin = QDoubleSpinBox()
        self.batch_cost_spin.setFixedHeight(32)
        self.batch_cost_spin.setRange(0.0, 100_000_000.0)
        self.batch_cost_spin.setDecimals(2)
        self.batch_cost_spin.setSuffix(" DA")
        b_grid.addWidget(self.batch_cost_spin, 2, 1)

        b_grid.addWidget(QLabel("Prix Vente Lot :"), 2, 2)
        self.batch_sell_spin = QDoubleSpinBox()
        self.batch_sell_spin.setFixedHeight(32)
        self.batch_sell_spin.setRange(0.0, 100_000_000.0)
        self.batch_sell_spin.setDecimals(2)
        self.batch_sell_spin.setSuffix(" DA")
        b_grid.addWidget(self.batch_sell_spin, 2, 3)

        b_grid.addWidget(QLabel("N° de Série (1/ligne) :"), 3, 0, Qt.AlignTop)
        self.serials_text = QPlainTextEdit()
        self.serials_text.setFixedHeight(50)
        self.serials_text.setPlaceholderText(
            "Scanner ou saisir les N° de Série ici (un par ligne)... Ex: SN-BOSCH-9001, SN-BOSCH-9002"
        )
        b_grid.addWidget(self.serials_text, 3, 1, 1, 3)

        batch_layout.addLayout(b_grid)

        btn_batch_row = QHBoxLayout()
        btn_batch_row.addStretch()
        self.receive_batch_btn = QPushButton("Réceptionner le Lot && Enregistrer les N° de Série")
        self.receive_batch_btn.setIcon(get_duotone_icon("barcode_scan", 16))
        self.receive_batch_btn.setIconSize(QSize(16, 16))
        self.receive_batch_btn.setCursor(Qt.PointingHandCursor)
        self.receive_batch_btn.setFixedHeight(34)
        self.receive_batch_btn.setStyleSheet(
            "QPushButton { background-color: #0E7471; color: white; font-weight: 700; font-size: 12px; min-height: 0px; padding: 4px 16px; border: none; border-radius: 6px; }"
            "QPushButton:hover { background-color: #0A5E5C; }"
        )
        self.receive_batch_btn.clicked.connect(self._on_receive_batch)
        btn_batch_row.addWidget(self.receive_batch_btn)
        batch_layout.addLayout(btn_batch_row)

        top_row.addWidget(batch_group, stretch=1)
        root_layout.addLayout(top_row, stretch=2)

        # Bottom Table: Overview of Catalog & Theoretical vs Physical Stock
        cat_card = QFrame()
        cat_card.setObjectName("CatalogCard")
        cat_layout = QVBoxLayout(cat_card)
        cat_layout.setContentsMargins(14, 12, 14, 12)
        cat_layout.setSpacing(8)

        table_header_layout = QHBoxLayout()
        table_lbl = QLabel("Référentiel Produits : Stock Physique vs Réservé Théorique vs Disponible Vente")
        table_lbl.setStyleSheet("font-size: 12.5px; font-weight: 800; color: #0F172A;")
        table_header_layout.addWidget(table_lbl)
        table_header_layout.addStretch()

        self.refresh_btn = QPushButton("Actualiser")
        self.refresh_btn.setIcon(get_duotone_icon("refresh", 14))
        self.refresh_btn.setIconSize(QSize(14, 14))
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.setFixedHeight(32)
        self.refresh_btn.setStyleSheet(
            "QPushButton { background: #FFFFFF; color: #0E7471; font-weight: 700; font-size: 12px; min-height: 0px; padding: 4px 12px; border: 1.5px solid #0E7471; border-radius: 6px; }"
            "QPushButton:hover { background: #E6F4F1; }"
        )
        self.refresh_btn.clicked.connect(self.refresh_products)
        table_header_layout.addWidget(self.refresh_btn)
        cat_layout.addLayout(table_header_layout)

        self.catalog_table = QTableWidget(0, 8)
        self.catalog_table.setStyleSheet(TABLE_STYLE)
        self.catalog_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Marque (Mark)",
                "Désignation Produit (Name)",
                "Catégorie",
                "Couleur",
                "Stock Physique",
                "Réservé (Théorique)",
                "Disponible Vente",
            ]
        )
        self.catalog_table.verticalHeader().setVisible(False)
        self.catalog_table.verticalHeader().setDefaultSectionSize(36)
        self.catalog_table.setAlternatingRowColors(True)
        self.catalog_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.catalog_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        c_hdr = self.catalog_table.horizontalHeader()
        c_hdr.setFixedHeight(38)
        c_hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        c_hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        c_hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        c_hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        c_hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        c_hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        c_hdr.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        c_hdr.setSectionResizeMode(7, QHeaderView.ResizeToContents)

        cat_layout.addWidget(self.catalog_table)
        tab_lots_layout.addWidget(cat_card, stretch=3)
        self.inner_tabs.addTab(tab_lots, get_duotone_icon("edit_lots", 16), "1. Référentiel Lots & Produits (Stock Physique)")

        # Tab 2: Journal de Traçabilité & Audit des Sorties
        tab_trace = QWidget()
        tab_trace_layout = QVBoxLayout(tab_trace)
        tab_trace_layout.setContentsMargins(8, 8, 8, 8)
        tab_trace_layout.setSpacing(10)

        trace_header = QFrame()
        trace_header.setObjectName("TraceHeaderCard")
        trace_header.setFixedHeight(52)
        trace_header.setStyleSheet("""
            QFrame#TraceHeaderCard {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        th_layout = QHBoxLayout(trace_header)
        th_layout.setContentsMargins(14, 0, 14, 0)
        th_layout.setSpacing(10)

        th_ic = QLabel()
        th_ic.setPixmap(get_duotone_icon("history", 20).pixmap(20, 20))
        th_layout.addWidget(th_ic)

        th_title = QLabel("Journal de Traçabilité & Audit des Sorties Magasin :")
        th_title.setStyleSheet("font-size: 13px; font-weight: 800; color: #1E293B;")
        th_layout.addWidget(th_title)

        self.cbo_trace_type = QComboBox()
        self.cbo_trace_type.setFixedHeight(34)
        self.cbo_trace_type.addItems([
            "Tous les Mouvements",
            "Sorties Magasin (Bon de Sortie)",
            "Réceptions de Lots (Achats)",
            "Retours Marchandises",
        ])
        self.cbo_trace_type.currentIndexChanged.connect(self.refresh_traceability)
        th_layout.addWidget(self.cbo_trace_type)

        self.txt_trace_search = QLineEdit()
        self.txt_trace_search.setFixedHeight(34)
        self.txt_trace_search.setPlaceholderText("Filtrer par désignation, N° de Série, Lot ou N° de Bon...")
        self.txt_trace_search.textChanged.connect(self.refresh_traceability)
        th_layout.addWidget(self.txt_trace_search, stretch=1)

        btn_refresh_trace = QPushButton("Actualiser la Traçabilité")
        btn_refresh_trace.setIcon(get_duotone_icon("refresh", 14))
        btn_refresh_trace.setIconSize(QSize(14, 14))
        btn_refresh_trace.setCursor(Qt.PointingHandCursor)
        btn_refresh_trace.setFixedHeight(34)
        btn_refresh_trace.setStyleSheet(
            "QPushButton { background: #FFFFFF; color: #007572; font-weight: 700; font-size: 12px; min-height: 0px; padding: 4px 12px; border: 1.5px solid #007572; border-radius: 6px; }"
            "QPushButton:hover { background: #E6F4F1; }"
        )
        btn_refresh_trace.clicked.connect(self.refresh_traceability)
        th_layout.addWidget(btn_refresh_trace)

        tab_trace_layout.addWidget(trace_header)

        self.trace_table = QTableWidget(0, 8)
        self.trace_table.setStyleSheet(TABLE_STYLE)
        self.trace_table.setHorizontalHeaderLabels([
            "Horodatage",
            "Type Mouvement",
            "Produit",
            "Lot / N° de Série",
            "Variation",
            "Stock Après",
            "Opérateur",
            "Référence & Notes",
        ])
        self.trace_table.verticalHeader().setVisible(False)
        self.trace_table.verticalHeader().setDefaultSectionSize(36)
        self.trace_table.setAlternatingRowColors(True)
        self.trace_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.trace_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        t_hdr = self.trace_table.horizontalHeader()
        t_hdr.setFixedHeight(38)
        t_hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        t_hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        t_hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        t_hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        t_hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        t_hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        t_hdr.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        t_hdr.setSectionResizeMode(7, QHeaderView.Stretch)

        tab_trace_layout.addWidget(self.trace_table, 1)

        self.inner_tabs.addTab(tab_trace, get_duotone_icon("history", 16), "2. Journal de Traçabilité & Mouvements (Sorties/Entrées)")
        root_layout.addWidget(self.inner_tabs, 1)

    def refresh_products(self) -> None:
        catalog = []
        if self.data_manager and hasattr(self.data_manager, "serials"):
            try:
                catalog = self.data_manager.serials.get_catalog_with_theoretical_stock()
            except Exception as exc:
                logger.error("Failed to load appliance catalog: %s", exc)
                catalog = []

        if not catalog and not (self.data_manager and hasattr(self.data_manager, "serials")):
            catalog = [
                {
                    "Product_ID": 101,
                    "Brand_Mark": "Bosch",
                    "Product_Name": "KGN39VLEB Combi NoFrost 368L",
                    "Category_Name": "Réfrigérateurs",
                    "Color_Finish": "Inox",
                    "Physical_Qty": 8,
                    "Reserved_Qty": 1,
                    "Available_Theoretical_Qty": 7,
                },
                {
                    "Product_ID": 102,
                    "Brand_Mark": "LG",
                    "Product_Name": "F4J6TY0W DirectDrive 9kg",
                    "Category_Name": "Lave-linge",
                    "Color_Finish": "Blanc",
                    "Physical_Qty": 12,
                    "Reserved_Qty": 0,
                    "Available_Theoretical_Qty": 12,
                },
                {
                    "Product_ID": 103,
                    "Brand_Mark": "Midea",
                    "Product_Name": "Inverter 12000 BTU Split R32",
                    "Category_Name": "Climatisation",
                    "Color_Finish": "Blanc",
                    "Physical_Qty": 5,
                    "Reserved_Qty": 1,
                    "Available_Theoretical_Qty": 4,
                },
            ]

        self.product_combo.clear()
        self.catalog_table.setRowCount(0)

        for row_idx, item in enumerate(catalog):
            pid = item.get("Product_ID")
            mark = item.get("Brand_Mark") or "-"
            name = item.get("Product_Name") or ""
            cat = item.get("Category_Name") or "-"
            color = item.get("Color_Finish") or "-"
            phys = float(item.get("Physical_Qty") or item.get("Physical_Stock") or 0)
            res = float(item.get("Reserved_Qty") or item.get("Theoretical_Reserved_Qty") or 0)
            avail = float(item.get("Available_Theoretical_Qty") or max(0.0, phys - res))

            self.product_combo.addItem(f"[{pid}] {mark} — {name} ({color})", pid)

            self.catalog_table.insertRow(row_idx)
            vals = [
                str(pid),
                mark,
                name,
                cat,
                color,
                f"{phys:g}",
                f"{res:g}",
                f"{avail:g} dispo",
            ]
            for col_idx, text in enumerate(vals):
                cell = QTableWidgetItem(text)
                cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                if col_idx in (0, 4, 5, 6, 7):
                    cell.setTextAlignment(Qt.AlignCenter)
                if col_idx == 1:
                    cell.setFont(QFont("Segoe UI", 9, QFont.Bold))
                if col_idx == 7:
                    cell.setForeground(QColor("#16A34A" if avail > 0 else "#94A3B8"))
                    cell.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.catalog_table.setItem(row_idx, col_idx, cell)

    def _on_create_product(self) -> None:
        name = self.name_input.text().strip()
        mark = self.mark_input.text().strip()
        category = self.category_input.text().strip()
        color = self.color_input.text().strip()

        if not name:
            QMessageBox.warning(self, "بيانات ناقصة", "يرجى إدخال اسم المنتج (Name).")
            return

        ext_attrs = {}
        raw_ext = self.ext_attrs_input.text().strip()
        if raw_ext:
            try:
                ext_attrs = json.loads(raw_ext)
            except ValueError:
                QMessageBox.warning(self, "خطأ JSON", "صيغة الخصائص الإضافية JSON غير صالحة.")
                return

        try:
            res = self.data_manager.serials.register_product_with_attributes(
                name=name,
                mark=mark,
                categorie=category,
                coloure=color,
                barcode=self.barcode_input.text().strip() or None,
                selling_price_ht=Decimal(str(self.sell_price_spin.value())),
                warranty_months=self.warranty_spin.value(),
                requires_serial=self.requires_serial_chk.isChecked(),
                extra_attributes=ext_attrs,
            )
            if res.get("success"):
                QMessageBox.information(
                    self,
                    "تم الحفظ",
                    f"تم حفظ المنتج بنجاح (رقم المعرف: {res.get('product_id')}).",
                )
                self.name_input.clear()
                self.barcode_input.clear()
                self.refresh_products()
                self.catalog_updated.emit()
        except Exception as err:
            QMessageBox.critical(self, "خطأ", f"تعذر حفظ المنتج: {err}")

    def _on_receive_batch(self) -> None:
        product_id = self.product_combo.currentData()
        if not product_id:
            QMessageBox.warning(self, "تنبيه", "يرجى اختيار المنتج أولاً.")
            return

        raw_lines = self.serials_text.toPlainText().splitlines()
        serials = [line.strip() for line in raw_lines if line.strip()]
        if not serials:
            QMessageBox.warning(
                self,
                "بيانات ناقصة",
                "يرجى إدخال رقم تسلسلي واحد على الأقل (N° de Série) للدفعة المستلمة.",
            )
            return

        try:
            res = self.data_manager.serials.register_batch_arrival(
                product_id=int(product_id),
                supplier_id=1,
                po_id=None,
                reception_date=self.received_date_edit.date().toString("yyyy-MM-dd"),
                unit_cost_ht=Decimal(str(self.batch_cost_spin.value())),
                freight_customs=Decimal("0.00"),
                serial_numbers=serials,
                user_id=self.current_user_id,
                selling_price_ht=Decimal(str(self.batch_sell_spin.value())) if self.batch_sell_spin.value() > 0 else None,
                batch_number=self.batch_number_input.text().strip() or None,
            )
            if res.get("success"):
                QMessageBox.information(
                    self,
                    "تم إدخال الدفعة",
                    f"تم تسجيل الدفعة ({res.get('batch_number')}) بنجاح بعدد {res.get('serials_count')} قطعة مرقمة.",
                )
                self.serials_text.clear()
                self.batch_number_input.clear()
                self.refresh_products()
                self.catalog_updated.emit()
        except Exception as err:
            QMessageBox.critical(
                self,
                "رفض إدخال الدفعة",
                f"فشل إدخال الدفعة:\n{err}",
            )

    def refresh_traceability(self) -> None:
        """Loads audit logs from Stock_Movement_Log to give live visibility into product physical movements."""
        if not hasattr(self, "trace_table"):
            return

        type_filter = self.cbo_trace_type.currentText() if hasattr(self, "cbo_trace_type") else "Tous les Mouvements"
        search_txt = self.txt_trace_search.text().strip().lower() if hasattr(self, "txt_trace_search") else ""

        db_type = None
        if "Sorties Magasin" in type_filter:
            db_type = "Sale"
        elif "Réceptions" in type_filter:
            db_type = "Purchase_Receive"
        elif "Retours" in type_filter:
            db_type = "Sale_Return"

        logs = []
        if self.data_manager and hasattr(self.data_manager, "stock_movement_log"):
            try:
                logs = self.data_manager.stock_movement_log.get_movements_log(
                    limit=200,
                    movement_type=db_type,
                    search_text=search_txt or None,
                )
            except Exception as exc:
                logger.error("Failed to load Stock_Movement_Log: %s", exc)
                logs = []

        if not logs and not (self.data_manager and hasattr(self.data_manager, "stock_movement_log")):
            # Fallback showcase log entries for demonstration/testing
            if not self._trace_cache:
                self._trace_cache = [
                    {
                        "Transaction_Date": "2026-11-05 10:15:22",
                        "Movement_Type": "Sale",
                        "Product_Name": "KGN39VLEB Combi NoFrost 368L",
                        "Lot_Number": "SN-BOSCH-889120",
                        "Qty_Change": -1,
                        "Stock_After": 8,
                        "Operator_Name": "Storekeeper (Magasinier)",
                        "Notes": "Bon de Sortie BS-20261105-0042 - N° Série: SN-BOSCH-889120",
                    },
                    {
                        "Transaction_Date": "2026-11-05 09:30:10",
                        "Movement_Type": "Purchase_Receive",
                        "Product_Name": "F4J6TY0W DirectDrive 9kg",
                        "Lot_Number": "LOT-20261105-P102",
                        "Qty_Change": 12,
                        "Stock_After": 12,
                        "Operator_Name": "Admin",
                        "Notes": "Réception Lot LOT-20261105-P102 (12 pièces avec N° de Série)",
                    },
                    {
                        "Transaction_Date": "2026-11-04 16:45:00",
                        "Movement_Type": "Sale_Return",
                        "Product_Name": "Inverter 12000 BTU Split R32",
                        "Lot_Number": "SN-MIDEA-4401",
                        "Qty_Change": 1,
                        "Stock_After": 5,
                        "Operator_Name": "SAV Responsable",
                        "Notes": "Bon de Retour BR-20261104-0012 - N° Série: SN-MIDEA-4401",
                    },
                ]
            logs = list(self._trace_cache)
            if db_type:
                logs = [l for l in logs if l.get("Movement_Type") == db_type]
            if search_txt:
                logs = [
                    l for l in logs
                    if search_txt in str(l.get("Product_Name", "")).lower()
                    or search_txt in str(l.get("Lot_Number", "")).lower()
                    or search_txt in str(l.get("Notes", "")).lower()
                ]

        self.trace_table.setRowCount(0)
        type_labels = {
            "Sale": "Sortie Magasin (Bon de Sortie)",
            "Purchase_Receive": "Réception Lot (Achat)",
            "Sale_Return": "Retour Marchandise",
            "Adjustment": "Ajustement Inventaire",
            "Waste": "Mise au Rebut",
        }

        for row_idx, entry in enumerate(logs):
            self.trace_table.insertRow(row_idx)
            ts = str(entry.get("Transaction_Date") or "-")[:19]
            raw_type = str(entry.get("Movement_Type") or "-")
            type_lbl = type_labels.get(raw_type, raw_type)
            p_name = str(entry.get("Product_Name") or "-")
            lot_sn = str(entry.get("Lot_Number") or entry.get("Batch_ID") or "-")
            qty = float(entry.get("Qty_Change") or 0)
            stk_aft = str(entry.get("Stock_After") if entry.get("Stock_After") is not None else "-")
            user = str(entry.get("Operator_Name") or entry.get("User_ID") or "Magasinier")
            notes = str(entry.get("Notes") or "")

            vals = [ts, type_lbl, p_name, lot_sn, f"{qty:+g}", stk_aft, user, notes]
            for col_idx, text in enumerate(vals):
                cell = QTableWidgetItem(text)
                cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                if col_idx in (0, 1, 3, 4, 5, 6):
                    cell.setTextAlignment(Qt.AlignCenter)
                if col_idx == 1:
                    cell.setFont(QFont("Segoe UI", 9, QFont.Bold))
                    if raw_type == "Sale":
                        cell.setForeground(QColor("#007572"))
                    elif raw_type == "Purchase_Receive":
                        cell.setForeground(QColor("#16A34A"))
                    elif raw_type == "Sale_Return":
                        cell.setForeground(QColor("#D97706"))
                if col_idx == 4:
                    cell.setFont(QFont("Segoe UI", 9, QFont.Bold))
                    cell.setForeground(QColor("#16A34A" if qty > 0 else "#DC2626"))
                self.trace_table.setItem(row_idx, col_idx, cell)
