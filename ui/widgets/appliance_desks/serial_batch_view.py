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

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
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

logger = logging.getLogger(__name__)


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
        self.setLayoutDirection(Qt.RightToLeft)
        self._build_ui()
        self.refresh_products()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)

        header = QLabel(
            "📦 إدارة المنتجات والدفعات والأرقام التسلسلية (Batches & N° de Série)"
        )
        header.setStyleSheet("font-size: 15px; font-weight: bold; color: #1E3A8A;")
        root_layout.addWidget(header)

        splitter = QSplitter(Qt.Horizontal)

        # Left Panel: Create / Update Appliance Product
        product_group = QGroupBox("1. تعريف منتج كهرومنزلي (بيانات أساسية وقابلة للتوسع)")
        product_form = QFormLayout(product_group)

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
        self.buy_price_spin.setSuffix(" د.ج")
        product_form.addRow("سعر الشراء المرجعي:", self.buy_price_spin)

        self.sell_price_spin = QDoubleSpinBox()
        self.sell_price_spin.setRange(0.0, 100_000_000.0)
        self.sell_price_spin.setDecimals(2)
        self.sell_price_spin.setSuffix(" د.ج")
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

        self.save_product_btn = QPushButton("➕ حفظ / إضافة المنتج")
        self.save_product_btn.setStyleSheet(
            "background-color: #2563EB; color: white; font-weight: bold; padding: 6px;"
        )
        self.save_product_btn.clicked.connect(self._on_create_product)
        product_form.addRow("", self.save_product_btn)

        splitter.addWidget(product_group)

        # Right Panel: Receive Batch with Serials
        batch_group = QGroupBox("2. إدخال دفعة مخزنية جديدة (Batch) مع الأرقام التسلسلية (N° de Série)")
        batch_layout = QVBoxLayout(batch_group)
        batch_form = QFormLayout()

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
        self.batch_cost_spin.setSuffix(" د.ج")
        batch_form.addRow("تكلفة الوحدة في الدفعة:", self.batch_cost_spin)

        self.batch_sell_spin = QDoubleSpinBox()
        self.batch_sell_spin.setRange(0.0, 100_000_000.0)
        self.batch_sell_spin.setDecimals(2)
        self.batch_sell_spin.setSuffix(" د.ج")
        batch_form.addRow("سعر البيع للدفعة:", self.batch_sell_spin)

        batch_layout.addLayout(batch_form)

        serials_lbl = QLabel(
            "الأرقام التسلسلية للقطع المستلمة (N° de Série) - رقم تسلسلي واحد في كل سطر:"
        )
        serials_lbl.setStyleSheet("font-weight: bold;")
        batch_layout.addWidget(serials_lbl)

        self.serials_text = QPlainTextEdit()
        self.serials_text.setPlaceholderText(
            "امسح أو أدخل الأرقام التسلسلية هنا (كل رقم في سطر مستقل)...\n"
            "مثال:\nSN-SAM-9001\nSN-SAM-9002\nSN-SAM-9003"
        )
        batch_layout.addWidget(self.serials_text)

        self.receive_batch_btn = QPushButton("📥 تسجيل الدفعة والأرقام التسلسلية في المخزن")
        self.receive_batch_btn.setStyleSheet(
            "background-color: #059669; color: white; font-weight: bold; padding: 8px;"
        )
        self.receive_batch_btn.clicked.connect(self._on_receive_batch)
        batch_layout.addWidget(self.receive_batch_btn)

        splitter.addWidget(batch_group)
        root_layout.addWidget(splitter)

        # Bottom Table: Overview of Catalog & Theoretical vs Physical Stock
        table_header_layout = QHBoxLayout()
        table_lbl = QLabel("📋 قائمة المنتجات والمخزون النظري مقابل الفعلي:")
        table_lbl.setStyleSheet("font-weight: bold;")
        table_header_layout.addWidget(table_lbl)
        table_header_layout.addStretch()

        self.refresh_btn = QPushButton("🔄 تحديث الجدول")
        self.refresh_btn.clicked.connect(self.refresh_products)
        table_header_layout.addWidget(self.refresh_btn)
        root_layout.addLayout(table_header_layout)

        self.catalog_table = QTableWidget(0, 8)
        self.catalog_table.setHorizontalHeaderLabels(
            [
                "المعرف",
                "العلامة (Mark)",
                "الاسم (Name)",
                "الفئة (Categorie)",
                "اللون (Coloure)",
                "المخزون الفعلي",
                "المحجوز نظرياً",
                "المتاح للبيع النظري",
            ]
        )
        self.catalog_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        root_layout.addWidget(self.catalog_table)

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
