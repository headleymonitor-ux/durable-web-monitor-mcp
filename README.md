# durable-web-monitor-mcp

A small, security-conscious reference implementation for durable website-change monitoring with MCP.

It demonstrates a pattern that is useful for long-running assistants and automations:

**baseline → detect → notify → acknowledge → durable inbox**

The monitor supports two fetch modes:

- **direct HTTPS** for ordinary pages;
- **isolated Playwright MCP** for pages that need browser rendering.

Each browser fetch launches a fresh, non-persistent Playwright MCP subprocess with `--isolated`, then tears it down after the snapshot.

## Why this exists

A reliable page monitor needs more than "fetch URL and compare strings". It should:

- avoid alerting on the first observation;
- normalize content before hashing;
- persist baseline state across process restarts;
- keep notifications until they are acknowledged;
- separate "delivered" notifications from "reviewed" state;
- use a disposable browser session for dynamic pages;
- reject obviously unsafe network targets before fetching;
- make the monitoring state inspectable through MCP.

This repository is deliberately generic. It does not contain private infrastructure, credentials, account identifiers, internal hostnames, or environment-specific deployment configuration.

## Security model

This project is a reference implementation, **not a network sandbox**.

It rejects non-HTTPS URLs and hostnames that resolve to loopback, private, link-local, multicast, reserved, or unspecified IP addresses. Redirect targets are revalidated in the direct HTTP adapter.

Application-level URL checks cannot completely eliminate DNS rebinding or browser redirect risk. For untrusted URLs, run the monitor in a container/VM with restrictive egress rules and no access to metadata services or private networks. See [SECURITY.md](SECURITY.md).

The browser adapter uses Playwright MCP's `--isolated` mode so browser profile state is not persisted between checks. Playwright MCP itself is not a security boundary.

## Requirements

- Python 3.10+
- Node.js 18+ and `npx` only if you use the browser adapter
- `mcp>=2,<3`
- Chromium installed for the pinned Playwright build if you use the browser adapter

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

The package installs two commands:

- `dwm` — CLI for checks and notification handling;
- `dwm-mcp` — stdio MCP server.

For browser-backed checks, install Chromium once for the Playwright build used by Playwright MCP v0.0.80:

```bash
npx -y playwright@1.63.0-alpha-2026-08-31 install chromium
```

## Run as an MCP server

```bash
dwm-mcp
```

This starts the bundled MCP server over stdio without requiring the optional MCP SDK CLI extra.

The server exposes:

- `check_url`
- `list_notifications`
- `mark_notifications_reviewed`
- `monitor_status`

The SQLite database defaults to:

```text
~/.local/share/durable-web-monitor-mcp/state.sqlite3
```

Override it with `DWM_STATE_PATH`.

## Example MCP flow

1. Call `check_url` with a stable monitor name and URL.
2. The first successful check stores a baseline and emits no notification.
3. Later content changes create durable notifications.
4. Call `list_notifications(status="new")`.
5. After successfully presenting those notifications to the user, call `mark_notifications_reviewed(through_seq=...)`.

That last step matters: reading the inbox does not itself advance the review cursor.

## Direct HTTPS example

```json
{
  "name": "example-docs",
  "url": "https://example.com/docs",
  "adapter": "direct",
  "watch_terms": []
}
```

An empty `watch_terms` list means any normalized content change is noteworthy.

## Browser example

```json
{
  "name": "dynamic-status",
  "url": "https://example.com/status",
  "adapter": "browser",
  "target": "body",
  "watch_terms": ["incident", "degraded"]
}
```

v0.1.0 deliberately pins the browser integration to the version tested for this release:

```text
npx -y @playwright/mcp@0.0.80 --headless --isolated --browser chromium --image-responses=omit
```

Playwright accessibility snapshots contain generated locator references such as `[ref=e17]`. The monitor removes those ephemeral references before hashing so locator churn does not create false change alerts.

Do not silently switch the package to `@latest` in production. Upgrade the pinned Playwright MCP and matching Playwright browser build deliberately, reinstall the browser binary, and rerun the unit and browser integration tests first.

## CLI

The same engine can be driven by cron, systemd timers, CI, or another scheduler:

```bash
dwm check \
  --name example-docs \
  --url https://example.com/docs \
  --adapter direct

dwm inbox --status new
dwm ack --through-seq 12
```

A scheduler is intentionally outside this package. Keeping scheduling separate makes the monitor usable with cron, systemd timers, GitHub Actions, container schedulers, or an agent platform without coupling the durable monitoring model to one runtime.

## Normalization

Direct HTML fetches are reduced to visible text with scripts/styles/comments removed, HTML entities decoded, and whitespace collapsed.

Browser snapshots are normalized as text by removing generated Playwright locator references, trimming line endings, collapsing horizontal whitespace, and removing repeated blank lines.

The normalized text is SHA-256 hashed. The database stores hashes and bounded excerpts rather than complete page bodies.

## Testing

Core tests use only the Python standard library:

```bash
python -m unittest discover -s tests -v
```

The Playwright MCP browser adapter is intentionally an integration boundary and is not launched by the unit tests.

Before publishing a release, also test installation in a fresh virtual environment, start the installed `dwm-mcp` entry point, and run real direct-HTTPS and isolated-browser checks against non-sensitive public pages.

## Design notes

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the state machine, notification cursor model, browser-isolation rationale, and known limits.

## License

Apache-2.0. See [LICENSE](LICENSE).
