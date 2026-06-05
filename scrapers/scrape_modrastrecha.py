"""
Scraper normálnych pôdorysov z modrastrecha.cz fóra.
Filter: hi-res landscape + nízka sýtosť (= výkres, nie telefónny screenshot/fotka).
Ukladá do ../test_podorysy/ ako plan_<id>.jpg.

Použitie:  python3 scrape_modrastrecha.py [počet]   (default 6)
"""
import os, re, sys, time, io, requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from PIL import Image

NEED = int(sys.argv[1]) if len(sys.argv) > 1 else 6
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_podorysy")
os.makedirs(OUT, exist_ok=True)
have = set(re.findall(r"(\d+)", " ".join(os.listdir(OUT))))

s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"})
RX = re.compile(r"https?://static\.4nets\.sk/photo/\S+?_1600\.jpe?g", re.I)
CATS = ["projekty", "novostavby", "montovane-domy-drevostavby", "rekonstrukce-stareho-domu", "podkrovi"]


def is_plan(content):
    """Hi-res landscape výkres s nízkou sýtosťou (nie fotka/screenshot)."""
    try:
        im = Image.open(io.BytesIO(content)).convert("RGB"); w, h = im.size
        if w < 1000 or not (1.0 <= w / h <= 2.4):
            return False
        px = list(im.resize((150, 110)).convert("HSV").getdata())
        sat = sum(p[1] for p in px) / len(px)
        val = sum(p[2] for p in px) / len(px)
        hi = sum(1 for p in px if p[1] > 120) / len(px)
        return sat < 42 and val > 168 and hi < 0.10
    except Exception:
        return False


seen = set(); got = 0
for slug in CATS:
    for page in range(1, 7):
        if got >= NEED:
            break
        url = f"https://www.modrastrecha.cz/forum/category/{slug}/" + ("" if page == 1 else f"?page={page}")
        try:
            cs = BeautifulSoup(s.get(url, timeout=30).content, "html.parser")
        except Exception:
            continue
        topics = dict.fromkeys(urljoin(url, a["href"]) for a in
                               cs.find_all("a", href=re.compile(rf"/forum/{slug}/[^/?]+/$")))
        for t in topics:
            if got >= NEED:
                break
            try:
                html = s.get(t, timeout=30).text
            except Exception:
                continue
            for u in RX.findall(html):
                if got >= NEED:
                    break
                pid = re.search(r"/(\d+)_1600", u).group(1)
                if pid in seen or pid in have:
                    continue
                seen.add(pid)
                try:
                    r = s.get(u, timeout=60)
                    if is_plan(r.content):
                        open(os.path.join(OUT, f"plan_{pid}.jpg"), "wb").write(r.content)
                        got += 1
                        print(f"  ✅ [{got}/{NEED}] plan_{pid}.jpg")
                except Exception:
                    pass
            time.sleep(0.25)
print(f"Hotovo: {got} nových pôdorysov v {OUT}")
