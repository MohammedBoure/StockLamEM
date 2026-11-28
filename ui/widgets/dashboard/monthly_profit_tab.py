# -*- coding: utf-8 -*-
"""
Monthly & Period Profit Tab (Bénéfices Mensuels & par Période) for Tableau de Bord.
Displays real-time net profit per month (Jan..Dec) or per custom date range (Du..Au),
computed dynamically using:
  Bénéfice Net = Prix de Vente (CA) - Prix Moyen d'Achat (PMP) - Décharges.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QDate, QSize, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.formatting import format_money
from ui.icons import get_duotone_icon

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    HAS_MPL = True
except Exception:
    FigureCanvas = None
    Figure = None
    HAS_MPL = False


MONTH_NAMES_FR = [
    "Janvier",
    "Février",
    "Mars",
    "Avril",
    "Mai",
    "Juin",
    "Juillet",
    "Août",
    "Septembre",
    "Octobre",
    "Novembre",
    "Décembre",
]

MONTH_SHORT_FR = [
    "Jan", "Fév", "Mar", "Avr", "Mai", "Jun",
    "Jul", "Aoû", "Sep", "Oct", "Nov", "Déc",
]


class MonthlyProfitTab(QWidget):
    """Dashboard tab showing net sales profit (CA - PMP - Décharges) by month or period."""

    def __init__(self, data_manager: Any, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.data_manager = data_manager
        self._current_year = datetime.now().year
        self._mode = "year"  # "year" | "period"
        self._rows: List[Dict[str, Any]] = []
        self._init_ui()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Recompute live every time the user enters this tab
        QTimer.singleShot(0, self.refresh)

    def _init_ui(self) -> None:
        self.setObjectName("MonthlyProfitTabRoot")
        self.setStyleSheet(
            """
            QWidget#MonthlyProfitTabRoot { background-color: #F8FAFC; }
            QFrame#ProfitCard {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 10px;
            }
            QFrame#ProfitCard QLabel { border: none; background: transparent; }
            QPushButton#ProfitModeBtn {
                background-color: #F1F5F9;
                color: #475569;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 0px 12px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton#ProfitModeBtn:hover:!checked {
                background-color: #E2E8F0;
                color: #0F172A;
            }
            QPushButton#ProfitModeBtn:checked {
                background-color: #0E7471;
                color: #FFFFFF;
                border-color: #0E7471;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # 1. Top Bar (Title + Mode Toggle + Year/Period Controls + Refresh)
        top_bar = QFrame()
        top_bar.setObjectName("ProfitCard")
        tb_lay = QHBoxLayout(top_bar)
        tb_lay.setContentsMargins(14, 10, 14, 10)
        tb_lay.setSpacing(10)

        hdr_icon = QLabel()
        hdr_icon.setFixedSize(36, 36)
        hdr_icon.setAlignment(Qt.AlignCenter)
        hdr_icon.setPixmap(get_duotone_icon("profit_chart", 24).pixmap(24, 24))
        hdr_icon.setStyleSheet("background-color: #E6F4F1; border-radius: 8px;")
        tb_lay.addWidget(hdr_icon)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        lbl_title = QLabel("Bénéfices Mensuels & par Période")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #0F172A;")
        lbl_sub = QLabel("Calcul en temps réel : Prix de Vente − Coût Moyen d'Achat (PMP) − Décharges")
        lbl_sub.setStyleSheet("font-size: 12px; color: #64748B;")
        title_col.addWidget(lbl_title)
        title_col.addWidget(lbl_sub)
        tb_lay.addLayout(title_col)

        tb_lay.addStretch(1)

        # Mode switch buttons
        self.btn_mode_year = QPushButton("Par Année (Mensuel)")
        self.btn_mode_year.setObjectName("ProfitModeBtn")
        self.btn_mode_year.setCheckable(True)
        self.btn_mode_year.setChecked(True)
        self.btn_mode_year.setFixedHeight(34)
        self.btn_mode_year.setCursor(Qt.PointingHandCursor)
        self.btn_mode_year.clicked.connect(lambda: self._set_mode("year"))

        self.btn_mode_period = QPushButton("Par Période (Temps)")
        self.btn_mode_period.setObjectName("ProfitModeBtn")
        self.btn_mode_period.setCheckable(True)
        self.btn_mode_period.setChecked(False)
        self.btn_mode_period.setFixedHeight(34)
        self.btn_mode_period.setCursor(Qt.PointingHandCursor)
        self.btn_mode_period.clicked.connect(lambda: self._set_mode("period"))

        tb_lay.addWidget(self.btn_mode_year)
        tb_lay.addWidget(self.btn_mode_period)

        # Year controls container
        self.year_controls = QWidget()
        yc_lay = QHBoxLayout(self.year_controls)
        yc_lay.setContentsMargins(6, 0, 0, 0)
        yc_lay.setSpacing(6)
        yr_ic = QLabel()
        yr_ic.setPixmap(get_duotone_icon("calendar", 16).pixmap(16, 16))
        yc_lay.addWidget(yr_ic)
        lbl_yr = QLabel("Année :")
        lbl_yr.setStyleSheet("font-size: 12.5px; font-weight: 700; color: #334155;")
        yc_lay.addWidget(lbl_yr)
        self.cbo_year = QComboBox()
        self.cbo_year.setFixedHeight(34)
        self.cbo_year.setMinimumWidth(96)
        self.cbo_year.setStyleSheet(
            "QComboBox { background:#FFFFFF; border:1px solid #CBD5E1; border-radius:6px; "
            "padding:4px 10px; font-size:13px; font-weight:700; color:#0F172A; }"
        )
        self.cbo_year.addItem(str(self._current_year), self._current_year)
        self.cbo_year.currentIndexChanged.connect(self._on_year_changed)
        yc_lay.addWidget(self.cbo_year)
        tb_lay.addWidget(self.year_controls)

        # Period controls container
        self.period_controls = QWidget()
        pc_lay = QHBoxLayout(self.period_controls)
        pc_lay.setContentsMargins(6, 0, 0, 0)
        pc_lay.setSpacing(6)
        lbl_du = QLabel("Du :")
        lbl_du.setStyleSheet("font-size: 12.5px; font-weight: 700; color: #334155;")
        self.date_from = QDateEdit(QDate.currentDate().addDays(-30))
        self.date_to = QDateEdit(QDate.currentDate())
        for d_edit in (self.date_from, self.date_to):
            d_edit.setCalendarPopup(True)
            d_edit.setFixedHeight(34)
            d_edit.setMinimumWidth(116)
            d_edit.setDisplayFormat("dd/MM/yyyy")
            d_edit.setStyleSheet(
                "QDateEdit { background:#FFFFFF; border:1px solid #CBD5E1; border-radius:6px; "
                "padding:4px 8px; font-size:12.5px; font-weight:600; color:#0F172A; }"
            )
            d_edit.dateChanged.connect(self._on_period_changed)
        lbl_au = QLabel("Au :")
        lbl_au.setStyleSheet("font-size: 12.5px; font-weight: 700; color: #334155;")
        pc_lay.addWidget(lbl_du)
        pc_lay.addWidget(self.date_from)
        pc_lay.addWidget(lbl_au)
        pc_lay.addWidget(self.date_to)
        self.period_controls.setVisible(False)
        tb_lay.addWidget(self.period_controls)

        self.btn_refresh = QPushButton("Actualiser")
        self.btn_refresh.setIcon(get_duotone_icon("refresh", 15))
        self.btn_refresh.setIconSize(QSize(15, 15))
        self.btn_refresh.setFixedHeight(34)
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setStyleSheet(
            "QPushButton { background:#FFFFFF; border:1px solid #CBD5E1; border-radius:6px; "
            "color:#334155; font-size:12px; font-weight:700; padding:0px 14px; }"
            "QPushButton:hover { background:#F1F5F9; border-color:#94A3B8; }"
        )
        self.btn_refresh.clicked.connect(self.refresh)
        tb_lay.addWidget(self.btn_refresh)

        root.addWidget(top_bar)

        # 2. KPI Strip (5 cards including Décharges)
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(10)

        self.lbl_kpi_profit_title, self.lbl_kpi_profit, card_profit = self._make_kpi_card(
            "BÉNÉFICE NET ANNUEL", "0,00 DA", "#0E7471", "profit_chart"
        )
        _, self.lbl_kpi_rev, card_rev = self._make_kpi_card(
            "CHIFFRE D'AFFAIRES", "0,00 DA", "#0F172A", "kpi_wallet"
        )
        _, self.lbl_kpi_cost, card_cost = self._make_kpi_card(
            "COÛT D'ACHAT (PMP)", "0,00 DA", "#B45309", "valuation"
        )
        _, self.lbl_kpi_dech, card_dech = self._make_kpi_card(
            "DÉCHARGES DÉDUITES", "0,00 DA", "#DC2626", "waste_bin"
        )
        self.lbl_kpi_best_title, self.lbl_kpi_best, card_best = self._make_kpi_card(
            "MEILLEUR MOIS", "—", "#15803D", "trophy_best"
        )

        for c in (card_profit, card_rev, card_cost, card_dech, card_best):
            kpi_row.addWidget(c, 1)
        root.addLayout(kpi_row)

        # 3. Chart Card (optional matplotlib)
        self._canvas = None
        self._figure = None
        if HAS_MPL:
            chart_card = QFrame()
            chart_card.setObjectName("ProfitCard")
            chart_card.setMinimumHeight(210)
            chart_card.setMaximumHeight(260)
            ch_lay = QVBoxLayout(chart_card)
            ch_lay.setContentsMargins(10, 8, 10, 8)
            self._figure = Figure(figsize=(8, 2.3), dpi=96)
            self._figure.patch.set_facecolor("#FFFFFF")
            self._canvas = FigureCanvas(self._figure)
            self._canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            ch_lay.addWidget(self._canvas)
            root.addWidget(chart_card)

        # 4. Breakdown Table (8 columns including Décharges)
        table_card = QFrame()
        table_card.setObjectName("ProfitCard")
        tc_lay = QVBoxLayout(table_card)
        tc_lay.setContentsMargins(10, 10, 10, 10)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "Mois",
            "Ventes (Nb)",
            "Unités",
            "Chiffre d'Affaires",
            "Coût Moyen (PMP)",
            "Décharges",
            "Bénéfice Net",
            "Marge (%)",
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.horizontalHeader().setFixedHeight(36)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            """
            QTableWidget {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                gridline-color: #F1F5F9;
                font-size: 12.5px;
                color: #0F172A;
            }
            QHeaderView::section {
                background-color: #F8FAFC;
                color: #334155;
                font-weight: 700;
                font-size: 12px;
                border: none;
                border-bottom: 2px solid #0E7471;
                padding: 6px 8px;
            }
            """
        )
        hdr = self.table.horizontalHeader()
        for col in range(8):
            hdr.setSectionResizeMode(col, QHeaderView.Stretch)

        tc_lay.addWidget(self.table, 1)
        root.addWidget(table_card, 1)

    def _make_kpi_card(self, label: str, value: str, color_hex: str, icon_name: str = ""):
        card = QFrame()
        card.setObjectName("ProfitCard")
        card.setFixedHeight(78)
        outer = QHBoxLayout(card)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(10)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        lbl_k = QLabel(label)
        lbl_k.setStyleSheet("font-size: 10.5px; font-weight: 700; color: #64748B;")
        lbl_v = QLabel(value)
        lbl_v.setStyleSheet(f"font-size: 16.5px; font-weight: 800; color: {color_hex};")
        text_col.addWidget(lbl_k)
        text_col.addWidget(lbl_v)
        outer.addLayout(text_col, 1)

        if icon_name:
            ic_lbl = QLabel()
            ic_lbl.setFixedSize(36, 36)
            ic_lbl.setAlignment(Qt.AlignCenter)
            ic_lbl.setPixmap(get_duotone_icon(icon_name, 20).pixmap(20, 20))
            ic_lbl.setStyleSheet(f"background-color: {color_hex}15; border-radius: 18px;")
            outer.addWidget(ic_lbl)

        return lbl_k, lbl_v, card

    def _set_mode(self, mode: str) -> None:
        self._mode = mode if mode in ("year", "period") else "year"
        is_year = self._mode == "year"
        self.btn_mode_year.setChecked(is_year)
        self.btn_mode_period.setChecked(not is_year)
        self.year_controls.setVisible(is_year)
        self.period_controls.setVisible(not is_year)
        self.refresh(sync_years=is_year)

    def set_period_dates(self, d_from: QDate, d_to: QDate, refresh_now: bool = False) -> None:
        """Syncs the period date range with DashboardTab's global date pickers."""
        if d_from and d_from.isValid() and d_to and d_to.isValid():
            self.date_from.blockSignals(True)
            self.date_to.blockSignals(True)
            self.date_from.setDate(d_from)
            self.date_to.setDate(d_to)
            self.date_from.blockSignals(False)
            self.date_to.blockSignals(False)
        if refresh_now:
            self.refresh()

    def _sync_years_combo(self) -> None:
        stats = getattr(self.data_manager, "stats", None)
        years = [datetime.now().year]
        if stats and hasattr(stats, "get_available_profit_years"):
            try:
                years = stats.get_available_profit_years() or years
            except Exception:
                pass
        selected = self.cbo_year.currentData() or self._current_year
        self.cbo_year.blockSignals(True)
        self.cbo_year.clear()
        for y in years:
            self.cbo_year.addItem(str(y), int(y))
        idx = self.cbo_year.findData(int(selected))
        if idx >= 0:
            self.cbo_year.setCurrentIndex(idx)
        self.cbo_year.blockSignals(False)

    def _on_year_changed(self) -> None:
        yr = self.cbo_year.currentData()
        if yr is not None:
            self._current_year = int(yr)
            if self._mode == "year":
                self.refresh(sync_years=False)

    def _on_period_changed(self) -> None:
        if self._mode == "period":
            self.refresh(sync_years=False)

    def refresh(self, sync_years: bool = True) -> None:
        stats = getattr(self.data_manager, "stats", None)

        if self._mode == "period":
            d1 = self.date_from.date()
            d2 = self.date_to.date()
            if d1 > d2:
                d1, d2 = d2, d1
            d1_str = d1.toString("yyyy-MM-dd")
            d2_str = d2.toString("yyyy-MM-dd")
            rows: List[Dict[str, Any]] = []
            if stats and hasattr(stats, "get_period_profit_report"):
                try:
                    rows = stats.get_period_profit_report(d1_str, d2_str) or []
                except Exception:
                    rows = []
            self._rows = rows
            self._render_period_kpis_and_table(d1, d2)
            self._render_period_chart(d1, d2)
            return

        if sync_years:
            self._sync_years_combo()
        yr = int(self.cbo_year.currentData() or self._current_year)
        self._current_year = yr

        rows = []
        if stats and hasattr(stats, "get_monthly_profit_report"):
            try:
                rows = stats.get_monthly_profit_report(yr) or []
            except Exception:
                rows = []
        if not rows:
            rows = [
                {
                    "month": m,
                    "revenue": 0.0,
                    "avg_cost": 0.0,
                    "decharges": 0.0,
                    "gross_profit": 0.0,
                    "profit": 0.0,
                    "units_sold": 0.0,
                    "sales_count": 0,
                }
                for m in range(1, 13)
            ]

        self._rows = rows
        self._render_year_kpis_and_table()
        self._render_year_chart()

    def _update_kpi_totals(self, profit_label: str, best_label: str, best_text: str) -> None:
        tot_rev = sum(float(r.get("revenue") or 0.0) for r in self._rows)
        tot_cost = sum(float(r.get("avg_cost") or 0.0) for r in self._rows)
        tot_dech = sum(float(r.get("decharges") or 0.0) for r in self._rows)
        tot_profit = sum(float(r.get("profit") or 0.0) for r in self._rows)

        self.lbl_kpi_profit_title.setText(profit_label)
        self.lbl_kpi_profit.setText(f"{format_money(tot_profit)} DA")
        self.lbl_kpi_profit.setStyleSheet(
            f"font-size: 16.5px; font-weight: 800; color: {'#0E7471' if tot_profit >= 0 else '#DC2626'};"
        )
        self.lbl_kpi_rev.setText(f"{format_money(tot_rev)} DA")
        self.lbl_kpi_cost.setText(f"{format_money(tot_cost)} DA")
        self.lbl_kpi_dech.setText(f"{format_money(tot_dech)} DA")
        self.lbl_kpi_best_title.setText(best_label)
        self.lbl_kpi_best.setText(best_text)

    def _populate_table_row(self, row_idx: int, label: str, r: Dict[str, Any], highlight_label: bool = False) -> None:
        bold = QFont("Segoe UI", 10, QFont.Bold)
        rev = float(r.get("revenue") or 0.0)
        cost = float(r.get("avg_cost") or 0.0)
        dech = float(r.get("decharges") or 0.0)
        prof = float(r.get("profit") or 0.0)
        units = float(r.get("units_sold") or 0.0)
        s_cnt = int(r.get("sales_count") or 0)
        margin = (prof / rev * 100.0) if rev > 0 else 0.0

        it_lbl = QTableWidgetItem(label)
        it_lbl.setFont(bold if highlight_label else QFont("Segoe UI", 10))
        self.table.setItem(row_idx, 0, it_lbl)

        it_cnt = QTableWidgetItem(str(s_cnt))
        it_cnt.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row_idx, 1, it_cnt)

        it_u = QTableWidgetItem(f"{units:g}")
        it_u.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row_idx, 2, it_u)

        it_rev = QTableWidgetItem(f"{format_money(rev)} DA")
        it_rev.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row_idx, 3, it_rev)

        it_cost = QTableWidgetItem(f"{format_money(cost)} DA")
        it_cost.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row_idx, 4, it_cost)

        it_dech = QTableWidgetItem(f"{format_money(dech)} DA")
        it_dech.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        it_dech.setForeground(QColor("#DC2626" if dech > 0 else "#64748B"))
        self.table.setItem(row_idx, 5, it_dech)

        it_prof = QTableWidgetItem(f"{format_money(prof)} DA")
        it_prof.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        it_prof.setFont(bold)
        it_prof.setForeground(QColor("#15803D" if prof > 0 else ("#DC2626" if prof < 0 else "#64748B")))
        self.table.setItem(row_idx, 6, it_prof)

        it_mg = QTableWidgetItem(f"{margin:.1f} %")
        it_mg.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row_idx, 7, it_mg)

    def _append_total_row(self, total_label: str) -> None:
        bold = QFont("Segoe UI", 10, QFont.Bold)
        tot_rev = sum(float(r.get("revenue") or 0.0) for r in self._rows)
        tot_cost = sum(float(r.get("avg_cost") or 0.0) for r in self._rows)
        tot_dech = sum(float(r.get("decharges") or 0.0) for r in self._rows)
        tot_profit = sum(float(r.get("profit") or 0.0) for r in self._rows)
        tot_units = sum(float(r.get("units_sold") or 0.0) for r in self._rows)
        tot_sales = sum(int(r.get("sales_count") or 0) for r in self._rows)
        tot_margin = (tot_profit / tot_rev * 100.0) if tot_rev > 0 else 0.0

        t_row = self.table.rowCount()
        self.table.insertRow(t_row)
        totals_cells = [
            (total_label, Qt.AlignLeft | Qt.AlignVCenter),
            (str(tot_sales), Qt.AlignCenter),
            (f"{tot_units:g}", Qt.AlignCenter),
            (f"{format_money(tot_rev)} DA", Qt.AlignRight | Qt.AlignVCenter),
            (f"{format_money(tot_cost)} DA", Qt.AlignRight | Qt.AlignVCenter),
            (f"{format_money(tot_dech)} DA", Qt.AlignRight | Qt.AlignVCenter),
            (f"{format_money(tot_profit)} DA", Qt.AlignRight | Qt.AlignVCenter),
            (f"{tot_margin:.1f} %", Qt.AlignRight | Qt.AlignVCenter),
        ]
        for col, (txt, align) in enumerate(totals_cells):
            it = QTableWidgetItem(txt)
            it.setTextAlignment(align)
            it.setFont(bold)
            it.setBackground(QBrush(QColor("#F0FDFA")))
            if col == 5:
                it.setForeground(QColor("#DC2626" if tot_dech > 0 else "#64748B"))
            elif col == 6:
                it.setForeground(QColor("#0E7471" if tot_profit >= 0 else "#DC2626"))
            self.table.setItem(t_row, col, it)

    def _render_year_kpis_and_table(self) -> None:
        best_row = max(self._rows, key=lambda r: float(r.get("profit") or 0.0), default=None)
        if best_row and float(best_row.get("profit") or 0.0) > 0:
            best_m = MONTH_NAMES_FR[int(best_row["month"]) - 1]
            best_text = f"{best_m} ({format_money(best_row['profit'])} DA)"
        else:
            best_text = "—"

        self._update_kpi_totals("BÉNÉFICE NET ANNUEL", "MEILLEUR MOIS", best_text)
        self.table.horizontalHeaderItem(0).setText("Mois")
        self.table.setRowCount(0)

        now_month = datetime.now().month if self._current_year == datetime.now().year else -1
        for idx, r in enumerate(self._rows):
            self.table.insertRow(idx)
            m_num = int(r.get("month") or (idx + 1))
            m_name = MONTH_NAMES_FR[m_num - 1] if 1 <= m_num <= 12 else f"Mois {m_num}"
            if m_num == now_month:
                m_name = f"{m_name} (En cours)"
            self._populate_table_row(idx, m_name, r, highlight_label=(m_num == now_month))

        self._append_total_row(f"TOTAL ANNUEL ({self._current_year})")

    def _render_period_kpis_and_table(self, d1: QDate, d2: QDate) -> None:
        best_row = max(self._rows, key=lambda r: float(r.get("profit") or 0.0), default=None)
        if best_row and float(best_row.get("profit") or 0.0) > 0:
            best_text = f"{best_row['date']} ({format_money(best_row['profit'])} DA)"
        else:
            best_text = "—"

        self._update_kpi_totals("BÉNÉFICE NET (PÉRIODE)", "MEILLEUR JOUR", best_text)
        self.table.horizontalHeaderItem(0).setText("Date")
        self.table.setRowCount(0)

        for idx, r in enumerate(self._rows):
            self.table.insertRow(idx)
            d_str = str(r.get("date") or "")
            qd = QDate.fromString(d_str, "yyyy-MM-dd")
            lbl = qd.toString("dd/MM/yyyy") if qd.isValid() else d_str
            self._populate_table_row(idx, lbl, r)

        p_lbl = f"TOTAL ({d1.toString('dd/MM/yyyy')} → {d2.toString('dd/MM/yyyy')})"
        self._append_total_row(p_lbl)

    def _draw_profit_bars(self, labels: List[str], profits: List[float], title: str) -> None:
        if not (HAS_MPL and self._figure and self._canvas):
            return
        self._figure.clear()
        ax = self._figure.add_subplot(111)
        if not labels:
            ax.text(0.5, 0.5, "Aucune opération sur cette période", ha="center", va="center", color="#64748B", fontsize=10)
            ax.set_axis_off()
            self._canvas.draw()
            return

        bar_colors = ["#0E7471" if p >= 0 else "#DC2626" for p in profits]
        bars = ax.bar(labels, profits, color=bar_colors, width=0.58, edgecolor="none")
        ax.axhline(0, color="#CBD5E1", linewidth=0.8)
        ax.set_title(title, fontsize=10.5, fontweight="bold", color="#0F172A", pad=8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#E2E8F0")
        ax.spines["bottom"].set_color("#CBD5E1")
        ax.tick_params(axis="both", labelsize=8.5, colors="#475569")
        if len(labels) > 12:
            ax.tick_params(axis="x", rotation=35)
        ax.grid(axis="y", linestyle="--", alpha=0.35, color="#94A3B8")
        ax.set_axisbelow(True)

        for bar, val in zip(bars, profits):
            if abs(val) > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    bar.get_height(),
                    f"{val:,.0f}",
                    ha="center",
                    va="bottom" if val >= 0 else "top",
                    fontsize=7.5,
                    color="#334155",
                    fontweight="bold",
                )

        self._figure.tight_layout()
        self._canvas.draw()

    def _render_year_chart(self) -> None:
        profits = [float(r.get("profit") or 0.0) for r in self._rows]
        self._draw_profit_bars(
            MONTH_SHORT_FR,
            profits,
            f"Évolution du Bénéfice Net Mensuel (après Décharges) — {self._current_year} (DA)",
        )

    def _render_period_chart(self, d1: QDate, d2: QDate) -> None:
        labels = []
        profits = []
        for r in self._rows:
            qd = QDate.fromString(str(r.get("date") or ""), "yyyy-MM-dd")
            labels.append(qd.toString("dd/MM") if qd.isValid() else str(r.get("date") or ""))
            profits.append(float(r.get("profit") or 0.0))
        self._draw_profit_bars(
            labels,
            profits,
            f"Bénéfice Net par Jour ({d1.toString('dd/MM/yyyy')} → {d2.toString('dd/MM/yyyy')}) (DA)",
        )
