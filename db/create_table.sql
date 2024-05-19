CREATE TYPE
    track AS ENUM ('DE', 'DS')
;

CREATE TABLE student (
    id              SERIAL          PRIMARY KEY,
    name            VARCHAR(5)      UNIQUE NOT NULL,
    slack_id        VARCHAR(15)     UNIQUE NOT NULL,
    track           track,
    email           VARCHAR(50)     UNIQUE NOT NULL
)
;
