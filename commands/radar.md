---
description: Escanea las fuentes verificadas y propone sobre qué publicar hoy (3 ángulos con fuente primaria)
allowed-tools: Bash, Read, WebFetch
---

# /radar

Dime sobre qué publicar hoy a partir de lo que han publicado las fuentes verificadas, no de lo que circula en LinkedIn.

## Pasos

1. Ejecuta el escáner determinista (sin modelo, unos 15 s):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/radar.py" --horas ${ARGUMENTS:-48}
   ```

   Deja `estado/radar-AAAA-MM-DD.md` con los candidatos agrupados por tier y categoría y actualiza `estado/vistos.json` para no repetir mañana. Las fuentes sin RSS se vigilan por diferencia de enlaces (`estado/vigilancia.json`): la primera pasada solo fija la referencia.

   Si el radar trae menos de tres candidatos en tema, usa la sección «Para búsqueda web dirigida» del markdown: elige dos o tres de esas fuentes y busca con WebSearch «<publisher> <tema del cliente> <mes y año>». Solo cuenta lo que tenga URL primaria en el sitio del publisher y fecha dentro de la ventana; nada de agregadores.

2. Lee el markdown resultante. Si existe un kit de voz del cliente (`cliente/*.local.md`), úsalo para conocer sus temas y posiciones; si no, apóyate en `cliente/temas.json` y pregunta al usuario en una sola línea desde qué posición escribe (cargo y sector) antes de proponer.

3. Elige como máximo **tres candidatos** y, para cada uno, propón en este orden:
   - **Hecho** (una frase, con la fuente primaria enlazada; si el candidato es tier 2, localiza la fuente primaria con WebFetch antes de proponerlo y, si no existe, descártalo).
   - **Ángulo del cliente**: qué puede decir que nadie más en su sector dirá, apoyado en su experiencia declarada (kit o respuesta del usuario).
   - **Por qué hoy**: qué lo hace oportuno esta semana y no dentro de un mes.
   - **Formato sugerido**: post, carrusel o comentario anclado (según el router de formatos).

4. No inventes cifras: solo las que aparecen en la fuente. Marca como «pendiente de verificar» cualquier dato que el titular sugiera pero el texto no sostenga.

5. Termina con una línea: «Para redactar, elige un candidato y pídeme el borrador» (en la versión completa del sistema, `/post <número>`).

## Reglas

- Tier 1 (regulador, banco central, institución, emisor, casa de research primaria) se puede enlazar. Tier 2 (prensa, wires) solo sirve para descubrir.
- Un candidato por tema: si tres fuentes hablan de lo mismo, elige la primaria.
- Si el radar devuelve menos de tres candidatos en tema, dilo y propón ampliar la ventana (`/radar 96`) antes de rellenar con material flojo.
