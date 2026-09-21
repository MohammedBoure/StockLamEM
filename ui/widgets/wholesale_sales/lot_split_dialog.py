# ui/widgets/wholesale_sales/lot_split_dialog.py

from datetime import datetime, date
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDoubleSpinBox,
    QFrame, QMessageBox, QSizePolicy, QWidget
)
from PySide6.QtCore import Qt, QSize, QEvent
from PySide6.QtGui import QFont, QColor, QKeySequence, QShortcut, QBrush
from ui.formatting import format_money
from ui.icons import get_duotone_icon


class ModalBackdropOverlay(QWidget):
    """
    Overlay opaque / semi-transparent couvrant entièrement la fenêtre parente.
    Résout les problèmes de transparence et de Z-Index/empilement,
    empêchant l'entête du tableau de facture en arrière-plan d'apparaître
    ou de chevaucher la boîte de dialogue modale.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ModalBackdropOverlay")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("""
            QWidget#ModalBackdropOverlay {
                background-color: rgba(15, 23, 42, 0.65);
            }
        """)
        if parent:
            self.setGeometry(parent.rect())
            parent.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj == self.parent() and event.type() == QEvent.Resize:
            self.setGeometry(self.parent().rect())
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        if self.parent():
            self.parent().removeEventFilter(self)
        super().closeEvent(event)


class MultiLotSelectionDialog(QDialog):
    """
    Dialogue modal de répartition et sélection multi-lots (Multi-Lot / Multi-Location Split Selector).
    Permet à l'opérateur de vente en gros d'allouer rapidement les quantités requises
    sur plusieurs lots / dates de péremption / emplacements en une seule opération ergonomique.
    """

    def __init__(
        self,
        parent,
        product_name: str,
        batches: list,
        requested_qty: float = 1.0,
        price_tier: str = 'Prix_1',
        resolve_price_fn=None
    ):
        super().__init__(parent)
        self.product_name = product_name
        self.batches = list(batches or [])
        self.requested_qty = max(0.01, float(requested_qty))
        self.price_tier = price_tier
        self.resolve_price_fn = resolve_price_fn
        self.spinboxes = []
        self.allocations = []
        self._overlay = None

        self.setWindowTitle("📦 Répartition Multi-Lots & Emplacements - Vente Gros")
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self.setModal(True)
        self.setObjectName("MultiLotSelectionDialog")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(True)
        self.setStyleSheet("""
            QDialog#MultiLotSelectionDialog {
                background-color: #F4F6F8;
            }
        """)
        self.resize(900, 530)
        self.setMinimumSize(800, 440)

        self.init_ui()
        self._auto_allocate_fifo()

    def exec(self):
        parent_widget = self.parent()
        if parent_widget:
            target = parent_widget.window() or parent_widget
            self._overlay = ModalBackdropOverlay(target)
            self._overlay.show()
            self._overlay.raise_()
            self.raise_()
            self.activateWindow()

        try:
            return super().exec()
        finally:
            if self._overlay:
                self._overlay.hide()
                self._overlay.deleteLater()
                self._overlay = None

    def exec_(self):
        return self.exec()

    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        # 1. Product Header Card
        header_frame = QFrame()
        header_frame.setObjectName("HeaderFrame")
        header_frame.setStyleSheet("""
            QFrame#HeaderFrame {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 8px;
            }
        """)
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(14, 10, 14, 10)
        h_layout.setSpacing(12)

        v_prod = QVBoxLayout()
        v_prod.setSpacing(3)
        lbl_pname = QLabel(f"Produit : {self.product_name}")
        lbl_pname.setStyleSheet("font-size: 15px; font-weight: 800; color: #0E7471;")
        total_avail = sum(float(b.get('Quantity_Current') or b.get('Current_Stock') or 0.0) for b in self.batches)
        lbl_sub = QLabel(f"Total disponible en stock (tous lots confondus) : {total_avail:g} unités | {len(self.batches)} lot(s) disponible(s)")
        lbl_sub.setStyleSheet("font-size: 11px; color: #64748B; font-weight: 500;")
        v_prod.addWidget(lbl_pname)
        v_prod.addWidget(lbl_sub)
        h_layout.addLayout(v_prod, 1)

        # Target requested quantity box
        lbl_req = QLabel("Quantité demandée :")
        lbl_req.setStyleSheet("font-size: 12px; font-weight: 700; color: #1F2937;")
        h_layout.addWidget(lbl_req)

        self.spin_target_qty = QDoubleSpinBox()
        self.spin_target_qty.setRange(0.01, 999999.0)
        self.spin_target_qty.setValue(self.requested_qty)
        self.spin_target_qty.setDecimals(2)
        self.spin_target_qty.setFixedHeight(38)
        self.spin_target_qty.setMinimumWidth(110)
        self.spin_target_qty.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.spin_target_qty.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 4px;
                font-weight: 700;
                font-size: 13px;
                color: #1F2937;
                padding: 4px 8px;
            }
            QDoubleSpinBox:focus {
                border: 1.5px solid #0E7471;
                background-color: #FFFFFF;
            }
            QDoubleSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 16px;
                border-left: 1px solid #DDE3EA;
                border-bottom: 1px solid #E2E8F0;
                background-color: #F8FAFC;
                border-top-right-radius: 3px;
            }
            QDoubleSpinBox::up-button:hover {
                background-color: #E6F4F1;
            }
            QDoubleSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 16px;
                border-left: 1px solid #DDE3EA;
                background-color: #F8FAFC;
                border-bottom-right-radius: 3px;
            }
            QDoubleSpinBox::down-button:hover {
                background-color: #E6F4F1;
            }
        """)
        self.spin_target_qty.valueChanged.connect(self._on_target_qty_changed)
        h_layout.addWidget(self.spin_target_qty)

        self.btn_fifo = QPushButton("Répartir (FIFO)")
        self.btn_fifo.setIcon(get_duotone_icon("fifo_alloc", 16))
        self.btn_fifo.setIconSize(QSize(16, 16))
        self.btn_fifo.setCursor(Qt.PointingHandCursor)
        self.btn_fifo.setFixedHeight(38)
        self.btn_fifo.setToolTip("Alloue automatiquement la quantité demandée en priorité aux lots les plus anciens (FIFO / Péremption)")
        self.btn_fifo.setStyleSheet("""
            QPushButton {
                background-color: #0E7471;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0A5C59;
            }
            QPushButton:pressed {
                background-color: #084846;
            }
        """)
        self.btn_fifo.clicked.connect(self._auto_allocate_fifo)
        h_layout.addWidget(self.btn_fifo)

        self.btn_reset = QPushButton("Réinitialiser")
        self.btn_reset.setIcon(get_duotone_icon("refresh", 16))
        self.btn_reset.setIconSize(QSize(16, 16))
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setFixedHeight(38)
        self.btn_reset.setToolTip("Réinitialiser toutes les allocations de quantité à zéro")
        self.btn_reset.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #475569;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
                padding: 0 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #F8FAFC;
                border-color: #CBD5E1;
                color: #1E293B;
            }
            QPushButton:pressed {
                background-color: #F1F5F9;
            }
        """)
        self.btn_reset.clicked.connect(self._reset_allocations)
        h_layout.addWidget(self.btn_reset)

        root_layout.addWidget(header_frame)

        # 2. Table of Batches (Spreadsheet-like Dense Data Table)
        self.table = QTableWidget()
        cols = [
            "N° Lot", "Date Péremption", "Emplacement",
            "Stock Disponible", "Prix Unit. HT", "Quantité Allouée"
        ]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setShowGrid(True)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
                gridline-color: #E2E8F0;
                font-size: 12px;
                color: #1F2937;
                selection-background-color: #E6F4F1;
                selection-color: #1F2937;
                alternate-background-color: #F8FAFC;
            }
            QHeaderView::section {
                background-color: #F8FAFC;
                color: #1F2937;
                font-weight: 700;
                font-size: 12px;
                border: none;
                border-bottom: 2px solid #0E7471;
                border-right: 1px solid #E2E8F0;
                padding: 7px 10px;
            }
        """)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 140)

        self.table.horizontalHeaderItem(0).setTextAlignment(Qt.AlignCenter)
        self.table.horizontalHeaderItem(1).setTextAlignment(Qt.AlignCenter)
        self.table.horizontalHeaderItem(2).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeaderItem(3).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.horizontalHeaderItem(4).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.horizontalHeaderItem(5).setTextAlignment(Qt.AlignCenter)

        self._populate_table()
        root_layout.addWidget(self.table, 1)

        # 3. Real-time Summary Cards & Action Bar
        self.summary_frame = QFrame()
        self.summary_frame.setObjectName("SummaryBarFrame")
        self.summary_frame.setStyleSheet("""
            QFrame#SummaryBarFrame {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 8px;
            }
        """)
        s_layout = QHBoxLayout(self.summary_frame)
        s_layout.setContentsMargins(12, 8, 12, 8)
        s_layout.setSpacing(10)

        # Card 1: Quantité Demandée
        card_demand = QFrame()
        card_demand.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
                padding: 4px 12px;
            }
        """)
        lay_demand = QVBoxLayout(card_demand)
        lay_demand.setContentsMargins(0, 0, 0, 0)
        lay_demand.setSpacing(1)
        lbl_d_title = QLabel("QUANTITÉ DEMANDÉE")
        lbl_d_title.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748B; letter-spacing: 0.5px;")
        self.lbl_demand_val = QLabel(f"{self.requested_qty:g}")
        self.lbl_demand_val.setStyleSheet("font-size: 14px; font-weight: 800; color: #1F2937;")
        lay_demand.addWidget(lbl_d_title)
        lay_demand.addWidget(self.lbl_demand_val)
        s_layout.addWidget(card_demand)

        # Card 2: Total Alloué
        self.card_allocated = QFrame()
        self.card_allocated.setStyleSheet("""
            QFrame {
                background-color: #E6F4F1;
                border: 1px solid #BCE3DC;
                border-radius: 6px;
                padding: 4px 12px;
            }
        """)
        lay_alloc = QVBoxLayout(self.card_allocated)
        lay_alloc.setContentsMargins(0, 0, 0, 0)
        lay_alloc.setSpacing(1)
        self.lbl_allocated_title = QLabel("TOTAL ALLOUÉ")
        self.lbl_allocated_title.setStyleSheet("font-size: 10px; font-weight: 700; color: #0E7471; letter-spacing: 0.5px;")
        self.lbl_allocated_val = QLabel("0.00")
        self.lbl_allocated_val.setStyleSheet("font-size: 14px; font-weight: 800; color: #0E7471;")
        lay_alloc.addWidget(self.lbl_allocated_title)
        lay_alloc.addWidget(self.lbl_allocated_val)
        s_layout.addWidget(self.card_allocated)

        # Card 3: Reste à Allouer
        self.card_remaining = QFrame()
        self.card_remaining.setStyleSheet("""
            QFrame {
                background-color: #FEF3C7;
                border: 1px solid #FDE68A;
                border-radius: 6px;
                padding: 4px 12px;
            }
        """)
        lay_rem = QVBoxLayout(self.card_remaining)
        lay_rem.setContentsMargins(0, 0, 0, 0)
        lay_rem.setSpacing(1)
        self.lbl_rem_title = QLabel("RESTE À ALLOUER")
        self.lbl_rem_title.setStyleSheet("font-size: 10px; font-weight: 700; color: #92400E; letter-spacing: 0.5px;")
        self.lbl_remaining_val = QLabel(f"{self.requested_qty:g}")
        self.lbl_remaining_val.setStyleSheet("font-size: 14px; font-weight: 800; color: #B45309;")
        lay_rem.addWidget(self.lbl_rem_title)
        lay_rem.addWidget(self.lbl_remaining_val)
        s_layout.addWidget(self.card_remaining)

        s_layout.addStretch(1)

        # 4. Action Buttons
        self.btn_cancel = QPushButton("Annuler (Échap)")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setFixedHeight(38)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #475569;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
                padding: 0 16px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #F8FAFC;
                border-color: #CBD5E1;
                color: #1E293B;
            }
            QPushButton:pressed {
                background-color: #F1F5F9;
            }
        """)
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_confirm = QPushButton("Valider la Répartition (F10 / Enter)")
        self.btn_confirm.setCursor(Qt.PointingHandCursor)
        self.btn_confirm.setFixedHeight(38)
        self.btn_confirm.setStyleSheet("""
            QPushButton {
                background-color: #16A34A;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 0 20px;
                font-weight: 700;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #15803D;
            }
            QPushButton:pressed {
                background-color: #166534;
            }
        """)
        self.btn_confirm.clicked.connect(self._validate_and_accept)

        s_layout.addWidget(self.btn_cancel)
        s_layout.addWidget(self.btn_confirm)

        root_layout.addWidget(self.summary_frame)

        # Shortcuts
        self.shortcut_enter = QShortcut(QKeySequence(Qt.Key_Return), self)
        self.shortcut_enter.activated.connect(self._validate_and_accept)
        self.shortcut_f10 = QShortcut(QKeySequence("F10"), self)
        self.shortcut_f10.activated.connect(self._validate_and_accept)

    def _populate_table(self):
        self.table.setRowCount(0)
        self.spinboxes = []

        for row, batch in enumerate(self.batches):
            self.table.insertRow(row)

            # 0. Lot Number
            item_lot = QTableWidgetItem(str(batch.get('Lot_Number') or '---'))
            item_lot.setTextAlignment(Qt.AlignCenter)
            item_lot.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
            item_lot.setForeground(QBrush(QColor("#1F2937")))
            self.table.setItem(row, 0, item_lot)

            # 1. Expiry Date (with conditional alert highlight)
            exp_date_str = str(batch.get('Expiry_Date') or '').strip()
            item_exp = QTableWidgetItem(exp_date_str if exp_date_str else '---')
            item_exp.setTextAlignment(Qt.AlignCenter)
            item_exp.setFont(QFont("Segoe UI", 9, QFont.Medium))

            if exp_date_str and exp_date_str != '---':
                try:
                    exp_d = datetime.strptime(exp_date_str[:10], "%Y-%m-%d").date()
                    days_left = (exp_d - date.today()).days
                    if days_left < 0:
                        item_exp.setForeground(QBrush(QColor("#DC2626")))
                        item_exp.setBackground(QBrush(QColor("#FEE2E2")))
                        item_exp.setFont(QFont("Segoe UI", 9, QFont.Bold))
                        item_exp.setToolTip(f"Lot périmé depuis {abs(days_left)} jour(s) !")
                    elif days_left <= 60:
                        item_exp.setForeground(QBrush(QColor("#D97706")))
                        item_exp.setBackground(QBrush(QColor("#FEF3C7")))
                        item_exp.setFont(QFont("Segoe UI", 9, QFont.Bold))
                        item_exp.setToolTip(f"Péremption proche : reste {days_left} jour(s)")
                    else:
                        item_exp.setForeground(QBrush(QColor("#1F2937")))
                except Exception:
                    item_exp.setForeground(QBrush(QColor("#1F2937")))
            else:
                item_exp.setForeground(QBrush(QColor("#64748B")))
            self.table.setItem(row, 1, item_exp)

            # 2. Location
            loc_name = str(batch.get('Location_Name') or 'Entrepôt Principal')
            item_loc = QTableWidgetItem(loc_name)
            item_loc.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item_loc.setForeground(QBrush(QColor("#1F2937")))
            self.table.setItem(row, 2, item_loc)

            # 3. Available stock
            max_stock = float(batch.get('Quantity_Current') or batch.get('Current_Stock') or 0.0)
            item_stock = QTableWidgetItem(f"{max_stock:g}")
            item_stock.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_stock.setFont(QFont("Segoe UI", 9, QFont.Bold))
            if max_stock <= 0:
                item_stock.setForeground(QBrush(QColor("#DC2626")))
                item_stock.setBackground(QBrush(QColor("#FEE2E2")))
            else:
                item_stock.setForeground(QBrush(QColor("#1F2937")))
            self.table.setItem(row, 3, item_stock)

            # 4. Unit price HT
            if callable(self.resolve_price_fn):
                price = self.resolve_price_fn(batch, self.price_tier)
            else:
                price = float(batch.get('Selling_Price_HT') or 0.0)
            item_price = QTableWidgetItem(f"{format_money(price)} DA")
            item_price.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_price.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
            item_price.setForeground(QBrush(QColor("#1F2937")))
            self.table.setItem(row, 4, item_price)

            # 5. Allocated Qty SpinBox (<input type="number"> format)
            cell_container = QWidget()
            cell_container.setStyleSheet("background: transparent;")
            cell_layout = QHBoxLayout(cell_container)
            cell_layout.setContentsMargins(6, 3, 6, 3)
            cell_layout.setAlignment(Qt.AlignCenter)

            spin = QDoubleSpinBox()
            spin.setRange(0.0, max_stock)
            spin.setValue(0.0)
            spin.setDecimals(2)
            spin.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            spin.setMinimumHeight(30)
            spin.setMinimumWidth(90)
            spin.setMaximumWidth(125)
            spin.setStyleSheet("""
                QDoubleSpinBox {
                    background-color: #FFFFFF;
                    border: 1px solid #DDE3EA;
                    border-radius: 4px;
                    font-weight: 700;
                    font-size: 12px;
                    color: #1F2937;
                    padding: 2px 6px;
                }
                QDoubleSpinBox:focus {
                    border: 1.5px solid #0E7471;
                    background-color: #FFFFFF;
                }
                QDoubleSpinBox::up-button {
                    subcontrol-origin: border;
                    subcontrol-position: top right;
                    width: 16px;
                    border-left: 1px solid #DDE3EA;
                    border-bottom: 1px solid #E2E8F0;
                    background-color: #F8FAFC;
                    border-top-right-radius: 3px;
                }
                QDoubleSpinBox::up-button:hover {
                    background-color: #E6F4F1;
                }
                QDoubleSpinBox::down-button {
                    subcontrol-origin: border;
                    subcontrol-position: bottom right;
                    width: 16px;
                    border-left: 1px solid #DDE3EA;
                    background-color: #F8FAFC;
                    border-bottom-right-radius: 3px;
                }
                QDoubleSpinBox::down-button:hover {
                    background-color: #E6F4F1;
                }
            """)
            spin.valueChanged.connect(self._recalculate_summary)
            cell_layout.addWidget(spin)
            self.table.setCellWidget(row, 5, cell_container)
            self.spinboxes.append((batch, spin))

    def _auto_allocate_fifo(self):
        """Alloue automatiquement la quantité demandée selon le FIFO (péremption la plus proche d'abord)."""
        target = self.spin_target_qty.value()
        remaining = target

        # Sort batches by expiry date (None/empty dates put last)
        sorted_indices = sorted(
            range(len(self.batches)),
            key=lambda idx: str(self.batches[idx].get('Expiry_Date') or '9999-12-31')
        )

        for idx in sorted_indices:
            batch, spin = self.spinboxes[idx]
            max_stock = float(batch.get('Quantity_Current') or batch.get('Current_Stock') or 0.0)
            take = min(remaining, max_stock)
            spin.blockSignals(True)
            spin.setValue(take)
            spin.blockSignals(False)
            remaining -= take
            if remaining <= 0:
                remaining = 0

        self._recalculate_summary()

    def _reset_allocations(self):
        for _, spin in self.spinboxes:
            spin.blockSignals(True)
            spin.setValue(0.0)
            spin.blockSignals(False)
        self._recalculate_summary()

    def _on_target_qty_changed(self):
        self.requested_qty = self.spin_target_qty.value()
        self.lbl_demand_val.setText(f"{self.requested_qty:g}")
        self._recalculate_summary()

    def _recalculate_summary(self):
        total_allocated = sum(spin.value() for _, spin in self.spinboxes)
        target = self.spin_target_qty.value()
        remaining = max(0.0, target - total_allocated)

        self.lbl_allocated_val.setText(f"{total_allocated:g}")

        if abs(total_allocated - target) < 0.001:
            self.card_allocated.setStyleSheet("""
                QFrame {
                    background-color: #DCFCE7;
                    border: 1px solid #BBF7D0;
                    border-radius: 6px;
                    padding: 4px 12px;
                }
            """)
            self.lbl_allocated_title.setStyleSheet("font-size: 10px; font-weight: 700; color: #166534; letter-spacing: 0.5px;")
            self.lbl_allocated_val.setStyleSheet("font-size: 14px; font-weight: 800; color: #16A34A;")

            self.card_remaining.setStyleSheet("""
                QFrame {
                    background-color: #DCFCE7;
                    border: 1px solid #BBF7D0;
                    border-radius: 6px;
                    padding: 4px 12px;
                }
            """)
            self.lbl_rem_title.setStyleSheet("font-size: 10px; font-weight: 700; color: #166534; letter-spacing: 0.5px;")
            self.lbl_remaining_val.setText("0 (Complet)")
            self.lbl_remaining_val.setStyleSheet("font-size: 14px; font-weight: 800; color: #16A34A;")

        elif total_allocated < target:
            self.card_allocated.setStyleSheet("""
                QFrame {
                    background-color: #E6F4F1;
                    border: 1px solid #BCE3DC;
                    border-radius: 6px;
                    padding: 4px 12px;
                }
            """)
            self.lbl_allocated_title.setStyleSheet("font-size: 10px; font-weight: 700; color: #0E7471; letter-spacing: 0.5px;")
            self.lbl_allocated_val.setStyleSheet("font-size: 14px; font-weight: 800; color: #0E7471;")

            self.card_remaining.setStyleSheet("""
                QFrame {
                    background-color: #FEF3C7;
                    border: 1px solid #FDE68A;
                    border-radius: 6px;
                    padding: 4px 12px;
                }
            """)
            self.lbl_rem_title.setStyleSheet("font-size: 10px; font-weight: 700; color: #92400E; letter-spacing: 0.5px;")
            self.lbl_remaining_val.setText(f"{remaining:g}")
            self.lbl_remaining_val.setStyleSheet("font-size: 14px; font-weight: 800; color: #B45309;")

        else:
            self.card_allocated.setStyleSheet("""
                QFrame {
                    background-color: #FEE2E2;
                    border: 1px solid #FECACA;
                    border-radius: 6px;
                    padding: 4px 12px;
                }
            """)
            self.lbl_allocated_title.setStyleSheet("font-size: 10px; font-weight: 700; color: #991B1B; letter-spacing: 0.5px;")
            self.lbl_allocated_val.setStyleSheet("font-size: 14px; font-weight: 800; color: #DC2626;")

            excess = total_allocated - target
            self.card_remaining.setStyleSheet("""
                QFrame {
                    background-color: #FEE2E2;
                    border: 1px solid #FECACA;
                    border-radius: 6px;
                    padding: 4px 12px;
                }
            """)
            self.lbl_rem_title.setStyleSheet("font-size: 10px; font-weight: 700; color: #991B1B; letter-spacing: 0.5px;")
            self.lbl_remaining_val.setText(f"+{excess:g} (Excès)")
            self.lbl_remaining_val.setStyleSheet("font-size: 14px; font-weight: 800; color: #DC2626;")

    def _validate_and_accept(self):
        allocs = []
        for batch, spin in self.spinboxes:
            qty = spin.value()
            if qty > 0:
                allocs.append((batch, qty))

        if not allocs:
            QMessageBox.warning(self, "Quantité Nulle", "Veuillez allouer au moins une quantité sur l'un des lots.")
            return

        total_alloc = sum(qty for _, qty in allocs)
        target = self.spin_target_qty.value()
        if total_alloc < target:
            reply = QMessageBox.question(
                self,
                "Allocation Partielle",
                f"La quantité totale allouée ({total_alloc:g}) est inférieure à la quantité demandée ({target:g}).\n"
                f"Souhaitez-vous quand même valider cette allocation partielle ?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        self.allocations = allocs
        self.accept()

    def get_allocations(self):
        """Retourne la liste des tuples (batch_dict, allocated_qty) confirmés."""
        return self.allocations
