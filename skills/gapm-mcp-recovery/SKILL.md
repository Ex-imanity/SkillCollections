---
name: gapm-mcp-recovery
version: 1.0.0
description: Use when GAPM MCP tools are missing from Codex, gapm_agent_tools is unavailable, OAuth reports invalid_client or authentication_required, App Server shows serverInfo null or empty tools, or a GAPM log investigation appears to require restarting Codex or opening a new conversation.
---

# Recovering GAPM MCP

## Overview

Separate MCP service health from the current conversation's Tool snapshot. A healthy App Server can call GAPM through the bundled bridge even when native `gapm_*` tools are absent, so restarting Codex is a last resort.

## Quick Workflow

Run from the current project:

```bash
python3 "$HOME/.codex/skills/gapm-mcp-recovery/scripts/gapm_mcp.py" status
```

Interpret `state`:

| State | Action |
| --- | --- |
| `HEALTHY` | Use native Tool if present; otherwise use bridge `call`. Do not restart. |
| `AUTH_REQUIRED` | Run `login`, complete browser authorization, then rerun `status`. |
| `CONFIG_MISSING` | Add the server using the returned `recommended_command`, then rerun `status`. |
| `CONFIG_INVALID` | Review and run the returned remove/add commands, then rerun `status`. |
| `TOOLS_MISSING` / `STARTUP_FAILED` | Report the returned error. Retry once before asking the MCP owner to investigate. |

OAuth recovery:

```bash
python3 "$HOME/.codex/skills/gapm-mcp-recovery/scripts/gapm_mcp.py" login
```

Tell the user when browser authorization is required. Do not `logout` first; only clear credentials if direct login repeatedly fails.

Verify connectivity without business identifiers:

```bash
python3 "$HOME/.codex/skills/gapm-mcp-recovery/scripts/gapm_mcp.py" smoke
```

## Call Without Restarting

Put Tool arguments in a Git-ignored `.local` JSON file, then call through an ephemeral read-only App Server thread:

```bash
python3 "$HOME/.codex/skills/gapm-mcp-recovery/scripts/gapm_mcp.py" call \
  --tool gapm_log_query_v2 \
  --arguments-file .local/gapm/query.json \
  --output .local/gapm/result.json
```

The bridge supports only the three known GAPM read tools. It never calls `mainSearch`, modifies production data, or prints raw GAPM results to the conversation.

## Restart Boundary

Restart only when native Tool injection itself is required and the bridge cannot satisfy the task. Before restarting, update the project's MRS. After restart, reopen the same task first; create a new task only if the old task still has a stale Tool snapshot.

## Evidence Rules

- `enabled` or `OAuth` from `codex mcp list/get` is configuration evidence, not health evidence.
- `serverInfo` plus all three enumerated tools proves App Server health.
- A successful empty smoke result proves connectivity.
- No matching logs does not prove an Agent or downstream call did not occur; record `TELEMETRY_MISSING` or `INSUFFICIENT_DATA`.
- Keep arguments, raw logs, trace IDs, question IDs, uid and sid under `.local/`.

## Report

Respond in Chinese with: detected `state`, evidence checked, action taken, whether restart was avoided, and any remaining user action. Never paste raw logs or credentials.
