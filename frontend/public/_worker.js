export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/api" || url.pathname.startsWith("/api/")) {
      const origin = env.API_ORIGIN;
      if (!origin) {
        return new Response("API_ORIGIN is not configured", { status: 500 });
      }
      const target = new URL(url.pathname + url.search, origin);
      return fetch(new Request(target, request));
    }
    return env.ASSETS.fetch(request);
  },
};
