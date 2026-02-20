# Testing EpisodicMemory Integration

The EpisodicMemory system automatically captures "recipes" (skeletons) of agent execution to enable long-term learning and retrieval.

## 1. Scripted Verification
The fastest way to test if the infrastructure is working is using the Phase 3 verification script.

```powershell
uv run python scripts/verify_phase3.py --test memory
```

- **What it does**: Manually triggers a `save_episode` call with mock data.
- **Success Criteria**: You should see:
  `✅ SUCCESS: Episodic skeleton saved at ...\memory\episodes\skeleton_test_verify_XXXX.json`

## 2. Integrated "Real World" Test
You can test the automatic persistence of actual IDE chats.

1. Start the backend: `npm run dev` (which starts `uvicorn`).
2. Send a chat query to the IDE Agent (via UI or `curl`).
3. Check the episodes directory:
   ```powershell
   ls memory/episodes/
   ```
4. Look for a file starting with `skeleton_ide_`.

## 3. Retrieval Test
Once you have saved episodes, the agent can "remember" them during planning.

- **Check Search**: You can verify search logic by checking the search functionality in `memory/episodic.py`.
- **Note**: The system uses individual files in `memory/episodes/` for persistence. A central `episodes.json` is **not** required as the system scans the directory for keyword matches.

## Summary of Storage
| Item | Location |
|---|---|
| Logic | `core/episodic_memory.py` |
| Low-level Ops | `memory/episodic.py` |
| Saved Episodes | `memory/episodes/skeleton_*.json` |
