# -*- coding: utf-8 -*-
"""Tests verifying minimalist, distraction-free SAVReceptionDialog and SAVWorkspaceTab UI."""

import os
import sys
import unittest
from unittest.mock import MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PYTEST_CURRENT_TEST"] = "1"

from PySide6.QtWidgets import QApplication, QFrame, QHeaderView

from ui.widgets.sav.sav_kanban_view import SAVReceptionDialog
from ui.widgets.sav.sav_workspace_view import SAVWorkspaceTab

app = QApplication.instance() or QApplication(sys.argv)


class TestSAVMinimalUI(unittest.TestCase):
    def setUp(self):
        self.dm = MagicMock()
        self.dm.current_user = {"User_ID": 1, "Role": "Admin"}
        self.dm.clients.get_all_clients.return_value = [
            {"Client_ID": 12, "Client_Name": "Amine Saidi"},
        ]
        self.dm.sav.get_all_sav_tickets.return_value = []
        self.dm.sav.find_bon_by_bon_rouge.return_value = {
            "Client_ID": 12,
            "Client_Name": "Amine Saidi",
            "Client_Phone": "0550112233",
            "Order_Number": "BC-2026-001",
            "Order_Date": "2026-11-10",
            "items": [
                {
                    "Brand_Mark": "LG",
                    "Product_Name": "Lave-Linge 9Kg",
                    "Barcode": "REF-LG-9KG",
                    "Serial_Number": "SN-LG-9001",
                    "Serial_Status": "DISPATCHED",
                }
            ],
        }

    def tearDown(self):
        app.processEvents()

    def test_sav_reception_dialog_minimal_clean_styling_and_one_step_selection(self):
        dlg = SAVReceptionDialog(data_manager=self.dm)

        # Clean tab labels without Qt '&' mnemonic corruption (_Bons)
        tab_titles = [dlg.lookup_tabs.tabText(i) for i in range(dlg.lookup_tabs.count())]
        self.assertEqual(tab_titles, ["Bon Rouge", "Recherche Client"])

        # No unscoped generic QFrame border rule leaking onto QLabel widgets
        self.assertNotIn("QFrame {", dlg.styleSheet())
        intake_section = dlg.findChild(QFrame, "SAVIntakeSection")
        self.assertIsNotNone(intake_section)
        self.assertIn("QFrame#SAVIntakeSection QLabel", intake_section.styleSheet())

        # Empty optional intake fields with placeholders (no hardcoded fake text)
        self.assertEqual(dlg.txt_symptom.text(), "")
        self.assertEqual(dlg.txt_cosmetic.text(), "")
        self.assertEqual(dlg.txt_acc.text(), "")
        self.assertTrue(bool(dlg.txt_symptom.placeholderText()))

        # Table headers configured cleanly without clipping
        hdr = dlg.tbl_br_items.horizontalHeader()
        self.assertGreaterEqual(hdr.minimumSectionSize(), 95)
        self.assertEqual(hdr.sectionResizeMode(1), QHeaderView.Stretch)
        self.assertEqual(hdr.sectionResizeMode(2), QHeaderView.ResizeToContents)

        # Bon Rouge lookup with 1 item auto-populates serial & client in 1 step
        dlg.txt_bon_rouge.setText("BC-2026-001")
        dlg._lookup_bon_rouge()
        self.assertEqual(dlg.tbl_br_items.rowCount(), 1)
        self.assertEqual(dlg.txt_serial.text(), "SN-LG-9001")
        self.assertEqual(dlg.cbo_client.currentData(), 12)
        self.assertIn("Lave-Linge 9Kg", dlg.lbl_serial_info.text())

        dlg.deleteLater()

    def test_sav_workspace_has_no_emojis_in_tabs_or_kpis(self):
        ws = SAVWorkspaceTab(data_manager=self.dm)
        emojis = ("📋", "📥", "🔧", "✅", "📦", "⚠️")
        for i in range(ws.tabs.count()):
            text = ws.tabs.tabText(i)
            for e in emojis:
                self.assertNotIn(e, text)
        self.assertEqual(
            [ws.tabs.tabText(i) for i in range(ws.tabs.count())],
            [
                "Toutes (0)",
                "Réception (0)",
                "Atelier (0)",
                "Prêts Restitution (0)",
                "Clôturés (0)",
                "Irréparables (0)",
            ],
        )
        # Redundant top KPI strip is hidden to eliminate duplicate information clutter
        self.assertTrue(ws.lbl_kpi_total.parentWidget().isHidden())
        for lbl in (
            ws.lbl_kpi_total,
            ws.lbl_kpi_received,
            ws.lbl_kpi_sent,
            ws.lbl_kpi_returned,
            ws.lbl_kpi_closed,
            ws.lbl_kpi_irreparable,
        ):
            for e in emojis:
                self.assertNotIn(e, lbl.text())

        tbl = ws._stage_tables["ALL"]
        hdr = tbl.horizontalHeader()
        self.assertEqual(hdr.sectionResizeMode(3), QHeaderView.Stretch)
        self.assertEqual(hdr.sectionResizeMode(8), QHeaderView.ResizeToContents)
        ws.deleteLater()


if __name__ == "__main__":
    unittest.main()
