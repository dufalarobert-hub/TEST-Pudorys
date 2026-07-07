"""
Extrakcia parametrov stavby z pôdorysu pomocou AI vízie (model-agnostická).

Vstup: cesta k PDF / PNG / JPG (pôdorys rodinného domu).
Výstup: dict s dĺžkou obvodového zdiva, priečok, kótami, plochami a confidence.

MODEL: volí sa cez providers.py (EXTRACTOR_PROVIDER=gemini|anthropic) — tento
modul model NEPOZNÁ, stavia prompt, renderuje PDF a normalizuje výstup.

Poznámka k presnosti (overené probe-mi 2026-06-04):
  - Obvod z kót = spoľahlivý (priama matematika z vonkajších rozmerov).
  - Priečky = AI odhad od oka (slabší článok, ~±15-20 %). MVP rozhodnutie: zatiaľ stačí.
  - Posielame CELÝ výkres vo vysokom DPI (orezanie zhoršuje čítanie spodku plánu).
"""
import io
import json
import os
import re
import statistics
from concurrent.futures import ThreadPoolExecutor

import fitz  # PyMuPDF
from PIL import Image

import providers

MAX_SCAN_PAGES = 25     # koľko strán projektovej dokumentácie prejdeme pri hľadaní pôdorysu
RENDER_ZOOM = 4.0       # DPI faktor pre render strán (3.0→4.0: viac detailu na čítanie drobných kót stien)
MAX_SIDE_PX = 3000      # downscale cap (2200→3000: čitateľnejšie kótovacie reťazce = presnejšie dĺžky stien)


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
2. Obvodové zdivo: spočítej délku obrysu jen ZDĚNÉ / VYTÁPĚNÉ budovy (po STĚNÁCH). POZORNĚ
   obkruž obvod a sečti všechny strany budovy — včetně garáže, přístavků, výstupků, zalomení
   (L/U/T tvary, arkýře, ustoupení).
   !!! NEzahrnuj do obvodu TERASU, balkon, dřevěnou palubu/dlubu, dlažbu, chodník, pergolu ani
   kryté stání / přístřešek (carport) — to jsou plochy BEZ obvodových stěn, často kreslené
   ČÁRKOVANĚ nebo jako dlažba MIMO obrys domu. Obvod veď JEN tam, kde je nakreslená stěna
   (plný šrafovaný/tlustý pás), NE po hraně terasy/zpevněné plochy. (Toto je častá chyba —
   terasa nafoukne obvod a zdvojnásobí cenu.)
   (Příklad: obdélník 11000 x 13500 mm => 2*(11+13.5) = 49 m; L-tvar = součet stran po obvodu.)
   Vyplň i "rozmery_celkove_m" — CELKOVOU šířku a délku domu z HLAVNÍCH (nejdelších)
   kót obvodu (bez terasy). To je tvrdá kontrola: obvod pravoúhlého domu NEMŮŽE být
   menší než 2×(šířka+délka).
   KONTROLA SAMA SEBE: reálné domy mají obvod typicky 4,2-5,5 * odmocnina(zastavěná plocha).
   Když ti vyjde MÉNĚ než 4*√plocha → přehlédl jsi část obvodu. Když VÍCE než ~6*√plocha →
   nejspíš jsi do obvodu zahrnul terasu/zpevněnou plochu — veď obrys jen po stěnách domu.
3. VNITŘNÍ STĚNY — rozliš DVA druhy podle TLOUŠŤKY (důležité, mají různou cenu):
   a) VNITŘNÍ NOSNÉ stěny — silnější (~175-300 mm), často značené "nosná" / kreslené
      tlustě jako obvod. Součet jejich délek do "vnitrni_nosne_m" + tloušťka.
   b) PŘÍČKY — tenké dělící stěny (~75-150 mm). Součet délek do "pricky_m" + tloušťka.
   Když to nerozlišíš spolehlivě, dej vše do pricky_m a vnitrni_nosne_m = 0.
3c. GARÁŽ / VEDLEJŠÍ NEVYTÁPĚNÉ PROSTORY — VÝSLOVNĚ ZKONTROLUJ (častá chyba = vynechání!):
   Projdi celý výkres a zjisti, jestli je SOUČÁSTÍ domu UZAVŘENÁ garáž, technická místnost nebo
   dílna OHRANIČENÁ STĚNAMI (poznáš podle popisku „garáž/technická/dílna", garážových vrat,
   nebo místnosti bez oken s autem OBKLOPENÉ stěnami). Takové stěny započítej do obvod_m /
   vnitrni_nosne_m / pricky_m podle tloušťky a nastav ma_garaz=true.
   POZOR — OTEVŘENÉ kryté stání / carport / přístřešek (jen střecha na sloupcích, BEZ stěn) a
   terasa NEMAJÍ obvodové zdivo → NEzapočítávej je do žádné délky stěn. Garáž = stěny ANO;
   carport/terasa = stěny NE. Když garáž ani vedlejší
   prostor není, ma_garaz=false. Buď upřímný, že délky jsou odhad.
   GARÁŽOVÁ VRATA NEpočítej mezi okna ani dveře — kalkulace je řeší zvlášť přes ma_garaz
   (překlad velkého rozponu i odpočet plochy vrat).
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
   Do pocet_dveri počítej VŠECHNY dveře VČETNĚ vchodových (vchod se v kalkulaci
   rozlišuje automaticky). Garážová vrata do počtů NEpatří (viz 3c).
6b. OTVORY JEDNOTLIVĚ (přesnější odpočet stěny + překlady podle rozponu): pokud jdou
   ŠÍŘKY otvorů vyčíst (šířkové kóty u otvorů, např. 900/1200/2400, nebo VÝPIS OKEN
   A DVEŘÍ), vyplň seznam "otvory" — položky {"typ", "sirka_m", "pocet"}:
   typ = "okno" | "francouzske_okno" (okno až na zem) | "hs_portal" (velké posuvné
   prosklení) | "dvere_vchod" | "dvere_vnitrni". Šířky v METRECH. Co spolehlivě
   nevyčteš, do seznamu NEdávej — seznam smí být i prázdný (kalkulace pak použije
   průměry). Když seznam vyplníš, počty musí sedět s pocet_oken/pocet_dveri.
   SPOLEHLIVĚJŠÍ: pokud je v dokumentu TABULKA / VÝPIS OKEN A DVEŘÍ (značky O1, O2, D1…
   s rozměry a počty kusů), použij počty a šířky ODTUD — je to tvrdší údaj než počítání
   symbolů na půdorysu. (Čti významově — výpis může být jakkoliv nadepsaný.)
7. SCHODIŠTĚ: je na půdorysu schodiště (stupně, šipka nahoru/dolů, "S" značka)? Pokud ano,
   dům má skoro jistě víc podlaží (nebo podkroví/sklep) → ma_schodiste=true. To je signál,
   že počítat jen 1 podlaží by bylo podcenění.
8. VÝŠKA PODLAŽÍ: pokud je k dispozici ŘEZ domu nebo výšková kóta, dej do vyska_podlazi_m
   KONSTRUKČNÍ výšku podlaží (podlaha–podlaha, např. 3,0 m). Máš-li jen SVĚTLOU výšku
   místnosti (např. 2,6 m), přičti ~0,4 m na strop+podlahu a uveď to v note.
   Když výšku nevidíš, nech null (dosadí se typická) a NEZVYŠUJ kvůli tomu confidence.

Vrať POUZE validní JSON (žádný text okolo), přesně v tomto schématu:
{
  "typ_stavby": "rodinny_dum" | "byt" | "bytovy_dum" | "jine"   (konzervativně: nejsi-li si jistý, "rodinny_dum"),
  "konstrukce": "zdene" | "drevostavba" | "skelet" | null        (nejsi-li si jistý → null = bereme jako zděné),
  "obvod_m": <číslo>,
  "rozmery_celkove_m": {"sirka_m": <celková šířka domu z hlavní kóty>, "dlzka_m": <celková délka>} nebo null,
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
  "ma_garaz": <true/false — je součástí domu garáž / technická místnost / dílna / vedlejší nevytápěná část? (jsou-li, jejich stěny MUSÍ být v délkách zahrnuty)>,
  "vyska_podlazi_m": <číslo nebo null>,
  "otvory": [{"typ": "okno|francouzske_okno|hs_portal|dvere_vchod|dvere_vnitrni", "sirka_m": <číslo>, "pocet": <číslo>}, …]   (jen otvory s vyčtenou šířkou; smí být []),
  "pocet_oken": <číslo nebo null — BEZ garážových vrat>,
  "pocet_dveri": <číslo nebo null — všechny dveře VČETNĚ vchodových, BEZ garážových vrat>,
  "pocet_mistnosti": <číslo nebo null>,
  "koty_mm": [<max ~30 NEJDŮLEŽITĚJŠÍCH přečtených kót (celkové rozměry, tloušťky stěn)>],
  "meritko_source": "z kót" | "měřítko/scale bar" | "plochy m²" | "žádné",
  "confidence_0_100": <číslo>,
  "co_potvrdit": ["max 4 věci které má uživatel potvrdit/doplnit"],
  "note": "1-2 věty: jak přesný odhad je a kde je největší riziko"
}
Pokud něco nelze přečíst, dej null a sniž confidence. Nevymýšlej si přesné kóty které nevidíš."""


# JSON Schema extrakcie — pre providery so ŠTRUKTÚROVANÝM výstupom (Claude/Fable tool-use
# ju vynúti na úrovni API; Gemini beží v JSON-mode a schému nesie prompt vyššie).
_NUM = {"type": ["number", "null"]}
_BOOL = {"type": "boolean"}
EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "typ_stavby": {"type": "string", "enum": ["rodinny_dum", "byt", "bytovy_dum", "jine"]},
        "konstrukce": {"type": ["string", "null"], "enum": ["zdene", "drevostavba", "skelet", None]},
        "obvod_m": _NUM,
        "rozmery_celkove_m": {"type": ["object", "null"], "properties": {
            "sirka_m": {"type": "number"}, "dlzka_m": {"type": "number"}}},
        "obvod_tloustka_mm": _NUM,
        "tloustka_z_koty": _BOOL, "ma_zateplenie": _BOOL,
        "obvod_material": {"type": ["string", "null"]},
        "obvod_material_trieda": {"type": ["string", "null"], "enum": ["lacne", "stredne", "drahe", None]},
        "zdivo_zdroj": {"type": "string", "enum": ["legenda", "kóta", "odhad"]},
        "vnitrni_nosne_m": _NUM, "vnitrni_nosne_tloustka_mm": _NUM,
        "pricky_m": _NUM, "pricky_tloustka_mm": _NUM,
        "plochy_mistnosti_m2": {"type": "array", "items": {"type": "number"}},
        "uzitna_plocha_m2": _NUM, "zastavena_plocha_m2": _NUM,
        "pocet_podlazi": _NUM, "ma_schodiste": _BOOL, "ma_garaz": _BOOL,
        "vyska_podlazi_m": _NUM,
        "otvory": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "typ": {"type": "string", "enum": ["okno", "francouzske_okno", "hs_portal",
                                                    "dvere_vchod", "dvere_vnitrni"]},
                "sirka_m": {"type": "number"},
                "pocet": {"type": "integer"},
            },
            "required": ["typ", "sirka_m", "pocet"],
        }},
        "pocet_oken": _NUM, "pocet_dveri": _NUM, "pocet_mistnosti": _NUM,
        "koty_mm": {"type": "array", "items": {"type": "number"}},
        "meritko_source": {"type": "string"},
        "confidence_0_100": {"type": "number"},
        "co_potvrdit": {"type": "array", "items": {"type": "string"}},
        "note": {"type": "string"},
    },
    "required": ["typ_stavby", "obvod_m", "confidence_0_100"],
}


def _pages_to_images(path: str, max_side: int = MAX_SIDE_PX, only_page=None, pages=None):
    """PDF -> zoznam PNG bytes; obrázok -> [bytes].
    only_page = vyrenderuj LEN tú jednu stranu; pages = konkrétny zoznam strán
    (PD deep-mining: pôdorys + rez + výpis otvorov)."""
    p = str(path).lower()
    imgs = []
    if p.endswith(".pdf"):
        doc = fitz.open(path)
        if pages is not None:
            idxs = pages
        elif only_page is not None:
            idxs = [only_page]
        else:
            idxs = range(min(doc.page_count, MAX_SCAN_PAGES))
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


CLASSIFY_PROMPT = """Dostáváš stránky stavební dokumentace rodinného domu — obrázky jsou
V POŘADÍ a číslují se od nuly (první obrázek = stránka 0, druhý = 1, …).
Urči, které stránky obsahují (indexy podle pořadí obrázků):
- "podorys_1np": okótovaný PŮDORYS PŘÍZEMÍ (1.NP) — plán s místnostmi a kótami
- "podorys_2np": okótovaný půdorys DALŠÍHO nadzemního podlaží (2.NP / patro / obytné
  podkroví). Sklep/suterén NE.
- "rez": svislý ŘEZ domem (výškové kóty, označení A-A' apod.)
- "vypis_otvorov": TABULKA / výpis oken a dveří (značky O1, O2, D1… s rozměry a počty)
PŮDORYS NENÍ: pohled (fasáda), situace, výkres krovu/základů/stropů, textová zpráva.
Vrať POUZE JSON:
{"podorys_1np": <idx nebo null>, "podorys_2np": <idx nebo null>, "rez": <idx nebo null>,
 "vypis_otvorov": <idx nebo null>, "found": true/false}
found=false jen když mezi stránkami žádný půdorys není."""


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


_NO_CLS = {"podorys_1np": 0, "podorys_2np": None, "rez": None, "vypis_otvorov": None}


def _classify_pages(path: str) -> dict:
    """Viacstránkové PDF/projekt -> klasifikácia strán (PD deep-mining):
    {podorys_1np, podorys_2np, rez, vypis_otvorov, n_pages}. Lacný lokálny predfilter
    na výkresové strany → lacný model označí, ČO ktorá strana je. Namiesto zahodenia
    celého projektu tak vyťažíme rez (výšky), výpis otvorov (presné okná) aj 2.NP."""
    p = str(path).lower()
    if not p.endswith(".pdf"):
        return {**_NO_CLS, "n_pages": 1}
    doc = fitz.open(path)
    n = doc.page_count
    if n <= 1:
        doc.close()
        return {**_NO_CLS, "n_pages": n}
    # malé projekty: vezmi všetky strany; veľké: len výkresových kandidátov
    cand = list(range(min(n, MAX_SCAN_PAGES))) if n <= MAX_PLAN_CANDIDATES else _drawing_candidate_idxs(doc)
    imgs = []
    for i in cand:
        pix = doc[i].get_pixmap(matrix=fitz.Matrix(1.4, 1.4))
        im = Image.open(io.BytesIO(pix.tobytes("png")))
        if max(im.size) > 760:
            s = 760 / max(im.size)
            im = im.resize((int(im.width * s), int(im.height * s)))
        buf = io.BytesIO()
        im.convert("RGB").save(buf, format="PNG")
        imgs.append(buf.getvalue())
    doc.close()
    try:
        # klasifikácia strán = lacný model (cheap=True); provider si model zvolí sám
        text, _usage, _model = providers.get_provider().generate(imgs, CLASSIFY_PROMPT, cheap=True)
        d = _parse_json(text)

        def _map(key):
            v = _num(d.get(key))
            if v is None:
                return None
            v = int(v)
            return cand[v] if 0 <= v < len(cand) else None   # pozícia → skutočná strana

        p1 = _map("podorys_1np")
        if not d.get("found") or p1 is None:
            p1 = cand[0] if cand else 0
        return {"podorys_1np": p1, "podorys_2np": _map("podorys_2np"),
                "rez": _map("rez"), "vypis_otvorov": _map("vypis_otvorov"), "n_pages": n}
    except Exception:
        return {**_NO_CLS, "podorys_1np": cand[0] if cand else 0, "n_pages": n}


def _parse_json(text: str) -> dict:
    text = text.strip()
    # odstráň prípadné ```json ... ``` obaly
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    # 1) čistý JSON (JSON-mode / tool-use)
    try:
        return json.loads(text)
    except ValueError:
        pass
    # 2) prvý VALIDNÝ objekt od prvej '{' — raw_decode ignoruje smeti ZA ním.
    #    Na ne-pôdorysoch (foto, detaily) model občas vráti dva objekty alebo
    #    trailing text → greedy regex z toho robil nevalidný blob (gate test 2026-07-07).
    i = text.find("{")
    if i >= 0:
        try:
            obj, _end = json.JSONDecoder().raw_decode(text[i:])
            if isinstance(obj, dict):
                return obj
        except ValueError:
            pass
    # 3) posledná šanca: greedy regex (pôvodné správanie)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return json.loads(m.group(0) if m else text)


def extract_from_plan(path: str) -> dict:
    """Hlavná funkcia: cesta k súboru -> extrahované parametre (dict).
    Pri viacstránkovom projekte najprv vyberie stránku s pôdorysom, potom z nej extrahuje."""
    cls = _classify_pages(path)                        # medzikrok pre projektovú dokumentáciu
    n_pages, page_idx = cls["n_pages"], cls["podorys_1np"]
    is_project = str(path).lower().endswith(".pdf") and n_pages > 1
    if is_project:
        # PD DEEP-MINING: k pôdorysu prilož aj REZ (výška podlažia) a VÝPIS OTVOROV
        # (presné šírky okien/dverí) — extrakčný prompt ich už vie využiť (body 6, 8).
        pages = [page_idx] + [i for i in (cls["rez"], cls["vypis_otvorov"])
                              if i is not None and i != page_idx]
        images = _pages_to_images(path, pages=pages)
    else:
        images = _pages_to_images(path)

    # SELF-CONSISTENCY: N nezávislých čítaní PARALELNE → medián numerických polí.
    # AI čítanie varíruje ~7 % medzi behmi; medián z 3 to zráža pod ~3 % (PLAN_PRESNOST B3).
    # Default 1 (šetrí API); produkcia: EXTRACT_RUNS=3. Paralelne kvôli Vercel 60 s.
    runs = max(1, int(os.environ.get("EXTRACT_RUNS", "1")))
    if runs == 1:
        out = _extract_once(images, page_idx, n_pages)
    else:
        with ThreadPoolExecutor(max_workers=runs) as ex:
            results = [r for r in ex.map(lambda _: _try_extract(images, page_idx, n_pages),
                                         range(runs)) if r]
        if not results:
            raise RuntimeError("Extrakcia zlyhala vo všetkých behoch.")
        out = results[0] if len(results) == 1 else _median_merge(results)
    # PD: prezraď app-ke, či klasifikácia našla aj pôdorys 2.NP (zmeria sa zvlášť a sčíta)
    out["_extra_floor_page_idx"] = cls["podorys_2np"] if is_project else None
    out["_pages_used"] = ({k: cls[k] for k in ("podorys_1np", "rez", "vypis_otvorov")}
                          if is_project else None)
    return out


def extract_page(path: str, page_idx: int) -> dict:
    """Extrahuj KONKRÉTNU stranu PDF (napr. pôdorys 2.NP nájdený klasifikáciou)."""
    doc = fitz.open(path)
    n = doc.page_count
    doc.close()
    images = _pages_to_images(path, only_page=page_idx)
    return _extract_once(images, page_idx, n)


def _try_extract(images, page_idx, n_pages):
    try:
        return _extract_once(images, page_idx, n_pages)
    except Exception:  # noqa: BLE001
        return None


def _extract_once(images, page_idx, n_pages) -> dict:
    # model-agnostické volanie: provider (gemini/anthropic) rieši model aj fallback sám;
    # schema vynúti štruktúrovaný výstup (Fable tool-use / Gemini JSON-mode)
    text, usage, model = providers.get_provider().generate(
        images, EXTRACTION_PROMPT, schema=EXTRACTION_SCHEMA)
    try:
        data = _parse_json(text)
    except ValueError:
        # Model vrátil nevalidný JSON — deje sa na NE-pôdorysoch (fotky, detaily),
        # kde sa model zmätie. 1 retry (stochastické), potom "nečitateľné" →
        # quality_gate to korektne ODMIETNE namiesto 500-ky userovi (gate test 2026-07-07).
        try:
            text, usage2, model = providers.get_provider().generate(
                images, EXTRACTION_PROMPT, schema=EXTRACTION_SCHEMA)
            usage = {"in": usage["in"] + usage2["in"], "out": usage["out"] + usage2["out"]}
            data = _parse_json(text)
        except ValueError:
            data = {"typ_stavby": "rodinny_dum", "obvod_m": 0, "confidence_0_100": 5,
                    "meritko_source": "žádné",
                    "note": "Model nevrátil čitatelný výstup — vstup pravděpodobně není půdorys."}
    data["_model"] = model
    data["_pages"] = len(images)
    data["_page_idx"] = page_idx
    data["_pages_total"] = n_pages
    data["_from_project"] = n_pages > 1
    data["_usage"] = usage
    return _normalize(data)


# polia zlučované mediánom pri self-consistency (numerické, nezávislé od seba)
_MEDIAN_FIELDS = ("obvod_m", "obvod_tloustka_mm", "vnitrni_nosne_m", "vnitrni_nosne_tloustka_mm",
                  "pricky_m", "pricky_tloustka_mm", "uzitna_plocha_m2", "zastavena_plocha_m2",
                  "pocet_oken", "pocet_dveri", "pocet_mistnosti", "confidence_0_100")


def _median_merge(results: list) -> dict:
    """N čítaní → jedno: numerika mediánom, booleany väčšinou, zvyšok z behu
    s obvodom najbližším mediánu (konzistentný 'kotviaci' beh)."""
    med_obvod = statistics.median(r["obvod_m"] for r in results)
    base = dict(min(results, key=lambda r: abs(r["obvod_m"] - med_obvod)))
    for k in _MEDIAN_FIELDS:
        vals = [r[k] for r in results if r.get(k) is not None]
        if vals:
            m = statistics.median(vals)
            base[k] = round(m) if isinstance(base.get(k), int) else round(m, 1)
    base["obvod_m"] = round(med_obvod, 1)
    for k in ("ma_zateplenie", "ma_garaz", "ma_schodiste", "tloustka_z_koty"):
        base[k] = sum(1 for r in results if r.get(k)) > len(results) / 2
    base["_usage"] = {"in": sum(r["_usage"]["in"] for r in results),
                      "out": sum(r["_usage"]["out"] for r in results)}
    base["_model"] = f"{base.get('_model', '?')} ×{len(results)} (medián)"
    # rozptyl behov na obvode → signál pre band (0 = úplná zhoda)
    if med_obvod:
        spread = (max(r["obvod_m"] for r in results) - min(r["obvod_m"] for r in results)) / med_obvod
        base["_ensemble_spread"] = round(spread, 3)
    return base


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
    # itemizované otvory: validuj typ aj šírku (0.3–6 m), zvyšok zahoď (pricing má fallback)
    otvory = []
    for o in (d.get("otvory") or []):
        if not isinstance(o, dict):
            continue
        typ, s = o.get("typ"), _num(o.get("sirka_m"))
        if typ in ("okno", "francouzske_okno", "hs_portal", "dvere_vchod", "dvere_vnitrni") \
                and s and 0.3 <= s <= 6.0:
            otvory.append({"typ": typ, "sirka_m": round(s, 2),
                           "pocet": max(1, int(_num(o.get("pocet"), 1) or 1))})
    # BBOX CHECK (deterministický, bez AI): obvod pravouhlého polygónu NEMÔŽE byť menší
    # než perimeter bounding boxu 2×(šírka+dĺžka). Chytá podčítané L/U tvary — hlavný
    # zdroj chýb obvodu v baseline (−16 až −24 %). L-tvar má obvod PRESNE = bbox perimeter.
    bbox = d.get("rozmery_celkove_m") or {}
    bb_w, bb_l = _num(bbox.get("sirka_m")), _num(bbox.get("dlzka_m"))
    obvod = _num(d.get("obvod_m"), 0) or 0
    obvod_bbox_fix = False
    if bb_w and bb_l and 3 <= bb_w <= 60 and 3 <= bb_l <= 60:
        bbox_perim = 2 * (bb_w + bb_l)
        if obvod and obvod < bbox_perim * 0.98:
            obvod = round(bbox_perim, 1)
            obvod_bbox_fix = True
    return {
        # konzervatívne defaulty: keď model netrafí enum, beriem ako murovaný RD (nech neodmietneme reálny dom)
        "typ_stavby": (d.get("typ_stavby") if d.get("typ_stavby") in
                       ("rodinny_dum", "byt", "bytovy_dum", "jine") else "rodinny_dum"),
        "konstrukce": (d.get("konstrukce") if d.get("konstrukce") in
                       ("zdene", "drevostavba", "skelet") else None),
        "obvod_m": obvod,
        "rozmery_celkove_m": ({"sirka_m": bb_w, "dlzka_m": bb_l} if bb_w and bb_l else None),
        "_obvod_bbox_fix": obvod_bbox_fix,
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
        "ma_garaz": bool(d.get("ma_garaz")),
        "vyska_podlazi_m": _num(d.get("vyska_podlazi_m"), 2.8) or 2.8,
        "otvory": otvory,
        "pocet_oken": int(_num(d.get("pocet_oken"), 0) or 0),
        "pocet_dveri": int(_num(d.get("pocet_dveri"), 0) or 0),
        "pocet_mistnosti": int(_num(d.get("pocet_mistnosti"), 0) or 0),
        "koty_mm": d.get("koty_mm") or [],
        "meritko_source": d.get("meritko_source") or "žádné",
        "confidence_0_100": int(_num(d.get("confidence_0_100"), 40) or 40),
        "co_potvrdit": d.get("co_potvrdit") or [],
        "note": d.get("note") or "",
        "_model": d.get("_model", ""),
        "_ensemble_spread": d.get("_ensemble_spread"),
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
