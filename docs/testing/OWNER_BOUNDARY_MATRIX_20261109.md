# Synthetic owner boundary matrix

The five cases in tests/test_owner_boundary_matrix.py exercise two distinct synthetic registered owners in both directions. They cover resource reads, list/search filtering, person/interaction writes, foreign goal/person/source IDs, source revocation, and same request keys across owners. Each rejected mutation must leave both selected API snapshots unchanged. This is not a complete all-table immutability proof.

The DELETE /api/personalization test injects the other owner ID in the query string and proves only the authenticated owner feature rows are removed. The other owner's nonempty feature rows, preferences and selected API snapshot remain unchanged. FeatureStore is explicitly enabled for this isolated test; this is not evidence the feature is deployed/enabled remotely.

The restart case closes the original DB adapter and creates a new adapter and App with existing cookies, checking persistence and cross-owner rejection. It is not an operating-system process restart.

Every case asserts and records the actual backend. Current execution is SQLite. The optional PostgreSQL path uses existing dedicated synthetic-marker fixtures; it has NOT been executed for this new matrix. No claim of RLS protection, E2E runtime-role parity, Cloud SQL acceptance or production backup protection follows from these results.

## PostgreSQL follow-up boundary
Do not run tests/pg_support.py against E2E or production: its reset intentionally TRUNCATEs synthetic tables and checks the database marker. An approved user-run isolated PG18 launcher must create a new marker-protected disposable container, bootstrap synthetic data and run this matrix under LIFEWORLD_TEST_BACKEND=postgresql, recording backend properties. The existing Docker pipe denial remains in force for the assistant. Do not reuse a production URL/password, change ACLs, or bypass the daemon denial. A matrix-specific launcher/update is needed before providing a copy-paste user command; this document does not authorize cloud writes.

Final integrated offline regression: 554 passed, 17 dedicated PostgreSQL skipped, 50.45 seconds. JUnit legacy format preserves backend properties. The five owner-matrix cases all record sqlite; the reopened backend is also sqlite. Independent static review confirmed status-200 snapshot checks, distinct owners and nonempty preserved rows.

## Disposable PG fixture correction

The first dedicated PG run returned 3 passed / 2 failed, cleanup confirmed. Both deletion tests stopped during FeatureStore.configure before DELETE: the dev bootstrap did not include the two memory tables. scripts/pg_owner_matrix_fixture.py adds only these tables to a fresh marker-protected local dev cluster, owned by lw_migration_role. Preferences receives SELECT/INSERT/UPDATE; features additionally receives DELETE. Runtime preflight checks exact columns/types, ownership, schema CREATE denial, table permissions including MAINTAIN and all grant options. No production migration or E2E alteration is implied. The original five matrix assertions are unchanged. Corrected real-PG execution remains pending.
