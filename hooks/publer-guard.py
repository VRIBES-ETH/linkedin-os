#!/usr/bin/env python3
"""publer-guard: ningún borrado en Publer desde Claude (hook PreToolUse de Bash).

Motivo: el borrado por la API de Publer no respeta la lista de identificadores que se le
pasa. Un DELETE con el parámetro mal nombrado vació la cola entera de un workspace
(dieciséis piezas programadas) y Publer no tiene papelera. Ocurrió dos veces antes de que
la regla escrita se convirtiera en un hook. Desde entonces el borrado es una acción
exclusivamente humana, en la interfaz de Publer.

Bloquea (exit 2) cualquier comando Bash que contenga a la vez «publer» y «delete», en
cualquier combinación de mayúsculas, y cualquier herramienta de un MCP de Publer (el oficial,
https://mcp.publer.com, u otro) cuyo nombre indique borrado: delete, remove, destroy, trash. Un falso positivo cuesta reformular un comando; un falso
negativo cuesta la cola entera.

Lee el payload JSON del hook por stdin. Solo biblioteca estándar.
"""
from __future__ import annotations

import json
import re
import sys

MENSAJE = (
    "BLOQUEADO (publer-guard): el comando toca Publer y contiene «delete». "
    "El borrado por API de Publer ignora los identificadores y vacía la cola entera del "
    "workspace, sin papelera. Borrar es una acción humana en la interfaz de Publer. "
    "Para cambiar el texto de una pieza usa PATCH; para cambiar imagen u hora, programa la "
    "pieza nueva y pide al usuario que borre la vieja a mano.\n"
)


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:  # noqa: BLE001
        return 0
    tool = data.get("tool_name") or ""
    if tool.startswith("mcp__") and "publer" in tool.lower() and re.search(r"delete|remove|destroy|trash|borra", tool.lower()):
        sys.stderr.write(MENSAJE)
        return 2
    if tool != "Bash":
        return 0
    cmd = str((data.get("tool_input") or {}).get("command") or "")
    # El propio hook se llama publer-guard: se retira del texto para poder leerlo o probarlo.
    low = re.sub(r"publer[-_]guard[\w.]*", "", cmd.lower())
    if "publer" in low and "delete" in low:
        sys.stderr.write(MENSAJE)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
