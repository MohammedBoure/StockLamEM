# ui/widgets/settings/auto_backup_tab.py

import os
import logging
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QGroupBox, QFormLayout,
                               QSpinBox, QMessageBox, QFileDialog, QCheckBox,
                               QDoubleSpinBox, QListWidget, QInputDialog)
from PySide6.QtCore import Qt


class AutoBackupTab(QWidget):
    """Onglet dédié à la sauvegarde automatique en arrière-plan et aux sauvegardes manuelles."""

    def __init__(self, settings=None, data_manager=None, local_store=None, parent=None):
        super().__init__(parent)
        self.settings = settings or {}
        self.data_manager = data_manager
        self.local_store = local_store
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(20)

        left_col = QVBoxLayout()
        right_col = QVBoxLayout()

        # =========================================================================
        # 1. Sauvegarde Automatique (Arrière-plan)
        # =========================================================================
        grp_auto_backup = QGroupBox("⏱️ Sauvegarde Automatique (Arrière-plan)")
        grp_auto_backup.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 1px solid #cfd8dc;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
        """)
        auto_backup_layout = QVBoxLayout()
        auto_backup_layout.setSpacing(10)

        form_auto = QFormLayout()
        form_auto.setSpacing(10)

        self.chk_auto_backup = QCheckBox("Activer la sauvegarde automatique")
        self.chk_auto_backup.setChecked(bool(self.settings.get("auto_backup_enabled", False)))

        self.spin_auto_interval = QDoubleSpinBox()
        self.spin_auto_interval.setRange(0.1, 1440.0)
        self.spin_auto_interval.setValue(float(self.settings.get("auto_backup_interval", 60.0)))
        self.spin_auto_interval.setSuffix(" min")

        self.txt_auto_pwd = QLineEdit(str(self.settings.get("auto_backup_password", "")))
        self.txt_auto_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_auto_pwd.setPlaceholderText("Optionnel (Chiffrement AES-256)")

        self.spin_max_backups = QSpinBox()
        self.spin_max_backups.setRange(1, 100)
        self.spin_max_backups.setValue(int(self.settings.get("auto_backup_max_files", 5)))

        form_auto.addRow("", self.chk_auto_backup)
        form_auto.addRow("⏱️ Intervalle (Minutes) :", self.spin_auto_interval)
        form_auto.addRow("🔐 Mot de passe ZIP :", self.txt_auto_pwd)
        form_auto.addRow("📁 Nbre max de sauvegardes :", self.spin_max_backups)
        auto_backup_layout.addLayout(form_auto)

        auto_backup_layout.addWidget(QLabel("Dossiers de destination (Cibles multiples) :"))
        self.list_backup_paths = QListWidget()

        paths = self.settings.get("backup_paths", [])
        if not paths and self.settings.get("backup_path"):
            paths = [self.settings.get("backup_path")]
        for p in paths:
            self.list_backup_paths.addItem(str(p))

        path_btns_layout = QHBoxLayout()
        btn_add_path = QPushButton("➕ Ajouter un dossier")
        btn_add_path.clicked.connect(self.add_backup_path)
        btn_rem_path = QPushButton("❌ Supprimer sélection")
        btn_rem_path.clicked.connect(self.remove_backup_path)
        path_btns_layout.addWidget(btn_add_path)
        path_btns_layout.addWidget(btn_rem_path)

        auto_backup_layout.addWidget(self.list_backup_paths)
        auto_backup_layout.addLayout(path_btns_layout)

        self.btn_force_auto = QPushButton("▶️ Forcer la sauvegarde maintenant")
        self.btn_force_auto.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold; padding: 10px; border-radius: 4px;")
        self.btn_force_auto.clicked.connect(self.force_manual_backup)
        auto_backup_layout.addWidget(self.btn_force_auto)

        grp_auto_backup.setLayout(auto_backup_layout)
        left_col.addWidget(grp_auto_backup)
        left_col.addStretch()

        # =========================================================================
        # 2. Sauvegarde & Restauration Manuelle
        # =========================================================================
        grp_manual = QGroupBox("💾 Sauvegarde & Restauration Manuelle")
        grp_manual.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 1px solid #cfd8dc;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
        """)
        manual_layout = QVBoxLayout()
        manual_layout.setSpacing(12)

        lbl_desc = QLabel("Effectuez des sauvegardes complètes ponctuelles ou restaurez vos données à partir d'une sauvegarde existante.")
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #555; font-size: 12px; margin-bottom: 5px;")
        manual_layout.addWidget(lbl_desc)

        btn_backup = QPushButton("Sauvegarde complète (Excel)")
        btn_backup.setMinimumHeight(42)
        btn_backup.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; font-size: 13px; border-radius: 4px;")
        btn_backup.clicked.connect(self.perform_backup)
        manual_layout.addWidget(btn_backup)

        btn_restore = QPushButton("♻️ Restauration complète")
        btn_restore.setMinimumHeight(42)
        btn_restore.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; font-size: 13px; border-radius: 4px;")
        btn_restore.clicked.connect(self.perform_restore)
        manual_layout.addWidget(btn_restore)

        manual_layout.addStretch()
        grp_manual.setLayout(manual_layout)
        right_col.addWidget(grp_manual)
        right_col.addStretch()

        main_layout.addLayout(left_col, 60)
        main_layout.addLayout(right_col, 40)

    # --- Actions Auto-Backup ---
    def add_backup_path(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier de sauvegarde")
        if folder_path:
            existing_paths = [self.list_backup_paths.item(i).text() for i in range(self.list_backup_paths.count())]
            if folder_path not in existing_paths:
                self.list_backup_paths.addItem(folder_path)

    def remove_backup_path(self):
        selected_items = self.list_backup_paths.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            self.list_backup_paths.takeItem(self.list_backup_paths.row(item))

    def force_manual_backup(self):
        paths = [self.list_backup_paths.item(i).text() for i in range(self.list_backup_paths.count())]
        if not paths:
            QMessageBox.warning(self, "Attention", "Veuillez ajouter au moins un dossier de destination.")
            return

        password = self.txt_auto_pwd.text()

        if self.data_manager and hasattr(self.data_manager, 'db') and hasattr(self.data_manager.db, 'create_multi_backup'):
            success, msg = self.data_manager.db.create_multi_backup(paths, password, is_auto=False)
            if success:
                QMessageBox.information(self, "Succès", f"Sauvegarde forcée terminée !\n{msg}")
            else:
                QMessageBox.critical(self, "Erreur", f"Échec de la sauvegarde forcée :\n{msg}")
        else:
            QMessageBox.critical(self, "Erreur", "La fonction 'create_multi_backup' est introuvable.")

    # --- Actions Sauvegarde & Restauration Manuelle ---
    def perform_backup(self):
        filename = f"sauvegarde_excel_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer la sauvegarde (Excel)", filename, "Fichiers ZIP (*.zip)")
        if path:
            if self.data_manager and hasattr(self.data_manager, 'db') and hasattr(self.data_manager.db, 'backup_database_excel'):
                success, msg = self.data_manager.db.backup_database_excel(path)
                if success:
                    QMessageBox.information(self, "Terminé", "La sauvegarde Excel a été créée avec succès.")
                else:
                    QMessageBox.critical(self, "Erreur", msg)
            else:
                QMessageBox.critical(self, "Erreur", "La fonction de sauvegarde Excel est introuvable.")

    def perform_restore(self):
        confirm = QMessageBox.warning(
            self,
            "Attention - Restauration",
            "Toutes les données actuelles seront supprimées et remplacées par celles du fichier de sauvegarde !\n\nÊtes-vous sûr ?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            path, _ = QFileDialog.getOpenFileName(self, "Sélectionner le fichier de sauvegarde", "", "Fichiers ZIP (*.zip)")
            if path:
                if not self.data_manager or not hasattr(self.data_manager, 'db'):
                    QMessageBox.critical(self, "Erreur", "Gestionnaire de base de données introuvable.")
                    return

                db_ref = self.data_manager.db
                password = None

                try:
                    if hasattr(db_ref, 'backup_zip_requires_password') and db_ref.backup_zip_requires_password(path):
                        password, ok = QInputDialog.getText(
                            self,
                            "Mot de passe sauvegarde",
                            "Cette sauvegarde est protégée. Entrez le mot de passe ZIP :",
                            QLineEdit.EchoMode.Password,
                            str(self.settings.get("auto_backup_password", ""))
                        )
                        if not ok:
                            return
                except Exception as e:
                    logging.warning(f"Impossible de vérifier le mot de passe de sauvegarde: {e}")

                if hasattr(db_ref, 'restore_database_backup'):
                    success, msg = db_ref.restore_database_backup(path, password=password)
                    if not success and str(msg).startswith("BACKUP_PASSWORD_REQUIRED"):
                        QMessageBox.warning(self, "Mot de passe requis", "Cette sauvegarde est chiffrée. Veuillez entrer le mot de passe.")
                        return
                    if not success and str(msg).startswith("BACKUP_BAD_PASSWORD"):
                        QMessageBox.critical(self, "Mot de passe incorrect", "Le mot de passe de la sauvegarde est incorrect.")
                        return
                    if success:
                        QMessageBox.information(self, "Terminé", "Restauration terminée avec succès.")
                    else:
                        QMessageBox.critical(self, "Échec", msg)
                elif hasattr(db_ref, 'restore_database_excel'):
                    success, msg = db_ref.restore_database_excel(path, password=password)
                    if success:
                        QMessageBox.information(self, "Terminé", "Restauration terminée avec succès.")
                    else:
                        QMessageBox.critical(self, "Échec", msg)
                else:
                    QMessageBox.critical(self, "Erreur", "La fonction de restauration est introuvable.")

    # --- Synchronisation des réglages ---
    def load_settings(self, settings):
        """Met à jour les contrôles avec le dictionnaire de réglages fourni."""
        self.settings = settings or {}
        self.chk_auto_backup.setChecked(bool(self.settings.get("auto_backup_enabled", False)))
        self.spin_auto_interval.setValue(float(self.settings.get("auto_backup_interval", 60.0)))
        self.txt_auto_pwd.setText(str(self.settings.get("auto_backup_password", "")))
        self.spin_max_backups.setValue(int(self.settings.get("auto_backup_max_files", 5)))

        self.list_backup_paths.clear()
        paths = self.settings.get("backup_paths", [])
        if not paths and self.settings.get("backup_path"):
            paths = [self.settings.get("backup_path")]
        for p in paths:
            self.list_backup_paths.addItem(str(p))

    def get_settings(self):
        """Retourne les paramètres de sauvegarde saisis sous forme de dictionnaire."""
        return {
            "auto_backup_enabled": self.chk_auto_backup.isChecked(),
            "auto_backup_interval": self.spin_auto_interval.value(),
            "auto_backup_password": self.txt_auto_pwd.text(),
            "auto_backup_max_files": self.spin_max_backups.value(),
            "backup_paths": [self.list_backup_paths.item(i).text() for i in range(self.list_backup_paths.count())],
        }
