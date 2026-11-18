"""The RACI rule: each activity has exactly one Accountable (A).

Breaking the rule is a warning, not an error. The report still loads and exports, and the
rows that break it are shown.
"""

from troubleshooter.domain.codes import RaciCode
from troubleshooter.domain.models import RaciRow


def has_one_accountable(row: RaciRow) -> bool:
    accountable = [a for a in row.assignments if a.code is RaciCode.ACCOUNTABLE]
    return len(accountable) == 1


def rows_without_one_accountable(raci: list[RaciRow]) -> list[int]:
    """Positions of the rows that break the rule, so the app can highlight them."""
    return [index for index, row in enumerate(raci) if not has_one_accountable(row)]


def roles_in_order(raci: list[RaciRow]) -> list[str]:
    """Every role in the matrix, in the order it first appears, for the grid's columns."""
    return list(dict.fromkeys(a.role for row in raci for a in row.assignments))


def codes_by_role(row: RaciRow, roles: list[str]) -> dict[str, str]:
    """The codes each role holds in one row, joined, and empty for roles with no part.

    A role listed twice keeps both codes ("R, A") rather than silently losing one.
    """
    cells: dict[str, list[str]] = {role: [] for role in roles}
    for assignment in row.assignments:
        cells[assignment.role].append(assignment.code)
    return {role: ", ".join(codes) for role, codes in cells.items()}
