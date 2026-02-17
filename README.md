# Arcturus

Arcturus is an agentic AI platform with a Python backend, Electron/React frontend, MCP tooling, memory systems, and a structured capstone execution program.

## Capstone Objectives
The capstone program is designed to:
1. Deliver all 15 project tracks (P01-P15) within the 20-day execution window.
2. Enforce quality gates through acceptance tests, integration tests, and baseline regression checks.
3. Keep student work isolated in feature branches and merge only validated PRs into `master`.

## Start Here
- Capstone index: [CAPSTONE/README.md](CAPSTONE/README.md)
- 20-day master plan: [CAPSTONE/MASTER_20_DAY_PLAN.md](CAPSTONE/MASTER_20_DAY_PLAN.md)
- Project charters (P01-P15): [CAPSTONE/project_charters/](CAPSTONE/project_charters/)
- PR review workflow: [CAPSTONE/PR_REVIEW_OPERATING_FLOW.md](CAPSTONE/PR_REVIEW_OPERATING_FLOW.md)
- Student assignment template: [CAPSTONE/STUDENT_TEAM_ASSIGNMENTS_TEMPLATE.md](CAPSTONE/STUDENT_TEAM_ASSIGNMENTS_TEMPLATE.md)
- Live GitHub project board: [Arcturus Capstone 15 Projects](https://github.com/users/theschoolofai/projects/3)

## Repository Layout
- [core/](core/) - agent loop, orchestration, reasoning, sandbox integration.
- [routers/](routers/) - API surfaces for runs, apps, MCP, settings, IDE paths.
- [mcp_servers/](mcp_servers/) - MCP servers (RAG, browser, sandbox, etc.).
- [platform-frontend/](platform-frontend/) - desktop/frontend client.
- [tests/](tests/) - baseline, acceptance, integration, stress/manual suites.
- [scripts/](scripts/) - test runners, diagnostics, devtools, GitHub ops scripts.
- [CAPSTONE/](CAPSTONE/) - project governance, charters, runbooks, and audit docs.

## Engineering Workflow
1. Create feature branch from `master`.
2. Implement only your assigned project scope.
3. Update [CAPSTONE/project_charters/PXX_DELIVERY_README.md](CAPSTONE/project_charters/) with evidence.
4. Run baseline locally:
   - `scripts/test_all.sh quick`
5. Open PR to `master`.

## CI Gates
PRs are validated by three workflow layers:
- [.github/workflows/ci.yml](.github/workflows/ci.yml) - backend + frontend baseline checks.
- [.github/workflows/project-gates.yml](.github/workflows/project-gates.yml) - project-specific acceptance + integration checks.
- [.github/workflows/extended-tests.yml](.github/workflows/extended-tests.yml) - optional extended/stress runs.

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
