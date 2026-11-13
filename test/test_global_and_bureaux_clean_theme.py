"""Regression tests verifying the SAV-style flat, underline, minimal UI overhaul across Bureaux and all workspaces."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication, QFrame, QTabWidget

from ui.widgets.appliance_desks.appliance_workflow_tab import ApplianceWorkflowTab
from ui.widgets.appliance_desks.cashier_desk_view import BonRetourDialog, CashierDeskWidget
from ui.widgets.appliance_desks.dispatch_desk_view import DispatchDeskWidget
from ui.widgets.appliance_desks.serial_batch_view import SerialBatchRegistryWidget
from ui.widgets.dashboard.ai_analytics_tab import AiAnalyticsTab
from ui.widgets.dashboard.dashboard_view import DashboardTab
from ui.widgets.dashboard.kpi_cards import KPICard, KPICardsSection
from ui.widgets.dashboard.statistics_tabs import WasteAnalysisTab
from ui.widgets.users.user_management_tab import SYSTEM_PERMISSIONS


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
    dm.product_refs.get_all_references.return_value = []
    dm.stats = MagicMock()
    dm.stats.db = MagicMock()
    dm.stats.get_dashboard_summary.return_value = {}
    dm.stats.get_active_alerts.return_value = []
    dm.stats.get_valuation_summary.return_value = []
    dm.stats.get_waste_stats.return_value = []
    dm.stats.get_family_reception_summary.return_value = []
    dm.printer.config = {}
    dm.db.fetch_all.return_value = []
    dm.db.fetch_one.return_value = None
    return dm


def test_global_qss_uses_flat_underline_tabs():
    qss = (PROJECT_ROOT / "ui" / "styles.qss").read_text(encoding="utf-8")
    assert "border-bottom: 2px solid #007572;" in qss
    assert "border-top: 3px solid #007572" not in qss
    assert "border: 1px solid #e2e8f0;" in qss


def test_bureaux_workflow_and_desks_are_flat_and_concise(qapp):
    dm = _make_mock_dm()
    workflow = ApplianceWorkflowTab(data_manager=dm)

    assert workflow.desk_tabs.documentMode() is True
    assert "border-bottom: 2px solid #007572" in workflow.desk_tabs.styleSheet()

    tab_titles = [workflow.desk_tabs.tabText(i) for i in range(workflow.desk_tabs.count())]
    assert any("1. Commandes" in t for t in tab_titles)
    assert any("2. Caisse" in t for t in tab_titles)
    assert any("3. Sortie Magasin" in t for t in tab_titles)

    caisse = CashierDeskWidget(data_manager=dm)
    assert caisse.lbl_selected_info.text() in ("Sélectionnez un bon.", "Aucun bon en attente dans la file.")
    assert caisse.lbl_rem_due.text().startswith("Reste :")
    assert "Utiliser le solde portefeuille" in caisse.cb_wallet.text()

    scan_frame = caisse.findChild(QFrame, "CaisseScanFrame")
    hero_card = caisse.findChild(QFrame, "CaisseAmountHeroCard")
    assert scan_frame is not None and "border-bottom: 1px solid #E2E8F0" in scan_frame.styleSheet()
    assert hero_card is not None and "border-left: 3px solid #007572" in hero_card.styleSheet()

    dispatch = DispatchDeskWidget(data_manager=dm)
    assert dispatch.lbl_status.text() == "Prêt"
    hdr = dispatch.findChild(QFrame, "DispatchHeaderCard")
    console = dispatch.findChild(QFrame, "DispatchScanConsole")
    assert hdr is not None and "border-bottom: 1px solid #DDE3EA" in hdr.styleSheet()
    assert console is not None and "border-top: 1px solid #DDE3EA" in console.styleSheet()

    sbv = SerialBatchRegistryWidget(data_manager=dm)
    assert sbv.inner_tabs.documentMode() is True
    for btn_txt in (sbv.btn_nav_procurement.text(), sbv.btn_nav_stock.text(), sbv.btn_search_serial.text()):
        for ch in ("🛒", "📦", "🔍", "⚠️"):
            assert ch not in btn_txt

    retour_dlg = BonRetourDialog(data_manager=dm)
    banner = retour_dlg.findChild(QFrame, "RetourFirewallBanner")
    assert banner is not None and "border-left: 3px solid #0E7471" in banner.styleSheet()


def test_dashboard_waste_ai_and_permissions_emoji_free_and_scoped(qapp):
    dm = _make_mock_dm()
    dash = DashboardTab(dm)
    assert dash.tabs.documentMode() is True
    assert "border-bottom: 2px solid #007572" in dash.tabs.styleSheet()

    waste = WasteAnalysisTab()
    assert waste.kpi_total_loss.objectName() == "WasteMiniKpi"
    assert "QFrame#WasteMiniKpi" in waste.kpi_total_loss.styleSheet()

    kpi_card = KPICard("VALEUR STOCK", "1 000 DA", "", "#27ae60")
    assert kpi_card.objectName() == "DashboardKpiCard"
    assert "QFrame#DashboardKpiCard" in kpi_card.styleSheet()

    kpi_sec = KPICardsSection()
    kpi_sec.update_data({"total_stock_value": 10, "total_consumption_value": 5, "total_out_units": 2, "total_waste_units": 0, "total_waste_value": 0})
    assert kpi_sec.layout.count() == 4

    ai = AiAnalyticsTab()
    assert ai.tabs.documentMode() is True
    assert "linear-gradient" not in ai.styleSheet()
    for i in range(ai.tabs.count()):
        for ch in ("🔮", "⚠️", "🚨"):
            assert ch not in ai.tabs.tabText(i)

    for grp in SYSTEM_PERMISSIONS.values():
        for ch in ("📊", "📚", "👥", "🛒", "⚠️", "📦", "📜", "🔧", "🏢"):
            assert ch not in grp["label"]


def test_mainwindow_subtabs_have_no_emojis(qapp):
    from ui.main_window import MainWindow

    dm = _make_mock_dm()
    admin = {"Username": "admin", "Role": "Admin", "Permissions": "[]"}
    with patch("ui.main_window.AutoBackupWorker"), \
         patch("ui.widgets.dashboard.dashboard_view.DashboardTab.refresh_all"), \
         patch("PySide6.QtWidgets.QMessageBox.question"):
        win = MainWindow(data_manager=dm, current_user=admin)
        emojis = ("📌", "📅", "📋", "💰", "🗑️", "⚠️", "🛒", "📜", "↩️", "📦", "🚚", "🏢", "⏱️", "🗄️", "🖨️", "🏷️", "🧾", "⚙️", "📝", "🎨")
        for pid in (0, 2, 3, 4):
            w = win._load_page(pid)
            tw = w.findChild(QTabWidget)
            if tw:
                for i in range(tw.count()):
                    for em in emojis:
                        assert em not in tw.tabText(i)
