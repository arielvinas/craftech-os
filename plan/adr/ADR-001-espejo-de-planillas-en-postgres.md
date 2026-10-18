# ADR-001 — Craftech OS: un paquete Python, tres procesos y PostgreSQL como única base; los hechos se recalculan desde las versiones crudas

**Estado:** propuesto · **Fecha:** 2026-10-18 · **Origen:** `docs/03-proposal.md` (propuesta aprobada por Ariel el 18-oct-2026)
**Veredicto:** simplify

Este documento revisa la propuesta aprobada. No la repite: dice qué queda igual, qué se achica y qué le falta. Donde no dice nada, vale lo que dice la propuesta.

## Necesidad

Craftech necesita ver qué cambió en las planillas financieras (qué celda, valor y color anterior y nuevo, cuándo y quién), guardar cada versión de cada planilla para siempre, y poder preguntar sobre los datos desde Claude Desktop con la celda de origen de cada número. Todo corre en la laptop de Ariel con Docker Compose, lo usa solo Ariel, nunca escribe en Google, y lo tiene que mantener gente con perfil DevOps/AWS.

## Diseño

**Lo que queda igual que en la propuesta:** un solo paquete Python 3.12 en una sola imagen Docker; PostgreSQL 16 como única base; migraciones en SQL numerado aplicadas por la propia herramienta, sin ORM; la lectura de Google con la service account de solo lectura (chequeo del número de versión cada 5 minutos, lectura completa solo si cambió, ventana de calma); la Drive Activity API para quién y cuándo; la web servida por FastAPI con plantillas, solo visualización; el servidor MCP (Model Context Protocol, el protocolo con el que Claude Desktop se conecta a herramientas externas) lanzado por Claude Desktop con `docker compose exec` por entrada y salida estándar; las tres únicas acciones humanas (resolver o ignorar un problema, anotar un hecho, asociar un editor de Google a una persona) con autor y motivo, solo por el servidor MCP; la clasificación de pestañas en `config/sources.yaml`.

**Cambios concretos**, cada uno con lo que lo haría volver:

1. **Sin API JSON en la v0.** La web se renderiza en el servidor y el servidor MCP habla directo con PostgreSQL: nadie consume JSON. El proceso se llama `web`, no `api`. Vuelve cuando exista un consumidor real (el resumen de Slack de la etapa D, o una aplicación rica en 2027).
2. **Sin cola de tareas.** Un solo worker con un bucle cada 5 minutos no necesita encolar nada. "Leer ahora" escribe una fila en una tabla `read_request` (planilla, pedido a las, atendido a las) que el worker revisa en cada vuelta. Compose queda con tres servicios: `postgres`, `worker`, `web`. El servidor MCP no es un servicio: es un proceso que Claude Desktop lanza y cierra.
3. **Los hechos no se versionan: se recalculan.** La propuesta daba a cada factura, devengado o cobro una vigencia (`valid_from`/`valid_to`) y cerraba la versión anterior al reinterpretar. Eso duplica el modelo y obliga a filtrar "el vigente" en cada consulta. En cambio: los hechos son una proyección determinística de (versiones crudas, cambios de celda, aliases, versión de las reglas). Reinterpretar una pestaña borra y vuelve a insertar sus hechos en una transacción, marcados con la versión de reglas que los produjo. La historia ya vive en las versiones crudas y en los cambios de celda, que nunca se borran: esa capa es el registro de eventos que pide el principio "eventos, no celdas" del documento base. La foto de un cierre (regla R18: foto al último día hábil) se reconstruye corriendo las reglas sobre la versión de ese día.
4. **Lo escrito por personas vive aparte y atado a claves estables.** Anotaciones, resoluciones de problemas y la asociación editor→persona son tablas propias, solo de inserción, con autor, fecha y motivo. Cada problema tiene una clave estable (tipo + origen: por ejemplo "color desconocido" + pestaña + color), así su resolución sobrevive a cualquier recálculo. Un color desconocido es un problema por (pestaña, color), no por celda: por celda, una sola pestaña genera miles.
5. **Sin `scenario_id` ahora.** Agregar la columna a todas las tablas de hechos es una migración de un día. Vuelve con el primer pedido real de simulación, después de la paridad.
6. **El catálogo semántico vive en un solo lugar:** `COMMENT ON TABLE` y `COMMENT ON COLUMN` dentro de las migraciones, en español, con el término del glosario de Craftech. El servidor MCP lo lee de `pg_description` y lo expone como recurso. El glosario completo es un archivo Markdown del repo que el servidor también expone. Nada que mantener en dos lados.
7. **Sin HTMX.** Las pantallas de la v0 son tablas con filtros y detalle: páginas enteras con formularios GET. Vuelve cuando una pantalla necesite refrescarse sola (por ejemplo, el estado de "leer ahora" en vivo).
8. **Sin compresión propia.** Cada versión de pestaña se guarda como un documento JSONB (valores, fórmulas, formato efectivo, celdas combinadas); PostgreSQL 16 lo comprime solo con `lz4`. No se normaliza celda por celda: una pestaña grande que cambie diez veces al día serían millones de filas por día.
9. **La alineación de filas usa el texto crudo normalizado, no la tabla de aliases.** Para detectar "fila insertada / borrada / movida" entre dos versiones alcanza con la columna clave tal como está escrita (minúsculas, sin acentos ni espacios dobles) dentro de su bloque. Un cliente renombrado es un cambio registrado, no un alias resuelto. Los aliases pertenecen a la interpretación (etapa B).
10. **Cada etapa crea sus tablas.** La propuesta "contempla en el modelo" contratos, HubSpot, Slack, flujo de budget y escenarios para no rediseñar. No se crea ninguna tabla hasta la migración de la etapa que la usa. La etapa A crea: `source`, `source_tab`, `snapshot`, `cell_change`, `drive_activity`, `editor_profile`, `issue`, `issue_resolution`, `annotation`, `read_request`, `system_event`.

**Flujo, en palabras.** El worker pregunta a Drive cada 5 minutos el número de versión de las 20 planillas. Si una cambió, espera que pasen 2 minutos sin modificaciones (tope 10), lee sus pestañas de carga y derivadas, y guarda una versión nueva solo de las pestañas cuyo contenido cambió (hash). Para cada pestaña con versión nueva calcula los cambios de celda alineando filas por clave dentro de cada bloque, y los cruza con las ediciones de Drive Activity del intervalo para atribuir autor y fecha. La web lee esas tablas y muestra Cambios, Problemas y Fuentes. Claude Desktop lanza el servidor MCP, que consulta las mismas tablas con un usuario de solo lectura y responde con planilla › pestaña › celda y momento de lectura.

```
Google (Sheets, Drive, Drive Activity; solo lectura)
   │ cada 5 min
   ▼
worker ──► PostgreSQL ◄── web (FastAPI + Jinja2, solo ver)   ← navegador de Ariel, 127.0.0.1
                ▲
                └── mcp (proceso lanzado por Claude Desktop, dos usuarios de base)
```

## Lo que NO se construye ahora

- **API JSON, cola de tareas, HTMX, compresión propia, `scenario_id`:** ver arriba, cada uno con su disparador.
- **Tablas de etapas futuras** (contratos inferidos, clientes canónicos, hechos de ingresos, gastos, sueldos, budget, paridad): se crean en la migración de su etapa (B y C). La capa cruda garantiza que no se pierde nada por esperar.
- **Caché de lecturas de Google, lectura en paralelo de pestañas, lectura por rangos parciales:** recién si una lectura completa de "Facturación - Craftech Total" medida en la etapa A supera 60 segundos.
- **Servidor MCP por HTTP con autenticación:** etapa D, cuando Emi y Ro conecten su Claude Desktop a una instancia hosteada.
- **Login en la web, Slack, alertas, seguridad por filas en PostgreSQL:** etapa D. En la v0 solo Ariel y solo desde su laptop.
- **Versiones crudas en S3:** cuando la base supere 20 GB o al pasar a AWS, lo que llegue antes.
- **Importación de revisiones viejas de Google:** decisión 3 de Ariel, "más adelante". El campo `snapshot.origin` ("lectura" / "revisión de Google") queda desde el principio porque cuesta una columna.

## Seguridad en los límites

- **Google → worker.** Clave de la service account `finance-bot-ingest` en `~/.config/craftech-os/secrets/`, montada en el contenedor como archivo de solo lectura, nunca en el repo ni en la imagen. Alcances de solo lectura (`spreadsheets.readonly`, `drive.readonly`, `drive.activity.readonly`): aunque el permiso en Drive subiera, el token no puede escribir. Con esa clave un atacante lee todas las finanzas de Craftech: por eso se rota apenas Compose esté andando (la actual es del 23 de agosto y pasó dos meses en Descargas) y en AWS pasa a Secrets Manager. **El contenido de las planillas es entrada no confiable:** cada valor se parsea estricto (número, fecha, color de la lista); lo que no cumple va a `issue`, nunca se adivina ni se convierte a la fuerza.
- **Navegador → web.** Sin login en la v0, por eso el puerto se publica solo en `127.0.0.1` en Compose, nunca en `0.0.0.0`; lo mismo PostgreSQL. La única acción es `POST /read-now`, idempotente (un pedido pendiente por planilla), sin efecto sobre datos. Jinja2 con autoescape obligatorio: la pantalla Cambios muestra texto que alguien escribió en una celda, y una celda puede contener HTML o un script.
- **Claude Desktop → mcp.** Lo lanza el usuario de la laptop con `docker compose exec`; quien pueda hacer eso ya puede abrir la base. Dos usuarios de PostgreSQL: `mcp_reader`, con SELECT solo sobre las vistas de consulta, transacciones de solo lectura, `statement_timeout` de 10 segundos y tope de filas, que es el único que corre la consulta SQL libre; y `mcp_writer`, con INSERT exclusivamente en `annotation`, `issue_resolution` y `editor_profile`, usado solo por las tres herramientas tipadas con autor y motivo obligatorios. La consulta libre nunca toca la conexión de escritura. Las tres herramientas de escritura se anotan como no-de-solo-lectura para que Claude Desktop pida confirmación antes de ejecutarlas. **Inyección de instrucciones vía celdas:** el texto de las planillas llega a Claude Desktop; una celda puede decir "ignorá lo anterior". Mitigación en la v0: las herramientas devuelven el contenido de celdas en campos estructurados (JSON), nunca como prosa, y las escrituras requieren confirmación. Se documenta como riesgo conocido.
- **Datos sensibles en reposo.** Sueldos y clientes viven en el volumen de Docker de la laptop. Requisito: FileVault activo (lo verifica Ariel). Los logs llevan identificadores y conteos, nunca valores de celdas. El dump diario (ver riesgos) se guarda cifrado si sale de la laptop.
- **Secretos de la base:** contraseñas en `infra/.env`, fuera de git; usuario de aplicación distinto del superusuario.

## Riesgos

| Riesgo | Cómo se ve |
|---|---|
| **Pérdida del disco de la laptop = pérdida de toda la historia.** Google no devuelve versiones viejas con el permiso actual; las versiones crudas solo existen acá. La propuesta no lo cubre. | Diseño: `pg_dump` comprimido una vez por día desde el worker a una carpeta fuera del repo. Métrica: fecha del último dump en Fuentes; alerta visual si tiene más de 48 horas. El destino final es pregunta abierta. |
| Una fila insertada arriba de un bloque genera cientos de cambios falsos. | Test con una pestaña de prueba: insertar una fila produce exactamente un cambio "fila insertada" y cero cambios de valor. Métrica: cambios por pestaña por día; un pico de más de 200 en una pestaña se revisa. |
| Lectura a mitad de una carga: dos versiones a minutos de distancia con cambios en la misma fila. | Métrica: versiones por planilla por hora. Si pasa seguido, se alarga la ventana de calma. |
| Varias personas editan en el mismo intervalo y la atribución es ambigua. | Métrica: porcentaje de cambios con un solo autor posible. Se muestra "una de: X, Y"; nunca se inventa. |
| Cuotas de la API de Google. | Reintentos con espera creciente; cada 429 queda en `system_event`. Métrica: llamadas por minuto. |
| Crecimiento de la base por versiones completas. | Métrica: tamaño de la base por semana en Fuentes. Estimado: pocos MB por día. Si supera 20 GB, versiones a S3. |
| Una pestaña grande hace lenta la lectura completa ("CASH FLOW USA", `data-*` de 14.000 filas). | Se mide en la etapa A: duración de cada lectura en `system_event`. Disparador de optimización: más de 60 segundos. |
| La laptop dormida corre las lecturas. | Aceptado por Ariel. Métrica: intervalo máximo entre vueltas del worker, visible en Fuentes. La fecha del cambio sale de Drive Activity, no de la lectura. |
| Instrucciones escondidas en celdas llegan a Claude Desktop. | Ver seguridad. Prueba manual en la etapa A con una celda de prueba en una planilla propia (nunca en las de Finanzas). |

## Alternativas descartadas

- **Hechos versionados con vigencia (`valid_from`/`valid_to`):** más tablas y cada consulta filtra "el vigente"; la historia ya está en las versiones crudas. Descartado por el recálculo determinístico.
- **Base de eventos o Kafka para "eventos, no celdas":** el principio se cumple con tablas append-only (versiones, cambios, escrituras humanas). Una pieza más que operar, sin beneficio a esta escala.
- **Cola de tareas genérica en PostgreSQL o Redis:** un worker, una tarea. Una tabla de pedidos de lectura alcanza.
- **Versiones crudas en archivos o S3 desde el día uno:** dos lugares donde buscar; en local, la base sola.
- **Celdas normalizadas (una fila por celda y versión):** millones de filas por día en pestañas grandes; el diff se calcula en Python sobre dos documentos.
- **Un solo usuario de PostgreSQL para el servidor MCP:** la consulta SQL libre podría escribir. Dos usuarios cuestan dos líneas en la migración.
- **Servidor MCP como servicio HTTP en Compose:** otra puerta abierta en la laptop sin autenticación. Por entrada y salida estándar no hay puerto.
- **React, Streamlit, Metabase; ORM y Alembic; Airflow, Dagster, Prefect, cron:** ya descartados en la propuesta (sección 2.2). Se concuerda.
- **Apps Script en las planillas:** descartado para siempre por Ariel (decisión 4).

## Preguntas abiertas

1. **Destino del dump diario.** Recomendado: un bucket S3 en la cuenta de AWS de Craftech, cifrado, con un script de tres líneas. Es la única excepción a "nada en la nube hasta que lo local esté perfecto"; la alternativa es una carpeta que Ariel sincronice a un disco externo o a iCloud. Lo decide Ariel; no bloquea la etapa A (el dump a carpeta local arranca igual).
2. **FileVault activo en la laptop.** Lo verifica Ariel; si no, se activa antes de la importación inicial.
3. **Rotación de la clave de la service account:** fecha. Propuesto: la semana en que Compose quede andando.

Sin preguntas de diseño: Ariel pidió "decidí vos, pero simple", y nada de lo anterior cambia con una respuesta distinta.

## Corte sugerido en tickets

Cubre la etapa A ("espejo"). Las etapas B (ingresos) y C (gastos, sueldos, budget, paridad) se cortan cuando A esté mergeada, con este mismo ADR como base.

| # | Unidad | Carril | Depende de |
|---|---|---|---|
| 1 | Andamiaje: paquete `craftech_os`, Compose (postgres, worker, web) con puertos en `127.0.0.1`, aplicador de migraciones SQL, CLI, carga de `config/sources.yaml` a `source` y `source_tab`, importación inicial de las 20 planillas a `snapshot` (valores, fórmulas, formato efectivo, combinadas, hash, origen). Medición de duración por pestaña. | `core` | — |
| 2 | Lectura continua: bucle del worker, chequeo de versión cada 5 minutos, ventana de calma, lectura completa solo de pestañas de carga y derivadas, versión nueva solo si cambió el hash, tabla `read_request`, dump diario a carpeta local, `system_event`. | `core` | 1 |
| 3 | Diferencias celda a celda: `cell_change` con tipos (valor, fórmula pisada, color, vaciada, fila insertada / borrada / movida, columna insertada, pestaña nueva / borrada / renombrada), alineación de filas por clave cruda dentro de bloques, `issue` con clave estable y colores desconocidos por (pestaña, color), `issue_resolution`. Fixtures sintéticos; ningún dato real en tests. | `core` | 2 |
| 4 | Actividad de Drive: importación hacia atrás (marzo 2026), `drive_activity`, `editor_profile`, atribución de cada cambio (autor cierto / "una de" / ventana), `annotation`. | `core` | 3 |
| 5 | Web: Cambios (filtros, detalle), Problemas, Fuentes (última lectura, duración, último dump, intervalo máximo del worker), "leer ahora". Jinja2 con autoescape. | `ui` | 3 (atribución de 4 se muestra cuando llegue) |
| 6 | Servidor MCP mínimo: usuarios `mcp_reader` y `mcp_writer` en migración, herramientas de consulta (cambios, problemas, fuentes, SQL libre sobre vistas), tres acciones con autor y motivo, catálogo desde `pg_description`, glosario como recurso, configuración de Claude Desktop documentada. | `api` | 4 |

`core` es secuencial (1 → 2 → 3 → 4); 5 y 6 corren en paralelo entre sí a partir de 3 y 4. Los archivos de migración se numeran en orden: un solo ticket de `core` activo a la vez.
