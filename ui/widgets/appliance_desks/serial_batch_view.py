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

        # Instantiate legacy inputs for backward compatibility (disabled & locked)
        self.mark_input = QLineEdit()
        self.name_input = QLineEdit()
        self.category_input = QLineEdit()
        self.color_input = QLineEdit()
        self.barcode_input = QLineEdit()
        self.warranty_spin = QSpinBox()
        self.buy_price_spin = QDoubleSpinBox()
        self.sell_price_spin = QDoubleSpinBox()
        self.ext_attrs_input = QLineEdit()
        self.requires_serial_chk = QCheckBox()
        self.save_product_btn = QPushButton("+ Enregistrer le Produit")
        self.save_product_btn.setEnabled(False)
        self.save_product_btn.clicked.connect(self._on_create_product)

        self.product_combo = QComboBox()
        self.batch_number_input = QLineEdit()
        self.received_date_edit = QDateEdit(QDate.currentDate())
        self.batch_cost_spin = QDoubleSpinBox()
        self.batch_sell_spin = QDoubleSpinBox()
        self.serials_text = QPlainTextEdit()
        self.receive_batch_btn = QPushButton("Réceptionner le Lot && Enregistrer les N° de Série")
        self.receive_batch_btn.setEnabled(False)
        self.receive_batch_btn.clicked.connect(self._on_receive_batch)

        # -------------------------------------------------------------
        # Centralized Inbound Policy & Serial Audit Banner (Task #6)
        # -------------------------------------------------------------
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        # Left Panel: Inbound Policy & Routing Card
        policy_card = QFrame()
        policy_card.setObjectName("PolicyCard")
        policy_card.setStyleSheet(
            "QFrame#PolicyCard { "
            "  background-color: #F8FAFC; border: 1.5px solid #007572; border-radius: 8px; "
            "}"
        )
        pol_layout = QVBoxLayout(policy_card)
        pol_layout.setContentsMargins(14, 12, 14, 12)
        pol_layout.setSpacing(6)

        pol_header = QHBoxLayout()
        lbl_pol_icon = QLabel()
        lbl_pol_icon.setPixmap(get_duotone_icon("security", 20).pixmap(20, 20))
        pol_header.addWidget(lbl_pol_icon)

        lbl_pol_title = QLabel("Politique de Réception Centralisée & Traçabilité (Parcours Restreint)")
        lbl_pol_title.setStyleSheet("font-size: 13px; font-weight: 800; color: #007572;")
        pol_header.addWidget(lbl_pol_title)
        pol_header.addStretch()
        pol_layout.addLayout(pol_header)

        lbl_pol_desc = QLabel(
            "La création de produits et la réception de nouveaux lots sont strictement restreintes à 2 parcours autorisés :<br>"
            "&nbsp;&nbsp;<b>1. Achats & Entrées</b> (Commandes et Bons de Réception officiels)<br>"
            "&nbsp;&nbsp;<b>2. Stock & Magasin</b> (Ajout direct au stock avec saisie obligatoire de toutes les données)<br>"
            "<i>Tout enregistrement direct depuis cette interface opérationnelle est verrouillé.</i>"
        )
        lbl_pol_desc.setStyleSheet("color: #334155; font-size: 11.5px; line-height: 1.4;")
        lbl_pol_desc.setWordWrap(True)
        pol_layout.addWidget(lbl_pol_desc)

        btn_row = QHBoxLayout()
        self.btn_nav_procurement = QPushButton("🛒 Aller à Achats & Entrées")
        self.btn_nav_procurement.setCursor(Qt.PointingHandCursor)
        self.btn_nav_procurement.setFixedHeight(30)
        self.btn_nav_procurement.setStyleSheet(
            "QPushButton { background: #007572; color: white; font-weight: 700; font-size: 11.5px; padding: 2px 14px; border: none; border-radius: 5px; }"
            "QPushButton:hover { background: #0A5E5C; }"
        )
        self.btn_nav_procurement.clicked.connect(self._on_goto_procurement)

        self.btn_nav_stock = QPushButton("📦 Aller à Stock & Magasin")
        self.btn_nav_stock.setCursor(Qt.PointingHandCursor)
        self.btn_nav_stock.setFixedHeight(30)
        self.btn_nav_stock.setStyleSheet(
            "QPushButton { background: #FFFFFF; color: #007572; font-weight: 700; font-size: 11.5px; padding: 2px 14px; border: 1.5px solid #007572; border-radius: 5px; }"
            "QPushButton:hover { background: #E6F4F1; }"
        )
        self.btn_nav_stock.clicked.connect(self._on_goto_stock)

        btn_row.addWidget(self.btn_nav_procurement)
        btn_row.addWidget(self.btn_nav_stock)
        btn_row.addStretch()
        pol_layout.addLayout(btn_row)

        top_row.addWidget(policy_card, stretch=3)

        # Right Panel: Serial Number Quick Audit / Inspection
        serial_card = QFrame()
        serial_card.setObjectName("SerialAuditCard")
        serial_card.setStyleSheet(
            "QFrame#SerialAuditCard { "
            "  background-color: #FFFFFF; border: 1.5px solid #CBD5E1; border-radius: 8px; "
            "}"
        )
        sn_layout = QVBoxLayout(serial_card)
        sn_layout.setContentsMargins(14, 12, 14, 12)
        sn_layout.setSpacing(6)

        sn_header = QHBoxLayout()
        lbl_sn_icon = QLabel()
        lbl_sn_icon.setPixmap(get_duotone_icon("barcode_scan", 20).pixmap(20, 20))
        sn_header.addWidget(lbl_sn_icon)

        lbl_sn_title = QLabel("Contrôle & Audit Instantané d'un N° de Série")
        lbl_sn_title.setStyleSheet("font-size: 13px; font-weight: 800; color: #0F172A;")
        sn_header.addWidget(lbl_sn_title)
        sn_header.addStretch()
        sn_layout.addLayout(sn_header)

        sn_input_row = QHBoxLayout()
        self.serial_search_input = QLineEdit()
        self.serial_search_input.setFixedHeight(32)
        self.serial_search_input.setPlaceholderText("Scanner ou saisir un N° de Série (ex: SN-BOSCH-9001)...")
        self.serial_search_input.returnPressed.connect(self._on_verify_serial)
        sn_input_row.addWidget(self.serial_search_input, 1)

        self.btn_search_serial = QPushButton("🔍 Vérifier")
        self.btn_search_serial.setCursor(Qt.PointingHandCursor)
        self.btn_search_serial.setFixedHeight(32)
        self.btn_search_serial.setStyleSheet(
            "QPushButton { background: #0E7471; color: white; font-weight: 700; font-size: 11.5px; padding: 2px 14px; border: none; border-radius: 5px; }"
            "QPushButton:hover { background: #0A5E5C; }"
        )
        self.btn_search_serial.clicked.connect(self._on_verify_serial)
        sn_input_row.addWidget(self.btn_search_serial)
        sn_layout.addLayout(sn_input_row)

        self.lbl_serial_result = QLabel("Prêt pour l'audit. Scannez un code-barres pour vérifier le lot et l'état.")
        self.lbl_serial_result.setStyleSheet("color: #64748B; font-size: 11px; padding-top: 2px;")
        self.lbl_serial_result.setWordWrap(True)
        sn_layout.addWidget(self.lbl_serial_result)

        top_row.addWidget(serial_card, stretch=2)
        tab_lots_layout.addLayout(top_row)

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
        """Blocked direct creation - redirected to authorized paths."""
        QMessageBox.warning(
            self,
            "Action Non Autorisée (Parcours Restreint)",
            "L'enregistrement des produits et la réception de nouveaux lots sont strictement "
            "restreints aux deux parcours exclusifs :\n\n"
            "1. Achats & Entrées (Bons de Réception Fournisseurs)\n"
            "2. Stock & Magasin (Ajout Direct au Stock avec saisie intégrale)\n\n"
            "L'enregistrement direct depuis cette interface opérationnelle est verrouillé afin de garantir l'intégrité comptable et la traçabilité des stocks."
        )

    def _on_receive_batch(self) -> None:
        """Blocked direct reception - redirected to authorized paths."""
        QMessageBox.warning(
            self,
            "Action Non Autorisée (Parcours Restreint)",
            "La réception et l'enregistrement de nouveaux lots sont strictement "
            "restreints aux deux parcours exclusifs :\n\n"
            "1. Achats & Entrées (Bons de Réception Fournisseurs)\n"
            "2. Stock & Magasin (Ajout Direct au Stock avec saisie intégrale)\n\n"
            "L'enregistrement direct depuis cette interface opérationnelle est verrouillé afin de garantir l'intégrité comptable et la traçabilité des stocks."
        )

    def _on_goto_procurement(self) -> None:
        parent = self.window()
        if parent and hasattr(parent, "switch_page"):
            parent.switch_page(2)
        else:
            QMessageBox.information(self, "Navigation", "Veuillez vous rendre dans le menu latéral : 'Achats & Entrées'.")

    def _on_goto_stock(self) -> None:
        parent = self.window()
        if parent and hasattr(parent, "switch_page"):
            parent.switch_page(3)
        else:
            QMessageBox.information(self, "Navigation", "Veuillez vous rendre dans le menu latéral : 'Stock & Magasin'.")

    def _on_verify_serial(self) -> None:
        sn = self.serial_search_input.text().strip()
        if not sn:
            self.lbl_serial_result.setText("<span style='color: #64748B;'>Veuillez scanner ou saisir un N° de Série.</span>")
            return
        if not self.data_manager or not hasattr(self.data_manager, "serials"):
            self.lbl_serial_result.setText(f"<b>N° Série :</b> {sn} (Mode démo)")
            return
        try:
            res = self.data_manager.serials.get_serial_details(sn)
            if res:
                st = res.get("Status", "UNKNOWN")
                st_color = "#007572" if st == "IN_STOCK" else ("#DC2626" if st == "SOLD" else "#D97706")
                st_fr = "En Stock Magasin" if st == "IN_STOCK" else ("Vendu / Sorti" if st == "SOLD" else st)
                cost = float(res.get("Unit_Cost_Landed", 0))
                self.lbl_serial_result.setText(
                    f"<b>Produit :</b> {res.get('Product_Name', '---')} ({res.get('Brand_Mark', '')} - {res.get('Color_Finish', '')})<br>"
                    f"<b>Lot :</b> #{res.get('Batch_ID', '---')} | <b>Statut :</b> <span style='color: {st_color}; font-weight: bold;'>{st_fr}</span> | "
                    f"<b>Coût Achat :</b> {cost:,.2f} DA"
                )
            else:
                self.lbl_serial_result.setText(f"<span style='color: #DC2626; font-weight: bold;'>⚠️ N° de Série '{sn}' introuvable dans le référentiel.</span>")
        except Exception as exc:
            self.lbl_serial_result.setText(f"<span style='color: #DC2626;'>Erreur d'audit : {exc}</span>")

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
