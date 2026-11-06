import unittest
from unittest.mock import MagicMock, patch
from decimal import Decimal
from datetime import date, datetime
import sys
import types

# Ensure mocks for third-party DB connectors if not present
try:
    import mysql.connector
except ImportError:
    fake_mysql = types.ModuleType("mysql")
    fake_connector = types.ModuleType("mysql.connector")
    fake_errorcode = types.ModuleType("mysql.connector.errorcode")
    fake_pooling = types.ModuleType("mysql.connector.pooling")
    class Error(Exception):
        pass
    fake_connector.Error = Error
    fake_connector.errorcode = fake_errorcode
    fake_connector.pooling = fake_pooling
    fake_mysql.connector = fake_connector
    sys.modules["mysql"] = fake_mysql
    sys.modules["mysql.connector"] = fake_connector
    sys.modules["mysql.connector.errorcode"] = fake_errorcode
    sys.modules["mysql.connector.pooling"] = fake_pooling

from database.client_manager import ClientManager
from database.client_payment_manager import ClientPaymentManager
from ui.navigation_permissions import has_navigation_permission, has_permission

try:
    from PySide6.QtWidgets import QApplication, QLabel
    from ui.widgets.sales.searchable_client_combo import SearchableClientComboBox
    HAS_QT = True
except (ImportError, RuntimeError):
    HAS_QT = False


class TestDebtsManagementBackend(unittest.TestCase):
    """
    Tests pour les méthodes de gestion des dettes, de réconciliation comptable (audit)
    et de règlements globaux FIFO / avances libres.
    """

    def setUp(self):
        self.mock_db = MagicMock()
        self.client_manager = ClientManager(self.mock_db)
        self.client_payment_manager = ClientPaymentManager(self.mock_db)

    def test_audit_client_debt_balance_balanced(self):
        """Vérifie que audit_client_debt_balance confirme l'équilibre lorsque Solde = Invoiced - Paid - CreditNotes."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        self.mock_db.get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock responses for audit queries
        mock_cursor.fetchone.side_effect = [
            # 1. SELECT Client profile
            {'Client_ID': 10, 'Client_Name': 'Laboratoire Espoir', 'Credit_Limit': 100000.0, 'Price_Tier': 'Prix_3'},
            # 2. Total Invoiced
            {'total_invoiced': 50000.0, 'count_invoices': 5},
            # 3. Total POS Cash Payments
            {'pos_paid': 10000.0, 'count_pos_payments': 2},
            # 4. Total Client_Payments
            {'client_paid': 15000.0, 'count_client_payments': 3},
            # 5. Total Credit Notes
            {'total_credit_notes': 5000.0, 'count_credit_notes': 1},
            # For get_client_balance inside audit:
            {'Client_ID': 10, 'Client_Name': 'Laboratoire Espoir', 'Credit_Limit': 100000.0, 'Price_Tier': 'Prix_3'},
            {'total_invoiced': 50000.0},
            {'pos_paid': 10000.0},
            {'client_paid': 15000.0},
            {'total_cn': 5000.0}
        ]

        audit = self.client_manager.audit_client_debt_balance(10)

        self.assertTrue(audit['is_balanced'])
        self.assertEqual(audit['current_balance'], 20000.0)
        self.assertEqual(audit['expected_balance'], 20000.0)
        self.assertEqual(audit['discrepancy'], 0.0)
        self.assertEqual(audit['total_invoiced'], 50000.0)
        self.assertEqual(audit['total_paid'], 25000.0)
        self.assertEqual(audit['total_credit_notes'], 5000.0)

    def test_get_client_unpaid_invoices(self):
        """Vérifie la récupération des factures impayées et le calcul des jours de retard."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        self.mock_db.get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            {
                'Invoice_ID': 101,
                'Invoice_No': 'FAC-2026-001',
                'Invoice_Date': '2026-01-01',
                'Due_Date': '2026-01-31',
                'Sale_Type': 'Wholesale',
                'Status': 'Validated',
                'Total_Amount_TTC': 15000.0,
                'Paid_Amount': 5000.0,
                'Remaining_Balance': 10000.0
            }
        ]

        invoices = self.client_manager.get_client_unpaid_invoices(10)
        self.assertEqual(len(invoices), 1)
        inv = invoices[0]
        self.assertEqual(inv['Invoice_No'], 'FAC-2026-001')
        self.assertEqual(inv['Remaining_Balance'], 10000.0)
        self.assertTrue(inv['Is_Overdue'])
        self.assertGreater(inv['Days_Overdue'], 0)

    def test_add_global_payment_fifo_allocation(self):
        """Vérifie que add_global_payment en mode FIFO alloue le montant aux factures les plus anciennes."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        self.mock_db.get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Client profile
        mock_cursor.fetchone.return_value = {'Client_ID': 10, 'Client_Name': 'Clinique Centrale'}

        # Unpaid invoices ordered by date ASC
        mock_cursor.fetchall.return_value = [
            {'Invoice_ID': 101, 'Invoice_No': 'FAC-101', 'Invoice_Date': '2026-01-01', 'Total_Amount_TTC': 10000.0, 'Paid_Amount': 0.0, 'Remaining': 10000.0},
            {'Invoice_ID': 102, 'Invoice_No': 'FAC-102', 'Invoice_Date': '2026-01-15', 'Total_Amount_TTC': 15000.0, 'Paid_Amount': 5000.0, 'Remaining': 10000.0},
        ]
        mock_cursor.lastrowid = 501

        # Pay 15,000 DA: should allocate 10,000 to FAC-101 (Paid), 5,000 to FAC-102 (Validated)
        res = self.client_payment_manager.add_global_payment(
            client_id=10,
            payment_date='2026-09-14',
            amount=15000.0,
            payment_method='Virement',
            auto_allocate_fifo=True
        )

        self.assertIsNotNone(res)
        self.assertTrue(res['success'])
        self.assertEqual(res['total_amount'], 15000.0)
        self.assertEqual(res['allocated_to_invoices'], 15000.0)
        self.assertEqual(res['free_advance'], 0.0)
        self.assertEqual(len(res['invoices_affected']), 2)

        # First invoice fully paid
        inv1 = res['invoices_affected'][0]
        self.assertEqual(inv1['invoice_id'], 101)
        self.assertEqual(inv1['allocated'], 10000.0)
        self.assertEqual(inv1['new_status'], 'Paid')

        # Second invoice partially paid
        inv2 = res['invoices_affected'][1]
        self.assertEqual(inv2['invoice_id'], 102)
        self.assertEqual(inv2['allocated'], 5000.0)
        self.assertEqual(inv2['new_status'], 'Validated')

    def test_add_global_payment_free_advance(self):
        """Vérifie que add_global_payment avec auto_allocate_fifo=False enregistre un acompte libre non lettré."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        self.mock_db.get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = {'Client_ID': 10, 'Client_Name': 'Clinique Centrale'}
        mock_cursor.lastrowid = 601

        res = self.client_payment_manager.add_global_payment(
            client_id=10,
            payment_date='2026-09-14',
            amount=8000.0,
            payment_method='Chèque',
            auto_allocate_fifo=False
        )

        self.assertIsNotNone(res)
        self.assertTrue(res['success'])
        self.assertEqual(res['free_advance'], 8000.0)
        self.assertEqual(res['allocated_to_invoices'], 0.0)

    def test_check_and_update_invoice_status_fully_paid(self):
        """Vérifie que la mise à jour du statut en 'Paid' n'essaie pas d'écrire dans une colonne Paid_Amount."""
        mock_cursor = MagicMock()
        # total_ttc = 5000, current_status = 'Validated'
        mock_cursor.fetchone.side_effect = [
            {'Total_Amount_TTC': 5000.0, 'Status': 'Validated'},
            {'COALESCE(SUM(Amount), 0)': 3000.0},  # cl_paid
            {'COALESCE(SUM(Amount), 0)': 2000.0},  # pos_paid
        ]

        self.client_payment_manager._check_and_update_invoice_status(mock_cursor, 42)

        # Doit exécuter UPDATE Sales_Invoices SET Status = %s WHERE Invoice_ID = %s
        update_calls = [
            call for call in mock_cursor.execute.call_args_list 
            if "UPDATE Sales_Invoices" in call[0][0]
        ]
        self.assertEqual(len(update_calls), 1)
        sql, params = update_calls[0][0]
        self.assertNotIn("Paid_Amount", sql)
        self.assertIn("Status", sql)
        self.assertEqual(params, ('Paid', 42))

    def test_check_and_update_invoice_status_partially_paid(self):
        """Vérifie qu'aucune mise à jour de statut n'est effectuée si la facture reste partiellement payée."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            {'Total_Amount_TTC': 5000.0, 'Status': 'Validated'},
            {'COALESCE(SUM(Amount), 0)': 1000.0},
            {'COALESCE(SUM(Amount), 0)': 1000.0},
        ]

        self.client_payment_manager._check_and_update_invoice_status(mock_cursor, 42)

        update_calls = [
            call for call in mock_cursor.execute.call_args_list 
            if "UPDATE Sales_Invoices" in call[0][0]
        ]
        self.assertEqual(len(update_calls), 0)

    def test_get_debts_analytics(self):
        """Vérifie le calcul des analytics de dettes sans erreur de colonne."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        self.mock_db.get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(self.client_manager, 'get_all_clients_with_balances') as mock_all:
            mock_all.return_value = [
                {'Client_ID': 1, 'Current_Balance': 25000.0},
                {'Client_ID': 2, 'Current_Balance': 0.0},
                {'Client_ID': 3, 'Current_Balance': 15000.0},
            ]
            mock_cursor.fetchone.side_effect = [
                {'overdue_total': 10000.0},       # overdue
                {'month_recovered': 5000.0},      # cl_payments
                {'month_pos': 2500.0},            # pos_payments
            ]

            analytics = self.client_manager.get_debts_analytics()
            self.assertEqual(analytics['total_receivables'], 40000.0)
            self.assertEqual(analytics['debtor_clients_count'], 2)
            self.assertEqual(analytics['overdue_receivables'], 10000.0)
            self.assertEqual(analytics['recovered_this_month'], 7500.0)

    def test_get_debtor_clients_summary(self):
        """Vérifie la génération de la liste synthétique avec statut et badge appropriés."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        self.mock_db.get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            {
                'Client_ID': 1,
                'Client_Name': 'Client A',
                'Phone': '0550000001',
                'City': 'Alger',
                'Credit_Limit': 50000.0,
                'Price_Tier': 'Prix_2',
                'total_invoiced': 80000.0,
                'total_paid': 10000.0,
                'total_credit_notes': 0.0,
                'Current_Balance': 70000.0,
                'Last_Payment_Date': '2026-09-01',
                'Overdue_Count': 1,
                'Unpaid_Count': 2
            },
            {
                'Client_ID': 2,
                'Client_Name': 'Client B',
                'Phone': '0550000002',
                'City': 'Oran',
                'Credit_Limit': 100000.0,
                'Price_Tier': 'Prix_1',
                'total_invoiced': 20000.0,
                'total_paid': 20000.0,
                'total_credit_notes': 0.0,
                'Current_Balance': 0.0,
                'Last_Payment_Date': '2026-09-10',
                'Overdue_Count': 0,
                'Unpaid_Count': 0
            }
        ]

        summary = self.client_manager.get_debtor_clients_summary(filter_status="Tous")
        self.assertEqual(len(summary), 2)
        # Client 1 balance 70,000 > limit 50,000 -> Plafond Dépassé
        self.assertEqual(summary[0]['Status_Badge'], "Plafond Dépassé")
        # Client 2 balance 0 -> Soldé
        self.assertEqual(summary[1]['Status_Badge'], "Soldé")



class TestDebtsNavigationPermissions(unittest.TestCase):
    """Vérifie les permissions de navigation et d'encaissement pour la gestion des créances."""

    def test_nav_debts_fallback_to_nav_sales(self):
        user = {"Permissions": {"nav_sales": True}}
        self.assertTrue(has_navigation_permission(user, "nav_debts"))

    def test_nav_debts_explicit_grant(self):
        user = {"Permissions": {"nav_debts": True}}
        self.assertTrue(has_navigation_permission(user, "nav_debts"))

    def test_nav_debts_granular_view_grant(self):
        user = {"Permissions": {"debts_management:view": True}}
        self.assertTrue(has_navigation_permission(user, "nav_debts"))

    def test_nav_debts_explicit_deny(self):
        user = {
            "Permissions": {
                "nav_sales": True,
                "nav_debts": False
            }
        }
        self.assertFalse(has_navigation_permission(user, "nav_debts"))


class TestSearchableClientComboBox(unittest.TestCase):
    """Tests unitaires du widget d'autocomplétion client par nom et par téléphone."""

    @classmethod
    def setUpClass(cls):
        if HAS_QT:
            cls.app = QApplication.instance() or QApplication([])

    def test_searchable_client_combo_name_and_phone(self):
        if not HAS_QT:
            self.skipTest("PySide6 not available in headless test environment.")

        combo = SearchableClientComboBox()
        clients = [
            {'Client_ID': 1, 'Client_Name': 'Laboratoire Al-Amal', 'Phone': '0550123456'},
            {'Client_ID': 2, 'Client_Name': 'Clinique El-Chifa', 'Phone': '0661987654'},
            {'Client_ID': 3, 'Client_Name': 'Pharmacie Centrale', 'Phone': ''}
        ]
        combo.set_clients(clients)

        # 1. Default should be "Tous les Clients" with ID None
        self.assertEqual(combo.count(), 4)
        self.assertIsNone(combo.get_selected_client_id())

        # 2. Display formats
        self.assertEqual(combo.itemText(0), "Tous les Clients")
        self.assertEqual(combo.itemText(1), "Laboratoire Al-Amal (0550123456)")
        self.assertEqual(combo.itemText(2), "Clinique El-Chifa (0661987654)")
        self.assertEqual(combo.itemText(3), "Pharmacie Centrale")

        # 3. Select programmatically
        combo.set_selected_client_id(2)
        self.assertEqual(combo.get_selected_client_id(), 2)

        # 4. Search resolution by phone digits
        combo.setEditText("0550")
        resolved = combo._resolve_from_text()
        self.assertEqual(resolved, 1)

        # 5. Search resolution by client name text
        combo.setEditText("Chifa")
        resolved_name = combo._resolve_from_text()
        self.assertEqual(resolved_name, 2)


class TestDebtsManagementUI(unittest.TestCase):
    """Tests unitaires des composants UI de la gestion des créances et dialogues de règlement."""

    @classmethod
    def setUpClass(cls):
        if HAS_QT:
            cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        if not HAS_QT:
            self.skipTest("PySide6 not available in headless test environment.")
        self.mock_dm = MagicMock()
        self.mock_dm.clients = MagicMock()
        self.mock_dm.client_payments = MagicMock()
        self.mock_dm.clients.get_debtor_clients_summary.return_value = []
        self.mock_dm.clients.get_debts_analytics.return_value = {
            'total_receivables': 125000.0,
            'overdue_receivables': 45000.0,
            'debtor_clients_count': 5,
            'recovered_this_month': 30000.0
        }
        self.mock_dm.clients.get_all_clients.return_value = []

    def test_debts_summary_bar_and_tables(self):
        from ui.widgets.sales.debts_management_tab import DebtsManagementTab
        tab = DebtsManagementTab(self.mock_dm)

        # Check KPI summary bar labels exist and display correct data
        self.assertIn("125", tab.lbl_kpi_total_receivables.text())
        self.assertIn("45", tab.lbl_kpi_overdue_receivables.text())
        self.assertIn("5 client", tab.lbl_kpi_debtor_count.text())
        self.assertIn("30", tab.lbl_kpi_month_recovered.text())

        # Check font sizes are calm (13px) and not bulky 22px
        self.assertIn("13px", tab.lbl_kpi_overdue_receivables.styleSheet())
        self.assertNotIn("22px", tab.lbl_kpi_overdue_receivables.styleSheet())

        # Check tables column widths and row height
        self.assertEqual(tab.table_clients.columnWidth(9), 200)
        self.assertEqual(tab.table_clients.verticalHeader().defaultSectionSize(), 38)
        self.assertEqual(tab.table_invoices.columnWidth(8), 200)
        self.assertEqual(tab.table_invoices.verticalHeader().defaultSectionSize(), 38)

    def test_global_payment_dialog_styling_and_heights(self):
        from ui.widgets.sales.debts_management_tab import GlobalPaymentDialog
        client_row = {
            'Client_ID': 12,
            'Client_Name': 'Laboratoire BioTest',
            'Current_Balance': 50000.0,
            'Credit_Limit': 100000.0
        }
        dlg = GlobalPaymentDialog(self.mock_dm, client_row)

        # Confirm 100% solid white opaque dialog without backdrop overlay
        self.assertIn("#FFFFFF", dlg.styleSheet())
        self.assertIn("#DDE3EA", dlg.styleSheet())

        # Check input comfortable heights
        self.assertEqual(dlg.edit_date.height(), 38)
        self.assertEqual(dlg.spin_amount.height(), 38)
        self.assertEqual(dlg.cb_method.height(), 38)
        self.assertEqual(dlg.edit_ref.height(), 38)
        self.assertEqual(dlg.edit_notes.height(), 38)

    def test_invoice_payment_dialog_styling_and_heights(self):
        from ui.widgets.sales.invoice_payment_dialog import InvoicePaymentDialog
        inv_row = {
            'Invoice_ID': 201,
            'Invoice_No': 'FAC-2026-0042',
            'Client_ID': 12,
            'Client_Name': 'Laboratoire BioTest',
            'Total_Amount_TTC': 75000.0,
            'Paid_Amount': 25000.0,
            'Invoice_Date': '2026-02-01',
            'Due_Date': '2026-02-28'
        }
        dlg = InvoicePaymentDialog(self.mock_dm, inv_row)

        # Confirm 100% solid white opaque dialog without backdrop overlay
        self.assertIn("#FFFFFF", dlg.styleSheet())
        self.assertIn("#DDE3EA", dlg.styleSheet())

        # Check input comfortable heights
        self.assertEqual(dlg.edit_date.height(), 38)
        self.assertEqual(dlg.spin_amount.height(), 38)
        self.assertEqual(dlg.cb_method.height(), 38)
        self.assertEqual(dlg.edit_ref.height(), 38)
        self.assertEqual(dlg.edit_notes.height(), 38)

    def test_client_statement_dialog_redesign_and_modalless_details(self):
        from ui.widgets.master_data.client_statement_dialog import ClientStatementDialog, TransactionDetailsDialog
        self.mock_dm.clients.get_client_ledger.return_value = {
            'client': {
                'Client_ID': 12,
                'Client_Name': 'Laboratoire BioTest',
                'Phone': '0550112233',
                'City': 'Alger',
                'Price_Tier': 'Prix_2',
                'Credit_Limit': 100000.0
            },
            'initial_balance': 25000.0,
            'final_balance': 65000.0,
            'transactions': [
                {
                    'date': '2026-02-10',
                    'type': 'Facture (Vente Gros)',
                    'reference': 'FAC-2026-0099',
                    'debit': 50000.0,
                    'credit': 0.0,
                    'balance': 75000.0,
                    'notes': 'Vente à terme',
                    'doc_id': 99,
                    'doc_category': 'invoice'
                },
                {
                    'date': '2026-02-15',
                    'type': 'Règlement (Chèque)',
                    'reference': 'REG-45',
                    'debit': 0.0,
                    'credit': 10000.0,
                    'balance': 65000.0,
                    'notes': 'Chèque BNA',
                    'doc_id': 45,
                    'doc_category': 'client_payment'
                }
            ]
        }

        dlg = ClientStatementDialog(self.mock_dm, 12)

        # 1. Check table columns: 8 columns including Actions
        self.assertEqual(dlg.table.columnCount(), 8)
        self.assertEqual(dlg.table.rowCount(), 2)

        # 2. Check no duplicate bottom close button
        self.assertFalse(hasattr(dlg, 'btn_close'))
        self.assertTrue(hasattr(dlg, 'btn_top_close'))

        # 3. Check KPI cards exist with bold contrast
        self.assertIn("25", dlg.card_initial.findChild(QLabel, "val").text())
        self.assertIn("65", dlg.card_final.findChild(QLabel, "val").text())

        # 4. Open non-modal TransactionDetailsDialog
        dlg.open_transaction_details(0)
        self.assertEqual(len(dlg._open_detail_dialogs), 1)
        sub_dlg = dlg._open_detail_dialogs[0]

        # Verify it is modalless (non-modal)
        self.assertFalse(sub_dlg.isModal())
        self.assertIn("#FFFFFF", sub_dlg.styleSheet())
        self.assertIn("#DDE3EA", sub_dlg.styleSheet())

        # Open a second details dialog simultaneously (supports multiple compare windows)
        dlg.open_transaction_details(1)
        self.assertEqual(len(dlg._open_detail_dialogs), 2)
        sub_dlg2 = dlg._open_detail_dialogs[1]
        self.assertFalse(sub_dlg2.isModal())

        # Cleanup
        sub_dlg.close()
        sub_dlg2.close()
        dlg.close()

    def test_tables_vertical_headers_hidden_and_selection_styling(self):
        from ui.widgets.sales.debts_management_tab import DebtsManagementTab
        from PySide6.QtCore import Qt
        tab = DebtsManagementTab(self.mock_dm)

        # 1. Vertical row number headers must be completely hidden
        self.assertFalse(tab.table_clients.verticalHeader().isVisible())
        self.assertFalse(tab.table_invoices.verticalHeader().isVisible())

        # 2. Selection style must preserve readable dark slate text (#0F172A)
        self.assertIn("color: #0F172A", tab.table_clients.styleSheet())
        self.assertIn("#E6F4F1", tab.table_clients.styleSheet())

        # 3. Empty card styling must scope labels with border: none
        self.assertIn("border: none !important;", tab.empty_invoices_card.styleSheet())
        self.assertIn("QFrame#EmptyInvoicesCard", tab.empty_invoices_card.styleSheet())

    def test_client_zero_or_negative_debt_disables_solder_button(self):
        from ui.widgets.sales.debts_management_tab import DebtsManagementTab
        from PySide6.QtWidgets import QPushButton
        from PySide6.QtCore import Qt

        clients_data = [
            {
                'Client_ID': 1,
                'Client_Name': 'azeaze',
                'Phone': '0555001122',
                'Credit_Limit': 0.0,
                'total_invoiced': 0.0,
                'total_paid': 2000.01,
                'Current_Balance': -2000.01,
                'Last_Payment_Date': '2026-03-01',
                'Status_Badge': 'Normal'
            },
            {
                'Client_ID': 2,
                'Client_Name': 'Client Débiteur Actif',
                'Phone': '0666112233',
                'Credit_Limit': 50000.0,
                'total_invoiced': 25000.0,
                'total_paid': 10000.0,
                'Current_Balance': 15000.0,
                'Last_Payment_Date': '2026-02-15',
                'Status_Badge': 'Normal'
            }
        ]
        self.mock_dm.clients.get_debtor_clients_summary.return_value = clients_data
        self.mock_dm.clients.get_client_unpaid_invoices.return_value = []

        tab = DebtsManagementTab(self.mock_dm)
        tab.load_debtors_table()

        # Check badge count
        self.assertIn("2 clients", tab.lbl_master_count_badge.text())

        # Row 0: Solde -2000.01 -> Solder button disabled
        cell_widget_0 = tab.table_clients.cellWidget(0, 9)
        buttons_0 = cell_widget_0.findChildren(QPushButton)
        btn_solder_0 = [b for b in buttons_0 if b.text() == "Solder"][0]
        self.assertFalse(btn_solder_0.isEnabled())
        self.assertEqual(btn_solder_0.cursor().shape(), Qt.ForbiddenCursor)

        # Row 1: Solde 15000.0 -> Solder button enabled
        cell_widget_1 = tab.table_clients.cellWidget(1, 9)
        buttons_1 = cell_widget_1.findChildren(QPushButton)
        btn_solder_1 = [b for b in buttons_1 if b.text() == "Solder"][0]
        self.assertTrue(btn_solder_1.isEnabled())
        self.assertEqual(btn_solder_1.cursor().shape(), Qt.PointingHandCursor)

    def test_filter_bar_reset_and_actions(self):
        from ui.widgets.sales.debts_management_tab import DebtsManagementTab
        tab = DebtsManagementTab(self.mock_dm)

        # Change filter values
        tab.spin_min_debt.setValue(5000.0)
        tab.cb_status_filter.setCurrentIndex(2)

        # Trigger reset
        tab.btn_reset.click()

        # Verify default values restored
        self.assertEqual(tab.spin_min_debt.value(), 0.0)
        self.assertEqual(tab.cb_status_filter.currentIndex(), 0)

    def test_detail_section_empty_state_and_global_pay_button(self):
        from ui.widgets.sales.debts_management_tab import DebtsManagementTab
        tab = DebtsManagementTab(self.mock_dm)

        # 1. Client with zero unpaid invoices
        client_clean = {
            'Client_ID': 99,
            'Client_Name': 'Client À Jour',
            'Current_Balance': 0.0
        }
        self.mock_dm.clients.get_client_unpaid_invoices.return_value = []
        tab._load_detail_invoices(client_clean)

        self.assertEqual(tab.detail_stack.currentIndex(), 1)
        self.assertFalse(tab.btn_detail_global_pay.isEnabled())
        self.assertIn("Aucune créance impayée", tab.lbl_empty_title.text())

        # 2. Client with unpaid invoices
        client_debtor = {
            'Client_ID': 88,
            'Client_Name': 'Client Débiteur',
            'Current_Balance': 10000.0
        }
        self.mock_dm.clients.get_client_unpaid_invoices.return_value = [
            {
                'Invoice_ID': 501,
                'Invoice_No': 'FAC-2026-0501',
                'Invoice_Date': '2026-03-01',
                'Due_Date': '2026-03-15',
                'Days_Overdue': 0,
                'Is_Overdue': False,
                'Total_Amount_TTC': 10000.0,
                'Paid_Amount': 0.0,
                'Remaining_Balance': 10000.0,
                'Status': 'Validated'
            }
        ]
        tab._load_detail_invoices(client_debtor)

        self.assertEqual(tab.detail_stack.currentIndex(), 0)
        self.assertTrue(tab.btn_detail_global_pay.isEnabled())
        self.assertEqual(tab.table_invoices.rowCount(), 1)


if __name__ == "__main__":
    unittest.main()
