---
id: T-013
title: Servidor MCP v1: herramienta vincular_alias y catálogo y glosario con los hechos de ingresos
status: pr
priority: high
lane: api
depends_on: [T-012]
effort: S
milestone: B
branch: arielvinas/t-013-mcp-v1
---

## Context

ADR-002, sección 8 y seguridad ("Claude Desktop → MCP"). Las vistas de ingresos ya las crearon T-009 a T-012; este ticket completa el servidor para que desde Claude Desktop se pueda preguntar por ingresos y resolver aliases sin abrir la base.

Decisiones de Ariel del 19-oct-2026: ADR-002 aprobado.

Verificado en el repo el 19-oct-2026:
- `app/craftech_os/mcp/server.py`, `build_server(reader_url, writer_url)`.
  - Herramientas de lectura: `listar_cambios`, `ver_cambio`, `listar_problemas`, `ver_problema`, `listar_fuentes`, `listar_editores` y `consultar_sql` (filtrada por `check_sql`).
  - Recursos: `craftech://catalogo` y `craftech://glosario`.
  - Herramientas de escritura: `resolver_problema`, `anotar` y `asociar_editor`, todas con autor y motivo obligatorios.
- El permiso de INSERT de `mcp_writer` en `client` y `client_alias`, con el trigger `record_mcp_write`, lo da la migración `0008` de T-009. Este ticket no agrega migraciones.

## Scope

**Dónde vive:**
- `mcp/server.py`
- el glosario y las instrucciones del servidor
- `docs/claude-desktop.md`
- `app/tests/test_mcp.py`

1. **`vincular_alias(fuente, texto, cliente, autor, motivo)`.**
   - Normaliza el texto con la misma función que `row_key`.
   - Si el cliente no existe por nombre de fantasía, lo crea, pero solo si se pasa `crear_cliente=true`; si no, devuelve un error con los clientes parecidos.
   - Inserta una decisión nueva en `client_alias` como `mcp_writer`.
   - Si hay problemas `alias_sin_cliente` abiertos para ese texto y fuente, los resuelve con el mismo autor y motivo, por el mismo camino que `resolver_problema`.
   - Sigue el patrón de las herramientas de escritura existentes: autor y motivo obligatorios, respuesta en campos estructurados.
2. **Glosario.** Agregar las definiciones de devengado, factura y sus estados por color, cobro y su certeza de fecha, baja, hito de funding, cotización y sus tipos, razón social, alias y paridad. Cada una con la regla enunciada en palabras, sin códigos sueltos.
3. **Instrucciones del servidor.** Una frase que diga que los ingresos están en `mcp.devengados`, `mcp.facturas`, `mcp.cobros`, `mcp.fundings` y las demás vistas nuevas, con el cliente ya resuelto, y que una fila sin cliente se resuelve con `vincular_alias`.
4. **`docs/claude-desktop.md`.** Tres preguntas de ejemplo: cuánto se le facturó a un cliente en un mes; qué facturas están en retraso; qué filas no tienen cliente.
5. **Tests:**
   - `vincular_alias` inserta, audita y cierra los problemas de alias;
   - sin autor o sin motivo, falla;
   - un cliente inexistente sin `crear_cliente`, falla;
   - `consultar_sql` puede leer cada vista nueva;
   - `mcp_reader` no puede escribir;
   - el catálogo lista todas las vistas nuevas con comentario.

**Descartado:** herramientas de lectura dedicadas por hecho (`listar_facturas` y similares). `consultar_sql` y el catálogo ya cubren la consulta libre (ADR-002 §8).

## Acceptance criteria

- [x] Desde Claude Desktop, con una fila de prueba sin cliente, `vincular_alias` la vincula. `mcp.devengados` y `mcp.facturas` muestran el cliente sin reinterpretar, y el problema `alias_sin_cliente` queda resuelto con el autor y el motivo dados. (verificado con el servidor MCP en los tests y por stdio con un cliente MCP; la aplicación Claude Desktop en sí no se abrió).
- [x] La escritura queda en la auditoría de `record_mcp_write`.
- [x] `craftech://catalogo` lista las vistas de ingresos con sus comentarios, y `craftech://glosario` define cada hecho con su regla en palabras.
- [x] Una llamada a `vincular_alias` sin autor o sin motivo devuelve un error y no escribe nada.
- [x] Los tests corren solo con datos inventados.

## Out of scope

- Editar o borrar aliases: solo se agregan decisiones nuevas.
- Herramientas de escritura sobre hechos: los hechos son proyección de las planillas.
- Chat dentro de la app web.

## Implementation

Archivos:
- `app/craftech_os/mcp/server.py`:
  - Herramienta `vincular_alias(fuente, texto, cliente, autor, motivo, crear_cliente=false)`.
  - Constante `FACTS_GLOSSARY`, que se suma al recurso `craftech://glosario`.
  - Una frase nueva en las instrucciones del servidor.
- `app/tests/test_mcp.py`:
  - Fixture `_income`, con datos inventados: dos pestañas, VENTAS y Pagos; un devengado y una factura con el texto "cliente inventado" y sin alias; un problema `alias_sin_cliente` por pestaña.
  - Cuatro tests nuevos.
  - Ajustes a los tests compartidos: cantidad de herramientas, instrucciones, autor y motivo vacíos, catálogo y glosario.
- `docs/claude-desktop.md`:
  - La herramienta nueva.
  - El usuario de escritura ahora inserta en cinco tablas.
  - Las vistas de ingresos.
  - Las tres preguntas de ejemplo.

Decisiones:
- **Normalización.** El texto se normaliza con `craftech_os.diff.compare.normalize`, la misma función que usa `row_key`. La fuente pasa por `clients.alias_source`, la misma función con que las vistas buscan el alias.
- **La fuente se valida.** Tiene que ser «planilla / pestaña» de alguna pestaña de `mcp.tabs`; si no, la herramienta devuelve un error y no escribe nada. Así un alias mal escrito no queda huérfano y en silencio.
- **El cliente se busca por nombre de fantasía normalizado.** Si no existe y no se pasa `crear_cliente`, el error lista los parecidos: los que contienen o están contenidos en el nombre, o tienen una similitud de 0,6 o más con `difflib` de la biblioteca estándar.
- **Una transacción.** El alias y las resoluciones de problemas se insertan juntos como `mcp_writer`. Las resoluciones van por la misma tabla `issue_resolution` que usa `resolver_problema`, con acción `resuelto`.
- **Crear el cliente no es atómico con el alias.** `mcp_writer` no puede leer, así que el id nuevo se lee con `mcp_reader` después de insertar. Si el alias falla después, el cliente queda creado; al reintentar se encuentra como existente.
- **Un alias vale para una sola fuente.** El mismo texto en otra pestaña necesita otra llamada; el test lo cubre con VENTAS y Pagos.
- La auditoría la escribe el trigger `record_mcp_write` de la migración 0008. Este ticket no agrega migraciones.
- No hubo consultas al asesor.

Cómo probar rápido:
```
uv run pytest app/tests/test_mcp.py -q
```
Necesita `TEST_DATABASE_URL`.

Sin verificar: la aplicación Claude Desktop en sí. El servidor se probó por stdio con el cliente MCP de Python contra la base local:
- 11 herramientas;
- las instrucciones nombran `vincular_alias`;
- el glosario trae los hechos de ingresos;
- `consultar_sql` lee devengados, facturas, cobros y fundings;
- autor vacío da error.

En esa base solo hubo lecturas y una escritura rechazada.

## Test plan

1. En Claude Desktop, preguntar "¿qué filas no tienen cliente?". Debe consultar las vistas de ingresos con `cliente IS NULL`, o los problemas `alias_sin_cliente` abiertos, y ofrecer `vincular_alias`.
2. `vincular_alias` con un cliente inexistente y sin `crear_cliente`. Debe dar error con los parecidos, y no deben aparecer filas nuevas en `client` ni en `client_alias`.
3. `vincular_alias` con `crear_cliente = true` sobre un texto de prueba:
   - `mcp.devengados` y `mcp.facturas` muestran el cliente;
   - el problema queda `resuelto` con ese autor y motivo;
   - `system_event` tiene `mcp_write` con herramienta `vincular_alias`.
4. El mismo texto en otra pestaña sigue sin cliente hasta que se llama otra vez con esa fuente.
5. Autor o motivo vacíos, o solo espacios: error, y nada escrito en ninguna de las cinco tablas.
6. Una fuente que no existe como «planilla / pestaña»: error, nada escrito.
7. Texto con mayúsculas o espacios distintos de la celda: debe vincular igual, porque se normaliza como `row_key`.
8. `craftech://catalogo` muestra cada vista de ingresos con su comentario. `craftech://glosario` tiene la sección «Hechos de ingresos», con los cinco colores de factura.
9. Con `consultar_sql`, un `INSERT` en `client_alias` se rechaza.

Alcance del cambio:
- `server.py` es compartido por todas las herramientas MCP: cambiaron las instrucciones, el glosario y la lista de herramientas.
- Los tests compartidos de `test_mcp.py` cuentan herramientas y tablas.
- Ninguna otra parte de la app importa el servidor.

## Post-merge

Sin migraciones ni variables de entorno nuevas. En main:

1. Reconstruir el contenedor `web`, que es donde Claude Desktop ejecuta `craftech-os mcp`:
   ```
   docker compose -f infra/docker-compose.yml up -d --build web
   ```
2. Reiniciar Claude Desktop. Verificar que lista 11 herramientas, entre ellas `vincular_alias`.
