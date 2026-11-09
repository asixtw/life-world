-- 隔離SQLite開發契約；正式PG另用受備份Gate保護的增量SQL，不由Runtime建表。
CREATE TABLE relationship_memory_preferences (
 owner_id TEXT PRIMARY KEY REFERENCES users(id), enabled INTEGER NOT NULL DEFAULT 0,
 preferences TEXT NOT NULL DEFAULT '{}', revision INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE relationship_features (
 owner_id TEXT NOT NULL REFERENCES users(id), subject_type TEXT NOT NULL CHECK(subject_type IN ('user','person','relationship','context')),
 subject_id TEXT NOT NULL, feature_key TEXT NOT NULL, value TEXT NOT NULL, source_refs TEXT NOT NULL,
 context_scope TEXT NOT NULL, epistemic_status TEXT NOT NULL, model_version TEXT NOT NULL,
 profile_version INTEGER NOT NULL, revocation_state TEXT NOT NULL CHECK(revocation_state IN ('active','withdrawn')),
 PRIMARY KEY(owner_id,subject_type,subject_id,feature_key)
);
