# unmarkai-skills

English | [简体中文](README.zh-CN.md)

[![Website](https://img.shields.io/badge/website-unmarkai.net-7f5bf5)](https://unmarkai.net/video-text-removal-api/)
[![License: MIT](https://img.shields.io/badge/License-MIT-38d995.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-streamable_HTTP-39b9ed)](https://api.unmarkai.net/mcp)

Agent skills for [UnmarkAI](https://unmarkai.net) — let Claude, Codex,
Cursor, opencode and any MCP-capable agent **remove hardcoded text
(subtitles, captions, on-screen titles) from videos you own** and **enhance authorized videos to 1080p, 2K or 4K** through the regional REST API.
Use `UNMARKAI_API_KEY` for your chosen region.

Product page: **[Video Text Removal API & MCP Server](https://unmarkai.net/video-text-removal-api/)**.

Text cleanup supports MCP and REST. Video HD (`video_upscale`) is available
on both the overseas and China REST APIs; there is no documented native HD
MCP tool. Translation is a separate service.
See [verified API contract and regional limits](skills/unmarkai-remove-text/references/api-contract.md) and
the [HD skill](skills/unmarkai-video-upscale/SKILL.md).

Two ways to connect for cleanup:

- **Remote MCP server** (recommended): `https://api.unmarkai.net/mcp`
- **Plain REST** (no MCP support needed): full curl walkthrough in
  [skills/unmarkai-remove-text/references/curl-fallback.md](skills/unmarkai-remove-text/references/curl-fallback.md)

## What you get

| | |
|---|---|
| Tools | `create_upload`, `create_url_upload`, `get_upload`, `remove_text`, `get_job`, `list_jobs`, `cancel_job`, `get_balance`, `estimate_cost` |
| Pricing | Use current regional balance/estimate; China: 15s minimum, CNY 0.040/s full/multi-region, 0.020/s single-region before discount |
| Limits | Max 2 GiB / 60 min per video; mp4 / mov / avi / mkv / webm / mpeg |
| Result | Signed download link, valid 1 hour (file kept 7 days) |
| Concurrency / rate limits | Read balance `concurrency`; honor 429 and Retry-After |

## Setup: get a key

1. Open the [China API Console](https://unmarkai.cn/developers/) or the
   overseas [UnmarkAI](https://unmarkai.net) API Console (Dashboard → API).
   Regional keys and wallets are independent.
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
  cp -R skills/unmarkai-remove-text skills/unmarkai-video-upscale ~/.claude/skills/
```

### Claude Desktop

For Claude Desktop configurations that use a local MCP bridge, use [`mcp-remote`](https://github.com/geelen/mcp-remote) in
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

Codex CLI supports native skills. From this checkout, copy both skills to your
project's `.agents/skills/` (or `~/.agents/skills/` for user-wide use):

```bash
mkdir -p .agents/skills
cp -R skills/unmarkai-remove-text skills/unmarkai-video-upscale .agents/skills/
```

Invoke `$unmarkai-remove-text` or `$unmarkai-video-upscale`. For optional cleanup
MCP, configure `~/.codex/config.toml`:

```toml
[mcp_servers.unmarkai]
url = "https://unmarkai.cn/api/mcp"
bearer_token_env_var = "UNMARKAI_API_KEY"
```

Use `https://api.unmarkai.net/mcp` with an overseas key. No experimental flag is
needed. The HD skill uses REST even when MCP is connected. Optional project
instructions: [codex/AGENTS-snippet.md](codex/AGENTS-snippet.md).
Sources: [Codex skills](https://developers.openai.com/codex/skills),
[Codex MCP](https://developers.openai.com/codex/mcp).

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
| Upload PUT returns 409/412 | Inspect upload status; obtain a fresh ticket if needed |
| URL import fails | Use a public HTTPS URL that directly returns a supported video with a stable Content-Length; page links are not accepted |

## Security notes

- The key grants spend from your API wallet — treat it like a credit card.
- Prefer env-var expansion (`$UNMARKAI_API_KEY`) over pasting literals into
  config files where the client supports it.
- Rotate the key in the API Console if it leaks; revoke immediately if shared
  in a repo; follow your repository’s incident process to remove exposed values.

## Responsible use

This tooling is for videos **you own or are authorized to modify**. The skill
ships with a guardrail that declines jobs targeting attribution notices,
provenance labels (including AI-content disclosures), or legal text. Removing
such markers from content you don't control may be unlawful — don't.

## License

[MIT](LICENSE) © DayBreak-u


## Public API example repositories

- [Video text removal & subtitle removal API](https://github.com/DayBreak-u/unmarkai-video-text-removal-api) — real cleanup comparisons, Python/cURL uploads, region modes, polling and downloads. [API guide](https://unmarkai.net/video-text-removal-api/).
- [Video translation & AI dubbing API](https://github.com/DayBreak-u/unmarkai-video-translation-api) — REST examples for translation, video and SRT downloads. [API guide](https://unmarkai.net/video-translation-api/).

The removal skill and published MCP tools cover text cleanup; the HD skill uses REST. Use the translation REST examples for the next localization stage; cleanup and translation are separate, separately billed jobs.

## Video HD (REST)

Install [unmarkai-video-upscale](skills/unmarkai-video-upscale/SKILL.md), then ask:

> Enhance my own source.mp4 to 4K. Estimate cost in this region's API wallet
> currency first, preserve frame rate and audio, and download the result.

Follow the [complete curl workflow](skills/unmarkai-video-upscale/references/curl-fallback.md):
probe → balance/local estimate → upload or HTTPS import → `POST /jobs` with
`{"type":"video_upscale","input":{"upload_id":"upl_REPLACE"},"upscale":{"target":"4k"}}`
→ poll → download `result.url`. Use `https://api.unmarkai.net/v1` with an
overseas key, or `https://unmarkai.cn/api/v1` with a China key. Targets:
`1080p`, `2k`, `4k`; the server determines FPS and doubles rates above 30 FPS.
China standard prices are CNY 0.04/0.08/0.12 per second, minimum 15 seconds,
then account discount. Overseas OpenAPI 1.4.0 bills USD as the active
`all_area` base rate × 1/2/3 for 1080p/2k/4k, then the same FPS multiplier and
discount, also with a 15-second minimum; read live `amounts.upscale_rates`
instead of copying CNY list prices. The public overseas cancel text does not
name `video_upscale`; do not assume a cancel window.
See [contract notes](skills/unmarkai-remove-text/references/api-contract.md) for all input, output, size,
resolution, retention, concurrency, billing and error details.

Translation `output_resolution` only caps translated video output; it is not
HD enhancement and does not forcibly upscale small sources.

## Region selection and verification

China REST: `https://unmarkai.cn/api/v1`; MCP: `https://unmarkai.cn/api/mcp`.
Overseas REST: `https://api.unmarkai.net/v1`; MCP: `https://api.unmarkai.net/mcp`.
The client examples above using `.net` are overseas configurations. Change both
endpoint and key for China.
Read `currency` and `amounts`; China uses CNY, not legacy USD fields. Overseas
HD uses the USD wallet and the 1.4.0 rate formula, not China CNY list prices.

Contract checked 2026-11-16: [overseas OpenAPI 1.4.0](https://unmarkai.net/openapi-v1.yaml),
[China OpenAPI 1.3.0](https://unmarkai.cn/openapi-v1.yaml),
[China developer docs](https://unmarkai.cn/developers/docs/).
Run offline checks with Python 3 plus PyYAML/jsonschema:
`python3 -m unittest discover -s tests -v`. No real uploads or paid jobs are needed.
