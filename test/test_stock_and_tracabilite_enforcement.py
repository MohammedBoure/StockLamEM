# -*- coding: utf-8 -*-
"""
test/test_stock_and_tracabilite_enforcement.py
==============================================
Verification Test Suite for Task #4:
1. Direct, accurate link between Products and Physical Stock (Batches + IN_STOCK Serials).
2. Strict prohibition of product exit from stock until Bon de Sortie is confirmed at Dispatch Desk.
3. Immutable logging and traceability of all movements (Reception, Sortie, Retour) in Stock_Movement_Log.
4. UI integration of Tab 5 (Traçabilité & Lots) with both physical stock catalog and movement audit table.
"""

import os
import sys
from decimal import Decimal
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from database.serial_tracking_manager import SerialTrackingManager
from database.bond_lifecycle_manager import (
    BondLifecycleManager,
    SecurityViolationException,
    StateCollisionException,
)
from database.sales_manager import SalesManager
from test.test_serial_uniqueness_and_concurrency import StatefulMockDB


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_db():
    return StatefulMockDB()


def test_accurate_product_physical_stock_link(mock_db):
    """
    Requirement 1: ربط كافة المنتجات بالمخزون الفعلي بشكل دقيق ومباشر.
    Verifies that:
    - Products have real-time direct calculation of physical stock.
    - Physical_Qty matches available batch quantity and count of IN_STOCK serials.
    - Theoretical reservation does NOT alter physical stock.
    """
    serial_mgr = SerialTrackingManager(mock_db)
    bond_mgr = BondLifecycleManager(mock_db)

    # 1. Register a product
    p_res = serial_mgr.register_product_with_attributes(
        name="Lave-vaisselle Serie 6",
        mark="Bosch",
        categorie="Lave-vaisselle",
        coloure="Inox",
        selling_price_ht=Decimal("120000.00"),
        requires_serial=True,
    )
    pid = p_res["product_id"]

    # Initial stock before batch arrival: 0
    summary0 = serial_mgr.get_product_stock_summary(pid)
    assert summary0["Physical_Qty"] == 0
    assert summary0["Available_Theoretical_Qty"] == 0
    assert summary0["Serials_In_Stock"] == 0

    # 2. Receive batch of 3 units with unique serials
    b_res = serial_mgr.register_batch_arrival(
        product_id=pid,
        supplier_id=1,
        po_id=None,
        reception_date="2026-11-05",
        unit_cost_ht=Decimal("95000.00"),
        freight_customs=Decimal("0.00"),
        serial_numbers=["SN-DW-101", "SN-DW-102", "SN-DW-103"],
        user_id=10,
    )
    assert b_res["success"] is True

    # Check that batch arrival wrote to Stock_Movement_Log (Traçabilité)
    reception_logs = [l for l in mock_db.stock_movement_logs if l["Movement_Type"] == "Purchase_Receive"]
    assert len(reception_logs) == 1
    assert reception_logs[0]["Product_ID"] == pid
    assert reception_logs[0]["Qty_Change"] == 3
    assert reception_logs[0]["Stock_After"] == 3

    # Check physical stock directly linked
    summary1 = serial_mgr.get_product_stock_summary(pid)
    assert summary1["Physical_Qty"] == 3
    assert summary1["Theoretical_Reserved_Qty"] == 0
    assert summary1["Available_Theoretical_Qty"] == 3
    assert summary1["Serials_In_Stock"] == 3

    # 3. Order Desk creates theoretical order for 2 units
    ord_res = bond_mgr.create_sales_order_draft(
        client_id=1,
        order_desk_user_id=5,
        items=[{"product_id": pid, "quantity": 2, "unit_price_ttc": "142800.00"}],
        bond_type="BON_C",
    )
    assert ord_res["success"] is True

    # CRITICAL: Physical stock MUST remain 3! Only theoretical reservation increases to 2
    summary2 = serial_mgr.get_product_stock_summary(pid)
    assert summary2["Physical_Qty"] == 3, "Physical stock must NOT decrease at Order Desk!"
    assert summary2["Theoretical_Reserved_Qty"] == 2
    assert summary2["Available_Theoretical_Qty"] == 1
    assert summary2["Serials_In_Stock"] == 3, "All physical serials must still be IN_STOCK!"


def test_prohibition_of_stock_exit_without_bon_de_sortie(mock_db):
    """
    Requirement 2 & 3:
    - منع تسجيل خروج أي منتج من المخزون إلا بعد صدور وتأكيد وصل الخروج (Sortie) من مكتب الخروج حصراً.
    - تسجيل وتوثيق كافة هذه الحركات والعمليات بدقة داخل سجل التتبع (Traçabilité).
    """
    serial_mgr = SerialTrackingManager(mock_db)
    bond_mgr = BondLifecycleManager(mock_db)

    # Register product and receive 2 units
    p_res = serial_mgr.register_product_with_attributes(
        name="Four Micro-ondes Grill",
        mark="LG",
        categorie="Micro-ondes",
        coloure="Noir",
        requires_serial=True,
    )
    pid = p_res["product_id"]

    b_res = serial_mgr.register_batch_arrival(
        product_id=pid,
        supplier_id=1,
        po_id=None,
        reception_date="2026-11-05",
        unit_cost_ht=Decimal("25000.00"),
        freight_customs=Decimal("0.00"),
        serial_numbers=["SN-MO-501", "SN-MO-502"],
        user_id=1,
    )
    batch_id = b_res["batch_id"]

    # Direct exit assertion should raise PermissionError
    with pytest.raises(PermissionError) as perm_info:
        serial_mgr.assert_product_exit_authorized(pid)
    assert "exige un Bon de Sortie émis par le Bureau de Sortie" in str(perm_info.value)

    # Create theoretical order
    ord_res = bond_mgr.create_sales_order_draft(
        client_id=1,
        order_desk_user_id=1,
        items=[{"product_id": pid, "quantity": 1, "unit_price_ttc": "35000.00"}],
        bond_type="BON_C",
    )
    oid = ord_res["order_id"]
    lid = [l["Line_ID"] for l in mock_db.order_lines.values() if l["Order_ID"] == oid][0]

    # Attempt to dispatch cancelled or unconfirmed order
    mock_db.orders[oid]["Status"] = "CANCELLED"
    with pytest.raises(SecurityViolationException) as sec_info:
        bond_mgr.validate_and_dispatch_serials(
            order_id=oid,
            invoice_id=100,
            storekeeper_user_id=20,
            scanned_serial_numbers=[{"order_line_id": lid, "serial_number": "SN-MO-501"}],
        )
    assert "Sortie physique non autorisée" in str(sec_info.value)

    # Restore order to valid status (authorized at Caisse)
    mock_db.orders[oid]["Status"] = "PAID_PENDING_DISPATCH"

    # Now execute official Bon de Sortie at Dispatch Desk
    exit_res = bond_mgr.validate_and_dispatch_serials(
        order_id=oid,
        invoice_id=100,
        storekeeper_user_id=20,
        scanned_serial_numbers=[{"order_line_id": lid, "serial_number": "SN-MO-501"}],
    )
    assert exit_res["success"] is True
    assert exit_res["exit_bond_number"].startswith("BS-")
    assert exit_res["financial_impact"] == "NONE"

    # 1. Physical stock in batch is now decremented to 1
    assert mock_db.batches[batch_id]["Quantity_Current"] == 1
    assert mock_db.batches[batch_id]["Theoretical_Reserved_Qty"] == 0

    # 2. Serial status transitioned to DISPATCHED
    assert mock_db.serials_by_sn["SN-MO-501"]["Status"] == "DISPATCHED"
    assert mock_db.serials_by_sn["SN-MO-502"]["Status"] == "IN_STOCK"

    # 3. Traçabilité (Stock_Movement_Log) recorded the exit!
    exit_logs = [l for l in mock_db.stock_movement_logs if l["Movement_Type"] == "Sale"]
    assert len(exit_logs) == 1
    assert exit_logs[0]["Product_ID"] == pid
    assert exit_logs[0]["Qty_Change"] == -1
    assert exit_logs[0]["Stock_After"] == 1
    assert "Bon de Sortie" in exit_logs[0]["Notes"]
    assert "SN-MO-501" in exit_logs[0]["Notes"]

    # 4. Double-dispatch of already dispatched unit must be rejected
    with pytest.raises(StateCollisionException) as col_info:
        bond_mgr.validate_and_dispatch_serials(
            order_id=oid,
            invoice_id=100,
            storekeeper_user_id=20,
            scanned_serial_numbers=[{"order_line_id": lid, "serial_number": "SN-MO-501"}],
        )
    assert "is not IN_STOCK" in str(col_info.value)


def test_serial_batch_view_ui_traceability_tab(qapp):
    """
    Requirement 3 UI:
    Verifies that SerialBatchRegistryWidget ("5. Traçabilité & Lots") includes:
    1. Tab 1: Physical Stock and Product/Batch overview.
    2. Tab 2: Live Journal de Traçabilité & Mouvements with movement filters.
    """
    from ui.widgets.appliance_desks.serial_batch_view import SerialBatchRegistryWidget
    from PySide6.QtWidgets import QTabWidget, QTableWidget

    widget = SerialBatchRegistryWidget(data_manager=None)

    # 1. Verify QTabWidget inner tabs
    assert hasattr(widget, "inner_tabs")
    assert isinstance(widget.inner_tabs, QTabWidget)
    assert widget.inner_tabs.count() == 2
    assert "Lots" in widget.inner_tabs.tabText(0)
    assert "Traçabilité" in widget.inner_tabs.tabText(1)

    # 2. Verify Tab 1: Catalog table displays Physical Stock accurately
    assert hasattr(widget, "catalog_table")
    assert widget.catalog_table.rowCount() >= 3
    # Check headers include Stock Physique and Disponible Vente
    headers = [widget.catalog_table.horizontalHeaderItem(i).text() for i in range(widget.catalog_table.columnCount())]
    assert any("Stock Physique" in h for h in headers)
    assert any("Disponible Vente" in h for h in headers)

    # 3. Verify Tab 2: Journal de Traçabilité table and filters
    assert hasattr(widget, "trace_table")
    assert hasattr(widget, "cbo_trace_type")
    assert hasattr(widget, "txt_trace_search")

    widget.refresh_traceability()
    assert widget.trace_table.rowCount() >= 3

    # Filter by 'Sorties Magasin'
    widget.cbo_trace_type.setCurrentIndex(1)
    for r in range(widget.trace_table.rowCount()):
        m_type = widget.trace_table.item(r, 1).text()
        assert "Sortie" in m_type
