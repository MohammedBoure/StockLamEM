# ui\main_window.py

import os
import logging
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QStackedWidget, QLabel, QPushButton, QFrame, QButtonGroup,
                               QTabWidget, QMessageBox, QApplication, QScrollArea)
from PySide6.QtCore import Qt, QSize, QFile, QTextStream, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup
from PySide6.QtGui import QPixmap, QIcon
import qtawesome as qta
import json
from .icons import get_duotone_icon

from .widgets.master_data.suppliers_tab import SuppliersTab
from .widgets.master_data.products_tab import ProductsTab
from .widgets.dashboard.dashboard_view import DashboardTab
from .widgets.procurement.procurement_tabs import ProcurementTab
from .widgets.inventory.inventory_tabs import InventoryTab
from .widgets.master_data.manufacturers_tab import ManufacturersTab
from .widgets.master_data.locations_tab import LocationsTab
from .widgets.master_data.automates_tab import AutomatesTab
from .widgets.master_data.waste_reasons_tab import WasteReasonsTab
from .widgets.settings.settings_tab import SettingsTab
from .widgets.settings.local_settings import LocalSettingsStore
from .widgets.master_data.product_families_tab import ProductFamiliesTab
from .widgets.master_data.packaging_units_tab import PackagingUnitsTab
from .widgets.users import UserManagementTab
from .widgets.master_data.external_partners_tab import ExternalPartnersTab
from .widgets.history import MovementHistoryTab
from .widgets.appliance_desks import ApplianceWorkflowTab
from .hardware.raw_input_filter import MultiScannerHIDManager, WindowsRawInputFilter
from .navigation_permissions import has_permission as check_permission, has_navigation_permission as check_navigation_permission
from database.auto_backup_worker import AutoBackupWorker
from database import active_user_id
from branding import (
    get_app_name,
    get_logo_path,
    get_organization_name,
    get_resource_path as get_brand_resource_path,
    get_settings_app_name,
    load_stylesheet_content,
)

class MainWindow(QMainWindow):
    def __init__(self, data_manager, current_user, connection_error=None):
        super().__init__()
        self.data_manager = data_manager
        self.current_user = current_user
        self.connection_error = connection_error
        self.local_settings = LocalSettingsStore(current_user)
        if self.data_manager is not None:
            self.data_manager.current_user = current_user
            self.data_manager.local_settings = self.local_settings
            self.data_manager.can_manage_stamps = self.has_permission("act_manage_stamps")
            if hasattr(self.data_manager, "printer") and hasattr(self.data_manager.printer, "set_local_settings"):
                self.data_manager.printer.set_local_settings(self.local_settings)

        if self.current_user:
            # نستخدم get للبحث عن User_ID أو id لتجنب أخطاء المفاتيح
            u_id = self.current_user.get('User_ID') or self.current_user.get('id')
            if u_id:
                active_user_id.set(u_id)
        # ---------------------

        # --- تحسين: تخزين الصفحات التي تم تحميلها فقط ---
        self.loaded_pages = {}

        # --- حالة الشريط الجانبي ---
        self.is_sidebar_expanded = True
        self.sidebar_full_width = 240
        self.sidebar_compact_width = 70
        self.button_texts = {}
        self.button_tooltips = {
            14: "Bureaux Opérationnels (Commandes, Caisse, Sortie)",
            15: "Service Après-Vente (SAV) & Réparations",
            17: "Gestion des Versements",
            18: "Suivi Paiement à la Livraison",
            19: "Trésorerie & Flux Financiers (Solde, Entrées, Sorties, Transferts)",
        }

        full_name = self.current_user.get('Full_Name', 'Utilisateur') if self.current_user else 'Invité'
        self.setWindowTitle(f"{get_app_name()} | {full_name}")

        logo_path = get_logo_path()
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))
        else:
            self.setWindowIcon(qta.icon('fa5s.heartbeat', color='#007572'))
        self.setMinimumSize(QSize(1366, 768))

        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QHBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self._setup_sidebar()

        self.content_area = QStackedWidget()
        self.main_layout.addWidget(self.content_area)

        # تهيئة الـ StackedWidget بعناصر فارغة
        self._init_placeholders()
        self.load_stylesheet()

        self.apply_permissions()

        if connection_error:
            self.switch_page(4)
        else:
            # خريطة الصفحات مرتبطة بصلاحياتها
            mapping = {
                0: "nav_dashboard",
                1: "nav_data",
                16: "nav_clients",
                2: "nav_procurement",
                8: "tab_proc_reclamation",
                3: "nav_inventory",
                7: "nav_history",
                14: "nav_appliance_workflow",
                17: "nav_versement",
                18: "nav_paiement_livraison",
                19: "nav_treasury",
                20: "nav_decharges",
                15: "nav_sav",
                5: "tab_users",
                4: "nav_settings"
            }

            first_permitted_page = None

            # المرور على الصفحات بالترتيب والتحقق من الصلاحية برمجياً
            for page_id in sorted(mapping.keys()):
                perm_key = mapping[page_id]
                if self.has_navigation_permission(perm_key):
                    first_permitted_page = page_id
                    break

            # فتح أول صفحة يملك المستخدم صلاحيتها
            if first_permitted_page is not None:
                self.switch_page(first_permitted_page)
                if self.nav_group.button(first_permitted_page):
                    self.nav_group.button(first_permitted_page).setChecked(True)
            else:
                logging.warning("User has no permitted pages to display.")
        self.auto_backup_thread = None
        if self.data_manager and not self.connection_error:
            self.auto_backup_thread = AutoBackupWorker(self.data_manager)
            self.auto_backup_thread.start()




    def open_product_history(self, search_text):
        """تستقبل طلب البحث من صفحة المخزون وتفتح السجل"""
        # 1. الانتقال لصفحة السجل (رقم 7)
        self.switch_page(7)

        # 2. تحديث الزر الجانبي ليظهر كمحدد
        if self.nav_group.button(7):
            self.nav_group.button(7).setChecked(True)

        # 3. الوصول للكائن الخاص بصفحة السجل
        history_widget = self.loaded_pages.get(7)

        if history_widget:
            # 4. وضع النص في مربع البحث (نفترض أن اسمه search_input)
            if hasattr(history_widget, 'search_input'):
                history_widget.search_input.setText(search_text)

                # 5. تشغيل عملية البحث/الفلترة
                # نحاول استدعاء دوال التحديث المعتادة
                if hasattr(history_widget, 'filter_data'):
                    history_widget.filter_data()
                elif hasattr(history_widget, 'load_data'):
                    history_widget.load_data()
                elif hasattr(history_widget, 'on_search_changed'): # احتمال آخر
                     history_widget.on_search_changed(search_text)

    def load_stylesheet(self):
        try:
            content = load_stylesheet_content("ui/styles.qss")
            if content:
                self.setStyleSheet(content)
                app = QApplication.instance()
                if app:
                    app.setStyleSheet(content)
            else:
                style_path = get_brand_resource_path("ui/styles.qss")
                style_file = QFile(style_path)
                if style_file.open(QFile.ReadOnly | QFile.Text):
                    stream = QTextStream(style_file)
                    content = stream.readAll()
                    self.setStyleSheet(content)
                    app = QApplication.instance()
                    if app:
                        app.setStyleSheet(content)
                    style_file.close()
        except Exception as e:
            logging.error(f"Error loading stylesheet: {e}")

    def update_header_layout(self, compact):
        if self.header_container.layout():
            old_layout = self.header_container.layout()
            old_layout.removeWidget(self.btn_toggle)
            old_layout.removeWidget(self.logo_label)
            old_layout.removeWidget(self.text_container)
            self.btn_toggle.setParent(self.header_container)
            self.logo_label.setParent(self.header_container)
            self.text_container.setParent(self.header_container)
            QWidget().setLayout(old_layout)

        if compact:
            layout = QVBoxLayout(self.header_container)
            layout.setContentsMargins(0, 8, 0, 6)
            layout.setSpacing(6)
            self.header_container.setFixedHeight(84)
            layout.addWidget(self.btn_toggle, alignment=Qt.AlignHCenter)
            layout.addWidget(self.logo_label, alignment=Qt.AlignHCenter)
            self.text_container.hide()
            self.btn_toggle.show()
            self.logo_label.show()
        else:
            layout = QHBoxLayout(self.header_container)
            layout.setContentsMargins(14, 8, 12, 8)
            layout.setSpacing(10)
            self.header_container.setFixedHeight(68)
            layout.addWidget(self.logo_label)
            layout.addWidget(self.text_container)
            layout.addStretch()
            layout.addWidget(self.btn_toggle)
            self.text_container.show()
            self.btn_toggle.show()
            self.logo_label.show()

    def _setup_sidebar(self):
        self.sidebar_container = QFrame()
        self.sidebar_container.setObjectName("sidebar_container")
        self.sidebar_container.setProperty("state", "expanded")
        self.sidebar_container.setFixedWidth(self.sidebar_full_width)

        sidebar_layout = QVBoxLayout(self.sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(6)

        self.header_container = QWidget()
        self.header_container.setObjectName("header_container")
        self.header_container.setFixedHeight(80)

        self.logo_label = QLabel()
        logo_path = get_logo_path()
        if os.path.exists(logo_path):
            self.logo_pixmap = QPixmap(logo_path)
        else:
            self.logo_pixmap = qta.icon('fa5s.heartbeat', color='#007572').pixmap(QSize(64, 64))
        self.logo_label.setPixmap(self.logo_pixmap.scaled(35, 35, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.logo_label.setFixedSize(35, 35)

        self.text_container = QWidget()
        text_layout = QVBoxLayout(self.text_container)
        text_layout.setContentsMargins(0, 2, 0, 2)
        text_layout.setSpacing(0)
        lbl_title = QLabel(get_app_name())
        lbl_title.setStyleSheet("font-family: 'Segoe UI', sans-serif; font-size: 16px; font-weight: 800; color: #2c3e50;")
        lbl_sub = QLabel("gestion de stock")
        lbl_sub.setStyleSheet("font-size: 10px; font-weight: 600; color: #007572; letter-spacing: 1px;")
        text_layout.addWidget(lbl_title)
        text_layout.addWidget(lbl_sub)

        self.btn_toggle = QPushButton()
        self.btn_toggle.setObjectName("btn_sidebar_toggle")
        self.btn_toggle.setIcon(get_duotone_icon("collapse", size=18))
        self.btn_toggle.setIconSize(QSize(18, 18))
        self.btn_toggle.setFixedSize(34, 34)
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_toggle.setToolTip("Réduire la barre latérale")
        self.btn_toggle.clicked.connect(self.toggle_sidebar_compact)

        self.update_header_layout(compact=False)
        sidebar_layout.addWidget(self.header_container)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #f0f2f5; margin: 0px 10px;")
        line.setFixedHeight(1)
        sidebar_layout.addWidget(line)
        sidebar_layout.addSpacing(10)

        self.nav_group = QButtonGroup(self)
        self.nav_group.idClicked.connect(self.switch_page)

        buttons_info = [
            (0, "Tableau de Bord", "dashboard"),
            (1, "Données de Base", "master_data"),
            (16, "Clients", "clients"),
            (2, "Achats && Entrées", "procurement"),
            (3, "Stock && Magasin", "inventory"),
            (8, "Réclamations", "reclamations"),
            (14, "Bureaux", "barcode_scan"),
            (17, "Versement", "kpi_wallet"),
            (18, "Paiement Livraison", "truck_delivery"),
            (19, "Trésorerie", "treasury"),
            (20, "Décharges", "return_arrow"),
            (15, "SAV", "wrench_sav"),
            (7, "Traçabilité", "history"),
            (5, "Utilisateurs", "users"),
            (4, "Paramètres", "settings"),
        ]

        nav_scroll = QScrollArea()
        nav_scroll.setObjectName("sidebar_scroll")
        nav_scroll.setFrameShape(QFrame.NoFrame)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nav_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setStyleSheet("QScrollArea#sidebar_scroll { background: transparent; border: none; }")

        nav_widget = QWidget()
        nav_widget.setObjectName("sidebar_nav_widget")
        nav_widget.setStyleSheet("QWidget#sidebar_nav_widget { background: transparent; border: none; }")
        nav_layout = QVBoxLayout(nav_widget)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(2)

        for btn_id, text, icon_key in buttons_info:
            icon = get_duotone_icon(icon_key, size=64)
            btn = QPushButton(text)
            btn.setIcon(icon)
            btn.setIconSize(QSize(22, 22))
            btn.setCheckable(True)
            btn.setProperty("class", "nav_button")
            btn.setCursor(Qt.PointingHandCursor)
            self.button_texts[btn] = text
            if btn_id in self.button_tooltips:
                btn.setToolTip(self.button_tooltips[btn_id])
            self.nav_group.addButton(btn, btn_id)
            nav_layout.addWidget(btn)

        nav_layout.addStretch()
        nav_scroll.setWidget(nav_widget)
        sidebar_layout.addWidget(nav_scroll, 1)

        self.btn_logout = QPushButton("Déconnexion")
        self.btn_logout.setIcon(get_duotone_icon("logout", size=48))
        self.btn_logout.setIconSize(QSize(22, 22))
        self.btn_logout.setProperty("class", "logout_button")
        self.btn_logout.setCursor(Qt.PointingHandCursor)
        self.btn_logout.clicked.connect(self.logout)
        self.button_texts[self.btn_logout] = "Déconnexion"
        sidebar_layout.addWidget(self.btn_logout)

        self.main_layout.addWidget(self.sidebar_container)

    def toggle_sidebar_compact(self):
        if self.sidebar_container.width() == 0:
            return
        target_width = self.sidebar_compact_width if self.is_sidebar_expanded else self.sidebar_full_width
        self.anim = QPropertyAnimation(self.sidebar_container, b"minimumWidth")
        self.anim.setDuration(250)
        self.anim.setStartValue(self.sidebar_container.width())
        self.anim.setEndValue(target_width)
        self.anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.anim.start()
        self.anim_max = QPropertyAnimation(self.sidebar_container, b"maximumWidth")
        self.anim_max.setDuration(250)
        self.anim_max.setStartValue(self.sidebar_container.width())
        self.anim_max.setEndValue(target_width)
        self.anim_max.start()

        if self.is_sidebar_expanded:
            self.sidebar_container.setProperty("state", "compact")
            self.update_header_layout(compact=True)
            self.btn_toggle.setIcon(get_duotone_icon("expand", size=18))
            self.btn_toggle.setToolTip("Développer la barre latérale")
            for btn in self.nav_group.buttons() + [self.btn_logout]:
                btn.setText("")
                btn_id = self.nav_group.id(btn)
                if btn_id in self.button_tooltips:
                    btn.setToolTip(self.button_tooltips[btn_id])
                else:
                    btn.setToolTip(self.button_texts.get(btn, "").replace("&&", "&"))
        else:
            self.sidebar_container.setProperty("state", "expanded")
            self.update_header_layout(compact=False)
            self.btn_toggle.setIcon(get_duotone_icon("collapse", size=18))
            self.btn_toggle.setToolTip("Réduire la barre latérale")
            for btn in self.nav_group.buttons() + [self.btn_logout]:
                btn.setText(self.button_texts[btn])
                btn_id = self.nav_group.id(btn)
                if btn_id in self.button_tooltips:
                    btn.setToolTip(self.button_tooltips[btn_id])
                else:
                    btn.setToolTip("")

        self.is_sidebar_expanded = not self.is_sidebar_expanded
        self.sidebar_container.style().unpolish(self.sidebar_container)
        self.sidebar_container.style().polish(self.sidebar_container)

    def closeEvent(self, event):
        """تأكيد الخروج وإيقاف المهام الخلفية قبل إغلاق التطبيق."""
        # إظهار رسالة تأكيد باللغة الفرنسية (لتطابق باقي النظام)
        reply = QMessageBox.question(
            self,
            "Confirmation de sortie",
            "Voulez-vous vraiment quitter l'application ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        # إذا وافق المستخدم على الخروج
        if reply == QMessageBox.Yes:
            # إيقاف خيط النسخ الاحتياطي التلقائي إن وجد
            if self.auto_backup_thread and self.auto_backup_thread.isRunning():
                logging.info("Stopping auto-backup thread...")
                self.auto_backup_thread.stop()

            # قبول حدث الإغلاق (يتم إغلاق البرنامج)
            event.accept()
        else:
            # تجاهل حدث الإغلاق (يبقى البرنامج مفتوحاً)
            event.ignore()

    def apply_permissions(self, reload_pages=False):
        """التحكم في ظهور أزرار القائمة الجانبية بناءً على الصلاحيات"""
        if not self.current_user: return

        # ربط المعرف (ID) الخاص بالزر بمفتاح الصلاحية (Permission Key)
        mapping = {
            0: "nav_dashboard",
            1: "nav_data",
            16: "nav_clients",
            2: "nav_procurement",
            8: "tab_proc_reclamation",
            3: "nav_inventory",
            14: "nav_appliance_workflow",
            17: "nav_versement",
            18: "nav_paiement_livraison",
            19: "nav_treasury",
            20: "nav_decharges",
            15: "nav_sav",
            7: "nav_history",  # واجهة السجل المستقلة
            5: "tab_users",
            4: "nav_settings"
        }
        for btn_id, perm in mapping.items():
            btn = self.nav_group.button(btn_id)
            if btn:
                btn.setVisible(self.has_navigation_permission(perm))

        if reload_pages:
            current_idx = self.content_area.currentIndex()
            for pid in list(self.loaded_pages.keys()):
                if pid != current_idx:
                    old_w = self.loaded_pages.pop(pid, None)
                    if old_w is not None:
                        self.content_area.removeWidget(old_w)
                        self.content_area.insertWidget(pid, QWidget())
                        old_w.deleteLater()

    def logout(self):
        """تسجيل الخروج مع طلب التأكيد"""
        ans = QMessageBox.question(
            self,
            "Confirmation",
            "Voulez-vous vraiment vous déconnecter ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if ans == QMessageBox.Yes:
            self.want_logout = True

            from PySide6.QtCore import QSettings
            settings = QSettings(get_organization_name(), get_settings_app_name())

            self.close()

    def _init_placeholders(self):
        for i in range(21):
            self.content_area.addWidget(QWidget())

    def has_permission(self, perm_key):
        return check_permission(self.current_user, perm_key)

    def has_navigation_permission(self, perm_key):
        return check_navigation_permission(self.current_user, perm_key)

    def _load_page(self, page_id):
        """تحميل الواجهات وإضافة التبويبات بناءً على الصلاحيات المخصصة"""
        if page_id in self.loaded_pages:
            return self.loaded_pages[page_id]

        widget = None

        # --- 0. Dashboard ---
        if page_id == 0:
            widget = DashboardTab(self.data_manager)
            widget.tabs.setIconSize(QSize(16, 16))
            if self.has_permission("tab_dash_overview"):
                widget.tabs.addTab(widget.page_overview, get_duotone_icon("dashboard", 16), "Vue d'ensemble")
            if self.has_permission("tab_dash_overview") or self.has_permission("tab_dash_valuation"):
                widget.tabs.addTab(widget.page_monthly_profit, get_duotone_icon("profit_chart", 16), "Bénéfices Mensuels")
            if self.has_permission("tab_dash_reception"):
                widget.tabs.addTab(widget.page_family_reception, get_duotone_icon("receipt_in", 16), "Entrées par Famille")
            if self.has_permission("tab_dash_consumption"):
                widget.tabs.addTab(widget.page_consumption, get_duotone_icon("consumption", 16), "Consommation")
            if self.has_permission("tab_dash_valuation"):
                widget.tabs.addTab(widget.page_valuation, get_duotone_icon("valuation", 16), "Valorisation")
            if self.has_permission("tab_dash_waste"):
                widget.tabs.addTab(widget.page_waste, get_duotone_icon("waste_bin", 16), "Pertes")
            if self.has_permission("tab_dash_alerts"):
                widget.tabs.addTab(widget.page_alerts, get_duotone_icon("alert_warning", 16), "Alertes")

        # --- 1. Master Data (Données de Base) ---
        elif page_id == 1:
            from .widgets.master_data.master_data_tabs import MasterDataTabs
            widget = MasterDataTabs(self.data_manager)
            widget.tabs.setIconSize(QSize(16, 16))

            if self.has_permission("tab_data_products"):
                widget.tabs.addTab(widget.tab_products, get_duotone_icon("box_product", 16), "Produits")
            if hasattr(self.data_manager, 'families') and self.has_permission("tab_data_families"):
                widget.tabs.addTab(widget.tab_families, get_duotone_icon("tag_family", 16), "Familles")
            if hasattr(self.data_manager, 'packaging_units') and self.has_permission("tab_data_units"):
                widget.tabs.addTab(widget.tab_units, get_duotone_icon("package_unit", 16), "Unités (Pkg)")
            if hasattr(self.data_manager, 'suppliers') and self.has_permission("tab_data_suppliers"):
                widget.tabs.addTab(widget.tab_suppliers, get_duotone_icon("supplier", 16), "Fournisseurs")
            if hasattr(self.data_manager, 'manufacturers') and self.has_permission("tab_data_manufacturers"):
                widget.tabs.addTab(widget.tab_manufacturers, get_duotone_icon("brand_badge", 16), "Marque")
            if hasattr(self.data_manager, 'partners') and self.has_permission("tab_data_partners"):
                widget.tabs.addTab(widget.tab_partners, get_duotone_icon("services", 16), "Partenaires")
            if hasattr(self.data_manager, 'automates') and self.has_permission("tab_data_automates"):
                widget.tabs.addTab(widget.tab_automates, get_duotone_icon("cpu_automate", 16), "Automates")
            if hasattr(self.data_manager, 'locations') and self.has_permission("tab_data_locations"):
                widget.tabs.addTab(widget.tab_locations, get_duotone_icon("location_pin", 16), "Emplacements")
            if hasattr(self.data_manager, 'waste_reasons') and self.has_permission("tab_data_waste_reasons"):
                widget.tabs.addTab(widget.tab_waste, get_duotone_icon("waste_bin", 16), "Motifs Rebut")
            if hasattr(self.data_manager, 'pos_terminals') and self.has_permission("tab_data_caisses"):
                widget.tabs.addTab(widget.tab_caisses, get_duotone_icon("pos", 16), "Caisses")
            if hasattr(widget, 'tab_colors') and self.has_permission("tab_data_colors"):
                widget.tabs.addTab(widget.tab_colors, get_duotone_icon("palette_color", 16), "Couleurs")
            if hasattr(widget, 'tab_decharge_types') and (
                self.has_permission("tab_data_decharge_types") or self.has_permission("nav_data")
            ):
                widget.tabs.addTab(widget.tab_decharge_types, get_duotone_icon("return_arrow", 16), "Types de Décharges")

        # --- 2. Procurement (Achats) ---
        elif page_id == 2:
            widget = ProcurementTab(self.data_manager)
            widget.tabs.setIconSize(QSize(16, 16))
            if self.has_permission("tab_proc_po"):
                widget.tabs.addTab(widget.po_tab, get_duotone_icon("order_doc", 16), "Bons de Commandes")
            if self.has_permission("tab_proc_reception"):
                widget.tabs.addTab(widget.history_tab, get_duotone_icon("receipt_in", 16), "Bons de Réceptions")
            if self.has_permission("tab_proc_credit"):
                widget.tabs.addTab(widget.credit_tab, get_duotone_icon("return_arrow", 16), "Avoirs / Retours")
            if self.has_permission("tab_proc_reclamation"):
                widget.tabs.addTab(widget.reclamation_tab, get_duotone_icon("reclamations", 16), "Réclamations")

        # --- 8. Réclamations ---
        elif page_id == 8:
            from .widgets.reclamation.reclamation_tab import ReclamationTab
            widget = ReclamationTab(self.data_manager)
            if hasattr(widget, "load_data"):
                widget.load_data()

        elif page_id == 3:
            widget = InventoryTab(self.data_manager)
            widget.tabs.setIconSize(QSize(16, 16))
            if hasattr(widget, 'batches_tab'):
                widget.batches_tab.request_product_history.connect(self.open_product_history)
            if self.has_permission("tab_inv_list"):
                widget.tabs.addTab(widget.batches_tab, get_duotone_icon("inventory", 16), "1. Stock Actuel")
            if self.has_permission("tab_inv_dispatch"):
                widget.tabs.addTab(widget.dispatch_tab, get_duotone_icon("transfer_arrows", 16), "2. Transfert & Consommation")

        # --- 4. Settings (Paramètres) ---
        elif page_id == 4:
            widget = SettingsTab(self.data_manager)
            widget.tabs.setIconSize(QSize(16, 16))
            if self.connection_error and hasattr(widget, 'set_connection_error'):
                widget.set_connection_error(self.connection_error)
            if self.connection_error:
                widget.tabs.addTab(widget.tab_db, get_duotone_icon("database_icon", 16), "Base de données")
                widget.tabs.setCurrentWidget(widget.tab_db)
            if self.has_permission("tab_config"):
                if hasattr(widget, 'tab_lab_info'):
                    widget.tabs.addTab(widget.tab_lab_info, get_duotone_icon("lab_info", 16), "Informations du Laboratoire")
                elif hasattr(widget, 'tab_general'):
                    widget.tabs.addTab(widget.tab_general, get_duotone_icon("lab_info", 16), "Informations du Laboratoire")
            if (self.has_permission("tab_auto_backup") or self.has_permission("tab_config")) and hasattr(widget, 'tab_auto_backup'):
                widget.tabs.addTab(widget.tab_auto_backup, get_duotone_icon("cloud_backup", 16), "Sauvegarde Automatique")
            if self.has_permission("tab_set_db") and hasattr(widget, 'tab_db'):
                widget.tabs.addTab(widget.tab_db, get_duotone_icon("database_icon", 16), "Base de données")
            if self.has_permission("tab_set_printer"):
                if hasattr(widget, 'tab_printer'):
                    widget.tabs.addTab(widget.tab_printer, get_duotone_icon("print", 16), "Imprimante")
                if hasattr(widget, 'tab_barcode_config'):
                    widget.tabs.addTab(widget.tab_barcode_config, get_duotone_icon("label_tag", 16), "Éditeur Étiquettes")
                if hasattr(widget, 'tab_receipt_config'):
                    widget.tabs.addTab(widget.tab_receipt_config, get_duotone_icon("receipt_thermal", 16), "Facture Thermique")
            if self.has_permission("tab_set_system") and hasattr(widget, 'tab_system'):
                widget.tabs.addTab(widget.tab_system, get_duotone_icon("settings", 16), "Système")
            if self.has_permission("tab_system_logs") and hasattr(widget, 'tab_system_logs'):
                widget.tabs.addTab(widget.tab_system_logs, get_duotone_icon("terminal_logs", 16), "Logs Système")
            if self.has_permission("tab_set_pdf") and hasattr(widget, 'tab_pdf_config'):
                widget.tabs.addTab(widget.tab_pdf_config, get_duotone_icon("pdf_doc", 16), "Configuration PDF")

        # --- 5. Users ---
        elif page_id == 5:
            widget = UserManagementTab(self.data_manager)

        elif page_id == 7:
            from .widgets.history import MovementHistoryTab
            widget = MovementHistoryTab(self.data_manager)
            if hasattr(widget, 'load_data'):
                widget.load_data()

        # --- 14. Multi-Desk Appliance Store Workflow (Bureaux Opérationnels) ---
        elif page_id == 14:
            u_id = (self.current_user.get('User_ID') or self.current_user.get('id') or 1) if self.current_user else 1
            if not hasattr(self, "hid_scanner_manager"):
                self.hid_scanner_manager = MultiScannerHIDManager(self)
                self.raw_input_filter = WindowsRawInputFilter(self.hid_scanner_manager)
                try:
                    self.raw_input_filter.register_raw_input_devices(int(self.winId()))
                    app = QApplication.instance()
                    if app:
                        app.installNativeEventFilter(self.raw_input_filter)
                except Exception as exc:
                    logging.debug(f"RawInput registration skipped: {exc}")
            user_perm_set = set()
            for tab_key in ("tab_desk_order", "tab_desk_caisse", "tab_desk_dispatch"):
                if self.has_permission(tab_key):
                    user_perm_set.add(tab_key)

            widget = ApplianceWorkflowTab(
                db_manager=self.data_manager,
                current_user_id=int(u_id),
                user_permissions=user_perm_set,
                hid_manager=self.hid_scanner_manager,
                parent=self,
                include_sav=False,
            )

        # --- 15. Service Après-Vente (SAV) Dedicated Workspace ---
        elif page_id == 15:
            from .widgets.sav import SAVWorkspaceTab
            widget = SAVWorkspaceTab(
                data_manager=self.data_manager,
                current_user=self.current_user,
                parent=self,
            )

        # --- 16. Clients (Espace Dédié avec Lazy Loading) ---
        elif page_id == 16:
            from .widgets.clients import ClientsTab
            widget = ClientsTab(self.data_manager)

        # --- 17. Versement ---
        elif page_id == 17:
            from .widgets.versement import VersementTab
            widget = VersementTab(self.data_manager, current_user=self.current_user)

        # --- 18. Paiement Livraison ---
        elif page_id == 18:
            from .widgets.paiement_livraison import PaiementLivraisonTab
            widget = PaiementLivraisonTab(self.data_manager, current_user=self.current_user)

        # --- 19. Trésorerie ---
        elif page_id == 19:
            from .widgets.treasury import TreasuryTab
            widget = TreasuryTab(self.data_manager, current_user=self.current_user)

        # --- 20. Décharges ---
        elif page_id == 20:
            from .widgets.decharges import DechargesTab
            widget = DechargesTab(self.data_manager, current_user=self.current_user)

        if widget:
            old_widget = self.content_area.widget(page_id)
            self.content_area.removeWidget(old_widget)
            self.content_area.insertWidget(page_id, widget)
            self.loaded_pages[page_id] = widget
            return widget
        return None

    def switch_page(self, page_id):
        if self.connection_error and page_id != 4:
            QMessageBox.warning(self, "Erreur Connexion", "Veuillez configurer la base de données.")
            self.switch_page(4)
            return

        # خريطة لربط رقم الصفحة بمفتاح الصلاحية المطلوب
        mapping = {
            0: "nav_dashboard",
            1: "nav_data",
            16: "nav_clients",
            2: "nav_procurement",
            8: "tab_proc_reclamation",
            3: "nav_inventory",
            14: "nav_appliance_workflow",
            17: "nav_versement",
            18: "nav_paiement_livraison",
            19: "nav_treasury",
            20: "nav_decharges",
            15: "nav_sav",
            7: "nav_history",
            5: "tab_users",
            4: "nav_settings"
        }

        required_perm = None if self.connection_error and page_id == 4 else mapping.get(page_id)
        # التحقق: إذا كانت الصفحة تتطلب صلاحية والمستخدم لا يملكها، امنع الدخول
        if required_perm and not self.has_navigation_permission(required_perm):
            logging.warning(f"Unauthorized access attempt to page {page_id}")
            return

        already_loaded = page_id in self.loaded_pages
        widget = self._load_page(page_id)
        if already_loaded and page_id == 19 and widget is not None and hasattr(widget, "refresh_data"):
            widget.refresh_data()
        self.content_area.setCurrentIndex(page_id)
