# -*- coding: utf-8 -*-
"""
test/test_cashier_desk_task3_enhancements.py
============================================
Automated Test Suite for Task #3 in Cashier Desk (Bureaux & SAV -> 2. Caisse & Règlements):
1. Validation buttons heightened for prominent tactile interaction:
   - btn_val_bon_c >= 46px
   - btn_val_credit >= 42px
   - btn_val_livraison >= 42px
2. Bottom operations buttons heightened for clear accessibility:
   - btn_versement >= 44px (Enregistrer Versement Client / Dépôt)
   - btn_retour >= 44px (Émettre Bon de Retour / Versement Virtuel)
3. Modal Dialog action buttons heightened:
   - BonRetourDialog (Valider / Annuler) >= 40px
   - AdminAuthModal (Autoriser / Annuler) >= 40px
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication, QPushButton
from ui.widgets.appliance_desks.cashier_desk_view import (
    AdminAuthModal,
    BonRetourDialog,
    CashierDeskWidget,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_data_manager():
    dm = MagicMock()
    dm.current_user = {"User_ID": 1, "Username": "caissier"}
    dm.bonds = MagicMock()
    dm.bonds.get_caisse_order_queue.return_value = [
        {
            "Order_ID": 10,
            "Order_Number": "BC-0010",
            "Client_ID": 1,
            "Client_Name": "Yacine Benali",
            "Bond_Type": "BON_C",
            "Total_Amount_TTC": 125000.0,
            "Status": "CONFIRMED_PENDING_PAYMENT",
        }
    ]
    dm.bonds.get_client_wallet_summary.return_value = {
        "real_cash_versement": 50000.0,
        "virtual_credit_avoir": 20000.0,
        "total_wallet_balance": 70000.0,
    }
    return dm


def test_cashier_desk_validation_buttons_height(qapp, mock_data_manager):
    """Verifies that all validation buttons on the right console have increased height."""
    desk = CashierDeskWidget(data_manager=mock_data_manager)

    # 1. Valider Bon Comptant
    assert hasattr(desk, "btn_val_bon_c")
    h_bon_c = desk.btn_val_bon_c.minimumHeight() or desk.btn_val_bon_c.height()
    assert h_bon_c >= 46, f"btn_val_bon_c height {h_bon_c}px < 46px"

    # 2. Autoriser Bon Crédit
    assert hasattr(desk, "btn_val_credit")
    h_credit = desk.btn_val_credit.minimumHeight() or desk.btn_val_credit.height()
    assert h_credit >= 42, f"btn_val_credit height {h_credit}px < 42px"

    # 3. Valider Bon de Livraison
    assert hasattr(desk, "btn_val_livraison")
    h_livraison = desk.btn_val_livraison.minimumHeight() or desk.btn_val_livraison.height()
    assert h_livraison >= 42, f"btn_val_livraison height {h_livraison}px < 42px"


def test_cashier_desk_bottom_operations_buttons_height(qapp, mock_data_manager):
    """Verifies that the bottom action buttons for saving/versement and Bon de Retour have heightened size."""
    desk = CashierDeskWidget(data_manager=mock_data_manager)

    # 1. Enregistrer un Versement Client (Dépôt Espèces)
    assert hasattr(desk, "btn_versement")
    h_vers = desk.btn_versement.minimumHeight() or desk.btn_versement.height()
    assert h_vers >= 44, f"btn_versement height {h_vers}px < 44px"

    # 2. Émettre Bon de Retour (Versement Virtuel)
    assert hasattr(desk, "btn_retour")
    h_ret = desk.btn_retour.minimumHeight() or desk.btn_retour.height()
    assert h_ret >= 44, f"btn_retour height {h_ret}px < 44px"


def test_cashier_modal_dialogs_buttons_height(qapp, mock_data_manager):
    """Verifies that the modal dialogs (BonRetourDialog & AdminAuthModal) have heightened buttons."""
    # 1. BonRetourDialog
    dlg_retour = BonRetourDialog(data_manager=mock_data_manager)
    buttons_ret = dlg_retour.findChildren(QPushButton)
    assert len(buttons_ret) >= 2
    for b in buttons_ret:
        h = b.minimumHeight() or b.height()
        assert h >= 40, f"BonRetourDialog button '{b.text()}' height {h}px < 40px"

    # 2. AdminAuthModal
    dlg_admin = AdminAuthModal(
        client_name="Test Client",
        requested_amount=50000.0,
        data_manager=mock_data_manager,
    )
    buttons_adm = dlg_admin.findChildren(QPushButton)
    assert len(buttons_adm) >= 2
    for b in buttons_adm:
        h = b.minimumHeight() or b.height()
        assert h >= 40, f"AdminAuthModal button '{b.text()}' height {h}px < 40px"
