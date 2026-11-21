# -*- coding: utf-8 -*-
"""
ui/widgets/appliance_desks/order_client_dialog.py
=================================================
Popup dialog for selecting, searching, or editing customer & delivery details
at the moment an Order Desk action (Bon C, Bon Crédit, Bon de Livraison, Versement)
is executed. Pre-populates client data sent from the mobile companion app if present.
"""

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ui.icons import get_duotone_icon
from .quick_client_dialog import QuickClientDialog


class OrderClientDialog(QDialog):
    """Modal dialog shown upon executing any Order Desk action to confirm/edit/select client details."""

    def __init__(
        self,
        data_manager=None,
        clients_cache: Optional[List[Dict[str, Any]]] = None,
        session_data: Optional[Dict[str, Any]] = None,
        bond_type: str = "BON_C",
        parent=None,
    ):
        super().__init__(parent)
        self.data_manager = data_manager
        self.clients_cache: List[Dict[str, Any]] = list(clients_cache or [])
        self.session_data: Dict[str, Any] = dict(session_data or {})
        self.bond_type = str(bond_type or "BON_C")
        self.selected_client_info: Optional[Dict[str, Any]] = None
        self.clients_cache_updated: bool = False

        self._incoming_cid = self.session_data.get("client_id")
        self._incoming_name = str(self.session_data.get("client_name") or "").strip()
        self._incoming_phone = str(self.session_data.get("client_phone") or "").strip()
        self._incoming_addr = str(self.session_data.get("delivery_address") or "").strip()
        self._has_incoming_data = bool(
            (self._incoming_name or self._incoming_phone or self._incoming_addr)
            and not self.session_data.get("edit_order")
        )

        self.setWindowTitle("Identification du Client")
        self.setFixedWidth(500)
        self.setModal(True)
        self._ensure_clients_cache()
        self._init_ui()
        self._populate_initial_state()

    def _ensure_clients_cache(self) -> None:
        if self.clients_cache:
            return
        loaded: List[Dict[str, Any]] = []
        if self.data_manager and hasattr(self.data_manager, "clients"):
            try:
                for c in self.data_manager.clients.get_all_clients() or []:
                    cid = c.get("Client_ID")
                    if cid is None:
                        continue
                    cname = str(c.get("Client_Name") or c.get("Full_Name") or f"Client #{cid}").strip()
                    loaded.append({
                        "Client_ID": int(cid),
                        "Client_Name": cname,
                        "Phone": str(c.get("Phone") or "").strip(),
                        "Address": str(c.get("Address") or "").strip(),
                        "Price_Tier": str(c.get("Price_Tier") or "Prix_1").strip(),
                    })
            except Exception:
                loaded = []
        if not loaded:
            loaded = [
                {
                    "Client_ID": 1,
                    "Client_Name": "Client Comptoir (Standard)",
                    "Phone": "",
                    "Address": "",
                    "Price_Tier": "Prix_1",
                }
            ]
        self.clients_cache = loaded

    def _init_ui(self) -> None:
        self.setObjectName("OrderClientDialog")
        self.setStyleSheet("""
            QDialog#OrderClientDialog {
                background-color: #FFFFFF;
            }
            QDialog#OrderClientDialog QLabel {
                font-size: 12px;
                font-weight: 600;
                color: #2C3E50;
                border: none;
                background: transparent;
            }
            QDialog#OrderClientDialog QLineEdit,
            QDialog#OrderClientDialog QComboBox {
                background-color: #FFFFFF;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 12px;
                color: #2C3E50;
                min-height: 30px;
            }
            QLineEdit:hover, QComboBox:hover {
                border-color: #ADB5BD;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1.5px solid #007572;
                background-color: #FFFFFF;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #CED4DA;
                border-radius: 4px;
                background-color: #FFFFFF;
                selection-background-color: #E6F4F1;
                selection-color: #007572;
                padding: 4px;
            }
            QPushButton#ConfirmBtn {
                background-color: #007572;
                color: #FFFFFF;
                font-weight: 700;
                font-size: 12px;
                border: none;
                border-radius: 4px;
                padding: 6px 18px;
                min-height: 34px;
            }
            QPushButton#ConfirmBtn:hover {
                background-color: #005A57;
            }
            QPushButton#ConfirmBtn:pressed {
                background-color: #003D3A;
            }
            QPushButton#OutlineBtn {
                background-color: #FFFFFF;
                color: #007572;
                font-weight: 700;
                font-size: 12px;
                border: 1px solid #007572;
                border-radius: 4px;
                padding: 4px 12px;
                min-height: 30px;
            }
            QPushButton#OutlineBtn:hover {
                background-color: #E8F8F5;
            }
            QPushButton#CancelBtn {
                background-color: #FFFFFF;
                color: #495057;
                font-weight: 600;
                font-size: 12px;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                padding: 6px 16px;
                min-height: 34px;
            }
            QPushButton#CancelBtn:hover {
                background-color: #F8FAFC;
                border-color: #ADB5BD;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # Header
        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_duotone_icon("users", 20).pixmap(20, 20))
        header_row.addWidget(icon_lbl)

        title_lbl = QLabel("Client & Livraison")
        title_lbl.setStyleSheet("font-size: 14px; font-weight: 800; color: #007572;")
        header_row.addWidget(title_lbl)

        mode_labels = {
            "BON_C": "Paiement complet",
            "BON_CREDIT": "Paiement à crédit",
            "BON_LIVRAISON": "Paiement à la livraison",
            "BON_VERSEMENT": "Versement",
        }
        mode_lbl = QLabel(mode_labels.get(self.bond_type, "Commande"))
        mode_lbl.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: #0E7471; background-color: #E6F4F1; "
            "border: 1px solid #99F6E4; border-radius: 10px; padding: 2px 9px;"
        )
        header_row.addWidget(mode_lbl)
        header_row.addStretch()

        self.btn_quick_client = QPushButton("+ Nouveau Client")
        self.btn_quick_client.setObjectName("OutlineBtn")
        self.btn_quick_client.setCursor(Qt.PointingHandCursor)
        self.btn_quick_client.clicked.connect(self._open_quick_client_dialog)
        header_row.addWidget(self.btn_quick_client)
        layout.addLayout(header_row)

        # Incoming Mobile Data Banner
        self.mobile_banner = QFrame()
        self.mobile_banner.setObjectName("MobileClientBanner")
        self.mobile_banner.setStyleSheet("""
            QFrame#MobileClientBanner {
                background-color: #E8F8F5;
                border: 1px solid #A3E4D7;
                border-left: 3px solid #007572;
                border-radius: 4px;
            }
            QLabel {
                color: #005A57;
                font-size: 11px;
                font-weight: 600;
                border: none;
                background: transparent;
            }
        """)
        b_lay = QHBoxLayout(self.mobile_banner)
        b_lay.setContentsMargins(10, 6, 10, 6)
        b_lbl = QLabel("Données client reçues depuis l'application — vérifiez, modifiez ou changez de client.")
        b_lbl.setWordWrap(True)
        b_lay.addWidget(b_lbl)
        self.mobile_banner.setVisible(self._has_incoming_data)
        layout.addWidget(self.mobile_banner)

        # Versement Info Note (amount is entered strictly at Caisse)
        self.versement_banner = QFrame()
        self.versement_banner.setObjectName("VersementInfoBanner")
        self.versement_banner.setStyleSheet("""
            QFrame#VersementInfoBanner {
                background-color: #FEF3C7;
                border: 1px solid #FDE68A;
                border-left: 3px solid #D97706;
                border-radius: 4px;
            }
            QLabel {
                color: #92400E;
                font-size: 11px;
                font-weight: 600;
                border: none;
                background: transparent;
            }
        """)
        v_lay = QHBoxLayout(self.versement_banner)
        v_lay.setContentsMargins(10, 6, 10, 6)
        v_lbl = QLabel("Versement : sélectionnez le client — la saisie du montant s'effectue uniquement en Caisse.")
        v_lbl.setWordWrap(True)
        v_lay.addWidget(v_lbl)
        self.versement_banner.setVisible(self.bond_type == "BON_VERSEMENT")
        layout.addWidget(self.versement_banner)

        # Search & Select Existing Client
        search_grid = QGridLayout()
        search_grid.setVerticalSpacing(8)
        search_grid.setHorizontalSpacing(10)

        search_grid.addWidget(QLabel("Rechercher client :"), 0, 0)
        self.txt_client_search = QLineEdit()
        self.txt_client_search.setClearButtonEnabled(True)
        self.txt_client_search.setPlaceholderText("Nom ou n° téléphone...")
        self.txt_client_search.textChanged.connect(self._on_search_changed)
        search_grid.addWidget(self.txt_client_search, 0, 1)

        search_grid.addWidget(QLabel("Client enregistré :"), 1, 0)
        self.cbo_client = QComboBox()
        self.cbo_client.currentIndexChanged.connect(self._on_combo_client_changed)
        search_grid.addWidget(self.cbo_client, 1, 1)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("background-color: #E2E8F0; max-height: 1px;")
        search_grid.addWidget(div, 2, 0, 1, 2)

        # Editable Customer Fields
        search_grid.addWidget(QLabel("Nom complet :"), 3, 0)
        self.txt_client_name = QLineEdit()
        self.txt_client_name.setPlaceholderText("Nom du client (optionnel pour Comptoir)...")
        search_grid.addWidget(self.txt_client_name, 3, 1)

        search_grid.addWidget(QLabel("Téléphone :"), 4, 0)
        self.txt_client_phone = QLineEdit()
        self.txt_client_phone.setPlaceholderText("N° de téléphone...")
        search_grid.addWidget(self.txt_client_phone, 4, 1)

        search_grid.addWidget(QLabel("Lieu / Livraison :"), 5, 0)
        self.txt_delivery_addr = QLineEdit()
        self.txt_delivery_addr.setPlaceholderText("Adresse de livraison ou lieu de retrait préféré...")
        search_grid.addWidget(self.txt_delivery_addr, 5, 1)

        layout.addLayout(search_grid)

        # Action Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.setObjectName("CancelBtn")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_confirm = QPushButton("Confirmer")
        self.btn_confirm.setObjectName("ConfirmBtn")
        self.btn_confirm.setDefault(True)
        self.btn_confirm.setCursor(Qt.PointingHandCursor)
        self.btn_confirm.clicked.connect(self._on_confirm)
        btn_row.addWidget(self.btn_confirm)

        layout.addLayout(btn_row)

    def _reload_client_combo(self, search_filter: str = "", selected_id: Optional[int] = None) -> None:
        q = search_filter.strip().lower()
        self.cbo_client.blockSignals(True)
        self.cbo_client.clear()

        if self._has_incoming_data or (self._incoming_cid is None and not q):
            manual_label = (
                f"Client de l'application ({self._incoming_name})"
                if self._incoming_name
                else "Saisie libre / Client ponctuel"
            )
            self.cbo_client.addItem(manual_label, None)

        matched_count = 0
        for c in self.clients_cache:
            cname = str(c.get("Client_Name") or "").strip()
            cphone = str(c.get("Phone") or "").strip()
            if q and q not in cname.lower() and q not in cphone.lower():
                continue
            disp = cname if not cphone else f"{cname}  —  Tél: {cphone}"
            self.cbo_client.addItem(disp, int(c["Client_ID"]))
            matched_count += 1

        if self.cbo_client.count() == 0:
            self.cbo_client.addItem("Aucun client correspondant — Saisie libre", None)

        target_idx = 0
        if selected_id is not None:
            idx = self.cbo_client.findData(int(selected_id))
            if idx >= 0:
                target_idx = idx
        elif q and matched_count > 0:
            # Select first matching DB client when actively searching
            for i in range(self.cbo_client.count()):
                if self.cbo_client.itemData(i) is not None:
                    target_idx = i
                    break

        self.cbo_client.setCurrentIndex(target_idx)
        self.cbo_client.blockSignals(False)

    def _find_client_record(self, client_id: Optional[int]) -> Optional[Dict[str, Any]]:
        if client_id is None:
            return None
        for c in self.clients_cache:
            if int(c.get("Client_ID") or 0) == int(client_id):
                return c
        return None

    def _populate_initial_state(self) -> None:
        target_cid: Optional[int] = None
        if self._incoming_cid is not None:
            target_cid = int(self._incoming_cid)
        elif self._incoming_name:
            low = self._incoming_name.lower()
            for c in self.clients_cache:
                if str(c.get("Client_Name") or "").strip().lower() == low:
                    target_cid = int(c["Client_ID"])
                    break
        elif not self._has_incoming_data and self.clients_cache:
            target_cid = int(self.clients_cache[0]["Client_ID"])

        self._reload_client_combo(selected_id=target_cid)

        rec = self._find_client_record(target_cid)
        if self._has_incoming_data:
            self.txt_client_name.setText(self._incoming_name or (rec["Client_Name"] if rec else ""))
            self.txt_client_phone.setText(self._incoming_phone or (rec["Phone"] if rec else ""))
            self.txt_delivery_addr.setText(self._incoming_addr or (rec["Address"] if rec else ""))
        elif rec:
            self.txt_client_name.setText(self._incoming_name or rec["Client_Name"])
            self.txt_client_phone.setText(self._incoming_phone or rec["Phone"])
            self.txt_delivery_addr.setText(self._incoming_addr or rec["Address"])
        else:
            self.txt_client_name.setText(self._incoming_name)
            self.txt_client_phone.setText(self._incoming_phone)
            self.txt_delivery_addr.setText(self._incoming_addr)

    def _on_search_changed(self, text: str) -> None:
        prev_cid = self.cbo_client.currentData()
        self._reload_client_combo(search_filter=text, selected_id=prev_cid if not text.strip() else None)
        if text.strip():
            curr = self.cbo_client.currentData()
            rec = self._find_client_record(curr)
            if rec:
                self.txt_client_name.setText(rec["Client_Name"])
                self.txt_client_phone.setText(rec["Phone"])
                if rec.get("Address") or not self._incoming_addr:
                    self.txt_delivery_addr.setText(rec.get("Address", ""))

    def _on_combo_client_changed(self, idx: int) -> None:
        if idx < 0:
            return
        cid = self.cbo_client.currentData()
        if cid is None:
            self.txt_client_name.setText(self._incoming_name)
            self.txt_client_phone.setText(self._incoming_phone)
            self.txt_delivery_addr.setText(self._incoming_addr)
            return
        rec = self._find_client_record(int(cid))
        if rec:
            self.txt_client_name.setText(rec["Client_Name"])
            self.txt_client_phone.setText(rec["Phone"])
            self.txt_delivery_addr.setText(rec["Address"] or self._incoming_addr)

    def _open_quick_client_dialog(self) -> None:
        dlg = QuickClientDialog(data_manager=self.data_manager, parent=self)
        if dlg.exec() == QDialog.Accepted and dlg.created_client:
            new_c = dict(dlg.created_client)
            if not isinstance(new_c.get("Client_ID"), int) or new_c["Client_ID"] <= 0:
                new_c["Client_ID"] = max([int(c.get("Client_ID") or 0) for c in self.clients_cache], default=1) + 1
            self.clients_cache.append(new_c)
            self.clients_cache_updated = True
            self.txt_client_search.blockSignals(True)
            self.txt_client_search.clear()
            self.txt_client_search.blockSignals(False)
            self._reload_client_combo(selected_id=int(new_c["Client_ID"]))
            self.txt_client_name.setText(str(new_c.get("Client_Name") or ""))
            self.txt_client_phone.setText(str(new_c.get("Phone") or ""))
            self.txt_delivery_addr.setText(str(new_c.get("Address") or ""))

    def _on_confirm(self) -> None:
        name = self.txt_client_name.text().strip()
        phone = self.txt_client_phone.text().strip()
        addr = self.txt_delivery_addr.text().strip()
        selected_cid = self.cbo_client.currentData()
        selected_rec = self._find_client_record(selected_cid)

        final_cid: int = 1
        final_name: str = name or "Client Comptoir"

        if selected_rec is not None and (
            not name or name.lower() == selected_rec["Client_Name"].strip().lower()
        ):
            final_cid = int(selected_rec["Client_ID"])
            final_name = selected_rec["Client_Name"]
        elif name:
            # Reuse existing client if exact name match exists
            matched = next(
                (c for c in self.clients_cache if str(c.get("Client_Name") or "").strip().lower() == name.lower()),
                None,
            )
            if matched is not None:
                final_cid = int(matched["Client_ID"])
                final_name = matched["Client_Name"]
            else:
                new_id = None
                if self.data_manager and hasattr(self.data_manager, "clients") and hasattr(self.data_manager.clients, "add_client"):
                    try:
                        candidate = self.data_manager.clients.add_client(
                            name=name,
                            phone=phone or None,
                            address=addr or None,
                        )
                        if isinstance(candidate, int) and candidate > 0:
                            new_id = candidate
                    except Exception:
                        new_id = None
                if new_id is not None:
                    final_cid = int(new_id)
                    self.clients_cache.append({
                        "Client_ID": final_cid,
                        "Client_Name": name,
                        "Phone": phone,
                        "Address": addr,
                        "Price_Tier": "Prix_1",
                    })
                    self.clients_cache_updated = True
                elif selected_cid is not None:
                    final_cid = int(selected_cid)
                else:
                    final_cid = 1
                final_name = name
        elif selected_cid is not None:
            final_cid = int(selected_cid)
            final_name = selected_rec["Client_Name"] if selected_rec else "Client Comptoir"

        self.selected_client_info = {
            "client_id": final_cid,
            "client_name": final_name,
            "client_phone": phone,
            "delivery_address": addr,
        }
        self.accept()
