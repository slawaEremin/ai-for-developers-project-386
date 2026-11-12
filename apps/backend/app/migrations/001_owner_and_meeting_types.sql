CREATE TABLE owners (
    id integer PRIMARY KEY CHECK (id = 1),
    name text NOT NULL
);

CREATE TABLE meeting_types (
    id varchar(64) PRIMARY KEY CHECK (id ~ '^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$'),
    owner_id integer NOT NULL REFERENCES owners(id),
    name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 120),
    description text NOT NULL CHECK (char_length(description) BETWEEN 1 AND 2000),
    duration_minutes integer NOT NULL CHECK (duration_minutes BETWEEN 1 AND 540)
);
