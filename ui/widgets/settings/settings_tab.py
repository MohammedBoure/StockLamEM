# ui/widgets/settings/settings_tab.py

import os
import logging
try:
    import win32print
except ImportError:
    win32print = None
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QGroupBox, QFormLayout,
                               QSpinBox, QMessageBox, QFileDialog, QTabWidget,
                               QComboBox, QInputDialog, QCheckBox, QDoubleSpinBox,
                               QListWidget, QTextEdit)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
import mysql.connector
import sys
from dotenv import dotenv_values

from .barcode_visual_editor import BarcodeVisualEditor
from .receipt_visual_editor import ReceiptVisualEditor
from .pdf.pdf_config_dialog import PdfConfigDialog
from .local_settings import LocalSettingsStore
from .system_logs_tab import SystemLogsTab
from .lab_info_tab import LabInfoTab
from .auto_backup_tab import AutoBackupTab

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

def get_external_path(filename):
    """توحيد مسار الحفظ ليتطابق بنسبة 100% مع مسارات البرنامج الرئيسية"""
    if hasattr(sys, '_MEIPASS'):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, filename)

ENV_FILE = get_external_path(".env")

class SettingsTab(QWidget):
    def __init__(self, data_manager, current_user=None, can_manage_stamps=None, local_store=None):
        super().__init__()
        self.data_manager = data_manager
        self.current_user = current_user or getattr(data_manager, "current_user", None)
        self.can_manage_stamps = (
            bool(can_manage_stamps)
            if can_manage_stamps is not None
            else bool(getattr(data_manager, "can_manage_stamps", False))
        )
        self.local_store = local_store or LocalSettingsStore(self.current_user)
        self.config_file = self.local_store.general_path
        self.pdf_config_dialog = None

        # Paramètres par défaut
        self.settings = {
            "lab_name": "Laboratoire Algérie",
            "lab_address": "Alger, Algérie",
            "expiry_warning_days": 30,
            "low_stock_threshold": 5,

            # --- Auto Backup Settings ---
            "auto_backup_enabled": False,
            "auto_backup_interval": 60.0,
            "auto_backup_password": "",
            "backup_paths": [],

            "db_host": "127.0.0.1",
            "db_port": 3306,
            "db_user": "root",
            "db_password": "root",
            "db_name": "Lab_Inventory_Enterprise_DB",

            "flask_env": "development",
            "secret_key": "change_me_key",
            "max_content_length": 16777216,

            "selected_printer": "",
            "selected_receipt_printer": "",
            "label_width": 50,
            "label_height": 30,
            "gap": 2
        }

        self.load_settings()
        self.load_database_settings_from_env()
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        self.tabs = QTabWidget()

        # Initialize widgets only
        self.tab_lab_info = LabInfoTab(self.settings, self)
        self.tab_auto_backup = AutoBackupTab(self.settings, self.data_manager, self.local_store, self)
        self.tab_general = self.tab_lab_info  # Compatibilité ascendante

        self.tab_db = QWidget()
        self._setup_database_tab()

        self.tab_printer = QWidget()
        self._setup_printer_tab()

        self.tab_system = QWidget()
        self._setup_system_tab()

        self.tab_barcode_config = BarcodeVisualEditor(self.data_manager) if hasattr(self, 'data_manager') and self.data_manager else QWidget()
        self.tab_receipt_config = ReceiptVisualEditor(self.data_manager) if hasattr(self, 'data_manager') and self.data_manager else QWidget()

        self.tab_pdf_config = QWidget()
        self._setup_pdf_launcher()

        self.tab_system_logs = SystemLogsTab(self.data_manager) if self.data_manager else QWidget()

        main_layout.addWidget(self.tabs)

        # Bottom buttons setup
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("Enregistrer les paramètres du programme")
        btn_save.setToolTip(
            "Enregistre uniquement les réglages généraux locaux. "
            "Les réglages PDF se gèrent dans la fenêtre Configuration PDF."
        )
        btn_save.setStyleSheet("background-color: #007572; color: white; padding: 8px 16px; border: none; border-radius: 4px; font-weight: bold;")
        btn_save.clicked.connect(self.save_settings)

        btn_export_env = QPushButton("Exporter .env")
        btn_export_env.setStyleSheet("background-color: #FFFFFF; color: #334155; border: 1px solid #CBD5E1; border-radius: 4px; padding: 8px 14px;")
        btn_export_env.clicked.connect(self.export_to_env_file)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_export_env)
        btn_layout.addWidget(btn_save)

        main_layout.addLayout(btn_layout)

    def _setup_general_tab(self):
        pass

    # --- Accesseurs de compatibilité pour Informations du Laboratoire ---
    @property
    def txt_lab_name(self):
        return self.tab_lab_info.txt_lab_name

    @property
    def txt_lab_address(self):
        return self.tab_lab_info.txt_lab_address

    @property
    def txt_lab_nif(self):
        return self.tab_lab_info.txt_lab_nif

    @property
    def txt_lab_rc(self):
        return self.tab_lab_info.txt_lab_rc

    # --- Accesseurs de compatibilité pour Sauvegarde Automatique ---
    @property
    def chk_auto_backup(self):
        return self.tab_auto_backup.chk_auto_backup

    @property
    def spin_auto_interval(self):
        return self.tab_auto_backup.spin_auto_interval

    @property
    def txt_auto_pwd(self):
        return self.tab_auto_backup.txt_auto_pwd

    @property
    def spin_max_backups(self):
        return self.tab_auto_backup.spin_max_backups

    @property
    def list_backup_paths(self):
        return self.tab_auto_backup.list_backup_paths

    def _setup_database_tab(self):
        layout = QVBoxLayout(self.tab_db)
        grp_conn = QGroupBox("Connexion MySQL")
        form_conn = QFormLayout()

        self.txt_db_host = QLineEdit(str(self.settings.get("db_host", "")))
        self.spin_db_port = QSpinBox()
        self.spin_db_port.setRange(1, 65535)
        self.spin_db_port.setValue(int(self.settings.get("db_port", 3306)))
        self.txt_db_user = QLineEdit(str(self.settings.get("db_user", "")))
        self.txt_db_pass = QLineEdit(str(self.settings.get("db_password", "")))
        self.txt_db_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_db_name = QLineEdit(str(self.settings.get("db_name", "")))

        form_conn.addRow("Hôte :", self.txt_db_host)
        form_conn.addRow("Port :", self.spin_db_port)
        form_conn.addRow("Utilisateur :", self.txt_db_user)
        form_conn.addRow("Mot de passe :", self.txt_db_pass)
        form_conn.addRow("Base de données :", self.txt_db_name)
        grp_conn.setLayout(form_conn)
        layout.addWidget(grp_conn)

        btn_test = QPushButton("🔌 Tester la connexion")
        btn_test.clicked.connect(self.test_db_connection)
        layout.addWidget(btn_test)

        self.grp_connection_error = QGroupBox("Derniere erreur de connexion")
        error_layout = QVBoxLayout(self.grp_connection_error)
        self.txt_connection_error = QTextEdit()
        self.txt_connection_error.setReadOnly(True)
        self.txt_connection_error.setMinimumHeight(130)
        error_layout.addWidget(self.txt_connection_error)
        self.grp_connection_error.setVisible(False)
        layout.addWidget(self.grp_connection_error)

        layout.addStretch()

    def _setup_printer_tab(self):
        layout = QVBoxLayout(self.tab_printer)

        # === 1. Section: Imprimante Code-Barres ===
        grp_barcode = QGroupBox("Imprimante Code-Barres")
        form_barcode = QFormLayout()

        self.combo_printers = QComboBox()
        printer_names = []
        try:
            printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
            printer_names = [p[2] for p in printers]
            self.combo_printers.addItems(printer_names)
        except:
            self.combo_printers.addItem("Erreur lors de la liste des imprimantes")

        current_p = self.settings.get("selected_printer", "")
        if current_p:
            idx = self.combo_printers.findText(current_p)
            if idx >= 0: self.combo_printers.setCurrentIndex(idx)

        self.spin_width = QSpinBox()
        self.spin_width.setRange(10, 200)
        self.spin_width.setValue(int(self.settings.get("label_width", 50)))

        self.spin_height = QSpinBox()
        self.spin_height.setRange(10, 200)
        self.spin_height.setValue(int(self.settings.get("label_height", 30)))

        self.spin_gap = QSpinBox()
        self.spin_gap.setRange(0, 10)
        self.spin_gap.setValue(int(self.settings.get("gap", 2)))

        form_barcode.addRow("Imprimante :", self.combo_printers)
        form_barcode.addRow("Largeur étiquette (mm) :", self.spin_width)
        form_barcode.addRow("Hauteur étiquette (mm) :", self.spin_height)
        form_barcode.addRow("Espacement (gap) (mm) :", self.spin_gap)
        grp_barcode.setLayout(form_barcode)
        layout.addWidget(grp_barcode)

        # === 2. Section: Imprimante Fiches/Tickets ===
        grp_receipt = QGroupBox("Imprimante Tickets")
        form_receipt = QFormLayout()

        self.combo_receipt_printers = QComboBox()
        try:
            self.combo_receipt_printers.addItems(printer_names)
        except:
            self.combo_receipt_printers.addItem("Erreur lors de la liste des imprimantes")

        current_rp = self.settings.get("selected_receipt_printer", "")
        if current_rp:
            idx_r = self.combo_receipt_printers.findText(current_rp)
            if idx_r >= 0: self.combo_receipt_printers.setCurrentIndex(idx_r)

        form_receipt.addRow("Imprimante :", self.combo_receipt_printers)
        grp_receipt.setLayout(form_receipt)
        layout.addWidget(grp_receipt)

        btn_test_print = QPushButton("Imprimer une étiquette test")
        btn_test_print.clicked.connect(self.test_print_label)
        layout.addWidget(btn_test_print)
        layout.addStretch()

    def _setup_pdf_launcher(self):
        layout = QVBoxLayout(self.tab_pdf_config)
        layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("<h2>Configuration PDF</h2>")
        description = QLabel(
            "Les reglages de mise en page restent propres a chaque utilisateur, "
            "mais la bibliotheque des cachets est partagee dans la base de donnees. "
            "Tout utilisateur qui a acces a cette interface peut ajouter, choisir, "
            "activer ou desactiver le cachet utilise dans les PDF."
        )
        description.setWordWrap(True)

        open_button = QPushButton("Ouvrir la configuration PDF")
        open_button.setMinimumHeight(48)
        open_button.setStyleSheet(
            "background-color: #9b59b6; color: white; font-weight: bold; "
            "font-size: 15px; padding: 10px;"
        )
        open_button.clicked.connect(self.open_pdf_config_dialog)

        load_hint = QLabel(
            "Les cachets disponibles sont charges depuis la bibliotheque partagee. "
            "Le bouton de sauvegarde dans la base conserve les reglages communs du modele PDF."
        )
        load_hint.setWordWrap(True)
        load_hint.setStyleSheet("color: #566573;")

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(open_button)
        layout.addWidget(load_hint)
        layout.addStretch()

    def open_pdf_config_dialog(self):
        dialog = PdfConfigDialog(
            self.data_manager,
            current_user=self.current_user,
            can_manage_stamps=self.can_manage_stamps,
            local_store=self.local_store,
            parent=self,
        )
        dialog.exec()

    def _setup_system_tab(self):
        layout = QVBoxLayout(self.tab_system)
        grp_sys = QGroupBox("Variables d'environnement")
        form_sys = QFormLayout()

        self.combo_env = QComboBox()
        self.combo_env.addItems(["development", "production"])
        self.combo_env.setCurrentText(self.settings.get("flask_env", "development"))
        self.txt_secret = QLineEdit(str(self.settings.get("secret_key", "")))
        self.spin_max_len = QSpinBox()
        self.spin_max_len.setRange(1024, 99999999)
        self.spin_max_len.setValue(int(self.settings.get("max_content_length", 16777216)))

        form_sys.addRow("FLASK_ENV :", self.combo_env)
        form_sys.addRow("SECRET_KEY :", self.txt_secret)
        form_sys.addRow("MAX_CONTENT_LENGTH :", self.spin_max_len)
        grp_sys.setLayout(form_sys)
        layout.addWidget(grp_sys)
        layout.addStretch()

    # --- Fonctions Auto-Backup (Délégation) ---
    def add_backup_path(self):
        if hasattr(self, 'tab_auto_backup'):
            return self.tab_auto_backup.add_backup_path()

    def remove_backup_path(self):
        if hasattr(self, 'tab_auto_backup'):
            return self.tab_auto_backup.remove_backup_path()

    def force_manual_backup(self):
        if hasattr(self, 'tab_auto_backup'):
            return self.tab_auto_backup.force_manual_backup()

    # --- Fonctions Générales (Save & Load) ---
    def load_settings(self):
        """Load this user's general settings from the local store."""
        logging.info(f"Reading local settings: {self.config_file}")
        self.settings.update(self.local_store.load_general(self.settings))
        if hasattr(self, 'tab_lab_info'):
            self.tab_lab_info.load_settings(self.settings)
        if hasattr(self, 'tab_auto_backup'):
            self.tab_auto_backup.load_settings(self.settings)

    def load_database_settings_from_env(self):
        if not os.path.exists(ENV_FILE):
            return
        try:
            env_values = dotenv_values(ENV_FILE)
            env_mapping = {
                "DB_HOST": "db_host",
                "DB_USER": "db_user",
                "DB_PASSWORD": "db_password",
                "DB_NAME": "db_name",
            }
            for env_key, setting_key in env_mapping.items():
                if env_values.get(env_key) is not None:
                    self.settings[setting_key] = env_values[env_key]

            if env_values.get("DB_PORT") is not None:
                self.settings["db_port"] = int(env_values["DB_PORT"])
        except Exception as e:
            logging.warning(f"Impossible de lire les parametres DB depuis .env: {e}")

    def save_settings(self):
        """Save general settings for this user without touching PDF settings."""
        # Read the laboratory settings from tab_lab_info
        if hasattr(self, 'tab_lab_info'):
            self.settings.update(self.tab_lab_info.get_settings())

        self.settings["db_host"] = self.txt_db_host.text()
        self.settings["db_port"] = self.spin_db_port.value()
        self.settings["db_user"] = self.txt_db_user.text()
        self.settings["db_password"] = self.txt_db_pass.text()
        self.settings["db_name"] = self.txt_db_name.text()

        self.settings["selected_printer"] = self.combo_printers.currentText()
        if hasattr(self, 'combo_receipt_printers'):
            self.settings["selected_receipt_printer"] = self.combo_receipt_printers.currentText()
        self.settings["label_width"] = self.spin_width.value()
        self.settings["label_height"] = self.spin_height.value()
        self.settings["gap"] = self.spin_gap.value()

        self.settings["flask_env"] = self.combo_env.currentText()
        self.settings["secret_key"] = self.txt_secret.text()
        self.settings["max_content_length"] = self.spin_max_len.value()

        # --- Réglages de sauvegarde ---
        if hasattr(self, 'tab_auto_backup'):
            self.settings.update(self.tab_auto_backup.get_settings())

        try:
            logging.info(f"💾 Sauvegarde vers : {self.config_file}")
            self.local_store.save_general(self.settings)

            if hasattr(self.data_manager, 'printer'):
                if hasattr(self.data_manager.printer, "set_local_settings"):
                    self.data_manager.printer.set_local_settings(self.local_store)
                else:
                    self.data_manager.printer.reload_settings()

            # إعادة تشغيل مؤقت الحفظ التلقائي في الخلفية بالإعدادات الجديدة
            try:
                main_window = self.window()
                auto_backup_thread = getattr(main_window, 'auto_backup_thread', None)
                if auto_backup_thread:
                    auto_backup_thread.stop()
                    auto_backup_thread.wait(500)
                    auto_backup_thread.start()
            except Exception as thread_err:
                logging.error(f"Erreur thread: {thread_err}")

            # رسالة تشخيصية: ستظهر لك بالضبط ما تم كتابته داخل الملف لتكون مطمئناً
            msg = (
                f"Paramètres généraux enregistrés localement dans :\n{self.config_file}\n\n"
                f"Auto-Backup Actif : {self.settings['auto_backup_enabled']}\n"
                f"Intervalle : {self.settings['auto_backup_interval']} min\n"
                f"Dossiers : {len(self.settings['backup_paths'])}"
            )
            QMessageBox.information(self, "Succès", msg)

        except Exception as e:
            logging.error(f"❌ Échec de la sauvegarde: {e}")
            QMessageBox.critical(self, "Erreur", f"Échec de l'enregistrement :\n{e}")

    # Rest of the functions remain the same
    def export_to_env_file(self):
        try:
            schema_check = "false"
            if os.path.exists(ENV_FILE):
                with open(ENV_FILE, 'r', encoding='utf-8') as existing_env:
                    for line in existing_env:
                        if line.strip().startswith("DB_SCHEMA_CHECK_ON_STARTUP="):
                            schema_check = line.strip().split("=", 1)[1] or "false"
                            break

            with open(ENV_FILE, 'w', encoding='utf-8') as f:
                f.write(f"FLASK_ENV={self.combo_env.currentText()}\n")
                f.write(f"SECRET_KEY={self.txt_secret.text()}\n")
                f.write(f"MAX_CONTENT_LENGTH={self.spin_max_len.value()}\n\n")
                f.write(f"DB_HOST={self.txt_db_host.text()}\n")
                f.write(f"DB_PORT={self.spin_db_port.value()}\n")
                f.write(f"DB_USER={self.txt_db_user.text()}\n")
                f.write(f"DB_PASSWORD={self.txt_db_pass.text()}\n")
                f.write(f"DB_NAME={self.txt_db_name.text()}\n")
                f.write(f"DB_SCHEMA_CHECK_ON_STARTUP={schema_check}\n")
            QMessageBox.information(self, "Succès", "Fichier .env exporté avec succès.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))

    def set_connection_error(self, error_text):
        if not hasattr(self, 'grp_connection_error'):
            return
        self.txt_connection_error.setPlainText(str(error_text))
        self.grp_connection_error.setVisible(True)

    def test_db_connection(self):
        logging.info(f"🚀 Tentative de connexion à {self.txt_db_host.text()}...")
        try:
            conn = mysql.connector.connect(
                host=self.txt_db_host.text(),
                port=self.spin_db_port.value(),
                user=self.txt_db_user.text(),
                password=self.txt_db_pass.text(),
                database=self.txt_db_name.text(),
                use_pure=True,
                auth_plugin='mysql_native_password',
                connection_timeout=5
            )
            if conn.is_connected():
                cursor = conn.cursor()
                cursor.execute("SELECT VERSION()")
                version = cursor.fetchone()[0]
                msg = "Connexion réussie ! Authentification validée."
                msg = f"{msg}\nVersion MySQL: {version}"
                logging.info(msg)
                QMessageBox.information(self, "Succès", msg)
                conn.close()
        except mysql.connector.Error as err:
            error_msg = f"❌ Erreur base de données : {err.msg} (Code : {err.errno})"
            logging.error(error_msg)
            self.set_connection_error(error_msg)
            QMessageBox.critical(self, "Échec", error_msg)
        except Exception as e:
            error_msg = f"Erreur inattendue : {str(e)}"
            logging.error(error_msg)
            self.set_connection_error(error_msg)
            QMessageBox.critical(self, "Échec", error_msg)

    def perform_backup(self):
        if hasattr(self, 'tab_auto_backup'):
            return self.tab_auto_backup.perform_backup()

    def perform_restore(self):
        if hasattr(self, 'tab_auto_backup'):
            return self.tab_auto_backup.perform_restore()

    def test_print_label(self):
        self.save_settings()
        if hasattr(self.data_manager, 'printer'):
            success, msg = self.data_manager.printer.print_label(
                "Réactif Test", "1234567890", "LOT-01", "2025-12-31"
            )
            if success: QMessageBox.information(self, "Succès", msg)
            else: QMessageBox.warning(self, "Erreur", msg)
