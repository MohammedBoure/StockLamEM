import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, 
    QDateEdit, QPushButton, QTabWidget, QTableWidget, 
    QTableWidgetItem, QHeaderView, QSplitter, QComboBox,
    QAbstractItemView
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtCharts import QChart, QChartView, QPieSeries, QPieSlice

from ui.formatting import format_money, format_quantity

# =============================================================================
# 1. TAB: VALORISATION DU STOCK (Jard)
# يعرض قيمة المخزون الحالية بالتفصيل (عدد العلب + عدد الفحوصات + القيمة المالية)
# =============================================================================
class StockValuationTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # ملخص سريع في الأعلى
        self.lbl_summary = QLabel("Valeur Totale: 0,00 DA")
        self.lbl_summary.setStyleSheet("font-size: 16px; font-weight: bold; color: #27ae60; margin-bottom: 10px;")
        layout.addWidget(self.lbl_summary)

        # الجدول
        self.table = QTableWidget()
        cols = ["Produit", "Stock (Boîtes)", "Unités d'Usage (Tests)", "Valeur HT (DA)"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        
        # تنسيق الجدول
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents) # اسم المنتج
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setStyleSheet("border: 1px solid #dcdde1; gridline-color: #ecf0f1;")
        
        layout.addWidget(self.table)

    def refresh(self, stats_manager):
        """جلب البيانات من get_stock_valuation_detailed"""
        try:
            self.table.setSortingEnabled(False)
            data = stats_manager.get_stock_valuation_detailed()
            self.table.setRowCount(0)
            
            total_value = 0
            
            for row, item in enumerate(data):
                self.table.insertRow(row)
                
                # 1. Product Name
                self.table.setItem(row, 0, QTableWidgetItem(str(item['Product_Name'])))
                
                # 2. Stock Boxes (Stock Unit)
                box_unit = item['Stock_Unit'] or "U"
                boxes = item['total_boxes']
                self.table.setItem(row, 1, QTableWidgetItem(format_quantity(boxes, box_unit)))
                
                # 3. Usage Units (Tests) - ميزة قوية للمختبرات
                usage_unit = item['Usage_Unit'] or "Tests"
                tests = item['total_tests']
                item_tests = QTableWidgetItem(format_quantity(tests, usage_unit))
                item_tests.setForeground(QColor("#2980b9")) # أزرق
                item_tests.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.table.setItem(row, 2, item_tests)
                
                # 4. Financial Value
                val = float(item['total_value_ht'])
                total_value += val
                item_val = QTableWidgetItem(format_money(val, 'DA'))
                item_val.setForeground(QColor("#27ae60")) # أخضر
                self.table.setItem(row, 3, item_val)

            self.lbl_summary.setText(f"💰 Valeur Totale du Stock : {format_money(total_value, 'DA')}")
            self.table.setSortingEnabled(True)
            
        except Exception as e:
            logging.error(f"Valuation Tab Error: {e}")

# =============================================================================
# 2. TAB: ANALYSE DES PERTES (Waste Analysis)
# يعرض أسباب التلف وتكلفتها (رسم بياني + جدول)
# =============================================================================
class WasteAnalysisTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        
        # --- الجانب الأيسر: الرسم البياني (Pie Chart) ---
        chart_frame = QFrame()
        chart_layout = QVBoxLayout(chart_frame)
        
        self.chart = QChart()
        self.chart.setTitle("Répartition des Pertes (Par Coût)")
        self.chart.setTitleFont(QFont("Segoe UI", 10, QFont.Bold))
        self.chart.setAnimationOptions(QChart.SeriesAnimations)
        self.chart.legend().setVisible(True)
        self.chart.legend().setAlignment(Qt.AlignBottom)
        
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        chart_layout.addWidget(self.chart_view)
        
        # --- الجانب الأيمن: جدول التفاصيل ---
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Motif (Raison)", "Fréquence", "Perte Estimée (DA)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        
        # تقسيم الشاشة
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(chart_frame)
        splitter.addWidget(self.table)
        splitter.setSizes([400, 600]) # نسبة العرض
        
        layout.addWidget(splitter)

    def refresh(self, stats_manager, d_from, d_to):
        """جلب البيانات من get_waste_analysis"""
        try:
            data = stats_manager.get_waste_analysis(d_from, d_to)
            
            # 1. تحديث الجدول
            self.table.setRowCount(0)
            series = QPieSeries()
            
            for row, item in enumerate(data):
                self.table.insertRow(row)
                
                reason = item['Reason_Name'] or "Inconnu"
                freq = item['frequency']
                loss = float(item['estimated_loss'])
                
                self.table.setItem(row, 0, QTableWidgetItem(reason))
                self.table.setItem(row, 1, QTableWidgetItem(str(freq)))
                
                val_item = QTableWidgetItem(format_money(loss, 'DA'))
                val_item.setForeground(QColor("#c0392b")) # أحمر
                self.table.setItem(row, 2, val_item)
                
                # إضافة للرسم البياني
                if loss > 0:
                    slice_obj = series.append(reason, loss)
                    slice_obj.setLabel(f"{reason} ({format_money(loss, 'DA')})")
            
            # إظهار أكبر قطعة في الكعكة (Explode)
            if series.count() > 0:
                slices = series.slices()
                # البحث عن أكبر شريحة
                max_slice = max(slices, key=lambda s: s.value())
                max_slice.setExploded(True)
                max_slice.setLabelVisible(True)
            
            self.chart.removeAllSeries()
            self.chart.addSeries(series)
            
        except Exception as e:
            logging.error(f"Waste Tab Error: {e}")

# =============================================================================
# 3. TAB: RAPPORT CONSOMMATION DÉTAILLÉ
# النسخة الكاملة لتقرير الاستهلاك
# =============================================================================
class FullConsumptionTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        cols = ["Produit", "Unité Usage", "Qté Consommée", "Coût Total TTC (DA)"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        
        layout.addWidget(self.table)

    def refresh(self, stats_manager, d_from, d_to):
        """جلب البيانات من get_detailed_consumption_report"""
        try:
            self.table.setSortingEnabled(False)
            data = stats_manager.get_detailed_consumption_report(d_from, d_to)
            self.table.setRowCount(0)
            
            for row, item in enumerate(data):
                self.table.insertRow(row)
                
                self.table.setItem(row, 0, QTableWidgetItem(str(item['Product_Name'])))
                self.table.setItem(row, 1, QTableWidgetItem(str(item['Usage_Unit'])))
                
                qty = item['total_qty_consumed']
                self.table.setItem(row, 2, QTableWidgetItem(format_quantity(qty)))
                
                cost = float(item['total_cost_ttc'])
                cost_item = QTableWidgetItem(format_money(cost, 'DA'))
                cost_item.setForeground(QColor("#007572"))
                cost_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.table.setItem(row, 3, cost_item)
                
            self.table.setSortingEnabled(True)
        except Exception as e:
            logging.error(f"Consumption Tab Error: {e}")

# =============================================================================
# 4. TAB: ANALYSE DES CAISSES & SESSIONS (Cash & Sessions Analysis)
# Suivi financier des sessions : fond initial, encaissements, clôtures et écarts
# =============================================================================
class CashSessionsAnalysisTab(QWidget):
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.raw_data = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # --- Filtres internes : Choix de Caisse ---
        filter_bar = QHBoxLayout()
        filter_bar.addWidget(QLabel("Filtrer par Caisse :"))
        self.combo_caisse = QComboBox()
        self.combo_caisse.setMinimumWidth(220)
        self.combo_caisse.addItem("Toutes les Caisses", None)
        self.combo_caisse.currentIndexChanged.connect(self.filter_table)
        filter_bar.addWidget(self.combo_caisse)

        self.combo_status = QComboBox()
        self.combo_status.addItem("Tous les statuts", None)
        self.combo_status.addItem("Sessions Clôturées", "Closed")
        self.combo_status.addItem("Sessions Ouvertes", "Open")
        self.combo_status.currentIndexChanged.connect(self.filter_table)
        filter_bar.addWidget(QLabel("Statut :"))
        filter_bar.addWidget(self.combo_status)

        filter_bar.addStretch()
        layout.addLayout(filter_bar)

        # --- Cartes KPI Récapitulatives ---
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(8)

        self.kpi_sessions = self._create_kpi_card("Total Sessions", "0", "#2c3e50")
        self.kpi_opening = self._create_kpi_card("Total Fonds d'Ouverture", "0,00 DA", "#2980b9")
        self.kpi_sales = self._create_kpi_card("Ventes Encaissées", "0,00 DA", "#27ae60")
        self.kpi_counted = self._create_kpi_card("Total Sorties / Compté", "0,00 DA", "#8e44ad")
        self.kpi_diff = self._create_kpi_card("Écart Net Constaté", "0,00 DA", "#c0392b")

        kpi_layout.addWidget(self.kpi_sessions)
        kpi_layout.addWidget(self.kpi_opening)
        kpi_layout.addWidget(self.kpi_sales)
        kpi_layout.addWidget(self.kpi_counted)
        kpi_layout.addWidget(self.kpi_diff)
        layout.addLayout(kpi_layout)

        # --- Tableau des Sessions ---
        self.table = QTableWidget()
        cols = [
            "ID", "N° Session", "Caisse", "Statut",
            "Ouverture", "Clôture", "Tickets",
            "Fond Initial", "Ventes Session", "Sortie / Compté", "Écart"
        ]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self.open_session_details)
        layout.addWidget(self.table)

    def _create_kpi_card(self, title, default_val, color):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: #ffffff; border: 1px solid #cbd5e1;
                border-top: 3px solid {color}; border-radius: 4px; padding: 6px;
            }}
        """)
        l = QVBoxLayout(frame)
        l.setContentsMargins(4, 4, 4, 4)
        l.setSpacing(2)
        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("font-size: 11px; font-weight: bold; color: #64748b;")
        lbl_v = QLabel(default_val)
        lbl_v.setObjectName("val")
        lbl_v.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {color};")
        l.addWidget(lbl_t)
        l.addWidget(lbl_v)
        return frame

    def refresh(self, d_from, d_to):
        try:
            # Charger les caisses dans le filtre si non chargées
            curr_caisse = self.combo_caisse.currentData()
            self.combo_caisse.blockSignals(True)
            self.combo_caisse.clear()
            self.combo_caisse.addItem("Toutes les Caisses", None)
            terminals = self.data_manager.pos_terminals.get_all_terminals(include_inactive=True) if hasattr(self.data_manager, 'pos_terminals') else []
            for t in terminals:
                self.combo_caisse.addItem(f"{t.get('Terminal_Name')} ({t.get('Terminal_Code')})", t.get('Terminal_ID'))
            idx = self.combo_caisse.findData(curr_caisse)
            if idx >= 0:
                self.combo_caisse.setCurrentIndex(idx)
            self.combo_caisse.blockSignals(False)

            # Charger les sessions
            self.raw_data = self.data_manager.cash_sessions.get_cash_sessions_report(d_from, d_to)
            self.filter_table()
        except Exception as e:
            logging.error(f"Error refreshing CashSessionsAnalysisTab: {e}", exc_info=True)

    def filter_table(self):
        t_id = self.combo_caisse.currentData()
        status_filter = self.combo_status.currentData()

        filtered = []
        for s in self.raw_data:
            if t_id is not None and s.get('Terminal_ID') != t_id:
                continue
            if status_filter and s.get('Status') != status_filter:
                continue
            filtered.append(s)

        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        tot_sessions = len(filtered)
        tot_opening = 0.0
        tot_sales = 0.0
        tot_counted = 0.0
        tot_diff = 0.0

        for r, s in enumerate(filtered):
            self.table.insertRow(r)

            sess_id = s.get('Cash_Session_ID')
            sess_no = str(s.get('Session_No') or f"#{sess_id}")
            caisse_name = f"{s.get('Terminal_Name', 'Caisse')} ({s.get('Terminal_Code', '')})"
            status = s.get('Status', 'Open')
            is_open = (status == 'Open')

            opened_at = str(s.get('Opened_At', '---'))[:16]
            opened_by = s.get('Opened_By_Name') or ''
            closed_at = str(s.get('Closed_At', '---'))[:16] if not is_open else '---'
            closed_by = s.get('Closed_By_Name') or ''

            tickets = int(s.get('Total_Invoices') or 0)
            opening_amt = float(s.get('Opening_Amount') or 0.0)
            sales_amt = float(s.get('Total_Sales_TTC') or 0.0)
            counted_amt = float(s.get('Counted_Cash') or 0.0) if not is_open else 0.0
            diff = float(s.get('Cash_Difference') or 0.0) if not is_open else 0.0

            tot_opening += opening_amt
            tot_sales += sales_amt
            if not is_open:
                tot_counted += counted_amt
                tot_diff += diff

            id_item = QTableWidgetItem(str(sess_id))
            id_item.setData(Qt.UserRole, sess_id)
            self.table.setItem(r, 0, id_item)

            self.table.setItem(r, 1, QTableWidgetItem(sess_no))
            self.table.setItem(r, 2, QTableWidgetItem(caisse_name))

            st_item = QTableWidgetItem("🟢 Ouverte" if is_open else "🔒 Clôturée")
            st_item.setTextAlignment(Qt.AlignCenter)
            st_item.setForeground(QBrush(QColor("#27ae60" if is_open else "#64748b")))
            st_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table.setItem(r, 3, st_item)

            self.table.setItem(r, 4, QTableWidgetItem(f"{opened_at} ({opened_by})" if opened_by else opened_at))
            self.table.setItem(r, 5, QTableWidgetItem(f"{closed_at} ({closed_by})" if closed_by else closed_at))
            
            t_item = QTableWidgetItem(str(tickets))
            t_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, 6, t_item)

            self.table.setItem(r, 7, QTableWidgetItem(f"{format_money(opening_amt)} DA"))
            self.table.setItem(r, 8, QTableWidgetItem(f"{format_money(sales_amt)} DA"))
            self.table.setItem(r, 9, QTableWidgetItem(f"{format_money(counted_amt)} DA" if not is_open else "---"))

            diff_sign = "+" if diff > 0 else ""
            diff_color = "#27ae60" if abs(diff) < 0.01 else ("#2980b9" if diff > 0 else "#c0392b")
            diff_item = QTableWidgetItem(f"{diff_sign}{format_money(diff)} DA" if not is_open else "---")
            diff_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            diff_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            if not is_open:
                diff_item.setForeground(QBrush(QColor(diff_color)))
            self.table.setItem(r, 10, diff_item)

        self.table.setSortingEnabled(True)

        # Mettre à jour les KPI
        self.kpi_sessions.findChild(QLabel, "val").setText(str(tot_sessions))
        self.kpi_opening.findChild(QLabel, "val").setText(f"{format_money(tot_opening)} DA")
        self.kpi_sales.findChild(QLabel, "val").setText(f"{format_money(tot_sales)} DA")
        self.kpi_counted.findChild(QLabel, "val").setText(f"{format_money(tot_counted)} DA")
        
        diff_sign_tot = "+" if tot_diff > 0 else ""
        diff_color_tot = "#27ae60" if abs(tot_diff) < 0.01 else ("#2980b9" if tot_diff > 0 else "#c0392b")
        lbl_diff_val = self.kpi_diff.findChild(QLabel, "val")
        lbl_diff_val.setText(f"{diff_sign_tot}{format_money(tot_diff)} DA")
        lbl_diff_val.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {diff_color_tot};")

    def open_session_details(self):
        row = self.table.currentRow()
        if row < 0: return
        item = self.table.item(row, 0)
        if not item: return
        sess_id = item.data(Qt.UserRole)
        if sess_id and hasattr(self.data_manager, "cash_sessions"):
            from PySide6.QtWidgets import QDialog
            session_data = self.data_manager.cash_sessions.get_session_details_full(int(sess_id)) or {}
            caisse_name = session_data.get('Terminal_Name') or session_data.get('Terminal_Code') or "Caisse"
            session_no = session_data.get('Session_No') or f"#{sess_id}"
            dlg = QDialog(self)
            dlg.setWindowTitle(f"📋 Détails de la Session : {session_no} - {caisse_name}")
            dlg.resize(700, 480)
            lay = QVBoxLayout(dlg)
            lbl_info = QLabel(
                f"<b>{caisse_name} — Session {session_no}</b><br>"
                f"Ouvert par : {session_data.get('Opened_By_Name') or '-'} le {str(session_data.get('Opened_At', '---'))[:19]}<br>"
                f"Fond initial : {format_money(float(session_data.get('Opening_Amount') or 0.0))} DA"
            )
            lay.addWidget(lbl_info)
            tbl = QTableWidget()
            cols = ["N° Facture", "Date", "Client", "Statut", "Mode Règlement", "Total TTC"]
            tbl.setColumnCount(len(cols))
            tbl.setHorizontalHeaderLabels(cols)
            tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            invoices = session_data.get('invoices', [])
            tbl.setRowCount(len(invoices))
            for r_idx, inv in enumerate(invoices):
                tbl.setItem(r_idx, 0, QTableWidgetItem(str(inv.get('Invoice_No') or f"#{inv.get('Invoice_ID')}")))
                tbl.setItem(r_idx, 1, QTableWidgetItem(str(inv.get('Invoice_Date') or '---')))
                tbl.setItem(r_idx, 2, QTableWidgetItem(str(inv.get('Client_Name') or 'Vente comptoir')))
                tbl.setItem(r_idx, 3, QTableWidgetItem(str(inv.get('Status') or '-')))
                tbl.setItem(r_idx, 4, QTableWidgetItem(str(inv.get('Payment_Method') or '-')))
                tbl.setItem(r_idx, 5, QTableWidgetItem(f"{format_money(float(inv.get('Total_Amount_TTC') or 0.0))} DA"))
            lay.addWidget(tbl)
            dlg.exec()

# =============================================================================
# MAIN VIEW: ANALYSIS VIEW (CONTAINER)
# =============================================================================
class AnalysisView(QWidget):
    """
    الواجهة الرئيسية التي تجمع كل التبويبات الإحصائية والذكاء الاصطناعي.
    تحتوي على شريط تحكم بالتاريخ (مشترك) وزر تحديث.
    """
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.stats = manager.stats # الوصول السريع لـ StatisticsManager
        
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # --- 1. Top Toolbar (Controls) ---
        toolbar = QFrame()
        toolbar.setStyleSheet("background-color: white; border-bottom: 1px solid #dcdde1;")
        toolbar.setFixedHeight(70)
        tool_layout = QHBoxLayout(toolbar)
        
        lbl_title = QLabel("📊 ANALYSE & RAPPORTS")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: 900; color: #2c3e50;")
        
        self.date_from = QDateEdit(QDate.currentDate().addDays(-30))
        self.date_to = QDateEdit(QDate.currentDate())
        for d in [self.date_from, self.date_to]:
            d.setCalendarPopup(True)
            d.setFixedWidth(120)
            d.setStyleSheet("padding: 5px; border: 1px solid #bdc3c7; border-radius: 4px;")

        btn_refresh = QPushButton("ACTUALISER LES DONNÉES")
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.setIcon(qta.icon('fa5s.sync-alt', color='white') if 'qta' in globals() else None)
        btn_refresh.setStyleSheet("""
            QPushButton { 
                background-color: #2c3e50; color: white; font-weight: bold; 
                border-radius: 4px; padding: 8px 20px; border: none;
            }
            QPushButton:hover { background-color: #34495e; }
        """)
        btn_refresh.clicked.connect(self.refresh_all)

        tool_layout.addWidget(lbl_title)
        tool_layout.addStretch()
        tool_layout.addWidget(QLabel("Période du:"))
        tool_layout.addWidget(self.date_from)
        tool_layout.addWidget(QLabel("au:"))
        tool_layout.addWidget(self.date_to)
        tool_layout.addSpacing(10)
        tool_layout.addWidget(btn_refresh)
        
        main_layout.addWidget(toolbar)

        # --- 2. Content Tabs ---
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #dcdde1; background: #f9f9f9; }
            QTabBar::tab { 
                background: #ecf0f1; color: #7f8c8d; padding: 12px 30px; 
                font-weight: bold; margin-right: 2px;
            }
            QTabBar::tab:selected { 
                background: white; color: #2c3e50; border-top: 3px solid #2c3e50; 
            }
        """)
        
        # إنشاء التبويبات
        from ui.widgets.dashboard.ai_analytics_tab import AiAnalyticsTab
        self.tab_valuation = StockValuationTab()
        self.tab_waste = WasteAnalysisTab()
        self.tab_consumption = FullConsumptionTab()
        self.tab_caisse = CashSessionsAnalysisTab(self.manager)
        self.tab_ai = AiAnalyticsTab(db_instance=self.stats.db)
        
        self.tabs.addTab(self.tab_valuation, "💰 Valorisation du Stock")
        self.tabs.addTab(self.tab_waste, "🗑️ Analyse des Pertes (Déchets)")
        self.tabs.addTab(self.tab_consumption, "📉 Rapport Consommation")
        self.tabs.addTab(self.tab_caisse, "💵 Analyse des Caisses & Sessions")
        self.tabs.addTab(self.tab_ai, "🧠 Intelligence Artificielle & Prédictions")
        
        main_layout.addWidget(self.tabs)
        
        # تحميل البيانات الأولي
        self.refresh_all()

    def refresh_all(self):
        """تحديث جميع التبويبات دفعة واحدة"""
        d_from_str = self.date_from.date().toString("yyyy-MM-dd")
        d_to_str = self.date_to.date().toString("yyyy-MM-dd")
        
        # 1. تحديث تقييم المخزون (لا يعتمد على التاريخ، بل على الحالة الحالية)
        self.tab_valuation.refresh(self.stats)
        
        # 2. تحديث تحليل الهدر (يعتمد على التاريخ)
        self.tab_waste.refresh(self.stats, d_from_str, d_to_str)
        
        # 3. تحديث تقرير الاستهلاك (يعتمد على التاريخ)
        self.tab_consumption.refresh(self.stats, d_from_str, d_to_str)

        # 4. تحديث تحليل جلسات وصناديق الكاسة
        if hasattr(self, 'tab_caisse'):
            self.tab_caisse.refresh(d_from_str, d_to_str)

        # 5. تحديث تحليلات الذكاء الاصطناعي
        if hasattr(self, 'tab_ai'):
            self.tab_ai.set_db(self.stats.db)
            self.tab_ai.refresh_ai_data()
