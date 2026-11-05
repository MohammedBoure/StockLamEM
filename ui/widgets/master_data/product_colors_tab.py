# -*- coding: utf-8 -*-
"""
ui/widgets/master_data/product_colors_tab.py
============================================
Product Colors & Finishes Management Tab (إدارة ألوان وتشطيبات المنتجات).
Allows administrators and managers to:
- View all registered product colors with visual color swatches.
- Add new colors with custom Hex codes and interactive color picker.
- Edit existing colors and toggle active/inactive status.
- Delete or deactivate colors.
"""

import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.icons import get_duotone_icon

logger = logging.getLogger(__name__)

TABLE_STYLE = """
    QTableWidget {
        background-color: #FFFFFF;
        alternate-background-color: #F8FAFC;
        border: 1px solid #DDE3EA;
        border-radius: 6px;
        gridline-color: #F1F5F9;
        color: #1E293B;
        font-size: 9.5pt;
        selection-background-color: #E6F4F1;
        selection-color: #007572;
    }
    QTableWidget::item {
        padding: 5px 8px;
        border: none;
    }
    QHeaderView::section {
        background-color: #F8FAFC;
        color: #0F172A;
        font-weight: 700;
        font-size: 9.5pt;
        padding: 8px;
        border: none;
        border-bottom: 2px solid #007572;
        border-right: 1px solid #E2E8F0;
    }
"""


class ColorDialog(QDialog):
    """Modal dialog to create or edit a product color finish."""

    def __init__(self, color_data: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.color_data = color_data or {}
        is_edit = bool(self.color_data.get("Color_ID"))
        self.setWindowTitle("Modifier la Couleur" if is_edit else "Nouvelle Couleur de Produit")
        self.setMinimumWidth(440)
        self.setStyleSheet("""
            QDialog {
                background-color: #F8FAFC;
            }
            QLabel {
                font-size: 11px;
                font-weight: 700;
                color: #334155;
            }
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11.5px;
                color: #0F172A;
            }
            QLineEdit:focus {
                border: 1.5px solid #007572;
            }
            QCheckBox {
                font-size: 11.5px;
                font-weight: 600;
                color: #334155;
                spacing: 6px;
            }
        """)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        card = QFrame()
        card.setStyleSheet("""
            background-color: #FFFFFF;
            border: 1px solid #DDE3EA;
            border-radius: 6px;
            padding: 12px;
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("Ex: Inox, Blanc, Noir, Gris Anthracite...")
        self.txt_name.setText(str(self.color_data.get("Color_Name") or ""))
        form.addRow("Nom de la Couleur :", self.txt_name)

        hex_row = QHBoxLayout()
        hex_row.setSpacing(8)
        self.txt_code = QLineEdit()
        self.txt_code.setPlaceholderText("#FFFFFF")
        default_hex = str(self.color_data.get("Color_Code") or "#8A9EA7").strip()
        self.txt_code.setText(default_hex)
        self.txt_code.textChanged.connect(self._update_swatch)
        hex_row.addWidget(self.txt_code, stretch=2)

        self.lbl_swatch = QLabel()
        self.lbl_swatch.setFixedSize(32, 28)
        self.lbl_swatch.setStyleSheet("border-radius: 4px; border: 1px solid #94A3B8;")
        hex_row.addWidget(self.lbl_swatch)

        btn_pick = QPushButton("Palette...")
        btn_pick.setCursor(Qt.PointingHandCursor)
        btn_pick.setFixedHeight(28)
        btn_pick.setStyleSheet("""
            QPushButton {
                background: #F1F5F9;
                color: #334155;
                font-weight: 700;
                font-size: 11px;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 4px 10px;
            }
            QPushButton:hover { background: #E2E8F0; }
        """)
        btn_pick.clicked.connect(self._open_color_picker)
        hex_row.addWidget(btn_pick)
        form.addRow("Code Hexadécimal :", hex_row)

        self.txt_desc = QLineEdit()
        self.txt_desc.setPlaceholderText("Ex: Finition brillante, acier brossé...")
        self.txt_desc.setText(str(self.color_data.get("Description") or ""))
        form.addRow("Description :", self.txt_desc)

        self.chk_active = QCheckBox("Couleur Active (disponible pour les produits)")
        self.chk_active.setChecked(bool(self.color_data.get("Is_Active", True)))
        form.addRow("", self.chk_active)

        c_layout.addLayout(form)
        layout.addWidget(card)

        self._update_swatch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("Annuler")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setFixedHeight(34)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #475569;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 4px 14px;
                font-weight: 700;
                font-size: 11.5px;
            }
            QPushButton:hover { background-color: #F1F5F9; }
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_save = QPushButton("Enregistrer la Couleur")
        btn_save.setIcon(get_duotone_icon("check", 14))
        btn_save.setIconSize(QSize(14, 14))
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setFixedHeight(34)
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #007572;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 4px 18px;
                font-weight: 700;
                font-size: 11.5px;
            }
            QPushButton:hover { background-color: #005A57; }
        """)
        btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(btn_save)

        layout.addLayout(btn_row)

    def _update_swatch(self) -> None:
        code = self.txt_code.text().strip()
        if not code.startswith("#"):
            code = f"#{code}"
        col = QColor(code)
        if col.isValid():
            self.lbl_swatch.setStyleSheet(
                f"background-color: {col.name()}; border-radius: 4px; border: 1.5px solid #64748B;"
            )
        else:
            self.lbl_swatch.setStyleSheet(
                "background-color: #FFFFFF; border-radius: 4px; border: 1.5px dashed #CBD5E1;"
            )

    def _open_color_picker(self) -> None:
        init_code = self.txt_code.text().strip()
        init_col = QColor(init_code) if init_code else QColor("#8A9EA7")
        col = QColorDialog.getColor(init_col, self, "Choisir une Couleur de Produit")
        if col.isValid():
            self.txt_code.setText(col.name().upper())
            self._update_swatch()

    def _on_save(self) -> None:
        name = self.txt_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Champ Requis", "Veuillez renseigner le nom de la couleur.")
            return
        code = self.txt_code.text().strip().upper()
        if not code.startswith("#"):
            code = f"#{code}"
        if not QColor(code).isValid():
            QMessageBox.warning(self, "Code Couleur Invalide", "Veuillez saisir un code hexadécimal valide (ex: #8A9EA7).")
            return

        self.color_data["Color_Name"] = name
        self.color_data["Color_Code"] = code
        self.color_data["Description"] = self.txt_desc.text().strip()
        self.color_data["Is_Active"] = self.chk_active.isChecked()
        self.accept()


class ProductColorsTab(QWidget):
    """Master Data tab for registering and managing product colors and finishes."""

    colors_changed = Signal()

    def __init__(self, data_manager=None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.data_manager = data_manager
        self._colors_cache: List[Dict[str, Any]] = []
        self._init_ui()
        self.load_data()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 1. Top Header Card with Search & Add Button
        header = QFrame()
        header.setObjectName("ColorsHeaderCard")
        header.setFixedHeight(54)
        header.setStyleSheet("""
            QFrame#ColorsHeaderCard {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(14, 0, 14, 0)
        h_layout.setSpacing(10)

        ic = QLabel()
        ic.setPixmap(get_duotone_icon("edit_lots", 20).pixmap(20, 20))
        h_layout.addWidget(ic)

        lbl_title = QLabel("Référentiel des Couleurs & Finitions des Produits :")
        lbl_title.setStyleSheet("font-size: 13px; font-weight: 800; color: #1E293B;")
        h_layout.addWidget(lbl_title)

        self.txt_search = QLineEdit()
        self.txt_search.setFixedHeight(34)
        self.txt_search.setPlaceholderText("Rechercher par nom de couleur, code hexadécimal ou description...")
        self.txt_search.textChanged.connect(self._apply_search_filter)
        h_layout.addWidget(self.txt_search, stretch=1)

        btn_add = QPushButton("+ Nouvelle Couleur")
        btn_add.setIcon(get_duotone_icon("check", 14))
        btn_add.setIconSize(QSize(14, 14))
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setFixedHeight(34)
        btn_add.setStyleSheet("""
            QPushButton {
                background-color: #007572;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 4px 16px;
                font-weight: 700;
                font-size: 11.5px;
            }
            QPushButton:hover { background-color: #005A57; }
        """)
        btn_add.clicked.connect(self._on_add_color)
        h_layout.addWidget(btn_add)

        btn_refresh = QPushButton("Actualiser")
        btn_refresh.setIcon(get_duotone_icon("refresh", 14))
        btn_refresh.setIconSize(QSize(14, 14))
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setFixedHeight(34)
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #007572;
                border: 1.5px solid #007572;
                border-radius: 6px;
                padding: 4px 12px;
                font-weight: 700;
                font-size: 11.5px;
            }
            QPushButton:hover { background-color: #E6F4F1; }
        """)
        btn_refresh.clicked.connect(self.load_data)
        h_layout.addWidget(btn_refresh)

        layout.addWidget(header)

        # 2. Main Table
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "ID",
            "Aperçu",
            "Nom de la Couleur",
            "Code Hexadécimal",
            "Description / Finition",
            "Statut",
        ])
        self.table.setStyleSheet(TABLE_STYLE)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.horizontalHeader().setFixedHeight(38)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self._on_table_double_clicked)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.Stretch)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        layout.addWidget(self.table, 1)

    def load_data(self) -> None:
        """Loads product colors from data_manager.colors or fallback registry."""
        colors = []
        if self.data_manager and hasattr(self.data_manager, "colors"):
            try:
                colors = self.data_manager.colors.get_all_colors()
            except Exception as exc:
                logger.error("Failed to load product colors from DB: %s", exc)
                colors = []

        if not colors and not (self.data_manager and hasattr(self.data_manager, "colors")):
            if not self._colors_cache:
                self._colors_cache = [
                    {"Color_ID": 1, "Color_Name": "Inox", "Color_Code": "#8A9EA7", "Description": "Acier inoxydable brossé", "Is_Active": True},
                    {"Color_ID": 2, "Color_Name": "Blanc", "Color_Code": "#FFFFFF", "Description": "Émail blanc standard", "Is_Active": True},
                    {"Color_ID": 3, "Color_Name": "Noir", "Color_Code": "#1E293B", "Description": "Noir mat / laqué", "Is_Active": True},
                    {"Color_ID": 4, "Color_Name": "Silver", "Color_Code": "#CBD5E1", "Description": "Gris argenté métallisé", "Is_Active": True},
                    {"Color_ID": 5, "Color_Name": "Gris Anthracite", "Color_Code": "#475569", "Description": "Gris anthracite contemporain", "Is_Active": True},
                    {"Color_ID": 6, "Color_Name": "Beige", "Color_Code": "#F5F5DC", "Description": "Crème / ivoire", "Is_Active": True},
                    {"Color_ID": 7, "Color_Name": "Rouge", "Color_Code": "#DC2626", "Description": "Rouge brillant", "Is_Active": True},
                ]
            colors = list(self._colors_cache)

        self._colors_cache = colors
        self._populate_table(colors)

    def _apply_search_filter(self) -> None:
        search = self.txt_search.text().strip().lower()
        if not search:
            self._populate_table(self._colors_cache)
            return

        filtered = [
            c for c in self._colors_cache
            if search in str(c.get("Color_Name", "")).lower()
            or search in str(c.get("Color_Code", "")).lower()
            or search in str(c.get("Description", "")).lower()
        ]
        self._populate_table(filtered)

    def _populate_table(self, colors: List[Dict[str, Any]]) -> None:
        self.table.setRowCount(0)
        for row_idx, item in enumerate(colors):
            self.table.insertRow(row_idx)
            cid = str(item.get("Color_ID") or "")
            name = str(item.get("Color_Name") or "")
            hex_code = str(item.get("Color_Code") or "#FFFFFF").upper()
            desc = str(item.get("Description") or "")
            is_active = bool(item.get("Is_Active", True))

            it_id = QTableWidgetItem(cid)
            it_id.setTextAlignment(Qt.AlignCenter)
            it_id.setData(Qt.UserRole, item)
            self.table.setItem(row_idx, 0, it_id)

            # Color preview badge
            swatch_cell = QWidget()
            swatch_cell.setStyleSheet("background: transparent;")
            sw_layout = QHBoxLayout(swatch_cell)
            sw_layout.setContentsMargins(6, 4, 6, 4)
            sw_badge = QLabel()
            sw_badge.setFixedSize(26, 20)
            col = QColor(hex_code)
            sw_badge.setStyleSheet(
                f"background-color: {col.name() if col.isValid() else '#FFFFFF'}; "
                "border: 1px solid #64748B; border-radius: 4px;"
            )
            sw_layout.addWidget(sw_badge)
            sw_layout.setAlignment(Qt.AlignCenter)
            self.table.setCellWidget(row_idx, 1, swatch_cell)

            it_name = QTableWidgetItem(name)
            it_name.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self.table.setItem(row_idx, 2, it_name)

            it_code = QTableWidgetItem(hex_code)
            it_code.setTextAlignment(Qt.AlignCenter)
            it_code.setFont(QFont("Consolas", 10, QFont.Bold))
            self.table.setItem(row_idx, 3, it_code)

            self.table.setItem(row_idx, 4, QTableWidgetItem(desc))

            it_st = QTableWidgetItem("Actif" if is_active else "Inactif")
            it_st.setTextAlignment(Qt.AlignCenter)
            it_st.setFont(QFont("Segoe UI", 9, QFont.Bold))
            it_st.setForeground(QColor("#16A34A" if is_active else "#94A3B8"))
            self.table.setItem(row_idx, 5, it_st)

    def _on_add_color(self) -> None:
        dlg = ColorDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.color_data
            if self.data_manager and hasattr(self.data_manager, "colors"):
                try:
                    self.data_manager.colors.add_color(
                        color_name=data["Color_Name"],
                        color_code=data["Color_Code"],
                        description=data.get("Description", ""),
                    )
                except Exception as err:
                    QMessageBox.critical(self, "Erreur", str(err))
                    return
            else:
                new_id = max([int(c.get("Color_ID") or 0) for c in self._colors_cache] + [0]) + 1
                data["Color_ID"] = new_id
                self._colors_cache.append(data)

            self.load_data()
            self.colors_changed.emit()
            QMessageBox.information(self, "Couleur Enregistrée", f"La couleur '{data['Color_Name']}' a été ajoutée.")

    def _on_table_double_clicked(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        it = self.table.item(row, 0)
        if not it:
            return
        color_item = it.data(Qt.UserRole)
        if not color_item:
            return

        dlg = ColorDialog(color_data=dict(color_item), parent=self)
        if dlg.exec() == QDialog.Accepted:
            updated = dlg.color_data
            cid = int(updated["Color_ID"])
            if self.data_manager and hasattr(self.data_manager, "colors"):
                try:
                    self.data_manager.colors.update_color(
                        color_id=cid,
                        color_name=updated["Color_Name"],
                        color_code=updated["Color_Code"],
                        description=updated.get("Description", ""),
                        is_active=updated.get("Is_Active", True),
                    )
                except Exception as err:
                    QMessageBox.critical(self, "Erreur", str(err))
                    return
            else:
                for c in self._colors_cache:
                    if int(c.get("Color_ID") or 0) == cid:
                        c.update(updated)
                        break

            self.load_data()
            self.colors_changed.emit()
            QMessageBox.information(self, "Couleur Modifiée", f"La couleur '{updated['Color_Name']}' a été mise à jour.")
