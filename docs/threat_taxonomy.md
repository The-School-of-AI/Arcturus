# Aegis — Threat Taxonomy (Project-wide)

This document provides a comprehensive threat taxonomy covering the phases and deliverables of the Aegis project.

Usage
- Each threat entry lists examples, possible impact, and recommended mitigations. Use this as a living document — update when new failure modes are discovered during red‑teaming or integration testing.

Roadmap (numbered milestones)

1. Milestone 1 — Weeks 1–2: Prompt Injection & Tool Defenses
   - Deliverables: `safety/input_scanner.py`, canary token support, middleware hook in `core/loop.py`.
   - Acceptance: input scanning blocks or flags injected prompts; canary tokens detectable; basic acceptance tests present.

2. Milestone 2 — Weeks 3–4: Anti‑Hallucination & Verification
   - Deliverables: claim-level confidence scoring, citation verification pipeline, contradiction detection hooks.
   - Acceptance: system annotates claims with confidence, verifies at least one class of citation claims, and raises contradictions when detected.

3. Milestone 3 — Weeks 5–6: Policy Engine, PII, & Audit
   - Deliverables: `safety/policy_engine.py`, PII detectors/redactors, audit logging, Trust Dashboard skeleton.
   - Acceptance: policy engine enforces PII redaction and blocks a set of policy violations; audit logs capture events for review.

4. Ongoing Work
   - Deliverables: rate limiting, monitoring/telemetry, CI gates, red‑team testing, incident response playbook.
   - Acceptance: CI gates run safety acceptance/integration tests; monitoring and alerts for policy breaches and high-cost operations.


1. Prompt Injection
   - Examples:
     - Direct overrides: "ignore system prompt" or "now follow these new instructions".
     - Obfuscated overrides: punctuation/whitespace/Unicode obfuscation to hide malicious tokens.
     - Embedded canary tokens in user input or files that get exfiltrated in outputs.
   - Impact: unauthorized instruction execution, data exfiltration, tool misuse.
   - Mitigations: input scanning, instruction hierarchy enforcement (system > tool > user), canary detection, reject/escape suspicious inputs, robust logging.

2. Tool / Skill Jailbreak
   - Examples:
     - `call_tool` requests that try to run OS commands, read sensitive local files, or escalate privileges.
     - Tool outputs containing system prompts or sensitive tokens.
   - Impact: code execution, lateral movement, credential leakage.
   - Mitigations: whitelist tools, capability-based tool permissions, sandboxing, tool-level rate limits, output inspection.

3. PII Leakage & Sensitive Data Exposure
   - Examples: accidental return of emails, SSNs, API keys, or aggregated user data across sessions.
   - Impact: privacy breaches, compliance violations (e.g., GDPR), legal/financial risk.
   - Mitigations: PII detectors and redaction, policy engine rules, per-organization masking policies, audit trails, differential access controls.

4. Hallucination & Information Integrity
   - Examples:
     - Fabricated facts presented as true.
     - Misattributed or invented citations and sources.
     - Contradictions between agent responses or session history.
   - Impact: misinformation, loss of trust, downstream decision errors.
   - Mitigations: claim-level confidence scoring, citation verification pipeline, optional post‑generation fact‑check agent, contradiction detection, UI indicators (confidence, sources).

5. Malicious Content Generation (Policy Violations)
   - Examples: instructions for wrongdoing, hate speech, disallowed domain‑specific content.
   - Impact: legal/ethical issues, user harm, brand damage.
   - Mitigations: configurable YAML policies, real‑time output scanning, automated blocking or redaction, human review/workflow for edge cases.

6. Availability, Abuse & Denial
   - Examples: rate-limit bypass, botnets triggering expensive operations, abuse of high-cost tools.
   - Impact: degraded service, high cost, denial of service for legitimate users.
   - Mitigations: per-user and per-session rate limiting, circuit breakers, cost-aware scheduler, quota enforcement.

7. Cross‑Project / Upstream Failure Propagation
   - Examples: failures in Nexus/Oracle/Legion entry points that cause unsafe fallbacks or inconsistent enforcement.
   - Impact: inconsistent policy application, silent failures, escalation across components.
   - Mitigations: integration tests, end‑to‑end CI gates, graceful degradation with explicit logs and alerts.

8. Adversarial Inputs & Evasion
   - Examples: inputs crafted to evade regex/pattern detectors (homoglyphs, steganography, whitespace obfuscation).
   - Impact: bypassing safety checks and exfiltrating data.
   - Mitigations: normalization pipelines, canonicalization, ML classifiers for jailbreak detection, layered detection (rule + ML), red‑team testing.

9. Model & Supply‑Chain Risks
   - Examples: poisoned training data, compromised model weights, third‑party tool compromise.
   - Impact: persistent bias, backdoors, large‑scale incorrect behavior.
   - Mitigations: provenance tracking, signed models, reproducible builds, lineage verification, dependency vetting.

10. Telemetry, Auditability & Forensics Gaps
    - Examples: insufficient logging for incidents, missing context for policy violations, lack of immutable audit trails.
    - Impact: inability to investigate, remediate, or produce compliance evidence.
    - Mitigations: comprehensive structured audit logs, policy event capture, retention policies, secure storage (WORM), admin review UIs.

11. Trust UI / User Interaction Risks
    - Examples: misleading trust scores, over‑reliance on UI indicators, lack of user controls to request evidence.
    - Impact: false sense of security, poor user decisions.
    - Mitigations: transparent sources panel, explicit confidence and provenance display, user feedback loops (thumbs up/down), ability to request human review.

12. Performance & Latency Constraints
    - Examples: policy evaluation or citation verification adding excessive latency to responses.
    - Impact: poor UX, timeouts, or disabled safety checks to meet latency SLAs.
    - Mitigations: lightweight local checks, async verification for non‑blocking ops, P95 latency targets for policy eval (<120ms), performance tests in CI.

13. CI/CD & Governance Risks
    - Examples: missing test gates, unchecked merges that disable safety, flaky tests hiding regressions.
    - Impact: regressions in safety behavior reaching production.
    - Mitigations: required CI checks (acceptance + integration), linting/typechecks, clear PR review checklist, delivery README evidence requirement.

Appendix: Suggested Mitigation Stack (baseline roadmap)
- Input Layer: normalization + rule‑based scanner + canary injection.
- Agent/Tool Layer: capability model, tool whitelist, sandboxing, per‑call quotas.
- Output Layer: policy engine (PII, content policies), redaction, block/abstain, audit logging.
- Post‑Processing: citation verification, fact‑checking agents, source scoring.
- Observability: metrics, structured logs, alerts, periodic red‑team reports.

Next steps
- Adopt this taxonomy into design docs and test plans. Use it to derive acceptance and integration tests for each week, and to populate the `CAPSTONE/project_charters/P12_DELIVERY_README.md` Test Evidence section.

