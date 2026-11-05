# -*- coding: utf-8 -*-
"""
test/test_order_desk_filters_like_stock_actuel.py
==================================================
Automated Test Suite for Task #8:
- Harmonizing Order Desk filters with 'Stock & Magasin -> Stock Actuel' (BatchesTab):
  * Dynamic loading of Brands (Marques) from data_manager.manufacturers and catalog items into cbo_mark.
  * Dynamic loading of Categories / Families from data_manager.families and catalog items into cbo_category.
  * Responsive dropdown popup widths (_adjust_combo_view_width) preventing name truncation.
  * Robust, accurate filtering across Brands, Categories, Colors, Search text, and Available-only toggle.
  * Filtering Information Display matching Stock Actuel:
    - 'Valeur Totale : X DA' (lbl_total_value) in dedicated bottom summary bar.
    - 'Stock disponible affiché : X' (lbl_total_quantity) in green summary badge.
    - 'Affichage: X / Y' (lbl_count_info) showing loaded vs total matching items.
    - Dynamic KPI badge (lbl_catalog_count_badge) with stock unit counts and comprehensive tooltip.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel
from ui.widgets.appliance_desks.order_desk_view import OrderDeskWidget


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_stock_actuel_data_manager():
    dm = MagicMock()
    dm.current_user = {"User_ID": 1, "Username": "admin"}
    dm.clients = MagicMock()
    dm.clients.get_all_clients.return_value = [
        {"Client_ID": 1, "Client_Name": "Client Standard", "Phone": "0550000000", "Price_Tier": "Prix_1"},
    ]
    dm.manufacturers = MagicMock()
    dm.manufacturers.get_all_manufacturers.return_value = [
        {"Manuf_ID": 10, "Manuf_Name": "Belling"},
        {"Manuf_ID": 20, "Manuf_Name": "Siemens"},
        {"Manuf_ID": 30, "Manuf_Name": "Teka International"},
    ]
    dm.families = MagicMock()
    dm.families.get_all_families.return_value = [
        {"Family_ID": 100, "Family_Name": "Fours Encastrables"},
        {"Family_ID": 200, "Family_Name": "Hottes Aspirantes"},
        {"Family_ID": 300, "Family_Name": "Micro-ondes Pro"},
    ]
    dm.serials = MagicMock()
    dm.serials.get_catalog_with_theoretical_stock.return_value = [
        {
            "Product_ID": 201,
            "Brand_Mark": "Belling",
            "Product_Name": "Four Cookcentre 90 DFT Inox",
            "Category_Name": "Fours Encastrables",
            "Color_Finish": "Inox",
            "Physical_Qty": 6,
            "Reserved_Qty": 1,
            "Available_Theoretical_Qty": 5,
            "Unit_Price_TTC": 120000.0,
            "Price_1_TTC": 120000.0,
            "Price_2_TTC": 115000.0,
            "Price_3_TTC": 110000.0,
            "Barcode": "5052263050011",
        },
        {
            "Product_ID": 202,
            "Brand_Mark": "Siemens",
            "Product_Name": "Hotte Murale Décorative 90cm Noir",
            "Category_Name": "Hottes Aspirantes",
            "Color_Finish": "Noir",
            "Physical_Qty": 8,
            "Reserved_Qty": 0,
            "Available_Theoretical_Qty": 8,
            "Unit_Price_TTC": 75000.0,
            "Price_1_TTC": 75000.0,
            "Price_2_TTC": 72000.0,
            "Price_3_TTC": 69000.0,
            "Barcode": "4242003850022",
        },
        {
            "Product_ID": 203,
            "Brand_Mark": "Teka International",
            "Product_Name": "Micro-ondes Encastrable 25L Blanc",
            "Category_Name": "Micro-ondes Pro",
            "Color_Finish": "Blanc",
            "Physical_Qty": 4,
            "Reserved_Qty": 4,
            "Available_Theoretical_Qty": 0,  # Exhausted
            "Unit_Price_TTC": 45000.0,
            "Price_1_TTC": 45000.0,
            "Price_2_TTC": 43000.0,
            "Price_3_TTC": 41000.0,
            "Barcode": "8421152140033",
        },
    ]
    return dm


def test_filters_dynamic_population_like_stock_actuel(qapp, mock_stock_actuel_data_manager):
    """Verifies dynamic populating of Brands and Families from database, matching Stock & Magasin."""
    desk = OrderDeskWidget(data_manager=mock_stock_actuel_data_manager)

    # 1. Marque combo dynamically populated with database manufacturers
    mark_items = [desk.cbo_mark.itemText(i) for i in range(desk.cbo_mark.count())]
    assert "Tous" in mark_items[0]
    assert "Belling" in mark_items
    assert "Siemens" in mark_items
    assert "Teka International" in mark_items

    # 2. Catégorie combo dynamically populated with database families
    cat_items = [desk.cbo_category.itemText(i) for i in range(desk.cbo_category.count())]
    assert "Tous" in cat_items[0]
    assert "Fours Encastrables" in cat_items
    assert "Hottes Aspirantes" in cat_items
    assert "Micro-ondes Pro" in cat_items


def test_filtering_information_display_metrics(qapp, mock_stock_actuel_data_manager):
    """Verifies that filter information (Valeur Totale, Stock disponible affiché, Affichage X / Y) displays accurately."""
    desk = OrderDeskWidget(data_manager=mock_stock_actuel_data_manager)
    desk.refresh_catalog()

    # 1. By default, chk_available_only is True -> 2 products are available (Product 201: 5 units, Product 202: 8 units = 13 units)
    # Total Value: 5 * 120 000 + 8 * 75 000 = 600 000 + 600 000 = 1 200 000 DA
    assert hasattr(desk, "lbl_total_value")
    assert hasattr(desk, "lbl_total_quantity")
    assert hasattr(desk, "lbl_count_info")

    assert "1 200 000" in desk.lbl_total_value.text()
    assert "Valeur Totale :" in desk.lbl_total_value.text()

    assert "13" in desk.lbl_total_quantity.text()
    assert "Stock disponible affiché :" in desk.lbl_total_quantity.text()

    assert "Affichage: 2 / 2" in desk.lbl_count_info.text()
    assert "2 produits trouvés" in desk.lbl_catalog_count_badge.text()
    assert "13 en stock" in desk.lbl_catalog_count_badge.text()


def test_filter_selection_updates_metrics_accurately(qapp, mock_stock_actuel_data_manager):
    """Verifies that selecting specific brand, category, or search filters updates all summary metrics."""
    desk = OrderDeskWidget(data_manager=mock_stock_actuel_data_manager)
    desk.refresh_catalog()

    # Select Belling in Marque combo
    belling_idx = desk.cbo_mark.findText("Belling")
    assert belling_idx >= 0
    desk.cbo_mark.setCurrentIndex(belling_idx)
    qapp.processEvents()

    # Only Product 201 should match (5 units, 120 000 DA = 600 000 DA)
    assert "600 000" in desk.lbl_total_value.text()
    assert "5" in desk.lbl_total_quantity.text()
    assert "Affichage: 1 / 1" in desk.lbl_count_info.text()
    assert "1 produit trouvé" in desk.lbl_catalog_count_badge.text()

    # Reset filters should restore full totals
    desk._reset_filters()
    qapp.processEvents()
    assert desk.cbo_mark.currentIndex() == 0
    assert "1 200 000" in desk.lbl_total_value.text()
    assert "13" in desk.lbl_total_quantity.text()
    assert "Affichage: 2 / 2" in desk.lbl_count_info.text()
