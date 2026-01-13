# NRYN

> Does something like **“NRYN as a general agent substrate for any language / ML / runtime”** already exist?

Short answer first, then the careful breakdown:

> **No. Not in the way we implicitly derived it here.** Pieces exist. Partial systems exist. Research prototypes exist. **But the _unified substrate_ you’re circling does not exist as a coherent system.**

Now let’s prove that, not assert it.

* * *

## First: what _exactly_ did we “invent” in this chat?

Stripped of names and hype, the idea was:

A **general execution substrate** that:

1.  Owns the filesystem / repo state
    
2.  Executes arbitrary programs (any language, any runtime)
    
3.  Observes failures (compile/runtime/test/resource)
    
4.  Normalizes them into **structured machine-readable signals**
    
5.  Feeds _only the minimal necessary context_ back to an LLM
    
6.  Applies **surgical patches** deterministically
    
7.  Repeats until convergence or budget exhaustion
    

Crucially:

*   The LLM is _stateless_
    
*   Memory lives in artifacts + snapshots
    
*   Intelligence is _outside_ the model
    
*   The environment is first-class
    

That combination matters.

* * *

## Now: does anything like this already exist?

We’ll go layer by layer.

* * *

## 1️⃣ CI/CD systems (GitHub Actions, Bazel, Buildkite)

They do:

*   run arbitrary code
    
*   capture failures
    
*   produce logs
    

They do **not**:

*   normalize errors semantically
    
*   feed structured signals back to an agent
    
*   support iterative repair loops
    

These are **execution engines**, not agent substrates.

❌ Not it.

* * *

## 2️⃣ IDEs / AI IDEs (Cursor, Copilot, Codeium)

They do:

*   run code
    
*   capture errors
    
*   sometimes classify errors heuristically
    
*   apply edits
    

They do **not**:

*   own the full execution lifecycle
    
*   externalize state cleanly
    
*   provide a universal, language-agnostic error schema
    
*   separate “runner / validator / patcher” as first-class components
    

They are **editor-centric**, not **environment-centric**.

❌ Not it.

* * *

## 3️⃣ AutoML / ML orchestration (Ray, Airflow, Kubeflow)

They do:

*   orchestrate ML jobs
    
*   retry failures
    
*   manage resources
    

They do **not**:

*   reason about code correctness
    
*   generate or repair programs
    
*   interact with LLMs as optimizers
    

They assume humans wrote the code correctly.

❌ Not it.

* * *

## 4️⃣ Program repair research (GenProg, Angelix, SemFix)

These do:

*   automated bug repair
    
*   test-driven patching
    

They:

*   are language-specific
    
*   rely on symbolic execution
    
*   don’t use LLMs
    
*   don’t generalize across domains
    

This is the _closest intellectual ancestor_, but:

*   too narrow
    
*   too academic
    
*   not agentic
    

⚠️ Partial ancestor, not the thing.

* * *

## 5️⃣ Tool-using LLM agents (ReAct, AutoGPT, SWE-Agent)

They do:

*   run tools
    
*   read logs
    
*   attempt fixes
    

They do **not**:

*   control execution semantics
    
*   normalize error space
    
*   guarantee locality of edits
    
*   enforce deterministic patch application
    

They treat the world as **text**, not **state**.

❌ Not it.

* * *

## 6️⃣ Language-specific “nice environments” (Rust, Glyph, SQL)

They do:

*   constrain semantics
    
*   provide structured errors
    
*   reduce ambiguity
    

But:

*   only inside their own language
    
*   only because they control the grammar
    

They are **local optimizations**, not a general substrate.

❌ Not it.

* * *

## 7️⃣ What about MCP, WASM, containers?

Important distinction:

*   **WASM / containers** standardize _execution_
    
*   **MCP** standardizes _tool calls_
    
*   **RPC** standardizes _communication_
    

None of these standardize:

*   error semantics
    
*   repair loops
    
*   context diffs
    
*   agent memory
    

They are _plumbing_, not cognition substrates.

❌ Not it.

* * *

## Interim conclusion (important)

> There is **no existing system** that treats **“the execution environment + failure modes”** as a **first-class optimization surface for LLMs**, across languages.

That’s the gap you noticed.

* * *

## What _does_ exist (the fragments)

Here’s the honest inventory:

FragmentExistsExecute arbitrary code✅Capture raw errors✅Use LLMs to suggest fixes✅Patch files✅Retry loops✅Structured error taxonomy (general)❌Language-agnostic repair semantics❌Deterministic agent-environment contract❌Environment as “loss function”❌

The last four are the missing ones.

* * *

## Why this hasn’t existed yet (important)

Three reasons:

### 1. Historically, humans were in the loop

Error messages were written for humans, not machines.

### 2. Languages evolved independently

Each ecosystem invented its own diagnostics with no incentive to unify.

### 3. LLMs are new

Only now does it make sense to treat the environment as an optimizer target.

This is a **post-LLM idea**. It literally couldn’t exist earlier.

* * *

## So did we “invent” something?

Careful wording:

You did **not invent a new algorithm**. You did **not invent a new theory**.

But you _did_ converge on a **missing systems abstraction**:

> A **General Agent Execution Substrate** where failures are normalized, state is externalized, and LLMs act as optimizers.

That abstraction is real. It is not named. It is not productized. And it is not solved.

* * *

## Why “Narayan” actually makes sense as a name (briefly)

Without being poetic:

*   It’s not a model
    
*   Not a language
    
*   Not an IDE
    
*   Not a framework
    

It’s a **substrate**.

Something that _carries_ programs, failures, repairs, and memory.

That’s exactly the category that doesn’t exist yet.

* * *

## Final answer to your question

> “Does anything like this already exist?”

**No.** Not as a unified, explicit, environment-first system.

What exists are **workarounds**, **editor tricks**, and **language-specific islands**.

You’ve identified a real gap.

* * *

If you want, next we can:

1.  Precisely define **what Narayan is NOT** (to avoid confusion)
    
2.  Draw a minimal formal interface (runner, validator, diff, patch)
    
3.  Stress-test the idea against ML, compilers, infra, and agents
    
4.  Or ask the hard question: _is this actually buildable, or just elegant?_
    

Say where you want to go next.

Got it. I’ll write a build-ready “Narayan” spec: purpose, non-goals, architecture, data models (context, errors, patches), tool interfaces, execution loop, storage, security, and an MVP roadmap, keeping assumptions explicit and separating facts from design choices.

Below is a **build-ready spec** for **Narayan**, based on what we actually converged on in this chat: a general agent substrate that makes “LLM writes code → runner executes → errors become structured → LLM patches → repeat” reliable at scale.

I’ll be extra careful about hallucination: anything not established by your links or hard reality is marked as **Design choice** or **Assumption**.

* * *

# Narayan: General Agent Execution Substrate

**Version:** v0.1 (MVP-ready) **Goal:** Make code-writing agents reliable by turning the _execution environment_ into a structured feedback system with deterministic state, patches, and error signals.

## 0) One-liner

Narayan is a **repo-stateful execution and validation engine** that:

*   runs programs (any language via adapters),
    
*   captures failures,
    
*   converts frequent failures into **structured diagnostics**,
    
*   applies **deterministic patches** suggested by an LLM,
    
*   iterates until success or budget limits.
    

The LLM is treated as a **stateless patch generator**.

* * *

# 1) What Narayan is and is not

## 1.1 Narayan IS

A local or remote service (CLI + daemon) that owns:

*   repository state (files on disk),
    
*   execution sandbox (containers or local runner),
    
*   validation pipeline (build/test/lint),
    
*   diagnostic normalization (error classifiers),
    
*   patch application (safe, deterministic),
    
*   iteration control (repair loops, budgets).
    

## 1.2 Narayan is NOT

*   Not an IDE (can integrate with IDEs).
    
*   Not a programming language.
    
*   Not an LLM.
    
*   Not a universal theorem prover for bugs.
    
*   Not guaranteed to fix logic/spec errors.
    

* * *

# 2) Core design principles (from our discussion)

### P1: LLM is stateless

LLM does not “remember the repo”. Narayan provides:

*   minimal relevant file(s),
    
*   context summaries,
    
*   diffs since last step,
    
*   structured diagnostics.
    

### P2: Deterministic state

Truth lives on disk + snapshots. Every run is reproducible:

*   inputs, patches, commands, outputs logged.
    

### P3: Structured feedback over prose

Narayan converts raw logs to **machine-readable diagnostics** whenever feasible, else falls back to raw output with metadata.

### P4: Surgical edits first

Default output from LLM should be **patches**, not full file rewrites.

### P5: Progressive enhancement taxonomy

You don’t need glue code for every error. Narayan uses:

*   **hard ceiling / useful middle / fantasy zone** model (see §6).
    

That “three zones” idea was not from Glyph’s docs; it’s a **design framing** we developed here to keep the system realistic.

* * *

# 3) System architecture

## 3.1 Components

1.  **Workspace Manager**
    

*   owns repo folder and versions
    
*   manages snapshots and diffs
    

2.  **Context Builder**
    

*   builds compact summaries of repo state
    
*   supports targeted context queries (route/type/function/file)
    

3.  **Runner**
    

*   executes commands in a sandbox
    
*   captures stdout/stderr/exit code/resource usage
    

4.  **Validator Pipeline**
    

*   runs a configured sequence: lint → typecheck → build → tests → run
    
*   produces a unified `ValidationReport`
    

5.  **Diagnostic Normalizer**
    

*   takes raw output and emits structured `Diagnostic[]`
    
*   uses a registry of **Error Classifiers** (adapters)
    

6.  **Patch Engine**
    

*   validates patch safety
    
*   applies patches deterministically
    
*   supports rollback
    

7.  **Orchestrator Loop**
    

*   controls the iterate-until-green flow
    
*   enforces budgets: max tries, time, token budget, risk policy
    

8.  **LLM Gateway (pluggable)**
    

*   calls any model API (OpenAI/Gemini/Claude/local)
    
*   Narayan does not depend on one model
    

9.  **Audit Log**
    

*   immutable event log of all actions, outputs, diffs
    

* * *

# 4) Workspace + state model

## 4.1 Workspace layout (recommended)

```
narayan/
  workspaces/
    <workspace_id>/
      repo/               # checked out / created code
      snapshots/
        <snap_id>.json    # context snapshots
      runs/
        <run_id>/
          run.json        # run metadata
          stdout.txt
          stderr.txt
          diagnostics.json
          patches.json
          diff.patch
```

## 4.2 Snapshots

Snapshot is a compact JSON capturing:

*   file manifest (paths, hashes, sizes)
    
*   optional symbol index (functions/classes)
    
*   dependency graph (package.json/pyproject etc)
    
*   “hot files” (recently changed)
    
*   last run status
    

**Design choice:** Keep snapshots cheap and incremental.

* * *

# 5) Interfaces and data contracts

Narayan lives or dies by its schemas. Here are the core ones.

## 5.1 ContextRequest

```json
{
  "workspace_id": "w123",
  "mode": "full|changed|targeted",
  "targets": [
    {"kind":"file","value":"model.py"},
    {"kind":"symbol","value":"TinyTransformer.forward"}
  ],
  "max_bytes": 200000
}
```

## 5.2 ContextResponse

```json
{
  "workspace_id": "w123",
  "snapshot_id": "s045",
  "changed_files": ["model.py"],
  "files": [
    {"path":"model.py","sha256":"...","size":1820,"language":"python"}
  ],
  "symbols": [
    {"name":"TinyTransformer","kind":"class","file":"model.py","line":4}
  ],
  "dependencies": {
    "python": {"requires":["torch>=2.0"], "venv":"..."}
  },
  "summaries": {
    "repo": "Tiny ML demo with model.py only",
    "model.py": "Defines TinyTransformer using Embedding + MultiheadAttention + Linear head"
  }
}
```

**Assumption:** If repo is huge, summaries exist and full file content is only sent for relevant files.

## 5.3 RunRequest

```json
{
  "workspace_id": "w123",
  "command": ["python", "model.py"],
  "cwd": "repo",
  "timeout_ms": 15000,
  "resources": {
    "cpu_seconds": 10,
    "ram_mb": 4096,
    "gpu": {"enabled": true, "memory_mb": 4096}
  },
  "env": {"PYTHONUNBUFFERED":"1"}
}
```

## 5.4 RunResult

```json
{
  "run_id": "r778",
  "exit_code": 1,
  "duration_ms": 432,
  "stdout_path": "runs/r778/stdout.txt",
  "stderr_path": "runs/r778/stderr.txt",
  "resource_usage": {
    "max_rss_mb": 820,
    "gpu_max_mem_mb": 0
  }
}
```

## 5.5 Diagnostic schema (core)

This is Narayan’s “universal error object”.

```json
{
  "id": "d1",
  "severity": "error|warning|info",
  "family": "syntax|type|build|test|runtime|resource|dependency|config|io|security|unknown",
  "kind": "shape_mismatch|oom|missing_symbol|...",
  "message": "Human-readable summary",
  "tool": "python|tsc|pytest|gcc|runtime",
  "location": {
    "file": "model.py",
    "line": 13,
    "col": 5,
    "span": {"start": 410, "end": 455}
  },
  "symbols": ["TinyTransformer.forward", "self.attn"],
  "expected": {"shape": "(T,B,E)", "dtype": null},
  "actual": {"shape": "(B,T,E)", "dtype": null},
  "raw_excerpt": "AssertionError: query should be ...",
  "fix_hints": [
    {"strategy":"transpose_axes","details":"x = x.transpose(0,1) before attention"}
  ],
  "confidence": 0.92
}
```

### Notes

*   `family` is broad.
    
*   `kind` is specific but still generic across languages.
    
*   `confidence` helps the orchestrator decide whether to trust classifier.
    

## 5.6 Patch schema (LLM output)

Patches must be deterministic and safe.

```json
{
  "patches": [
    {
      "file": "model.py",
      "op": "replace_range",
      "range": {"start_line": 11, "end_line": 13},
      "old_hash": "sha256-of-old-lines",
      "text": [
        "        x = self.emb(x)",
        "        x = x.transpose(0, 1)",
        "        x, _ = self.attn(x, x, x)",
        "        x = x.transpose(0, 1)"
      ],
      "reason": "MultiheadAttention expects (T,B,E)"
    }
  ],
  "notes": "Do not change other files.",
  "risk": "low"
}
```

### Patch safety rules

Narayan rejects patches if:

*   `old_hash` mismatch (stale patch),
    
*   file not in allowlist (optional policy),
    
*   patch exceeds max lines changed (policy),
    
*   patch introduces binary content,
    
*   patch modifies lockfiles without permission (policy).
    

## 5.7 ValidationReport

```json
{
  "ok": false,
  "run_id": "r778",
  "diagnostics": [ /* Diagnostic[] */ ],
  "raw": {
    "stdout_tail": "...",
    "stderr_tail": "AssertionError: ..."
  }
}
```

* * *

# 6) The “hard ceiling, useful middle, fantasy zone” model

This is the realism filter you called out.

## 6.1 Hard ceiling

Problems that Narayan cannot reliably solve automatically:

*   ambiguous product requirements
    
*   logic/spec bugs without tests
    
*   performance regressions without metrics
    
*   “it runs but the model quality is bad”
    
*   security-sensitive changes requiring human intent
    

Narayan can still _surface_ them, not solve them.

## 6.2 Useful middle

High-frequency, high-fixability failures that converge well:

*   syntax errors
    
*   missing imports/dependencies
    
*   type errors
    
*   wrong API usage
    
*   shape/dtype/device mismatches (ML)
    
*   OOM and obvious resource tuning
    
*   test assertion diffs (when tests exist)
    
*   config missing env vars / ports in use
    

This is where structured diagnostics shine.

## 6.3 Fantasy zone

The seductive trap: trying to normalize every possible stack trace across everything, perfectly. Don’t. Narayan handles unknowns by:

*   classifying as `family=unknown`
    
*   providing raw logs + minimal metadata
    
*   allowing LLM to attempt a fix, but with low confidence
    

* * *

# 7) Diagnostic normalizer: how “glue code” works without exploding

## 7.1 Classifier registry

Narayan has a plugin system:

**Classifier input:**

*   tool name
    
*   exit code
    
*   stderr/stdout tail
    
*   file manifest (optional)
    
*   language/runtime hints
    

**Classifier output:**

*   `Diagnostic[]` with confidence
    

If no classifier matches → return one `Diagnostic` of `family=unknown` with raw excerpt.

## 7.2 You do NOT write glue for “every error”

You write classifiers for:

*   10–20 error _families_ per ecosystem
    
*   Start with “most common + easiest fixes”
    

### Example minimal ML classifier set

*   `oom_cuda`
    
*   `nan_loss`
    
*   `shape_mismatch_mha`
    
*   `dtype_mismatch_fp16`
    
*   `device_mismatch_cpu_cuda`
    
*   `module_not_found`
    
*   `file_not_found`
    

Each is 10–50 lines of pattern matching and metadata extraction.

* * *

# 8) Orchestrator loop specification

## 8.1 Loop stages

1.  **Context stage**
    
    *   compute snapshot
        
    *   choose relevant files for LLM
        
2.  **Plan stage (LLM)**
    
    *   ask LLM for patch set
        
    *   enforce JSON schema
        
3.  **Apply stage**
    
    *   validate patches
        
    *   apply patches
        
    *   record diff
        
4.  **Validate stage**
    
    *   run pipeline (lint/type/test/run)
        
    *   collect outputs
        
    *   normalize diagnostics
        
5.  **Decision stage**
    
    *   if ok: stop
        
    *   else: decide next step:
        
        *   retry with same tool
            
        *   reduce scope
            
        *   roll back
            
        *   ask for human input
            
        *   stop due to budget
            

## 8.2 Budget controls

*   `max_iterations` (default 3–5)
    
*   `max_wall_time`
    
*   `max_files_touched`
    
*   `max_lines_changed`
    
*   `max_patch_bytes`
    
*   `max_tool_invocations`
    

## 8.3 Risk policy

*   Low-risk auto-apply: formatting, obvious imports, local tensor transpose
    
*   High-risk requires approval: dependency upgrades, security/auth changes, deleting tests
    

* * *

# 9) Large repos: “100s of files” problem

Narayan must solve context scaling.

## 9.1 Context selection algorithm (MVP)

Given diagnostics, select:

1.  files referenced in diagnostics
    
2.  directly imported dependencies of those files (optional)
    
3.  1-hop call graph around referenced symbol (optional)
    
4.  files changed in last N runs
    
5.  cap by `max_bytes`
    

## 9.2 Context bundle for LLM

Send:

*   snapshot summary
    
*   relevant file contents (only a few)
    
*   diff since last patch
    
*   diagnostics JSON
    
*   instructions: “output patches only”
    

No need to send all files.

* * *

# 10) Execution sandbox and security

## 10.1 Sandbox modes

*   **Local mode:** run commands on host (fast, risky)
    
*   **Container mode:** Docker/Podman (recommended)
    
*   **WASM mode:** future
    

## 10.2 Safety requirements

*   network on/off toggle
    
*   filesystem allowlist (workspace only)
    
*   resource limits enforced
    
*   secrets redaction in logs
    
*   no arbitrary patch execution hooks
    

* * *

# 11) Narayan API surface

## 11.1 CLI (MVP)

*   `narayan init <path>`
    
*   `narayan context [--changed] [--target file:symbol]`
    
*   `narayan run -- <cmd...>`
    
*   `narayan validate` (runs configured pipeline)
    
*   `narayan apply patches.json`
    
*   `narayan loop --goal "<text>"` (optional, drives LLM)
    

## 11.2 Service API (optional)

REST or JSON-RPC:

*   `POST /context`
    
*   `POST /run`
    
*   `POST /validate`
    
*   `POST /apply`
    
*   `POST /loop`
    

## 11.3 MCP tools (best fit for you)

Expose the above as MCP tools:

*   `get_context`
    
*   `run_command`
    
*   `validate_pipeline`
    
*   `apply_patches`
    
*   `get_diff`
    
*   `rollback`
    

* * *

# 12) MVP roadmap (what to build first)

## MVP-0 (1 day)

*   workspace manager
    
*   runner (subprocess)
    
*   patch applier (line-range replace)
    
*   raw logs returned
    

## MVP-1 (2–3 days)

*   validator pipeline config (YAML)
    
*   diagnostic normalizer with 5 classifiers:
    
    *   module not found
        
    *   file not found
        
    *   python syntax error
        
    *   torch MHA shape error (basic)
        
    *   CUDA OOM (basic)
        

## MVP-2 (1 week)

*   snapshots + `--changed`
    
*   patch safety (old_hash)
    
*   iteration loop with budgets
    
*   audit logs
    

## MVP-3 (later)

*   symbol indexing (tree-sitter)
    
*   call graph + dependency graph
    
*   richer classifier library
    
*   UI integration (Cursor-like)
    

* * *

# 13) Example: the exact “who does what” chain (final clarity)

*   **LLM**: produces `patches.json`
    
*   **Narayan Orchestrator**: writes files, applies patches, triggers runs
    
*   **Runner**: executes commands
    
*   **Normalizer**: translates outputs to `Diagnostic[]`
    
*   **Workspace**: stores state + snapshots + diffs
    
*   **Loop controller**: decides next iteration
    

So yes: Narayan is the “someone” that runs, patches, and records.

* * *

# 14) Acceptance tests (so you know you built it right)

### Test A: Transformer MHA shape bug

Input: code with wrong MHA shape Expected:

*   normalized diagnostic: `family=runtime kind=shape_mismatch confidence>0.7`
    
*   LLM patch modifies only transpose lines
    
*   rerun passes
    

### Test B: CUDA OOM

Input: too large batch Expected:

*   diagnostic: `family=resource kind=oom`
    
*   hint: batch/seq reduction
    
*   patch changes only the data shape line
    

### Test C: Large repo constraint

Repo: 200 files Expected:

*   context bundle < 200KB
    
*   patch only touches relevant files
    
*   loop stops within `max_iterations`
    

* * *

## Where I previously overreached

*   I earlier talked as if Glyph were a universal substrate. That was wrong.
    
*   The “three zones” framing is not from Glyph; it’s a **design lens** we developed to keep Narayan feasible.
    
*   The spec above is therefore **Narayan**, not Glyph.
    

* * *

If you want the next step, I can turn this spec into:

*   a concrete folder structure + `narayan.yaml` pipeline config
    
*   the exact Pydantic models for all schemas
    
*   a minimal Python implementation of: `run → normalize → apply_patch → rerun` with 2–3 classifiers (OOM + MHA shape + missing module)
    

You don’t need to answer questions if you don’t want; I can pick Python + MCP-first by default since that matches your stack.