# -*- coding: utf-8 -*-
"""
ui/widgets/appliance_desks/_theme.py
====================================
Shared Enterprise UI & UX Design System for the Bureaux Opérationnels workspace
(Commandes, Caisse, Sortie Magasin, and Modal Dialogs).
"""

# ---------------------------------------------------------------------------
# Color & Typography Tokens
# ---------------------------------------------------------------------------
BRAND_TEAL = "#007572"
BRAND_TEAL_ALT = "#0E7471"
BRAND_TEAL_HOVER = "#005A57"
BRAND_TEAL_PRESSED = "#003D3A"
BRAND_TEAL_TINT = "#E6F4F1"
BRAND_TEAL_BORDER = "#A7DFD9"

CANVAS_BG = "#F5F7FA"
CARD_BG = "#FFFFFF"
SUBTLE_BG = "#F8FAFC"
BORDER_SUBTLE = "#DDE3EA"
BORDER_CONTROL = "#CBD5E1"

TEXT_PRIMARY = "#0F172A"
TEXT_BODY = "#334155"
TEXT_MUTED = "#64748B"

STATUS_SUCCESS = "#047857"
STATUS_SUCCESS_BG = "#ECFDF5"
STATUS_SUCCESS_BORDER = "#A7F3D0"

STATUS_INFO = "#1D4ED8"
STATUS_INFO_BG = "#EFF6FF"
STATUS_INFO_BORDER = "#BFDBFE"

STATUS_WARN = "#B45309"
STATUS_WARN_BG = "#FFFBEB"
STATUS_WARN_BORDER = "#FDE68A"

STATUS_DANGER = "#DC2626"
STATUS_DANGER_BG = "#FEF2F2"
STATUS_DANGER_BORDER = "#FCA5A5"

# ---------------------------------------------------------------------------
# Bond Type Badge Metadata
# ---------------------------------------------------------------------------
BOND_TYPE_BADGES = {
    "BON_C": {
        "label": "Bon Comptant",
        "short": "Comptant",
        "fg": BRAND_TEAL,
        "bg": BRAND_TEAL_TINT,
        "border": BRAND_TEAL_BORDER,
    },
    "BON_CREDIT": {
        "label": "Bon Crédit",
        "short": "Crédit",
        "fg": STATUS_INFO,
        "bg": STATUS_INFO_BG,
        "border": STATUS_INFO_BORDER,
    },
    "BON_LIVRAISON": {
        "label": "Bon de Livraison",
        "short": "Livraison",
        "fg": STATUS_WARN,
        "bg": STATUS_WARN_BG,
        "border": STATUS_WARN_BORDER,
    },
    "BON_VERSEMENT": {
        "label": "Bon Versement",
        "short": "Versement",
        "fg": STATUS_SUCCESS,
        "bg": STATUS_SUCCESS_BG,
        "border": STATUS_SUCCESS_BORDER,
    },
}

# ---------------------------------------------------------------------------
# Scoped Reusable Stylesheets
# ---------------------------------------------------------------------------
BUREAUX_TABLE_QSS = f"""
    QTableWidget {{
        background-color: {CARD_BG};
        alternate-background-color: {SUBTLE_BG};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: 6px;
        gridline-color: #EEF2F6;
        color: {TEXT_PRIMARY};
        font-size: 12px;
        selection-background-color: {BRAND_TEAL_TINT};
        selection-color: {TEXT_PRIMARY};
        outline: 0;
    }}
    QTableWidget::item {{
        padding: 4px 8px;
        border-bottom: 1px solid #F1F5F9;
    }}
    QTableWidget::item:selected {{
        background-color: {BRAND_TEAL_TINT};
        color: {TEXT_PRIMARY};
    }}
    QTableWidget::item:hover:!selected {{
        background-color: #F8FAFC;
    }}
    QHeaderView::section {{
        background-color: {SUBTLE_BG};
        color: #1E293B;
        font-weight: 700;
        font-size: 11.5px;
        border: none;
        border-right: 1px solid #E2E8F0;
        border-bottom: 2px solid {BRAND_TEAL};
        padding: 6px 8px;
    }}
    QHeaderView::section:last {{
        border-right: none;
    }}
    QScrollBar:horizontal {{
        border: none;
        background: #F1F5F9;
        height: 8px;
        margin: 0px;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal {{
        background: {BRAND_TEAL};
        min-width: 36px;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {BRAND_TEAL_HOVER}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; height: 0px; }}
    QScrollBar:vertical {{
        border: none;
        background: #F1F5F9;
        width: 8px;
        margin: 0px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: {BRAND_TEAL};
        min-height: 36px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {BRAND_TEAL_HOVER}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ width: 0px; height: 0px; }}
"""

INPUT_QSS = f"""
    QLineEdit {{
        background-color: {CARD_BG};
        border: 1px solid {BORDER_CONTROL};
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 12.5px;
        color: {TEXT_PRIMARY};
    }}
    QLineEdit:hover {{
        border-color: #94A3B8;
    }}
    QLineEdit:focus {{
        border: 1.5px solid {BRAND_TEAL};
        background-color: {CARD_BG};
    }}
"""

COMBO_QSS = f"""
    QComboBox {{
        background-color: {CARD_BG};
        border: 1px solid {BORDER_CONTROL};
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 12.5px;
        color: {TEXT_PRIMARY};
    }}
    QComboBox:hover {{
        border-color: #94A3B8;
    }}
    QComboBox:focus {{
        border: 1.5px solid {BRAND_TEAL};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 22px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {CARD_BG};
        border: 1px solid {BORDER_CONTROL};
        border-radius: 6px;
        selection-background-color: {BRAND_TEAL_TINT};
        selection-color: {BRAND_TEAL};
        padding: 4px;
        font-size: 12px;
        color: {TEXT_PRIMARY};
    }}
"""

FILTER_CHIP_QSS = f"""
    QPushButton {{
        background-color: {SUBTLE_BG};
        color: {TEXT_BODY};
        border: 1px solid {BORDER_CONTROL};
        border-radius: 6px;
        padding: 4px 11px;
        font-size: 11.5px;
        font-weight: 700;
    }}
    QPushButton:hover {{
        border-color: {BRAND_TEAL};
        color: {BRAND_TEAL};
        background-color: #F0FDFA;
    }}
    QPushButton:checked {{
        background-color: {BRAND_TEAL};
        color: #FFFFFF;
        border-color: {BRAND_TEAL};
    }}
"""

PRIMARY_CTA_QSS = f"""
    QPushButton {{
        background-color: {BRAND_TEAL};
        color: #FFFFFF;
        font-weight: 700;
        font-size: 12.5px;
        padding: 0 16px;
        border-radius: 6px;
        border: 1px solid {BRAND_TEAL_HOVER};
    }}
    QPushButton:hover:enabled {{
        background-color: {BRAND_TEAL_HOVER};
        border-color: {BRAND_TEAL_PRESSED};
    }}
    QPushButton:pressed:enabled {{
        background-color: {BRAND_TEAL_PRESSED};
    }}
    QPushButton:disabled {{
        background-color: #F1F5F9;
        color: #94A3B8;
        border-color: {BORDER_CONTROL};
    }}
"""

SECONDARY_OUTLINE_QSS = f"""
    QPushButton {{
        background-color: {CARD_BG};
        color: {BRAND_TEAL};
        border: 1.5px solid {BRAND_TEAL};
        font-weight: 700;
        font-size: 12px;
        padding: 0 14px;
        border-radius: 6px;
    }}
    QPushButton:hover:enabled {{
        background-color: {BRAND_TEAL_TINT};
        border-color: {BRAND_TEAL_HOVER};
        color: {BRAND_TEAL_HOVER};
    }}
    QPushButton:pressed:enabled {{
        background-color: #CCEBE6;
    }}
    QPushButton:disabled {{
        background-color: {SUBTLE_BG};
        color: #94A3B8;
        border-color: {BORDER_CONTROL};
    }}
"""

SLATE_OUTLINE_QSS = f"""
    QPushButton {{
        background-color: {CARD_BG};
        color: {TEXT_BODY};
        border: 1px solid {BORDER_CONTROL};
        font-weight: 700;
        font-size: 12px;
        padding: 0 12px;
        border-radius: 6px;
    }}
    QPushButton:hover:enabled {{
        background-color: #F1F5F9;
        border-color: #94A3B8;
        color: {TEXT_PRIMARY};
    }}
    QPushButton:pressed:enabled {{
        background-color: #E2E8F0;
    }}
    QPushButton:disabled {{
        background-color: {SUBTLE_BG};
        color: #94A3B8;
    }}
"""

DANGER_OUTLINE_QSS = f"""
    QPushButton {{
        background-color: {CARD_BG};
        color: {STATUS_DANGER};
        border: 1px solid {STATUS_DANGER_BORDER};
        font-weight: 700;
        font-size: 12px;
        padding: 0 12px;
        border-radius: 6px;
    }}
    QPushButton:hover:enabled {{
        background-color: {STATUS_DANGER_BG};
        border-color: #EF4444;
        color: #B91C1C;
    }}
    QPushButton:pressed:enabled {{
        background-color: #FEE2E2;
    }}
    QPushButton:disabled {{
        background-color: {SUBTLE_BG};
        color: #94A3B8;
        border-color: {BORDER_CONTROL};
    }}
"""

AMBER_OUTLINE_QSS = f"""
    QPushButton {{
        background-color: {CARD_BG};
        color: {STATUS_WARN};
        border: 1.5px solid #D97706;
        font-weight: 700;
        font-size: 12px;
        padding: 0 14px;
        border-radius: 6px;
    }}
    QPushButton:hover:enabled {{
        background-color: #FEF3C7;
        border-color: {STATUS_WARN};
    }}
    QPushButton:pressed:enabled {{
        background-color: #FDE68A;
    }}
    QPushButton:disabled {{
        background-color: {SUBTLE_BG};
        color: #94A3B8;
        border-color: {BORDER_CONTROL};
    }}
"""

SPLITTER_QSS = f"""
    QSplitter::handle {{
        background-color: #E2E8F0;
        width: 6px;
        margin: 6px 2px;
        border-radius: 3px;
    }}
    QSplitter::handle:hover {{
        background-color: {BRAND_TEAL};
    }}
"""

DIALOG_BASE_QSS = f"""
    QDialog {{
        background-color: {CARD_BG};
        color: {TEXT_PRIMARY};
    }}
    QLabel {{
        border: none;
        background: transparent;
    }}
"""
