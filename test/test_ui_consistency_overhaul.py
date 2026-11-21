# -*- coding: utf-8 -*-
"""Regression tests verifying the comprehensive StockLam UI consistency overhaul."""

import pathlib
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

from ui.theme_tokens import (
    BRAND_TEAL,
    CANVAS_BG,
    CARD_BG,
    CLEAN_TABLE_QSS,
    DANGER_OUTLINE_QSS,
    PRIMARY_CTA_QSS,
    SLATE_OUTLINE_QSS,
    scoped_banner_qss,
    scoped_card_qss,
    scoped_dialog_qss,
    set_enabled_with_reason,
)

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_theme_tokens_and_scoped_helpers(qapp):
    assert BRAND_TEAL == "#007572"
    assert CANVAS_BG == "#F5F7FA"
    assert CARD_BG == "#FFFFFF"
    assert "QHeaderView::section" in CLEAN_TABLE_QSS
    assert "#007572" in PRIMARY_CTA_QSS
    assert "#DC2626" in DANGER_OUTLINE_QSS
    assert "#CBD5E1" in SLATE_OUTLINE_QSS

    card_qss = scoped_card_qss("DemoCard")
    assert "QFrame#DemoCard" in card_qss
    assert "QFrame#DemoCard QLabel" in card_qss

    banner_qss = scoped_banner_qss("DemoBanner", tone="warn")
    assert "QFrame#DemoBanner" in banner_qss
    assert "QFrame#DemoBanner QLabel" in banner_qss

    dlg_qss = scoped_dialog_qss("DemoDialog")
    assert "QDialog#DemoDialog" in dlg_qss
    assert "QDialog#DemoDialog QGroupBox" in dlg_qss

    from PySide6.QtWidgets import QPushButton

    btn = QPushButton("Action")
    set_enabled_with_reason(btn, False, "Sélectionnez une ligne d'abord.")
    assert not btn.isEnabled()
    assert "Sélectionnez" in btn.toolTip()
    set_enabled_with_reason(btn, True, "N/A", "Action disponible")
    assert btn.isEnabled()
    assert btn.toolTip() == "Action disponible"


def test_modernized_views_emoji_free_and_disabled_tooltips(qapp):
    from ui.widgets.inventory.tabs_consumption import ConsumptionTab
    from ui.widgets.inventory.tabs_dispatch import DispatchTab
    from ui.widgets.master_data.caisses_tab import CaissesTab
    from ui.widgets.procurement.procurement_tabs import PurchaseOrdersTab
    from ui.widgets.procurement.reception_tab import ReceptionTab
    from ui.widgets.dashboard.family_reception_tab import FamilyReceptionTab
    from ui.widgets.settings.auto_backup_tab import AutoBackupTab
    from ui.widgets.users.user_management_tab import UserManagementTab

    dm = MagicMock()
    dm.batches.get_all_batches_with_details.return_value = []
    dm.locations.get_all_locations.return_value = []
    dm.suppliers.get_all_suppliers.return_value = []
    dm.products.get_all_products.return_value = []
    dm.families.get_all_families.return_value = []
    dm.terminals.get_all_terminals.return_value = []
    dm.users.get_all_users.return_value = []
    dm.po.get_orders_by_date_range.return_value = []
    dm.po.get_all_pos_with_stats.return_value = []

    cons = ConsumptionTab(dm)
    assert "🚀" not in cons.btn_execute.text() and "⚡" not in cons.btn_execute.text()
    assert "🗑️" not in cons.btn_clear.text()

    disp = DispatchTab(dm)
    assert "📉" not in disp.btn_consume.text()
    assert "🚚" not in disp.btn_transfer.text()

    caisses = CaissesTab(dm)
    assert not caisses.btn_edit.isEnabled()
    assert bool(caisses.btn_edit.toolTip().strip())
    assert bool(caisses.btn_toggle_active.toolTip().strip())
    assert bool(caisses.btn_delete.toolTip().strip())

    po_tab = PurchaseOrdersTab(dm)
    assert po_tab is not None

    rec_tab = ReceptionTab(dm)
    assert "#ecf0f1" not in rec_tab.table.styleSheet().lower()

    fam_tab = FamilyReceptionTab(dm)
    for i in range(fam_tab.combo_unit.count()):
        for em in ("📦", "🚚", "🧪"):
            assert em not in fam_tab.combo_unit.itemText(i)

    backup = AutoBackupTab(settings={}, data_manager=dm)
    assert "▶️" not in backup.btn_force_auto.text()

    users = UserManagementTab(dm)
    assert "#28a745" not in users.btn_add.styleSheet().lower()


def test_no_legacy_slop_backgrounds_or_dialog_qss_leaks():
    checked_dirs = [
        "ui/widgets/inventory",
        "ui/widgets/procurement",
        "ui/widgets/dashboard",
        "ui/widgets/master_data",
        "ui/widgets/settings",
        "ui/widgets/reclamation",
        "ui/widgets/users",
    ]
    for rel_dir in checked_dirs:
        for py_file in (PROJECT_ROOT / rel_dir).rglob("*.py"):
            if py_file.name == "_.py":
                continue
            text = py_file.read_text(encoding="utf-8")
            assert "#ecf0f1" not in text.lower(), f"Legacy #ecf0f1 still in {py_file}"
            assert "#bdc3c7" not in text.lower(), f"Legacy #bdc3c7 still in {py_file}"
            assert "#f4f7fa" not in text.lower(), f"Legacy #f4f7fa still in {py_file}"
