# ui/icons.py
"""Dual-tone vector icons generator matching the modern outline & flat color aesthetic."""

from typing import Dict, Optional
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QIcon
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtSvg import QSvgRenderer

_icon_cache: Dict[str, QIcon] = {}

DUOTONE_SVGS: Dict[str, str] = {
    # 0: Tableau de Bord (Dashboard)
    "dashboard": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <rect x="4" y="4" width="10" height="13" rx="2" fill="#E6F4F1" stroke="#007572" stroke-width="2"/>
        <rect x="18" y="4" width="10" height="7" rx="2" fill="#F8FAFC" stroke="#1E293B" stroke-width="2"/>
        <rect x="18" y="15" width="10" height="13" rx="2" fill="#E6F4F1" stroke="#007572" stroke-width="2"/>
        <rect x="4" y="21" width="10" height="7" rx="2" fill="#F8FAFC" stroke="#1E293B" stroke-width="2"/>
    </svg>''',

    # 1: Données de Base (Master Data)
    "master_data": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <ellipse cx="16" cy="7" rx="11" ry="4" fill="#E6F4F1" stroke="#007572" stroke-width="2"/>
        <path d="M5 7v9c0 2.2 4.9 4 11 4s11-1.8 11-4V7" fill="none" stroke="#1E293B" stroke-width="2"/>
        <path d="M5 16v9c0 2.2 4.9 4 11 4s11-1.8 11-4v-9" fill="none" stroke="#007572" stroke-width="2"/>
        <line x1="10" y1="13" x2="14" y2="13" stroke="#1E293B" stroke-width="2" stroke-linecap="round"/>
        <line x1="10" y1="22" x2="14" y2="22" stroke="#007572" stroke-width="2" stroke-linecap="round"/>
    </svg>''',

    # 2: Achats & Entrées (Procurement)
    "procurement": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <path d="M7 4h18l3 7v15a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V11l3-7z" fill="#E6F4F1" stroke="#007572" stroke-width="2" stroke-linejoin="round"/>
        <line x1="4" y1="11" x2="28" y2="11" stroke="#1E293B" stroke-width="2"/>
        <path d="M21 16a5 5 0 0 1-10 0" fill="none" stroke="#007572" stroke-width="2" stroke-linecap="round"/>
    </svg>''',

    # 3: Stock & Magasin (Inventory)
    "inventory": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <rect x="4" y="6" width="24" height="20" rx="2" fill="#F8FAFC" stroke="#1E293B" stroke-width="2"/>
        <line x1="4" y1="16" x2="28" y2="16" stroke="#1E293B" stroke-width="2"/>
        <rect x="7" y="9" width="7" height="5" rx="1" fill="#E6F4F1" stroke="#007572" stroke-width="1.8"/>
        <rect x="18" y="9" width="7" height="5" rx="1" fill="#F8FAFC" stroke="#1E293B" stroke-width="1.8"/>
        <rect x="7" y="19" width="8" height="5" rx="1" fill="#E6F4F1" stroke="#007572" stroke-width="1.8"/>
        <rect x="18" y="19" width="6" height="5" rx="1" fill="#F8FAFC" stroke="#1E293B" stroke-width="1.8"/>
    </svg>''',

    # 6: Sous-Traitants (Partners)
    "services": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <circle cx="12" cy="11" r="5" fill="#E6F4F1" stroke="#007572" stroke-width="2"/>
        <path d="M4 27v-3a6 6 0 0 1 12 0v3" fill="none" stroke="#1E293B" stroke-width="2"/>
        <circle cx="23" cy="12" r="3.5" fill="#F8FAFC" stroke="#1E293B" stroke-width="1.8"/>
        <path d="M20 25a5 5 0 0 1 8 0" fill="none" stroke="#1E293B" stroke-width="1.8"/>
    </svg>''',

    # 8: Réclamations (Alerts)
    "reclamations": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <path d="M16 4L29 27H3L16 4z" fill="#FEF2F2" stroke="#DC2626" stroke-width="2" stroke-linejoin="round"/>
        <line x1="16" y1="12" x2="16" y2="19" stroke="#DC2626" stroke-width="2.2" stroke-linecap="round"/>
        <circle cx="16" cy="23" r="1.3" fill="#DC2626"/>
    </svg>''',

    # 9: Inventaire (Stock Count)
    "inventaire": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <rect x="6" y="5" width="20" height="23" rx="2" fill="#F8FAFC" stroke="#1E293B" stroke-width="2"/>
        <rect x="11" y="2" width="10" height="5" rx="1.5" fill="#E6F4F1" stroke="#007572" stroke-width="1.8"/>
        <path d="M10 13l3 3 6-6" fill="none" stroke="#007572" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <line x1="10" y1="21" x2="22" y2="21" stroke="#1E293B" stroke-width="2" stroke-linecap="round"/>
    </svg>''',

    # 10: Point de Vente (POS)
    "pos": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <rect x="4" y="6" width="24" height="15" rx="2" fill="#E6F4F1" stroke="#007572" stroke-width="2"/>
        <line x1="4" y1="12" x2="28" y2="12" stroke="#1E293B" stroke-width="2"/>
        <rect x="8" y="16" width="6" height="2" rx="0.5" fill="#007572"/>
        <path d="M6 25h20l2 3H4l2-3z" fill="#F8FAFC" stroke="#1E293B" stroke-width="2" stroke-linejoin="round"/>
    </svg>''',

    # 11: Vente en Gros B2B (Wholesale)
    "wholesale": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <rect x="4" y="8" width="24" height="19" rx="2" fill="#E6F4F1" stroke="#007572" stroke-width="2"/>
        <path d="M4 8l12-5 12 5" fill="none" stroke="#1E293B" stroke-width="2" stroke-linejoin="round"/>
        <line x1="16" y1="3" x2="16" y2="27" stroke="#007572" stroke-width="1.8"/>
        <line x1="10" y1="15" x2="10" y2="21" stroke="#1E293B" stroke-width="2" stroke-linecap="round"/>
        <line x1="22" y1="15" x2="22" y2="21" stroke="#1E293B" stroke-width="2" stroke-linecap="round"/>
    </svg>''',

    # 12: Historique Ventes (Sales History)
    "sales_history": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <rect x="4" y="4" width="24" height="24" rx="2" fill="#F8FAFC" stroke="#1E293B" stroke-width="2"/>
        <polyline points="7 22 13 15 18 19 25 10" fill="none" stroke="#007572" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="25" cy="10" r="2" fill="#007572"/>
    </svg>''',

    # 7: Traçabilité (History & Audit Trail)
    "history": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <circle cx="16" cy="16" r="12" fill="#E6F4F1" stroke="#007572" stroke-width="2"/>
        <polyline points="16 9 16 16 21 18" fill="none" stroke="#1E293B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>''',

    # 5: Utilisateurs (Users)
    "users": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <circle cx="16" cy="10" r="5" fill="#E6F4F1" stroke="#007572" stroke-width="2"/>
        <path d="M6 26v-2a6 6 0 0 1 12 0v2" fill="none" stroke="#1E293B" stroke-width="2"/>
        <path d="M20 18a5 5 0 0 1 6 0v2" fill="none" stroke="#007572" stroke-width="1.8"/>
        <circle cx="23" cy="11" r="3.5" fill="#F8FAFC" stroke="#007572" stroke-width="1.8"/>
    </svg>''',

    # 4: Paramètres (Settings)
    "settings": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <line x1="5" y1="9" x2="27" y2="9" stroke="#1E293B" stroke-width="2" stroke-linecap="round"/>
        <circle cx="12" cy="9" r="3" fill="#E6F4F1" stroke="#007572" stroke-width="2"/>
        <line x1="5" y1="16" x2="27" y2="16" stroke="#1E293B" stroke-width="2" stroke-linecap="round"/>
        <circle cx="20" cy="16" r="3" fill="#E6F4F1" stroke="#007572" stroke-width="2"/>
        <line x1="5" y1="23" x2="27" y2="23" stroke="#1E293B" stroke-width="2" stroke-linecap="round"/>
        <circle cx="10" cy="23" r="3" fill="#E6F4F1" stroke="#007572" stroke-width="2"/>
    </svg>''',

    # Logout (Power / Exit)
    "logout": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <path d="M16 5V15" stroke="#DC2626" stroke-width="2.6" stroke-linecap="round"/>
        <path d="M10 9C6.5 11.2 4.5 15 4.5 19C4.5 25.4 9.6 30.5 16 30.5C22.4 30.5 27.5 25.4 27.5 19C27.5 15 25.5 11.2 22 9" fill="none" stroke="#1E293B" stroke-width="2.6" stroke-linecap="round"/>
    </svg>''',

    # Collapse Sidebar
    "collapse": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <rect x="4" y="6" width="24" height="20" rx="2" fill="#F8FAFC" stroke="#1E293B" stroke-width="2"/>
        <line x1="12" y1="6" x2="12" y2="26" stroke="#1E293B" stroke-width="2"/>
        <path d="M21 13L18 16L21 19" fill="none" stroke="#007572" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>''',

    # Expand Sidebar
    "expand": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <rect x="4" y="6" width="24" height="20" rx="2" fill="#F8FAFC" stroke="#1E293B" stroke-width="2"/>
        <line x1="12" y1="6" x2="12" y2="26" stroke="#1E293B" stroke-width="2"/>
        <path d="M18 13L21 16L18 19" fill="none" stroke="#007572" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>''',

    # Menu Hamburger Toggle
    "menu": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <line x1="6" y1="9" x2="26" y2="9" stroke="#1E293B" stroke-width="2.2" stroke-linecap="round"/>
        <line x1="6" y1="16" x2="26" y2="16" stroke="#007572" stroke-width="2.2" stroke-linecap="round"/>
        <line x1="6" y1="23" x2="26" y2="23" stroke="#1E293B" stroke-width="2.2" stroke-linecap="round"/>
    </svg>''',

    # Trash / Delete action
    "trash": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <path d="M7 9h18v17a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2V9z" fill="#FEF2F2" stroke="#DC2626" stroke-width="2" stroke-linejoin="round"/>
        <line x1="4" y1="9" x2="28" y2="9" stroke="#DC2626" stroke-width="2" stroke-linecap="round"/>
        <path d="M11 9V5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v4" fill="none" stroke="#DC2626" stroke-width="2" stroke-linejoin="round"/>
        <line x1="13" y1="14" x2="13" y2="23" stroke="#DC2626" stroke-width="1.8" stroke-linecap="round"/>
        <line x1="19" y1="14" x2="19" y2="23" stroke="#DC2626" stroke-width="1.8" stroke-linecap="round"/>
    </svg>''',

    # 13: Créances Clients (Debts & Receivables)
    "debts": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <rect x="5" y="4" width="22" height="24" rx="2" fill="#E6F4F1" stroke="#0E7471" stroke-width="2"/>
        <line x1="9" y1="10" x2="23" y2="10" stroke="#1E293B" stroke-width="2" stroke-linecap="round"/>
        <line x1="9" y1="15" x2="23" y2="15" stroke="#1E293B" stroke-width="2" stroke-linecap="round"/>
        <line x1="9" y1="20" x2="16" y2="20" stroke="#0E7471" stroke-width="2" stroke-linecap="round"/>
        <circle cx="22" cy="22" r="5" fill="#FFFFFF" stroke="#0E7471" stroke-width="2"/>
        <text x="22" y="25" font-family="sans-serif" font-size="7" font-weight="bold" fill="#0E7471" text-anchor="middle">D</text>
    </svg>''',

    # KPI & Debts Specific Vector Icons
    "kpi_wallet": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#0E7471" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="2" y="5" width="20" height="14" rx="2" fill="#E6F4F1"/>
        <line x1="2" y1="10" x2="22" y2="10"/>
        <circle cx="17" cy="14" r="1.5" fill="#0E7471"/>
    </svg>''',

    "kpi_overdue": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#DC2626" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="9" fill="#FEF2F2"/>
        <polyline points="12 7 12 12 15 15"/>
    </svg>''',

    "kpi_debtors": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#475569" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" fill="#F1F5F9"/>
        <circle cx="9" cy="7" r="4"/>
        <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
        <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
    </svg>''',

    "kpi_recovered": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#16A34A" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="9" fill="#F0FDF4"/>
        <polyline points="8 12 11 15 16 9"/>
    </svg>''',

    "empty_invoices": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none" stroke="#94A3B8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="16" y="8" width="32" height="48" rx="4" fill="#F8FAFC" stroke="#CBD5E1"/>
        <line x1="24" y1="20" x2="40" y2="20" stroke="#CBD5E1"/>
        <line x1="24" y1="28" x2="36" y2="28" stroke="#CBD5E1"/>
        <circle cx="32" cy="42" r="9" fill="#E6F4F1" stroke="#0E7471"/>
        <polyline points="28 42 31 45 36 39" stroke="#0E7471" stroke-width="2.5"/>
    </svg>''',

    "success_circle": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" fill="none">
        <circle cx="24" cy="24" r="22" fill="#DCFCE7" stroke="#16A34A" stroke-width="2"/>
        <polyline points="15 25 21 31 33 17" fill="none" stroke="#16A34A" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>''',

    "client_select": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" fill="none">
        <circle cx="24" cy="24" r="22" fill="#E6F4F1" stroke="#0E7471" stroke-width="2"/>
        <circle cx="24" cy="18" r="6" stroke="#0E7471" stroke-width="2.5" fill="#FFFFFF"/>
        <path d="M14 36c0-5.523 4.477-10 10-10s10 4.477 10 10" stroke="#0E7471" stroke-width="2.5" stroke-linecap="round"/>
    </svg>''',

    "filter": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#0E7471" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
    </svg>''',

    "refresh": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#0E7471" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="23 4 23 10 17 10"/>
        <polyline points="1 20 1 14 7 14"/>
        <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
    </svg>''',

    "refresh_white": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="23 4 23 10 17 10"/>
        <polyline points="1 20 1 14 7 14"/>
        <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
    </svg>''',

    "export": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#334155" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
        <polyline points="7 10 12 15 17 10"/>
        <line x1="12" y1="15" x2="12" y2="3"/>
    </svg>''',

    "payment": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#0E7471" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="1" y="4" width="22" height="16" rx="2" fill="#E6F4F1"/>
        <line x1="1" y1="10" x2="23" y2="10"/>
    </svg>''',

    "payment_white": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="2" y="5" width="20" height="14" rx="2"/>
        <line x1="2" y1="10" x2="22" y2="10"/>
        <rect x="5" y="14" width="4" height="2" fill="#FFFFFF"/>
    </svg>''',

    "statement": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#0E7471" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <line x1="16" y1="13" x2="8" y2="13"/>
        <line x1="16" y1="17" x2="8" y2="17"/>
        <line x1="10" y1="9" x2="8" y2="9"/>
    </svg>''',

    "audit": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#0E7471" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="8"/>
        <line x1="21" y1="21" x2="16.65" y2="16.65"/>
        <line x1="11" y1="8" x2="11" y2="14"/>
        <line x1="8" y1="11" x2="14" y2="11"/>
    </svg>''',

    "print": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#334155" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="6 9 6 2 18 2 18 9"/>
        <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/>
        <rect x="6" y="14" width="12" height="8"/>
    </svg>''',

    "fifo_alloc": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M4 6h16M4 12h10M4 18h14"/>
        <polyline points="15 9 18 12 15 15"/>
    </svg>''',

    "alert_warning": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#DC2626" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" fill="#FEF2F2"/>
        <line x1="12" y1="9" x2="12" y2="13"/>
        <circle cx="12" cy="17" r="1" fill="#DC2626"/>
    </svg>''',

    "edit_lots": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#0E7471" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" fill="#E6F4F1"/>
        <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
        <line x1="12" y1="22.08" x2="12" y2="12"/>
    </svg>''',

    "barcode_scan": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#0E7471" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 7V5a2 2 0 0 1 2-2h2"/>
        <path d="M17 3h2a2 2 0 0 1 2 2v2"/>
        <path d="M21 17v2a2 2 0 0 1-2 2h-2"/>
        <path d="M7 21H5a2 2 0 0 1-2-2v-2"/>
        <line x1="7" y1="8" x2="7" y2="16" stroke="#1E293B"/>
        <line x1="10" y1="8" x2="10" y2="16"/>
        <line x1="14" y1="8" x2="14" y2="16" stroke="#1E293B"/>
        <line x1="17" y1="8" x2="17" y2="16"/>
    </svg>''',

    "wrench_sav": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#0E7471" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" fill="#E6F4F1"/>
    </svg>''',

    "truck_delivery": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#0E7471" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="1" y="3" width="15" height="13" rx="1" fill="#E6F4F1"/>
        <polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/>
        <circle cx="5.5" cy="18.5" r="2.5" stroke="#1E293B"/>
        <circle cx="18.5" cy="18.5" r="2.5" stroke="#1E293B"/>
    </svg>''',

    "shield_admin": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#0E7471" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" fill="#E6F4F1"/>
        <polyline points="9 12 11 14 15 10"/>
    </svg>''',

    "return_arrow": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#0E7471" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="9 14 4 9 9 4"/>
        <path d="M20 20v-7a4 4 0 0 0-4-4H4"/>
    </svg>''',
}

def get_duotone_icon(
    name: str,
    arg1: Optional[object] = None,
    arg2: Optional[str] = None,
    size: int = 64,
) -> QIcon:
    """Returns a cached high-resolution QIcon in the dual-tone illustration theme."""
    if isinstance(arg1, int):
        size = arg1
    cache_key = f"{name}_{size}"
    if cache_key in _icon_cache:
        return _icon_cache[cache_key]

    svg_content = DUOTONE_SVGS.get(name)
    if not svg_content:
        return QIcon()

    renderer = QSvgRenderer(QByteArray(svg_content.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    renderer.render(painter)
    painter.end()

    icon = QIcon(pixmap)
    _icon_cache[cache_key] = icon
    return icon

def get_reclamation_icon() -> QIcon:
    """Compatibility helper for existing reclamation views."""
    return get_duotone_icon("reclamations", 32)

def get_trash_icon(size: int = 24) -> QIcon:
    """Returns a vector trash / delete icon."""
    return get_duotone_icon("trash", size)

def get_warning_icon(size: int = 24) -> QIcon:
    """Returns a vector warning / alert icon."""
    return get_duotone_icon("alert_warning", size)

def get_edit_lots_icon(size: int = 24) -> QIcon:
    """Returns a vector edit lots / box icon."""
    return get_duotone_icon("edit_lots", size)
