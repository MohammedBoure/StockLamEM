# -*- coding: utf-8 -*-
"""
test/test_order_desk_payment_labels.py
======================================
Unit tests for Task #11 (Bureaux -> 1. Commandes):
- Verifies corrected French payment option button labels:
  * "Paiement complet" (BON_C)
  * "Paiement à la livraison" (BON_LIVRAISON)
  * "Paiement à crédit" (BON_CREDIT)
- Verifies each button dispatches the expected underlying bond type to _submit_order.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from ui.widgets.appliance_desks.order_desk_view import OrderDeskWidget


class TestOrderDeskPaymentLabels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["PYTEST_CURRENT_TEST"] = "1"
        cls.app = QApplication.instance() or QApplication([])

    def _make_mock_data_manager(self):
        dm = MagicMock()
        dm.manufacturers.get_all_manufacturers.return_value = []
        dm.families.get_all_families.return_value = []
        dm.colors.get_all_colors.return_value = []
        dm.clients.get_all_clients.return_value = []
        dm.serials.get_catalog_with_theoretical_stock.return_value = []
        return dm

    def test_payment_button_labels_and_actions(self):
        widget = OrderDeskWidget(self._make_mock_data_manager())
        try:
            self.assertEqual(widget.btn_bon_c.text(), "Paiement complet")
            self.assertEqual(widget.btn_livraison.text(), "Paiement à la livraison")
            self.assertEqual(widget.btn_credit.text(), "Paiement à crédit")

            with patch.object(widget, "_submit_order") as mock_submit:
                widget.btn_bon_c.click()
                widget.btn_livraison.click()
                widget.btn_credit.click()

                self.assertEqual(
                    [call.args[0] for call in mock_submit.call_args_list],
                    ["BON_C", "BON_LIVRAISON", "BON_CREDIT"],
                )
        finally:
            widget.deleteLater()


if __name__ == "__main__":
    unittest.main()
