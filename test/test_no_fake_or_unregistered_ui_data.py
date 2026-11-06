# -*- coding: utf-8 -*-
"""
test/test_no_fake_or_unregistered_ui_data.py
=============================================
Verification tests for Task #4:
"لا أريد أي بيانات غير حقيقة لم تضف في البرنامج بالفعل بل موجودة فقط على الواجهة"
Verifies that none of the appliance desk UI interfaces (SAV, Caisse, Dispatch, Order Desk,
and Serial/Lots Registry) inject mock, fake, placeholder, or hardcoded showcase rows when
the database returns empty data. If data hasn't been added to the program, the interface
must strictly display empty states (0 rows / 0 counts).
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication, QScrollArea
from ui.widgets.appliance_desks.sav_workspace_view import SAVWorkspaceTab
from ui.widgets.appliance_desks.sav_kanban_view import SAVKanbanWidget
from ui.widgets.appliance_desks.cashier_desk_view import CashierDeskWidget
from ui.widgets.appliance_desks.dispatch_desk_view import DispatchDeskWidget
from ui.widgets.appliance_desks.serial_batch_view import SerialBatchRegistryWidget
from ui.widgets.appliance_desks.order_desk_view import OrderDeskWidget


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def empty_mock_data_manager():
    """Mock DataManager simulating a real fresh database with zero records."""
    dm = MagicMock()
    dm.current_user = {"User_ID": 1, "Username": "admin"}

    # Clients: 0 clients
    dm.clients = MagicMock()
    dm.clients.get_all_clients.return_value = []

    # Products & Serials: 0 products
    dm.serials = MagicMock()
    dm.serials.get_catalog_with_theoretical_stock.return_value = []
    dm.serials.get_serial_details.return_value = None

    # SAV: 0 tickets
    dm.sav = MagicMock()
    dm.sav.get_all_sav_tickets.return_value = []

    # Bonds / Caisse / Dispatch: 0 orders
    dm.bonds = MagicMock()
    dm.bonds.get_caisse_order_queue.return_value = []
    dm.bonds.get_dispatch_order_queue.return_value = []

    # Stock Movement Log: 0 audit logs
    dm.stock_movement_log = MagicMock()
    dm.stock_movement_log.get_movements_log.return_value = []

    # Manufacturers & Families: empty
    dm.manufacturers = MagicMock()
    dm.manufacturers.get_all_manufacturers.return_value = []
    dm.families = MagicMock()
    dm.families.get_all_families.return_value = []

    return dm


def test_sav_workspace_displays_zero_fake_tickets_when_db_is_empty(qapp, empty_mock_data_manager):
    """Verifies that SAVWorkspaceTab never displays hardcoded showcase tickets if DB is empty."""
    tab = SAVWorkspaceTab(data_manager=empty_mock_data_manager)
    tab.refresh_tickets()

    # KPI badges must all show 0
    assert "0" in tab.lbl_kpi_total.text()
    assert "0" in tab.lbl_kpi_received.text()
    assert "0" in tab.lbl_kpi_sent.text()
    assert "0" in tab.lbl_kpi_returned.text()
    assert "0" in tab.lbl_kpi_closed.text()
    assert "0" in tab.lbl_kpi_irreparable.text()

    # All stage tables must have exactly 0 rows
    for key, table in tab._stage_tables.items():
        assert table.rowCount() == 0, f"Table '{key}' in SAVWorkspaceTab contains fake rows! rowCount={table.rowCount()}"

    # Verify no fake clients or tickets exist in data
    assert len(tab._all_tickets) == 0


def test_sav_kanban_displays_zero_cards_when_db_is_empty(qapp, empty_mock_data_manager):
    """Verifies that SAVKanbanWidget displays zero cards if DB has zero tickets."""
    kanban = SAVKanbanWidget(data_manager=empty_mock_data_manager)
    kanban.refresh_tickets()

    # Total cards across all columns must be 0 (excluding the stretch item)
    total_cards = sum(
        max(0, col.findChild(QScrollArea).widget().layout().count() - 1)
        for col in kanban._columns.values()
    )
    assert total_cards == 0, f"SAVKanbanWidget contains fake cards! count={total_cards}"


def test_cashier_desk_displays_zero_orders_when_queue_is_empty(qapp, empty_mock_data_manager):
    """Verifies that CashierDeskWidget displays an empty queue table if DB has no unpaid orders."""
    caisse = CashierDeskWidget(data_manager=empty_mock_data_manager)
    caisse.refresh_queue()

    assert caisse.queue_table.rowCount() == 0, "CashierDeskWidget contains fake orders!"
    assert len(caisse._orders_queue) == 0


def test_dispatch_desk_displays_zero_orders_when_queue_is_empty(qapp, empty_mock_data_manager):
    """Verifies that DispatchDeskWidget displays an empty order list if DB has no dispatch orders."""
    dispatch = DispatchDeskWidget(data_manager=empty_mock_data_manager)
    dispatch.refresh_dispatch_queue()

    assert dispatch.cbo_orders.count() == 0, "DispatchDeskWidget contains fake order entries in combo!"
    assert dispatch.table.rowCount() == 0, "DispatchDeskWidget contains fake line items!"
    assert len(dispatch._dispatch_orders) == 0


def test_serial_batch_view_displays_zero_rows_when_db_is_empty(qapp, empty_mock_data_manager):
    """Verifies that SerialBatchRegistryWidget displays 0 catalog products and 0 trace logs if DB is empty."""
    registry = SerialBatchRegistryWidget(data_manager=empty_mock_data_manager)
    registry.refresh_products()
    registry.refresh_traceability()

    assert registry.catalog_table.rowCount() == 0, "SerialBatchRegistryWidget contains fake catalog products!"
    assert registry.trace_table.rowCount() == 0, "SerialBatchRegistryWidget contains fake movement logs!"


def test_order_desk_displays_zero_rows_when_catalog_is_empty(qapp, empty_mock_data_manager):
    """Verifies that OrderDeskWidget displays 0 items and no unregistered clients if DB is empty."""
    desk = OrderDeskWidget(data_manager=empty_mock_data_manager)
    desk.refresh_catalog()

    assert desk.table.rowCount() == 0, "OrderDeskWidget contains fake products in catalog table!"
    assert len(desk._catalog_filtered_items) == 0
    assert "0" in desk.lbl_catalog_count_badge.text() or "0" in desk.lbl_count_info.text()
