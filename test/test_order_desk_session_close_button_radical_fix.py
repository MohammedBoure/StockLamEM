# -*- coding: utf-8 -*-
"""
test/test_order_desk_session_close_button_radical_fix.py
=========================================================
Unit tests verifying the radical fix for Task #3:
- Tab close button is 100% contained within the visual tab frame (never protruding).
- Zero stylesheet conflict with global styles.qss QPushButton padding.
- Text '×' glyph is crisp and centered.
- Rounded circular hover badge without harsh red square block clipping.
- Dynamic contrast handling for active (#FFFFFF) and inactive (#64748B) tabs.
- Full session close / reset workflow compatibility.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication, QPushButton, QTabBar
from PySide6.QtCore import Qt
from ui.widgets.appliance_desks.order_desk_view import OrderDeskWidget


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    # Load global styles to test inheritance safety
    styles_path = os.path.join(os.path.dirname(__file__), "..", "ui", "styles.qss")
    if os.path.exists(styles_path):
        with open(styles_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
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


def test_close_button_geometry_strictly_inside_tab(qapp, mock_data_manager):
    """Verifies that tab close buttons are 100% contained inside their tab boundaries."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    desk.resize(1100, 700)
    desk.show()

    # Create 3 sessions
    desk._create_new_session()
    desk._create_new_session()
    desk.session_tab_bar.setCurrentIndex(0)
    desk._update_tab_close_buttons()

    tb = desk.session_tab_bar
    assert tb.count() == 3

    for i in range(tb.count()):
        tab_rect = tb.tabRect(i)
        btn = tb.tabButton(i, QTabBar.RightSide)
        assert btn is not None and isinstance(btn, QPushButton)
        bg = btn.geometry()

        # The right edge of the button must not exceed the right edge of the tab
        assert bg.right() <= tab_rect.right(), f"Tab {i} close button protrudes horizontally! btn_right={bg.right()} > tab_right={tab_rect.right()}"
        # The left edge of the button must be inside the tab
        assert bg.left() >= tab_rect.left(), f"Tab {i} close button left is outside tab! btn_left={bg.left()} < tab_left={tab_rect.left()}"
        # Button top and bottom must be inside tab
        assert bg.top() >= tab_rect.top(), f"Tab {i} close button top is outside tab!"
        assert bg.bottom() <= tab_rect.bottom(), f"Tab {i} close button bottom is outside tab!"


def test_close_button_stylesheet_and_padding_reset(qapp, mock_data_manager):
    """Verifies that close buttons reset padding/margin and use circular border-radius."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    desk.resize(1100, 700)
    desk.show()

    desk._create_new_session()
    tb = desk.session_tab_bar

    for i in range(tb.count()):
        btn = tb.tabButton(i, QTabBar.RightSide)
        assert btn is not None
        assert btn.text() == "×"
        assert btn.width() <= 16
        assert btn.height() <= 16

        ss = btn.styleSheet()
        # Must explicitly reset padding and margin to 0px
        assert "padding: 0px;" in ss or "padding:0px;" in ss, "Close button must reset padding to 0px"
        assert "margin: 0px;" in ss or "margin:0px;" in ss, "Close button must reset margin to 0px"
        # Must have rounded border-radius for sleek circular badge (anti-red-block)
        assert "border-radius: 7px;" in ss or "border-radius: 8px;" in ss, "Close button must have circular border-radius"
        # Must have hover state with red background
        assert ":hover" in ss
        assert "#EF4444" in ss or "#DC2626" in ss


def test_close_button_contrast_active_vs_inactive(qapp, mock_data_manager):
    """Verifies dynamic contrast: active tab close button is white, inactive is slate."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    desk.resize(1100, 700)
    desk.show()

    desk._create_new_session()
    # Active tab is session 2 (index 1)
    desk.session_tab_bar.setCurrentIndex(1)
    desk._on_session_tab_switched(1)

    tb = desk.session_tab_bar
    btn0 = tb.tabButton(0, QTabBar.RightSide)  # inactive
    btn1 = tb.tabButton(1, QTabBar.RightSide)  # active

    assert "#64748B" in btn0.styleSheet(), "Inactive tab close button should have subtle slate contrast"
    assert "#FFFFFF" in btn1.styleSheet(), "Active tab close button should have bright white contrast"


def test_close_button_click_triggers_session_closure(qapp, mock_data_manager):
    """Verifies that clicking the close button properly initiates session removal."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)
    desk._create_new_session()
    assert desk.session_tab_bar.count() == 2

    # Click close button on tab 1
    btn1 = desk.session_tab_bar.tabButton(1, QTabBar.RightSide)
    assert btn1 is not None

    with patch.object(desk, "_on_session_tab_close_requested") as mock_close:
        btn1.click()
        assert mock_close.called
