# ui/widgets/inventory/tabs_batches/_table.py
"""
عرض بيانات الجدول: التحميل الكسول، الفرز، تلوين الصفوف
"""

import logging
import json

from PySide6.QtWidgets import (
    QTableWidgetItem, QApplication, QHeaderView, QStyle, QStyleOptionHeader
)
from PySide6.QtCore import Qt, QRect, QSize, QEvent
from PySide6.QtGui import QColor, QFont, QIcon

from ui.formatting import format_money, format_quantity


# ---------------------------------------------------------------------------
# أيقونات مخصصة
# ---------------------------------------------------------------------------
from ui.icons import get_reclamation_icon


# ---------------------------------------------------------------------------
# رأس عمودي مخصص يضمن محاذاة أرقام الأسطر دون تأثر بأيقونة الشكاوى
# ---------------------------------------------------------------------------

class BatchesVerticalHeader(QHeaderView):
    """
    رأس عمودي مخصص لجدول اللوطات (Batches Table):
    - يضمن بقاء أرقام الأسطر مرتبة تحت بعضها عمودياً بمحاذاة موحدة وثابتة تماماً.
    - يخصص مساحة ثابتة للأيقونة التحذيرية الحمراء (Réclamation) على اليسار دون التأثير
      إطلاقاً على موقع أو محاذاة أرقام الأسطر.
    - يدعم النقر على الأيقونة/الصف لفتح حوار تعديل الشكوى (setSectionsClickable).
    - يغير شكل المؤشر إلى PointingHandCursor عند التمرير فوق صف يحتوي على شكوى.
    """
    def __init__(self, parent=None):
        super().__init__(Qt.Vertical, parent)
        self.setDefaultSectionSize(30)
        self.setSectionResizeMode(QHeaderView.Fixed)
        self.setSectionsClickable(True)
        self.viewport().setMouseTracking(True)

    def sizeHint(self):
        s = super().sizeHint()
        model = self.model()
        rows = model.rowCount() if model else 0
        max_num_str = str(max(rows, 99))
        text_w = self.fontMetrics().horizontalAdvance(max_num_str)
        w = max(46, text_w + 32)
        return QSize(w, s.height())

    def paintSection(self, painter, rect, logicalIndex):
        painter.save()
        # رسم خلفية وحدود قسم الهيدر الافتراضية المناسبة للمظهر العام
        opt = QStyleOptionHeader()
        self.initStyleOption(opt)
        opt.rect = rect
        opt.section = logicalIndex
        opt.text = ''
        opt.icon = QIcon()
        self.style().drawControl(QStyle.CE_Header, opt, painter, self)

        model = self.model()
        if model:
            text = str(model.headerData(logicalIndex, Qt.Vertical, Qt.DisplayRole) or '')
            icon = model.headerData(logicalIndex, Qt.Vertical, Qt.DecorationRole)
        else:
            text = str(logicalIndex + 1)
            icon = None

        # رسم أيقونة الشكوى في موضع مخصص وثابت على اليسار
        icon_sz = 14
        if icon and isinstance(icon, QIcon) and not icon.isNull():
            icon_rect = QRect(
                rect.left() + 4,
                rect.top() + (rect.height() - icon_sz) // 2,
                icon_sz,
                icon_sz
            )
            icon.paint(painter, icon_rect)

        # رسم رقم السطر في مساحة ثابتة ومحاذاة موحدة لجميع الأسطر
        num_rect = QRect(rect.left() + 22, rect.top(), rect.width() - 28, rect.height())
        if opt.state & QStyle.State_Selected:
            painter.setPen(opt.palette.highlightedText().color())
        else:
            painter.setPen(opt.palette.buttonText().color())
        painter.setFont(self.font())
        painter.drawText(num_rect, Qt.AlignCenter, text)

        painter.restore()

    def viewportEvent(self, event):
        if event.type() == QEvent.MouseMove:
            pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
            idx = self.logicalIndexAt(pos)
            m = self.model()
            if m and idx >= 0:
                icon = m.headerData(idx, Qt.Vertical, Qt.DecorationRole)
                if icon and isinstance(icon, QIcon) and not icon.isNull():
                    self.viewport().setCursor(Qt.PointingHandCursor)
                    return super().viewportEvent(event)
            self.viewport().setCursor(Qt.ArrowCursor)
        elif event.type() == QEvent.Leave:
            self.viewport().setCursor(Qt.ArrowCursor)
        return super().viewportEvent(event)


# ---------------------------------------------------------------------------
# مساعد بناء خلية والتحقق من الصلاحيات
# ---------------------------------------------------------------------------

def _make_item(val, align=Qt.AlignCenter, color=None, font=None, bg_color=None):
    from PySide6.QtGui import QBrush
    s_val = str(val) if val is not None else ""
    it = QTableWidgetItem(s_val)
    it.setTextAlignment(align)
    if color:
        it.setForeground(color)
    if bg_color:
        it.setBackground(QBrush(bg_color))
    if font:
        it.setFont(font)
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    return it


def _can_view_financials(widget):
    """دالة تتحقق مما إذا كان المستخدم يملك صلاحية رؤية القيم المالية بشكل آمن"""
    try:
        # 1. محاولة جلب المستخدم من النافذة الرئيسية مباشرة
        main_window = widget.window()
        user = getattr(main_window, 'current_user', None)

        # 2. إذا لم يعثر عليه (الواجهة قيد البناء ولم تدمج بعد بالنافذة)
        # نقوم بالبحث صعوداً في شجرة المكونات الآباء
        if user is None:
            parent = widget.parent()
            while parent:
                if hasattr(parent, 'current_user'):
                    user = parent.current_user
                    break
                parent = parent.parent()

        # 3. إذا لم نعثر على المستخدم في أي مكان
        if not user:
            return False

        perms = user.get('Permissions', {})

        # معالجة الصلاحيات
        if isinstance(perms, str):
            try:
                perms = json.loads(perms)
            except json.JSONDecodeError:
                perms = {}

        if isinstance(perms, list):
            return "tab_inv_financials" in perms
        elif isinstance(perms, dict):
            return perms.get("tab_inv_financials", False)

        return False
    except Exception as e:
        logging.error(f"Error checking financial permissions: {e}")
        return False


# ---------------------------------------------------------------------------
# التحميل الكسول (Lazy Loading / Infinite Scroll)
# ---------------------------------------------------------------------------

def on_scroll_value_changed(self, value):
    """تحميل المزيد عند الاقتراب من قاع الجدول"""
    bar = self.table.verticalScrollBar()
    if value >= bar.maximum() - 20:
        load_more_data(self)


def load_more_data(self):
    """إضافة الدفعة التالية من الصفوف للجدول"""
    total = len(self.filtered_data)
    if self.loaded_count >= total:
        return

    start = self.loaded_count
    end   = min(start + self.batch_size, total)
    _append_rows(self, self.filtered_data[start:end])
    self.loaded_count = end
    self.lbl_count_info.setText(f"Affichage: {self.loaded_count} / {total}")


def _append_rows(self, chunk):
    """إضافة chunk من الصفوف إلى نهاية الجدول"""
    hide_fin = not _can_view_financials(self)
    start_row = self.table.rowCount()

    for i, b in enumerate(chunk):
        r = start_row + i
        self.table.insertRow(r)
        _fill_row(self.table, r, b, hide_fin)

    for col in (3, 4, 5, 6, 19, 20, 21):
        self.table.setColumnHidden(col, hide_fin)


# ---------------------------------------------------------------------------
# عرض صفحة كاملة (مع حساب المجموع)
# ---------------------------------------------------------------------------

def populate_table(self, data):
    """عرض شريحة محددة مع حساب المجموع الكلي من filtered_data"""
    self.table.setSortingEnabled(False)
    self.table.setRowCount(0)

    hide_fin = not _can_view_financials(self)

    # حساب المجموع من كامل القائمة المفلترة
    total_value = 0.0
    if not hide_fin:
        for b in self.filtered_data:
            try:
                qty = float(b.get('Quantity_Current', 0))
                if qty > 0:
                    p = float(b.get('Unit_Price_Received', 0))
                    d = float(b.get('Discount_Percent', 0)) / 100.0
                    t = float(b.get('Tax_Rate_Percent', 0)) / 100.0
                    total_value += qty * p * (1 - d) * (1 + t)
            except Exception:
                pass

    for r, b in enumerate(data):
        self.table.insertRow(r)
        _fill_row(self.table, r, b, hide_fin)

    self.table.setSortingEnabled(False)
    for col in (3, 4, 5, 6, 19, 20, 21):
        self.table.setColumnHidden(col, hide_fin)

    if hide_fin:
        self.lbl_total_value.hide()
    else:
        self.lbl_total_value.show()
        self.lbl_total_value.setText(f"💰 Total Filtré : {format_money(total_value, 'DA')}")


def _fill_row(table, r, b, hide_fin):
    """ملء صف واحد بالبيانات مع الأولوية للأسعار الرئيسية بعد المنتج والكمية، وتأخير أسعار 2 و 3 و 4 قبل الشكاوى"""
    qty = float(b.get('Quantity_Current', 0))
    raw_note = b.get('Reception_Note')
    reclamation = str(raw_note).strip() if raw_note is not None else ""
    if reclamation.lower() in ("none", "null"):
        reclamation = ""

    bg_color = QColor("#ffe4cd") if reclamation else None

    prod_name = b.get('Product_Name', '---')

    # 0. Désignation Produit
    prod_item = _make_item(
        prod_name,
        Qt.AlignLeft | Qt.AlignVCenter,
        bg_color=bg_color
    )
    prod_item.setData(Qt.UserRole, b)
    table.setItem(r, 0, prod_item)

    # 1. Stock (Actuel)
    stock_unit = b.get('Stock_Unit') or ''
    stock_text = format_quantity(qty)
    stock_item = _make_item(
        stock_text,
        color=QColor("#27ae60"),
        font=QFont("", -1, QFont.Bold),
        bg_color=bg_color
    )
    if stock_unit:
        stock_item.setToolTip(f"{stock_text} {stock_unit}")
    table.setItem(r, 1, stock_item)

    # 2. Unité (Unité de Stock du Produit)
    unit_str = b.get('Stock_Unit') or '---'
    unit_item = _make_item(unit_str, align=Qt.AlignCenter, bg_color=bg_color)
    unit_item.setForeground(QColor("#007572"))
    unit_item.setFont(QFont("", -1, QFont.Bold))
    usage_u = b.get('Usage_Unit')
    order_u = b.get('Ordering_Unit')
    tip_parts = [f"Unité de stock : {unit_str}"]
    if usage_u and usage_u != unit_str:
        tip_parts.append(f"Unité d'usage : {usage_u}")
    if order_u and order_u != unit_str:
        tip_parts.append(f"Unité de commande : {order_u}")
    unit_item.setToolTip("\n".join(tip_parts))
    table.setItem(r, 2, unit_item)

    # تطبيق الفلتر المالي على الأسعار الرئيسية ذات الأولوية الأولى (3 إلى 6)
    if not hide_fin:
        p  = float(b.get('Unit_Price_Received', 0) or 0)
        d  = float(b.get('Discount_Percent', 0) or 0) / 100.0
        t  = float(b.get('Tax_Rate_Percent', 0) or 0) / 100.0
        p_ttc = p * (1 - d) * (1 + t)
        lv = qty * p_ttc
        sv1 = float(b.get('Selling_Price_HT') or 0)

        # 3. Prix U. HT
        table.setItem(r, 3, _make_item(format_money(p), bg_color=bg_color))
        # 4. Prix U. TTC
        table.setItem(r, 4, _make_item(format_money(p_ttc), bg_color=bg_color))
        # 5. Valeur (DA)
        table.setItem(r, 5, _make_item(format_money(lv), bg_color=bg_color))
        # 6. Prix Vente 1
        table.setItem(r, 6, _make_item(format_money(sv1), bg_color=bg_color))
    else:
        for col in range(3, 7):
            table.setItem(r, col, _make_item('', bg_color=bg_color))

    # 7. N° Lot
    table.setItem(r, 7,  _make_item(b.get('Lot_Number', '---'), bg_color=bg_color))
    # 8. Date Exp.
    table.setItem(r, 8,  _make_item(str(b.get('Expiry_Date', ''))[:10], bg_color=bg_color))
    # 9. Qté Init.
    table.setItem(r, 9,  _make_item(format_quantity(b.get('Quantity_Initial', 0)), bg_color=bg_color))
    # 10. Code-Barres
    table.setItem(r, 10,  _make_item(
        b.get('Internal_Barcode') or b.get('Barcode'),
        bg_color=bg_color
    ))
    # 11. Code Ext
    table.setItem(r, 11, _make_item(b.get('External_Barcode') or '---', bg_color=bg_color))
    # 12. Emplacement
    table.setItem(r, 12, _make_item(b.get('Location_Name', '---'), bg_color=bg_color))

    # 13. Famille
    table.setItem(r, 13, _make_item(b.get('Family_Name', '---'), bg_color=bg_color))
    # 14. Marque
    table.setItem(r, 14, _make_item(b.get('Manuf_Name', '---'), bg_color=bg_color))
    # 15. Automate
    table.setItem(r, 15, _make_item(b.get('Automate_Name', '---'), bg_color=bg_color))
    # 16. Fournisseur
    table.setItem(r, 16, _make_item(b.get('Supplier_Name', '---'), bg_color=bg_color))
    # 17. Ref PO
    table.setItem(r, 17, _make_item(str(b.get('PO_ID') or '---'), bg_color=bg_color))
    # 18. Date Entrée
    table.setItem(r, 18, _make_item(
        str(b.get('Date_Received') or b.get('Created_At', ''))[:10],
        bg_color=bg_color
    ))

    # 19-21. Prix Vente 2, 3, 4 (في نهاية الجدول قبل الشكاوى)
    if not hide_fin:
        sv2 = float(b.get('Selling_Price_HT_2') or 0)
        sv3 = float(b.get('Selling_Price_HT_3') or 0)
        sv4 = float(b.get('Selling_Price_HT_4') or 0)
        table.setItem(r, 19, _make_item(format_money(sv2), bg_color=bg_color))
        table.setItem(r, 20, _make_item(format_money(sv3), bg_color=bg_color))
        table.setItem(r, 21, _make_item(format_money(sv4), bg_color=bg_color))
    else:
        for col in (19, 20, 21):
            table.setItem(r, col, _make_item('', bg_color=bg_color))

    # 22. Réclamation
    rec_item = _make_item(reclamation, bg_color=bg_color)
    if reclamation:
        rec_item.setIcon(get_reclamation_icon())
    table.setItem(r, 22, rec_item)

    # 23. Groupe Vente (Priorité Caisse)
    pos_grp = b.get('POS_Priority_Group')
    grp_str = f"⭐ {pos_grp}" if pos_grp else "---"
    grp_item = _make_item(grp_str, align=Qt.AlignCenter, bg_color=bg_color)
    if pos_grp:
        grp_item.setForeground(QColor("#007572"))
        grp_item.setFont(QFont("", -1, QFont.Bold))
    table.setItem(r, 23, grp_item)

    # 24. Réf (Référence Produit / Lot)
    ref_display = (
        b.get('Ref_Code')
        or b.get('Primary_Ref')
        or b.get('Manuf_Cat_No')
        or b.get('Barcode')
        or '---'
    )
    ref_item = _make_item(str(ref_display), align=Qt.AlignCenter, bg_color=bg_color)
    all_refs = b.get('All_Refs')
    if all_refs:
        ref_item.setToolTip(f"Références : {all_refs}")
    table.setItem(r, 24, ref_item)

    # تعيين الهيدر العمودي (رقم الصف وأيقونة الشكوى إذا وجدت)
    v_header_item = QTableWidgetItem(str(r + 1))
    v_header_item.setTextAlignment(Qt.AlignCenter)
    if reclamation:
        v_header_item.setIcon(get_reclamation_icon())
        v_header_item.setToolTip(f"Réclamation: {reclamation}")
    table.setVerticalHeaderItem(r, v_header_item)


# ---------------------------------------------------------------------------
# الفرز
# ---------------------------------------------------------------------------

COL_MAP = {
    0: 'Product_Name',          1: 'Quantity_Current',
    2: 'Stock_Unit',            3: 'Unit_Price_Received',
    4: 'Unit_Price_Received_TTC', 5: 'Total_Value',
    6: 'Selling_Price_HT',      7: 'Lot_Number',
    8: 'Expiry_Date',           9: 'Quantity_Initial',
    10: 'Internal_Barcode',     11: 'External_Barcode',
    12: 'Location_Name',        13: 'Family_Name',
    14: 'Manuf_Name',           15: 'Automate_Name',
    16: 'Supplier_Name',        17: 'PO_ID',
    18: 'Date_Received',        19: 'Selling_Price_HT_2',
    20: 'Selling_Price_HT_3',   21: 'Selling_Price_HT_4',
    22: 'Reception_Note',       23: 'POS_Priority_Group'
}

NUMERIC_COLS = {1, 3, 4, 5, 6, 9, 19, 20, 21}
DATE_COLS    = {8, 18}


def _sort_key(col_index, item):
    if col_index == 5:
        try:
            qty = float(item.get('Quantity_Current', 0))
            p  = float(item.get('Unit_Price_Received', 0))
            d  = float(item.get('Discount_Percent', 0)) / 100.0
            t  = float(item.get('Tax_Rate_Percent', 0)) / 100.0
            return qty * p * (1 - d) * (1 + t)
        except Exception:
            return 0.0
    elif col_index == 4:
        try:
            p  = float(item.get('Unit_Price_Received', 0))
            d  = float(item.get('Discount_Percent', 0)) / 100.0
            t  = float(item.get('Tax_Rate_Percent', 0)) / 100.0
            return p * (1 - d) * (1 + t)
        except Exception:
            return 0.0
    elif col_index in NUMERIC_COLS:
        try:
            return float(item.get(COL_MAP.get(col_index), 0) or 0)
        except Exception:
            return 0.0

    key_name = COL_MAP.get(col_index)
    val = item.get(key_name)

    if val is None:
        return -1 if col_index in NUMERIC_COLS else ""

    if col_index in NUMERIC_COLS:
        try:
            return float(val)
        except Exception:
            return 0.0
    elif col_index in DATE_COLS:
        return str(val)[:10]
    else:
        return str(val).lower()


def on_header_clicked(self, col_index):
    """عكس الاتجاه أو تعيين عمود جديد ثم تطبيق الفرز"""
    if self.current_sort_col == col_index:
        self.current_sort_asc = not self.current_sort_asc
    else:
        self.current_sort_col = col_index
        self.current_sort_asc = True
    apply_sorting(self)


def apply_sorting(self):
    """فرز filtered_data كاملاً ثم إعادة العرض من الصفر"""
    if self.current_sort_col == -1:
        return

    QApplication.setOverrideCursor(Qt.WaitCursor)
    QApplication.processEvents()

    try:
        col = self.current_sort_col
        asc = self.current_sort_asc

        header = self.table.horizontalHeader()
        header.setSortIndicatorShown(True)
        header.setSortIndicator(
            col,
            Qt.AscendingOrder if asc else Qt.DescendingOrder
        )

        key_name = COL_MAP.get(col)
        if not key_name and col not in (4, 5):
            return

        self.filtered_data.sort(
            key=lambda item: _sort_key(col, item),
            reverse=not asc
        )

        # إعادة العرض من الصفر (lazy loading)
        self.table.setRowCount(0)
        self.loaded_count = 0
        load_more_data(self)

    except Exception as e:
        logging.error(f"Sorting Error: {e}")
    finally:
        QApplication.restoreOverrideCursor()
