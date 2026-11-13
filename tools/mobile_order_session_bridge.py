"""Thread-safe bridge from the mobile HTTP API to OrderDeskWidget sessions."""

import logging
from threading import Lock
from typing import Any, Dict, Optional

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot


class MobileOrderSessionBridge(QObject):
    """Marshals mobile Order Desk session calls onto the Qt GUI thread."""

    _invoke_signal = Signal(str, object)

    def __init__(self, window=None):
        super().__init__()
        self.window = window
        self._lock = Lock()
        self._result: Dict[str, Any] = {}
        self._invoke_signal.connect(
            self._execute_on_gui,
            Qt.ConnectionType.BlockingQueuedConnection,
        )

    def set_window(self, window) -> None:
        self.window = window

    def _find_order_desk(self):
        if self.window is None:
            return None
        if hasattr(self.window, "get_mobile_sessions_snapshot"):
            return self.window
        for child in self.window.findChildren(QObject):
            if hasattr(child, "get_mobile_sessions_snapshot"):
                return child
        return None

    def _call(self, action: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._lock:
            if QThread.currentThread() == self.thread():
                return self._execute_impl(action, payload or {})
            self._result = {"success": False, "message": "Erreur de communication UI."}
            try:
                self._invoke_signal.emit(action, payload or {})
            except RuntimeError:
                logging.exception("MobileOrderSessionBridge could not reach Qt GUI thread.")
                return {"success": False, "message": "Interface bureau indisponible."}
            return dict(self._result)

    @Slot(str, object)
    def _execute_on_gui(self, action: str, payload: object) -> None:
        self._result = self._execute_impl(action, payload if isinstance(payload, dict) else {})

    def _execute_impl(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        desk = self._find_order_desk()
        if desk is None:
            return {
                "success": False,
                "message": "Veuillez ouvrir l'onglet Bureaux -> Commandes sur le PC serveur.",
            }

        try:
            if action == "list_sessions":
                return {
                    "success": True,
                    "sessions": desk.get_mobile_sessions_snapshot(),
                }
            if action == "create_session":
                session = desk.create_mobile_session(
                    client_id=payload.get("client_id"),
                    label=payload.get("label"),
                    created_by=payload.get("created_by"),
                )
                return {
                    "success": True,
                    "message": f"Session « {session['label']} » créée.",
                    "session": session,
                }
            if action == "add_item":
                return desk.add_mobile_item_to_session(
                    session_id=str(payload.get("session_id") or ""),
                    product_id=payload.get("product_id"),
                    barcode=payload.get("barcode"),
                    quantity=payload.get("quantity", 1),
                    price_tier=payload.get("price_tier"),
                    added_by=payload.get("added_by"),
                )
            if action == "update_item_qty":
                return desk.update_mobile_item_quantity(
                    session_id=str(payload.get("session_id") or ""),
                    product_id=int(payload.get("product_id") or 0),
                    delta=int(payload.get("delta") or 0),
                    actor=payload.get("actor"),
                )
        except Exception as exc:
            logging.exception("Order session mobile bridge action '%s' failed.", action)
            return {"success": False, "message": str(exc)}

        return {"success": False, "message": f"Action inconnue : {action}"}

    def list_sessions(self) -> Dict[str, Any]:
        return self._call("list_sessions")

    def create_session(
        self,
        client_id: Optional[int] = None,
        label: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._call(
            "create_session",
            {"client_id": client_id, "label": label, "created_by": created_by},
        )

    def add_item(
        self,
        session_id: str,
        product_id: Optional[int] = None,
        barcode: Optional[str] = None,
        quantity: int = 1,
        price_tier: Optional[str] = None,
        added_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._call(
            "add_item",
            {
                "session_id": session_id,
                "product_id": product_id,
                "barcode": barcode,
                "quantity": quantity,
                "price_tier": price_tier,
                "added_by": added_by,
            },
        )

    def update_item_qty(
        self,
        session_id: str,
        product_id: int,
        delta: int,
        actor: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._call(
            "update_item_qty",
            {
                "session_id": session_id,
                "product_id": product_id,
                "delta": delta,
                "actor": actor,
            },
        )
