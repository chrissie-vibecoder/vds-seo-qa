import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import json
from urllib.parse import urlparse, urljoin

# ─── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="VDS Organic SEO QA Tool",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Montserrat', sans-serif; }

.vds-header {
    background-color: #E21B23;
    padding: 22px 30px;
    border-radius: 8px;
    margin-bottom: 24px;
    color: white;
}
.vds-header h1 { color: white; margin: 0; font-size: 22px; font-weight: 700; }
.vds-header p  { color: rgba(255,255,255,0.85); margin: 4px 0 0; font-size: 13px; }

.section-header {
    background: #2d2d2d;
    color: white;
    padding: 8px 14px;
    border-radius: 5px;
    font-weight: 600;
    font-size: 13px;
    margin: 14px 0 6px;
}
.manual-tag { color: #888; font-size: 12px; font-style: italic; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="vds-header">
    <h1>VDS Organic SEO — QA Tool</h1>
    <p>Complete your QA pass and generate a report before closing your Teamwork task.</p>
</div>
""", unsafe_allow_html=True)

# ─── Data: Optimizations ───────────────────────────────────────────────────────
OPTIMIZATIONS = {
    "Core SEO": [
        "Title Tag",
        "Meta Description",
    ],
    "Technical SEO": [
        "Robots.txt Check",
        "AIO AI Crawler Directives",
        "LLMs.txt Check",
        "XML Sitemaps",
        "Canonical Tags",
        "URL Hygiene & Indexing",
        "Page Speed Analysis",
        "Internal Links to Redirects",
        "NAP Information",
        "Indexation Audits",
        "Backlink QA & Analysis",
        "Disavow Spammy Backlinks",
        "Caching Plugin (WP Rocket / LiteSpeed)",
        "Image Compression (Imagify)",
        "Fixed 404s & Broken URLs",
        "New Page / URL Created",
    ],
    "On-Page Content": [
        "Metadata & Heading Structure",
        "H1 Tag",
        "H2 / H3 / H4 Tags",
        "Image Alt Text & Optimization",
        "Internal Linking & Anchor Text",
        "External Linking",
        "Schema Markup",
        "Social Metadata (OG & Twitter)",
        "Google Maps Embedding",
        "YouTube Video Embedding",
        "Section Design & FAQ Content",
        "TOC (Table of Contents)",
        "Formatting, Structure & Layout",
    ],
    "AIO / Deep": [
        "TLDR / AI Takeaways",
        "Content Reformatting",
        "LSI Keywords",
        "Geo Keywords",
    ],
    "Content Production (CP)": [
        "Brand Integrity",
        "Geo-Targeting & Service Areas",
        "Service & Product Accuracy",
        "CTA Structure & Alignment",
        "Website & Guide Consistency",
        "Grammar, Syntax & Polish",
    ],
    "Off-Site": [
        "YouTube Channel Optimization",
    ],
}

# Items with NO auto-check (guided only)
MANUAL_ONLY = {
    "TLDR / AI Takeaways",
    "Content Reformatting",
    "LSI Keywords",
    "Geo Keywords",
    "Brand Integrity",
    "Geo-Targeting & Service Areas",
    "Service & Product Accuracy",
    "CTA Structure & Alignment",
    "Website & Guide Consistency",
    "Grammar, Syntax & Polish",
    "YouTube Channel Optimization",
    "Backlink QA & Analysis",
    "Disavow Spammy Backlinks",
    "Indexation Audits",
    "Formatting, Structure & Layout",
}

# Guided checklist questions per optimization
GUIDED_QUESTIONS = {
    "Title Tag": [
        "Primary keyword and geo target (if applicable) are included",
        "Brand name is appended at the end",
    ],
    "Meta Description": [
        "Primary keyword and geo target (if applicable) are present",
        "A clear CTA is included",
        "Description accurately summarizes the page purpose",
    ],
    "H1 Tag": [
        "H1 did not inadvertently change the nav or footer navigation label",
        "H1 is consistent with H1 tags on similar page types across the site",
    ],
    "H2 / H3 / H4 Tags": [
        "Subheadings naturally incorporate supporting, LSI, and geo keywords",
        "Heading text accurately describes the section that follows",
    ],
    "Image Alt Text & Optimization": [
        "Alt text describes what is actually in the image (not keyword stuffed)",
        "Image filenames are descriptive (not image01.jpg or screenshot.png)",
    ],
    "Internal Linking & Anchor Text": [
        "Links are distributed naturally throughout the content (not clustered)",
        "At least one link points to a high-value 'money page' (service/product)",
        "Link styling is consistent and clearly identifiable as clickable",
    ],
    "External Linking": [
        "No external links point to Wikipedia, forums, or competitor websites",
        "All external links enhance the trustworthiness and EEAT profile of the page",
        "Existing external links that don't enhance EEAT have rel='nofollow' applied",
    ],
    "Schema Markup": [
        "Schema type selected is appropriate for the page (Article, FAQ, Product, HowTo)",
        "Schema was verified using the Google Rich Results Test with zero errors",
        "FAQ schema content (if used) matches the visible text on the page exactly",
    ],
    "Social Metadata (OG & Twitter)": [
        "Social titles and descriptions have slight variation from main title/meta",
        "OG and Twitter tags were updated via the Social tab in AIOSEO or Yoast",
    ],
    "Google Maps Embedding": [
        "Iframe uses the verified Google Business Profile link (not a generic address)",
        "Map was verified on the live site and loads/displays the correct location",
    ],
    "YouTube Video Embedding": [
        "Video is embedded on a relevant service, blog, or location page",
        "Page includes a keyword-informed title, description, or transcript",
        "Embedded video loads correctly on mobile",
    ],
    "Section Design & FAQ Content": [
        "FAQ answers are concise (40-60 words), direct, and written for search intent",
        "FAQ section is placed after core content is established on the page",
        "No keyword stuffing in FAQ content — written naturally and conversationally",
    ],
    "TOC (Table of Contents)": [
        "TOC is updated to reflect all current sections including new or renamed ones",
        "Labels are short, descriptive, and match exact section heading names",
    ],
    "Robots.txt Check": [
        "New rules have been verified to target only intended paths",
        "No critical content was accidentally blocked",
        "Existing directives necessary for indexation remain intact",
    ],
    "AIO AI Crawler Directives": [
        "Documentation includes a record of old and new robots.txt content",
        "New rules apply to individual AI crawlers (not just catch-all *)",
        "Reference site checked (e.g., lemonlaws.com/robots.txt) for formatting guidance",
    ],
    "LLMs.txt Check": [
        "File includes site name, purpose, key topics/services",
        "Key pages are listed with descriptive titles, clean URLs, and brief context",
        "Language is plain and direct, written for machines not humans",
        "llms-full.txt is linked if applicable",
    ],
    "XML Sitemaps": [
        "Sitemap includes only relevant, high-quality canonical URLs (status 200)",
        "Irrelevant sections (categories, tags, author archives) are excluded",
        "Sitemap has been submitted to Google Search Console and shows Success status",
    ],
    "Canonical Tags": [
        "Canonical was intentionally placed (not added by mistake)",
        "The page it canonicalizes to is the primary version of that content",
    ],
    "URL Hygiene & Indexing": [
        "URL contains the relevant keyword and removes stop words",
        "If URL was changed, a 301 redirect from the old URL was implemented",
        "Child pages were checked before changing any parent page URL",
        "New URL was submitted for indexing after the change",
    ],
    "Page Speed Analysis": [
        "Issues were flagged for the dev team with specific recommendations",
        "Mobile scores were prioritized",
        "Post-fix testing was completed to confirm improvement",
    ],
    "NAP Information": [
        "NAP formatting and branding is consistent across all site instances",
        "NAP details exactly match the Google Business Profile",
    ],
    "Internal Links to Redirects": [
        "All updated internal links were verified to return status 200",
        "Anchor text and surrounding content were not altered during URL updates",
    ],
    "Indexation Audits": [
        "All target non-indexed pages verified as legitimate via live render test",
        "Indexing manually requested for all validated high-priority pages",
        "Sitemap confirmed as submitted and processed in GSC",
    ],
    "Backlink QA & Analysis": [
        "Full backlink profile pulled from Ahrefs, filtered for followed links and high spam scores",
        "All identified links categorized by risk level: High, Medium, or Low",
        "Anchor text distribution audited for over-optimized exact-match keywords",
        "GSC checked for any manual action notices",
        "All flagged links documented in a tracker",
    ],
    "Image Compression (Imagify)": [
        "Imagify plugin is confirmed active in the WordPress dashboard",
        "Bulk compression was run on existing images",
        "New images are being auto-compressed on upload",
        "Page speed was re-tested after compression to confirm improvement",
    ],
    "Fixed 404s & Broken URLs": [
        "All fixed URLs were verified to return 200 in the tracking spreadsheet",
        "301 redirects were implemented where URLs changed permanently",
        "Internal links pointing to old URLs were updated to the new destinations",
    ],
    "New Page / URL Created": [
        "New page returns 200 and is accessible on the live site",
        "Page has been submitted for indexing in Google Search Console",
        "Page is linked to from at least one relevant internal page",
    ],
    "Caching Plugin (WP Rocket / LiteSpeed)": [
        "Caching plugin (WP Rocket or LiteSpeed Cache) is confirmed active in the WordPress dashboard",
        "Minification settings (CSS/JS) are enabled in the plugin",
        "Caching was tested on the live site after configuration",
    ],
    "Disavow Spammy Backlinks": [
        "Disavow file follows correct syntax (one URL or domain per line with domain: prefix)",
        "List is strictly limited to toxic or spammy links only (no high-quality backlinks removed)",
        "File successfully uploaded to the correct property in GSC",
        "Domain-level disavows used for widespread spam sources",
    ],
    "TLDR / AI Takeaways": [
        "Summary is front-loaded at the top of the page",
        "Content accurately distills the main points into a concise overview",
        "Uses scannable elements (bullets or blockquote) for readability",
        "No literal 'TLDR' heading used — framed appropriately for the client",
    ],
    "Content Reformatting": [
        "Large paragraphs converted into concise bullet points",
        "A brief introductory summary is placed at the top of the page",
        "Critical information is front-loaded in the early content",
        "Clear H2/H3 subheadings define content hierarchy",
        "No original meaning or core information was lost or altered",
    ],
    "LSI Keywords": [
        "Primary keyword is supported by conceptually related LSI terms",
        "LSI keywords integrated naturally and not keyword stuffed",
        "LSI terms sourced from PAA sections or Related Searches in SERPs",
    ],
    "Geo Keywords": [
        "Geo keywords are relevant and applicable to this specific page",
        "Geographic identifiers include specific locations (city, county, state, neighborhood)",
        "'Near me' is NOT used as a primary geo keyword",
    ],
    "Brand Integrity": [
        "Client name is spelled exactly as it appears in the Brand Guide",
        "Writing style (tone, POV, formatting) follows all Brand Guide Writing Rules",
        "'About the Client' sections align with the approved brand story",
    ],
    "Geo-Targeting & Service Areas": [
        "Content aligns with the primary geo-targeting (State/Region)",
        "All cities mentioned are on the 'Cities Served' list",
        "No mentions of geolocations or service areas not found on the client's website",
    ],
    "Service & Product Accuracy": [
        "All products/services mentioned are currently offered on the client's website",
        "Content makes zero claims about services the client does not provide",
        "No factual inaccuracies regarding pricing, warranties, or specific features",
        "AI-generated content has been reviewed for hallucinations",
    ],
    "CTA Structure & Alignment": [
        "CTA follows the exact structure required by the Brand Guide",
        "Phone number in the CTA matches the contact info on the live site",
        "The 'Ask' is appropriate for the content type (no 'Buy Now' on a blog)",
        "A final CTA exists at the end of the page/post",
    ],
    "Website & Guide Consistency": [
        "No contradictions exist between new content and the Brand Guide",
        "No inconsistencies between the content and the existing live website",
        "External links (if any) do not lead to competitor sites",
        "Customer logic check passed: content flows naturally to the homepage",
    ],
    "Grammar, Syntax & Polish": [
        "Zero spelling or grammatical errors",
        "No repetitive sentence starters (e.g., 3 paragraphs starting with 'The...')",
        "Content is written in the correct POV per the Brand Guide",
        "Content was reviewed with Grammarly or Hemingway as a baseline",
    ],
    "Formatting, Structure & Layout": [
        "Paragraphs are structured properly for readability",
        "Lists, bullets, or bold text are used to break up walls of text",
        "Page mimics the layout and structure of other pages on the site",
        "Content renders correctly on mobile (checked via DevTools emulator)",
        "A clear CTA button or link is visible above the fold or after key sections",
    ],
    "YouTube Channel Optimization": [
        "Video titles are under 60 characters with primary keyword near the front",
        "Descriptions have keyword-rich content and essential links in first 2-3 lines",
        "Video chapters are implemented with accurate timestamps",
        "Auto-captions are enabled and edited for accuracy",
        "VideoObject schema is deployed on all website pages with embedded videos",
    ],
}

# ─── Helper Functions ──────────────────────────────────────────────────────────

def fetch_page(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; VDS-SEO-QA/1.0)"}
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        soup = BeautifulSoup(resp.text, "html.parser")
        return soup, resp, None
    except Exception as e:
        return None, None, str(e)

def get_domain(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"

def ri(label, status, detail=""):
    """Render a result item."""
    icons = {"pass": "✅", "fail": "❌", "warn": "⚠️", "info": "ℹ️"}
    icon = icons.get(status, "ℹ️")
    st.markdown(f"{icon} **{label}**{' — ' + detail if detail else ''}")

# ─── Auto-Check Functions ──────────────────────────────────────────────────────

def check_title_tag(soup):
    title = soup.find("title")
    if not title or not title.text.strip():
        return [("Title tag", "fail", "Missing or empty")]
    t = title.text.strip()
    brand_stripped = re.split(r'\s*[\|–—\-]\s*[^|\-–—]+$', t)[0].strip()
    count = len(brand_stripped)
    results = []
    results.append(("Title tag exists", "pass", ""))
    if count > 60:
        results.append(("Title length (excl. brand)", "fail", f"{count} chars — aim for under 60"))
    else:
        results.append(("Title length (excl. brand)", "pass", f"{count} chars"))
    results.append(("Title content", "info", f'"{t}"'))
    return results

def check_meta_description(soup):
    meta = soup.find("meta", attrs={"name": "description"})
    if not meta or not meta.get("content", "").strip():
        return [("Meta description", "fail", "Missing or empty")]
    c = meta["content"].strip()
    count = len(c)
    results = []
    if count < 120:
        results.append(("Meta description length", "warn", f"{count} chars — aim for 120-160"))
    elif count > 160:
        results.append(("Meta description length", "warn", f"{count} chars — may truncate in SERPs"))
    else:
        results.append(("Meta description length", "pass", f"{count} chars"))
    cta_words = ["call", "contact", "get", "request", "schedule", "learn", "discover", "find", "start", "try"]
    if any(w in c.lower() for w in cta_words):
        results.append(("Meta description CTA", "pass", "Action-oriented language detected"))
    else:
        results.append(("Meta description CTA", "warn", "No clear CTA detected"))
    results.append(("Meta content", "info", f'"{c[:100]}{"..." if len(c) > 100 else ""}"'))
    return results

def check_h1(soup):
    h1s = soup.find_all("h1")
    if not h1s:
        return [("H1 tag", "fail", "No H1 found on page")]
    results = []
    if len(h1s) > 1:
        results.append(("H1 count", "fail", f"{len(h1s)} H1 tags found — should be exactly 1"))
    else:
        results.append(("H1 count", "pass", "Exactly 1 H1 found"))
    t = h1s[0].text.strip()
    if len(t) > 70:
        results.append(("H1 length", "warn", f"{len(t)} chars — aim for under 70"))
    else:
        results.append(("H1 length", "pass", f"{len(t)} chars"))
    results.append(("H1 content", "info", f'"{t}"'))
    return results

def check_heading_hierarchy(soup):
    headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    if not headings:
        return [("Headings", "warn", "No headings found on page")]
    levels = [int(h.name[1]) for h in headings]
    skips = []
    for i in range(1, len(levels)):
        if levels[i] > levels[i - 1] + 1:
            skips.append(f"H{levels[i-1]} to H{levels[i]}")
    if skips:
        return [("Heading hierarchy", "fail", f"Skipped levels: {', '.join(skips)}")]
    return [("Heading hierarchy", "pass", "No skipped heading levels")]

def check_image_alt(soup):
    imgs = soup.find_all("img")
    if not imgs:
        return [("Images", "info", "No images found on page")]
    generic_pat = re.compile(r'^(image\d*|img\d*|screenshot|photo\d*|picture\d*|banner\d*)$', re.I)
    missing, generic = [], []
    for img in imgs:
        alt = img.get("alt")
        src = img.get("src", "").split("/")[-1][:40]
        if alt is None:
            missing.append(src)
        elif generic_pat.match(alt.strip()):
            generic.append(alt.strip())
    results = []
    if missing:
        results.append(("Missing alt text", "fail", f"{len(missing)} image(s) missing alt attribute"))
    else:
        results.append(("Alt text coverage", "pass", f"All {len(imgs)} images have alt attributes"))
    if generic:
        results.append(("Generic alt text", "warn", f"{len(generic)} image(s) have generic alt text: {', '.join(generic[:3])}"))
    return results

def check_image_compression(soup, response):
    results = []
    imgs = soup.find_all("img", src=True)
    if not imgs:
        return [("Images", "info", "No images found on page")]

    # Check for Imagify headers
    headers = {k.lower(): v for k, v in response.headers.items()}
    imagify_signals = ["x-imagify", "x-imagify-cache", "imagify"]
    if any(s in str(headers) for s in imagify_signals):
        results.append(("Imagify plugin", "pass", "Imagify headers detected"))
    else:
        results.append(("Imagify plugin", "info", "No Imagify headers detected — verify plugin is active in WP dashboard"))

    # Check image formats
    modern_formats = (".webp", ".avif")
    legacy_formats = (".jpg", ".jpeg", ".png", ".gif", ".bmp")
    modern, legacy, unknown = [], [], []

    for img in imgs:
        src = img.get("src", "").lower().split("?")[0]
        if any(src.endswith(f) for f in modern_formats):
            modern.append(src)
        elif any(src.endswith(f) for f in legacy_formats):
            legacy.append(src)

    total = len(imgs)
    if legacy and not modern:
        results.append(("Image formats", "fail",
                        f"All {len(legacy)} image(s) are legacy format (JPG/PNG) — no WebP/AVIF detected"))
    elif legacy and modern:
        results.append(("Image formats", "warn",
                        f"{len(modern)} modern (WebP/AVIF) and {len(legacy)} legacy (JPG/PNG) — consider converting remaining"))
    elif modern:
        results.append(("Image formats", "pass",
                        f"All {len(modern)} image(s) use modern formats (WebP/AVIF)"))
    else:
        results.append(("Image formats", "info", "Could not determine image formats from src attributes"))

    return results

def check_url_exists(check_url):
    """Check if a specific URL returns 200."""
    try:
        resp = requests.get(check_url, timeout=10, allow_redirects=True,
                            headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            return [("Page exists", "pass", f"{check_url} returns 200 OK")]
        else:
            return [("Page exists", "fail", f"{check_url} returned status {resp.status_code}")]
    except Exception as e:
        return [("Page exists", "fail", f"Could not reach {check_url}: {e}")]

def check_url_batch(urls_text):
    """Check a list of URLs pasted as newline or comma-separated text."""
    raw = re.split(r'[\n,]+', urls_text.strip())
    urls = [u.strip() for u in raw if u.strip().startswith("http")]
    if not urls:
        return [("URL batch", "warn", "No valid URLs found — make sure each URL starts with http")]

    results = []
    for u in urls[:30]:  # cap at 30 to avoid timeouts
        try:
            resp = requests.get(u, timeout=8, allow_redirects=True,
                                headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                results.append((u[:70], "pass", "200 OK"))
            elif resp.status_code in (301, 302):
                results.append((u[:70], "warn", f"{resp.status_code} redirect — verify final destination"))
            else:
                results.append((u[:70], "fail", f"Status {resp.status_code}"))
        except Exception as e:
            results.append((u[:70], "fail", f"Could not reach: {str(e)[:50]}"))

    if len(urls) > 30:
        results.append(("Note", "info", f"Checked first 30 of {len(urls)} URLs — paste in batches for full coverage"))

    return results

def check_canonical(soup, url):
    canon = soup.find("link", attrs={"rel": "canonical"})
    if not canon:
        return [("Canonical tag", "fail", "No canonical tag found")]
    href = canon.get("href", "").strip()
    if not href:
        return [("Canonical tag", "fail", "Canonical present but href is empty")]
    results = []
    if href.rstrip("/") == url.rstrip("/"):
        results.append(("Canonical", "pass", "Self-canonicalized correctly"))
    else:
        results.append(("Canonical", "warn", f"Points to: {href} — verify this is intentional"))
    staging = ["staging.", "stage.", "dev.", "test.", "localhost"]
    if any(p in href.lower() for p in staging):
        results.append(("Canonical staging check", "fail", "Canonical references a staging URL!"))
    return results

def check_noindex(soup):
    meta = soup.find("meta", attrs={"name": "robots"})
    if meta and "noindex" in meta.get("content", "").lower():
        return [("Noindex tag", "fail", "Page has noindex directive — should NOT be on a live optimized page")]
    return [("Noindex / Robots meta", "pass", "No noindex directive found")]

def check_og_twitter(soup):
    og = {k: soup.find("meta", property=k) for k in ["og:title", "og:description", "og:image"]}
    tw = {k: soup.find("meta", attrs={"name": k}) for k in ["twitter:card", "twitter:title"]}
    results = []
    missing_og = [k for k, v in og.items() if not v]
    missing_tw = [k for k, v in tw.items() if not v]
    results.append(("Open Graph tags", "warn" if missing_og else "pass",
                    f"Missing: {', '.join(missing_og)}" if missing_og else "og:title, og:description, og:image all present"))
    results.append(("Twitter/X tags", "warn" if missing_tw else "pass",
                    f"Missing: {', '.join(missing_tw)}" if missing_tw else "twitter:card present"))
    return results

def check_external_links(soup):
    ext = [a for a in soup.find_all("a", href=True) if a["href"].startswith("http")]
    if not ext:
        return [("External links", "info", "No external links found on page")]
    missing_target = [a["href"][:60] for a in ext if a.get("target") != "_blank"]
    results = []
    if missing_target:
        results.append(("External links: target=_blank", "fail",
                        f"{len(missing_target)} external link(s) missing target='_blank'"))
    else:
        results.append(("External links: target=_blank", "pass",
                        f"All {len(ext)} external links open in new tab"))
    return results

def check_anchor_text(soup):
    bad = {"click here", "learn more", "read more", "here", "this link", "link", "more"}
    flagged = []
    for a in soup.find_all("a", href=True):
        if a.text.strip().lower() in bad:
            flagged.append(f'"{a.text.strip()}"')
    if flagged:
        return [("Anchor text quality", "fail", f"Generic anchor text: {', '.join(flagged[:5])}")]
    return [("Anchor text quality", "pass", "No generic anchor text detected")]

def check_schema(soup):
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    if not scripts:
        return [("Schema markup", "warn", "No JSON-LD schema found on page")]
    types = []
    for s in scripts:
        try:
            d = json.loads(s.string)
            if isinstance(d, dict):
                types.append(d.get("@type", "Unknown"))
            elif isinstance(d, list):
                types += [i.get("@type", "Unknown") for i in d if isinstance(i, dict)]
        except:
            pass
    results = [("Schema types found", "pass", ", ".join(types))]
    if "FAQPage" in types:
        results.append(("FAQPage schema", "pass", "FAQPage schema detected"))
    if "VideoObject" in types:
        results.append(("VideoObject schema", "pass", "VideoObject schema detected"))
    return results

def check_google_maps(soup):
    iframes = [i for i in soup.find_all("iframe") if "google.com/maps" in i.get("src", "")]
    if not iframes:
        return [("Google Maps embed", "info", "No Google Maps iframe found")]
    results = [("Google Maps embed", "pass", f"{len(iframes)} Maps iframe(s) found")]
    for i in iframes:
        src = i.get("src", "")
        if any(x in src for x in ["/place/", "cid=", "ftid="]):
            results.append(("Maps embed type", "pass", "Uses a specific GBP/location link"))
        else:
            results.append(("Maps embed type", "warn", "Verify this uses the GBP link, not a generic address"))
    return results

def check_youtube(soup):
    iframes = [i for i in soup.find_all("iframe")
               if "youtube.com/embed" in i.get("src", "") or "youtube-nocookie.com" in i.get("src", "")]
    if not iframes:
        return [("YouTube embed", "info", "No YouTube embed found")]
    results = [("YouTube embed", "pass", f"{len(iframes)} YouTube iframe(s) found")]
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    has_video_schema = False
    for s in scripts:
        try:
            d = json.loads(s.string)
            if (isinstance(d, dict) and d.get("@type") == "VideoObject") or \
               (isinstance(d, list) and any(i.get("@type") == "VideoObject" for i in d if isinstance(i, dict))):
                has_video_schema = True
        except:
            pass
    results.append(("VideoObject schema", "pass" if has_video_schema else "fail",
                    "VideoObject schema found" if has_video_schema else "YouTube embed present but no VideoObject schema"))
    return results

def check_robots_txt(domain):
    url = f"{domain}/robots.txt"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return [("robots.txt", "fail", f"Returned status {resp.status_code}")]
        content = resp.text
        results = [("robots.txt accessible", "pass", f"Found at {url}")]
        results.append(("Sitemap in robots.txt", "pass" if "sitemap" in content.lower() else "warn",
                        "Sitemap URL referenced" if "sitemap" in content.lower() else "No sitemap reference found"))
        ai_crawlers = ["GPTBot", "ClaudeBot", "PerplexityBot", "GoogleOther", "CCBot", "anthropic-ai", "cohere-ai"]
        found = [c for c in ai_crawlers if c.lower() in content.lower()]
        results.append(("AI crawler directives", "pass" if found else "warn",
                        f"Found: {', '.join(found)}" if found else "No specific AI crawlers named — only catch-all * may be set"))
        return results
    except Exception as e:
        return [("robots.txt", "fail", f"Could not fetch: {e}")]

def check_llms_txt(domain):
    url = f"{domain}/llms.txt"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 404:
            return [("llms.txt", "warn", "File not found — consider creating one for AEO/GEO visibility")]
        if resp.status_code != 200:
            return [("llms.txt", "fail", f"Unexpected status: {resp.status_code}")]
        content = resp.text
        results = [("llms.txt exists", "pass", f"Found at {url}")]
        results.append(("llms.txt: H1 heading", "pass" if content.strip().startswith("#") else "warn",
                        "Starts with H1 heading" if content.strip().startswith("#") else "Should start with a # H1 heading"))
        results.append(("llms.txt: Links present", "pass" if "http" in content or "[" in content else "warn",
                        "Links detected" if "http" in content or "[" in content else "No links detected — add key page URLs"))
        results.append(("llms.txt: Summary blockquote", "pass" if ">" in content else "warn",
                        "Blockquote summary detected" if ">" in content else "Consider adding a summary blockquote"))
        return results
    except Exception as e:
        return [("llms.txt", "fail", f"Could not fetch: {e}")]

def check_xml_sitemap(domain):
    paths = ["/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml"]
    for path in paths:
        try:
            resp = requests.get(f"{domain}{path}", timeout=10)
            if resp.status_code == 200:
                results = [("XML Sitemap", "pass", f"Found at {domain}{path}")]
                try:
                    robots = requests.get(f"{domain}/robots.txt", timeout=8)
                    results.append(("Sitemap in robots.txt", "pass" if "sitemap" in robots.text.lower() else "warn",
                                    "Referenced in robots.txt" if "sitemap" in robots.text.lower() else "Not referenced in robots.txt"))
                except:
                    pass
                return results
        except:
            pass
    return [("XML Sitemap", "warn", "No sitemap found at common paths — verify submission in GSC")]

def check_url_hygiene(url):
    parsed = urlparse(url)
    path = parsed.path
    results = []
    results.append(("URL: Lowercase", "pass" if path == path.lower() else "fail",
                    "All lowercase" if path == path.lower() else "Contains uppercase letters"))
    results.append(("URL: No underscores", "pass" if "_" not in path else "fail",
                    "Uses hyphens correctly" if "_" not in path else "Contains underscores — use hyphens"))
    staging = ["staging.", "stage.", "dev.", "test.", "localhost"]
    is_staging = any(p in url.lower() for p in staging)
    results.append(("URL: Live domain", "fail" if is_staging else "pass",
                    "Staging domain detected — run QA on live URL" if is_staging else "Appears to be a live domain"))
    return results

def check_nap(soup):
    text = soup.get_text()
    phones = re.findall(r'(\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4})', text)
    addr_words = ["street", " st.", " ave", " blvd", "suite", " ste.", " rd.", "drive", " dr."]
    results = []
    results.append(("NAP: Phone number", "pass" if phones else "warn",
                    f"Phone found: {phones[0]}" if phones else "No phone number pattern detected"))
    has_addr = any(p.lower() in text.lower() for p in addr_words)
    results.append(("NAP: Address content", "pass" if has_addr else "warn",
                    "Address-like content detected" if has_addr else "No address content detected — verify NAP is on page"))
    results.append(("NAP: GBP match", "info", "Manually verify NAP matches the Google Business Profile exactly"))
    return results

def check_internal_redirects(soup, url):
    domain = get_domain(url)
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/") or href.startswith(domain):
            full = href if href.startswith("http") else urljoin(url, href)
            if full not in links:
                links.append(full)
    if not links:
        return [("Internal links", "info", "No internal links found to check")]
    sample = links[:15]
    redirects = []
    for link in sample:
        try:
            r = requests.head(link, timeout=5, allow_redirects=False,
                              headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code in (301, 302, 307, 308):
                redirects.append(link)
        except:
            pass
    if redirects:
        return [("Internal links to redirects", "fail",
                 f"{len(redirects)} link(s) point to redirects: {redirects[0][:60]}")]
    return [("Internal links to redirects", "pass",
             f"{len(sample)} internal links sampled — no redirects found")]

def check_faq(soup):
    headings = soup.find_all(["h2", "h3", "h4"])
    faq_headings = [h for h in headings if "?" in h.text or
                    "faq" in h.text.lower() or "frequently" in h.text.lower()]
    if not faq_headings:
        return [("FAQ section", "info", "No FAQ section detected")]
    results = [("FAQ headings", "pass", f"{len(faq_headings)} FAQ-style heading(s) found")]
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    has_faq = False
    for s in scripts:
        try:
            d = json.loads(s.string)
            if (isinstance(d, dict) and d.get("@type") == "FAQPage") or \
               (isinstance(d, list) and any(i.get("@type") == "FAQPage" for i in d if isinstance(i, dict))):
                has_faq = True
        except:
            pass
    results.append(("FAQPage schema", "pass" if has_faq else "fail",
                    "FAQPage JSON-LD detected" if has_faq else "FAQ content found but no FAQPage schema present"))
    return results

def check_toc(soup):
    anchors = soup.find_all("a", href=lambda h: h and h.startswith("#"))
    if len(anchors) < 3:
        return [("TOC", "info", "No table of contents detected (fewer than 3 anchor links found)")]
    results = [("TOC anchor links", "pass", f"{len(anchors)} anchor links found")]
    broken = [a["href"] for a in anchors[:10] if not soup.find(id=a["href"][1:])]
    if broken:
        results.append(("TOC broken anchors", "fail",
                        f"These anchors may not resolve: {', '.join(broken[:3])}"))
    else:
        results.append(("TOC anchor targets", "pass", "All checked anchor targets exist on page"))
    return results

def check_page_speed(url):
    api = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&strategy=mobile"
    try:
        resp = requests.get(api, timeout=30)
        data = resp.json()
        score = data.get("lighthouseResult", {}).get("categories", {}).get("performance", {}).get("score")
        audits = data.get("lighthouseResult", {}).get("audits", {})
        results = []
        if score is not None:
            s = int(score * 100)
            status = "pass" if s >= 90 else "warn" if s >= 50 else "fail"
            results.append(("PageSpeed mobile score", status, f"{s}/100"))
        lcp = audits.get("largest-contentful-paint", {}).get("displayValue", "N/A")
        cls = audits.get("cumulative-layout-shift", {}).get("displayValue", "N/A")
        results.append(("LCP", "info", lcp))
        results.append(("CLS", "info", cls))
        return results
    except:
        return [("PageSpeed", "warn", "Could not retrieve — check manually at pagespeed.web.dev")]

def check_caching(url, response):
    results = []
    headers = {k.lower(): v for k, v in response.headers.items()}

    cache_signals = {
        "WP Rocket":      ["x-wp-rocket", "x-rocket-id"],
        "LiteSpeed":      ["x-litespeed-cache", "x-litespeed-tag", "x-lsadc"],
        "Cloudflare":     ["cf-cache-status", "cf-ray"],
        "WP Super Cache": ["x-wpsc-pre-compressed"],
        "W3 Total Cache": ["x3-powered-by"],
        "Generic Cache":  ["x-cache", "x-cache-hits", "x-cache-status"],
    }

    detected = []
    for plugin, header_keys in cache_signals.items():
        if any(h in headers for h in header_keys):
            # Get the actual header value for context
            for h in header_keys:
                if h in headers:
                    detected.append(f"{plugin} ({h}: {headers[h]})")
                    break

    if detected:
        results.append(("Caching detected", "pass", " | ".join(detected)))
    else:
        results.append(("Caching plugin", "warn",
                        "No caching headers detected — verify WP Rocket or LiteSpeed Cache is active and configured"))

    # Also check for compression (a related performance signal)
    encoding = headers.get("content-encoding", "")
    if encoding in ("gzip", "br", "zstd"):
        results.append(("Compression", "pass", f"Content is compressed ({encoding})"))
    else:
        results.append(("Compression", "warn", "No compression detected (gzip/brotli) — flag for dev team"))

    return results

# ─── Auto-Check Dispatcher ─────────────────────────────────────────────────────

def run_auto_checks_for(opt, soup, url, domain, response=None):
    dispatch = {
        "Title Tag":                    lambda: check_title_tag(soup),
        "Meta Description":             lambda: check_meta_description(soup),
        "Metadata & Heading Structure": lambda: check_title_tag(soup) + check_meta_description(soup) + check_h1(soup) + check_heading_hierarchy(soup),
        "H1 Tag":                       lambda: check_h1(soup),
        "H2 / H3 / H4 Tags":           lambda: check_heading_hierarchy(soup),
        "Image Alt Text & Optimization":lambda: check_image_alt(soup),
        "Canonical Tags":               lambda: check_canonical(soup, url),
        "URL Hygiene & Indexing":       lambda: check_url_hygiene(url) + check_canonical(soup, url) + check_noindex(soup),
        "Social Metadata (OG & Twitter)": lambda: check_og_twitter(soup),
        "External Linking":             lambda: check_external_links(soup),
        "Internal Linking & Anchor Text": lambda: check_anchor_text(soup),
        "Schema Markup":                lambda: check_schema(soup),
        "Google Maps Embedding":        lambda: check_google_maps(soup),
        "YouTube Video Embedding":      lambda: check_youtube(soup),
        "Robots.txt Check":             lambda: check_robots_txt(domain),
        "AIO AI Crawler Directives":    lambda: check_robots_txt(domain),
        "LLMs.txt Check":               lambda: check_llms_txt(domain),
        "XML Sitemaps":                 lambda: check_xml_sitemap(domain),
        "Page Speed Analysis":          lambda: check_page_speed(url),
        "NAP Information":              lambda: check_nap(soup),
        "Internal Links to Redirects":  lambda: check_internal_redirects(soup, url),
        "Section Design & FAQ Content": lambda: check_faq(soup),
        "TOC (Table of Contents)":      lambda: check_toc(soup),
        "Caching Plugin (WP Rocket / LiteSpeed)": lambda: check_caching(url, response),
        "Image Compression (Imagify)":  lambda: check_image_compression(soup, response),
        "New Page / URL Created":       lambda: check_url_exists(new_page_url) if new_page_url else [("New page URL", "info", "Enter the new page URL in the field below the optimization list")],
    }
    if opt in dispatch and opt not in MANUAL_ONLY:
        return dispatch[opt]()
    return []

# ─── Report Generator ──────────────────────────────────────────────────────────

def generate_report(url, specialist, month, selected, auto_results, guided_results):
    ts = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    icons = {"pass": "PASS", "fail": "FAIL", "warn": "WARN", "info": "INFO"}

    lines = [
        "=" * 62,
        "  VDS ORGANIC SEO — MONTHLY QA REPORT",
        "=" * 62,
        f"  URL:         {url}",
        f"  Specialist:  {specialist}",
        f"  Period:      {month}",
        f"  Date:        {ts}",
        "=" * 62,
        "",
        "OPTIMIZATIONS COMPLETED THIS PERIOD:",
    ]
    for o in selected:
        lines.append(f"  - {o}")

    lines += ["", "-" * 62, "  AUTO-CHECK RESULTS", "-" * 62, ""]
    for opt, results in auto_results.items():
        lines.append(f"[ {opt} ]")
        for label, status, detail in results:
            tag = icons.get(status, "INFO")
            lines.append(f"  [{tag}] {label}{': ' + detail if detail else ''}")
        lines.append("")

    if guided_results:
        lines += ["-" * 62, "  SELF-CERTIFIED CHECKS", "-" * 62, ""]
        for opt, answers in guided_results.items():
            lines.append(f"[ {opt} ]")
            for question, answer in answers.items():
                mark = "[YES]" if answer else "[NO ]"
                lines.append(f"  {mark} {question}")
            lines.append("")

    # Summary
    all_statuses = [s for results in auto_results.values() for _, s, _ in results]
    passes = all_statuses.count("pass")
    fails  = all_statuses.count("fail")
    warns  = all_statuses.count("warn")
    guided_total = sum(len(v) for v in guided_results.values())
    guided_yes   = sum(sum(1 for v in d.values() if v) for d in guided_results.values())

    lines += [
        "-" * 62,
        "  SUMMARY",
        "-" * 62,
        f"  Auto-checks:    {passes} pass  |  {fails} fail  |  {warns} warnings",
        f"  Manual checks:  {guided_yes}/{guided_total} confirmed" if guided_total else "  Manual checks:  N/A",
        "",
        "=" * 62,
        "  Generated by VDS Organic SEO QA Tool",
        "=" * 62,
    ]
    return "\n".join(lines)

# ─── UI ────────────────────────────────────────────────────────────────────────

# Inputs
col1, col2, col3 = st.columns([3, 1, 1])
with col1:
    url_input = st.text_input("Page URL", placeholder="https://example.com/service-page")
with col2:
    specialist_name = st.text_input("Your Name", placeholder="e.g. Alex S.")
with col3:
    report_month = st.text_input("Month / Period", placeholder="e.g. June 2026")

st.markdown("---")
st.markdown("### Optimizations Completed This Period")
st.caption("Select everything you completed. Auto-checkable items will run against the live URL. Manual items will prompt a guided checklist.")

selected_opts = []
cols = st.columns(2)

for idx, (category, opts) in enumerate(OPTIMIZATIONS.items()):
    with cols[idx % 2]:
        st.markdown(f'<div class="section-header">{category}</div>', unsafe_allow_html=True)
        for opt in opts:
            is_manual = opt in MANUAL_ONLY
            label = f"{opt}  *(manual)*" if is_manual else opt
            if st.checkbox(label, key=f"chk_{opt}"):
                selected_opts.append(opt)

# ── Optional: New page URL (shown only when relevant opt is selected) ──
new_page_url = ""
if "New Page / URL Created" in selected_opts:
    new_page_url = st.text_input(
        "New page URL to verify",
        placeholder="https://www.example.com/blog/",
        help="Enter the URL of the new page — the tool will confirm it returns 200"
    )

# ── Optional: URL batch checker for 404 fixes ──
batch_urls_input = ""
if "Fixed 404s & Broken URLs" in selected_opts:
    st.markdown("#### Paste Fixed URLs to Verify")
    st.caption("Paste the URLs that were previously 404s — one per line or comma-separated. The tool will confirm each one is now live.")
    batch_urls_input = st.text_area(
        "Fixed URLs",
        placeholder="https://example.com/page-one\nhttps://example.com/page-two",
        height=120,
        key="batch_urls"
    )

st.markdown("---")
run_btn = st.button("🔍 Run QA Pass", type="primary",
                    disabled=(not url_input or not selected_opts or not specialist_name))

if not url_input or not specialist_name:
    st.info("Enter the page URL and your name above to get started.")
elif not selected_opts:
    st.info("Select at least one optimization above to run the QA pass.")

# ─── Execution ─────────────────────────────────────────────────────────────────

if run_btn and url_input and selected_opts and specialist_name:

    if not url_input.startswith("http"):
        url_input = "https://" + url_input

    domain = get_domain(url_input)
    auto_results = {}
    guided_results = {}

    st.markdown("## QA Results")

    # Fetch page
    with st.spinner("Fetching page..."):
        soup, response, error = fetch_page(url_input)

    if error:
        st.error(f"Could not fetch the page: {error}")
        st.stop()
    if response.status_code != 200:
        st.warning(f"Page returned status {response.status_code} — results may be incomplete.")

    # Split opts
    auto_opts   = [o for o in selected_opts if o not in MANUAL_ONLY]
    manual_opts = [o for o in selected_opts if o in MANUAL_ONLY]

    # Auto-checks
    if auto_opts:
        st.markdown("### Auto-Check Results")
        slow = {"Page Speed Analysis", "Internal Links to Redirects"}
        fast_opts = [o for o in auto_opts if o not in slow]
        slow_opts  = [o for o in auto_opts if o in slow]

        # Deduplicate (robots.txt called for both Robots.txt Check and AIO AI Crawler Directives)
        seen = {}
        for opt in fast_opts:
            key = opt
            # Merge overlapping checks
            if opt == "AIO AI Crawler Directives" and "Robots.txt Check" in fast_opts:
                continue  # Will be covered by Robots.txt Check
            results = run_auto_checks_for(opt, soup, url_input, domain, response)
            if results:
                auto_results[opt] = results

        for opt in slow_opts:
            with st.spinner(f"Running {opt} — this may take a moment..."):
                results = run_auto_checks_for(opt, soup, url_input, domain, response)
            if results:
                auto_results[opt] = results

        for opt, results in auto_results.items():
            with st.expander(f"**{opt}**", expanded=True):
                for label, status, detail in results:
                    ri(label, status, detail)

    # ── Batch URL checker ──
    if "Fixed 404s & Broken URLs" in selected_opts and batch_urls_input.strip():
        st.markdown("### Fixed 404s — URL Status Check")
        with st.spinner("Checking URLs... this may take a moment for large lists."):
            batch_results = check_url_batch(batch_urls_input)
        auto_results["Fixed 404s & Broken URLs"] = batch_results
        with st.expander("**Fixed 404s & Broken URLs**", expanded=True):
            for label, status, detail in batch_results:
                ri(label, status, detail)
        fails_404 = sum(1 for _, s, _ in batch_results if s == "fail")
        if fails_404:
            st.error(f"{fails_404} URL(s) still returning errors — these need attention before closing the task.")

    # Guided checklist
    opts_with_guided = [o for o in selected_opts if o in GUIDED_QUESTIONS]
    if opts_with_guided:
        st.markdown("### Manual Verification Checklist")
        st.caption("Confirm each item you can verify. These become part of your QA report.")

        with st.form("guided_form"):
            for opt in opts_with_guided:
                st.markdown(f"**{opt}**")
                answers = {}
                for q, *_ in [(q,) for q in GUIDED_QUESTIONS[opt]]:
                    answers[q] = st.checkbox(q, key=f"g_{opt}_{q}")
                guided_results[opt] = answers
                st.divider()
            st.form_submit_button("Save Manual Checks")

    # Report
    st.markdown("---")
    st.markdown("### Monthly QA Report")
    st.caption("Copy this and paste it as a comment on your Teamwork task before closing.")

    report = generate_report(
        url_input, specialist_name, report_month or "Not specified",
        selected_opts, auto_results, guided_results
    )
    st.text_area("", value=report, height=420, key="report_output")

    # Summary callout
    all_s = [s for r in auto_results.values() for _, s, _ in r]
    fails = all_s.count("fail")
    warns = all_s.count("warn")

    if fails > 0:
        st.error(f"**{fails} item(s) need attention before closing this task.** Review the ❌ items above.")
    elif warns > 0:
        st.warning(f"**{warns} warning(s) to review.** Check ⚠️ items and confirm they are intentional.")
    else:
        st.success("**All auto-checks passed!** Complete the manual checklist above and copy the report to Teamwork.")
