"""
Smart Equity Transaction Intelligence
Phase 9 — Advanced Dashboard Orchestrator

This module combines the validated analytics engines without modifying them.
It is intentionally independent from the PySide6 UI.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from app.analytics import metrics as m
from app.analytics import data_integrity
from app.analytics import daily_player
from app.analytics import new_exited_shareholders
from app.analytics import accumulation_distribution
from app.analytics import round_trip
from app.analytics import anomaly
from app.analytics import behavior_correlation
from app.analytics import concentration


def run_dashboard(
    conn: sqlite3.Connection,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, Any]:
    """
    Build the Phase 9 dashboard data model.

    The metrics section respects the requested date range.
    The validated Phase 1–8 engines are read-only and currently operate
    on the complete available dataset, so their results are explicitly
    kept under dataset_analysis.

    No database mutation is performed.
    """

    conn.row_factory = sqlite3.Row

    # ------------------------------------------------------------------
    # Period-sensitive dashboard metrics
    # ------------------------------------------------------------------
    overview = m.overview(conn, start, end)
    price_series = m.price_series(conn, start, end)

    top_buyers = m.top_persons(
        conn,
        "buyer",
        start,
        end,
        top_n=10,
        by="value",
    )

    top_sellers = m.top_persons(
        conn,
        "seller",
        start,
        end,
        top_n=10,
        by="value",
    )

    top_buyer_brokers = m.top_brokers(
        conn,
        "buyer",
        start,
        end,
        top_n=10,
    )

    top_seller_brokers = m.top_brokers(
        conn,
        "seller",
        start,
        end,
        top_n=10,
    )

    broker_net_position = m.broker_net_position(
        conn,
        start,
        end,
        top_n=10,
    )

    person_net_position = m.net_position_persons(
        conn,
        start,
        end,
        top_n=10,
    )

    individual_vs_institutional = m.individual_vs_institutional(
        conn,
        start,
        end,
    )

    # ------------------------------------------------------------------
    # Validated Phase 1–8 engines
    # ------------------------------------------------------------------
    phase1 = data_integrity.run_data_integrity(conn)
    phase2 = daily_player.run_daily_player_analysis(conn)
    phase3 = new_exited_shareholders.run_new_exited_shareholders(conn)
    phase4 = accumulation_distribution.run_accumulation_distribution(conn)
    phase5 = round_trip.run_round_trip(conn)
    phase6 = anomaly.run_anomaly_detection(conn)
    phase7 = behavior_correlation.run_behavior_correlation(conn)
    phase8 = concentration.run_concentration_analysis(conn)

    result: dict[str, Any] = {
        "ready": bool(overview),

        "period": {
            "start": start,
            "end": end,
            "overview": overview,
            "price_series": price_series,
            "top_buyers": top_buyers,
            "top_sellers": top_sellers,
            "top_buyer_brokers": top_buyer_brokers,
            "top_seller_brokers": top_seller_brokers,
            "broker_net_position": broker_net_position,
            "person_net_position": person_net_position,
            "individual_vs_institutional": individual_vs_institutional,
        },

        "dataset_analysis": {
            "data_integrity": phase1,
            "daily_player": phase2,
            "new_exited_shareholders": phase3,
            "accumulation_distribution": phase4,
            "round_trip": phase5,
            "anomaly": phase6,
            "behavior_correlation": phase7,
            "concentration": phase8,
        },

        "methodology": {
            "period_metrics": "Metrics in the period section respect start/end.",
            "phase_engines": (
                "Phase 1–8 engines operate on the complete available dataset "
                "because their current public APIs accept only a database connection."
            ),
            "read_only": True,
            "synthetic_scores": False,
            "ranking_score": False,
        },
    }

    result["validation"] = validate_dashboard_result(result)

    return result


def validate_dashboard_result(result: dict[str, Any]) -> dict[str, Any]:
    """
    Validate the structural integrity of a dashboard result.

    This validation does not judge the quality of any investment,
    trading decision, person, broker, or market participant.
    """

    checks: dict[str, Any] = {
        "result_present": isinstance(result, dict),
        "ready_present": "ready" in result,
        "period_present": isinstance(result.get("period"), dict),
        "dataset_analysis_present": isinstance(
            result.get("dataset_analysis"), dict
        ),
        "methodology_present": isinstance(
            result.get("methodology"), dict
        ),
    }

    period = result.get("period", {})
    dataset = result.get("dataset_analysis", {})

    checks["overview_present"] = isinstance(
        period.get("overview"), dict
    )
    checks["price_series_present"] = isinstance(
        period.get("price_series"), list
    )

    required_engines = (
        "data_integrity",
        "daily_player",
        "new_exited_shareholders",
        "accumulation_distribution",
        "round_trip",
        "anomaly",
        "behavior_correlation",
        "concentration",
    )

    for name in required_engines:
        checks[f"{name}_present"] = isinstance(
            dataset.get(name), dict
        )

    checks["read_only"] = (
        result.get("methodology", {}).get("read_only") is True
    )
    checks["synthetic_scores_disabled"] = (
        result.get("methodology", {}).get("synthetic_scores") is False
    )
    checks["ranking_score_disabled"] = (
        result.get("methodology", {}).get("ranking_score") is False
    )

    valid = all(bool(value) for value in checks.values())

    return {
        "valid": valid,
        "checks": checks,
    }


def audit_dashboard(
    db_path: str,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, Any]:
    """
    Convenience audit entry point for the Phase 9 engine.
    """

    conn = sqlite3.connect(db_path)

    try:
        result = run_dashboard(conn, start, end)
        return {
            "valid": result.get("validation", {}).get("valid", False),
            "validation": result.get("validation", {}),
            "ready": result.get("ready", False),
            "period": result.get("period", {}),
            "dataset_analysis": result.get("dataset_analysis", {}),
        }
    finally:
        conn.close()
