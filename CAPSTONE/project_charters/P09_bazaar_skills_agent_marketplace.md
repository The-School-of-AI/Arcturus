# PROJECT 9: "Bazaar" — Skills & Agent Marketplace


> **Inspired by:** OpenClaw (ClawHub skills registry), existing scaling plan (Project "Bazaar")
> **Team:** Platform & Ecosystem · **Priority:** P1 · **Duration:** 4 weeks

### Objective
Build an **App Store for AI skills and agents** where users can discover, install, and publish skills — creating a community-driven ecosystem that continuously expands Arcturus's capabilities.

### Detailed Features

#### 9.1 Skills Registry
- **Discovery:** Searchable catalog with categories, ratings, install counts, author profiles
- **Categories:** Productivity, Development, Research, Communication, Finance, Education, Entertainment, Integrations
- **Skill pages:** Each skill has a detail page with description, screenshots, reviews, changelog, permissions required
- **Version management:** Semantic versioning, auto-update with user opt-in
- **Permissions model:** Each skill declares what tools/APIs it needs, user grants permissions on install

#### 9.2 Skill Development Kit (SDK)
- **Skill manifest:** YAML schema defining skill metadata, triggers, tools, prompts
- **Skill template generator:** `arcturus skill create <name>` — scaffold new skill project
- **Local testing:** `arcturus skill test <name>` — run skill in sandboxed environment
- **Documentation generator:** Auto-generate skill docs from manifest and code
- **Publishing flow:** `arcturus skill publish` — validate, package, upload to registry

#### 9.3 Pre-Built Premium Skills
- **Email Manager:** Gmail/Outlook integration — read, compose, schedule, categorize
- **Calendar Agent:** Google/Outlook calendar — scheduling, conflict detection, meeting prep
- **Code Reviewer:** GitHub PR review agent — code analysis, security scanning, style checks
- **Research Assistant:** Deep web research with auto-report generation (uses Project 2)
- **Data Analyst:** Upload data → auto-analysis, visualization, insights (uses Project 4)
- **Social Media Manager:** Twitter/LinkedIn post drafting, scheduling, analytics

#### 9.4 Monetization
- **Free tier:** Community skills with ads-free experience
- **Premium skills:** Creator-set pricing via Stripe Connect
- **Revenue share:** 70/30 split (creator/platform)
- **Subscription bundles:** Monthly subscription for access to all premium skills

#### 9.5 Deliverables
- `marketplace/registry.py` — skill registry API (CRUD, search, reviews, versioning)
- `marketplace/sdk/` — skill development kit (CLI tools, templates, validators)
- `marketplace/install.py` — skill installer with permission management
- `marketplace/billing.py` — Stripe Connect integration for payments
- Frontend: `features/marketplace/` — browse, search, install, publish, review UI
- `routers/marketplace.py` — API endpoints

### Strategy
- Seed marketplace with 20+ first-party skills to establish quality bar
- Existing `core/skills/` directory already has YAML skill definitions — migrate these as the first marketplace entries
- Open-source the SDK to attract community contributors

---

## 20-Day Execution Addendum

### Team Split
- Student A: Registry backend, package metadata, discovery APIs.
- Student B: Installer, trust checks, and marketplace UI.

### Day Plan
- Days 1-5: Skill package spec and publish/install flow.
- Days 6-10: Signature/hash validation and trust policy.
- Days 11-15: SDK commands and local test harness.
- Days 16-20: Rollback, moderation, and abuse controls.

### Mandatory Test Gate
- Acceptance: `tests/acceptance/p09_bazaar/test_tampered_skill_is_blocked.py`
- Integration: `tests/integration/test_bazaar_skill_install_execution.py`
- CI required check: `p09-bazaar-marketplace`

### Expanded Mandatory Test Gate Contract (10 Hard Conditions)

#### Acceptance Hard Conditions
1. The acceptance file declared above must exist and contain at least 8 executable test cases.
2. Happy-path user flow must pass end-to-end for this project's core feature.
3. Invalid-input and malformed-payload behavior must return controlled errors (no crashes).
4. Retry/idempotency behavior must be validated where external calls or queued tasks are used.
5. Publishing, installing, pinning, upgrading, rollback, and uninstall flows must all be tested; tampered packages must be blocked.

#### Integration Hard Conditions
6. The integration file declared above must exist and include at least 5 executable integration scenarios.
7. Integration must prove installed skills are executable in real agent runs and subject to Aegis/tool policy enforcement.
8. Cross-project failure propagation must be tested (upstream failure to graceful downstream behavior with logs/metrics).

#### CI And Delivery Hard Conditions
9. CI check p09-bazaar-marketplace must run and require all of the following:
   - project acceptance tests,
   - project integration tests,
   - baseline regression suite: scripts/test_all.sh quick (the earlier consolidated test baseline),
   - lint/typecheck for touched code paths.
10. Branch delivery evidence is mandatory:
   - add CAPSTONE/project_charters/P09_DELIVERY_README.md,
   - include sections: Scope Delivered, Architecture Changes, API/UI Changes, Test Evidence, Known Gaps, Rollback Plan, Demo Steps,
   - CI fails if this README file is missing,
   - project P95 target: < 2.5s install metadata resolution.
