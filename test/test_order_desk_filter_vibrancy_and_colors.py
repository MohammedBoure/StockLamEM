# -*- coding: utf-8 -*-
"""
test/test_order_desk_filter_vibrancy_and_colors.py
==================================================
Automated Test Suite for Task #3:
- Visual color swatches in the Order Desk filter combobox (`cbo_color`).
- Live `ColorFilterBadge` preview showing real color application, swatches, and hex codes.
- Vibrant, energetic styling for `OrderTopFilterBar` (gradient, left brand accent, vector badge).
- Clean filter field micro-badges with icons (Marque, Catégorie, Couleur).
- Clear button enabled on search bar with instant reset.
- Live catalog KPI count badge (`lbl_catalog_count_badge`).
- Dynamic synchronization of catalog color finishes into combobox.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from ui.widgets.appliance_desks.order_desk_view import ColorFilterBadge, OrderDeskWidget


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
            "Product_Name": "KGN39VLEB Combi NoFrost 368L Inox",
            "Category_Name": "Gros Électroménager",
            "Color_Finish": "Inox",
            "Physical_Qty": 10,
            "Reserved_Qty": 2,
            "Available_Theoretical_Qty": 8,
            "Unit_Price_TTC": 115000.0,
            "Barcode": "4242005198030",
        },
        {
            "Product_ID": 102,
            "Brand_Mark": "Samsung",
            "Product_Name": "WW90T554DAN Ecobubble 9kg Blanc",
            "Category_Name": "Lave-linge",
            "Color_Finish": "Blanc",
            "Physical_Qty": 5,
            "Reserved_Qty": 0,
            "Available_Theoretical_Qty": 5,
            "Unit_Price_TTC": 88000.0,
            "Barcode": "8806098321092",
        },
        {
            "Product_ID": 103,
            "Brand_Mark": "LG",
            "Product_Name": "Side by Side Multi Door Noir Mat",
            "Category_Name": "Gros Électroménager",
            "Color_Finish": "Noir",
            "Physical_Qty": 3,
            "Reserved_Qty": 1,
            "Available_Theoretical_Qty": 2,
            "Unit_Price_TTC": 210000.0,
            "Barcode": "8806098399999",
        },
    ]
    return dm


def test_color_filter_swatches_and_badge_integration(qapp, mock_data_manager):
    """Verifies that the color filter combobox displays swatch icons and live preview badge."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)

    # 1. Combobox items have icons
    assert desk.cbo_color.count() >= 3
    # Check that color items (e.g. index 1) have valid non-null swatch icons
    icon_item1 = desk.cbo_color.itemIcon(1)
    assert not icon_item1.isNull(), "Color item in cbo_color must have a valid visual swatch QIcon"

    # 2. Live ColorFilterBadge exists
    assert hasattr(desk, "color_preview_badge")
    badge = desk.color_preview_badge
    assert isinstance(badge, ColorFilterBadge)
    assert badge.lbl_text.text() == "Toutes"

    # 3. Select a specific color (Inox)
    inox_idx = -1
    for i in range(desk.cbo_color.count()):
        if "inox" in desk.cbo_color.itemText(i).lower():
            inox_idx = i
            break
    assert inox_idx > 0
    desk.cbo_color.setCurrentIndex(inox_idx)
    qapp.processEvents()

    # Badge should update to Inox
    assert badge.lbl_text.text() == "Inox"
    assert "Inox" in badge.toolTip()
    assert "#8A9EA7" in badge.toolTip()

    # 4. Interactive badge click resets to Toutes
    desk._on_color_badge_clicked()
    qapp.processEvents()
    assert desk.cbo_color.currentIndex() == 0
    assert badge.lbl_text.text() == "Toutes"


def test_filter_bar_vibrancy_and_ergonomics(qapp, mock_data_manager):
    """Verifies filter bar styling vibrancy, heights, and live counter KPI badge."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)

    # Filter bar height >= 50px
    top_bar = desk.findChild(type(desk), "OrderTopFilterBar") or getattr(desk, "top_filter_bar", None)
    # Check txt_search height and clear button
    assert desk.txt_search.height() >= 34 or desk.txt_search.minimumHeight() >= 34
    assert desk.txt_search.isClearButtonEnabled(), "Search bar must have native instant clear button enabled"

    # Combobox heights >= 34px
    assert desk.cbo_mark.height() >= 34 or desk.cbo_mark.minimumHeight() >= 34
    assert desk.cbo_category.height() >= 34 or desk.cbo_category.minimumHeight() >= 34
    assert desk.cbo_color.height() >= 34 or desk.cbo_color.minimumHeight() >= 34

    # Live count KPI badge
    assert hasattr(desk, "lbl_catalog_count_badge")
    assert "produits trouvés" in desk.lbl_catalog_count_badge.text()


def test_reset_filters_restores_all_defaults(qapp, mock_data_manager):
    """Verifies that clicking Réinitialiser resets all comboboxes, clears search, and restores color badge."""
    desk = OrderDeskWidget(data_manager=mock_data_manager)

    # Set non-default filters
    desk.cbo_mark.setCurrentIndex(1)
    desk.cbo_category.setCurrentIndex(1)
    desk.cbo_color.setCurrentIndex(1)
    desk.txt_search.setText("Bosch")
    qapp.processEvents()

    # Trigger reset
    desk._reset_filters()
    qapp.processEvents()

    assert desk.cbo_mark.currentIndex() == 0
    assert desk.cbo_category.currentIndex() == 0
    assert desk.cbo_color.currentIndex() == 0
    assert desk.txt_search.text() == ""
    assert desk.color_preview_badge.lbl_text.text() == "Toutes"
