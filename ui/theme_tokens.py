# -*- coding: utf-8 -*-
"""Shared StockLam Enterprise UI & UX design tokens and scoped stylesheet helpers.

Single source of truth for surface colors, brand teal accents, status palettes,
reusable control QSS, and `#ObjectName`-scoped containers across all workspaces.
"""

from pathlib import Path

_CHECK_ICON_PATH = (
    Path(__file__).resolve().parent / "assets" / "icons" / "check_white.svg"
).as_posix()

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
SURFACE_MUTED = "#F1F5F9"
BORDER_SUBTLE = "#DDE3EA"
BORDER_HAIRLINE = "#E2E8F0"
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

TONE_PALETTES = {
    "brand": (BRAND_TEAL_ALT, BRAND_TEAL_TINT, BRAND_TEAL_BORDER),
    "info": (STATUS_INFO, STATUS_INFO_BG, STATUS_INFO_BORDER),
    "success": (STATUS_SUCCESS, STATUS_SUCCESS_BG, STATUS_SUCCESS_BORDER),
    "warn": (STATUS_WARN, STATUS_WARN_BG, STATUS_WARN_BORDER),
    "danger": (STATUS_DANGER, STATUS_DANGER_BG, STATUS_DANGER_BORDER),
}

# ---------------------------------------------------------------------------
# Reusable Leaf-Control & Table Stylesheets
# ---------------------------------------------------------------------------
CLEAN_TABLE_QSS = f"""
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
        color: #475569;
        border: 1px solid {BORDER_CONTROL};
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
        background-color: #F1F5F9;
        color: #475569;
        border: 1px solid {BORDER_CONTROL};
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
        background-color: #F1F5F9;
        color: #475569;
        border: 1px solid {BORDER_CONTROL};
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
        background-color: #F1F5F9;
        color: #475569;
        border: 1px solid {BORDER_CONTROL};
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
        background-color: #F1F5F9;
        color: #475569;
        border: 1px solid {BORDER_CONTROL};
    }}
"""

SPLITTER_QSS = f"""
    QSplitter::handle {{
        background-color: {BORDER_HAIRLINE};
        width: 6px;
        margin: 6px 2px;
        border-radius: 3px;
    }}
    QSplitter::handle:hover {{
        background-color: {BRAND_TEAL};
    }}
"""

CHECKBOX_QSS = f"""
    QCheckBox {{
        spacing: 8px;
        color: {TEXT_PRIMARY};
        background: transparent;
    }}
    QCheckBox:disabled {{
        color: {TEXT_MUTED};
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border-radius: 4px;
        border: 1.5px solid {TEXT_MUTED};
        background-color: {CARD_BG};
    }}
    QCheckBox::indicator:hover:enabled {{
        border-color: {BRAND_TEAL};
        background-color: #F0FDFA;
    }}
    QCheckBox::indicator:checked {{
        background-color: {BRAND_TEAL};
        border: 1.5px solid {BRAND_TEAL};
        image: url({_CHECK_ICON_PATH});
    }}
    QCheckBox::indicator:checked:hover:enabled {{
        background-color: {BRAND_TEAL_HOVER};
        border-color: {BRAND_TEAL_HOVER};
    }}
    QCheckBox::indicator:disabled {{
        background-color: #F1F5F9;
        border: 1.5px solid #94A3B8;
    }}
    QCheckBox::indicator:checked:disabled {{
        background-color: #94A3B8;
        border: 1.5px solid #94A3B8;
        image: url({_CHECK_ICON_PATH});
    }}
"""

FLAT_SUBTABS_QSS = f"""
    QTabWidget::pane {{
        border: none;
        border-top: 1px solid {BORDER_HAIRLINE};
        background: {CANVAS_BG};
    }}
    QTabBar::tab {{
        background: transparent;
        color: {TEXT_MUTED};
        border: none;
        border-bottom: 2px solid transparent;
        padding: 8px 14px;
        font-weight: 600;
        font-size: 12.5px;
    }}
    QTabBar::tab:selected {{
        color: {BRAND_TEAL};
        border-bottom: 2px solid {BRAND_TEAL};
        font-weight: 700;
    }}
    QTabBar::tab:hover:!selected {{
        color: {TEXT_PRIMARY};
        background: {SURFACE_MUTED};
    }}
"""


def scoped_card_qss(
    obj_name: str,
    *,
    bg: str = CARD_BG,
    border: str = BORDER_HAIRLINE,
    radius: int = 8,
    left_accent: str | None = None,
) -> str:
    """Return `#ObjectName`-scoped card QSS preventing style leakage to child widgets."""
    accent_rule = f"border-left: 3px solid {left_accent};" if left_accent else ""
    return (
        f"QFrame#{obj_name} {{ background-color: {bg}; border: 1px solid {border}; "
        f"border-radius: {radius}px; {accent_rule} }}"
        f"QFrame#{obj_name} QLabel {{ border: none; background: transparent; }}"
    )


def scoped_banner_qss(obj_name: str, tone: str = "info", radius: int = 8) -> str:
    """Return `#ObjectName`-scoped status banner QSS for info/warn/success/danger/brand."""
    fg, bg, border = TONE_PALETTES.get(tone, TONE_PALETTES["info"])
    return (
        f"QFrame#{obj_name} {{ background-color: {bg}; border: 1px solid {border}; "
        f"border-left: 3px solid {fg}; border-radius: {radius}px; }}"
        f"QFrame#{obj_name} QLabel {{ color: {fg}; border: none; background: transparent; }}"
    )


def scoped_dialog_qss(obj_name: str, bg: str = SUBTLE_BG) -> str:
    """Return `#ObjectName`-scoped dialog stylesheet keeping controls consistent and leak-free."""
    return (
        f"QDialog#{obj_name} {{ background-color: {bg}; color: {TEXT_PRIMARY}; }}"
        f"QDialog#{obj_name} QLabel {{ border: none; background: transparent; }}"
        f"QDialog#{obj_name} QGroupBox {{ background-color: {CARD_BG}; "
        f"border: 1px solid {BORDER_HAIRLINE}; border-radius: 8px; "
        f"margin-top: 16px; padding-top: 12px; font-weight: 700; color: {TEXT_PRIMARY}; }}"
        f"QDialog#{obj_name} QGroupBox::title {{ subcontrol-origin: margin; "
        f"subcontrol-position: top left; left: 12px; padding: 0 6px; color: {BRAND_TEAL}; }}"
        f"{CHECKBOX_QSS}"
    )


def set_enabled_with_reason(
    widget,
    enabled: bool,
    disabled_reason: str = "",
    enabled_tooltip: str = "",
) -> None:
    """Enable/disable a control while guaranteeing a clear explanatory tooltip when disabled."""
    widget.setEnabled(enabled)
    if enabled:
        if enabled_tooltip is not None:
            widget.setToolTip(enabled_tooltip)
    elif disabled_reason:
        widget.setToolTip(disabled_reason)
