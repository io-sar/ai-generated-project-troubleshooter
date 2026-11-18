from typing import Any

from troubleshooter.ui.report_view import raci_edits_from_grid, role_column
from troubleshooter.ui.state import RaciEdit


def test_grid_rows_become_edits_by_role() -> None:
    roles = ["PM", "Vendor manager"]
    rows: list[dict[str, Any]] = [
        {"activity": "Vendor follow-up", role_column(0): "A", role_column(1): "R", "check": ""},
        {"activity": "Release", role_column(0): None, role_column(1): "A", "edited": ""},
    ]

    assert raci_edits_from_grid(rows, roles) == [
        RaciEdit("Vendor follow-up", {"PM": "A", "Vendor manager": "R"}),
        RaciEdit("Release", {"PM": None, "Vendor manager": "A"}),
    ]


def test_added_row_with_missing_cells_has_no_codes() -> None:
    # A row added in the editor may lack keys for cells the visitor never touched.
    assert raci_edits_from_grid([{"activity": "New"}], ["PM"]) == [RaciEdit("New", {"PM": None})]


def test_role_columns_are_keyed_by_position() -> None:
    # Role names are report text, so they label columns but never serve as keys.
    assert [role_column(i) for i in range(3)] == ["role_0", "role_1", "role_2"]
