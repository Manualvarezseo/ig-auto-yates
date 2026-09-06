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
import os, re, json, sys, glob, time, datetime
import requests
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

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

# Aviso a Telegram (grupo Barcos). Opcional: si no hay TG_TOKEN/TG_CHAT no avisa.
TG_TOKEN = os.environ.get("TG_TOKEN", "").strip()
TG_CHAT = os.environ.get("TG_CHAT", "").strip()
# Opcional: ids de temas/canales del grupo (coma-separado). Si se ponen, avisa en cada uno.
TG_THREADS = [t.strip() for t in os.environ.get("TG_THREADS", "").split(",") if t.strip()]


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


def boat_name(fold, caption):
    """Nombre legible del barco: primera línea del caption hasta el guion,
    o si no, el slug de la carpeta en bonito."""
    first = caption.splitlines()[0] if caption else ""
    for sep in (" — ", " – ", " - ", " —"):
        if sep in first:
            first = first.split(sep, 1)[0]
            break
    first = first.strip().rstrip("🛥️").strip()
    if first:
        return first
    slug = re.sub(r"^\d+_", "", fold).replace("-", " ")
    return slug.title()


def telegram_notify(name):
    """Avisa al grupo Barcos de que se ha publicado. No rompe si falla."""
    if not (TG_TOKEN and TG_CHAT):
        return
    text = f'✅ La publicación "{name}" se ha publicado en Instagram.'
    targets = TG_THREADS or [None]
    for thread in targets:
        body = {"chat_id": TG_CHAT, "text": text, "disable_web_page_preview": True}
        if thread:
            body["message_thread_id"] = thread
        try:
            requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                          data=body, timeout=20)
        except Exception as e:
            print(f"Aviso Telegram falló (no crítico): {e}")


def api_post(path, params):
    r = requests.post(f"{GRAPH}/{path}", data=params, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"API {path} -> {r.status_code}: {r.text}")
    return r.json()


def create_item(url):
    j = api_post(f"{IG_USER_ID}/media", {
        "image_url": url, "is_carousel_item": "true", "access_token": IG_TOKEN})
    return j["id"]


def time_gate():
    """En ejecuciones programadas, solo publica si en Madrid son las 8:00 o 20:00.
    Así se respeta 8:00/20:00 hora española todo el año (verano e invierno),
    aunque el cron de GitHub sea en UTC. Las ejecuciones manuales pasan siempre."""
    if os.environ.get("EVENT_NAME", "") != "schedule":
        return True
    hours = [int(x) for x in os.environ.get("PUBLISH_HOURS", "8,20").split(",")]
    if ZoneInfo is None:
        return True
    now = datetime.datetime.now(ZoneInfo("Europe/Madrid"))
    if now.hour in hours:
        return True
    print(f"Hora Madrid {now:%H:%M}: fuera de franja {hours}. Salgo sin publicar.")
    return False


def resolve_ig_user_id():
    """Descubre el IG_USER_ID a partir del token (no hace falta darlo a mano):
    token -> /me/accounts (Página) -> instagram_business_account."""
    r = requests.get(f"{GRAPH}/me/accounts",
                     params={"access_token": IG_TOKEN, "fields": "id,name"}, timeout=30)
    r.raise_for_status()
    pages = r.json().get("data", [])
    if not pages:
        raise SystemExit("El token no da acceso a ninguna Página de Facebook.")
    page_id = pages[0]["id"]
    r2 = requests.get(f"{GRAPH}/{page_id}",
                      params={"access_token": IG_TOKEN,
                              "fields": "instagram_business_account"}, timeout=30)
    r2.raise_for_status()
    iba = r2.json().get("instagram_business_account")
    if not iba:
        raise SystemExit("La Página no tiene una cuenta de Instagram profesional vinculada.")
    return iba["id"]


def main():
    global IG_USER_ID
    if not time_gate():
        return
    for v in ("IG_TOKEN", "IMG_BASE"):
        if not globals()[v]:
            raise SystemExit(f"Falta variable de entorno {v}")
    if not IG_USER_ID:
        IG_USER_ID = resolve_ig_user_id()
        print(f"IG_USER_ID detectado automáticamente: {IG_USER_ID}")

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

    telegram_notify(boat_name(fold, caption))

    state["posted"].append(fold)
    save_state(state)
    print(f"Estado actualizado: {len(state['posted'])}/{len(boat_folders())} publicados.")


if __name__ == "__main__":
    main()
