import { test } from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { Matchers, Pact, SpecificationVersion } from "@pact-foundation/pact";

import { fetchRouteVariants } from "../src/routeApi.ts";

const { eachLike, integer, string } = Matchers;

test("the frontend can search for route 240", async () => {
  const pact = new Pact({
    consumer: "TransperthFrontend",
    provider: "TransperthApi",
    dir: path.resolve("pacts"),
    spec: SpecificationVersion.SPECIFICATION_VERSION_V4,
    logLevel: "warn",
  });

  await pact
    .addInteraction()
    .uponReceiving("a request for route 240")
    .withRequest("GET", "/api/routes", (builder) => {
      builder.query({ number: "240" });
    })
    .willRespondWith(200, (builder) => {
      builder.headers({ "Content-Type": "application/json" });
      builder.jsonBody(
        eachLike({
          route_id: string("SWA-SRI-146"),
          route_number: string("240"),
          trip_count: integer(2),
          sample_trip_id: string("7070970"),
        }),
      );
    })
    .executeTest(async (mockServer) => {
      const variants = await fetchRouteVariants(mockServer.url, "240");

      assert.equal(variants.length, 1);
      assert.equal(variants[0].route_number, "240");
      assert.equal(variants[0].trip_count, 2);
    });
});
