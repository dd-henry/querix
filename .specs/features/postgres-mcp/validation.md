# postgres-mcp Validation

**Verdict**: PASS  
**Date**: 2026-10-25  
**Spec**: Inline acceptance criteria supplied with the verification request; no formal spec added.  
**Diff range**: `b85183f^..b85183f` (`b85183fdc6a2389d70ac148c378101c1caac5199`)  
**Verifier**: Independent feature verifier  

## Acceptance criteria

| Criterion | Expected outcome | Evidence | Result |
| --- | --- | --- | --- |
| 1. VS Code workspace MCP config starts PostgreSQL MCP through Docker in restricted/read-only mode and passes local, uncommitted `DATABASE_URI` from `.env.mcp`. | Stdio server uses Docker, exports `DATABASE_URI` into the container, loads `${workspaceFolder}/.env.mcp`, and selects restricted mode. | `.vscode/mcp.json:4-15` | PASS, static configuration verified. No database connection was attempted; the user must create and populate the ignored local env file. |
| 2. `.env.mcp` is gitignored and a placeholder example exists. | Git ignores `.env.mcp`; tracked example contains a placeholder URI. | `.gitignore:3`; `.env.mcp.example:1` | PASS |
| 3. Docs explain setup, startup, safe schema lookup, and credential handling. | Instructions cover local setup, starting/restarting the server, schema-only lookup, and protecting/encoding credentials. | `docs/postgres-mcp.md:7-15` | PASS |

## Discrimination sensor

| Mutation | Sensor check | Result |
| --- | --- | --- |
| In an isolated project-local copy of the committed config, replace `--access-mode=restricted` with `--access-mode=unrestricted`. | Re-run the acceptance predicate requiring restricted mode. | Killed: the acceptance check rejected the unrestricted config (1/1). |

The real worktree was not mutated for the sensor. `git status --porcelain` captured immediately before and after the sensor was identical. The scratch copy was removed.

## Gates

| Gate | Result |
| --- | --- |
| Parse committed `.vscode/mcp.json` as JSON | PASS |
| Check Docker, env-file, and restricted-mode wiring | PASS |
| `git check-ignore --no-index .env.mcp` | PASS |
| Check placeholder example and documentation expectations | PASS |
| `git diff --check b85183f^ b85183f` | PASS |
| `python3 /Users/ddhenry/Documents/dev/ask-sql/.claude/skills/tlc-spec-driven/scripts/validate_state.py postgres-mcp` | PASS |

## Caveats

- Runtime startup and database access were intentionally not tested. No local `DATABASE_URI` was supplied or read.
- The sensor proves the static acceptance check distinguishes the required access mode; it does not exercise Docker or the MCP server.
- No project test suite was run because this change only adds MCP configuration and documentation.
