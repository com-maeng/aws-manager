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

create table slack_instance_request_log(
		id              SERIAL          PRIMARY KEY,
		student_name    VARCHAR(5)		not NULl,
		instance_id     VARCHAR(20)		not null,
		request_type 	request_type,
		request_time  	timestamp 		not null
);

alter table slack_instance_request_log add foreign key (student_name) references student(name);
alter table instance_info  add foreign key (instance_id) references instance_info(instance_id);

