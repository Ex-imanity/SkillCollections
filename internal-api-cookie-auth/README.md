# Internal API Cookie Authentication

This Skill helps agents develop and debug scripts that call supported internal
HTTP APIs without manually exporting session Cookies. It bundles a small tool
that gets a fresh CAS Cookie through the local `baijia-cookie` checkout and
writes it to a `0600` file.

## Dependency

The default cookie-tool location is:

```text
/Users/gaotu/Projects/baijia-cookie
```

Override it when needed:

```bash
export BAIJIA_COOKIE_TOOL_DIR=/path/to/baijia-cookie
```

The checkout must have Node.js dependencies installed.

## Manual Use

Run in an interactive terminal to enter credentials without placing a password
in shell history or command arguments:

```bash
COOKIE_FILE="$(mktemp)"
python scripts/fetch_cookie.py \
  --url https://internal-ad.gaotu100.com/welcome \
  --output "$COOKIE_FILE" \
  --username your-account
```

Then use the file with a compatible script:

```bash
python /Users/gaotu/Projects/FeedbackEntrance/scripts/batch_qapair_status.py \
  offline --ids-file qapair_ids.txt --cookie-file "$COOKIE_FILE" --execute
rm -f "$COOKIE_FILE"
```

`SITE_USERNAME` and `SITE_PASSWORD` are supported for non-interactive use. Do
not commit either credential or any generated Cookie file.

## Supported Hosts

- Internal AD / UOS: production and `test-` environments
- Athena: production and `test-` environments
- Compass: production and `test-` environments

The tool deliberately rejects all other hosts.
