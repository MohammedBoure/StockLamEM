# ui/widgets/settings/user_management_tab.py

import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
    QTableWidgetItem, QPushButton, QHeaderView, QMessageBox, 
    QAbstractItemView, QFormLayout, QLineEdit, QComboBox,
    QTreeWidget, QTreeWidgetItem
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QBrush
import qtawesome as qta
from ui.widgets.master_data.dialogs import BaseDialog 

SYSTEM_PERMISSIONS = {
    "1. TABLEAU_DE_BORD": {
        "label": "📊 Tableau de Bord",
        "icon": "fa5s.chart-pie",
        "perms": {
            "nav_dashboard": "Accès au Tableau de bord",
            "tab_dash_overview": "Vue d'ensemble",
            "tab_dash_reception": "Entrées par Famille",
            "tab_dash_consumption": "Consommation",
            "tab_dash_valuation": "Valorisation",
            "tab_dash_waste": "Pertes",
            "tab_dash_alerts": "Alertes"
        }
    },
    "2. DONNEES_DE_BASE": {
        "label": "📚 Données de Base",
        "icon": "fa5s.layer-group",
        "perms": {
            "nav_data": "Accès aux Données de base",
            "tab_data_products": "Produits",
            "tab_data_families": "Familles",
            "tab_data_units": "Unités (Pkg)",
            "tab_data_suppliers": "Fournisseurs",
            "tab_data_manufacturers": "Fabricants",
            "tab_data_partners": "Partenaires Externes",
            "tab_data_automates": "Automates",
            "tab_data_locations": "Emplacements",
            "tab_data_waste_reasons": "Motifs Rebut",
            "tab_clients": "Clients",
            "tab_data_caisses": "Caisses & Terminaux POS",
            "tab_data_colors": "Couleurs des Produits"
        }
    },
    "3. ACHATS": {
        "label": "🛒 Achats & Entrées",
        "icon": "fa5s.shopping-cart",
        "perms": {
            "nav_procurement": "Accès aux Achats",
            "tab_proc_po": "Bons de Commandes",
            "tab_proc_reception": "Bons de Réceptions",
            "tab_proc_credit": "Avoirs / Retours"
        }
    },
    "3a. RECLAMATIONS": {
        "label": "Réclamations & Anomalies",
        "icon": "fa5s.exclamation-circle",
        "perms": {
            "tab_proc_reclamation": "Réclamations"
        }
    },
    "4. STOCK": {
        "label": "📦 Stock & Magasin",
        "icon": "fa5s.boxes",
        "perms": {
            "nav_inventory": "Accès au Stock",
            "tab_inv_list": "Stock Actuel",
            "tab_inv_dispatch": "Transfert & Consommation",
            "tab_inv_financials": "Voir les valeurs financières (Prix/Total)" 
        }
    },
    "4a. INVENTAIRE": {
        "label": "Inventaire",
        "icon": "fa5s.clipboard-list",
        "perms": {
            "nav_inventaire": "Acces a l'inventaire",
            "act_inventory_create": "Creer une session",
            "act_inventory_scan": "Scanner les articles",
            "act_inventory_apply": "Appliquer les ecarts",
            "act_inventory_cancel": "Annuler une session",
            "act_inventory_export": "Exporter vers Excel"
        }
    },
    "5. POINT_DE_VENTE": {
        "label": "🛒 Point de Vente (POS / Caisse)",
        "icon": "fa5s.cash-register",
        "perms": {
            "nav_pos": "Accès Point de Vente (Caisse POS)",
            "nav_sales": "Accès Global Ventes (Compatibilité)",
            "act_create_sale": "Créer une vente en caisse",
            "act_validate_sale": "Valider un ticket / encaissement POS",
            "act_sale_without_client": "Vente comptoir sans client",
            "act_pos_open_session": "Ouvrir une session de caisse",
            "act_pos_close_session": "Clôturer une session de caisse",
            "act_edit_closed_cash_session": "Modifier une session clôturée",
            "act_pos_reopen_session": "Réouvrir une session de caisse",
            "act_pos_cash_movement": "Mouvements de fond (Cash In / Out)",
            "act_pos_multi_payment": "Autoriser les paiements multiples",
            "act_pos_credit_sale": "Autoriser la vente à crédit au POS",
            "act_pos_hold_sale": "Mettre en attente / suspendre un panier",
            "act_pos_resume_sale": "Reprendre un panier en attente",
            "act_pos_quote": "Créer un devis de caisse",
            "act_pos_discount": "Appliquer une remise en caisse",
            "act_pos_price_override": "Modifier le prix de vente en direct",
            "act_pos_return": "Effectuer un retour d'article POS",
            "act_pos_return_without_invoice": "Retour sans facture (Manager)",
            "act_pos_refund": "Autoriser un remboursement",
            "act_pos_exchange": "Autoriser un échange d'article",
            "act_pos_manage_promotions": "Gérer les promotions",
            "act_pos_manage_loyalty": "Gérer le programme fidélité"
        }
    },
    "5a. VENTE_EN_GROS": {
        "label": "🏢 Vente en Gros B2B",
        "icon": "fa5s.truck-loading",
        "perms": {
            "nav_wholesale": "Accès Vente en Gros B2B",
            "tab_wholesale_sales": "Interface commandes & facturation de gros",
            "act_wholesale_create": "Créer un document de gros (Devis, BC, BL, Facture)",
            "act_wholesale_validate": "Valider un document de gros avec déduction stock",
            "act_wholesale_credit_override": "Autoriser le dépassement du plafond de crédit",
            "act_wholesale_pdf_export": "Exporter les factures & BL en PDF A4"
        }
    },
    "5b. HISTORIQUE_VENTES": {
        "label": "📊 Historique & Facturation Ventes",
        "icon": "fa5s.file-invoice-dollar",
        "perms": {
            "nav_sales_history": "Accès Historique des Ventes & Factures",
            "tab_sales_invoices": "Consulter les factures de vente",
            "tab_sales_returns": "Consulter l'historique des retours & avoirs",
            "tab_sales_payments": "Consulter les paiements et encaissements",
            "act_cancel_sale": "Annuler une facture validée",
            "act_edit_sale": "Modifier les lignes d'une facture existante",
            "act_pos_view_profit": "Consulter la marge et le bénéfice (Profit / Fayda)",
            "act_pos_reprint_invoice": "Réimprimer une facture de vente",
            "act_pos_audit": "Consulter la piste d'audit des ventes"
        }
    },
    "5c. CREANCES_CLIENTS": {
        "label": "💳 Gestion des Créances & Dettes Clients",
        "icon": "fa5s.hand-holding-usd",
        "perms": {
            "nav_debts": "Accès Gestion des Créances Clients",
            "debts_management:view": "Consulter les dettes et créances clients",
            "debts_management:settle": "Encaisser et solder les créances clients"
        }
    },
    "6. SOUS_TRAITANTS": {
        "label": "🧾 Sous-Traitants",
        "icon": "fa5s.file-invoice-dollar",
        "perms": {
            "nav_services": "Accès Facturation / Sous-traitants",
            "nav_market": "Accès Marché (Devises / Devis)"
        }
    },
    "7. TRACABILITE": {
        "label": "📜 Traçabilité",
        "icon": "fa5s.history",
        "perms": {
            "nav_history": "Accès Traçabilité Globale",
            "tab_inv_history": "Historique des mouvements de stock",
            "tab_serial_registry": "Référentiel Lots, Produits & N° de Série",
            "act_serial_audit": "Audit instantané d'un N° de Série"
        }
    },
    "8. UTILISATEURS": {
        "label": "👥 Utilisateurs",
        "icon": "fa5s.users",
        "perms": {
            "tab_users": "Gestion des Utilisateurs"
        }
    },
    "9. PARAMETRES": {
        "label": "🔧 Paramètres",
        "icon": "fa5s.sliders-h",
        "perms": {
            "nav_settings": "Accès aux Paramètres",
            "tab_config": "Informations du Laboratoire",
            "tab_auto_backup": "Sauvegarde Automatique",
            "tab_set_db": "Base de données",
            "tab_set_printer": "Imprimante",
            "tab_set_system": "Système",
            "tab_system_logs": "Logs Système",
            "tab_set_pdf": "Configuration PDF",
            "act_manage_stamps": "Ajouter et supprimer les cachets locaux"
        }
    },
    "10. BUREAUX_WORKFLOW": {
        "label": "🏢 Bureaux & Workflow Magasin",
        "icon": "fa5s.cash-register",
        "perms": {
            "nav_appliance_workflow": "Accès au Workflow Multi-Bureaux",
            "tab_desk_order": "Bureau des Commandes (Order Desk)",
            "tab_desk_caisse": "Bureau Caisse (Encaissement & Règlements)",
            "tab_desk_dispatch": "Bureau Sortie Magasin (Dispatch)",
            "act_order_create": "Émettre des commandes (Comptant, Crédit, BL)",
            "act_caisse_settle": "Valider et encaisser les commandes en caisse",
            "act_caisse_bon_credit_auth": "Autoriser les bons à crédit (Superviseur)",
            "act_caisse_versement": "Enregistrer des versements clients",
            "act_caisse_bon_retour": "Émettre des bons de retour (Avoir virtuel)",
            "act_dispatch_validate": "Valider la sortie physique et scanner les N° de série"
        }
    },
    "11. SAV_WORKSPACE": {
        "label": "🔧 Service Après-Vente (SAV)",
        "icon": "fa5s.wrench",
        "perms": {
            "nav_sav": "Accès à l'Espace SAV & Réparations",
            "tab_desk_sav": "Consulter les demandes et tickets SAV",
            "act_sav_ticket_create": "Réceptionner un appareil et créer un ticket SAV",
            "act_sav_dispatch_tech": "Envoyer un appareil vers l'atelier / technicien",
            "act_sav_return_tech": "Enregistrer le retour de réparation",
            "act_sav_deliver_client": "Restituer l'appareil au client et clôturer",
            "act_sav_declare_irreparable": "Déclarer un appareil irréparable (Avoir portefeuille)"
        }
    }
}
# =================================================================================
# 1. CLASS UserDialog (نافذة الإضافة والتعديل المدمجة مع شجرة الصلاحيات)
# =================================================================================
class UserDialog(BaseDialog):
    """Boîte de dialogue pour ajouter/modifier un utilisateur avec permissions granulaires"""
    def __init__(self, parent=None, data=None):
        title = "Modifier l'utilisateur" if data else "Ajouter un utilisateur"
        super().__init__(title, parent)
        self.resize(850, 600)  # توسيع النافذة لتسع شجرة الصلاحيات
        self.data = data
        self.init_ui()

    def init_ui(self):
        # الاعتماد على تخطيط أفقي لفصل البيانات الأساسية عن الصلاحيات
        main_layout = QHBoxLayout(self.form_widget)
        
        # --- اللوحة اليسرى (بيانات الحساب) ---
        left_widget = QWidget()
        form_layout = QFormLayout(left_widget)
        
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        
        if self.data:
            self.password_input.setPlaceholderText("Laissez vide pour ne pas changer")
        
        self.full_name_input = QLineEdit()
        self.role_combo = QComboBox()
        self.role_combo.addItems(['Administrateur', 'Responsable', 'Technicien'])

        form_layout.addRow("Nom d'utilisateur:", self.username_input)
        form_layout.addRow("Mot de passe:", self.password_input)
        form_layout.addRow("Nom complet:", self.full_name_input)
        form_layout.addRow("Rôle (Catégorie):", self.role_combo)
        
        main_layout.addWidget(left_widget, 1) # الوزن 1

        # --- اللوحة اليمنى (شجرة الصلاحيات) ---
        self.tree_perms = QTreeWidget()
        self.tree_perms.setHeaderLabel("Accès et Permissions (Cochez pour autoriser)")
        self.tree_perms.itemChanged.connect(self.handle_item_changed)
        self.build_permissions_tree()
        main_layout.addWidget(self.tree_perms, 2) # الوزن 2 لتكون أوسع

        # --- تعبئة البيانات إذا كنا في وضع التعديل ---
        if self.data:
            self.username_input.setText(self.data.get('Username', ''))
            self.full_name_input.setText(self.data.get('Full_Name', ''))
            
            db_role = self.data.get('Role', 'Technician')
            display_role = "Technicien"
            if db_role == 'Admin': display_role = 'Administrateur'
            elif db_role == 'Manager': display_role = 'Responsable'
            self.role_combo.setCurrentText(display_role)
            
            # إسقاط الصلاحيات على الشجرة
            self.set_permissions(self.data.get('Permissions', {}))
        else:
            self.role_combo.currentTextChanged.connect(self._apply_role_defaults)
            self._apply_role_defaults(self.role_combo.currentText())

    def _apply_role_defaults(self, role_name):
        """Applique des permissions par défaut selon le rôle lors de l'ajout d'un utilisateur."""
        all_keys = []
        for group in SYSTEM_PERMISSIONS.values():
            if "perms" in group:
                all_keys.extend(group["perms"].keys())

        if role_name == 'Administrateur':
            self.set_permissions({k: True for k in all_keys})
        elif role_name == 'Responsable':
            excluded = {"tab_set_db", "tab_system_logs", "tab_set_system"}
            self.set_permissions({k: (k not in excluded) for k in all_keys})
        else:
            tech_perms = {
                "nav_pos": True, "nav_sales": True, "act_create_sale": True, "act_validate_sale": True,
                "nav_inventory": True, "tab_inv_list": True, "tab_inv_dispatch": True,
                "nav_procurement": True, "tab_proc_reception": True, "tab_proc_credit": True,
                # Bureaux Opérationnels & SAV pour profil Technicien
                "nav_appliance_workflow": True,
                "tab_desk_order": True,
                "act_order_create": True,
                "tab_desk_dispatch": True,
                "act_dispatch_validate": True,
                "nav_sav": True,
                "tab_desk_sav": True,
                "act_sav_ticket_create": True,
                "act_sav_return_tech": True,
                "tab_serial_registry": True,
                "act_serial_audit": True,
            }
            self.set_permissions(tech_perms)

    def build_permissions_tree(self):
        self.tree_perms.blockSignals(True)
        self.tree_perms.clear()
        
        header_font = QFont()
        header_font.setBold(True)

        def _sort_key(item):
            prefix = item[0].split(".")[0].strip()
            num_part = "".join(ch for ch in prefix if ch.isdigit())
            alpha_part = "".join(ch for ch in prefix if not ch.isdigit())
            return (int(num_part) if num_part else 999, alpha_part)

        for group_id, content in sorted(SYSTEM_PERMISSIONS.items(), key=_sort_key):
            group_item = QTreeWidgetItem(self.tree_perms)
            group_item.setText(0, content["label"])
            group_item.setIcon(0, qta.icon(content["icon"], color="#d4af37"))
            
            group_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
            group_item.setCheckState(0, Qt.Unchecked)
            group_item.setFont(0, header_font)
            group_item.setForeground(0, QBrush(QColor("#2c3e50")))
            group_item.setBackground(0, QBrush(QColor("#f4f7fa")))

            if "perms" in content:
                for key, label in content["perms"].items():
                    child = QTreeWidgetItem(group_item)
                    child.setText(0, label)
                    child.setData(0, Qt.UserRole, key) # تخزين الـ Key (مثال: nav_dashboard)
                    child.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
                    child.setCheckState(0, Qt.Unchecked)

        self.tree_perms.expandAll()
        self.tree_perms.blockSignals(False)

    def handle_item_changed(self, item, column):
        self.tree_perms.blockSignals(True)
        # إذا كان العنصر "أب" (مجموعة)
        if item.childCount() > 0:
            state = item.checkState(0)
            for i in range(item.childCount()):
                item.child(i).setCheckState(0, state)
        # إذا كان العنصر "ابن" (صلاحية مفردة)
        else:
            parent = item.parent()
            if parent:
                checked_count = sum(1 for i in range(parent.childCount()) if parent.child(i).checkState(0) == Qt.Checked)
                if checked_count == 0:
                    parent.setCheckState(0, Qt.Unchecked)
                elif checked_count == parent.childCount():
                    parent.setCheckState(0, Qt.Checked)
                else:
                    parent.setCheckState(0, Qt.PartiallyChecked)
        self.tree_perms.blockSignals(False)

    def set_permissions(self, perms_data):
        self.tree_perms.blockSignals(True)
        
        # تحويل النص إلى كائن برمجي إذا تم تمريره كنص
        if isinstance(perms_data, str):
            try: perms_data = json.loads(perms_data)
            except: perms_data = {}
            
        for i in range(self.tree_perms.topLevelItemCount()):
            group = self.tree_perms.topLevelItem(i)
            checked_children = 0
            for j in range(group.childCount()):
                child = group.child(j)
                key = child.data(0, Qt.UserRole)
                
                # فحص ما إذا كان المفتاح مفعلاً
                is_checked = False
                if isinstance(perms_data, list): is_checked = key in perms_data
                elif isinstance(perms_data, dict): is_checked = perms_data.get(key, False)
                
                if is_checked:
                    child.setCheckState(0, Qt.Checked)
                    checked_children += 1
                else:
                    child.setCheckState(0, Qt.Unchecked)
                    
            if checked_children == 0: group.setCheckState(0, Qt.Unchecked)
            elif checked_children == group.childCount(): group.setCheckState(0, Qt.Checked)
            else: group.setCheckState(0, Qt.PartiallyChecked)

        self.tree_perms.blockSignals(False)

    def get_selected_permissions(self):
        perms = {}
        for i in range(self.tree_perms.topLevelItemCount()):
            group = self.tree_perms.topLevelItem(i)
            for j in range(group.childCount()):
                child = group.child(j)
                if child.checkState(0) == Qt.Checked:
                    key = child.data(0, Qt.UserRole)
                    if key: perms[key] = True
        return perms

    def get_data(self):
        role_map = {
            'Administrateur': 'Admin',
            'Responsable': 'Manager',
            'Technicien': 'Technician'
        }
        
        selected_display_role = self.role_combo.currentText()
        db_role = role_map.get(selected_display_role, 'Technician')

        data = {
            "Username": self.username_input.text().strip(),
            "Full_Name": self.full_name_input.text().strip(),
            "Role": db_role,
            "Permissions": self.get_selected_permissions() # إضافة الصلاحيات الديناميكية
        }
        
        pwd = self.password_input.text().strip()
        if pwd:
            data["Password"] = pwd
            
        return data

# =================================================================================
# 2. CLASS UserManagementTab (الواجهة الرئيسية لإدارة المستخدمين)
# =================================================================================
class UserManagementTab(QWidget):
    def __init__(self, data_manager):
        super().__init__() 
        self.data_manager = data_manager
        self.users_list = []
        self.init_ui()
        self.load_users()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # --- Barre d'outils ---
        toolbar = QHBoxLayout()
        
        self.btn_add = QPushButton(" Ajouter")
        self.btn_add.setIcon(qta.icon("fa5s.plus", color="white"))
        self.btn_add.setStyleSheet("background-color: #28a745; color: white; padding: 8px 15px; font-weight: bold;")
        self.btn_add.clicked.connect(self.add_user)
        
        self.btn_edit = QPushButton(" Modifier")
        self.btn_edit.setIcon(qta.icon("fa5s.edit", color="white"))
        self.btn_edit.setStyleSheet("background-color: #007bff; color: white; padding: 8px 15px; font-weight: bold;")
        self.btn_edit.clicked.connect(self.edit_selected_user)
        
        self.btn_delete = QPushButton(" Supprimer")
        self.btn_delete.setIcon(qta.icon("fa5s.trash-alt", color="white"))
        self.btn_delete.setStyleSheet("background-color: #dc3545; color: white; padding: 8px 15px; font-weight: bold;")
        self.btn_delete.clicked.connect(self.delete_selected_user)

        self.btn_refresh = QPushButton(" Actualiser")
        self.btn_refresh.setIcon(qta.icon("fa5s.sync-alt", color="white"))
        self.btn_refresh.setStyleSheet("background-color: #17a2b8; color: white; padding: 8px 15px; font-weight: bold;") 
        self.btn_refresh.clicked.connect(self.load_users)

        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(self.btn_edit)
        toolbar.addWidget(self.btn_delete)
        toolbar.addSpacing(10)
        toolbar.addWidget(self.btn_refresh)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # --- Tableau ---
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Nom d'utilisateur", "Nom Complet", "Rôle"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self.edit_selected_user)
        
        layout.addWidget(self.table)

    def load_users(self):
        role_translation = {
            "Admin": "Administrateur",
            "Manager": "Responsable",
            "Technician": "Technicien"
        }

        self.users_list = self.data_manager.users.get_all_users(include_inactive=True)
        self.table.setRowCount(0)
        
        for row, u in enumerate(self.users_list):
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(u['User_ID'])))
            self.table.setItem(row, 1, QTableWidgetItem(u['Username']))
            self.table.setItem(row, 2, QTableWidgetItem(u['Full_Name'] or ""))
            
            db_role = u['Role']
            translated_role = role_translation.get(db_role, db_role)
            self.table.setItem(row, 3, QTableWidgetItem(translated_role))

    def get_selected_user_data(self):
        selected_row = self.table.currentRow()
        if selected_row >= 0:
            user_id = int(self.table.item(selected_row, 0).text())
            for user in self.users_list:
                if user['User_ID'] == user_id:
                    return user
        return None

    def add_user(self):
        dlg = UserDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            if data['Username'] and data.get('Password'):
                perms = data.pop('Permissions', {})
                res = self.data_manager.users.add_user(
                    data['Username'], data['Password'], data['Role'], data['Full_Name'], permissions=perms
                )
                if res == -1:
                    QMessageBox.warning(self, "Erreur", "Ce nom d'utilisateur existe déjà.")
                elif res is None:
                    QMessageBox.critical(self, "Erreur", "Erreur base de données.")
                
                self.load_users()
            else:
                QMessageBox.warning(self, "Champs requis", "Nom d'utilisateur et mot de passe obligatoires.")

    def edit_selected_user(self):
        user_data = self.get_selected_user_data()
        if not user_data:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner un utilisateur.")
            return

        dlg = UserDialog(self, data=user_data)
        if dlg.exec():
            updated_data = dlg.get_data()
            success = self.data_manager.users.update_user(user_data['User_ID'], **updated_data)
            if success:
                # تحديث صلاحيات المستخدم الحالي فوراً في الذاكرة وإعادة تطبيق القائمة الجانبية
                if hasattr(self.data_manager, 'current_user') and self.data_manager.current_user:
                    curr_id = self.data_manager.current_user.get('User_ID') or self.data_manager.current_user.get('id')
                    if curr_id and curr_id == user_data['User_ID']:
                        self.data_manager.current_user['Permissions'] = updated_data.get('Permissions', {})
                        main_win = self.window()
                        if hasattr(main_win, 'apply_permissions'):
                            main_win.apply_permissions()
                self.load_users()
            else:
                QMessageBox.critical(self, "Erreur", "Échec de la modification.")

    def delete_selected_user(self):
        user_data = self.get_selected_user_data()
        if not user_data:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner un utilisateur.")
            return

        if user_data['Username'].lower() == "admin":
            QMessageBox.critical(self, "Interdit", "L'utilisateur 'admin' ne peut pas être supprimé.")
            return

        confirm = QMessageBox.question(
            self, "Confirmation", 
            f"Voulez-vous vraiment supprimer '{user_data['Username']}' ?",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm == QMessageBox.Yes:
            success = self.data_manager.users.update_user(user_data['User_ID'], Is_Active=0)
            if success:
                self.load_users()
            else:
                QMessageBox.critical(self, "Erreur", "Échec de la suppression.")
