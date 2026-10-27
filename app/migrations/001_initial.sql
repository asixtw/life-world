CREATE TABLE users (
 id TEXT PRIMARY KEY, status TEXT NOT NULL CHECK(status IN ('guest','registered')),
 username TEXT UNIQUE, password_hash TEXT, name TEXT NOT NULL DEFAULT '', bio TEXT NOT NULL DEFAULT '',
 timezone TEXT NOT NULL DEFAULT 'Asia/Taipei', hatched_at TEXT, created_at TEXT NOT NULL
);
CREATE TABLE sessions (
 token_hash TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id),
 csrf_token TEXT NOT NULL, expires_at TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX session_owner_idx ON sessions(owner_id);
CREATE TABLE goals (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), title TEXT NOT NULL,
 outcome TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('active','completed')),
 created_at TEXT NOT NULL, completed_at TEXT, reflection TEXT NOT NULL DEFAULT ''
);
CREATE INDEX goals_owner_idx ON goals(owner_id);
CREATE TABLE actions (
 id TEXT PRIMARY KEY, goal_id TEXT NOT NULL REFERENCES goals(id), owner_id TEXT NOT NULL REFERENCES users(id),
 title TEXT NOT NULL, unit TEXT NOT NULL, target TEXT NOT NULL,
 level INTEGER NOT NULL CHECK(level BETWEEN 1 AND 3), weekdays TEXT NOT NULL, position INTEGER NOT NULL
);
CREATE TABLE people (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), name TEXT NOT NULL,
 role TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE TABLE drafts (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), goal_id TEXT REFERENCES goals(id),
 person_id TEXT REFERENCES people(id), raw_text TEXT NOT NULL, occurred_at TEXT NOT NULL,
 contributions TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('draft','confirmed')),
 revision INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE experiences (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), draft_id TEXT NOT NULL UNIQUE REFERENCES drafts(id),
 goal_id TEXT REFERENCES goals(id), person_id TEXT REFERENCES people(id), raw_text TEXT NOT NULL,
 summary TEXT NOT NULL, occurred_at TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX experiences_owner_idx ON experiences(owner_id);
CREATE TABLE contributions (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), experience_id TEXT NOT NULL REFERENCES experiences(id),
 action_id TEXT NOT NULL REFERENCES actions(id), quantity TEXT NOT NULL,
 UNIQUE(experience_id, action_id)
);
CREATE TABLE reward_ledger (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), experience_id TEXT NOT NULL UNIQUE REFERENCES experiences(id),
 points INTEGER NOT NULL CHECK(points>0), rule_version TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE tasks (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), experience_id TEXT NOT NULL REFERENCES experiences(id),
 title TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0 CHECK(done IN (0,1))
);
CREATE TABLE evidence (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), goal_id TEXT NOT NULL REFERENCES goals(id),
 filename TEXT NOT NULL, mime TEXT NOT NULL, digest TEXT NOT NULL, content BLOB NOT NULL, size INTEGER NOT NULL,
 created_at TEXT NOT NULL, UNIQUE(owner_id, goal_id, digest)
);
CREATE TABLE completions (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), goal_id TEXT NOT NULL UNIQUE REFERENCES goals(id),
 evidence_ids TEXT NOT NULL, reflection TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE notes (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), person_id TEXT REFERENCES people(id),
 kind TEXT NOT NULL CHECK(kind IN ('preparation','simulation','message')), title TEXT NOT NULL,
 content TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE requests (
 owner_id TEXT NOT NULL REFERENCES users(id), operation TEXT NOT NULL, request_id TEXT NOT NULL,
 fingerprint TEXT NOT NULL, response TEXT NOT NULL, PRIMARY KEY(owner_id, operation, request_id)
);
