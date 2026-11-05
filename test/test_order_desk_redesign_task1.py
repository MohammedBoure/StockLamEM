# -*- coding: utf-8 -*-
"""
test/test_order_desk_redesign_task1.py
======================================
Automated verification test suite for Task #1 Order Desk Redesign:
1. Lazy Loading in catalog table:
   - Initial load chunks to 35 items.
   - Incremental chunk loading as user scrolls or requests more.
   - Accurate counter label: "Catalogue des Produits Disponibles (X / Total)".
2. Elimination of double overlapping color text:
   - QTableWidgetItem text is empty string (data stored in UserRole).
   - Only ColorBadgeWidget renders the color swatch and text.
3. Removal of obsolete badge texts:
   - "Vente Théorique" label completely eliminated from UI.
   - "Isolation HID Active" eliminated from UI (lbl_scanner_status invisible & empty).
4. True connected session tabs & refined close button:
   - Session bar is transparent/borderless.
   - Sleek soft-hover close buttons shown only when >1 session.
5. Action column ergonomics:
   - High-contrast "+ Ajouter" button with cart vector icon and 195px column width.
   - "Épuisé" button for out-of-stock items.
6. ApplianceWorkflowTab tab 5 renamed to "5. Référentiel Lots && Séries".
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QTabBar
from ui.widgets.appliance_desks.order_desk_view import (
    ColorBadgeWidget,
    OrderDeskWidget,
)
from ui.widgets.appliance_desks.appliance_workflow_tab import ApplianceWorkflowTab


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_data_manager_large():
    dm = MagicMock()
    dm.current_user = {"User_ID": 1, "Username": "admin"}
    dm.clients = MagicMock()
    dm.clients.get_all_clients.return_value = [
        {"Client_ID": 1, "Client_Name": "Comptoir Client Standard", "Phone": "0550000000"}
    ]
    dm.serials = MagicMock()

    # Generate 85 mock products for lazy loading validation
    mock_catalog = []
    for i in range(1, 86):
        mock_catalog.append({
            "Product_ID": 100 + i,
            "Brand_Mark": "Bosch" if i % 2 == 0 else "Samsung",
            "Product_Name": f"Produit Électroménager Test #{i:03d}",
            "Category_Name": "Réfrigérateurs" if i % 3 == 0 else "Lave-linge",
            "Color_Finish": "Inox" if i % 2 == 0 else "Blanc",
            "Physical_Qty": 10,
            "Reserved_Qty": 1,
            "Available_Theoretical_Qty": 9 if i < 80 else 0,  # last 5 out of stock
            "Unit_Price_TTC": 75000.0 + i * 500,
            "Barcode": f"619123456{i:04d}",
            "Requires_Serial_Tracking": True,
        })
    dm.serials.get_catalog_with_theoretical_stock.return_value = mock_catalog
    return dm


def test_order_desk_lazy_loading(qapp, mock_data_manager_large):
    """Verifies that catalog items load in chunks of 35 and incrementally expand on demand."""
    desk = OrderDeskWidget(data_manager=mock_data_manager_large)
    desk.refresh_catalog()

    # 1. First chunk should have exactly 35 items
    assert desk.table.rowCount() == 35, f"Initial rowCount was {desk.table.rowCount()}, expected 35"
    assert "35 / 85" in desk.lbl_cat_title.text()

    # 2. Trigger loading next chunk
    desk._load_next_catalog_chunk()
    assert desk.table.rowCount() == 70, f"Second rowCount was {desk.table.rowCount()}, expected 70"
    assert "70 / 85" in desk.lbl_cat_title.text()

    # 3. Trigger loading final chunk (remaining 15)
    desk._load_next_catalog_chunk()
    assert desk.table.rowCount() == 85, f"Final rowCount was {desk.table.rowCount()}, expected 85"
    assert "85 / 85" in desk.lbl_cat_title.text()

    # 4. Triggering beyond total does not append duplicate rows
    desk._load_next_catalog_chunk()
    assert desk.table.rowCount() == 85


def test_order_desk_no_color_double_text(qapp, mock_data_manager_large):
    """Verifies that QTableWidgetItem has empty text to eliminate overlapping double text."""
    desk = OrderDeskWidget(data_manager=mock_data_manager_large)
    desk.refresh_catalog()

    for row in range(min(5, desk.table.rowCount())):
        item = desk.table.item(row, 3)
        assert item is not None
        # QTableWidgetItem text must be empty so item delegate does NOT paint underlying text
        assert item.text() == "", f"Row {row} QTableWidgetItem text was '{item.text()}', must be empty!"
        assert item.data(Qt.UserRole) in ("Inox", "Blanc")

        badge = desk.table.cellWidget(row, 3)
        assert isinstance(badge, ColorBadgeWidget)
        assert badge.color_name in ("Inox", "Blanc")


def test_order_desk_removal_of_unwanted_badge_texts(qapp, mock_data_manager_large):
    """Verifies that 'Vente Théorique' and 'Isolation HID Active' are completely absent from visible UI."""
    desk = OrderDeskWidget(data_manager=mock_data_manager_large)

    # 1. 'Vente Théorique' label must be absent from desk
    all_labels = desk.findChildren(QLabel)
    vente_theorique_labels = [lbl for lbl in all_labels if "Vente Théorique" in lbl.text()]
    assert len(vente_theorique_labels) == 0, "Found 'Vente Théorique' label, must be removed!"

    # 2. 'Isolation HID Active' must not be visible
    assert desk.lbl_scanner_status.isVisible() is False
    assert desk.lbl_scanner_status.text() == ""


def test_order_desk_session_tabs_and_close_buttons(qapp, mock_data_manager_large):
    """Verifies that session tabs use true connected styling and refined close buttons."""
    desk = OrderDeskWidget(data_manager=mock_data_manager_large)

    assert desk.session_tab_bar.count() == 1
    assert desk.session_tab_bar.tabButton(0, QTabBar.RightSide) is None

    # Add second session
    desk._create_new_session()
    assert desk.session_tab_bar.count() == 2

    # Both tabs now have close buttons
    btn0 = desk.session_tab_bar.tabButton(0, QTabBar.RightSide)
    btn1 = desk.session_tab_bar.tabButton(1, QTabBar.RightSide)
    assert btn0 is not None and isinstance(btn0, QPushButton)
    assert btn1 is not None and isinstance(btn1, QPushButton)
    assert btn0.text() == "×"
    assert btn0.width() == 18 and btn0.height() == 18


def test_order_desk_action_column_and_exhausted_state(qapp, mock_data_manager_large):
    """Verifies action button design for available and exhausted items."""
    desk = OrderDeskWidget(data_manager=mock_data_manager_large)
    desk.refresh_catalog()

    # Load all items so we can inspect exhausted items
    while desk._catalog_loaded_count < len(desk._catalog_filtered_items):
        desk._load_next_catalog_chunk()

    # Row 0 is available
    cell0 = desk.table.cellWidget(0, 6)
    btn0 = cell0.findChild(QPushButton)
    assert btn0.isEnabled() is True
    assert "+ Ajouter" in btn0.text()

    # Row 84 is out of stock (available = 0)
    cell84 = desk.table.cellWidget(84, 6)
    btn84 = cell84.findChild(QPushButton)
    assert btn84.isEnabled() is False
    assert "Épuisé" in btn84.text()


def test_appliance_workflow_desk_tab_renaming(qapp, mock_data_manager_large):
    """Verifies that Desk 5 in ApplianceWorkflowTab is named '5. Référentiel Lots && Séries'."""
    tab_widget = ApplianceWorkflowTab(data_manager=mock_data_manager_large)
    tab_5_text = tab_widget.desk_tabs.tabText(4)
    assert "Référentiel Lots" in tab_5_text, f"Desk 5 tab was '{tab_5_text}', expected 'Référentiel Lots'"
