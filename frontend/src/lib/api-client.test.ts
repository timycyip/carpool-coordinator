import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  setAuthToken,
  clearAuthToken,
  getAuthToken,
  onUnauthorized,
  ApiError,
  get,
  post,
  patch,
  del,
} from "./api-client";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

beforeEach(() => {
  mockFetch.mockReset();
  clearAuthToken();
});

describe("token management", () => {
  it("stores and retrieves a token", () => {
    expect(getAuthToken()).toBeNull();
    setAuthToken("abc123");
    expect(getAuthToken()).toBe("abc123");
  });

  it("clears the token", () => {
    setAuthToken("abc123");
    clearAuthToken();
    expect(getAuthToken()).toBeNull();
  });
});

describe("request", () => {
  it("builds URL with /api base path", async () => {
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );

    await get("/sessions");

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/sessions",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("includes Authorization header when token is set", async () => {
    setAuthToken("mytoken");
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );

    await get("/sessions");

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/sessions",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer mytoken",
        }),
      }),
    );
  });

  it("omits Authorization header when no token", async () => {
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );

    await get("/sessions");

    const headers = mockFetch.mock.calls[0][1].headers as Record<string, string>;
    expect(headers).not.toHaveProperty("Authorization");
  });

  it("parses successful JSON response", async () => {
    const data = { session_code: "ABC" };
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify(data), { status: 200 }),
    );

    const result = await get<{ session_code: string }>("/sessions/ABC");
    expect(result).toEqual(data);
  });

  it("returns undefined for 204 No Content", async () => {
    mockFetch.mockResolvedValueOnce(new Response(null, { status: 204 }));

    const result = await del("/sessions/ABC");
    expect(result).toBeUndefined();
  });

  it("sends JSON body for POST", async () => {
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ id: "1" }), { status: 201 }),
    );

    await post("/sessions", { title: "Test" });

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/sessions",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ title: "Test" }),
      }),
    );
  });

  it("sends JSON body for PATCH", async () => {
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ id: "1" }), { status: 200 }),
    );

    await patch("/sessions/ABC", { title: "Updated" });

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/sessions/ABC",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ title: "Updated" }),
      }),
    );
  });
});

describe("error handling", () => {
  it("throws ApiError with nested error body", async () => {
    const errorBody = {
      error: {
        code: "VALIDATION_ERROR",
        message: "One or more fields failed validation.",
        details: { fields: [{ path: "email", issue: "required" }] },
      },
    };

    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify(errorBody), { status: 422 }),
    );

    try {
      await post("/sessions", {});
      expect.fail("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError);
      const apiErr = e as ApiError;
      expect(apiErr.code).toBe("VALIDATION_ERROR");
      expect(apiErr.message).toBe("One or more fields failed validation.");
      expect(apiErr.details).toEqual({
        fields: [{ path: "email", issue: "required" }],
      });
    }
  });

  it("throws generic ApiError for non-JSON error responses", async () => {
    mockFetch.mockResolvedValueOnce(
      new Response("Internal Server Error", { status: 500 }),
    );

    try {
      await get("/sessions");
      expect.fail("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError);
      const apiErr = e as ApiError;
      expect(apiErr.code).toBe("UNKNOWN_ERROR");
    }
  });

  it("clears token on 401 response", async () => {
    setAuthToken("expired-token");

    const errorBody = {
      error: {
        code: "UNAUTHORIZED",
        message: "Authentication required.",
      },
    };

    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify(errorBody), { status: 401 }),
    );

    await expect(get("/sessions")).rejects.toThrow(ApiError);
    expect(getAuthToken()).toBeNull();
  });

  it("notifies onUnauthorized listeners on 401", async () => {
    const listener = vi.fn();
    const unsub = onUnauthorized(listener);

    setAuthToken("expired-token");

    mockFetch.mockResolvedValueOnce(
      new Response(
        JSON.stringify({ error: { code: "UNAUTHORIZED", message: "Auth required." } }),
        { status: 401 },
      ),
    );

    await expect(get("/sessions")).rejects.toThrow(ApiError);
    expect(listener).toHaveBeenCalledOnce();

    unsub();
  });
});
