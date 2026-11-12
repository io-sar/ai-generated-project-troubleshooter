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
