"""F-746-L2 — the worldview COUNTER line counts the manifest through the ONE shared
active-ray predicate, never raw projected rows.

RED (the retired shape): office-worldview.py:1101 rendered `len(sigs)` over every
row _jsonl_rows_effective returned — at the tic-746 boot that read '60 active ·
loudest sig_detected_drift_03045829c7cb (vol 45)' while the active population
was 58 (56 active + 2 acknowledged; two resolved-in-place duplicate drift rows
still in the file) and every sibling reader (governance_query signals.status,
the SIREN line, the crisis detector) read 58 through lib/signal_active.is_active_ray.
GREEN: _active_signal_rows filters through that predicate; the count and the
loudest are computed over the active population only.
"""
import importlib.util
import pathlib


def _load():
    here = pathlib.Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location("ow746", here / "office-worldview.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ROWS = [
    {"signal_id": "sig_a", "status": "active", "volume": 40, "band": "COGNITIVE"},
    {"signal_id": "sig_b", "status": "active", "volume": 12, "band": "PRIMITIVE"},
    {"signal_id": "sig_ack_cold", "status": "acknowledged", "volume": 0, "band": "COGNITIVE"},
    {"signal_id": "sig_detected_drift_x", "status": "resolved", "volume": 45, "band": "COGNITIVE"},
    {"signal_id": "sig_detected_drift_x", "status": "resolved", "volume": 45, "band": "COGNITIVE"},
]


def test_counter_population_is_the_shared_active_predicate():
    m = _load()
    active = m._active_signal_rows(ROWS)
    ids = sorted(r["signal_id"] for r in active)
    assert ids == ["sig_a", "sig_b"], ids
    # the resolved duplicate drift rows (the tic-746 live instance) are OUT of the population
    assert all(r["status"] != "resolved" for r in active)
    # NEGATIVE CONTROL — the retired shape (raw len) disagrees with the predicate population
    assert len(ROWS) == 5 and len(active) == 2


def test_loudest_is_chosen_over_the_active_population_only():
    m = _load()
    active = m._active_signal_rows(ROWS)
    loud = max(active, key=lambda s: s.get("effective_volume", s.get("volume", 0)))
    # the retired shape picked the resolved drift row (vol 45); the cure picks sig_a (vol 40)
    assert loud["signal_id"] == "sig_a", loud
    raw_loud = max(ROWS, key=lambda s: s.get("effective_volume", s.get("volume", 0)))
    assert raw_loud["signal_id"] == "sig_detected_drift_x"


def test_predicate_agrees_with_signal_active_module():
    m = _load()
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "lib"))
    from signal_active import active_rays
    assert [r["signal_id"] for r in m._active_signal_rows(ROWS)] == [r["signal_id"] for r in active_rays(ROWS)]
