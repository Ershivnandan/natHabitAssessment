async def test_health_reports_dependency_status(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "checks" in body
    assert set(body["checks"]) == {"database", "redis"}


async def test_metrics_exposes_prometheus_counters(client):
    await client.get("/health")
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "taskflow_requests_total" in resp.text
