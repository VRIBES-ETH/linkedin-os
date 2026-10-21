#!/usr/bin/env python3
"""es-content-lint: guardia determinista de español peninsular (hook PreToolUse de Write y Edit).

Bloquea (exit 2) el texto que va a escribirse en las zonas de contenido del plugin cuando
contiene algo que un regex puede juzgar sin dudar:

  - raya larga (U+2014) en prosa propia (se respeta dentro de citas «> » y como separador solo),
  - raya corta (U+2013) en prosa, comillas rizadas, guiones y espacios tipográficos, caracteres invisibles,
  - léxico no peninsular (computadora, celular, platicar...),
  - palabras que sin tilde no son español válido (asi, aqui, informacion...).

Todo lo demás (muletillas, jerga, tono) es juicio del revisor, no de este script.

Zonas: rutas que contienen `salidas/` o `cliente/` (por defecto). Se cambian con la variable
de entorno LINKEDIN_OS_LINT_PATHS (segmentos separados por comas, p. ej. "salidas/,cliente/,borradores/").
Extensiones vigiladas: .md, .txt, .json.

Lee el payload JSON del hook por stdin. No escribe en disco, no llama a nada externo.
Solo biblioteca estándar.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata

ZONAS_DEFECTO = "salidas/,cliente/"
EXTENSIONES = (".md", ".txt", ".json")

RAYA = "\u2014"          # raya larga
RAYA_CORTA = "\u2013"    # raya corta
GUION_TIPO = "\u2010"
MENOS = "\u2212"

LATAM = [r"\bcomputadoras?\b", r"\bcelulares?\b", r"\benojad[oa]s?\b", r"\bal interior de\b",
         r"\bplaticar\b", r"\bmanejar el (auto|carro)\b", r"\bcarros?\b", r"\bplata\b(?! de ley)",
         r"\bahorita\b", r"\bmesero\b"]
SIN_TILDE = [
    "asi", "aqui", "ahi", "dia", "dias", "tambien", "ademas", "todavia",
    "informacion", "regulacion", "comunicacion", "tokenizacion", "interes",
    "analisis", "inversion", "economia", "espana", "podria", "deberia",
    "habria", "tendria", "ultimo", "ultima", "unico", "unica",
    "segun", "despues", "credito", "facil", "dificil", "numero", "publico",
    "practica", "politica", "tecnologia", "energia", "garantia", "companias",
]
INVISIBLES = {
    "\u200B": "U+200B zero-width space", "\u200C": "U+200C zero-width non-joiner",
    "\u200D": "U+200D zero-width joiner", "\u2060": "U+2060 word joiner",
    "\uFEFF": "U+FEFF BOM", "\u00AD": "U+00AD soft hyphen",
    "\u2028": "U+2028 line separator", "\u2029": "U+2029 paragraph separator",
}
ESPACIOS = {"\u00A0": "U+00A0 NBSP", "\u202F": "U+202F narrow NBSP", "\u205F": "U+205F medium math space",
            "\u3000": "U+3000 ideographic space",
            **{chr(c): f"U+{c:04X} espacio tipográfico" for c in range(0x2000, 0x200B)}}
COMILLAS = {"\u201C": "U+201C", "\u201D": "U+201D", "\u2018": "U+2018", "\u2019": "U+2019"}
_SOLO_RAYAS = re.compile("^[\u2014\u2013\\-\u2012\u2015]{2,}$")
_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿]")


def _strip_urlish(line: str) -> str:
    """Quita URLs, destinos de enlace markdown y código en línea para no lintar slugs."""
    line = re.sub(r"https?://\S+|www\.\S+", " ", line)
    line = re.sub(r"\]\([^)]*\)", "]()", line)
    line = re.sub(r"`[^`]*`", " ", line)
    return line


def lint(text: str, lang: str = "es") -> list[str]:
    hard: list[str] = []
    for i, line in enumerate(text.split("\n"), 1):
        if _SOLO_RAYAS.match(line.strip()):
            continue  # separador visual del post
        cita = line.lstrip().startswith(">")
        for ch, name in INVISIBLES.items():
            for m in re.finditer(re.escape(ch), line):
                if ch == "\u200D":
                    a, b = line[max(0, m.start() - 2):m.start()], line[m.end():m.end() + 2]
                    if _EMOJI.search(a) and _EMOJI.search(b):
                        continue  # secuencia legítima de emoji
                hard.append(f"L{i}: carácter invisible {name}: eliminar")
                break
        for ch, name in ESPACIOS.items():
            if ch in line:
                hard.append(f"L{i}: espacio unicode {name} ({line.count(ch)}x): sustituir por espacio normal")
        otros = {c for c in line if unicodedata.category(c) == "Cf" and c not in INVISIBLES}
        if otros:
            hard.append(f"L{i}: carácter de formato invisible {', '.join(f'U+{ord(c):04X}' for c in sorted(otros))}: eliminar")
        clean = _strip_urlish(line)
        if cita:
            continue  # la cita literal conserva la puntuación de la fuente
        if RAYA in clean and clean.strip() != RAYA:
            hard.append(f"L{i}: raya larga (U+2014) en prosa propia: usa coma, paréntesis, punto o dos puntos")
        if RAYA_CORTA in clean:
            if re.search(rf"(?<=\d)\s?{RAYA_CORTA}\s?(?=\d)", clean) and clean.count(RAYA_CORTA) == len(re.findall(rf"(?<=\d)\s?{RAYA_CORTA}\s?(?=\d)", clean)):
                pass  # rango numérico (5-10): tolerado
            else:
                hard.append(f"L{i}: raya corta (U+2013) en prosa: usa coma, paréntesis o guion ASCII")
        rizadas = [n for ch, n in COMILLAS.items() if ch in clean]
        if rizadas:
            hard.append(f"L{i}: comillas rizadas {', '.join(rizadas)}: usar rectas (\" ') o angulares (« »)")
        if GUION_TIPO in clean:
            hard.append(f"L{i}: guion tipográfico U+2010: usar guion ASCII (-)")
        if MENOS in clean and not re.search(rf"(\d|\s){MENOS}\s?\d", clean):
            hard.append(f"L{i}: signo menos U+2212 fuera de contexto numérico: usar guion ASCII")
        if lang != "es":
            continue
        low = unicodedata.normalize("NFC", clean.lower())
        for w in SIN_TILDE:
            if re.search(rf"\b{w}\b", low):
                hard.append(f"L{i}: posible tilde ausente: «{w}»")
        for rx in LATAM:
            m = re.search(rx, low)
            if m:
                hard.append(f"L{i}: léxico no peninsular: «{m.group(0)}» (español de España)")
    return hard


def zonas() -> tuple[str, ...]:
    raw = os.environ.get("LINKEDIN_OS_LINT_PATHS", ZONAS_DEFECTO)
    return tuple(z.strip() for z in raw.split(",") if z.strip())


def texto_del_payload(payload: dict) -> tuple[str, str]:
    """Devuelve (texto a lintar, idioma). Write -> content; Edit -> new_string."""
    tool = payload.get("tool_name", "")
    inp = payload.get("tool_input") or {}
    text = inp.get("content", "") if tool == "Write" else inp.get("new_string", "")
    if not isinstance(text, str):
        return "", "es"
    lang = "es"
    body = text
    if tool == "Write" and text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            fm, body = parts[1], parts[2]
            m = re.search(r"(?mi)^lang:\s*[\"']?([a-z]{2})", fm)
            if m:
                lang = m.group(1).lower()
    return body, lang


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:  # noqa: BLE001
        return 0
    if payload.get("tool_name") not in ("Write", "Edit"):
        return 0
    fp = str((payload.get("tool_input") or {}).get("file_path", "")).replace("\\", "/")
    if not fp.lower().endswith(EXTENSIONES):
        return 0
    if not any(z in fp for z in zonas()):
        return 0
    body, lang = texto_del_payload(payload)
    if not body:
        return 0
    hard = lint(body, lang)
    if not hard:
        return 0
    msg = ["es-content-lint: el texto viola reglas de español peninsular (bloqueado).",
           f"Archivo: {fp}", ""]
    msg += [f"  - {x}" for x in hard[:20]]
    if len(hard) > 20:
        msg.append(f"  ... y {len(hard) - 20} más")
    msg.append("")
    msg.append("Corrige el texto (mismo contenido, sin estos patrones) y vuelve a escribirlo. "
               "Si es un falso positivo, explícaselo al usuario antes de forzarlo.")
    print("\n".join(msg), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
