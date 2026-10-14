"""Collect recent zero-knowledge papers from IACR ePrint and arXiv into papers.json."""
import json, re, pathlib, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

OUT = pathlib.Path(__file__).with_name("papers.json")
KEEP_DAYS = 400
KW = re.compile(r"zero[- ]knowledge|\bzk\w*|\bsnarks?\b|\bstarks?\b|\bnizks?\b|sigma[- ]protocol|"
                r"succinct (non-interactive )?arguments?|interactive oracle proof|polynomial commitment", re.I)

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "recent-zk-papers (github pages project)"})
    return urllib.request.urlopen(req, timeout=60).read()

def clean(t):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t or "")).strip()

def eprint():
    root = ET.fromstring(get("https://eprint.iacr.org/rss/rss.xml"))
    for it in root.iter("item"):
        link = (it.findtext("link") or "").strip()
        m = re.search(r"/(\d{4}/\d+)", link)
        if not m: continue
        d = parsedate_to_datetime(it.findtext("pubDate")).astimezone(timezone.utc)
        authors = ", ".join(clean(a.text) for a in it.findall("author")) or clean(it.findtext("creator") or "")
        yield dict(id="eprint:" + m.group(1), title=clean(it.findtext("title")), authors=authors,
                   abstract=clean(it.findtext("description")), url=link, pdf=link + ".pdf",
                   source="ePrint", date=d.isoformat())

def arxiv():
    q = '(ti:"zero-knowledge" OR abs:"zero-knowledge" OR abs:"zero knowledge" OR abs:SNARK OR abs:STARK) AND cat:cs.CR'
    url = "http://export.arxiv.org/api/query?" + urllib.parse.urlencode(
        dict(search_query=q, sortBy="submittedDate", sortOrder="descending", max_results=300))
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for e in ET.fromstring(get(url)).findall("a:entry", ns):
        link = e.findtext("a:id", namespaces=ns).strip()
        aid = link.rsplit("/abs/", 1)[-1]
        yield dict(id="arxiv:" + re.sub(r"v\d+$", "", aid), title=clean(e.findtext("a:title", namespaces=ns)),
                   authors=", ".join(clean(a.findtext("a:name", namespaces=ns)) for a in e.findall("a:author", ns)),
                   abstract=clean(e.findtext("a:summary", namespaces=ns)), url=link,
                   pdf=link.replace("/abs/", "/pdf/"), source="arXiv",
                   date=e.findtext("a:published", namespaces=ns).strip())

def main():
    old = json.loads(OUT.read_text()) if OUT.exists() else {"papers": []}
    papers = {p["id"]: p for p in old["papers"]}
    for name, fn in (("ePrint", eprint), ("arXiv", arxiv)):
        try:
            n = 0
            for p in fn():
                if KW.search(p["title"] + " " + p["abstract"]):
                    papers[p["id"]] = p; n += 1
            print(f"{name}: {n} matching papers")
        except Exception as ex:
            print(f"{name} failed: {ex}")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)).isoformat()
    kept = sorted((p for p in papers.values() if p["date"] >= cutoff), key=lambda p: p["date"], reverse=True)
    OUT.write_text(json.dumps({"updated": datetime.now(timezone.utc).isoformat(), "papers": kept}, indent=1))

if __name__ == "__main__":
    main()
