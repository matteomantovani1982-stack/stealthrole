"""
app/api/middleware/cache_control.py

Starlette middleware that adds Cache-Control headers to GET responses.

Rules:
  - Health/ready endpoints: short cache (10s) — prevents LB hammering
  - Auth and mutation endpoints: no-store
  - Everything else: private, no-cache (browser revalidates every time)

This is a production-safe baseline. For aggressive caching of specific
endpoints, add explicit Cache-Control headers in the route itself.
"""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)

        # Only add Cache-Control to GET responses that don't already have it
        if request.method != "GET" or "cache-control" in response.headers:
            return response

        path = request.url.path

        # Health probes — allow short caching to reduce load
        if path.startswith("/health"):
            response.headers["Cache-Control"] = "public, max-age=10"
        # Auth & billing — never cache
        elif "/auth/" in path or "/billing/" in path or "/credits/" in path:
            response.headers["Cache-Control"] = "no-store"
        # API GETs — private, must revalidate
        elif path.startswith("/api/"):
            response.headers["Cache-Control"] = "private, no-cache"

        return response
