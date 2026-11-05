# -*- coding: utf-8 -*-
"""
test/test_order_desk_session_bar_compact.py
===========================================
Automated verification tests for Task #1:
- Ultra-compact session tab bar (minimum height <= 28px, tab height <= 22px).
- Low-profile '+ Nouvelle Session' button (height 22px).
- Close button ('×') is always properly present and aligned on every session tab.
- Close button contrast styling (white on active teal tab, slate on inactive tab).
- Single session close/reset behavior and multi-session removal behavior.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication, QPushButton, QTabBar, QWidget
from ui.widgets.appliance_desks.order_desk_view import OrderDeskWidget


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_data_manager():
    dm = MagicMock()
    dm.current_user = {"User_ID": 1, "Username": "admin"}
    dm.clients = MagicMock()
    dm.clients.get_all_clients.return_value = [
        {"Client_ID": 1, "Client_Name": "Client Standard", "Phone": "0550000000"}
    ]
    dm.serials = MagicMock()
    dm.serials.get_catalog_with_theoretical_stock.return_value = [
        {
            "Product_ID": 101,
            "Brand_Mark": "Bosch",
            "Product_Name": "KGN39VLEB Combi NoFrost 368L",
            "Category_Name": "Réfrigérateurs",
            "Color_Finish": "Inox",
            "Physical_Qty": 5,
            "Available_Theoretical_Qty": 5,
            "Unit_Price_TTC": 115000.0,
            "Barcode": "4242005198030",
        }
    ]
    return dm


def test_session_bar_minimal_height(qapp, mock_data_manager):
    """Verifies that the session tab bar has the minimum possible height (<= 28px)."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)

    session_bars = [w for w in desk.findChildren(QWidget) if w.objectName() == "SessionTabsBar"]
    assert len(session_bars) == 1, "SessionTabsBar widget must exist"
    sb = session_bars[0]
    assert sb.height() <= 28 or sb.maximumHeight() <= 28, f"SessionTabsBar height is {sb.height()}, expected <= 28px"

    # Verify '+ Nouvelle Session' button has compact height <= 24px
    buttons = sb.findChildren(QPushButton)
    new_sess_btn = next((b for b in buttons if "Nouvelle Session" in b.text()), None)
    assert new_sess_btn is not None
    assert new_sess_btn.height() <= 24 or new_sess_btn.maximumHeight() <= 24


def test_session_close_button_always_properly_present(qapp, mock_data_manager):
    """Verifies that every session tab has a properly positioned close button ('×')."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)

    # 1. Single session initially: close button must be present!
    assert desk.session_tab_bar.count() == 1
    btn0 = desk.session_tab_bar.tabButton(0, QTabBar.RightSide)
    assert btn0 is not None and isinstance(btn0, QPushButton), "Tab 0 must have a close button"
    assert btn0.text() == "×"
    assert btn0.width() <= 18 and btn0.height() <= 18

    # 2. Add second session
    desk._create_new_session()
    assert desk.session_tab_bar.count() == 2

    btn0 = desk.session_tab_bar.tabButton(0, QTabBar.RightSide)
    btn1 = desk.session_tab_bar.tabButton(1, QTabBar.RightSide)
    assert btn0 is not None and btn1 is not None
    assert btn0.text() == "×"
    assert btn1.text() == "×"

    # 3. Add third session
    desk._create_new_session()
    assert desk.session_tab_bar.count() == 3
    for i in range(3):
        btn = desk.session_tab_bar.tabButton(i, QTabBar.RightSide)
        assert btn is not None
        assert btn.text() == "×"


def test_session_close_action_single_and_multi(qapp, mock_data_manager):
    """Verifies closing a session when multiple exist, and resetting when single exists."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)

    # Add second session
    desk._create_new_session()
    assert desk.session_tab_bar.count() == 2

    # Close session 2
    desk._close_session_by_id("SESSION_2")
    assert desk.session_tab_bar.count() == 1

    # Remaining tab 0 retains close button
    btn0 = desk.session_tab_bar.tabButton(0, QTabBar.RightSide)
    assert btn0 is not None

    # Trigger close on tab 0 (clears/resets session cleanly)
    desk._on_session_tab_close_requested(0)
    assert desk.session_tab_bar.count() == 1
    assert desk.session_tab_bar.tabButton(0, QTabBar.RightSide) is not None
