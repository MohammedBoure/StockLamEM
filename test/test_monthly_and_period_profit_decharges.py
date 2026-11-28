# -*- coding: utf-8 -*-
"""
Unit tests for Décharges deduction in Monthly & Period Profit reports
(StatisticsManager + MonthlyProfitTab).
"""

from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from database.statistics_manager import StatisticsManager


def _get_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_mock_db(sales_rows, decharge_rows):
    cursor = MagicMock()
    cursor.fetchall.side_effect = [sales_rows, decharge_rows]
    conn = MagicMock()
    conn.cursor.return_value = cursor

    @contextmanager
    def _get_db_connection():
        yield conn

    db = MagicMock()
    db.get_db_connection.side_effect = _get_db_connection
    return db, cursor


def test_monthly_profit_report_deducts_active_decharges():
    sales_rows = [
        {"month": 3, "revenue": 10000.0, "avg_cost": 6000.0, "gross_profit": 4000.0, "units_sold": 5.0, "sales_count": 2},
    ]
    decharge_rows = [
        {"m_num": 3, "decharges": 1500.0},
        {"m_num": 4, "decharges": 500.0},
    ]
    db, cursor = _make_mock_db(sales_rows, decharge_rows)
    stats = StatisticsManager(db)

    result = stats.get_monthly_profit_report(2026)

    assert len(result) == 12
    march = result[2]
    assert march["month"] == 3
    assert march["revenue"] == 10000.0
    assert march["avg_cost"] == 6000.0
    assert march["decharges"] == 1500.0
    assert march["profit"] == 2500.0  # 10000 - 6000 - 1500

    april = result[3]
    assert april["month"] == 4
    assert april["decharges"] == 500.0
    assert april["profit"] == -500.0

    # Ensure query filters only ACTIVE décharges
    decharge_sql = cursor.execute.call_args_list[1][0][0]
    assert "Status = 'ACTIVE'" in decharge_sql


def test_period_profit_report_deducts_decharges_per_day():
    sales_rows = [
        {"d_str": "2026-11-10", "revenue": 8000.0, "avg_cost": 5000.0, "gross_profit": 3000.0, "units_sold": 2.0, "sales_count": 1},
    ]
    decharge_rows = [
        {"d_str": "2026-11-10", "decharges": 1200.0},
        {"d_str": "2026-11-11", "decharges": 400.0},
    ]
    db, _ = _make_mock_db(sales_rows, decharge_rows)
    stats = StatisticsManager(db)

    result = stats.get_period_profit_report("2026-11-01", "2026-11-30")

    assert len(result) == 2
    assert result[0]["date"] == "2026-11-10"
    assert result[0]["decharges"] == 1200.0
    assert result[0]["profit"] == 1800.0  # 8000 - 5000 - 1200
    assert result[1]["date"] == "2026-11-11"
    assert result[1]["decharges"] == 400.0
    assert result[1]["profit"] == -400.0


def test_monthly_profit_tab_displays_decharges_in_year_and_period_modes():
    QtCore = pytest.importorskip("PySide6.QtCore")
    QtWidgets = pytest.importorskip("PySide6.QtWidgets")
    from ui.widgets.dashboard.monthly_profit_tab import MonthlyProfitTab

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])

    stats = MagicMock()
    stats.get_available_profit_years.return_value = [2026]
    stats.get_monthly_profit_report.return_value = [
        {
            "month": m,
            "revenue": 10000.0 if m == 1 else 0.0,
            "avg_cost": 6000.0 if m == 1 else 0.0,
            "decharges": 1000.0 if m == 1 else 0.0,
            "gross_profit": 4000.0 if m == 1 else 0.0,
            "profit": 3000.0 if m == 1 else 0.0,
            "units_sold": 2.0 if m == 1 else 0.0,
            "sales_count": 1 if m == 1 else 0,
        }
        for m in range(1, 13)
    ]
    stats.get_period_profit_report.return_value = [
        {
            "date": "2026-11-10",
            "revenue": 5000.0,
            "avg_cost": 3000.0,
            "decharges": 500.0,
            "gross_profit": 2000.0,
            "profit": 1500.0,
            "units_sold": 1.0,
            "sales_count": 1,
        }
    ]

    dm = MagicMock()
    dm.stats = stats

    tab = MonthlyProfitTab(dm)
    tab.refresh()

    assert tab.table.columnCount() == 8
    assert tab.table.horizontalHeaderItem(5).text() == "Décharges"
    assert "3 000" in tab.lbl_kpi_profit.text() or "3,000" in tab.lbl_kpi_profit.text()
    assert "1 000" in tab.lbl_kpi_dech.text() or "1,000" in tab.lbl_kpi_dech.text()

    # Switch to Period mode
    tab.set_period_dates(QtCore.QDate(2026, 11, 1), QtCore.QDate(2026, 11, 30))
    tab.btn_mode_period.click()

    assert tab.table.horizontalHeaderItem(0).text() == "Date"
    assert tab.table.rowCount() == 2  # 1 day + total row
    assert "1 500" in tab.lbl_kpi_profit.text() or "1,500" in tab.lbl_kpi_profit.text()
    assert "500" in tab.lbl_kpi_dech.text()
