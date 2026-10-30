# Publer · incidentes conocidos de la API

Reglas aprendidas operando la API de Publer durante meses sobre varias cuentas. Cada una costó al menos un post mal programado, un duplicado o una cola vacía. Valen igual para la API y para el MCP oficial de Publer (https://mcp.publer.com, plan Business); `/publer` explica cómo conectarlo. Léelo entero antes de programar.

## 1. El borrado por API vacía la cola entera

`DELETE /api/v1/posts` borra TODOS los posts del workspace (programados y borradores) cuando no reconoce los ids. Basta un parámetro mal nombrado (`ids[]` en vez de `post_ids[]`) para que ignore el filtro y arrase la cola. No hay papelera ni vuelta atrás; lo ya publicado en LinkedIn sobrevive, pero el registro en Publer se pierde.

**Regla:** nunca borrar por API ni por MCP. El hook `publer-guard` bloquea cualquier comando o herramienta de Publer que borre. Retirar un post es una acción humana en la interfaz de Publer.

## 2. Sustituir un post es crear uno nuevo un minuto después

Como no se borra por API, una pieza mal programada no se arregla desde el MCP: se programa la buena y la persona retira la mala a mano en Publer.

- `PATCH /posts/{id}` con `scheduled_at` devuelve 200 y **no mueve la hora**. Solo cambia el texto.
- `PATCH` con `media` devuelve 200 y **no cambia la imagen**.
- Dos posts en la misma cuenta y el mismo minuto: el job sale `complete` pero con el fallo «Ya hay otra publicación en este horario. Se requiere un minuto de diferencia».

**Regla:** la pieza nueva se programa un minuto después de la vieja (o a otra hora), nunca en el mismo minuto, y se pide a la persona que quite la vieja en la interfaz. Si solo cambia el texto, PATCH `{"text": ...}` sí funciona; releer con GET después, porque la API devuelve 200 aunque ignore el cuerpo.

## 3. `get_job_status` puede devolver status null con el post creado

Tras `schedule_post`, el job puede responder `status: null, payload: {}` una y otra vez aunque el post esté programado. Reintentar porque el job no confirma crea duplicados.

**Regla:** la confirmación fiable es `list_scheduled` (estado `scheduled` o `draft`, filtrando por `account_id`). Nunca reintentar un `schedule_post` solo porque el job devuelva null.

## 4. Un job `complete` puede no haber creado nada

El job marca `complete` y deja el error en `payload.failures` («El editor está en un estado incorrecto para esta cuenta», «Ya hay otra publicación en este horario», «Document(s) not found for class Media::Base»).

**Regla:** mirar siempre `payload.failures`, no solo `status`, y confirmar con `list_scheduled`.

## 5. `get_recent_posts` va con retraso

Sale del endpoint de analítica, que incorpora los posts nuevos horas después de publicarse. Un post que acaba de salir no aparece, y dar por «no publicado» lo que sí salió lleva a reprogramar un duplicado y a avisar mal al cliente.

**Regla:** para saber si un post se publicó, `list_scheduled(state="published")`. Las métricas, después.

## 6. `get_recent_posts` no dice si el post llevaba imagen

Devuelve texto y métricas, no el media. Un post que «parece solo texto» puede haber llevado imagen, gráfico o carrusel.

**Regla:** no deducir el formato visual del corpus de Publer. Si importa, comprobarlo en LinkedIn o preguntar.

## 7. X exige `network="twitter"` y, por encima de 280 caracteres, Long post

Con el `network` por defecto (`linkedin`) y una cuenta de X, el job sale `complete`, falla en `failures` y no crea post. Y un texto de más de 280 caracteres necesita `details.type = long_post` (requiere X Premium); sin él Publer lo guarda como publicación normal y falla al salir.

**Regla:** para cuentas de X pasar siempre `network="twitter"`. El MCP añade `long_post` solo si la red es twitter y el texto supera 280 caracteres. Verificar tras programar que el post trae `details.type = long_post`.

## 8. `media_id` es una cadena, y un parámetro desconocido se ignora en silencio

`schedule_post` y `create_draft` aceptan `media_id` en singular y como cadena. Si se pasa `media_ids` o una lista, el parámetro se ignora sin error: el job sale limpio, `list_scheduled` muestra el post, y lo programado es solo texto (`type: status`, `media: null`). Varios ids separados por comas tampoco valen: Publer los busca como un solo id y el job falla.

**Regla:** un `media_id`, cadena. Tras programar cualquier pieza con imagen, comprobar en `list_scheduled` que `tiene_media` es verdadero (o GET `/posts/{id}` y mirar `type` y `media`).

## 9. Subida de media desde disco: directa; desde URL o PDF: asíncrona

`POST /media` multipart (`upload_media_from_file`) devuelve el objeto de media al momento, con su `id`. No hace falta alojar la imagen en una URL pública. Gotchas de la implementación: quitar `Content-Type` de las cabeceras (httpx fija su boundary); `direct_upload: true` en `media/from-url` no sirve como alternativa.

En cambio, `media/from-url` devuelve `job_id` y hay que consultar `get_job_status` hasta `complete`. Un PDF también entra como trabajo asíncrono.

**Regla:** imagen en disco → `upload_media_from_file` → `media_id` → `schedule_post`. URL solo cuando la imagen ya vive publicada.

## 10. El formato documento (carrusel PDF) de LinkedIn no se puede pedir por API

La API rasteriza el PDF y publica un mosaico de imágenes. `type: "document"` lo rechaza LinkedIn («Post type is not valid»); `type: "carousel"` revienta con un error interno de Publer; `/media/documents` no existe.

**Regla:** programar las láminas como imágenes (`type: photo`, varias entradas en `media`, hoy fuera del MCP: una sola imagen por herramienta) y marcar a mano en el editor web la casilla «Publicar fotos como documento PDF», rellenando el «Título» que aparece debajo.

## 11. El texto plano es `type: status`, no `post`

`post` no es un tipo válido: LinkedIn responde «Post type is not valid» tanto en programado como en borrador, en perfil y en página. Tipos válidos: `status` (texto), `link`, `photo`, `gif`, `video`, `reel`, `story`, `short`, `poll`, `document`, `carousel`, `article`. Con imagen, `photo` y `media: [{id, type: "image"}]`.

El MCP ya lo aplica. Si se programa por API directa, usar ese esquema.

## 12. El ER de Publer anticorrelaciona con el alcance

`engagement_rate` = interacciones / `reach`, y `reach` son impresiones únicas. Un post con 68 impresiones y 10 interacciones marca 14,7; uno con 25.000 y 224 marca 0,9. Medido sobre más de cien posts, la correlación ER~reach es negativa (Spearman en torno a -0,5) y ER~interacciones es nula. `get_top_posts` ordena por ER, así que devuelve lo que menos gente vio.

**Regla:** para juzgar rendimiento usar `interacciones`, `multiplo_alcance` (reach/seguidores) y `er_seguidores` ((reacciones+comentarios+compartidos)/seguidores, en %), que el MCP calcula por fila. Nunca ordenar por ER ni por reach brutos.

## 13. `post_insights` trae filas vacías y duplicados

El endpoint devuelve a veces el mismo post con dos ids (uno con las impresiones reales y otro casi a cero) y filas con texto vacío. El MCP deduplica (mismo id, o mismo texto normalizado y misma fecha; sobrevive la fila de mayor alcance), marca `sin_texto` y devuelve `duplicados_retirados`. En `get_post_insights` la deduplicación es solo dentro de la página pedida.

## 14. Varias cuentas en un workspace comparten calendario

Si el workspace tiene perfil personal y página de empresa, `list_scheduled` los mezcla.

**Regla:** filtrar por `account_id` antes de atribuir un post a una cuenta, y comprobar siempre el recuento de la cola antes y después de cualquier cambio.

## 15. Seguidores: series por tramos de 90 días

`analytics/{cuenta}/chart_data` con `chart_ids[]=followers` devuelve puntos semanales si el rango es de 90 días o menos y anuales si es mayor. Para una serie larga, pedir por tramos de 90 días. El dato es `last_value`.

## 16. Entorno

El Python de sistema de macOS (framework 3.10) falla con `CERTIFICATE_VERIFY_FAILED` contra `app.publer.com`. Usar el Python del venv del MCP (httpx trae certificados). Con `urllib` Cloudflare corta con 403; usar httpx o curl.
