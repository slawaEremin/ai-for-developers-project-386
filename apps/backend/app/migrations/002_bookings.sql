CREATE TABLE bookings (
    id uuid PRIMARY KEY,
    owner_id integer NOT NULL REFERENCES owners(id) CHECK (owner_id = 1),
    meeting_type_id varchar(64) NOT NULL REFERENCES meeting_types(id),
    meeting_type_name text NOT NULL,
    duration_minutes integer NOT NULL CHECK (duration_minutes BETWEEN 1 AND 540),
    starts_at timestamptz NOT NULL,
    ends_at timestamptz NOT NULL,
    CHECK (ends_at > starts_at),
    CHECK (ends_at = starts_at + duration_minutes * interval '1 minute'),
    -- Один владелец: занятость общая для всех типов, соприкосновение разрешено.
    CONSTRAINT bookings_no_overlap EXCLUDE USING gist (
        tstzrange(starts_at, ends_at, '[)') WITH &&
    )
);
