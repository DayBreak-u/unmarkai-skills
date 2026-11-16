# unmarkai-skills

[English](README.md) | 简体中文

为剪狐 / UnmarkAI API 提供 Agent Skills 和远程 MCP 接入指南，帮助 Claude、Codex、Cursor 等客户端处理**自己拥有或已获授权的视频**：去除硬字幕、画面文字，或通过对应地区的 REST API 将视频增强至 1080p、2K、4K。

本仓库不提供独立处理引擎。文字擦除可使用远程 MCP 或 REST；视频高清使用正式任务类型 `video_upscale`，海外与中国区 REST 均已在公开契约中提供，没有对应的原生 MCP 工具。

## 选择地区并准备密钥

| 地区 | REST 基地址（已含版本号） | MCP 地址 |
|---|---|---|
| 中国区（剪狐） | `https://unmarkai.cn/api/v1` | `https://unmarkai.cn/api/mcp` |
| 海外区 | `https://api.unmarkai.net/v1` | `https://api.unmarkai.net/mcp` |

1. 打开[中国区 API 控制台](https://unmarkai.cn/developers/)。海外用户从 [UnmarkAI](https://unmarkai.net) 的 Dashboard → API 进入。
2. 创建 API 密钥，赋予 `jobs:read`、`jobs:write`、`balance:read` 权限。
3. 在所选地区为 API 钱包充值。两区密钥和钱包独立，网页会员及积分不等于 API 余额。
4. 在运行客户端的环境中设置密钥：

```bash
export UNMARKAI_API_KEY='uma_live_REPLACE_WITH_YOUR_KEY'
```

不要把真实密钥写进仓库、网页前端、日志或聊天记录。所有业务 API 请求使用 `Authorization: Bearer ...`。中国区金额读取 `currency=CNY` 和 `amounts`，不能按旧的 USD 字段展示人民币。

## 安装和使用 Skills

本仓库的两个技能分别是：

- [unmarkai-remove-text](skills/unmarkai-remove-text/SKILL.md)：文字擦除，包含选区、上传、估价、查询和下载指引。
- [unmarkai-video-upscale](skills/unmarkai-video-upscale/SKILL.md)：视频高清，通过所选地区的 REST 创建任务。

在本仓库根目录执行复制命令；若安装到其他项目，请将目标目录改为该项目路径。

### Codex CLI

Codex CLI 支持原生技能。安装到项目的 `.agents/skills/`，也可改为用户级的 `~/.agents/skills/`：

```bash
mkdir -p .agents/skills
cp -R skills/unmarkai-remove-text skills/unmarkai-video-upscale .agents/skills/
```

在提示中使用 `$unmarkai-remove-text` 或 `$unmarkai-video-upscale`，也可由 Codex 根据任务选择技能。可选的项目约束见 [AGENTS.md 片段](codex/AGENTS-snippet.md)。技能支持以 [Codex 官方文档](https://developers.openai.com/codex/skills)为准。

文字擦除若使用 MCP，在 `~/.codex/config.toml` 添加：

```toml
[mcp_servers.unmarkai]
url = "https://unmarkai.cn/api/mcp"
bearer_token_env_var = "UNMARKAI_API_KEY"
```

无需旧的实验性 RMCP 开关；配置参考 [Codex MCP 文档](https://developers.openai.com/codex/mcp)。即使连接了 MCP，高清技能也走 REST。

### Claude Code

```bash
claude mcp add --transport http unmarkai https://unmarkai.cn/api/mcp \
  --header "Authorization: Bearer $UNMARKAI_API_KEY"
mkdir -p ~/.claude/skills
cp -R skills/unmarkai-remove-text skills/unmarkai-video-upscale ~/.claude/skills/
```

### 其他客户端

Cursor 可在 `~/.cursor/mcp.json` 使用以下连接配置。占位值需要通过客户端支持的安全方式提供；不要提交真实密钥。

```json
{
  "mcpServers": {
    "unmarkai": {
      "type": "http",
      "url": "https://unmarkai.cn/api/mcp",
      "headers": {"Authorization": "Bearer uma_live_REPLACE_WITH_YOUR_KEY"}
    }
  }
}
```

Windsurf、Gemini CLI、opencode 和采用 `mcp-remote` 桥接的 Claude Desktop 配置见[英文 README](README.md)。其中海外地址需要连同密钥一起切换为中国区配置。客户端配置字段随版本变化，不支持远程 MCP 时直接使用 REST。

官方列出的 MCP 工具为 `create_upload`、`create_url_upload`、`get_upload`、`remove_text`、`get_job`、`list_jobs`、`cancel_job`、`get_balance`、`estimate_cost`。它们覆盖擦除流程；不要虚构高清或翻译工具，也不要把擦除的 `estimate_cost` 当作高清估价接口。

## 去除硬字幕或画面文字

例如向 Agent 提出：

> 请处理我自己的 draft.mp4，去除底部硬字幕。先估价，选择能覆盖字幕的合适选区，再将结果下载到原文件旁边。

流程为：ffprobe 探测尺寸及时间 → 查询价格 / 估价 → 获得花费授权 → 上传或导入直链 → 创建 `remove_text` → 查询状态 → 下载 `result.url`。

| 模式 | rect 参数 | 计费 |
|---|---|---|
| `all_area` | 省略或 null | 全画面费率 |
| `sel_area` | 单个源视频像素矩形，面积不超过画面一半 | 单框费率 |
| `multi_area` | 非空矩形数组，每框均在源画面内 | 全画面费率；使用 REST，MCP 需先核对工具 schema |

坐标使用原始视频像素，满足 `0 ≤ x1 < x2 ≤ width`、`0 ≤ y1 < y2 ≤ height`，建议文字周围留 8–16 像素。中国区标准单框价 ¥0.020/秒，全画面 / 多框 ¥0.040/秒，向上取整，最低计费 15 秒，再应用账户折扣。实际使用当前余额和估价响应中的价格，不要跨区套用费率。

完整命令见[擦除 REST / curl 流程](skills/unmarkai-remove-text/references/curl-fallback.md)，坐标说明见[选区参考](skills/unmarkai-remove-text/references/rect-and-dimensions.md)。

## 视频高清 / 画质增强 / 超分辨率

例如：

> 把我自己的 source.mp4 增强到 4K。先按当前地区 API 钱包币种估价，保留帧率和音轨，确认费用后提交并下载结果。

向所选地区的 `POST /jobs` 提交（海外完整地址 `https://api.unmarkai.net/v1/jobs`，中国区 `https://unmarkai.cn/api/v1/jobs`）：

```json
{
  "type": "video_upscale",
  "input": {"upload_id": "upl_REPLACE"},
  "upscale": {"target": "4k"},
  "metadata": {"order_id": "your_order"}
}
```

必填 `type`、`input.upload_id`、`upscale.target`，`metadata` 可选且不超过 16 KiB。`target` 仅接受 `1080p`、`2k`、`4k`。不要提交 FPS、倍率、模型或增强强度等契约未提供的参数。服务端返回的 `upscale.fps`、`upscale.multiplier` 是探测结果。

| target | 源视频长边 / 短边上限 | 中国区标准价（≤30 FPS） |
|---|---|---|
| `1080p` | 1920 / 1080 | ¥0.04/秒 |
| `2k` | 2560 / 1440 | ¥0.08/秒 |
| `4k` | 3840 / 2160 | ¥0.12/秒 |

支持竖屏和同分辨率增强，保留比例、帧率和音轨，API 成片不加平台水印。单视频最多 60 分钟；上传契约精确限制为 2147483648 字节（2 GiB），高清指南简写为 2 GB。支持 MP4、MOV、AVI、MKV、WebM、MPEG；多声道音频建议先转为立体声。

中国区计费秒数为 `max(15, ceil(实际秒数))`。平均帧率**大于** 30 FPS 时费率翻倍，再应用账户折扣；29.97 不翻倍，59.94 翻倍。30 秒 4K / 60 FPS 的中国区标准费用是 ¥7.20，八折后 ¥5.76。不能套用网页的每 30 秒积分档位或 1 秒缓冲规则。

海外区不要套用上述人民币单价。海外 OpenAPI 1.4.0 写明使用 USD 钱包：以当前 `all_area` 基础费率 × 1/2/3（对应 1080p/2k/4k），平均帧率大于 30 再 ×2，然后再套账户折扣；同样最低 15 秒，并按源时长向上取整到整秒。契约没有公布固定的海外美元标价，必须读取 `GET /balance` 的 `amounts.upscale_rates`（以及响应里如有的 `upscale_rates`）。

没有公开的 REST 高清估价端点。先用余额接口读取已含折扣的 ≤30 FPS 秒价，再结合本地探测的时间及 FPS 估算。未固定的嵌套键名应检查实际返回值，不能自行编造。最终费用以服务端探测和任务的 `currency` / `amounts` 为准。

完整可执行步骤见[高清 curl 流程](skills/unmarkai-video-upscale/references/curl-fallback.md)：本地探测 → 余额与估价 → 上传或 HTTPS 导入 → 创建 → 有截止时间的轮询 → 下载。高清在两区都走 REST，公开文档没有原生 MCP 工具。海外 OpenAPI 的取消说明没有点名 `video_upscale`，不要自行假定可取消窗口。

翻译任务 `video_translation` 的 `output_resolution` 是另一个功能，只接受 `source`、`720p`、`1080p`，用于限制翻译视频的输出尺寸，不强行放大低分辨率素材，**不能替代视频高清服务**。翻译和擦除也分别创建、分别计费。

## 上传、幂等、取消和下载

- 本地文件先 `POST /uploads`，再向返回的签名 URL PUT 原始字节，原样携带全部 `headers`，不要附加 API 鉴权。凭证 1 小时有效且只可写一次；409/412 时先查上传状态。
- 直链使用 `POST /url-uploads`，仅支持可直接下载的公网 HTTPS 视频，需稳定 Content-Length 和支持的 MIME，可带签名参数。网页、平台分享页及内网地址不适用。`GET /uploads/{upload_id}` 到 `uploaded` 后才能创建任务。
- 创建任务和导入直链都必须提供 `Idempotency-Key`（1–255 字符，账号内有效 24 小时）。每个业务操作保存一个键，重试时复用原键和相同请求体；改变参数时使用新键。
- 上传未绑定任务时有效 24 小时，最多 100 个有效未绑定上传，滚动 24 小时未消费上传量最多 20 GiB；申请凭证前需有最低计费余额。
- `GET /jobs/{job_id}` 查询状态，建议每 5 秒一次并设置截止时间。超时保留任务 ID，不要重新提交。默认并发为账号共享的两个执行任务，实际读取余额响应 `concurrency`。
- 取消使用 `POST /jobs/{job_id}/cancel`。中国区指南写明擦除和高清仅能在 `validating` / `queued` 取消；海外 OpenAPI 1.4.0 的取消说明只写了擦除和翻译，没有点名高清，不要套用中国区规则去猜海外可取消阶段。状态变化可能返回 409 `job_not_cancelable`。未交付失败或允许的取消释放冻结费用，成功后结算。
- 成功后从 `result.url` 下载，链接最长 1 小时，文件保留 7 天。保留期内链接过期可重新查询任务。下载时不要向资源服务器转发 API 密钥。

## 错误与安全

错误结构为 `error.code`、`error.message`、`error.request_id`。401/403 检查密钥及权限；402 检查余额；400/422 修正参数；409 检查幂等冲突或取消阶段；429 遵循 Retry-After 并退避。临时 5xx 使用有上限的重试，不要无条件循环。任务失败需检查 `error`，查询超时不等于失败。

密钥可支出钱包余额，泄漏后应立即撤销并轮换。不要记录签名 URL 或把临时响应加入版本库。只处理拥有或获准修改的素材；擦除技能拒绝针对署名、归属信息、来源标识、AI 内容披露或法律声明的请求。

## 文档来源与离线验证

2026-11-16 核对的权威来源：[海外 OpenAPI 1.4.0](https://unmarkai.net/openapi-v1.yaml)、[国内 OpenAPI 1.3.0](https://unmarkai.cn/openapi-v1.yaml)、[中国区 API 指南](https://unmarkai.cn/developers/docs/)。`https://unmarkai.net/developers/docs/` 现为 404，不能用来判断海外是否支持。海外站点上的高清产品页是网站积分说明，与 API 计费分开。字段、错误、限制和计费细节集中在[契约参考](skills/unmarkai-remove-text/references/api-contract.md)。

测试依赖 Python 3、PyYAML、jsonschema，运行 `python3 -m unittest discover -s tests -v`。仅解析小型契约快照、验证请求体、检查本地链接和 Bash 语法，不会上传或调用付费任务。

相关只读示例：[文字擦除 API](https://github.com/DayBreak-u/unmarkai-video-text-removal-api)、[视频翻译 API](https://github.com/DayBreak-u/unmarkai-video-translation-api)。

## 许可证

[MIT](LICENSE) © DayBreak-u
