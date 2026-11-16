# Model Drift Diagnostic Report: `qwen2.5:3b`

- **Check Timestamp**: 2026-11-16 14:12:44 UTC
- **Baseline Digest**: `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`
- **Current Digest**: `new_altered_sha256_digest_1234567890abcdef`
- **Digest Status**: **DRIFT DETECTED** (Silent re-pull or weight change)
- **Gate Verdict**: **PROMOTE**
- **McNemar p-value**: 1.0000
- **Regressed Tests (b)**: 0
- **Fixed Tests (c)**: 0
- **Delta Pass Rate**: +0.00%

### Action Required
The weights or quant of model `qwen2.5:3b` changed without an artifact version update.
Review regressed test cases and promote only after team approval.
