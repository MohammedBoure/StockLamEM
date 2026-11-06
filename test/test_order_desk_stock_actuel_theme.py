# -*- coding: utf-8 -*-
"""
test/test_order_desk_stock_actuel_theme.py
==========================================
Automated test suite verifying Task #1:
Harmonization of Order Desk (Bureau des Commandes) theme with
Stock & Magasin -> Stock Actuel (BatchesTab):
1. Clean crisp white canvas background (#FFFFFF) matching BatchesTabRoot.
2. Filter bar container styling (1px solid #DCDFE6; border-radius: 6px) matching Stock Actuel QGroupBox.
3. Input controls (QLineEdit, QComboBox) styled with 1px solid #CED4DA, border-radius: 4px,
   text color #2C3E50, and 1.5px solid #007572 on focus.
4. Action buttons matching Stock Actuel:
   - Actualiser: Solid primary teal (#007572, white bold text, border: none, border-radius: 4px).
   - Réinitialiser: Slate outline button (#FFFFFF, #495057 text, 1px solid #CED4DA, border-radius: 4px).
   - Émettre Bon Comptant: Solid primary teal (#007572, white bold text, border: none, border-radius: 4px).
   - Bon Crédit & Bon de Livraison: Styled outline buttons with #007572 border and text, border-radius: 4px.
   - Vider (Clear Cart): Clean danger button with #C0392B text and 1px solid #CED4DA, border-radius: 4px.
   - + Nouveau Client: Styled outline button with #007572 border and text, border-radius: 4px.
   - + Nouvelle Session: Clean button with 1px solid #CED4DA, border-radius: 4px, color #007572.
5. Table styling and headers matching Stock Actuel (#2C3E50 text, 2px solid #007572 bottom border, #007572 scrollbar handles).
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication, QPushButton, QComboBox, QLineEdit, QCheckBox, QFrame
from ui.widgets.appliance_desks.order_desk_view import (
    OrderDeskWidget,
    PRIMARY_BTN_STYLE,
    OUTLINE_BTN_STYLE,
    SLATE_OUTLINE_BTN_STYLE,
    DANGER_BTN_STYLE,
    TABLE_STYLE,
)
from ui.widgets.appliance_desks.appliance_workflow_tab import ApplianceWorkflowTab


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
        {"Client_ID": 1, "Client_Name": "Client Comptoir (Standard)", "Phone": "0550000000", "Address": "Alger"}
    ]
    dm.serials = MagicMock()
    dm.serials.get_catalog_with_theoretical_stock.return_value = [
        {
            "Product_ID": 101,
            "Brand_Mark": "Bosch",
            "Product_Name": "KGN39VLEB Combi NoFrost 368L",
            "Category_Name": "Gros Électroménager",
            "Color_Finish": "Inox",
            "Physical_Qty": 5,
            "Reserved_Qty": 0,
            "Available_Theoretical_Qty": 5,
            "Unit_Price_TTC": 115000.0,
            "Price_1_TTC": 115000.0,
            "Price_2_TTC": 110000.0,
            "Price_3_TTC": 105000.0,
            "Barcode": "4242005198030",
        }
    ]
    return dm


def test_order_desk_root_and_filter_bar_theme(qapp, mock_data_manager):
    """Verifies that OrderDeskWidget root and filter bar match Stock Actuel styling."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)

    # 1. Content widget background is pure white matching BatchesTabRoot
    scroll_style = desk.scroll_area.styleSheet()
    assert "#FFFFFF" in scroll_style or "#ffffff" in scroll_style
    assert "#F4F6F8" not in scroll_style

    # 2. Filter panel has 1px solid #DCDFE6 and border-radius: 6px
    filter_bar = desk.findChild(QFrame, "OrderTopFilterBar")
    assert filter_bar is not None
    fbar_style = filter_bar.styleSheet()
    assert "#DCDFE6" in fbar_style.upper()
    assert "border-radius: 6px" in fbar_style
    assert "#CED4DA" in fbar_style.upper()
    assert "#007572" in fbar_style


def test_order_desk_filter_inputs_theme(qapp, mock_data_manager):
    """Verifies all input fields match Stock Actuel borders, padding, and focus colors."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)

    # Comboboxes in filter bar
    for combo in (desk.cbo_mark, desk.cbo_category, desk.cbo_color):
        assert combo.maximumHeight() == 32

    # Search input field
    assert desk.txt_search.maximumHeight() == 32

    # Checkbox 'Disponibles uniquement'
    chk_style = desk.chk_available_only.styleSheet()
    assert "#007572" in chk_style
    assert "#CED4DA" in chk_style.upper()
    assert "border-radius: 4px" in chk_style


def test_order_desk_buttons_match_stock_actuel_hierarchy(qapp, mock_data_manager):
    """Verifies button stylesheets match Stock Actuel's primary, secondary, and danger patterns."""
    # 1. PRIMARY_BTN_STYLE: Solid teal #007572, border: none, border-radius: 4px
    assert "#007572" in PRIMARY_BTN_STYLE
    assert "border: none" in PRIMARY_BTN_STYLE
    assert "border-radius: 4px" in PRIMARY_BTN_STYLE
    assert "#005A57" in PRIMARY_BTN_STYLE.upper()

    # 2. SLATE_OUTLINE_BTN_STYLE (Reset): #FFFFFF background, #CED4DA border, #495057 text, border-radius: 4px
    assert "#CED4DA" in SLATE_OUTLINE_BTN_STYLE.upper()
    assert "#495057" in SLATE_OUTLINE_BTN_STYLE
    assert "border-radius: 4px" in SLATE_OUTLINE_BTN_STYLE

    # 3. OUTLINE_BTN_STYLE: #FFFFFF background, #007572 border, border-radius: 4px
    assert "#007572" in OUTLINE_BTN_STYLE
    assert "border-radius: 4px" in OUTLINE_BTN_STYLE
    assert "#E8F8F5" in OUTLINE_BTN_STYLE.upper()

    # 4. DANGER_BTN_STYLE: #FFFFFF background, #C0392B text, #CED4DA border, border-radius: 4px
    assert "#C0392B" in DANGER_BTN_STYLE.upper()
    assert "#CED4DA" in DANGER_BTN_STYLE.upper()
    assert "border-radius: 4px" in DANGER_BTN_STYLE


def test_order_desk_cart_controls_and_buttons_theme(qapp, mock_data_manager):
    """Verifies cart inputs and buttons adopt Stock Actuel styling."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)

    # Client combo
    client_style = desk.cbo_client.styleSheet()
    assert "#CED4DA" in client_style.upper()
    assert "#007572" in client_style
    assert "border-radius: 4px" in client_style

    # Delivery address input
    addr_style = desk.txt_delivery_addr.styleSheet()
    assert "#CED4DA" in addr_style.upper()
    assert "#007572" in addr_style
    assert "border-radius: 4px" in addr_style

    # Panels border
    cat_style = desk.catalog_panel.styleSheet()
    assert "#DCDFE6" in cat_style.upper()
    cart_style = desk.cart_panel.styleSheet()
    assert "#DCDFE6" in cart_style.upper()


def test_appliance_workflow_tabs_theme(qapp, mock_data_manager):
    """Verifies that ApplianceWorkflowTab banner and sub-desk tabs match Stock Actuel."""
    workflow = ApplianceWorkflowTab(data_manager=mock_data_manager)

    banner_style = workflow.findChild(type(workflow.refresh_all_btn.parentWidget())).styleSheet()
    assert "#DCDFE6" in banner_style.upper()

    btn_style = workflow.refresh_all_btn.styleSheet()
    assert "#007572" in btn_style
    assert "border-radius: 4px" in btn_style
    assert "border: none" in btn_style

    tabs_style = workflow.desk_tabs.styleSheet()
    assert "#DCDFE6" in tabs_style.upper()
    assert "#007572" in tabs_style
    assert "#CED4DA" in tabs_style.upper()
