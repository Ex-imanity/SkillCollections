---
name: internal-api-cookie-auth
description: Handle Cookie authentication for internal HTTPS API calls without asking users to manually paste session Cookies. Use this skill whenever a script, service, or API debugging task lacks a Cookie, reports a session expiry, redirects to cas.baijia.com or test-cas.baijia.com, returns HTTP 401, returns a CAS-style JSON code 700, or may have failed because of authentication. Use it proactively before hardcoding a Cookie or asking the user to export one. Only probe an unknown host after the user has authorized a real read-only network test; treat HTTP 403 as a possible authorization failure, not automatic evidence that a Cookie refresh will solve it.
---

# Internal API Cookie Authentication

## Purpose

Obtain a short-lived Cookie from the local `baijia-cookie` CAS tool only when it
is needed, then pass it to the target script through a protected file or process
environment. This avoids copying session Cookies into commands, source files, or
chat output while preserving the user's existing authentication choices.

## Scope And Trust Boundary

These HTTPS hosts have built-in CAS service configuration:

- `internal-ad.gaotu100.com` and `test-internal-ad.gaotu100.com`
- `athena.baijia.com` and `test-athena.baijia.com`
- `dis.baijia.com` and `test-dis.baijia.com`

Other internal HTTPS hosts are supported only by one of these evidence-based
paths:

1. The user or repository configuration provides an explicit HTTPS
   `--cas-service-url`.
2. A user-authorized, read-only `--discover-cas` probe receives a redirect to
   the CAS host matching the target environment and includes one HTTPS
   `service` parameter.

The probe sends no Cookie, follows no redirect, and accepts only
`https://cas.baijia.com/cas/login` for production targets or
`https://test-cas.baijia.com/cas/login` for `test-` targets. A redirect to any
other login host is not evidence that this Skill may send credentials there.

The default dependency path is `/Users/gaotu/Projects/baijia-cookie`. Override
it with `BAIJIA_COOKIE_TOOL_DIR` or `--cookie-tool-dir` when the local checkout
is elsewhere.

## Authentication Decision

1. Reuse an explicit Cookie, configured Cookie file, or the target program's
   documented Cookie environment variable first.
2. During dry-run, mock, unit-test, or static-development work, do not issue a
   network probe just to discover authentication. Preserve the script's normal
   dry-run boundary.
3. When the user authorizes a real read-only test, attempt it without a Cookie.
   A `302/303/307/308` to trusted CAS can be discovered automatically. HTTP
   `401` and a JSON `code:700` show that authentication is needed, but do not by
   themselves reveal a CAS service URL; use a separately authorized safe probe,
   explicit `--cas-service-url`, or the browser fallback.
4. A `403` can mean the account lacks a role or permission. Fetch once only if
   there was no valid Cookie; if a fresh Cookie still receives `403`, stop and
   report an authorization problem instead of looping.
5. Retry automatically only for idempotent reads (`GET`, `HEAD`) after a fresh
   Cookie. Do not silently retry side-effecting calls such as publish, offline,
   create, update, or delete; confirm the operation is idempotent or ask before
   repeating it.

## Fetch a Cookie

Run the bundled script from the installed Skill directory only after the user
has authorized the authentication attempt. It accepts a username via `--username`
or `SITE_USERNAME`; it reads `SITE_PASSWORD` when supplied and otherwise prompts
in an interactive terminal. It never accepts a password as a command-line
argument.

```bash
COOKIE_FILE="$(mktemp)"
python <skill-root>/scripts/fetch_cookie.py \
  --url https://internal-ad.gaotu100.com/welcome \
  --output "$COOKIE_FILE" \
  --username your-account
```

For an unknown host whose safe read-only URL has been authorized, let the helper
derive the service URL from a trusted CAS redirect:

```bash
python <skill-root>/scripts/fetch_cookie.py \
  --url https://internal-service.example.com/api/status \
  --discover-cas \
  --output "$COOKIE_FILE" \
  --username your-account
```

For a write operation, do not use the write endpoint as an authentication probe.
Ask for or locate a safe read-only probe URL first. If discovery finds no trusted
CAS redirect, stop and request an explicit `--cas-service-url` rather than
guessing a login route.

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
- Unknown host without a trusted CAS redirect: stop and request an explicit
  `--cas-service-url` or browser fallback. Do not guess from a `401`, `700`,
  HTML login page, or an untrusted redirect.
- Fresh Cookie with `403`: report that authentication succeeded but the account
  may lack authorization; do not repeatedly refresh the session.

## Completion Report

State whether an existing Cookie was reused or a fresh Cookie was fetched, the
target host, and whether the API call was attempted. Never include the Cookie or
password in the report.
