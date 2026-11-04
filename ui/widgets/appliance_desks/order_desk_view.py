# ui/widgets/appliance_desks/order_desk_view.py
"""
Order Desk UI (مكتب الطلبات - Comptoir de Vente).
Provides:
- Multi-Scanner / Multi-Session tabs so multiple barcode scanners on the same PC
  route scans to completely independent sales sessions.
- Filtering by Mark (العلامة التجارية), Name (الاسم), Categorie (الفئة), and Coloure (اللون).
- Theoretical stock reservation without locking physical serial numbers (N° de Série).
- Generation of Bon C (بيع مباشر), Bon Crédit (أجل), and Bon de Livraison (توصيل).
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.hardware.raw_input_filter import MultiScannerHIDManager


class OrderDeskWidget(QWidget):
    """Order Desk workstation supporting Multi-Scanner / Multi-Session and Theoretical Orders."""

    bonCGenerated = Signal(dict)
    bonCreditRequested = Signal(dict)
    bonLivraisonGenerated = Signal(dict)

    def __init__(
        self,
        data_manager=None,
        hid_manager: Optional[MultiScannerHIDManager] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.data_manager = data_manager
        self.hid_manager = hid_manager or MultiScannerHIDManager()

        # Multi-Session state: each session_id has its own independent cart, client, and scanner binding
        self._sessions: Dict[str, Dict[str, Any]] = {
            "SESSION_1": {"label": "Session Vente #1", "scanner_id": "SCANNER_A", "client_id": 1, "cart": []},
            "SESSION_2": {"label": "Session Vente #2", "scanner_id": "SCANNER_B", "client_id": 1, "cart": []},
        }
        self._active_session_id = "SESSION_1"
        self._catalog_cache: List[Dict[str, Any]] = []

        # Bind default scanners in MultiScannerHIDManager
        for sid, sdata in self._sessions.items():
            self.hid_manager.bind_scanner_to_session(sdata["scanner_id"], sid)
            self.hid_manager.register_session_callback(
                sid, lambda dev_id, code, target_sid=sid: self._on_scanner_input_for_session(target_sid, dev_id, code)
            )

        self._init_ui()
        self.refresh_catalog()

    def _init_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        # 1. Top Multi-Scanner / Multi-Session Bar
        session_bar = QFrame()
        session_bar.setStyleSheet(
            "background-color: #FFFFFF; border: 1px solid #DDE3EA; border-radius: 8px; padding: 6px;"
        )
        sb_layout = QHBoxLayout(session_bar)
        sb_layout.setContentsMargins(10, 4, 10, 4)

        lbl_sess = QLabel("🔀 الجلسات والقارئات المتعددة (Multi-Scanner / Multi-Session):")
        lbl_sess.setFont(QFont("Segoe UI", 10, QFont.Bold))
        lbl_sess.setStyleSheet("color: #0E7471; border: none;")
        sb_layout.addWidget(lbl_sess)

        self.cbo_session = QComboBox()
        for sid, sdata in self._sessions.items():
            self.cbo_session.addItem(f"{sdata['label']} [{sdata['scanner_id']}]", sid)
        self.cbo_session.currentIndexChanged.connect(self._on_session_switched)
        sb_layout.addWidget(self.cbo_session)

        btn_new_sess = QPushButton("+ جلسة بيع جديدة")
        btn_new_sess.setStyleSheet(
            "background-color: #0E7471; color: white; font-weight: bold; padding: 6px 12px; border-radius: 6px;"
        )
        btn_new_sess.clicked.connect(self._create_new_session)
        sb_layout.addWidget(btn_new_sess)

        btn_bind_scanner = QPushButton("🔗 ربط قارئ باركود بالجلسة")
        btn_bind_scanner.setStyleSheet(
            "background-color: #2563EB; color: white; font-weight: bold; padding: 6px 12px; border-radius: 6px;"
        )
        btn_bind_scanner.clicked.connect(self._prompt_scanner_binding)
        sb_layout.addWidget(btn_bind_scanner)

        sb_layout.addStretch()
        self.lbl_scanner_status = QLabel("الحالة: كل قارئ موجه لجلسة مستقلة")
        self.lbl_scanner_status.setStyleSheet("color: #16A34A; font-weight: bold; border: none;")
        sb_layout.addWidget(self.lbl_scanner_status)
        root_layout.addWidget(session_bar)

        # 2. Main 3-Column Body
        body_layout = QHBoxLayout()
        body_layout.setSpacing(12)

        body_layout.addWidget(self._create_filter_panel(), stretch=1)
        body_layout.addWidget(self._create_catalog_panel(), stretch=3)
        body_layout.addWidget(self._create_cart_panel(), stretch=2)

        root_layout.addLayout(body_layout)

    def _create_filter_panel(self) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet(
            "background-color: #FFFFFF; border: 1px solid #DDE3EA; border-radius: 8px; padding: 10px;"
        )
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)

        title = QLabel("🔍 خصائص المنتج (الفلترة)")
        title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        title.setStyleSheet("color: #0E7471; border: none;")
        layout.addWidget(title)

        layout.addWidget(QLabel("العلامة التجارية (Mark):"))
        self.cbo_mark = QComboBox()
        self.cbo_mark.addItems(["Tous", "Bosch", "Samsung", "LG", "Brandt", "Condor", "Cristor", "Midea", "Moulinex"])
        self.cbo_mark.currentTextChanged.connect(self.refresh_catalog)
        layout.addWidget(self.cbo_mark)

        layout.addWidget(QLabel("الفئة أو التصنيف (Categorie):"))
        self.cbo_category = QComboBox()
        self.cbo_category.addItems([
            "Tous",
            "Gros Électroménager",
            "Petit Électroménager",
            "Réfrigérateurs",
            "Lave-linge",
            "Climatisation",
            "Téléviseurs & Multimédia",
            "Cuisson & Fours",
        ])
        self.cbo_category.currentTextChanged.connect(self.refresh_catalog)
        layout.addWidget(self.cbo_category)

        layout.addWidget(QLabel("اللون (Coloure):"))
        self.cbo_color = QComboBox()
        self.cbo_color.addItems(["Tous", "Inox", "Blanc", "Noir", "Silver", "Gris"])
        self.cbo_color.currentTextChanged.connect(self.refresh_catalog)
        layout.addWidget(self.cbo_color)

        btn_reset = QPushButton("🔄 عرض الكل")
        btn_reset.setStyleSheet("background-color: #64748B; color: white; padding: 8px; border-radius: 6px;")
        btn_reset.clicked.connect(self._reset_filters)
        layout.addWidget(btn_reset)

        note_lbl = QLabel(
            "ℹ️ <b>البيع النظري (Order Desk):</b><br>"
            "يتم تسجيل اسم المنتج ونوعه ولونه فقط دون حجز رقم تسلسلي فيزيائي.<br>"
            "مكتب الإخراج (Dispatch) هو المسؤول الوحيد عن مسح الرقم التسلسلي الفعلي."
        )
        note_lbl.setWordWrap(True)
        note_lbl.setStyleSheet(
            "background-color: #F0FDFA; color: #0F766E; border: 1px solid #99F6E4; border-radius: 6px; padding: 8px; font-size: 11px;"
        )
        layout.addWidget(note_lbl)

        layout.addStretch()
        return panel

    def _create_catalog_panel(self) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet(
            "background-color: #FFFFFF; border: 1px solid #DDE3EA; border-radius: 8px; padding: 10px;"
        )
        layout = QVBoxLayout(panel)

        top_bar = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 بحث بالاسم (Name)، العلامة (Mark)، الفئة (Categorie)، اللون (Coloure) أو الباركود...")
        self.txt_search.textChanged.connect(self.refresh_catalog)
        top_bar.addWidget(self.txt_search)

        btn_refresh = QPushButton("Actualiser")
        btn_refresh.setStyleSheet("background-color: #0E7471; color: white; font-weight: bold; padding: 8px 14px; border-radius: 6px;")
        btn_refresh.clicked.connect(self.refresh_catalog)
        top_bar.addWidget(btn_refresh)
        layout.addLayout(top_bar)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Mark (العلامة)",
            "Name (الاسم)",
            "Categorie (الفئة)",
            "Coloure (اللون)",
            "المخزون الفعلي",
            "المتاح نظرياً",
            "إضافة للطلب",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)
        return panel

    def _create_cart_panel(self) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet(
            "background-color: #FFFFFF; border: 1px solid #DDE3EA; border-radius: 8px; padding: 10px;"
        )
        layout = QVBoxLayout(panel)

        self.lbl_cart_header = QLabel("🛒 سلة الطلب النظري - Session Vente #1")
        self.lbl_cart_header.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.lbl_cart_header.setStyleSheet("color: #0E7471; border: none;")
        layout.addWidget(self.lbl_cart_header)

        client_row = QHBoxLayout()
        client_row.addWidget(QLabel("الزبون (Client):"))
        self.cbo_client = QComboBox()
        self._load_clients_into_combo()
        client_row.addWidget(self.cbo_client, stretch=1)
        layout.addLayout(client_row)

        self.cart_table = QTableWidget(0, 4)
        self.cart_table.setHorizontalHeaderLabels(["المنتج", "اللون", "الكمية", "المجموع TTC"])
        self.cart_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.cart_table)

        # Delivery info for Bon de Livraison
        deliv_row = QHBoxLayout()
        self.txt_delivery_addr = QLineEdit()
        self.txt_delivery_addr.setPlaceholderText("عنوان التوصيل ورقم الهاتف (خاص بـ Bon de Livraison)...")
        deliv_row.addWidget(self.txt_delivery_addr)
        layout.addLayout(deliv_row)

        self.lbl_total = QLabel("TOTAL TTC: 0.00 DA")
        self.lbl_total.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self.lbl_total.setStyleSheet("color: #059669; margin: 6px 0; border: none;")
        layout.addWidget(self.lbl_total)

        btn_bon_c = QPushButton("⚡ إنشاء Bon C (بيع مباشر -> للصندوق)")
        btn_bon_c.setStyleSheet(
            "background-color: #059669; color: white; padding: 10px; font-weight: bold; border-radius: 6px;"
        )
        btn_bon_c.clicked.connect(lambda: self._submit_order("BON_C"))
        layout.addWidget(btn_bon_c)

        btn_credit = QPushButton("💳 طلب Bon Crédit (أجل - يتطلب موافقة Admin)")
        btn_credit.setStyleSheet(
            "background-color: #D97706; color: white; padding: 10px; font-weight: bold; border-radius: 6px;"
        )
        btn_credit.clicked.connect(lambda: self._submit_order("BON_CREDIT"))
        layout.addWidget(btn_credit)

        btn_livraison = QPushButton("🚚 إنشاء Bon de Livraison (توصيل مع دفع/تسبيق)")
        btn_livraison.setStyleSheet(
            "background-color: #2563EB; color: white; padding: 10px; font-weight: bold; border-radius: 6px;"
        )
        btn_livraison.clicked.connect(lambda: self._submit_order("BON_LIVRAISON"))
        layout.addWidget(btn_livraison)

        btn_clear = QPushButton("🗑️ تفريغ سلة الجلسة الحالية")
        btn_clear.setStyleSheet("background-color: #EF4444; color: white; padding: 7px; border-radius: 6px;")
        btn_clear.clicked.connect(self._clear_current_cart)
        layout.addWidget(btn_clear)

        return panel

    def _load_clients_into_combo(self) -> None:
        self.cbo_client.clear()
        self.cbo_client.addItem("Client Comptoir (افتراضي)", 1)
        if self.data_manager and hasattr(self.data_manager, "clients"):
            try:
                clients = self.data_manager.clients.get_all_clients() or []
                for c in clients:
                    cid = c.get("Client_ID")
                    cname = c.get("Client_Name") or f"Client #{cid}"
                    if cid:
                        self.cbo_client.addItem(cname, int(cid))
            except Exception:
                pass

    def _reset_filters(self) -> None:
        self.cbo_mark.setCurrentIndex(0)
        self.cbo_category.setCurrentIndex(0)
        self.cbo_color.setCurrentIndex(0)
        self.txt_search.clear()
        self.refresh_catalog()

    def refresh_catalog(self) -> None:
        """Loads catalog items from database (or fallback showcase rows) with theoretical availability."""
        search_txt = self.txt_search.text().strip() if hasattr(self, "txt_search") else ""
        mark_txt = self.cbo_mark.currentText() if hasattr(self, "cbo_mark") else "Tous"
        cat_txt = self.cbo_category.currentText() if hasattr(self, "cbo_category") else "Tous"
        col_txt = self.cbo_color.currentText() if hasattr(self, "cbo_color") else "Tous"

        items: List[Dict[str, Any]] = []
        if self.data_manager and hasattr(self.data_manager, "serials"):
            items = self.data_manager.serials.get_catalog_with_theoretical_stock(
                search=search_txt,
                brand_mark=mark_txt,
                category_name=cat_txt,
                color_finish=col_txt,
            )

        if not items and not (self.data_manager and hasattr(self.data_manager, "serials")):
            items = [
                {
                    "Product_ID": 101,
                    "Brand_Mark": "Bosch",
                    "Product_Name": "KGN39VLEB Combi 368L",
                    "Category_Name": "Réfrigérateurs",
                    "Color_Finish": "Inox",
                    "Physical_Qty": 8,
                    "Available_Theoretical_Qty": 7,
                    "Unit_Price_TTC": 115000.0,
                    "Barcode": "4242005198030",
                },
                {
                    "Product_ID": 102,
                    "Brand_Mark": "LG",
                    "Product_Name": "F4J6TY0W DirectDrive 9kg",
                    "Category_Name": "Lave-linge",
                    "Color_Finish": "Blanc",
                    "Physical_Qty": 12,
                    "Available_Theoretical_Qty": 12,
                    "Unit_Price_TTC": 88000.0,
                    "Barcode": "8806098321092",
                },
                {
                    "Product_ID": 103,
                    "Brand_Mark": "Midea",
                    "Product_Name": "Inverter 12000 BTU Split",
                    "Category_Name": "Climatisation",
                    "Color_Finish": "Blanc",
                    "Physical_Qty": 5,
                    "Available_Theoretical_Qty": 4,
                    "Unit_Price_TTC": 64000.0,
                    "Barcode": "6939962711029",
                },
            ]

        self._catalog_cache = items
        self.table.setRowCount(0)
        for prod in items:
            row = self.table.rowCount()
            self.table.insertRow(row)
            mark = str(prod.get("Brand_Mark") or "Générique")
            name = str(prod.get("Product_Name") or "")
            cat = str(prod.get("Category_Name") or "Électroménager")
            color = str(prod.get("Color_Finish") or "Standard")
            phys = int(prod.get("Physical_Qty") or 0)
            avail = int(prod.get("Available_Theoretical_Qty") or 0)
            price = float(prod.get("Unit_Price_TTC") or 0.0)

            self.table.setItem(row, 0, QTableWidgetItem(mark))
            self.table.setItem(row, 1, QTableWidgetItem(name))
            self.table.setItem(row, 2, QTableWidgetItem(cat))
            self.table.setItem(row, 3, QTableWidgetItem(color))
            self.table.setItem(row, 4, QTableWidgetItem(str(phys)))
            self.table.setItem(row, 5, QTableWidgetItem(f"{avail} متاح"))

            btn = QPushButton(f"+ إضافة ({price:,.0f} DA)")
            btn.setEnabled(avail > 0)
            btn.setStyleSheet(
                "background-color: #0E7471; color: white; font-weight: bold; padding: 5px; border-radius: 4px;"
                if avail > 0
                else "background-color: #94A3B8; color: white; padding: 5px; border-radius: 4px;"
            )
            btn.clicked.connect(lambda checked=False, p=prod: self._add_product_to_session(self._active_session_id, p))
            self.table.setCellWidget(row, 6, btn)

    # =========================================================================
    # MULTI-SESSION & MULTI-SCANNER ROUTING
    # =========================================================================

    def _on_session_switched(self, idx: int) -> None:
        sid = self.cbo_session.itemData(idx)
        if sid and sid in self._sessions:
            self._active_session_id = sid
            sdata = self._sessions[sid]
            self.lbl_cart_header.setText(f"🛒 سلة الطلب النظري - {sdata['label']} [{sdata['scanner_id']}]")
            self._refresh_cart_ui()

    def _create_new_session(self) -> None:
        next_num = len(self._sessions) + 1
        sid = f"SESSION_{next_num}"
        scanner_id = f"SCANNER_{chr(64 + min(next_num, 26))}"
        label = f"Session Vente #{next_num}"
        self._sessions[sid] = {
            "label": label,
            "scanner_id": scanner_id,
            "client_id": 1,
            "cart": [],
        }
        self.hid_manager.bind_scanner_to_session(scanner_id, sid)
        self.hid_manager.register_session_callback(
            sid, lambda dev_id, code, target_sid=sid: self._on_scanner_input_for_session(target_sid, dev_id, code)
        )
        self.cbo_session.addItem(f"{label} [{scanner_id}]", sid)
        self.cbo_session.setCurrentIndex(self.cbo_session.count() - 1)

    def _prompt_scanner_binding(self) -> None:
        sdata = self._sessions[self._active_session_id]
        text, ok = QInputDialog.getText(
            self,
            "ربط قارئ باركود بجلسة مستقلة",
            f"أدخل معرف قارئ الباركود (Device Handle / ID) لربطه بـ {sdata['label']}:",
            text=sdata["scanner_id"],
        )
        if ok and text.strip():
            new_dev = text.strip()
            self.hid_manager.unbind_scanner(sdata["scanner_id"])
            sdata["scanner_id"] = new_dev
            self.hid_manager.bind_scanner_to_session(new_dev, self._active_session_id)
            curr_idx = self.cbo_session.currentIndex()
            self.cbo_session.setItemText(curr_idx, f"{sdata['label']} [{new_dev}]")
            self.lbl_scanner_status.setText(f"تم ربط القارئ [{new_dev}] بـ {sdata['label']}")

    def _on_scanner_input_for_session(self, session_id: str, device_id: str, barcode: str) -> None:
        """
        Routes a barcode scanned by a specific physical scanner directly into its assigned session cart,
        even if another session is currently displayed on screen!
        """
        code_clean = barcode.strip()
        matched_prod = None
        for prod in self._catalog_cache:
            if str(prod.get("Barcode") or "").strip() == code_clean or str(prod.get("Product_ID")) == code_clean:
                matched_prod = prod
                break
        if not matched_prod and self._catalog_cache:
            matched_prod = self._catalog_cache[0]

        if matched_prod:
            self._add_product_to_session(session_id, matched_prod)
            self.lbl_scanner_status.setText(
                f"📡 القارئ [{device_id}] أضاف '{matched_prod.get('Product_Name')}' إلى {session_id}"
            )

    def _add_product_to_session(self, session_id: str, product: Dict[str, Any]) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return
        cart = session["cart"]
        pid = int(product.get("Product_ID") or 0)
        for existing in cart:
            if existing["product_id"] == pid:
                existing["quantity"] += 1
                if session_id == self._active_session_id:
                    self._refresh_cart_ui()
                return

        cart.append({
            "product_id": pid,
            "brand": str(product.get("Brand_Mark") or ""),
            "model": str(product.get("Product_Name") or ""),
            "finish": str(product.get("Color_Finish") or "Standard"),
            "unit_price_ttc": float(product.get("Unit_Price_TTC") or 0.0),
            "quantity": 1,
        })
        if session_id == self._active_session_id:
            self._refresh_cart_ui()

    def _clear_current_cart(self) -> None:
        self._sessions[self._active_session_id]["cart"].clear()
        self._refresh_cart_ui()

    def _refresh_cart_ui(self) -> None:
        cart = self._sessions[self._active_session_id]["cart"]
        self.cart_table.setRowCount(0)
        total = 0.0
        for item in cart:
            row = self.cart_table.rowCount()
            self.cart_table.insertRow(row)
            self.cart_table.setItem(row, 0, QTableWidgetItem(f"{item['brand']} {item['model']}".strip()))
            self.cart_table.setItem(row, 1, QTableWidgetItem(item["finish"]))
            self.cart_table.setItem(row, 2, QTableWidgetItem(str(item["quantity"])))
            line_tot = item["unit_price_ttc"] * item["quantity"]
            total += line_tot
            self.cart_table.setItem(row, 3, QTableWidgetItem(f"{line_tot:,.2f} DA"))
        self.lbl_total.setText(f"TOTAL TTC: {total:,.2f} DA")

    def _submit_order(self, bond_type: str) -> None:
        session = self._sessions[self._active_session_id]
        cart = session["cart"]
        if not cart:
            QMessageBox.warning(self, "السلة فارغة", "يرجى إضافة منتجات للطلب قبل إصدار السند.")
            return

        client_id = int(self.cbo_client.currentData() or 1)
        user_id = 1
        if self.data_manager and getattr(self.data_manager, "current_user", None):
            user_id = int(
                self.data_manager.current_user.get("User_ID")
                or self.data_manager.current_user.get("id")
                or 1
            )

        payment_req_map = {
            "BON_C": "CASH",
            "BON_CREDIT": "CREDIT",
            "BON_LIVRAISON": "LIVRAISON_COD",
        }
        deliv_addr = self.txt_delivery_addr.text().strip() if bond_type == "BON_LIVRAISON" else None

        try:
            res = {"order_number": f"{bond_type}-SIM", "type": bond_type, "items": list(cart)}
            if self.data_manager and hasattr(self.data_manager, "bonds"):
                res = self.data_manager.bonds.create_sales_order_draft(
                    client_id=client_id,
                    order_desk_user_id=user_id,
                    items=cart,
                    payment_method_requested=payment_req_map.get(bond_type, "CASH"),
                    bond_type=bond_type,
                    scanner_session_id=self._active_session_id,
                    delivery_address=deliv_addr,
                )

            if bond_type == "BON_C":
                self.bonCGenerated.emit(res)
                QMessageBox.information(
                    self,
                    "تم إصدار Bon C",
                    f"تم تسجيل السند ({res.get('order_number')}) نظرياً وإرساله إلى مكتب الصندوق (Caisse).",
                )
            elif bond_type == "BON_CREDIT":
                self.bonCreditRequested.emit(res)
                QMessageBox.information(
                    self,
                    "طلب Bon Crédit",
                    f"تم إرسال طلب البيع بالأجل ({res.get('order_number')}) إلى الصندوق بانتظار موافقة وكلمة مرور المشرف (Admin).",
                )
            else:
                self.bonLivraisonGenerated.emit(res)
                QMessageBox.information(
                    self,
                    "تم إصدار Bon de Livraison",
                    f"تم إنشاء سند التوصيل ({res.get('order_number')}) وإرساله للصندوق لتسجيل التسبيق قبل الإرسال.",
                )

            cart.clear()
            self.txt_delivery_addr.clear()
            self._refresh_cart_ui()
            self.refresh_catalog()
        except Exception as err:
            QMessageBox.critical(self, "خطأ في إنشاء السند", str(err))
