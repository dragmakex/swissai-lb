"""SwissAI metrics: fixed route/outcome/reason labels; no request IDs or credential material."""

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

REGISTRY = CollectorRegistry(auto_describe=True)
REQUESTS = Counter("swissai_lb_requests_total", "Logical requests", ["route", "outcome"], registry=REGISTRY)
ATTEMPTS = Counter(
    "swissai_lb_upstream_attempts_total", "Upstream attempts", ["route", "outcome", "status_class"], registry=REGISTRY
)
FAILOVERS = Counter("swissai_lb_failovers_total", "Cross-key failovers before output", ["reason"], registry=REGISTRY)
INFLIGHT = Gauge("swissai_lb_key_inflight", "In-flight leases", ["key_id"], registry=REGISTRY)
STATE = Gauge("swissai_lb_key_state", "Derived key state", ["key_id", "state"], registry=REGISTRY)
ELIGIBLE = Gauge("swissai_lb_eligible_keys", "Eligible keys before client/model restrictions", registry=REGISTRY)
CATALOG_AGE = Gauge("swissai_lb_model_catalog_age_seconds", "Catalog age", registry=REGISTRY)
REQUEST_LATENCY = Histogram(
    "swissai_lb_request_duration_seconds", "Logical request duration", ["route"], registry=REGISTRY
)
LATENCY = Histogram("swissai_lb_upstream_latency_seconds", "Attempt latency", ["route"], registry=REGISTRY)
TTFT = Histogram(
    "swissai_lb_upstream_ttft_seconds", "Attempt start to first observed model output", ["route"], registry=REGISTRY
)
ADMISSION = Histogram("swissai_lb_admission_wait_seconds", "Admission wait", registry=REGISTRY)


def request(route: str, outcome: str, elapsed: float) -> None:
    REQUESTS.labels(route=route, outcome=outcome).inc()
    REQUEST_LATENCY.labels(route=route).observe(elapsed)


def attempt(route: str, status: int | None, reason: str | None, elapsed: float) -> None:
    ATTEMPTS.labels(
        route=route,
        outcome="error" if reason else "success",
        status_class=f"{status // 100}xx" if status else "transport",
    ).inc()
    LATENCY.labels(route=route).observe(elapsed)


def failover(reason: str) -> None:
    FAILOVERS.labels(reason=reason).inc()


def first_output(route: str, elapsed: float) -> None:
    TTFT.labels(route=route).observe(elapsed)


def admission(elapsed: float) -> None:
    ADMISSION.observe(elapsed)


async def scrape(catalog_age: float | None) -> bytes:
    from app.modules.swissai.repository import list_keys, pool_settings

    keys = await list_keys()
    config = await pool_settings()
    INFLIGHT.clear()
    STATE.clear()
    for key in keys:
        INFLIGHT.labels(key_id=key.source.id).set(key.in_flight)
        STATE.labels(key_id=key.source.id, state=key.status).set(1)
    ELIGIBLE.set(
        sum(
            key.status == "active"
            and key.in_flight
            < (key.source.max_concurrency if key.source.max_concurrency is not None else config.default_max_concurrency)
            and (config.strategy != "single_key" or key.source.id == config.single_key_id)
            for key in keys
        )
    )
    CATALOG_AGE.set(catalog_age if catalog_age is not None else float("nan"))
    return generate_latest(REGISTRY)
