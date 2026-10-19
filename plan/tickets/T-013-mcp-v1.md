---
id: T-013
title: Servidor MCP v1: herramienta vincular_alias y catálogo y glosario con los hechos de ingresos
status: backlog
priority: high
lane: api
depends_on: [T-012]
effort: S
milestone: B
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

- [ ] Desde Claude Desktop, con una fila de prueba sin cliente, `vincular_alias` la vincula. `mcp.devengados` y `mcp.facturas` muestran el cliente sin reinterpretar, y el problema `alias_sin_cliente` queda resuelto con el autor y el motivo dados.
- [ ] La escritura queda en la auditoría de `record_mcp_write`.
- [ ] `craftech://catalogo` lista las vistas de ingresos con sus comentarios, y `craftech://glosario` define cada hecho con su regla en palabras.
- [ ] Una llamada a `vincular_alias` sin autor o sin motivo devuelve un error y no escribe nada.
- [ ] Los tests corren solo con datos inventados.

## Out of scope

- Editar o borrar aliases: solo se agregan decisiones nuevas.
- Herramientas de escritura sobre hechos: los hechos son proyección de las planillas.
- Chat dentro de la app web.
