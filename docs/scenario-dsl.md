# Scenario file reference

A scenario file is YAML. `python -m filmwright.demo.run_scenarios scenarios.yaml` runs each scenario in its own fresh browser context, in
order, and records one sharp video per scenario (`videos/<id>.mp4`) plus an event log
(`videos/<id>.events.json`). The `recording:` block (resolution, pace, cursor, typing speed) is in
`docs/film.md`.

```yaml
name: <feature name>                   # heading of results.md
base_url: http://localhost:3000
allow_hosts: [localhost]         # needed when the host has no dev/staging/sandbox/localhost in it
auth:
  storage_state: auth.json               # written by `python -m filmwright.demo.login`, relative to this file
  token_js: "localStorage.getItem('auth_token')"   # how `api` steps get a bearer token
  stub_routes:                           # optional: answer matching requests locally (e.g. an SSO heartbeat)
    - {url: "**/api/login/sso-check*", json: {active: true}}
viewport: {width: 1440, height: 810}     # 16:9, even numbers; also the video size
slow_mo: 300                             # ms between actions: makes videos watchable
default_timeout: 25                      # seconds per step
vars: {record_id: <id of a seeded record>}   # usable as {{record_id}} in any step
scenarios:
  - id: S01
    area: Record view
    title: <happy path, in the user's words>
    expected: <what should be on screen, quoting the UI text>
    steps: [...]
  - id: S09
    area: Roles
    title: <what a read-only member sees>
    expected: <…>
    skip: needs a read-only login on this environment, covered by <unit test file>
```

Scenario fields: `id`, `title` (required); `area`, `expected` (shown in the table); `steps`; `skip`
(reason: the row still appears); `hold` (seconds to linger at the end, default 1.2).

## Targets

Most steps take a *target*. Prefer, in this order, because they match what users see and survive
restyling:

| Key | Example | Playwright |
|---|---|---|
| `role` + `name` | `{role: button, name: "Assign"}` | `get_by_role` |
| `label` | `{label: "Skip review"}` | `get_by_label` |
| `placeholder` | `{placeholder: "Search records…"}` | `get_by_placeholder` |
| `text` | `{text: "Saved"}` or just `"Saved"` | `get_by_text` |
| `testid` | `{testid: <component-testid>}` | `get_by_test_id` |
| `css` | `{css: "tr:has-text('<Name>') input[type=checkbox]"}` | `locator` (last resort) |

Modifiers: `exact: true` (whole-string match), `nth: 2` (0-based; default is the first match), and
`within: <target>` to scope a search, e.g.
`{role: checkbox, within: {role: row, name: "<Name>"}}`.

`name` matches the accessible name: for icon buttons that's the `aria-label`.

## Steps

| Step | Shape | Notes |
|---|---|---|
| `goto` | `goto: /records/{{id}}` | relative to `base_url`; waits for network idle |
| `click` | `click: <target>` | |
| `hover` | `hover: <target>` | |
| `fill` | `fill: {placeholder: "Search records…", value: "<Name>"}` | replaces the field's value |
| `type` | `type: {placeholder: "Search teammates…", value: "<name>"}` | types key by key (comboboxes that filter) |
| `check` / `uncheck` | `check: {role: checkbox, name: "Select <Name>"}` | |
| `press` | `press: Escape` | keyboard, e.g. `Enter`, `Meta+K` |
| `select` | `select: {label: "Rows", option: "25"}` | native `<select>` only |
| `pause` | `pause: 1.5` | seconds; use before/after moments you want visible in the video |
| `wait_for` | `wait_for: {text: "Saved"}` | add `state: hidden` to wait for something to go away |
| `expect_visible` | `expect_visible: {role: dialog, name: "Assign owner"}` | assertion → evidence in results |
| `expect_hidden` | `expect_hidden: {role: dialog}` | |
| `expect_text` | `expect_text: {testid: <component-testid>, contains: "<text>"}` | substring |
| `expect_count` | `expect_count: {text: "<chip text>", exact: true, count: 2}` | |
| `expect_url` | `expect_url: {contains: "/records/{{record_id}}"}` | |
| `api` | see below | backend check with the app's own session |
| `eval` | `eval: "document.title"` + `save_as: t` | escape hatch, runs in the page |
| `screenshot` | `screenshot: after-assign` | saved as `shots/<id>-after-assign.png` |

Any step may carry `note:` (ignored by the runner; for humans reading the file).

### `api`: verify the backend, not just the screen

The UI can look right while the data is wrong; most of the trustworthy confirmations in a run come
from here. It runs `fetch()` inside the page, so it uses the app's own origin and session.

```yaml
- api:
    path: /api/<endpoint>/{{record_id}}
    method: GET                 # default GET; body: {...} for POST/PATCH
    status: 200                 # default 200
    expect:
      - {path: data.id, equals: "{{record_id}}"}
      - {path: data.items, length: 2}
      - {path: data.items.0.enabled, truthy: true}
      - {path: data.error, falsy: true}
      - {path: data.name, contains: "<Name>"}
    save: {first_item: data.items.0.id}    # later steps can use {{first_item}}
```

Write list indexes as `.0`, not `[0]`. Inside `{…}`, YAML reads `[` as the start of a list and
rejects the file. Quoting also works: `{path: "data.items[0].id", …}`.

## Writing scenarios that make good videos

- Start each scenario with `goto`: contexts are fresh, nothing carries over but `vars`.
- Add `pause: 1` after the moment that matters (a banner appearing, a toast) so viewers can read it.
- One idea per scenario; the builder turns each into one narrated section.
- Destructive scenarios (remove, replace, send) go last, and only on seeded test data.

## Sign-in

For an app behind a sign-in, run `python -m filmwright.demo.login --base-url <url> --run-dir <folder>` once. It opens a
browser window where **you** sign in (filmwright never types credentials) and saves the session to `<folder>/auth.json`
(chmod 600). That file holds a live session token: keep it out of version control (the repo's `.gitignore` already
ignores it) and never paste it anywhere. If sign-in happens in a browser window the script can't see (some SSO flows),
`demo/import_chrome_session.sh <host> <base-url> <folder> [token-key]` copies the session from your own signed-in Chrome
tab on macOS, without printing it.

## Test environments only

The runner refuses hosts that look like production. localhost, `*.localhost`, `*.test`, `*.example` and hosts containing
dev, staging, sandbox, preview or playground are allowed; anything else must be listed under `allow_hosts`. Record a
production site only read-only, with a demo account, and with the site owner's permission.
