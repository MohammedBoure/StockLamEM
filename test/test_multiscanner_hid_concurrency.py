# -*- coding: utf-8 -*-
"""
test/test_multiscanner_hid_concurrency.py
=========================================
Automated Test Suite for:
1. Multi-Scanner / Multi-Session HID Routing (`MultiScannerHIDManager` & `DeviceScanBuffer`):
   - Connecting multiple barcode scanners (`SCANNER_A`, `SCANNER_B`, `SCANNER_DISPATCH`) to the same PC.
   - Routing 100 interleaved character-by-character hardware keystrokes from two scanners simultaneously
     to completely independent sales sessions with ZERO character cross-talk or session contamination.
2. Multi-Role RBAC Permissions (`ROLE_PERMISSION_PRESETS`) and Desk UI Gating (`ApplianceWorkflowTab`).
"""

import os
import sys
import random
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication
from ui.hardware.raw_input_filter import MultiScannerHIDManager
from ui.widgets.appliance_desks import ApplianceWorkflowTab
from database.user_manager import UserManager

ROLE_PERMISSION_PRESETS = UserManager.ROLE_PERMISSION_PRESETS


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_multiscanner_100_interleaved_scans_zero_crosstalk(qapp):
    """
    Simulates two physical USB barcode scanners (`SCANNER_A` and `SCANNER_B`) connected to the
    same PC and firing character-by-character keystrokes concurrently in interleaved order.
    Verifies:
    - Every barcode from `SCANNER_A` is routed exclusively to `SESSION_1`.
    - Every barcode from `SCANNER_B` is routed exclusively to `SESSION_2`.
    - Zero character corruption or cross-talk across 100 total scans (50 per scanner).
    """
    hid_mgr = MultiScannerHIDManager()
    hid_mgr.bind_scanner_to_session("SCANNER_A", "SESSION_1")
    hid_mgr.bind_scanner_to_session("SCANNER_B", "SESSION_2")

    session_1_received = []
    session_2_received = []

    hid_mgr.register_session_callback(
        "SESSION_1", lambda dev_id, code: session_1_received.append((dev_id, code))
    )
    hid_mgr.register_session_callback(
        "SESSION_2", lambda dev_id, code: session_2_received.append((dev_id, code))
    )

    expected_a = [f"88060901{i:04d}" for i in range(50)]
    expected_b = [f"42420059{i:04d}" for i in range(50)]

    # Feed character-by-character interleaved keystrokes between SCANNER_A and SCANNER_B
    for code_a, code_b in zip(expected_a, expected_b):
        max_len = max(len(code_a), len(code_b))
        for idx in range(max_len):
            if idx < len(code_a):
                hid_mgr.feed_device_character("SCANNER_A", ord(code_a[idx]))
            if idx < len(code_b):
                hid_mgr.feed_device_character("SCANNER_B", ord(code_b[idx]))
        # Terminate both scans with Enter (0x0D)
        hid_mgr.feed_device_character("SCANNER_A", 0x0D)
        hid_mgr.feed_device_character("SCANNER_B", 0x0D)

    assert len(session_1_received) == 50
    assert len(session_2_received) == 50
    assert [code for _, code in session_1_received] == expected_a
    assert [code for _, code in session_2_received] == expected_b
    assert all(dev == "SCANNER_A" for dev, _ in session_1_received)
    assert all(dev == "SCANNER_B" for dev, _ in session_2_received)


def test_order_desk_multi_session_cart_isolation_and_rbac_tabs(qapp):
    """
    Verifies:
    1. `OrderDeskWidget` inside `ApplianceWorkflowTab` routes scans from `SCANNER_A` into
       `SESSION_1`'s cart and scans from `SCANNER_B` into `SESSION_2`'s cart without mixing items.
    2. `ROLE_PERMISSION_PRESETS` defines distinct permissions for Order Desk, Cashier Desk,
       Dispatch Desk, SAV Desk, and Admin.
    3. `ApplianceWorkflowTab.apply_rbac_permissions` enables only the permitted desk tabs for each role.
    """
    assert "Order_Desk" in ROLE_PERMISSION_PRESETS
    assert "Cashier_Desk" in ROLE_PERMISSION_PRESETS
    assert "Dispatch_Desk" in ROLE_PERMISSION_PRESETS
    assert "SAV_Desk" in ROLE_PERMISSION_PRESETS
    assert "Admin" in ROLE_PERMISSION_PRESETS

    hid_mgr = MultiScannerHIDManager()
    workflow_tab = ApplianceWorkflowTab(data_manager=None, hid_manager=hid_mgr)

    # Scan Bosch Fridge barcode (4242005198030) on SCANNER_A -> routes to SESSION_1
    hid_mgr.simulate_scan("SCANNER_A", "4242005198030")
    # Scan LG Washer barcode (8806098321092) twice on SCANNER_B -> routes to SESSION_2
    hid_mgr.simulate_scan("SCANNER_B", "8806098321092")
    hid_mgr.simulate_scan("SCANNER_B", "8806098321092")

    cart_s1 = workflow_tab.order_desk._sessions["SESSION_1"]["cart"]
    cart_s2 = workflow_tab.order_desk._sessions["SESSION_2"]["cart"]

    assert len(cart_s1) == 1
    assert cart_s1[0]["product_id"] == 101
    assert cart_s1[0]["quantity"] == 1

    assert len(cart_s2) == 1
    assert cart_s2[0]["product_id"] == 102
    assert cart_s2[0]["quantity"] == 2

    # Verify RBAC tab gating for a Cashier-only user
    workflow_tab.apply_rbac_permissions({"desk.cashier.settle_bon_c", "desk.cashier.record_versement"})
    assert workflow_tab.desk_tabs.isTabEnabled(0) is False  # Order Desk disabled
    assert workflow_tab.desk_tabs.isTabEnabled(1) is True   # Caisse Desk enabled
    assert workflow_tab.desk_tabs.isTabEnabled(2) is False  # Dispatch Desk disabled
    assert workflow_tab.desk_tabs.isTabEnabled(3) is False  # SAV Desk disabled

    # Verify RBAC tab gating for Admin enables all 5 tabs
    workflow_tab.apply_rbac_permissions({"admin"})
    for idx in range(workflow_tab.desk_tabs.count()):
        assert workflow_tab.desk_tabs.isTabEnabled(idx) is True
