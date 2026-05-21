CREATE TABLE testruns (
    id SERIAL PRIMARY KEY,
    runid VARCHAR(64) DEFAULT '',

    filepath VARCHAR(512) NOT NULL,
    module VARCHAR(256) NOT NULL,
    classname VARCHAR(256),
    testname VARCHAR(256) NOT NULL,

    runner VARCHAR(128) NOT NULL,
    platform VARCHAR(128) NOT NULL,

    started DATETIME NOT NULL,
    finished DATETIME NOT NULL,
    duration DOUBLE PRECISION,
    result VARCHAR(64) NOT NULL,
    error TEXT,
    exception TEXT,

    username VARCHAR(128) NOT NULL,
    parallely BOOLEAN,
    threads INT,
    git_repo BOOLEAN,
    branch VARCHAR(256),
    insertdate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
