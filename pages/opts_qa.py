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

def parse_soup(html):
    return BeautifulSoup(html, "html.parser")

def icon(status):
    return {"pass": "✅", "fail": "❌", "warn": "⚠️", "manual": "☑️"}.get(status, "•")

def has_updated_date(soup):
    patterns = [
        r'updated\s+(on\s+)?[A-Z][a-z]+\s+\d{1,2},?\s+\d{4}',
        r'last\s+updated[:\s]+[A-Z][a-z]+',
        r'updated\s+\d{1,2}/\d{1,2}/\d{2,4}',
        r'modified[:\s]+[A-Z][a-z]+',
        r'updated[:\s]+\d{4}-\d{2}-\d{2}',
    ]
    text = soup.get_text(" ", strip=True)
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return True
    for s in soup.find_all("script", type="application/ld+json"):
        if s.string and "dateModified" in s.string:
            return True
    for tag in soup.find_all("meta"):
        prop = (tag.get("property") or tag.get("name") or "").lower()
        if "modified" in prop or "updated" in prop:
            return True
    return False

def has_schema(soup):
    scripts = soup.find_all("script", type="application/ld+json")
    return len(scripts) > 0

def get_h_structure(soup):
    """Return a summary of heading hierarchy."""
    headings = []
    for tag in soup.find_all(["h1","h2","h3","h4"]):
        headings.append((tag.name, tag.get_text(strip=True)[:60]))
    return headings

def qa_onpage_url(url, checks_config):
    """
    Run automated checks on a URL.
    checks_config is a dict of which checks to run.
    Returns list of (label, status, detail).
    """
    results = []
    status_code, html = fetch_page(url)
    if status_code is None:
        return [("Page Load", "fail", f"Could not reach: {html}")]
    if status_code != 200:
        return [("Page Load", "fail", f"HTTP {status_code}")]
    results.append(("Page Load", "pass", f"HTTP {status_code}"))
    soup = parse_soup(html)

    # Always: Title tag
    title_tag = soup.find("title")
    if title_tag and title_tag.get_text(strip=True):
        t = title_tag.get_text(strip=True)
        length = len(t)
        if 30 <= length <= 65:
            results.append(("Title Tag", "pass", f"{length} chars: \"{t}\""))
        elif length > 65:
            results.append(("Title Tag", "warn", f"{length} chars (over 65): \"{t}\""))
        else:
            results.append(("Title Tag", "warn", f"Only {length} chars (under 30): \"{t}\""))
    else:
        results.append(("Title Tag", "fail", "Missing title tag"))

    # Always: Meta description
    meta_desc = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    if meta_desc and meta_desc.get("content", "").strip():
        d = meta_desc["content"].strip()
        dl = len(d)
        if 70 <= dl <= 160:
            results.append(("Meta Description", "pass", f"{dl} chars: \"{d[:80]}{'...' if dl > 80 else ''}\""))
        elif dl > 160:
            results.append(("Meta Description", "warn", f"{dl} chars (over 160): \"{d[:80]}...\""))
        else:
            results.append(("Meta Description", "warn", f"Only {dl} chars (under 70): \"{d}\""))
    else:
        results.append(("Meta Description", "fail", "Missing meta description"))

    # Always: H1
    h1_tags = soup.find_all("h1")
    if len(h1_tags) == 1:
        results.append(("H1", "pass", f"\"{h1_tags[0].get_text(strip=True)[:80]}\""))
    elif len(h1_tags) == 0:
        results.append(("H1", "fail", "No H1 found"))
    else:
        texts = " | ".join(h.get_text(strip=True)[:40] for h in h1_tags[:3])
        results.append(("H1", "warn", f"{len(h1_tags)} H1s found: {texts}"))

    # Always: Canonical
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

    # Conditional: Updated date
    if checks_config.get("updated_date"):
        if has_updated_date(soup):
            results.append(("Updated Date", "pass", "Found 'Updated On' date or dateModified signal"))
        else:
            results.append(("Updated Date", "fail", "No 'Updated On' date detected — verify manually"))

    # Conditional: Schema
    if checks_config.get("schema"):
        if has_schema(soup):
            scripts = soup.find_all("script", type="application/ld+json")
            results.append(("Schema", "pass", f"{len(scripts)} schema block(s) found"))
        else:
            results.append(("Schema", "fail", "No schema markup found"))

    # Conditional: H2/H3 hierarchy (deep touches)
    if checks_config.get("heading_hierarchy"):
        headings = get_h_structure(soup)
        h2s = [h for h in headings if h[0] == "h2"]
        h3s = [h for h in headings if h[0] == "h3"]
        if h2s:
            results.append(("H2 Structure", "pass", f"{len(h2s)} H2(s) found: {' | '.join(t for _,t in h2s[:3])}{'...' if len(h2s) > 3 else ''}"))
        else:
            results.append(("H2 Structure", "warn", "No H2 tags found — review heading hierarchy"))
        if h3s:
            results.append(("H3 Structure", "pass", f"{len(h3s)} H3(s) present"))
        else:
            results.append(("H3 Structure", "warn", "No H3 tags found"))

    # Conditional: Internal links count (deep touches)
    if checks_config.get("internal_links"):
        parsed = urlparse(url)
        domain = parsed.netloc
        all_links = soup.find_all("a", href=True)
        internal = [a for a in all_links if domain in urljoin(url, a["href"])]
        count = len(internal)
        if count >= 3:
            results.append(("Internal Links", "pass", f"{count} internal link(s) on page"))
        elif count > 0:
            results.append(("Internal Links", "warn", f"Only {count} internal link(s) — consider adding more"))
        else:
            results.append(("Internal Links", "fail", "No internal links found"))

    return results

def parse_opt_notes(notes):
    """
    Parse the notes/description from column D and return a checks config dict
    plus a list of manual checklist items.
    """
    notes_lower = notes.lower()
    checks = {
        "updated_date": False,
        "schema": False,
        "heading_hierarchy": False,
        "internal_links": False,
    }
    manual_items = []

    # Updated date / blog date
    if any(k in notes_lower for k in ["updated on", "update blog date", "blog date", "updated on date", "content revision"]):
        checks["updated_date"] = True

    # Schema
    if "schema" in notes_lower:
        checks["schema"] = True
        manual_items.append("Verify schema type is correct for this page (Article, LocalBusiness, Service, FAQ, etc.)")
        manual_items.append("Test schema using Google Rich Results Test — zero errors")

    # Deep touches / deep optimizations
    if any(k in notes_lower for k in ["deep touch", "deep opt", "deep optimization", "llm", "multi-platform"]):
        checks["schema"] = True
        checks["heading_hierarchy"] = True
        checks["internal_links"] = True
        manual_items.append("Confirm header hierarchy is logical (H1 > H2 > H3) and keyword-informed")
        manual_items.append("Verify semantic/geo keywords are naturally included in body content")
        manual_items.append("Check that internal links point to relevant money/service pages")
        manual_items.append("Confirm page is optimized for LLM visibility (clear entity signals, structured content)")

    # Core opts
    if any(k in notes_lower for k in ["core opt", "core optimization", "missing tags", "keyword/geo", "keyword geo"]):
        manual_items.append("Confirm primary keyword appears in title tag, H1, and meta description")
        manual_items.append("Verify geo target (city/region) is present in title or H1")

    # 404 / redirects
    if any(k in notes_lower for k in ["404", "redirect"]):
        manual_items.append("Confirm all previously identified 404 URLs now redirect correctly (no chains)")
        manual_items.append("Verify redirect destinations are the most relevant live pages")
        manual_items.append("Check in GSC that 404 errors are resolved")

    # Alt tags
    if any(k in notes_lower for k in ["alt tag", "alt text", "missing alt"]):
        manual_items.append("Spot-check images on the page to confirm alt text has been added")
        manual_items.append("Verify alt text is descriptive and keyword-relevant, not just filenames")

    # Navigation
    if any(k in notes_lower for k in ["navigation", "nav tab", "7 tab", "main nav"]):
        manual_items.append("Count main navigation tabs — confirm 7 or fewer")
        manual_items.append("Verify nav labels are clear and match the pages they link to")

    # Internal linking / CTA
    if any(k in notes_lower for k in ["internal link", "cta", "call to action"]):
        checks["internal_links"] = True
        manual_items.append("Confirm CTAs are present and link to relevant service/contact pages")
        manual_items.append("Verify new internal links use keyword-relevant anchor text")

    # Sitemap
    if any(k in notes_lower for k in ["sitemap", "xml sitemap"]):
        manual_items.append("Confirm sitemap was submitted to GSC")
        manual_items.append("Verify excluded URLs are no longer present in the sitemap")

    # Content revisions
    if any(k in notes_lower for k in ["content revision", "content update"]):
        manual_items.append("Confirm content has been meaningfully updated, not just date-stamped")
        manual_items.append("Verify the 'Updated On' date is visible on the page")

    return checks, manual_items

def render_auto_result(label, status, detail):
    ic = icon(status)
    if status == "pass":
        st.success(f"{ic} **{label}:** {detail}")
    elif status == "fail":
        st.error(f"{ic} **{label}:** {detail}")
    else:
        st.warning(f"{ic} **{label}:** {detail}")

def results_to_text(month, specialist, on_page_results, opt_notes, manual_items):
    lines = [
        "VDS ON-PAGE OPTS QA REPORT",
        f"Month: {month}",
        f"Specialist: {specialist or 'Not specified'}",
        f"Run: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 60,
    ]
    if opt_notes:
        lines.append(f"\nOPT NOTES: {opt_notes}")
    if manual_items:
        lines.append("\nMANUAL CHECKLIST:")
        for item in manual_items:
            lines.append(f"  ☑️ {item}")
    if on_page_results:
        lines.append("\nAUTOMATED CHECKS")
        lines.append("-" * 40)
        for url, checks in on_page_results:
            lines.append(f"\n{url}")
            for label, status, detail in checks:
                lines.append(f"  {icon(status)} {label}: {detail}")
    lines.append("\n" + "=" * 60)
    fails = sum(1 for _, checks in on_page_results for _, s, _ in checks if s == "fail")
    warns = sum(1 for _, checks in on_page_results for _, s, _ in checks if s == "warn")
    if fails:
        lines.append(f"RESULT: {fails} FAIL(s), {warns} warning(s) — needs attention before closing.")
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
    month_label = st.text_input("Month / Period", placeholder="e.g. May 2026")
with c2:
    specialist_name = st.text_input("Specialist", placeholder="e.g. Alex S.")
with c3:
    client_name = st.text_input("Client", placeholder="e.g. Herrmann Services")

st.divider()

# ── Opt Notes ─────────────────────────────────────────────────────────────────
st.subheader("Opt Description")
st.caption("Paste the notes from column D of the planning workbook. The tool will use this to tailor the checklist.")

opt_notes = st.text_area(
    "Opt notes",
    height=100,
    placeholder="e.g. Content Revisions + Add 'Updated On' date + Core Opts Refresh or Deeper Touches as-needed\nCore opts focus on addressing missing tags, aligning with primary keyword/geo targets\nDeep touches focus on multi-platform visibility (Google + LLMs)...",
    label_visibility="collapsed"
)

# Parse notes and show preview of what will be checked
if opt_notes.strip():
    checks_config, manual_items = parse_opt_notes(opt_notes)
    active_auto = []
    if checks_config.get("updated_date"): active_auto.append("Updated Date")
    if checks_config.get("schema"): active_auto.append("Schema")
    if checks_config.get("heading_hierarchy"): active_auto.append("Heading Hierarchy")
    if checks_config.get("internal_links"): active_auto.append("Internal Links")

    always = ["Page Load", "Title Tag", "Meta Description", "H1", "Canonical"]
    all_auto = always + active_auto

    st.caption(f"**Auto-checks that will run:** {', '.join(all_auto)}")
    if manual_items:
        st.caption(f"**Manual checklist items detected:** {len(manual_items)}")
else:
    checks_config = {"updated_date": False, "schema": False, "heading_hierarchy": False, "internal_links": False}
    manual_items = []

st.divider()

# ── On-Page URLs ──────────────────────────────────────────────────────────────
st.subheader("On-Page URLs")
st.caption("Paste the URLs from the On-Page rows in your planning workbook, one per line.")

onpage_input = st.text_area(
    "On-Page URLs",
    height=160,
    placeholder="https://www.herrmannservices.com/blog/why-is-my-air-conditioner-buzzing-when-it-is-off/\nhttps://www.herrmannservices.com/blog/certified-hvac-technician-career/\n...",
    label_visibility="collapsed"
)

st.divider()
run_btn = st.button("Run QA Checks", type="primary", use_container_width=True)

if run_btn:
    onpage_urls = [u.strip().strip('"').strip("'") for u in onpage_input.strip().splitlines() if u.strip().startswith("http")] if onpage_input.strip() else []

    if not onpage_urls:
        st.warning("Paste at least one URL to run checks.")
        st.stop()

    # Re-parse in case notes changed
    if opt_notes.strip():
        checks_config, manual_items = parse_opt_notes(opt_notes)
    else:
        checks_config = {"updated_date": False, "schema": False, "heading_hierarchy": False, "internal_links": False}
        manual_items = []

    # ── Manual Checklist ───────────────────────────────────────────────────────
    if manual_items:
        st.subheader("Manual Checklist")
        st.caption("Complete these items manually before closing the Teamwork task.")
        for item in manual_items:
            st.checkbox(item, key=f"manual_{item[:30]}")
        st.divider()

    # ── Auto Checks ────────────────────────────────────────────────────────────
    on_page_results = []
    st.subheader(f"Automated Checks ({len(onpage_urls)} URLs)")
    prog = st.progress(0, text="Checking pages...")

    for i, url in enumerate(onpage_urls):
        prog.progress(i / len(onpage_urls), text=f"Checking {i+1}/{len(onpage_urls)}: {url[:60]}...")
        checks = qa_onpage_url(url, checks_config)
        on_page_results.append((url, checks))
        st.markdown(f"**{url}**")
        for label, status, detail in checks:
            render_auto_result(label, status, detail)
        st.divider()

    prog.progress(1.0, text="Done.")

    # ── Summary ────────────────────────────────────────────────────────────────
    all_statuses = [s for _, checks in on_page_results for _, s, _ in checks]
    fails = all_statuses.count("fail")
    warns = all_statuses.count("warn")

    if fails:
        st.error(f"{fails} item(s) failed — review before closing the Teamwork task.")
    elif warns:
        st.warning(f"{warns} warning(s) — review and confirm before closing.")
    else:
        st.success("All automated checks passed. Complete the manual checklist above before closing.")

    # ── Report ─────────────────────────────────────────────────────────────────
    st.subheader("Copy Report to Teamwork")
    report_text = results_to_text(
        month_label or "Not specified",
        specialist_name,
        on_page_results,
        opt_notes,
        manual_items
    )
    st.code(report_text, language=None)
