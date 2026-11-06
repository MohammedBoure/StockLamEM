# ui/widgets/sales_history/sale_details_dialog.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QFormLayout, QAbstractItemView, QSpinBox, QMessageBox,
    QInputDialog, QWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ui.formatting import format_money
from .pdf_export import export_invoice_to_pdf


class SaleDetailsDialog(QDialog):
    """
    Dialogue modal affichant le détail complet des lignes d'une facture de vente,
    avec options d'annulation, modification de quantité, restitution de stock et réimpression PDF.
    """

    def __init__(self, data_manager, invoice_data, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.invoice_data = invoice_data
        self.parent_tab = parent  # To trigger refresh
        sale_ref = invoice_data.get('Invoice_No') or f"#{invoice_data['Invoice_ID']}"
        self.setWindowTitle(f"Détails de la Vente {sale_ref}")
        self.resize(850, 500)
        self.details_list = []
        self.init_ui()

    def _has_permission(self, permission):
        checker = getattr(self.window(), "has_permission", None)
        if callable(checker):
            return bool(checker(permission))
        return True

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # Invoice summary
        summary_group = QGroupBox("Résumé de la Facture")
        form = QFormLayout(summary_group)

        client_name = self.invoice_data.get('Client_Name')
        if not client_name:
            client_name = "Vente comptoir"

        form.addRow("<b>Client :</b>", QLabel(client_name))
        form.addRow("<b>Date :</b>", QLabel(str(self.invoice_data.get('Invoice_Date'))))
        form.addRow("<b>Statut :</b>", QLabel(self.invoice_data.get('Status', '')))

        self.lbl_total = QLabel(format_money(self.invoice_data.get('Total_Amount_TTC', 0)) + " DA")
        form.addRow("<b>Total TTC :</b>", self.lbl_total)

        profit = float(self.invoice_data.get('Total_Profit') or 0)
        self.lbl_profit = QLabel(format_money(profit) + " DA")
        self.lbl_profit.setStyleSheet("color: #27ae60; font-weight: bold;" if profit > 0 else "color: #e74c3c; font-weight: bold;")
        if self._has_permission("act_pos_view_profit"):
            form.addRow("<b>Fayda (Profit) :</b>", self.lbl_profit)

        layout.addWidget(summary_group)

        # Table for products
        self.table = QTableWidget()
        cols = ["Produit", "Lot", "Qté", "Prix Vente HT", "Remise %", "TVA %", "Total Ligne TTC", "Profit", "Actions"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)

        layout.addWidget(self.table)

        btn_row = QHBoxLayout()

        self.btn_cancel_sale = QPushButton("🔴 Annuler la Facture")
        self.btn_cancel_sale.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; padding: 5px;")
        self.btn_cancel_sale.clicked.connect(self.cancel_sale)

        if self.invoice_data.get('Status') == 'Cancelled':
            self.btn_cancel_sale.setEnabled(False)

        self.btn_save = QPushButton("💾 Sauvegarder les modifications")
        self.btn_save.clicked.connect(self.save_changes)

        self.btn_pdf = QPushButton("🖨️ Imprimer Facture")
        self.btn_pdf.setStyleSheet("background-color: #3498db; color: white; font-weight: bold; padding: 5px;")
        self.btn_pdf.clicked.connect(self.print_pdf)

        self.btn_return = QPushButton("Retour / Remboursement")
        self.btn_return.setStyleSheet("background-color: #f59e0b; color: white; font-weight: bold; padding: 5px;")
        self.btn_return.clicked.connect(self.create_return_for_selected_line)
        self.btn_return.setEnabled(hasattr(self.data_manager, "pos_features"))

        self.btn_audit = QPushButton("Audit")
        self.btn_audit.clicked.connect(self.show_audit_timeline)

        btn_close = QPushButton("Fermer")
        btn_close.clicked.connect(self.accept)

        btn_row.addWidget(self.btn_cancel_sale)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_return)
        btn_row.addWidget(self.btn_audit)
        btn_row.addWidget(self.btn_pdf)
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)

        self.load_details()

    def load_details(self):
        self.details_list = self.data_manager.sales.get_invoice_details_with_profit(self.invoice_data['Invoice_ID'])
        self.table.setRowCount(0)

        for r, d in enumerate(self.details_list):
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(d.get('Product_Name', '---')))
            self.table.setItem(r, 1, QTableWidgetItem(d.get('Lot_Number', '---')))

            # Editable Qty SpinBox
            qty_spin = QSpinBox()
            qty_spin.setRange(1, 99999)
            qty_spin.setValue(int(d.get('Qty_Sold', 1)))
            qty_spin.setAlignment(Qt.AlignCenter)
            qty_spin.setProperty("detail_id", d['Detail_ID'])
            qty_spin.setProperty("old_qty", int(d.get('Qty_Sold', 1)))
            qty_spin.setStyleSheet("min-height: 25px;")

            qty_container = QWidget()
            qty_container.setStyleSheet("background: transparent;")
            qty_layout = QHBoxLayout(qty_container)
            qty_layout.setContentsMargins(2, 2, 2, 2)
            qty_layout.addWidget(qty_spin, alignment=Qt.AlignCenter)

            self.table.setCellWidget(r, 2, qty_container)

            self.table.setItem(r, 3, QTableWidgetItem(format_money(d.get('Unit_Price_HT', 0))))

            remise = float(d.get('Discount_Percent', 0))
            tva = float(d.get('TVA_Percent', 0))

            remise_item = QTableWidgetItem(f"{remise}%")
            if remise > 0:
                remise_item.setForeground(Qt.darkGreen)
            self.table.setItem(r, 4, remise_item)

            tva_item = QTableWidgetItem(f"{tva}%")
            self.table.setItem(r, 5, tva_item)

            self.table.setItem(r, 6, QTableWidgetItem(format_money(d.get('Line_Total_TTC', 0))))

            profit = float(d.get('Line_Profit') or 0)
            profit_item = QTableWidgetItem(format_money(profit))
            profit_item.setForeground(Qt.darkGreen if profit > 0 else Qt.red)
            profit_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table.setItem(r, 7, profit_item)

            # Actions
            btn_del = QPushButton("🗑️")
            btn_del.setFixedSize(30, 30)
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.setStyleSheet("padding: 0; margin: 2px; border-radius: 5px;")
            btn_del.clicked.connect(lambda checked=False, d_id=d['Detail_ID']: self.delete_detail(d_id))

            if self.invoice_data.get('Status') == 'Cancelled' or d.get('Is_Theoretical_Order_Line') or not d.get('Detail_ID'):
                qty_spin.setEnabled(False)
                qty_container.setEnabled(False)
                btn_del.setEnabled(False)
                if d.get('Is_Theoretical_Order_Line') or not d.get('Detail_ID'):
                    qty_spin.setToolTip("Ligne de commande Bureaux (gérée via Bon de Sortie / Bon de Retour)")
                    btn_del.setToolTip("Utilisez le Bon de Retour en Caisse pour retourner un article avec N° de Série")
                if self.invoice_data.get('Status') == 'Cancelled':
                    self.btn_save.setEnabled(False)

            action_container = QWidget()
            action_container.setStyleSheet("background: transparent;")
            action_layout = QHBoxLayout(action_container)
            action_layout.setContentsMargins(2, 2, 2, 2)
            action_layout.addWidget(btn_del, alignment=Qt.AlignCenter)

            self.table.setCellWidget(r, 8, action_container)

        has_remise = any(float(d.get('Discount_Percent', 0)) > 0 for d in self.details_list)
        has_tva = any(float(d.get('TVA_Percent', 0)) > 0 for d in self.details_list)
        self.table.setColumnHidden(4, not has_remise)
        self.table.setColumnHidden(5, not has_tva)
        self.table.setColumnHidden(7, not self._has_permission("act_pos_view_profit"))

    def create_return_for_selected_line(self):
        checker = getattr(self.window(), "has_permission", None)
        if checker and not checker("act_pos_return"):
            QMessageBox.warning(self, "Autorisation", "Autorisation refusée pour créer un retour.")
            return
        row = self.table.currentRow()
        if row < 0 or row >= len(self.details_list):
            QMessageBox.warning(self, "Retour", "Sélectionnez une ligne à retourner.")
            return
        detail = self.details_list[row]
        max_qty = float(detail.get("Qty_Sold") or 0)
        qty, ok = QInputDialog.getDouble(
            self, "Quantité retournée", "Quantité:", max_qty, 0.01, max_qty, 2
        )
        if not ok:
            return
        labels = ["Espèces", "Carte", "Virement", "Versement", "Autre", "Crédit client"]
        values = ["Cash", "Card", "Transfer", "Versement", "Other", "Credit"]
        label, ok = QInputDialog.getItem(self, "Remboursement", "Moyen:", labels, 0, False)
        if not ok:
            return
        reason, ok = QInputDialog.getText(self, "Motif du retour", "Motif:")
        if not ok:
            return
        success, result = self.data_manager.pos_features.create_sale_return(
            self.invoice_data.get("Invoice_ID"),
            [{"original_detail_id": detail.get("Detail_ID"), "qty_returned": qty}],
            refund_method=values[labels.index(label)],
            reason=reason.strip() or "Retour client",
            user_id=self._current_user_id(),
        )
        if success:
            QMessageBox.information(self, "Retour", f"Retour enregistré: {result.get('return_no')}")
            if hasattr(self.parent_tab, "load_sales_data"):
                self.parent_tab.load_sales_data()
            self.accept()
        else:
            QMessageBox.warning(self, "Retour", result.get("message", "Impossible d'enregistrer le retour."))

    def show_audit_timeline(self):
        checker = getattr(self.window(), "has_permission", None)
        if checker and not checker("act_pos_audit"):
            QMessageBox.warning(self, "Autorisation", "Autorisation refusée pour consulter l'audit.")
            return
        events = self.data_manager.pos_features.list_audit_events(
            "Sales_Invoice", self.invoice_data.get("Invoice_ID"), limit=100
        )
        if not events:
            QMessageBox.information(self, "Audit", "Aucun événement enregistré pour cette facture.")
            return
        lines = []
        for event in events:
            lines.append(
                f"{event.get('Created_At')} | {event.get('Action')} | "
                f"{event.get('User_Name') or '-'} | {event.get('Details') or ''}"
            )
        QMessageBox.information(self, "Timeline audit", "\n".join(lines))

    def _current_user_id(self):
        try:
            from database.system_logger import active_user_id
            return active_user_id.get()
        except Exception:
            return None

    def save_changes(self):
        checker = getattr(self.window(), "has_permission", None)
        if checker and not checker("act_edit_sale"):
            QMessageBox.warning(self, "Autorisation", "Autorisation refusée pour modifier cette facture.")
            return
        changes_made = False
        for r in range(self.table.rowCount()):
            container = self.table.cellWidget(r, 2)
            if container:
                spin = container.layout().itemAt(0).widget()
                detail_id = spin.property("detail_id")
                old_qty = spin.property("old_qty")
                new_qty = spin.value()

                if old_qty != new_qty:
                    success = self.data_manager.sales.update_invoice_detail_qty(
                        detail_id, new_qty, self.data_manager.batches
                    )
                    if not success:
                        QMessageBox.warning(self, "Erreur", "Échec de la mise à jour pour la ligne. Vérifiez le stock disponible.")
                    else:
                        changes_made = True

        if changes_made:
            QMessageBox.information(self, "Succès", "Les modifications ont été sauvegardées avec succès.")
            if hasattr(self.parent_tab, 'load_sales_data'):
                self.parent_tab.load_sales_data()
            self.accept()

    def delete_detail(self, detail_id):
        reply = QMessageBox.question(
            self, "Confirmation",
            "Voulez-vous vraiment supprimer ce produit de la facture ? Le stock sera restitué.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success = self.data_manager.sales.remove_invoice_detail(detail_id, self.data_manager.batches)
            if success:
                QMessageBox.information(self, "Succès", "Produit supprimé et stock restitué.")
                if hasattr(self.parent_tab, 'load_sales_data'):
                    self.parent_tab.load_sales_data()
                self.accept()
            else:
                QMessageBox.warning(self, "Erreur", "Échec de la suppression.")

    def cancel_sale(self):
        checker = getattr(self.window(), "has_permission", None)
        if checker and not checker("act_cancel_sale"):
            QMessageBox.warning(self, "Autorisation", "Autorisation refusée pour annuler cette facture.")
            return
        reply = QMessageBox.question(
            self, "Annuler la Vente",
            "Voulez-vous annuler complètement cette vente ? Tous les produits seront remis en stock.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success = self.data_manager.sales.cancel_invoice(self.invoice_data['Invoice_ID'], self.data_manager.batches)
            if success:
                QMessageBox.information(self, "Succès", "Vente annulée et stock restitué.")
                if hasattr(self.parent_tab, 'load_sales_data'):
                    self.parent_tab.load_sales_data()
                self.accept()
            else:
                QMessageBox.warning(self, "Erreur", "Échec de l'annulation.")

    def print_pdf(self):
        checker = getattr(self.window(), "has_permission", None)
        if checker and not checker("act_pos_reprint_invoice"):
            QMessageBox.warning(self, "Autorisation", "Autorisation refusée pour réimprimer cette facture.")
            return
        export_invoice_to_pdf(self.data_manager, self.invoice_data, self)
