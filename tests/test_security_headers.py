def test_csp_header_present(test_app):
    r = test_app.get("/health")
    assert "Content-Security-Policy" in r.headers
    csp = r.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp

def test_existing_headers_still_present(test_app):
    r = test_app.get("/health")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
