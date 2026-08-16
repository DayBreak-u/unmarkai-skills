# curl fallback — the full remove-text flow without MCP

Use this when the `unmarkai` MCP server is not connected. Everything is plain
`curl` + `jq` against the UnmarkAI REST API v1. Requires `UNMARKAI_API_KEY`
(an active `uma_live_*` key from the UnmarkAI dashboard).

Only process videos you own or have explicit permission to modify.

## 0. Environment

```bash
: "${UNMARKAI_API_KEY:?set UNMARKAI_API_KEY to your uma_live_* key}"
API="https://api.unmarkai.net/v1"
AUTH="Authorization: Bearer $UNMARKAI_API_KEY"
```

## 1. Probe the video

```bash
VIDEO="my-video.mp4"

ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height -show_entries format=duration \
  -of json "$VIDEO"

SIZE=$(stat -f%z "$VIDEO")   # macOS; on Linux: stat -c%s "$VIDEO"
```

## 2. (Optional) Check the wallet

```bash
curl -sS "$API/balance" -H "$AUTH" | jq .
```

## 3. Create an upload ticket

```bash
TICKET=$(curl -sS -X POST "$API/uploads" \
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
curl -sS -X PUT "$PUT_URL" \
  -H 'content-type: video/mp4' \
  -H 'content-length: '"$SIZE" \
  -H 'if-none-match: *' \
  --data-binary "@$VIDEO" -o /dev/null -w '%{http_code}\n'
```

A `200`/`201` means the upload landed. A `412` means the one-shot ticket was
already used — do NOT PUT again; go back to step 3 for a fresh ticket.

## 5. Create the job

```bash
# Unique per (file, settings) so retries never double-bill.
IDEMPOTENCY="rt-$(shasum "$VIDEO" | cut -c1-16)"

JOB=$(curl -sS -X POST "$API/jobs" \
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
  "input": { "upload_id": "upl_..." },
  "mode": "sel_area",
  "rect": { "x1": 40, "y1": 880, "x2": 1240, "y2": 1000 }
}
```

## 6. Poll until terminal

```bash
until STATUS=$(curl -sS "$API/jobs/$JOB_ID" -H "$AUTH" | tee /tmp/job.json | jq -r .status) \
  && [[ "$STATUS" == succeeded || "$STATUS" == failed || "$STATUS" == canceled ]]; do
  echo "status: $STATUS"; sleep 5
done
cat /tmp/job.json | jq .
```

## 7. Download the result (link expires in 1 hour)

```bash
curl -sS -o "clean-$(basename "$VIDEO")" \
  "$(jq -r .result.url /tmp/job.json)"
```

## Error reference

Every non-2xx response is `{ "error": { "code", "message", "request_id" } }`.

| HTTP | `error.code` | Fix |
|---|---|---|
| 401 | `unauthorized` | Key missing/invalid — check `UNMARKAI_API_KEY` |
| 403 | `insufficient_scope` | Recreate the key with jobs:read, jobs:write, balance:read |
| 409 | `idempotency_conflict` | Same Idempotency-Key reused with a different body — use a new key |
| 413 | `request_too_large` | Body over 64 KiB (metadata too big) |
| 422 | `invalid_request` / `INVALID_RECT` | Check body fields; re-check rect vs actual dimensions |
| 429 | `rate_limit_exceeded` | Back off ~5s and retry (write 50/min, read 120/min) |
| 402 | `insufficient_balance` | Top up the API wallet in the dashboard |
