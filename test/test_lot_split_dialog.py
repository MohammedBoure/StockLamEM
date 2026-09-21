import os
import unittest
from datetime import date, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from ui.widgets.wholesale_sales.lot_split_dialog import MultiLotSelectionDialog
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False
    QApplication = None
    MultiLotSelectionDialog = None


class TestMultiLotSelectionDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if HAS_PYSIDE6:
            cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        if not HAS_PYSIDE6:
            self.skipTest("PySide6 not available")

        self.today = date.today()
        self.sample_batches = [
            {
                "Batch_ID": 101,
                "Batch_Number": "LOT-2026-A",
                "Expiry_Date": (self.today + timedelta(days=20)).strftime("%Y-%m-%d"),
                "Location_Name": "Rayon A1",
                "Quantity_Current": 15.0,
                "Selling_Price_HT": 120.0,
            },
            {
                "Batch_ID": 102,
                "Batch_Number": "LOT-2026-B",
                "Expiry_Date": (self.today + timedelta(days=90)).strftime("%Y-%m-%d"),
                "Location_Name": "Rayon A2",
                "Quantity_Current": 25.0,
                "Selling_Price_HT": 120.0,
            },
            {
                "Batch_ID": 103,
                "Batch_Number": "LOT-2026-C",
                "Expiry_Date": (self.today - timedelta(days=5)).strftime("%Y-%m-%d"),
                "Location_Name": "Zone Périmée",
                "Quantity_Current": 10.0,
                "Selling_Price_HT": 120.0,
            }
        ]

    def test_dialog_instantiation_and_opaque_attributes(self):
        """Dialog must be modal, have opaque paint event and styled background set to prevent bleed-through."""
        dialog = MultiLotSelectionDialog(
            parent=None,
            product_name="Doliprane 1000mg",
            batches=self.sample_batches,
            requested_qty=20.0
        )

        self.assertTrue(dialog.isModal())
        self.assertTrue(dialog.testAttribute(Qt.WA_StyledBackground))
        self.assertTrue(dialog.testAttribute(Qt.WA_OpaquePaintEvent))
        self.assertTrue(dialog.autoFillBackground())
        self.assertEqual(dialog.spin_target_qty.value(), 20.0)
        self.assertEqual(dialog.table.rowCount(), 3)
        dialog.close()

    def test_fifo_allocation_logic(self):
        """FIFO allocates requested quantity into earliest available batches automatically on launch and on button click."""
        dialog = MultiLotSelectionDialog(
            parent=None,
            product_name="Doliprane 1000mg",
            batches=self.sample_batches,
            requested_qty=20.0
        )

        # On launch, FIFO auto-allocated 20 units
        # Batch 103 is oldest/expired: takes 10 units
        # Batch 101 is next: takes 10 units
        total_allocated = sum(s.value() for _, s in dialog.spinboxes)
        self.assertEqual(total_allocated, 20.0)
        self.assertEqual(dialog.lbl_allocated_val.text(), "20")
        self.assertEqual(dialog.lbl_remaining_val.text(), "0 (Complet)")

        # Reset, then click FIFO again
        dialog.btn_reset.click()
        self.assertEqual(sum(s.value() for _, s in dialog.spinboxes), 0.0)

        dialog.btn_fifo.click()
        self.assertEqual(sum(s.value() for _, s in dialog.spinboxes), 20.0)

        # Validate and accept
        dialog._validate_and_accept()
        allocations = dialog.get_allocations()
        self.assertEqual(sum(qty for _, qty in allocations), 20.0)
        dialog.close()

    def test_reset_allocations(self):
        """Reset button must zero out all spinboxes and update summary cards."""
        dialog = MultiLotSelectionDialog(
            parent=None,
            product_name="Doliprane 1000mg",
            batches=self.sample_batches,
            requested_qty=20.0
        )

        self.assertGreater(sum(s.value() for _, s in dialog.spinboxes), 0)

        # Click reset
        dialog.btn_reset.click()
        self.assertEqual(sum(s.value() for _, s in dialog.spinboxes), 0.0)
        self.assertEqual(dialog.lbl_allocated_val.text(), "0")
        self.assertEqual(dialog.lbl_remaining_val.text(), "20")
        dialog.close()

    def test_manual_allocation_and_card_color_updates(self):
        """Manual spinbox changes correctly update remaining quantity and status styling."""
        dialog = MultiLotSelectionDialog(
            parent=None,
            product_name="Doliprane 1000mg",
            batches=self.sample_batches,
            requested_qty=10.0
        )

        # Reset first to test individual manual adjustments
        dialog.btn_reset.click()
        self.assertEqual(sum(s.value() for _, s in dialog.spinboxes), 0.0)

        spin_0 = dialog.spinboxes[0][1]
        # Allocate 5
        spin_0.setValue(5.0)
        self.assertEqual(dialog.lbl_allocated_val.text(), "5")
        self.assertEqual(dialog.lbl_remaining_val.text(), "5")

        # Allocate exact 10
        spin_0.setValue(10.0)
        self.assertEqual(dialog.lbl_allocated_val.text(), "10")
        self.assertEqual(dialog.lbl_remaining_val.text(), "0 (Complet)")

        # Allocate 15 (more than 10 requested) -> over-allocated card shows excess
        spin_0.setValue(15.0)
        self.assertEqual(dialog.lbl_allocated_val.text(), "15")
        self.assertIn("+5", dialog.lbl_remaining_val.text())
        dialog.close()

    def test_modal_clean_formatting_and_elements(self):
        """Test modal has solid white opaque background, no backdrop overlay, 32px centered spinboxes, and full button width."""
        dialog = MultiLotSelectionDialog(
            parent=None,
            product_name="Doliprane 1000mg",
            batches=self.sample_batches,
            requested_qty=10.0
        )

        # 1. 100% Opaque Solid White Background
        self.assertTrue(dialog.testAttribute(Qt.WA_OpaquePaintEvent))
        self.assertTrue(dialog.testAttribute(Qt.WA_StyledBackground))
        self.assertTrue(dialog.autoFillBackground())
        self.assertIn("#FFFFFF", dialog.styleSheet())
        self.assertIn("#DDE3EA", dialog.styleSheet())

        # 2. Validation button has full text and adequate width
        self.assertEqual(dialog.btn_confirm.text(), "Valider la Répartition (F10 / Enter)")
        self.assertGreaterEqual(dialog.btn_confirm.minimumWidth(), 260)
        self.assertEqual(dialog.btn_confirm.height(), 38)

        # 3. Column 5 Spinbox has explicit 32px height and centered alignment
        self.assertEqual(dialog.table.columnWidth(5), 150)
        spin_0 = dialog.spinboxes[0][1]
        self.assertEqual(spin_0.height(), 32)
        self.assertEqual(spin_0.alignment(), Qt.AlignCenter)

        dialog.close()


if __name__ == "__main__":
    unittest.main()
