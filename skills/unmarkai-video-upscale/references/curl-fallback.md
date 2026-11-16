# Video HD REST workflow

These commands create a billable job when run with real inputs. Only use authorized
material and confirm the estimate before submission. This repository's tests do
not execute requests. Requires Bash, curl with `--fail-with-body`, jq and ffprobe.
See [contract notes](../../unmarkai-remove-text/references/api-contract.md) for authoritative sources and regional billing.

## Prepare and estimate locally

```bash
set -euo pipefail
: "${UNMARKAI_API_KEY:?set the API key for the chosen region}"
# Overseas: API='https://api.unmarkai.net/v1'
# China:    API='https://unmarkai.cn/api/v1'
API='https://api.unmarkai.net/v1'
VIDEO='source.mp4'
TARGET='4k'  # exactly 1080p, 2k or 4k
AUTH="Authorization: Bearer $UNMARKAI_API_KEY"
ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height,avg_frame_rate:stream_side_data=rotation:format=duration \
  -of json "$VIDEO"
curl --fail-with-body -sS "$API/balance" -H "$AUTH" \
  | jq '{currency,amounts,concurrency}'
```

Check both source edges against the target and read `amounts.upscale_rates`.
The docs do not fix its nested keys, so inspect the returned rates. Compute
`max(15, ceil(duration_seconds)) × discounted_target_rate × (FPS > 30 ? 2 : 1)`.
No REST estimate endpoint or HD MCP estimate tool is documented. China standard
30s, 4k, 60 FPS costs CNY 7.20 before discount. Overseas OpenAPI 1.4.0 uses the
USD `all_area` base × 1/2/3, then the FPS multiplier and discount; do not copy
CNY list prices or website credit blocks.

## Upload local bytes

```bash
SIZE=$(wc -c < "$VIDEO" | tr -d ' ')
TICKET=$(curl --fail-with-body -sS "$API/uploads" -H "$AUTH" \
  -H 'Content-Type: application/json' \
  --data "$(jq -n --arg filename "$(basename "$VIDEO")" --argjson size "$SIZE" \
    '{filename:$filename,content_type:"video/mp4",file_size_bytes:$size}')")
UPLOAD_ID=$(jq -er .upload_id <<<"$TICKET")
UPLOAD_HEADERS=()
while IFS= read -r header; do UPLOAD_HEADERS+=(-H "$header"); done \
  < <(jq -r '.headers | to_entries[] | "\(.key): \(.value)"' <<<"$TICKET")
curl --fail-with-body -sS -X PUT "$(jq -er .url <<<"$TICKET")" \
  "${UPLOAD_HEADERS[@]}" --data-binary "@$VIDEO"
```

Use the correct MIME for non-MP4 files. PUT exactly once; on 409/412 query the
upload and obtain a fresh ticket if necessary. Never send API auth to the PUT URL.

Alternatively skip the ticket/PUT and import a direct public HTTPS video:

```bash
SOURCE_URL='https://cdn.example.com/source.mp4'
IMPORT_KEY='replace-with-persisted-unique-import-id'
UPLOAD=$(curl --fail-with-body -sS "$API/url-uploads" -H "$AUTH" \
  -H 'Content-Type: application/json' -H "Idempotency-Key: $IMPORT_KEY" \
  --data "$(jq -n --arg url "$SOURCE_URL" '{source_url:$url}')")
UPLOAD_ID=$(jq -er .upload_id <<<"$UPLOAD")
```

For either path, verify readiness. The loop has a deadline; timeout preserves
`UPLOAD_ID` so the caller can query later instead of importing again.

```bash
READY=false
for ((i=0; i<360; i++)); do
  UPLOAD=$(curl --fail-with-body -sS "$API/uploads/$UPLOAD_ID" -H "$AUTH")
  case "$(jq -er .status <<<"$UPLOAD")" in
    uploaded) READY=true; break ;;
    failed|expired) jq '{status,error}' <<<"$UPLOAD"; exit 1 ;;
  esac
  sleep 5
done
[[ "$READY" == true ]] || { echo "Upload pending: $UPLOAD_ID"; exit 1; }
```

## Create, query and download

Save a new business key once; reuse the same key and body on retry, including
a lost response. Do not generate a fresh key on every retry.

```bash
REQUEST_KEY='replace-with-persisted-unique-hd-request-id'
JOB=$(curl --fail-with-body -sS "$API/jobs" -H "$AUTH" \
  -H 'Content-Type: application/json' -H "Idempotency-Key: $REQUEST_KEY" \
  --data "$(jq -n --arg id "$UPLOAD_ID" --arg target "$TARGET" \
    '{type:"video_upscale",input:{upload_id:$id},upscale:{target:$target}}')")
JOB_ID=$(jq -er .id <<<"$JOB")
echo "Save job ID: $JOB_ID"
for ((i=0; i<360; i++)); do
  JOB=$(curl --fail-with-body -sS "$API/jobs/$JOB_ID" -H "$AUTH")
  case "$(jq -er .status <<<"$JOB")" in
    succeeded)
      curl --fail-with-body -sS "$(jq -er .result.url <<<"$JOB")" -o enhanced.mp4
      jq '{id,status,upscale,currency,amounts}' <<<"$JOB"
      break ;;
    failed|canceled) jq '{id,status,error}' <<<"$JOB"; exit 1 ;;
  esac
  sleep 5
done
# If still pending, keep JOB_ID and query later; do not recreate the job.
```

Response `upscale.fps` and `upscale.multiplier` are server-derived, not request
parameters. Refresh an expired result link with GET during the 7-day retention.
To request cancel (a separate optional action). The China guide allows this
while validating/queued; overseas OpenAPI 1.4.0 does not name `video_upscale`
in the cancel description:

```bash
curl --fail-with-body -sS -X POST "$API/jobs/$JOB_ID/cancel" -H "$AUTH" \
  -H 'Content-Type: application/json' --data '{}'
```

A state race may return 409 `job_not_cancelable`. Do not assume an overseas HD
job can be canceled in a particular state. Do not blindly retry
auth/validation/balance errors. On 429 honor Retry-After and use bounded
backoff; preserve IDs and keys on transient failures.
