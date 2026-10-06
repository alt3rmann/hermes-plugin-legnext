# Legnext for Hermes

Four tools: `mj_balance` (free), `mj_imagine` (one paid diffusion submission), `mj_job` (resume/poll/download), and `mj_action` (paid upscale/variation/reroll). The Legnext API is unofficial. Submit requires `LEGNEXT_API_KEY` in the active Hermes profile's `.env`; job lookups require only the private UUID (treat it as a capability token).

Configure optional settings under `plugins.entries.legnext.settings`: `output_dir` (default `<HERMES_HOME>/legnext-output`), `poll_interval` (default 5 seconds), `default_timeout` (600 seconds), and `default_version` (default `8.2`; when set empty the Legnext API falls back to v7, not the newest version). An explicit `--v`/`--niji` in the prompt wins over the `version` argument, which wins over this setting. Use Hermes config commands, not manual config.yaml edits.

For images, use prompt-native Midjourney flags such as `--v 8.2 --ar 16:9`; there are no JSON `model`, `mode`, or `aspectRatio` fields. A submit response is not a finished image. Completed delivery URLs expire, so the plugin immediately downloads completed files into durable local storage. A timeout does not cancel a server task: resume the same `job_id` via `mj_job`, never resubmit just because waiting timed out. Paid POST calls are deliberately not retried after ambiguous network failures.

Legnext's pricing varies by model and parameters; the tool descriptions provide only indicative prices. Check balance first. JSON error results include actionable HTTP status guidance, while API keys are never returned.
