---
name: unmarkai-video-upscale
description: Enhance or upscale authorized videos to 1080p, 2K or 4K using the China UnmarkAI video_upscale REST API. Use for video HD or super-resolution, not translation output sizing.
---

# UnmarkAI Video Upscale

Use the official China REST workflow. There is no documented native HD MCP tool;
never invent an `upscale` MCP call or route HD through `remove_text` or translation.
Only process material the user owns or is authorized to modify. Never expose
API keys or signed upload/download URLs in logs or committed files.

Read [the contract](../unmarkai-remove-text/references/api-contract.md) for limits, pricing,
regional differences and errors, and [curl workflow](references/curl-fallback.md)
for concrete requests. Requires `UNMARKAI_API_KEY`, Bash, curl, jq and ffprobe.

1. Probe duration, display dimensions (including rotation) and average FPS.
   Select `1080p`, `2k` or `4k` with both source edges within the target.
2. Read domestic balance and `amounts.upscale_rates`. Estimate locally with
   `max(15, ceil(seconds))`, doubling for FPS >30; rates already include account
   discount. Explain the estimate and obtain spending authorization if it has
   not already been provided. No live estimate endpoint exists for this flow.
3. Obtain an upload ticket and PUT once with every returned header, or import
   a direct public HTTPS URL. Wait for `uploaded`; stop on failure or expiry.
4. Persist a business idempotency key. POST `/jobs` with `type=video_upscale`,
   `input.upload_id`, `upscale.target` and optional `metadata`. Do not send FPS
   or multiplier; these are server-measured response fields.
5. Save the job ID and poll with a deadline. On timeout retain the ID; do not
   submit another job. Stop on `succeeded`, `failed` or `canceled`.
6. Download `result.url` promptly without API auth headers. Report output path,
   target and final `currency`/`amounts`; surface `error.code/error.message` on
   failure. Signed links last up to 1 hour, results 7 days.

Cancellation is allowed during `validating` or `queued` using POST
`/jobs/{job_id}/cancel`; handle a race with 409 `job_not_cancelable`.
Use bounded backoff on 429/temporary 5xx; fix other request errors before retrying.
