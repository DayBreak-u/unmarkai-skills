# curl fallback — the full remove-text flow without MCP

Use this when the `unmarkai` MCP server is not connected. Everything is plain
`curl` + `jq` against the UnmarkAI REST API v1. Requires `UNMARKAI_API_KEY`
(an active `uma_live_*` key from the UnmarkAI dashboard).

Only process videos you own or have explicit permission to modify.

## 0. Environment

```bash
: "${UNMARKAI_API_KEY:?set UNMARKAI_API_KEY to your uma_live_* key}"
set -euo pipefail
API="https://unmarkai.cn/api/v1" # overseas: https://api.unmarkai.net/v1
AUTH="Authorization: Bearer $UNMARKAI_API_KEY"
```

## 1. Probe the video

```bash
VIDEO="my-video.mp4"

ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height -show_entries format=duration \
  -of json "$VIDEO"

SIZE=$(wc -c < "$VIDEO" | tr -d ' ')
```

## 2. (Optional) Check the wallet

```bash
curl --fail-with-body -sS "$API/balance" -H "$AUTH" | jq .
```

## 3. Create an upload ticket

For a local file, use the existing one-shot ticket flow:

```bash
TICKET=$(curl --fail-with-body -sS -X POST "$API/uploads" \
  -H "$AUTH" -H 'Content-Type: application/json' \
  --data "{
    \"filename\": \"$(basename "$VIDEO")\",
    \"content_type\": \"video/mp4\",
    \"file_size_bytes\": $SIZE
  }")

UPLOAD_ID=$(jq -r .upload_id <<<"$TICKET")
PUT_URL=$(jq -r .url <<<"$TICKET")
```

The response also contains a `headers` object — the PUT below must replay
every entry verbatim (`content-type`, `content-length`, `if-none-match`).

## 4. Upload the raw bytes (single PUT)

```bash
UPLOAD_HEADERS=()
while IFS= read -r header; do UPLOAD_HEADERS+=(-H "$header"); done \
  < <(jq -r '.headers | to_entries[] | "\(.key): \(.value)"' <<<"$TICKET")
curl --fail-with-body -sS -X PUT "$PUT_URL" \
  "${UPLOAD_HEADERS[@]}" --data-binary "@$VIDEO"
```

A `200`/`201` means the upload landed. A `409`/`412` means the ticket cannot overwrite an object; inspect upload
status, and obtain a fresh ticket if needed. Do not blindly PUT again.

### Alternative: import a direct HTTPS video URL

Skip the ticket and PUT when the source is already a directly downloadable
public HTTPS video. Signed query parameters are supported; web pages,
YouTube/TikTok links, private-network hosts, unknown file sizes, and unsupported
video MIME types are rejected.

```bash
SOURCE_URL='https://cdn.example.com/source.mp4?signature=xxx'
URL_IDEMPOTENCY='url-import-001'

URL_UPLOAD=$(curl --fail-with-body -sS -X POST "$API/url-uploads" \
  -H "$AUTH" -H 'Content-Type: application/json' \
  -H "Idempotency-Key: $URL_IDEMPOTENCY" \
  --data "$(jq -n --arg source_url "$SOURCE_URL" \
    '{source_url: $source_url}')")

UPLOAD_ID=$(jq -r .upload_id <<<"$URL_UPLOAD")
STATUS=pending
for ((i=0; i<360; i++)); do
  UPLOAD=$(curl --fail-with-body -sS "$API/uploads/$UPLOAD_ID" -H "$AUTH")
  STATUS=$(jq -er .status <<<"$UPLOAD")
  case "$STATUS" in uploaded|failed|expired) break ;; esac
  sleep 5
done
[[ "$STATUS" == uploaded ]] || { echo "Not ready; retain $UPLOAD_ID"; exit 1; }
```

Only continue to job creation after the URL upload reaches `uploaded`. Reuse
the same idempotency key only for an identical URL import request.

## 5. Create the job

```bash
# Unique per (file, settings) so retries never double-bill.
IDEMPOTENCY="replace-with-persisted-unique-business-request-id"

JOB=$(curl --fail-with-body -sS -X POST "$API/jobs" \
  -H "$AUTH" -H 'Content-Type: application/json' \
  -H "Idempotency-Key: $IDEMPOTENCY" \
  --data '{
    "type": "remove_text",
    "input": { "upload_id": "'"$UPLOAD_ID"'" },
    "mode": "all_area"
  }')

JOB_ID=$(jq -r .id <<<"$JOB")
```

For a partial region, replace the body with (coordinates are absolute pixels
of the original video; add an 8–16px margin around the text):

```json
{
  "type": "remove_text",
  "input": { "upload_id": "upl_REPLACE" },
  "mode": "sel_area",
  "rect": { "x1": 40, "y1": 880, "x2": 1240, "y2": 1000 }
}
```

## 6. Poll until terminal

```bash
STATUS=queued
for ((i=0; i<360; i++)); do
  JOB=$(curl --fail-with-body -sS "$API/jobs/$JOB_ID" -H "$AUTH")
  STATUS=$(jq -er .status <<<"$JOB")
  case "$STATUS" in succeeded|failed|canceled) break ;; esac
  sleep 5
done
jq '{id,status,error,currency,amounts}' <<<"$JOB"
[[ "$STATUS" == succeeded ]] || { echo "Retain job ID: $JOB_ID"; exit 1; }
```

## 7. Download the result (link expires in 1 hour)

```bash
curl --fail-with-body -sS -o "clean-$(basename "$VIDEO")" \
  "$(jq -er .result.url <<<"$JOB")"
```

## Error reference

Every non-2xx response is `{ "error": { "code", "message", "request_id" } }`.

| HTTP | `error.code` | Fix |
|---|---|---|
| 401 | `unauthorized` | Key missing/invalid — check `UNMARKAI_API_KEY` |
| 403 | `insufficient_scope` | Recreate the key with jobs:read, jobs:write, balance:read |
| 409 | `idempotency_conflict` | Same Idempotency-Key reused with a different body — use a new key |
| 413 | `request_too_large` | Body over 64 KiB (metadata too big) |
| 422 | `invalid_request` / `invalid_media` | Check body fields; re-check rect vs actual dimensions |
| 429 | `rate_limit_exceeded` | Honor Retry-After; use bounded backoff with jitter |
| 402 | `insufficient_balance` | Top up the API wallet in the dashboard |

## Current contract additions

Read [contract notes](api-contract.md) for regional pricing,
15-second domestic minimum, upload quotas, errors and concurrency. Estimate removal
locally from current balance rates when using REST; there is no REST estimate endpoint.
`sel_area` covers at most half the frame. For REST `multi_area`, use a nonempty
rectangle array as `rect`; billing uses `all_area` rates.

Cancel only during validating/queued:

```bash
curl --fail-with-body -sS -X POST "$API/jobs/$JOB_ID/cancel" -H "$AUTH" \
  -H 'Content-Type: application/json' --data '{}'
```

On 409 `job_not_cancelable`, inspect the current job instead of resubmitting.
Read `currency` and `amounts`; China uses CNY and a separate wallet/key.
Use bounded polling and preserve IDs on timeout. Download signed results without
API Authorization headers; re-query expired links within the 7-day retention.
