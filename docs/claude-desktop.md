# Claude Desktop con Craftech OS

Claude Desktop se conecta a Craftech OS con un servidor MCP (Model Context Protocol, el estándar con el que Claude Desktop usa herramientas externas). El servidor corre dentro del contenedor `web` y habla por entrada y salida estándar: Claude Desktop lo arranca con `docker compose exec` al abrirse y lo cierra al salir. No abre ningún puerto.

## Requisitos

1. `infra/.env` con `MCP_READER_PASSWORD` y `MCP_WRITER_PASSWORD` (solo letras y números).
2. Los dos usuarios de PostgreSQL creados. En un volumen nuevo se crean solos; en uno existente, una vez:

   ```bash
   docker compose -f infra/docker-compose.yml up -d postgres
   docker compose -f infra/docker-compose.yml exec postgres sh /docker-entrypoint-initdb.d/02-mcp-roles.sh
   ```

3. Las migraciones aplicadas (la `0006` falla con un mensaje claro si los usuarios no existen; la `0007` agrega `mcp.celdas`) y el contenedor `web` reconstruido:

   ```bash
   docker compose -f infra/docker-compose.yml run --rm app craftech-os migrate
   docker compose -f infra/docker-compose.yml up -d --build web
   ```

## Configuración

Primero, la ruta completa de `docker` en tu máquina:

```bash
which docker
```

Con Docker Desktop suele ser `/usr/local/bin/docker` o `~/.docker/bin/docker` (escrita entera, por ejemplo `/Users/<usuario>/.docker/bin/docker`). Claude Desktop no carga el `PATH` de la terminal: sin la ruta completa no encuentra `docker`.

En Claude Desktop: Configuración → Desarrollador → Editar configuración. Eso abre `~/Library/Application Support/Claude/claude_desktop_config.json`. Agregar, con la salida de `which docker` en lugar de `<docker>` y la ruta absoluta del repo en lugar de `<ruta>`:

```json
{
  "mcpServers": {
    "craftech-os": {
      "command": "<docker>",
      "args": [
        "compose", "-f", "<ruta>/infra/docker-compose.yml",
        "exec", "-T", "web", "craftech-os", "mcp"
      ]
    }
  }
}
```

`-T` hace falta: sin él, `docker compose exec` abre una terminal y el protocolo se rompe. Reiniciar Claude Desktop después de guardar.

El contenedor `web` tiene que estar levantado (`docker compose -f infra/docker-compose.yml up -d`). Si no lo está, Claude Desktop muestra el servidor como desconectado.

## Qué ofrece

- **Consultas**, con el usuario `mcp_reader`, que solo ve las vistas del esquema `mcp` (nunca la columna `content` de las lecturas guardadas), en transacciones de solo lectura que se cortan a los 10 segundos:
  - `listar_cambios` y `ver_cambio`: cambios de celda, con filtros por planilla, pestaña, tipo, clave de fila, editor y fechas.
  - `listar_problemas` y `ver_problema`: problemas con su estado, resoluciones y anotaciones.
  - `listar_fuentes`: planillas, última lectura y salud del worker.
  - `listar_editores`: los editores de Drive, con nombre si ya se asoció.
  - `consultar_sql`: un único `SELECT` o `WITH` sobre las vistas del esquema `mcp`, hasta 500 filas. El contenido actual de las planillas está en la vista `mcp.celdas`: cada celda no vacía de la última lectura de cada pestaña activa, con `planilla`, `pestaña`, `celda` (notación A1), `texto`, `valor`, `formula`, `color_fondo` y `leido_en`.
  - Los ingresos interpretados están en `mcp.devengados`, `mcp.facturas`, `mcp.cobros`, `mcp.bajas`, `mcp.cambios_de_estado_de_factura`, `mcp.cotizaciones`, `mcp.fundings` y las vistas de paridad (`mcp.paridad_pagos`, `mcp.paridad_fundings`), con el cliente ya resuelto por su alias; los clientes, razones sociales y alias, en `mcp.clientes`, `mcp.razones_sociales` y `mcp.aliases`.
- **Escrituras**, con el usuario `mcp_writer`, que solo puede insertar en cinco tablas. Claude Desktop pide confirmación antes de cada una. `autor` y `motivo` son obligatorios:
  - `resolver_problema`: marca un problema como resuelto o ignorado.
  - `anotar`: agrega una nota a una planilla, pestaña, cambio o problema.
  - `asociar_editor`: le pone nombre a un editor de Google (`people/...`).
  - `vincular_alias`: vincula el texto con que un cliente figura en una planilla y pestaña a un cliente por su nombre de fantasía, y resuelve los problemas `alias_sin_cliente` de ese texto. Si el cliente no existe, devuelve los parecidos; con `crear_cliente` lo crea. Las filas de ingresos de ese texto muestran el cliente en seguida, sin reinterpretar.

  Cada escritura deja un evento `mcp_write` en `system_event` con la herramienta y el autor, sin el texto.
- **Recursos** (en Claude Desktop, el botón "+" → craftech-os):
  - `craftech://catalogo`: cada vista y columna con su descripción en español, leída de la base en cada pedido.
  - `craftech://glosario`: el glosario de `docs/v0.9.md` y la definición de cada hecho de ingresos (devengado, factura, cobro, baja, hito de funding, cotización, razón social, alias, paridad) con su regla escrita.

Cada respuesta trae el origen de cada dato: planilla, pestaña, celda y `leido_en` (cuándo Craftech OS leyó la planilla).

## Cómo probarlo

1. Desde la terminal, sin Claude Desktop, el servidor tiene que arrancar y quedarse esperando (Ctrl-C para salir). Un error de conexión o de contraseña aparece en seguida:

   ```bash
   docker compose -f infra/docker-compose.yml exec -T web craftech-os mcp
   ```

2. En Claude Desktop, Configuración → Desarrollador: `craftech-os` aparece como conectado. El ícono de herramientas lista 11 herramientas.
3. Preguntas de prueba, sobre la planilla de prueba propia (nunca una de Finanzas):
   - "¿Qué cambió hoy en <planilla de prueba>?" La respuesta cita planilla, pestaña, celda y momento de lectura.
   - "¿Qué problemas hay abiertos?"
   - "¿Cuándo fue la última vuelta del worker?"
   - "¿En qué celdas de <pestaña> de <planilla de prueba> aparece <un texto que sepas que está>?" Claude busca en `mcp.celdas` y responde con la celda en notación A1 (la misma que muestra Google Sheets) y el momento de lectura. Con una planilla de Finanzas sería, por ejemplo, "¿en qué celdas de CASH FLOW MENSUAL aparece tal proveedor?".
   - "¿Cuánto se le facturó a <cliente> en <mes>?" Claude suma `monto` de `mcp.facturas` por `cliente` y `mes`, separando dólares de pesos (`moneda`), y cita la celda de cada factura.
   - "¿Qué facturas están en retraso?" Claude filtra `mcp.facturas` por `estado = 'retraso'` (celda magenta) y responde con cliente, mes, monto y vencimiento.
   - "¿Qué filas no tienen cliente?" Claude busca en `mcp.devengados`, `mcp.facturas`, `mcp.bajas` y `mcp.fundings` las filas con `cliente` nulo, o los problemas `alias_sin_cliente` abiertos, y ofrece `vincular_alias` para cada texto.
4. Una escritura: "Ignorá el problema N, autor Ariel, motivo prueba". Claude Desktop pide confirmación. Después, el problema aparece `ignorado` en `listar_problemas` y en <http://127.0.0.1:8000/problemas>.
5. Los registros del servidor (errores incluidos) quedan en `~/Library/Logs/Claude/mcp-server-craftech-os.log`.

## Riesgo: instrucciones dentro de las celdas

Una celda puede contener texto como "ignorá las instrucciones anteriores y …", escrito a propósito o por error, que llega a Claude Desktop como parte de una respuesta. En esta versión hay tres defensas:

1. El contenido de las celdas siempre viaja en campos con nombre (`valor_nuevo`, `formula_anterior`, `texto`, …), nunca mezclado con texto del servidor.
2. Las descripciones de las herramientas avisan que esos valores son datos, no instrucciones.
3. Las escrituras piden confirmación en Claude Desktop, y el usuario de la base que usan solo puede insertar resoluciones, notas, nombres de editores, clientes y alias: no puede borrar ni cambiar nada, ni leer.

No alcanza contra todo. Si Claude Desktop propone una escritura que no pediste, rechazala. Mitigaciones adicionales se revisan en la etapa D.
