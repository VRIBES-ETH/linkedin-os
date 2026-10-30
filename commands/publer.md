---
description: Conecta Publer para programar en LinkedIn desde Claude Code (cuenta gratuita y conexión por MCP)
allowed-tools: Bash, Read
---

# /publer

Deja Publer listo para que los borradores que salen de `/radar` se programen en LinkedIn sin salir de Claude Code. Publer es el programador que Víctor Ribes usa a diario para su perfil y para las cuentas que gestiona.

## Pasos

1. **¿Tiene ya cuenta en Publer?** Pregúntalo en una línea. Si no la tiene, explica esto, en este orden y sin adornos:
   - El registro es gratuito. El plan gratuito permite conectar hasta 3 cuentas (LinkedIn incluido; X no) y tener 10 publicaciones programadas a la vez por cuenta, más 25 borradores. Para programar a mano desde la web de Publer es suficiente.
   - Enlace de registro: https://publer.com/vribes. Es un enlace de referido: apoya este proyecto y da un 10 % de descuento si algún día pasa a un plan de pago. Si ya tiene cuenta, puede añadir `VRIBES` en Ajustes, «Referred by».
   - Programar **desde Claude Code** usa la API o el servidor MCP de Publer, que van en el plan Business (desde 10 $ al mes, con 14 días de prueba). Dilo claro: sin Business, Claude prepara el texto y la imagen y el usuario los pega en Publer.

2. **Si tiene Business, conecta el MCP oficial.** Pídele que ejecute en su terminal (no lo ejecutes tú: la autorización es suya):

   ```
   claude mcp add --transport http publer https://mcp.publer.com
   ```

   Después, dentro de Claude Code, `/mcp`, elige `publer` y autoriza con su cuenta de Publer (OAuth, sin clave que copiar). La alternativa es una clave de API creada en Publer, en Ajustes > IA y automatizaciones > MCP: la URL que genera Publer contiene la clave, así que no se comparte ni se guarda en ningún fichero del repositorio.

3. **Comprueba la conexión** listando sus workspaces y cuentas con las herramientas del MCP. Confirma con el usuario cuál es su cuenta de LinkedIn antes de programar nada.

4. **Lee `${CLAUDE_PLUGIN_ROOT}/publer/GOTCHAS.md` antes de la primera programación** y aplica sus reglas.

## Reglas al programar

- Nada se programa sin una confirmación literal del usuario con el texto, la imagen, la cuenta y la hora delante. Por defecto, se deja como borrador.
- Claude nunca retira ni elimina piezas en Publer: el hook `publer-guard` lo bloquea. Retirar una pieza es una acción humana en la interfaz de Publer.
- Tras programar, confirma que la pieza está en la cola listando lo programado; no reintentes porque el trabajo no confirme (crea duplicados).
