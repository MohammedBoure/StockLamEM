"""Regression tests for Task #2: Caisse UI button hierarchy, clean hero card, equal quick-cash widths, and single refresh."""

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication, QFrame, QPushButton

from ui.widgets.appliance_desks._theme import BORDER_CONTROL, BRAND_TEAL
from ui.widgets.appliance_desks.appliance_workflow_tab import ApplianceWorkflowTab
from ui.widgets.appliance_desks.cashier_desk_view import CashierDeskWidget


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
    dm.printer.config = {}
    dm.db.fetch_all.return_value = []
    dm.db.fetch_one.return_value = None
    return dm


def test_caisse_has_no_duplicate_actualiser_button(qapp):
    dm = _make_mock_dm()
    workflow = ApplianceWorkflowTab(data_manager=dm)
    assert workflow.refresh_all_btn.text() == "Actualiser"

    caisse_refresh_btns = [
        b for b in workflow.cashier_desk.findChildren(QPushButton)
        if b.text().strip() == "Actualiser"
    ]
    assert caisse_refresh_btns == []


def test_caisse_button_hierarchy_and_neutral_outlines(qapp):
    dm = _make_mock_dm()
    caisse = CashierDeskWidget(data_manager=dm)

    # Neutral slate outline (#CBD5E1) on secondary utility buttons
    for btn in (
        caisse.btn_clear_scan,
        caisse.btn_versement,
        caisse.btn_retour,
        caisse.btn_wallet_balance,
        caisse.btn_view_articles,
        caisse.btn_inspect_wallet,
        caisse.btn_use_versement,
    ):
        assert BORDER_CONTROL in btn.styleSheet(), f"{btn.text()} should use neutral slate border"
        assert f"1.5px solid {BRAND_TEAL}" not in btn.styleSheet()

    # Trouver & Exact are outlined teal (not filled primary competing with settlement CTA)
    assert f"1.5px solid {BRAND_TEAL}" in caisse.btn_scan_find.styleSheet()
    assert f"1.5px solid {BRAND_TEAL}" in caisse.btn_exact_cash.styleSheet()
    assert f"background-color: {BRAND_TEAL};" not in caisse.btn_scan_find.styleSheet()


def test_caisse_hero_and_wallet_cards_clean_uniform_borders(qapp):
    dm = _make_mock_dm()
    caisse = CashierDeskWidget(data_manager=dm)

    for obj_name in ("CaisseAmountHeroCard", "CustomerWalletCard"):
        card = caisse.findChild(QFrame, obj_name)
        assert card is not None
        qss = card.styleSheet()
        assert "border: 1px solid" in qss
        assert "border-left:" not in qss
        assert "qlineargradient" not in qss


def test_caisse_quick_cash_buttons_equal_width(qapp):
    dm = _make_mock_dm()
    caisse = CashierDeskWidget(data_manager=dm)
    caisse.resize(1280, 768)
    caisse.show()
    qapp.processEvents()

    assert len(caisse.quick_cash_buttons) == 5
    widths = [b.width() for b in caisse.quick_cash_buttons]
    assert max(widths) - min(widths) <= 2, f"Expected equal quick cash button widths, got {widths}"
    caisse.close()
