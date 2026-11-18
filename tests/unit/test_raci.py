import pytest

from troubleshooter.domain.models import RaciRow
from troubleshooter.domain.raci import (
    codes_by_role,
    has_one_accountable,
    roles_in_order,
    rows_without_one_accountable,
)


def make_row(*codes: str) -> RaciRow:
    """A row with one role per code: Role 1 gets the first code, and so on."""
    return RaciRow.model_validate(
        {
            "activity": "Weekly vendor checkpoint",
            "assignments": [
                {"role": f"Role {number}", "code": code} for number, code in enumerate(codes, 1)
            ],
        }
    )


@pytest.mark.parametrize(
    ("codes", "expected"),
    [
        ((), False),  # no one is assigned
        (("R", "C", "I"), False),  # zero A
        (("A",), True),
        (("A", "R", "C", "I"), True),
        (("A", "A"), False),
        (("A", "R", "A"), False),
    ],
)
def test_has_one_accountable(codes: tuple[str, ...], expected: bool) -> None:
    assert has_one_accountable(make_row(*codes)) is expected


def test_empty_table_has_no_broken_rows() -> None:
    assert rows_without_one_accountable([]) == []


def test_valid_table_has_no_broken_rows() -> None:
    assert rows_without_one_accountable([make_row("A", "R"), make_row("R", "A")]) == []


def test_broken_rows_are_found_by_position() -> None:
    raci = [make_row("A"), make_row("R"), make_row("A", "R"), make_row("A", "A")]

    assert rows_without_one_accountable(raci) == [1, 3]


def test_roles_keep_the_order_they_first_appear() -> None:
    rows = [make_row("A", "R"), make_row("C", "A", "I")]

    assert roles_in_order(rows) == ["Role 1", "Role 2", "Role 3"]


def test_no_rows_means_no_roles() -> None:
    assert roles_in_order([]) == []


def test_roles_with_no_part_get_an_empty_cell() -> None:
    row = make_row("A")

    assert codes_by_role(row, ["Role 1", "Role 2"]) == {"Role 1": "A", "Role 2": ""}


def test_a_role_listed_twice_keeps_both_codes() -> None:
    row = RaciRow.model_validate(
        {
            "activity": "Cutover",
            "assignments": [{"role": "PM", "code": "R"}, {"role": "PM", "code": "A"}],
        }
    )

    assert codes_by_role(row, ["PM"]) == {"PM": "R, A"}
