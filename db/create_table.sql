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

CREATE TABLE instance_info(
    id              SERIAL          PRIMARY KEY,
    instance_id     VARCHAR(20)     UNIQUE NOT NULL,
    state           VARCHAR(10)
)
;

CREATE TYPE
    request_type AS ENUM ('start', 'end')
;

CREATE TABLE slack_instance_request_log(
    id                  SERIAL          PRIMARY KEY,
    student_id          VARCHAR(5)      NOT NULL,
    instance_info_id    VARCHAR(20)     NOT NULL,
    request_type        request_type,
    request_time        TIMESTAMP       NOT NULL,
    FOREIGN KEY(student_name)       REFERENCES student(id)          ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY(instance_info_id)   REFERENCES instance_info(id)    ON DELETE CASCADE ON UPDATE CASCADE
)
;

