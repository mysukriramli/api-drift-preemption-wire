# API Drift Preemption Wire

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Autonomous Machine Feed](https://img.shields.io/badge/Feed-Autonomous_6h-blue.svg)](data/today.json)

An autonomous contract-breakage radar engineered for **AI coding agents (Cursor, Devin, Copilot), integration-maintenance bots, and platform engineering pipelines**.

Monitors active OpenAPI specifications from upstream cloud platforms, runs semantic diffs on operations and required parameter signatures, correlates changes against public SDK release cadence (PyPI/npm), and emits deterministic failover directives before production code breaks.

---

## 🎯 Per-Service Dedicated Machine Endpoints (Zero-Auth / Fastly Edge CDN)

Coding agents only fetch the single API they are writing integrations for, minimizing token overhead:

| Target Cloud Service | Dedicated Machine JSON | Single-Service LLM Prompt Hook |
| :--- | :--- | :--- |
| **OpenAI** | [`data/services/openai/today.json`](data/services/openai/today.json) | [`data/services/openai/llms.txt`](data/services/openai/llms.txt) |
| **GitHub** | [`data/services/github/today.json`](data/services/github/today.json) | [`data/services/github/llms.txt`](data/services/github/llms.txt) |
| **Stripe** | [`data/services/stripe/today.json`](data/services/stripe/today.json) | [`data/services/stripe/llms.txt`](data/services/stripe/llms.txt) |
| **Resend** | [`data/services/resend/today.json`](data/services/resend/today.json) | [`data/services/resend/llms.txt`](data/services/resend/llms.txt) |
| **PostHog** | [`data/services/posthog/today.json`](data/services/posthog/today.json) | [`data/services/posthog/llms.txt`](data/services/posthog/llms.txt) |

---

## 📡 Global Machine Endpoints

| Endpoint | Format | Consumer Purpose |
| :--- | :--- | :--- |
| [`data/today.json`](data/today.json) | JSON | Master registry of all tracked cloud services and their drift status. |
| [`data/remediation_queue.jsonl`](data/remediation_queue.jsonl) | JSONL | Streaming queue for CI/CD test generation and automated PR builders. |
| [`data/llms.txt`](data/llms.txt) | Markdown | Global digest for multi-service agent orchestrators. |
| `data/archive/YYYY/MM/` | JSON | Permanent historical records of upstream API breaking-change timelines. |

---

## 🤖 Directives Emitted

- `GENERATE_COMPATIBILITY_SHIM`: Endpoint removed or parameter added; generate local adapter shim.
- `PIN_SDK`: Upstream schema has mutated breaking contracts while official SDK has lagged behind; pin current version.
- `REGENERATE_CLIENT`: Schema updated with matching active SDK release; re-run openapi-generator.
- `ADD_CONTRACT_TEST`: Non-critical schema variance; inject mock contract test into test suite.
- `SAFE_TO_UPGRADE`: Zero breaking changes detected; fully backward-compatible.

---

## 💡 How AI Coding Agents Ingest This in Cursor / Claude Code

Add this rule to your project's `.cursorrules` or system prompt:

```text
Before modifying integrations with OpenAI, Stripe, or GitHub:
1. Fetch [https://raw.githubusercontent.com/mysukriramli/api-drift-preemption-wire/main/data/services/](https://raw.githubusercontent.com/mysukriramli/api-drift-preemption-wire/main/data/services/)<service>/today.json
2. Check the "directive" field.
3. If directive is GENERATE_COMPATIBILITY_SHIM or PIN_SDK, do not use deprecated or newly required properties without appropriate fallbacks.
