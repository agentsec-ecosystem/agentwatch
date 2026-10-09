-- agentwatch derived Postgres index (M28 DATA-1, PRD 41; design docs/design/derived-postgres.md)
--
-- The hash-chained JSONL store is the source of truth. This schema is a
-- DERIVED index: it is fully rebuildable from the chain and may be dropped at
-- any time (the drop-Postgres mode). Every table carries source_seq/source_hash
-- back-references so a row can always be traced to the chain entry it came from;
-- nothing here authorizes a read that the store cannot reproduce.

CREATE TABLE IF NOT EXISTS sessions (
    session_id     TEXT PRIMARY KEY,
    project        TEXT,
    harness        TEXT,
    agent_name     TEXT,
    agent_version  TEXT,
    started_at     TIMESTAMPTZ,
    ended_at       TIMESTAMPTZ,
    source_seq     BIGINT NOT NULL,
    source_hash    TEXT NOT NULL,
    derived_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS records (
    record_id      TEXT PRIMARY KEY,
    session_id     TEXT NOT NULL REFERENCES sessions (session_id),
    seq            BIGINT NOT NULL,
    tool           TEXT,
    outcome        TEXT,
    record_phase   TEXT,
    producer_kind  TEXT,
    started_at     TIMESTAMPTZ,
    source_seq     BIGINT NOT NULL,
    source_hash    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    event_id       TEXT PRIMARY KEY,
    session_id     TEXT NOT NULL REFERENCES sessions (session_id),
    type           TEXT NOT NULL,
    emitter        TEXT,
    emitted_at     TIMESTAMPTZ,
    source_seq     BIGINT NOT NULL,
    source_hash    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS usage (
    usage_id       TEXT PRIMARY KEY,
    session_id     TEXT NOT NULL REFERENCES sessions (session_id),
    tokens         BIGINT,
    cost_usd       DOUBLE PRECISION,
    duration_ms    DOUBLE PRECISION,
    source_seq     BIGINT NOT NULL,
    source_hash    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS identity (
    identity_id        TEXT PRIMARY KEY,
    session_id         TEXT NOT NULL REFERENCES sessions (session_id),
    credential_class   TEXT,
    workload_identity  TEXT,
    principal_hash     TEXT,
    delegation_chain   JSONB,
    source_seq         BIGINT NOT NULL,
    source_hash        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS detectors (
    finding_id     TEXT PRIMARY KEY,
    session_id     TEXT NOT NULL REFERENCES sessions (session_id),
    detector       TEXT NOT NULL,
    severity       TEXT,
    explanation    TEXT,
    source_seq     BIGINT NOT NULL,
    source_hash    TEXT NOT NULL
);

-- Back-reference indexes: a rebuild verifies each row against its chain entry.
CREATE INDEX IF NOT EXISTS records_source_seq_idx ON records (source_seq);
CREATE INDEX IF NOT EXISTS events_source_seq_idx ON events (source_seq);
CREATE INDEX IF NOT EXISTS detectors_session_idx ON detectors (session_id);
