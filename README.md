# Arcturus

Arcturus is an agentic AI platform with a Python backend, Electron/React frontend, MCP tooling, memory systems, and a structured capstone execution program.

## Student Start Here
- Capstone master plan: `CAPSTONE/MASTER_20_DAY_PLAN.md`
- Capstone index: `CAPSTONE/README.md`
- Project charters (P01-P15): `CAPSTONE/project_charters/`
- Daily PR flow: `CAPSTONE/PR_REVIEW_OPERATING_FLOW.md`

## Repository Layout
- `core/` - agent loop, orchestration, reasoning, sandbox integration.
- `routers/` - API surfaces for runs, apps, MCP, settings, IDE paths.
- `mcp_servers/` - MCP servers (RAG, browser, sandbox, etc.).
- `platform-frontend/` - desktop/frontend client.
- `tests/` - baseline, acceptance, integration, stress/manual suites.
- `scripts/` - test runners, diagnostics, devtools, GitHub ops scripts.
- `CAPSTONE/` - project governance, charters, runbooks, and audit docs.

## Engineering Workflow
1. Create feature branch from `master`.
2. Implement only your assigned project scope.
3. Update `CAPSTONE/project_charters/PXX_DELIVERY_README.md` with evidence.
4. Run baseline locally:
   - `scripts/test_all.sh quick`
5. Open PR to `master`.

## CI Gates
PRs are validated by three workflow layers:
- `.github/workflows/ci.yml` - backend + frontend baseline checks.
- `.github/workflows/project-gates.yml` - project-specific acceptance + integration checks.
- `.github/workflows/extended-tests.yml` - optional extended/stress runs.

## Local Setup
### Backend
```bash
uv sync --python 3.11
```

### Frontend
```bash
cd platform-frontend
npm ci
```

### Baseline Tests
```bash
cd /path/to/Arcturus
scripts/test_all.sh quick
```

## Security Notes
- `.env` is intentionally untracked.
- Use `.env.example` as template for local secrets.
- Never commit real API keys.
