# -*- coding: utf-8 -*-
"""
Minimal, clean dialogs for viewing, editing, and exporting Order Desk Bons
(Today's Bons + all unclosed Bon de Livraison vouchers).
"""

import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QCompleter,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.formatting import format_money
from ui.icons import get_duotone_icon
from .bon_pdf_export import export_order_bon_to_pdf

logger = logging.getLogger("StockLam.UI.OrderBonsDialog")


BOND_TYPE_LABELS = {
    "BON_C": "Bon Comptant",
    "BON_CREDIT": "Bon Crédit",
    "BON_LIVRAISON": "Bon de Livraison",
}

STATUS_LABELS = {
    "CONFIRMED_PENDING_PAYMENT": "Attente Caisse",
    "PAID_PENDING_DISPATCH": "Payé • Attente Sortie",
    "APPROVED_CREDIT_PENDING_DISPATCH": "Crédit • Attente Sortie",
    "APPROVED_LIVRAISON_PENDING_DISPATCH": "BL • Attente Sortie",
    "PARTIALLY_DISPATCHED": "Sortie Partielle",
    "DISPATCHED_PENDING_COD": "BL En Livraison (COD)",
    "COMPLETED": "Clôturé",
    "CANCELLED": "Annulé",
}


class OrderBonEditDialog(QDialog):
    """Sleek, container-free modal dialog for editing an Order Desk Bon."""

    def __init__(
        self,
        data_manager: Any,
        order_data: Dict[str, Any],
        catalog_items: Optional[List[Dict[str, Any]]] = None,
        clients_list: Optional[List[Dict[str, Any]]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.data_manager = data_manager
        self.order_data = dict(order_data)
        self.catalog_items = list(catalog_items or [])
        self.clients_list = list(clients_list or [])
        self.updated_result: Optional[Dict[str, Any]] = None
        self._edit_lines: List[Dict[str, Any]] = []

        self.setWindowTitle(f"Modifier {self.order_data.get('Order_Number', 'Bon')}")
        self.resize(740, 480)
        self._load_initial_data()
        self._init_ui()
        self._refresh_table()

    def _load_initial_data(self) -> None:
        if not self.clients_list and self.data_manager and hasattr(self.data_manager, "clients"):
            try:
                self.clients_list = self.data_manager.clients.get_all_clients() or []
            except Exception:
                self.clients_list = []

        if not self.catalog_items and self.data_manager and hasattr(self.data_manager, "serials"):
            try:
                self.catalog_items = self.data_manager.serials.get_catalog_with_theoretical_stock(only_available=True) or []
            except Exception:
                self.catalog_items = []

        raw_lines = self.order_data.get("lines") or []
        if not raw_lines and self.data_manager and hasattr(self.data_manager, "bonds"):
            oid = self.order_data.get("Order_ID")
            if oid:
                raw_lines = self.data_manager.bonds.get_order_lines(int(oid)) or []

        for ln in raw_lines:
            self._edit_lines.append({
                "product_id": int(ln.get("Product_ID") or ln.get("product_id") or 0),
                "name": str(ln.get("Product_Name") or ln.get("name") or ""),
                "mark": str(ln.get("Brand_Mark") or ln.get("mark") or ""),
                "coloure": str(ln.get("Color_Finish") or ln.get("coloure") or "Standard"),
                "quantity": int(ln.get("Quantity_Ordered") or ln.get("quantity") or 1),
                "unit_price_ttc": float(ln.get("Unit_Price_TTC") or ln.get("unit_price_ttc") or 0.0),
            })

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            QDialog { background-color: #FFFFFF; color: #1E293B; }
            QLabel { border: none; background: transparent; color: #334155; font-size: 12px; }
            QLineEdit, QComboBox {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
                color: #1E293B;
            }
            QLineEdit:focus, QComboBox:focus { border: 1.5px solid #007572; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Row 1: Client + Type de Bon
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        top_row.addWidget(QLabel("Client :"))
        self.cbo_client = QComboBox()
        self.cbo_client.setEditable(True)
        self.cbo_client.setFixedHeight(34)
        curr_cid = int(self.order_data.get("Client_ID") or 1)
        sel_idx = 0
        for idx, c in enumerate(self.clients_list):
            cid = int(c.get("Client_ID") or 0)
            cname = str(c.get("Client_Name") or f"Client #{cid}")
            self.cbo_client.addItem(cname, cid)
            if cid == curr_cid:
                sel_idx = idx
        if self.cbo_client.count() == 0:
            self.cbo_client.addItem(str(self.order_data.get("Client_Name") or "Client Standard"), curr_cid)
        self.cbo_client.setCurrentIndex(sel_idx)
        completer = QCompleter(self.cbo_client.model(), self.cbo_client)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.cbo_client.setCompleter(completer)
        top_row.addWidget(self.cbo_client, 2)

        top_row.addWidget(QLabel("Type :"))
        self.cbo_type = QComboBox()
        self.cbo_type.setFixedHeight(34)
        for code, label in BOND_TYPE_LABELS.items():
            self.cbo_type.addItem(label, code)
        curr_type = str(self.order_data.get("Bond_Type") or "BON_C").upper()
        t_idx = self.cbo_type.findData(curr_type)
        if t_idx >= 0:
            self.cbo_type.setCurrentIndex(t_idx)
        # Lock type change if an invoice already exists
        if self.order_data.get("Invoice_ID"):
            self.cbo_type.setEnabled(False)
        self.cbo_type.currentIndexChanged.connect(self._on_type_changed)
        top_row.addWidget(self.cbo_type, 1)
        layout.addLayout(top_row)

        # Row 2: Delivery Address (visible when BON_LIVRAISON or non-empty)
        self.txt_addr = QLineEdit(str(self.order_data.get("Delivery_Address") or ""))
        self.txt_addr.setFixedHeight(34)
        self.txt_addr.setPlaceholderText("Adresse de livraison & téléphone...")
        layout.addWidget(self.txt_addr)
        self._on_type_changed()

        # Row 3: Quick Add Product Bar
        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self.cbo_add_prod = QComboBox()
        self.cbo_add_prod.setEditable(True)
        self.cbo_add_prod.setFixedHeight(34)
        for p in self.catalog_items:
            pid = int(p.get("Product_ID") or 0)
            p_title = f"{p.get('Brand_Mark', '')} {p.get('Product_Name', '')}".strip()
            p_price = float(p.get("Unit_Price_TTC") or p.get("Price_1_TTC") or 0.0)
            self.cbo_add_prod.addItem(f"{p_title} — {format_money(p_price)} DA", p)
        if self.cbo_add_prod.lineEdit():
            self.cbo_add_prod.lineEdit().setPlaceholderText("Ajouter un article du stock...")
        add_row.addWidget(self.cbo_add_prod, 1)

        btn_add = QPushButton("+ Ajouter")
        btn_add.setFixedHeight(34)
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF; color: #007572; border: 1px solid #007572;
                border-radius: 4px; font-weight: 700; padding: 0 12px;
            }
            QPushButton:hover { background-color: #E6F4F1; }
        """)
        btn_add.clicked.connect(self._add_selected_product)
        add_row.addWidget(btn_add)
        layout.addLayout(add_row)

        # Row 4: Lines Table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Désignation", "Couleur", "Qté", "Prix Unit.", "Suppr."])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget { border: 1px solid #DDE3EA; border-radius: 4px; gridline-color: #E2E8F0; }
            QHeaderView::section {
                background-color: #F8FAFC; color: #1E293B; font-weight: 700;
                padding: 6px; border: none; border-bottom: 2px solid #007572;
            }
        """)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 85)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(4, 60)
        layout.addWidget(self.table, 1)

        # Row 5: Total + Save / Cancel
        footer = QHBoxLayout()
        self.lbl_total = QLabel("Total TTC : 0.00 DA")
        self.lbl_total.setStyleSheet("font-size: 14px; font-weight: 800; color: #007572;")
        footer.addWidget(self.lbl_total)
        footer.addStretch()

        btn_cancel = QPushButton("Annuler")
        btn_cancel.setFixedHeight(38)
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF; color: #475569; border: 1px solid #CBD5E1;
                border-radius: 4px; font-weight: 600; padding: 0 14px;
            }
            QPushButton:hover { background-color: #F1F5F9; }
        """)
        btn_cancel.clicked.connect(self.reject)
        footer.addWidget(btn_cancel)

        self.btn_save = QPushButton("Enregistrer")
        self.btn_save.setFixedHeight(38)
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #007572; color: #FFFFFF; border: none;
                border-radius: 4px; font-weight: 700; padding: 0 18px;
            }
            QPushButton:hover { background-color: #005A57; }
        """)
        self.btn_save.clicked.connect(self._save_changes)
        footer.addWidget(self.btn_save)
        layout.addLayout(footer)

    def _on_type_changed(self) -> None:
        is_bl = self.cbo_type.currentData() == "BON_LIVRAISON"
        self.txt_addr.setVisible(is_bl or bool(self.txt_addr.text().strip()))

    def _add_selected_product(self) -> None:
        prod = self.cbo_add_prod.currentData()
        if not isinstance(prod, dict):
            return
        pid = int(prod.get("Product_ID") or 0)
        if not pid:
            return
        for item in self._edit_lines:
            if item["product_id"] == pid:
                item["quantity"] += 1
                self._refresh_table()
                return
        self._edit_lines.append({
            "product_id": pid,
            "name": str(prod.get("Product_Name") or ""),
            "mark": str(prod.get("Brand_Mark") or ""),
            "coloure": str(prod.get("Color_Finish") or "Standard"),
            "quantity": 1,
            "unit_price_ttc": float(prod.get("Unit_Price_TTC") or prod.get("Price_1_TTC") or 0.0),
        })
        self._refresh_table()

    def _refresh_table(self) -> None:
        self.table.setRowCount(0)
        tot = 0.0
        for idx, item in enumerate(self._edit_lines):
            self.table.insertRow(idx)
            title = f"{item.get('mark', '')} {item.get('name', '')}".strip()
            self.table.setItem(idx, 0, QTableWidgetItem(title))
            self.table.setItem(idx, 1, QTableWidgetItem(str(item.get("coloure") or "-")))

            spn = QSpinBox()
            spn.setRange(1, 999)
            spn.setValue(int(item["quantity"]))
            spn.setAlignment(Qt.AlignCenter)
            spn.valueChanged.connect(lambda val, i=idx: self._on_qty_changed(i, val))
            self.table.setCellWidget(idx, 2, spn)

            u_price = float(item["unit_price_ttc"])
            tot += u_price * int(item["quantity"])
            it_p = QTableWidgetItem(f"{format_money(u_price)} DA")
            it_p.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(idx, 3, it_p)

            btn_del = QPushButton("×")
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.setStyleSheet("""
                QPushButton {
                    background: transparent; color: #DC2626; font-size: 16px;
                    font-weight: 800; border: none; padding: 0;
                }
                QPushButton:hover { background-color: #FEE2E2; border-radius: 4px; }
            """)
            btn_del.clicked.connect(lambda _=False, i=idx: self._remove_line(i))
            self.table.setCellWidget(idx, 4, btn_del)

        self.lbl_total.setText(f"Total TTC : {format_money(tot)} DA")

    def _on_qty_changed(self, idx: int, val: int) -> None:
        if 0 <= idx < len(self._edit_lines):
            self._edit_lines[idx]["quantity"] = int(val)
            tot = sum(float(x["unit_price_ttc"]) * int(x["quantity"]) for x in self._edit_lines)
            self.lbl_total.setText(f"Total TTC : {format_money(tot)} DA")

    def _remove_line(self, idx: int) -> None:
        if 0 <= idx < len(self._edit_lines):
            del self._edit_lines[idx]
            self._refresh_table()

    def _save_changes(self) -> None:
        if not self._edit_lines:
            QMessageBox.warning(self, "Articles requis", "Veuillez conserver au moins un article dans le bon.")
            return
        try:
            oid = int(self.order_data["Order_ID"])
            cid = int(self.cbo_client.currentData() or self.order_data.get("Client_ID") or 1)
            b_type = str(self.cbo_type.currentData() or "BON_C")
            addr = self.txt_addr.text().strip() or None
            uid = int((getattr(self.data_manager, "current_user", None) or {}).get("User_ID") or 1)

            if self.data_manager and hasattr(self.data_manager, "bonds"):
                self.updated_result = self.data_manager.bonds.update_sales_order_draft(
                    order_id=oid,
                    client_id=cid,
                    bond_type=b_type,
                    items=self._edit_lines,
                    delivery_address=addr,
                    user_id=uid,
                )
            else:
                tot = sum(float(x["unit_price_ttc"]) * int(x["quantity"]) for x in self._edit_lines)
                self.updated_result = {
                    "success": True,
                    "order_id": oid,
                    "order_number": self.order_data.get("Order_Number"),
                    "bond_type": b_type,
                    "total_ttc": tot,
                }
            self.accept()
        except Exception as err:
            QMessageBox.critical(self, "Erreur Modification", str(err))


class OrderDeskBonsDialog(QDialog):
    """
    Minimalist, clutter-free dialog showing all Bons created today PLUS all unclosed
    Bon de Livraison (BL) vouchers, with instant Edit and PDF Export actions.
    """

    def __init__(
        self,
        data_manager: Any,
        catalog_items: Optional[List[Dict[str, Any]]] = None,
        clients_list: Optional[List[Dict[str, Any]]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.data_manager = data_manager
        self.catalog_items = catalog_items or []
        self.clients_list = clients_list or []
        self._bons: List[Dict[str, Any]] = []
        self.was_modified = False

        self.setWindowTitle("Bons du Jour & Livraisons en Cours")
        self.resize(880, 520)
        self._init_ui()
        self.refresh_bons()

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            QDialog { background-color: #FFFFFF; color: #1E293B; }
            QLabel { border: none; background: transparent; color: #1E293B; }
            QLineEdit, QComboBox {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 12px;
                color: #1E293B;
            }
            QLineEdit:focus, QComboBox:focus { border: 1.5px solid #007572; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Single clean top bar (search + filter + refresh)
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.txt_search = QLineEdit()
        self.txt_search.setFixedHeight(34)
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.setPlaceholderText("Rechercher par N° Bon ou Client...")
        self.txt_search.textChanged.connect(self._apply_filter)
        top_bar.addWidget(self.txt_search, 1)

        self.cbo_filter = QComboBox()
        self.cbo_filter.setFixedHeight(34)
        self.cbo_filter.addItem("Tous les Bons", "ALL")
        self.cbo_filter.addItem("BL Non Clôturés", "BL_OPEN")
        self.cbo_filter.addItem("Bon Comptant", "BON_C")
        self.cbo_filter.addItem("Bon Crédit", "BON_CREDIT")
        self.cbo_filter.addItem("Bon de Livraison", "BON_LIVRAISON")
        self.cbo_filter.currentIndexChanged.connect(self._apply_filter)
        top_bar.addWidget(self.cbo_filter)

        btn_refresh = QPushButton("Actualiser")
        btn_refresh.setIcon(get_duotone_icon("refresh", 14))
        btn_refresh.setIconSize(QSize(14, 14))
        btn_refresh.setFixedHeight(34)
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF; color: #475569; border: 1px solid #CBD5E1;
                border-radius: 4px; font-weight: 600; padding: 0 12px;
            }
            QPushButton:hover { background-color: #F8FAFC; }
        """)
        btn_refresh.clicked.connect(self.refresh_bons)
        top_bar.addWidget(btn_refresh)
        layout.addLayout(top_bar)

        # Clean single Table
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "N° Bon", "Type", "Client", "Date", "Total TTC", "Reste", "Statut"
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #DDE3EA; border-radius: 5px;
                gridline-color: #E2E8F0; selection-background-color: #E6F4F1; selection-color: #0F172A;
            }
            QHeaderView::section {
                background-color: #F8FAFC; color: #0F172A; font-weight: 700; font-size: 12px;
                padding: 7px; border: none; border-bottom: 2px solid #007572;
            }
        """)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.cellDoubleClicked.connect(lambda _r, _c: self._edit_selected())
        layout.addWidget(self.table, 1)

        # Clean Action Footer
        footer = QHBoxLayout()
        footer.setSpacing(8)

        self.lbl_count = QLabel("0 bon(s)")
        self.lbl_count.setStyleSheet("font-size: 12px; color: #64748B; font-weight: 600;")
        footer.addWidget(self.lbl_count)
        footer.addStretch()

        self.btn_edit = QPushButton("Modifier")
        self.btn_edit.setIcon(get_duotone_icon("edit", 14))
        self.btn_edit.setIconSize(QSize(14, 14))
        self.btn_edit.setFixedHeight(38)
        self.btn_edit.setCursor(Qt.PointingHandCursor)
        self.btn_edit.setEnabled(False)
        self.btn_edit.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF; color: #007572; border: 1.5px solid #007572;
                border-radius: 4px; font-weight: 700; padding: 0 16px;
            }
            QPushButton:hover:enabled { background-color: #E6F4F1; }
            QPushButton:disabled { color: #94A3B8; border-color: #CBD5E1; background-color: #F8FAFC; }
        """)
        self.btn_edit.clicked.connect(self._edit_selected)
        footer.addWidget(self.btn_edit)

        self.btn_pdf = QPushButton("Exporter PDF")
        self.btn_pdf.setIcon(get_duotone_icon("statement", 14))
        self.btn_pdf.setIconSize(QSize(14, 14))
        self.btn_pdf.setFixedHeight(38)
        self.btn_pdf.setCursor(Qt.PointingHandCursor)
        self.btn_pdf.setEnabled(False)
        self.btn_pdf.setStyleSheet("""
            QPushButton {
                background-color: #007572; color: #FFFFFF; border: none;
                border-radius: 4px; font-weight: 700; padding: 0 18px;
            }
            QPushButton:hover:enabled { background-color: #005A57; }
            QPushButton:disabled { background-color: #CBD5E1; color: #FFFFFF; }
        """)
        self.btn_pdf.clicked.connect(self._export_selected_pdf)
        footer.addWidget(self.btn_pdf)

        btn_close = QPushButton("Fermer")
        btn_close.setFixedHeight(38)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF; color: #475569; border: 1px solid #CBD5E1;
                border-radius: 4px; font-weight: 600; padding: 0 14px;
            }
            QPushButton:hover { background-color: #F1F5F9; }
        """)
        btn_close.clicked.connect(self.accept)
        footer.addWidget(btn_close)
        layout.addLayout(footer)

    def refresh_bons(self) -> None:
        bons: List[Dict[str, Any]] = []
        if self.data_manager and hasattr(self.data_manager, "bonds"):
            try:
                res = self.data_manager.bonds.get_order_desk_bons()
                if isinstance(res, list):
                    bons = res
            except Exception as err:
                logger.error(f"Error loading Order Desk bons: {err}")
        self._bons = bons
        self._apply_filter()

    def _apply_filter(self) -> None:
        q = (self.txt_search.text() or "").strip().lower()
        mode = self.cbo_filter.currentData() or "ALL"

        filtered = []
        for b in self._bons:
            b_type = str(b.get("Bond_Type") or "").upper()
            st = str(b.get("Status") or "").upper()
            if mode == "BL_OPEN" and not (b_type == "BON_LIVRAISON" and st not in ("COMPLETED", "CANCELLED")):
                continue
            elif mode in ("BON_C", "BON_CREDIT", "BON_LIVRAISON") and b_type != mode:
                continue

            if q:
                hay = f"{b.get('Order_Number', '')} {b.get('Client_Name', '')}".lower()
                if q not in hay:
                    continue
            filtered.append(b)

        self._filtered_bons = filtered
        self.table.setRowCount(0)
        for row, b in enumerate(filtered):
            self.table.insertRow(row)
            it_num = QTableWidgetItem(str(b.get("Order_Number") or ""))
            it_num.setFont(QFont("Segoe UI", 9, QFont.Bold))
            it_num.setData(Qt.UserRole, b)
            self.table.setItem(row, 0, it_num)

            b_type = str(b.get("Bond_Type") or "BON_C").upper()
            it_type = QTableWidgetItem(BOND_TYPE_LABELS.get(b_type, b_type))
            it_type.setTextAlignment(Qt.AlignCenter)
            if b_type == "BON_LIVRAISON":
                it_type.setForeground(QColor("#B45309"))
            elif b_type == "BON_CREDIT":
                it_type.setForeground(QColor("#1D4ED8"))
            else:
                it_type.setForeground(QColor("#007572"))
            it_type.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table.setItem(row, 1, it_type)

            self.table.setItem(row, 2, QTableWidgetItem(str(b.get("Client_Name") or "Client Comptoir")))
            self.table.setItem(row, 3, QTableWidgetItem(str(b.get("Order_Date") or "")[:16]))

            tot = float(b.get("Total_Amount_TTC") or 0.0)
            it_tot = QTableWidgetItem(f"{format_money(tot)} DA")
            it_tot.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_tot.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table.setItem(row, 4, it_tot)

            rem = float(b.get("Amount_Remaining_Credit") if b.get("Amount_Remaining_Credit") is not None else tot)
            if str(b.get("Status") or "") in ("COMPLETED", "PAID_PENDING_DISPATCH"):
                rem = 0.0
            it_rem = QTableWidgetItem(f"{format_money(rem)} DA")
            it_rem.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_rem.setForeground(QColor("#DC2626" if rem > 0.01 else "#16A34A"))
            self.table.setItem(row, 5, it_rem)

            raw_st = str(b.get("Status") or "")
            it_st = QTableWidgetItem(STATUS_LABELS.get(raw_st, raw_st))
            it_st.setTextAlignment(Qt.AlignCenter)
            it_st.setForeground(QColor("#D97706" if raw_st != "COMPLETED" else "#16A34A"))
            it_st.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table.setItem(row, 6, it_st)

        self.lbl_count.setText(f"{len(filtered)} bon(s)")
        self._on_selection_changed()

    def _selected_bon(self) -> Optional[Dict[str, Any]]:
        row = self.table.currentRow()
        if row < 0:
            return None
        it = self.table.item(row, 0)
        return it.data(Qt.UserRole) if it else None

    def _is_editable(self, bon: Optional[Dict[str, Any]]) -> bool:
        if not bon:
            return False
        st = str(bon.get("Status") or "")
        b_type = str(bon.get("Bond_Type") or "")
        lines = bon.get("lines") or []
        if any(int(l.get("Quantity_Dispatched") or 0) > 0 for l in lines):
            return False
        if st == "CONFIRMED_PENDING_PAYMENT":
            return True
        if b_type == "BON_LIVRAISON" and st == "APPROVED_LIVRAISON_PENDING_DISPATCH":
            return True
        return False

    def _on_selection_changed(self) -> None:
        bon = self._selected_bon()
        self.btn_pdf.setEnabled(bon is not None)
        self.btn_edit.setEnabled(self._is_editable(bon))

    def _edit_selected(self) -> None:
        bon = self._selected_bon()
        if not bon:
            return
        if not self._is_editable(bon):
            QMessageBox.information(
                self,
                "Modification non disponible",
                "Ce bon a déjà été expédié ou clôturé. Vous pouvez toujours l'exporter en PDF.",
            )
            return
        dlg = OrderBonEditDialog(
            data_manager=self.data_manager,
            order_data=bon,
            catalog_items=self.catalog_items,
            clients_list=self.clients_list,
            parent=self,
        )
        if dlg.exec() == QDialog.Accepted and dlg.updated_result:
            self.was_modified = True
            self.refresh_bons()

    def _export_selected_pdf(self) -> None:
        bon = self._selected_bon()
        if not bon:
            return
        export_order_bon_to_pdf(self.data_manager, bon, parent_widget=self)
