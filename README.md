# xingchi-codex

Point the **Codex CLI** at the Xingchi API and pick your model and reasoning
level with `/model`. Setup accepts a required GPT公益/Sol key and an optional
Astra-专属余额 key. Select the key group explicitly at launch.

```
Codex ── HTTPS (OpenAI Responses API) ──> Xingchi
          default: GPT公益/Sol key
          --astra: Astra-专属余额 key
```

Both installers configure Codex to use Xingchi's **Responses API** with the
coding-client headers used by the local setup. The launcher connects directly;
it selects one key for the whole session and does not run a proxy.

You may configure just the required GPT公益/Sol key, or configure both keys.
The installer prompts for the optional Astra-专属余额 key after the Sol key;
press Enter to skip it. Do not paste one group's key into the other group's
prompt. The group is chosen when you start Codex, not by changing models in
`/model`.

## Models and reasoning

The model catalogs are separate because each API key is tied to its own group.
This table compares the model IDs currently included in this project's group
catalogs.

| GPT公益 | Astra-专属余额 |
| --- | --- |
| `gpt-6.1-sol` | `gpt-5.6-sol` |
|  | `gpt-6` |
|  | `gpt-5.6` |
|  | `gpt-5.6-terra` |
|  | `gpt-5.6-luna` |
|  | `gpt-6.1-terra` |
|  | `gpt-6.1-sol` |
|  | `gpt-6-sol` |
|  | `gpt-6-luna` |
|  | `gpt-6-astra` |
|  | `gpt-5.5` |
|  | `gpt-5.4` |
|  | `gpt-5.4-mini` |
|  | `gpt-5.3-codex-spark` |
|  | `codex-auto-review` |
|  | `gpt-5.2` |
|  | `gpt-image-1` |
|  | `gpt-image-1.5` |
|  | `gpt-image-2` |
|  | `gpt-image-2.5-flare` |
|  | `gpt-image-2.5-sunburst` |
|  | `gpt-image-2.6-flare` |
|  | `gpt-image-2.6-sunburst` |

The installer queries both configured keys separately and writes
`xingchi-models.json` for GPT公益 and `xingchi-models-astra.json` for Astra.
The Astra launcher selects the second catalog as well as the Astra key. Each
catalog can also include additional IDs discovered from that same key.

An ID in this table is only a catalog listing; it does **not** prove the group
has balance, an active route, or that the ID supports interactive Codex
requests. Non-conversation image, embedding, and utility IDs are included
because the group advertises them, but may reject a Codex text request.
In the earlier session check, Astra requests returned an insufficient-balance
error; the menu can expose the group's full list, but that account-side balance
issue must be resolved separately before Astra requests will succeed.

Known GPT-6 model entries have per-model reasoning presets; model IDs without
known metadata are shown without a reasoning submenu.

Ultra is a Codex preset. In the reference CLI, 0.170.0, selecting Ultra sends
`reasoning.effort = "max"` to the API.

The launcher chooses the key group for the whole session; it never silently
routes individual models across keys. Use a model listed for the selected
group.

The `gpt-6-astra` model is available only in the Astra-专属余额 catalog.
Start with `xingchi-codex --astra`, then select it in `/model` or pass
`-m gpt-6-astra`. The `--astra` flag selects the separate Astra key for the
whole session.

The menu and its reasoning choices are local configuration. **They do not
grant account access.** If Xingchi returns `model_not_found` for Astra, Luna,
or Terra, that exact model must be enabled for your key's account group.

## Install

macOS and Linux (any distros)

```sh
curl -fsSL https://raw.githubusercontent.com/kikiprojecto/xingchi-codex/main/install.sh | sh
```

Windows (PowerShell 5.1+)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/kikiprojecto/xingchi-codex/main/install.ps1 | iex"
```

The installer:

1. Asks for the required **GPT公益/Sol API key**, then offers an optional
   **Astra-专属余额 API key** prompt. Press Enter at the optional prompt to
   install with only the Sol key on a fresh setup. If `astra.key` already
   exists, the installer reuses it; remove that file only if you intentionally
   want to remove the saved Astra credential. The keys are stored separately as
   `~/.xingchi/upstream.key` and `~/.xingchi/astra.key` (mode 600 on
   macOS/Linux). Neither key is written into this repository.
2. Installs or updates the Codex CLI (`npm install -g @openai/codex`) when it
   is missing or older than the supported minimum, 0.170.0.
3. Checks each configured key and reads its list of models from `/v1/models`,
   then writes a separate catalog for each group, reasoning
   presets, compaction compatibility setting, feature defaults and launchers.

If the upstream rejects the key (`401`/`403`) the installer exits non-zero and
tells you to get a new key, so a failed check never looks like a finished
install. Paste the key with or without surrounding spaces; it is trimmed.

Non-interactive:

```sh
XINGCHI_API_KEY='<GPT公益/Sol key>' \\
  XINGCHI_ASTRA_API_KEY='<optional Astra-专属余额 key>' \\
  sh install.sh --yes
```

Leave out `XINGCHI_ASTRA_API_KEY` to configure only GPT公益/Sol. On Windows,
set `$env:XINGCHI_API_KEY` (and optionally `$env:XINGCHI_ASTRA_API_KEY`) before
running `install.ps1 -Yes`. Avoid putting real keys in shell history, scripts,
screenshots, or this repository; the interactive hidden prompt is preferred.
To remove an Astra key that was saved previously, delete
`~/.xingchi/astra.key` (Windows: `Remove-Item "$env:USERPROFILE\.xingchi\astra.key"`)
and rerun the installer. This does not delete the Sol key.

To install from this checkout using your saved key:

```sh
sh install.sh --yes
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Yes
```

## What it writes

`~/.codex/config.toml` (existing settings are merged, the old file is copied to
`config.toml.xingchi.bak`):

```toml
model_provider = "OpenAI"
model = "gpt-6.1-sol"
model_catalog_json = "/absolute/path/to/.codex/xingchi-models.json"

[model_providers.OpenAI]
name = "OpenAI"
base_url = "https://api.xingchiapi.com/v1"
wire_api = "responses"
requires_openai_auth = false
env_key = "XINGCHI_API_KEY"
supports_websockets = false
http_headers = { "x-openai-actor-authorization" = "local-image-extension" }
capabilities.remote_compaction = "unsupported"

[features]
api_key_model_discovery = true
image_generation = true
goals = true
```

The installer builds the model catalog beside `config.toml` and uses
`CODEX_HOME` when set. Codex reads the model and reasoning choices from that
catalog. The feature values above are defaults for a fresh install; explicitly
saved feature choices are retained on reinstall. The installer also preserves
your saved model (if still in the catalog) and reasoning level. It does not
force one reasoning level for every model.

The launcher configures one OpenAI provider and supplies the selected key via
`XINGCHI_API_KEY`. The standard command uses the GPT公益/Sol key and its
catalog. Adding `--astra` selects the Astra-专属余额 key and catalog; when no
model is explicitly selected, it starts with `gpt-6-astra`. An explicit
`-m`/`--model` or `-c model=...` is preserved. Both modes connect directly to
Xingchi over HTTPS, without a local proxy.

### Project-local skill collection

To make a reviewable project-local copy of skills from all three user roots,
run:

```sh
python3 scripts/sync-skills.py
```

The utility copies skill directories into the public `skills/` directory
without modifying the originals. It deduplicates identical same-name skills,
gives divergent same-name variants deterministic `--variant-<hash>` names, and
writes a review inventory to `skills/LIST.md`. The sync stops rather than
overwriting a non-empty existing `skills/` directory. The generated bundle is
intended to be reviewed, staged, committed, and published with this project;
see `skills/LIST.md` for the inventory. Runtime state, dependencies,
credentials, local repository metadata, and common secret-bearing files are
excluded. Textual
absolute home-directory paths are redacted as `<HOME>`. Third-party license
and redistribution terms still require human review before publishing.

The installers do not automatically install this bundle.
Run the utility again only after moving or removing the current project-local
copy.

The integration step preserves every existing `mcp_servers` entry and adds
portable definitions for the current Codex MCP set when an entry is absent:

- Rust Anything, OpenAI Developer Docs, Context7, GitHub, Exa, GitLab, Magic,
  MongoDB, filesystem, Sequential Thinking, Playwright, PostgreSQL, Supabase,
  Linear, Atlassian, Figma, Chrome DevTools, Firecrawl, Redis, Repomix,
  shadcn, SQLite, Tavily and Time.

Credential-dependent, OAuth-managed, or compatibility-sensitive entries stay
in the config but are inactive until authenticated or explicitly enabled.
This keeps one missing token, invalid local database path, or failed stdio
handshake from making the whole MCP startup fail. Set a matching credential
or opt in explicitly before launching Codex:

| MCP | Credential or opt-in |
| --- | --- |
| GitHub | `GITHUB_PAT_TOKEN` |
| Exa | `EXA_API_KEY` |
| GitLab | `GITLAB_PERSONAL_ACCESS_TOKEN` |
| Magic | `API_KEY` |
| MongoDB | `MDB_MCP_CONNECTION_STRING` |
| Firecrawl | `FIRECRAWL_API_KEY` |
| PostgreSQL | `DATABASE_URL` or an existing connection string |
| Supabase, Linear, Atlassian, Figma | Authenticate with the provider's Codex OAuth flow |
| filesystem | `XINGCHI_ENABLE_MCP_FILESYSTEM=1` and an existing directory |
| SQLite | `XINGCHI_ENABLE_MCP_SQLITE=1` |
| Redis | `XINGCHI_ENABLE_MCP_REDIS=1` and a reachable Redis instance |
| Tavily | Authenticate with the provider's Codex OAuth flow |

The repository contains integration logic only, never private skill files,
local workspace metadata, or credentials. API keys are read from environment
variables or local files at install/runtime and are never written into this
checkout.

To skip all automatic skills/MCP integration changes for one installation:

```sh
XINGCHI_SKIP_INTEGRATIONS=1 sh install.sh
```

```powershell
$env:XINGCHI_SKIP_INTEGRATIONS = '1'
.\install.ps1
Remove-Item Env:\XINGCHI_SKIP_INTEGRATIONS
```

This opt-out leaves existing skills and MCP configuration untouched; API-key
and model setup still runs.

Compaction uses ordinary Responses requests to summarize conversation history.
The provider override above disables Codex's remote compaction v2 protocol,
whose `compaction_trigger` input fails on Xingchi. This keeps compaction
available for long sessions and `/compact`.

On Windows, the default Codex directory is `%USERPROFILE%\.codex`, and the
launchers are installed under `%LOCALAPPDATA%\xingchi\bin`.

`~/.xingchi/upstream.key` — your GPT公益/Sol key, mode 600.
`~/.xingchi/astra.key` — optional Astra-专属余额 key, mode 600.
`~/.local/bin/xingchi-codex` — reads the selected key at runtime and launches
`codex` directly.
`~/.local/bin/xingchi` — prints the current setup.

## Use

```sh
xingchi-codex                            # GPT公益/Sol key (default)
xingchi-codex --astra                    # Astra-专属余额 key; default model: gpt-6-astra
xingchi-codex -m gpt-6.1-sol             # GPT公益/Sol, explicitly select a model
xingchi-codex --astra -m gpt-6-astra     # Astra, explicitly select a model
xingchi-codex /inherit                  # choose saved work and continue in a fresh chat
xingchi-codex --astra /inherit          # use the Astra key for the fresh chat
xingchi-codex exec "..."                 # non-interactive using GPT公益/Sol
xingchi-codex --astra exec "..."         # non-interactive using Astra
xingchi                                  # show API, model, key and Codex status
xingchi --doctor                         # run codex doctor
codex doctor                             # full health check
```

`xingchi-codex` passes your arguments to `codex` and adds `--no-daemon` so
each launch reads the installed catalog. Codex's shared background server can
keep an older model list even after you quit and reopen the terminal UI.

`--astra` must be the first argument after `xingchi-codex`. It selects
`astra.key` and the Astra catalog for that run; without it, the launcher uses
`upstream.key` and the GPT公益 catalog. Both keys are optional only in the
sense that Astra may be omitted: a missing selected key stops launch without
falling back to the other group. `/model` selects among the chosen group's
catalog and changes reasoning effort where supported; it does not switch the
API key/group. Use the exact model IDs shown for that group.

Rerun the updated installer and restart `xingchi-codex`. Open `/model`,
select a model, and choose a reasoning level. Max and Ultra appear under
**More reasoning** where available. Reinstalling keeps your saved reasoning
level and any saved model that is still in the catalog.
The installers check for Codex CLI 0.170.0 or newer and update older versions.

### OpenBot's ChatGPT provider on Linux

OpenBot can prefer its own managed Codex binary, bypassing `xingchi-codex`.
With this repository's provider configuration, that can produce
`Missing environment variable: XINGCHI_API_KEY` even though the Xingchi CLI
works in your terminal. After installing Xingchi and OpenBot, run:

```sh
python3 scripts/setup-openbot.py          # preview the local changes
python3 scripts/setup-openbot.py --apply  # install the OpenBot launchers
```

Quit and reopen OpenBot from its application-menu entry or
`~/.local/bin/openbot`. The setup uses OpenBot's `OPENBOT_CODEX_PATH`
override to route its ChatGPT provider through the installed Xingchi launcher.
The key stays in `~/.xingchi/upstream.key` and is read when Codex starts;
neither the desktop entry nor the OpenBot wrapper contains it.

This OpenBot-specific launcher sets Codex defaults to `gpt-6.1-sol`,
`sandbox_mode="danger-full-access"`, and `approval_policy="never"`.
OpenBot sends its own settings for each agent, so also select **Full access**
and **Always allow** for the ChatGPT agent and choose `gpt-6.1-sol` there.
Other uses of `xingchi-codex` retain their existing permissions and model choices.
OpenBot and Codex both read `~/.agents/skills`; changes to that shared library
are available to both without a separate copy or synchronization job.

The command preserves custom desktop fields, backs up an existing desktop
entry before its first change, and refuses to overwrite an unrelated command
at `~/.local/bin/openbot`. An already-running OpenBot process needs a restart
to read the launcher override.

### Continue saved work with `/inherit` (recommended for session limits)

Use `/inherit` when a conversation reaches `session_turn_limit_exceeded` or
`session_request_limit_exceeded`, especially when `--continue` immediately
hits the same error again.

1. Start `xingchi-codex` in the same project directory as the saved session.
   Use `xingchi-codex --astra` if that work needs the Astra key.
2. In the chat, type `/inherit` and press Enter. You can also type `/` and
   press Enter on the selected `/inherit` entry. The picker opens locally,
   including in a capped chat.
3. Use ↑/↓ or Page Up/Down to choose a session. Type part of its title or ID
   to filter the list. Press Esc to cancel and return to the current chat.
4. Press Enter on the session you want. The launcher starts a fresh chat and
   automatically prompts it to read the selected history and continue unfinished
   work. You do not need to paste a continuation prompt yourself.

Inherited chats automatically use **Full access** with approval policy **never**.
This applies to both the in-chat picker and `xingchi-codex /inherit`, even when
the original chat used restricted permissions. Commands in the new chat run
without sandboxing or command approval prompts; no `/permissions` step is needed.
Both installers refresh the launcher and all its helpers in the PATH directory
and keep a matching runtime copy under `~/.xingchi/bin` (`XINGCHI_HOME/bin` when
customized). Ordinary, non-inherited chats retain their existing permissions.

If the old chat is already closed, run `xingchi-codex /inherit` from that
project directory to open the picker directly. For Astra, run
`xingchi-codex --astra /inherit`. After installing an update, exit any running
Codex and relaunch `xingchi-codex` once to load the new command.

**Why prefer `/inherit` over `--continue` for a capped conversation?**

| | `/inherit` | `xingchi-codex --continue` |
| --- | --- | --- |
| New conversation | Starts with a continuation prompt referencing the selected session; old turns are available through a scoped history tool. | Runs native `fork --last`, copying the latest saved conversation into a fork with a new session ID. |
| Choose the source | Browse and filter sessions from the same project directory, including archived sessions. | Uses the latest session; choose another explicitly with `xingchi-codex fork <SESSION_ID>`. |
| Context at launch | Reads relevant saved turns and tool results on demand. | Begins with the fork's saved context, including any existing summaries. |
| Recover from a turn limit | Starts without replaying the capped conversation as previous messages. | The copied conversation can still trigger the provider's turn limit, even with a new session ID. |

`/inherit` is the recommended recovery path because it separates the new
conversation from the old message sequence while keeping saved history
accessible. `--continue` remains useful when you want to branch directly from
the latest saved context and that context is still accepted by the provider.
Neither command increases your API balance, account quota, or context window,
or restores unsaved/deleted history. See the [history commands and limitations](#start-a-fresh-chat-with-saved-context-inherit)
for explicit session selectors and manual history reads.

## Requirements

- curl and tar (macOS/Linux); PowerShell 5.1+ (Windows)
- Python 3 (checks model availability and writes the Codex configuration)
- Node.js with npm (to install the Codex CLI)

## Security

- Your Xingchi keys are stored in `~/.xingchi/upstream.key` and optional
  `~/.xingchi/astra.key`; the Codex config contains environment variable names,
  never key values. These files and their backups use mode 600 on
  macOS/Linux. The key is never committed to this repository or passed on a
  command line.
- The Windows installer stores keys beneath `%USERPROFILE%\.xingchi`; do not
  share that directory or paste its files into diagnostics. It writes explicit
  user-restricted ACLs for both key files (alongside the normal Windows system
  and administrator access), and does not put key values in the generated
  launcher or Codex config.
- The launcher reads the key file at runtime; the repository contains no
  credentials.
- Both launch modes connect directly over HTTPS. `xingchi-codex --astra`
  selects the Astra key directly; no proxy is involved.

## Adding other model IDs

If your account can use a model that Xingchi's `/v1/models` omits, add its
exact ID to `~/.xingchi/models.txt` (`%USERPROFILE%\.xingchi\models.txt` on
Windows, or under `XINGCHI_HOME` if set). Use one model ID per line, save as
UTF-8, prefix each entry with `sol:` or `astra:` (for example,
`astra:gpt-6.2-astra`), then rerun the installer and restart Codex. IDs added
this way are user-supplied, not verified by `/v1/models`. Entries without known
reasoning metadata appear without a reasoning submenu.

Choose the key group first, then select a model available to that group. You
can also try a specific model and reasoning setting from the terminal.

```powershell
xingchi-codex --astra -m gpt-6-astra -c 'model_reasoning_effort="high"'
xingchi-codex --astra -c 'model_reasoning_effort="high"'
```

`--astra` is consumed by the Xingchi launcher and is never passed to Codex.
It must appear immediately after `xingchi-codex`. Without it, the launcher
uses `upstream.key`; with it, the launcher uses `astra.key`. If the selected
key file is missing, launch stops with an error instead of silently falling
back to the other key.

Changing the reasoning level in `/model` saves it for the next launch. A
command-line `-c` override applies to that invocation.

## Troubleshooting

### Start a fresh chat with saved context (`/inherit`)

Inside `xingchi-codex`, type `/inherit` and press Enter. A session picker
opens immediately, including when the current chat has hit a provider limit.
Use ↑/↓ or Page Up/Down, type a title or ID to filter, then press Enter to
inherit the selected session. Esc returns to the current chat. The list is
restricted to saved sessions in the launch directory and includes archived
sessions. `/inherit <ID or title>` opens the same picker with a filter.

Typing `/` displays `/inherit` as the selected first row of the command popup.
Press Enter to open the session list, or ↓ to select Codex's normal commands.
After updating an already-running launcher, exit it and start `xingchi-codex`
once to load the terminal command extension.

The same picker and selectors are available from the shell:

```sh
xingchi-codex /inherit                    # choose from same-directory sessions
xingchi-codex /inherit --list             # show names and IDs without starting a chat
xingchi-codex /inherit '<SESSION_ID>'     # full ID, unique prefix, or title
xingchi-codex /inherit 'Verify Codex model configuration'
```

`--inherit` is an alias for the shell command; put `--astra` before either
form to use the dedicated key for the new chat. In-chat inheritance keeps the
key group and command-line settings of the running launcher.

The launcher starts a fresh chat, not a resume or a fork. Its first prompt
contains the selected session ID, not its old turns. The new chat can read the
source's saved turns and tool results on demand through a read-only tool scoped
to the selected session. For manual use,
`xingchi-codex --inherit-history <SESSION_ID>` prints the latest saved turn as
JSON; pass its `nextCursor` to `--cursor` to keep reading.
Listings and manual reads do not send a model request. History the new chat
reads as tool output can be sent to the model. Only persisted history that
Codex still exposes can be recovered; unsaved or deleted turns cannot.

### Session request or turn limits

If Xingchi returns `session_request_limit_exceeded` or
`session_turn_limit_exceeded`, type `/inherit` inside the current chat and
choose the saved session. The picker does not send a model request. If you
have already exited, run this from the same project directory:

```sh
xingchi-codex /inherit
```

For Astra, use `xingchi-codex --astra /inherit`. Follow the
[navigation steps and command comparison](#continue-saved-work-with-inherit-recommended-for-session-limits)
above. If `--continue` keeps hitting the same limit, switch to `/inherit`
instead of repeatedly forking the capped conversation.

| Symptom | Cause / fix |
| --- | --- |
| `session_turn_limit_exceeded` or `session_request_limit_exceeded` | Use `/inherit`, select the saved session, and press Enter to continue in a fresh chat. From the shell, run `xingchi-codex /inherit` in the same directory. |
| `No connected db` | Something points Codex at an old LiteLLM proxy. Remove any `127.0.0.1:4010` base URL and restart Codex. |
| `No models are available` | Rerun the installer to rebuild the catalog, then restart Codex. |
| `/model` does not show newly discovered models | Rerun the installer to refresh both model lists, then restart `xingchi-codex` so the shared background server reloads the catalog. |
| `client_not_allowed` | The upstream rejects scripts/SDKs/proxies. Use the Codex CLI directly, not curl or a proxy. |
| `model_not_found` | Xingchi rejected that exact model ID for the selected key group. Rerun the installer to refresh both `/v1/models` responses; catalog visibility does not grant access or imply every model accepts Codex text requests. |
| `Upstream request failed` (`upstream_error`, HTTP 400) | Xingchi rejects the `custom_tool_call` items Codex writes for its experimental Code Mode `exec` tool. The generated catalog keeps that tool off; a session started before this fix still replays those items, so start a new `xingchi-codex` session instead of resuming the old one. |
| `Error running remote compact task` | Rerun the updated installer, restart `xingchi-codex`, and resume the session. The provider must set `capabilities.remote_compaction = "unsupported"` so compaction uses ordinary Responses requests. |
| `401` on install | The key is wrong or expired. Create a new one at <https://xingchiapi.com/keys>. |
| Restart needed | If Codex was already running, fully quit it so it reloads `~/.codex/config.toml`. |

Restore the previous Codex config with:

```sh
mv ~/.codex/config.toml.xingchi.bak ~/.codex/config.toml
```

The installer adds the launcher directory to your shell PATH if needed.

### MCP startup errors

MCP servers in your existing Codex config are preserved during installation.
Fix their entries in `~/.codex/config.toml` (`%USERPROFILE%\.codex\config.toml`
on Windows, or under `CODEX_HOME` when set):

```toml
[mcp_servers.filesystem]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "/absolute/path/to/an/existing/projects/directory"]

[mcp_servers.github]
url = "https://api.githubcopilot.com/mcp/"
bearer_token_env_var = "GITHUB_PAT_TOKEN"

[mcp_servers.supabase]
url = "https://mcp.supabase.com/mcp"
```

Replace the filesystem path with an existing directory you want the server
to access. On Windows, use a path such as `C:/your-projects-directory`.
The sample `/path/to/your/projects` makes the server exit during startup.

GitHub needs `GITHUB_PAT_TOKEN` exported in the terminal that launches
`xingchi-codex`; setting up the URL alone does not authenticate it. In
PowerShell, the corresponding environment variable is `$env:GITHUB_PAT_TOKEN`.
Enter your token locally; do not commit it to this repository.

Authenticate Supabase with `codex mcp login supabase`, then restart
`xingchi-codex` and check `/mcp`. A Cloudflare 403 can block access separately
from authentication; a corrected URL does not establish a working connection.

## Development checks

With Python 3.11+:

```sh
python3 -m unittest discover -s tests
```

The tests cover fresh installs, CLI upgrades, saved selections, all advertised
reasoning values, resumed-session compaction, and the real Codex model/effort
menus against a local fake upstream. Native Windows installer tests run on
Windows. No paid API requests are used by the suite.

## Uninstall

```sh
rm -f ~/.local/bin/xingchi ~/.local/bin/xingchi-codex
rm -rf ~/.xingchi
```

Windows:

```powershell
Remove-Item "$env:LOCALAPPDATA\xingchi" -Recurse -Force
```
