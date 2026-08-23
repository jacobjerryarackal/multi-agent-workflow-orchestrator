"""Security headers middleware for HTTP response hardening."""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Applies standard defensive HTTP security headers to all API responses:
    - X-Content-Type-Options: nosniff (Prevents MIME-type sniffing attacks)
    - X-Frame-Options: DENY (Mitigates clickjacking attacks)
    - X-XSS-Protection: 1; mode=block (Enforces legacy browser XSS filters)
    - Referrer-Policy: strict-origin-when-cross-origin (Prevents leaking full path across cross-origin requests)
    - Content-Security-Policy: Restricts allowed content sources
    - Permissions-Policy: Disables unused client-side hardware features (camera, mic, geo)
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # Apply hardening headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none';"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"

        return response
