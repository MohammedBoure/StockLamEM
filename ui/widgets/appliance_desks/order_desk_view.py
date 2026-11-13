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

import logging
import os
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import QEvent, QObject, QPoint, QSettings, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
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
from .bon_pdf_export import export_order_bon_to_pdf
from .order_bons_dialog import OrderDeskBonsDialog

from ui.formatting import format_money, format_quantity
from ui.hardware.raw_input_filter import MultiScannerHIDManager
from ui.icons import get_duotone_icon, get_trash_icon

try:
    import qtawesome as qta
except ImportError:
    qta = None


logger = logging.getLogger("StockLamPlus.OrderDesk")


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
        self.swatch.setFixedSize(14, 14)
        border_col = "#94A3B8" if self.hex_code.upper() in ("#FFFFFF", "#FDFBF7", "#F5F5DC", "#F1F5F9") else "rgba(0,0,0,0.3)"
        self.swatch.setStyleSheet(
            f"background-color: {self.hex_code}; border: 1.5px solid {border_col}; border-radius: 7px;"
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


class ColorFilterBadge(QFrame):
    """
    Vibrant live preview pill badge for the active color filter in Order Desk:
    - Multi-color gradient dot when 'Tous' is selected
    - Direct antialiased color dot with border when a specific color is chosen
    - Responsive color name label and rich tooltips with hex codes
    - Interactive click to quickly reset or toggle color filter
    """

    clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("ColorFilterBadge")
        self.setFixedHeight(34)
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignCenter)

        self.dot = QFrame()
        self.dot.setFixedSize(14, 14)
        layout.addWidget(self.dot)

        self.lbl_text = QLabel("Toutes")
        self.lbl_text.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: #475569; background: transparent; border: none;"
        )
        layout.addWidget(self.lbl_text)

        self.update_color("Tous", "")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def update_color(self, name: str, hex_code: str = "") -> None:
        clean_name = str(name or "Tous").strip()
        if not clean_name or clean_name.lower() in ("tous", "all", "toutes", "toutes les couleurs"):
            self.dot.setStyleSheet(
                "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
                "stop:0 #007572, stop:0.35 #2563EB, stop:0.7 #DC2626, stop:1 #D97706); "
                "border-radius: 7px; border: 1px solid rgba(0,0,0,0.25);"
            )
            self.lbl_text.setText("Toutes")
            self.lbl_text.setStyleSheet(
                "font-size: 11px; font-weight: 700; color: #475569; background: transparent; border: none;"
            )
            self.setStyleSheet("""
                QFrame#ColorFilterBadge {
                    background-color: #F8FAFC;
                    border: 1.5px solid #CBD5E1;
                    border-radius: 6px;
                }
                QFrame#ColorFilterBadge:hover {
                    background-color: #F1F5F9;
                    border-color: #94A3B8;
                }
            """)
            self.setToolTip("Couleurs : Toutes les finitions sont affichées (cliquez pour choisir)")
        else:
            actual_hex = hex_code or get_color_hex(clean_name)
            border = "#94A3B8" if actual_hex.upper() in ("#FFFFFF", "#FDFBF7", "#F5F5DC") else "rgba(0,0,0,0.3)"
            self.dot.setStyleSheet(
                f"background-color: {actual_hex}; border-radius: 7px; border: 1.2px solid {border};"
            )
            self.lbl_text.setText(clean_name)
            self.lbl_text.setStyleSheet(
                "font-size: 11px; font-weight: 800; color: #007572; background: transparent; border: none;"
            )
            self.setStyleSheet("""
                QFrame#ColorFilterBadge {
                    background-color: #F0FDFA;
                    border: 1.5px solid #007572;
                    border-radius: 6px;
                }
                QFrame#ColorFilterBadge:hover {
                    background-color: #CCFBF1;
                    border-color: #0A5C59;
                }
            """)
            self.setToolTip(f"Filtre actif : {clean_name} ({actual_hex})\nCliquez pour réinitialiser sur 'Toutes'")


class ProductPriceWidget(QWidget):
    """
    Renders only the primary price in the catalog table with an interactive dropdown menu:
    - Displays only the first price (Prix 1 - Détail / Comptoir) in the cell, eliminating visual overlap.
    - Features a clean dropdown chevron indicator (▾).
    - Clicking opens a styled dropdown menu (QMenu) presenting all 3 pricing tiers.
    - Selecting an alternative tier dynamically updates the displayed price and passes it to cart addition.
    """
    priceTierSelected = Signal(str, float)

    def __init__(
        self,
        p1: float,
        p2: float,
        p3: float,
        prod_ref: Optional[Dict[str, Any]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.p1 = float(p1 or 0.0)
        self.p2 = float(p2 or (self.p1 * 0.95))
        self.p3 = float(p3 or (self.p1 * 0.90))
        self.prod_ref = prod_ref
        self.selected_tier = "Prix_1"
        self.current_price = self.p1

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignCenter)

        # Single interactive button displaying only the primary price + dropdown arrow
        self.btn_price = QPushButton()
        self.btn_price.setObjectName("BtnPriceDropdown")
        self.btn_price.setCursor(Qt.PointingHandCursor)
        self.btn_price.setFixedHeight(28)
        self.btn_price.setStyleSheet("""
            QPushButton#BtnPriceDropdown {
                background-color: #FFFFFF;
                color: #007572;
                border: 1.5px solid #CED4DA;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: bold;
                text-align: center;
            }
            QPushButton#BtnPriceDropdown:hover {
                background-color: #E8F8F5;
                border-color: #007572;
                color: #005A57;
            }
            QPushButton#BtnPriceDropdown:pressed {
                background-color: #CCEBE5;
            }
        """)

        # Label references for backwards compatibility
        self.lbl_p1 = QLabel(f"{format_money(self.p1)} DA")
        self.lbl_sub = QLabel(f"DG: {format_money(self.p2)} • G: {format_money(self.p3)}")
        self.lbl_sub.setVisible(False)

        self._update_button_label()
        self.btn_price.clicked.connect(self._show_price_menu)
        layout.addWidget(self.btn_price)

        self._setup_tooltip()

    def _update_button_label(self) -> None:
        tier_tag = ""
        if self.selected_tier == "Prix_2":
            tier_tag = " [DG]"
        elif self.selected_tier == "Prix_3":
            tier_tag = " [G]"
        self.btn_price.setText(f"{format_money(self.current_price)} DA{tier_tag}  ▾")
        self.lbl_p1.setText(f"{format_money(self.current_price)} DA")

    def _setup_tooltip(self) -> None:
        tt = (
            f"Grille Tarifaire du Produit (TTC) :\n"
            f"• Prix 1 (Détail / Comptoir) : {format_money(self.p1)} DA\n"
            f"• Prix 2 (Demi-Gros / Revendeur) : {format_money(self.p2)} DA\n"
            f"• Prix 3 (Grossiste B2B) : {format_money(self.p3)} DA\n"
            f"(Cliquez pour afficher la liste déroulante des prix)"
        )
        self.setToolTip(tt)
        self.btn_price.setToolTip(tt)

    def _show_price_menu(self) -> None:
        """Displays the dropdown menu listing all available price tiers upon click."""
        menu = QMenu(self)
        menu.setObjectName("PriceTierMenu")
        menu.setStyleSheet("""
            QMenu#PriceTierMenu {
                background-color: #FFFFFF;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                padding: 4px;
                font-size: 11px;
            }
            QMenu#PriceTierMenu::item {
                padding: 6px 14px;
                border-radius: 4px;
                color: #2C3E50;
                font-weight: 600;
            }
            QMenu#PriceTierMenu::item:selected {
                background-color: #E6F4F1;
                color: #007572;
                font-weight: bold;
            }
            QMenu#PriceTierMenu::separator {
                height: 1px;
                background-color: #E2E8F0;
                margin: 4px 6px;
            }
        """)

        header_act = menu.addAction("Tarifs Disponibles (TTC) :")
        header_act.setEnabled(False)
        menu.addSeparator()

        prefix1 = "✔ " if self.selected_tier == "Prix_1" else "   "
        act1 = menu.addAction(f"{prefix1}Prix 1 (Détail / Comptoir) : {format_money(self.p1)} DA")
        act1.triggered.connect(lambda: self._select_tier("Prix_1", self.p1))

        prefix2 = "✔ " if self.selected_tier == "Prix_2" else "   "
        act2 = menu.addAction(f"{prefix2}Prix 2 (Demi-Gros) : {format_money(self.p2)} DA")
        act2.triggered.connect(lambda: self._select_tier("Prix_2", self.p2))

        prefix3 = "✔ " if self.selected_tier == "Prix_3" else "   "
        act3 = menu.addAction(f"{prefix3}Prix 3 (Grossiste B2B) : {format_money(self.p3)} DA")
        act3.triggered.connect(lambda: self._select_tier("Prix_3", self.p3))

        pos = self.btn_price.mapToGlobal(QPoint(0, self.btn_price.height()))
        menu.exec_(pos)

    def _select_tier(self, tier: str, price: float) -> None:
        self.selected_tier = tier
        self.current_price = price
        self._update_button_label()
        if self.prod_ref is not None:
            self.prod_ref["selected_price_tier"] = tier
            self.prod_ref["selected_price_ttc"] = price
        self.priceTierSelected.emit(tier, price)


class AddActionCellWidget(QWidget):
    """
    Renders the add action in its own framed slot:
    - Dedicated slot frame border (QFrame#AddActionSlot)
    - Borderless '+' button centered inside (no border around the button itself)
    - Hover highlights the slot in brand teal
    - Clicking the '+' button or slot frame adds product to active cart session
    """

    def __init__(self, on_add_callback, is_available: bool = True, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.on_add_callback = on_add_callback
        self.is_available = is_available

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter)

        # The framed slot container
        self.slot_frame = QFrame()
        self.slot_frame.setObjectName("AddActionSlot")
        self.slot_frame.setFixedSize(38, 30)
        slot_layout = QHBoxLayout(self.slot_frame)
        slot_layout.setContentsMargins(0, 0, 0, 0)
        slot_layout.setAlignment(Qt.AlignCenter)

        self.btn_add = QPushButton("+")
        self.btn_add.setObjectName("BtnPlusOnly")
        self.btn_add.setFixedSize(34, 26)

        if is_available:
            self.slot_frame.setCursor(Qt.PointingHandCursor)
            self.btn_add.setCursor(Qt.PointingHandCursor)
            self.slot_frame.setStyleSheet("""
                QFrame#AddActionSlot {
                    background-color: #FFFFFF;
                    border: 1.5px solid #CED4DA;
                    border-radius: 4px;
                }
                QFrame#AddActionSlot:hover {
                    background-color: #E8F8F5;
                    border-color: #007572;
                }
            """)
            self.btn_add.setStyleSheet("""
                QPushButton#BtnPlusOnly {
                    background: transparent;
                    border: none;
                    color: #007572;
                    font-size: 17px;
                    font-weight: bold;
                    padding: 0;
                    margin: 0;
                }
                QPushButton#BtnPlusOnly:hover {
                    color: #005A57;
                }
                QPushButton#BtnPlusOnly:pressed {
                    color: #003D3A;
                }
            """)
            self.btn_add.clicked.connect(self._trigger_add)
            self.setToolTip("Ajouter au panier (+)")
            self.btn_add.setToolTip("Ajouter au panier (+)")
        else:
            self.btn_add.setText("—")
            self.btn_add.setEnabled(False)
            self.slot_frame.setStyleSheet("""
                QFrame#AddActionSlot {
                    background-color: #F8FAFC;
                    border: 1px solid #E2E8F0;
                    border-radius: 4px;
                }
            """)
            self.btn_add.setStyleSheet("""
                QPushButton#BtnPlusOnly {
                    background: transparent;
                    border: none;
                    color: #94A3B8;
                    font-size: 14px;
                    font-weight: bold;
                    padding: 0;
                    margin: 0;
                }
            """)
            self.setToolTip("Épuisé — Rupture de stock")
            self.btn_add.setToolTip("Épuisé — Rupture de stock")

        slot_layout.addWidget(self.btn_add)
        layout.addWidget(self.slot_frame)

    def mousePressEvent(self, event):
        if self.is_available and event.button() == Qt.LeftButton:
            self._trigger_add()
        super().mousePressEvent(event)

    def _trigger_add(self):
        if self.is_available and callable(self.on_add_callback):
            self.on_add_callback()


class CartRemoveCellWidget(QWidget):
    """
    Action slot widget rendering an elegant, compact delete button with vector trash icon:
    - Zero vertical clipping inside the cart row.
    - Soft red hover effect (#FEE2E2 / #F87171) for clear tactile feedback.
    - Tooltip: 'Supprimer cet article de la commande'.
    - Pointing hand cursor.
    """

    def __init__(self, on_remove: Optional[Callable[[], None]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.on_remove = on_remove

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignCenter)

        self.btn_delete = QPushButton()
        self.btn_delete.setObjectName("BtnCartRemove")
        self.btn_delete.setFixedSize(26, 26)
        self.btn_delete.setCursor(Qt.PointingHandCursor)
        self.btn_delete.setIcon(get_trash_icon(14))
        self.btn_delete.setIconSize(QSize(14, 14))
        self.btn_delete.setToolTip("Supprimer cet article de la commande")
        self.btn_delete.setStyleSheet("""
            QPushButton#BtnCartRemove {
                background-color: #FFFFFF;
                color: #C0392B;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                padding: 0;
            }
            QPushButton#BtnCartRemove:hover {
                background-color: #FDF2F2;
                border-color: #C0392B;
            }
            QPushButton#BtnCartRemove:pressed {
                background-color: #FCE8E6;
            }
        """)
        self.btn_delete.clicked.connect(self._trigger_remove)
        layout.addWidget(self.btn_delete)

    def _trigger_remove(self) -> None:
        if callable(self.on_remove):
            self.on_remove()


TABLE_STYLE = """
    QTableWidget {
        background-color: #FFFFFF;
        border: 1px solid #DCDFE6;
        border-radius: 4px;
        gridline-color: #F1F5F9;
        selection-background-color: #E6F4F1;
        selection-color: #007572;
        alternate-background-color: #F8FAFC;
        font-size: 12px;
        color: #2C3E50;
    }
    QHeaderView::section {
        background-color: #F8FAFC;
        color: #2C3E50;
        font-weight: bold;
        font-size: 12px;
        padding: 5px 6px;
        border: none;
        border-bottom: 2px solid #007572;
        border-right: 1px solid #E2E8F0;
    }
    QScrollBar:horizontal {
        border: none;
        background: #F1F5F9;
        height: 7px;
        margin: 0px;
        border-radius: 3px;
    }
    QScrollBar::handle:horizontal {
        background: #007572;
        min-width: 35px;
        border-radius: 3px;
    }
    QScrollBar::handle:horizontal:hover {
        background: #005A57;
    }
    QScrollBar::handle:horizontal:pressed {
        background: #003D3A;
    }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        width: 0px;
        height: 0px;
        background: none;
        border: none;
    }
    QScrollBar:vertical {
        border: none;
        background: #F1F5F9;
        width: 7px;
        margin: 0px;
        border-radius: 3px;
    }
    QScrollBar::handle:vertical {
        background: #007572;
        min-height: 35px;
        border-radius: 3px;
    }
    QScrollBar::handle:vertical:hover {
        background: #005A57;
    }
    QScrollBar::handle:vertical:pressed {
        background: #003D3A;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        width: 0px;
        height: 0px;
        background: none;
        border: none;
    }
"""

PRIMARY_BTN_STYLE = """
    QPushButton {
        background-color: #007572;
        color: #FFFFFF;
        font-weight: bold;
        min-height: 28px;
        padding: 4px 10px;
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
        border: 1px solid #007572;
        font-weight: bold;
        min-height: 28px;
        padding: 4px 12px;
        border-radius: 4px;
        font-size: 12px;
    }
    QPushButton:hover { background-color: #E8F8F5; border-color: #005A57; color: #005A57; }
    QPushButton:pressed { background-color: #CCEBE5; }
    QPushButton:disabled { background-color: #F8FAFC; color: #94A3B8; border-color: #CED4DA; }
"""

DANGER_BTN_STYLE = """
    QPushButton {
        background-color: #FFFFFF;
        color: #C0392B;
        border: 1px solid #CED4DA;
        border-radius: 4px;
        padding: 2px 10px;
        font-size: 11px;
        font-weight: bold;
        min-height: 28px;
    }
    QPushButton:hover {
        background-color: #FDF2F2;
        border-color: #C0392B;
        color: #962D22;
    }
    QPushButton:pressed {
        background-color: #FCE8E6;
    }
"""

SLATE_OUTLINE_BTN_STYLE = """
    QPushButton {
        background-color: #FFFFFF;
        color: #495057;
        border: 1px solid #CED4DA;
        font-weight: bold;
        min-height: 28px;
        padding: 4px 10px;
        border-radius: 4px;
        font-size: 12px;
    }
    QPushButton:hover { background-color: #F8FAFC; border-color: #ADB5BD; color: #212529; }
    QPushButton:pressed { background-color: #E9ECEF; }
    QPushButton:disabled { background-color: #F8FAFC; color: #94A3B8; border-color: #CED4DA; }
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
                background-color: #FFFFFF;
                color: #495057;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #F8FAFC;
                color: #212529;
                border-color: #ADB5BD;
            }
            QPushButton:pressed {
                background-color: #E9ECEF;
            }
        """)
        self.btn_minus.clicked.connect(self._decrement)
        layout.addWidget(self.btn_minus)

        self.lbl_qty = QLabel(str(self._qty))
        self.lbl_qty.setFixedWidth(24)
        self.lbl_qty.setAlignment(Qt.AlignCenter)
        self.lbl_qty.setStyleSheet(
            "font-size: 12px; font-weight: bold; color: #2C3E50; background: transparent; border: none;"
        )
        layout.addWidget(self.lbl_qty)

        self.btn_plus = QPushButton("+")
        self.btn_plus.setFixedSize(22, 22)
        self.btn_plus.setCursor(Qt.PointingHandCursor)
        self.btn_plus.setStyleSheet("""
            QPushButton {
                background-color: #E8F8F5;
                color: #007572;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #A3E4D7;
                border-radius: 4px;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #CCEBE5;
                border-color: #007572;
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
        self._catalog_filtered_items: List[Dict[str, Any]] = []
        self._catalog_loaded_count: int = 0
        self._catalog_chunk_size: int = 35
        self._is_loading_chunk: bool = False

        # Connect global listener to automatically route all hardware scanner inputs
        self.scanDispatched.connect(self._process_scanned_barcode)
        self.hid_manager.register_global_callback(self._on_any_scanner_input)

        self._init_ui()
        self.refresh_catalog()

    def _init_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 0. Automatic Horizontal Scroll Area ensuring responsive horizontal adaptability
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("OrderDeskScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea#OrderDeskScrollArea {
                background: #FFFFFF;
                border: none;
            }
            QWidget#OrderDeskContentWidget {
                background-color: #FFFFFF;
            }
        """)

        content_widget = QWidget()
        content_widget.setObjectName("OrderDeskContentWidget")
        content_widget.setMinimumWidth(1080)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 6, 10, 8)
        content_layout.setSpacing(6)

        # 1. Top Session Tabs Bar (Ultra-compact low profile)
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
        self.catalog_panel.setMinimumWidth(550)
        self.cart_panel.setMinimumWidth(320)
        self.splitter.addWidget(self.catalog_panel)
        self.splitter.addWidget(self.cart_panel)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self._restore_splitter_state()
        self.splitter.splitterMoved.connect(self._save_splitter_state)
        self.splitter.splitterMoved.connect(lambda: self._adjust_catalog_column_widths())
        self.splitter.splitterMoved.connect(lambda: self._adjust_cart_column_widths())
        content_layout.addWidget(self.splitter, 1)

        self.scroll_area.setWidget(content_widget)
        root_layout.addWidget(self.scroll_area)

    def _create_session_tabs_bar(self) -> QWidget:
        session_bar = QWidget()
        session_bar.setObjectName("SessionTabsBar")
        session_bar.setFixedHeight(26)
        session_bar.setStyleSheet("""
            QWidget#SessionTabsBar {
                background: transparent;
                border: none;
            }
            QTabBar#SessionTabBar {
                border-bottom: 1.5px solid #DCDFE6;
            }
            QTabBar#SessionTabBar::tab {
                background-color: #F8FAFC;
                color: #495057;
                font-weight: bold;
                font-size: 11px;
                padding: 2px 24px 2px 10px;
                margin-right: 0px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                border: 1px solid #CED4DA;
                border-bottom: none;
                height: 22px;
                min-height: 22px;
                max-height: 22px;
            }
            QTabBar#SessionTabBar::tab:selected {
                background-color: #007572;
                color: #FFFFFF;
                border: 1px solid #007572;
                border-bottom: 2px solid #007572;
            }
            QTabBar#SessionTabBar::tab:hover:!selected {
                background-color: #E9ECEF;
                color: #212529;
                border-color: #ADB5BD;
            }
        """)
        sb_layout = QHBoxLayout(session_bar)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        sb_layout.setSpacing(6)

        # Specialized Connected Session Tabs (Ultra-compact low profile)
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

        # "+ Nouvelle Session" Button (Clean text without duplicate '+' icon)
        btn_new_sess = QPushButton("+ Nouvelle Session")
        btn_new_sess.setCursor(Qt.PointingHandCursor)
        btn_new_sess.setFixedHeight(22)
        btn_new_sess.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #007572;
                font-weight: bold;
                font-size: 11px;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                padding: 0 10px;
                height: 22px;
                min-height: 22px;
                max-height: 22px;
            }
            QPushButton:hover {
                background-color: #E8F8F5;
                border-color: #007572;
            }
            QPushButton:pressed {
                background-color: #CCEBE5;
            }
        """)
        btn_new_sess.clicked.connect(lambda: self._create_new_session())
        sb_layout.addWidget(btn_new_sess)

        self.btn_bind_scanner = QPushButton("🔗 Scanner")
        self.btn_bind_scanner.setCursor(Qt.PointingHandCursor)
        self.btn_bind_scanner.setFixedHeight(22)
        self.btn_bind_scanner.setToolTip("Associer un lecteur code-barres libre à la session active")
        self.btn_bind_scanner.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #475569;
                font-weight: bold;
                font-size: 11px;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                padding: 0 8px;
                height: 22px;
                min-height: 22px;
                max-height: 22px;
            }
            QPushButton:hover {
                background-color: #E8F8F5;
                color: #007572;
                border-color: #007572;
            }
        """)
        self.btn_bind_scanner.clicked.connect(lambda: self._prompt_scanner_binding())
        sb_layout.addWidget(self.btn_bind_scanner)

        sb_layout.addStretch()

        # Invisible label placeholder to retain programmatic compatibility without displaying unwanted text
        self.lbl_scanner_status = QLabel("")
        self.lbl_scanner_status.setVisible(False)
        sb_layout.addWidget(self.lbl_scanner_status)

        return session_bar

    def _create_top_filter_bar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("OrderTopFilterBar")
        panel.setFixedHeight(54)
        panel.setStyleSheet("""
            QFrame#OrderTopFilterBar {
                background-color: #FFFFFF;
                border: 1px solid #DCDFE6;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
                font-size: 12px;
                color: #2C3E50;
            }
            QComboBox {
                background-color: #FFFFFF;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                padding: 2px 8px;
                min-height: 28px;
                height: 28px;
                font-size: 12px;
                color: #2C3E50;
            }
            QComboBox:hover {
                border-color: #ADB5BD;
            }
            QComboBox:focus {
                border: 1.5px solid #007572;
                background-color: #FFFFFF;
            }
            QComboBox::drop-down {
                border: none;
                width: 18px;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                selection-background-color: #E6F4F1;
                selection-color: #007572;
                padding: 4px;
                font-size: 12px;
                color: #2C3E50;
            }
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                padding: 2px 8px;
                min-height: 28px;
                height: 28px;
                font-size: 12px;
                color: #2C3E50;
            }
            QLineEdit:hover {
                border-color: #ADB5BD;
            }
            QLineEdit:focus {
                border: 1.5px solid #007572;
                background-color: #FFFFFF;
            }
        """)
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        # 1. Subtle Filter Icon (Compact - Task #6: no space-wasting text badge)
        f_icon = QLabel()
        if qta:
            f_icon.setPixmap(qta.icon("fa5s.filter", color="#007572").pixmap(14, 14))
        else:
            f_icon.setPixmap(get_duotone_icon("filter", 14).pixmap(14, 14))
        f_icon.setToolTip("Filtres du catalogue")
        layout.addWidget(f_icon)

        # Retain filter_badge for compatibility without adding it to the visible line layout
        self.filter_badge = QFrame()
        self.filter_badge.setVisible(False)

        def make_filter_lbl(txt: str, icon_name: str = "", fallback_icon: str = "") -> QWidget:
            lbl = QLabel(txt)
            lbl.setStyleSheet("font-size: 12px; font-weight: 700; color: #334155; background: transparent; border: none;")
            return lbl

        # 2. Marque Filter
        layout.addWidget(make_filter_lbl("Marque :", "fa5s.tag", "filter"))
        self.cbo_mark = QComboBox()
        self.cbo_mark.setFixedHeight(32)
        self.cbo_mark.setMinimumWidth(110)
        self.populate_manufacturers()
        self.cbo_mark.currentIndexChanged.connect(self.refresh_catalog)
        layout.addWidget(self.cbo_mark)

        # 3. Catégorie Filter
        layout.addWidget(make_filter_lbl("Catégorie :", "fa5s.th-large", "filter"))
        self.cbo_category = QComboBox()
        self.cbo_category.setFixedHeight(32)
        self.cbo_category.setMinimumWidth(145)
        self.populate_families()
        self.cbo_category.currentIndexChanged.connect(self.refresh_catalog)
        layout.addWidget(self.cbo_category)

        # 4. Vibrant Couleur Filter with Swatches (Task #6: removed redundant 'Toutes' pill button)
        layout.addWidget(make_filter_lbl("Couleur :", "fa5s.palette", "filter"))
        self.cbo_color = QComboBox()
        self.cbo_color.setFixedHeight(32)
        self.cbo_color.setFixedWidth(115)
        self.cbo_color.setIconSize(QSize(14, 14))
        self._load_colors_into_combo()
        self.cbo_color.currentIndexChanged.connect(self._on_color_filter_changed)
        layout.addWidget(self.cbo_color)

        # Hidden color_preview_badge kept for backend and test compatibility
        self.color_preview_badge = ColorFilterBadge()
        self.color_preview_badge.setVisible(False)
        self.color_preview_badge.clicked.connect(self._on_color_badge_clicked)
        self._update_color_filter_swatch()

        # 5. Disponibles Uniquement Filter (Task #6: simplified and shortened text to 'En stock')
        self.chk_available_only = QCheckBox("En stock")
        self.chk_available_only.setObjectName("ChkAvailableOnly")
        self.chk_available_only.setChecked(True)
        self.chk_available_only.setFixedHeight(32)
        self.chk_available_only.setCursor(Qt.PointingHandCursor)
        self.chk_available_only.setToolTip(
            "Afficher uniquement les produits en stock (disponibles immédiatement)"
        )
        self.chk_available_only.setStyleSheet("""
            QCheckBox#ChkAvailableOnly {
                color: #2C3E50;
                font-size: 12px;
                font-weight: bold;
                spacing: 7px;
                background-color: #FFFFFF;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                padding: 0 10px;
            }
            QCheckBox#ChkAvailableOnly:hover {
                border-color: #ADB5BD;
                background-color: #F8FAFC;
            }
            QCheckBox#ChkAvailableOnly:checked {
                color: #007572;
                background-color: #E8F8F5;
                border: 1px solid #A3E4D7;
            }
            QCheckBox#ChkAvailableOnly::indicator {
                width: 15px;
                height: 15px;
                border-radius: 3px;
                border: 1.5px solid #CED4DA;
                background-color: #FFFFFF;
            }
            QCheckBox#ChkAvailableOnly::indicator:hover {
                border-color: #007572;
            }
            QCheckBox#ChkAvailableOnly::indicator:checked {
                background-color: #007572;
                border-color: #007572;
            }
        """)
        self.chk_available_only.toggled.connect(self._on_available_only_toggled)
        self.btn_available_only = self.chk_available_only  # Convenient alias
        self.chk_available_only.setVisible(False)
        layout.addWidget(self.chk_available_only)

        # 6. Search Bar with Instant Clear
        self.txt_search = QLineEdit()
        self.txt_search.setFixedHeight(32)
        self.txt_search.setMinimumWidth(160)
        self.txt_search.setPlaceholderText("Rechercher désignation, marque, réf, code-barres...")
        self.txt_search.setClearButtonEnabled(True)
        if qta:
            self.txt_search.addAction(qta.icon("fa5s.search", color="#94A3B8"), QLineEdit.LeadingPosition)
        self.txt_search.textChanged.connect(self.refresh_catalog)
        self.txt_search.returnPressed.connect(self._on_search_return_pressed)
        layout.addWidget(self.txt_search, 1)

        # Retain lbl_catalog_count_badge for testing and metrics without displaying it on the filter line (Task #6)
        self.lbl_catalog_count_badge = QLabel("0 produit")
        self.lbl_catalog_count_badge.setVisible(False)

        # 7. Action Icon Buttons (Task #6: compact icon buttons saving maximum horizontal space)
        btn_reset = QPushButton("")
        btn_reset.setObjectName("BtnResetFilter")
        if qta:
            btn_reset.setIcon(qta.icon("fa5s.undo", color="#495057"))
        else:
            btn_reset.setIcon(get_duotone_icon("return_arrow", 14))
        btn_reset.setIconSize(QSize(14, 14))
        btn_reset.setCursor(Qt.PointingHandCursor)
        btn_reset.setFixedSize(32, 32)
        btn_reset.setStyleSheet("""
            QPushButton#BtnResetFilter {
                background-color: #FFFFFF;
                color: #495057;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                padding: 0px;
            }
            QPushButton#BtnResetFilter:hover {
                background-color: #F8FAFC;
                border-color: #ADB5BD;
            }
            QPushButton#BtnResetFilter:pressed {
                background-color: #E2E8F0;
            }
        """)
        btn_reset.setToolTip("Réinitialiser tous les filtres de recherche")
        btn_reset.clicked.connect(self._reset_filters)
        self.btn_reset = btn_reset
        layout.addWidget(btn_reset)

        btn_refresh = QPushButton("")
        btn_refresh.setObjectName("BtnRefreshCatalog")
        if qta:
            btn_refresh.setIcon(qta.icon("fa5s.sync-alt", color="#FFFFFF"))
        else:
            btn_refresh.setIcon(get_duotone_icon("refresh_white", 14))
        btn_refresh.setIconSize(QSize(14, 14))
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setFixedSize(32, 32)
        btn_refresh.setStyleSheet("""
            QPushButton#BtnRefreshCatalog {
                background-color: #007572;
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                padding: 0px;
            }
            QPushButton#BtnRefreshCatalog:hover {
                background-color: #005A57;
            }
            QPushButton#BtnRefreshCatalog:pressed {
                background-color: #004543;
            }
        """)
        btn_refresh.setToolTip("Actualiser / Recharger le catalogue")
        btn_refresh.clicked.connect(self.refresh_catalog)
        self.btn_refresh = btn_refresh
        layout.addWidget(btn_refresh)

        return panel

    def _adjust_combo_view_width(self, combo: QComboBox) -> None:
        """Expands dropdown popup width to comfortably fit the longest item without truncation."""
        if not combo:
            return
        width = combo.width()
        fm = combo.fontMetrics()
        for i in range(combo.count()):
            text_width = fm.horizontalAdvance(combo.itemText(i)) + 35
            if text_width > width:
                width = text_width
        if combo.view():
            combo.view().setMinimumWidth(max(width, combo.minimumWidth()))

    def populate_manufacturers(self) -> None:
        """Populates the Marque combobox dynamically from database manufacturers and catalog items, matching Stock & Magasin."""
        if not hasattr(self, "cbo_mark") or not self.cbo_mark:
            return
        curr_text = self.cbo_mark.currentText()
        self.cbo_mark.blockSignals(True)
        self.cbo_mark.clear()
        self.cbo_mark.addItem("Tous", None)

        marques = set()
        # 1. From data_manager.manufacturers
        if self.data_manager and hasattr(self.data_manager, "manufacturers"):
            try:
                for m in self.data_manager.manufacturers.get_all_manufacturers():
                    m_name = (m.get("Manuf_Name") or "").strip()
                    if m_name:
                        marques.add(m_name)
            except Exception as e:
                logger.debug(f"Could not load manufacturers from manager: {e}")

        # 2. From _catalog_cache
        if hasattr(self, "_catalog_cache") and self._catalog_cache:
            for item in self._catalog_cache:
                m_name = (item.get("Brand_Mark") or "").strip()
                if m_name and m_name.lower() not in ("générique", "generique", "tous", "all"):
                    marques.add(m_name)

        if not marques:
            marques.update(["Bosch", "Samsung", "LG", "Brandt", "Condor", "Cristor", "Midea", "Moulinex"])

        for m_name in sorted(list(marques), key=lambda s: s.lower()):
            self.cbo_mark.addItem(m_name, m_name)

        idx = self.cbo_mark.findText(curr_text)
        if idx >= 0:
            self.cbo_mark.setCurrentIndex(idx)
        else:
            self.cbo_mark.setCurrentIndex(0)

        self._adjust_combo_view_width(self.cbo_mark)
        self.cbo_mark.blockSignals(False)

    def populate_families(self) -> None:
        """Populates the Catégorie / Famille combobox dynamically from database families and catalog items, matching Stock & Magasin."""
        if not hasattr(self, "cbo_category") or not self.cbo_category:
            return
        curr_text = self.cbo_category.currentText()
        self.cbo_category.blockSignals(True)
        self.cbo_category.clear()
        self.cbo_category.addItem("Tous", None)

        families = set()
        # 1. From data_manager.families
        if self.data_manager and hasattr(self.data_manager, "families"):
            try:
                for f in self.data_manager.families.get_all_families():
                    f_name = (f.get("Family_Name") or "").strip()
                    if f_name:
                        families.add(f_name)
            except Exception as e:
                logger.debug(f"Could not load families from manager: {e}")

        # 2. From _catalog_cache
        if hasattr(self, "_catalog_cache") and self._catalog_cache:
            for item in self._catalog_cache:
                c_name = (item.get("Category_Name") or "").strip()
                if c_name and c_name.lower() not in ("électroménager", "electromenager", "tous", "all"):
                    families.add(c_name)

        if not families:
            families.update([
                "Gros Électroménager",
                "Petit Électroménager",
                "Réfrigérateurs",
                "Lave-linge",
                "Climatisation",
                "Téléviseurs & Multimédia",
                "Cuisson & Fours",
            ])

        for f_name in sorted(list(families), key=lambda s: s.lower()):
            self.cbo_category.addItem(f_name, f_name)

        idx = self.cbo_category.findText(curr_text)
        if idx >= 0:
            self.cbo_category.setCurrentIndex(idx)
        else:
            self.cbo_category.setCurrentIndex(0)

        self._adjust_combo_view_width(self.cbo_category)
        self.cbo_category.blockSignals(False)

    def _sync_catalog_brands_and_categories_to_combos(self) -> None:
        """
        Ensures any distinct manufacturers or categories in the loaded catalog cache
        are present in cbo_mark and cbo_category without resetting the active selection.
        """
        if not hasattr(self, "_catalog_cache") or not self._catalog_cache:
            return

        # 1. Sync Brands
        if hasattr(self, "cbo_mark") and self.cbo_mark:
            existing_marks = {self.cbo_mark.itemText(i).strip().lower() for i in range(self.cbo_mark.count())}
            self.cbo_mark.blockSignals(True)
            for it in self._catalog_cache:
                m = str(it.get("Brand_Mark") or "").strip()
                if m and m.lower() not in existing_marks and m.lower() not in ("générique", "generique", "tous", "all"):
                    existing_marks.add(m.lower())
                    self.cbo_mark.addItem(m, m)
            self._adjust_combo_view_width(self.cbo_mark)
            self.cbo_mark.blockSignals(False)

        # 2. Sync Categories
        if hasattr(self, "cbo_category") and self.cbo_category:
            existing_cats = {self.cbo_category.itemText(i).strip().lower() for i in range(self.cbo_category.count())}
            self.cbo_category.blockSignals(True)
            for it in self._catalog_cache:
                c = str(it.get("Category_Name") or "").strip()
                if c and c.lower() not in existing_cats and c.lower() not in ("électroménager", "electromenager", "tous", "all"):
                    existing_cats.add(c.lower())
                    self.cbo_category.addItem(c, c)
            self._adjust_combo_view_width(self.cbo_category)
            self.cbo_category.blockSignals(False)

    def _load_colors_into_combo(self) -> None:
        """Loads available product colors with real visual swatches into the filter combobox."""
        if not hasattr(self, "cbo_color") or not self.cbo_color:
            return

        current_selected = ""
        c_data = self.cbo_color.currentData()
        if isinstance(c_data, dict):
            current_selected = c_data.get("Color_Name", "")
        elif isinstance(c_data, str):
            current_selected = c_data
        if not current_selected:
            current_selected = self.cbo_color.currentText()

        self.cbo_color.blockSignals(True)
        self.cbo_color.clear()

        # 1. "Tous" option (clean, without redundant palette icon)
        self.cbo_color.addItem("Tous", {"Color_Name": "Tous", "Color_Code": ""})

        # 2. Collect colors from ProductColorManager or default registry
        colors_list: List[Dict[str, Any]] = []
        color_mgr = getattr(self.data_manager, "product_colors", None) or getattr(self.data_manager, "colors", None)
        if not color_mgr and hasattr(self.data_manager, "db") and self.data_manager.db:
            try:
                from database.product_color_manager import ProductColorManager
                color_mgr = ProductColorManager(self.data_manager.db)
            except Exception:
                color_mgr = None

        if color_mgr and hasattr(color_mgr, "get_all_colors"):
            try:
                colors_list = color_mgr.get_all_colors(active_only=True)
            except Exception as e:
                logger.debug(f"Could not load colors via manager: {e}")

        if not colors_list:
            from database.product_color_manager import DEFAULT_PRODUCT_COLORS
            colors_list = [
                {"Color_Name": name, "Color_Code": code, "Description": desc}
                for name, code, desc in DEFAULT_PRODUCT_COLORS
            ]

        seen_names = {"tous"}
        for c in colors_list:
            name = str(c.get("Color_Name") or "").strip()
            if name:
                seen_names.add(name.lower())

        # Also merge colors from catalog cache if available
        if hasattr(self, "_catalog_cache") and self._catalog_cache:
            for item in self._catalog_cache:
                c_fin = str(item.get("Color_Finish") or "").strip()
                if c_fin and c_fin.lower() not in seen_names and c_fin.lower() != "standard":
                    seen_names.add(c_fin.lower())
                    colors_list.append({
                        "Color_Name": c_fin,
                        "Color_Code": get_color_hex(c_fin),
                        "Description": f"Finition {c_fin}",
                    })

        # 3. Add each color with high-res circular swatch icon
        select_index = 0
        for idx, c in enumerate(colors_list, start=1):
            name = str(c.get("Color_Name") or "").strip()
            code = str(c.get("Color_Code") or get_color_hex(name)).strip()
            if not name:
                continue

            pixmap = QPixmap(14, 14)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QBrush(QColor(code)))
            border_qcol = QColor("#94A3B8" if code.upper() in ("#FFFFFF", "#FDFBF7", "#F5F5DC") else "rgba(0,0,0,0.3)")
            painter.setPen(QPen(border_qcol, 1.2))
            painter.drawEllipse(1, 1, 12, 12)
            painter.end()

            self.cbo_color.addItem(QIcon(pixmap), name, {"Color_Name": name, "Color_Code": code})

            if current_selected and name.lower() == current_selected.lower():
                select_index = idx

        self.cbo_color.setCurrentIndex(select_index)
        self.cbo_color.blockSignals(False)

        # Update the live swatch badge
        self._update_color_filter_swatch()

    def _sync_catalog_colors_to_combo(self) -> None:
        """Ensures any distinct color finishes present in loaded catalog items exist in the combobox."""
        if not hasattr(self, "cbo_color") or not self.cbo_color:
            return
        if not hasattr(self, "_catalog_cache") or not self._catalog_cache:
            return

        existing_names = set()
        for i in range(self.cbo_color.count()):
            d = self.cbo_color.itemData(i)
            c_name = d.get("Color_Name") if isinstance(d, dict) else self.cbo_color.itemText(i)
            if c_name:
                existing_names.add(str(c_name).strip().lower())

        added_any = False
        for item in self._catalog_cache:
            c_fin = str(item.get("Color_Finish") or "").strip()
            if c_fin and c_fin.lower() not in existing_names and c_fin.lower() != "standard":
                existing_names.add(c_fin.lower())
                code = get_color_hex(c_fin)

                pixmap = QPixmap(14, 14)
                pixmap.fill(Qt.transparent)
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setBrush(QBrush(QColor(code)))
                border_qcol = QColor("#94A3B8" if code.upper() in ("#FFFFFF", "#FDFBF7", "#F5F5DC") else "rgba(0,0,0,0.3)")
                painter.setPen(QPen(border_qcol, 1.2))
                painter.drawEllipse(1, 1, 12, 12)
                painter.end()

                self.cbo_color.blockSignals(True)
                self.cbo_color.addItem(QIcon(pixmap), c_fin, {"Color_Name": c_fin, "Color_Code": code})
                self.cbo_color.blockSignals(False)
                added_any = True

    def _on_color_filter_changed(self) -> None:
        self._update_color_filter_swatch()
        self.refresh_catalog()

    def _update_color_filter_swatch(self) -> None:
        """Updates the live color badge widget next to the color combobox."""
        if not hasattr(self, "color_preview_badge") or not self.color_preview_badge:
            return

        name = "Tous"
        code = ""
        if hasattr(self, "cbo_color") and self.cbo_color:
            c_data = self.cbo_color.currentData()
            if isinstance(c_data, dict):
                name = c_data.get("Color_Name") or "Tous"
                code = c_data.get("Color_Code") or ""
            elif isinstance(c_data, str) and c_data:
                name = c_data
                code = get_color_hex(name)
            else:
                name = self.cbo_color.currentText() or "Tous"
                code = get_color_hex(name)

        self.color_preview_badge.update_color(name, code)

    def _on_color_badge_clicked(self) -> None:
        if hasattr(self, "cbo_color") and self.cbo_color:
            if self.cbo_color.currentIndex() != 0:
                self.cbo_color.setCurrentIndex(0)
            else:
                self.cbo_color.showPopup()

    def _create_catalog_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("OrderCatalogPanel")
        panel.setStyleSheet("""
            QFrame#OrderCatalogPanel {
                background-color: #FFFFFF;
                border: 1px solid #DCDFE6;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
                color: #2C3E50;
            }
        """)
        # De-containerize: remove double-box nesting by eliminating outer margins and spacing (Task #7)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Retain lbl_cat_title for backend metrics and test compatibility without wasting vertical space or clipping (Task #7)
        self.lbl_cat_title = QLabel("Catalogue des Produits Disponibles")
        self.lbl_cat_title.setVisible(False)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "Marque",
            "Désignation Produit",
            "Catégorie",
            "Réf",
            "Phys.",
            "Dispo.",
            "Prix TTC",
            "Ajout",
        ])
        self.table.setStyleSheet(
            TABLE_STYLE
            + "\nQTableWidget { border: none; border-bottom: 1px solid #E2E8F0; border-radius: 0px; }"
        )
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.horizontalHeader().setFixedHeight(38)
        self.table.horizontalHeader().setMinimumSectionSize(45)
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
        self.table.horizontalHeaderItem(7).setTextAlignment(Qt.AlignCenter)

        # Automatic horizontal scrollbar as needed to prevent any clipping
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 115)
        h.setSectionResizeMode(1, QHeaderView.Interactive)
        self.table.setColumnWidth(1, 280)
        h.setSectionResizeMode(2, QHeaderView.Interactive)
        self.table.setColumnWidth(2, 160)
        h.setSectionResizeMode(3, QHeaderView.Interactive)
        self.table.setColumnWidth(3, 86)
        h.setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(4, 56)
        h.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 60)
        h.setSectionResizeMode(6, QHeaderView.Interactive)
        self.table.setColumnWidth(6, 150)
        h.setSectionResizeMode(7, QHeaderView.Fixed)
        self.table.setColumnWidth(7, 62)

        h.sectionResized.connect(self._on_catalog_header_section_resized)
        self.table.installEventFilter(self)

        # Connect scroll listener for professional lazy loading
        self.table.verticalScrollBar().valueChanged.connect(self._on_catalog_scroll)

        layout.addWidget(self.table, 1)

        # Bottom summary information bar matching Stock & Magasin -> Stock Actuel
        self.catalog_bottom_bar = self._create_catalog_bottom_bar()
        layout.addWidget(self.catalog_bottom_bar)

        return panel

    def _create_catalog_bottom_bar(self) -> QWidget:
        """
        Builds the bottom summary information bar:
        - Valeur Totale (TTC) of filtered items (clean typography, no boxed container)
        - Stock disponible affiché (clean typography, no boxed container)
        - Loaded count vs total filtered items (slate text)
        """
        bottom_frame = QFrame()
        self.bottom_frame = bottom_frame
        bottom_frame.setObjectName("CatalogBottomBar")
        bottom_frame.setFixedHeight(38)
        bottom_frame.setStyleSheet("""
            QFrame#CatalogBottomBar {
                background-color: #FAFAFA;
                border-top: 1px solid #E2E8F0;
                border-bottom: none;
                border-left: none;
                border-right: none;
                border-radius: 0px;
            }
            QLabel {
                font-size: 11px;
                font-weight: 700;
                background: transparent;
                border: none;
            }
        """)
        bar_layout = QHBoxLayout(bottom_frame)
        bar_layout.setContentsMargins(12, 4, 12, 4)
        bar_layout.setSpacing(12)

        # 1. Total Value badge (TTC) - de-containerized clean typography (Task #7)
        self.lbl_total_value = QLabel("Valeur Totale : 0,00 DA")
        self.lbl_total_value.setObjectName("LblCatalogTotalValue")
        self.lbl_total_value.setStyleSheet("""
            QLabel#LblCatalogTotalValue {
                color: #007572;
                font-weight: 800;
                font-size: 11px;
                background: transparent;
                border: none;
                padding: 0px;
            }
        """)
        bar_layout.addWidget(self.lbl_total_value)
        self.lbl_total_value.setVisible(False)

        sep1 = QLabel("•")
        sep1.setStyleSheet("color: #CBD5E1; font-weight: bold; font-size: 10px; background: transparent; border: none;")
        sep1.setVisible(False)
        bar_layout.addWidget(sep1)

        # 2. Total Quantity available badge - de-containerized clean typography (Task #7)
        self.lbl_total_quantity = QLabel("Stock disponible affiché : 0")
        self.lbl_total_quantity.setObjectName("LblCatalogTotalQuantity")
        self.lbl_total_quantity.setStyleSheet("""
            QLabel#LblCatalogTotalQuantity {
                color: #166534;
                font-weight: 800;
                font-size: 11px;
                background: transparent;
                border: none;
                padding: 0px;
            }
        """)
        bar_layout.addWidget(self.lbl_total_quantity)

        sep2 = QLabel("•")
        sep2.setStyleSheet("color: #CBD5E1; font-weight: bold; font-size: 10px; background: transparent; border: none;")
        bar_layout.addWidget(sep2)

        # 3. Count Info: Displayed / Total
        self.lbl_count_info = QLabel("Affichage: 0 / 0")
        self.lbl_count_info.setObjectName("LblCatalogCountInfo")
        self.lbl_count_info.setStyleSheet("""
            QLabel#LblCatalogCountInfo {
                color: #64748B;
                font-weight: 700;
                font-size: 11px;
                background: transparent;
                border: none;
                padding: 0px;
            }
        """)
        bar_layout.addWidget(self.lbl_count_info)

        bar_layout.addStretch()

        return bottom_frame

    def _update_catalog_filter_metrics(self) -> None:
        """Updates the filter summary labels and badges matching Stock & Magasin -> Stock Actuel."""
        total_items = len(self._catalog_filtered_items) if hasattr(self, "_catalog_filtered_items") else 0
        loaded_count = getattr(self, "_catalog_loaded_count", 0)

        total_available_qty = 0
        total_value_ttc = 0.0

        if hasattr(self, "_catalog_filtered_items") and self._catalog_filtered_items:
            for it in self._catalog_filtered_items:
                qty = max(0, int(it.get("Available_Theoretical_Qty") or 0))
                price = float(it.get("Unit_Price_TTC") or it.get("Price_1_TTC") or 0.0)
                total_available_qty += qty
                total_value_ttc += (qty * price)

        # Update Bottom Bar labels (matching Stock Actuel)
        if hasattr(self, "lbl_total_value") and self.lbl_total_value:
            self.lbl_total_value.setText(f"Valeur Totale : {format_money(total_value_ttc)} DA")
            self.lbl_total_value.setToolTip(f"Valeur marchande TTC totale des {total_items} produit(s) filtré(s)")

        if hasattr(self, "lbl_total_quantity") and self.lbl_total_quantity:
            self.lbl_total_quantity.setText(f"Stock disponible affiché : {format_quantity(total_available_qty)}")
            self.lbl_total_quantity.setToolTip(f"Quantité totale d'unités disponibles immédiatement à la vente")

        if hasattr(self, "lbl_count_info") and self.lbl_count_info:
            self.lbl_count_info.setText(f"Affichage: {loaded_count} / {total_items}")
            self.lbl_count_info.setToolTip(f"{loaded_count} produit(s) affiché(s) sur un total de {total_items} correspondant aux filtres")

        # Update Top KPI count badge
        if hasattr(self, "lbl_catalog_count_badge") and self.lbl_catalog_count_badge:
            if total_items == 1:
                self.lbl_catalog_count_badge.setText(f"1 produit trouvé ({format_quantity(total_available_qty)} en stock)")
                self.lbl_catalog_count_badge.setStyleSheet("""
                    QLabel {
                        background-color: #E6F4F1;
                        color: #007572;
                        font-size: 11px;
                        font-weight: 800;
                        border: 1px solid #A7F3D0;
                        border-radius: 13px;
                        padding: 2px 10px;
                    }
                """)
            elif total_items > 1:
                self.lbl_catalog_count_badge.setText(f"{total_items} produits trouvés ({format_quantity(total_available_qty)} en stock)")
                self.lbl_catalog_count_badge.setStyleSheet("""
                    QLabel {
                        background-color: #E6F4F1;
                        color: #007572;
                        font-size: 11px;
                        font-weight: 800;
                        border: 1px solid #A7F3D0;
                        border-radius: 13px;
                        padding: 2px 10px;
                    }
                """)
            else:
                self.lbl_catalog_count_badge.setText("0 résultat")
                self.lbl_catalog_count_badge.setStyleSheet("""
                    QLabel {
                        background-color: #F8FAFC;
                        color: #94A3B8;
                        font-size: 11px;
                        font-weight: 700;
                        border: 1px solid #E2E8F0;
                        border-radius: 13px;
                        padding: 2px 10px;
                    }
                """)
            self.lbl_catalog_count_badge.setToolTip(
                f"Catalogue Filtré :\n"
                f"• {total_items} produit(s)\n"
                f"• {format_quantity(total_available_qty)} unités disponibles en stock\n"
                f"• {format_money(total_value_ttc)} DA de valeur marchande TTC"
            )

    def _adjust_catalog_column_widths(self) -> None:
        """
        Dynamically adjusts 'Désignation Produit' column (index 1) width:
        - When the catalog table viewport has surplus space, column 1 stretches smoothly to fill it.
        - When the table is narrowed (e.g. by dragging the splitter or resizing), column 1 is clamped
          to a minimum of 280px, activating the horizontal scrollbar so product names and details
          are 100% visible and never clipped.
        """
        if getattr(self, "_is_adjusting_columns", False):
            return
        if not hasattr(self, "table") or self.table is None:
            return

        self._is_adjusting_columns = True
        try:
            viewport_w = self.table.viewport().width()
            if viewport_w <= 0:
                if self.table.columnWidth(1) < 280:
                    self.table.setColumnWidth(1, 280)
                return

            other_widths = sum(self.table.columnWidth(c) for c in range(self.table.columnCount()) if c != 1)
            min_desig_width = 280
            avail = viewport_w - other_widths
            target = max(min_desig_width, avail)

            if self.table.columnWidth(1) != target:
                self.table.setColumnWidth(1, target)
        finally:
            self._is_adjusting_columns = False

    def _on_catalog_header_section_resized(self, logical_index: int, old_size: int, new_size: int) -> None:
        """Ensures designation column does not shrink below readable threshold and updates layout."""
        if getattr(self, "_is_adjusting_columns", False):
            return
        if logical_index == 1:
            if new_size < 260:
                self.table.setColumnWidth(1, 260)
        else:
            self._adjust_catalog_column_widths()

    def _adjust_cart_column_widths(self) -> None:
        """
        Dynamically adjusts 'Désignation' column (index 0) width in the cart table:
        - When the cart panel viewport has surplus space, column 0 stretches smoothly to fill it.
        - When the cart panel is narrowed, column 0 is clamped to a minimum of 180px,
          activating the horizontal scrollbar so all items (Couleur badge, Qté stepper, Total TTC,
          and Suppr. button) remain 100% complete, unclipped, and fully readable.
        """
        if getattr(self, "_is_adjusting_cart_columns", False):
            return
        if not hasattr(self, "cart_table") or self.cart_table is None:
            return

        self._is_adjusting_cart_columns = True
        try:
            viewport_w = self.cart_table.viewport().width()
            if viewport_w <= 0:
                if self.cart_table.columnWidth(0) < 180:
                    self.cart_table.setColumnWidth(0, 180)
                return

            other_widths = sum(self.cart_table.columnWidth(c) for c in range(self.cart_table.columnCount()) if c != 0)
            min_desig_width = 180
            avail = viewport_w - other_widths
            target = max(min_desig_width, avail)

            if self.cart_table.columnWidth(0) != target:
                self.cart_table.setColumnWidth(0, target)
        finally:
            self._is_adjusting_cart_columns = False

    def _on_cart_header_section_resized(self, logical_index: int, old_size: int, new_size: int) -> None:
        """Ensures cart designation column does not shrink below readable threshold."""
        if getattr(self, "_is_adjusting_cart_columns", False):
            return
        if logical_index == 0:
            if new_size < 160:
                self.cart_table.setColumnWidth(0, 160)
        else:
            self._adjust_cart_column_widths()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is getattr(self, "table", None) and event.type() == QEvent.Resize:
            self._adjust_catalog_column_widths()
        elif watched is getattr(self, "cart_table", None) and event.type() == QEvent.Resize:
            self._adjust_cart_column_widths()
        return super().eventFilter(watched, event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._adjust_catalog_column_widths()
        self._adjust_cart_column_widths()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._adjust_catalog_column_widths()
        self._adjust_cart_column_widths()

    def _create_cart_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("OrderCartPanel")
        panel.setMinimumWidth(300)
        panel.setStyleSheet("""
            QFrame#OrderCartPanel {
                background-color: #FFFFFF;
                border: 1px solid #DCDFE6;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
                color: #2C3E50;
            }
        """)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setSpacing(8)

        # Cart Header + Clear Button
        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        c_icon = QLabel()
        c_icon.setPixmap(get_duotone_icon("pos", 18).pixmap(18, 18))
        header_row.addWidget(c_icon)

        self.lbl_cart_header = QLabel("Panier — Session #1")
        self.lbl_cart_header.setStyleSheet("font-size: 13px; font-weight: bold; color: #007572;")
        header_row.addWidget(self.lbl_cart_header)
        header_row.addStretch()

        self.btn_daily_bons = QPushButton("Bons du Jour")
        self.btn_daily_bons.setIcon(get_duotone_icon("statement", 14))
        self.btn_daily_bons.setIconSize(QSize(14, 14))
        self.btn_daily_bons.setCursor(Qt.PointingHandCursor)
        self.btn_daily_bons.setFixedHeight(28)
        self.btn_daily_bons.setStyleSheet(OUTLINE_BTN_STYLE)
        self.btn_daily_bons.setToolTip("Afficher, modifier ou exporter en PDF les bons du jour et les BL non clôturés")
        self.btn_daily_bons.clicked.connect(self._open_daily_bons_dialog)
        header_row.addWidget(self.btn_daily_bons)

        btn_clear = QPushButton("Vider")
        btn_clear.setIcon(get_trash_icon(14))
        btn_clear.setIconSize(QSize(14, 14))
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.setFixedHeight(28)
        btn_clear.setStyleSheet(DANGER_BTN_STYLE)
        btn_clear.clicked.connect(self._clear_current_cart)
        header_row.addWidget(btn_clear)
        layout.addLayout(header_row)

        # Client Selection Header & Dedicated Full-Width Combobox
        client_header = QHBoxLayout()
        client_header.setSpacing(6)
        lbl_cl = QLabel("Client :")
        lbl_cl.setStyleSheet("font-size: 12px; font-weight: 700; color: #334155;")
        client_header.addWidget(lbl_cl)
        client_header.addStretch()

        btn_new_client = QPushButton("+ Nouveau Client")
        btn_new_client.setCursor(Qt.PointingHandCursor)
        btn_new_client.setFixedHeight(28)
        btn_new_client.setStyleSheet(OUTLINE_BTN_STYLE)
        btn_new_client.setToolTip("Ajouter rapidement un nouveau client en quelques secondes")
        btn_new_client.clicked.connect(self._open_quick_client_dialog)
        client_header.addWidget(btn_new_client)
        layout.addLayout(client_header)

        self.cbo_client = QComboBox()
        self.cbo_client.setObjectName("OrderClientCombo")
        self.cbo_client.setFixedHeight(36)
        self.cbo_client.setMinimumHeight(36)
        self.cbo_client.setEditable(True)
        self.cbo_client.setInsertPolicy(QComboBox.NoInsert)
        self.cbo_client.setStyleSheet("""
            QComboBox#OrderClientCombo {
                background-color: #FFFFFF;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 600;
                color: #2C3E50;
                min-height: 28px;
            }
            QComboBox#OrderClientCombo:hover {
                border-color: #ADB5BD;
            }
            QComboBox#OrderClientCombo:focus {
                border: 1.5px solid #007572;
                background-color: #FFFFFF;
            }
            QComboBox#OrderClientCombo::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid #CED4DA;
                background-color: #F8FAFC;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }
            QComboBox#OrderClientCombo QAbstractItemView {
                border: 1px solid #CED4DA;
                border-radius: 4px;
                background-color: #FFFFFF;
                selection-background-color: #E6F4F1;
                selection-color: #007572;
                font-size: 12px;
                padding: 4px;
                color: #2C3E50;
            }
        """)
        if self.cbo_client.lineEdit():
            self.cbo_client.lineEdit().setPlaceholderText("Rechercher par nom ou n° téléphone...")
            self.cbo_client.lineEdit().setStyleSheet(
                "border: none; background: transparent; font-size: 12px; font-weight: 600; color: #1E293B; padding: 0 4px;"
            )
        self._load_clients_into_combo()
        self.cbo_client.currentIndexChanged.connect(self._on_client_changed)
        layout.addWidget(self.cbo_client)

        # Cart Items Table (5 columns: Désignation, Couleur, Qté, Total TTC, Suppr.)
        self.cart_table = QTableWidget(0, 5)
        self.cart_table.setHorizontalHeaderLabels(["Désignation", "Réf", "Qté", "Total TTC", "Suppr."])
        self.cart_table.setStyleSheet(TABLE_STYLE)
        self.cart_table.verticalHeader().setVisible(False)
        self.cart_table.verticalHeader().setDefaultSectionSize(40)
        self.cart_table.horizontalHeader().setFixedHeight(34)
        self.cart_table.setShowGrid(True)
        self.cart_table.setAlternatingRowColors(True)
        self.cart_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.cart_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.cart_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.cart_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.cart_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.cart_table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.cart_table.installEventFilter(self)

        ch = self.cart_table.horizontalHeader()
        ch.setSectionResizeMode(0, QHeaderView.Interactive)
        self.cart_table.setColumnWidth(0, 180)
        ch.setSectionResizeMode(1, QHeaderView.Interactive)
        self.cart_table.setColumnWidth(1, 105)
        ch.setSectionResizeMode(2, QHeaderView.Fixed)
        self.cart_table.setColumnWidth(2, 80)
        ch.setSectionResizeMode(3, QHeaderView.Fixed)
        self.cart_table.setColumnWidth(3, 105)
        ch.setSectionResizeMode(4, QHeaderView.Fixed)
        self.cart_table.setColumnWidth(4, 42)

        self.cart_table.horizontalHeaderItem(0).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.cart_table.horizontalHeaderItem(1).setTextAlignment(Qt.AlignCenter)
        self.cart_table.horizontalHeaderItem(2).setTextAlignment(Qt.AlignCenter)
        self.cart_table.horizontalHeaderItem(3).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.cart_table.horizontalHeaderItem(4).setTextAlignment(Qt.AlignCenter)
        self.cart_table.horizontalHeaderItem(4).setToolTip("Supprimer l'article de la commande")
        ch.sectionResized.connect(self._on_cart_header_section_resized)
        layout.addWidget(self.cart_table, 1)

        # Delivery info for Bon de Livraison
        self.txt_delivery_addr = QLineEdit()
        self.txt_delivery_addr.setFixedHeight(34)
        self.txt_delivery_addr.setPlaceholderText("Adresse de livraison & téléphone (pour Bon de Livraison)...")
        self.txt_delivery_addr.setStyleSheet("""
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 12px;
                color: #2C3E50;
            }
            QLineEdit:hover {
                border-color: #ADB5BD;
            }
            QLineEdit:focus {
                border: 1.5px solid #007572;
                background-color: #FFFFFF;
            }
        """)
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
        lbl_tot_tag.setStyleSheet("font-size: 11px; font-weight: bold; color: #007572;")
        tot_layout.addWidget(lbl_tot_tag)
        tot_layout.addStretch()
        self.lbl_total = QLabel("0.00 DA")
        self.lbl_total.setStyleSheet("font-size: 16px; font-weight: bold; color: #007572;")
        tot_layout.addWidget(self.lbl_total)
        layout.addWidget(total_box)

        # Primary CTA: Paiement complet (Bon Comptant)
        self.btn_bon_c = QPushButton("Paiement complet")
        self.btn_bon_c.setIcon(get_duotone_icon("payment_white", 16))
        self.btn_bon_c.setIconSize(QSize(16, 16))
        self.btn_bon_c.setCursor(Qt.PointingHandCursor)
        self.btn_bon_c.setFixedHeight(44)
        self.btn_bon_c.setStyleSheet("""
            QPushButton {
                background-color: #007572;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 12px;
                border: none;
                border-radius: 4px;
                padding: 0 12px;
            }
            QPushButton:hover {
                background-color: #005A57;
            }
            QPushButton:pressed {
                background-color: #003D3A;
            }
        """)
        self.btn_bon_c.clicked.connect(lambda: self._submit_order("BON_C"))
        layout.addWidget(self.btn_bon_c)

        # Secondary Row: Paiement à crédit & Paiement à la livraison side-by-side
        sec_row = QHBoxLayout()
        sec_row.setSpacing(8)

        self.btn_credit = QPushButton("Paiement à crédit")
        self.btn_credit.setIcon(get_duotone_icon("shield_admin", 15))
        self.btn_credit.setIconSize(QSize(15, 15))
        self.btn_credit.setCursor(Qt.PointingHandCursor)
        self.btn_credit.setFixedHeight(40)
        self.btn_credit.setStyleSheet(OUTLINE_BTN_STYLE)
        self.btn_credit.clicked.connect(lambda: self._submit_order("BON_CREDIT"))
        sec_row.addWidget(self.btn_credit)

        self.btn_livraison = QPushButton("Paiement à la livraison")
        self.btn_livraison.setIcon(get_duotone_icon("truck_delivery", 15))
        self.btn_livraison.setIconSize(QSize(15, 15))
        self.btn_livraison.setCursor(Qt.PointingHandCursor)
        self.btn_livraison.setFixedHeight(40)
        self.btn_livraison.setStyleSheet(OUTLINE_BTN_STYLE)
        self.btn_livraison.clicked.connect(lambda: self._submit_order("BON_LIVRAISON"))
        sec_row.addWidget(self.btn_livraison)

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
            loaded_clients = []
            if self.data_manager and hasattr(self.data_manager, "clients"):
                try:
                    db_clients = self.data_manager.clients.get_all_clients() or []
                    for c in db_clients:
                        cid = c.get("Client_ID")
                        cname = str(c.get("Client_Name") or f"Client #{cid}").strip()
                        cphone = str(c.get("Phone") or "").strip()
                        caddr = str(c.get("Address") or "").strip()
                        c_tier = str(c.get("Price_Tier") or "Prix_1").strip()
                        loaded_clients.append({
                            "Client_ID": int(cid) if cid is not None else 0,
                            "Client_Name": cname,
                            "Phone": cphone,
                            "Address": caddr,
                            "Price_Tier": c_tier,
                        })
                except Exception as err:
                    logger.debug(f"Error loading clients: {err}")
            elif os.environ.get("PYTEST_CURRENT_TEST"):
                loaded_clients = [
                    {"Client_ID": 1, "Client_Name": "Client Standard", "Phone": "", "Address": "", "Price_Tier": "Prix_1"}
                ]
            self._clients_cache = loaded_clients

        select_idx = 0
        for idx, c in enumerate(self._clients_cache):
            display = c["Client_Name"]
            if c.get("Phone"):
                display += f"  —  Tél: {c['Phone']}"
            self.cbo_client.addItem(display, c["Client_ID"])
            if selected_id is not None and c["Client_ID"] == selected_id:
                select_idx = idx

        completer = QCompleter(self.cbo_client.model(), self.cbo_client)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.cbo_client.setCompleter(completer)

        self.cbo_client.setCurrentIndex(select_idx)
        self.cbo_client.blockSignals(False)

    def _on_available_only_toggled(self, checked: bool) -> None:
        """Refreshes catalog when availability filter is toggled."""
        self.refresh_catalog()

    def _reset_filters(self) -> None:
        if hasattr(self, "cbo_mark") and self.cbo_mark:
            self.cbo_mark.setCurrentIndex(0)
        if hasattr(self, "cbo_category") and self.cbo_category:
            self.cbo_category.setCurrentIndex(0)
        if hasattr(self, "cbo_color") and self.cbo_color:
            self.cbo_color.setCurrentIndex(0)
        if hasattr(self, "txt_search") and self.txt_search:
            self.txt_search.clear()
        if hasattr(self, "chk_available_only") and self.chk_available_only:
            self.chk_available_only.setChecked(True)
        self._update_color_filter_swatch()
        self.refresh_catalog()

    def refresh_catalog(self) -> None:
        """Loads catalog items from database (or fallback showcase rows) with theoretical availability and resets lazy loading."""
        search_txt = self.txt_search.text().strip() if hasattr(self, "txt_search") else ""

        # Extract brand filter term
        mark_txt = "Tous"
        if hasattr(self, "cbo_mark") and self.cbo_mark:
            m_data = self.cbo_mark.currentData()
            if m_data and str(m_data).strip().lower() not in ("tous", "all", "toutes", "none"):
                mark_txt = str(m_data).strip()
            else:
                m_txt = self.cbo_mark.currentText().strip()
                clean_m = m_txt.replace("🏭", "").replace("📁", "").strip()
                if clean_m.lower() not in ("tous", "all", "toutes", "marques", ""):
                    mark_txt = clean_m
                else:
                    mark_txt = "Tous"

        # Extract category / family filter term
        cat_txt = "Tous"
        if hasattr(self, "cbo_category") and self.cbo_category:
            c_data = self.cbo_category.currentData()
            if c_data and str(c_data).strip().lower() not in ("tous", "all", "toutes", "none"):
                cat_txt = str(c_data).strip()
            else:
                c_txt = self.cbo_category.currentText().strip()
                clean_c = c_txt.replace("📁", "").replace("🏭", "").strip()
                if clean_c.lower() not in ("tous", "all", "toutes", "familles", "catégories", ""):
                    cat_txt = clean_c
                else:
                    cat_txt = "Tous"

        col_txt = "Tous"
        if hasattr(self, "cbo_color") and self.cbo_color:
            c_data = self.cbo_color.currentData()
            if isinstance(c_data, dict):
                col_txt = c_data.get("Color_Name") or self.cbo_color.currentText()
            elif isinstance(c_data, str) and c_data:
                col_txt = c_data
            else:
                col_txt = self.cbo_color.currentText()
        if not col_txt:
            col_txt = "Tous"

        only_avail = True

        items: List[Dict[str, Any]] = []
        if self.data_manager and hasattr(self.data_manager, "serials"):
            try:
                items = self.data_manager.serials.get_catalog_with_theoretical_stock(
                    search=search_txt,
                    brand_mark=mark_txt,
                    category_name=cat_txt,
                    color_finish=col_txt,
                    only_available=only_avail,
                )
            except TypeError:
                items = self.data_manager.serials.get_catalog_with_theoretical_stock(
                    search=search_txt,
                    brand_mark=mark_txt,
                    category_name=cat_txt,
                    color_finish=col_txt,
                )
            self._catalog_cache = items
            s_low = search_txt.lower()
            m_low = mark_txt.lower() if mark_txt != "Tous" else ""
            c_low = cat_txt.lower() if cat_txt != "Tous" else ""
            col_low = col_txt.lower() if col_txt != "Tous" else ""

            filtered_db_items = []
            for it in items:
                avail_qty = int(it.get("Available_Theoretical_Qty") or 0)
                if avail_qty <= 0:
                    continue
                if "Physical_Stock_Qty" in it and int(it.get("Physical_Stock_Qty") or 0) <= 0:
                    continue
                if s_low:
                    name_match = s_low in str(it.get("Product_Name", "")).lower()
                    mark_match = s_low in str(it.get("Brand_Mark", "")).lower()
                    cat_match = s_low in str(it.get("Category_Name", "")).lower()
                    col_match = s_low in str(it.get("Color_Finish", "")).lower()
                    bar_match = s_low in str(it.get("Barcode", "")).lower()
                    if not (name_match or mark_match or cat_match or col_match or bar_match):
                        continue
                if m_low:
                    it_mark = str(it.get("Brand_Mark", "")).lower()
                    if m_low not in it_mark and it_mark not in m_low:
                        continue
                if c_low:
                    it_cat = str(it.get("Category_Name", "")).lower()
                    if c_low not in it_cat and it_cat not in c_low:
                        continue
                if col_low:
                    it_col = str(it.get("Color_Finish", "")).lower()
                    if col_low not in it_col and it_col not in col_low:
                        continue
                filtered_db_items.append(it)
            items = filtered_db_items
        else:
            # Fallback catalog in-memory filtering (offline / test mode)
            if not self._catalog_cache:
                if not os.environ.get("PYTEST_CURRENT_TEST"):
                    self._catalog_cache = []
                else:
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
            m_low = mark_txt.lower() if mark_txt != "Tous" else ""
            c_low = cat_txt.lower() if cat_txt != "Tous" else ""
            col_low = col_txt.lower() if col_txt != "Tous" else ""

            for it in self._catalog_cache:
                if only_avail:
                    avail_qty = int(it.get("Available_Theoretical_Qty") or 0)
                    if avail_qty <= 0:
                        continue
                if s_low:
                    name_match = s_low in str(it.get("Product_Name", "")).lower()
                    mark_match = s_low in str(it.get("Brand_Mark", "")).lower()
                    cat_match = s_low in str(it.get("Category_Name", "")).lower()
                    col_match = s_low in str(it.get("Color_Finish", "")).lower()
                    bar_match = s_low in str(it.get("Barcode", "")).lower()
                    if not (name_match or mark_match or cat_match or col_match or bar_match):
                        continue
                if m_low:
                    it_mark = str(it.get("Brand_Mark", "")).lower()
                    if m_low not in it_mark and it_mark not in m_low:
                        continue
                if c_low:
                    it_cat = str(it.get("Category_Name", "")).lower()
                    if c_low not in it_cat and it_cat not in c_low:
                        continue
                if col_low:
                    it_col = str(it.get("Color_Finish", "")).lower()
                    if col_low not in it_col and it_col not in col_low:
                        continue
                items.append(it)

        self._catalog_filtered_items = items
        self._catalog_loaded_count = 0
        self.table.setRowCount(0)

        # Synchronize dynamic color finishes, brands, and categories
        self._sync_catalog_colors_to_combo()
        self._sync_catalog_brands_and_categories_to_combos()

        # Update filter metrics & summary information matching Stock & Magasin -> Stock Actuel
        self._update_catalog_filter_metrics()

        self._load_next_catalog_chunk()

    def _load_next_catalog_chunk(self) -> None:
        """Appends the next chunk of catalog rows into the table (lazy loading)."""
        if getattr(self, "_is_loading_chunk", False):
            return
        if not hasattr(self, "_catalog_filtered_items"):
            return

        total = len(self._catalog_filtered_items)
        if self._catalog_loaded_count >= total and total > 0:
            return

        self._is_loading_chunk = True
        try:
            chunk_size = getattr(self, "_catalog_chunk_size", 35)
            start_idx = self._catalog_loaded_count
            end_idx = min(start_idx + chunk_size, total)

            self.table.setUpdatesEnabled(False)
            for i in range(start_idx, end_idx):
                prod = self._catalog_filtered_items[i]
                self._append_catalog_row(prod)
            self.table.setUpdatesEnabled(True)

            self._catalog_loaded_count = end_idx

            if hasattr(self, "lbl_cat_title"):
                if total > 0:
                    self.lbl_cat_title.setText(
                        f"Catalogue des Produits Disponibles ({self._catalog_loaded_count} / {total})"
                    )
                else:
                    self.lbl_cat_title.setText("Catalogue des Produits Disponibles (0)")

            self._update_catalog_filter_metrics()
        finally:
            self._is_loading_chunk = False

    def _on_catalog_scroll(self, value: int) -> None:
        """Detects scroll near bottom to load the next chunk of catalog rows."""
        vbar = self.table.verticalScrollBar()
        if vbar.maximum() > 0 and value >= vbar.maximum() - 4:
            if hasattr(self, "_catalog_filtered_items") and self._catalog_loaded_count < len(self._catalog_filtered_items):
                self._load_next_catalog_chunk()

    def _append_catalog_row(self, prod: Dict[str, Any]) -> None:
        """Renders an individual product row into the catalog table with high enterprise ergonomics."""
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
        it_mark.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.table.setItem(row, 0, it_mark)

        it_name = QTableWidgetItem(name)
        it_name.setToolTip(name)
        self.table.setItem(row, 1, it_name)

        it_cat = QTableWidgetItem(cat)
        it_cat.setToolTip(f"Catégorie : {cat}")
        self.table.setItem(row, 2, it_cat)

        ref_val = str(
            prod.get("Barcode")
            or prod.get("Manuf_Cat_No")
            or prod.get("Reference")
            or prod.get("Product_Code")
            or "---"
        )
        it_ref = QTableWidgetItem(ref_val)
        it_ref.setData(Qt.UserRole, ref_val)
        it_ref.setTextAlignment(Qt.AlignCenter)
        it_ref.setToolTip(f"Réf : {ref_val}")
        self.table.setItem(row, 3, it_ref)

        it_phys = QTableWidgetItem(str(phys))
        it_phys.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 4, it_phys)

        it_avail = QTableWidgetItem(str(avail))
        it_avail.setTextAlignment(Qt.AlignCenter)
        it_avail.setForeground(QColor("#16A34A" if avail > 0 else "#94A3B8"))
        it_avail.setFont(QFont("Segoe UI", 10, QFont.Bold))
        it_avail.setToolTip(f"Quantité disponible : {avail}")
        self.table.setItem(row, 5, it_avail)

        # Column 6: Dedicated Price Column with interactive dropdown menu
        p1 = float(prod.get("Price_1_TTC") or prod.get("Unit_Price_TTC") or prod.get("Default_Selling_Price_HT") or 0.0)
        p2 = float(prod.get("Price_2_TTC") or (p1 * 0.95))
        p3 = float(prod.get("Price_3_TTC") or (p1 * 0.90))

        # Fix: empty text on QTableWidgetItem to prevent double overlapping ghost text
        it_price = QTableWidgetItem("")
        it_price.setTextAlignment(Qt.AlignCenter)
        it_price.setToolTip(
            f"Grille Tarifaire (TTC) :\n"
            f"• Prix 1 (Détail / Comptoir) : {format_money(p1)} DA\n"
            f"• Prix 2 (Demi-Gros / Revendeur) : {format_money(p2)} DA\n"
            f"• Prix 3 (Grossiste B2B) : {format_money(p3)} DA\n"
            f"(Cliquez pour afficher la liste déroulante des prix)"
        )
        self.table.setItem(row, 6, it_price)
        self.table.setCellWidget(row, 6, ProductPriceWidget(p1, p2, p3, prod_ref=prod))

        # Column 7: Action Cell Slot with borderless '+' button (no button border, framed cell slot)
        it_action = QTableWidgetItem("+" if avail > 0 else "—")
        it_action.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 7, it_action)
        action_widget = AddActionCellWidget(
            on_add_callback=lambda p=prod: self._add_product_to_session(self._active_session_id, p),
            is_available=(avail > 0),
        )
        self.table.setCellWidget(row, 7, action_widget)

    # =========================================================================
    # MULTI-SESSION & MULTI-SCANNER ROUTING (Tabs & HID Isolation)
    # =========================================================================

    def _on_delivery_addr_changed(self, text: str) -> None:
        if hasattr(self, "_active_session_id") and self._active_session_id in self._sessions:
            self._sessions[self._active_session_id]["delivery_address"] = text.strip()

    def _format_session_tab_text(self, sid: str) -> str:
        sdata = self._sessions.get(sid)
        if not sdata:
            return sid
        cart_count = len(sdata.get("cart", []))
        count_tag = f" ({cart_count})" if cart_count > 0 else ""
        if sdata.get("scanner_id"):
            return f"📷 Scanner [{sdata['scanner_id']}] • {sdata['label']}{count_tag}"
        return f"🔍 Recherche • {sdata['label']}{count_tag}"

    def _get_session_tab_icon(self, sid: str):
        sdata = self._sessions.get(sid, {})
        has_event = bool(sdata.get("has_event"))
        color = "#D97706" if has_event else ("#007572" if sdata.get("scanner_id") else "#64748B")
        if qta:
            icon_name = "fa5s.barcode" if sdata.get("scanner_id") else "fa5s.search"
            return qta.icon(icon_name, color=color)
        return get_duotone_icon("barcode_scan" if sdata.get("scanner_id") else "pos", 14)

    def _apply_session_tab_visuals(self, idx: int, sid: str) -> None:
        if not hasattr(self, "session_tab_bar") or idx < 0:
            return
        sdata = self._sessions.get(sid, {})
        has_event = bool(sdata.get("has_event"))
        self.session_tab_bar.setTabText(idx, self._format_session_tab_text(sid))
        self.session_tab_bar.setTabIcon(idx, self._get_session_tab_icon(sid))
        if has_event:
            self.session_tab_bar.setTabTextColor(idx, QColor("#D97706"))
        else:
            self.session_tab_bar.setTabTextColor(idx, QColor("#495057"))

    def _mark_session_event(self, sid: str) -> None:
        """Highlights the session tab button color when an event occurs in that session."""
        if sid not in self._sessions:
            return
        self._sessions[sid]["has_event"] = True
        if hasattr(self, "session_tab_bar"):
            for idx in range(self.session_tab_bar.count()):
                if self.session_tab_bar.tabData(idx) == sid:
                    self._apply_session_tab_visuals(idx, sid)
                    break

    def _update_tab_label(self, sid: str) -> None:
        if not hasattr(self, "session_tab_bar"):
            return
        if sid not in self._sessions:
            return

        for idx in range(self.session_tab_bar.count()):
            if self.session_tab_bar.tabData(idx) == sid:
                self._apply_session_tab_visuals(idx, sid)
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
        """Restores the user's previously saved separator position with balanced catalog/cart proportions."""
        try:
            settings = QSettings("StockLam", "OrderDesk")
            saved_state = settings.value("main_splitter_state")
            if saved_state:
                self.splitter.restoreState(saved_state)
                sizes = self.splitter.sizes()
                if len(sizes) == 2:
                    total = sum(sizes)
                    if total > 0 and (sizes[0] / float(total)) < 0.69:
                        cart_sz = max(430, min(465, int(total * 0.29)))
                        self.splitter.setSizes([max(580, total - cart_sz), cart_sz])
                    elif sizes[1] < 420 and total >= 1000:
                        self.splitter.setSizes([max(560, total - 445), 445])
            else:
                saved_sizes = settings.value("main_splitter_sizes")
                if saved_sizes and isinstance(saved_sizes, (list, tuple)) and len(saved_sizes) == 2:
                    cat_sz = max(720, int(saved_sizes[0]))
                    cart_sz = max(430, min(465, int(saved_sizes[1])))
                    self.splitter.setSizes([cat_sz, cart_sz])
                else:
                    self.splitter.setSizes([1110, 455])
        except Exception as err:
            logger.debug(f"Could not restore splitter state: {err}")
            self.splitter.setSizes([1110, 455])

    def _update_tab_close_buttons(self) -> None:
        """Attaches sleek, human-crafted close buttons to all tabs with proper color contrast."""
        if not hasattr(self, "session_tab_bar"):
            return
        total_tabs = self.session_tab_bar.count()
        for idx in range(total_tabs):
            sid = self.session_tab_bar.tabData(idx)
            is_active = (sid == getattr(self, "_active_session_id", None))

            btn = QPushButton("×")
            btn.setObjectName(f"TabCloseBtn_{sid}")
            btn.setFixedSize(14, 14)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip("Fermer cette session" if total_tabs > 1 else "Réinitialiser cette session")

            close_color = "#FFFFFF" if is_active else "#64748B"
            btn.setStyleSheet(f"""
                QPushButton#{btn.objectName()} {{
                    border: none;
                    background-color: transparent;
                    color: {close_color};
                    font-size: 12px;
                    font-weight: bold;
                    padding: 0px;
                    margin: 0px;
                    border-radius: 7px;
                    text-align: center;
                }}
                QPushButton#{btn.objectName()}:hover {{
                    background-color: #EF4444;
                    color: #FFFFFF;
                }}
                QPushButton#{btn.objectName()}:pressed {{
                    background-color: #B91C1C;
                    color: #FFFFFF;
                }}
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

        act_bind = menu.addAction("🔗 Associer un Lecteur Code-Barres...")
        act_bind.triggered.connect(lambda: self._prompt_scanner_binding(sid))

        if sdata.get("scanner_id"):
            act_unbind = menu.addAction("🔓 Dissocier le Lecteur (Mode Recherche)")
            act_unbind.triggered.connect(lambda: self.unbind_scanner_from_session(sid))

        menu.addSeparator()

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
            tab_pos = self.session_tab_bar.addTab(
                self._get_session_tab_icon(sid),
                self._format_session_tab_text(sid),
            )
            self.session_tab_bar.setTabData(tab_pos, sid)
            self._apply_session_tab_visuals(tab_pos, sid)
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
        sdata["has_event"] = False
        self._apply_session_tab_visuals(idx, sid)
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
        self._update_tab_close_buttons()

    def _on_session_switched(self, idx: int) -> None:
        """Legacy compatibility wrapper forwarding to tab switch."""
        self._on_session_tab_switched(idx)

    def _on_session_tab_close_requested(self, index: int) -> None:
        sid = self.session_tab_bar.tabData(index)
        sdata = self._sessions.get(sid)
        if not sdata:
            return

        # If it is the last remaining session, clear/reset it rather than destroying the desk
        if self.session_tab_bar.count() <= 1:
            if sdata.get("cart"):
                reply = QMessageBox.question(
                    self,
                    "Réinitialiser la session",
                    f"Le panier de '{sdata['label']}' contient des articles en cours.\n"
                    "Voulez-vous vider le panier et réinitialiser cette session ?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply != QMessageBox.Yes:
                    return
            self._clear_session_cart(sid)
            self._load_clients_into_combo(selected_id=1)
            if hasattr(self, "txt_delivery_addr"):
                self.txt_delivery_addr.clear()
            self._update_tab_close_buttons()
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

    def get_bound_scanners(self, exclude_sid: Optional[str] = None) -> Dict[str, str]:
        """Returns a mapping of scanner_id -> session_id for all scanners already assigned on this device."""
        bound: Dict[str, str] = {}
        for s_id, sdata in self._sessions.items():
            if exclude_sid and s_id == exclude_sid:
                continue
            sc_id = sdata.get("scanner_id")
            if sc_id:
                bound[str(sc_id).strip()] = s_id
        return bound

    def bind_scanner_to_session(self, sid: str, scanner_id: str) -> Tuple[bool, str]:
        """Binds a barcode scanner to a session if not already bound to another session on the same device."""
        if sid not in self._sessions:
            return False, "Session introuvable."
        clean_dev = str(scanner_id or "").strip()
        if not clean_dev:
            return False, "Identifiant du scanner invalide."

        bound = self.get_bound_scanners(exclude_sid=sid)
        if clean_dev in bound:
            other_sid = bound[clean_dev]
            other_label = self._sessions.get(other_sid, {}).get("label", other_sid)
            return False, f"Le lecteur '{clean_dev}' est déjà assigné à '{other_label}'."

        old_dev = self._sessions[sid].get("scanner_id")
        if old_dev and old_dev != clean_dev:
            self.hid_manager.unbind_scanner(old_dev)

        self._sessions[sid]["scanner_id"] = clean_dev
        self.hid_manager.bind_scanner_to_session(clean_dev, sid)
        self._update_tab_label(sid)
        if hasattr(self, "lbl_scanner_status"):
            self.lbl_scanner_status.setText(f"Scanner [{clean_dev}] associé à {self._sessions[sid]['label']}")
        return True, "OK"

    def unbind_scanner_from_session(self, sid: str) -> None:
        """Unbinds any scanner from the given session, returning it to direct search mode."""
        if sid not in self._sessions:
            return
        old_dev = self._sessions[sid].get("scanner_id")
        if old_dev:
            self.hid_manager.unbind_scanner(old_dev)
        self._sessions[sid]["scanner_id"] = None
        self._update_tab_label(sid)

    def _create_new_session(self, scanner_id: Optional[str] = None) -> str:
        clean_sc = str(scanner_id).strip() if scanner_id else None
        if clean_sc:
            bound = self.get_bound_scanners()
            if clean_sc in bound:
                return bound[clean_sc]

        self._session_counter += 1
        sid = f"SESSION_{self._session_counter}"
        while sid in self._sessions:
            self._session_counter += 1
            sid = f"SESSION_{self._session_counter}"

        label = f"Session #{self._session_counter}"
        self._sessions[sid] = {
            "label": label,
            "scanner_id": clean_sc,
            "client_id": 1,
            "cart": [],
            "delivery_address": "",
            "has_event": False,
        }
        if clean_sc:
            self.hid_manager.bind_scanner_to_session(clean_sc, sid)

        if hasattr(self, "session_tab_bar"):
            tab_idx = self.session_tab_bar.addTab(
                self._get_session_tab_icon(sid),
                self._format_session_tab_text(sid),
            )
            self.session_tab_bar.setTabData(tab_idx, sid)
            self._apply_session_tab_visuals(tab_idx, sid)
            if clean_sc is None:
                self.session_tab_bar.setCurrentIndex(tab_idx)
            self._update_tab_close_buttons()

        return sid

    def _prompt_scanner_binding(self, target_sid: Optional[str] = None) -> None:
        sid = target_sid or self._active_session_id
        sdata = self._sessions.get(sid)
        if not sdata:
            return
        curr_dev = sdata.get("scanner_id") or ""
        text, ok = QInputDialog.getText(
            self,
            "Association Scanner USB / HID",
            f"Identifiant matériel (hDevice / Handle) du lecteur pour {sdata['label']} :",
            text=curr_dev,
        )
        if ok and text.strip():
            success, msg = self.bind_scanner_to_session(sid, text.strip())
            if not success:
                QMessageBox.warning(self, "Scanner Déjà Assigné", msg)

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

        # 3. Only auto-bind the initial empty SESSION_1 if it is the sole session and has no cart items
        if len(self._sessions) == 1:
            sole_sid, sole_data = next(iter(self._sessions.items()))
            if not sole_data.get("scanner_id") and not sole_data.get("cart"):
                self.bind_scanner_to_session(sole_sid, clean_dev)
                return sole_sid

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
            self._mark_session_event(session_id)
            s_label = self._sessions.get(session_id, {}).get("label", session_id)
            self.lbl_scanner_status.setText(
                f"Scan [{device_id}] -> {s_label} : {matched_prod.get('Product_Name')} (Ajouté)"
            )
        else:
            self._mark_session_event(session_id)
            self.lbl_scanner_status.setText(
                f"Scan [{device_id}] ({clean_bc}) : Référence introuvable dans le stock"
            )

    def _get_client_tiered_price(self, session_id: str, prod: Dict[str, Any]) -> float:
        """Determines the appropriate unit price TTC based on explicit user dropdown selection or the active client's Price_Tier."""
        if prod.get("selected_price_ttc") is not None:
            return float(prod["selected_price_ttc"])

        base_price = float(prod.get("Unit_Price_TTC") or prod.get("Default_Selling_Price_HT") or 0.0)
        p1 = float(prod.get("Price_1_TTC") or base_price)
        p2 = float(prod.get("Price_2_TTC") or (p1 * 0.95))
        p3 = float(prod.get("Price_3_TTC") or (p1 * 0.90))

        client_id = None
        if hasattr(self, "_sessions") and session_id in self._sessions:
            client_id = self._sessions[session_id].get("client_id")

        tier = "Prix_1"
        if client_id and hasattr(self, "_clients_cache"):
            for c in self._clients_cache:
                if c.get("Client_ID") == client_id:
                    tier = str(c.get("Price_Tier") or "Prix_1")
                    break

        if "prix_3" in tier.lower() or "gros" in tier.lower():
            return p3
        elif "prix_2" in tier.lower() or "demi" in tier.lower():
            return p2
        return p1

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

        unit_price = self._get_client_tiered_price(session_id, prod)
        cart.append({
            "product_id": pid,
            "mark": str(prod.get("Brand_Mark") or ""),
            "name": str(prod.get("Product_Name") or ""),
            "ref": str(prod.get("Barcode") or prod.get("Manuf_Cat_No") or prod.get("Reference") or prod.get("Product_Code") or "---"),
            "coloure": str(prod.get("Color_Finish") or "Standard"),
            "unit_price_ttc": unit_price,
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

            # Col 0: Désignation Produit (Full title + tooltip)
            prod_title = f"{item.get('mark', '')} {item.get('name', '')}".strip()
            it_name = QTableWidgetItem(prod_title)
            it_name.setToolTip(prod_title)
            self.cart_table.setItem(row, 0, it_name)

            # Col 1: Réf du produit
            ref_val = str(item.get("ref") or item.get("Barcode") or item.get("Manuf_Cat_No") or "---")
            it_ref = QTableWidgetItem(ref_val)
            it_ref.setTextAlignment(Qt.AlignCenter)
            it_ref.setToolTip(f"Réf : {ref_val}")
            self.cart_table.setItem(row, 1, it_ref)

            # Col 2: Quantité (Stepper with - / qty / +)
            stepper = CartQtyStepper(
                qty=int(item["quantity"]),
                max_qty=int(item.get("max_avail") or 99),
            )
            stepper.qtyChanged.connect(lambda val, i=idx: self._update_line_qty(i, val))
            self.cart_table.setCellWidget(row, 2, stepper)

            # Col 3: Total TTC (Bold font, right aligned)
            it_tot = QTableWidgetItem(f"{format_money(line_tot)} DA")
            it_tot.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_tot.setFont(QFont("Segoe UI", 10, QFont.Bold))
            it_tot.setToolTip(f"Prix unitaire TTC : {format_money(item['unit_price_ttc'])} DA\nTotal ligne : {format_money(line_tot)} DA")
            self.cart_table.setItem(row, 3, it_tot)

            # Col 4: Action Supprimer (Dedicated remove button with vector trash icon)
            del_widget = CartRemoveCellWidget(on_remove=lambda i=idx: self._remove_cart_line(i))
            self.cart_table.setCellWidget(row, 4, del_widget)

        self.lbl_total.setText(f"{format_money(total_ttc)} DA")
        self._adjust_cart_column_widths()

    def _remove_cart_line(self, index: int) -> None:
        """Removes a specific line item from the active session cart."""
        if self._active_session_id in self._sessions:
            cart = self._sessions[self._active_session_id]["cart"]
            if 0 <= index < len(cart):
                del cart[index]
                self._refresh_cart_ui()
                self._update_tab_label(self._active_session_id)

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
                sim_prefixes = {
                    "BON_C": "1-BC",
                    "BON_CREDIT": "2-BCR",
                    "BON_LIVRAISON": "3-BLV",
                }
                pfx = sim_prefixes.get(bond_type, "1-BC")
                res = {
                    "success": True,
                    "order_id": 900,
                    "order_number": f"{pfx}-SIM-900",
                    "bond_type": bond_type,
                    "total_ttc": float(total_val),
                    "scanner_session_id": self._active_session_id,
                }

            order_num = res["order_number"]
            total_ttc = res["total_ttc"]

            client_label = self.cbo_client.currentText().split("  —  ")[0].strip() or "Client Comptoir"
            bon_snapshot = {
                "Order_ID": res.get("order_id"),
                "Order_Number": order_num,
                "Client_ID": client_id,
                "Client_Name": client_label,
                "Bond_Type": bond_type,
                "Total_Amount_TTC": total_ttc,
                "Delivery_Address": deliv_addr or "",
                "lines": [
                    {
                        "Product_ID": it["product_id"],
                        "Product_Name": it.get("name", ""),
                        "Brand_Mark": it.get("mark", ""),
                        "Color_Finish": it.get("coloure", "Standard"),
                        "Quantity_Ordered": it["quantity"],
                        "Unit_Price_TTC": it["unit_price_ttc"],
                        "Line_Total_TTC": float(it["unit_price_ttc"]) * int(it["quantity"]),
                    }
                    for it in cart
                ],
            }
            self._last_created_bon = bon_snapshot

            if bond_type == "BON_C":
                self.bonCGenerated.emit(res)
                title_txt = "Bon Comptant Créé"
                msg_txt = f"Bon Comptant ({order_num}) enregistré — {format_money(total_ttc)} DA."
            elif bond_type == "BON_CREDIT":
                self.bonCreditRequested.emit(res)
                title_txt = "Bon Crédit Créé"
                msg_txt = f"Bon Crédit ({order_num}) transmis en Caisse — {format_money(total_ttc)} DA."
            else:
                self.bonLivraisonGenerated.emit(res)
                title_txt = "Bon de Livraison Créé"
                msg_txt = f"Bon de Livraison ({order_num}) enregistré — {format_money(total_ttc)} DA."

            if os.environ.get("PYTEST_CURRENT_TEST"):
                QMessageBox.information(self, title_txt, msg_txt)
            else:
                box = QMessageBox(self)
                box.setWindowTitle(title_txt)
                box.setIcon(QMessageBox.Information)
                box.setText(msg_txt)
                btn_pdf = box.addButton("Exporter PDF", QMessageBox.ActionRole)
                box.addButton("Fermer", QMessageBox.AcceptRole)
                box.exec()
                if box.clickedButton() == btn_pdf:
                    export_order_bon_to_pdf(self.data_manager, bon_snapshot, parent_widget=self)

            self._clear_current_cart()
            self.txt_delivery_addr.clear()
            self.refresh_catalog()
        except Exception as err:
            QMessageBox.critical(self, "Erreur Création Bon", f"Impossible de créer le bon :\n{err}")

    def _open_daily_bons_dialog(self) -> None:
        """Opens the minimalist dialog listing today's Bons and all unclosed BL vouchers."""
        dlg = OrderDeskBonsDialog(
            data_manager=self.data_manager,
            catalog_items=getattr(self, "_catalog_cache", None),
            clients_list=getattr(self, "_clients_cache", None),
            parent=self,
        )
        dlg.exec()
        if dlg.was_modified:
            self.refresh_catalog()
