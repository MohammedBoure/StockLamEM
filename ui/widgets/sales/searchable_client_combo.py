# ui/widgets/sales/searchable_client_combo.py

import logging
from PySide6.QtWidgets import QComboBox, QCompleter, QLineEdit
from PySide6.QtCore import Qt, Signal


class SearchableClientComboBox(QComboBox):
    """
    Searchable autocomplete combobox for Client selection.
    Matches in real-time by both Client Name and Phone Number.
    Formats items as: 'Nom Client (Téléphone)'.
    """

    client_changed = Signal(object)  # Emits client_id (int or None)

    def __init__(self, parent=None, placeholder="🔍 Tous les Clients (Nom / Tél)..."):
        super().__init__(parent)
        self._placeholder = placeholder
        self._clients_list = []
        self._selected_client_id = None
        self._init_ui()

    def _init_ui(self):
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.setMinimumWidth(200)

        line_edit = self.lineEdit()
        if line_edit:
            line_edit.setPlaceholderText(self._placeholder)
            line_edit.returnPressed.connect(self._on_return_pressed)

        completer = self.completer()
        if completer:
            completer.setFilterMode(Qt.MatchContains)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setCompletionMode(QCompleter.PopupCompletion)

        self.activated.connect(self._on_activated)
        self.currentIndexChanged.connect(self._on_index_changed)

        self.setStyleSheet("""
            QComboBox {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6px;
                padding: 3px 8px;
                font-size: 12px;
                min-height: 28px;
            }
            QComboBox:focus {
                border-color: #0E7471;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                border: 1px solid #DDE3EA;
                selection-background-color: #0E7471;
                selection-color: #FFFFFF;
                padding: 4px;
            }
        """)

    def set_clients(self, clients):
        """
        Populate the dropdown from a list of client dicts.
        Item format: 'Nom Client (Téléphone)'
        Special item: 'Tous les Clients' (ID: None)
        """
        self.blockSignals(True)
        self.clear()
        self._clients_list = clients or []

        # Special "All Clients" item
        self.addItem("Tous les Clients", None)

        for c in self._clients_list:
            c_id = c.get('Client_ID')
            c_name = str(c.get('Client_Name') or '').strip()
            c_phone = str(c.get('Phone') or '').strip()

            if c_phone:
                display = f"{c_name} ({c_phone})"
            else:
                display = c_name

            self.addItem(display, c_id)

        self.blockSignals(False)
        self.setCurrentIndex(0)
        self._selected_client_id = None

    def get_selected_client_id(self):
        """
        Returns the selected client ID (int) or None if 'Tous les Clients' is selected.
        """
        idx = self.currentIndex()
        if idx < 0:
            return self._resolve_from_text()
        data = self.itemData(idx)
        return data

    def set_selected_client_id(self, client_id):
        """Programmatically select a client by ID."""
        self.blockSignals(True)
        if client_id is None or client_id == -1:
            self.setCurrentIndex(0)
            self._selected_client_id = None
            self.blockSignals(False)
            return

        for idx in range(self.count()):
            if self.itemData(idx) == client_id:
                self.setCurrentIndex(idx)
                self._selected_client_id = client_id
                self.blockSignals(False)
                return

        self.blockSignals(False)

    def _resolve_from_text(self):
        """
        Resolves the text currently typed in the lineEdit to a client ID.
        If numeric: searches specifically by phone number.
        If alphanumeric: searches by name, then phone.
        """
        raw_text = self.currentText().strip()
        if not raw_text or raw_text.lower() in ("tous", "tous les clients", "-"):
            return None

        # Check if text matches current item text
        idx = self.findText(raw_text, Qt.MatchExactly)
        if idx >= 0:
            return self.itemData(idx)

        # Check if user typed numeric phone number
        is_numeric = raw_text.replace(" ", "").replace("-", "").isdigit()
        cleaned_search = raw_text.replace(" ", "").replace("-", "").lower()

        if is_numeric:
            for c in self._clients_list:
                phone = str(c.get('Phone') or '').replace(" ", "").replace("-", "")
                if cleaned_search in phone:
                    return c.get('Client_ID')

        # Text search by name
        for c in self._clients_list:
            name = str(c.get('Client_Name') or '').lower()
            if raw_text.lower() in name:
                return c.get('Client_ID')

        return None

    def _on_activated(self, index):
        client_id = self.itemData(index)
        self._selected_client_id = client_id
        self.client_changed.emit(client_id)

    def _on_index_changed(self, index):
        client_id = self.itemData(index) if index >= 0 else None
        self._selected_client_id = client_id
        self.client_changed.emit(client_id)

    def _on_return_pressed(self):
        resolved_id = self._resolve_from_text()
        self.set_selected_client_id(resolved_id)
        self.client_changed.emit(resolved_id)
