# -*- coding: utf-8 -*-
"""
ui/widgets/appliance_desks/serial_batch_view.py
===============================================
Product & Batch Serial Registry Desk (إدارة المنتجات والدفعات والأرقام التسلسلية).
Implements Section 1 of the Electrical Appliance Store specification:
- Product attributes: Mark (العلامة التجارية), Name (الاسم), Categorie (الفئة),
  Coloure (اللون), Warranty Months, and Extensible JSON Attributes.
- Batch Entry (إدارة الدفعات): Enter goods in batches with distinct arrival dates,
  purchase costs, selling prices, and individual unique Serial Numbers (N° de Série).
"""

import json
import logging
from decimal import Decimal
from typing import Optional

from PySide6.QtCore import QDate, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from ui.icons import get_duotone_icon

logger = logging.getLogger(__name__)

TABLE_STYLE = """
    QTableWidget {
        background-color: #FFFFFF;
        alternate-background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 6px;
        gridline-color: #F1F5F9;
        color: #1E293B;
        font-size: 9.5pt;
        selection-background-color: #CCFBF1;
        selection-color: #0F172A;
    }
    QTableWidget::item {
        padding: 4px 8px;
        border: none;
    }
    QHeaderView::section {
        background-color: #F8FAFC;
        color: #334155;
        font-weight: bold;
        font-size: 9pt;
        padding: 8px 10px;
        border: none;
        border-bottom: 2px solid #0E7471;
        border-right: 1px solid #E2E8F0;
    }
"""

INPUT_STYLE = """
    QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QDateEdit, QPlainTextEdit {
        background-color: #FFFFFF;
        border: 1px solid #CBD5E1;
        border-radius: 6px;
        padding: 5px 10px;
        font-size: 9.5pt;
        color: #0F172A;
    }
    QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus, QDateEdit:focus, QPlainTextEdit:focus {
        border: 1.5px solid #0E7471;
    }
"""


class SerialBatchRegistryWidget(QWidget):
    """
    UI Widget for registering Appliance Products (Mark, Name, Categorie, Coloure)
    and receiving Inventory Batches with unique Serial Numbers (N° de Série).
    """

    catalog_updated = Signal()

    def __init__(
        self,
        data_manager=None,
        db_manager=None,
        current_user_id: int = 1,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.data_manager = data_manager or db_manager
        self.db_manager = self.data_manager
        self.current_user_id = current_user_id
        self.setStyleSheet(
            """
            QFrame#ProductCard, QFrame#BatchCard, QFrame#CatalogCard {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
            }
            QLabel {
                border: none;
                background: transparent;
                color: #1E293B;
            }
            QCheckBox {
                color: #334155;
                font-weight: 600;
                spacing: 6px;
            }
            """
            + INPUT_STYLE
        )
        self._build_ui()
        self.refresh_products()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(8)

        # Left Panel: Create / Update Appliance Product
        product_group = QFrame()
        product_group.setObjectName("ProductCard")
        pg_layout = QVBoxLayout(product_group)
        pg_layout.setContentsMargins(14, 14, 14, 14)
        pg_layout.setSpacing(10)

        pg_title = QLabel("1. تعريف منتج كهرومنزلي (بيانات أساسية وقابلة للتوسع)")
        pg_title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        pg_title.setStyleSheet("color: #0F172A; padding-bottom: 4px; border-bottom: 2px solid #0E7471;")
        pg_layout.addWidget(pg_title)

        product_form = QFormLayout()
        product_form.setVerticalSpacing(8)
        product_form.setHorizontalSpacing(10)

        self.mark_input = QLineEdit()
        self.mark_input.setPlaceholderText("مثال: Samsung, LG, Condor, Brandt...")
        product_form.addRow("العلامة التجارية (Mark):", self.mark_input)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("مثال: غسالة ملابس 9 كغ EcoBubble")
        product_form.addRow("الاسم (Name):", self.name_input)

        self.category_input = QLineEdit()
        self.category_input.setPlaceholderText("مثال: غسالات، ثلاجات، مكيفات...")
        product_form.addRow("الفئة / التصنيف (Categorie):", self.category_input)

        self.color_input = QLineEdit()
        self.color_input.setPlaceholderText("مثال: Inox, أبيض، أسود، رمادي...")
        product_form.addRow("اللون (Coloure):", self.color_input)

        self.barcode_input = QLineEdit()
        self.barcode_input.setPlaceholderText("باركود الطراز (Model EAN/UPC)")
        product_form.addRow("باركود الطراز (Barcode):", self.barcode_input)

        self.buy_price_spin = QDoubleSpinBox()
        self.buy_price_spin.setRange(0.0, 100_000_000.0)
        self.buy_price_spin.setDecimals(2)
        self.buy_price_spin.setSuffix(" DA")
        product_form.addRow("سعر الشراء المرجعي:", self.buy_price_spin)

        self.sell_price_spin = QDoubleSpinBox()
        self.sell_price_spin.setRange(0.0, 100_000_000.0)
        self.sell_price_spin.setDecimals(2)
        self.sell_price_spin.setSuffix(" DA")
        product_form.addRow("سعر البيع:", self.sell_price_spin)

        self.warranty_spin = QSpinBox()
        self.warranty_spin.setRange(0, 120)
        self.warranty_spin.setValue(24)
        self.warranty_spin.setSuffix(" شهر")
        product_form.addRow("مدة الضمان:", self.warranty_spin)

        self.requires_serial_chk = QCheckBox("يتطلب رقم تسلسلي فريد (N° de Série) عند الإخراج")
        self.requires_serial_chk.setChecked(True)
        product_form.addRow("", self.requires_serial_chk)

        self.ext_attrs_input = QLineEdit()
        self.ext_attrs_input.setPlaceholderText('{"energy": "A+++", "power_w": 2000}')
        product_form.addRow("خصائص إضافية (JSON):", self.ext_attrs_input)

        pg_layout.addLayout(product_form)

        self.save_product_btn = QPushButton("+ حفظ / إضافة المنتج")
        self.save_product_btn.setCursor(Qt.PointingHandCursor)
        self.save_product_btn.setStyleSheet(
            "QPushButton { background-color: #0E7471; color: white; font-weight: bold; padding: 8px 14px; border: none; border-radius: 6px; }"
            "QPushButton:hover { background-color: #0A5E5C; }"
        )
        self.save_product_btn.clicked.connect(self._on_create_product)
        pg_layout.addWidget(self.save_product_btn)

        splitter.addWidget(product_group)

        # Right Panel: Receive Batch with Serials
        batch_group = QFrame()
        batch_group.setObjectName("BatchCard")
        batch_layout = QVBoxLayout(batch_group)
        batch_layout.setContentsMargins(14, 14, 14, 14)
        batch_layout.setSpacing(10)

        bg_title = QLabel("2. إدخال دفعة مخزنية جديدة (Batch) مع الأرقام التسلسلية (N° de Série)")
        bg_title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        bg_title.setStyleSheet("color: #0F172A; padding-bottom: 4px; border-bottom: 2px solid #0E7471;")
        batch_layout.addWidget(bg_title)

        batch_form = QFormLayout()
        batch_form.setVerticalSpacing(8)
        batch_form.setHorizontalSpacing(10)

        self.product_combo = QComboBox()
        batch_form.addRow("المنتج:", self.product_combo)

        self.batch_number_input = QLineEdit()
        self.batch_number_input.setPlaceholderText("مثال: BATCH-2026-11-A")
        batch_form.addRow("رقم الدفعة (Batch No):", self.batch_number_input)

        self.received_date_edit = QDateEdit(QDate.currentDate())
        self.received_date_edit.setCalendarPopup(True)
        self.received_date_edit.setDisplayFormat("yyyy-MM-dd")
        batch_form.addRow("تاريخ استلام الدفعة:", self.received_date_edit)

        self.batch_cost_spin = QDoubleSpinBox()
        self.batch_cost_spin.setRange(0.0, 100_000_000.0)
        self.batch_cost_spin.setDecimals(2)
        self.batch_cost_spin.setSuffix(" DA")
        batch_form.addRow("تكلفة الوحدة في الدفعة:", self.batch_cost_spin)

        self.batch_sell_spin = QDoubleSpinBox()
        self.batch_sell_spin.setRange(0.0, 100_000_000.0)
        self.batch_sell_spin.setDecimals(2)
        self.batch_sell_spin.setSuffix(" DA")
        batch_form.addRow("سعر البيع للدفعة:", self.batch_sell_spin)

        batch_layout.addLayout(batch_form)

        serials_lbl = QLabel(
            "الأرقام التسلسلية للقطع المستلمة (N° de Série) — رقم تسلسلي واحد في كل سطر:"
        )
        serials_lbl.setStyleSheet("font-weight: 600; color: #334155;")
        batch_layout.addWidget(serials_lbl)

        self.serials_text = QPlainTextEdit()
        self.serials_text.setPlaceholderText(
            "امسح أو أدخل الأرقام التسلسلية هنا (كل رقم في سطر مستقل)...\n"
            "مثال:\nSN-SAM-9001\nSN-SAM-9002\nSN-SAM-9003"
        )
        batch_layout.addWidget(self.serials_text)

        self.receive_batch_btn = QPushButton("تسجيل الدفعة والأرقام التسلسلية في المخزن")
        self.receive_batch_btn.setIcon(get_duotone_icon("barcode_scan", "#FFFFFF", "#CCFBF1", size=16))
        self.receive_batch_btn.setCursor(Qt.PointingHandCursor)
        self.receive_batch_btn.setStyleSheet(
            "QPushButton { background-color: #0E7471; color: white; font-weight: bold; padding: 9px 14px; border: none; border-radius: 6px; }"
            "QPushButton:hover { background-color: #0A5E5C; }"
        )
        self.receive_batch_btn.clicked.connect(self._on_receive_batch)
        batch_layout.addWidget(self.receive_batch_btn)

        splitter.addWidget(batch_group)
        root_layout.addWidget(splitter, stretch=3)

        # Bottom Table: Overview of Catalog & Theoretical vs Physical Stock
        cat_card = QFrame()
        cat_card.setObjectName("CatalogCard")
        cat_layout = QVBoxLayout(cat_card)
        cat_layout.setContentsMargins(14, 12, 14, 12)
        cat_layout.setSpacing(8)

        table_header_layout = QHBoxLayout()
        table_lbl = QLabel("قائمة المنتجات والمخزون النظري مقابل الفعلي")
        table_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        table_lbl.setStyleSheet("color: #0F172A;")
        table_header_layout.addWidget(table_lbl)
        table_header_layout.addStretch()

        self.refresh_btn = QPushButton("تحديث الجدول")
        self.refresh_btn.setIcon(get_duotone_icon("refresh", "#0E7471", "#99F6E4", size=14))
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.setStyleSheet(
            "QPushButton { background: #F8FAFC; color: #334155; font-weight: 600; padding: 6px 12px; border: 1px solid #CBD5E1; border-radius: 6px; }"
            "QPushButton:hover { background: #F1F5F9; border-color: #0E7471; color: #0E7471; }"
        )
        self.refresh_btn.clicked.connect(self.refresh_products)
        table_header_layout.addWidget(self.refresh_btn)
        cat_layout.addLayout(table_header_layout)

        self.catalog_table = QTableWidget(0, 8)
        self.catalog_table.setStyleSheet(TABLE_STYLE)
        self.catalog_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Mark (العلامة)",
                "Désignation (الاسم)",
                "Catégorie",
                "Couleur",
                "Stock Physique",
                "Réservé (Théorique)",
                "Disponible Vente",
            ]
        )
        self.catalog_table.verticalHeader().setVisible(False)
        self.catalog_table.verticalHeader().setDefaultSectionSize(34)
        self.catalog_table.setAlternatingRowColors(True)
        self.catalog_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.catalog_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        c_hdr = self.catalog_table.horizontalHeader()
        c_hdr.setFixedHeight(38)
        c_hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        c_hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        c_hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        c_hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        c_hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        c_hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        c_hdr.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        c_hdr.setSectionResizeMode(7, QHeaderView.ResizeToContents)

        cat_layout.addWidget(self.catalog_table)
        root_layout.addWidget(cat_card, stretch=2)

    def refresh_products(self) -> None:
        if not self.data_manager or not hasattr(self.data_manager, "serials"):
            return
        try:
            catalog = self.data_manager.serials.get_catalog_with_theoretical_stock()
        except Exception as exc:
            logger.error("Failed to load appliance catalog: %s", exc)
            catalog = []

        self.product_combo.clear()
        self.catalog_table.setRowCount(0)

        for row_idx, item in enumerate(catalog):
            pid = item.get("Product_ID")
            mark = item.get("Brand_Mark") or "-"
            name = item.get("Product_Name") or ""
            cat = item.get("Category_Name") or "-"
            color = item.get("Color_Finish") or "-"
            phys = float(item.get("Physical_Qty") or item.get("Physical_Stock") or 0)
            res = float(item.get("Reserved_Qty") or item.get("Theoretical_Reserved_Qty") or 0)
            avail = float(item.get("Available_Theoretical_Qty") or max(0.0, phys - res))

            self.product_combo.addItem(f"[{pid}] {mark} - {name} ({color})", pid)

            self.catalog_table.insertRow(row_idx)
            vals = [
                str(pid),
                mark,
                name,
                cat,
                color,
                f"{phys:g}",
                f"{res:g}",
                f"{avail:g}",
            ]
            for col_idx, text in enumerate(vals):
                cell = QTableWidgetItem(text)
                cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                self.catalog_table.setItem(row_idx, col_idx, cell)

    def _on_create_product(self) -> None:
        name = self.name_input.text().strip()
        mark = self.mark_input.text().strip()
        category = self.category_input.text().strip()
        color = self.color_input.text().strip()

        if not name:
            QMessageBox.warning(self, "بيانات ناقصة", "يرجى إدخال اسم المنتج (Name).")
            return

        ext_attrs = {}
        raw_ext = self.ext_attrs_input.text().strip()
        if raw_ext:
            try:
                ext_attrs = json.loads(raw_ext)
            except ValueError:
                QMessageBox.warning(self, "خطأ JSON", "صيغة الخصائص الإضافية JSON غير صالحة.")
                return

        try:
            res = self.data_manager.serials.register_product_with_attributes(
                name=name,
                mark=mark,
                categorie=category,
                coloure=color,
                barcode=self.barcode_input.text().strip() or None,
                selling_price_ht=Decimal(str(self.sell_price_spin.value())),
                warranty_months=self.warranty_spin.value(),
                requires_serial=self.requires_serial_chk.isChecked(),
                extra_attributes=ext_attrs,
            )
            if res.get("success"):
                QMessageBox.information(
                    self,
                    "تم الحفظ",
                    f"تم حفظ المنتج بنجاح (رقم المعرف: {res.get('product_id')}).",
                )
                self.name_input.clear()
                self.barcode_input.clear()
                self.refresh_products()
                self.catalog_updated.emit()
        except Exception as err:
            QMessageBox.critical(self, "خطأ", f"تعذر حفظ المنتج: {err}")

    def _on_receive_batch(self) -> None:
        product_id = self.product_combo.currentData()
        if not product_id:
            QMessageBox.warning(self, "تنبيه", "يرجى اختيار المنتج أولاً.")
            return

        raw_lines = self.serials_text.toPlainText().splitlines()
        serials = [line.strip() for line in raw_lines if line.strip()]
        if not serials:
            QMessageBox.warning(
                self,
                "بيانات ناقصة",
                "يرجى إدخال رقم تسلسلي واحد على الأقل (N° de Série) للدفعة المستلمة.",
            )
            return

        try:
            res = self.data_manager.serials.register_batch_arrival(
                product_id=int(product_id),
                supplier_id=1,
                po_id=None,
                reception_date=self.received_date_edit.date().toString("yyyy-MM-dd"),
                unit_cost_ht=Decimal(str(self.batch_cost_spin.value())),
                freight_customs=Decimal("0.00"),
                serial_numbers=serials,
                user_id=self.current_user_id,
                selling_price_ht=Decimal(str(self.batch_sell_spin.value())) if self.batch_sell_spin.value() > 0 else None,
                batch_number=self.batch_number_input.text().strip() or None,
            )
            if res.get("success"):
                QMessageBox.information(
                    self,
                    "تم إدخال الدفعة",
                    f"تم تسجيل الدفعة ({res.get('batch_number')}) بنجاح بعدد {res.get('serials_count')} قطعة مرقمة.",
                )
                self.serials_text.clear()
                self.batch_number_input.clear()
                self.refresh_products()
                self.catalog_updated.emit()
        except Exception as err:
            QMessageBox.critical(
                self,
                "رفض إدخال الدفعة",
                f"فشل إدخال الدفعة:\n{err}",
            )
