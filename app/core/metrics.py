import time

from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

REQUEST_COUNT = Counter(
    "taskflow_requests_total",
    "Total HTTP requests.",
    ["method", "path", "status"],
)
REQUEST_ERRORS = Counter(
    "taskflow_request_errors_total",
    "HTTP requests that returned a 5xx status.",
    ["method", "path"],
)
REQUEST_LATENCY = Histogram(
    "taskflow_request_latency_seconds",
    "Request latency in seconds.",
    ["method", "path"],
)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Use the route template (e.g. /tasks/{task_id}) rather than the raw
        # path so per-id requests do not explode label cardinality.
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start

        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        method = request.method

        REQUEST_COUNT.labels(method, path, response.status_code).inc()
        REQUEST_LATENCY.labels(method, path).observe(elapsed)
        if response.status_code >= 500:
            REQUEST_ERRORS.labels(method, path).inc()
        return response
