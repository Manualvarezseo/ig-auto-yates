# Autopublicación de carruseles en Instagram (gratis)

Publica automáticamente un carrusel de barco por ejecución usando la **Instagram Graph API**
(oficial de Meta) y **GitHub Actions** (cron). Coste: 0 €.

## Qué hace
- Recorre `carruseles/NN_slug/` en orden.
- Monta un carrusel: `00_cover.jpg` + fotos + `zz_cta.jpg` (máx. 10 imágenes de IG).
- Usa el texto de `caption.txt` como pie de foto.
- Publica **un barco por ejecución** y guarda el progreso en `state.json`
  (no repite: salta los ya publicados).

---

## PASOS QUE DEBES HACER TÚ (una sola vez)

Estas partes necesitan tu login en Meta; por seguridad no las hago yo.

### 1. Cuenta de Instagram + Página de Facebook
- La cuenta de IG donde se publica debe ser **Business** o **Creator**
  (Ajustes → Tipo de cuenta → cambiar a profesional).
- Debe estar **vinculada a una Página de Facebook** (en la app de IG:
  Configuración → Cuentas vinculadas / Centro de cuentas).

### 2. App de Meta + token
1. Entra en https://developers.facebook.com/ → **My Apps → Create App** → tipo **Business**.
2. Añade el producto **Instagram Graph API**.
3. Ve a **Graph API Explorer**, elige tu app y genera un **User Token** con permisos:
   `instagram_basic`, `instagram_content_publish`, `pages_show_list`,
   `pages_read_engagement`, `business_management`.
4. Convierte ese token en **larga duración** (60 días) o crea un
   **System User token** en Business Settings (no caduca) — recomendado.
5. Consigue el **IG_USER_ID** (id numérico de la cuenta IG):
   en Graph API Explorer llama a:  `me/accounts` → coge el `id` de la Página →
   luego `{PAGE_ID}?fields=instagram_business_account` → ahí está el IG user id.

> Guarda dos valores: **IG_USER_ID** y **IG_TOKEN**.

### 3. Subir esta carpeta a un repo de GitHub
```bash
cd ~/Desktop/ig-auto-yates
git init && git add . && git commit -m "ig auto carruseles"
# crea el repo (privado o público) y haz push, p.ej. con gh:
gh repo create ig-auto-yates --private --source=. --push
```
> Las imágenes se sirven vía `raw.githubusercontent.com` (el workflow arma la URL solo).
> Si el repo es **privado**, las raw URLs no son públicas y la API no podrá leerlas:
> en ese caso, hazlo **público** o activa **GitHub Pages** (o dime y lo cambiamos
> a alojar las imágenes en tu Hostinger).

### 4. Secrets en GitHub
En el repo → **Settings → Secrets and variables → Actions → New repository secret**:
- `IG_USER_ID` = tu id numérico
- `IG_TOKEN` = tu token

### 5. Probar
- Repo → pestaña **Actions** → workflow *"Publicar carrusel en Instagram"* →
  **Run workflow** con `dry_run = 1` (no publica; comprueba imágenes y caption en el log).
- Si se ve bien, lánzalo con `dry_run = 0` → publica el primer barco.
- A partir de ahí, el **cron** publica solo (por defecto cada 2 días a las 18:00 UTC;
  cámbialo en `.github/workflows/ig-carousel.yml`).

---

## Uso / ajustes
- **Forzar un barco**: Run workflow con `only = tesoro-t40` (parte del nombre de carpeta).
- **Cambiar frecuencia**: edita el `cron` del workflow.
- **Reordenar**: las carpetas se publican por su número (`01_…`, `02_…`, …).
- **Reset**: vacía `state.json` a `{"posted": []}` para volver a empezar.
- **Prueba en local**:
  ```bash
  IG_USER_ID=... IG_TOKEN=... IMG_BASE=https://raw.githubusercontent.com/USUARIO/ig-auto-yates/main/carruseles DRY_RUN=1 python3 publish_ig.py
  ```

## Notas
- Límite de la API: 25 publicaciones/día (de sobra).
- El token de 60 días caduca → usa **System User token** para no renovar, o pon un
  recordatorio. Puedo añadir un paso de auto-refresh si me lo pides.
- Esto NO viola términos (es la API oficial de publicación de Meta).
