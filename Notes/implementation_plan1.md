# [Goal Description]
Automate the creation and maintenance of [.gitignore](file:///Users/rohanshravan/TSAI/Arcturus/.gitignore) during Arcturus repository initialization. This ensures that internal files (`.arcturus/`), build artifacts, and standard language-specific files are not tracked by Git, keeping user repositories clean.

## User Review Required
No major user review required, but users should be aware that [.gitignore](file:///Users/rohanshravan/TSAI/Arcturus/.gitignore) will be modified if they initialize a project via Arcturus.

## Proposed Changes
### Backend
#### [MODIFY] [git.py](file:///Users/rohanshravan/TSAI/Arcturus/routers/git.py)
- Update [init_arcturus_branch](file:///Users/rohanshravan/TSAI/Arcturus/routers/git.py#247-297) to calls a new internal helper function `ensure_gitignore`.
- This function will:
    - Check if [.gitignore](file:///Users/rohanshravan/TSAI/Arcturus/.gitignore) exists.
    - If not, create it with a standard template (Python + Node.js + Arcturus).
    - If it exists, append `.arcturus/`, `__pycache__/`, `node_modules/`, and [.DS_Store](file:///Users/rohanshravan/TSAI/Arcturus/.DS_Store) if they are missing.
    - Ensure `.arcturus` and `.arcturus/` are covered.

## Verification Plan
### Automated Tests
- Create a temporary directory.
- Initialize it via the `POST /git/arcturus/init` endpoint.
- Verify [.gitignore](file:///Users/rohanshravan/TSAI/Arcturus/.gitignore) exists and contains `.arcturus/`.
- Create a directory with an existing [.gitignore](file:///Users/rohanshravan/TSAI/Arcturus/.gitignore), initialize, and verify new rules are appended.

### Manual Verification
- Open a new folder in Arcturus (e.g., `Downloads/NewTestProject`).
- Wait for auto-init.
- Check [.gitignore](file:///Users/rohanshravan/TSAI/Arcturus/.gitignore) content.
- Check Git status to ensure `.arcturus` files are ignored.
