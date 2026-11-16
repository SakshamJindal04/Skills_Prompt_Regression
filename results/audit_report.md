# Regression Manager System Audit Trail Report

Generated at: 2026-11-10 10:48:45 UTC
Total recorded events: 50

## Audit Log Summary Table

| ID | Timestamp (UTC) | Action | Actor | Commits (Base -> Cand) | Verdict | p-value | (b, c) | Approver |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 50 | 2026-11-10T10:45:33 | `gate_evaluated_promote` | gate_evaluator | `1` -> `4` | PROMOTE | 1.0000 | (0, 0) | - |
| 49 | 2026-11-10T10:45:27 | `reject_change_request` | Bob Lead | `sha_bas` -> `sha_can` | REJECTED | - | (0, 0) | Bob Lead |
| 48 | 2026-11-10T10:45:27 | `submit_change_request` | Eve Engineer | `sha_bas` -> `sha_can` | - | - | (0, 0) | - |
| 47 | 2026-11-10T10:45:27 | `approve_and_promote` | Alice Reviewer | `sha_bas` -> `sha_can` | PROMOTED | - | (0, 0) | Alice Reviewer |
| 46 | 2026-11-10T10:45:27 | `submit_change_request` | Dan Developer | `sha_bas` -> `sha_can` | - | - | (0, 0) | - |
| 45 | 2026-11-10T10:45:27 | `test_audit_event` | security_tester | - | - | - | (0, 0) | - |
| 44 | 2026-11-10T10:45:27 | `gate_evaluated_promote` | gate_evaluator | - | PROMOTE | 0.1250 | (0, 4) | - |
| 43 | 2026-11-10T10:45:27 | `gate_evaluated_block` | gate_evaluator | - | BLOCK | 0.2188 | (1, 5) | - |
| 42 | 2026-11-10T10:45:27 | `gate_evaluated_block` | gate_evaluator | - | BLOCK | 0.0352 | (12, 3) | - |
| 41 | 2026-11-10T10:45:27 | `gate_evaluated_promote` | gate_evaluator | - | PROMOTE | 0.0352 | (3, 12) | - |
| 40 | 2026-11-10T10:45:00 | `reject_change_request` | Carol Admin | `08e43ee` -> `c3_mode` | REJECTED | - | (0, 0) | Carol Admin |
| 39 | 2026-11-10T10:45:00 | `submit_change_request` | Carol Admin | `08e43ee` -> `c3_mode` | - | - | (0, 0) | - |
| 38 | 2026-11-10T10:45:00 | `gate_evaluated_block` | gate_evaluator | - | BLOCK | 0.0312 | (6, 0) | - |
| 37 | 2026-11-10T10:41:48 | `reject_change_request` | Bob Lead | `08e43ee` -> `c2_weak` | REJECTED | - | (0, 0) | Bob Lead |
| 36 | 2026-11-10T10:41:48 | `submit_change_request` | Bob Contributor | `08e43ee` -> `c2_weak` | - | - | (0, 0) | - |
| 35 | 2026-11-10T10:41:48 | `gate_evaluated_block` | gate_evaluator | - | BLOCK | 0.0039 | (9, 0) | - |
| 34 | 2026-11-10T10:38:07 | `approve_and_promote` | Alice Reviewer | `08e43ee` -> `c1_harm` | PROMOTED | - | (0, 0) | Alice Reviewer |
| 33 | 2026-11-10T10:38:07 | `submit_change_request` | Alice Analyst | `08e43ee` -> `c1_harm` | - | - | (0, 0) | - |
| 32 | 2026-11-10T10:38:07 | `gate_evaluated_promote` | gate_evaluator | - | PROMOTE | 1.0000 | (0, 0) | - |
| 31 | 2026-11-10T10:28:51 | `reject_change_request` | Bob Lead | `08e43ee` -> `c2_weak` | REJECTED | - | (0, 0) | Bob Lead |
| 30 | 2026-11-10T10:28:51 | `submit_change_request` | Bob Contributor | `08e43ee` -> `c2_weak` | - | - | (0, 0) | - |
| 29 | 2026-11-10T10:28:50 | `gate_evaluated_block` | gate_evaluator | - | BLOCK | 0.0039 | (9, 0) | - |
| 28 | 2026-11-10T10:25:02 | `approve_and_promote` | Alice Reviewer | `08e43ee` -> `c1_harm` | PROMOTED | - | (0, 0) | Alice Reviewer |
| 27 | 2026-11-10T10:25:02 | `submit_change_request` | Alice Analyst | `08e43ee` -> `c1_harm` | - | - | (0, 0) | - |
| 26 | 2026-11-10T10:25:02 | `gate_evaluated_promote` | gate_evaluator | - | PROMOTE | 1.0000 | (0, 0) | - |
| 25 | 2026-11-10T10:24:22 | `gate_evaluated_promote` | gate_evaluator | `1` -> `4` | PROMOTE | 1.0000 | (0, 0) | - |
| 24 | 2026-11-10T10:22:40 | `reject_change_request` | Bob Lead | `sha_bas` -> `sha_can` | REJECTED | - | (0, 0) | Bob Lead |
| 23 | 2026-11-10T10:22:40 | `submit_change_request` | Eve Engineer | `sha_bas` -> `sha_can` | - | - | (0, 0) | - |
| 22 | 2026-11-10T10:22:40 | `approve_and_promote` | Alice Reviewer | `sha_bas` -> `sha_can` | PROMOTED | - | (0, 0) | Alice Reviewer |
| 21 | 2026-11-10T10:22:40 | `submit_change_request` | Dan Developer | `sha_bas` -> `sha_can` | - | - | (0, 0) | - |
| 20 | 2026-11-10T10:22:40 | `test_audit_event` | security_tester | - | - | - | (0, 0) | - |
| 19 | 2026-11-10T10:22:40 | `gate_evaluated_promote` | gate_evaluator | - | PROMOTE | 0.1250 | (0, 4) | - |
| 18 | 2026-11-10T10:22:40 | `gate_evaluated_block` | gate_evaluator | - | BLOCK | 0.2188 | (1, 5) | - |
| 17 | 2026-11-10T10:22:40 | `gate_evaluated_block` | gate_evaluator | - | BLOCK | 0.0352 | (12, 3) | - |
| 16 | 2026-11-10T10:22:40 | `gate_evaluated_promote` | gate_evaluator | - | PROMOTE | 0.0352 | (3, 12) | - |
| 15 | 2026-11-10T10:18:51 | `submit_change_request` | Alice Analyst | `08e43ee` -> `c1_harm` | - | - | (0, 0) | - |
| 14 | 2026-11-10T10:18:51 | `gate_evaluated_promote` | gate_evaluator | - | PROMOTE | 1.0000 | (0, 0) | - |
| 13 | 2026-11-10T10:18:40 | `gate_evaluated_promote` | gate_evaluator | `1` -> `4` | PROMOTE | 1.0000 | (0, 0) | - |
| 12 | 2026-11-10T10:17:54 | `gate_evaluated_promote` | gate_evaluator | `1` -> `4` | PROMOTE | 1.0000 | (0, 0) | - |
| 11 | 2026-11-10T10:16:58 | `reject_change_request` | Bob Lead | `sha_bas` -> `sha_can` | REJECTED | - | (0, 0) | Bob Lead |
| 10 | 2026-11-10T10:16:58 | `submit_change_request` | Eve Engineer | `sha_bas` -> `sha_can` | - | - | (0, 0) | - |
| 9 | 2026-11-10T10:16:58 | `approve_and_promote` | Alice Reviewer | `sha_bas` -> `sha_can` | PROMOTED | - | (0, 0) | Alice Reviewer |
| 8 | 2026-11-10T10:16:58 | `submit_change_request` | Dan Developer | `sha_bas` -> `sha_can` | - | - | (0, 0) | - |
| 7 | 2026-11-10T10:16:58 | `test_audit_event` | security_tester | - | - | - | (0, 0) | - |
| 6 | 2026-11-10T10:16:37 | `reject_change_request` | Bob Lead | `sha_bas` -> `sha_can` | REJECTED | - | (0, 0) | Bob Lead |
| 5 | 2026-11-10T10:16:37 | `submit_change_request` | Eve Engineer | `sha_bas` -> `sha_can` | - | - | (0, 0) | - |
| 4 | 2026-11-10T10:16:37 | `approve_and_promote` | Alice Reviewer | `sha_bas` -> `sha_can` | PROMOTED | - | (0, 0) | Alice Reviewer |
| 3 | 2026-11-10T10:16:37 | `submit_change_request` | Dan Developer | `sha_bas` -> `sha_can` | - | - | (0, 0) | - |
| 2 | 2026-11-10T10:16:37 | `test_audit_event` | security_tester | - | - | - | (0, 0) | - |
| 1 | 2026-11-10T10:07:29 | `test_action` | test_actor | - | - | - | (0, 0) | - |

## Append-Only Security Verification

All audit records are immutable. Record modifications and deletions are rejected by the database schema listener and application access layers.
