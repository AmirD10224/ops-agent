"""STACK node, infers tech stack from response headers + HTML signatures.

No paid API. Focused on signals that show up reliably in the public surface:
 - Server / X-Powered-By headers
 - Cookie-name fingerprints (Cloudflare, Shopify, HubSpot)
 - <script src> patterns (Segment, GA4, Stripe, Intercom, Plausible)
 - <meta generator>
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from selectolax.parser import HTMLParser

from backend.app.agent.runtime import RunContext
from backend.app.schemas.nodes import ScrapeResult, StackResult
from backend.app.schemas.scorecard import StackEntry
from backend.app.schemas.state import AgentState


@dataclass(frozen=True)
class Signature:
    pattern: str
    tool: str
    category: str
    method: str  # short tag we surface in detection_methods


# ---- Signatures (sorted by category for sanity) ---------------------------

_HEADER_SIGS: list[Signature] = [
    Signature(r"\bcloudflare\b", "Cloudflare", "cdn", "header:server"),
    Signature(r"\bvercel\b", "Vercel", "hosting", "header:server"),
    Signature(r"\bnetlify\b", "Netlify", "hosting", "header:server"),
    Signature(r"\bnginx\b", "Nginx", "hosting", "header:server"),
    Signature(r"\bcloudfront\b", "AWS CloudFront", "cdn", "header:via"),
    Signature(r"\bphp\b", "PHP", "language", "header:x-powered-by"),
    Signature(r"\baspnet\b|\basp\.net\b", "ASP.NET", "framework", "header:x-powered-by"),
    Signature(r"\bnext\.js\b", "Next.js", "framework", "header:x-powered-by"),
    Signature(r"\bexpress\b", "Express.js", "framework", "header:x-powered-by"),
]

_COOKIE_SIGS: list[Signature] = [
    Signature(r"__cfduid|__cf_bm", "Cloudflare", "cdn", "cookie"),
    Signature(r"_shopify_", "Shopify", "ecommerce", "cookie"),
    Signature(r"hubspotutk", "HubSpot", "marketing", "cookie"),
    Signature(r"__hssrc|__hssc", "HubSpot", "marketing", "cookie"),
    Signature(r"intercom-id|intercom-session", "Intercom", "support", "cookie"),
    Signature(r"_ga\b|_gid\b", "Google Analytics", "analytics", "cookie"),
]

_SCRIPT_SIGS: list[Signature] = [
    Signature(r"googletagmanager\.com", "Google Tag Manager", "analytics", "script"),
    Signature(r"google-analytics\.com|gtag/js", "Google Analytics", "analytics", "script"),
    Signature(r"segment\.com|cdn\.segment", "Segment", "analytics", "script"),
    Signature(r"plausible\.io", "Plausible", "analytics", "script"),
    Signature(r"mixpanel", "Mixpanel", "analytics", "script"),
    Signature(r"amplitude", "Amplitude", "analytics", "script"),
    Signature(r"posthog", "PostHog", "analytics", "script"),
    Signature(r"hs-scripts\.com|hubspot\.com/_hcms", "HubSpot", "marketing", "script"),
    Signature(r"intercomcdn\.com|intercom\.io", "Intercom", "support", "script"),
    Signature(r"crisp\.chat", "Crisp", "support", "script"),
    Signature(r"drift\.com", "Drift", "support", "script"),
    Signature(r"js\.stripe\.com", "Stripe", "payments", "script"),
    Signature(r"checkout\.shopify\.com", "Shopify", "ecommerce", "script"),
    Signature(r"snap\.licdn\.com", "LinkedIn Insight Tag", "marketing", "script"),
    Signature(r"clarity\.ms", "Microsoft Clarity", "analytics", "script"),
    Signature(r"sentry\.io", "Sentry", "monitoring", "script"),
    Signature(r"datadoghq\.com", "Datadog RUM", "monitoring", "script"),
]

_META_GENERATOR: list[Signature] = [
    Signature(r"webflow", "Webflow", "cms", "meta:generator"),
    Signature(r"wordpress", "WordPress", "cms", "meta:generator"),
    Signature(r"wix\.com", "Wix", "cms", "meta:generator"),
    Signature(r"shopify", "Shopify", "ecommerce", "meta:generator"),
    Signature(r"hubspot", "HubSpot CMS", "cms", "meta:generator"),
    Signature(r"squarespace", "Squarespace", "cms", "meta:generator"),
    Signature(r"framer", "Framer", "cms", "meta:generator"),
]


def _scan(text: str, sigs: list[Signature]) -> list[Signature]:
    return [s for s in sigs if re.search(s.pattern, text, re.IGNORECASE)]


def _extract_signals(scrape: ScrapeResult) -> tuple[list[StackEntry], set[str]]:
    hits: dict[tuple[str, str], StackEntry] = {}
    methods: set[str] = set()

    for page in scrape.pages:
        # Headers
        header_blob = " ".join(page.headers_seen.values())
        for sig in _scan(header_blob, _HEADER_SIGS):
            hits.setdefault(
                (sig.category, sig.tool),
                StackEntry(
                    category=sig.category,  # type: ignore[arg-type]
                    tool=sig.tool,
                    evidence=f"Detected via response header on {page.url}",
                    confidence=0.85,
                ),
            )
            methods.add(sig.method)

        # Cookies live inside set-cookie header value
        cookie_blob = page.headers_seen.get("set-cookie", "")
        for sig in _scan(cookie_blob, _COOKIE_SIGS):
            hits.setdefault(
                (sig.category, sig.tool),
                StackEntry(
                    category=sig.category,  # type: ignore[arg-type]
                    tool=sig.tool,
                    evidence=f"Cookie fingerprint on {page.url}",
                    confidence=0.8,
                ),
            )
            methods.add(sig.method)

        # HTML body (script srcs + meta generator)
        if not page.text:
            continue
        # Re-parse cheap: text was stripped, so we need raw markup. We didn't keep
        # raw markup on the page object to bound state size; instead rely on
        # 'text' which still contains script src tokens since we used separator=" ".
        body = page.text
        for sig in _scan(body, _SCRIPT_SIGS):
            hits.setdefault(
                (sig.category, sig.tool),
                StackEntry(
                    category=sig.category,  # type: ignore[arg-type]
                    tool=sig.tool,
                    evidence=f"Script signature on {page.url}",
                    confidence=0.75,
                ),
            )
            methods.add(sig.method)
        for sig in _scan(body, _META_GENERATOR):
            hits.setdefault(
                (sig.category, sig.tool),
                StackEntry(
                    category=sig.category,  # type: ignore[arg-type]
                    tool=sig.tool,
                    evidence=f"meta-generator on {page.url}",
                    confidence=0.9,
                ),
            )
            methods.add(sig.method)

    return list(hits.values()), methods


def detect_in_html(html: str, source_url: str = "the page") -> list[StackEntry]:
    """Direct-from-HTML detection, used by tests; uses raw markup."""
    tree = HTMLParser(html)
    blob = " ".join((n.attributes.get("src") or "") for n in tree.css("script") if n.attributes)
    blob += " " + " ".join(
        (n.attributes.get("content") or "")
        for n in tree.css('meta[name="generator"]')
        if n.attributes
    )
    out: list[StackEntry] = []
    for sig in _scan(blob, _SCRIPT_SIGS + _META_GENERATOR):
        out.append(
            StackEntry(
                category=sig.category,  # type: ignore[arg-type]
                tool=sig.tool,
                evidence=f"{sig.method} on {source_url}",
                confidence=0.8,
            )
        )
    return out


async def run_stack(state: AgentState, *, ctx: RunContext) -> dict[str, StackResult]:
    async with ctx.node("stack", summary="signature detection") as rec:
        if not state.scrape or not state.scrape.pages:
            rec.mark_skipped("no scrape data")
            return {"stack": StackResult(stack=[], detection_methods=[])}
        entries, methods = _extract_signals(state.scrape)
        # Sort: highest-confidence first, capped to 20 per scorecard schema.
        entries = sorted(entries, key=lambda e: e.confidence, reverse=True)[:20]
        rec.notes = f"{len(entries)} entries"
    return {"stack": StackResult(stack=entries, detection_methods=sorted(methods))}
