# ui/widgets/settings/lab_info_tab.py

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QFormLayout,
                               QLineEdit)


class LabInfoTab(QWidget):
    """Onglet dédié aux informations du laboratoire."""

    def __init__(self, settings=None, parent=None):
        super().__init__(parent)
        self.settings = settings or {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        grp_info = QGroupBox("Informations du laboratoire")
        grp_info.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
                color: #007572;
            }
        """)

        form_info = QFormLayout()
        form_info.setSpacing(12)

        self.txt_lab_name = QLineEdit(str(self.settings.get("lab_name", "")))
        self.txt_lab_name.setPlaceholderText("Nom du laboratoire...")

        self.txt_lab_address = QLineEdit(str(self.settings.get("lab_address", "")))
        self.txt_lab_address.setPlaceholderText("Adresse du laboratoire...")

        self.txt_lab_nif = QLineEdit(str(self.settings.get("lab_nif", "")))
        self.txt_lab_nif.setPlaceholderText("Numéro d'identification fiscale...")

        self.txt_lab_rc = QLineEdit(str(self.settings.get("lab_rc", "")))
        self.txt_lab_rc.setPlaceholderText("Registre du commerce...")

        form_info.addRow("Nom du laboratoire :", self.txt_lab_name)
        form_info.addRow("Adresse :", self.txt_lab_address)
        form_info.addRow("NIF :", self.txt_lab_nif)
        form_info.addRow("Reg Commerce (RC) :", self.txt_lab_rc)

        grp_info.setLayout(form_info)
        layout.addWidget(grp_info)
        layout.addStretch()

    def load_settings(self, settings):
        """Met à jour les champs avec le dictionnaire de réglages fourni."""
        self.settings = settings or {}
        self.txt_lab_name.setText(str(self.settings.get("lab_name", "")))
        self.txt_lab_address.setText(str(self.settings.get("lab_address", "")))
        self.txt_lab_nif.setText(str(self.settings.get("lab_nif", "")))
        self.txt_lab_rc.setText(str(self.settings.get("lab_rc", "")))

    def get_settings(self):
        """Retourne les paramètres saisis sous forme de dictionnaire."""
        return {
            "lab_name": self.txt_lab_name.text().strip(),
            "lab_address": self.txt_lab_address.text().strip(),
            "lab_nif": self.txt_lab_nif.text().strip(),
            "lab_rc": self.txt_lab_rc.text().strip(),
        }
