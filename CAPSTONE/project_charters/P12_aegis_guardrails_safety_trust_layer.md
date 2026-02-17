# PROJECT 12: "Aegis" — Guardrails, Safety & Trust Layer


> **Inspired by:** Perplexity (anti-hallucination, confidence scores, source transparency), OpenClaw (security model, DM pairing), existing scaling plan (Project "Aegis")
> **Team:** Safety & Trust Engineering · **Priority:** P0 · **Duration:** 4 weeks

### Objective
Build a comprehensive **safety and trust layer** that prevents prompt injection, detects hallucination, ensures source accuracy, and manages content policies — making Arcturus enterprise-safe.

### Detailed Features

#### 12.1 Prompt Injection Defense
- **Input scanning:** NeMo Guardrails or Lakera Guard integration for real-time input analysis
- **Instruction hierarchy:** System vs user vs tool prompts with strict privilege boundaries
- **Canary tokens:** Inject trackers to detect prompt leakage
- **Jailbreak detection:** Pattern-matching + ML classifier for known jailbreak patterns
- **Rate limiting:** Per-user and per-session rate limits on sensitive operations

#### 12.2 Anti-Hallucination System
- **Confidence scoring:** Per-claim confidence score (0-1) displayed inline
- **Citation verification:** Auto-verify cited sources actually contain the claimed information
- **Contradiction alerts:** Flag when agent response contradicts its own prior statements or established facts
- **Unsupported claim detection:** Highlight claims that lack source backing
- **Fact-checking pipeline:** Optional post-generation fact-check agent that verifies key claims

#### 12.3 Content Policy Engine
- **Configurable policies:** YAML-defined content policies (no PII exposure, no harmful content, domain-specific rules)
- **Output scanning:** Real-time output scanning against policy before delivery to user
- **PII detection & redaction:** Automatically detect and mask PII in agent outputs
- **Audit logging:** Every policy violation logged with full context for review

#### 12.4 Trust Dashboard
- **Per-response trust score:** Aggregate score based on source quality, confidence, and policy compliance
- **Source transparency:** One-click access to all sources used in generating a response
- **Bias detection:** Flag potential bias in sources or response (using sentiment/perspective analysis)
- **User feedback loop:** Thumbs up/down on responses → feeds back into quality improvement

#### 12.5 Deliverables
- `safety/input_scanner.py` — prompt injection detection middleware
- `safety/hallucination.py` — confidence scoring and claim verification
- `safety/policy_engine.py` — configurable content policy engine
- `safety/pii_detector.py` — PII detection and redaction
- `safety/audit.py` — comprehensive audit logging
- Frontend: `features/safety/` — trust score display, source panel, feedback buttons
- Config: `config/safety_policies.yaml` — default and custom safety policies

### Strategy
- Integrate safety as middleware in `core/loop.py` — intercept both input and output
- Start with prompt injection defense (week 1-2), then anti-hallucination (week 3-4), then content policies (week 5-6)
- Make safety configurable per-user and per-organization for enterprise flexibility

---

## 20-Day Execution Addendum

### Team Split
- Student A: Injection and policy-defense middleware.
- Student B: Hallucination checks, confidence/trace transparency UI.

### Day Plan
- Days 1-5: Prompt/tool injection defense layer.
- Days 6-10: Fact-check hooks and confidence scoring.
- Days 11-15: PII and content policy enforcement.
- Days 16-20: Safety red-team suite and audit output.

### Mandatory Test Gate
- Acceptance: `tests/acceptance/p12_aegis/test_injection_attempts_blocked.py`
- Integration: `tests/integration/test_aegis_enforcement_on_oracle_and_legion.py`
- CI required check: `p12-aegis-safety`

### Expanded Mandatory Test Gate Contract (10 Hard Conditions)

#### Acceptance Hard Conditions
1. The acceptance file declared above must exist and contain at least 8 executable test cases.
2. Happy-path user flow must pass end-to-end for this project's core feature.
3. Invalid-input and malformed-payload behavior must return controlled errors (no crashes).
4. Retry/idempotency behavior must be validated where external calls or queued tasks are used.
5. Prompt injection, tool jailbreak, and PII leakage scenarios must be blocked/redacted; confidence scoring must support abstain behavior.

#### Integration Hard Conditions
6. The integration file declared above must exist and include at least 5 executable integration scenarios.
7. Integration must prove Aegis enforcement applies consistently across Nexus, Oracle, Legion, and Gateway entry points.
8. Cross-project failure propagation must be tested (upstream failure to graceful downstream behavior with logs/metrics).

#### CI And Delivery Hard Conditions
9. CI check p12-aegis-safety must run and require all of the following:
   - project acceptance tests,
   - project integration tests,
   - baseline regression suite: scripts/test_all.sh quick (the earlier consolidated test baseline),
   - lint/typecheck for touched code paths.
10. Branch delivery evidence is mandatory:
   - add CAPSTONE/project_charters/P12_DELIVERY_README.md,
   - include sections: Scope Delivered, Architecture Changes, API/UI Changes, Test Evidence, Known Gaps, Rollback Plan, Demo Steps,
   - CI fails if this README file is missing,
   - project P95 target: < 120ms policy evaluation latency.
