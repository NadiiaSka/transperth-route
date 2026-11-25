import { test } from "node:test";
import path from "node:path";
import { Verifier } from "@pact-foundation/pact";

test("the API satisfies the frontend contract", async () => {
  await new Verifier({
    provider: "TransperthApi",
    providerBaseUrl: "http://127.0.0.1:8001",
    pactUrls: [path.resolve("pacts", "TransperthFrontend-TransperthApi.json")],
  }).verifyProvider();
});
