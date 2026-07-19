---
name: internal-api-cookie-auth
description: Handle Cookie authentication for supported internal API calls without asking users to manually paste session Cookies. Use this skill whenever a script, service, or API debugging task targets Internal AD/UOS, Athena, or Compass and lacks a Cookie, reports a session expiry, returns HTTP 401, or may have failed because of authentication. Use it proactively before hardcoding a Cookie or asking the user to export one. Treat HTTP 403 as a possible authorization failure, not automatic evidence that a Cookie refresh will solve it.
---

# Internal API Cookie Authentication

## Purpose

Obtain a short-lived Cookie from the local `baijia-cookie` CAS tool only when it
is needed, then pass it to the target script through a protected file or process
environment. This avoids copying session Cookies into commands, source files, or
chat output while preserving the user's existing authentication choices.

## Scope

Use the bundled tool only for these HTTPS hosts:

- `internal-ad.gaotu100.com` and `test-internal-ad.gaotu100.com`
- `athena.baijia.com` and `test-athena.baijia.com`
- `dis.baijia.com` and `test-dis.baijia.com`

The default dependency path is `/Users/gaotu/Projects/baijia-cookie`. Override
it with `BAIJIA_COOKIE_TOOL_DIR` or `--cookie-tool-dir` when the local checkout
is elsewhere. Do not send the user's credentials to unrelated URLs.

## Authentication Decision

1. Reuse an explicit Cookie, configured Cookie file, or the target program's
   documented Cookie environment variable first.
2. When no Cookie exists, or a safe read request returns `401`, fetch a fresh
   Cookie using `scripts/fetch_cookie.py`.
3. A `403` can mean the account lacks a role or permission. Fetch once only if
   there was no valid Cookie; if a fresh Cookie still receives `403`, stop and
   report an authorization problem instead of looping.
4. Retry automatically only for idempotent reads (`GET`, `HEAD`) after a fresh
   Cookie. Do not silently retry side-effecting calls such as publish, offline,
   create, update, or delete; confirm the operation is idempotent or ask before
   repeating it.

## Fetch a Cookie

Run the bundled script from the installed Skill directory. It accepts a username
via `--username` or `SITE_USERNAME`; it reads `SITE_PASSWORD` when supplied and
otherwise prompts in an interactive terminal. It never accepts a password as a
command-line argument.

```bash
COOKIE_FILE="$(mktemp)"
python <skill-root>/scripts/fetch_cookie.py \
  --url https://internal-ad.gaotu100.com/welcome \
  --output "$COOKIE_FILE" \
  --username your-account
```

The output file has mode `0600` and contains only the Cookie header value. Pass
it to programs that support `--cookie-file`, then remove it as soon as the
operation is complete:

```bash
python scripts/batch_qapair_status.py offline --ids-file qapair_ids.txt \
  --cookie-file "$COOKIE_FILE" --execute
rm -f "$COOKIE_FILE"
```

For new Python scripts, prefer a local helper that follows the same precedence:
explicit Cookie, Cookie file, documented environment variable, then this CAS
fetch flow. Keep the Cookie in memory or a protected file; do not print it.

## Credential and Logging Rules

- Do not add a `--password` option. Prompt with `getpass` or read a named
  environment variable.
- Do not put usernames, passwords, Cookie values, or request headers containing
  Cookies in source control, terminal output, errors, tests, or chat messages.
- Pass a password only through the child process environment. Do not add it to a
  command list, command string, URL, or log.
- Mask authentication headers in debug logs. Report only host, status code, and
  a short non-sensitive error summary.
- Do not persist Cookies beyond the requested operation unless the user has
  explicitly asked for a protected local cache and its expiry behavior is known.

## Failure Handling

- Missing Node.js or cookie-tool checkout: report the missing dependency and
  the expected path. Do not invent a browser, SSO, or password-based fallback.
- Login failure: surface the tool's sanitized error; do not expose credentials.
- Unsupported host: stop. Extend the host allowlist only after confirming the
  site uses the approved CAS flow.
- Fresh Cookie with `403`: report that authentication succeeded but the account
  may lack authorization; do not repeatedly refresh the session.

## Completion Report

State whether an existing Cookie was reused or a fresh Cookie was fetched, the
target host, and whether the API call was attempted. Never include the Cookie or
password in the report.
