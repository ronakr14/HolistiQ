CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    runner TEXT NOT NULL,          -- "custom" or "pytest"
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS test_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    test_name TEXT NOT NULL,
    file_path TEXT,
    line INTEGER,
    outcome TEXT NOT NULL,         -- 'passed','failed','error','skipped'
    duration REAL,
    details TEXT,
    FOREIGN KEY(run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS coverage_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER,
    total_coverage REAL,
    covered INTEGER,
    measured INTEGER,
    created_at TEXT,
    metadata TEXT,
    FOREIGN KEY(run_id) REFERENCES runs(id)
);

test_runs:
    id
    runid
    testname
    filepath
    runner
    started
    finished
    result
    error
    mode
    branch
    classname
    module
    test_case
    username
    parallely
    threads
    duration
    exception
    insertdate
    git_repo
    testid

testcases
    id
    insertdate
    updatedate
    branch
    filepath
    module
    classname
    testname
    setup
    setupall
    teardown
    teardownall
    published by
    updated by
    hashkey

creds
    id
    emailid
    username
    fname
    lname
    password
    dob
    insertdate


    create table public.site_pages (
  id bigserial not null,
  url character varying not null,
  chunk_number integer not null,
  title character varying not null,
  summary character varying not null,
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  embedding public.vector null,
  created_at timestamp with time zone not null default timezone ('utc'::text, now()),
  constraint site_pages_pkey primary key (id),
  constraint site_pages_url_chunk_number_key unique (url, chunk_number)
) TABLESPACE pg_default;

create index IF not exists idx_site_pages_metadata on public.site_pages using gin (metadata) TABLESPACE pg_default;

create index IF not exists site_pages_embedding_idx on public.site_pages using ivfflat (embedding vector_cosine_ops) TABLESPACE pg_default;

create index IF not exists site_pages_embedding_idx1 on public.site_pages using ivfflat (embedding vector_cosine_ops) TABLESPACE pg_default;
