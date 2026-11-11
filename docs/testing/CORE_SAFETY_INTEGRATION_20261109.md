# Core safety integration review

Base: 66fd8d42ad99c8018e933744df6b9b5a7c62b490. Integrates pool lifecycle/openers ownership fixes, deterministic snapshot timestamp mutation, fixed-clock public-release test, and the explicitly accepted non-POSIX EvaluationStore fail-closed restriction.

## Evidence
- Integrated cloud Linux offline regression: 549 passed, 17 dedicated PostgreSQL skipped, 13 warnings, 47.48 seconds. Python networking blocked by runner; Node available.
- Earlier user-run OSSANG isolated PG18 suite: 542 passed, 2 failed, 13 Node skipped; required 17 PG tests passed; cleanup_confirmed=true. That run predates the final timestamp/fail-closed integration and is not a full rerun of this commit.
- OSSANG Windows 3.12.2 actual platform probe loaded integrated model_eval/core.py in memory, SHA256 16c09a9ef56eca530c6b6b03e1a99bf9ae88554defa8e0075e63a937350a0068. Constructor and all six CLI commands rejected before storage; CLI returned 2. Existing package CLI/dependencies were reused without modifying files. This is a targeted platform probe, not a full Windows checkout regression.
- Fixed-clock reproduction: old timestamp test fails when both clock reads are identical; corrected test passes.

## Limitations and remaining acceptance
Windows model evaluation is intentionally unsupported; no ACL protection is claimed. Existing Windows evaluation happy-path tests cannot be reported as passing. POSIX filesystem/ACL/symlink hardening is not newly certified.
No Cloud SQL validation, deployment, production endpoint check, real credentials, or real data. No change to OSSANG original working tree. Complete three-track acceptance remains outstanding; an independent branch is preservation, not completion. No remote push before trigger/authentication review.
