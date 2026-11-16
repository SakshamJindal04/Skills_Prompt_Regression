# ADR-004: Local-First Air-Gapped Architectural Boundary

- **Status:** Accepted
- **Date:** 2026-11-16
- **Context:** Establishing the operational boundary and cloud dependency policy for prompt evaluation and agent runtime.

## Context

Enterprises working with proprietary analytics schemas, internal code repositories, and sensitive operational databases cannot send prompts, queries, and execution traces to third-party hosted APIs (e.g., OpenAI, Anthropic) due to data exfiltration risks, regulatory compliance (GDPR, EU AI Act, HIPAA), and subscription cost unpredictability.

Furthermore, remote API evaluation introduces network latency, rate limits, and uncontrollable provider-side model updates that destroy regression reproducibility.

## Decision

We mandate a strictly **Local-First, Air-Gapped Architecture**:
1. All language model inference runs on the local workstation or private host via local Ollama (`http://localhost:11434`), supporting local open-weights models (`qwen2.5:3b`, `llama3.2:3b`, `gemma2:2b`).
2. Zero external cloud APIs, telemetry pings, remote font CDNs, or external network requests are permitted at runtime.
3. Persistence is backed exclusively by local MySQL (Docker or native) or local SQLite (`regression_manager.db`).
4. Dashboard and API bind strictly to localhost (`127.0.0.1`), with CORS origin confinement.
5. All fonts and icons use local system stacks and bundled Material icons (`:material/...`).

## Consequences & Empirical Evidence

- **Data Privacy & Exfiltration Immunity**: As documented in `docs/THREAT_MODEL.md` and `docs/SECURITY_SCAN.md`, sensitive SQL schemas and customer data never leave the local memory space.
- **Cost Predictability**: As measured in `results/cost.md`, operational cost per gate evaluation is **$0.0000** in API fees, consuming only ~27 seconds of local CPU/GPU compute.
- **Portability**: Verified that the entire regression pipeline functions completely offline with network adapters disabled.
