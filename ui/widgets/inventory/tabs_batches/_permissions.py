# ui/widgets/inventory/tabs_batches/_permissions.py
"""
إدارة الصلاحيات: إخفاء/إظهار العناصر حسب دور المستخدم
"""

import logging
from ._table import _can_view_financials

def apply_role_permissions(self, role=None):
    """إخفاء البيانات المالية تماماً لمن لا يملك الصلاحية"""

    if role == 'Technician':
        hide_fin = True
    elif role in ('Admin', 'Pharmacist', 'Manager'):
        hide_fin = False
    else:
        # استخدام الدالة الديناميكية للتحقق من صلاحية "tab_inv_financials"
        hide_fin = not _can_view_financials(self)

    self.table.setColumnHidden(3, True)  # Prix U. HT toujours masqué
    for col in (4, 5, 6, 19, 20, 21):
        self.table.setColumnHidden(col, hide_fin)

    if hasattr(self, 'lbl_total_value'):
        if hide_fin:
            self.lbl_total_value.hide()
            self.lbl_total_value.setFixedWidth(0)
        else:
            self.lbl_total_value.show()
            self.lbl_total_value.setFixedWidth(250)

    if hasattr(self, 'btn_sales_price'):
        self.btn_sales_price.setVisible(not hide_fin)

    logging.info(
        f"BatchesTab: Visibility set dynamically based on permissions. "
        f"Financials Hidden: {hide_fin}"
    )
