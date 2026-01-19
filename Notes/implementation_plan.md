# Git-Driven Python Testing & UX - Implementation Plan

## Goal
Establish a strictly Git-Driven lifecycle for tests (Creation *and* Deletion) and enhance the testing UX to provide precise code navigation and detailed failure logs.

## User Review Required
> [!IMPORTANT]
> **Paradigm Shift**: Tests are now treated as a "Verified View" of Git Commits.
> - **Generation**: Triggered by **Added/Modified** lines in a commit.
> - **Deletion**: Triggered by **Deleted** lines in a commit (tests covering deleted code are removed).
> - **Mapping**: Tests are statically linked to Functions to enable "Click Test -> Highlight Code".

---

## Proposed Changes

### Phase 1: Git-Driven Lifecycle (Backend)

We replace the generic check with specific Diff Analysis.

#### [MODIFY] [routers/git.py](file:///Users/rohanshravan/TSAI/Arcturus/routers/git.py)
Update the auto-commit hook to analyze diffs:
1.  **Analyze Diff**: Get Added vs Removed hunks.
2.  **Deleted Code Handling**:
    *   Identify functions/classes removed in the diff.
    *   Find corresponding tests in `manifest.json`.
    *   **DELETE** those test files (or functions within test files).
3.  **New Code Handling**:
    *   Generate tests *only* for the added/modified functions.

#### [MODIFY] [routers/tests.py](file:///Users/rohanshravan/TSAI/Arcturus/routers/tests.py)
Update `generate_tests`:
*   Accept `deleted_functions` list.
*   Update Manifest to remove entries for deleted functions.

---

### Phase 2: Code Highlighting & Navigation (Backend + Frontend)

Enable "Click Test -> Highlight Function".

#### [MODIFY] [routers/tests.py](file:///Users/rohanshravan/TSAI/Arcturus/routers/tests.py)
*   **Static Analysis**: When parsing test files (in `get_tests_for_file`), extract not just the test code, but also the **Target Function Name** (e.g., `test_multiply` targets `multiply`).
*   **Return Data**: Include `target_symbol` in the `TestItem` response.

#### [MODIFY] [TestsSidebar.tsx](file:///Users/rohanshravan/TSAI/Arcturus/platform-frontend/src/features/ide/components/Sidebars/TestsSidebar.tsx)
*   **Navigation Logic**: When expanding a test:
    1.  Open the SUT file (already done).
    2.  **Scroll to Symbol**: Use `monaco.editor.revealLine` (or equivalent via `openIdeDocument` options) to jump to the `target_symbol`.

---

### Phase 3: Enhanced Failure UX

Show the full, ugly error details so the user knows *why* it failed.

#### [MODIFY] [TestsSidebar.tsx](file:///Users/rohanshravan/TSAI/Arcturus/platform-frontend/src/features/ide/components/Sidebars/TestsSidebar.tsx)
*   **Error UI**: Instead of a simple "Fix" button or tooltip:
    *   Show a scrollable `<pre>` block with `failure.message` inside the accordion.
    *   Ensure newlines are preserved.

---

## Verification Plan

### Manual Verification
1.  **Test Deletion**:
    *   Delete a function `foo()` in `vector_multiply.py`.
    *   Wait for auto-commit.
    *   Verify `test_foo()` is **automatically deleted** from `tests/test_vector_multiply.py`.
2.  **Highlighting**:
    *   Click `test_multiply_vectors`.
    *   Verify editor opens `vector_multiply.py` AND **scrolls** to `def multiply_vectors`.
3.  **Failure Logs**:
    *   Break a test (assert 1==2).
    *   Run test.
    *   Verify the UI shows `AssertionError: 1 != 2` clearly.
