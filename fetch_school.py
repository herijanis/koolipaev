# Fetches Viimsi Kool's weekly lunch menu (PDFs in the school's public Google Drive folder) and the
# latest school news (WordPress REST API) and writes menu.json and news.json for the app.
import io, json, re, socket, urllib.request, datetime, zoneinfo
from pypdf import PdfReader

_gai = socket.getaddrinfo
socket.getaddrinfo = lambda host, *a, **k: [r for r in _gai(host, *a, **k) if r[0] == socket.AF_INET] or _gai(host, *a, **k)

FOLDER = "https://drive.google.com/drive/folders/1aZV0Nf1UFE0Cw7HEwcRye9eNuLUNGXK_"
NEWS = "https://viimsi.edu.ee/wp-json/wp/v2/posts?per_page=5&_fields=date,title,link"
MONTHS = ["jaanuar", "veebruar", "märts", "aprill", "mai", "juuni", "juuli", "august", "september", "oktoober", "november", "detsember"]
DAY_RE = re.compile(r"^(esmaspäev|teisipäev|kolmapäev|neljapäev|reede),\s*(\d{1,2})\.\s*([a-zõäöü]+)", re.I)
SKIP = ("kastmevalik", "seemne", "maitsevesi", "mahlajook", "pria", "leivatoodete", "kokku", "kogus")

def get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (koolipaev)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def name_of(line):
    # "Hakklihasupp 300 214 9.76 ..." -> "Hakklihasupp"
    return re.split(r"\s+\d", line.strip(), 1)[0].strip(" -")

def parse_menu(pdf_bytes):
    text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf_bytes)).pages)
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})\s*-\s*\d{2}\.\d{2}\.\d{4}", text)
    year = int(m.group(3)) if m else datetime.date.today().year
    days, cur, after_total = {}, None, False
    for line in text.splitlines():
        d = DAY_RE.match(line.strip())
        if d:
            month = MONTHS.index(d.group(3).lower()) + 1 if d.group(3).lower() in MONTHS else None
            if month:
                cur = str(datetime.date(year, month, int(d.group(2))))
                days[cur] = {"main": "", "veg": "", "sides": [], "snack": ""}
            after_total = False
            continue
        if not cur:
            continue
        name = name_of(line)
        if not name or len(name) < 3:
            continue
        low = name.lower()
        if low.startswith("kokku"):
            after_total = True
            continue
        if after_total:
            # the line right after the totals is the vegetarian main dish
            days[cur]["veg"] = days[cur]["veg"] or name
            after_total = False
            continue
        if low.startswith("snäkid"):
            days[cur]["snack"] = name.split(":", 1)[-1].strip()
        elif low.startswith("köögivilja") or low.startswith("taimne"):
            days[cur]["veg"] = name
        elif any(low.startswith(s) for s in SKIP):
            continue
        elif not days[cur]["main"]:
            days[cur]["main"] = name
        elif len(days[cur]["sides"]) < 4:
            days[cur]["sides"].append(name)
    # the vegetarian dish is printed after the "Kokku" line, which can land under the next day's header
    return {k: v for k, v in days.items() if v["main"]}

def menu():
    html = get(FOLDER).decode("utf8", "replace")
    files = {}
    for m in re.finditer(r'data-id="([A-Za-z0-9_-]{20,})"', html):
        n = re.search(r'aria-label="([^"]+?\.pdf)', html[m.end():m.end() + 3000])
        if n:
            files[m.group(1)] = n.group(1)
    week = datetime.date.today().isocalendar()[1]
    out = {}
    for fid, name in files.items():
        w = re.match(r"(\d{1,2})\.ndl", name)
        if not w or "ViimsiKoolid_N" not in name or "KõikVanuse" in name or int(w.group(1)) < week - 1:
            continue
        out.update(parse_menu(get(f"https://drive.google.com/uc?export=download&id={fid}")))
    return out

def news():
    items = json.loads(get(NEWS))
    unesc = lambda s: re.sub(r"<[^>]+>", "", s).replace("&#8211;", "–").replace("&#8222;", "„").replace("&#8220;", "“").replace("&amp;", "&").replace("&nbsp;", " ")
    return [{"date": i["date"][:10], "title": unesc(i["title"]["rendered"]), "link": i["link"]} for i in items]

def write(path, data):
    try:
        if json.load(open(path, encoding="utf8")) == data:
            return
    except Exception:
        pass
    json.dump(data, open(path, "w", encoding="utf8"), ensure_ascii=False, separators=(",", ":"))

if __name__ == "__main__":
    for fn, path in ((menu, "menu.json"), (news, "news.json")):
        try:
            data = fn()
            if data:
                write(path, data)
        except Exception as e:  # a broken source must not break the other one or fail the workflow
            print(path, "ebaõnnestus:", e)
