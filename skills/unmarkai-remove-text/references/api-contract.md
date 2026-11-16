# Public API contract notes

Verified 2026-11-16 against the [domestic OpenAPI 1.3.0](https://unmarkai.cn/openapi-v1.yaml)
and the [official developer guide](https://unmarkai.cn/developers/docs/), discovered
from the [homepage](https://unmarkai.cn/). The [HD product page](https://unmarkai.cn/features/video-upscale/)
describes website credits; use the developer guide for API billing.

## Regions, authentication and shared lifecycle

| Region | REST base (includes v1) | MCP endpoint |
|---|---|---|
| China / 剪狐 | `https://unmarkai.cn/api/v1` | `https://unmarkai.cn/api/mcp` |
| Overseas | `https://api.unmarkai.net/v1` | `https://api.unmarkai.net/mcp` |

Keys and wallets are independent between regions. Set `UNMARKAI_API_KEY` to an
active `uma_live_*` key; send `Authorization: Bearer ...`. Create/cancel needs
`jobs:write`, queries need `jobs:read`, and balance needs `balance:read`.
Use `currency` and `amounts` (six-decimal strings), especially domestic CNY;
do not label CNY as USD or depend on overseas legacy `_usd` fields.
API wallets are separate from web subscriptions and web credits.

`createApiUpload` (`POST /uploads`) requires `filename`, `content_type`, and
`file_size_bytes`. Maximum is 2147483648 bytes (2 GiB); the guide also describes
HD as “2 GB”. Supported MIME types: `video/mp4`, `video/quicktime`,
`video/x-msvideo`, `video/x-matroska`, `video/webm`, `video/mpeg`.
The shared guide limits videos to 60 minutes. PUT raw bytes once to the returned
`url`, replaying **all** `headers`. Ticket lifetime: 1 hour; unused upload: 24
hours. On 409/412 inspect upload status; never blindly repeat PUT. At most 100
unbound active uploads and 20 GiB unconsumed uploads per rolling 24 hours;
a minimum billable balance is needed before obtaining a ticket.

Alternatively, `createApiUrlUpload` (`POST /url-uploads`) requires `source_url`
and optionally `filename`. Only public direct HTTPS video URLs with stable
Content-Length and supported MIME; signed queries are allowed, pages and
private networks are rejected. Poll `getApiUpload` (`GET /uploads/{upload_id}`)
until `uploaded`; stop on `failed`/`expired`.

Both URL imports and `createApiJob` (`POST /jobs`) require `Idempotency-Key`
(1–255 characters, account-scoped, valid 24 hours). Persist one per business
operation and reuse it with the identical normalized body on retries.
Changed bodies require new keys; conflicts return 409. Job creation returns
202, including replays (`Idempotent-Replayed: true`). URL imports return 202,
or 200 on replay. JSON requests are limited to 64 KiB except translation
creation (512 KiB); metadata is limited to 16 KiB.

`getApiJob` (`GET /jobs/{job_id}`) returns status, progress, costs, error and
result. States: `validating`, `queued`, `processing`, `succeeded`, `failed`,
`canceled`. Use bounded polling (e.g. every 5 seconds); keep the ID on timeout.
MCP `wait_seconds` is not a documented REST query parameter. `listApiJobs`
(`GET /jobs`) supports `status`, `limit` (1–100, default 20), and opaque `after`
from `next_cursor`, ordered by creation time and ID descending.

Successful cleanup and HD return `result.url` and `result.expires_at`. Only use
these temporary signed URLs; no invented download endpoint. Links last at most
1 hour within the 7-day result retention. Re-query the job to refresh an expired
link during retention. Download without forwarding the API Authorization header.
Webhooks report state transitions, not every progress value or signed URLs;
query the job after an event. See the official guide for raw-body signature
verification and event deduplication.

`cancelApiJob` (`POST /jobs/{job_id}/cancel`, body `{}`) cancels cleanup and HD
only in `validating`/`queued`; processing translation can also be canceled.
Already canceled returns the current job. Handle 409 `job_not_cancelable` when
the job advances before cancellation. Server validation precedes reservation;
success settles actual duration, undelivered failure/allowed cancellation releases
reserved money. A client timeout does not cancel a job.

The guide says default execution concurrency is two per account, shared across
keys; read `GET /balance` → `concurrency` for actual `effective_limit`,
`slots_in_use`, `slots_available`. Do not treat schema examples as fixed limits.
For 429 honor `Retry-After` when present and use bounded backoff with jitter;
no universal fixed requests-per-minute rate is promised here.

Errors have `error.code`, `error.message`, `error.request_id`. Relevant codes:
`unauthorized` (401), `insufficient_scope` (403), `insufficient_balance` (402),
`invalid_request` / `invalid_media`, `upload_not_ready`, `file_too_large`,
`unsupported_media_type`, `idempotency_conflict`, `idempotency_in_progress`,
`job_not_cancelable`, `rate_limit_exceeded`, `queue_limit_exceeded`,
`upload_limit_exceeded`, `feature_unavailable`, `service_unavailable`.
Fix auth, parameters or balance before retrying; use bounded retries for temporary
5xx and 429. Preserve request IDs for support without disclosing keys or signed URLs.

## Video HD / enhancement / super-resolution

The sole official task string is **`video_upscale`**, documented for **China**.
Do not infer overseas availability from the shared server list.
Required creation fields: `type`, `input.upload_id`, `upscale.target`.
`upscale.target` accepts exactly `1080p`, `2k`, `4k`; optional `metadata` is an
object. No client `fps`, multiplier, model, strength or scale parameter exists.

Input long/short edges must not exceed the selected target: 1920×1080,
2560×1440, 3840×2160 respectively. Portrait and same-resolution enhancement
are supported; preserve aspect ratio, frame rate and audio, with no platform
watermark on API output. Stereo conversion is recommended for multichannel audio.
Output is the enhanced video through `result.url`; no separate SRT is promised.
Response `upscale` contains `target`, server-probed `fps` and `multiplier` (1 or 2).

Standard API prices: CNY 0.04 / 0.08 / 0.12 per second for 1080p / 2k / 4k.
Billable seconds = `max(15, ceil(actual_seconds))`. Average FPS **greater than**
30 doubles the rate (29.97 does not, 59.94 does), then account recharge discount
applies. The guide's 10/20/30 credit ratio is explanatory; this API charges its
CNY wallet, not website credits, 30-second blocks or a 1-second buffer.

There is **no REST estimate endpoint** in this OpenAPI and no documented native
HD MCP tool. Read `getApiBalance` (`GET /balance`) → `amounts.upscale_rates` for
account-discounted ≤30 FPS rates, then locally estimate using duration and FPS.
The guide does not specify the nested rate keys: inspect the actual response;
do not invent them. Display currency, calculation and uncertainty before spending.
For example 30s at 4k/60 FPS: CNY 7.20 standard or CNY 5.76 at 20% discount.
Final costs use server measurements and job `currency` / `amounts`.
Cancel, result, reservation, retention and shared upload limits are as above.

**Translation `output_resolution` is not enhancement**: it belongs to
`video_translation`, accepts `source` / `720p` / `1080p`, caps output while
preserving aspect ratio, and does not forcibly upscale low-resolution sources.
Translation is a separate REST job with separate billing and result assets.

## Text removal updates

`remove_text` modes are `all_area`, `sel_area`, `multi_area`. `sel_area` takes
one source-pixel rectangle covering at most half the frame. `multi_area` takes a
nonempty array of in-frame rectangles at the `all_area` rate. `all_area` omits
`rect` or uses null. Domestic standard rates are CNY 0.020/s single-region and
0.040/s full/multiple regions, rounded up with a **15-second minimum**. Read
current account prices from balance; overseas pricing must use that region's
response rather than domestic rates. MCP `estimate_cost` is documented for
cleanup, not HD or translation. Published tools remain `create_upload`,
`create_url_upload`, `get_upload`, `remove_text`, `get_job`, `list_jobs`,
`cancel_job`, `get_balance`, `estimate_cost`; use REST for HD and translation.
