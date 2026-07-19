---
name: internal-api-cookie-auth
description: Handle Cookie authentication for internal HTTPS API calls without asking users to manually paste session Cookies. Use this skill whenever a script, service, or API debugging task lacks a Cookie, reports a session expiry, redirects to cas.baijia.com or test-cas.baijia.com, returns HTTP 401, returns a CAS-style JSON code 700, or may have failed because of authentication. Also use it when the user pastes a browser "copy as cURL" command for an internal host (gaotu100.com, baijia.com) and wants it turned into a repeatable, authenticated API call: it teaches how to wrap the request in any form (one-off command, bash, or Python) with a fresh Cookie and minimal headers, rather than reusing the pasted Cookie, and to confirm before replaying side-effecting POST/PUT/PATCH/DELETE calls. Use it proactively before hardcoding a Cookie or asking the user to export one. Only probe an unknown host after the user has authorized a real read-only network test; treat HTTP 403 as a possible authorization failure, not automatic evidence that a Cookie refresh will solve it.
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
   The service URL can be discovered automatically from either a `302/303/307/308`
   redirect to trusted CAS, or a JSON body `{"code":700,"data":"<cas login url>"}`
   returned with HTTP `200`/`401`. Most gaotu internal APIs use the JSON form:
   the `data` field is the full `https://<cas-host>/cas/login?service=...` URL, and
   the `service` parameter is the value the cookie tool needs. A bare HTTP `401`
   with no body, or a `code:700` whose `data` is not a trusted-CAS login URL, does
   not reveal a service URL; fall back to a separately authorized safe probe,
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

## From a curl Command to an Authenticated Call

When the user pastes a browser "copy as cURL" command, do not hardcode its
Cookie. Recognize it as an authenticated internal request and wrap it. The output
form is up to the situation — a one-off command, a small bash function, a Python
client in the user's codebase, or the bundled `scripts/call_api.py` reference.
Whatever the form, follow these principles.

1. Recognize the auth. The CAS session cookies (`SESSION`, `JSESSIONID`,
   `cas_name`, `CAS_AC_CURRENT_ROLE`, `uid`) in the `-b`/`Cookie` value mark the
   request as CAS-authenticated. Treat the pasted Cookie as evidence only; never
   reuse it — it will expire and must not be committed.
2. Handle the Cookie, not the paste. Obtain a fresh Cookie for the target host
   with `scripts/fetch_cookie.py` (use `--discover-cas` for a non-built-in host,
   or `--cas-service-url`). Keep it in memory or a `0600` file, set it as the
   whole `Cookie` header, and never print or log it. In bash:
   `curl -H "Cookie: $(cat "$COOKIE_FILE")" ...`; in Python, read the file or
   import `fetch_cookie`.
3. Keep the wrapper minimal. Forward only what the endpoint needs — usually just
   the Cookie plus `content-type` when there is a JSON body. Drop everything else
   the browser attached: `origin`, `referer`, `priority`, `sec-ch-*`,
   `sec-fetch-*`, `accept-language`, `user-agent`, and identity headers like
   `uid` (the Cookie already carries identity). Start minimal and add a header
   back only if the call fails without it. (Measured example: `test-mi` needs
   only the Cookie + `content-type`; `b_client`, `accept`, `uid` are all
   unnecessary.)
4. Gate side effects. Replay `GET`/`HEAD` freely. For any method that can mutate
   state — `POST`, `PUT`, `PATCH`, `DELETE` — you MUST confirm with the user
   before sending, even the first time, because a pasted `POST` may create,
   update, or delete. A `POST` that is plainly a read (a `/list`, `/query`,
   `/search`, or `/detail` call) is lower risk but still confirm if unsure. Do
   not auto-retry a side-effecting call.

Reference implementation (optional): `scripts/call_api.py` embodies the above —
minimal allowlist headers (`--keep-header` to add more), a `--confirm-write`
gate that refuses to send a non-`GET`/`HEAD` method until the user confirms, and
one auth-refresh retry for reads only. It prints the response body to stdout and
the host/status/header decisions to stderr; the Cookie never appears in either.

```bash
# read (GET/HEAD or a clearly read-only POST like /list, after confirming):
python <skill-root>/scripts/call_api.py --curl-file request.curl \
  --discover-cas --username your-account
# side-effecting method, only after the user confirms it is safe to replay:
python <skill-root>/scripts/call_api.py --curl-file request.curl \
  --discover-cas --username your-account --confirm-write
```

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
- Unknown host with no trusted CAS redirect and no `code:700` `data` pointing at
  a trusted CAS login URL: stop and request an explicit `--cas-service-url` or
  browser fallback. Do not guess from a bare `401`, an HTML login page, or an
  untrusted redirect/`data` value.
- Fresh Cookie with `403`: report that authentication succeeded but the account
  may lack authorization; do not repeatedly refresh the session.

## Completion Report

State whether an existing Cookie was reused or a fresh Cookie was fetched, the
target host, and whether the API call was attempted. Never include the Cookie or
password in the report.
