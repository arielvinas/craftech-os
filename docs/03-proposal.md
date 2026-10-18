# Craftech OS — Etapa 3: Propuesta

**Fecha:** 18 oct 2026 · **Base:** `docs/KICKOFF.md`, `docs/v0.9.md`, `docs/01-understanding.md`, `docs/02-questions.md` con las respuestas de Ariel, las decisiones de la sesión de aliases y las verificaciones del 18-oct con la service account.

**Qué es este documento.** Cómo propongo construir Craftech OS: arquitectura, modelo de datos, cómo resuelvo la primera versión (la "v0": importar, leer continuo, registrar cambios, reportar lo ilegible), cómo se usa, en qué etapas se entrega, cómo cumple cada regla del documento base y qué riesgos tiene. **Termina con las decisiones de Ariel** (sección 11): las contestó todas el 18 de octubre y el texto ya las incorpora. **Propuesta aprobada.** Lo que sigue es el flujo de desarrollo con las skills de Ariel: revisión de arquitectura (`/architect`), PRDs y tickets (`/ticket`) en `plan/`, y recién después código. Un primer intento de escribir especificaciones y código directamente desde esta propuesta quedó descartado (ver `CLAUDE.md`).

**Convención:** cada planilla se nombra por su título completo (por ejemplo "Facturación - Craftech Total", no "S1"). Cada regla del documento base se cita con su número y con su contenido, para que no haga falta ir a buscarla.

---

## 0. Resumen en una página

- **Una sola base de datos (PostgreSQL) con cuatro capas:** (1) **crudo**: cada versión de cada planilla guardada entera, para siempre; (2) **cambios**: la diferencia celda a celda entre dos versiones, con valor, fórmula y color anteriores y nuevos, cuándo se detectó y, si Google lo permite, quién; (3) **interpretado**: facturas, devengados, cobros, fundings, gastos, sueldos y budgets, derivados del crudo por reglas versionadas que se pueden volver a correr; (4) **canónico y enriquecimiento**: clientes, razones sociales, contratos, personas y anotaciones hechas por gente, atadas a claves estables y no a celdas.
- **La regla "una regla financiera sin respuesta no se implementa" se sostiene con la capa cruda:** todo queda guardado desde el día uno, y cuando Emi contesta se vuelve a interpretar hacia atrás. No se pierde nada por esperar.
- **Lectura continua barata:** cada 5 minutos se consulta solo el número de versión de cada planilla (una llamada liviana por planilla); solo si cambió se lee la planilla completa, se guarda la versión y se calcula la diferencia. Las pestañas se clasifican en CARGA (se registran cambios y se alertan), DERIVADA (se leen para paridad, sin alertas), HISTÓRICA (se importan una vez) e IGNORAR (anexo A).
- **Quién y cuándo:** la Drive Activity API quedó habilitada el 18 de octubre y funciona con el permiso de Lector: da quién editó cada planilla y cuándo, a nivel archivo, con historia hacia atrás hasta marzo de 2026. Un cambio de celda se atribuye cruzando la diferencia entre dos lecturas con las ediciones registradas en ese intervalo. Lo que Google **no** expone a un Lector es el historial de versiones (el contenido de las versiones anteriores): Ariel decidió que la historia de celdas empiece el día del arranque y ver más adelante la importación antigua (decisión 3, sección 4.4).
- **Tecnologías:** un solo paquete Python 3.12 con tres puntos de entrada (API con FastAPI, proceso trabajador, servidor MCP), PostgreSQL 16, web servida por el mismo FastAPI con plantillas (sin segundo lenguaje ni toolchain de Node), todo en Docker Compose en la laptop de Ariel. **El chat sobre los datos es desde Claude Desktop**, conectado a un servidor MCP (Model Context Protocol, el estándar con el que Claude Desktop se conecta a herramientas externas) que expone consultas de solo lectura y responde siempre con la referencia de origen (planilla › pestaña › celda y momento de lectura). La web es solo visualización. Nada tiene licencia ni costo por uso.
- **Etapas:** semanas 1–2 el "espejo" (importar todo y ver cambios); semanas 3–4 los ingresos interpretados y el primer servidor MCP para preguntar desde Claude Desktop con referencias (ahí ya es útil); semanas 5–8 gastos, sueldos, budget y funding completos, con el P&L y el cashflow regenerados y un tablero de paridad; después hosting en AWS para que entren Emi y Ro, Slack y alertas. La API de Mercury queda para 2027 (decisión 7). Lo de fin de año se detalla en la sección 6.
- **Un cambio al modelo del documento base:** un cliente comercial puede tener varias razones sociales (Widergy tiene tres, n1u dos, Digiventures dos). Propongo cliente 1:n entidad legal del cliente. Es un refinamiento de la regla R32 (ratificada). Ariel lo aceptó provisoriamente y lo cierra con Emi; no bloquea nada (decisión 5).

---

## 1. Qué tiene que cumplir

**Del KICKOFF (sección 4):** lo construye Ariel con Claude Code y lo tiene que poder mantener gente de Craftech con perfil DevOps/AWS; sin licencias pagas para ser robusto; puede correr en la cuenta de AWS de Craftech; lo primero útil en pocas semanas; nunca escribe en las planillas ni en Drive; las reglas financieras las deciden Emi y Ro.

**De las respuestas de Ariel (Etapa 2):**

| Respuesta | Qué ordena en la propuesta |
|---|---|
| Todo en Docker local; la nube después. | Docker Compose como entorno único hasta que esté perfecto. Las mismas imágenes van después a AWS. |
| En la v0 el sistema lo usa solo Ariel; Emi y Ro entran con la versión hosteada. | La v0 es una web local sin login. Slack, permisos y accesos quedan para la versión hosteada. |
| Lo más útil es **preguntar por chat sobre los datos, con referencia de dónde salió cada dato**. El chat tiene que ser desde Claude Desktop; la app es solo visualización y base de datos (decisión 1). | El sistema expone un servidor MCP con herramientas de solo lectura; Claude Desktop se conecta a él. Entra temprano (semana 3–4) sobre lo ya interpretado, y toda respuesta cita su origen. La web no tiene chat. |
| Tecnologías: "decidí vos, pero sistemas simples, fáciles de mantener, sin sobrecomplicaciones" (decisión 1). | Un solo lenguaje (Python), una sola base, una sola imagen Docker con tres puntos de entrada, web con plantillas servidas por el mismo proceso. Sección 2.2. |
| Nada de scripts dentro de Google Docs: todo de nuestro lado, para que el día que se deshabilite Google no quede nada atado (decisión 4). | Las planillas no se modifican nunca, ni con scripts. Todo lo que el sistema sabe vive en PostgreSQL (la capa cruda guarda cada versión entera), así que apagar Google no pierde nada. |
| Las cinco preguntas de ejemplo (sección 7). | Dos de ellas necesitan cosas que hoy no existen en las fuentes: la API de Mercury y una regla fiscal. Se dicen tal cual. |
| Leer cada 15 minutos en horario laboral, cada hora fuera; si se pinta el viernes y se lee el lunes, la fecha es el viernes. | Lectura por número de versión cada 5 minutos (más barata y más frecuente que lo pedido) y fecha del cambio tomada de la actividad de Drive cuando se pueda (sección 4.4). |
| Importar todos los valores históricos; la historia de cambios "hasta donde la API permita". | Sección 4.2. |
| Clasificación de pestañas propuesta por mí y validada por Finanzas. | Anexo A. |
| Paridad = "P&L Craftech" mensual y "Resumen mensual Cash Flow ARG-USA". | Sección 3.7 y etapa C. |
| Documentación en español; código y especificaciones técnicas en inglés con el glosario de Craftech. | Así está organizado el repo (sección 2.5). |
| Repo: todo en este repo (decisión 10). | Un solo repo: `docs/`, `app/`, `config/`, `infra/` (sección 2.5). |
| "FUNDINGS - Log de status [OFICIAL]" tiene la verdad sobre el funding; la fila "Funding de AWS confirmados" de Facturación - Craftech Total › Pagos es un IMPORTRANGE de su pestaña "Pagos confirmados". | Esa fila se lee como control y no se suma como cobro. |
| El vendedor por contrato va a estar en HubSpot; lo de las planillas se ignora. | Comisiones (regla R21) quedan para cuando HubSpot esté integrado. |
| La columna "Servicio" de Pagos no se usa, pero conviene etiquetar lo histórico. | Se importa como etiqueta informativa, sin lógica. |

---

## 2. Arquitectura y tecnologías

### 2.1 Forma general

Un paquete Python, una imagen Docker, tres procesos y una sola base de datos:

```
Google Sheets + Drive Activity (solo lectura, service account finance-bot-ingest)
        │  cada 5 min: ¿cambió la versión?  →  si cambió: lectura completa de la planilla
        ▼
  worker  ──►  PostgreSQL  ◄──  api + web (FastAPI, plantillas)   ← navegador de Ariel (solo ver)
                  │       ◄──  mcp (servidor MCP, solo lectura)   ← Claude Desktop (preguntar)
                  ├─ crudo: versiones completas de cada planilla
                  ├─ cambios: diferencias celda a celda, con quién y cuándo
                  ├─ interpretado: facturas, devengados, cobros, fundings, gastos, sueldos, budget
                  ├─ canónico: clientes, razones sociales, contratos, personas, dimensiones
                  ├─ enriquecimiento: anotaciones de personas
                  └─ problemas: lo ilegible y las contradicciones, con dueño y estado
```

- **worker:** lee Google, guarda versiones, calcula diferencias, cruza con la actividad de Drive, interpreta, detecta problemas. Un solo proceso con un planificador interno; las tareas se encolan en una tabla de PostgreSQL (sin Redis ni colas externas).
- **api + web:** un proceso FastAPI que sirve JSON y las páginas de la web (plantillas del servidor). La web es **solo visualización**: no tiene botones que escriban, salvo "leer ahora".
- **mcp:** el servidor MCP que usa Claude Desktop. Expone herramientas de consulta (buscar cambios, facturas, fundings, problemas; consulta SQL libre sobre vistas) con un usuario de PostgreSQL que solo puede leer, más el catálogo semántico y el glosario como recursos. Es también la **única superficie de escritura humana** en la v0, acotada a tres acciones con autor y motivo: resolver o ignorar un problema, anotar un hecho, y asignar un editor de Google a una persona (sección 4.4). Nada más escribe en la base fuera de la ingesta.
- **PostgreSQL:** única base. Incluye las versiones crudas (comprimidas) mientras corre en local; en AWS las versiones crudas pasan a S3 y la base guarda solo la referencia.

Los tres procesos son el mismo paquete Python con tres puntos de entrada (`craftech-os worker`, `craftech-os api`, `craftech-os mcp`) y una sola imagen; comparten modelos, reglas y acceso a datos.

### 2.2 Elecciones y porqués

| Pieza | Elección | Por qué | Qué descarté y por qué |
|---|---|---|---|
| Lenguaje del backend | **Python 3.12** | Es lo que mejor maneja un equipo DevOps/AWS; las librerías de Google y de Claude son de primera clase; el trabajo es de datos (diferencias, interpretación, reglas), donde Python es natural. | **TypeScript full-stack:** válido, pero el trabajo pesado es de datos y reglas, no de interfaz. **Go:** menos cómodo para iterar reglas financieras con Claude Code. |
| API | **FastAPI** | Tipado, documentación automática, liviano. | **Django:** trae más de lo necesario (admin, ORM pesado) para una API sobre un modelo que va a cambiar seguido. |
| Base de datos | **PostgreSQL 16** | Una sola base para crudo (JSONB comprimido), hechos, vistas y la cola de tareas. JSONB, vistas materializadas y seguridad por filas cubren todo lo que la v0 y la paridad necesitan. Es el servicio administrado más barato y conocido en AWS (RDS). | **Bases de eventos dedicadas (EventStoreDB, Kafka):** otra pieza que operar sin beneficio a esta escala (decenas de planillas, miles de cambios por día como mucho). **Bases NoSQL:** la paridad es SQL puro. **Supabase/Firebase:** hosting ajeno y dependencia. |
| Migraciones y acceso a datos | **SQL explícito con migraciones versionadas** (archivos SQL numerados que aplica la propia herramienta; sin Alembic ni ORM: una dependencia menos, mismo resultado) | Las vistas del P&L y el cashflow se escriben en SQL y se leen como SQL: cualquiera de Craftech las puede auditar. | **ORM completo:** esconde justamente lo que la paridad necesita ver. |
| Planificador | **Proceso worker con un bucle simple (sin librería de planificación) y cola en PostgreSQL** | Trece planillas y una tarea cada 5 minutos no justifican un orquestador. | **Airflow / Dagster / Prefect:** mucha operación para poco. **Cron del sistema:** no sirve igual en la laptop y en AWS. |
| Web | **Plantillas del servidor (Jinja2 + HTMX) servidas por el mismo FastAPI** | Ariel pidió sistemas simples y una app de solo visualización: tablas con filtros y detalle, sin chat ni edición. Con eso, un segundo lenguaje y un toolchain de Node (React, Vite, dependencias) no pagan su costo de mantenimiento para un equipo DevOps/AWS. Un solo lenguaje, un solo proceso, una sola imagen. | **React + TypeScript:** mejor si la web fuera una aplicación rica con edición y flujos; eso es la etapa E (2027) y se decide ahí, con la API JSON ya existente como frontera. **Streamlit:** solo para prototipos. **Herramientas de tableros (Metabase, Superset):** no reemplazan el producto; pueden sumarse después, en modo lectura sobre PostgreSQL. |
| Chat sobre datos | **Servidor MCP (Model Context Protocol) en Python, consumido desde Claude Desktop** | Es la prioridad número uno de Ariel y lo pidió así (decisión 1). Claude Desktop recibe la pregunta, elige qué herramienta del servidor usar (consultas prearmadas o SQL libre sobre vistas con un usuario de PostgreSQL que solo puede leer), y responde con las referencias de origen de cada número. No hay interfaz de chat propia que mantener ni costo por uso de API: Claude Desktop ya está pago. En la v0 el servidor corre en el Compose local y Claude Desktop lo lanza como proceso local (transporte stdio, con `docker compose exec`); en la etapa hosteada se expone por HTTP con autenticación para que Emi y Ro conecten su propio Claude Desktop. | **Chat embebido en la web con la API de Claude:** otra interfaz, otra clave, costo por uso, y Ariel no lo quiere. **Texto a SQL sin catálogo:** inventa; por eso el catálogo semántico es parte del modelo de datos y se expone como recurso del servidor. |
| Lectura de Google | **API de Google Sheets v4, Drive v3 y Drive Activity v2, service account `finance-bot-ingest`**, alcances de solo lectura (`spreadsheets.readonly`, `drive.readonly`, `drive.activity.readonly`) | Verificado el 18-oct: la clave funciona, abre las 20 planillas y lee la actividad de Drive. Con alcances de solo lectura, el token no puede escribir aunque el permiso en Drive fuera mayor. | **Apps Script dentro de las planillas:** descartado por decisión de Ariel (decisión 4): nada se instala en Google, para que apagar Google Docs algún día no deje nada atado. **Delegación de dominio:** daría a la service account poder sobre cualquier usuario de craftech.io; innecesario. |
| Línea de comandos | **Una sola herramienta `craftech-os`** (importar, leer ahora, reinterpretar, chequear paridad): solo operación, no datos | Todo lo operativo se hace desde la terminal del contenedor, con historial en `system_event`. Evita botones de administración en la web. Las acciones de personas sobre datos van siempre por el servidor MCP. | **Panel de administración web:** más superficie, y la web es solo visualización. |
| Secretos | Clave en `~/.config/craftech-os/secrets/`, montada en el contenedor como archivo de solo lectura; `.env` fuera de git | Nunca una credencial en el repo. | — |
| Hosting futuro | Mismas imágenes en **AWS**: RDS PostgreSQL + ECS Fargate (o una sola EC2 con Compose como primer paso), S3 para versiones crudas, Secrets Manager para la clave | Es la cuenta y el perfil del equipo. Se decide cuando lo local esté perfecto, como pidió Ariel. | — |

### 2.3 Lo que no entra en la primera etapa, a propósito

Integraciones de escritura (HubSpot, Slack, Jira, Notion, Partner Central), autenticación y permisos por persona, flujos de aprobación, escenarios. Todas están contempladas en el modelo (sección 3) para no rediseñar, pero no se construyen hasta tener paridad.

### 2.4 Qué pasa con la laptop apagada

Lo que aceptó Ariel: durante la v0 se acepta que una lectura se corra; cada lectura lleva su marca de tiempo real y la fecha del cambio sale de la actividad de Drive (ya verificada), no de la lectura. La web muestra "detectado el lunes 9:00, editado el viernes 22:10" en vez de un solo dato ambiguo.

### 2.5 Organización del repo

```
docs/            documentación en español (KICKOFF, v0.9, 01, 02, 03); plan/ (PRDs, ADRs, tickets) según las skills
app/             un paquete Python (inglés; términos de Craftech: Accrual, Invoice, Payment…)
  craftech_os/
    ingest/      lectura de Google, snapshots, actividad de Drive
    diff/        diferencias celda a celda, identidad de fila
    rules/       interpretación: hechos de negocio, versionada
    api/         FastAPI: JSON + páginas (plantillas en api/templates/)
    mcp/         servidor MCP para Claude Desktop
    cli.py       herramienta de línea de comandos
  migrations/    SQL versionado (archivos numerados)
  tests/
config/sources.yaml   las 20 planillas y la clasificación de sus pestañas (anexo A); sin datos de clientes
infra/           docker-compose.yml, Dockerfile, después Terraform para AWS
```

Un solo repo (decisión 10). Los datos de clientes y sueldos no entran al repo bajo ninguna forma: ni fixtures, ni exportaciones, ni capturas. La clasificación de pestañas sí (son nombres de pestañas, no datos), así se versiona y se revisa como código en vez de editarse desde la web.

---

## 3. Modelo de datos conceptual

El modelo tiene capas. Cada capa solo depende de la anterior, y las de abajo nunca se borran.

### 3.1 Capa cruda: versiones de planillas

- **`source`**: cada planilla conocida (id de Drive, título, unidad compartida, entidad que la carga).
- **`source_tab`**: cada pestaña, con su clasificación (CARGA / DERIVADA / HISTÓRICA / IGNORAR), cargada desde `config/sources.yaml` del repo, y su "esquema" conocido (en qué fila está el encabezado, qué columna identifica la fila, qué bloques hay y dónde empiezan). El anexo A es la clasificación inicial.
- **`snapshot`**: una lectura completa de una pestaña en un momento: valores, fórmulas, formato efectivo (color de fondo, formato numérico), celdas combinadas, número de versión de Drive y hora de modificación que informó Google, hora de lectura, y hash del contenido. Se guarda comprimida. **Nunca se borra.**

Por qué guardar todo: porque las reglas van a cambiar (Emi todavía no contestó varias) y porque "importar toda la historia" necesita poder volver a mirar cualquier momento. El costo es bajo: una pestaña grande ocupa unos pocos megabytes comprimidos, y solo se guarda cuando cambió.

### 3.2 Capa de cambios

- **`cell_change`**: para cada par de versiones consecutivas de una pestaña, una fila por celda que cambió: posición, valor anterior y nuevo, fórmula anterior y nueva, color anterior y nuevo, tipo de cambio (valor, fórmula pisada a mano, color, celda vaciada, fila insertada, fila borrada, columna insertada, pestaña nueva o borrada, pestaña renombrada), hora de detección, ventana de tiempo en la que pudo ocurrir, y la atribución de autor (sección 4.4).
- **`row_identity`**: cómo se identificó cada fila entre versiones (sección 3.6).

Esto es lo que el KICKOFF pide ver en la v0: qué cambió, dónde, cuándo y, si se puede, quién.

### 3.3 Capa interpretada: hechos de negocio

Cada hecho sale de un snapshot por una regla, y lleva la referencia exacta de origen (`snapshot_id`, pestaña, celda o rango) y la versión de la regla que lo generó. Los hechos no se editan: una reinterpretación genera una nueva versión del hecho y cierra la anterior (vigencia `valid_from` / `valid_to`, por hora de detección).

| Hecho | De dónde sale | Regla del documento base |
|---|---|---|
| **Devengado (`Accrual`)**: cliente × mes × USD, con unidad de negocio y POD | VENTAS de Facturación - Craftech Total y de Facturación - SleakOps Total | R1 (prorrateo por días), R14 (neto de IVA), R37 (Ventas Argentina 2025 ya está en VENTAS) |
| **Factura (`Invoice`)**: clave = fila de cliente + mes + entidad legal; monto; moneda; estado por color; cotización si es en ARS | Pagos y Pagos ARG de las dos planillas de facturación | R25 (entidad legal según pestaña), R26 (identidad), R29 (colores), R30 (vacío = no existe), R23 y R10 (ARS a cotización pactada), R38 (cotización tipeada a mano) |
| **Cambio de estado de factura (`InvoiceStatusChanged`)** | Cambio de color detectado | R29, R30 |
| **Cobro (`Payment`)**: factura pasó a verde | Cambio de color a `#d9ead3` | R4 (fecha del verde) |
| **Baja de cliente SleakOps (`ClientChurned`)** | Celda pintada sin monto en Facturación - SleakOps Total | R31 |
| **Hito de funding (`FundingMilestone`)** y su cobro | Bloque AWS de Pagos hasta el 24/2/2026; "FUNDINGS - Log de status [OFICIAL]" desde el 25/2/2026 | R22, R24, R27, R28 |
| **Movimiento bancario (`BankMovement`)** y **gasto (`Expense`)** | Base informe Craftech › Consolidado y pestañas por banco | R11 (intercompany), R17, R34 (cuentas de ajuste), R35 |
| **Costo laboral (`PayrollAccrual`)** y **pago de nómina (`PayrollPayment`)** | "Costos" › sueldos (lo que lee el P&L), Base sueldos, Base informe › Sueldos / Bonos / SAC / Comisiones / control sueldos y ccss | R5, R6, R7, R8, R33, R39 |
| **Línea de budget (`BudgetLine`)** | Budget y "Budget por Area 2026 - Final" | Pendiente F-14 (cuál es el viejo y cuál el nuevo) |
| **Cotización (`FxRate`)**: tipo, mes, valor, fuente | Pagos ARG filas 1 y 23–27; Base informe › TC MEP | R10; verificado: la MEP operativa es la fila 27 |
| **Objetivo de venta** | VENTAS, objetivos por mes y trimestre | Sin regla; se importa como dato (F-23 abierta) |

**Clave del diseño:** si Emi contesta mañana que la cotización pactada de los clientes de la S.A. es el "Dólar oficial" de la fila 1, la regla de `Invoice` cambia de versión y se vuelve a correr sobre todos los snapshots guardados. No hay que volver a leer nada ni se pierde la historia.

### 3.4 Capa canónica: entidades que existen una sola vez

- **`client`**: el cliente comercial (nombre visible = nombre de fantasía de las planillas; id de HubSpot).
- **`client_legal_entity`**: cada razón social de ese cliente: nombre legal, país, identificación fiscal, sistema donde vive (Bejerman para Craftech S.A., Zoho hoy y HubSpot después para Craftech-io Inc), plazo de pago (default 10 días). **Un cliente puede tener varias** (Widergy: WIDERGY S.R.L. en Argentina, Dalcudia SA en Uruguay y Widergy España; n1u: Blockchain Payments Rails S.A. y Level Up Finance LLC; Digiventures: Digi Tech Argentina y DIMEX).
- **`client_alias`**: cada variante de nombre en cada fuente ("Consorcioabierto SRL", "Consorcio Abierto", "TRackchain"…) → cliente, con quién lo decidió y cuándo. Se carga desde las decisiones del artefacto de aliases (51 decisiones ya tomadas).
- **`contract`**: en USD, tipo, horas reservadas, tarifas, fechas, upfront, plazo, tipo de cotización si factura en ARS, vendedor (de HubSpot, después). Al principio se **infieren** de VENTAS y de las fórmulas de Pagos ARG (el monto del contrato está escrito dentro de la fórmula: `7200*1.21*M1`), se marcan como inferidos y los revisan Emi y Ro.
- **`legal_entity`**: Craftech S.A. y Craftech-io Inc.
- **`person`, `position`**: con vigencia de rol, banda, área y unidad de negocio (R7, R8).
- **`aws_program`**: oportunidad + tipo (POC, IW MIGRATE/BUILD/ASSESS, MAP, MAP 2.0, CEI = AWS Customer Engagement Incentive, programa terminado en 2026).
- **`bank_account`**, **`vendor`**, **`adjustment_account`** (AFIP y CLIENTES).
- **`dimension`** con vigencia: unidad de negocio, POD, área, vendedor, programa de AWS, línea de servicio.

**Refinamiento a la regla R32** (ratificada: "el cliente canónico es la razón social legal; el nombre de fantasía es su nombre visible y alias"): la identidad fiscal sigue siendo la razón social, pero **la unidad comercial es el cliente, y un cliente tiene una o más razones sociales**. Sin esto, Widergy serían tres clientes y el devengado de VENTAS (que está por nombre de fantasía) no se podría cruzar con las facturas. Lo tienen que aceptar Ariel y Emi (decisión 5 de la sección 11).

### 3.5 Capa de enriquecimiento y problemas

- **`annotation`**: texto o dato estructurado que una persona agrega sobre cualquier entidad (cliente, factura, hito de funding, línea de budget), con autor, fecha y motivo. Se ata a la **clave estable** de la entidad (por ejemplo, factura = cliente + mes + entidad legal), nunca a una celda. Por eso sobrevive a que la fila se mueva o la pestaña cambie.
- **`issue`**: cada cosa que el sistema no puede interpretar o que contradice otra: valor ilegible (`814,8`), color fuera de la lista, fila sin cliente reconocido, alias desconocido, oportunidad de funding duplicada entre el bloque AWS y la planilla de fundings (R28), diferencia entre la fila 23 y la 27 de MEP, diferencia de color entre Pagos y Pagos ARG (F-04, aceptada), celda con cotización tipeada a mano (R38). Cada problema tiene tipo, origen exacto, estado (abierto, en revisión, resuelto, ignorado con motivo) y dueño. **"Lo frenado tiene dueño" arranca acá, con los problemas de datos, antes que con los deals.**
- **`system_event`**: bitácora de lo que hizo el sistema (lecturas, interpretaciones, errores) y de lo que hizo cada persona desde Claude Desktop o la línea de comandos (resolvió un problema, anotó un hecho, asoció un editor, disparó una lectura).

### 3.6 Identidad de fila: cómo una factura sigue siendo la misma si insertan una fila arriba

La API de Google Sheets no da identificadores estables de fila, y el Anexo del documento base dice que los bloques de Pagos ARG se ubican por número de fila. Propuesta:

1. Cada pestaña de CARGA tiene definida su **columna clave** (el nombre del cliente en VENTAS, Pagos y Pagos ARG; la empresa en FUNDINGS) y sus **bloques** (encabezados como "FUNDINGS SHEET Proyectados", "TOTAL PAGOS ARG", "Funding de AWS confirmados").
2. Entre dos versiones, las filas se **alinean por clave normalizada dentro del bloque** (pasando por la tabla de aliases), no por número. Una fila que aparece con clave nueva es "fila insertada"; una clave que desaparece es "fila borrada"; una fila que cambia de número pero conserva clave y contenido es "fila movida", sin cambios de negocio.
3. Si la alineación es ambigua (dos filas con la misma clave en el mismo bloque, o una clave que cambia de texto y de posición a la vez), el sistema **no adivina**: genera un problema y deja las facturas de esas filas marcadas como "identidad en revisión".
4. La regla R26 ("para ver dos contratos separados se usan dos filas") se respeta: dos filas con el mismo cliente en el mismo bloque son dos series de facturas, y se distinguen por un sufijo de orden que el sistema mantiene mientras la posición relativa no cambie; si cambia, problema.

### 3.7 Vistas derivadas y paridad

- **P&L** y **cashflow** se calculan como vistas SQL sobre la capa interpretada, con la versión del conjunto de reglas que usan.
- **`parity_check`**: para cada celda del "P&L Craftech" mensual y del "Resumen mensual Cash Flow ARG-USA" (las vistas que Ariel aceptó como criterio), el valor que da el sistema, el valor que tiene la planilla en el último snapshot y la diferencia. Se recalcula con cada lectura. La paridad se mide, no se declara.
- Las cosas que hoy se hacen distinto de lo ideal (el P&L sin cargas sociales, "Gastos Devs" y "Gastos DATA" leyendo el mismo rango si Emi confirma que es un error) se replican igual y quedan listadas en la sección de mejoras, como pide el documento base (8.1).

### 3.8 Escenarios (después de la paridad)

Toda tabla de hechos y de vistas lleva una columna `scenario_id`; el real es el escenario `0`. Una simulación crea un escenario que **copia al escribir** los hechos que modifica y hereda el resto. Nada escribe sobre el escenario `0` salvo la ingesta y las correcciones con autor y motivo. Así las simulaciones nunca tocan los datos reales, como pide el KICKOFF.

### 3.9 Catálogo semántico (para el servidor MCP)

Una descripción en español de cada tabla, columna y vista, con el término del glosario de Craftech que le corresponde ("Ventas / Booking = ingreso devengado = `Accrual`"), ejemplos de preguntas y las reglas que aplican. El servidor MCP lo expone como recurso y en la descripción de cada herramienta; es lo que Claude Desktop lee antes de armar una consulta. Vive en el repo y en la base, y se actualiza con cada migración.

---

## 4. Cómo resuelvo la v0

### 4.1 Importación inicial

1. Alta de las 20 planillas que la service account ya lee (las 10 del KICKOFF, "FUNDINGS - Log de status [OFICIAL]", "Costos", "Costos - Escenario 1", "Budget por Area 2026 - Final" y los siete P&L por unidad de negocio) con la clasificación de pestañas del anexo A.
2. Lectura completa de **todas** las pestañas, incluidas las ocultas y las históricas, con valores, fórmulas, formato efectivo y celdas combinadas. Primer snapshot de cada una. Las pestañas se leen de a una, con el rango usado real (la API devuelve solo filas con contenido; las "1.000 filas" vacías no pesan).
3. Interpretación de las pestañas de CARGA que tengan reglas ratificadas (sección 3.3) y generación de los primeros problemas.
4. Carga de la tabla de aliases desde las decisiones del artefacto.

Volumen estimado: 342 pestañas, del orden de 1 a 2 millones de celdas con contenido. Entra sin problema en PostgreSQL local.

### 4.2 Toda la historia

Ariel aceptó la distinción: **historia de valores** completa, **historia de cambios** hasta donde Google permita.

- **Historia de valores:** las pestañas por año 2021–2024 de las dos planillas de facturación, "Historia" (foto diaria de totales desde el 2/1/2025), "Base facturacion" de Base informe (semilla histórica según el documento base), "Historico Cash Flow" (37.821 filas) y los `listado-*` históricos. Se importan una vez como HISTÓRICAS, con su propio esquema por año, y se interpretan como hechos con marca "histórico".
- **Historia de cambios anterior al arranque:** depende del acceso al historial de versiones de Google (sección 4.4). Si se consigue, cada revisión disponible se exporta a formato Excel (que conserva valores y colores), se guarda como snapshot con la fecha de la revisión y se le calculan diferencias igual que a una lectura normal. Google compacta revisiones viejas, así que la cobertura real se sabe recién al listar. Si no se consigue, la historia de cambios empieza el día que arranca la ingesta, y se dice así.

### 4.3 Lectura continua y detección de cambios

1. **Cada 5 minutos**, para cada planilla: `files.get` de Drive con `supportsAllDrives=true` pidiendo solo `version` y `modifiedTime`. Es una llamada liviana; 20 planillas × 12 veces por hora está muy por debajo de las cuotas de Google (300 lecturas por minuto por proyecto en Sheets).
2. Si el número de versión cambió, se espera un período corto de calma (2 minutos sin nuevas modificaciones, con tope de 10) para no leer a mitad de una carga, y se hace la **lectura completa** de las pestañas CARGA y DERIVADA de esa planilla. Las HISTÓRICAS e IGNORAR no se vuelven a leer salvo que Ariel lo pida.
3. Cada pestaña leída se compara con su último snapshot: si el hash es igual, no se guarda nada; si cambió, se guarda el snapshot y se calcula `cell_change` (sección 3.2), con alineación de filas (sección 3.6).
4. Se reinterpretan solo las filas afectadas; se abren o cierran problemas.
5. Un botón "leer ahora" en la web, para cuando Ariel quiera ver algo sin esperar.

Qué detecta, con ejemplos del documento base: un monto nuevo (valor), una celda que cambia de color (estado de factura), una fila que se borra (alineación), una fórmula pisada a mano (la celda pasa de fórmula a valor o de referenciar la fila 27 a tener un número tipeado: eso además dispara la regla R38), una celda vaciada (R30), una pestaña nueva o renombrada, un color que no está en la lista (problema).

### 4.4 Quién y cuándo: lo que Google expone y lo que se decidió

Verificado el 18-oct con la service account, con permiso de **Lector** en las unidades compartidas, antes y después de que Ariel habilitara la Drive Activity API (decisión 2):

- **Drive Activity API: funciona con Lector.** Para "FUNDINGS - Log de status [OFICIAL]" devuelve 1.141 eventos, el más viejo del 16 de marzo de 2026: cada edición con marca de tiempo exacta y quién la hizo, a nivel archivo (no a nivel celda). Con esto, para cada cambio de celda detectado entre dos lecturas se tiene la lista de personas que editaron esa planilla en el intervalo y la hora de cada edición. Si hubo una sola, la atribución es cierta y **la fecha del cambio es la de su edición** (resuelve "se pintó el viernes, se leyó el lunes"). Si hubo varias, se registra "una de: X, Y" y la ventana. Además se importa toda la actividad disponible hacia atrás, así "quién tocó qué planilla y cuándo" existe desde marzo aunque la historia de celdas empiece hoy.
- **Los editores vienen como identificadores de perfil de Google, no como nombres.** Resolverlos a nombre requiere la People API, que no está habilitada, y aun habilitándola una service account normalmente no puede leer el directorio de otros usuarios sin permisos que no queremos darle. Solución simple: una tabla `editor_profile` que asocia cada identificador a una persona, que Ariel llena una vez (en la planilla de fundings aparecen 12 editores distintos en siete meses, contados en la importación del 18-oct) desde Claude Desktop, con una herramienta del servidor MCP: el sistema le muestra las ediciones de cada editor sin identificar (qué planillas, qué horarios) y él dice quién es. Un identificador sin asociar se muestra como "editor sin identificar #3", nunca inventado.
- **Historial de versiones (el contenido de las versiones anteriores): Lector no alcanza.** `canReadRevisions` es `false` y la lista de revisiones vuelve vacía. Decisión 3 (18-oct): **empezar hoy**; la importación antigua de cambios se ve más adelante.
- **Nada se instala en las planillas.** Ariel descartó cualquier script dentro de Google (decisión 4): nada de autoría por celda vía Apps Script, nunca. Lo que no se puede atribuir por celda se muestra como conjunto y ventana.

**Decisión 3, explicada y tomada.** Lo que ya tenemos sin hacer nada más: quién editó cada planilla y cuándo, desde marzo de 2026, y la historia de **celdas** desde el día que arranque la ingesta. Lo que agregaría el historial de versiones: el contenido de las versiones anteriores a ese día, para calcular diferencias celda a celda **hacia atrás** (con la cobertura parcial que Google conserve, porque compacta versiones viejas). Los caminos, con el elegido primero:

| Camino | Qué da | Qué cuesta |
|---|---|---|
| **Empezar hoy** (elegido por Ariel el 18-oct) | Historia de celdas desde el arranque; actividad de Drive desde marzo. Cero pasos extra. Si en unos meses se extraña la historia anterior, se puede pasar al camino B en ese momento: Google sigue guardando las versiones. El modelo de datos ya lo permite: un snapshot puede tener fecha anterior al arranque y origen "revisión de Google". | Nada. |
| **B. Subir la service account a Colaborador** en las dos unidades compartidas | Habilita leer y exportar las versiones anteriores. Un click de Ariel, reversible. | Ser honesto: el permiso le **permitiría escribir**; lo único que lo impide es que el código pide tokens de solo lectura. Es una barrera de software, no de permisos. |
| **C. Exportación única con la cuenta de Ariel** | Lo mismo que B, una sola vez. | Ariel corre un script con su propio login desde su navegador; yo no lo puedo correr por él. Un paso manual, y hay que repetirlo si se quiere actualizar. |

Lo que la web muestra siempre, con cualquier camino: hora de detección, ventana posible, y la atribución con su grado de certeza. Nunca un "quién" inventado.

### 4.5 Qué se reporta en vez de adivinar

Todo lo listado en 3.5 como `issue`, más las contradicciones entre planillas que ya conocemos: la pestaña "Pagos confirmados" de la planilla de fundings contra la fila "TOTAL PAGOS AWS" de Pagos (Ariel ya dijo que la planilla de fundings tiene la verdad: la diferencia se muestra, no se corrige), y las razones sociales que facturan en Zoho sin fila en las planillas (Endow, TP Professional Services Corp).

### 4.6 Cómo lo ve Ariel en la v0

Dos lugares: la **web local** para mirar y **Claude Desktop** para preguntar y para las pocas acciones humanas.

La web, sin login (solo Ariel, como respondió) y **solo visualización** (decisión 1), con cuatro pantallas:

1. **Cambios:** lista cronológica filtrable por planilla, pestaña, cliente, tipo de cambio, persona y fecha. Cada fila abre el detalle: celda, valor y color anterior y nuevo, fórmula, hora de detección, ventana, atribución. Resumen por día.
2. **Problemas:** lo ilegible y las contradicciones, con origen exacto, estado y dueño.
3. **Fuentes:** las 20 planillas, sus pestañas, la clasificación (viene de `config/sources.yaml`), la última lectura, el botón "leer ahora" (la única acción de la web; no escribe datos, dispara una lectura).
4. **Clientes y aliases:** la tabla canónica con sus razones sociales y variantes, con las decisiones del artefacto ya cargadas.

Claude Desktop, conectado al servidor MCP: todas las consultas (con referencia de origen en cada número) y tres acciones con autor y motivo: resolver o ignorar un problema, anotar un hecho, asociar un editor de Google a una persona. Así hay una sola superficie de escritura humana y la web no necesita formularios.

A partir de la semana 3 se suman a la web **Facturas y cobros** y **Fundings**, y al servidor MCP las herramientas sobre ingresos.

---

## 5. Cómo se va a ver y usar: el día uno de cada persona

| Persona | En la v0 (local) | Con la versión hosteada |
|---|---|---|
| **Ariel** | Abre la web local; ve qué cambió ayer en las planillas y quién; revisa problemas. Desde Claude Desktop (semana 3 en adelante) pregunta "¿qué facturas de septiembre siguen sin cobrar y desde cuándo?" y recibe la respuesta con la celda de origen; desde ahí mismo resuelve problemas y asocia editores. | Lo mismo desde cualquier lado, más alertas en Slack y escenarios. |
| **Emi** | No usa el sistema. Sigue cargando en sus planillas como siempre. Recibe de Ariel preguntas puntuales que salen de los problemas detectados. | Ve el tablero de paridad (su P&L contra el del sistema, celda por celda), conecta su Claude Desktop al servidor hosteado, resuelve problemas de datos, declara cierres (R18), anota contexto sobre facturas. |
| **Ro** | No usa el sistema. Sigue cargando VENTAS, Pagos y el tracker de fundings. | Ve sus cambios registrados, pregunta desde su Claude Desktop, resuelve problemas de fundings (duplicados, claim due dates), después maneja el checklist Committed → Launched. |
| **Sofi** | No usa el sistema. | Resuelve problemas de bancos y conciliación; carga de extractos. |
| **Líderes de área** | — | Flujo de budget (2027). |

---

## 6. Etapas y entregables

Hoy es 18 de octubre; a fin de año quedan diez semanas. Lo que sigue es lo que creo realista. Lo que el KICKOFF llama "el proyecto ambicioso completo" no entra en diez semanas, y prefiero decirlo ahora.

| Etapa | Semanas | Entregable | Qué necesita |
|---|---|---|---|
| **A. Espejo** | 1–2 (hasta ~1 nov) | Repo, Docker Compose (PostgreSQL, worker, api+web, mcp). Importación inicial de las 20 planillas con historia de valores. Lectura continua por versión. Registro de cambios celda a celda con colores y filas borradas, con quién y cuándo desde la actividad de Drive (importada hacia atrás hasta marzo de 2026). Problemas básicos (ilegibles, colores desconocidos). Pantallas Cambios, Problemas, Fuentes. Servidor MCP mínimo (cambios, problemas, fuentes, asociar editores). | Nada más que lo que ya hay. |
| **B. Ingresos y primer servidor MCP completo** | 3–4 (hasta ~15 nov) | Interpretación de ingresos: devengados, facturas con estado por color, cobros, bajas de SleakOps, fundings (bloque AWS y planilla de fundings), clientes canónicos con aliases y razones sociales múltiples. Pantallas Facturas y cobros, Fundings, Clientes. **Servidor MCP v1** sobre todo lo interpretado, con consulta libre sobre vistas y referencias de origen, usado desde Claude Desktop. **Acá es cuando "ya sirve".** | Confirmación de Emi al refinamiento de la regla R32 (no bloquea: se modela 1:n igual). |
| **C. Gastos, sueldos, budget y paridad** | 5–8 (hasta ~13 dic) | Movimientos bancarios y gastos, cuentas de ajuste, costo laboral y pagos de nómina, budget. P&L y cashflow regenerados con las reglas ratificadas. **Tablero de paridad** celda por celda contra "P&L Craftech" y "Resumen mensual Cash Flow ARG-USA". Servidor MCP sobre todo. Catálogo semántico completo. | Respuestas de Finanzas a F-01, F-07, F-08, F-10, F-14. Sin ellas, la paridad cubre lo que tenga regla y lista el resto como "sin regla". |
| **D. Hosting y Finanzas adentro** | 9–10 + enero | Despliegue en AWS (misma imagen), login, Emi y Ro con acceso a la web y con su Claude Desktop conectado al servidor MCP por HTTP con autenticación, resumen diario en Slack, alertas (pago atrasado, claim due date), cierre de paridad trabajando con Emi, rotación de la clave de la service account. | Decisión de Ariel sobre la nube cuando lo local esté perfecto. |
| **E. Sacarle trabajo a las planillas** | 2027, primer trimestre | API de Mercury (R35, R36; decisión 7), checklist Committed → Launched con HubSpot (R19, workflow 7), vendedor por contrato desde HubSpot y comisiones (R21), flujo de budget (workflow 7), HubSpot Invoices, escenarios, enriquecimiento para todos, primer tipo de dato que pasa a vivir en el sistema (ventas y contratos). Si la web necesita edición y flujos, acá se decide si pasa a una aplicación rica (React) sobre la API JSON ya existente. | Paridad cerrada; integraciones de HubSpot. |

Al 31 de diciembre: A, B y C terminadas y D empezada. Es "estar por encima de las finanzas de la empresa de forma adecuada", que es lo que el KICKOFF pide para los primeros tiempos.

---

## 7. Las cinco preguntas de Ariel y cómo se responden

| Pregunta | Fuente de la respuesta | Etapa | Observación |
|---|---|---|---|
| "¿Cuál es el costo proyectado de la fiesta de fin de año?" | Budget (línea del área que la presupuesta) y Base informe › Consolidado, rubro "25. Evento Fin de año" (192 movimientos históricos, verificado). | C | Responde proyectado y real por año, con la celda de origen. |
| "¿Los pagos por contrato que debemos hacerle a Grego AI ya están en el cashflow proyectado?" | CASH FLOW MENSUAL › "Cash Flow - c/ pagos proyectados"; VENTAS y FUNDINGS para el contexto del deal. | C | Grego es además el caso de referencia del funding por consumo (R12, R24). |
| "¿Cuánto está proyectado de ganancia para el pago de impuestos al IRS?" | Hoy no hay regla. Base informe tiene pestañas "Tax EEUU 20xx" y "Tax EEUU 2025 - calculo para budget", que son papeles de trabajo. | Después de C | **Necesita una regla fiscal de Finanzas.** No la invento. Se agrega como pregunta F-26 para Emi. |
| "¿Entró el pago de funding al banco Mercury de X proyecto?" | Hoy: Base informe › Mercury (carga manual) cruzado con la planilla de fundings. Bien resuelto: **API de Mercury** (R35, R36: payment number → Partner Central → claims). | Parcial en C; completa en E (2027) | Hasta la etapa E se responde desde la carga manual de Base informe › Mercury, diciendo que es carga manual y de qué fecha. La API de Mercury queda para más adelante (decisión 7). |
| "¿Está pronosticado el pago de sponsoreo del evento de Quick con Beto Ortega para noviembre?" | Budget (línea de Marketing) y "Cash Flow - c/ pagos proyectados". | C | Responde con la línea y el mes, o "no está". |

---

## 8. Trazabilidad: reglas R1 a R39

Cada regla del documento base, dicha en una frase, y dónde la cumple la propuesta o por qué queda fuera de la primera etapa.

| Regla | Qué dice | Dónde se cumple |
|---|---|---|
| R1 | Devengado mensual por contrato, prorrateado por días calendario en el mes de inicio y fin. | Hecho `Accrual` (3.3), etapa B. El prorrateo se valida contra VENTAS; el sistema no recalcula, lee. |
| R2 | Horas por encima de lo reservado: facturables si el cliente autorizó; si no, se miden como pérdida. | Fuera de la primera etapa: no hay fuente de horas en las planillas. El modelo deja lugar (`OvertimeDetected`) para cuando se integre Jira. |
| R3 | Facturación un mes después del devengado; vencimientos: upfront al enviar, resto a 10 días, algunos a 30. | Plazo de pago en `client_legal_entity`, tomado de Zoho (sesión de aliases); vencimiento calculado en `Invoice`. Alertas de vencimiento en etapa D. |
| R4 | Cobro = fecha en que Emi pinta el verde; mientras se lea la planilla, la fecha de detección; con Mercury, la fecha real del banco. | `Payment` con fecha de detección, ventana y, con Drive Activity API, la fecha de la edición (4.4). Mercury en etapa D. |
| R5 | Cargas sociales solo para nómina argentina o híbrida; no van al P&L (como hoy); al cashflow cuando se pagan. | `SocialChargesPaid` desde Base informe › CCSS, solo en cashflow. Etapa C. Reconocerlas en el P&L queda en mejoras. |
| R6 | Sueldos pagados en USD: factor 1,0 aunque la persona esté en Argentina. | Regla de `PayrollAccrual`, etapa C. |
| R7 | Sueldo = base de categoría × % de banda. | `position` con banda y porcentaje, etapa C (lectura de Proyección sueldos). |
| R8 | Cambio de área o seniority aplica desde el mes de la decisión. | Vigencia en `position`, etapa C. |
| R9 | Cashflow ARG: traer USD para cerrar el mes con 4M ARS. | Parámetro del cashflow proyectado, etapa C. |
| R10 | Cotización pactada por contrato ARG; valores en Pagos ARG filas 23–27; el sistema lee la fila que referencia la fórmula; MEP es la operativa. | `FxRate` y `Invoice` (3.3). Verificado: la operativa es la fila 27. La fila 1 "Dólar oficial" que usan las fórmulas de ARS sigue abierta (F-01): hasta la respuesta, la factura guarda la cotización que su fórmula referencia y se marca "tipo a confirmar". |
| R11 | Intercompany por rubro "CAJA. Intercompany"; el cliente 000004 de Bejerman excluido del revenue. | `Transfer.type=INTERCOMPANY` desde Base informe (rubro verificado, 18 movimientos). Etapa C. |
| R12 | Saldo tracker contra Partner Central = 0, con excepciones documentadas. | Fuera de la primera etapa: Partner Central no se lee todavía. Las excepciones se cargan como anotaciones sobre el programa (caso Grego). |
| R13 | Herramientas compartidas se prorratean por área. | Replica lo que hace Base informe por área; etapa C. |
| R14 | Ventas netas de IVA; facturas ARG brutas; IVA 21%; neto = bruto / 1,21. | `Invoice` en ARS guarda bruto, neto e IVA. Etapa B. |
| R15 | Funding separado en la base; en vistas, total mezclado más "de los cuales AWS". | `FundingMilestone` es un hecho distinto de `Invoice`; las vistas lo suman con una línea aparte. Etapa B y C. |
| R16 | Marketplace de Craftech como factura más del cliente; Marketplace de SleakOps en su planilla. | Lectura de las dos planillas de facturación, etapa B. |
| R17 | Gastos ARG y USA unificados como gasto o línea de budget con entidad legal. | `Expense` y `BudgetLine` con `legal_entity`. Etapa C. |
| R18 | Cierre: foto al último día hábil; lo del primer día hábil integra el cierre; después, correcciones con autor y motivo; Emi puede declarar cierre. | Snapshots con fecha permiten reconstruir la foto; "cierre declarado" como evento en la versión hosteada (etapa D). |
| R19 | Committed dispara lo operativo; Launched con proyecto arrancado, funding en cash claim, contrato firmado y upfront pagado. | Etapa E (HubSpot). El modelo tiene `contract.status`. |
| R20 | Headcount para materiales de AWS: 33 FTE. | Parámetro de reporte, etapa C. |
| R21 | Comisiones por vendedor y trimestre sobre lo devengado, funding incluido; porcentajes y personas son parámetros. | Etapa E: el vendedor viene de HubSpot (respuesta F-13). |
| R22 | Cobro del funding: sign-off estimado + 30 días; por consumo, el mes del umbral + 30 días. | `FundingMilestone` con fechas estimadas, etapa B. |
| R23 | Todo contrato en USD; facturas ARG en ARS brutas a la cotización pactada. | `contract` en USD; `Invoice` en ARS con cotización. Etapa B. |
| R24 | Funding: en el P&L oficial entra completo en el mes del derecho a cobro; en la vista de gestión se asigna a los meses trabajados; la reasignación es manual con motivo. | `FundingAccrued` (oficial) y `FundingAllocated` (gestión, editable con anotación). Etapa C. |
| R25 | Factura en Pagos ARG → Craftech S.A.; resto → Craftech-io Inc. | Regla de `Invoice`, etapa B. Aceptado además (F-04) que Pagos ARG manda sobre el estado y que una diferencia de color con Pagos se reporta. |
| R26 | Identidad de la factura = fila de cliente + mes + entidad legal; dos contratos = dos filas. | Clave de `Invoice` e identidad de fila (3.6). Etapa B. |
| R27 | Identidad del hito = fund claim ID; la claim due date es alerta; MAP 2.0 Mobilize puede tener varios hitos. | `FundingMilestone` con `claim_id` (vacío hasta que Ro cargue la columna; mientras, clave provisoria por programa + orden, marcada). Alerta en etapa D. |
| R28 | Funding: bloque AWS de Pagos hasta el 24/2/2026; planilla de fundings desde el 25/2/2026; duplicados se reportan. | Corte por fecha en la lectura; duplicado = problema. Etapa B. |
| R29 | Cinco colores de estado; con monto y sin color = a facturar; mapeo único y global. | Tabla de colores → estado; color desconocido = problema (F-05 aceptada). Etapa A (detección) y B (estado). |
| R30 | Vaciar la celda = el dato deja de existir; cambio de color = cambio de estado; lo ilegible se reporta. | `cell_change` tipo "vaciada" cierra la factura; ilegible = problema. Para un 0 con color o un magenta sin monto, Ariel respondió "misma regla que al vaciar": se trata como inexistente y se registra el cambio. Etapa A y B. |
| R31 | Celda pintada sin monto en la planilla de SleakOps = baja del cliente. | `ClientChurned`, etapa B. El color exacto de la marca sigue en F-05; hasta tenerlo, cualquier color sin monto en esa planilla se trata como baja y se marca. |
| R32 | Cliente canónico = razón social legal; nombre de fantasía = nombre visible y alias. | `client`, `client_legal_entity`, `client_alias` (3.4), con el refinamiento de varias razones sociales por cliente. Etapa B. |
| R33 | SAC entero en el P&L en el mes en que se paga, sumado al sueldo. | Regla de `PayrollAccrual`, etapa C. |
| R34 | Cuentas AFIP y CLIENTES de Base informe son ajustes impositivos que el P&L replica. | `adjustment_account`; la fórmula exacta está abierta (F-10): hasta la respuesta se replica lo que la planilla muestra. Etapa C. |
| R35 | Cuentas bancarias; Mercury → Mesh es transferencia interna; bancos ARG por archivo; Mercury por API. | `bank_account` y `BankMovement` desde Base informe en etapa C; Mercury por API y carga de extractos en etapa D. |
| R36 | Pagos de AWS con varias POCs: payment number de Mercury → Partner Central → N claims. | Etapa D (Mercury) y E (Partner Central). |
| R37 | "Ventas Argentina 2025" no se ingiere aparte. | Pestaña clasificada IGNORAR para interpretación (anexo A). |
| R38 | Cotización tipeada a mano en una celda de conversión: se guarda como cotización de esa factura y se marca para revisión. | Detección de "fórmula pisada" (4.3) + problema. Etapa A y B. |
| R39 | Bono semestral en USD a contractors, sin cargas, en el P&L en el mes de pago; fuente para separarlo: Base informe › Bonos. | Regla de `PayrollAccrual`, etapa C. |

---

## 9. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| **La paridad no cierra y nadie confía.** | Tablero celda por celda desde la etapa C, no al final. Lo que no coincide se explica o se convierte en pregunta. Replicar lo que hoy se hace, aunque parezca error, hasta que Emi diga. |
| **Google no da el historial de versiones con el permiso actual.** | La actividad de Drive ya está (quién y cuándo, desde marzo de 2026). La historia de celdas anterior al arranque quedó para más adelante (decisión 3). El sistema registra todos los cambios desde el arranque y lo dice así en la web; el modelo admite importar revisiones viejas después. |
| **Filas insertadas, borradas o movidas rompen la identidad de las facturas.** | Alineación por clave y bloque (3.6); ambigüedad = problema, no adivinanza. El Anexo del documento base ya pide a Finanzas no mover los bloques. |
| **Varias personas editan en el mismo intervalo y la atribución es ambigua.** | Se registra el conjunto y la ventana. Afinar por celda exigiría un script dentro de las planillas, y eso está descartado (decisión 4): se acepta la ambigüedad y se muestra como tal. Con lecturas cada 5 minutos los intervalos son cortos y la mayoría de los cambios tiene un solo editor. |
| **Pestañas enormes y lecturas lentas.** | Lectura por pestaña con el rango usado; hash para no guardar lo que no cambió; CARGA y DERIVADA continuas, el resto una vez. "CASH FLOW USA" (62 × 1.545) y los `data-*` de 14.000 filas se miden en la etapa A y se ajusta la frecuencia por planilla si hace falta. |
| **Cuotas de la API de Google.** | Lectura por versión (una llamada liviana por planilla cada 5 minutos) y lectura completa solo cuando cambió. Reintentos con espera creciente. |
| **El cashflow no es 100% regenerable (tiene celdas manuales y escenarios).** | La paridad se mide sobre el "Resumen mensual"; las celdas manuales se importan como datos con origen y se listan como tales. Lo que es escenario se clasifica como tal (anexo A) y queda fuera del real. |
| **Las razones sociales y plazos de pago de Zoho desaparecen cuando se apague.** | Ya están extraídos del backup del 17-oct y cargados como decisiones de aliases. Se importan a `client_legal_entity` en la etapa B. |
| **Datos personales (sueldos) en una base que después ve más gente.** | En la v0 solo Ariel. En la versión hosteada, seguridad por filas en PostgreSQL por área de datos antes de que entre nadie más. |
| **La clave de la service account estuvo dos meses en Descargas.** | Ya está en `~/.config/craftech-os/secrets/` con permisos restringidos; se rota (clave nueva, borrar la del 23 de agosto) cuando Docker esté andando, y en AWS pasa a Secrets Manager. |
| **Alcance que crece.** | Las etapas tienen entregables cerrados; lo nuevo entra en la etapa E o después. |
| **Bus factor.** | Stack mínimo y conocido (Python, PostgreSQL, Docker; sin Node), SQL legible, catálogo semántico en español, documentación en el repo. Nada mágico. |
| **Dependencia de Google el día que se apague.** | Todo lo leído vive en PostgreSQL (versiones enteras, cambios, actividad). Nada instalado en Google (decisión 4). Apagar Google Sheets deja el sistema completo y congelado en la última lectura. |
| **La laptop apagada corre las lecturas.** | Aceptado por Ariel durante la v0; fecha de edición desde la actividad de Drive cuando se pueda; en la etapa D corre siempre prendido. |

---

## 10. Reglas abiertas que no se implementan hasta tener respuesta

Ninguna frena las etapas A y B. Todas afectan la paridad (etapa C).

| Pregunta | Para quién | Qué hace el sistema mientras tanto |
|---|---|---|
| F-01: si el "Dólar oficial" de la fila 1 es la cotización pactada de los clientes de Craftech S.A. | Emi | Guarda la cotización que referencia cada fórmula y marca el tipo como "a confirmar". |
| F-07: si "Gastos Devs" y "Gastos DATA" leyendo el mismo rango es un error (verificado: no existe `total_devs`). | Emi | Replica lo que hace la planilla y lo lista en mejoras. |
| F-08: si "Costos" es la fuente oficial del costo laboral y qué relación tiene con Base sueldos › sueldos-percibidos. (La respuesta registrada fue "de acuerdo con la propuesta", pero esa pregunta no tenía propuesta: sigue abierta.) | Emi | Para la paridad lee "Costos" › sueldos porque es lo que el P&L lee hoy; no decide cuál es la fuente oficial. |
| F-10: fórmula exacta de los ajustes AFIP y CLIENTES. | Sofi, Emi | Replica los valores de la planilla sin recalcularlos. |
| F-14: cuál es el budget viejo y cuál el nuevo ("Budget" y "Budget por Area 2026 - Final" son candidatos). | Emi, Sofi | Importa los dos; ninguno alimenta el P&L regenerado hasta saberlo. |
| F-26 (nueva): regla para proyectar la ganancia imponible de Craftech-io Inc para el IRS. | Emi | El chat responde que no hay regla. |
| Visma: Ariel la vinculó a "PRISMA HOLDING INC", que es Prisma Retail (cliente 2023–2024). | Ariel, Emi | Visma queda sin razón social. |
| Las demás de la Etapa 2 sin responder (dos filas "FUNDINGS SHEET", SleakOps por la S.A., datos sueltos de Broota, valor ilegible y totales, pestaña "Historia", objetivos de venta, "Pagos en disputa", escenarios del Cash Flow). | Emi, Ro | Se importan como datos; no se interpreta nada que dependa de la respuesta. |

---

## 11. Decisiones de Ariel (18 de octubre de 2026)

| # | Decisión | Respuesta de Ariel | Qué cambió en la propuesta |
|---|---|---|---|
| 1 | Tecnologías | "Decidí vos, pero sistemas simples, fáciles de mantener, sin sobrecomplicaciones. El chat tiene que ser desde Claude Desktop, exponiendo un MCP o algo así. La app sería para visualización solamente y la base de datos." | Chat embebido con la API de Claude → **servidor MCP consumido desde Claude Desktop**. Web React → **plantillas servidas por FastAPI, solo visualización**. Tres procesos de un solo paquete Python, una imagen. Las pocas acciones humanas (resolver problema, anotar, asociar editor) van por el servidor MCP. |
| 2 | Drive Activity API | "Ya la habilité." | Verificada el mismo día con permiso de Lector: funciona, con actividad desde marzo de 2026. Entra en la etapa A, con importación hacia atrás. Falta que Ariel asocie los identificadores de editor a personas (8 en la planilla de fundings). |
| 3 | Historial de versiones | Primero "No entendí, explicalo mejor"; con la explicación: "Empecemos hoy y más adelante vemos lo de la ingesta antigua de cambios." | La historia de celdas empieza el día del arranque. La actividad de Drive (quién y cuándo) se importa desde marzo de 2026. El modelo deja lugar para importar revisiones viejas si algún día se decide (sección 4.4). |
| 4 | Script en las planillas | "Todo de nuestro lado; nada de scripts de Google Docs, así el día que deshabilitemos Google no queda atado a nada." | Opción eliminada. Restricción dura: **nunca modificar las planillas, ni con scripts**. Riesgo nuevo en la sección 9 sobre apagar Google. |
| 5 | Cliente con varias razones sociales (refinamiento de R32) | "Lo terminamos de revisar con Emi; no bloquea nada ahora." | Se modela 1:n desde la etapa B; marcado como provisorio hasta la confirmación de Emi. |
| 6 | Etapas | "De acuerdo al orden." | Sin cambios de orden; A, B y C al 31 de diciembre, D empezada. |
| 7 | Mercury | "Para más adelante la API." | API de Mercury pasa de la etapa D a la E (2027). Hasta entonces se responde desde la carga manual de Base informe › Mercury, dicho como tal. |
| 8 | Frecuencia | "Sí." | Chequeo de versión cada 5 minutos, lectura completa solo si cambió. |
| 9 | Planilla del dólar MEP | "Sí." (no compartirla) | Se leen los valores que llegan a Base informe › TC MEP. La planilla origen queda fuera. |
| 10 | Repo | "Todo acá." | Un solo repo: `docs/`, `app/`, `config/`, `infra/`. |

Con las diez contestadas, la propuesta queda aprobada el 18 de octubre de 2026. Lo que sigue no es código: es la revisión de arquitectura y los PRDs con tickets en `plan/`, cada uno con el OK de Ariel.

---

## Anexo A — Clasificación inicial de pestañas

Leída el 18-oct con la service account: 20 planillas, 342 pestañas. Clases: **CARGA** (se lee continuo, se registran cambios y se alertan), **DERIVADA** (se lee continuo para paridad, cambios sin alerta), **HISTÓRICA** (se importa una vez), **IGNORAR** (se importa una vez, no se interpreta). "A confirmar" = necesito que Finanzas diga qué es. La clasificación vive en `config/sources.yaml` y se cambia como código; esta es la propuesta de arranque.

**Facturación - Craftech Total (47 pestañas)**
- CARGA: Pagos, Pagos ARG, VENTAS, PROYECCION VENTAS, PROYECCION PAGOS USA (2025-2026).
- DERIVADA: listado-ventas, listado-ventas-2025, listado-ventas-proyectadas, listado-ventas-proyectadas-2025-2026, data-ventas-2025, data-pagos-2025, data-proyeccion-sales-2025, Ventas IA, Ventas Data, Ventas DevOps, Q-Ventas, M-Ventas, 3M-Ventas, InterM-Ventas.
- HISTÓRICA: Pagos USA (2021, 2022, 2023, 2024), Pagos ARG 2021, Pagos ARG (2022, 2023, 2024), VENTAS USA 2023, VENTAS USA 2024, Ventas ARG (2024), Pagos AWS (2023), Pagos USA Sleakops (2023, 2024), Proyeccion Sales USA (2024, 2025), listado-ventas-2023, listado-ventas-2024, listado-proyeccion sales USA-2024, Ventas con CEI, listado-ventas-CEI, Historia.
- IGNORAR: Ventas ARG (2025) (regla R37: Ro ya la vuelca en VENTAS), recalc, JDJDKDKDKDKD, Copia de VENTAS USA 2025 COMPARATIVO, Hubspot Corrección NO USAR VENTAS USA 2025.
- A confirmar: Gastos.

**Facturación - SleakOps Total (34 pestañas)**
- CARGA: Pagos, Pagos ARG, VENTAS, PROYECCION PAGOS, PROYECCION VENTAS.
- DERIVADA: listado-ventas, listado-ventas-actual, listado-ventas proyectadas-actual, listado-ventas-proyectadas, listado-pagos, listado-ingresos, listado-ventas-aws, listado-ventas-aws-2025, listado-pagos-suscripciones, listado-pagos-suscripciones-2025, listado-pagos-onboarding, listado-pagos-onboarding-2025.
- HISTÓRICA: Pago USA 2023, VENTAS 2023, Listado-ventas-2023, Pagos USA 2024 - SleakOps, Ventas USA 2024 - SleakOps, Pago USA 2024 - Suscripciones, Pagos USA 2024 - Onboarding, Ventas 2024 - AWS, Pagos ARG 2024 - Suscripciones, listado-pagos-suscripciones-2024, listado-ventas-aws-2024, listado-pagos-onboarding-2024, listado-ventas-2024, Pago USA 2025 - Suscripciones, Pagos USA 2025 - Onboarding, Ventas 2025 - AWS.
- IGNORAR: recalc.

**FUNDINGS - Log de status [OFICIAL] (5 pestañas)**
- CARGA: FUNDINGS.
- DERIVADA: Pagos confirmados (control de paridad; es lo que importa la fila "Funding de AWS confirmados"), DB, SUMA.
- HISTÓRICA: 2025.

**P&L Completo Craftech (11 pestañas)**: todas DERIVADA. "P&L Craftech" es la vista de paridad. Las "esc 1" se marcan como escenario.

**P&L por unidad de negocio (7 planillas: DATA; DEVOPS; GEN AI / DEVs; SleakOps; Completo - U. Negocio IT; DevOps & IT Services; GEN AI - DATA; 73 pestañas)**: todas DERIVADA, baja prioridad: se importan en la etapa A y se usan recién para paridad por unidad de negocio, después de la paridad del P&L completo.

**CASH FLOW MENSUAL (13 pestañas)**
- CARGA: CASH FLOW USA, CASH FLOW ARG, Cash Flow - c/ pagos proyectados, Pagos en disputa, Gastos Budget 2026.
- DERIVADA: Resumen mensual Cash Flow ARG-USA (vista de paridad), Dashboard Historico Cash flow USA, Dashboard Historico Cash flow USA proyectado, Tracking Cashflow.
- HISTÓRICA: Historico Cash Flow, Tracking Cashflow Historico.
- A confirmar: FACTURAS A JUSTIFICAR, Gastos TC.

**Base informe Craftech (42 pestañas)**
- CARGA: Consolidado, Mesh, Mercury, Galicia, Macro, Credicoop, Caja, Ajuste cobros clientes (cuenta CLIENTES), Ajuste Credito Fiscal (cuenta AFIP), Sueldos, Bonos, SAC, Comisiones, control sueldos y ccss, Ingresos Financieros, CIRCUITO TECNOM/YELLAMO, Prestamos, Deuda Planes de pago, Planes AFIP.
- DERIVADA: TC MEP, GASTOS POR AREA, Resumen Gastos, Resumen Ingresos Financieros, Planilla de gastos - control budget, Consolidado Banco ARG, BASE DETALLE.
- HISTÓRICA: Base facturacion, VETA - ARG, VETA - USD, Rendimientos Inversiones - VETA - 2023, USDC, Caja Crypto, Tax EEUU 2021, Tax EEUU 2022, Tax EEUU 2023, Tax EEUU 2024 - Copia de seguridad, Tax EEUU 2025 - Copia de Seguridad.
- A confirmar: Tax EEUU 2025 - calculo para budget (puede ser la base de la pregunta del IRS), Dolar Futuro, Viajes Marketing/Comercial, Sleakops, Sleakops - ajuste.

**Proyeccion sueldos (23 pestañas)**
- CARGA: Base sueldos, Calculo sueldos proyectados, Resumen sueldos proyectados 2025, 2026 y 2027, Sueldos percibidos, Comisiones percibidas, Comisiones devengadas, Nomina, Bandas salariales, Estado de resultados objetivo.
- DERIVADA: Sueldos percibidos Finales, Sueldos devengados, data-sueldos-devengados, data-sueldos-percibidos, data-comisiones-devengadas, data-comisiones-percibidas, data-sueldos+comisiones-percibidas, data-sueldos+comisiones-devengadas, Cantidad de empleados por area, cantidad de nomina.
- HISTÓRICA: Proyecciones sueldos devengados - 2023/2024, Bonos Percibidos Ene 2025 (Dic 2024).

**Base sueldos - historico y actual (6 pestañas)**
- CARGA: sueldos-percibidos, sueldos-percibidos-actual, sueldos-devengados, sueldos-devengados-actual.
- HISTÓRICA: sueldos-percibidos-historico, sueldos-devengados-historico.

**SUELDOS EEUU (10 pestañas)**
- CARGA: Sueldos, Bajas, Comisiones proyectadas.
- DERIVADA: Neto a transferir (papel de trabajo; se lee sin alertas), Monto de cargas que se descuenta, Control de invoices entregadas.
- HISTÓRICA: Sueldos 2024 brutos.
- IGNORAR: Copia de Sueldos, Temporal, Hoja 40.

**Budget (25 pestañas)**
- CARGA: COMERCIAL, MKT, RRHH, IT, SLEAKOPS, DATA, GEN IA, DEVS, GERENCIAL, LEGALES, COMUNES, FINANZAS, CONTABLE, IMPUESTOS, OPERACIONES, ACTIVOS, DEUDA AFIP, Gastos de USA, Dolar - Inflación.
- DERIVADA: Consolidado, data-consolidado, Control sumas budgets, Cantidad de empleados por area.
- IGNORAR: Tabla dinámica 1, cosas rrhh.

**Budget por Area 2026 - Final (21 pestañas)** (candidata a "budget nuevo", pendiente F-14)
- CARGA: Comercial, MKT, RRHH, DevOps, SleakOps, Data, Gen IA, Devs, Gerencial, Legales, Comunes, Finanzas, Contable, Impuestos, Operaciones, Activos, Supuestos Macro, Dolar - Inflación.
- DERIVADA: Consolidado Budget, Control Budget vs Real.
- IGNORAR: Instrucciones.

**Costos (18 pestañas)**
- DERIVADA: sueldos (es lo que lee el P&L; falta saber de dónde se alimenta, pregunta F-08), gastos, costos, costos-craftech, costos-sleakops, ingresos-financieros, data-costos-por-persona-craftech, data-costos-craftech, data-rentabilidad-craftech, data-rentabilidad-sleakops, data-pasivos, data-costos-sleakops, data-gastos+sueldos-craftech, control-gastos-areas.
- A confirmar: Budget IT, nomina-2024, nomina-actual, pasivos.

**Costos - Escenario 1 (14 pestañas)**: todas DERIVADA y marcadas como escenario (no entran al real).

---

## Anexo B — Verificaciones hechas el 18-oct

Con la service account `finance-bot-ingest@prefab-isotope-287618.iam.gserviceaccount.com`, alcances de solo lectura, desde un contenedor Docker en la laptop de Ariel:

- Abre las 20 planillas listadas en el anexo A. Todas están en unidades compartidas: cada llamada a Drive necesita `supportsAllDrives=true` (sin eso, 404).
- `canReadRevisions = false` y lista de revisiones vacía en "Facturación - Craftech Total", "Facturación - SleakOps Total" y "FUNDINGS - Log de status [OFICIAL]".
- Drive Activity API: a la mañana, 403 "no habilitada en el proyecto 906631527139". Después de que Ariel la habilitó, con el mismo permiso de Lector: 200; para "FUNDINGS - Log de status [OFICIAL]" 1.141 eventos, el más viejo del 16 de marzo de 2026, cada uno con marca de tiempo, tipo (edición, cambio de permiso) y actor. Los actores vienen como identificadores de perfil de Google (8 distintos), no como nombres; no coinciden con los identificadores de permisos de Drive; la People API no está habilitada en el proyecto.
- Números de versión de Drive: Facturación - Craftech Total 66.931; Facturación - SleakOps Total 7.552; planilla de fundings 4.315. Cambian con cada guardado: sirven para detectar cambios sin leer el contenido.
- Pagos ARG: la conversión a USD (filas 29–45) divide por la fila 27 en todas las celdas; Pagos y PROYECCION PAGOS USA consumen esas filas convertidas; VENTAS y el Cash Flow no referencian las filas 23 ni 27. Filas 23 y 27 idénticas salvo jul-2025.
- Base informe › Consolidado: 46 rubros; "CAJA. Intercompany" existe (18 movimientos); "25. Evento Fin de año" existe (192 movimientos).
- Rangos con nombre de Base informe: `total_operaciones, total_IT, total_sleakops, total_impuestos, total_legales, total_gerencial, total_comunes, total_GEN_IA, total_finanzas, total_contable, total_DATA, total_activos, total_comercial, total_rrhh, total_deuda_afip, total_marketing, ingresos_financieros`. No existe `total_devs`.
- Base informe › TC MEP importa de la planilla `1VJfYRAi1HWh25ox-xdzBG3fHTvKhBwRz9e3WadYarXw` (pestañas `dolar-mep` y `dolar-mep-completo`), que la service account no puede abrir.

**Estado:** las diez decisiones de la sección 11 contestadas el 18 de octubre. Propuesta aprobada.
