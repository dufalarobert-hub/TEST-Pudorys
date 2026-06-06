"""
Extrakcia parametrov stavby z pôdorysu pomocou Gemini vízie.

Vstup: cesta k PDF / PNG / JPG (pôdorys rodinného domu).
Výstup: dict s dĺžkou obvodového zdiva, priečok, kótami, plochami a confidence.

Poznámka k presnosti (overené probe-mi 2026-06-04):
  - Obvod z kót = spoľahlivý (priama matematika z vonkajších rozmerov).
  - Priečky = AI odhad od oka (slabší článok, ~±15-20 %). MVP rozhodnutie: zatiaľ stačí.
  - Posielame CELÝ výkres vo vysokom DPI (orezanie zhoršuje čítanie spodku plánu).
"""
import io
import json
import re

import fitz  # PyMuPDF
from PIL import Image
from google import genai
from google.genai import types

import config

MAX_SCAN_PAGES = 25     # koľko strán projektovej dokumentácie prejdeme pri hľadaní pôdorysu
RENDER_ZOOM = 3.0       # DPI faktor pre render strán
MAX_SIDE_PX = 2200      # downscale aby sme nezahltili request


EXTRACTION_PROMPT = r"""Jsi expert na stavební rozpočty a čtení půdorysů rodinných domů.
Dostáváš jednu nebo více stránek projektu RD (může mezi nimi být zakótovaný půdorys i parametrický popis).

ZÁSADA: dokumenty jsou RŮZNÉ (jiný architekt, software, formát, jazyk, zkratky). Čti je
VÝZNAMOVĚ — rozuměj tomu, CO na výkresu je (rozměry, materiál, plochy, otvory), a vytěž
maximum z toho, co je k dispozici. NEspoléhej na konkrétní vzory/formáty; příklady níže
jsou jen ILUSTRACE, ne pravidla. Co není v dokumentu, nevymýšlej — vrať null a sniž confidence.

Tvůj úkol: z výkresu vyčíst data potřebná pro odhad ceny HRUBÉ STAVBY (zdivo).

DRUH OBJEKTU A KONSTRUKCE (důležité — kalkulačka platí jen pro ZDĚNÝ RODINNÝ DŮM):
Rozpoznej VÝZNAMOVĚ, CO je na výkrese:
- typ_stavby: jde o celý rodinný dům, nebo jen o BYT (jedna bytová jednotka v patře — popisek
  "byt", "byt č.", dispozice typu "3+kk/2+1", okolo jsou sousední jednotky, jen část podlaží),
  nebo o BYTOVÝ DŮM (více bytů), nebo něco jiného (hala, garáž, komerční objekt).
- konstrukce: je nosný systém ZDĚNÝ (cihla/tvárnice/pórobeton), DŘEVOSTAVBA (rámová/sloupková,
  dřevěné stěny), nebo SKELET/jiné (železobetonový/ocelový skelet)?
DŮLEŽITÉ — buď KONZERVATIVNÍ: když to z výkresu jednoznačně NEPLYNE, předpokládej
typ_stavby="rodinny_dum" a konstrukce=null (= bereme jako zděný RD). Hodnotu "byt" / "drevostavba"
/ "skelet" dej JEN když je pro to v dokumentu jasný signál (popisek, legenda, charakter výkresu).

POSTUP:
1. Najdi zakótovaný půdorys. Přečti kóty (v mm) DOSLOVA z obrázku.
   POZOR na jednotky kót: mohou být v mm (např. 11000) NEBO v metrech (např. 11.0 m).
   Rozpoznej to a VŠE přepočítej do metrů. Pokud jsou kóty ve STOPÁCH/PALCÍCH (znaky ' a "
   nebo formát 34'-6"), přepočítej na metry (1' = 0,3048 m, 1" = 0,0254 m) a v note to uveď.
   Pokud je výkres focený POD ÚHLEM / pootočený / rozmazaný / ručně kreslený (ne čistý CAD),
   výrazně SNIŽ confidence a uveď to v note — kóty pak nejsou spolehlivé.
2. Obvodové zdivo: spočítej délku vnějšího obrysu domu z celkových kót
   (např. obdélník 11000 x 13500 mm => obvod = 2*(11+13.5) = 49 m; nebo 17.10 x 8.90 m
   => 2*(17.1+8.9) = 52 m). U členitého (L/U) tvaru sečti všechny vnější strany.
3. VNITŘNÍ STĚNY — rozliš DVA druhy podle TLOUŠŤKY (důležité, mají různou cenu):
   a) VNITŘNÍ NOSNÉ stěny — silnější (~175-300 mm), často značené "nosná" / kreslené
      tlustě jako obvod. Součet jejich délek do "vnitrni_nosne_m" + tloušťka.
   b) PŘÍČKY — tenké dělící stěny (~75-150 mm). Součet délek do "pricky_m" + tloušťka.
   Když to nerozlišíš spolehlivě, dej vše do pricky_m a vnitrni_nosne_m = 0.
   Stěny GARÁŽE započítej podle funkce (obvodová garáže do obvod_m, vnitřní nosná
   garáže do vnitrni_nosne_m). Buď upřímný že délky jsou odhad.
4. TLOUŠŤKA ZDIVA — POZOR, klíčové: urči tloušťku samotné NOSNÉ TVÁRNICE / CIHLY
   (zdiva), NE celé skladby stěny vč. zateplení. Pokud je obvodová stěna SLOŽENÁ
   (např. "OBVODOVÁ STĚNA tl. 500 mm = YTONG Standard 300 + tepelná izolace 200 mm"),
   vrať tloušťku BLOKU = 300 (NE celkových 500!). Nezapočítávej zateplení/izolaci,
   obklad ani omítku. Když vidíš v legendě/popisu typ tvárnice (např. "Ytong 300",
   "Porotherm 44"), vezmi to číslo. Obvodové zdivo bývá 240-450 mm, příčky 80-150 mm.
   DŮLEŽITÉ: tloušťka stěny je často MALÁ KÓTA přímo u stěny v kótovacím řetězci
   (řetězec vypadá např. "500 · 3500 · 150 · 2250 · 150 …" kde 500 = tloušťka obvodu,
   150 = tloušťka příčky mezi místnostmi). Tyto malé kóty u stěn PŘEČTI a použij,
   a nastav tloustka_z_koty=true. POZOR: pokud je obvodová stěna ŠRAFOVANÁ (křížkové
   šrafy = složená stěna s izolací) a kóta je velká (450-550 mm), je to nejspíš
   ZDIVO+ZATEPLENÍ — odhadni tloušťku samotného zdiva (~300-375) a ma_zateplenie=true.
4b. MATERIÁL OBVODOVÉHO ZDIVA (je-li v dokumentu uveden — je to NEJSPOLEHLIVĚJŠÍ údaj, VYTĚŽ ho):
   Specifikace materiálu může být KDEKOLIV a JAKKOLIV zapsaná — legenda materiálů, skladba stěny,
   popiska/odkaz u stěny, tabulka, technická zpráva, poznámka. Čti VÝZNAMOVĚ: pochop, z ČEHO je
   OBVODOVÁ nosná stěna a jakou má tloušťku, bez ohledu na konkrétní formát, značku či jazyk.
   Materiál ZAŘAĎ do cenové třídy (obvod_material_trieda) podle jeho POVAHY (ne podle názvu):
     - "lacne"   = základní / levnější zdicí bloky
     - "stredne" = běžné nosné zdivo (běžná keramika nebo pórobeton standardní hustoty)
     - "drahe"   = jednovrstvý TEPELNĚIZOLAČNÍ blok (plněný izolací / nízká λ, nepotřebuje
                   samostatné zateplení)
   Je-li u obvodové stěny uvedena samostatná vrstva TEPELNÉ IZOLACE (jakákoliv) → ma_zateplenie=true
   (zdivo = jen nosný blok, ne celá skladba).
   (Jen ILUSTRACE zápisu, NE vyčerpávající seznam: "cihelné bloky 300", "Ytong Standard 300",
   "Porotherm 44 T Profi", "tvárnice P+D 240".)
   Vyplň obvod_material (co jsi přečetl), obvod_material_trieda a zdivo_zdroj.
   Když materiál nikde NENÍ → obvod_material=null, obvod_material_trieda=null,
   zdivo_zdroj = "kóta" (máš-li tloušťku z kót) nebo "odhad".
5. PLOCHA (důležité pro cross-check): Pokud jsou u místností popsané plochy
   (např. "Obývací pokoj 43,56 m²", "Ložnice 12,26 m²"), SEČTI je všechny do
   uzitna_plocha_m2 a vrať i jejich seznam. Terasu/balkon do užitné NEpočítej.
   Zastavěnou plochu vezmi z parametrů, nebo odhadni z vnějšího obrysu (šířka×délka).
   Když je oficiální užitná/zastavěná uvedena v popisu, použij ji.
6. Spočítej okna a dveře (i odhadem). Okna/dveře poznáš podle přerušení ve stěně
   se symbolem otevírání (oblouk) nebo podle šířkové kóty otvoru (800, 900, 2150…).
   SPOLEHLIVĚJŠÍ: pokud je v dokumentu TABULKA / VÝPIS OKEN A DVEŘÍ (značky O1, O2, D1…
   s rozměry a počty kusů), použij počty a šířky ODTUD — je to tvrdší údaj než počítání
   symbolů na půdorysu. (Čti významově — výpis může být jakkoliv nadepsaný.)
7. SCHODIŠTĚ: je na půdorysu schodiště (stupně, šipka nahoru/dolů, "S" značka)? Pokud ano,
   dům má skoro jistě víc podlaží (nebo podkroví/sklep) → ma_schodiste=true. To je signál,
   že počítat jen 1 podlaží by bylo podcenění.
8. VÝŠKA PODLAŽÍ: pokud je k dispozici ŘEZ domu nebo výšková kóta (konstrukční/světlá výška,
   např. 2,75 / 3,0 m), použij ji do vyska_podlazi_m. Když ji nevidíš, nech null
   (dosadí se typická 2,8 m) a NEZVYŠUJ kvůli tomu confidence.

Vrať POUZE validní JSON (žádný text okolo), přesně v tomto schématu:
{
  "typ_stavby": "rodinny_dum" | "byt" | "bytovy_dum" | "jine"   (konzervativně: nejsi-li si jistý, "rodinny_dum"),
  "konstrukce": "zdene" | "drevostavba" | "skelet" | null        (nejsi-li si jistý → null = bereme jako zděné),
  "obvod_m": <číslo>,
  "obvod_tloustka_mm": <číslo>,
  "tloustka_z_koty": <true/false — je tloušťka NOSNÉ TVÁRNICE dána výslovně (kóta tloušťky NEBO typ tvárnice v legendě, např. "Ytong 300")? true jen pokud to vidíš; jinak false (vizuální odhad)>,
  "ma_zateplenie": <true/false — je u obvodové stěny uvedena samostatná vrstva tepelné izolace / zateplení?>,
  "obvod_material": <string: materiál obvodového zdiva přečtený z dokumentu (legenda/skladba/popis), nebo null>,
  "obvod_material_trieda": "lacne" | "stredne" | "drahe" | null,
  "zdivo_zdroj": "legenda" | "kóta" | "odhad",
  "vnitrni_nosne_m": <součet délek vnitřních NOSNÝCH stěn v m, 0 pokud žádné>,
  "vnitrni_nosne_tloustka_mm": <číslo nebo null>,
  "pricky_m": <číslo>,
  "pricky_tloustka_mm": <číslo>,
  "plochy_mistnosti_m2": [<plochy jednotlivých místností které vidíš>],
  "uzitna_plocha_m2": <součet ploch místností, nebo oficiální údaj, nebo null>,
  "zastavena_plocha_m2": <číslo nebo null>,
  "pocet_podlazi": <číslo nebo null>,
  "ma_schodiste": <true/false — je na půdorysu schodiště (= dům má pravděpodobně víc podlaží)?>,
  "vyska_podlazi_m": <číslo nebo null>,
  "pocet_oken": <číslo nebo null>,
  "pocet_dveri": <číslo nebo null>,
  "pocet_mistnosti": <číslo nebo null>,
  "koty_mm": [<přečtené kóty>],
  "meritko_source": "z kót" | "měřítko/scale bar" | "plochy m²" | "žádné",
  "confidence_0_100": <číslo>,
  "co_potvrdit": ["max 4 věci které má uživatel potvrdit/doplnit"],
  "note": "1-2 věty: jak přesný odhad je a kde je největší riziko"
}
Pokud něco nelze přečíst, dej null a sniž confidence. Nevymýšlej si přesné kóty které nevidíš."""


def _pages_to_images(path: str, max_side: int = MAX_SIDE_PX, only_page=None):
    """PDF -> zoznam PNG bytes; obrázok -> [bytes].
    only_page = vyrenderuj LEN tú jednu stranu (na pôdorys vybraný z projektu)."""
    p = str(path).lower()
    imgs = []
    if p.endswith(".pdf"):
        doc = fitz.open(path)
        idxs = [only_page] if only_page is not None else range(min(doc.page_count, MAX_SCAN_PAGES))
        for i in idxs:
            pix = doc[i].get_pixmap(matrix=fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM))
            imgs.append(Image.open(io.BytesIO(pix.tobytes("png"))))
        doc.close()
    else:
        imgs.append(Image.open(path).convert("RGB"))

    out = []
    for im in imgs:
        if max(im.size) > max_side:
            scale = max_side / max(im.size)
            im = im.resize((int(im.width * scale), int(im.height * scale)))
        buf = io.BytesIO()
        im.convert("RGB").save(buf, format="PNG")
        out.append(buf.getvalue())
    return out


PLAN_PICK_PROMPT = """Dostáváš očíslované stránky (0, 1, 2, …) stavební dokumentace rodinného domu.
Najdi stránku, která je PŮDORYS PŘÍZEMÍ (1.NP) — okótovaný plán půdorysu s místnostmi a kótami.
NENÍ to: řez, pohled (fasáda), situace, výkres krovu/základů/stropů, ani textová zpráva/tabulka.
Když je víc půdorysů různých podlaží, vyber PŘÍZEMÍ (1.NP).
Vrať POUZE JSON: {"plan_page": <index stránky s půdorysem>, "found": true/false}.
Když mezi stránkami žádný půdorys není, dej found=false a plan_page=0."""


MAX_DOC_PAGES = 150         # tvrdý strop (extrémne PDF neprocesujeme celé)
MAX_PLAN_CANDIDATES = 14    # koľko "výkresových" strán pošleme Geminimu na výber pôdorysu


def _drawing_candidate_idxs(doc):
    """LACNÝ lokálny predfilter (bez AI): z veľkého projektu vyber strany čo vyzerajú ako
    VÝKRES (veľa vektorových čiar / veľký raster, málo textu) — nie technická zpráva,
    tabuľka, titulka. Vráti zoradené indexy strán (kandidátov na pôdorys)."""
    n = min(doc.page_count, MAX_DOC_PAGES)
    scored = []
    for i in range(n):
        page = doc[i]
        t = len(page.get_text("text") or "")
        try:
            d = len(page.get_drawings())
        except Exception:
            d = 0
        has_img = len(page.get_images()) > 0
        is_drawingish = (d >= 40 or has_img) and t < 2000   # výkres = čiary/raster + málo textu
        score = d + (800 if has_img else 0) - t * 0.05
        scored.append((is_drawingish, score, i))
    draws = [(s, i) for dl, s, i in scored if dl]
    if draws:
        draws.sort(reverse=True)
        return sorted(i for _, i in draws[:MAX_PLAN_CANDIDATES])
    return list(range(min(n, MAX_PLAN_CANDIDATES)))     # fallback: prvých N strán


def _pick_plan_page(path: str):
    """Viacstránkové PDF/projekt -> index strany s pôdorysom 1.NP.
    Veľký projekt: lacný lokálny predfilter na výkresové strany → Gemini vyberie pôdorys.
    Vráti (idx, pocet_stran). Pre obrázok / 1-stranové PDF vráti (0, 1)."""
    p = str(path).lower()
    if not p.endswith(".pdf"):
        return 0, 1
    doc = fitz.open(path)
    n = doc.page_count
    if n <= 1:
        doc.close()
        return 0, n
    # malé projekty: vezmi všetky strany; veľké: len výkresových kandidátov
    cand = list(range(min(n, MAX_SCAN_PAGES))) if n <= MAX_PLAN_CANDIDATES else _drawing_candidate_idxs(doc)
    parts = []
    for pos, i in enumerate(cand):
        pix = doc[i].get_pixmap(matrix=fitz.Matrix(1.4, 1.4))
        im = Image.open(io.BytesIO(pix.tobytes("png")))
        if max(im.size) > 760:
            s = 760 / max(im.size)
            im = im.resize((int(im.width * s), int(im.height * s)))
        buf = io.BytesIO()
        im.convert("RGB").save(buf, format="PNG")
        parts.append(f"Stránka {pos}:")
        parts.append(types.Part.from_bytes(data=buf.getvalue(), mime_type="image/png"))
    doc.close()
    parts.append(PLAN_PICK_PROMPT)
    try:
        client = genai.Client(api_key=config.get_gemini_key())
        cfg = types.GenerateContentConfig(thinking_config=types.ThinkingConfig(thinking_budget=256))
        resp = client.models.generate_content(model=config.GEMINI_VISION_MODEL, contents=parts, config=cfg)
        d = _parse_json(resp.text)
        pos = int(_num(d.get("plan_page"), 0) or 0)
        if not d.get("found") or pos < 0 or pos >= len(cand):
            pos = 0
        return cand[pos], n           # mapuj pozíciu v zozname kandidátov na skutočnú stranu
    except Exception:
        return (cand[0] if cand else 0), n


def _parse_json(text: str) -> dict:
    text = text.strip()
    # odstráň prípadné ```json ... ``` obaly
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group(0)
    return json.loads(text)


def extract_from_plan(path: str) -> dict:
    """Hlavná funkcia: cesta k súboru -> extrahované parametre (dict).
    Pri viacstránkovom projekte najprv vyberie stránku s pôdorysom, potom z nej extrahuje."""
    page_idx, n_pages = _pick_plan_page(path)          # medzikrok pre projektovú dokumentáciu
    only = page_idx if (str(path).lower().endswith(".pdf") and n_pages > 1) else None
    images = _pages_to_images(path, only_page=only)
    parts = [types.Part.from_bytes(data=img, mime_type="image/png") for img in images]
    parts.append(EXTRACTION_PROMPT)

    client = genai.Client(api_key=config.get_gemini_key())
    cfg = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=config.GEMINI_THINKING_BUDGET))
    last_err = None
    for model in (config.GEMINI_VISION_MODEL, config.GEMINI_VISION_FALLBACK):
        try:
            resp = client.models.generate_content(model=model, contents=parts, config=cfg)
            data = _parse_json(resp.text)
            data["_model"] = model
            data["_pages"] = len(images)
            data["_page_idx"] = page_idx
            data["_pages_total"] = n_pages
            data["_from_project"] = n_pages > 1
            um = getattr(resp, "usage_metadata", None)
            data["_usage"] = {
                "in": getattr(um, "prompt_token_count", 0) or 0,
                "out": getattr(um, "candidates_token_count", 0) or 0,
            } if um else {"in": 0, "out": 0}
            return _normalize(data)
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
    raise RuntimeError(f"Extrakcia zlyhala: {last_err}")


def _num(v, default=None):
    try:
        if v is None:
            return default
        return float(str(v).replace(",", "."))
    except (ValueError, TypeError):
        return default


def _normalize(d: dict) -> dict:
    """Zjednoť typy a doplň rozumné defaulty pre chýbajúce hodnoty."""
    # úžitná plocha: ak chýba, sčítaj plochy miestností
    rooms = [_num(x) for x in (d.get("plochy_mistnosti_m2") or []) if _num(x)]
    uzit = _num(d.get("uzitna_plocha_m2"))
    if not uzit and rooms:
        uzit = round(sum(rooms), 1)
    d["uzitna_plocha_m2"] = uzit
    return {
        # konzervatívne defaulty: keď model netrafí enum, beriem ako murovaný RD (nech neodmietneme reálny dom)
        "typ_stavby": (d.get("typ_stavby") if d.get("typ_stavby") in
                       ("rodinny_dum", "byt", "bytovy_dum", "jine") else "rodinny_dum"),
        "konstrukce": (d.get("konstrukce") if d.get("konstrukce") in
                       ("zdene", "drevostavba", "skelet") else None),
        "obvod_m": _num(d.get("obvod_m"), 0) or 0,
        "obvod_tloustka_mm": int(_num(d.get("obvod_tloustka_mm"), 300) or 300),
        "tloustka_z_koty": bool(d.get("tloustka_z_koty")),
        "ma_zateplenie": bool(d.get("ma_zateplenie")),
        "obvod_material": d.get("obvod_material") or None,
        "obvod_material_trieda": (d.get("obvod_material_trieda")
                                  if d.get("obvod_material_trieda") in ("lacne", "stredne", "drahe") else None),
        "zdivo_zdroj": d.get("zdivo_zdroj") or ("kóta" if d.get("tloustka_z_koty") else "odhad"),
        "vnitrni_nosne_m": _num(d.get("vnitrni_nosne_m"), 0) or 0,
        "vnitrni_nosne_tloustka_mm": int(_num(d.get("vnitrni_nosne_tloustka_mm"), 250) or 250),
        "pricky_m": _num(d.get("pricky_m"), 0) or 0,
        "pricky_tloustka_mm": int(_num(d.get("pricky_tloustka_mm"), 100) or 100),
        "uzitna_plocha_m2": _num(d.get("uzitna_plocha_m2")),
        "zastavena_plocha_m2": _num(d.get("zastavena_plocha_m2")),
        "plochy_mistnosti_m2": rooms,
        "pocet_podlazi": int(_num(d.get("pocet_podlazi"), 1) or 1),
        "ma_schodiste": bool(d.get("ma_schodiste")),
        "vyska_podlazi_m": _num(d.get("vyska_podlazi_m"), 2.8) or 2.8,
        "pocet_oken": int(_num(d.get("pocet_oken"), 0) or 0),
        "pocet_dveri": int(_num(d.get("pocet_dveri"), 0) or 0),
        "pocet_mistnosti": int(_num(d.get("pocet_mistnosti"), 0) or 0),
        "koty_mm": d.get("koty_mm") or [],
        "meritko_source": d.get("meritko_source") or "žádné",
        "confidence_0_100": int(_num(d.get("confidence_0_100"), 40) or 40),
        "co_potvrdit": d.get("co_potvrdit") or [],
        "note": d.get("note") or "",
        "_model": d.get("_model", ""),
        "_pages": d.get("_pages", 1),
        "_usage": d.get("_usage", {"in": 0, "out": 0}),
        "_page_idx": int(d.get("_page_idx", 0) or 0),
        "_pages_total": int(d.get("_pages_total", 1) or 1),
        "_from_project": bool(d.get("_from_project")),
    }


if __name__ == "__main__":
    import sys
    res = extract_from_plan(sys.argv[1])
    print(json.dumps(res, ensure_ascii=False, indent=2))
