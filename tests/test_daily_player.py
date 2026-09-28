from app.analytics.daily_player import run_daily_player_analysis


DB_PATH = "data/smart_equity.db"
TARGET_DATE = "2026-09-14"


def _run():
    return run_daily_player_analysis(DB_PATH)


def _target_rows(result):
    return [
        row
        for row in result["rows"]
        if row["trade_date_gregorian"] == TARGET_DATE
    ]


def test_daily_player_target_day_counts():
    result = _run()
    rows = _target_rows(result)

    assert len(rows) == 199

    assert sum(row["position_status"] == "OBSERVABLE" for row in rows) == 165
    assert sum(row["position_status"] == "INSUFFICIENT_HISTORY" for row in rows) == 26
    assert sum(row["position_status"] == "DATA_CONFLICT" for row in rows) == 8

    assert sum(row["event_type"] == "ENTRY_OBSERVED" for row in rows) == 54
    assert sum(row["event_type"] == "FULL_EXIT_OBSERVED" for row in rows) == 20
    assert sum(row["event_type"] == "HEAVY_SELL_OBSERVED" for row in rows) == 8


def test_daily_player_registry_evidence_does_not_change_events():
    result = _run()
    rows = _target_rows(result)

    event_rows = [row for row in rows if row["event_type"] is not None]

    assert len(event_rows) == 82

    assert sum(
        row["event_type"] == "ENTRY_OBSERVED"
        for row in event_rows
    ) == 54

    assert sum(
        row["event_type"] == "FULL_EXIT_OBSERVED"
        for row in event_rows
    ) == 20

    assert sum(
        row["event_type"] == "HEAVY_SELL_OBSERVED"
        for row in event_rows
    ) == 8


def test_daily_player_heavy_sell_threshold_is_inclusive():
    result = _run()
    rows = {
        row["person_id"]: row
        for row in _target_rows(result)
    }

    row = rows[4326]

    assert row["position_before"] == 6_000_000
    assert row["sell_quantity"] == 3_000_000
    assert row["position_after"] == 3_000_000
    assert row["sell_ratio"] == 0.5
    assert row["event_type"] == "HEAVY_SELL_OBSERVED"


def test_daily_player_full_exit_is_distinct_from_heavy_sell():
    result = _run()
    rows = {
        row["person_id"]: row
        for row in _target_rows(result)
    }

    row = rows[920]

    assert row["position_before"] == 100_000
    assert row["sell_quantity"] == 100_000
    assert row["position_after"] == 0
    assert row["event_type"] == "FULL_EXIT_OBSERVED"


def test_daily_player_non_observable_rows_have_no_event():
    result = _run()

    for row in _target_rows(result):
        if row["position_status"] != "OBSERVABLE":
            assert row["event_type"] is None


def test_daily_player_registry_evidence_statuses():
    result = _run()
    rows = _target_rows(result)

    evidence_counts = {}

    for row in rows:
        status = row["registry_status"]
        evidence_counts[status] = evidence_counts.get(status, 0) + 1

    assert evidence_counts["REGISTRY_HISTORY_PRESENT"] == 79
    assert evidence_counts["REGISTRY_NEW_ON_SNAPSHOT"] == 1
    assert evidence_counts["NO_REGISTRY_MATCH"] == 119


def test_daily_player_registry_evidence_summary():
    result = _run()

    assert result["registry_evidence_rows"] == 8354
    assert result["registry_new_on_snapshot_count"] == 105


def test_daily_player_registry_fields_are_consistent():
    result = _run()

    valid_statuses = {
        "REGISTRY_HISTORY_PRESENT",
        "REGISTRY_NEW_ON_SNAPSHOT",
        "NO_REGISTRY_MATCH",
    }

    for row in _target_rows(result):
        assert row["registry_status"] in valid_statuses

        if row["registry_status"] == "NO_REGISTRY_MATCH":
            assert row["registry_opening_quantity"] is None
            assert row["registry_buy_quantity"] is None
            assert row["registry_sell_quantity"] is None
            assert row["registry_closing_quantity"] is None
            assert row["registry_match_method"] is None
            assert row["registry_match_confidence"] is None
