import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

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

def qa_link(anchor, target_url):
    results = []
    status_code, html = fetch_page(target_url)
    if status_code is None:
        return [
            ("Target URL Live", "fail", f"Could not reach: {html}"),
            ("Anchor Text on Page", "fail", "Skipped — page unreachable"),
        ]
    if status_code != 200:
        return [
            ("Target URL Live", "fail", f"HTTP {status_code}"),
            ("Anchor Text on Page", "fail", "Skipped — page returned error"),
        ]
    results.append(("Target URL Live", "pass", f"HTTP {status_code}"))
    soup = parse_soup(html)
    page_text = soup.get_text(" ", strip=True).lower()
    anchor_lower = anchor.strip().lower()
    link_texts = [a.get_text(strip=True).lower() for a in soup.find_all("a")]
    if anchor_lower in page_text:
        results.append(("Anchor Text on Page", "pass", f"\"{anchor}\" found in page text"))
    elif any(anchor_lower in lt for lt in link_texts):
        results.append(("Anchor Text on Page", "pass", f"\"{anchor}\" found in link text"))
    else:
        results.append(("Anchor Text on Page", "fail", f"\"{anchor}\" NOT found on page — verify manually"))
    return results

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
        lines.append("\nLINK BUILDING")
        lines.append("-" * 40)
        for anchor, target, checks in link_results:
            lines.append(f"\nAnchor: {anchor}")
            lines.append(f"Target: {target}")
            for label, status, detail in checks:
                lines.append(f"  {icon(status)} {label}: {detail}")
    lines.append("\n" + "=" * 60)
    fails = sum(1 for _, checks in on_page_results for _, s, _ in checks if s == "fail")
    fails += sum(1 for _, _, checks in link_results for _, s, _ in checks if s == "fail")
    warns = sum(1 for _, checks in on_page_results for _, s, _ in checks if s == "warn")
    warns += sum(1 for _, _, checks in link_results for _, s, _ in checks if s == "warn")
    if fails:
        lines.append(f"RESULT: {fails} FAIL(s), {warns} warning(s) — needs attention before closing.")
    elif warns:
        lines.append(f"RESULT: {warns} warning(s) — review before closing.")
    else:
        lines.append("RESULT: All checks passed.")
    return "\n".join(lines)

# ── UI ─────────────────────────────────────────────────────────────────────────
st.title("VDS On-Page Opts QA")
st.caption("Paste optimizations from the SEO Planning Workbook to run QA checks before closing your Teamwork task.")

month_label = st.text_input("Month / Period", placeholder="e.g. May 2026")

st.divider()
st.subheader("On-Page Optimizations")
st.caption("Paste the URLs from the On-Page rows in your planning workbook, one per line.")

onpage_input = st.text_area(
    "On-Page URLs",
    height=160,
    placeholder="https://www.herrmannservices.com/blog/why-is-my-air-conditioner-buzzing-when-it-is-off/\nhttps://www.herrmannservices.com/blog/certified-hvac-technician-career/\n...",
    label_visibility="collapsed"
)

st.divider()
st.subheader("Link Building")
st.caption("Paste anchor and target URL pairs. Use alternating format: anchor line, then URL line, repeating.")

link_format = st.radio(
    "Paste format",
    ["Alternating (anchor, URL, anchor, URL...)", "Two columns (anchors + targets separately)"],
    horizontal=True,
    label_visibility="collapsed"
)

link_pairs = []

if link_format == "Alternating (anchor, URL, anchor, URL...)":
    link_input = st.text_area(
        "Anchor + Target pairs",
        height=130,
        placeholder="water heater repair in West Chester, Ohio\nhttps://www.herrmannservices.com/west-chester-oh-furnace-airconditioner-plumbing-electrical-services/\nhvac service in Cincinnati\nhttps://www.herrmannservices.com/cincinnati-ac-repair/",
        label_visibility="collapsed"
    )
    if link_input.strip():
        raw = [l.strip() for l in link_input.strip().splitlines() if l.strip()]
        for i in range(0, len(raw) - 1, 2):
            link_pairs.append((raw[i], raw[i+1]))
else:
    lc1, lc2 = st.columns(2)
    with lc1:
        anchors_input = st.text_area("Anchor Text (one per line)", height=110, placeholder="water heater repair in West Chester, Ohio\nhvac service in Cincinnati")
    with lc2:
        targets_input = st.text_area("Target URLs (one per line, same order)", height=110, placeholder="https://www.herrmannservices.com/west-chester-oh-...\nhttps://www.herrmannservices.com/cincinnati-ac-repair/")
    if anchors_input.strip() and targets_input.strip():
        anchors = [l.strip() for l in anchors_input.strip().splitlines() if l.strip()]
        targets = [l.strip() for l in targets_input.strip().splitlines() if l.strip()]
        link_pairs = list(zip(anchors, targets))

st.divider()
run_btn = st.button("Run QA Checks", type="primary", use_container_width=True)

if run_btn:
    onpage_urls = [u.strip() for u in onpage_input.strip().splitlines() if u.strip().startswith("http")] if onpage_input.strip() else []

    if not onpage_urls and not link_pairs:
        st.warning("Paste at least one URL or link pair to run checks.")
        st.stop()

    on_page_results = []
    link_results = []

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

    if link_pairs:
        st.subheader(f"Link Building Results ({len(link_pairs)} pairs)")
        prog2 = st.progress(0, text="Checking links...")
        for i, (anchor, target) in enumerate(link_pairs):
            prog2.progress(i / len(link_pairs), text=f"Checking {i+1}/{len(link_pairs)}...")
            checks = qa_link(anchor, target)
            link_results.append((anchor, target, checks))
            st.markdown(f"**Anchor:** {anchor}")
            st.markdown(f"**Target:** {target}")
            for label, status, detail in checks:
                render_result(label, status, detail)
            st.divider()
        prog2.progress(1.0, text="Link checks complete.")

    all_statuses = [s for _, checks in on_page_results for _, s, _ in checks]
    all_statuses += [s for _, _, checks in link_results for _, s, _ in checks]
    fails = all_statuses.count("fail")
    warns = all_statuses.count("warn")

    if fails:
        st.error(f"{fails} item(s) failed QA — review before closing the Teamwork task.")
    elif warns:
        st.warning(f"{warns} warning(s) — review and confirm before closing.")
    else:
        st.success("All checks passed. Safe to close the Teamwork task.")

    st.subheader("Copy Report to Teamwork")
    report_text = results_to_text(month_label or "Not specified", on_page_results, link_results)
    st.code(report_text, language=None)
