type PagesContext = {
  request: Request;
  env: {
    CF_PAGES_BRANCH: string;
    DEV_API_ORIGIN?: string;
    STAGING_API_ORIGIN?: string;
  };
};

/** Proxy only API routes to the environment-specific Lambda Function URL. */
export async function onRequest({ request, env }: PagesContext): Promise<Response> {
  if (!["GET", "POST", "PATCH", "DELETE"].includes(request.method)) {
    return new Response("Method not allowed", {
      status: 405,
      headers: { Allow: "GET, POST, PATCH, DELETE" },
    });
  }

  // The Pages workflow deploys master as the Pages branch "staging".
  const originValue =
    env.CF_PAGES_BRANCH === "master" || env.CF_PAGES_BRANCH === "staging"
      ? env.STAGING_API_ORIGIN
      : env.DEV_API_ORIGIN;
  if (!originValue) {
    return Response.json({ error: "API origin is not configured" }, { status: 503 });
  }

  let origin: URL;
  try {
    origin = new URL(originValue);
  } catch {
    return Response.json({ error: "API origin is invalid" }, { status: 503 });
  }
  if (
    origin.protocol !== "https:" ||
    origin.username ||
    origin.password ||
    origin.pathname !== "/" ||
    origin.search ||
    origin.hash
  ) {
    return Response.json({ error: "API origin is invalid" }, { status: 503 });
  }

  const incoming = new URL(request.url);
  const apiPath = incoming.pathname.slice("/api".length) || "/";
  const target = new URL(`${apiPath}${incoming.search}`, origin);

  try {
    return await fetch(new Request(target, request));
  } catch {
    return Response.json({ error: "API upstream is unavailable" }, { status: 502 });
  }
}
