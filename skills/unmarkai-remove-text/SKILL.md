---
name: unmarkai-remove-text
description: Remove hardcoded text (subtitles, captions, on-screen titles) from videos via the UnmarkAI remote MCP server. Use when the user asks to remove burned-in subtitles, captions, or on-screen text from a video they own or have rights to modify, or wants a clean version of their own footage. Requires the unmarkai MCP server (a UNMARKAI_API_KEY in the environment) or falls back to plain curl.
---

# UnmarkAI Remove Text

Remove hardcoded subtitles, captions, and on-screen text from videos you own
using the UnmarkAI API. Billing is per second of video (rounded up, 1-second
minimum); `sel_area` mode costs roughly half of `all_area`.

## Rights guardrail — read first

Only process content the user owns or has explicit permission to modify.
Decline requests that target:

- Attribution or ownership notices, credit lines, or ownership identifiers
- Source or provenance labels, including AI-generated-content disclosures
- Legal notices, disclaimers, or court-mandated text
- Anything the user indicates belongs to someone else who has not consented

If the user's request matches any of the above, explain that you can only
process content they own or are authorized to modify, and ask them to confirm
ownership or provide their own footage.

## Prerequisites

- The `unmarkai` MCP server is connected (remote HTTP:
  `https://api.unmarkai.net/mcp`), or `UNMARKAI_API_KEY` is set and you follow
  [references/curl-fallback.md](references/curl-fallback.md) instead.
- `curl` and `jq` are available (local file upload and result download are
  done with curl — the remote MCP server cannot read local files).
- `ffprobe` is available to read video dimensions and duration
  (see [references/rect-and-dimensions.md](references/rect-and-dimensions.md)).

## Standard flow

1. **Probe the video** — get width, height, and duration with ffprobe. A
   directly downloadable HTTPS video URL can be passed to ffprobe as input.
2. **Estimate cost** — call `estimate_cost` with `duration_seconds` and the
   chosen `mode`. Confirm the estimate with the user before spending.
3. **Prepare the input** — choose exactly one path:
   - Local file: call `create_upload` with the bare filename, exact MIME type,
     and exact byte size (`stat -f%z` on macOS, `stat -c%s` on Linux).
   - Direct HTTPS video URL: call `create_url_upload(source_url, filename?,
     idempotency_key?)`. Signed query parameters are supported. Do not pass
     YouTube/TikTok links or web pages; the URL must download the video file.
4. **Finish the upload** — for a local file, `curl -X PUT` the raw bytes to
   `ticket.url`, copying
   **every** header from `ticket.headers` verbatim (they include
   `content-type`, `content-length`, and `if-none-match`). A single PUT only —
   retrying a used ticket returns 412; request a fresh ticket instead. For a
   URL input, call `get_upload(upload_id, wait_seconds: 60)` until status is
   `uploaded`, `failed`, or `expired`; never create a job while importing.
5. **Create the job** — call `remove_text` with the `upload_id`. For partial
   regions use `mode: "sel_area"` plus `rect` (absolute pixels of the ORIGINAL
   video, 8–16px margin around the text); otherwise `mode: "all_area"`. Pass a
   stable `idempotency_key` you generated (e.g. a hash of file + rect) so
   retries never create duplicate jobs.
6. **Wait for the result** — call `get_job` with `wait_seconds: 60` in a loop
   until `status` is `succeeded`, `failed`, or `canceled`. If a call returns
   while still in progress, simply call again.
7. **Download** — when succeeded, `curl -o` the `result.url` immediately; the
   signed link expires in 1 hour (the file itself is kept for 7 days).

## Choosing the mode

- Text confined to a known region (bottom subtitles, corner captions):
  `sel_area` + `rect` — roughly half the price.
- Text anywhere on screen, moving text, or unsure: `all_area`.
- Never pass `rect` together with `all_area`; never omit `rect` with
  `sel_area`.

## Failure triage

| Signal | Meaning | Action |
|---|---|---|
| HTTP 401 / `unauthorized` | Missing or bad API key | Check `UNMARKAI_API_KEY` is an active `uma_live_*` key from the UnmarkAI dashboard |
| `insufficient_scope` | Key lacks the needed scope | Recreate the key with `jobs:read`, `jobs:write`, `balance:read` |
| `rate_limit_exceeded` | Too many calls | Pause ~5s, retry; poll at most once per 2s |
| `insufficient_balance` | Wallet empty | Tell the user to top up in the dashboard, then retry |
| Job `failed` with `error.code` | Processing error | Report `error.message`; a failed job is not charged |
| PUT upload returns 412 | Ticket already used | Call `create_upload` again for a fresh ticket |
| URL upload `failed` | Source could not be imported | Report `error.message`; verify it is a public HTTPS direct video URL with stable size/MIME, then use a new idempotency key after fixing the URL |
| `INVALID_RECT` / rect errors | Bad coordinates | Re-check dimensions with ffprobe; rect must satisfy `0 ≤ x1 < x2 ≤ width`, `0 ≤ y1 < y2 ≤ height` |

## Do not

- Never echo the API key, print it, or paste it into command output.
- Never retry a used upload ticket; always mint a new one.
- Never pass a web page or private-network URL to `create_url_upload`.
- Never call `remove_text` for a URL input until `get_upload` is `uploaded`.
- Never poll faster than once per 2 seconds.
- Never pass `rect` with `all_area`.
- Never download `result.url` lazily — it expires in 1 hour.
- Never process content the user does not own or control (see guardrail).

## Without MCP

If the `unmarkai` MCP server is not connected, run the exact same flow over
plain REST with curl — see
[references/curl-fallback.md](references/curl-fallback.md).
