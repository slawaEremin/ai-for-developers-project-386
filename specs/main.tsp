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
