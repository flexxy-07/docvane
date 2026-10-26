import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from backend.app.core.logging import ctx_request_id, ctx_tenant_id


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that establishes request tracing and tenant context:
    - Sets unique request_id per incoming request.
    - Extracts tenant_id from 'X-Tenant-ID' header or authenticated session.
    - Binds both to contextvars for structured JSON logging across async execution.
    - Returns 'X-Request-ID' header in HTTP response.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # request ID from the header or generate new uuid
        incoming_req_id = request.headers.get("X-Request-ID")
        request_id = incoming_req_id if incoming_req_id else str(uuid.uuid4())
        ctx_request_id.set(request_id)
        request.state.request_id = request_id

        # Tenant Id from header for multi tenancy
        tenant_id = request.headers.get("X-Tenant-ID")

        if tenant_id:
            ctx_tenant_id.set(tenant_id)
            request.state.tenant_id = tenant_id
        else:
            ctx_tenant_id.set(None)
            request.state.tenant_id = None

        # call next middleware and handle response
        try:
            response = await call_next(request)
        except Exception as e:
            ctx_request_id.set(None)
            ctx_tenant_id.set(None)
            raise e

        # add response headers
        response.headers["X-Request-ID"] = request_id
        if tenant_id:
            response.headers["X-Tenant-ID"] = tenant_id

        return response
