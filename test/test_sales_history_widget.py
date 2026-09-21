import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from ui.widgets.sales_history import SalesHistoryTab
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False
    QApplication = None
    SalesHistoryTab = None


class FakeClientsManager:
    def get_all_clients(self):
        return []


class FakePOSTerminalsManager:
    def get_all_terminals(self, include_inactive=True):
        return [{"Terminal_ID": 1, "Terminal_Name": "Caisse 1", "Terminal_Code": "POS-01"}]


class FakeSalesManager:
    def __init__(self, records_count=75):
        self.records_count = records_count

    def get_sales_operations_history(self, start_date=None, end_date=None, client_id=None):
        results = []
        for i in range(self.records_count):
            is_cancelled = (i == 0)
            results.append({
                "Row_Type": "Sale",
                "Operation_ID": f"SALE-{i+1}",
                "Invoice_ID": i + 1,
                "Invoice_No": f"INV-{1000 + i}",
                "Invoice_Date": "2026-09-21 14:00:00",
                "Event_Date": "2026-09-21 14:00:00",
                "Operation_Label": "Vente",
                "Client_Name": f"Client {i+1}",
                "Status": "Cancelled" if is_cancelled else "Validated",
                "Due_Date": None,
                "Days_Overdue": None,
                "Terminal_Name": "Caisse 1",
                "Caisse_Label": "Caisse 1",
                "User_Name": "Admin",
                "Payment_Method": "Cash",
                "Payment_Summary": "Cash: 1,000.00",
                "Paid_Amount": 1000.0,
                "Total_Amount_TTC": 1000.0,
                "Total_Cost": 600.0,
                "Total_Profit": 400.0,
            })
        return results


class FakeDataManager:
    def __init__(self, records_count=75):
        self.clients = FakeClientsManager()
        self.pos_terminals = FakePOSTerminalsManager()
        self.sales = FakeSalesManager(records_count)


@unittest.skipUnless(HAS_PYSIDE6, "PySide6 is not installed in the current environment")
class SalesHistoryWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if HAS_PYSIDE6:
            cls.app = QApplication.instance() or QApplication([])

    def test_lazy_loading_and_single_line_bottom_bar(self):
        manager = FakeDataManager(records_count=75)
        widget = SalesHistoryTab(manager)
        self.app.processEvents()

        # Check single thin bottom bar
        self.assertEqual(widget.lbl_status.parent().objectName(), "SalesHistoryBottomBar")
        self.assertEqual(widget.lbl_status.parent().height(), 34)

        # First batch loaded: 50 items out of 75
        self.assertEqual(widget.table.rowCount(), 50)
        self.assertEqual(widget.lbl_status.text(), "50/75")
        self.assertTrue(widget.has_more_data)

        # Check metric calculations across all 75 filtered records
        # 1 cancelled, 74 valid sales
        # Each valid sale: TTC=1000, Cost=600, Profit=400
        # Total sales count: 74
        # Total cost: 74 * 600 = 44,400.00 DA
        # Total revenue: 74 * 1000 = 74,000.00 DA
        # Total profit: 74 * 400 = 29,600.00 DA
        self.assertIn("74", widget.lbl_sales_count.text())
        self.assertIn("44 400,00", widget.lbl_total_cost.text())
        self.assertIn("74 000,00", widget.lbl_total_sales.text())
        self.assertIn("29 600,00", widget.lbl_total_period_profit.text())

        # Load next batch
        widget.load_next_batch()
        self.assertEqual(widget.table.rowCount(), 75)
        self.assertEqual(widget.lbl_status.text(), "75/75")
        self.assertFalse(widget.has_more_data)

        widget.deleteLater()

    def test_permission_restricted_profit_and_cost(self):
        manager = FakeDataManager(records_count=10)
        widget = SalesHistoryTab(manager)
        widget.can_view_profit = False
        widget.update_summary_metrics()

        self.assertIn("accès restreint", widget.lbl_total_cost.text())
        self.assertIn("accès restreint", widget.lbl_total_period_profit.text())
        self.assertIn("9", widget.lbl_sales_count.text())

        widget.deleteLater()


if __name__ == "__main__":
    unittest.main()
