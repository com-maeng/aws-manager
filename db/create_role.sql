-- 절대 복붙 금지! 템플릿으로만 활용
-- https://www.postgresql.org/docs/13/sql-createrole.html

CREATE ROLE
    developers
;

CREATE ROLE
    hongju
WITH
    CREATEDB
    CONNECTION LIMIT 5
    LOGIN
    PASSWORD 'placeholder'
    IN ROLE developers
;

CREATE ROLE
    yoonjae
WITH
    CREATEDB
    CONNECTION LIMIT 5
    LOGIN
    PASSWORD 'placeholder'
    IN ROLE developers
;
