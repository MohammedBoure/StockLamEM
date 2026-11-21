# -*- coding: utf-8 -*-
"""
ui/widgets/appliance_desks/_theme.py
====================================
Shared Enterprise UI & UX Design System for the Bureaux Opérationnels workspace
(Commandes, Caisse, Sortie Magasin, and Modal Dialogs).
"""

from ui.theme_tokens import (
    BRAND_TEAL,
    BRAND_TEAL_ALT,
    BRAND_TEAL_HOVER,
    BRAND_TEAL_PRESSED,
    BRAND_TEAL_TINT,
    BRAND_TEAL_BORDER,
    CANVAS_BG,
    CARD_BG,
    SUBTLE_BG,
    BORDER_SUBTLE,
    BORDER_CONTROL,
    TEXT_PRIMARY,
    TEXT_BODY,
    TEXT_MUTED,
    STATUS_SUCCESS,
    STATUS_SUCCESS_BG,
    STATUS_SUCCESS_BORDER,
    STATUS_INFO,
    STATUS_INFO_BG,
    STATUS_INFO_BORDER,
    STATUS_WARN,
    STATUS_WARN_BG,
    STATUS_WARN_BORDER,
    STATUS_DANGER,
    STATUS_DANGER_BG,
    STATUS_DANGER_BORDER,
    CLEAN_TABLE_QSS as BUREAUX_TABLE_QSS,
    INPUT_QSS,
    COMBO_QSS,
    FILTER_CHIP_QSS,
    PRIMARY_CTA_QSS,
    SECONDARY_OUTLINE_QSS,
    SLATE_OUTLINE_QSS,
    DANGER_OUTLINE_QSS,
    AMBER_OUTLINE_QSS,
    SPLITTER_QSS,
    CHECKBOX_QSS,
)

# ---------------------------------------------------------------------------
# Bond Type Badge Metadata
# ---------------------------------------------------------------------------
BOND_TYPE_BADGES = {
    "BON_C": {
        "label": "Paiement complet",
        "short": "Paiement complet",
        "fg": BRAND_TEAL,
        "bg": BRAND_TEAL_TINT,
        "border": BRAND_TEAL_BORDER,
    },
    "BON_CREDIT": {
        "label": "Paiement à crédit",
        "short": "Paiement à crédit",
        "fg": STATUS_INFO,
        "bg": STATUS_INFO_BG,
        "border": STATUS_INFO_BORDER,
    },
    "BON_LIVRAISON": {
        "label": "Paiement à la livraison",
        "short": "Paiement à la livraison",
        "fg": STATUS_WARN,
        "bg": STATUS_WARN_BG,
        "border": STATUS_WARN_BORDER,
    },
    "BON_VERSEMENT": {
        "label": "Versement",
        "short": "Versement",
        "fg": STATUS_SUCCESS,
        "bg": STATUS_SUCCESS_BG,
        "border": STATUS_SUCCESS_BORDER,
    },
}

DIALOG_BASE_QSS = f"""
    QDialog {{
        background-color: {CARD_BG};
        color: {TEXT_PRIMARY};
    }}
    QLabel {{
        border: none;
        background: transparent;
    }}
    {CHECKBOX_QSS}
"""
