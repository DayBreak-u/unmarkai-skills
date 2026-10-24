# unmarkai-skills

[![Website](https://img.shields.io/badge/website-unmarkai.net-7f5bf5)](https://unmarkai.net/video-text-removal-api/)
[![License: MIT](https://img.shields.io/badge/License-MIT-38d995.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-streamable_HTTP-39b9ed)](https://api.unmarkai.net/mcp)

Agent skills for [UnmarkAI](https://unmarkai.net) — let Claude, Codex,
Cursor, opencode and any MCP-capable agent **remove hardcoded text
(subtitles, captions, on-screen titles) from videos you own** with a single
`UNMARKAI_API_KEY` and no other setup.

Product page: **[Video Text Removal API & MCP Server](https://unmarkai.net/video-text-removal-api/)**.

Two ways to connect, same engine underneath:

- **Remote MCP server** (recommended): `https://api.unmarkai.net/mcp`
- **Plain REST** (no MCP support needed): full curl walkthrough in
  [skills/unmarkai-remove-text/references/curl-fallback.md](skills/unmarkai-remove-text/references/curl-fallback.md)

## What you get

| | |
|---|---|
| Tools | `create_upload`, `create_url_upload`, `get_upload`, `remove_text`, `get_job`, `list_jobs`, `cancel_job`, `get_balance`, `estimate_cost` |
| Pricing | Per second, rounded up, 1s minimum — `all_area` $0.010/s, `sel_area` $0.005/s (partial region, ~half price) |
| Limits | Max 2 GiB / 60 min per video; mp4 / mov / avi / mkv / webm / mpeg |
| Result | Signed download link, valid 1 hour (file kept 7 days) |
| Rate limits | 50 write / 120 read calls per minute |

## Setup: get a key

1. Sign in at [unmarkai.net](https://unmarkai.net) and open the
   **API Console** (Dashboard → API).
2. Create an API key with scopes `jobs:read`, `jobs:write`, `balance:read`.
3. Top up the API wallet (pay-as-you-go).
4. Export it:

```bash
export UNMARKAI_API_KEY="uma_live_xxxxxxxxxxxx"
```

## Connect your agent (remote MCP)

### Claude Code

```bash
claude mcp add --transport http unmarkai https://api.unmarkai.net/mcp \
  --header "Authorization: Bearer $UNMARKAI_API_KEY"
```

Then install the skill so Claude Code follows the full flow (mode selection,
rect margins, error triage):

```bash
mkdir -p ~/.claude/skills && \
  cp -r skills/unmarkai-remove-text ~/.claude/skills/
```

### Claude Desktop

Claude Desktop does not speak to remote HTTP MCP servers natively — bridge it
with [`mcp-remote`](https://github.com/geelen/mcp-remote) in
`claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "unmarkai": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://api.unmarkai.net/mcp",
        "--header",
        "Authorization: Bearer uma_live_xxxxxxxxxxxx"
      ]
    }
  }
}
```

### Cursor

`~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "unmarkai": {
      "type": "http",
      "url": "https://api.unmarkai.net/mcp",
      "headers": { "Authorization": "Bearer uma_live_xxxxxxxxxxxx" }
    }
  }
}
```

### Windsurf

`~/.codeium/windsurf/mcp_config.json` — same shape as Cursor but with the
streamable-HTTP type (see the Windsurf docs for your version):

```json
{
  "mcpServers": {
    "unmarkai": {
      "type": "streamableHttp",
      "url": "https://api.unmarkai.net/mcp",
      "headers": { "Authorization": "Bearer uma_live_xxxxxxxxxxxx" }
    }
  }
}
```

### Codex CLI

Streamable HTTP is still experimental in Codex — enable the RMCP client and
declare the server in `~/.codex/config.toml`:

```toml
experimental_use_rmcp_client = true

[mcp_servers.unmarkai]
url = "https://api.unmarkai.net/mcp"
bearer_token = "uma_live_xxxxxxxxxxxx"
```

Codex has no native skills system; put the flow instructions in your
`AGENTS.md` instead — see
[codex/AGENTS-snippet.md](codex/AGENTS-snippet.md). If the experimental HTTP
client misbehaves in your Codex version, fall back to the
[curl flow](skills/unmarkai-remove-text/references/curl-fallback.md).

### opencode

`~/.config/opencode/opencode.json` (or `opencode.json` in a project):

```json
{
  "mcp": {
    "unmarkai": {
      "type": "remote",
      "url": "https://api.unmarkai.net/mcp",
      "headers": { "Authorization": "Bearer uma_live_xxxxxxxxxxxx" }
    }
  }
}
```

### Gemini CLI

`~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "unmarkai": {
      "httpUrl": "https://api.unmarkai.net/mcp",
      "headers": { "Authorization": "Bearer uma_live_xxxxxxxxxxxx" }
    }
  }
}
```

## Try it

Once connected, just ask:

> Remove the hardcoded subtitles from `draft.mp4` (it's my own video). Estimate
> the cost first, use the cheapest mode that covers the subtitle area, and
> download the clean version next to the original.

The agent will probe the video, quote the estimate, import a direct HTTPS URL
or upload a local file with a one-shot ticket, create the job, wait for
completion, and download the result.

## Verify the connection

```bash
curl -sS -X POST https://api.unmarkai.net/mcp \
  -H "Authorization: Bearer $UNMARKAI_API_KEY" \
  -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

A JSON-RPC result listing the nine tools means everything works. `401
unauthorized` means the key is wrong; `404` means you hit the wrong URL.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `unauthorized` | Key must start with `uma_live_` and be active; check the API Console |
| `insufficient_scope` | Recreate the key with `jobs:read jobs:write balance:read` |
| `rate_limit_exceeded` | Slow down — agents should poll at most once per 2s |
| `insufficient_balance` | Top up the API wallet in the dashboard |
| Client can't connect to remote MCP | Check the client's syntax above for the exact config shape; worst case use the curl fallback |
| Upload PUT returns 412 | Upload tickets are one-shot — request a new one |
| URL import fails | Use a public HTTPS URL that directly returns a supported video with a stable Content-Length; page links are not accepted |

## Security notes

- The key grants spend from your API wallet — treat it like a credit card.
- Prefer env-var expansion (`$UNMARKAI_API_KEY`) over pasting literals into
  config files where the client supports it.
- Rotate the key in the API Console if it leaks; revoke immediately if shared
  in a repo (`git rm --cached` + rewrite history).

## Responsible use

This tooling is for videos **you own or are authorized to modify**. The skill
ships with a guardrail that declines jobs targeting attribution notices,
provenance labels (including AI-content disclosures), or legal text. Removing
such markers from content you don't control may be unlawful — don't.

## License

[MIT](LICENSE) © DayBreak-u


## Public API example repositories

- [Video text removal & subtitle removal API](https://github.com/DayBreak-u/unmarkai-video-text-removal-api) — real cleanup comparisons, Python/cURL uploads, region modes, polling and downloads. [API guide](https://unmarkai.net/video-text-removal-api/).
- [Video translation & AI dubbing API](https://github.com/DayBreak-u/unmarkai-video-translation-api) — REST examples for translation, two-stage text review, video and SRT downloads. [API guide](https://unmarkai.net/video-translation-api/).

The Skill and MCP tools in this repository cover text cleanup. Use the translation REST examples for the next localization stage; cleanup and translation are separate, separately billed jobs.
