# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in this repository.

## What this is

Customer Intelligence Platform: churn prediction, predictive CLV, behavioral
segmentation, customer-360 analytics, cohort/retention analytics, SHAP
explainability, and a transparent retention simulator, served through a
FastAPI + PostgreSQL backend and a Next.js dashboard. Full spec:
`Customer_Intelligence_Platform_Complete_Project_Guide.docx`. Architecture,
roadmap, and repository layout: `docs/architecture.md`.

This is a **single git repository** — `src/`, `frontend/`, `scripts/`,
`tests/`, `notebooks/`, and `docs/` all live in and commit from this one
repo root. There's no separate repo per side and no "wrong folder" gotcha
to worry about the way a multi-repo project has.

## Git Commit Rule

After **every** change (not a judgment call — every time), give commit
messages for it, grouped and formatted exactly like this:

1. State which side each group of changes belongs to as a heading —
   `Backend` (`src/`, `scripts/`, `tests/`, `notebooks/`, backend-specific
   `docs/*.md`, `Dockerfile`, `docker-compose.yml`, `pyproject.toml`,
   `conftest.py`, `.env.example`), `Frontend` (everything under
   `frontend/`, including `frontend/Dockerfile`), or `General` for changes
   that are neither (root `README.md`, `.gitignore`, cross-cutting
   `docs/*.md` like `docs/architecture.md` or `docs/deployment.md`, the
   project guide docx). If multiple sides changed, say which should be
   committed first and why.
2. Under each heading, one block per logical commit:
   ```
   git add <exact file names, no `-A` or `.`>
   git commit -m "<type>(<scope>): <summary>"
   ```
   Conventional Commits style (`feat`, `fix`, `chore`, `refactor`, `docs`,
   `test`), message explains *why*, not just what.
3. Do **not** append `Co-Authored-By: Claude` (or any Claude/Anthropic
   attribution).
4. Claude must only *give* these as text — never run `git add`/`git commit`
   on the user's behalf. Committing stays a manual, user-driven action.

If a change is trivial enough that no commit is warranted (exploratory/
scratch edits), say so instead of manufacturing one.
