# -*- coding: utf-8 -*-
"""
ui/widgets/master_data/product_references_tab.py
================================================
Product References (Réf) Management Tab (إدارة مراجع المنتجات Réf).
A product can own several Réf codes (manufacturer ref, supplier ref, legacy ref...).
This tab allows users to:
- View every Réf with its linked product, brand and primary flag.
- Add a Réf to a product (globally unique code).
- Edit / delete a Réf and choose which one is the primary Réf displayed in the desks.
Access is controlled by the `tab_data_references` permission (Utilisateurs).
"""

import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
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
    QTableWidget::item { padding: 5px 8px; border: none; }
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

PRIMARY_BTN_STYLE = """
    QPushButton {
        background-color: #007572; color: #FFFFFF; border: none; border-radius: 6px;
        padding: 4px 16px; font-weight: 700; font-size: 11.5px;
    }
    QPushButton:hover { background-color: #005A57; }
    QPushButton:disabled { background-color: #CBD5E1; color: #F8FAFC; }
"""

OUTLINE_BTN_STYLE = """
    QPushButton {
        background-color: #FFFFFF; color: #007572; border: 1.5px solid #007572; border-radius: 6px;
        padding: 4px 12px; font-weight: 700; font-size: 11.5px;
    }
    QPushButton:hover { background-color: #E6F4F1; }
    QPushButton:disabled { color: #94A3B8; border-color: #CBD5E1; background-color: #F8FAFC; }
"""

DANGER_BTN_STYLE = """
    QPushButton {
        background-color: #FFFFFF; color: #DC2626; border: 1.5px solid #FCA5A5; border-radius: 6px;
        padding: 4px 12px; font-weight: 700; font-size: 11.5px;
    }
    QPushButton:hover { background-color: #FEF2F2; border-color: #EF4444; }
    QPushButton:disabled { color: #94A3B8; border-color: #CBD5E1; background-color: #F8FAFC; }
"""


class ReferenceDialog(QDialog):
    """Modal dialog to create or edit a product Réf."""

    def __init__(
        self,
        products: List[Dict[str, Any]],
        ref_data: Optional[Dict[str, Any]] = None,
        preselect_product_id: Optional[int] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.products = products
        self.ref_data = dict(ref_data or {})
        self.is_edit = bool(self.ref_data.get("Ref_ID"))
        self._preselect_product_id = preselect_product_id or self.ref_data.get("Product_ID")
        self.setWindowTitle("Modifier la Réf" if self.is_edit else "Nouvelle Réf Produit")
        self.setMinimumWidth(500)
        self.setStyleSheet("""
            QDialog { background-color: #F8FAFC; }
            QLabel { font-size: 11px; font-weight: 700; color: #334155; }
            QLineEdit, QComboBox {
                background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 6px;
                padding: 6px 10px; font-size: 11.5px; color: #0F172A; min-height: 22px;
            }
            QLineEdit:focus, QComboBox:focus { border: 1.5px solid #007572; }
            QCheckBox { font-size: 11.5px; font-weight: 600; color: #334155; spacing: 6px; }
        """)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        card = QFrame()
        card.setStyleSheet("background-color: #FFFFFF; border: 1px solid #DDE3EA; border-radius: 6px;")
        form = QFormLayout(card)
        form.setContentsMargins(14, 14, 14, 14)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.cb_product = QComboBox()
        self.cb_product.setEditable(True)
        self.cb_product.setInsertPolicy(QComboBox.NoInsert)
        for p in self.products:
            brand = str(p.get("Brand_Mark") or p.get("Manuf_Name") or "").strip()
            suffix = f"  ({brand})" if brand else ""
            self.cb_product.addItem(f"{p.get('Product_Name', '')}{suffix}", int(p["Product_ID"]))
        completer = QCompleter(self.cb_product.model(), self.cb_product)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.cb_product.setCompleter(completer)
        if self._preselect_product_id is not None:
            idx = self.cb_product.findData(int(self._preselect_product_id))
            if idx >= 0:
                self.cb_product.setCurrentIndex(idx)
        else:
            self.cb_product.setCurrentIndex(-1)
            self.cb_product.lineEdit().setPlaceholderText("Taper le nom du produit...")
        # The linked product cannot change when editing an existing Réf
        self.cb_product.setEnabled(not self.is_edit)
        form.addRow("Produit :", self.cb_product)

        self.txt_ref = QLineEdit(str(self.ref_data.get("Ref_Code") or ""))
        self.txt_ref.setPlaceholderText("Ex: KGN39VLEB, REF-ABC-123...")
        self.txt_ref.setMaxLength(100)
        form.addRow("Code Réf :", self.txt_ref)

        self.txt_notes = QLineEdit(str(self.ref_data.get("Notes") or ""))
        self.txt_notes.setPlaceholderText("Ex: Réf fabricant, Réf fournisseur X...")
        form.addRow("Notes :", self.txt_notes)

        self.chk_primary = QCheckBox("Réf principale (affichée dans les bureaux et tableaux)")
        self.chk_primary.setChecked(bool(self.ref_data.get("Is_Primary")))
        form.addRow("", self.chk_primary)
        layout.addWidget(card)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("Annuler")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setFixedHeight(34)
        btn_cancel.setStyleSheet(OUTLINE_BTN_STYLE)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_save = QPushButton("Enregistrer la Réf")
        btn_save.setIcon(get_duotone_icon("check", 14))
        btn_save.setIconSize(QSize(14, 14))
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setFixedHeight(34)
        btn_save.setStyleSheet(PRIMARY_BTN_STYLE)
        btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def _on_save(self) -> None:
        product_id = self.cb_product.currentData()
        if product_id is None:
            QMessageBox.warning(self, "Produit requis", "Veuillez choisir un produit dans la liste.")
            return
        code = self.txt_ref.text().strip()
        if not code:
            QMessageBox.warning(self, "Champ requis", "Veuillez saisir le code Réf.")
            return
        self.ref_data.update({
            "Product_ID": int(product_id),
            "Ref_Code": code,
            "Notes": self.txt_notes.text().strip(),
            "Is_Primary": self.chk_primary.isChecked(),
        })
        self.accept()


class ProductReferencesTab(QWidget):
    """Master Data tab for registering Réf codes linked to products."""

    references_changed = Signal()

    def __init__(self, data_manager=None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.data_manager = data_manager
        self._refs_cache: List[Dict[str, Any]] = []
        self._init_ui()
        self.load_data()

    # ------------------------------------------------------------------ UI
    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        header = QFrame()
        header.setObjectName("RefsHeaderCard")
        header.setFixedHeight(54)
        header.setStyleSheet("""
            QFrame#RefsHeaderCard { background-color: #FFFFFF; border: 1px solid #DDE3EA; border-radius: 6px; }
            QLabel { border: none; background: transparent; }
        """)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(14, 0, 14, 0)
        h_layout.setSpacing(10)

        ic = QLabel()
        ic.setPixmap(get_duotone_icon("edit_lots", 20).pixmap(20, 20))
        h_layout.addWidget(ic)

        lbl_title = QLabel("Références (Réf) des Produits :")
        lbl_title.setStyleSheet("font-size: 13px; font-weight: 800; color: #1E293B;")
        h_layout.addWidget(lbl_title)

        self.txt_search = QLineEdit()
        self.txt_search.setFixedHeight(34)
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.setPlaceholderText("Rechercher par Réf, produit, marque ou notes...")
        self.txt_search.textChanged.connect(self._apply_search_filter)
        h_layout.addWidget(self.txt_search, stretch=1)

        self.btn_add = QPushButton("+ Nouvelle Réf")
        self.btn_add.setIcon(get_duotone_icon("check", 14))
        self.btn_add.setIconSize(QSize(14, 14))
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.setFixedHeight(34)
        self.btn_add.setStyleSheet(PRIMARY_BTN_STYLE)
        self.btn_add.clicked.connect(self._on_add_reference)
        h_layout.addWidget(self.btn_add)

        btn_refresh = QPushButton("Actualiser")
        btn_refresh.setIcon(get_duotone_icon("refresh", 14))
        btn_refresh.setIconSize(QSize(14, 14))
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setFixedHeight(34)
        btn_refresh.setStyleSheet(OUTLINE_BTN_STYLE)
        btn_refresh.clicked.connect(self.load_data)
        h_layout.addWidget(btn_refresh)
        layout.addWidget(header)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID", "Réf", "Produit", "Marque", "Principale", "Notes"])
        self.table.setStyleSheet(TABLE_STYLE)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.horizontalHeader().setFixedHeight(38)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        self.table.doubleClicked.connect(lambda _idx: self._on_edit_reference())
        self.table.itemSelectionChanged.connect(self._update_action_buttons)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.lbl_count = QLabel("0 Réf")
        self.lbl_count.setStyleSheet("font-size: 11px; font-weight: 700; color: #475569;")
        actions.addWidget(self.lbl_count)
        actions.addStretch()

        self.btn_add_for_product = QPushButton("+ Autre Réf pour ce produit")
        self.btn_add_for_product.setCursor(Qt.PointingHandCursor)
        self.btn_add_for_product.setFixedHeight(32)
        self.btn_add_for_product.setStyleSheet(OUTLINE_BTN_STYLE)
        self.btn_add_for_product.clicked.connect(self._on_add_for_selected_product)
        actions.addWidget(self.btn_add_for_product)

        self.btn_edit = QPushButton("Modifier")
        self.btn_edit.setCursor(Qt.PointingHandCursor)
        self.btn_edit.setFixedHeight(32)
        self.btn_edit.setStyleSheet(OUTLINE_BTN_STYLE)
        self.btn_edit.clicked.connect(self._on_edit_reference)
        actions.addWidget(self.btn_edit)

        self.btn_set_primary = QPushButton("Définir comme principale")
        self.btn_set_primary.setCursor(Qt.PointingHandCursor)
        self.btn_set_primary.setFixedHeight(32)
        self.btn_set_primary.setStyleSheet(OUTLINE_BTN_STYLE)
        self.btn_set_primary.clicked.connect(self._on_set_primary)
        actions.addWidget(self.btn_set_primary)

        self.btn_delete = QPushButton("Supprimer")
        self.btn_delete.setIcon(get_duotone_icon("trash", 13))
        self.btn_delete.setIconSize(QSize(13, 13))
        self.btn_delete.setCursor(Qt.PointingHandCursor)
        self.btn_delete.setFixedHeight(32)
        self.btn_delete.setStyleSheet(DANGER_BTN_STYLE)
        self.btn_delete.clicked.connect(self._on_delete_reference)
        actions.addWidget(self.btn_delete)
        layout.addLayout(actions)
        self._update_action_buttons()

    # ---------------------------------------------------------------- data
    def _manager(self):
        return getattr(self.data_manager, "product_refs", None) if self.data_manager else None

    def _load_products(self) -> List[Dict[str, Any]]:
        if self.data_manager and hasattr(self.data_manager, "products"):
            try:
                return self.data_manager.products.get_all_products() or []
            except Exception as exc:
                logger.error("Failed to load products for Réf dialog: %s", exc)
        return []

    def load_data(self) -> None:
        """Loads every Réf with its linked product."""
        mgr = self._manager()
        refs: List[Dict[str, Any]] = []
        if mgr is not None:
            try:
                refs = mgr.get_all_references() or []
            except Exception as exc:
                logger.error("Failed to load product references: %s", exc)
        self._refs_cache = refs
        self._apply_search_filter()

    def _apply_search_filter(self) -> None:
        search = self.txt_search.text().strip().lower() if hasattr(self, "txt_search") else ""
        if not search:
            self._populate_table(self._refs_cache)
            return
        filtered = [
            r for r in self._refs_cache
            if search in str(r.get("Ref_Code", "")).lower()
            or search in str(r.get("Product_Name", "")).lower()
            or search in str(r.get("Brand_Mark", "")).lower()
            or search in str(r.get("Notes", "") or "").lower()
        ]
        self._populate_table(filtered)

    def _populate_table(self, refs: List[Dict[str, Any]]) -> None:
        self.table.setRowCount(0)
        for row_idx, item in enumerate(refs):
            self.table.insertRow(row_idx)
            is_primary = bool(item.get("Is_Primary"))

            it_id = QTableWidgetItem(str(item.get("Ref_ID") or ""))
            it_id.setTextAlignment(Qt.AlignCenter)
            it_id.setData(Qt.UserRole, item)
            self.table.setItem(row_idx, 0, it_id)

            it_ref = QTableWidgetItem(str(item.get("Ref_Code") or ""))
            it_ref.setFont(QFont("Consolas", 10, QFont.Bold))
            self.table.setItem(row_idx, 1, it_ref)

            it_prod = QTableWidgetItem(str(item.get("Product_Name") or ""))
            it_prod.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self.table.setItem(row_idx, 2, it_prod)

            self.table.setItem(row_idx, 3, QTableWidgetItem(str(item.get("Brand_Mark") or "")))

            it_primary = QTableWidgetItem("Principale" if is_primary else "—")
            it_primary.setTextAlignment(Qt.AlignCenter)
            it_primary.setFont(QFont("Segoe UI", 9, QFont.Bold))
            it_primary.setForeground(QColor("#16A34A" if is_primary else "#94A3B8"))
            self.table.setItem(row_idx, 4, it_primary)

            self.table.setItem(row_idx, 5, QTableWidgetItem(str(item.get("Notes") or "")))
        self.lbl_count.setText(f"{self.table.rowCount()} Réf")
        self._update_action_buttons()

    def _selected_ref(self) -> Optional[Dict[str, Any]]:
        row = self.table.currentRow()
        if row < 0:
            return None
        it = self.table.item(row, 0)
        return it.data(Qt.UserRole) if it else None

    def _update_action_buttons(self) -> None:
        sel = self._selected_ref()
        has_sel = sel is not None
        self.btn_edit.setEnabled(has_sel)
        self.btn_delete.setEnabled(has_sel)
        self.btn_add_for_product.setEnabled(has_sel)
        self.btn_set_primary.setEnabled(has_sel and not bool(sel.get("Is_Primary")))

    # ------------------------------------------------------------- actions
    def _warn_no_backend(self) -> bool:
        if self._manager() is None:
            QMessageBox.warning(self, "Indisponible", "Le gestionnaire de Réf n'est pas disponible.")
            return True
        return False

    def _open_add_dialog(self, preselect_product_id: Optional[int] = None) -> None:
        if self._warn_no_backend():
            return
        products = self._load_products()
        if not products:
            QMessageBox.information(self, "Aucun produit", "Créez d'abord un produit dans l'onglet Produits.")
            return
        dlg = ReferenceDialog(products, preselect_product_id=preselect_product_id, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        data = dlg.ref_data
        try:
            self._manager().add_reference(
                product_id=data["Product_ID"],
                ref_code=data["Ref_Code"],
                is_primary=data.get("Is_Primary", False),
                notes=data.get("Notes", ""),
            )
        except ValueError as err:
            QMessageBox.warning(self, "Réf invalide", str(err))
            return
        except Exception as err:
            QMessageBox.critical(self, "Erreur", str(err))
            return
        self.load_data()
        self.references_changed.emit()

    def _on_add_reference(self) -> None:
        self._open_add_dialog()

    def _on_add_for_selected_product(self) -> None:
        sel = self._selected_ref()
        self._open_add_dialog(int(sel["Product_ID"]) if sel else None)

    def _on_edit_reference(self) -> None:
        sel = self._selected_ref()
        if not sel or self._warn_no_backend():
            return
        dlg = ReferenceDialog(self._load_products(), ref_data=sel, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        data = dlg.ref_data
        try:
            self._manager().update_reference(
                ref_id=int(sel["Ref_ID"]),
                ref_code=data["Ref_Code"],
                is_primary=data.get("Is_Primary", False),
                notes=data.get("Notes", ""),
            )
        except ValueError as err:
            QMessageBox.warning(self, "Réf invalide", str(err))
            return
        except Exception as err:
            QMessageBox.critical(self, "Erreur", str(err))
            return
        self.load_data()
        self.references_changed.emit()

    def _on_set_primary(self) -> None:
        sel = self._selected_ref()
        if not sel or self._warn_no_backend():
            return
        try:
            self._manager().set_primary_reference(int(sel["Ref_ID"]))
        except Exception as err:
            QMessageBox.critical(self, "Erreur", str(err))
            return
        self.load_data()
        self.references_changed.emit()

    def _on_delete_reference(self) -> None:
        sel = self._selected_ref()
        if not sel or self._warn_no_backend():
            return
        reply = QMessageBox.question(
            self,
            "Supprimer la Réf",
            f"Supprimer la Réf « {sel.get('Ref_Code')} » du produit « {sel.get('Product_Name')} » ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            self._manager().delete_reference(int(sel["Ref_ID"]))
        except Exception as err:
            QMessageBox.critical(self, "Erreur", str(err))
            return
        self.load_data()
        self.references_changed.emit()

    def _on_context_menu(self, pos) -> None:
        if self._selected_ref() is None:
            return
        menu = QMenu(self)
        act_edit = menu.addAction("Modifier")
        act_other = menu.addAction("Ajouter une autre Réf pour ce produit")
        act_primary = menu.addAction("Définir comme principale")
        act_primary.setEnabled(not bool(self._selected_ref().get("Is_Primary")))
        menu.addSeparator()
        act_delete = menu.addAction("Supprimer")
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen == act_edit:
            self._on_edit_reference()
        elif chosen == act_other:
            self._on_add_for_selected_product()
        elif chosen == act_primary:
            self._on_set_primary()
        elif chosen == act_delete:
            self._on_delete_reference()
