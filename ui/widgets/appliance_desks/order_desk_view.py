# -*- coding: utf-8 -*-
"""
ui/widgets/appliance_desks/order_desk_view.py
=============================================
Order Desk UI (Bureau des Commandes - مكتب الطلبات).
Provides:
- Multi-Scanner / Multi-Session tabs so multiple barcode scanners on the same PC
  route scans to completely independent sales sessions.
- Filtering by Mark (العلامة التجارية), Name (الاسم), Categorie (الفئة), and Coloure (اللون).
- Theoretical stock reservation without locking physical serial numbers (N° de Série).
- Generation of Bon C (بيع مباشر), Bon Crédit (أجل), and Bon de Livraison (توصيل).
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QSettings, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from .quick_client_dialog import QuickClientDialog

from ui.formatting import format_money
from ui.hardware.raw_input_filter import MultiScannerHIDManager
from ui.icons import get_duotone_icon, get_trash_icon


COLOR_PALETTE = {
    "inox": "#8A9EA7",
    "acier": "#8A9EA7",
    "blanc": "#FFFFFF",
    "white": "#FFFFFF",
    "noir": "#1E293B",
    "black": "#1E293B",
    "silver": "#CBD5E1",
    "argent": "#CBD5E1",
    "gris": "#64748B",
    "grey": "#64748B",
    "gray": "#64748B",
    "gris anthracite": "#475569",
    "anthracite": "#475569",
    "beige": "#F5F5DC",
    "crème": "#FDFBF7",
    "creme": "#FDFBF7",
    "rouge": "#DC2626",
    "red": "#DC2626",
    "marron": "#78350F",
    "brown": "#78350F",
    "bleu": "#2563EB",
    "blue": "#2563EB",
    "vert": "#16A34A",
    "green": "#16A34A",
    "doré": "#D97706",
    "dore": "#D97706",
    "gold": "#D97706",
}


def get_color_hex(color_name: str) -> str:
    """Returns the hex color code for a color name, with fallback to neutral slate."""
    if not color_name:
        return "#94A3B8"
    c_clean = str(color_name).strip()
    if c_clean.startswith("#") and len(c_clean) in (4, 7):
        return c_clean
    return COLOR_PALETTE.get(c_clean.lower(), "#94A3B8")


class ColorBadgeWidget(QWidget):
    """
    Renders the direct visual application of a color finish:
    - Circular swatch preview with subtle border (prevents white on white blending)
    - Clean color name text
    - Rich interactive tooltip with color name, hex code, and application notice
    """

    def __init__(self, color_name: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.color_name = color_name or "Standard"
        self.hex_code = get_color_hex(self.color_name)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignCenter)

        # Swatch dot
        self.swatch = QFrame()
        self.swatch.setFixedSize(13, 13)
        border_col = "#94A3B8" if self.hex_code.upper() in ("#FFFFFF", "#FDFBF7", "#F5F5DC") else "rgba(0,0,0,0.25)"
        self.swatch.setStyleSheet(
            f"background-color: {self.hex_code}; border: 1px solid {border_col}; border-radius: 6px;"
        )
        layout.addWidget(self.swatch)

        # Name label
        self.lbl_text = QLabel(self.color_name)
        self.lbl_text.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #334155; background: transparent; border: none;"
        )
        layout.addWidget(self.lbl_text)

        tt = f"Couleur / Finition : {self.color_name}\nCode Hex : {self.hex_code}\n(Aperçu visuel direct)"
        self.setToolTip(tt)
        self.swatch.setToolTip(tt)
        self.lbl_text.setToolTip(tt)

TABLE_STYLE = """
    QTableWidget {
        background-color: #FFFFFF;
        border: 1px solid #DCDFE6;
        border-radius: 6px;
        gridline-color: #F1F5F9;
        selection-background-color: #E6F4F1;
        selection-color: #007572;
        alternate-background-color: #FAFBFC;
        font-size: 12px;
        color: #2C3E50;
    }
    QHeaderView::section {
        background-color: #F8FAFC;
        color: #2C3E50;
        font-weight: 700;
        font-size: 12px;
        padding: 6px 6px;
        border: none;
        border-bottom: 2px solid #007572;
        border-right: 1px solid #E2E8F0;
    }
"""

PRIMARY_BTN_STYLE = """
    QPushButton {
        background-color: #007572;
        color: #FFFFFF;
        font-weight: 700;
        min-height: 0px;
        padding: 4px 14px;
        border-radius: 4px;
        border: none;
        font-size: 12px;
    }
    QPushButton:hover { background-color: #005A57; }
    QPushButton:pressed { background-color: #003D3A; }
    QPushButton:disabled { background-color: #F1F5F9; color: #94A3B8; border: 1px solid #E2E8F0; }
"""

OUTLINE_BTN_STYLE = """
    QPushButton {
        background-color: #FFFFFF;
        color: #007572;
        border: 1.5px solid #007572;
        font-weight: 700;
        min-height: 0px;
        padding: 4px 12px;
        border-radius: 4px;
        font-size: 12px;
    }
    QPushButton:hover { background-color: #E6F4F1; border-color: #005A57; color: #005A57; }
    QPushButton:pressed { background-color: #CCEBE6; }
    QPushButton:disabled { background-color: #F8FAFC; color: #94A3B8; border-color: #CBD5E1; }
"""

DANGER_BTN_STYLE = """
    QPushButton {
        background-color: #FFFFFF;
        color: #C0392B;
        border: 1px solid #E74C3C;
        border-radius: 4px;
        padding: 2px 10px;
        font-size: 11px;
        font-weight: 700;
        min-height: 28px;
    }
    QPushButton:hover {
        background-color: #FDF2F2;
        border-color: #C0392B;
        color: #962D22;
    }
"""

SLATE_OUTLINE_BTN_STYLE = """
    QPushButton {
        background-color: #FFFFFF;
        color: #334155;
        border: 1px solid #CBD5E1;
        font-weight: 600;
        min-height: 0px;
        padding: 4px 12px;
        border-radius: 4px;
        font-size: 12px;
    }
    QPushButton:hover { background-color: #F8FAFC; border-color: #94A3B8; color: #0F172A; }
"""


class CartQtyStepper(QWidget):
    """Compact and tactile +/- quantity stepper for cart items, eliminating raw Qt SpinBox borders."""
    qtyChanged = Signal(int)

    def __init__(self, qty: int, max_qty: int = 999, parent=None):
        super().__init__(parent)
        self._qty = qty
        self._max = max(1, max_qty)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignCenter)

        self.btn_minus = QPushButton("−")
        self.btn_minus.setFixedSize(22, 22)
        self.btn_minus.setCursor(Qt.PointingHandCursor)
        self.btn_minus.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9;
                color: #334155;
                font-weight: 800;
                font-size: 13px;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #E2E8F0;
                color: #0F172A;
                border-color: #94A3B8;
            }
            QPushButton:pressed {
                background-color: #CBD5E1;
            }
        """)
        self.btn_minus.clicked.connect(self._decrement)
        layout.addWidget(self.btn_minus)

        self.lbl_qty = QLabel(str(self._qty))
        self.lbl_qty.setFixedWidth(24)
        self.lbl_qty.setAlignment(Qt.AlignCenter)
        self.lbl_qty.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: #0F172A; background: transparent; border: none;"
        )
        layout.addWidget(self.lbl_qty)

        self.btn_plus = QPushButton("+")
        self.btn_plus.setFixedSize(22, 22)
        self.btn_plus.setCursor(Qt.PointingHandCursor)
        self.btn_plus.setStyleSheet("""
            QPushButton {
                background-color: #E6F4F1;
                color: #0E7471;
                font-weight: 800;
                font-size: 13px;
                border: 1px solid #BCE3DC;
                border-radius: 4px;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #CCEBE5;
                border-color: #0E7471;
            }
            QPushButton:pressed {
                background-color: #B2DFDB;
            }
        """)
        self.btn_plus.clicked.connect(self._increment)
        layout.addWidget(self.btn_plus)

    def _decrement(self) -> None:
        if self._qty > 1:
            self._qty -= 1
            self.lbl_qty.setText(str(self._qty))
            self.qtyChanged.emit(self._qty)
        elif self._qty == 1:
            self.qtyChanged.emit(0)

    def _increment(self) -> None:
        if self._qty < self._max:
            self._qty += 1
            self.lbl_qty.setText(str(self._qty))
            self.qtyChanged.emit(self._qty)


class OrderDeskWidget(QWidget):
    """Order Desk workstation supporting Multi-Scanner / Multi-Session and Theoretical Orders."""

    bonCGenerated = Signal(dict)
    bonCreditRequested = Signal(dict)
    bonLivraisonGenerated = Signal(dict)
    scanDispatched = Signal(str, str)

    def __init__(
        self,
        data_manager=None,
        hid_manager: Optional[MultiScannerHIDManager] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.data_manager = data_manager
        self.hid_manager = hid_manager or MultiScannerHIDManager()

        self._session_counter = 1
        self._sessions: Dict[str, Dict[str, Any]] = {
            "SESSION_1": {
                "label": "Session Vente #1",
                "scanner_id": None,
                "client_id": 1,
                "cart": [],
                "delivery_address": "",
            },
        }
        self._active_session_id = "SESSION_1"
        self._catalog_cache: List[Dict[str, Any]] = []

        # Connect global listener to automatically route all hardware scanner inputs
        self.scanDispatched.connect(self._process_scanned_barcode)
        self.hid_manager.register_global_callback(self._on_any_scanner_input)

        self._init_ui()
        self.refresh_catalog()

    def _init_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 0. Automatic Horizontal & Vertical Scroll Area ensuring all elements are fully visible
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("OrderDeskScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("""
            QScrollArea#OrderDeskScrollArea {
                background: transparent;
                border: none;
            }
            QWidget#OrderDeskContentWidget {
                background-color: #F4F6F8;
            }
        """)

        content_widget = QWidget()
        content_widget.setObjectName("OrderDeskContentWidget")
        content_widget.setMinimumWidth(1080)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(10)

        # 1. Top Session Tabs Bar (Replacing the legacy static combo bar)
        session_bar = self._create_session_tabs_bar()
        content_layout.addWidget(session_bar)

        # 2. Top Filter Bar (Relocated from the side panel to the top)
        filter_bar = self._create_top_filter_bar()
        content_layout.addWidget(filter_bar)

        # 3. Main 2-Column Body: Catalog (Left) + Cart (Right) with Movable Splitter
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setObjectName("OrderDeskMainSplitter")
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setStyleSheet("""
            QSplitter#OrderDeskMainSplitter::handle {
                background-color: #E2E8F0;
                width: 6px;
                margin: 4px 1px;
                border-radius: 3px;
            }
            QSplitter#OrderDeskMainSplitter::handle:hover {
                background-color: #007572;
            }
        """)
        self.catalog_panel = self._create_catalog_panel()
        self.cart_panel = self._create_cart_panel()
        self.splitter.addWidget(self.catalog_panel)
        self.splitter.addWidget(self.cart_panel)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self._restore_splitter_state()
        self.splitter.splitterMoved.connect(self._save_splitter_state)
        content_layout.addWidget(self.splitter, 1)

        self.scroll_area.setWidget(content_widget)
        root_layout.addWidget(self.scroll_area)

    def _create_session_tabs_bar(self) -> QWidget:
        session_bar = QFrame()
        session_bar.setObjectName("SessionTabsBar")
        session_bar.setFixedHeight(48)
        session_bar.setStyleSheet("""
            QFrame#SessionTabsBar {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
            }
            QTabBar#SessionTabBar {
                border-bottom: none;
            }
            QTabBar#SessionTabBar::tab {
                background-color: #F1F5F9;
                color: #475569;
                font-weight: 700;
                font-size: 12px;
                padding: 6px 14px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                border: 1px solid #CBD5E1;
                min-height: 24px;
            }
            QTabBar#SessionTabBar::tab:selected {
                background-color: #0E7471;
                color: #FFFFFF;
                border-color: #0E7471;
            }
            QTabBar#SessionTabBar::tab:hover:!selected {
                background-color: #E2E8F0;
                color: #0F172A;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        sb_layout = QHBoxLayout(session_bar)
        sb_layout.setContentsMargins(10, 4, 12, 4)
        sb_layout.setSpacing(10)

        lbl_scan_icon = QLabel()
        lbl_scan_icon.setPixmap(get_duotone_icon("barcode_scan", 18).pixmap(18, 18))
        sb_layout.addWidget(lbl_scan_icon)

        # Specialized Session Tabs
        self.session_tab_bar = QTabBar()
        self.session_tab_bar.setObjectName("SessionTabBar")
        self.session_tab_bar.setDrawBase(False)
        self.session_tab_bar.setUsesScrollButtons(True)
        self.session_tab_bar.setTabsClosable(False)  # Managed via custom sleek close buttons
        self.session_tab_bar.setCursor(Qt.PointingHandCursor)
        self.session_tab_bar.setContextMenuPolicy(Qt.CustomContextMenu)
        self.session_tab_bar.customContextMenuRequested.connect(self._on_session_tab_context_menu)
        self.session_tab_bar.currentChanged.connect(self._on_session_tab_switched)

        self._sync_session_tabs()
        sb_layout.addWidget(self.session_tab_bar)

        # "+ Nouvelle Session" Button
        btn_new_sess = QPushButton("+ Nouvelle Session")
        btn_new_sess.setIcon(get_duotone_icon("barcode_scan", 14))
        btn_new_sess.setIconSize(QSize(14, 14))
        btn_new_sess.setCursor(Qt.PointingHandCursor)
        btn_new_sess.setFixedHeight(32)
        btn_new_sess.setStyleSheet(PRIMARY_BTN_STYLE)
        btn_new_sess.clicked.connect(self._create_new_session)
        sb_layout.addWidget(btn_new_sess)

        sb_layout.addStretch()

        # Scanner isolation badge
        self.lbl_scanner_status = QLabel("Isolation HID Active")
        self.lbl_scanner_status.setToolTip("Chaque scanner USB / HID est routé vers sa propre session")
        self.lbl_scanner_status.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: #0E7471; background-color: #E6F4F1; "
            "border: 1px solid #BCE3DC; border-radius: 4px; padding: 4px 8px;"
        )
        sb_layout.addWidget(self.lbl_scanner_status)

        return session_bar

    def _create_top_filter_bar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("OrderTopFilterBar")
        panel.setFixedHeight(50)
        panel.setStyleSheet("""
            QFrame#OrderTopFilterBar {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
            QComboBox {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 5px;
                padding: 3px 8px;
                font-size: 12px;
                color: #1E293B;
            }
            QComboBox:hover {
                border-color: #0E7471;
            }
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 5px;
                padding: 3px 10px;
                font-size: 12px;
                color: #1E293B;
            }
            QLineEdit:focus {
                border: 1.5px solid #0E7471;
            }
        """)
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)

        f_icon = QLabel()
        f_icon.setPixmap(get_duotone_icon("filter", 16).pixmap(16, 16))
        layout.addWidget(f_icon)

        title = QLabel("FILTRES :")
        title.setStyleSheet("font-size: 11px; font-weight: 800; color: #0E7471; letter-spacing: 0.5px;")
        layout.addWidget(title)

        def make_lbl(txt: str) -> QLabel:
            lbl = QLabel(txt)
            lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #475569;")
            return lbl

        layout.addWidget(make_lbl("Marque :"))
        self.cbo_mark = QComboBox()
        self.cbo_mark.setFixedHeight(34)
        self.cbo_mark.setFixedWidth(115)
        self.cbo_mark.addItems(["Tous", "Bosch", "Samsung", "LG", "Brandt", "Condor", "Cristor", "Midea", "Moulinex"])
        self.cbo_mark.currentTextChanged.connect(self.refresh_catalog)
        layout.addWidget(self.cbo_mark)

        layout.addWidget(make_lbl("Catégorie :"))
        self.cbo_category = QComboBox()
        self.cbo_category.setFixedHeight(34)
        self.cbo_category.setFixedWidth(155)
        self.cbo_category.addItems([
            "Tous",
            "Gros Électroménager",
            "Petit Électroménager",
            "Réfrigérateurs",
            "Lave-linge",
            "Climatisation",
            "Téléviseurs & Multimédia",
            "Cuisson & Fours",
        ])
        self.cbo_category.currentTextChanged.connect(self.refresh_catalog)
        layout.addWidget(self.cbo_category)

        layout.addWidget(make_lbl("Couleur :"))
        self.cbo_color = QComboBox()
        self.cbo_color.setFixedHeight(34)
        self.cbo_color.setFixedWidth(95)
        self.cbo_color.addItems(["Tous", "Inox", "Blanc", "Noir", "Silver", "Gris"])
        self.cbo_color.currentTextChanged.connect(self.refresh_catalog)
        layout.addWidget(self.cbo_color)

        self.txt_search = QLineEdit()
        self.txt_search.setFixedHeight(34)
        self.txt_search.setMinimumWidth(170)
        self.txt_search.setPlaceholderText("Rechercher désignation, marque, catégorie, code-barres...")
        self.txt_search.textChanged.connect(self.refresh_catalog)
        self.txt_search.returnPressed.connect(self._on_search_return_pressed)
        layout.addWidget(self.txt_search, 1)

        btn_reset = QPushButton("Réinitialiser")
        btn_reset.setIcon(get_duotone_icon("refresh", 13))
        btn_reset.setIconSize(QSize(13, 13))
        btn_reset.setCursor(Qt.PointingHandCursor)
        btn_reset.setFixedHeight(34)
        btn_reset.setFixedWidth(105)
        btn_reset.setStyleSheet(SLATE_OUTLINE_BTN_STYLE)
        btn_reset.clicked.connect(self._reset_filters)
        layout.addWidget(btn_reset)

        btn_refresh = QPushButton("Actualiser")
        btn_refresh.setIcon(get_duotone_icon("refresh", 13))
        btn_refresh.setIconSize(QSize(13, 13))
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setFixedHeight(34)
        btn_refresh.setFixedWidth(95)
        btn_refresh.setStyleSheet(OUTLINE_BTN_STYLE)
        btn_refresh.clicked.connect(self.refresh_catalog)
        layout.addWidget(btn_refresh)

        lbl_info = QLabel("Vente Théorique")
        lbl_info.setToolTip(
            "Ce bureau réserve uniquement le modèle et la quantité théorique sans bloquer de N° de Série physique.\n"
            "Le scan du N° de Série s'effectue exclusivement au Bureau de Sortie."
        )
        lbl_info.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: #0E7471; background-color: #F8FAFC; "
            "border: 1px solid #CBD5E1; border-left: 3px solid #0E7471; border-radius: 4px; padding: 4px 8px;"
        )
        layout.addWidget(lbl_info)

        return panel

    def _create_catalog_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("OrderCatalogPanel")
        panel.setStyleSheet("""
            QFrame#OrderCatalogPanel {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        cat_header = QHBoxLayout()
        cat_header.setSpacing(8)
        cat_icon = QLabel()
        cat_icon.setPixmap(get_duotone_icon("pos", 16).pixmap(16, 16))
        cat_header.addWidget(cat_icon)
        lbl_cat_title = QLabel("Catalogue des Produits Disponibles")
        lbl_cat_title.setStyleSheet("font-size: 13px; font-weight: 800; color: #1E293B;")
        cat_header.addWidget(lbl_cat_title)
        cat_header.addStretch()
        layout.addLayout(cat_header)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Marque",
            "Désignation Produit",
            "Catégorie",
            "Couleur",
            "Phys.",
            "Dispo.",
            "Action",
        ])
        self.table.setStyleSheet(TABLE_STYLE)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.horizontalHeader().setFixedHeight(38)
        self.table.horizontalHeader().setMinimumSectionSize(52)
        self.table.setShowGrid(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        self.table.horizontalHeaderItem(0).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeaderItem(1).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeaderItem(2).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeaderItem(3).setTextAlignment(Qt.AlignCenter)
        self.table.horizontalHeaderItem(4).setTextAlignment(Qt.AlignCenter)
        self.table.horizontalHeaderItem(5).setTextAlignment(Qt.AlignCenter)
        self.table.horizontalHeaderItem(6).setTextAlignment(Qt.AlignCenter)

        # Automatic horizontal scrollbar as needed to prevent any clipping
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 85)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(2, QHeaderView.Interactive)
        self.table.setColumnWidth(2, 165)
        h.setSectionResizeMode(3, QHeaderView.Interactive)
        self.table.setColumnWidth(3, 115)
        h.setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(4, 52)
        h.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 52)
        h.setSectionResizeMode(6, QHeaderView.Fixed)
        self.table.setColumnWidth(6, 142)

        layout.addWidget(self.table, 1)
        return panel

    def _create_cart_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("OrderCartPanel")
        panel.setMinimumWidth(300)
        panel.setStyleSheet("""
            QFrame#OrderCartPanel {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Cart Header + Clear Button
        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        c_icon = QLabel()
        c_icon.setPixmap(get_duotone_icon("pos", 18).pixmap(18, 18))
        header_row.addWidget(c_icon)

        self.lbl_cart_header = QLabel("Panier — Session #1")
        self.lbl_cart_header.setStyleSheet("font-size: 13px; font-weight: 800; color: #1E293B;")
        header_row.addWidget(self.lbl_cart_header)
        header_row.addStretch()

        btn_clear = QPushButton("Vider")
        btn_clear.setIcon(get_trash_icon(14))
        btn_clear.setIconSize(QSize(14, 14))
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.setFixedHeight(28)
        btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #DC2626;
                border: 1px solid #FECACA;
                border-radius: 5px;
                padding: 0 10px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #FEF2F2;
                border-color: #DC2626;
            }
        """)
        btn_clear.clicked.connect(self._clear_current_cart)
        header_row.addWidget(btn_clear)
        layout.addLayout(header_row)

        # Client Selection Row with fast search by Name/Phone & Quick Add
        client_row = QHBoxLayout()
        client_row.setSpacing(6)
        lbl_cl = QLabel("Client :")
        lbl_cl.setStyleSheet("font-size: 12px; font-weight: 700; color: #2C3E50;")
        client_row.addWidget(lbl_cl)

        self.cbo_client = QComboBox()
        self.cbo_client.setFixedHeight(32)
        self.cbo_client.setEditable(True)
        self.cbo_client.setInsertPolicy(QComboBox.NoInsert)
        if self.cbo_client.lineEdit():
            self.cbo_client.lineEdit().setPlaceholderText("🔍 Rechercher par nom ou tél...")
        self._load_clients_into_combo()
        self.cbo_client.currentIndexChanged.connect(self._on_client_changed)
        client_row.addWidget(self.cbo_client, stretch=1)

        btn_new_client = QPushButton("+ Client")
        btn_new_client.setIcon(get_duotone_icon("users", 13))
        btn_new_client.setIconSize(QSize(13, 13))
        btn_new_client.setCursor(Qt.PointingHandCursor)
        btn_new_client.setFixedHeight(32)
        btn_new_client.setStyleSheet(OUTLINE_BTN_STYLE)
        btn_new_client.setToolTip("Ajouter rapidement un nouveau client en quelques secondes")
        btn_new_client.clicked.connect(self._open_quick_client_dialog)
        client_row.addWidget(btn_new_client)

        layout.addLayout(client_row)

        # Cart Items Table
        self.cart_table = QTableWidget(0, 4)
        self.cart_table.setHorizontalHeaderLabels(["Désignation", "Couleur", "Qté", "Total TTC"])
        self.cart_table.setStyleSheet(TABLE_STYLE)
        self.cart_table.verticalHeader().setVisible(False)
        self.cart_table.verticalHeader().setDefaultSectionSize(36)
        self.cart_table.horizontalHeader().setFixedHeight(34)
        self.cart_table.setShowGrid(True)
        self.cart_table.setAlternatingRowColors(True)
        self.cart_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.cart_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.cart_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.cart_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        ch = self.cart_table.horizontalHeader()
        ch.setSectionResizeMode(0, QHeaderView.Stretch)
        ch.setSectionResizeMode(1, QHeaderView.Interactive)
        self.cart_table.setColumnWidth(1, 55)
        ch.setSectionResizeMode(2, QHeaderView.Fixed)
        self.cart_table.setColumnWidth(2, 75)
        ch.setSectionResizeMode(3, QHeaderView.Fixed)
        self.cart_table.setColumnWidth(3, 95)
        self.cart_table.horizontalHeaderItem(0).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.cart_table.horizontalHeaderItem(1).setTextAlignment(Qt.AlignCenter)
        self.cart_table.horizontalHeaderItem(2).setTextAlignment(Qt.AlignCenter)
        self.cart_table.horizontalHeaderItem(3).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.cart_table, 1)

        # Delivery info for Bon de Livraison
        self.txt_delivery_addr = QLineEdit()
        self.txt_delivery_addr.setFixedHeight(34)
        self.txt_delivery_addr.setPlaceholderText("Adresse de livraison & téléphone (pour Bon de Livraison)...")
        self.txt_delivery_addr.textChanged.connect(self._on_delivery_addr_changed)
        layout.addWidget(self.txt_delivery_addr)

        # Summary Total Box (Styled matching Stock & Magasin KPI badges)
        total_box = QFrame()
        total_box.setObjectName("CartTotalBox")
        total_box.setFixedHeight(44)
        total_box.setStyleSheet("""
            QFrame#CartTotalBox {
                background-color: #E8F8F5;
                border: 1px solid #A3E4D7;
                border-radius: 4px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        tot_layout = QHBoxLayout(total_box)
        tot_layout.setContentsMargins(12, 0, 12, 0)
        lbl_tot_tag = QLabel("TOTAL COMMANDE TTC :")
        lbl_tot_tag.setStyleSheet("font-size: 11px; font-weight: 700; color: #007572;")
        tot_layout.addWidget(lbl_tot_tag)
        tot_layout.addStretch()
        self.lbl_total = QLabel("0.00 DA")
        self.lbl_total.setStyleSheet("font-size: 16px; font-weight: 800; color: #007572;")
        tot_layout.addWidget(self.lbl_total)
        layout.addWidget(total_box)

        # Primary CTA: Bon C (Increased height for prominent enterprise hierarchy)
        btn_bon_c = QPushButton("Émettre Bon Comptant (Vente Directe -> Caisse)")
        btn_bon_c.setIcon(get_duotone_icon("payment_white", 16))
        btn_bon_c.setIconSize(QSize(16, 16))
        btn_bon_c.setCursor(Qt.PointingHandCursor)
        btn_bon_c.setFixedHeight(44)
        btn_bon_c.setStyleSheet("""
            QPushButton {
                background-color: #007572;
                color: #FFFFFF;
                font-weight: 700;
                font-size: 12px;
                border: 1px solid #005A57;
                border-radius: 5px;
                padding: 0 12px;
            }
            QPushButton:hover {
                background-color: #005A57;
                border-color: #003D3A;
            }
            QPushButton:pressed {
                background-color: #003D3A;
            }
        """)
        btn_bon_c.clicked.connect(lambda: self._submit_order("BON_C"))
        layout.addWidget(btn_bon_c)

        # Secondary Row: Bon Crédit & Bon de Livraison side-by-side (Increased height)
        sec_row = QHBoxLayout()
        sec_row.setSpacing(8)

        btn_credit = QPushButton("Bon Crédit (Admin)")
        btn_credit.setIcon(get_duotone_icon("shield_admin", 15))
        btn_credit.setIconSize(QSize(15, 15))
        btn_credit.setCursor(Qt.PointingHandCursor)
        btn_credit.setFixedHeight(40)
        btn_credit.setStyleSheet(OUTLINE_BTN_STYLE)
        btn_credit.clicked.connect(lambda: self._submit_order("BON_CREDIT"))
        sec_row.addWidget(btn_credit)

        btn_livraison = QPushButton("Bon de Livraison")
        btn_livraison.setIcon(get_duotone_icon("truck_delivery", 15))
        btn_livraison.setIconSize(QSize(15, 15))
        btn_livraison.setCursor(Qt.PointingHandCursor)
        btn_livraison.setFixedHeight(40)
        btn_livraison.setStyleSheet(OUTLINE_BTN_STYLE)
        btn_livraison.clicked.connect(lambda: self._submit_order("BON_LIVRAISON"))
        sec_row.addWidget(btn_livraison)

        layout.addLayout(sec_row)
        return panel

    def _open_quick_client_dialog(self) -> None:
        dlg = QuickClientDialog(data_manager=self.data_manager, parent=self)
        if dlg.exec() == QDialog.Accepted and dlg.created_client:
            new_c = dlg.created_client
            if not new_c.get("Client_ID"):
                new_c["Client_ID"] = max([c["Client_ID"] for c in getattr(self, "_clients_cache", [])], default=1) + 1

            if not hasattr(self, "_clients_cache"):
                self._clients_cache = []
            self._clients_cache.append(new_c)

            self._load_clients_into_combo(selected_id=new_c["Client_ID"])

            # Set as active session's client
            if hasattr(self, "_active_session_id") and self._active_session_id in self._sessions:
                self._sessions[self._active_session_id]["client_id"] = new_c["Client_ID"]

            # Auto-fill delivery address if provided and currently empty
            if new_c.get("Address") and hasattr(self, "txt_delivery_addr") and not self.txt_delivery_addr.text().strip():
                self.txt_delivery_addr.setText(new_c["Address"])

            self.lbl_scanner_status.setText(f"Client '{new_c['Client_Name']}' créé et sélectionné")

    def _on_client_changed(self, idx: int) -> None:
        if hasattr(self, "_active_session_id") and self._active_session_id in self._sessions:
            cid = self.cbo_client.currentData()
            if cid is not None:
                self._sessions[self._active_session_id]["client_id"] = int(cid)
                for c in getattr(self, "_clients_cache", []):
                    if c.get("Client_ID") == int(cid) and c.get("Address") and hasattr(self, "txt_delivery_addr"):
                        if not self.txt_delivery_addr.text().strip():
                            self.txt_delivery_addr.setText(c["Address"])
                        break

    def _load_clients_into_combo(self, selected_id: Optional[int] = None) -> None:
        self.cbo_client.blockSignals(True)
        self.cbo_client.clear()

        if not hasattr(self, "_clients_cache") or not self._clients_cache:
            self._clients_cache = [
                {"Client_ID": 1, "Client_Name": "Client Comptoir (Standard)", "Phone": "", "Address": ""}
            ]
            if self.data_manager and hasattr(self.data_manager, "clients"):
                try:
                    clients = self.data_manager.clients.get_all_clients() or []
                    for c in clients:
                        cid = c.get("Client_ID")
                        cname = str(c.get("Client_Name") or f"Client #{cid}").strip()
                        cphone = str(c.get("Phone") or "").strip()
                        caddr = str(c.get("Address") or "").strip()
                        if cid and int(cid) != 1:
                            self._clients_cache.append({
                                "Client_ID": int(cid),
                                "Client_Name": cname,
                                "Phone": cphone,
                                "Address": caddr,
                            })
                except Exception as err:
                    logger.debug(f"Error loading clients: {err}")

        select_idx = 0
        for idx, c in enumerate(self._clients_cache):
            display = c["Client_Name"]
            if c.get("Phone"):
                display += f"  —  📞 {c['Phone']}"
            self.cbo_client.addItem(display, c["Client_ID"])
            if selected_id is not None and c["Client_ID"] == selected_id:
                select_idx = idx

        completer = QCompleter(self.cbo_client.model(), self.cbo_client)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.cbo_client.setCompleter(completer)

        self.cbo_client.setCurrentIndex(select_idx)
        self.cbo_client.blockSignals(False)

    def _reset_filters(self) -> None:
        self.cbo_mark.setCurrentIndex(0)
        self.cbo_category.setCurrentIndex(0)
        self.cbo_color.setCurrentIndex(0)
        self.txt_search.clear()
        self.refresh_catalog()

    def refresh_catalog(self) -> None:
        """Loads catalog items from database (or fallback showcase rows) with theoretical availability."""
        search_txt = self.txt_search.text().strip() if hasattr(self, "txt_search") else ""
        mark_txt = self.cbo_mark.currentText() if hasattr(self, "cbo_mark") else "Tous"
        cat_txt = self.cbo_category.currentText() if hasattr(self, "cbo_category") else "Tous"
        col_txt = self.cbo_color.currentText() if hasattr(self, "cbo_color") else "Tous"

        items: List[Dict[str, Any]] = []
        if self.data_manager and hasattr(self.data_manager, "serials"):
            items = self.data_manager.serials.get_catalog_with_theoretical_stock(
                search=search_txt,
                brand_mark=mark_txt,
                category_name=cat_txt,
                color_finish=col_txt,
            )
            self._catalog_cache = items
        else:
            # Fallback showcase catalog in-memory filtering (offline / test mode)
            if not self._catalog_cache:
                self._catalog_cache = [
                    {
                        "Product_ID": 101,
                        "Brand_Mark": "Bosch",
                        "Product_Name": "KGN39VLEB Combi NoFrost 368L",
                        "Category_Name": "Réfrigérateurs",
                        "Color_Finish": "Inox",
                        "Physical_Qty": 8,
                        "Available_Theoretical_Qty": 7,
                        "Unit_Price_TTC": 115000.0,
                        "Barcode": "4242005198030",
                    },
                    {
                        "Product_ID": 102,
                        "Brand_Mark": "LG",
                        "Product_Name": "F4J6TY0W DirectDrive 9kg",
                        "Category_Name": "Lave-linge",
                        "Color_Finish": "Blanc",
                        "Physical_Qty": 12,
                        "Available_Theoretical_Qty": 12,
                        "Unit_Price_TTC": 88000.0,
                        "Barcode": "8806098321092",
                    },
                    {
                        "Product_ID": 103,
                        "Brand_Mark": "Midea",
                        "Product_Name": "Inverter 12000 BTU Split",
                        "Category_Name": "Climatisation",
                        "Color_Finish": "Blanc",
                        "Physical_Qty": 5,
                        "Available_Theoretical_Qty": 4,
                        "Unit_Price_TTC": 64000.0,
                        "Barcode": "6939962711029",
                    },
                ]

            s_low = search_txt.lower()
            m_low = mark_txt.lower()
            c_low = cat_txt.lower()
            col_low = col_txt.lower()

            for it in self._catalog_cache:
                if s_low:
                    name_match = s_low in str(it.get("Product_Name", "")).lower()
                    mark_match = s_low in str(it.get("Brand_Mark", "")).lower()
                    cat_match = s_low in str(it.get("Category_Name", "")).lower()
                    bar_match = s_low in str(it.get("Barcode", "")).lower()
                    if not (name_match or mark_match or cat_match or bar_match):
                        continue
                if m_low and m_low not in ("tous", "all"):
                    if m_low != str(it.get("Brand_Mark", "")).lower():
                        continue
                if c_low and c_low not in ("tous", "all"):
                    if c_low != str(it.get("Category_Name", "")).lower():
                        continue
                if col_low and col_low not in ("tous", "all"):
                    if col_low != str(it.get("Color_Finish", "")).lower():
                        continue
                items.append(it)

        self.table.setRowCount(0)
        for prod in items:
            row = self.table.rowCount()
            self.table.insertRow(row)
            mark = str(prod.get("Brand_Mark") or "Générique")
            name = str(prod.get("Product_Name") or "")
            cat = str(prod.get("Category_Name") or "Électroménager")
            color = str(prod.get("Color_Finish") or "Standard")
            phys = int(prod.get("Physical_Qty") or 0)
            avail = int(prod.get("Available_Theoretical_Qty") or 0)
            price = float(prod.get("Unit_Price_TTC") or 0.0)

            it_mark = QTableWidgetItem(mark)
            it_mark.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self.table.setItem(row, 0, it_mark)

            self.table.setItem(row, 1, QTableWidgetItem(name))

            it_cat = QTableWidgetItem(cat)
            it_cat.setToolTip(f"Catégorie : {cat}")
            self.table.setItem(row, 2, it_cat)

            it_col = QTableWidgetItem(color)
            it_col.setTextAlignment(Qt.AlignCenter)
            it_col.setToolTip(f"Couleur / Finition : {color}\nCode Hex : {get_color_hex(color)}")
            self.table.setItem(row, 3, it_col)
            self.table.setCellWidget(row, 3, ColorBadgeWidget(color))

            it_phys = QTableWidgetItem(str(phys))
            it_phys.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, it_phys)

            it_avail = QTableWidgetItem(str(avail))
            it_avail.setTextAlignment(Qt.AlignCenter)
            it_avail.setForeground(QColor("#16A34A" if avail > 0 else "#94A3B8"))
            it_avail.setFont(QFont("Segoe UI", 10, QFont.Bold))
            it_avail.setToolTip(f"Quantité disponible : {avail}")
            self.table.setItem(row, 5, it_avail)

            btn = QPushButton()
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(28)

            if avail > 0:
                btn.setText(f"+ Ajouter • {format_money(price)} DA")
                btn.setIcon(get_duotone_icon("pos", 13))
                btn.setIconSize(QSize(13, 13))
                btn.setEnabled(True)
                btn.setToolTip(f"Ajouter '{name}' au panier ({self._sessions[self._active_session_id]['label']})")
                btn.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #007572;
                        color: #FFFFFF;
                        font-weight: 700;
                        font-size: 11px;
                        min-height: 28px;
                        max-height: 28px;
                        padding: 3px 8px;
                        border-radius: 4px;
                        border: 1px solid #005A57;
                    }
                    QPushButton:hover {
                        background-color: #005A57;
                        border-color: #003D3A;
                    }
                    QPushButton:pressed {
                        background-color: #003D3A;
                    }
                    """
                )
                btn.clicked.connect(lambda checked=False, p=prod: self._add_product_to_session(self._active_session_id, p))
            else:
                btn.setText("🚫 Épuisé")
                btn.setEnabled(False)
                btn.setToolTip("Rupture de stock théorique")
                btn.setStyleSheet(
                    """
                    QPushButton {
                        background-color: #F8FAFC;
                        color: #94A3B8;
                        font-weight: 600;
                        font-size: 11px;
                        min-height: 28px;
                        max-height: 28px;
                        padding: 3px 8px;
                        border-radius: 4px;
                        border: 1px solid #E2E8F0;
                    }
                    """
                )

            cell_widget = QWidget()
            cell_widget.setStyleSheet("background: transparent;")
            cell_layout = QHBoxLayout(cell_widget)
            cell_layout.setContentsMargins(4, 3, 4, 3)
            cell_layout.addWidget(btn)
            self.table.setCellWidget(row, 6, cell_widget)

    # =========================================================================
    # MULTI-SESSION & MULTI-SCANNER ROUTING (Tabs & HID Isolation)
    # =========================================================================

    def _on_delivery_addr_changed(self, text: str) -> None:
        if hasattr(self, "_active_session_id") and self._active_session_id in self._sessions:
            self._sessions[self._active_session_id]["delivery_address"] = text.strip()

    def _update_tab_label(self, sid: str) -> None:
        if not hasattr(self, "session_tab_bar"):
            return
        sdata = self._sessions.get(sid)
        if not sdata:
            return
        scanner_tag = f" [{sdata['scanner_id']}]" if sdata.get("scanner_id") else ""
        cart_count = len(sdata.get("cart", []))
        count_tag = f" ({cart_count})" if cart_count > 0 else ""
        tab_text = f"{sdata['label']}{scanner_tag}{count_tag}"

        for idx in range(self.session_tab_bar.count()):
            if self.session_tab_bar.tabData(idx) == sid:
                self.session_tab_bar.setTabText(idx, tab_text)
                break
        self._update_tab_close_buttons()

    def _save_splitter_state(self, *args) -> None:
        """Persists the movable separator state between catalog and cart across sessions."""
        try:
            settings = QSettings("StockLam", "OrderDesk")
            settings.setValue("main_splitter_state", self.splitter.saveState())
            settings.setValue("main_splitter_sizes", self.splitter.sizes())
        except Exception as err:
            logger.debug(f"Could not persist splitter state: {err}")

    def _restore_splitter_state(self) -> None:
        """Restores the user's previously saved separator position."""
        try:
            settings = QSettings("StockLam", "OrderDesk")
            saved_state = settings.value("main_splitter_state")
            if saved_state:
                self.splitter.restoreState(saved_state)
            else:
                saved_sizes = settings.value("main_splitter_sizes")
                if saved_sizes and isinstance(saved_sizes, (list, tuple)) and len(saved_sizes) == 2:
                    self.splitter.setSizes([int(saved_sizes[0]), int(saved_sizes[1])])
                else:
                    self.splitter.setSizes([720, 360])
        except Exception as err:
            logger.debug(f"Could not restore splitter state: {err}")
            self.splitter.setSizes([720, 360])

    def _update_tab_close_buttons(self) -> None:
        """Attaches sleek, human-crafted close buttons to tabs when more than 1 session exists."""
        if not hasattr(self, "session_tab_bar"):
            return
        total_tabs = self.session_tab_bar.count()
        for idx in range(total_tabs):
            sid = self.session_tab_bar.tabData(idx)
            if total_tabs <= 1:
                self.session_tab_bar.setTabButton(idx, QTabBar.RightSide, None)
                continue

            btn = QPushButton("×")
            btn.setFixedSize(18, 18)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip("Fermer cette session")
            btn.setStyleSheet("""
                QPushButton {
                    border: none;
                    background-color: transparent;
                    color: #64748B;
                    font-size: 15px;
                    font-weight: bold;
                    line-height: 14px;
                    border-radius: 9px;
                    padding-bottom: 2px;
                }
                QPushButton:hover {
                    background-color: #EF4444;
                    color: #FFFFFF;
                }
            """)
            btn.clicked.connect(lambda checked=False, target_sid=sid: self._close_session_by_id(target_sid))
            self.session_tab_bar.setTabButton(idx, QTabBar.RightSide, btn)

    def _close_session_by_id(self, sid: str) -> None:
        """Closes session corresponding to the provided ID after user confirmation."""
        if not hasattr(self, "session_tab_bar"):
            return
        for idx in range(self.session_tab_bar.count()):
            if self.session_tab_bar.tabData(idx) == sid:
                self._on_session_tab_close_requested(idx)
                break

    def _clear_session_cart(self, sid: str) -> None:
        """Empties cart items for a given session ID."""
        if sid in self._sessions:
            self._sessions[sid]["cart"] = []
            self._sessions[sid]["delivery_address"] = ""
            if sid == self._active_session_id and hasattr(self, "txt_delivery_addr"):
                self.txt_delivery_addr.clear()
            self._update_tab_label(sid)
            if sid == self._active_session_id:
                self._refresh_cart_ui()

    def _on_session_tab_context_menu(self, pos) -> None:
        """Right-click context menu on session tabs for rapid session management."""
        tab_idx = self.session_tab_bar.tabAt(pos)
        if tab_idx < 0:
            return
        sid = self.session_tab_bar.tabData(tab_idx)
        sdata = self._sessions.get(sid, {})
        menu = QMenu(self)

        act_clear = menu.addAction(f"Vider le panier ({len(sdata.get('cart', []))} articles)")
        act_clear.triggered.connect(lambda: self._clear_session_cart(sid))

        if self.session_tab_bar.count() > 1:
            act_close = menu.addAction(f"Fermer '{sdata.get('label', sid)}'")
            act_close.triggered.connect(lambda: self._close_session_by_id(sid))

        menu.exec(self.session_tab_bar.mapToGlobal(pos))

    def _sync_session_tabs(self) -> None:
        """Synchronizes the session tab bar with the active sessions dictionary."""
        if not hasattr(self, "session_tab_bar"):
            return
        self.session_tab_bar.blockSignals(True)
        while self.session_tab_bar.count() > 0:
            self.session_tab_bar.removeTab(0)
        target_idx = 0
        for idx, (sid, sdata) in enumerate(self._sessions.items()):
            scanner_tag = f" [{sdata['scanner_id']}]" if sdata.get("scanner_id") else ""
            cart_count = len(sdata.get("cart", []))
            count_tag = f" ({cart_count})" if cart_count > 0 else ""
            tab_pos = self.session_tab_bar.addTab(
                get_duotone_icon("barcode_scan", 14),
                f"{sdata['label']}{scanner_tag}{count_tag}",
            )
            self.session_tab_bar.setTabData(tab_pos, sid)
            if sid == self._active_session_id:
                target_idx = tab_pos
        self.session_tab_bar.setCurrentIndex(target_idx)
        self.session_tab_bar.blockSignals(False)
        self._update_tab_close_buttons()

    def _on_session_tab_switched(self, idx: int) -> None:
        if idx < 0 or not hasattr(self, "session_tab_bar") or idx >= self.session_tab_bar.count():
            return
        sid = self.session_tab_bar.tabData(idx)
        if not sid or sid not in self._sessions:
            return

        # Save previous session's delivery address
        if hasattr(self, "_active_session_id") and self._active_session_id in self._sessions:
            if hasattr(self, "txt_delivery_addr"):
                self._sessions[self._active_session_id]["delivery_address"] = self.txt_delivery_addr.text().strip()

        self._active_session_id = sid
        sdata = self._sessions[sid]
        self.lbl_cart_header.setText(f"Panier — {sdata['label']}")

        # Restore client selection
        if hasattr(self, "cbo_client"):
            cid = sdata.get("client_id", 1)
            c_idx = self.cbo_client.findData(cid)
            if c_idx >= 0:
                self.cbo_client.blockSignals(True)
                self.cbo_client.setCurrentIndex(c_idx)
                self.cbo_client.blockSignals(False)

        # Restore delivery address
        if hasattr(self, "txt_delivery_addr"):
            self.txt_delivery_addr.blockSignals(True)
            self.txt_delivery_addr.setText(sdata.get("delivery_address", ""))
            self.txt_delivery_addr.blockSignals(False)

        self._refresh_cart_ui()

    def _on_session_switched(self, idx: int) -> None:
        """Legacy compatibility wrapper forwarding to tab switch."""
        self._on_session_tab_switched(idx)

    def _on_session_tab_close_requested(self, index: int) -> None:
        if self.session_tab_bar.count() <= 1:
            QMessageBox.information(
                self,
                "Fermeture Impossible",
                "Vous devez conserver au moins une session active pour les commandes.",
            )
            return

        sid = self.session_tab_bar.tabData(index)
        sdata = self._sessions.get(sid)
        if not sdata:
            return

        if sdata.get("cart"):
            reply = QMessageBox.question(
                self,
                "Confirmer la fermeture",
                f"Le panier de '{sdata['label']}' contient des articles en cours.\n"
                "Voulez-vous vraiment fermer cette session et perdre son contenu ?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        if sdata.get("scanner_id"):
            self.hid_manager.unbind_scanner(sdata["scanner_id"])
        del self._sessions[sid]

        self.session_tab_bar.blockSignals(True)
        self.session_tab_bar.removeTab(index)
        self.session_tab_bar.blockSignals(False)

        new_idx = min(index, self.session_tab_bar.count() - 1)
        self.session_tab_bar.setCurrentIndex(new_idx)
        self._on_session_tab_switched(new_idx)
        self._update_tab_close_buttons()

    def _create_new_session(self, scanner_id: Optional[str] = None) -> str:
        self._session_counter += 1
        sid = f"SESSION_{self._session_counter}"
        while sid in self._sessions:
            self._session_counter += 1
            sid = f"SESSION_{self._session_counter}"

        label = f"Session Vente #{self._session_counter}"
        self._sessions[sid] = {
            "label": label,
            "scanner_id": scanner_id,
            "client_id": 1,
            "cart": [],
            "delivery_address": "",
        }
        if scanner_id:
            self.hid_manager.bind_scanner_to_session(scanner_id, sid)

        scanner_tag = f" [{scanner_id}]" if scanner_id else ""
        if hasattr(self, "session_tab_bar"):
            tab_idx = self.session_tab_bar.addTab(
                get_duotone_icon("barcode_scan", 14),
                f"{label}{scanner_tag}",
            )
            self.session_tab_bar.setTabData(tab_idx, sid)
            if scanner_id is None:
                self.session_tab_bar.setCurrentIndex(tab_idx)
            self._update_tab_close_buttons()

        return sid

    def _prompt_scanner_binding(self) -> None:
        sdata = self._sessions[self._active_session_id]
        curr_dev = sdata.get("scanner_id") or ""
        text, ok = QInputDialog.getText(
            self,
            "Association Scanner USB / HID",
            f"Identifiant matériel (hDevice / Handle) du lecteur pour {sdata['label']} :",
            text=curr_dev,
        )
        if ok and text.strip():
            new_dev = text.strip()
            if curr_dev:
                self.hid_manager.unbind_scanner(curr_dev)
            sdata["scanner_id"] = new_dev
            self.hid_manager.bind_scanner_to_session(new_dev, self._active_session_id)
            self._update_tab_label(self._active_session_id)
            self.lbl_scanner_status.setText(f"Scanner [{new_dev}] associé à {sdata['label']}")

    @property
    def cbo_session(self):
        """Compatibility adapter property providing legacy combobox interface to session tabs."""
        outer = self

        class _CboSessionAdapter:
            def currentIndex(self):
                return outer.session_tab_bar.currentIndex() if hasattr(outer, "session_tab_bar") else 0

            def itemData(self, idx):
                return outer.session_tab_bar.tabData(idx) if hasattr(outer, "session_tab_bar") else None

            def count(self):
                return outer.session_tab_bar.count() if hasattr(outer, "session_tab_bar") else 0

            def setCurrentIndex(self, idx):
                if hasattr(outer, "session_tab_bar"):
                    outer.session_tab_bar.setCurrentIndex(idx)

            def addItem(self, text, sid):
                if hasattr(outer, "session_tab_bar"):
                    t_idx = outer.session_tab_bar.addTab(get_duotone_icon("barcode_scan", 14), text)
                    outer.session_tab_bar.setTabData(t_idx, sid)

            def setItemText(self, idx, text):
                if hasattr(outer, "session_tab_bar") and 0 <= idx < outer.session_tab_bar.count():
                    outer.session_tab_bar.setTabText(idx, text)

        return _CboSessionAdapter()

    def _resolve_session_for_device(self, device_id: str) -> str:
        clean_dev = str(device_id).strip()

        # 1. Device already mapped in hid_manager to an existing session
        bound_sid = self.hid_manager.get_session_for_device(clean_dev)
        if bound_sid and bound_sid in self._sessions:
            return bound_sid

        # 2. Device recorded in _sessions
        for sid, sdata in self._sessions.items():
            if sdata.get("scanner_id") == clean_dev:
                self.hid_manager.bind_scanner_to_session(clean_dev, sid)
                return sid

        # 3. Check if there is an unassigned session (e.g. initial SESSION_1 waiting for its first device)
        for sid, sdata in self._sessions.items():
            if not sdata.get("scanner_id"):
                sdata["scanner_id"] = clean_dev
                self.hid_manager.bind_scanner_to_session(clean_dev, sid)
                self._update_tab_label(sid)
                self.lbl_scanner_status.setText(f"Scanner [{clean_dev}] associé à {sdata['label']}")
                return sid

        # 4. Brand new device (different from first device): automatically create new session (unlimited)
        new_sid = self._create_new_session(scanner_id=clean_dev)
        sdata = self._sessions[new_sid]
        self.lbl_scanner_status.setText(f"Nouvelle session créée pour le scanner [{clean_dev}]")
        return new_sid

    def _on_any_scanner_input(self, device_id: str, barcode: str, session_id: Optional[str] = None) -> None:
        """Entry point called by MultiScannerHIDManager when a complete barcode arrives."""
        from PySide6.QtCore import QThread
        if QThread.currentThread() == self.thread():
            self._process_scanned_barcode(str(device_id), str(barcode))
        else:
            self.scanDispatched.emit(str(device_id), str(barcode))

    def _process_scanned_barcode(self, device_id: str, barcode: str) -> None:
        """Main GUI thread barcode handler resolving device to session and adding product to cart."""
        target_sid = self._resolve_session_for_device(device_id)
        self._on_scanner_input_for_session(target_sid, device_id, barcode)

    def _find_product_by_barcode(self, barcode: str) -> Optional[Dict[str, Any]]:
        """
        Universal barcode resolver for Order Desk:
        Matches barcode against:
        - serial tracking manager (checking Products_Master, Inventory_Batches, Product_Serials)
        - catalog cache (with comma-separated barcode support and composite barcodes)
        - database catalog reload
        The barcode is strictly used for theoretical product recognition; no serial is locked in cart.
        """
        clean_bc = str(barcode or "").strip()
        if not clean_bc:
            return None

        # 1. Ask serial_tracking_manager if available
        if self.data_manager and hasattr(self.data_manager, "serials"):
            if hasattr(self.data_manager.serials, "find_product_by_any_barcode"):
                found = self.data_manager.serials.find_product_by_any_barcode(clean_bc)
                if found:
                    return found

        # 2. Check in-memory catalog cache
        for p in getattr(self, "_catalog_cache", []):
            p_bar = str(p.get("Barcode") or "").strip()
            bar_tokens = [t.strip() for t in p_bar.split(",") if t.strip()]
            if clean_bc in bar_tokens or p_bar == clean_bc or str(p.get("Product_ID")) == clean_bc:
                return p
            # Check composite serial format: e.g. "101::SERIAL"
            if "::" in clean_bc and clean_bc.split("::")[0] == str(p.get("Product_ID")):
                return p

        # 3. If cache was filtered, check if data_manager can reload without filter
        if self.data_manager and hasattr(self.data_manager, "serials"):
            full_items = self.data_manager.serials.get_catalog_with_theoretical_stock(search=clean_bc)
            if full_items:
                return full_items[0]

        return None

    def _on_search_return_pressed(self) -> None:
        """Handles enter key / scanner wedge in the search field to auto-add matched barcode product."""
        query = self.txt_search.text().strip()
        if not query:
            return
        matched_prod = self._find_product_by_barcode(query)
        if matched_prod:
            self._add_product_to_session(self._active_session_id, matched_prod)
            self.txt_search.blockSignals(True)
            self.txt_search.clear()
            self.txt_search.blockSignals(False)
            self.refresh_catalog()
            s_label = self._sessions.get(self._active_session_id, {}).get("label", "Session")
            self.lbl_scanner_status.setText(
                f"Code-barres identifié -> {s_label} : {matched_prod.get('Product_Name')} (Ajouté)"
            )
        else:
            self.refresh_catalog()

    def _on_scanner_input_for_session(self, session_id: str, device_id: str, barcode: str) -> None:
        """Routes a barcode scan directly into its bound session's cart without disturbing other sessions."""
        clean_bc = barcode.strip()
        matched_prod = self._find_product_by_barcode(clean_bc)

        if matched_prod:
            self._add_product_to_session(session_id, matched_prod)
            s_label = self._sessions.get(session_id, {}).get("label", session_id)
            self.lbl_scanner_status.setText(
                f"Scan [{device_id}] -> {s_label} : {matched_prod.get('Product_Name')} (Ajouté)"
            )
        else:
            self.lbl_scanner_status.setText(
                f"Scan [{device_id}] ({clean_bc}) : Référence introuvable dans le stock"
            )

    def _add_product_to_session(self, session_id: str, prod: Dict[str, Any]) -> None:
        if session_id not in self._sessions:
            return
        cart = self._sessions[session_id]["cart"]
        pid = int(prod["Product_ID"])
        avail = int(prod.get("Available_Theoretical_Qty") or 0)

        for item in cart:
            if item["product_id"] == pid:
                if item["quantity"] + 1 > avail:
                    QMessageBox.warning(
                        self,
                        "Stock Théorique Insuffisant",
                        f"La quantité demandée dépasse le stock disponible ({avail}).",
                    )
                    return
                item["quantity"] += 1
                if session_id == self._active_session_id:
                    self._refresh_cart_ui()
                self._update_tab_label(session_id)
                return

        if avail <= 0:
            QMessageBox.warning(self, "Rupture de Stock", "Ce produit n'a plus de stock théorique disponible.")
            return

        cart.append({
            "product_id": pid,
            "mark": str(prod.get("Brand_Mark") or ""),
            "name": str(prod.get("Product_Name") or ""),
            "coloure": str(prod.get("Color_Finish") or "Standard"),
            "unit_price_ttc": float(prod.get("Unit_Price_TTC") or 0.0),
            "quantity": 1,
            "max_avail": avail,
        })
        if session_id == self._active_session_id:
            self._refresh_cart_ui()
        self._update_tab_label(session_id)

    def _refresh_cart_ui(self) -> None:
        cart = self._sessions[self._active_session_id]["cart"]
        self.cart_table.setRowCount(0)
        total_ttc = 0.0

        for idx, item in enumerate(cart):
            row = self.cart_table.rowCount()
            self.cart_table.insertRow(row)
            line_tot = item["unit_price_ttc"] * item["quantity"]
            total_ttc += line_tot

            self.cart_table.setItem(row, 0, QTableWidgetItem(f"{item['mark']} {item['name']}".strip()))
            it_col = QTableWidgetItem(item["coloure"])
            it_col.setTextAlignment(Qt.AlignCenter)
            self.cart_table.setItem(row, 1, it_col)

            stepper = CartQtyStepper(
                qty=int(item["quantity"]),
                max_qty=int(item.get("max_avail") or 99),
            )
            stepper.qtyChanged.connect(lambda val, i=idx: self._update_line_qty(i, val))
            self.cart_table.setCellWidget(row, 2, stepper)

            it_tot = QTableWidgetItem(f"{format_money(line_tot)} DA")
            it_tot.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_tot.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self.cart_table.setItem(row, 3, it_tot)

        self.lbl_total.setText(f"{format_money(total_ttc)} DA")

    def _update_line_qty(self, index: int, new_qty: int) -> None:
        cart = self._sessions[self._active_session_id]["cart"]
        if 0 <= index < len(cart):
            if new_qty <= 0:
                del cart[index]
                self._refresh_cart_ui()
                self._update_tab_label(self._active_session_id)
                return
            cart[index]["quantity"] = int(new_qty)
            line_tot = cart[index]["unit_price_ttc"] * cart[index]["quantity"]
            it_tot = self.cart_table.item(index, 3)
            if it_tot:
                it_tot.setText(f"{format_money(line_tot)} DA")
            total_ttc = sum(it["unit_price_ttc"] * it["quantity"] for it in cart)
            self.lbl_total.setText(f"{format_money(total_ttc)} DA")
            self._update_tab_label(self._active_session_id)

    def _clear_current_cart(self) -> None:
        if self._active_session_id in self._sessions:
            self._sessions[self._active_session_id]["cart"] = []
            self._sessions[self._active_session_id]["delivery_address"] = ""
        if hasattr(self, "txt_delivery_addr"):
            self.txt_delivery_addr.clear()
        self._update_tab_label(self._active_session_id)
        self._refresh_cart_ui()

    # =========================================================================
    # ORDER SUBMISSION (Bon C, Bon Crédit, Bon de Livraison)
    # =========================================================================

    def _submit_order(self, bond_type: str) -> None:
        sdata = self._sessions[self._active_session_id]
        cart = sdata["cart"]
        if not cart:
            QMessageBox.warning(self, "Panier Vide", "Veuillez ajouter au moins un produit avant de créer le bon.")
            return

        client_id = int(self.cbo_client.currentData() or 1)
        user_id = 1
        if self.data_manager and getattr(self.data_manager, "current_user", None):
            user_id = int(
                self.data_manager.current_user.get("User_ID")
                or self.data_manager.current_user.get("id")
                or 1
            )

        payment_req_map = {
            "BON_C": "CASH",
            "BON_CREDIT": "CREDIT_APPROVAL_REQUIRED",
            "BON_LIVRAISON": "LIVRAISON_COD",
        }
        deliv_addr = sdata.get("delivery_address") or self.txt_delivery_addr.text().strip() or None

        try:
            if self.data_manager and hasattr(self.data_manager, "bonds"):
                res = self.data_manager.bonds.create_sales_order_draft(
                    client_id=client_id,
                    order_desk_user_id=user_id,
                    items=cart,
                    payment_method_requested=payment_req_map.get(bond_type, "CASH"),
                    bond_type=bond_type,
                    scanner_session_id=self._active_session_id,
                    delivery_address=deliv_addr,
                )
            else:
                total_val = sum(Decimal(str(i["unit_price_ttc"])) * int(i["quantity"]) for i in cart)
                res = {
                    "success": True,
                    "order_id": 900,
                    "order_number": f"{bond_type[:3]}-SIM-900",
                    "bond_type": bond_type,
                    "total_ttc": float(total_val),
                    "scanner_session_id": self._active_session_id,
                }

            order_num = res["order_number"]
            total_ttc = res["total_ttc"]

            if bond_type == "BON_C":
                self.bonCGenerated.emit(res)
                QMessageBox.information(
                    self,
                    "Bon Comptant Créé",
                    f"Bon Comptant ({order_num}) enregistré avec succès.\n"
                    f"Montant TTC : {format_money(total_ttc)} DA\n"
                    "Le client peut se présenter au Bureau Caisse pour validation.",
                )
            elif bond_type == "BON_CREDIT":
                self.bonCreditRequested.emit(res)
                QMessageBox.information(
                    self,
                    "Demande Bon Crédit",
                    f"Bon Crédit ({order_num}) transmis au Bureau Caisse.\n"
                    f"Montant TTC : {format_money(total_ttc)} DA\n"
                    "Nécessite l'autorisation d'un Administrateur en Caisse.",
                )
            elif bond_type == "BON_LIVRAISON":
                self.bonLivraisonGenerated.emit(res)
                QMessageBox.information(
                    self,
                    "Bon de Livraison Créé",
                    f"Bon de Livraison ({order_num}) enregistré.\n"
                    f"Montant TTC : {format_money(total_ttc)} DA\n"
                    "Transmis en Caisse pour enregistrement d'acompte éventuel avant expédition.",
                )

            self._clear_current_cart()
            self.txt_delivery_addr.clear()
            self.refresh_catalog()
        except Exception as err:
            QMessageBox.critical(self, "Erreur Création Bon", f"Impossible de créer le bon :\n{err}")
