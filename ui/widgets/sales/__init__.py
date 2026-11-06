# ui/widgets/sales/__init__.py
"""
Point of Sale (POS) Module - Retail Sales
"""

from .point_of_sale_tab import PointOfSaleTab
from .return_dialog import ReturnProductSelectionDialog
from .searchable_client_combo import SearchableClientComboBox

__all__ = [
    "PointOfSaleTab",
    "ReturnProductSelectionDialog",
    "SearchableClientComboBox",
]

