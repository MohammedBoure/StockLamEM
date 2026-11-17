"""Regression tests for Task #1: Global Theme, Single Sidebar Toggle, CheckBox/Disabled States & Icon Contrast."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from ui.icons import get_duotone_icon
from ui.widgets.appliance_desks._theme import (
    AMBER_OUTLINE_QSS,
    CHECKBOX_QSS,
    DANGER_OUTLINE_QSS,
    PRIMARY_CTA_QSS,
    SECONDARY_OUTLINE_QSS,
    SLATE_OUTLINE_QSS,
)
from ui.widgets.appliance_desks.appliance_workflow_tab import ApplianceWorkflowTab
from ui.widgets.appliance_desks.cashier_desk_view import CashierDeskWidget
from ui.widgets.appliance_desks.dispatch_desk_view import DispatchDeskWidget


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_mock_dm():
    dm = MagicMock()
    dm.serials.get_catalog_with_theoretical_stock.return_value = []
    dm.serials.get_stock_movements.return_value = []
    dm.clients.get_all_clients.return_value = []
    dm.clients.get_all_clients_with_balances.return_value = []
    dm.bonds.get_caisse_queue.return_value = []
    dm.bonds.get_dispatch_queue.return_value = []
    dm.product_colors.get_all_colors.return_value = []
    dm.stats = MagicMock()
    dm.stats.db = MagicMock()
    dm.stats.get_dashboard_summary.return_value = {}
    dm.stats.get_active_alerts.return_value = []
    dm.printer.config = {}
    dm.db.fetch_all.return_value = []
    dm.db.fetch_one.return_value = None
    return dm


def test_single_sidebar_toggle_and_compact_alignment(qapp):
    from ui.main_window import MainWindow

    dm = _make_mock_dm()
    admin_user = {"Role": "Admin", "Permissions": {}}

    with patch("ui.main_window.AutoBackupWorker"), \
         patch("ui.widgets.dashboard.dashboard_view.DashboardTab.refresh_all"), \
         patch("PySide6.QtWidgets.QMessageBox.question"):
        win = MainWindow(data_manager=dm, current_user=admin_user)

        assert hasattr(win, "btn_toggle")
        assert win.btn_toggle.objectName() == "btn_sidebar_toggle"
        assert not hasattr(win, "btn_hide_sidebar")
        assert not hasattr(win, "btn_show_sidebar")
        assert not hasattr(win, "show_sidebar_container")

        # Toggle to compact mode and verify header alignment at top
        win.toggle_sidebar_compact()
        qapp.processEvents()
        assert not win.is_sidebar_expanded
        assert win.btn_toggle.pos().y() <= 12
        assert win.btn_toggle.height() == 34

        # Toggle back to expanded mode
        win.toggle_sidebar_compact()
        qapp.processEvents()
        assert win.is_sidebar_expanded

        win.deleteLater()
        qapp.processEvents()


def test_global_qss_checkbox_disabled_and_sidebar_toggle():
    qss = (PROJECT_ROOT / "ui" / "styles.qss").read_text(encoding="utf-8")
    assert "QCheckBox::indicator" in qss
    assert "url(ui/assets/icons/check_white.svg)" in qss
    assert "QPushButton:disabled" in qss
    assert "color: #475569;" in qss
    assert "QPushButton#btn_sidebar_toggle" in qss
    assert (PROJECT_ROOT / "ui" / "assets" / "icons" / "check_white.svg").exists()


def test_theme_disabled_contrast_and_checkbox_qss():
    assert "QCheckBox::indicator" in CHECKBOX_QSS
    for style in (PRIMARY_CTA_QSS, SECONDARY_OUTLINE_QSS, SLATE_OUTLINE_QSS, DANGER_OUTLINE_QSS, AMBER_OUTLINE_QSS):
        assert "color: #475569;" in style


def test_white_icons_and_16px_primary_buttons(qapp):
    for key in (
        "search_white",
        "barcode_scan_white",
        "truck_delivery_white",
        "shield_admin_white",
        "return_arrow_white",
        "print_white",
        "payment_white",
        "refresh_white",
    ):
        icon = get_duotone_icon(key, 16)
        assert not icon.isNull(), f"Missing icon: {key}"
        assert not icon.pixmap(16, 16, QIcon.Disabled).isNull()

    dm = _make_mock_dm()
    workflow = ApplianceWorkflowTab(data_manager=dm)
    assert workflow.refresh_all_btn.iconSize() == QSize(16, 16)

    caisse = CashierDeskWidget(data_manager=dm)
    assert caisse.btn_scan_find.iconSize() == QSize(16, 16)
    assert caisse.btn_val_bon_c.iconSize() == QSize(16, 16)
    assert caisse.btn_val_livraison.iconSize() == QSize(16, 16)
    assert "QCheckBox::indicator" in caisse.styleSheet()

    dispatch = DispatchDeskWidget(data_manager=dm)
    assert dispatch.btn_emit_sortie.iconSize() == QSize(16, 16)
