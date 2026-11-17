"""Regression tests for Task #3: Caisse UX (Auto-focus, Enter/Esc, zero-due lock, confirmation, right-alignment)."""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from ui.widgets.appliance_desks.cashier_desk_view import CashierDeskWidget


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_dm(orders=None, wallet=None):
    dm = MagicMock()
    dm.current_user = {"User_ID": 1}
    if orders is None:
        orders = [
            {
                "Order_ID": 10,
                "Order_Number": "1-BC-20261117-00010",
                "Client_ID": 1,
                "Client_Name": "Karim Mansouri",
                "Bond_Type": "BON_C",
                "Total_Amount_TTC": 25000.0,
                "Status": "CONFIRMED_PENDING_PAYMENT",
                "Amount_Paid_So_Far": 0.0,
                "Amount_Remaining_Credit": 25000.0,
            },
            {
                "Order_ID": 11,
                "Order_Number": "3-BLV-20261117-00011",
                "Client_ID": 2,
                "Client_Name": "Nadia Haddad",
                "Bond_Type": "BON_LIVRAISON",
                "Total_Amount_TTC": 1190.0,
                "Status": "APPROVED_LIVRAISON_PENDING_DISPATCH",
                "Amount_Paid_So_Far": 1190.0,
                "Amount_Remaining_Credit": 0.0,
            },
        ]
    dm.bonds.get_caisse_order_queue.return_value = orders
    dm.bonds.get_client_wallet.return_value = wallet or {
        "current_balance": 0.0,
        "real_deposit_balance": 0.0,
        "virtual_credit_balance": 0.0,
    }
    return dm


def test_caisse_autofocus_enter_by_client_and_escape_clear(qapp):
    dm = _make_dm()
    caisse = CashierDeskWidget(data_manager=dm)
    caisse.show()
    qapp.processEvents()

    # Auto-focus on show
    assert caisse.txt_scan_bon.hasFocus() or qapp.focusWidget() is caisse.txt_scan_bon

    # Enter matches by client name as well as bon number
    caisse.txt_scan_bon.setText("Nadia")
    caisse._on_bon_scanned()
    assert caisse._selected_order is not None
    assert caisse._selected_order["Order_Number"] == "3-BLV-20261117-00011"

    # Escape shortcut resets scan filter and restores focus
    assert hasattr(caisse, "_esc_shortcut")
    caisse._esc_shortcut.activated.emit()
    assert caisse.txt_scan_bon.text() == ""
    assert not caisse.queue_table.isRowHidden(0)
    assert not caisse.queue_table.isRowHidden(1)

    # After finalizing payment, focus returns to scan input
    caisse.queue_table.selectRow(0)
    caisse._on_order_selected()
    caisse.txt_cash.setText("25000")
    with patch("ui.widgets.appliance_desks.cashier_desk_view.QMessageBox.information"):
        caisse._finalize_bon_c()
    assert caisse.txt_scan_bon.hasFocus() or qapp.focusWidget() is caisse.txt_scan_bon
    caisse.close()


def test_caisse_disables_payment_controls_when_reste_is_zero_and_deduplicates_versement(qapp):
    dm = _make_dm()
    caisse = CashierDeskWidget(data_manager=dm)

    # Row 1: BL already 100% paid (Reste = 0.00 DA), wallet = 0.00 DA
    caisse.queue_table.selectRow(1)
    caisse._on_order_selected()

    assert not caisse.txt_cash.isEnabled()
    assert not caisse.btn_exact_cash.isEnabled()
    assert all(not chip.isEnabled() for chip in caisse.quick_cash_buttons)
    assert all(not pm.isEnabled() for pm in caisse.payment_method_buttons.values())
    assert not caisse.cb_wallet.isEnabled()
    assert not caisse.lbl_change_due.isHidden()
    assert "0,00 DA" in caisse.lbl_change_due.text()

    # Duplicate wallet buttons hidden when redundant/zero balance
    assert caisse.btn_inspect_wallet.isHidden()
    assert caisse.btn_use_versement.isHidden()

    # Row 0: Unpaid order enables payment inputs & chips
    caisse.queue_table.selectRow(0)
    caisse._on_order_selected()
    assert caisse.txt_cash.isEnabled()
    assert caisse.btn_exact_cash.isEnabled()
    assert all(chip.isEnabled() for chip in caisse.quick_cash_buttons)
    assert all(pm.isEnabled() for pm in caisse.payment_method_buttons.values())
    caisse.close()


def test_caisse_retirer_bon_confirmation_mentions_bon_and_client(qapp):
    dm = _make_dm()
    caisse = CashierDeskWidget(data_manager=dm)
    caisse.queue_table.selectRow(0)
    caisse._on_order_selected()

    with patch("ui.widgets.appliance_desks.cashier_desk_view.QMessageBox.question", return_value=QMessageBox.No) as mock_q:
        caisse._remove_selected_bon()
        mock_q.assert_called_once()
        msg_text = mock_q.call_args[0][2]
        assert "1-BC-20261117-00010" in msg_text
        assert "Karim Mansouri" in msg_text
        dm.bonds.cancel_or_remove_caisse_order.assert_not_called()
    caisse.close()


def test_caisse_montant_ttc_column_is_right_aligned(qapp):
    dm = _make_dm()
    caisse = CashierDeskWidget(data_manager=dm)

    hdr_item = caisse.queue_table.horizontalHeaderItem(3)
    assert hdr_item is not None
    assert bool(hdr_item.textAlignment() & Qt.AlignRight)
    for row in range(caisse.queue_table.rowCount()):
        cell = caisse.queue_table.item(row, 3)
        assert cell is not None
        assert bool(cell.textAlignment() & Qt.AlignRight)
    caisse.close()
