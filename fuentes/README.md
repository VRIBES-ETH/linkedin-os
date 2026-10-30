# Fuentes verificadas

`fuentes.json` es el catálogo de fuentes que el radar consulta cada día. Son las mismas que alimentan desde mayo de 2026 un boletín diario de activos digitales y finanzas: reguladores, bancos centrales, instituciones, emisores, casas de research y unas pocas cabeceras de prensa para descubrir. Cada una se validó a mano antes de entrar.

## Campos

| Campo | Qué es |
| --- | --- |
| `id` | Identificador estable |
| `publisher` | Quién publica |
| `tier` | 1 = fuente primaria (se puede enlazar y citar). 2 = prensa, wires o agregador (solo para descubrir: antes de escribir hay que ir a la fuente primaria) |
| `categoria` | Familia: `regulacion_*`, `macro_*`, `filings_*`, `research_cripto`, `tokenizacion_rwa`, `publisher_corporativo`, `seguridad_compliance`, `infraestructura`, `organismo`, `consultora`, `banco`, `wires`, `discovery_*` |
| `metodo` | `rss` (lectura del feed) o `watch` (sin RSS: el radar vigila la página y avisa de enlaces nuevos; la primera pasada solo fija la referencia en `~/.linkedin-os/vigilancia.json`) |
| `uso` | `enlazable` o `solo_descubrimiento`, derivado del tier |
| `palabras_clave` | Si no está vacío, solo pasan las entradas que contienen alguna (para feeds corporativos muy generalistas) |
| `activo` | `false` deja la fuente en el catálogo pero fuera del escaneo |

## Cobertura (octubre de 2026)

| Familia | Ejemplos |
| --- | --- |
| Reguladores y supervisores | SEC, CFTC, OCC, ESMA, Comisión Europea (DG FISMA), FCA, PRA, FINMA, HKMA, CNMV, CVM Brasil |
| Bancos centrales e instituciones | BCE, Reserva Federal, Banco de Inglaterra, Banco de España, BIS, FSB, FMI, OMFIF |
| Emisores y plataformas | Tether, Circle, Coinbase Institutional, Fireblocks, Securitize |
| Research | Glassnode, Messari, Galaxy, Kaiko, Coin Metrics, 21Shares, Pantera, a16z crypto, Allium, RWA.xyz, Chainalysis, TRM Labs |
| Consultoras y banca | McKinsey, BCG, Citi Institute, JPMorgan Kinexys |
| Descubrimiento (tier 2) | Ledger Insights, Blockworks, Bloomberg Markets, FT Economy, PR Newswire |

## Lo que no exponen RSS

MAS, AMF, JFSA, ASIC, IOSCO, EBA, NYDFS, FMI (notas), Banque de France, DTCC, Euroclear, Clearstream, Circle, Securitize, Ondo, Franklin Templeton, BlackRock, JPMorgan, Santander, SWIFT y el Tesoro de EE. UU. Los que bloquean robots (marcados `bloquea_bots`) y los `watch` inactivos salen en el radar bajo «Para búsqueda web dirigida»: el comando `/radar` los busca con WebSearch cuando el día viene flojo.

## Gotchas conocidos

- La SEC rechaza peticiones sin un user agent con nombre y correo de contacto: exporta `RADAR_USER_AGENT="Nombre correo@dominio"`.
- El feed de ESMA llega a veces mal formado; el radar lo salta y lo lista en «Feeds sin respuesta».
- Las instalaciones de Python de python.org en macOS no traen certificados; el radar usa `certifi` si está instalado o el almacén del sistema.

## Alta de una fuente

1. Comprobar que el feed responde y que las entradas traen fecha y enlace.
2. Decidir tier con la regla de arriba, no por prestigio de la cabecera.
3. Añadirla con `activo: true` y la fecha en `nota`.
