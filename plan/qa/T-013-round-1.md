# QA T-013 — Ronda 1

**Verdict: PASS**
**Branch:** arielvinas/t-013-mcp-v1 @ 67083d7
**Gates:** typecheck — (el repo no tiene) · lint ✓ (`ruff check`; `ruff format --check`: 54 archivos) · tests ✓ (293 passed con `TEST_DATABASE_URL`, en una base aislada `craftech_os_t013_test`) · build — (no hay)
**Criteria:** 5/5 se cumplen. El criterio 1 se verificó con el servidor MCP real por stdio (cliente MCP de Python) y en tests; la aplicación Claude Desktop en sí no se abrió (ver "No verificado").
**Mutation:** arnés `plan/qa/evidence/T-013-r1-mutants.py`, salida en `plan/qa/evidence/T-013-r1-mutants.txt`. Corre solo `app/tests/test_mcp.py`. Mata 10 de 13. El cambio central muere en todas sus formas:
- no resolver los problemas;
- no normalizar el texto;
- no validar la fuente;
- crear el cliente sin `crear_cliente`;
- no filtrar los problemas por fuente;
- sacar el glosario de hechos;
- sacar la frase de las instrucciones;
- no registrar la herramienta;
- vaciar la lista de parecidos;
- guardar otro autor en la resolución.

Los 3 sobrevivientes son guardas secundarias sin test (F1). Las sondas de QA matan los 3.

## Qué se probó además de la suite

- **Sondas con el intérprete real** (`plan/qa/evidence/T-013-r1-probe.py`, 20 tests, todos pasan; se corrieron como archivo temporal en `app/tests/` y se borraron). Usan el Google falso de `test_interpret`, así que el problema `alias_sin_cliente` lo abre el intérprete y no un fixture armado a mano:
  - De punta a punta: `vincular_alias` con el texto `"  Clíente   ÚNO "` y la fuente `"COBRANZAS ficticias/ventas"` vincula las dos series de la fila (la repetida también, por la regla de que una clave repetida es otra serie del mismo cliente). Reinterpretar todo deja el problema `resuelto`, no lo reabre. El problema del otro texto sigue `abierto`.
  - Un cliente existente se encuentra aunque cambien mayúsculas, tildes y espacios, y no se crea otro.
  - Volver a vincular el mismo texto a otro cliente: manda la última decisión y no se resuelve dos veces el mismo problema.
  - Un problema `ignorado` no se toca. Un problema `reabierto` (resuelto a mano y visto de nuevo por el intérprete) sí se resuelve.
  - Ocho entradas inválidas (fuente, texto, cliente, autor o motivo en blanco; fuente sin pestaña, con una parte de más, o solo `/`): error y nada escrito en `client`, `client_alias` ni `issue_resolution`. Sin el argumento `autor`, error de validación y nada escrito.
  - Nombres de cliente raros (etiqueta HTML, eñe y emoji, 2000 caracteres, un intento de inyección SQL) se guardan como dato.
  - Sin ningún cliente cargado, el error dice "Parecidos: ninguno".
- **Servidor real por stdio** (`plan/qa/evidence/T-013-r1-stdio.txt`): `uv run craftech-os mcp` con los usuarios `mcp_reader` y `mcp_writer` contra la base aislada, recorriendo el plan de pruebas del ticket. Las 11 herramientas aparecen; `vincular_alias` pide los cinco textos y `crear_cliente` es opcional; el error de cliente inexistente lista los dos parecidos; el vínculo crea el cliente y resuelve el problema; `mcp.devengados` muestra el cliente en las dos celdas de la fila sin reinterpretar; un `INSERT` por `consultar_sql` se rechaza; el catálogo trae comentario para las nueve vistas de ingresos más razones sociales y aliases; el glosario trae «Hechos de ingresos» con los cinco colores.
- **Auditoría:** `system_event` tiene cuatro `mcp_write` por un vínculo con cliente nuevo: `vincular_alias` con autor (alias), `vincular_alias` sin autor (cliente, ver F2) y `resolver_problema` con autor (la resolución).

## Findings

### F1 [minor] Tres guardas de `vincular_alias` sin test en la suite del ticket
- **Repro:** `python3 -I plan/qa/evidence/T-013-r1-mutants.py <raíz>` con `TEST_DATABASE_URL`.
- **Actual:** sobreviven tres mutantes en `app/craftech_os/mcp/server.py`:
  - **"texto and cliente not required":** sacar `texto` y `cliente` de `_required`. Ningún test de `test_mcp.py` llama con texto o cliente en blanco. Hoy lo frenaría igual la restricción de la base (`btrim(text) <> ''`), pero con `crear_cliente = true` y texto en blanco el cliente se crearía antes de que falle el alias.
  - **"estado filter only abierto"** y **"estado filter dropped":** cambiar o sacar `estado IN ('abierto', 'reabierto')`. Sin el filtro, un problema `ignorado` pasaría a `resuelto`; sin `reabierto`, un problema reabierto quedaría sin resolver.
- **Expected:** un test por cada guarda. El código actual se comporta bien: las sondas de QA (entradas en blanco, problema ignorado, problema reabierto) matan los tres mutantes.
- **Por qué es minor:** el comportamiento es correcto y está verificado; falta solo la red de tests. El plan de pruebas del ticket no los promete.

### F2 [minor] Crear un cliente queda auditado sin autor
- **Actual:** con `crear_cliente = true`, el trigger `record_mcp_write` registra el `INSERT` en `client` con `autor` nulo, porque la tabla `client` (de T-009) no tiene columna de autor. El evento del alias, inmediatamente después, sí lleva el autor.
- **Expected:** que la auditoría de cada escritura de MCP diga quién la hizo.
- **Por qué es minor:** se reconstruye por el evento siguiente y es un diseño heredado de la migración 0008, no de este ticket. Ver split-out.

### F3 [minor] Crear el cliente no es atómico con el alias
- Documentado en el ticket: `mcp_writer` no puede leer, así que el cliente se inserta y se relee con `mcp_reader` antes del alias. Si el alias falla, el cliente queda creado y al reintentar se encuentra. Con la validación previa de los cinco textos y de la fuente, QA no encontró una entrada que lo provoque.

### F4 [nit] El error de cliente inexistente arma el mensaje con datos
- El `ToolError` mete el nombre pedido y los nombres de clientes parecidos dentro del texto del mensaje, en lugar de campos con nombre. Es la única forma de devolver un error por MCP y no hay montos; se anota por la convención de que los datos viajan en campos.

### F5 [nit] El glosario nombra preguntas por código
- "hasta que Emi responda la pregunta F-05" (bajas) y "la pregunta F-01" (dólar oficial). La regla está enunciada en palabras alrededor; el código solo identifica la pregunta. Para alguien que lee desde Claude Desktop sin el repo, diría más "la pregunta de qué color marca la baja".

### Comportamientos anotados, no defectos
- Un texto que no tiene ningún problema abierto igual se vincula y devuelve `problemas_resueltos: []`. Sirve para cargar alias por adelantado; la fuente sí se valida.
- `vincular_alias` busca el cliente solo por nombre de fantasía, como dice el ticket. `load_aliases` también resuelve por razón social; si alguien pasa una razón social, recibe "no existe" con parecidos.

## Criterios

1. Una fila de prueba sin cliente se vincula; `mcp.devengados` y `mcp.facturas` muestran el cliente sin reinterpretar y el problema queda resuelto con autor y motivo: ✓ en tests (`_income`, VENTAS y Pagos), en las sondas con el intérprete real y por stdio con el servidor real. Claude Desktop en sí, no verificado.
2. La escritura queda en la auditoría de `record_mcp_write`: ✓ (alias y resolución con autor; cliente sin autor, F2).
3. `craftech://catalogo` lista las vistas de ingresos con comentario y `craftech://glosario` define cada hecho con su regla en palabras: ✓ (nueve vistas de ingresos más razones sociales y aliases; nueve definiciones; F5 como nit).
4. Sin autor o sin motivo: error y nada escrito: ✓ en blanco, solo espacios y argumento ausente, contando las cinco tablas.
5. Tests solo con datos inventados: ✓. Los nombres son "cliente inventado", "Ficticia Uno" y similares; no hay datos reales en el diff ni en la evidencia.

## No verificado

- **La aplicación Claude Desktop:** QA no la abre. Falta el paso humano del punto 1 del plan de pruebas: preguntar "¿qué filas no tienen cliente?" y ver que consulta las vistas con `cliente IS NULL` u ofrece `vincular_alias`.
- **Base local real:** QA no escribió en ella; todo se probó en `craftech_os_t013_test`. Esa base quedó en el contenedor compartido y se puede borrar con `DROP DATABASE craftech_os_t013_test`. No se tocó la base ni los contenedores de T-014.
- **Navegador:** no aplica, no hay interfaz en este ticket.

## Split-outs sugeridos (fuera del alcance)

- Auditoría con autor para la creación de clientes por MCP (F2): una columna de autor en `client`, o que el trigger tome el autor de la sesión. Toca la migración de T-009; no bloquea.
