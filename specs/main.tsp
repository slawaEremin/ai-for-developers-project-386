import "@typespec/http";
import "@typespec/openapi3";

using TypeSpec.Http;

@service(#{ title: "Calendar API" })
namespace Calendar;

model HealthResponse {
  status: "ok";
}

@route("/health")
@get
op getHealth(): HealthResponse;

@minLength(1)
@maxLength(64)
@pattern("^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$")
scalar MeetingTypeId extends string;

@minLength(1)
@maxLength(120)
@doc("Однострочный обычный текст; края очищаются от пробелов, длина в Unicode.")
scalar MeetingTypeName extends string;

@minLength(1)
@maxLength(2000)
@doc("Обычный текст с внутренними переносами; края очищаются от пробелов.")
scalar MeetingTypeDescription extends string;

@minValue(1)
@maxValue(540)
scalar DurationMinutes extends int32;

model MeetingType {
  id: MeetingTypeId;
  name: MeetingTypeName;
  description: MeetingTypeDescription;
  durationMinutes: DurationMinutes;
}

model ApiError {
  code: string;
  message: string;
  fieldErrors?: Record<string>;
}

model ErrorResponse<Status extends int32> {
  @statusCode statusCode: Status;
  @header cacheControl: "no-store";
  @body body: ApiError;
}

@route("/api/meeting-types")
@post
op createMeetingType(
  @header contentType: "application/json",
  @body body: MeetingType,
):
  | {
      @statusCode statusCode: 201;
      @header cacheControl: "no-store";
      @body body: MeetingType;
    }
  | ErrorResponse<400>
  | ErrorResponse<409>
  | ErrorResponse<415>
  | ErrorResponse<422>
  | ErrorResponse<503>
  | ErrorResponse<500>;

model MeetingTypeList {
  serverTime: utcDateTime;
  items: MeetingType[];
}

@route("/api/meeting-types")
@get
op listMeetingTypes():
  | {
      @statusCode statusCode: 200;
      @header cacheControl: "no-store";
      @body body: MeetingTypeList;
    }
  | ErrorResponse<503>
  | ErrorResponse<500>;

@route("/api/meeting-types/{id}")
@get
op getMeetingType(@path id: MeetingTypeId):
  | {
      @statusCode statusCode: 200;
      @header cacheControl: "no-store";
      @body body: MeetingType;
    }
  | ErrorResponse<404>
  | ErrorResponse<422>
  | ErrorResponse<503>
  | ErrorResponse<500>;

model AvailableSlot {
  startsAt: utcDateTime;
  endsAt: utcDateTime;
}

model AvailabilityDay {
  date: plainDate;
  slots: AvailableSlot[];
}

model Availability {
  serverTime: utcDateTime;
  timeZone: "Europe/Moscow";
  windowStartDate: plainDate;
  windowEndDate: plainDate;

  @minItems(14)
  @maxItems(14)
  days: AvailabilityDay[];
}

@route("/api/meeting-types/{id}/availability")
@get
op getAvailability(@path id: MeetingTypeId):
  | {
      @statusCode statusCode: 200;
      @header cacheControl: "no-store";
      @body body: Availability;
    }
  | ErrorResponse<404>
  | ErrorResponse<422>
  | ErrorResponse<503>
  | ErrorResponse<500>;

model BookingRequest {
  meetingTypeId: MeetingTypeId;

  @doc("RFC 3339 со смещением или Z; эквивалентные моменты равнозначны.")
  startsAt: utcDateTime;
}

model Booking {
  @format("uuid") id: string;
  meetingTypeId: MeetingTypeId;
  meetingTypeName: MeetingTypeName;
  startsAt: utcDateTime;
  endsAt: utcDateTime;
  durationMinutes: DurationMinutes;
  timeZone: "Europe/Moscow";
}

@route("/api/bookings")
@post
op createBooking(
  @header contentType: "application/json",
  @header("Idempotency-Key") @format("uuid") idempotencyKey: string,
  @body body: BookingRequest,
):
  | {
      @statusCode statusCode: 201;
      @header cacheControl: "no-store";
      @body body: Booking;
    }
  | {
      @statusCode statusCode: 200;
      @header cacheControl: "no-store";
      @body body: Booking;
    }
  | ErrorResponse<400>
  | ErrorResponse<404>
  | ErrorResponse<409>
  | ErrorResponse<415>
  | ErrorResponse<422>
  | ErrorResponse<503>
  | ErrorResponse<500>;

model UpcomingBookings {
  serverTime: utcDateTime;
  items: Booking[];
}

@route("/api/bookings/upcoming")
@get
op listUpcomingBookings():
  | {
      @statusCode statusCode: 200;
      @header cacheControl: "no-store";
      @body body: UpcomingBookings;
    }
  | ErrorResponse<503>
  | ErrorResponse<500>;
