import { afterEach, describe, expect, it, vi } from "vitest";

import { onRequest } from "./[[path]]";

describe("Pages API proxy", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("routes the staging Pages branch to the staging API origin", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response("ok", { status: 200 }));

    const response = await onRequest({
      request: new Request("https://preview.example.com/api/health"),
      env: {
        CF_PAGES_BRANCH: "staging",
        DEV_API_ORIGIN: "https://dev-api.example.com",
        STAGING_API_ORIGIN: "https://staging-api.example.com",
      },
    });

    expect(response.status).toBe(200);
    const forwarded = fetchMock.mock.calls[0]?.[0];
    expect(forwarded).toBeInstanceOf(Request);
    expect((forwarded as Request).url).toBe("https://staging-api.example.com/health");
  });
});
