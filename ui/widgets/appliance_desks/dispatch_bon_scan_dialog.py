# -*- coding: utf-8 -*-
"""
Large modal dialog for Sortie Magasin (Dispatch Desk) allowing storekeepers to
perform a fresh, complete barcode/Réf/serial scan of all pre-selected products
in a Caisse-confirmed Bon, and then confirm & emit a Bon de Sortie or Bon Rouge.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.formatting import format_money
from ui.icons import get_duotone_icon
from ui.widgets.appliance_desks._theme import (
    BORDER_SUBTLE,
    BRAND_TEAL,
    BRAND_TEAL_TINT,
    BUREAUX_TABLE_QSS,
    CARD_BG,
    INPUT_QSS,
    PRIMARY_CTA_QSS,
    SLATE_OUTLINE_QSS,
    TEXT_PRIMARY,
)
from ui.widgets.appliance_desks.bon_pdf_export import export_exit_bon_to_pdf


BON_ROUGE_CTA_QSS = """
    QPushButton {
        background-color: #B91C1C;
        color: #FFFFFF;
        border: none;
        border-radius: 6px;
        font-size: 13px;
        font-weight: 700;
        padding: 0px 18px;
    }
    QPushButton:hover { background-color: #991B1B; }
    QPushButton:pressed { background-color: #7F1D1D; }
    QPushButton:disabled {
        background-color: #E2E8F0;
        color: #94A3B8;
    }
"""


class DispatchBonScanDialog(QDialog):
    """
    Large verification dialog for a single Bon in Sortie Magasin.
    - For pending bons: requires a fresh complete scan of every pre-selected product
      (by Product Barcode, Réf / Manuf_Cat_No, Batch Barcode, or Serial Number),
      then enables 'Confirmer & Bon de Sortie' and 'Confirmer & Bon Rouge'.
    - For completed bons: displays the completed summary and allows re-exporting
      the Bon de Sortie / Bon Rouge PDF.
    """

    def __init__(
        self,
        data_manager: Any,
        order_data: Dict[str, Any],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.data_manager = data_manager
        self.order_data = dict(order_data or {})
        self.is_completed = bool(self.order_data.get("Is_Completed"))
        self.dispatch_result: Optional[Dict[str, Any]] = None

        self._line_states: List[Dict[str, Any]] = []
        self._used_serials: Set[str] = set()
        self._build_line_states()

        ord_num = str(self.order_data.get("Order_Number") or f"#{self.order_data.get('Order_ID', '')}")
        self.setWindowTitle(f"Sortie Magasin — {ord_num}")
        self.setModal(True)
        self.resize(1040, 680)
        self.setMinimumSize(860, 560)

        self._init_ui()
        self._refresh_table()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self.is_completed and hasattr(self, "txt_scan"):
            QTimer.singleShot(50, self.txt_scan.setFocus)

    def _build_line_states(self) -> None:
        self._line_states = []
        for line in self.order_data.get("lines") or []:
            qty_ordered = max(1, int(line.get("Quantity_Ordered") or 1))
            qty_already_dispatched = max(0, int(line.get("Quantity_Dispatched") or 0))
            qty_required = qty_ordered if self.is_completed else max(0, qty_ordered - qty_already_dispatched)
            if not self.is_completed and qty_required <= 0:
                continue

            # Collect all valid product/Réf/batch codes for this line
            valid_codes: Set[str] = set()
            for field in ("Barcode", "Manuf_Cat_No"):
                v = str(line.get(field) or "").strip()
                if v:
                    valid_codes.add(v.upper())
            for csv_field in ("Batch_Barcodes", "Batch_Refs"):
                raw_csv = str(line.get(csv_field) or "")
                for part in raw_csv.split(","):
                    p = part.strip()
                    if p:
                        valid_codes.add(p.upper())

            ref_display = str(line.get("Manuf_Cat_No") or "").strip()
            bc_display = str(line.get("Barcode") or "").strip()
            if ref_display and bc_display and ref_display != bc_display:
                code_display = f"{ref_display}  |  {bc_display}"
            else:
                code_display = bc_display or ref_display or "—"

            self._line_states.append(
                {
                    "line_id": int(line.get("Line_ID") or 0),
                    "product_id": int(line.get("Product_ID") or 0),
                    "product_name": str(line.get("Product_Name") or ""),
                    "brand": str(line.get("Brand_Mark") or ""),
                    "color": str(line.get("Color_Finish") or ""),
                    "code_display": code_display,
                    "valid_codes": valid_codes,
                    "qty_ordered": qty_ordered,
                    "qty_required": qty_required,
                    "scanned_codes": [] if not self.is_completed else ["VÉRIFIÉ"] * qty_ordered,
                    "unit_price_ttc": float(line.get("Unit_Price_TTC") or 0.0),
                    "last_scan_time": "-" if not self.is_completed else str(self.order_data.get("Exit_Timestamp") or "-")[:16],
                }
            )

    def _init_ui(self) -> None:
        self.setObjectName("DispatchBonScanDialog")
        self.setStyleSheet(
            f"QDialog#DispatchBonScanDialog {{ background-color: #F8FAFC; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        # 1. Header Info Card
        hdr_card = QFrame()
        hdr_card.setObjectName("DispatchDialogHeader")
        hdr_card.setStyleSheet(
            f"QFrame#DispatchDialogHeader {{ background-color: {CARD_BG}; border: 1px solid {BORDER_SUBTLE}; border-radius: 10px; }}"
            "QFrame#DispatchDialogHeader QLabel { border: none; background: transparent; }"
        )
        hdr_lay = QVBoxLayout(hdr_card)
        hdr_lay.setContentsMargins(16, 12, 16, 12)
        hdr_lay.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        ord_num = str(self.order_data.get("Order_Number") or f"#{self.order_data.get('Order_ID', '')}")
        lbl_bon = QLabel(f"Bon : {ord_num}")
        lbl_bon.setStyleSheet(f"font-size: 17px; font-weight: 800; color: {TEXT_PRIMARY};")
        top_row.addWidget(lbl_bon)

        b_type = str(self.order_data.get("Bond_Type") or "BON_C").upper()
        type_map = {
            "BON_C": ("Paiement Complet (PC)", "#0F766E", "#CCFBF1"),
            "BON_VERSEMENT": ("Versement (PC)", "#0F766E", "#CCFBF1"),
            "BON_LIVRAISON": ("Paiement à la Livraison (PL)", "#B45309", "#FEF3C7"),
            "BON_CREDIT": ("Paiement à Crédit (CR)", "#1D4ED8", "#DBEAFE"),
        }
        t_txt, t_fg, t_bg = type_map.get(b_type, (b_type, "#334155", "#E2E8F0"))
        lbl_type = QLabel(t_txt)
        lbl_type.setStyleSheet(
            f"font-size: 11.5px; font-weight: 700; color: {t_fg}; background-color: {t_bg}; "
            f"border-radius: 10px; padding: 3px 10px;"
        )
        top_row.addWidget(lbl_type)
        top_row.addStretch(1)

        self.lbl_progress = QLabel("")
        self.lbl_progress.setStyleSheet(
            f"font-size: 13px; font-weight: 800; color: {BRAND_TEAL}; background-color: {BRAND_TEAL_TINT}; "
            f"border-radius: 8px; padding: 5px 12px;"
        )
        top_row.addWidget(self.lbl_progress)
        hdr_lay.addLayout(top_row)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(18)
        client_name = str(self.order_data.get("Client_Name") or "Client Comptoir")
        phone = str(self.order_data.get("Client_Phone") or "").strip()
        addr = str(self.order_data.get("Delivery_Address") or "").strip()
        total_ttc = float(self.order_data.get("Total_Amount_TTC") or 0.0)

        lbl_client = QLabel(f"<b>Client :</b> {client_name}" + (f"  •  <b>Tél :</b> {phone}" if phone else ""))
        lbl_client.setStyleSheet("font-size: 12.5px; color: #334155;")
        meta_row.addWidget(lbl_client)

        if addr:
            lbl_addr = QLabel(f"<b>Adresse :</b> {addr}")
            lbl_addr.setStyleSheet("font-size: 12.5px; color: #475569;")
            meta_row.addWidget(lbl_addr)

        meta_row.addStretch(1)
        lbl_tot = QLabel(f"<b>Total TTC :</b> {format_money(total_ttc)} DA")
        lbl_tot.setStyleSheet("font-size: 13px; color: #0F172A;")
        meta_row.addWidget(lbl_tot)
        hdr_lay.addLayout(meta_row)

        if self.is_completed:
            exit_no = str(self.order_data.get("Exit_Bond_Number") or "—")
            doc_t = "Bon Rouge" if self.order_data.get("Exit_Doc_Type") == "BON_ROUGE" else "Bon de Sortie"
            ts = str(self.order_data.get("Exit_Timestamp") or "")[:16]
            done_banner = QLabel(
                f"Sortie déjà complétée — Document émis : {doc_t} ({exit_no})" + (f" le {ts}" if ts else "")
            )
            done_banner.setStyleSheet(
                "font-size: 12.5px; font-weight: 700; color: #15803D; background-color: #DCFCE7; "
                "border-radius: 6px; padding: 6px 10px;"
            )
            hdr_lay.addWidget(done_banner)

        root.addWidget(hdr_card)

        # 2. Scanner Input Card (only for pending bons)
        if not self.is_completed:
            scan_card = QFrame()
            scan_card.setObjectName("DispatchDialogScanCard")
            scan_card.setStyleSheet(
                f"QFrame#DispatchDialogScanCard {{ background-color: {CARD_BG}; border: 1.5px solid {BRAND_TEAL}; border-radius: 10px; }}"
                "QFrame#DispatchDialogScanCard QLabel { border: none; background: transparent; }"
            )
            sc_lay = QVBoxLayout(scan_card)
            sc_lay.setContentsMargins(14, 10, 14, 10)
            sc_lay.setSpacing(6)

            row_in = QHBoxLayout()
            row_in.setSpacing(8)

            ic = QLabel()
            ic.setPixmap(get_duotone_icon("barcode_scan", 20).pixmap(20, 20))
            row_in.addWidget(ic)

            self.txt_scan = QLineEdit()
            self.txt_scan.setFixedHeight(40)
            self.txt_scan.setStyleSheet(INPUT_QSS + "QLineEdit { font-size: 13.5px; font-weight: 600; }")
            self.txt_scan.setPlaceholderText(
                "Scanner le Code-Barres produit, Réf ou N° de Série puis appuyer sur Entrée..."
            )
            self.txt_scan.returnPressed.connect(self._on_scan_submit)
            row_in.addWidget(self.txt_scan, 1)

            btn_scan = QPushButton("Valider Scan")
            btn_scan.setFixedHeight(40)
            btn_scan.setCursor(Qt.PointingHandCursor)
            btn_scan.setStyleSheet(PRIMARY_CTA_QSS)
            btn_scan.clicked.connect(self._on_scan_submit)
            row_in.addWidget(btn_scan)

            btn_reset_scans = QPushButton("Réinitialiser")
            btn_reset_scans.setFixedHeight(40)
            btn_reset_scans.setCursor(Qt.PointingHandCursor)
            btn_reset_scans.setStyleSheet(SLATE_OUTLINE_QSS)
            btn_reset_scans.setToolTip("Effacer tous les scans en cours pour recommencer")
            btn_reset_scans.clicked.connect(self._reset_scans)
            row_in.addWidget(btn_reset_scans)

            sc_lay.addLayout(row_in)

            self.lbl_scan_feedback = QLabel(
                "Scannez chaque produit listé ci-dessous pour débloquer l'émission du Bon de Sortie ou Bon Rouge."
            )
            self.lbl_scan_feedback.setStyleSheet("font-size: 12px; color: #475569; font-weight: 600;")
            sc_lay.addWidget(self.lbl_scan_feedback)
            root.addWidget(scan_card)

        # 3. Pre-selected Products Table
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Produit",
            "Marque / Couleur",
            "Réf / Code-Barres",
            "Qté Attendue",
            "Scanné",
            "Dernier Code Scanné",
            "Statut",
        ])
        self.table.setStyleSheet(BUREAUX_TABLE_QSS)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.horizontalHeader().setFixedHeight(38)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        root.addWidget(self.table, 1)

        # 4. Footer Actions
        footer = QHBoxLayout()
        footer.setSpacing(10)

        btn_close = QPushButton("Fermer")
        btn_close.setFixedHeight(40)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet(SLATE_OUTLINE_QSS)
        btn_close.clicked.connect(self.reject)
        footer.addWidget(btn_close)

        footer.addStretch(1)

        if self.is_completed:
            self.btn_reprint_sortie = QPushButton("Exporter Bon de Sortie (PDF)")
            self.btn_reprint_sortie.setIcon(get_duotone_icon("print_white", 16))
            self.btn_reprint_sortie.setIconSize(QSize(16, 16))
            self.btn_reprint_sortie.setFixedHeight(42)
            self.btn_reprint_sortie.setCursor(Qt.PointingHandCursor)
            self.btn_reprint_sortie.setStyleSheet(PRIMARY_CTA_QSS)
            self.btn_reprint_sortie.clicked.connect(lambda: self._export_completed_pdf("BON_SORTIE"))
            footer.addWidget(self.btn_reprint_sortie)

            self.btn_reprint_rouge = QPushButton("Exporter Bon Rouge (PDF)")
            self.btn_reprint_rouge.setIcon(get_duotone_icon("print_white", 16))
            self.btn_reprint_rouge.setIconSize(QSize(16, 16))
            self.btn_reprint_rouge.setFixedHeight(42)
            self.btn_reprint_rouge.setCursor(Qt.PointingHandCursor)
            self.btn_reprint_rouge.setStyleSheet(BON_ROUGE_CTA_QSS)
            self.btn_reprint_rouge.clicked.connect(lambda: self._export_completed_pdf("BON_ROUGE"))
            footer.addWidget(self.btn_reprint_rouge)
        else:
            self.btn_confirm_sortie = QPushButton("Confirmer && Bon de Sortie")
            self.btn_confirm_sortie.setIcon(get_duotone_icon("print_white", 16))
            self.btn_confirm_sortie.setIconSize(QSize(16, 16))
            self.btn_confirm_sortie.setFixedHeight(42)
            self.btn_confirm_sortie.setCursor(Qt.PointingHandCursor)
            self.btn_confirm_sortie.setStyleSheet(PRIMARY_CTA_QSS)
            self.btn_confirm_sortie.setEnabled(False)
            self.btn_confirm_sortie.clicked.connect(lambda: self._confirm_dispatch("BON_SORTIE"))
            footer.addWidget(self.btn_confirm_sortie)

            self.btn_confirm_rouge = QPushButton("Confirmer && Bon Rouge")
            self.btn_confirm_rouge.setIcon(get_duotone_icon("print_white", 16))
            self.btn_confirm_rouge.setIconSize(QSize(16, 16))
            self.btn_confirm_rouge.setFixedHeight(42)
            self.btn_confirm_rouge.setCursor(Qt.PointingHandCursor)
            self.btn_confirm_rouge.setStyleSheet(BON_ROUGE_CTA_QSS)
            self.btn_confirm_rouge.setEnabled(False)
            self.btn_confirm_rouge.clicked.connect(lambda: self._confirm_dispatch("BON_ROUGE"))
            footer.addWidget(self.btn_confirm_rouge)

        root.addLayout(footer)

    def _set_feedback(self, text: str, kind: str = "info") -> None:
        if not hasattr(self, "lbl_scan_feedback"):
            return
        styles = {
            "ok": "font-size: 12px; color: #15803D; font-weight: 700;",
            "error": "font-size: 12px; color: #DC2626; font-weight: 700;",
            "warn": "font-size: 12px; color: #B45309; font-weight: 700;",
            "info": "font-size: 12px; color: #475569; font-weight: 600;",
        }
        self.lbl_scan_feedback.setStyleSheet(styles.get(kind, styles["info"]))
        self.lbl_scan_feedback.setText(text)

    def _reset_scans(self) -> None:
        self._used_serials.clear()
        for st in self._line_states:
            st["scanned_codes"] = []
            st["last_scan_time"] = "-"
        self._set_feedback("Scans réinitialisés. Veuillez rescanner les produits du bon.", "info")
        self._refresh_table()
        if hasattr(self, "txt_scan"):
            self.txt_scan.setFocus()

    def _on_scan_submit(self) -> None:
        raw = self.txt_scan.text().strip()
        self.txt_scan.clear()
        if raw:
            self.process_scan(raw)
        self.txt_scan.setFocus()

    def process_scan(self, raw_scan: str) -> bool:
        """
        Matches a scanned barcode / Réf / serial number against pending pre-selected lines.
        Supports product-level barcode/Réf tracking AND unique serial tracking.
        """
        if self.is_completed:
            return False

        clean = raw_scan.strip()
        clean_up = clean.upper()
        if not clean_up:
            return False

        explicit_prod_id: Optional[int] = None
        code_part = clean_up
        if "::" in clean_up:
            parts = clean_up.split("::", 1)
            if parts[0].isdigit():
                explicit_prod_id = int(parts[0])
                code_part = parts[1].strip()

        # 1. Check if this code is a registered unique serial in Product_Serials
        is_serial = False
        if self.data_manager and hasattr(self.data_manager, "serials"):
            try:
                db_serial = self.data_manager.serials.get_serial_details(code_part)
            except Exception:
                db_serial = None
            if db_serial:
                if db_serial.get("Status") != "IN_STOCK":
                    self._set_feedback(
                        f"Rejeté : le N° de Série '{code_part}' n'est pas en stock ({db_serial.get('Status')}).",
                        "error",
                    )
                    return False
                if code_part in self._used_serials:
                    self._set_feedback(
                        f"Doublon : le N° de Série '{code_part}' a déjà été scanné sur ce bon.",
                        "error",
                    )
                    return False
                explicit_prod_id = int(db_serial["Product_ID"])
                is_serial = True

        # 2. If not resolved yet, try universal barcode lookup (Products_Master / Inventory_Batches / Réf)
        if explicit_prod_id is None and self.data_manager and hasattr(self.data_manager, "serials"):
            if hasattr(self.data_manager.serials, "find_product_by_any_barcode"):
                try:
                    found = self.data_manager.serials.find_product_by_any_barcode(code_part)
                    if isinstance(found, dict) and found.get("Product_ID"):
                        explicit_prod_id = int(found["Product_ID"])
                except Exception:
                    pass

        # 3. Match against a line that still needs scans
        matched_line = None
        already_complete_match = False
        for st in self._line_states:
            code_matches = (
                (explicit_prod_id is not None and st["product_id"] == explicit_prod_id)
                or (code_part in st["valid_codes"])
            )
            if not code_matches:
                continue
            if len(st["scanned_codes"]) < st["qty_required"]:
                matched_line = st
                break
            already_complete_match = True

        if matched_line is None:
            if already_complete_match:
                self._set_feedback(
                    f"Quantité déjà atteinte pour le code '{code_part}'.",
                    "warn",
                )
            else:
                self._set_feedback(
                    f"Produit non attendu : le code '{code_part}' ne correspond à aucun article de ce bon.",
                    "error",
                )
            return False

        matched_line["scanned_codes"].append(code_part)
        matched_line["last_scan_time"] = datetime.now().strftime("%H:%M:%S")
        if is_serial:
            self._used_serials.add(code_part)

        done_cnt = len(matched_line["scanned_codes"])
        req_cnt = matched_line["qty_required"]
        self._set_feedback(
            f"Validé : {matched_line['product_name']} ({done_cnt}/{req_cnt}) — Code : {code_part}",
            "ok",
        )
        self._refresh_table()
        return True

    def _refresh_table(self) -> None:
        self.table.setRowCount(0)
        total_req = 0
        total_done = 0

        for st in self._line_states:
            row = self.table.rowCount()
            self.table.insertRow(row)

            req = st["qty_required"]
            done = len(st["scanned_codes"])
            total_req += req
            total_done += done
            complete = done >= req

            it_prod = QTableWidgetItem(st["product_name"])
            it_prod.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self.table.setItem(row, 0, it_prod)

            meta = " • ".join(p for p in (st["brand"], st["color"]) if p) or "—"
            it_meta = QTableWidgetItem(meta)
            it_meta.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, it_meta)

            it_code = QTableWidgetItem(st["code_display"])
            it_code.setTextAlignment(Qt.AlignCenter)
            it_code.setFont(QFont("Consolas", 9))
            self.table.setItem(row, 2, it_code)

            it_req = QTableWidgetItem(str(req))
            it_req.setTextAlignment(Qt.AlignCenter)
            it_req.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self.table.setItem(row, 3, it_req)

            it_done = QTableWidgetItem(f"{done} / {req}")
            it_done.setTextAlignment(Qt.AlignCenter)
            it_done.setFont(QFont("Segoe UI", 10, QFont.Bold))
            it_done.setForeground(QColor("#15803D" if complete else "#B45309"))
            self.table.setItem(row, 4, it_done)

            last_code = st["scanned_codes"][-1] if st["scanned_codes"] else "—"
            it_last = QTableWidgetItem(last_code)
            it_last.setTextAlignment(Qt.AlignCenter)
            it_last.setFont(QFont("Consolas", 9, QFont.Bold))
            self.table.setItem(row, 5, it_last)

            st_text = "COMPLÉTÉ" if complete else f"RESTE {req - done}"
            it_st = QTableWidgetItem(st_text)
            it_st.setTextAlignment(Qt.AlignCenter)
            it_st.setFont(QFont("Segoe UI", 9, QFont.Bold))
            it_st.setForeground(QColor("#15803D" if complete else "#D97706"))
            self.table.setItem(row, 6, it_st)

        all_complete = total_req > 0 and total_done >= total_req
        self.lbl_progress.setText(f"Scannés : {total_done} / {total_req}")
        if all_complete:
            self.lbl_progress.setStyleSheet(
                "font-size: 13px; font-weight: 800; color: #15803D; background-color: #DCFCE7; "
                "border-radius: 8px; padding: 5px 12px;"
            )
        else:
            self.lbl_progress.setStyleSheet(
                f"font-size: 13px; font-weight: 800; color: {BRAND_TEAL}; background-color: {BRAND_TEAL_TINT}; "
                f"border-radius: 8px; padding: 5px 12px;"
            )

        if not self.is_completed:
            tip_disabled = (
                f"Scannez tous les produits restants ({total_done}/{total_req}) avant de confirmer la sortie."
            )
            self.btn_confirm_sortie.setEnabled(all_complete)
            self.btn_confirm_sortie.setToolTip(
                "Confirmer la sortie physique et générer le Bon de Sortie" if all_complete else tip_disabled
            )
            self.btn_confirm_rouge.setEnabled(all_complete)
            self.btn_confirm_rouge.setToolTip(
                "Confirmer la sortie physique et générer le Bon Rouge" if all_complete else tip_disabled
            )

    def _confirm_dispatch(self, exit_doc_type: str) -> None:
        scans_payload: List[Dict[str, Any]] = []
        for st in self._line_states:
            for code in st["scanned_codes"]:
                scans_payload.append(
                    {
                        "order_line_id": st["line_id"],
                        "product_id": st["product_id"],
                        "scanned_code": code,
                    }
                )
        if not scans_payload:
            return

        order_id = int(self.order_data["Order_ID"])
        invoice_id = int(self.order_data.get("Invoice_ID") or 0)
        doc_label = "Bon Rouge" if exit_doc_type == "BON_ROUGE" else "Bon de Sortie"

        try:
            if self.data_manager and hasattr(self.data_manager, "bonds"):
                uid = int((getattr(self.data_manager, "current_user", None) or {}).get("User_ID") or 1)
                res = self.data_manager.bonds.validate_and_dispatch_items(
                    order_id=order_id,
                    invoice_id=invoice_id,
                    storekeeper_user_id=uid,
                    scanned_items=scans_payload,
                    exit_doc_type=exit_doc_type,
                )
            else:
                pfx = "BRG" if exit_doc_type == "BON_ROUGE" else "BS"
                res = {
                    "success": True,
                    "exit_bond_number": f"{pfx}-SIM-{order_id}",
                    "exit_doc_type": exit_doc_type,
                    "gate_pass": f"GATE-{order_id:04d}",
                    "order_status": "COMPLETED",
                }

            self.dispatch_result = res
            exit_num = res.get("exit_bond_number", "")
            gate_pass = res.get("gate_pass", "")

            reply = QMessageBox.question(
                self,
                f"{doc_label} Validé",
                f"{doc_label} ({exit_num}) généré avec succès.\n"
                f"Code laissez-passer : {gate_pass}\n\n"
                f"Souhaitez-vous exporter le {doc_label} en PDF maintenant ?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.Yes:
                export_exit_bon_to_pdf(
                    self.data_manager,
                    self.order_data,
                    exit_info={
                        "exit_bond_number": exit_num,
                        "exit_doc_type": exit_doc_type,
                        "gate_pass": gate_pass,
                        "scanned_lines": self._line_states,
                    },
                    parent_widget=self,
                )

            self.accept()
        except Exception as err:
            QMessageBox.critical(self, f"Erreur {doc_label}", str(err))

    def _export_completed_pdf(self, exit_doc_type: str) -> None:
        exit_num = str(self.order_data.get("Exit_Bond_Number") or f"BS-{self.order_data.get('Order_ID', 0)}")
        export_exit_bon_to_pdf(
            self.data_manager,
            self.order_data,
            exit_info={
                "exit_bond_number": exit_num,
                "exit_doc_type": exit_doc_type,
                "gate_pass": "",
                "scanned_lines": self._line_states,
            },
            parent_widget=self,
        )
