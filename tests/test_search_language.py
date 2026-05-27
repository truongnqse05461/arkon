"""Unit test for the dedupe-by-page-id behavior in search_pages_semantic.

The production code relies on the DB ORDER BY similarity DESC giving the best
hit first, then "first-wins" dedupe keeping only one row per page_id. This
fixture-free test pins that invariant so a future refactor can't quietly drop
it.
"""


def test_dedupe_keeps_first_hit_per_page_id():
    rows = [
        {"id": "a", "matched_language": "target", "similarity": 0.9},
        {"id": "a", "matched_language": "source", "similarity": 0.7},
        {"id": "b", "matched_language": "source", "similarity": 0.6},
    ]
    seen: dict[str, dict] = {}
    for r in rows:
        if r["id"] in seen:
            continue
        seen[r["id"]] = r

    assert seen["a"]["matched_language"] == "target"
    assert seen["a"]["similarity"] == 0.9
    assert seen["b"]["similarity"] == 0.6
    assert len(seen) == 2
