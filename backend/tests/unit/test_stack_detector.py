"""Stack detector, exercises signature matching directly."""

from __future__ import annotations

from backend.app.agent.nodes.stack import detect_in_html


def test_detects_segment_and_stripe() -> None:
    html = """
    <html><head>
      <script src="https://cdn.segment.com/analytics.js/v1/abc/analytics.min.js"></script>
      <script src="https://js.stripe.com/v3/"></script>
    </head><body>x</body></html>
    """
    tools = {e.tool for e in detect_in_html(html, "https://x.com")}
    assert "Segment" in tools
    assert "Stripe" in tools


def test_meta_generator_webflow() -> None:
    html = '<html><head><meta name="generator" content="Webflow"></head></html>'
    entries = detect_in_html(html, "https://x.com")
    assert any(e.tool == "Webflow" for e in entries)


def test_no_signals_returns_empty() -> None:
    html = "<html><head><title>plain</title></head><body>nothing</body></html>"
    assert detect_in_html(html, "https://x.com") == []
