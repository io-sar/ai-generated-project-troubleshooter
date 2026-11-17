# ADR 0003: MIT licence

- **Status:** Accepted
- **Date:** 2026-11-17
- **Files:** [`LICENSE`](../../LICENSE), `license = "MIT"` in [`pyproject.toml`](../../pyproject.toml)

## Context
The repository is public so that recruiters and other readers can see how the app is built. It is a personal portfolio project and does not take outside contributions. Without a licence, public code is "all rights reserved", so a licence is needed for anyone to reuse it. The repository already ships the MIT licence; this record states why.

## Decision
The project is licensed under the MIT licence, declared in `LICENSE` and as the SPDX identifier `MIT` in `pyproject.toml`.

## Why
- MIT is short, widely known and lets anyone read, run and reuse the code, which suits a portfolio piece.
- The project has no patents to grant and no wish to keep derivative works open, so a longer or copyleft licence would add terms without benefit.

## Alternatives considered
- **Apache-2.0:** permissive like MIT and adds an explicit patent grant. Rejected as unnecessary for a project with no patent concerns.
- **AGPL-3.0 or GPL-3.0:** would keep hosted or distributed derivatives open. Rejected because it limits reuse, which works against the project's purpose.
- **No licence:** the code would be public but not reusable. Rejected.

## Consequences
- Anyone may reuse the code, including commercially, as long as the copyright notice is kept.
- Every dependency must have a licence compatible with MIT. The two direct runtime dependencies, Streamlit (Apache-2.0) and Pydantic (MIT), are compatible. A full check of the indirect dependencies is planned before the v0.1 release. GPL- or AGPL-licensed packages are not added.
- Changing the licence later only needs the author's agreement, because there are no outside contributors.
