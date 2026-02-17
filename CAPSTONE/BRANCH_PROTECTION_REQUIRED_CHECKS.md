# Branch Protection Required Checks

This project uses 15 project-gate checks from `.github/workflows/project-gates.yml`.

## Required Check Names
- p01-nexus-gateway
- p02-oracle-research
- p03-spark-pages
- p04-forge-studio
- p05-chronicle-replay
- p06-canvas-runtime
- p07-echo-voice
- p08-legion-swarm
- p09-bazaar-marketplace
- p10-phantom-browser
- p11-mnemo-memory
- p12-aegis-safety
- p13-orbit-mobile
- p14-watchtower-ops
- p15-gateway-api

Source file: `ci/project_required_checks.txt`

## Apply via GitHub CLI

Prerequisites:
- Branch protection must already be enabled for the branch.
- You need admin permission on the repository.
- `gh auth login` must be configured.

Command:

```bash
scripts/github/set_branch_protection_checks.sh <owner/repo> main
```

Example:

```bash
scripts/github/set_branch_protection_checks.sh your-org/arcturus main
```
