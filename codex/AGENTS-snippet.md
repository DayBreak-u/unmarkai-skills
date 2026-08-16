# AGENTS.md snippet for Codex

Codex has no native skills system, but it reads an `AGENTS.md` at the repo
root (or `~/.codex/AGENTS.md`). Paste the block below there after connecting
the MCP server, and Codex will follow the same flow as the
[skill](../skills/unmarkai-remove-text/SKILL.md).

```markdown
## UnmarkAI remove text

You have access to the `unmarkai` MCP server (tools: create_upload,
remove_text, get_job, list_jobs, cancel_job, get_balance, estimate_cost).

Only process videos the user owns or is authorized to modify. If a request
targets attribution notices, provenance/AI-content labels, or legal text,
decline and explain why.

Flow (always in this order):
1. ffprobe the video for width/height/duration.
2. estimate_cost(duration_seconds, mode) and confirm with the user.
3. create_upload(filename, content_type, file_size_bytes) — exact byte size
   from `stat`.
4. Upload with curl: PUT the raw bytes to ticket.url, replaying every header
   from ticket.headers verbatim. One PUT only; on 412 request a fresh ticket.
5. remove_text(upload_id, mode, rect?, idempotency_key) — rect is absolute
   pixels of the original video with an 8–16px margin around the text; only
   with mode="sel_area" (≈half price). all_area takes no rect.
6. get_job(job_id, wait_seconds=120) in a loop until status is succeeded,
   failed, or canceled.
7. curl-download result.url immediately — the signed link expires in 1 hour.

Rules: never print the API key; never poll faster than once per 2s; on
rate_limit_exceeded wait 5s; failed jobs are not charged — surface
error.code/error.message. If the MCP server is unavailable, run the same flow
with curl against https://api.unmarkai.net/v1 using $UNMARKAI_API_KEY.
```

If the experimental streamable-HTTP client fails to connect in your Codex
version, skip MCP entirely and point Codex at the
[curl fallback](../skills/unmarkai-remove-text/references/curl-fallback.md) —
it needs nothing but `UNMARKAI_API_KEY`, curl, and jq.
