"""Regression tests for Task #5: Paiement Livraison row button clearance, disabled contrast, and compact KPI cards."""

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication, QFrame, QPushButton

from ui.widgets.paiement_livraison import PaiementLivraisonTab


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_dm():
    dm = MagicMock()
    dm.bonds.get_bons_with_payments.return_value = [
        {
            "Order_ID": 1,
            "Order_Number": "3-BLV-20261106-57516",
            "Client_ID": 10,
            "Client_Name": "AZEA",
            "Client_Phone": "0550000001",
            "Bond_Type": "BON_LIVRAISON",
            "Total_Amount_TTC": 2380.0,
            "Total_Paid": 2380.0,
            "Remaining_Amount": 0.0,
            "Payments_Count": 1,
            "Payment_State": "PAID",
            "Order_Date": "2026-11-06",
            "Invoice_No": "BL-LIV-20261106-8",
        },
        {
            "Order_ID": 2,
            "Order_Number": "3-BLV-20261106-99999",
            "Client_ID": 11,
            "Client_Name": "Karim",
            "Client_Phone": "",
            "Bond_Type": "BON_LIVRAISON",
            "Total_Amount_TTC": 5000.0,
            "Total_Paid": 1000.0,
            "Remaining_Amount": 4000.0,
            "Payments_Count": 1,
            "Payment_State": "PARTIAL",
            "Order_Date": "2026-11-06",
            "Invoice_No": "BL-LIV-20261106-9",
        },
        {
            "Order_ID": 3,
            "Order_Number": "BLV-20261105-21206",
            "Client_ID": 12,
            "Client_Name": "azeaze",
            "Client_Phone": "03453453",
            "Bond_Type": "BON_LIVRAISON",
            "Total_Amount_TTC": 0.0,
            "Total_Paid": 0.0,
            "Remaining_Amount": 0.0,
            "Payments_Count": 0,
            "Payment_State": "UNPAID",
            "Order_Date": "2026-11-05",
            "Invoice_No": "FAC-C-20261106-3",
        },
    ]
    return dm


def test_paiement_livraison_row_height_and_unclipped_cell_buttons(qapp):
    tab = PaiementLivraisonTab(data_manager=_make_dm())
    tab.resize(1300, 760)
    tab.show()
    qapp.processEvents()

    assert tab.bons_table.verticalHeader().defaultSectionSize() >= 44
    for r in range(tab.bons_table.rowCount()):
        row_h = tab.bons_table.rowHeight(r)
        assert row_h >= 44
        cell = tab.bons_table.cellWidget(r, 9)
        assert cell is not None
        margins = cell.layout().contentsMargins()
        btn_add = cell.findChild(QPushButton, "btn_row_add")
        btn_edit = cell.findChild(QPushButton, "btn_row_edit")
        assert btn_add is not None and btn_add.height() == 28
        assert btn_edit is not None and btn_edit.height() == 28
        assert btn_add.height() + margins.top() + margins.bottom() <= row_h
    tab.close()


def test_paiement_livraison_disabled_button_contrast_and_tooltips(qapp):
    tab = PaiementLivraisonTab(data_manager=_make_dm())

    # Row 0: Paid bon -> disabled + informative tooltip
    btn0 = tab.bons_table.cellWidget(0, 9).findChild(QPushButton, "btn_row_add")
    assert not btn0.isEnabled()
    assert "soldé" in btn0.toolTip().lower()
    assert "color: #475569;" in btn0.styleSheet()
    assert "background-color: #F1F5F9;" in btn0.styleSheet()

    # Row 1: Partial bon -> enabled
    btn1 = tab.bons_table.cellWidget(1, 9).findChild(QPushButton, "btn_row_add")
    assert btn1.isEnabled()

    # Row 2: Zero-amount bon -> disabled + clear zero-amount tooltip
    btn2 = tab.bons_table.cellWidget(2, 9).findChild(QPushButton, "btn_row_add")
    assert not btn2.isEnabled()
    assert "0,00 DA" in btn2.toolTip()


def test_paiement_livraison_compact_kpi_cards(qapp):
    tab = PaiementLivraisonTab(data_manager=_make_dm())
    tab.resize(1400, 800)
    tab.show()
    qapp.processEvents()

    cards = tab.findChildren(QFrame, "SummaryStatCard")
    assert len(cards) == 4
    for card in cards:
        assert card.height() <= 72
        assert card.width() <= 250
    assert "DA" in tab.lbl_kpi_total.text()
    assert "DA" in tab.lbl_kpi_paid.text()
    assert "DA" in tab.lbl_kpi_rem.text()
    tab.close()
