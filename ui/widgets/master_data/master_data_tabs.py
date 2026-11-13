# ui/widgets/master_data/master_data_tabs.py

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTabWidget)

from .products_tab import ProductsTab
from .suppliers_tab import SuppliersTab
from .manufacturers_tab import ManufacturersTab
from .locations_tab import LocationsTab
from .automates_tab import AutomatesTab
from .waste_reasons_tab import WasteReasonsTab
from .product_families_tab import ProductFamiliesTab
from .packaging_units_tab import PackagingUnitsTab
from .external_partners_tab import ExternalPartnersTab 
from .caisses_tab import CaissesTab
from .product_colors_tab import ProductColorsTab
from .product_references_tab import ProductReferencesTab

class MasterDataTabs(QWidget):
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        
        # 1. تهيئة الواجهات فقط
        self.tab_products = ProductsTab(self.data_manager)
        self.tab_families = ProductFamiliesTab(self.data_manager)
        self.tab_units = PackagingUnitsTab(self.data_manager)
        dm = self.data_manager
        self.tab_suppliers = SuppliersTab(getattr(dm, "suppliers", None))
        self.tab_manufacturers = ManufacturersTab(getattr(dm, "manufacturers", None))
        self.tab_locations = LocationsTab(getattr(dm, "locations", None))
        self.tab_automates = AutomatesTab(getattr(dm, "automates", None), getattr(dm, "locations", None))
        self.tab_waste = WasteReasonsTab(getattr(dm, "waste_reasons", None))
        self.tab_partners = ExternalPartnersTab(getattr(dm, "partners", None))
        self.tab_clients = None  # Migré vers un espace de travail dédié dans la barre de navigation
        self.tab_caisses = CaissesTab(self.data_manager)
        self.tab_colors = ProductColorsTab(self.data_manager)
        self.tab_references = ProductReferencesTab(self.data_manager)


        layout.addWidget(self.tabs)
