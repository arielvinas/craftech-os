# Craftech OS — Etapa 1: Entendimiento

**Fecha:** 17 oct 2026 · **Base:** `docs/KICKOFF.md` y `docs/v0.9.md`, más un recorrido de solo lectura por las planillas.

Este documento cuenta con mis palabras qué entendí de la intención y cómo funciona hoy el circuito financiero. Todo lo que no está escrito explícitamente en el KICKOFF o en el v0.9 lleva la marca **[Inferencia]**. Las diferencias entre el v0.9 y lo que vi en las planillas están en la sección 4. Ahí solo las anoto: no resuelvo ninguna.

---

## 0. Cómo hice el recorrido y acceso

- **Lectura:** usé el conector de Google Sheets/Drive con la cuenta de Ariel, solo con operaciones de lectura (metadata, valores, fórmulas y colores de fondo de rangos puntuales). No escribí nada en ninguna planilla ni en Drive.
- **Cobertura:** las 9 planillas de la sección 6 del KICKOFF respondieron. No recorrí todo: miré estructura de pestañas, encabezados, bloques que el v0.9 nombra por número de fila, fórmulas clave y colores en muestras. Lo que no verifiqué está en la sección 7.
- **Service account de GCP: no la pude verificar.** No hay `gcloud` ni configuración de gcloud en esta máquina, el servidor MCP de GCP no conectó en esta sesión, y no busqué archivos de claves por el disco. Revisé los permisos de S1 y de Base informe: **ninguna cuenta `…@….iam.gserviceaccount.com` tiene acceso**. Sí aparece **`finance-bot@craftech.io`** como lector en las dos. Es un usuario de Workspace, no una service account. **Ariel confirmó (17-oct)** que `finance-bot` es la identidad que se creó y se usaba vía service account para acceder a las planillas. La verificación de las credenciales queda para la implementación: no hace falta para planificar. Verifiqué después que `finance-bot` también es lector en S7 ("FUNDINGS - Log de status [OFICIAL]") y en "Costos". Falta ver "Costos - Escenario 1".
- **Hallazgo de seguridad (solo lo reporto, no lo toco):** S1 tiene un permiso **"anyone" con rol lector**. Cualquiera con el link puede leer la facturación de Craftech. Importa porque define con qué identidad corre la ingesta y qué se puede saber de "quién cambió qué": el historial de revisiones y la actividad de Drive muestran el usuario de cada cambio, pero una service account solo los ve si tiene acceso al archivo. **[Inferencia]** Lo que efectivamente expone la API, lo detallo en la propuesta.
- **Datos personales:** las planillas de sueldos tienen nombres y montos por persona. En este documento describo solo su estructura.

---

## 1. La intención, con mis palabras

Craftech quiere un **sistema propio donde vivan los compromisos y los movimientos de la empresa**, empezando por finanzas: lo vendido, lo facturado, lo cobrado, lo pagado, lo presupuestado, los sueldos y el funding de AWS. Ese sistema tiene que mostrar, en tiempo casi real y a gente que no es de Finanzas, cómo viene la empresa y qué está trabado, con dueño y motivo.

Hoy la información existe pero está atrapada. Vive en planillas cargadas a mano, conectadas entre sí por IMPORTRANGE y fórmulas, con estados expresados como colores de celda, y solo Finanzas sabe leerlas. Se pierde la historia (lo que cambió y quién lo cambió), las causas de los frenos no están escritas, y para pensar escenarios Ariel termina estimando en su cabeza o tocando fórmulas.

La estrategia es **no tocar la operación**:

1. **Primero mirar sin intervenir (v0).** Importar todas las planillas con su historia, seguir leyéndolas de forma continua, registrar cada cambio (valor, color, fila borrada, fórmula pisada) con dónde, cuándo y, si se puede, quién, y reportar lo que no se puede interpretar en vez de adivinarlo. Esto solo ya da algo que hoy no existe: un registro auditable de cómo se mueven los números.
2. **Después, paridad.** Regenerar el P&L y el cashflow con las reglas de hoy, incluso lo que hoy se hace distinto de lo ideal (por ejemplo, el P&L sin cargas sociales), hasta que coincidan con los de Emi. Lo mejorable se anota, no se corrige.
3. **Recién ahí, sacarle trabajo a las planillas.** Un tipo de dato por vez pasa a cargarse en el sistema, empezando por ventas, contratos y pagos, y la planilla queda como vista o se deja. No hay fecha; hay criterio.

A todo eso se le suma **enriquecimiento**: conocimiento que hoy está en cabezas, Slack o mails, atado a algo estable y no a una celda, para que no se pierda cuando la planilla cambia. También **flujos de aprobación y alertas** (budgets, pagos atrasados, checklist Committed → Launched), **escenarios** que nunca tocan los datos reales, **una IA** que consulta datos bien estructurados, y la **extensión a otras áreas** (AWS, comercial, marketing, RRHH, delivery, OKRs) sin rediseñar.

Tiene que ser mantenible por cualquiera de Craftech (perfil DevOps/AWS), sin licencias pagas para ser robusto y con posibilidad de correr en la cuenta de AWS de Craftech. Además tiene que ser un lugar lindo para trabajar.

Las reglas financieras no son mías ni de Ariel: las deciden Emi y Ro. Si falta una regla, se pregunta.

---

## 2. Cómo funciona hoy el circuito financiero

### 2.1 Ingresos de servicios (Craftech)

1. **Venta / devengado.** Ro carga en **S1 › VENTAS** el devengado mensual por cliente, en USD, neto de IVA, prorrateado por días en el mes de inicio y de fin (R1). Grilla: filas = cliente (con *Fuente de ingreso*, *U. Negocio* y *POD*), columnas = meses de ene-2025 a dic-2027. La pestaña también tiene totales por mes y por trimestre, **objetivos** mensuales y trimestrales, y el % de cumplimiento. Lo que Ro traía de "Ventas Argentina 2025" ya está volcado acá en USD (R37). Es la base de comisiones (R21).
2. **Factura.** Normalmente se factura un mes después del devengado (R3).
   - **Clientes de Craftech-io Inc (USD):** la factura figura en **S1 › Pagos**, una celda por cliente × mes. Se emite hoy desde Zoho y en adelante desde HubSpot.
   - **Clientes de Craftech S.A. (ARS):** la fuente es **S1 › Pagos ARG**, con ARS brutos con IVA 21% (R14, R23, R25). Se emite en Bejerman/AFIP. Pagos ARG tiene un bloque en ARS, filas de cotizaciones y un bloque de conversión a USD. En Pagos, las filas 18–38 repiten esos clientes en USD por fórmula.
   - **Identidad de la factura** = fila de cliente + mes + entidad legal (R26).
3. **Estado.** El estado de cada factura lo dice el **color de la celda** (R29): celeste `#00ffff` a confirmar, azul `#4a86e8` confirmada, naranja `#ff9900` enviada, verde `#d9ead3` pagada, magenta `#ff00ff` retraso; con monto y sin color = a facturar. Vaciar la celda = el dato deja de existir (R30).
4. **Cobro.** Emi pinta el verde cuando ve la plata en el banco, casi a diario (R4). Mientras se lea la planilla, la fecha de cobro es la fecha en que el sistema detecta el verde. Vencimientos: upfront el día del envío, resto a 10 días, algunos clientes a 30 (R3). Hoy Zoho manda los recordatorios.

### 2.2 SleakOps (S2)

Misma estructura de grillas que S1 (Pagos, Pagos ARG, VENTAS, proyecciones), cargada por Emi y Sofi cada quince días. Líneas de suscripción (en general USD 339,50/mes, algunas de USD 97) y un bloque **Onboarding**, que es una línea de servicio real y muchas veces la cubre un funding de AWS. Una celda pintada sin monto es la **marca de baja** del cliente, no una factura (R31). El Marketplace de AWS factura solo, por eso no hay "FC A CONFIRMAR".

### 2.3 Funding de AWS

- **Hasta el 24/2/2026** el funding vive en el bloque AWS de **S1 › Pagos** (filas 96–204 según el v0.9). Desde el **25/2/2026** vive en **S7**, el tracker de Ro (R28). No se deduplica: una oportunidad en ambos es un error de carga.
- **Ciclo:** programa (fund request en Partner Central: POC, IW MIGRATE/BUILD/ASSESS, MAP…) → hitos identificados por el fund claim ID (R27) → disparo por sign-off o por umbral de consumo → cobro estimado a +30 días (R22).
- **Dos vistas** (R24): en el **P&L oficial**, el hito entra completo en el mes en que nace el derecho a cobro; en la **vista de gestión**, ese ingreso se asigna a los meses trabajados.
- **Conciliación del cobro:** Mercury trae el payment number, Partner Central lo abre en N claims (R36). El saldo del tracker contra Partner Central tiene que dar 0, salvo excepciones documentadas (R12).

### 2.4 Gastos y bancos

- **Base informe › Consolidado:** todos los movimientos bancarios desde sep-2021, una fila por movimiento. Columnas: mes, origen (EEUU/ARG), banco, tipo de erogación, frecuencia, tipo de movimiento, **Rubro**, **Agrupador**, equipo, moneda, monto, TC, monto USD, detalle, subdetalle, **Área**, tipo de gasto.
- Hay pestañas por banco (Mercury, Mesh, Galicia, Macro, Credicoop, Caja, VETA, etc.) y cuentas de ajuste **AFIP** y **CLIENTES** (R34).
- **Intercompany:** se identifica por el Rubro "CAJA. Intercompany" (R11).
- **Cómo entran los datos:** Mercury por API; Galicia, Macro y Credicoop por archivo de extracto (R35). La carga de Mercury a Mesh es una transferencia interna y el gasto se registra en Mesh.
- **[Inferencia]** Hoy las pestañas por banco se cargan a mano o pegando extractos, y el Consolidado se arma a partir de ellas.

### 2.5 Sueldos

- **Proyección sueldos** (Emi): roles, bandas (sueldo = base × % de banda, R7), área, unidad de negocio, persona × mes, cargas proyectadas (×1,5 sobre lo que se paga en ARS) y resúmenes anuales.
- **Base sueldos › sueldos-percibidos:** Empleado, Fecha, Monto, Área, Unidad de negocio. Según el v0.9, es lo que el P&L toma como costo laboral. Ese monto no incluye cargas; el SAC (R33) y el bono (R39) van sumados al mes en que se pagan.
- **Lo pagado real** sale de Base informe: *control sueldos y ccss*, *Sueldos*, *Bonos*, *SAC*, *Comisiones*. Las cargas sociales salen de Rubro "01. Sueldos" › Agrupador "CCSS" y van **solo al cashflow** (R5).
- **Sueldos EEUU** es el papel de trabajo de Emi para el neto a transferir. Tiene también la pestaña *Comisiones proyectadas*, que es el cálculo actual de comisiones.

### 2.6 Budget

- **Budget:** una pestaña por área (COMERCIAL, MKT, RRHH, IT, SLEAKOPS, DATA, GEN IA, DEVS, GERENCIAL, LEGALES, COMUNES, FINANZAS, CONTABLE, IMPUESTOS, OPERACIONES, ACTIVOS, DEUDA AFIP). Cada línea tiene país pagador (ARG/EEUU), tipo (Fijo / Variable / Discrecional) y meses, con un índice de inflación y un MEP proyectado por mes. Hay un *Consolidado* y un *data-consolidado*.
- El v0.9 habla de un budget **viejo**, que alimenta reportes, y uno **nuevo**, que es el prototipo manual del flujo de aprobación (ver D19).

### 2.7 Vistas: P&L y Cash Flow

- **P&L Completo:**
  - **Revenue** = `listado-ventas` de S1 + `listado-ventas` de S2.
  - **Costos directos y operativos:** sueldos por área + gastos por área.
  - **Resultados:** Gross Profit y EBITDA.
  - Hay variantes *por Q y anual*, *% sobre revenue*, *ventas proyectadas* y *Esc 1* (escenario).
- **Cash Flow Mensual:**
  - Resumen ARG-USA (saldo inicial, $ recibidos de la Inc, pagos recibidos, gastos, saldo final).
  - Pestañas CASH FLOW USA / ARG muy anchas.
  - Histórico, dashboards, tracking y "pagos en disputa".
  - Bloques de escenario ("con facturación mínima", "2025 aislado", "Para que modifique ARI").
- **Regla de cashflow ARG:** traer USD para cerrar el mes con 4M ARS (R9).
- **Cierre de mes:** snapshot al último día hábil; lo cargado el primer día hábil integra el cierre; después, todo cambio es una corrección con autor y motivo (R18).

### 2.8 Lo operativo de un deal

Cuando un deal pasa a **Committed** en HubSpot arranca lo operativo: contrato, funding, upfront. Pasa a **Launched** cuando el proyecto arrancó, el funding está en cash claim, el contrato está firmado y el upfront pagado (R19). Hoy ninguna planilla identifica contratos: al principio se infieren. **[Inferencia]** Hoy este checklist no está escrito en ningún lado; vive en la cabeza de Ro y en Slack.

---

## 3. Fuentes: lo que dice el v0.9 y lo que vi

| Fuente | Lo que vi |
|---|---|
| **S1 Facturación Craftech Total** | 48 pestañas. Las vigentes: *VENTAS* (encabezado en la fila 23, datos desde la 24), *Pagos* (encabezado en la fila 17, datos desde la 18, leyenda de colores en D9:H9), *Pagos ARG*, *PROYECCION VENTAS*, *PROYECCION PAGOS USA (2025-2026)*. Hay además: pestañas por año para 2021–2024 (*Pagos USA (2021…2024)*, *Pagos ARG (2021…2024)*, *VENTAS USA 2023/2024*, *Ventas ARG 2024/2025*, *Pagos AWS (2023)*, *Ventas con CEI*), pestañas `listado-*` / `data-*` (formato largo, alimentan el P&L), *Ventas IA / Data / DevOps*, *Q-Ventas*, *M-Ventas*, *3M-Ventas*, *InterM-Ventas*, *Gastos*, *recalc*, *Historia*, y pestañas que parecen de trabajo (*JDJDKDKDKDKD*, *Hubspot Corrección NO USAR…*, *Copia de VENTAS USA 2025 COMPARATIVO*). |
| **S1 › Pagos ARG** | Fila 1 "Dólar oficial"; fila 2 meses; filas 3–19 clientes en ARS; fila 22 total; fila 23 MEP; fila 24 Dólar Divisa VTA; fila 25 CCL; **fila 27 un segundo MEP**; fila 28 meses; filas 29–45 conversión a USD; fila 51 total USD; filas 56–65 proyección de IVA/IIBB (BRUTO, NETO, IVA, IVA PAGADO, DDJJ, PAGO DDJJ, %, IIBB, Cambio USD, Total IVA). Coincide con el v0.9 salvo D1/D2. |
| **S2 Facturación SleakOps Total** | 34 pestañas con la misma lógica que S1 (vigentes + históricas + `listado-*`). *Pagos* tiene encabezado en la fila 10 y bloques Suscripción → Onboarding. Tiene una pestaña *Pagos ARG* chica (30 filas) y una fila "TOTAL PAGOS ARG" (ver D9). |
| **S7 Tracker de fundings** | No está en el KICKOFF. Encontré en Drive **"FUNDINGS - Log de status [OFICIAL]"**, con pestañas *2025*, *FUNDINGS*, *DB*, *SUMA* y *Pagos confirmados*. **[Inferencia]** Es S7; hay que confirmarlo. *FUNDINGS* tiene empresa, tipo de funding, status, unidad comercial, fechas (carga en FP, sign-off estimado, cobro estimado), cash/credit, monto, OPP ID, AWS ID, link a HubSpot, calculadora, SOW, **Fund request ID** (URL), responsables AM/SA, sign-off, invoice cargada, fecha de pago y nota. **No tiene todavía columna de fund claim ID**, lo que es coherente con la acción pendiente de Ro. |
| **P&L Completo** | Pestañas *gastos* (IMPORTRANGE de Budget › data-consolidado), *sueldos* (IMPORTRANGE de Base sueldos › sueldos-percibidos!A:E), *ventas*, *Ventas proyectadas*, sus variantes *esc 1*, y las vistas P&L. Las vistas no leen de esas pestañas locales como describe el v0.9 (D12, D13). |
| **Cash Flow Mensual** | 13 pestañas. *CASH FLOW USA* tiene 1.545 columnas y *CASH FLOW ARG* 732. **[Inferencia]** Granularidad diaria o por movimiento. *Historico Cash Flow* tiene 37.521 filas. También hay una pestaña *Gastos Budget 2026*. |
| **Base informe Craftech** | 42 pestañas. *Consolidado* tiene 21.731 filas desde sep-2021 y 17 columnas con encabezado. Confirmé que existe Rubro "01. Sueldos" › Agrupador "CCSS". Hay pestañas de ajuste (*Ajuste cobros clientes*, *Ajuste Credito Fiscal*), *Base facturacion*, *GASTOS POR AREA*, *Planilla de gastos - control budget*, *TC MEP*, *Dolar Futuro*, *Prestamos*, *Deuda Planes de pago*, *CIRCUITO TECNOM/YELLAMO* y pestañas Tax EEUU por año. |
| **Proyección sueldos** | 23 pestañas: bandas, base, cálculo y resúmenes proyectados 2025/2026/2027, sueldos percibidos/devengados, nómina, comisiones devengadas/percibidas, `data-*`. |
| **Base sueldos** | *sueldos-percibidos* / *-devengados*, cada una en variantes *-actual* e *-historico*. Columnas: Empleado, Fecha, Monto, Área, Unidad de negocio. |
| **Sueldos EEUU** | *Sueldos*, *Bajas*, *Neto a transferir*, *Comisiones proyectadas*, *Monto de cargas que se descuenta*, *Control de invoices entregadas* y pestañas de trabajo (*Temporal*, *Hoja 40*, *Copia de Sueldos*). |
| **Budget** | Ver 2.6. |
| **Costos** (no está en el KICKOFF) | Planilla "Costos". El P&L lee de ella los sueldos por área (D12). Hay también una "Costos - Escenario 1". El v0.9 menciona "Costos (Valio)" como vista. |

---

## 4. Diferencias y contradicciones encontradas (sin resolver)

Cada punto queda anotado para convertirlo en pregunta a Finanzas en la Etapa 2. Ninguno lo resuelvo yo.

**Cotizaciones y conversión ARG**

- **D1. La conversión ARS no siempre referencia las filas 23–27.** En la muestra que leí de Pagos ARG (Moni, dic-2025 y ene-2026), la celda en ARS es una fórmula con el monto del contrato adentro que multiplica por la **fila 1 "Dólar oficial"** (`M3 = 7200*1.21*M1`, con `M1` = 1.475). No revisé los demás clientes. El ejemplo de R38 se confirma: `R19 = 1875*1.21*1491.57`, cotización tipeada a mano. R10 dice que los valores del mes están en las filas 23–27 y que el sistema lee la fila referenciada por la fórmula. Esa fila 1 no figura en el v0.9. No sé si "Dólar oficial" es la cotización pactada de esos clientes o si es otra cosa.
- **D2. Hay dos filas MEP (23 y 27) y no siempre coinciden.** Ej.: jul-2025, 1236,42 contra 1255. La conversión a USD (filas 29–45) divide por la **fila 27** (`=M3/M$27`). No está claro cuál es la "tasa operativa de reportes" (R10).
- **D3. El USD de los clientes ARG incluye IVA y la diferencia entre el oficial y el MEP.** Ej.: Moni, ene-2025: contrato USD 7.200 neto → ARS 9.169.380 brutos (7.200 × 1,21 × 1.052,5) → USD 7.854 (÷ MEP 1.167,52). Esos USD 7.854 son los que suma "TOTAL PAGOS ARG" en S1 › Pagos. Hay que saber qué espera ver Finanzas en el cashflow y en la paridad.
- **D4. Los colores del bloque USD de clientes ARG se pintan aparte.** En S1 › Pagos, filas 18–38, los valores son fórmulas `='Pagos ARG'!Xnn` (coincide con el v0.9), pero los colores se pintan sobre esas celdas, independientes de los de Pagos ARG, que también tiene colores. Además las referencias no siguen el orden de filas: GigaRed y DIBUSOFT están en orden invertido entre las dos pestañas (la fila 32 apunta a la 44 de Pagos ARG y la 33 a la 43), y hay una celda suelta que apunta a `Q50`. ¿Qué color manda para el estado de una factura S.A.: el de Pagos ARG o el de Pagos?
- **D26. El monto del contrato ARG está escrito dentro de la fórmula** (`7200*1.21*…`). Es útil para inferir contratos, pero hay que confirmar que siempre es el valor del contrato en USD neto.

**Grilla de colores y celdas**

- **D7. Aparecen colores que R29 no lista.** La leyenda D9:H9 confirma los 5 hex de R29. Además aparecen: `#c9daf8` (celeste claro) en celdas vacías futuras de S1 › Pagos, `#d0e0e3` en celdas vacías de Pagos ARG, `#ea9999` (rojo claro) en celdas sin monto de S2, y blanco explícito, que no es lo mismo que "sin color" para la API. R29 dice "mapeo único y global" y R31 dice "pintada sin monto" sin especificar el color.
- **D8. En S2 hay casos ambiguos.** Ej.: Blimop tiene celdas **magenta (RETRASO PAGO) sin monto**, algunas con fórmula a Pagos ARG que da vacío, y celdas con **USD 0,00 pintadas de verde**. ¿El magenta sin monto es baja o retraso? ¿Un 0 pagado es un dato o es "vacío"? (R30, R31)
- **D10. Hay valores ilegibles reales.** S2 › Pagos, Atlantics, feb-2026: el texto `814,8`, con coma decimal y sin formato de moneda. Es justo el caso que R30 manda reportar.
- **D21. Hay datos sueltos dentro de una grilla de carga.** En S1 › Pagos, la fila de Broota tiene valores en AR–AW ("TARJETA DE CREDITO", 2524, 0.3, …) y la columna AQ se llama "Forma de pago". No sé si son datos o cálculos de trabajo.

**Bloques y filas**

- **D5. El bloque AWS de S1 › Pagos va de la fila 96 a la 203.** La 204 está vacía y "Total Ingresos" está en la 205; el v0.9 dice 96–204. Adentro hay filas "General / CEI", una "MAP 2.0" y una fila "Funding de AWS confirmados" (178). El glosario no define **CEI**.
- **D6. La columna Servicio se sigue cargando.** El v0.9 dice que es legado 2020–2022 y no se importa, pero en las pestañas vigentes está completa para clientes 2025–2027 (M. Devops, Project, MSP, Support, Licencias y, en PROYECCION, también MAP, IW Migrate y POC).
- **D11. Hay dos filas "FUNDINGS SHEET".** El Anexo 1 habla de "la fila FUNDINGS SHEET", pero en *PROYECCION PAGOS USA (2025-2026)* hay dos: "FUNDINGS SHEET Proyectados" y "FUNDINGS SHEET Confirmados".
- **D9. SleakOps también factura por la S.A.** S2 tiene *Pagos ARG* y "TOTAL PAGOS ARG" (ej.: Xcons, ~USD 424/mes). El v0.9 describe S2 como Marketplace que factura solo, pero hay facturación de SleakOps por Craftech S.A.

**P&L**

- **D12. El costo laboral del P&L no sale de donde dice el v0.9.** La pestaña *sueldos* del P&L existe con el IMPORTRANGE que describe el v0.9 (`sueldos-percibidos!A:E`), pero las filas "Sueldos IT / SleakOps / Comercial / Gerencial / Operaciones / RRHH / MKT / Finanzas" de *P&L Craftech* leen de **otra planilla: "Costos" › sueldos**, filtrando por área. En el bloque *Esc 1*, de lo que leí (ene–mar 2024), solo la celda ene/Sueldos IT lee de "Costos - Escenario 1"; el resto lee de "Costos". "Costos" no está en la lista de fuentes del KICKOFF.
- **D13. Los gastos del P&L salen de otro lado, y hay una posible doble cuenta.** Las filas de gastos leen **rangos con nombre de Base informe** (`total_it`, `total_comercial`, …, de a 12 columnas, o sea un año), no la pestaña *gastos* del P&L, que importa de Budget › data-consolidado. **"Gastos Devs" y "Gastos DATA" usan el mismo rango `total_data`**, lo que parece una doble cuenta. Si se replica al 100%, hay que replicarla también. Lo decide Finanzas.
- **D14. No sé quién genera `listado-ventas`.** El revenue del P&L sale de esas pestañas de S1 (columna C) y S2 (columna D). **[Inferencia]** Las genera un script o una fórmula a partir de VENTAS; no lo verifiqué.

**Historia**

- **D15. Ya existe un historial parcial.** S1 › *Historia* guarda una foto diaria de totales por mes (ene-2025 a dic-2026) desde el 2/1/2025. Desde el 19/9/2025 es automática (~23:43), se corta el 1/1/2026 y tiene dos filas sueltas el 25/2/2026. Contradice en parte "no hay historial" y puede servir de semilla. No identifiqué qué total guarda: no coincide con "Total Mensual" de VENTAS ni con "TOTAL PAGOS" de ene-2025.
- **D22. La historia está en pestañas por año con estructuras distintas.** Las vigentes de Pagos y VENTAS arrancan en ene-2025; 2021–2024 están en pestañas por año con distinta cantidad de columnas. La sección 3 del v0.9 no las describe, y "importar toda la historia" las necesita.

**Funding / S7**

- **D16. "Pagos confirmados" no coincide con el v0.9.** El v0.9 dice que 2026 da \$558.079 Craftech + \$30.000 SleakOps. En la planilla candidata, el total 2026 de Craftech es **USD 1.118.427**, e incluye oct (515.683) y nov (29.065). Tampoco coincide con la fila "TOTAL PAGOS AWS" de S1 › Pagos. La diferencia grande está en **ene–may 2026**: S1 da 63.763 / 92.090 / 93.853 / 152.400 / 183.569 y Pagos confirmados da 0 / 0 / 0 / 6.000 / 118.809. Ene–feb se podrían explicar por el corte de R28 (24/2); mar–may, no. También hay diferencias en jul (157.083 contra 158.949), ago (29.400 contra 67.025) y sep (85.246 contra 90.246). La planilla se creó el 16/3/2026, cuando el corte del v0.9 es el 25/2/2026.

**Vocabulario, dimensiones y budget**

- **D17. VENTAS no tiene columna de vendedor.** Tiene Fuente de ingreso, U. Negocio y POD. R21 calcula comisiones por vendedor sobre los contratos atribuidos, pero no vi de dónde sale esa atribución.
- **D18. Un mismo cliente aparece con nombres distintos entre pestañas.** Ej.: "Consorcioabierto SRL" / "Consorcio Abierto", "GigaRed" / "Gigared", "SIDOM" / "Sidom", "TrackChain" / "TRackchain" / "Trackchain", y nombres con espacios al final ("Alephee ", "UALI "). Confirma que hace falta la sesión de aliases (R32).
- **D19. No queda claro cuál es el budget viejo y cuál el nuevo.** El v0.9 habla de los dos; recibí un solo archivo Budget, y además existe *Gastos Budget 2026* dentro de Cash Flow y *Planilla de gastos - control budget* en Base informe.
- **D20. El Cash Flow no es solo una vista.** Tiene bloques de escenario y notas manuales ("Para que modifique ARI", "Balanz monto inicial 28000 usd"). **[Inferencia]** Tiene celdas cargadas a mano, así que no es 100% regenerable.
- **D23. S1 tiene muchas pestañas que el v0.9 no clasifica.** Ventas IA/Data/DevOps, Q-Ventas, M-Ventas, PROYECCION VENTAS/PAGOS y las de trabajo. El v0.9 solo dice qué se ingiere de VENTAS, Pagos y Pagos ARG; no sé cuáles de las otras son carga y cuáles derivadas.
- **D24. "CAJA. Intercompany" no lo verifiqué.** No apareció en el tramo de Base informe › Consolidado que leí (filas 21.500–21.731). Que "desde el día uno" signifique sep-2021 es **[Inferencia]**.
- **D25. VENTAS tiene objetivos de venta** por mes y trimestre, y un "% Objetivo". El v0.9 no los menciona; es dato de negocio que la empresa usa.

---

## 5. Cosas del planteo que me parecen en tensión

El KICKOFF pide decirlo si algo no cierra.

1. **"Importar toda la historia" tiene un límite.** Las planillas guardan sobre todo el **estado actual**, más las pestañas por año y la foto diaria parcial de *Historia*. La evolución de cada celda en el pasado, colores incluidos, solo existe en el historial de versiones de Google. **[Inferencia]** No sé todavía cuánto de ese historial se puede leer por API para Sheets nativos. Lo investigo en la Etapa 3. Hasta saberlo, conviene asumir que la historia "de cambios" empieza el día que arranca la ingesta y que lo anterior es la historia "de valores".
2. **R4 hace que la fecha de cobro dependa del sistema.** Mientras se lea la planilla, la fecha de cobro es la fecha en que el sistema detecta el verde, así que la frecuencia de lectura pasa a definir un dato de negocio. Para Finanzas no es lo mismo leer cada 5 minutos que una vez por día.
3. **Replicar al 100% incluye replicar lo que parece un error** (D13). Está bien como regla, pero alguien tiene que confirmar caso por caso si es un error o una decisión, y quedar anotado en 8.1.
4. **Las fuentes del KICKOFF no son todas las que usa el P&L.** Faltan S7 (sin link) y "Costos" / "Costos - Escenario 1", que el P&L usa (D12). Para la paridad necesito leerlas.
5. **"Vista" y "carga" se mezclan en un mismo archivo.** El v0.9 trata Cash Flow y P&L como vistas regenerables, pero ambos tienen escenarios y celdas manuales (D20). La paridad tiene que distinguir qué parte se regenera y qué parte es dato.
6. **El KICKOFF trata como vinculantes secciones que en el v0.9 son chicas.** La sección 8.1 y el Anexo son vinculantes; la 8 es "Criterios de éxito y riesgos". No es una contradicción, pero el criterio de éxito ("cinco preguntas que hoy llevan un día de Excel") no dice cuáles son las preguntas. Vale definirlas temprano porque ordenan el modelo.

---

## 6. Inferencias (resumen)

- Las pestañas por banco de Base informe se cargan a mano o pegando extractos, y el Consolidado se arma a partir de ellas.
- El checklist Committed → Launched hoy no está escrito en ningún lado.
- `listado-ventas` y las demás pestañas `listado-*` / `data-*` son derivadas, por fórmula o por script.
- *Historia* la llena un trigger de Apps Script.
- "FUNDINGS - Log de status [OFICIAL]" es S7.
- Las pestañas CASH FLOW USA/ARG tienen granularidad diaria o por movimiento.
- El Cash Flow tiene celdas manuales que no se regeneran.
- "Desde el día uno" en Base informe = sep-2021.
- Lo que la API de Google expone sobre autoría y versiones: a verificar en la Etapa 3.

---

## 7. Lo que no vi y queda para la Etapa 2

- **Confirmaciones de Ariel:** que S7 es la planilla que encontré, si "Costos" tiene que estar en la lista de fuentes, y los datos de la service account (proyecto y email).
- **Sin recorrer en detalle:** PROYECCION VENTAS/PAGOS, Ventas IA/Data/DevOps, pestañas por año 2021–2024, *Historico Cash Flow*, CASH FLOW USA/ARG, *control sueldos y ccss*, Sueldos EEUU, Proyección sueldos por dentro, la pestaña 2025 de S7, los bloques Onboarding de S2 a fondo, y si "CAJA. Intercompany" existe.
- **Scripts:** no revisé Apps Script ni rangos con nombre. Solo vi que el P&L usa rangos con nombre de Base informe.

**Fin de la Etapa 1.** La Etapa 2 (`docs/02-questions.md`) arranca cuando Ariel lo indique.
