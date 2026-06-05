"""
CV meranie stien z ORezaného hi-res pôdorysu (prototyp, štýl projektyrd).

Princíp:
  - mierka: šírka domu v pixeloch ↔ známy rozmer v metroch (z kót, Gemini).
  - stena = plná tmavá HRUBÁ štruktúra (nábytok/text/šrafy sú tenké → DT filter).
  - dĺžka steny bez skeletonu:  L = plocha² / (4·Σ DT)  (geometricky presné).
  - priečky = vnútorné steny = stena ∩ (silueta zmenšená o hrúbku obvodu).

Debug: ukladá /tmp/cv_*.png nech vidno čo sa meria.
"""
import sys
import cv2
import numpy as np


def _wall_mask(gray):
    """Steny = ČISTO ČIERNE čiary. Vezmeme najväčší súvislý komponent
    (steny domu tvoria jednu sieť; nábytok/text/kóty = menšie samostatné bloby)."""
    mask = (gray < 120).astype(np.uint8)
    # POZOR: opening NErobíme pred komponentom (rozsekal by sieť stien).
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    if n <= 1:
        return mask, cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    # najväčší komponent = sieť stien domu
    biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    walls = (lab == biggest).astype(np.uint8)
    dt = cv2.distanceTransform(walls, cv2.DIST_L2, 5)
    return walls, dt


def _length_m(mask, scale):
    """L = plocha² / (4·Σ DT)  →  metre."""
    if mask.sum() == 0:
        return 0.0
    dt = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    area = float(mask.sum())
    sdt = float(dt.sum())
    length_px = area * area / (4 * sdt) if sdt else 0
    return length_px * scale


def measure(path, width_m, debug=True):
    img = cv2.imread(path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    walls, dt = _wall_mask(gray)

    # bbox stien → mierka (šírka domu = width_m)
    ys, xs = np.where(walls)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    bbox_w = x1 - x0
    scale = width_m / bbox_w  # metre na pixel

    ext_th = float(np.percentile(dt[walls > 0], 95) * 2)  # hrúbka obvodu (px)

    # silueta footprintu: zatesni otvory → floodFill pozadia → diery = miestnosti
    seal = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(3 * ext_th) | 1,) * 2)
    closed = cv2.morphologyEx(walls, cv2.MORPH_CLOSE, seal)
    ff = closed.copy()
    m2 = np.zeros((ff.shape[0] + 2, ff.shape[1] + 2), np.uint8)
    cv2.floodFill(ff, m2, (0, 0), 1)
    sil = (closed | (ff == 0)).astype(np.uint8)

    # obvod = HRUBÝ (vysoký DT) A ZÁROVEŇ pri OKRAJI (v obvodovom prstenci).
    # → nosná stena v strede (hrubá, ale nie pri okraji) ostane priečkou.
    ring = (sil - cv2.erode(sil, np.ones((3, 3), np.uint8),
                            iterations=int(1.5 * ext_th))).clip(0, 1)
    T = max(8.0, ext_th * 0.40)
    ext_full = cv2.dilate((dt >= T).astype(np.uint8), np.ones((3, 3), np.uint8),
                          iterations=int(T) + 3) & walls
    exterior = (ext_full & ring).astype(np.uint8)
    pricky_raw = (walls & (1 - exterior)).astype(np.uint8)
    open_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    pricky_mask = cv2.morphologyEx(pricky_raw, cv2.MORPH_OPEN, open_k)

    obvod_m = 2 * ((x1 - x0) + (y1 - y0)) * scale
    pricky_m = _length_m(pricky_mask, scale)

    if debug:
        dbg = img.copy()
        dbg[walls > 0] = (0, 0, 255)          # všetky steny červené
        dbg[pricky_mask > 0] = (0, 200, 0)    # priečky zelené
        cv2.rectangle(dbg, (x0, y0), (x1, y1), (255, 0, 0), 3)
        cv2.imwrite("/tmp/cv_debug.png", dbg)
        cv2.imwrite("/tmp/cv_walls.png", walls * 255)
        cv2.imwrite("/tmp/cv_pricky.png", pricky_mask * 255)

    return {"scale_m_per_px": round(scale, 5), "bbox_px": [int(bbox_w), int(y1 - y0)],
            "obvod_m_cv": round(obvod_m, 1), "pricky_m_cv": round(pricky_m, 1),
            "ext_thickness_px": round(float(ext_th), 1)}


if __name__ == "__main__":
    path = sys.argv[1]
    width_m = float(sys.argv[2]) if len(sys.argv) > 2 else 11.0
    import json
    print(json.dumps(measure(path, width_m), ensure_ascii=False, indent=2))
