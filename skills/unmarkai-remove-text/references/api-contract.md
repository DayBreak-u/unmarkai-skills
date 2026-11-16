# Public API contract notes

Verified 2026-11-16 against these public sources:

- Overseas OpenAPI 1.4.0: [https://unmarkai.net/openapi-v1.yaml](https://unmarkai.net/openapi-v1.yaml). Official example READMEs also treat this file as the overseas contract source of truth.
- China OpenAPI 1.3.0: [https://unmarkai.cn/openapi-v1.yaml](https://unmarkai.cn/openapi-v1.yaml) and the [China developer guide](https://unmarkai.cn/developers/docs/), discovered from [unmarkai.cn](https://unmarkai.cn/).
- The older path `https://unmarkai.net/developers/docs/` returns 404 and is not a source. The overseas homepage points to [API product pages](https://unmarkai.net/video-text-removal-api/), [translation API](https://unmarkai.net/video-translation-api/), and [Dashboard → API Documentation](https://unmarkai.net/dashboard/api/docs). The dashboard docs URL is a login/SPA shell when fetched unauthenticated; billing and fields below come from the public OpenAPI, not from a logged-in console.
- Website HD pages such as [unmarkai.net/video-upscaler](https://unmarkai.net/video-upscaler/) and [unmarkai.cn/features/video-upscale](https://unmarkai.cn/features/video-upscale/) describe website credits; they are not API prices.

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

`cancelApiJob` (`POST /jobs/{job_id}/cancel`, body `{}`) is the documented
cancel endpoint. Already canceled returns the current job. Handle 409
`job_not_cancelable` when the job advances before cancellation. Server
validation precedes reservation; success settles actual duration, undelivered
failure or an allowed cancellation releases reserved money. A client timeout
does not cancel a job.

The China developer guide documents cleanup and HD cancel only in
`validating`/`queued`; processing translation can also be canceled. The
overseas OpenAPI 1.4.0 `cancelApiJob` text names Remove Text (`validating` /
`queued`) and translation (also `processing`) but does **not** name
`video_upscale`. Do not assume an overseas HD cancel window from the China
guide or from cleanup/translation rules.

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

The official task string is **`video_upscale`**. It is available on both
regional REST APIs:

- Overseas: confirmed by [OpenAPI 1.4.0](https://unmarkai.net/openapi-v1.yaml). The
  document describes a public video-HD API, `JobCreateRequest` / `Job` include
  this type, and `VideoUpscaleCreateRequest` specifies the International API.
  Use `https://api.unmarkai.net/v1`.
- China: confirmed by [OpenAPI 1.3.0](https://unmarkai.cn/openapi-v1.yaml)
  (`VideoUpscaleCreateRequest` is labeled 中国区视频高清) and the
  [China developer guide](https://unmarkai.cn/developers/docs/). Use
  `https://unmarkai.cn/api/v1`.

There is no documented native HD MCP tool in the public overseas or China
materials; do not invent an `upscale` MCP tool. Official example repositories
document MCP for text cleanup only.

Required creation fields: `type`, `input.upload_id`, `upscale.target`.
`upscale.target` accepts exactly `1080p`, `2k`, `4k`; optional `metadata` is an
object. No client `fps`, multiplier, model, strength or scale parameter exists.

Input long/short edges must not exceed the selected target: 1920×1080,
2560×1440, 3840×2160 respectively. Portrait and same-resolution enhancement
are supported; preserve aspect ratio, frame rate and audio, with no platform
watermark on API output. Stereo conversion is recommended for multichannel audio.
Output is the enhanced video through `result.url`; no separate SRT is promised.
Response `upscale` contains `target`, server-probed `fps` and `multiplier` (1 or 2).
Shared upload limits still apply: up to 2147483648 bytes (2 GiB) and 60 minutes.
The International API returns 202 before media validation; invalid media becomes
a failed job.

### China billing

Standard API prices in the China OpenAPI / developer guide: CNY 0.04 / 0.08 /
0.12 per second for 1080p / 2k / 4k. Billable seconds =
`max(15, ceil(actual_seconds))`. Average FPS **greater than** 30 doubles the
rate (29.97 does not, 59.94 does), then the account recharge discount applies.
The website 10/20/30 credit ratio is not API billing; China API charges the CNY
wallet, not website credits, 30-second blocks or a 1-second buffer. For example,
30s at 4k/60 FPS is CNY 7.20 standard or CNY 5.76 at 20% discount.

### Overseas billing

Do **not** apply China CNY 0.04 / 0.08 / 0.12 to overseas. The International
API uses the regional USD wallet and does not use website credits. OpenAPI 1.4.0
says USD rates use the active `all_area` base rate times 1/2/3 for 1080p / 2k /
4k, then a 2× multiplier above 30 FPS, then the account discount. Minimum 15
seconds, rounded up to whole source seconds. The contract does not publish a
fixed overseas dollar list price; read `getApiBalance` (`GET /balance`) →
`amounts.upscale_rates` (and `upscale_rates` when present) for
account-discounted ≤30 FPS rates. `upscale_rates` is not a required
`PublicBalance` field. Inspect the actual response keys; do not invent them.
Display currency, calculation and uncertainty before spending. Final costs use
server measurements and the job `currency` / `amounts`.

Trial watermark policy “follows the international API account”; the public
contract does not define further API trial details. Do not treat the website
upscaler’s 4-second watermarked trial as an API rule.

There is **no REST estimate endpoint** in these OpenAPI documents. Locally
estimate from duration, FPS and the regional balance rates, then obtain spend
authorization. Result, reservation, retention and shared upload limits are as
above. For cancel, see the regional notes in the lifecycle section; do not
guess an overseas HD cancel window.

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
