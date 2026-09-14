# GoHighLevel CLI

A command-line interface for GoHighLevel that lets you (or Claude Code) drive your CRM from the terminal — contacts, opportunities, calendars, conversations, workflows, emails, payments, forms, social media, locations, and documents.

> Originally built by [Lead Gen Jay](https://leadgenjay.com). This is an adapted
> and generalized fork maintained by [JC](https://github.com/gojc31) — client
> data, campaign-specific builders and hard-coded account IDs removed so it
> works against any GoHighLevel sub-account.

---

## What you get

- **11 command groups** covering the full GHL surface (contacts, opportunities, calendars, workflows, conversations, emails, payments, forms, social, locations, documents).
- **A REPL** — type `ghl` with no args and you get an interactive shell with autocomplete.
- **A Chrome extension** that grabs a Firebase refresh token, one of the token types the "internal" GHL API can use (the public API can't create workflows; the internal one can) — see [Auth for the internal API](#auth-for-the-internal-api) for which token type currently works.
- **A Claude Code skill** at `cli_anything/gohighlevel/skills/SKILL.md` so Claude can use the CLI on your behalf.

---

## Install (60 seconds)

Requirements: **Python 3.10+** and a GoHighLevel sub-account.

```bash
git clone <this repo> gohighlevel-cli
cd gohighlevel-cli
./install.sh
```

The installer creates a `.venv/`, installs the package, and copies `.env.example` → `.env`.

The CLI itself reads `.env` — the wrappers (`ghl`, `ghl.cmd`) just launch Python, and
`cli_anything/_env.py` loads `.env` from the project root at startup (standard library only,
no `python-dotenv`). Variables already exported in your shell win over the file; set
`GHL_ENV_FILE=/path/to/file` to read a different file.

Open `.env` and fill in. An inline `#` comment (preceded by a space or tab, as below) is stripped from the value; quote a value if it needs a literal ` #`.

```env
GHL_API_KEY=pit-xxxxxxxx-...        # GHL Settings → Private Integrations
GHL_LOCATION_ID=YOUR_LOCATION_ID    # the long ID in your GHL URL
```

Smoke test:

```bash
./ghl contacts list --limit 5
```

You should see 5 contacts (or an empty list, depending on the account). Done.

### Windows

`install.sh` and the `ghl` wrapper are bash scripts — run them from Git Bash or WSL.
For PowerShell / cmd, use the bundled `ghl.cmd` wrapper instead:

```cmd
python -m venv .venv
.venv\Scripts\pip install -e .
copy .env.example .env
ghl.cmd contacts list --limit 5
```

---

## Quickstart examples

```bash
# Contacts
./ghl contacts search "@example.com"
./ghl contacts create --first-name Ada --last-name Test --email ada@example.com
./ghl contacts add-tag <id> trial_started

# Workflows
./ghl --json workflows list
./ghl workflows enroll --contact-id <id> --workflow-id <id>

# Opportunities
./ghl opportunities list --pipeline-id <id>

# Conversations
./ghl conversations list --type SMS

# REPL (no args = interactive shell with autocomplete)
./ghl
```

`--json` works on most read commands and pipes cleanly into `jq`.

---

## Workflow building

The public GHL API is read-only for workflows. To **create or update** workflows, the CLI uses GHL's internal API, gated behind `--experimental`. That API needs a token, and the code currently prefers a different kind of token than the Chrome extension in this repo grabs — read this section before relying on it.

### Auth for the internal API

`cli_anything/gohighlevel/utils/ghl_internal_client.py` tries, in order:

1. **`GHL_BACKEND_BEARER`** (or a `_ghl_bearer.txt` file in the repo root) — a GHL-native "LeadConnector" bearer token. This is what the code sends as `Authorization: Bearer ...`, and per the code's own comment it's the token the workflow endpoints have required since ~2026-07. Capture it from your browser's devtools Network tab on `app.gohighlevel.com`: find a request to `backend.leadconnectorhq.com`, use "Copy as cURL", and pull the `Authorization: Bearer <token>` value out of it. Put it in `.env` as `GHL_BACKEND_BEARER=...`, or save the raw token to `_ghl_bearer.txt` at the repo root.
2. **`GHL_FIREBASE_REFRESH_TOKEN`** — the token the bundled Chrome extension grabs (`chrome://extensions/` → Load unpacked → `chrome-extension/` → open an `app.gohighlevel.com` tab → extension icon → Grab Refresh Token). The client exchanges it for a Firebase ID token and sends it as a `token-id` header. **As of this writing the code's own comments say the workflow API rejects this Firebase id-token** — so the Chrome extension flow is a legacy fallback that may not work for workflow creation. It may still work for other internal-API uses; the CLI's own error messages are the source of truth if it doesn't.
3. **`GHL_FIREBASE_TOKEN`** — a Firebase ID token supplied directly, same `token-id` header as above, same caveat as #2.

If you only need to *read* GHL data, none of this applies — the public API (`GHL_API_KEY`) covers everything except creating/updating workflows.

**This is genuinely ambiguous from reading the code alone**: it's clear the backend-bearer path is what currently works and the Firebase path is what the extension currently produces, but there's no code-level confirmation that the mismatch has been reconciled (e.g. no in-repo tooling to grab a backend bearer directly). Treat `GHL_BACKEND_BEARER` / `_ghl_bearer.txt` as the documented, working path and the Chrome extension as unverified for workflow endpoints until you've confirmed it works for your account.

### Build a workflow

With the token in place, the workflow-building helpers in
`cli_anything/gohighlevel/utils/workflow_builder.py` let you compose a campaign
as step dicts (`tag_step`, `wait_step`, `link_steps`, `validate_campaign`) and
deploy it through `InternalGHLClient`. Write a small script per campaign; a
builder that passes `--update <workflow_id>` re-deploys in place instead of
creating a duplicate.

---

## Project layout

```
gohighlevel-cli/
├── ghl                         # the executable wrapper (bash)
├── ghl.cmd                     # Windows wrapper
├── setup.py                    # package definition
├── install.sh                  # one-shot installer
├── .env.example                # template for your secrets
│
├── cli_anything/               # the actual Python package
│   ├── gohighlevel/            # GHL commands (the main thing)
│   │   ├── gohighlevel_cli.py  # ~1,260 lines of CLI
│   │   ├── utils/              # API clients (public + internal + workflow builder)
│   │   └── skills/SKILL.md     # Claude Code skill manifest
│   ├── nextcloud/              # bonus: Nextcloud CLI
│   └── blotato/                # bonus: Blotato CLI
│
└── chrome-extension/           # Firebase token grabber
    ├── manifest.json
    ├── popup.html
    ├── popup.js
    └── icon48.png
```

---

## Using it with Claude Code

The repo includes a Claude Code skill so Claude can call the CLI on your behalf:

1. Copy `cli_anything/gohighlevel/skills/SKILL.md` into a Claude Code skills directory (e.g. `~/.claude/skills/gohighlevel-cli/SKILL.md`).
2. Add `ghl` to your shell's PATH (or symlink the `ghl` wrapper somewhere on PATH).
3. In any Claude Code session, say "use the gohighlevel-cli skill" and Claude will be able to run `ghl ...` for you.

---

## Two layers of GHL API

The CLI talks to two APIs:

| API | What it can do | How it authenticates |
|-----|----------------|----------------------|
| **Public** (`services.leadconnectorhq.com`) | Read everything, create contacts/opportunities/etc. **Workflows are GET-only here.** | `GHL_API_KEY` (Private Integration Token) |
| **Internal** (`backend.leadconnectorhq.com`) | Everything the GHL UI can do — including **creating workflows**. Hidden behind a `--experimental` flag on commands that use it. | `GHL_BACKEND_BEARER` (or `_ghl_bearer.txt`) preferred; falls back to a Firebase JWT from `GHL_FIREBASE_REFRESH_TOKEN` / `GHL_FIREBASE_TOKEN` — see [Auth for the internal API](#auth-for-the-internal-api) |

You only need one of those extra tokens if you want to **build** workflows. Everything else works with just the API key.

---

## Security notes

- `.env` is gitignored. **Never** commit it.
- Any of `GHL_BACKEND_BEARER`, `_ghl_bearer.txt`, `GHL_FIREBASE_REFRESH_TOKEN`, or `GHL_FIREBASE_TOKEN` is sensitive (each is effectively your GHL session). Treat all of them like passwords.
- The bundled Chrome extension only reads from IndexedDB on `*.gohighlevel.com` and `*.leadconnectorhq.com` — no network calls.
- The internal API is undocumented and unversioned. GHL can change it without notice; pin nothing to it that you can't repair.

---

## Credits and license

Original tool by [Lead Gen Jay](https://leadgenjay.com). This fork is
generalized for public use; see [LICENSE](LICENSE).
