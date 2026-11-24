# -*- coding: utf-8 -*-
"""
Monthly Profit Tab (Bénéfices Mensuels) for Tableau de Bord.
Displays real-time profit per month for the selected year (Jan..Dec),
computed dynamically whenever the user opens this tab using:
  Profit = Prix de Vente - Prix Moyen d'Achat (PMP).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
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
    """Full Dashboard tab showing monthly sales profit across all 12 months of a year."""

    def __init__(self, data_manager: Any, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.data_manager = data_manager
        self._current_year = datetime.now().year
        self._monthly_rows: List[Dict[str, Any]] = []
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
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # 1. Top Bar (Title + Year Selector + Refresh)
        top_bar = QFrame()
        top_bar.setObjectName("ProfitCard")
        tb_lay = QHBoxLayout(top_bar)
        tb_lay.setContentsMargins(14, 10, 14, 10)
        tb_lay.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        lbl_title = QLabel("Bénéfices Mensuels par Année")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #0F172A;")
        lbl_sub = QLabel("Calcul en temps réel : Prix de Vente − Prix Moyen d'Achat (PMP)")
        lbl_sub.setStyleSheet("font-size: 12px; color: #64748B;")
        title_col.addWidget(lbl_title)
        title_col.addWidget(lbl_sub)
        tb_lay.addLayout(title_col)

        tb_lay.addStretch(1)

        lbl_yr = QLabel("Année :")
        lbl_yr.setStyleSheet("font-size: 12.5px; font-weight: 700; color: #334155;")
        tb_lay.addWidget(lbl_yr)

        self.cbo_year = QComboBox()
        self.cbo_year.setFixedHeight(34)
        self.cbo_year.setMinimumWidth(100)
        self.cbo_year.setStyleSheet(
            "QComboBox { background:#FFFFFF; border:1px solid #CBD5E1; border-radius:6px; "
            "padding:4px 10px; font-size:13px; font-weight:700; color:#0F172A; }"
        )
        self.cbo_year.addItem(str(self._current_year), self._current_year)
        self.cbo_year.currentIndexChanged.connect(self._on_year_changed)
        tb_lay.addWidget(self.cbo_year)

        self.btn_refresh = QPushButton("Actualiser")
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

        # 2. KPI Strip
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(10)

        self.lbl_kpi_profit, card_profit = self._make_kpi_card("BÉNÉFICE ANNUEL", "0,00 DA", "#0E7471")
        self.lbl_kpi_rev, card_rev = self._make_kpi_card("CHIFFRE D'AFFAIRES", "0,00 DA", "#0F172A")
        self.lbl_kpi_cost, card_cost = self._make_kpi_card("COÛT D'ACHAT MOYEN (PMP)", "0,00 DA", "#B45309")
        self.lbl_kpi_best, card_best = self._make_kpi_card("MEILLEUR MOIS", "—", "#15803D")

        for c in (card_profit, card_rev, card_cost, card_best):
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

        # 4. 12-Month Breakdown Table
        table_card = QFrame()
        table_card.setObjectName("ProfitCard")
        tc_lay = QVBoxLayout(table_card)
        tc_lay.setContentsMargins(10, 10, 10, 10)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Mois",
            "Ventes (Nb)",
            "Unités",
            "Chiffre d'Affaires",
            "Coût Moyen (PMP)",
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
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 7):
            hdr.setSectionResizeMode(col, QHeaderView.Stretch)

        tc_lay.addWidget(self.table, 1)
        root.addWidget(table_card, 1)

    def _make_kpi_card(self, label: str, value: str, color_hex: str):
        card = QFrame()
        card.setObjectName("ProfitCard")
        card.setFixedHeight(74)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(2)

        lbl_k = QLabel(label)
        lbl_k.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748B;")
        lbl_v = QLabel(value)
        lbl_v.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {color_hex};")
        lay.addWidget(lbl_k)
        lay.addWidget(lbl_v)
        return lbl_v, card

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
            self.refresh(sync_years=False)

    def refresh(self, sync_years: bool = True) -> None:
        if sync_years:
            self._sync_years_combo()
        yr = int(self.cbo_year.currentData() or self._current_year)
        self._current_year = yr

        stats = getattr(self.data_manager, "stats", None)
        rows: List[Dict[str, Any]] = []
        if stats and hasattr(stats, "get_monthly_profit_report"):
            try:
                rows = stats.get_monthly_profit_report(yr) or []
            except Exception:
                rows = []
        if not rows:
            rows = [
                {"month": m, "revenue": 0.0, "avg_cost": 0.0, "profit": 0.0, "units_sold": 0.0, "sales_count": 0}
                for m in range(1, 13)
            ]

        self._monthly_rows = rows
        self._render_kpis_and_table()
        self._render_chart()

    def _render_kpis_and_table(self) -> None:
        tot_rev = sum(float(r.get("revenue") or 0.0) for r in self._monthly_rows)
        tot_cost = sum(float(r.get("avg_cost") or 0.0) for r in self._monthly_rows)
        tot_profit = sum(float(r.get("profit") or 0.0) for r in self._monthly_rows)
        tot_units = sum(float(r.get("units_sold") or 0.0) for r in self._monthly_rows)
        tot_sales = sum(int(r.get("sales_count") or 0) for r in self._monthly_rows)

        best_row = max(self._monthly_rows, key=lambda r: float(r.get("profit") or 0.0), default=None)
        if best_row and float(best_row.get("profit") or 0.0) > 0:
            best_m = MONTH_NAMES_FR[int(best_row["month"]) - 1]
            best_text = f"{best_m} ({format_money(best_row['profit'])} DA)"
        else:
            best_text = "—"

        self.lbl_kpi_profit.setText(f"{format_money(tot_profit)} DA")
        self.lbl_kpi_rev.setText(f"{format_money(tot_rev)} DA")
        self.lbl_kpi_cost.setText(f"{format_money(tot_cost)} DA")
        self.lbl_kpi_best.setText(best_text)

        self.table.setRowCount(0)
        bold = QFont("Segoe UI", 10, QFont.Bold)
        now_month = datetime.now().month if self._current_year == datetime.now().year else -1

        for idx, r in enumerate(self._monthly_rows):
            self.table.insertRow(idx)
            m_num = int(r.get("month") or (idx + 1))
            m_name = MONTH_NAMES_FR[m_num - 1] if 1 <= m_num <= 12 else f"Mois {m_num}"
            if m_num == now_month:
                m_name = f"{m_name} (En cours)"

            rev = float(r.get("revenue") or 0.0)
            cost = float(r.get("avg_cost") or 0.0)
            prof = float(r.get("profit") or 0.0)
            units = float(r.get("units_sold") or 0.0)
            s_cnt = int(r.get("sales_count") or 0)
            margin = (prof / rev * 100.0) if rev > 0 else 0.0

            it_m = QTableWidgetItem(m_name)
            it_m.setFont(bold if m_num == now_month else QFont("Segoe UI", 10))
            self.table.setItem(idx, 0, it_m)

            it_cnt = QTableWidgetItem(str(s_cnt))
            it_cnt.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(idx, 1, it_cnt)

            it_u = QTableWidgetItem(f"{units:g}")
            it_u.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(idx, 2, it_u)

            it_rev = QTableWidgetItem(f"{format_money(rev)} DA")
            it_rev.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(idx, 3, it_rev)

            it_cost = QTableWidgetItem(f"{format_money(cost)} DA")
            it_cost.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(idx, 4, it_cost)

            it_prof = QTableWidgetItem(f"{format_money(prof)} DA")
            it_prof.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_prof.setFont(bold)
            it_prof.setForeground(QColor("#15803D" if prof > 0 else ("#DC2626" if prof < 0 else "#64748B")))
            self.table.setItem(idx, 5, it_prof)

            it_mg = QTableWidgetItem(f"{margin:.1f} %")
            it_mg.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(idx, 6, it_mg)

        # Total Annual Row
        t_row = self.table.rowCount()
        self.table.insertRow(t_row)
        tot_margin = (tot_profit / tot_rev * 100.0) if tot_rev > 0 else 0.0
        totals_cells = [
            (f"TOTAL ANNUEL ({self._current_year})", Qt.AlignLeft | Qt.AlignVCenter),
            (str(tot_sales), Qt.AlignCenter),
            (f"{tot_units:g}", Qt.AlignCenter),
            (f"{format_money(tot_rev)} DA", Qt.AlignRight | Qt.AlignVCenter),
            (f"{format_money(tot_cost)} DA", Qt.AlignRight | Qt.AlignVCenter),
            (f"{format_money(tot_profit)} DA", Qt.AlignRight | Qt.AlignVCenter),
            (f"{tot_margin:.1f} %", Qt.AlignRight | Qt.AlignVCenter),
        ]
        for col, (txt, align) in enumerate(totals_cells):
            it = QTableWidgetItem(txt)
            it.setTextAlignment(align)
            it.setFont(bold)
            it.setBackground(QBrush(QColor("#F0FDFA")))
            if col == 5:
                it.setForeground(QColor("#0E7471" if tot_profit >= 0 else "#DC2626"))
            self.table.setItem(t_row, col, it)

    def _render_chart(self) -> None:
        if not (HAS_MPL and self._figure and self._canvas):
            return
        self._figure.clear()
        ax = self._figure.add_subplot(111)
        profits = [float(r.get("profit") or 0.0) for r in self._monthly_rows]
        bar_colors = ["#0E7471" if p >= 0 else "#DC2626" for p in profits]
        bars = ax.bar(MONTH_SHORT_FR, profits, color=bar_colors, width=0.58, edgecolor="none")
        ax.axhline(0, color="#CBD5E1", linewidth=0.8)
        ax.set_title(f"Évolution du Bénéfice Mensuel — {self._current_year} (DA)", fontsize=10.5, fontweight="bold", color="#0F172A", pad=8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#E2E8F0")
        ax.spines["bottom"].set_color("#CBD5E1")
        ax.tick_params(axis="both", labelsize=8.5, colors="#475569")
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
