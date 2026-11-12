-- Только успешно зафиксированные попытки; связь сохраняется вместе с записью.
CREATE TABLE booking_keys (
    key uuid PRIMARY KEY,
    booking_id uuid NOT NULL UNIQUE REFERENCES bookings(id)
);
