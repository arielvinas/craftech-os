# Claude Desktop con Craftech OS

Claude Desktop se conecta a Craftech OS con un servidor MCP (Model Context Protocol, el estándar con el que Claude Desktop usa herramientas externas). El servidor corre dentro del contenedor `web` y habla por entrada y salida estándar: Claude Desktop lo arranca con `docker compose exec` al abrirse y lo cierra al salir. No abre ningún puerto.

## Requisitos

1. `infra/.env` con `MCP_READER_PASSWORD` y `MCP_WRITER_PASSWORD` (solo letras y números).
2. Los dos usuarios de PostgreSQL creados. En un volumen nuevo se crean solos; en uno existente, una vez:

   ```bash
   docker compose -f infra/docker-compose.yml up -d postgres
   docker compose -f infra/docker-compose.yml exec postgres sh /docker-entrypoint-initdb.d/02-mcp-roles.sh
   ```

3. La migración `0006` aplicada (falla con un mensaje claro si los usuarios no existen) y el contenedor `web` reconstruido:

   ```bash
   docker compose -f infra/docker-compose.yml run --rm app craftech-os migrate
   docker compose -f infra/docker-compose.yml up -d --build web
   ```

## Configuración

En Claude Desktop: Configuración → Desarrollador → Editar configuración. Eso abre `~/Library/Application Support/Claude/claude_desktop_config.json`. Agregar (con la ruta absoluta del repo en lugar de `<ruta>`):

```json
{
  "mcpServers": {
    "craftech-os": {
      "command": "/usr/local/bin/docker",
      "args": [
        "compose", "-f", "<ruta>/infra/docker-compose.yml",
        "exec", "-T", "web", "craftech-os", "mcp"
      ]
    }
  }
}
```

`command` es la ruta completa de `docker` (`which docker`; con Docker Desktop suele ser `/usr/local/bin/docker`), porque Claude Desktop no carga el `PATH` de la terminal. `-T` hace falta: sin él, `docker compose exec` abre una terminal y el protocolo se rompe. Reiniciar Claude Desktop después de guardar.

El contenedor `web` tiene que estar levantado (`docker compose -f infra/docker-compose.yml up -d`). Si no lo está, Claude Desktop muestra el servidor como desconectado.

## Qué ofrece

- **Consultas**, con el usuario `mcp_reader`, que solo ve las vistas del esquema `mcp` (nunca el contenido completo de las fotos), en transacciones de solo lectura que se cortan a los 10 segundos:
  - `listar_cambios` y `ver_cambio`: cambios de celda, con filtros por planilla, pestaña, tipo, clave de fila, editor y fechas.
  - `listar_problemas` y `ver_problema`: problemas con su estado, resoluciones y anotaciones.
  - `listar_fuentes`: planillas, última lectura y salud del worker.
  - `listar_editores`: los editores de Drive, con nombre si ya se asoció.
  - `consultar_sql`: un único `SELECT` o `WITH` sobre las vistas del esquema `mcp`, hasta 500 filas.
- **Escrituras**, con el usuario `mcp_writer`, que solo puede insertar en tres tablas. Claude Desktop pide confirmación antes de cada una. `autor` y `motivo` son obligatorios:
  - `resolver_problema`: marca un problema como resuelto o ignorado.
  - `anotar`: agrega una nota a una planilla, pestaña, cambio o problema.
  - `asociar_editor`: le pone nombre a un editor de Google (`people/...`).

  Cada escritura deja un evento `mcp_write` en `system_event` con la herramienta y el autor, sin el texto.
- **Recursos** (en Claude Desktop, el botón "+" → craftech-os):
  - `craftech://catalogo`: cada vista y columna con su descripción en español, leída de la base en cada pedido.
  - `craftech://glosario`: el glosario de `docs/v0.9.md`.

Cada respuesta trae el origen de cada dato: planilla, pestaña, celda y `leido_en` (cuándo Craftech OS leyó la planilla).

## Cómo probarlo

1. Desde la terminal, sin Claude Desktop, el servidor tiene que arrancar y quedarse esperando (Ctrl-C para salir). Un error de conexión o de contraseña aparece en seguida:

   ```bash
   docker compose -f infra/docker-compose.yml exec -T web craftech-os mcp
   ```

2. En Claude Desktop, Configuración → Desarrollador: `craftech-os` aparece como conectado. El ícono de herramientas lista 10 herramientas.
3. Preguntas de prueba, sobre la planilla de prueba propia (nunca una de Finanzas):
   - "¿Qué cambió hoy en <planilla de prueba>?" La respuesta cita planilla, pestaña, celda y momento de lectura.
   - "¿Qué problemas hay abiertos?"
   - "¿Cuándo fue la última vuelta del worker?"
4. Una escritura: "Ignorá el problema N, autor Ariel, motivo prueba". Claude Desktop pide confirmación. Después, el problema aparece `ignorado` en `listar_problemas` y en <http://127.0.0.1:8000/problemas>.
5. Los registros del servidor (errores incluidos) quedan en `~/Library/Logs/Claude/mcp-server-craftech-os.log`.

## Riesgo: instrucciones dentro de las celdas

Una celda puede contener texto como "ignorá las instrucciones anteriores y …", escrito a propósito o por error, que llega a Claude Desktop como parte de una respuesta. En esta versión hay tres defensas:

1. El contenido de las celdas siempre viaja en campos con nombre (`valor_nuevo`, `formula_anterior`, …), nunca mezclado con texto del servidor.
2. Las descripciones de las herramientas avisan que esos valores son datos, no instrucciones.
3. Las escrituras piden confirmación en Claude Desktop, y el usuario de la base que usan solo puede insertar resoluciones, notas y nombres de editores: no puede borrar ni cambiar nada, ni leer.

No alcanza contra todo. Si Claude Desktop propone una escritura que no pediste, rechazala. Mitigaciones adicionales se revisan en la etapa D.
