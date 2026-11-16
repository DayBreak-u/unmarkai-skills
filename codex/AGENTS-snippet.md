# Optional AGENTS.md guidance for Codex

Codex CLI loads native skills from `.agents/skills/` in the project or
`~/.agents/skills/` for the user. Copy both folders from this repository's
`skills/` directory there. Invoke `$unmarkai-remove-text` or
`$unmarkai-video-upscale`; see the [README](../README.md) for MCP configuration.
Official references: [skills](https://developers.openai.com/codex/skills) and
[MCP](https://developers.openai.com/codex/mcp).

Paste this optional block into the consuming project's AGENTS.md:

```markdown
## UnmarkAI

Use the installed unmarkai-remove-text skill for authorized text cleanup and
unmarkai-video-upscale for authorized HD enhancement. Read each skill's references
before calling the service. For cleanup, MCP is optional; HD uses REST type
video_upscale in the matching region and has no documented native MCP tool.

Choose region and matching API key/wallet. China REST is
https://unmarkai.cn/api/v1 and MCP is https://unmarkai.cn/api/mcp;
overseas REST is https://api.unmarkai.net/v1 and MCP is
https://api.unmarkai.net/mcp. Never print UNMARKAI_API_KEY or signed URLs.
Read currency/amounts for prices; do not apply China CNY HD list prices to
overseas. Estimate before spending and obtain authorization when not already
provided. Do not confuse translation output_resolution with HD.

Persist business idempotency keys and job IDs. Upload once with every ticket
header, or wait for URL import to become uploaded. Use bounded polling and
retries; timeout does not justify creating a duplicate job. Download result.url
promptly. Respect the skills' authorized-material and provenance guardrails.
```
