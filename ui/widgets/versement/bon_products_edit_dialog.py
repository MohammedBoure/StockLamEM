# -*- coding: utf-8 -*-
"""
Full Bon & Products Editor Dialog for the Versement workspace.
Allows users to manually search and add new products, adjust quantities and unit prices,
or remove products from any Bon de Versement, automatically recalculating totals,
theoretical stock reservations, and remaining balances.
"""

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.formatting import format_money
from ui.icons import get_duotone_icon
from .bon_payments_dialogs import _resolve_bonds_manager

logger = logging.getLogger("StockLam.UI.BonProductsEditDialog")


class BonProductsEditDialog(QDialog):
    """
    Large dialog enabling complete manual editing of products inside a Bon:
    - Left pane: manual catalog search to find & add products by name, Réf, barcode, brand, or color.
    - Right pane: current Bon lines with editable quantity, unit price TTC, and row removal.
    """

    def __init__(
        self,
        data_manager: Any,
        bon_data: Dict[str, Any],
        current_user: Optional[Dict[str, Any]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.data_manager = data_manager
        self._bonds_mgr = _resolve_bonds_manager(data_manager)
        self.bon_data = dict(bon_data or {})
        self.current_user = current_user or {}
        self.order_id = int(self.bon_data.get("Order_ID") or 0)
        self.has_changes = False

        self._order_full: Dict[str, Any] = {}
        self._catalog_items: List[Dict[str, Any]] = []
        self._filtered_catalog: List[Dict[str, Any]] = []
        self._bon_lines: List[Dict[str, Any]] = []
        self._already_paid = float(self.bon_data.get("Total_Paid") or 0.0)

        ord_num = str(self.bon_data.get("Order_Number") or f"#{self.order_id}")
        self.setWindowTitle(f"Modifier les Produits du Bon — {ord_num}")
        self.setModal(True)
        self.resize(1100, 660)
        self.setMinimumSize(880, 540)

        self._load_initial_data()
        self._init_ui()
        self._filter_catalog()
        self._rebuild_lines_table()

    def _load_initial_data(self) -> None:
        # 1. Load full order & lines
        if self._bonds_mgr and hasattr(self._bonds_mgr, "get_order_by_id") and self.order_id:
            try:
                fetched = self._bonds_mgr.get_order_by_id(self.order_id)
                if isinstance(fetched, dict):
                    self._order_full = fetched
            except Exception as err:
                logger.error(f"Error loading order #{self.order_id}: {err}")

        if not self._order_full:
            self._order_full = dict(self.bon_data)

        raw_lines = self._order_full.get("lines") or []
        if not raw_lines and self._bonds_mgr and hasattr(self._bonds_mgr, "get_order_lines") and self.order_id:
            try:
                raw_lines = self._bonds_mgr.get_order_lines(self.order_id) or []
            except Exception:
                raw_lines = []

        self._bon_lines = []
        for ln in raw_lines:
            self._bon_lines.append(
                {
                    "product_id": int(ln.get("Product_ID") or 0),
                    "name": str(ln.get("Product_Name") or f"Produit #{ln.get('Product_ID', '')}"),
                    "brand": str(ln.get("Brand_Mark") or ""),
                    "color": str(ln.get("Color_Finish") or ln.get("Requested_Color") or ""),
                    "barcode": str(ln.get("Barcode") or ""),
                    "quantity": max(1, int(ln.get("Quantity_Ordered") or 1)),
                    "unit_price_ttc": float(ln.get("Unit_Price_TTC") or 0.0),
                }
            )

        # 2. Load catalog products for manual search
        catalog: List[Dict[str, Any]] = []
        if self.data_manager is not None:
            if hasattr(self.data_manager, "serials") and hasattr(
                self.data_manager.serials, "get_catalog_with_theoretical_stock"
            ):
                try:
                    catalog = (
                        self.data_manager.serials.get_catalog_with_theoretical_stock(only_available=False) or []
                    )
                except Exception as err:
                    logger.warning(f"Catalog load via serials failed: {err}")
            if not catalog and hasattr(self.data_manager, "products") and hasattr(
                self.data_manager.products, "get_all_products"
            ):
                try:
                    catalog = self.data_manager.products.get_all_products() or []
                except Exception as err:
                    logger.warning(f"Catalog load via products failed: {err}")

        self._catalog_items = [dict(p) for p in catalog]

    def _init_ui(self) -> None:
        self.setObjectName("BonProductsEditDialog")
        self.setStyleSheet(
            """
            QDialog#BonProductsEditDialog { background-color: #F8FAFC; }
            QFrame#BonEditCard {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 10px;
            }
            QFrame#BonEditCard QLabel { border: none; background: transparent; }
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12.5px;
                color: #0F172A;
            }
            QLineEdit:focus { border: 1.5px solid #0E7471; }
            QTableWidget {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                gridline-color: #F1F5F9;
                font-size: 12px;
                color: #0F172A;
            }
            QHeaderView::section {
                background-color: #F8FAFC;
                color: #334155;
                font-weight: 700;
                font-size: 11.5px;
                border: none;
                border-bottom: 2px solid #0E7471;
                padding: 6px 8px;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        # Header Summary Card
        hdr = QFrame()
        hdr.setObjectName("BonEditCard")
        h_lay = QHBoxLayout(hdr)
        h_lay.setContentsMargins(14, 10, 14, 10)
        h_lay.setSpacing(16)

        ord_num = str(self._order_full.get("Order_Number") or self.bon_data.get("Order_Number") or f"#{self.order_id}")
        client_name = str(self._order_full.get("Client_Name") or self.bon_data.get("Client_Name") or "Client")

        lbl_info = QLabel(
            f"<b style='font-size:15px; color:#0F172A;'>Bon {ord_num}</b>  •  "
            f"<span style='color:#475569;'>Client : <b>{client_name}</b></span>"
        )
        h_lay.addWidget(lbl_info)
        h_lay.addStretch(1)

        self.lbl_paid_info = QLabel(f"Déjà payé : {format_money(self._already_paid)} DA")
        self.lbl_paid_info.setStyleSheet("font-size: 12.5px; font-weight: 700; color: #0E7471;")
        h_lay.addWidget(self.lbl_paid_info)

        self.lbl_new_total = QLabel("Nouveau Total : 0,00 DA")
        self.lbl_new_total.setStyleSheet(
            "font-size: 13.5px; font-weight: 800; color: #0F172A; "
            "background-color: #CCFBF1; border-radius: 6px; padding: 5px 12px;"
        )
        h_lay.addWidget(self.lbl_new_total)

        self.lbl_new_rem = QLabel("Reste : 0,00 DA")
        self.lbl_new_rem.setStyleSheet("font-size: 12.5px; font-weight: 700; color: #B45309;")
        h_lay.addWidget(self.lbl_new_rem)
        root.addWidget(hdr)

        # Split Pane: Left = Manual Product Catalog Search | Right = Bon Products Editor
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Left Pane: Catalog Search
        left_card = QFrame()
        left_card.setObjectName("BonEditCard")
        l_lay = QVBoxLayout(left_card)
        l_lay.setContentsMargins(12, 12, 12, 12)
        l_lay.setSpacing(8)

        lbl_cat = QLabel("1. Rechercher et ajouter un produit manuellement")
        lbl_cat.setStyleSheet("font-size: 13px; font-weight: 700; color: #0F172A;")
        l_lay.addWidget(lbl_cat)

        self.txt_cat_search = QLineEdit()
        self.txt_cat_search.setFixedHeight(36)
        self.txt_cat_search.setClearButtonEnabled(True)
        self.txt_cat_search.setPlaceholderText("Rechercher par nom, Réf, code-barres, marque ou couleur...")
        self.txt_cat_search.textChanged.connect(self._filter_catalog)
        l_lay.addWidget(self.txt_cat_search)

        self.cat_table = QTableWidget(0, 5)
        self.cat_table.setHorizontalHeaderLabels(["Produit", "Réf / Code", "Stock", "Prix TTC", ""])
        self.cat_table.verticalHeader().setVisible(False)
        self.cat_table.verticalHeader().setDefaultSectionSize(38)
        self.cat_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.cat_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.cat_table.setAlternatingRowColors(True)
        self.cat_table.doubleClicked.connect(self._on_catalog_double_click)
        ch = self.cat_table.horizontalHeader()
        ch.setSectionResizeMode(0, QHeaderView.Stretch)
        ch.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        ch.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        ch.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        ch.setSectionResizeMode(4, QHeaderView.Fixed)
        self.cat_table.setColumnWidth(4, 72)
        l_lay.addWidget(self.cat_table, 1)

        splitter.addWidget(left_card)

        # Right Pane: Current Bon Products
        right_card = QFrame()
        right_card.setObjectName("BonEditCard")
        r_lay = QVBoxLayout(right_card)
        r_lay.setContentsMargins(12, 12, 12, 12)
        r_lay.setSpacing(8)

        lbl_lines = QLabel("2. Produits actuels du Bon (quantités & prix modifiables)")
        lbl_lines.setStyleSheet("font-size: 13px; font-weight: 700; color: #0F172A;")
        r_lay.addWidget(lbl_lines)

        self.lines_table = QTableWidget(0, 5)
        self.lines_table.setHorizontalHeaderLabels(["Produit", "Qté", "Prix Unit. TTC", "Total TTC", "Suppr."])
        self.lines_table.verticalHeader().setVisible(False)
        self.lines_table.verticalHeader().setDefaultSectionSize(42)
        self.lines_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.lines_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.lines_table.setAlternatingRowColors(True)
        lh = self.lines_table.horizontalHeader()
        lh.setSectionResizeMode(0, QHeaderView.Stretch)
        lh.setSectionResizeMode(1, QHeaderView.Fixed)
        lh.setSectionResizeMode(2, QHeaderView.Fixed)
        lh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        lh.setSectionResizeMode(4, QHeaderView.Fixed)
        self.lines_table.setColumnWidth(1, 76)
        self.lines_table.setColumnWidth(2, 128)
        self.lines_table.setColumnWidth(4, 58)
        r_lay.addWidget(self.lines_table, 1)

        self.lbl_validation_err = QLabel("")
        self.lbl_validation_err.setWordWrap(True)
        self.lbl_validation_err.setStyleSheet("font-size: 12px; font-weight: 700; color: #DC2626;")
        self.lbl_validation_err.setVisible(False)
        r_lay.addWidget(self.lbl_validation_err)

        splitter.addWidget(right_card)
        splitter.setSizes([500, 560])
        root.addWidget(splitter, 1)

        # Footer Buttons
        footer = QHBoxLayout()
        footer.setSpacing(10)

        btn_cancel = QPushButton("Annuler")
        btn_cancel.setIcon(get_duotone_icon("close_slate", 15))
        btn_cancel.setIconSize(QSize(15, 15))
        btn_cancel.setFixedHeight(38)
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet(
            "QPushButton { background:#FFFFFF; border:1px solid #CBD5E1; border-radius:6px; "
            "color:#334155; font-weight:600; padding:0px 18px; }"
            "QPushButton:hover { background:#F8FAFC; }"
        )
        btn_cancel.clicked.connect(self.reject)
        footer.addWidget(btn_cancel)
        footer.addStretch(1)

        self.btn_save = QPushButton("Enregistrer les Modifications")
        self.btn_save.setIcon(get_duotone_icon("save_white", 16))
        self.btn_save.setIconSize(QSize(16, 16))
        self.btn_save.setFixedHeight(40)
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setStyleSheet(
            "QPushButton { background:#0E7471; border:none; border-radius:6px; "
            "color:#FFFFFF; font-size:13px; font-weight:700; padding:0px 22px; }"
            "QPushButton:hover { background:#0A5C59; }"
            "QPushButton:disabled { background:#CBD5E1; color:#64748B; }"
        )
        self.btn_save.clicked.connect(self._save_changes)
        footer.addWidget(self.btn_save)
        root.addLayout(footer)

    def _resolve_product_price_ttc(self, prod: Dict[str, Any]) -> float:
        for key in ("Selling_Price_TTC", "Prix_1_TTC", "Price_1_TTC"):
            if prod.get(key) is not None and float(prod.get(key) or 0) > 0:
                return float(prod[key])
        ht = float(prod.get("Default_Selling_Price_HT") or prod.get("Selling_Price_HT") or 0.0)
        tva = float(prod.get("Selling_TVA_Percent") or 0.0)
        return round(ht * (1.0 + tva / 100.0), 2)

    def _filter_catalog(self) -> None:
        q = self.txt_cat_search.text().strip().lower()
        filtered: List[Dict[str, Any]] = []
        for p in self._catalog_items:
            if q:
                hay = " ".join(
                    str(p.get(k) or "")
                    for k in ("Product_Name", "Brand_Mark", "Color_Finish", "Barcode", "Manuf_Cat_No", "Primary_Ref", "Ref_Code")
                ).lower()
                if q not in hay:
                    continue
            filtered.append(p)
        self._filtered_catalog = filtered[:120]
        self._populate_catalog_table()

    def _populate_catalog_table(self) -> None:
        self.cat_table.setRowCount(0)
        bold = QFont("Segoe UI", 9, QFont.Bold)
        for row_idx, p in enumerate(self._filtered_catalog):
            self.cat_table.insertRow(row_idx)
            name = str(p.get("Product_Name") or "")
            brand = str(p.get("Brand_Mark") or "").strip()
            disp_name = f"{brand} — {name}" if brand and brand.lower() not in name.lower() else name

            it_name = QTableWidgetItem(disp_name)
            it_name.setFont(bold)
            self.cat_table.setItem(row_idx, 0, it_name)

            ref_code = str(p.get("Manuf_Cat_No") or p.get("Primary_Ref") or p.get("Barcode") or "—")
            it_ref = QTableWidgetItem(ref_code)
            it_ref.setTextAlignment(Qt.AlignCenter)
            self.cat_table.setItem(row_idx, 1, it_ref)

            avail = int(p.get("Available_Theoretical_Qty") if p.get("Available_Theoretical_Qty") is not None else (p.get("Physical_Stock_Qty") or 0))
            it_stk = QTableWidgetItem(str(avail))
            it_stk.setTextAlignment(Qt.AlignCenter)
            it_stk.setForeground(QColor("#15803D" if avail > 0 else "#DC2626"))
            self.cat_table.setItem(row_idx, 2, it_stk)

            price_ttc = self._resolve_product_price_ttc(p)
            it_pr = QTableWidgetItem(f"{format_money(price_ttc)} DA")
            it_pr.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.cat_table.setItem(row_idx, 3, it_pr)

            btn_add = QPushButton("+ Ajouter")
            btn_add.setFixedHeight(28)
            btn_add.setCursor(Qt.PointingHandCursor)
            btn_add.setStyleSheet(
                "QPushButton { background:#CCFBF1; color:#0F766E; border:1px solid #99F6E4; "
                "border-radius:4px; font-size:11px; font-weight:700; padding:0px 6px; }"
                "QPushButton:hover { background:#0F766E; color:#FFFFFF; }"
            )
            btn_add.clicked.connect(lambda _=False, prod=p: self._add_product_to_bon(prod))
            self.cat_table.setCellWidget(row_idx, 4, btn_add)

    def _on_catalog_double_click(self, index) -> None:
        r = index.row()
        if 0 <= r < len(self._filtered_catalog):
            self._add_product_to_bon(self._filtered_catalog[r])

    def _add_product_to_bon(self, prod: Dict[str, Any]) -> None:
        pid = int(prod.get("Product_ID") or 0)
        if pid <= 0:
            return
        for ln in self._bon_lines:
            if ln["product_id"] == pid:
                ln["quantity"] += 1
                self._rebuild_lines_table()
                return

        self._bon_lines.append(
            {
                "product_id": pid,
                "name": str(prod.get("Product_Name") or f"Produit #{pid}"),
                "brand": str(prod.get("Brand_Mark") or ""),
                "color": str(prod.get("Color_Finish") or ""),
                "barcode": str(prod.get("Barcode") or ""),
                "quantity": 1,
                "unit_price_ttc": self._resolve_product_price_ttc(prod),
            }
        )
        self._rebuild_lines_table()

    def _rebuild_lines_table(self) -> None:
        self.lines_table.setRowCount(0)
        bold = QFont("Segoe UI", 9, QFont.Bold)
        for idx, ln in enumerate(self._bon_lines):
            self.lines_table.insertRow(idx)

            it_name = QTableWidgetItem(ln["name"])
            it_name.setFont(bold)
            self.lines_table.setItem(idx, 0, it_name)

            sp_qty = QSpinBox()
            sp_qty.setRange(1, 9999)
            sp_qty.setValue(int(ln["quantity"]))
            sp_qty.setFixedHeight(30)
            sp_qty.valueChanged.connect(lambda val, i=idx: self._on_line_qty_changed(i, val))
            self.lines_table.setCellWidget(idx, 1, sp_qty)

            sp_price = QDoubleSpinBox()
            sp_price.setRange(0.0, 99999999.0)
            sp_price.setDecimals(2)
            sp_price.setSingleStep(100.0)
            sp_price.setValue(float(ln["unit_price_ttc"]))
            sp_price.setFixedHeight(30)
            sp_price.valueChanged.connect(lambda val, i=idx: self._on_line_price_changed(i, val))
            self.lines_table.setCellWidget(idx, 2, sp_price)

            line_tot = float(ln["quantity"]) * float(ln["unit_price_ttc"])
            it_tot = QTableWidgetItem(f"{format_money(line_tot)} DA")
            it_tot.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_tot.setFont(bold)
            self.lines_table.setItem(idx, 3, it_tot)

            btn_del = QPushButton("×")
            btn_del.setFixedSize(28, 28)
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.setToolTip("Retirer ce produit du bon")
            btn_del.setStyleSheet(
                "QPushButton { background:#FEE2E2; color:#B91C1C; border:none; border-radius:4px; font-weight:800; font-size:14px; }"
                "QPushButton:hover { background:#EF4444; color:#FFFFFF; }"
            )
            btn_del.clicked.connect(lambda _=False, i=idx: self._remove_line(i))
            wrap = QWidget()
            wl = QHBoxLayout(wrap)
            wl.setContentsMargins(0, 0, 0, 0)
            wl.setAlignment(Qt.AlignCenter)
            wl.addWidget(btn_del)
            self.lines_table.setCellWidget(idx, 4, wrap)

        self._recalculate_totals()

    def _on_line_qty_changed(self, idx: int, val: int) -> None:
        if 0 <= idx < len(self._bon_lines):
            self._bon_lines[idx]["quantity"] = int(val)
            self._update_line_total_cell(idx)
            self._recalculate_totals()

    def _on_line_price_changed(self, idx: int, val: float) -> None:
        if 0 <= idx < len(self._bon_lines):
            self._bon_lines[idx]["unit_price_ttc"] = float(val)
            self._update_line_total_cell(idx)
            self._recalculate_totals()

    def _update_line_total_cell(self, idx: int) -> None:
        ln = self._bon_lines[idx]
        line_tot = float(ln["quantity"]) * float(ln["unit_price_ttc"])
        it = self.lines_table.item(idx, 3)
        if it:
            it.setText(f"{format_money(line_tot)} DA")

    def _remove_line(self, idx: int) -> None:
        if 0 <= idx < len(self._bon_lines):
            self._bon_lines.pop(idx)
            self._rebuild_lines_table()

    def _recalculate_totals(self) -> None:
        new_total = sum(float(ln["quantity"]) * float(ln["unit_price_ttc"]) for ln in self._bon_lines)
        new_rem = max(0.0, new_total - self._already_paid)

        self.lbl_new_total.setText(f"Nouveau Total : {format_money(new_total)} DA")
        self.lbl_new_rem.setText(f"Reste : {format_money(new_rem)} DA")

        err = ""
        if not self._bon_lines:
            err = "Le bon doit contenir au moins un produit."
        elif new_total + 0.01 < self._already_paid:
            err = (
                f"Le nouveau total ({format_money(new_total)} DA) ne peut pas être inférieur "
                f"au montant déjà versé ({format_money(self._already_paid)} DA)."
            )

        self.lbl_validation_err.setText(err)
        self.lbl_validation_err.setVisible(bool(err))
        self.btn_save.setEnabled(not bool(err))
        self.btn_save.setToolTip(err if err else "Enregistrer les nouveaux produits et recalculer le bon")

    def _save_changes(self) -> None:
        if not self._bon_lines:
            return
        if not self._bonds_mgr or not hasattr(self._bonds_mgr, "update_sales_order_draft"):
            QMessageBox.warning(self, "Erreur", "Gestionnaire de bons indisponible.")
            return

        client_id = int(self._order_full.get("Client_ID") or self.bon_data.get("Client_ID") or 1)
        bond_type = str(self._order_full.get("Bond_Type") or self.bon_data.get("Bond_Type") or "BON_VERSEMENT")
        deliv_addr = self._order_full.get("Delivery_Address") or self.bon_data.get("Delivery_Address")
        uid = int(self.current_user.get("User_ID") or 1)

        items_payload = [
            {
                "product_id": int(ln["product_id"]),
                "quantity": int(ln["quantity"]),
                "unit_price_ttc": Decimal(str(ln["unit_price_ttc"])).quantize(Decimal("0.01")),
                "color": ln.get("color") or None,
            }
            for ln in self._bon_lines
        ]

        try:
            self._bonds_mgr.update_sales_order_draft(
                order_id=self.order_id,
                client_id=client_id,
                bond_type=bond_type,
                items=items_payload,
                delivery_address=deliv_addr,
                user_id=uid,
            )
            self.has_changes = True
            self.accept()
        except Exception as err:
            QMessageBox.critical(self, "Modification Impossible", str(err))
