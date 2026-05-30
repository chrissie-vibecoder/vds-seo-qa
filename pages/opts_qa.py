import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

# ── Helpers ────────────────────────────────────────────────────────────────────
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; VDS-SEO-QA/1.0)"}

@st.cache_data(show_spinner=False, ttl=300)
def fetch_page(url):
    try:
        r = requests.get(url.strip(), headers=HEADERS, timeout=15, allow_redirects=True)
        return r.status_code, r.text
    except Exception as e:
        return None, str(e)

@st.cache_data(show_spinner=False, ttl=300)
def check_redirect(url):
    try:
        r = requests.get(url.strip(), headers=HEADERS, timeout=15, allow_redirects=True)
        final = r.url.rstrip("/")
        original = url.strip().rstrip("/")
        hops = len(r.history)
        return r.status_code, final, hops
    except Exception as e:
        return None, str(e), 0

def parse_soup(html):
    return BeautifulSoup(html, "html.parser")

def icon(status):
    return {"pass": "✅", "fail": "❌", "warn": "⚠️"}.get(status, "•")

def find_updated_date_text(soup):
    """Return the actual text snippet containing the updated date, or None."""
    patterns = [
        r'(updated\s+on\s+[A-Z][a-z]+\s+\d{1,2},?\s+\d{4})',
        r'(last\s+updated[:\s]+[A-Z][a-z]+\s+\d{1,2},?\s+\d{4})',
        r'(updated\s+\d{1,2}/\d{1,2}/\d{2,4})',
        r'(updated[:\s]+\d{4}-\d{2}-\d{2})',
        r'(modified[:\s]+[A-Z][a-z]+\s+\d{1,2},?\s+\d{4})',
    ]
    text = soup.get_text(" ", strip=True)
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    # Check schema for dateModified
    for s in soup.find_all("script", type="application/ld+json"):
        if s.string and "dateModified" in s.string:
            m = re.search(r'"dateModified"\s*:\s*"([^"]+)"', s.string)
            if m:
                return f"dateModified in schema: {m.group(1)}"
    # Check meta tags
    for tag in soup.find_all("meta"):
        prop = (tag.get("property") or tag.get("name") or "").lower()
        if "modified" in prop or "updated" in prop:
            val = tag.get("content", "")
            if val:
                return f"{prop} meta: {val}"
    return None

def get_schema_types(soup):
    """Return list of schema @type values found on page."""
    import json
    types = []
    for s in soup.find_all("script", type="application/ld+json"):
        if s.string:
            try:
                data = json.loads(s.string)
                if isinstance(data, dict):
                    t = data.get("@type")
                    if t:
                        types.append(t if isinstance(t, str) else ", ".join(t))
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            t = item.get("@type")
                            if t:
                                types.append(t if isinstance(t, str) else ", ".join(t))
            except:
                pass
    return types

def validate_heading_hierarchy(soup):
    """
    Check heading hierarchy. Returns list of (label, status, detail) results.
    """
    results = []
    headings = [(tag.name, tag.get_text(strip=True)) for tag in soup.find_all(["h1","h2","h3","h4"])]

    h1s = [h for h in headings if h[0] == "h1"]
    h2s = [h for h in headings if h[0] == "h2"]
    h3s = [h for h in headings if h[0] == "h3"]

    # H1 count
    if len(h1s) == 1:
        results.append(("H1", "pass", f"\"{h1s[0][1][:80]}\""))
    elif len(h1s) == 0:
        results.append(("H1", "fail", "No H1 found"))
    else:
        results.append(("H1", "warn", f"{len(h1s)} H1s found: {'; '.join(h[1][:40] for h in h1s)}"))

    # H2s
    if h2s:
        results.append(("H2s", "pass", "; ".join(h[1][:50] for h in h2s)))
    else:
        results.append(("H2s", "warn", "No H2 tags found"))

    # H3s
    if h3s:
        results.append(("H3s", "pass", "; ".join(h[1][:50] for h in h3s)))
    else:
        results.append(("H3s", "warn", "No H3 tags found"))

    # Hierarchy violations
    violations = []
    level_map = {"h1": 1, "h2": 2, "h3": 3, "h4": 4}
    prev_level = 0
    for tag_name, text in headings:
        level = level_map.get(tag_name, 0)
        if prev_level > 0 and level > prev_level + 1:
            violations.append(f"Jumps from H{prev_level} to H{level}: \"{text[:40]}\"")
        prev_level = level

    if violations:
        results.append(("Hierarchy", "warn", "Skipped levels: " + "; ".join(violations)))
    else:
        results.append(("Hierarchy", "pass", "Heading order is logical — no skipped levels"))

    return results

def qa_onpage_url(url, checks_config, primary_keyword=""):
    results = []
    status_code, html = fetch_page(url)
    if status_code is None:
        return [("Page Load", "fail", f"Could not reach: {html}")]
    if status_code != 200:
        return [("Page Load", "fail", f"HTTP {status_code}")]
    results.append(("Page Load", "pass", f"HTTP {status_code}"))
    soup = parse_soup(html)
    parsed = urlparse(url)
    domain = parsed.netloc

    # Title tag
    title_text = ""
    title_tag = soup.find("title")
    if title_tag and title_tag.get_text(strip=True):
        title_text = title_tag.get_text(strip=True)
        length = len(title_text)
        if 30 <= length <= 65:
            results.append(("Title Tag", "pass", f"{length} chars: \"{title_text}\""))
        elif length > 65:
            results.append(("Title Tag", "warn", f"{length} chars (over 65): \"{title_text}\""))
        else:
            results.append(("Title Tag", "warn", f"Only {length} chars (under 30): \"{title_text}\""))
    else:
        results.append(("Title Tag", "fail", "Missing title tag"))

    # Meta description
    meta_text = ""
    meta_desc = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    if meta_desc and meta_desc.get("content", "").strip():
        meta_text = meta_desc["content"].strip()
        dl = len(meta_text)
        if 70 <= dl <= 160:
            results.append(("Meta Description", "pass", f"{dl} chars: \"{meta_text[:80]}{'...' if dl > 80 else ''}\""))
        elif dl > 160:
            results.append(("Meta Description", "warn", f"{dl} chars (over 160): \"{meta_text[:80]}...\""))
        else:
            results.append(("Meta Description", "warn", f"Only {dl} chars (under 70): \"{meta_text}\""))
    else:
        results.append(("Meta Description", "fail", "Missing meta description"))

    # Canonical
    canonical = soup.find("link", rel="canonical")
    if canonical and canonical.get("href"):
        href = canonical["href"].strip().rstrip("/")
        page_url = url.strip().rstrip("/")
        if href == page_url or href == page_url.replace("https://", "http://"):
            results.append(("Canonical", "pass", href))
        else:
            results.append(("Canonical", "warn", f"Points elsewhere: {href}"))
    else:
        results.append(("Canonical", "warn", "No canonical tag found"))

    # Primary keyword check
    if primary_keyword.strip():
        kw = primary_keyword.strip().lower()
        hits = []
        if kw in title_text.lower(): hits.append("Title")
        h1_tags = soup.find_all("h1")
        if any(kw in h.get_text(strip=True).lower() for h in h1_tags): hits.append("H1")
        if kw in meta_text.lower(): hits.append("Meta Description")
        missing = [f for f in ["Title", "H1", "Meta Description"] if f not in hits]
        if not missing:
            results.append(("Primary Keyword", "pass", f"\"{primary_keyword}\" found in: {', '.join(hits)}"))
        elif hits:
            results.append(("Primary Keyword", "warn", f"\"{primary_keyword}\" found in {', '.join(hits)} but missing from: {', '.join(missing)}"))
        else:
            results.append(("Primary Keyword", "fail", f"\"{primary_keyword}\" not found in Title, H1, or Meta Description"))

    # Heading hierarchy
    heading_results = validate_heading_hierarchy(soup)
    results.extend(heading_results)

    # Updated date
    if checks_config.get("updated_date"):
        snippet = find_updated_date_text(soup)
        if snippet:
            results.append(("Updated Date", "pass", snippet))
        else:
            results.append(("Updated Date", "fail", "No 'Updated On' date detected — add or verify manually"))

    # Schema
    if checks_config.get("schema"):
        schema_types = get_schema_types(soup)
        if schema_types:
            results.append(("Schema", "pass", f"Types found: {', '.join(schema_types)}"))
        else:
            results.append(("Schema", "fail", "No schema markup found"))

    # Internal links
    if checks_config.get("internal_links"):
        all_links = soup.find_all("a", href=True)
        internal = []
        for a in all_links:
            href = a.get("href", "")
            full = urljoin(url, href)
            if urlparse(full).netloc == domain and not href.startswith("#"):
                text = a.get_text(strip=True)
                if text:
                    internal.append(f"\"{text[:40]}\" → {full[:60]}")
        if len(internal) >= 3:
            results.append(("Internal Links", "pass", f"{len(internal)} found: " + "; ".join(internal[:5]) + ("..." if len(internal) > 5 else "")))
        elif len(internal) > 0:
            results.append(("Internal Links", "warn", f"Only {len(internal)}: " + "; ".join(internal)))
        else:
            results.append(("Internal Links", "fail", "No internal links found"))

    # Alt text audit
    if checks_config.get("alt_text"):
        imgs = soup.find_all("img")
        missing_alt = [img for img in imgs if not img.get("alt", "").strip()]
        total = len(imgs)
        if total == 0:
            results.append(("Alt Text", "warn", "No images found on page"))
        elif not missing_alt:
            results.append(("Alt Text", "pass", f"All {total} image(s) have alt text"))
        else:
            srcs = "; ".join((img.get("src","")[:40] or "unknown") for img in missing_alt[:3])
            results.append(("Alt Text", "fail", f"{len(missing_alt)}/{total} image(s) missing alt text: {srcs}{'...' if len(missing_alt) > 3 else ''}"))

    # Nav tab count
    if checks_config.get("nav_count"):
        nav = soup.find("nav")
        if nav:
            top_links = [a for a in nav.find_all("a", href=True) if a.get_text(strip=True)]
            # Try to get only top-level items
            count = len(top_links)
            if count <= 7:
                results.append(("Nav Tabs", "pass", f"{count} nav link(s) found — within limit"))
            else:
                results.append(("Nav Tabs", "warn", f"{count} nav link(s) found — consider reducing to 7 or fewer"))
        else:
            results.append(("Nav Tabs", "warn", "No <nav> element found — check manually"))

    return results

def check_redirects_auto(urls):
    """Check a list of URLs for redirect status. Returns list of (url, status, detail)."""
    results = []
    for url in urls:
        code, final, hops = check_redirect(url)
        if code is None:
            results.append((url, "fail", f"Could not reach: {final}"))
        elif code == 200 and hops == 0:
            results.append((url, "pass", "Returns 200 directly"))
        elif code == 200 and hops == 1:
            results.append((url, "pass", f"Redirects cleanly to: {final}"))
        elif code == 200 and hops > 1:
            results.append((url, "warn", f"Redirect chain ({hops} hops) → {final}"))
        elif code in (301, 302):
            results.append((url, "warn", f"HTTP {code} — still redirecting, not resolving to 200"))
        else:
            results.append((url, "fail", f"HTTP {code} — not resolving correctly"))
    return results

def parse_opt_notes(notes):
    notes_lower = notes.lower()
    checks = {
        "updated_date": False,
        "schema": False,
        "internal_links": False,
        "alt_text": False,
        "nav_count": False,
    }
    manual_items = []
    redirect_urls = []

    if any(k in notes_lower for k in ["updated on", "update blog date", "blog date", "updated on date", "content revision"]):
        checks["updated_date"] = True

    if "schema" in notes_lower:
        checks["schema"] = True
        manual_items.append("Test schema using Google Rich Results Test — zero errors")
        manual_items.append("Confirm schema type matches the page purpose")

    if any(k in notes_lower for k in ["deep touch", "deep opt", "deep optimization", "llm", "multi-platform"]):
        checks["schema"] = True
        checks["internal_links"] = True
        manual_items.append("Verify semantic/geo keywords are naturally included in body content")
        manual_items.append("Confirm page is optimized for LLM visibility (clear entity signals, structured content)")

    if any(k in notes_lower for k in ["core opt", "core optimization", "missing tags", "keyword/geo", "keyword geo"]):
        manual_items.append("Verify geo target (city/region) is present in title or H1")

    if any(k in notes_lower for k in ["404", "redirect"]):
        manual_items.append("Paste any specific 404 URLs into the Redirect Checker below")

    if any(k in notes_lower for k in ["alt tag", "alt text", "missing alt"]):
        checks["alt_text"] = True

    if any(k in notes_lower for k in ["navigation", "nav tab", "7 tab", "main nav"]):
        checks["nav_count"] = True

    if any(k in notes_lower for k in ["internal link", "cta", "call to action"]):
        checks["internal_links"] = True
        manual_items.append("Confirm CTAs are present and link to relevant service/contact pages")

    if any(k in notes_lower for k in ["sitemap", "xml sitemap"]):
        manual_items.append("Confirm sitemap was submitted to GSC")
        manual_items.append("Verify excluded URLs are no longer present in the sitemap")

    if any(k in notes_lower for k in ["content revision", "content update"]):
        manual_items.append("Confirm content has been meaningfully updated, not just date-stamped")

    if any(k in notes_lower for k in ["gsc", "google search console", "search console"]):
        manual_items.append("Review GSC data — confirm impressions/clicks trending correctly")

    return checks, manual_items

def render_auto_result(label, status, detail):
    ic = icon(status)
    if status == "pass":
        st.success(f"{ic} **{label}:** {detail}")
    elif status == "fail":
        st.error(f"{ic} **{label}:** {detail}")
    else:
        st.warning(f"{ic} **{label}:** {detail}")

def results_to_text(month, specialist, client, on_page_results, opt_notes, manual_items, redirect_results, primary_keyword):
    lines = [
        "VDS ON-PAGE OPTS QA REPORT",
        f"Client: {client or 'Not specified'}",
        f"Month: {month or 'Not specified'}",
        f"Specialist: {specialist or 'Not specified'}",
        f"Run: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 60,
    ]
    if opt_notes:
        lines.append(f"\nOPT NOTES:\n{opt_notes}")
    if primary_keyword:
        lines.append(f"\nPrimary Keyword: {primary_keyword}")
    if manual_items:
        lines.append("\nMANUAL CHECKLIST:")
        for item in manual_items:
            lines.append(f"  ☑️ {item}")
    if redirect_results:
        lines.append("\nREDIRECT CHECKS")
        lines.append("-" * 40)
        for url, status, detail in redirect_results:
            lines.append(f"  {icon(status)} {url}")
            lines.append(f"     {detail}")
    if on_page_results:
        lines.append("\nAUTOMATED PAGE CHECKS")
        lines.append("-" * 40)
        for url, checks in on_page_results:
            lines.append(f"\n{url}")
            for label, status, detail in checks:
                lines.append(f"  {icon(status)} {label}: {detail}")
    lines.append("\n" + "=" * 60)
    fails = sum(1 for _, checks in on_page_results for _, s, _ in checks if s == "fail")
    warns = sum(1 for _, checks in on_page_results for _, s, _ in checks if s == "warn")
    redirect_fails = sum(1 for _, s, _ in redirect_results if s == "fail")
    total_fails = fails + redirect_fails
    if total_fails:
        lines.append(f"RESULT: {total_fails} FAIL(s), {warns} warning(s) — needs attention before closing.")
    elif warns:
        lines.append(f"RESULT: {warns} warning(s) — review before closing.")
    else:
        lines.append("RESULT: All automated checks passed. Complete manual checklist before closing.")
    return "\n".join(lines)

# ── UI ─────────────────────────────────────────────────────────────────────────
st.title("VDS On-Page Opts QA")
st.caption("Paste optimizations from the SEO Planning Workbook to run QA checks before closing your Teamwork task.")

c1, c2, c3 = st.columns([2, 1, 1])
with c1:
    client_name = st.text_input("Client", placeholder="e.g. Herrmann Services")
with c2:
    month_label = st.text_input("Month / Period", placeholder="e.g. May 2026")
with c3:
    specialist_name = st.text_input("Specialist", placeholder="e.g. Alex S.")

st.divider()

st.subheader("Opt Description")
st.caption("Paste the notes from column D of the planning workbook. The tool will use this to tailor the checklist.")

opt_notes = st.text_area(
    "Opt notes",
    height=100,
    placeholder="e.g. Content Revisions + Add 'Updated On' date + Core Opts Refresh or Deeper Touches as-needed...",
    label_visibility="collapsed"
)

primary_keyword = st.text_input(
    "Primary keyword (optional)",
    placeholder="e.g. AC repair Cincinnati — if entered, the tool checks for it in Title, H1, and Meta Description"
)

if opt_notes.strip():
    checks_config, manual_items = parse_opt_notes(opt_notes)
    always = ["Page Load", "Title Tag", "Meta Description", "Canonical", "Heading Hierarchy"]
    active_auto = []
    if primary_keyword.strip(): active_auto.append("Primary Keyword")
    if checks_config.get("updated_date"): active_auto.append("Updated Date")
    if checks_config.get("schema"): active_auto.append("Schema")
    if checks_config.get("internal_links"): active_auto.append("Internal Links")
    if checks_config.get("alt_text"): active_auto.append("Alt Text")
    if checks_config.get("nav_count"): active_auto.append("Nav Tab Count")
    st.caption(f"**Auto-checks that will run:** {', '.join(always + active_auto)}")
    if manual_items:
        st.caption(f"**Manual checklist items:** {len(manual_items)}")
else:
    checks_config = {"updated_date": False, "schema": False, "internal_links": False, "alt_text": False, "nav_count": False}
    manual_items = []

st.divider()

st.subheader("On-Page URLs")
st.caption("Paste the URLs from the On-Page rows in your planning workbook, one per line.")

onpage_input = st.text_area(
    "On-Page URLs",
    height=160,
    placeholder="https://www.herrmannservices.com/blog/why-is-my-air-conditioner-buzzing-when-it-is-off/\nhttps://www.herrmannservices.com/blog/certified-hvac-technician-career/",
    label_visibility="collapsed"
)

st.divider()

st.subheader("Redirect Checker (optional)")
st.caption("If the opt notes mention 404s or redirects, paste those URLs here to verify they resolve correctly.")

redirect_input = st.text_area(
    "URLs to check for redirects",
    height=100,
    placeholder="https://www.herrmannservices.com/old-broken-page/\nhttps://www.herrmannservices.com/another-404/",
    label_visibility="collapsed"
)

st.divider()
run_btn = st.button("Run QA Checks", type="primary", use_container_width=True)

if run_btn:
    onpage_urls = [u.strip().strip('"').strip("'") for u in onpage_input.strip().splitlines() if u.strip().startswith("http")] if onpage_input.strip() else []
    redirect_urls = [u.strip().strip('"').strip("'") for u in redirect_input.strip().splitlines() if u.strip().startswith("http")] if redirect_input.strip() else []

    if not onpage_urls and not redirect_urls:
        st.warning("Paste at least one URL to run checks.")
        st.stop()

    if opt_notes.strip():
        checks_config, manual_items = parse_opt_notes(opt_notes)
    else:
        checks_config = {"updated_date": False, "schema": False, "internal_links": False, "alt_text": False, "nav_count": False}
        manual_items = []

    redirect_results = []

    # Redirect checks
    if redirect_urls:
        st.subheader(f"Redirect Results ({len(redirect_urls)} URLs)")
        prog_r = st.progress(0, text="Checking redirects...")
        redirect_results = []
        for i, url in enumerate(redirect_urls):
            prog_r.progress(i / len(redirect_urls), text=f"Checking {i+1}/{len(redirect_urls)}...")
            code, final, hops = check_redirect(url)
            if code is None:
                redirect_results.append((url, "fail", f"Could not reach: {final}"))
            elif code == 200 and hops == 0:
                redirect_results.append((url, "pass", "Returns 200 directly"))
            elif code == 200 and hops == 1:
                redirect_results.append((url, "pass", f"Redirects cleanly to: {final}"))
            elif code == 200 and hops > 1:
                redirect_results.append((url, "warn", f"Redirect chain ({hops} hops) to: {final}"))
            else:
                redirect_results.append((url, "fail", f"HTTP {code} — not resolving correctly"))
            st.markdown(f"**{url}**")
            render_auto_result("Redirect", redirect_results[-1][1], redirect_results[-1][2])
            st.divider()
        prog_r.progress(1.0, text="Redirect checks complete.")

    # Manual checklist
    if manual_items:
        st.subheader("Manual Checklist")
        st.caption("Complete these items manually before closing the Teamwork task.")
        for item in manual_items:
            st.checkbox(item, key=f"manual_{item[:40]}")
        st.divider()

    # Auto page checks
    on_page_results = []
    if onpage_urls:
        st.subheader(f"Automated Page Checks ({len(onpage_urls)} URLs)")
        prog = st.progress(0, text="Checking pages...")
        for i, url in enumerate(onpage_urls):
            prog.progress(i / len(onpage_urls), text=f"Checking {i+1}/{len(onpage_urls)}: {url[:60]}...")
            checks = qa_onpage_url(url, checks_config, primary_keyword)
            on_page_results.append((url, checks))
            st.markdown(f"**{url}**")
            for label, status, detail in checks:
                render_auto_result(label, status, detail)
            st.divider()
        prog.progress(1.0, text="Done.")

    # Summary
    all_statuses = [s for _, checks in on_page_results for _, s, _ in checks]
    all_statuses += [s for _, s, _ in redirect_results]
    fails = all_statuses.count("fail")
    warns = all_statuses.count("warn")

    if fails:
        st.error(f"{fails} item(s) failed — review before closing the Teamwork task.")
    elif warns:
        st.warning(f"{warns} warning(s) — review and confirm before closing.")
    else:
        st.success("All automated checks passed. Complete the manual checklist above before closing.")

    st.subheader("Copy Report to Teamwork")
    report_text = results_to_text(
        month_label, specialist_name, client_name,
        on_page_results, opt_notes, manual_items,
        redirect_results, primary_keyword
    )
    st.code(report_text, language=None)
