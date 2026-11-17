"""Regression tests for Task #6: Cross-screen UI/UX consistency (Sortie Magasin, Versement, Stock & Magasin)."""

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton

from ui.widgets.appliance_desks.dispatch_desk_view import DispatchDeskWidget
from ui.widgets.inventory.tabs_batches import BatchesTab
from ui.widgets.versement import BonPaymentAddDialog, BonPaymentsManageDialog, VersementTab


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_dispatch_dm(orders):
    dm = MagicMock()
    dm.bonds.get_dispatch_order_queue.return_value = orders
    return dm


def _make_versement_dm(bons):
    dm = MagicMock()
    dm.bonds.get_bons_with_payments.return_value = bons
    dm.bonds.get_bon_payments.return_value = {
        "bon": {
            "Order_ID": 1,
            "Order_Number": "4-VRS-001",
            "Client_Name": "Client Test",
            "Invoice_No": "FAC-1",
            "Total_Amount_TTC": 5000.0,
            "Total_Paid": 5000.0,
            "Remaining_Amount": 0.0,
        },
        "payments": [
            {
                "payment_id": 10,
                "entry_type": "CLIENT_PAYMENT",
                "payment_date": "2026-11-17",
                "payment_method": "Cash",
                "amount": 5000.0,
                "notes": "Test",
                "editable": True,
                "deletable": True,
            }
        ],
    }
    return dm


def _make_batches_mgr(batches):
    mgr = MagicMock()
    mgr.families.get_all_families.return_value = []
    mgr.manufacturers.get_all_manufacturers.return_value = []
    mgr.automates.get_all_automates.return_value = []
    mgr.suppliers.get_all_suppliers.return_value = []
    mgr.locations.get_all_locations_flat.return_value = []
    mgr.batches.get_all_batches_with_details.return_value = batches
    mgr.batches.get_priority_groups_summary.return_value = []
    return mgr


def test_sortie_magasin_shortcuts_empty_state_and_disabled_tooltip(qapp):
    orders = [
        {
            "Order_ID": 1,
            "Order_Number": "1-BC-0001",
            "Client_Name": "Ali",
            "Bond_Type": "BON_C",
            "lines": [
                {"Line_ID": 1, "Product_ID": 10, "Brand_Mark": "LG", "Product_Name": "TV", "Quantity_Ordered": 1, "Quantity_Dispatched": 0}
            ],
        }
    ]
    dm = _make_dispatch_dm(orders)
    desk = DispatchDeskWidget(data_manager=dm)

    # Disabled emit button explains why
    assert not desk.btn_emit_sortie.isEnabled()
    assert "N° de Série" in desk.btn_emit_sortie.toolTip()

    # Filter with no match -> Empty State visible
    desk.txt_order_search.setText("NO_MATCH_999")
    assert not desk.dispatch_empty_state.isHidden()
    assert desk.table.isHidden()
    assert "Sélectionnez un bon" in desk.btn_emit_sortie.toolTip()

    # Esc resets filter and restores table
    desk._shortcut_esc.activated.emit()
    assert desk.txt_order_search.text() == ""
    assert desk.dispatch_empty_state.isHidden()
    assert not desk.table.isHidden()

    # F5 / Ctrl+R triggers refresh
    before_calls = dm.bonds.get_dispatch_order_queue.call_count
    desk._shortcut_f5.activated.emit()
    desk._shortcut_ctrl_r.activated.emit()
    assert dm.bonds.get_dispatch_order_queue.call_count == before_calls + 2


def test_versement_shortcuts_empty_state_alignment_and_dialogs(qapp):
    bons = [
        {
            "Order_ID": 1,
            "Order_Number": "4-VRS-001",
            "Client_ID": 1,
            "Client_Name": "Client A",
            "Bond_Type": "BON_VERSEMENT",
            "Total_Amount_TTC": 5000.0,
            "Total_Paid": 2000.0,
            "Remaining_Amount": 3000.0,
            "Payments_Count": 1,
            "Payment_State": "PARTIAL",
            "Order_Date": "2026-11-17",
            "Invoice_No": "FAC-1",
        }
    ]
    dm = _make_versement_dm(bons)
    tab = VersementTab(data_manager=dm)

    # Right-aligned monetary headers
    for col in (4, 5, 6):
        assert bool(tab.bons_table.horizontalHeaderItem(col).textAlignment() & Qt.AlignRight)

    # Empty state on unmatched filter + Esc reset
    tab.txt_search.setText("MISSING_BON_XYZ")
    assert not tab.bons_empty_state.isHidden()
    assert tab.bons_table.isHidden()

    tab._shortcut_esc.activated.emit()
    assert tab.txt_search.text() == ""
    assert tab.bons_empty_state.isHidden()
    assert not tab.bons_table.isHidden()

    before_calls = dm.bonds.get_bons_with_payments.call_count
    tab._shortcut_f5.activated.emit()
    tab._shortcut_ctrl_r.activated.emit()
    assert dm.bonds.get_bons_with_payments.call_count == before_calls + 2

    # Manage dialog row height >= 44 and disabled tooltip
    dlg = BonPaymentsManageDialog(data_manager=dm, order_id=1)
    assert dlg.table.verticalHeader().defaultSectionSize() >= 44
    assert dlg.table.rowHeight(0) >= 44
    assert not dlg.btn_add_payment.isEnabled()
    assert "soldé" in dlg.btn_add_payment.toolTip().lower()
    btns = dlg.table.cellWidget(0, 5).findChildren(QPushButton)
    assert all(b.height() == 28 for b in btns)

    # Add dialog disabled save button has tooltip
    add_dlg = BonPaymentAddDialog(data_manager=dm, bon_data=bons[0])
    add_dlg.txt_amount.setValue(0.0)
    assert not add_dlg.btn_save.isEnabled()
    assert "montant" in add_dlg.btn_save.toolTip().lower()


def test_stock_actuel_monetary_right_alignment_shortcuts_and_empty_state(qapp):
    batches = [
        {
            "Batch_ID": 1,
            "Product_Name": "Analyseur X",
            "Stock_Unit": "U",
            "Quantity_Current": 5,
            "Quantity_Initial": 5,
            "Unit_Price_Received": 10000.0,
            "Discount_Percent": 0.0,
            "Tax_Rate_Percent": 0.0,
            "Selling_Price_HT": 15000.0,
            "Selling_Price_HT_2": 14000.0,
            "Selling_Price_HT_3": 13000.0,
            "Selling_Price_HT_4": 12000.0,
            "Lot_Number": "L-100",
        }
    ]
    mgr = _make_batches_mgr(batches)
    tab = BatchesTab(mgr)
    tab.current_user = {"Role": "Admin", "Permissions": {"tab_inv_financials": True}}
    tab.load_data()

    # All 7 monetary columns right-aligned in headers and rows
    for col in (3, 4, 5, 6, 19, 20, 21):
        assert bool(tab.table.horizontalHeaderItem(col).textAlignment() & Qt.AlignRight)
        cell = tab.table.item(0, col)
        assert cell is not None
        assert bool(cell.textAlignment() & Qt.AlignRight)

    # Empty state when search misses, Esc restores
    tab.search_input.setText("NO_BATCH_MATCH_XYZ")
    assert not tab.batches_empty_state.isHidden()
    assert tab.table.isHidden()

    tab._shortcut_esc.activated.emit()
    assert tab.search_input.text() == ""
    assert tab.batches_empty_state.isHidden()
    assert not tab.table.isHidden()

    before_calls = mgr.batches.get_all_batches_with_details.call_count
    tab._shortcut_f5.activated.emit()
    tab._shortcut_ctrl_r.activated.emit()
    assert mgr.batches.get_all_batches_with_details.call_count == before_calls + 2
