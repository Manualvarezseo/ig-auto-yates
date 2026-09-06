#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Publica en Instagram (Graph API) el siguiente carrusel de barco de la cola.

Requiere variables de entorno:
  IG_USER_ID   -> ID de la cuenta de IG Business/Creator (numérico)
  IG_TOKEN     -> token de acceso de larga duración (o de System User)
  IMG_BASE     -> base pública https donde están las imágenes, p.ej.
                  https://raw.githubusercontent.com/USUARIO/REPO/main/carruseles

Opcionales:
  DRY_RUN=1    -> no publica; solo imprime lo que haría
  ONLY=slug    -> fuerza un barco concreto (nombre de carpeta, con o sin nº)

Estado en state.json: {"posted": ["23_tesoro-t40", ...]}
Publica UN barco por ejecución, en orden de carpeta, saltando los ya posteados.
"""
import os, re, json, sys, glob, time
import requests

GRAPH = "https://graph.facebook.com/v21.0"
HERE = os.path.dirname(os.path.abspath(__file__))
CAR = os.path.join(HERE, "carruseles")
STATE = os.path.join(HERE, "state.json")
MAX_IMAGES = 10  # límite de Instagram para carrusel

IG_USER_ID = os.environ.get("IG_USER_ID", "").strip()
IG_TOKEN = os.environ.get("IG_TOKEN", "").strip()
IMG_BASE = os.environ.get("IMG_BASE", "").strip().rstrip("/")
DRY = os.environ.get("DRY_RUN", "") == "1"
ONLY = os.environ.get("ONLY", "").strip()


def load_state():
    if os.path.exists(STATE):
        return json.load(open(STATE))
    return {"posted": []}


def save_state(s):
    json.dump(s, open(STATE, "w"), ensure_ascii=False, indent=2)


def boat_folders():
    return sorted(d for d in os.listdir(CAR)
                  if re.match(r"^\d+_", d) and os.path.isdir(os.path.join(CAR, d)))


def pick_next(state):
    if ONLY:
        for f in boat_folders():
            if ONLY in f:
                return f
        raise SystemExit(f"ONLY='{ONLY}' no coincide con ninguna carpeta")
    for f in boat_folders():
        if f not in state["posted"]:
            return f
    return None


def carousel_images(fold):
    d = os.path.join(CAR, fold)
    imgs = []
    cover = os.path.join(d, "00_cover.jpg")
    if os.path.exists(cover):
        imgs.append("00_cover.jpg")
    middles = sorted(os.path.basename(x) for x in glob.glob(os.path.join(d, "[0-9][0-9].jpg")))
    cta = "zz_cta.jpg" if os.path.exists(os.path.join(d, "zz_cta.jpg")) else None
    # cover + middles + cta, respetando el máximo de 10
    room = MAX_IMAGES - len(imgs) - (1 if cta else 0)
    imgs += middles[:max(room, 0)]
    if cta:
        imgs.append(cta)
    return [f"{IMG_BASE}/{fold}/{name}" for name in imgs]


def read_caption(fold):
    p = os.path.join(CAR, fold, "caption.txt")
    return open(p, encoding="utf-8").read().strip() if os.path.exists(p) else ""


def api_post(path, params):
    r = requests.post(f"{GRAPH}/{path}", data=params, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"API {path} -> {r.status_code}: {r.text}")
    return r.json()


def create_item(url):
    j = api_post(f"{IG_USER_ID}/media", {
        "image_url": url, "is_carousel_item": "true", "access_token": IG_TOKEN})
    return j["id"]


def main():
    for v in ("IG_USER_ID", "IG_TOKEN", "IMG_BASE"):
        if not globals()[v]:
            raise SystemExit(f"Falta variable de entorno {v}")

    state = load_state()
    fold = pick_next(state)
    if not fold:
        print("No quedan barcos por publicar. Cola completada.")
        return

    urls = carousel_images(fold)
    caption = read_caption(fold)
    print(f"== Barco: {fold}  ({len(urls)} imágenes) ==")
    for u in urls:
        print("  ", u)
    print("---- caption ----")
    print(caption[:400])
    print("-----------------")

    if DRY:
        print("DRY_RUN: no se publica nada.")
        return

    # 1) contenedores hijos
    children = []
    for u in urls:
        cid = create_item(u)
        children.append(cid)
        time.sleep(2)

    # 2) contenedor del carrusel
    parent = api_post(f"{IG_USER_ID}/media", {
        "media_type": "CAROUSEL",
        "children": ",".join(children),
        "caption": caption,
        "access_token": IG_TOKEN,
    })["id"]

    # 3) esperar a que el contenedor esté listo y publicar
    time.sleep(5)
    pub = api_post(f"{IG_USER_ID}/media_publish", {
        "creation_id": parent, "access_token": IG_TOKEN})
    print(f"PUBLICADO ✅  media id = {pub.get('id')}")

    state["posted"].append(fold)
    save_state(state)
    print(f"Estado actualizado: {len(state['posted'])}/{len(boat_folders())} publicados.")


if __name__ == "__main__":
    main()
