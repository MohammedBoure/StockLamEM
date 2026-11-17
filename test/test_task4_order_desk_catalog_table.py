"""Regression tests for Task #4: Order Desk catalog table, right-aligned text pricing, resize modes, and empty state."""

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHeaderView, QMenu, QWidget

from ui.widgets.appliance_desks.order_desk_view import AddActionCellWidget, OrderDeskWidget


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_dm():
    dm = MagicMock()
    dm.clients.get_all_clients.return_value = [
        {"Client_ID": 1, "Client_Name": "Client Comptoir", "Phone": "0550000000", "Price_Tier": "Prix_1"},
    ]
    dm.product_colors.get_all_colors.return_value = []
    dm.manufacturers.get_all_manufacturers.return_value = []
    dm.families.get_all_families.return_value = []
    dm.serials.get_catalog_with_theoretical_stock.return_value = [
        {
            "Product_ID": 101,
            "Brand_Mark": "LIOFILCHEM DIAGNOSTICI",
            "Product_Name": "AMIKACIN AK 30 UG DISQUES ANTIBIOGRAMME",
            "Category_Name": "BACTERIOLOGIE",
            "Manuf_Cat_No": "REF-9012",
            "Color_Finish": "Standard",
            "Physical_Qty": 18,
            "Reserved_Qty": 0,
            "Available_Theoretical_Qty": 18,
            "Unit_Price_TTC": 16660.0,
            "Price_1_TTC": 16660.0,
            "Price_2_TTC": 15800.0,
            "Price_3_TTC": 14900.0,
            "Barcode": "1234567890123",
        },
    ]
    return dm


def test_catalog_price_column_is_right_aligned_text_with_click_tier_menu(qapp, monkeypatch):
    dm = _make_dm()
    desk = OrderDeskWidget(data_manager=dm)
    desk.refresh_catalog()

    # Zero embedded dropdown widget per row
    assert desk.table.cellWidget(0, 6) is None

    hdr6 = desk.table.horizontalHeaderItem(6)
    assert hdr6 is not None and bool(hdr6.textAlignment() & Qt.AlignRight)

    it_price = desk.table.item(0, 6)
    assert it_price is not None
    assert "16 660" in it_price.text()
    assert "▾" not in it_price.text()
    assert bool(it_price.textAlignment() & Qt.AlignRight)

    # Clicking cell 6 opens clean PriceTierMenu on demand
    menu_actions = []

    def _fake_exec(menu_self, pos=None):
        menu_actions.extend(a.text() for a in menu_self.actions())
        return None

    monkeypatch.setattr(QMenu, "exec_", _fake_exec)
    desk._on_catalog_cell_clicked(0, 6)
    assert any("Prix 1" in t for t in menu_actions)
    assert any("Prix 2" in t for t in menu_actions)
    assert any("Prix 3" in t for t in menu_actions)

    # Applying Prix 2 updates cell text & cart unit price
    prod = it_price.data(Qt.UserRole)
    desk._apply_price_tier_to_row(0, prod, "Prix_2", 15800.0)
    assert "15 800" in desk.table.item(0, 6).text()
    assert "[DG]" in desk.table.item(0, 6).text()

    act_w = desk.table.cellWidget(0, 7)
    assert isinstance(act_w, AddActionCellWidget)
    act_w.btn_add.click()
    cart = desk._sessions["SESSION_1"]["cart"]
    assert len(cart) == 1
    assert cart[0]["unit_price_ttc"] == 15800.0


def test_catalog_column_resize_modes_and_no_right_clipping(qapp):
    dm = _make_dm()
    desk = OrderDeskWidget(data_manager=dm)
    desk.resize(1120, 720)
    desk.show()
    qapp.processEvents()

    hdr = desk.table.horizontalHeader()
    assert hdr.sectionResizeMode(0) == QHeaderView.ResizeToContents
    assert hdr.sectionResizeMode(1) == QHeaderView.Stretch
    assert hdr.sectionResizeMode(2) == QHeaderView.ResizeToContents
    assert hdr.sectionResizeMode(3) == QHeaderView.ResizeToContents
    assert hdr.sectionResizeMode(6) == QHeaderView.ResizeToContents

    content = desk.findChild(QWidget, "OrderDeskContentWidget")
    assert content is not None and content.minimumWidth() <= 900
    desk.close()


def test_catalog_empty_state_and_quick_reset(qapp):
    dm = _make_dm()
    desk = OrderDeskWidget(data_manager=dm)
    desk.refresh_catalog()
    assert not desk.table.isHidden()
    assert desk.catalog_empty_state.isHidden()
    assert desk.table.rowCount() == 1

    # Search with no matching results switches to Empty State
    desk.txt_search.setText("NON_EXISTENT_PRODUCT_XYZ")
    desk.refresh_catalog()
    assert desk.table.rowCount() == 0
    assert desk.table.isHidden()
    assert not desk.catalog_empty_state.isHidden()

    # Clicking quick reset button clears search and restores catalog table
    desk.btn_empty_reset.click()
    assert desk.txt_search.text() == ""
    assert desk.table.rowCount() == 1
    assert not desk.table.isHidden()
    assert desk.catalog_empty_state.isHidden()
