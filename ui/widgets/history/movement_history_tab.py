import logging

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QHeaderView,
    QPushButton,
    QHBoxLayout,
    QLabel,
    QTableWidgetItem,
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, QDate, QSize, QTimer
from PySide6.QtGui import QColor, QBrush, QFont

from ui.icons import get_duotone_icon
from ui.widgets.inventory.dialogs import BarcodeLineEdit
from ui.formatting import format_money, format_quantity


class MovementDetailsDialog(QDialog):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.setWindowTitle("Détails de l'Opération")
        self.resize(550, 600)
        self.init_ui()

    def init_ui(self):
        self._build_details_view()

    def _build_details_view(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        def value(*keys, default="-"):
            for key in keys:
                val = self.data.get(key)
                if val not in (None, ""):
                    return str(val)
            return default

        def add_row(form, label, text):
            label_widget = QLabel(f"<b>{label}</b>")
            value_widget = QLabel(text)
            value_widget.setWordWrap(True)
            value_widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
            form.addRow(label_widget, value_widget)

        type_map = {
            "Purchase_Receive": "Réception (Achat)",
            "Patient_Test": "Consommation",
            "QC_Run": "QC",
            "Calibration": "Calibration",
            "Open_Pack": "Ouverture",
            "Adjustment": "Ajustement",
            "Waste": "Perte",
            "Transfer": "Transfert",
            "External_Transfer": "Vente/Externe",
            "Transfer_Return": "Retour Sous-traitant",
            "Return_To_Supplier": "Retour Fournisseur",
            "Sale": "Vente (POS)",
            "Sale_Return": "Retour Vente",
        }

        movement_type = value("Movement_Type")
        qty_raw = self.data.get("Qty_Change")
        try:
            qty_text = format_quantity(qty_raw, value("Unit_Used", default=""))
        except (TypeError, ValueError):
            qty_text = value("Qty_Change")

        main_group = QGroupBox("Operation")
        main_form = QFormLayout(main_group)
        add_row(main_form, "Date :", value("Transaction_Date")[:19])
        add_row(main_form, "Type :", type_map.get(movement_type, movement_type))
        add_row(main_form, "Quantite :", qty_text)
        add_row(
            main_form,
            "Stock apres mouvement :",
            value("Stock_After", "Batch_Historical_Stock", "Historical_Stock"),
        )
        add_row(main_form, "Utilisateur :", value("Operator_Name"))
        layout.addWidget(main_group)

        product_group = QGroupBox("Produit et lot")
        product_form = QFormLayout(product_group)
        add_row(product_form, "Produit :", value("Product_Name"))
        add_row(product_form, "Code-barres :", value("Batch_Barcode", "Product_Barcode"))
        add_row(product_form, "Lot :", value("Lot_Number"))
        add_row(product_form, "Emplacement :", value("Location_Name"))
        add_row(product_form, "Batch ID :", value("Batch_ID"))
        layout.addWidget(product_group)

        notes_group = QGroupBox("Notes")
        notes_form = QFormLayout(notes_group)
        add_row(notes_form, "Raison :", value("Reason_Name"))
        add_row(notes_form, "Notes :", value("Notes"))
        add_row(notes_form, "Mouvement ID :", value("Movement_ID", "Log_ID"))
        layout.addWidget(notes_group)

        btn_close = QPushButton("Fermer")
        btn_close.setIcon(get_duotone_icon("close_slate", 15))
        btn_close.setIconSize(QSize(15, 15))
        btn_close.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)


class MovementHistoryTab(QWidget):
    """Movement history with server-side filters and incremental loading."""

    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.current_offset = 0
        self.batch_size = 50
        self.total_records = 0
        self.is_loading = False
        self.has_more_data = True
        self.raw_data = []

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(300)
        self.search_timer.timeout.connect(self._on_debounced_search)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)

        self.date_from = QDateEdit(QDate.currentDate().addYears(-1))
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        self.date_from.setFixedWidth(115)
        self.date_from.setFixedHeight(36)
        self.date_from.setEnabled(True)
        self.date_from.dateChanged.connect(self.reset_and_reload)

        self.date_to = QDateEdit(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        self.date_to.setFixedWidth(115)
        self.date_to.setFixedHeight(36)
        self.date_to.setEnabled(True)
        self.date_to.dateChanged.connect(self.reset_and_reload)

        self.combo_type = QComboBox()
        self.combo_type.setFixedHeight(36)
        self.combo_type.setIconSize(QSize(15, 15))
        movement_filter_items = [
            ("Tous les mouvements", None, "filter"),
            ("Réceptions (Achats)", "Purchase_Receive", "receipt_in"),
            ("Consommations (Patients)", "Patient_Test", "consumption"),
            ("Contrôles Qualité (QC)", "QC_Run", "shield_admin"),
            ("Calibrations", "Calibration", "settings"),
            ("Ouvertures Boîtes", "Open_Pack", "box_product"),
            ("Ajustements Manuels", "Adjustment", "edit"),
            ("Rebuts / Pertes", "Waste", "waste_bin"),
            ("Transferts Internes", "Transfer", "transfer_arrows"),
            ("Ventes / Transf. Externes", "External_Transfer", "truck_delivery"),
            ("Retours Sous-traitants (BR)", "Transfer_Return", "return_arrow"),
            ("Retours Fournisseurs (Avoirs)", "Return_To_Supplier", "return_arrow"),
            ("Ventes / Sorties (POS & Bon de Sortie)", "Sale", "pos"),
            ("Retours Ventes (Bon de Retour)", "Sale_Return", "return_arrow"),
        ]
        for label, movement_type, icon_name in movement_filter_items:
            self.combo_type.addItem(get_duotone_icon(icon_name, 15), label, movement_type)

        self.combo_type.setMinimumWidth(220)
        self.combo_type.setStyleSheet("QComboBox { padding: 4px 8px; font-size: 13px; }")
        self.combo_type.currentIndexChanged.connect(self.reset_and_reload)

        # Unified search & barcode/serial scan input
        self.search_input = BarcodeLineEdit()
        self.search_input.setObjectName("UnifiedTraceSearchInput")
        self.search_input.setFixedHeight(36)
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setPlaceholderText(
            "Rechercher ou scanner (N° Série, Code-barres, Produit, Lot, Utilisateur)..."
        )
        self.search_input.setStyleSheet(
            "QLineEdit#UnifiedTraceSearchInput {"
            "  background-color: #FFFFFF;"
            "  border: 1.5px solid #CBD5E1;"
            "  border-radius: 6px;"
            "  padding: 4px 10px;"
            "  font-size: 13px;"
            "}"
            "QLineEdit#UnifiedTraceSearchInput:focus {"
            "  border-color: #0E7471;"
            "}"
        )
        self.search_input.textChanged.connect(self.on_search_text_changed)
        self.search_input.returnPressed.connect(self.verify_serial_number)

        btn_refresh = QPushButton()
        btn_refresh.setIcon(get_duotone_icon("refresh", 16))
        btn_refresh.setIconSize(QSize(16, 16))
        btn_refresh.setFixedSize(36, 36)
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setToolTip("Recharger")
        btn_refresh.clicked.connect(self.reset_and_reload)

        ic_cal = QLabel()
        ic_cal.setPixmap(get_duotone_icon("calendar", 16).pixmap(16, 16))
        filter_layout.addWidget(ic_cal)
        filter_layout.addWidget(QLabel("Du:"))
        filter_layout.addWidget(self.date_from)
        filter_layout.addWidget(QLabel("Au:"))
        filter_layout.addWidget(self.date_to)
        ic_flt = QLabel()
        ic_flt.setPixmap(get_duotone_icon("filter", 15).pixmap(15, 15))
        filter_layout.addWidget(ic_flt)
        filter_layout.addWidget(self.combo_type)
        filter_layout.addWidget(self.search_input, stretch=1)
        filter_layout.addWidget(btn_refresh)
        layout.addLayout(filter_layout)

        # Compact inline audit banner updated automatically when a serial number is scanned/searched
        self.serial_audit_banner = QFrame()
        self.serial_audit_banner.setObjectName("SerialAuditBanner")
        self.serial_audit_banner.setStyleSheet(
            "QFrame#SerialAuditBanner {"
            "  background-color: #F8FAFC;"
            "  border: 1px solid #CBD5E1;"
            "  border-radius: 6px;"
            "}"
            "QLabel { border: none; background: transparent; }"
        )
        banner_lay = QHBoxLayout(self.serial_audit_banner)
        banner_lay.setContentsMargins(10, 6, 10, 6)
        banner_lay.setSpacing(8)
        self.lbl_serial_audit_result = QLabel("")
        self.lbl_serial_audit_result.setWordWrap(True)
        self.lbl_serial_audit_result.setStyleSheet("color: #334155; font-size: 12px;")
        banner_lay.addWidget(self.lbl_serial_audit_result, 1)
        self.serial_audit_banner.setVisible(False)
        layout.addWidget(self.serial_audit_banner)

        self.PROFIT_COL = 10
        self.table = QTableWidget()
        columns = [
            "Date",
            "Produit",
            "Code-Barres",
            "Lot",
            "Type",
            "Mvt",
            "Stock",
            "Emplacement",
            "Utilisateur",
            "Notes",
            "Bénéfice",
        ]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)

        font = self.table.font()
        font.setPointSize(9)
        self.table.setFont(font)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.Stretch)
        header.setSectionResizeMode(self.PROFIT_COL, QHeaderView.ResizeToContents)
        self.table.setColumnHidden(self.PROFIT_COL, True)

        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self.show_full_details)
        self.table.verticalScrollBar().valueChanged.connect(self._on_scroll)
        layout.addWidget(self.table)

        status_layout = QHBoxLayout()
        status_layout.setSpacing(8)
        self.lbl_status = QLabel("0/0")
        self.lbl_status.setStyleSheet(
            "font-weight: bold; font-size: 12px; color: #2c3e50;"
        )
        status_layout.addWidget(self.lbl_status, stretch=1)
        layout.addLayout(status_layout)

        self.reset_and_reload()

    def on_search_text_changed(self):
        if not self.search_input.text().strip():
            self.lbl_serial_audit_result.setText("")
            self.serial_audit_banner.setVisible(False)
        self.search_timer.start()

    def _on_debounced_search(self):
        query = self.search_input.text().strip()
        if len(query) >= 3:
            self._lookup_serial_badge(query, show_not_found=False)
        else:
            self.lbl_serial_audit_result.setText("")
            self.serial_audit_banner.setVisible(False)
        self.reset_and_reload()

    def _on_scroll(self, value):
        scroll_bar = self.table.verticalScrollBar()
        if scroll_bar.maximum() > 0 and value >= scroll_bar.maximum() - 20:
            self.load_next_batch()

    def reset_and_reload(self):
        self.current_offset = 0
        self.has_more_data = True
        self.table.setRowCount(0)
        self.total_records = 0
        self.raw_data = []
        is_sales_filter = self.combo_type.currentData() == "Sale"
        self.table.setColumnHidden(self.PROFIT_COL, not is_sales_filter)
        self.load_next_batch()

    def load_data(self):
        """Compatibility entry point used by MainWindow and inventory pages."""
        self.reset_and_reload()

    def filter_by_product(self, product_name):
        if product_name:
            self.search_input.setText(product_name)
            self.reset_and_reload()

    def get_active_filters(self):
        search_text = self.search_input.text().strip() or None
        return {
            "movement_type": self.combo_type.currentData(),
            "search_text": search_text,
            "start_date": self.date_from.date().toString("yyyy-MM-dd"),
            "end_date": self.date_to.date().toString("yyyy-MM-dd"),
        }

    def load_next_batch(self):
        if self.is_loading or not self.has_more_data:
            return

        self.is_loading = True
        self.lbl_status.setText("Chargement du lot suivant...")

        try:
            filters = self.get_active_filters()
            if self.current_offset == 0:
                self.total_records = self.manager.movement.get_movements_count(**filters)

            movements = self.manager.movement.get_movements_log(
                limit=self.batch_size,
                offset=self.current_offset,
                **filters,
            )

            if not movements:
                self.has_more_data = False
            else:
                self.raw_data.extend(movements)
                self._append_rows_to_table(movements)
                self.current_offset += len(movements)
                if len(movements) < self.batch_size:
                    self.has_more_data = False

            self.update_status_ui()
        except Exception as error:
            logging.error("Error fetching lazy movement batch: %s", error)
            self.lbl_status.setText("Erreur lors du chargement des données")
        finally:
            self.is_loading = False

    def update_status_ui(self):
        self.lbl_status.setText(f"{self.table.rowCount()}/{self.total_records}")

    def _append_rows_to_table(self, data):
        self.table.setSortingEnabled(False)
        start_row = self.table.rowCount()

        type_map = {
            "Purchase_Receive": "Réception (Achat)",
            "Patient_Test": "Consommation",
            "QC_Run": "QC",
            "Calibration": "Calibration",
            "Open_Pack": "Ouverture",
            "Adjustment": "Ajustement",
            "Waste": "Perte",
            "Transfer": "Transfert",
            "External_Transfer": "Vente/Externe",
            "Transfer_Return": "Retour Sous-traitant",
            "Return_To_Supplier": "Retour Fourn.",
            "Sale": "Vente (POS)",
            "Sale_Return": "Retour Vente",
        }

        for index, mov in enumerate(data):
            row = start_row + index
            self.table.insertRow(row)

            def item(text, align=Qt.AlignCenter, color=None, font=None):
                value = str(text) if text is not None else "-"
                table_item = QTableWidgetItem(value)
                table_item.setTextAlignment(align)
                if color:
                    table_item.setForeground(QBrush(QColor(color)))
                if font:
                    table_item.setFont(font)
                return table_item

            date_value = mov.get("Transaction_Date", "")
            self.table.setItem(row, 0, item(str(date_value)[:16]))
            self.table.item(row, 0).setData(Qt.UserRole, mov)

            self.table.setItem(
                row,
                1,
                item(mov.get("Product_Name", "-"), font=QFont("Segoe UI", 9, QFont.Bold)),
            )
            self.table.setItem(row, 2, item(mov.get("Batch_Barcode") or "-"))
            self.table.setItem(row, 3, item(mov.get("Lot_Number") or "-"))

            raw_type = mov.get("Movement_Type", "")
            notes_str = str(mov.get("Notes", "") or "")
            display_type = type_map.get(raw_type, raw_type)
            if raw_type == "Sale" and "Bon de Sortie" in notes_str:
                display_type = "Sortie Magasin (Bon de Sortie)"
            elif raw_type == "Sale_Return" and "Bon de Retour" in notes_str:
                display_type = "Bon de Retour (Avoir Virtuel)"
            type_item = item(display_type)
            if raw_type == "Purchase_Receive":
                type_item.setBackground(QBrush(QColor("#e8f5e9")))
            elif raw_type == "Waste":
                type_item.setBackground(QBrush(QColor("#ffebee")))
            elif raw_type == "Sale":
                type_item.setForeground(QBrush(QColor("#007572")))
            elif raw_type == "Sale_Return":
                type_item.setForeground(QBrush(QColor("#D97706")))
            elif raw_type in ["Patient_Test", "QC_Run"]:
                type_item.setForeground(QBrush(QColor("#1976d2")))
            self.table.setItem(row, 4, type_item)

            try:
                qty = float(mov.get("Qty_Change", 0) or 0)
            except (TypeError, ValueError):
                qty = 0
            self.table.setItem(
                row,
                5,
                item(
                    format_quantity(qty),
                    Qt.AlignCenter,
                    "#c0392b" if qty < 0 else "#27ae60",
                ),
            )

            batch_stock = mov.get("Batch_Historical_Stock")
            if batch_stock is None:
                batch_stock = mov.get("Stock_After")
            if batch_stock is None:
                batch_stock = mov.get("Historical_Stock")
            stock_text = format_quantity(batch_stock) if batch_stock is not None else "?"
            stock_item = item(stock_text, font=QFont("Arial", 9, QFont.Bold))

            try:
                stock_is_empty = batch_stock is not None and float(batch_stock) <= 0
            except (TypeError, ValueError):
                stock_is_empty = False
            stock_item.setForeground(
                QBrush(QColor("#c0392b" if stock_is_empty else "#2c3e50"))
            )
            self.table.setItem(row, 6, stock_item)

            self.table.setItem(
                row,
                7,
                item(mov.get("Location_Name", "---"), Qt.AlignCenter, "#2980b9"),
            )
            self.table.setItem(
                row,
                8,
                item(mov.get("Operator_Name") or "Système", Qt.AlignCenter, "#7f8c8d"),
            )
            note = f'{mov.get("Reason_Name", "") or ""} {mov.get("Notes", "") or ""}'.strip()
            self.table.setItem(row, 9, item(note, Qt.AlignLeft | Qt.AlignVCenter))

            # Conditional Sales Profit column (Prix Vente - Prix Moyen PMP)
            profit_val = mov.get("Sale_Profit")
            if profit_val is not None:
                try:
                    p_float = float(profit_val)
                    p_color = "#15803D" if p_float > 0 else ("#DC2626" if p_float < 0 else "#64748B")
                    p_item = item(
                        f"{format_money(p_float)} DA",
                        Qt.AlignRight | Qt.AlignVCenter,
                        p_color,
                        QFont("Segoe UI", 9, QFont.Bold),
                    )
                    u_sale = float(mov.get("Unit_Sale_Price") or 0.0)
                    u_avg = float(mov.get("Avg_Purchase_Price") or 0.0)
                    p_item.setToolTip(
                        f"Prix Vente : {format_money(u_sale)} DA\n"
                        f"Prix Moyen d'Achat (PMP) : {format_money(u_avg)} DA\n"
                        f"Quantité : {abs(qty):g}"
                    )
                except (TypeError, ValueError):
                    p_item = item("—", Qt.AlignRight | Qt.AlignVCenter, "#64748B")
            else:
                p_item = item("—", Qt.AlignRight | Qt.AlignVCenter, "#94A3B8")
            self.table.setItem(row, self.PROFIT_COL, p_item)

        self.table.setSortingEnabled(True)

    def apply_filter_local(self):
        """Keep the legacy helper for callers outside this widget."""
        date_from = self.date_from.date().toString("yyyy-MM-dd")
        date_to = self.date_to.date().toString("yyyy-MM-dd")
        text = self.search_input.text().lower().strip()
        filtered = []
        for movement in self.raw_data:
            movement_date = str(movement.get("Transaction_Date", ""))[:10]
            if not (date_from <= movement_date <= date_to):
                continue
            full_text = (
                f'{movement.get("Product_Name", "")} '
                f'{movement.get("Lot_Number", "")} '
                f'{movement.get("Batch_Barcode", "")} '
                f'{movement.get("Product_Barcode", "")} '
                f'{movement.get("Operator_Name", "")}'
            ).lower()
            if text and text not in full_text:
                continue
            filtered.append(movement)

        self.table.setRowCount(0)
        self._append_rows_to_table(filtered)

    def _lookup_serial_badge(self, query: str, show_not_found: bool = True) -> None:
        serial_mgr = getattr(self.manager, "serials", None)
        if not (serial_mgr and hasattr(serial_mgr, "get_serial_details")):
            return
        try:
            res = serial_mgr.get_serial_details(query)
            if isinstance(res, dict) and res:
                st = str(res.get("Status") or "UNKNOWN")
                status_labels = {
                    "IN_STOCK": ("En Stock Magasin", "#16A34A"),
                    "DISPATCHED": ("Sorti / Vendu (Bon de Sortie)", "#007572"),
                    "SOLD": ("Sorti / Vendu", "#007572"),
                    "IN_SAV": ("En Réparation SAV", "#D97706"),
                    "SCRAPPED": ("Irréparable / Rebut (SAV)", "#DC2626"),
                }
                st_lbl, st_col = status_labels.get(st, (st, "#334155"))
                prod = res.get("Product_Name") or "-"
                brand = res.get("Brand_Mark") or ""
                color = res.get("Color_Finish") or ""
                lot = res.get("Lot_Number") or f"Lot #{res.get('Batch_ID', '-')}"
                client = res.get("Original_Client_Name") or "-"
                inv_no = res.get("Original_Invoice_No") or "-"
                self.lbl_serial_audit_result.setText(
                    f"<b>Produit :</b> {brand} {prod} ({color}) | "
                    f"<b>Lot :</b> {lot} | "
                    f"<b>Statut :</b> <span style='color:{st_col}; font-weight:bold;'>{st_lbl}</span> | "
                    f"<b>Client :</b> {client} | <b>Facture :</b> {inv_no}"
                )
                self.serial_audit_banner.setVisible(True)
            elif show_not_found:
                self.lbl_serial_audit_result.setText(
                    f"<span style='color:#64748B;'>Filtre appliqué sur « {query} » (aucun N° de Série exact correspondant).</span>"
                )
                self.serial_audit_banner.setVisible(True)
            else:
                self.lbl_serial_audit_result.setText("")
                self.serial_audit_banner.setVisible(False)
        except Exception as err:
            logging.error(f"Error auditing serial {query}: {err}")

    def verify_serial_number(self):
        """Uses the unified search/scan field to audit a N° de Série or barcode and filter logs."""
        self.search_timer.stop()
        sn = self.search_input.text().strip()
        if not sn:
            self.lbl_serial_audit_result.setText("")
            self.serial_audit_banner.setVisible(False)
            self.reset_and_reload()
            return

        self._lookup_serial_badge(sn, show_not_found=True)
        self.reset_and_reload()

    def show_full_details(self):
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        data = item.data(Qt.UserRole) if item else None
        if data:
            MovementDetailsDialog(data, self).exec()
