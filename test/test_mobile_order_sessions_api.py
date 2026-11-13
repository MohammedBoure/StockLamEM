"""End-to-end tests for Mobile Companion Order Desk Sessions API & Bridge."""

import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api import build_server
from api.auth import FIXED_API_TOKEN
from tools.mobile_order_session_bridge import MobileOrderSessionBridge
from ui.widgets.appliance_desks.order_desk_view import OrderDeskWidget


def _get_qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_mock_data_manager():
    dm = MagicMock()
    dm.clients = MagicMock()
    dm.clients.get_all_clients.return_value = [
        {"Client_ID": 1, "Full_Name": "Client Divers", "Phone": "", "Price_Tier": "Prix_1"},
        {"Client_ID": 2, "Full_Name": "Ali Benali", "Phone": "0550112233", "Price_Tier": "Prix_2"},
    ]
    dm.manufacturers = MagicMock()
    dm.manufacturers.get_all_manufacturers.return_value = []
    dm.families = MagicMock()
    dm.families.get_all_families.return_value = []
    dm.colors = MagicMock()
    dm.colors.get_all_colors.return_value = []
    dm.serials = MagicMock()
    catalog = [
        {
            "Product_ID": 101,
            "Product_Name": "Réfrigérateur 420L",
            "Brand_Mark": "LG",
            "Primary_Ref": "REF-LG-420",
            "All_Refs": "REF-LG-420",
            "Color_Finish": "Inox",
            "Physical_Stock_Qty": 5,
            "Available_Theoretical_Qty": 5,
            "Price_1_TTC": 120000.0,
            "Price_2_TTC": 115000.0,
            "Price_3_TTC": 110000.0,
            "Barcode": "6130000001014",
        }
    ]
    dm.serials.get_catalog_with_theoretical_stock.return_value = catalog
    dm.serials.find_product_by_any_barcode.side_effect = (
        lambda bc: catalog[0] if str(bc).strip() == "6130000001014" else None
    )
    return dm


def _http_json(url: str, method: str = "GET", body: dict | None = None):
    result = {}

    def _worker():
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={"Content-Type": "application/json", "X-API-Key": FIXED_API_TOKEN},
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                result["out"] = (resp.status, json.loads(resp.read().decode("utf-8")))
        except urllib.error.HTTPError as err:
            result["out"] = (err.code, json.loads(err.read().decode("utf-8")))
        except Exception as exc:
            result["err"] = exc

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    app = _get_qapp()
    while t.is_alive():
        app.processEvents()
        t.join(timeout=0.01)
    if "err" in result:
        raise result["err"]
    return result["out"]


class TestMobileOrderSessionsAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = _get_qapp()

    def setUp(self):
        self.dm = _make_mock_data_manager()
        self.desk = OrderDeskWidget(self.dm)
        self.bridge = MobileOrderSessionBridge(self.desk)
        self.server = build_server(
            "127.0.0.1",
            0,
            data_manager=self.dm,
            order_session_bridge=self.bridge,
        )
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.desk.close()

    def test_create_session_and_add_products_from_mobile_api(self):
        base = f"http://127.0.0.1:{self.port}"

        # 1. List initial sessions
        status, res = _http_json(f"{base}/api/order-sessions")
        self.assertEqual(status, 200)
        self.assertTrue(res["success"])
        self.assertEqual(len(res["sessions"]), 1)

        # 2. List clients & search catalog
        status, clients_res = _http_json(f"{base}/api/order-sessions/clients?search=Ali")
        self.assertEqual(status, 200)
        self.assertEqual(clients_res["clients"][0]["client_id"], 2)

        status, cat_res = _http_json(f"{base}/api/order-sessions/catalog?search=REF-LG")
        self.assertEqual(status, 200)
        self.assertEqual(cat_res["products"][0]["product_id"], 101)

        # 3. Create new session for Client 2 without switching desktop's active tab
        status, created = _http_json(
            f"{base}/api/order-sessions",
            method="POST",
            body={"client_id": 2, "label": "Ali - Salle 1", "created_by": "Karim"},
        )
        self.assertEqual(status, 201)
        self.assertTrue(created["success"])
        new_sid = created["session"]["session_id"]
        self.assertEqual(created["session"]["client_id"], 2)
        self.assertEqual(self.desk._active_session_id, "SESSION_1")
        self.assertTrue(self.desk._sessions[new_sid]["has_event"])

        # 4. Add product by product_id (qty=2)
        status, add1 = _http_json(
            f"{base}/api/order-sessions/{new_sid}/items",
            method="POST",
            body={"product_id": 101, "quantity": 2, "added_by": "Karim"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(add1["session"]["item_count"], 2)
        self.assertEqual(add1["session"]["items"][0]["unit_price_ttc"], 115000.0)

        # 5. Add 1 more by barcode
        status, add2 = _http_json(
            f"{base}/api/order-sessions/{new_sid}/items",
            method="POST",
            body={"barcode": "6130000001014", "quantity": 1, "added_by": "Karim"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(add2["session"]["item_count"], 3)

        # 6. Exceeding theoretical stock returns 400 cleanly
        status, fail_over = _http_json(
            f"{base}/api/order-sessions/{new_sid}/items",
            method="POST",
            body={"product_id": 101, "quantity": 10},
        )
        self.assertEqual(status, 400)
        self.assertFalse(fail_over["success"])


if __name__ == "__main__":
    unittest.main()
