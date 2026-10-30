#!/usr/bin/env python3
"""Radar de fuentes: qué han publicado las fuentes verificadas en las últimas horas.

Determinista, sin modelo. Lee `fuentes/fuentes.json`, descarga los feeds RSS/Atom
activos, filtra por ventana temporal y por los temas del cliente
(`cliente/temas.json`), descarta lo ya visto (`estado/vistos.json`) y deja un
markdown con los candidatos agrupados por tier y categoría. Solo biblioteca
estándar de Python 3.

Uso:
    python3 scripts/radar.py                      # últimas 48 h, salida en estado/radar-AAAA-MM-DD.md
    python3 scripts/radar.py --horas 24 --salida /ruta/radar.md
    python3 scripts/radar.py --sin-temas          # sin filtro de palabras clave
    python3 scripts/radar.py --sin-estado         # ignora y no actualiza vistos.json

Los temas y el estado viven fuera del plugin, en ~/.linkedin-os/ (o en la carpeta que
indique LINKEDIN_OS_HOME), para que sobrevivan a las actualizaciones: temas.json,
radar-AAAA-MM-DD.md, vistos.json y vigilancia.json. Sin temas.json propio se usan los
temas de ejemplo (`cliente/temas.example.json`).
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

RAIZ = Path(__file__).resolve().parent.parent
FUENTES = RAIZ / "fuentes" / "fuentes.json"
DATOS = Path(os.environ.get("LINKEDIN_OS_HOME") or Path.home() / ".linkedin-os").expanduser()
TEMAS_EJEMPLO = RAIZ / "cliente" / "temas.example.json"
ESTADO = DATOS / "vistos.json"
ESTADO_WATCH = DATOS / "vigilancia.json"
UA_NAVEGADOR = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
TERMINOS_NAVEGACION = ("/tag/", "/tags/", "/category/", "/categories/", "/author/", "/page/", "/login", "/signup", "/privacy", "/terms", "/contact", "/about", "/careers", "/pricing", "/search")
MAX_ENLACES_WATCH = 150
UA = os.environ.get("RADAR_USER_AGENT", "linkedin-os radar/0.1")
UA_CON_CONTACTO = "@" in UA  # la SEC solo responde a un user agent con nombre y correo de contacto
TIMEOUT = 15
RETENCION_DIAS = 45


def normaliza(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().lower()


def parsea_fecha(valor: str | None) -> datetime | None:
    if not valor:
        return None
    valor = valor.strip()
    try:
        d = parsedate_to_datetime(valor)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        pass
    try:
        d = datetime.fromisoformat(valor.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    for formato in ("%A, %B %d, %Y - %H:%M", "%B %d, %Y - %H:%M", "%d %B %Y"):  # FCA: «Friday, October 30, 2026 - 09:00»
        try:
            return datetime.strptime(valor, formato).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def texto_de(nodo, *nombres: str) -> str | None:
    """Primer valor por orden de preferencia de las etiquetas, no por orden en el feed (el Banco de Inglaterra pone guid antes que link)."""
    for nombre in nombres:
        for hijo in nodo:
            if hijo.tag.split("}")[-1] != nombre:
                continue
            if nombre == "link" and hijo.get("href"):
                return hijo.get("href")
            if hijo.text and hijo.text.strip():
                return hijo.text.strip()
    return None


def parsea_feed(cuerpo: bytes) -> list[dict]:
    raiz = ET.fromstring(cuerpo)
    entradas = []
    for nodo in raiz.iter():
        etiqueta = nodo.tag.split("}")[-1]
        if etiqueta not in ("item", "entry"):
            continue
        titulo = texto_de(nodo, "title")
        enlace = texto_de(nodo, "link", "id", "guid")
        fecha = parsea_fecha(texto_de(nodo, "pubDate", "published", "updated", "date"))
        resumen = texto_de(nodo, "description", "summary", "content") or ""
        resumen = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", resumen))).strip()
        titulo = html.unescape(titulo) if titulo else titulo
        if titulo and enlace and enlace.startswith("http"):
            entradas.append({"titulo": titulo, "url": enlace, "fecha": fecha, "resumen": resumen[:400]})
    return entradas


def contexto_ssl():
    """Las instalaciones de python.org en macOS no traen certificados; se usa certifi o el del sistema."""
    import ssl

    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    for ruta in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        if Path(ruta).exists():
            return ssl.create_default_context(cafile=ruta)
    return ssl.create_default_context()


CTX = contexto_ssl()


def descarga(fuente: dict) -> tuple[dict, list[dict] | None, str | None]:
    peticion = urllib.request.Request(fuente["url"], headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT, context=CTX) as r:
            cuerpo = r.read()
        return fuente, parsea_feed(cuerpo), None
    except Exception as exc:  # noqa: BLE001 - un feed caído no para el radar
        return fuente, None, f"{type(exc).__name__}: {str(exc)[:80]}"


def dominio(url: str) -> str:
    partes = (urlparse(url).hostname or "").split(".")
    return ".".join(partes[-2:]) if len(partes) >= 2 else ""


def canonica(url: str) -> str:
    u = urlparse(url)
    return f"{u.scheme}://{u.netloc}{u.path}".rstrip("/").lower()


def enlaces_de_landing(html_crudo: str, url_pagina: str, url_landing: str, fuente: dict) -> list[dict]:
    """Enlaces de contenido de una página sin RSS: mismo dominio, sin rutas de navegación, ruta de dos segmentos o más."""
    dom = dominio(url_landing)
    inc = re.compile(fuente["url_include"]) if fuente.get("url_include") else None
    exc = re.compile(fuente["url_exclude"]) if fuente.get("url_exclude") else None
    vistos_aqui: set[str] = set()
    out: list[dict] = []
    for m in re.finditer(r'<a\s[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', html_crudo, re.S | re.I):
        href = urljoin(url_pagina, m.group(1).strip())
        if not href.startswith("http") or dominio(href) != dom:
            continue
        ruta = (urlparse(href).path or "/").lower()
        if any(t in ruta for t in TERMINOS_NAVEGACION):
            continue
        if len([seg for seg in ruta.split("/") if seg]) < 2:
            continue
        if inc and not inc.search(href):
            continue
        if exc and exc.search(href):
            continue
        c = canonica(href)
        if c in vistos_aqui:
            continue
        vistos_aqui.add(c)
        texto = html.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))
        texto = re.sub(r"\s+", " ", texto).strip()[:200]
        out.append({"titulo": texto or href, "url": href, "fecha": None, "resumen": ""})
        if len(out) >= MAX_ENLACES_WATCH:
            break
    return out


def vigila(fuente: dict) -> tuple[dict, list[dict] | None, str | None]:
    """Método watch: descarga la landing y devuelve sus enlaces de contenido actuales."""
    url = fuente.get("watch_url") or fuente["url"]
    peticion = urllib.request.Request(url, headers={"User-Agent": UA_NAVEGADOR, "Accept": "text/html,*/*"})
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT, context=CTX) as r:
            cuerpo = r.read().decode("utf-8", "ignore")
        return fuente, enlaces_de_landing(cuerpo, url, fuente["url"], fuente), None
    except Exception as exc:  # noqa: BLE001
        return fuente, None, f"{type(exc).__name__}: {str(exc)[:80]}"


def ruta_temas() -> Path:
    for ruta in (DATOS / "temas.json", RAIZ / "cliente" / "temas.json", TEMAS_EJEMPLO):
        if ruta.exists():
            return ruta
    return TEMAS_EJEMPLO


def carga_temas(ruta: Path) -> dict:
    if not ruta.exists():
        return {"incluir": [], "excluir": []}
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return {"incluir": [normaliza(t) for t in datos.get("incluir", [])],
            "excluir": [normaliza(t) for t in datos.get("excluir", [])]}


def contiene(texto: str, termino: str) -> bool:
    """Los términos cortos (hasta cuatro letras) se buscan como palabra entera: «mica» no debe saltar con «America»."""
    if len(termino) <= 4:
        return re.search(r"(?<![a-z0-9])" + re.escape(termino) + r"(?![a-z0-9])", texto) is not None
    return termino in texto


def pasa_temas(entrada: dict, fuente: dict, temas: dict) -> bool:
    texto = normaliza(entrada["titulo"] + " " + entrada["resumen"])
    if any(contiene(texto, t) for t in temas["excluir"]):
        return False
    claves = [normaliza(k) for k in fuente.get("palabras_clave", [])]
    if claves and not any(contiene(texto, k) for k in claves):
        return False
    if temas["incluir"] and not any(contiene(texto, t) for t in temas["incluir"]):
        return False
    return True


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--horas", type=int, default=48)
    p.add_argument("--salida", type=Path)
    p.add_argument("--fuentes", type=Path, default=FUENTES)
    p.add_argument("--temas", type=Path, default=None, help="por defecto ~/.linkedin-os/temas.json o, si no existe, los temas de ejemplo")
    p.add_argument("--max-por-fuente", type=int, default=5)
    p.add_argument("--sin-temas", action="store_true", help="no filtra por cliente/temas.json")
    p.add_argument("--sin-estado", action="store_true", help="no lee ni escribe estado/vistos.json")
    p.add_argument("--sin-vigilancia", action="store_true", help="omite las fuentes sin RSS (método watch)")
    args = p.parse_args()

    catalogo = json.loads(args.fuentes.read_text(encoding="utf-8"))
    activas = [f for f in catalogo["fuentes"] if f.get("activo")]
    fuentes = [f for f in activas if f.get("metodo") == "rss"]
    sin_contacto = [] if UA_CON_CONTACTO else [f for f in fuentes if "sec.gov/cgi-bin" in f["url"]]
    fuentes = [f for f in fuentes if f not in sin_contacto]
    vigiladas = [] if args.sin_vigilancia else [f for f in activas if f.get("metodo") == "watch"]
    ciegas = [f for f in catalogo["fuentes"] if f.get("bloquea_bots") or (f.get("metodo") == "watch" and not f.get("activo"))]
    temas_ruta = args.temas or ruta_temas()
    temas = {"incluir": [], "excluir": []} if args.sin_temas else carga_temas(temas_ruta)
    ahora = datetime.now(timezone.utc)
    desde = ahora - timedelta(hours=args.horas)

    vistos: dict[str, str] = {}
    if not args.sin_estado and ESTADO.exists():
        vistos = json.loads(ESTADO.read_text(encoding="utf-8"))

    candidatos: list[dict] = []
    en_esta_pasada: set[str] = set()  # la misma pieza puede salir en dos feeds del mismo publisher
    errores: list[str] = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        futuros = [pool.submit(descarga, f) for f in fuentes]
        for fut in as_completed(futuros):
            fuente, entradas, error = fut.result()
            if error:
                errores.append(f"{fuente['id']}: {error}")
                continue
            n = 0
            for e in entradas:
                if e["fecha"] and e["fecha"] < desde:
                    continue
                if e["url"] in vistos or canonica(e["url"]) in en_esta_pasada:
                    continue
                if not pasa_temas(e, fuente, temas):
                    continue
                en_esta_pasada.add(canonica(e["url"]))
                candidatos.append({**e, "fuente": fuente})
                n += 1
                if n >= args.max_por_fuente:
                    break

    # Fuentes sin RSS: diferencia de enlaces contra la referencia guardada. La primera pasada solo fija la referencia.
    referencia: dict[str, list[str]] = {}
    if not args.sin_estado and ESTADO_WATCH.exists():
        referencia = json.loads(ESTADO_WATCH.read_text(encoding="utf-8"))
    nuevos_watch: list[dict] = []
    sin_referencia: list[str] = []
    if vigiladas:
        with ThreadPoolExecutor(max_workers=8) as pool:
            for fut in as_completed([pool.submit(vigila, f) for f in vigiladas]):
                fuente, enlaces, error = fut.result()
                if error:
                    if not fuente.get("bloquea_bots"):  # las que bloquean robots ya salen en la lista de búsqueda dirigida
                        errores.append(f"{fuente['id']}: {error}")
                    continue
                actuales = [canonica(e["url"]) for e in enlaces]
                if fuente["id"] not in referencia:
                    sin_referencia.append(fuente["id"])
                else:
                    conocidos = set(referencia[fuente["id"]])
                    n = 0
                    for e in enlaces:
                        if canonica(e["url"]) in conocidos or e["url"] in vistos:
                            continue
                        if not pasa_temas(e, fuente, temas):
                            continue
                        nuevos_watch.append({**e, "fuente": fuente})
                        n += 1
                        if n >= args.max_por_fuente:
                            break
                referencia[fuente["id"]] = sorted(set(referencia.get(fuente["id"], [])) | set(actuales))[-2000:]
        candidatos += nuevos_watch

    candidatos.sort(key=lambda c: (c["fuente"]["tier"], c["fuente"]["categoria"], -(c["fecha"] or desde).timestamp()))

    lineas = [f"# Radar de fuentes · {ahora.strftime('%Y-%m-%d %H:%M')} UTC",
              "",
              f"Ventana: {args.horas} h · feeds RSS: {len(fuentes)} · páginas vigiladas: {len(vigiladas)} · candidatos: {len(candidatos)} (de vigilancia: {len(nuevos_watch)}) · fuentes sin respuesta: {len(errores)}",
              "",
              "Regla: tier 1 se puede enlazar; tier 2 solo sirve para descubrir y hay que ir a la fuente primaria antes de escribir.",
              ""]
    if args.sin_temas:
        lineas += ["Temas: sin filtro.", ""]
    elif temas_ruta == TEMAS_EJEMPLO:
        lineas += [f"Temas: los de ejemplo (tokenización, stablecoins, MiCA, pagos, custodia). Para usar los tuyos, copia `{TEMAS_EJEMPLO}` a `{DATOS / 'temas.json'}` y edítalo.", ""]
    else:
        lineas += [f"Temas: `{temas_ruta}`.", ""]
    tier_actual, cat_actual = None, None
    for c in candidatos:
        f = c["fuente"]
        if f["tier"] != tier_actual:
            tier_actual, cat_actual = f["tier"], None
            lineas += [f"## Tier {tier_actual}", ""]
        if f["categoria"] != cat_actual:
            cat_actual = f["categoria"]
            lineas += [f"### {cat_actual}", ""]
        fecha = c["fecha"].strftime("%Y-%m-%d") if c["fecha"] else "sin fecha, nuevo desde la última pasada"
        lineas.append(f"- **{f['publisher']}** · {fecha} · [{c['titulo']}]({c['url']})")
        if c["resumen"]:
            lineas.append(f"  {c['resumen'][:220].strip()}")
    if sin_referencia:
        lineas += ["", f"Vigilancia: primera pasada en {len(sin_referencia)} páginas (solo fijan referencia; avisarán de enlaces nuevos a partir de mañana)."]
    if ciegas:
        lineas += ["", "## Para búsqueda web dirigida (sin RSS o bloquean robots)", "",
                   "Estas fuentes no se pueden escanear. Si el día viene flojo, buscar a mano «<publisher> + tema + últimos días» y validar la URL primaria.", ""]
        lineas += [f"- {f['publisher']} · {f['url']}" for f in ciegas]
    if sin_contacto:
        lineas += ["", "## Fuentes que piden configuración", "",
                   "EDGAR (la base de registros de la SEC) solo responde si el radar se identifica con un nombre y un correo. Para activarla: `export RADAR_USER_AGENT=\"Nombre Apellido correo@dominio.com\"`.", ""]
        lineas += [f"- {f['publisher']} · {f['url']}" for f in sin_contacto]
    if errores:
        lineas += ["", "## Fuentes sin respuesta", ""] + [f"- {e}" for e in sorted(errores)]

    salida = args.salida or (DATOS / f"radar-{ahora.strftime('%Y-%m-%d')}.md")
    salida.parent.mkdir(parents=True, exist_ok=True)
    if not candidatos and salida.exists() and not args.salida:
        # Segunda pasada del día sin nada nuevo: se conserva el informe de la primera.
        print(f"Nada nuevo desde la última pasada. El informe de hoy sigue en {salida}")
        return 0
    salida.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    if not args.sin_estado:
        limite = (ahora - timedelta(days=RETENCION_DIAS)).isoformat()
        vistos = {u: d for u, d in vistos.items() if d >= limite}
        for c in candidatos:
            vistos[c["url"]] = ahora.isoformat()
        ESTADO.parent.mkdir(parents=True, exist_ok=True)
        ESTADO.write_text(json.dumps(vistos, ensure_ascii=False, indent=0), encoding="utf-8")
        if vigiladas:
            ESTADO_WATCH.write_text(json.dumps(referencia, ensure_ascii=False, indent=0), encoding="utf-8")

    print(f"{len(candidatos)} candidatos de {len(fuentes)} feeds y {len(vigiladas)} páginas vigiladas ({len(errores)} sin respuesta) -> {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
