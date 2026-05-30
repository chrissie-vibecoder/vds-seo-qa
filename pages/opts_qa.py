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
    return {"pass": "✅", "fail": "❌", "warn": "⚠️"}.get(status, "•")

def normalize_url(url):
    return url.strip().rstrip("/").lower()

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

def qa_onpage_url(url):
    results = []
    status_code, html = fetch_page(url)
    if status_code is None:
        return [("Page Load", "fail", f"Could not reach: {html}")]
    if status_code != 200:
        return [("Page Load", "fail", f"HTTP {status_code}")]
    results.append(("Page Load", "pass", f"HTTP {status_code}"))
    soup = parse_soup(html)

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

    h1_tags = soup.find_all("h1")
    if len(h1_tags) == 1:
        results.append(("H1", "pass", f"\"{h1_tags[0].get_text(strip=True)[:80]}\""))
    elif len(h1_tags) == 0:
        results.append(("H1", "fail", "No H1 found"))
    else:
        texts = " | ".join(h.get_text(strip=True)[:40] for h in h1_tags[:3])
        results.append(("H1", "warn", f"{len(h1_tags)} H1s found: {texts}"))

    if has_updated_date(soup):
        results.append(("Updated Date", "pass", "Found 'Updated On' date or dateModified signal"))
    else:
        results.append(("Updated Date", "fail", "No 'Updated On' date detected — verify manually"))

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

    return results

def crawl_for_internal_link(base_url, anchor_text, target_url, max_pages, progress_callback=None):
    """
    Crawl the site starting from base_url.
    Find all pages where anchor_text appears as link text pointing to target_url.
    Returns: (found_instances, pages_checked, pages_with_wrong_target)
    """
    parsed_base = urlparse(base_url)
    domain = parsed_base.scheme + "://" + parsed_base.netloc

    visited = set()
    to_visit = [base_url]
    found_instances = []      # (source_page, href) where anchor matches and target matches
    wrong_target = []         # (source_page, actual_href) where anchor matches but target wrong
    pages_checked = 0

    anchor_lower = anchor_text.strip().lower()
    target_normalized = normalize_url(target_url)

    while to_visit and pages_checked < max_pages:
        url = to_visit.pop(0)
        if normalize_url(url) in visited:
            continue
        visited.add(normalize_url(url))

        status_code, html = fetch_page(url)
        if status_code != 200 or not html:
            continue

        pages_checked += 1
        if progress_callback:
            progress_callback(pages_checked, url)

        soup = parse_soup(html)

        # Check all links on this page
        for a_tag in soup.find_all("a", href=True):
            link_text = a_tag.get_text(strip=True).lower()
            if anchor_lower in link_text:
                href = a_tag["href"]
                full_href = urljoin(url, href).rstrip("/")
                if normalize_url(full_href) == target_normalized:
                    found_instances.append((url, full_href))
                else:
                    # Anchor text matches but points somewhere else
                    if urlparse(full_href).netloc == parsed_base.netloc:
                        wrong_target.append((url, full_href))

        # Collect internal links to crawl
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            full = urljoin(url, href)
            parsed = urlparse(full)
            if parsed.netloc == parsed_base.netloc and parsed.scheme in ("http", "https"):
                clean = full.split("#")[0].split("?")[0]
                if normalize_url(clean) not in visited and clean not in to_visit:
                    # Skip admin, feed, wp-, sitemap paths
                    skip_patterns = ["/wp-admin", "/feed", "/wp-json", "xmlrpc", "sitemap"]
                    if not any(p in clean for p in skip_patterns):
                        to_visit.append(clean)

    return found_instances, pages_checked, wrong_target

def render_result(label, status, detail):
    ic = icon(status)
    if status == "pass":
        st.success(f"{ic} **{label}:** {detail}")
    elif status == "fail":
        st.error(f"{ic} **{label}:** {detail}")
    else:
        st.warning(f"{ic} **{label}:** {detail}")

def results_to_text(month, on_page_results, link_results):
    lines = [
        "VDS ON-PAGE OPTS QA REPORT",
        f"Month: {month}",
        f"Run: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 60,
    ]
    if on_page_results:
        lines.append("\nON-PAGE OPTIMIZATIONS")
        lines.append("-" * 40)
        for url, checks in on_page_results:
            lines.append(f"\n{url}")
            for label, status, detail in checks:
                lines.append(f"  {icon(status)} {label}: {detail}")
    if link_results:
        lines.append("\nLINK BUILDING (Internal Link Audit)")
        lines.append("-" * 40)
        for anchor, target, pages_checked, found, wrong in link_results:
            lines.append(f"\nAnchor: \"{anchor}\"")
            lines.append(f"Target: {target}")
            lines.append(f"Pages crawled: {pages_checked}")
            if found:
                lines.append(f"Found on {len(found)} page(s):")
                for src, href in found:
                    lines.append(f"  ✅ {src}")
            else:
                lines.append("  ❌ Not found on any crawled page")
            if wrong:
                lines.append(f"Anchor found but pointing to wrong target on {len(wrong)} page(s):")
                for src, href in wrong:
                    lines.append(f"  ⚠️ {src} -> {href}")
    lines.append("\n" + "=" * 60)
    return "\n".join(lines)

# ── UI ─────────────────────────────────────────────────────────────────────────
st.title("VDS On-Page Opts QA")
st.caption("Paste optimizations from the SEO Planning Workbook to run QA checks before closing your Teamwork task.")

month_label = st.text_input("Month / Period", placeholder="e.g. May 2026")

st.divider()

# ── On-Page Section ────────────────────────────────────────────────────────────
st.subheader("On-Page Optimizations")
st.caption("Paste the URLs from the On-Page rows in your planning workbook, one per line.")

onpage_input = st.text_area(
    "On-Page URLs",
    height=160,
    placeholder="https://www.herrmannservices.com/blog/why-is-my-air-conditioner-buzzing-when-it-is-off/\nhttps://www.herrmannservices.com/blog/certified-hvac-technician-career/\n...",
    label_visibility="collapsed"
)

st.divider()

# ── Link Building Section ──────────────────────────────────────────────────────
st.subheader("Link Building — Internal Link Audit")
st.caption("Enter the site to crawl, then paste anchor text and target URL pairs. The tool will crawl the site and find every page where each anchor links to the correct target.")

site_to_crawl = st.text_input(
    "Site base URL to crawl",
    placeholder="https://www.herrmannservices.com"
)

max_pages = st.slider("Max pages to crawl", min_value=10, max_value=200, value=50, step=10)

st.caption("Paste anchor and target URL pairs below, alternating: anchor line, then target URL line.")

link_input = st.text_area(
    "Anchor + Target pairs",
    height=130,
    placeholder="water heater repair in West Chester, Ohio\nhttps://www.herrmannservices.com/west-chester-oh-furnace-airconditioner-plumbing-electrical-services/\nhvac service in Cincinnati\nhttps://www.herrmannservices.com/cincinnati-ac-repair/",
    label_visibility="collapsed"
)

link_pairs = []
if link_input.strip():
    raw = [l.strip() for l in link_input.strip().splitlines() if l.strip()]
    for i in range(0, len(raw) - 1, 2):
        link_pairs.append((raw[i], raw[i+1]))

st.divider()
run_btn = st.button("Run QA Checks", type="primary", use_container_width=True)

if run_btn:
    onpage_urls = [u.strip() for u in onpage_input.strip().splitlines() if u.strip().startswith("http")] if onpage_input.strip() else []

    if not onpage_urls and not link_pairs:
        st.warning("Paste at least one URL or link pair to run checks.")
        st.stop()

    on_page_results = []
    link_results = []

    # ── On-Page Checks ─────────────────────────────────────────────────────────
    if onpage_urls:
        st.subheader(f"On-Page Results ({len(onpage_urls)} URLs)")
        prog = st.progress(0, text="Checking pages...")
        for i, url in enumerate(onpage_urls):
            prog.progress(i / len(onpage_urls), text=f"Checking {i+1}/{len(onpage_urls)}: {url[:60]}...")
            checks = qa_onpage_url(url)
            on_page_results.append((url, checks))
            st.markdown(f"**{url}**")
            for label, status, detail in checks:
                render_result(label, status, detail)
            st.divider()
        prog.progress(1.0, text="On-page checks complete.")

    # ── Link Building Crawl ────────────────────────────────────────────────────
    if link_pairs and site_to_crawl.strip():
        st.subheader("Link Building Results")
        st.info(f"Crawling up to {max_pages} pages on {site_to_crawl} — this may take a minute.")

        crawl_status = st.empty()
        prog_link = st.progress(0, text="Starting crawl...")

        # We crawl once and check all anchors against the same crawled pages
        # For efficiency, crawl per anchor/target pair
        for anchor, target in link_pairs:
            st.markdown(f"**Anchor:** \"{anchor}\"")
            st.markdown(f"**Target:** {target}")

            pages_checked_count = [0]
            status_placeholder = st.empty()

            def update_progress(count, current_url):
                pages_checked_count[0] = count
                prog_link.progress(
                    min(count / max_pages, 1.0),
                    text=f"Crawling page {count}/{max_pages}: {current_url[:60]}..."
                )
                status_placeholder.caption(f"Last checked: {current_url}")

            found, pages_checked, wrong = crawl_for_internal_link(
                site_to_crawl.strip(),
                anchor,
                target,
                max_pages,
                progress_callback=update_progress
            )

            link_results.append((anchor, target, pages_checked, found, wrong))
            status_placeholder.empty()

            if found:
                st.success(f"✅ Found on {len(found)} page(s):")
                for src, href in found:
                    st.markdown(f"- {src}")
            else:
                st.error("❌ Not found on any crawled page — link may not be placed yet or anchor text doesn't match exactly.")

            if wrong:
                st.warning(f"⚠️ Anchor text found on {len(wrong)} page(s) but pointing to a different target:")
                for src, href in wrong:
                    st.markdown(f"- {src} points to: {href}")

            st.caption(f"{pages_checked} pages crawled")
            st.divider()

        prog_link.progress(1.0, text="Crawl complete.")

    elif link_pairs and not site_to_crawl.strip():
        st.warning("Enter a site base URL to crawl for the link building check.")

    # ── Summary ────────────────────────────────────────────────────────────────
    all_statuses = [s for _, checks in on_page_results for _, s, _ in checks]
    fails = all_statuses.count("fail")
    warns = all_statuses.count("warn")

    if on_page_results:
        if fails:
            st.error(f"{fails} on-page item(s) failed QA — review before closing the Teamwork task.")
        elif warns:
            st.warning(f"{warns} on-page warning(s) — review and confirm before closing.")
        else:
            st.success("All on-page checks passed.")

    # ── Report ─────────────────────────────────────────────────────────────────
    if on_page_results or link_results:
        st.subheader("Copy Report to Teamwork")
        report_text = results_to_text(month_label or "Not specified", on_page_results, link_results)
        st.code(report_text, language=None)
