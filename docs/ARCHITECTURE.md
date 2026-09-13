# Architecture

## Core state machine

For each named monitor:

```text
successful fetch
    ↓
normalize
    ↓
SHA-256
    ↓
no baseline? ── yes ──> store baseline, no alert
    │
    no
    ↓
same hash? ─── yes ───> update checked timestamp
    │
    no
    ↓
watch terms configured?
    │             │
    no            yes
    │             ↓
    │      any term present?
    │          │       │
    │         yes      no
    │          │       │
    └──────────┘       └──> update baseline, no notification
          ↓
create durable notification
          ↓
update baseline
```

The first observation is intentionally quiet. A monitor should learn its baseline before it can report a change.

## Durable inbox

Notifications use an autoincrementing sequence number.

A separate metadata record stores:

- `reviewed_through_seq`
- `last_reviewed_at`

`list_notifications(status="new")` returns notifications whose sequence is greater than the durable cursor. It does **not** advance the cursor.

Only `mark_notifications_reviewed(through_seq=N)` advances it. This prevents a failed consumer from losing notifications merely because it tried to read them.

## Storage

SQLite is used because it is:

- durable;
- inspectable;
- transactional;
- dependency-free in Python;
- appropriate for a small single-host monitor.

The database stores hashes and bounded excerpts, not full copies of every monitored page.

## Direct adapter

The direct adapter:

1. validates the URL;
2. resolves the hostname and rejects non-public addresses;
3. performs an HTTPS request without automatic redirects;
4. validates each redirect target before following it;
5. caps redirect count and response bytes;
6. extracts text from HTML.

For adversarial URLs, infrastructure-level egress controls are still required.

## Browser adapter

The browser adapter starts a new Playwright MCP subprocess for every fetch. v0.1.0 pins the MCP package and explicitly requests Chromium with sandboxing and isolated profile state:

```text
npx -y @playwright/mcp@0.0.80
  --headless
  --sandbox
  --isolated
  --browser chromium
  --image-responses omit
  --codegen none
```

By default, Playwright MCP resolves Chromium using its normal Playwright installation. The matching browser can be installed with:

```bash
npx -y playwright@1.63.0-alpha-2026-08-31 install chromium
```

Some server deployments manage Chromium independently. Setting `DWM_BROWSER_EXECUTABLE_PATH` adds:

```text
--executable-path <configured path>
```

This keeps host-specific executable paths out of the package while allowing deployments to use a trusted system Chromium.

The browser adapter calls:

1. `browser_navigate`
2. `browser_snapshot`
3. `browser_close`

Before hashing, generated Playwright locator tokens such as `[ref=e17]` are removed from the textual accessibility snapshot. Those references are useful for interaction but are not page content and can otherwise create false change alerts when their generated values move between runs.

Exiting the MCP client context tears down the subprocess. No shared browser profile is reused between monitor runs.

The browser and MCP dependencies are intentionally pinned rather than fetched as `latest`. Upgrade them deliberately, install the matching browser build when applicable, rerun unit and browser integration tests, then change the pins in a reviewed release.

This costs more than direct HTTP, so use it only when rendering is necessary.

## Scheduling

Scheduling is deliberately external. The monitor can be called by cron, a systemd timer, CI, a container scheduler, or an agent runtime.

That separation keeps the package focused on the durable monitoring semantics rather than forcing a particular job scheduler on users.

## Delivery

The durable inbox is the canonical delivery boundary in this reference implementation. A host can poll `list_notifications`, present or forward the result, then acknowledge the successfully handled high-water sequence.

Email, Slack, webhook or other outbound delivery can be layered on top without changing the baseline/inbox model.

## Failure behavior

A failed fetch:

- does not replace the existing baseline;
- does not create a false "content changed" notification;
- returns an explicit error to the caller.

A later successful fetch compares against the last successful baseline.
