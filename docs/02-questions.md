# Craftech OS — Etapa 2: Preguntas

**Fecha:** 17 oct 2026 · **Base:** `docs/01-understanding.md` (las diferencias D1–D26 están ahí con detalle).

Dos bloques, como pide el KICKOFF: preguntas de producto para Ariel y preguntas de reglas para Finanzas. Cada pregunta dice qué bloquea: **v0** (importar, leer continuo, registrar cambios, reportar lo ilegible), **paridad** (P&L y cashflow iguales a los de Emi) o **nada** (se puede decidir después).

**Regla que aplico mientras no haya respuesta:** una regla financiera sin respuesta **no se implementa**. Las propuestas que escribo son para acelerar la decisión, no un default que tomo si nadie contesta. La v0 no necesita ninguna regla financiera, así que puede arrancar mientras Finanzas contesta su bloque.

## Ya resuelto en el chat (17-oct)

- La identidad para leer planillas es `finance-bot@craftech.io`. Tiene lectura en S1, Base informe, S7 y "Costos" (verificado). Las credenciales se verifican al implementar.
- Todo corre en **Docker local** (DB incluida). La nube se decide cuando lo local esté perfecto.
- Ariel aceptó separar las preguntas que bloquean la v0 de las que bloquean la paridad.

---

## A. Preguntas de producto para Ariel

### Bloquean la v0

**P-01. Qué planillas y pestañas entran en la v0.**
*Qué vi:* S1 tiene 48 pestañas y S2 34. Entre vigentes, históricas por año (2021–2024), derivadas (`listado-*`, `data-*`) y de trabajo (`JDJDKDKDKDKD`, `Hubspot Corrección NO USAR…`, `Copia de…`, `recalc`). Además el P&L usa dos planillas que no están en el KICKOFF: "Costos" y "Costos - Escenario 1".
*Por qué importa:* ingerir todo cuesta poco en volumen pero mucho en ruido: cada pestaña de trabajo va a generar "cambios" sin valor.
*Propuesta:* v0 ingiere **todo lo de las 9 planillas + S7 + Costos**, pero con una clasificación por pestaña: `CARGA` (se registran cambios y se alertan), `DERIVADA` (se ingiere para paridad, cambios sin alerta), `HISTÓRICA` (se importa una vez), `IGNORAR`. La clasificación inicial la propongo yo en la Etapa 3 y la valida Finanzas.

**P-02. Confirmar que S7 es "FUNDINGS - Log de status [OFICIAL]".**
*Qué vi:* es la única planilla de Drive con pestaña "Pagos confirmados". Su pestaña "2025" está vacía en las primeras filas; el funding 2025 estaría solo en el bloque AWS de S1 › Pagos.
*Por qué importa:* es la fuente del funding desde el 25/2/2026 (R28).

**P-03. Quién ve la v0 y por dónde, mientras corre en tu laptop.**
*Qué vi:* el KICKOFF dice que el registro de cambios es "visible para Ariel y Finanzas". En Docker local, solo lo ve quien tenga la laptop.
*Por qué importa:* define si la v0 necesita web, Slack, o ambos, y si Emi y Ro participan desde el día uno o recién cuando esté hosteado.
*Propuesta:* v0 = web local mínima + un canal de Slack donde el sistema publica el resumen diario de cambios y lo ilegible. El canal lo pueden ver Emi y Ro aunque el sistema corra en tu máquina. Web para Finanzas, recién cuando esté hosteado.

**P-04. Qué pasa con R4 si la laptop está apagada.**
*Qué vi:* R4 dice que la fecha de cobro es la fecha en que el sistema detecta el verde. Una laptop apagada de noche o un fin de semana corre esa fecha uno o más días.
*Por qué importa:* durante la v0 esa fecha no se usa para nada (no hay paridad todavía), pero si la historia de cambios de la v0 después alimenta la paridad, los cobros de esos días quedan corridos.
*Propuesta:* aceptar el corrimiento durante la v0 y marcar cada lectura con su timestamp real, para que "detectado el lunes 9:00" no se confunda con "cobrado el lunes". Si querés evitarlo, hace falta una máquina siempre prendida desde el día uno (una Mac mini, un VPS chico o la cuenta de AWS). Lo decidís vos.

**P-05. Cada cuánto leer las planillas.**
*Propuesta:* cada 15 minutos en horario laboral (8–20, lun–vie), cada hora fuera de ese horario. Lo tiene que validar Emi porque toca R4 (ver F-11).

**P-06. Qué significa "toda la historia".**
*Qué vi:* las planillas guardan el estado actual, las pestañas por año y una foto diaria parcial (*Historia*). La evolución de cada celda en el pasado solo está en el historial de versiones de Google, y todavía no sé cuánto de eso expone la API (lo investigo en la Etapa 3).
*Por qué importa:* "importar toda la historia" puede significar dos cosas distintas: (a) todos los **valores** históricos (2021–2026) o (b) todos los **cambios** históricos de cada celda. (a) es seguro; (b) depende de Google y puede ser parcial.
*Propuesta:* (a) completo, (b) hasta donde la API permita, y aclarar que la historia de cambios completa empieza el día que arranca la ingesta.

### Bloquean la paridad (no la v0)

**P-07. Qué significa "útil en pocas semanas" para vos.**
Opciones, no excluyentes: (1) ver el log de cambios de las planillas, (2) el P&L regenerado igual al de Emi, (3) responder preguntas por chat sobre los datos. ¿Cuál es la que, si está en 3–4 semanas, decís "esto ya sirve"?

**P-08. Las cinco preguntas que hoy llevan un día de Excel.**
*Qué vi:* el v0.9 §8 las pone como criterio de éxito pero no las nombra.
*Por qué importa:* ordenan el modelo de datos y la prioridad de qué ingerir primero. Nombralas aunque sea en borrador.

**P-09. Alcance del P&L a replicar.**
*Qué vi:* el P&L tiene cinco vistas: mensual, por Q y anual, % sobre revenue, ventas proyectadas, y "Esc 1". El Cash Flow tiene varios bloques de escenario.
*Propuesta:* paridad = "P&L Craftech" mensual y "Resumen mensual Cash Flow ARG-USA". Las demás son derivadas o escenarios.

### No bloquean

**P-10. Idioma de la documentación técnica.** El KICKOFF permite inglés preservando términos de Craftech. Propongo: docs/ en español (son para vos y Finanzas), código y specs técnicas en inglés con el glosario del v0.9 (`Accrual`, `Invoice`, `Payment`…) tal cual.

**P-11. Permiso "anyone con el link" en S1.** Lo reporté en 01-understanding §0. No es del sistema, pero conviene que lo saques.

**P-12. Repo.** Si querés que la propuesta y las specs vivan en este repo y el código en otro, o todo acá.

---

## B. Preguntas de reglas para Finanzas

Escritas para que Emi, Ro o Sofi puedan contestar sin leer el resto. Las referencias son `planilla › pestaña › celda`.

### Bloquean la paridad

**F-01. Cotización de las facturas ARG: fila 1 "Dólar oficial" o filas 23–27.** → Emi
*Qué vi:* en S1 › Pagos ARG, la celda de Moni para dic-2025 es `M3 = 7200*1.21*M1`, y `M1` es la fila 1, "Dólar oficial" (1.475). Ene-2026 igual: `N3 = 7200*1.21*N1`, con `N1` = 1.480. La regla R10 dice que la cotización pactada está en las filas 23–27 (MEP, Divisa, CCL) y que el sistema lee la fila que referencia la fórmula. Solo miré Moni; no sé si todos los clientes usan la fila 1.
*Por qué importa:* el sistema tiene que saber qué cotización usar para cada factura ARG.
*Qué bloquea:* el cálculo de facturas ARG y el "TOTAL PAGOS ARG" en USD.
*Pregunta:* ¿"Dólar oficial" (fila 1) es la cotización pactada de esos contratos? ¿Hay clientes que usan otra fila? ¿Hay que agregar "oficial" a la lista de tipos de cotización de R10?

**F-02. Hay dos filas MEP (23 y 27) con valores distintos.** → Emi
*Qué vi:* S1 › Pagos ARG, jul-2025: fila 23 dice 1.236,42 y fila 27 dice 1.255. Ese 1.255 es igual al "Dólar oficial" de jul-2025 (`H1`); parece un valor copiado de la fila equivocada. La conversión a USD (filas 29–45) divide por la fila 27.
*Pregunta:* ¿Cuál es la MEP "operativa de reportes" de R10? ¿Para qué sirve cada fila?

**F-03. El USD de los clientes ARG incluye el IVA y la diferencia oficial/MEP.** → Emi
*Qué vi:* Moni, ene-2025: contrato USD 7.200 → ARS 9.169.380 (× 1,21 × oficial) → USD 7.854 (÷ MEP). Esos 7.854 son los que suma "TOTAL PAGOS ARG" en S1 › Pagos.
*Por qué importa:* VENTAS está neto de IVA (R14) pero el cobro en USD de la misma factura no, y además usa otra cotización. El cashflow y el P&L tienen que saber cuál es "la" cifra.
*Pregunta:* ¿Qué querés ver en el cashflow para una factura ARG: los USD a MEP con IVA (como hoy), el neto, o ambos?

**F-04. Qué color manda para una factura S.A.: el de Pagos ARG o el de Pagos.** → Emi
*Qué vi:* S1 › Pagos filas 18–38 traen los USD de Pagos ARG por fórmula, pero los colores se pintan en las dos pestañas por separado. Además GigaRed y DIBUSOFT están en orden invertido entre las dos pestañas, y hay una celda que apunta a `'Pagos ARG'!Q50`, una fila vacía.
*Por qué importa:* el estado de cada factura S.A. sale del color, y hoy hay dos lugares donde puede estar pintado.
*Pregunta:* ¿Cuál de las dos pestañas es la fuente del estado? ¿O las dos tienen que coincidir siempre y una diferencia es un error a reportar?
*Propuesta:* Pagos ARG es la fuente del estado para S.A.; una diferencia de color entre las dos se reporta.

**F-05. Colores fuera de la lista de R29.** → Emi
*Qué vi:* además de los 5 colores de R29 aparecen: `#c9daf8` (celeste claro) en celdas vacías futuras de S1 › Pagos, `#d0e0e3` (gris verdoso) en celdas vacías de Pagos ARG, `#ea9999` (rojo claro) en celdas sin monto de S2 › Pagos, y blanco explícito.
*Por qué importa:* el mapeo de R29 es la única forma que tiene el sistema de leer el estado de una factura. Un color fuera de la lista es o un estado nuevo o ruido, y el sistema no puede decidirlo solo.
*Pregunta:* ¿Esos colores significan algo o son "sin color"? ¿Cuál es el color exacto de la marca de baja de SleakOps (R31)?
*Propuesta:* tratarlos como "sin color" y reportar cualquier color nuevo que aparezca.

**F-06. Casos ambiguos en S2.** → Emi
*Qué vi:* S2 › Pagos, Blimop (fila 12): may–jul 2025 **USD 0,00 pintadas de verde** (FC PAGADA); ago-2025 a ene-2026 **magenta sin monto** (la de ene-2026 es una fórmula a Pagos ARG que da vacío); feb–mar 2026 **magenta con monto** (1.694 y 1.271, fórmulas a `'Pagos ARG'!O14` y `P14`, o sea Blimop también factura por la S.A., ver F-19). En S1 también hay celdas "USD $0" con color.
*Por qué importa:* R30 y R31 definen "vacío" y "pintada sin monto", pero no qué hacer con un 0 con color ni con un magenta sin monto. Son casos reales, no teóricos.
*Pregunta:* ¿Magenta sin monto = retraso de pago o baja? ¿Un 0 pintado de verde es una factura pagada de 0, un dato borrado o un error?

**F-07. Posible doble cuenta en el P&L: "Gastos Devs" y "Gastos DATA" leen el mismo rango.** → Emi
*Qué vi:* en P&L Completo › P&L Craftech, las filas "Gastos Devs" y "Gastos DATA" importan ambas el rango `total_data` de Base informe.
*Por qué importa:* si es un error, la paridad lo tiene que replicar igual y anotarlo en 8.1. Si es intencional, hay que saber por qué.
*Pregunta:* ¿Es un error? ¿Existe un rango `total_devs`?

**F-08. La fuente real del costo laboral del P&L es "Costos", no `sueldos-percibidos`.** → Emi
*Qué vi:* las filas "Sueldos IT / SleakOps / Comercial / …" del P&L leen de la planilla **"Costos" › sueldos** (mismas columnas: Empleado, Fecha, Monto, Área, [vacía], Unidad de negocio). La pestaña *sueldos* del P&L que importa de `sueldos-percibidos` existe pero las vistas no la usan. "Esc 1" lee una celda de "Costos - Escenario 1".
*Pregunta:* ¿"Costos" es la fuente oficial del costo laboral? ¿Qué relación tiene con "Base sueldos › sueldos-percibidos"? ¿Es una copia, una versión depurada, otra cosa?

**F-09. El origen de `listado-ventas`.** → Emi
*Qué vi:* el revenue del P&L sale de `listado-ventas` de S1 (columna C) y de S2 (columna D).
*Pregunta:* ¿Quién genera esas pestañas, una fórmula o un script? ¿Se regeneran solas cuando cambia VENTAS?

**F-10. Cuentas de ajuste AFIP y CLIENTES: fórmula exacta.** → Sofi, Emi
*Qué vi:* R34 dice que el P&L las replica, pero no dice cómo se calculan.
*Pregunta:* ¿Cuál es la regla de cada ajuste (qué movimientos toma, con qué signo, en qué mes)?

**F-11. Frecuencia de lectura y fecha de cobro.** → Emi
*Qué vi:* R4 dice que mientras se lea la planilla, la fecha de cobro es la fecha en que se detecta el verde. Propongo leer cada 15 minutos en horario laboral.
*Pregunta:* ¿Te alcanza esa frecuencia? Si pintás el verde el viernes a la noche y el sistema lo lee el lunes, ¿la fecha de cobro es lunes o viernes?

**F-12. "Pagos confirmados" de S7 no coincide con el v0.9 ni con S1.** → Ro
*Qué vi:* S7 › Pagos confirmados, 2026: total Craftech USD 1.118.427 (el v0.9 dice $558.079 + $30.000 SleakOps). Ene–may 2026 da 0 / 0 / 0 / 6.000 / 118.809, mientras S1 › Pagos "TOTAL PAGOS AWS" da 63.763 / 92.090 / 93.853 / 152.400 / 183.569. Jul, ago y sep también difieren.
*Por qué importa:* la pestaña es el control de paridad del funding (sección 3 del v0.9).
*Pregunta:* ¿Cuál de los dos es el número correcto por mes? ¿Ene–feb se explican por el corte del 24/2 (R28)? ¿Y mar–may?

**F-13. Vendedor por contrato.** → Ro
*Qué vi:* VENTAS tiene Fuente de ingreso, U. Negocio y POD, pero no vendedor. R21 calcula comisiones por vendedor.
*Pregunta:* ¿Dónde está la atribución contrato → vendedor? ¿HubSpot, "Sueldos EEUU › Comisiones proyectadas", otro lado?

**F-14. Budget viejo y nuevo.** → Emi, Sofi
*Qué vi:* un solo archivo "Budget" (una pestaña por área), más "Gastos Budget 2026" dentro de Cash Flow y "Planilla de gastos - control budget" en Base informe.
*Pregunta:* ¿Cuál es el viejo y cuál el nuevo? ¿Cuál alimenta el P&L y cuál es el prototipo del flujo de aprobación?

### Bloquean la ingesta correcta (v0 corre igual, pero con ruido)

**F-15. Columna "Servicio" en Pagos: ¿se sigue usando?** → Ro
*Qué vi:* el v0.9 dice que es legado 2020–2022 y no se importa, pero en las pestañas vigentes está completa para clientes 2025–2027 (M. Devops, Project, MSP, Support, Licencias, MAP, IW Migrate, POC).
*Pregunta:* ¿La ignoramos igual, o la importamos como etiqueta?

**F-16. Qué es "CEI".** → Ro
*Qué vi:* filas "General / CEI / CEI" en el bloque AWS de S1 › Pagos, una pestaña "Ventas con CEI" y "listado-ventas-CEI". El glosario no lo define.
*Respuesta (Ariel, 18-oct):* **AWS Customer Engagement Incentive**, programa de funding de AWS que dejó de existir en 2026. Según la guía de AWS de 2024: pago fijo al partner en dos fases por oportunidad (Scope, con la oportunidad en Business Validation o más, y Launch, cuando la cuenta empieza a consumir), reclamado una vez por trimestre por el total del trimestre anterior, con mínimo de USD 5.000 y máximo de USD 200.000 por trimestre. Se cobra por factura en Payee Central, a 30 días de la aprobación. Las pestañas de CEI se clasifican como HISTÓRICAS.

**F-17. Fila "Funding de AWS confirmados" (S1 › Pagos fila 178) y "MAP 2.0".** → Ro
*Qué vi:* dentro del bloque AWS hay una fila que parece un total ("Funding de AWS confirmados") y una fila "Kigo (XAL) / MAP 2.0".
*Pregunta:* ¿La fila 178 es un cliente, un total o una nota? ¿"MAP 2.0" es un tipo de funding distinto de "POC CASH"?
*Respuesta (Ariel, 18-oct):* "MAP 2.0" es del programa **MAP (Migration Acceleration Program)** de AWS, un programa distinto. La fila 178 no es un cliente: es `IMPORTRANGE` de la planilla de fundings, pestaña "Pagos confirmados", rango `B6:M6`. Son los pagos de funding ya cargados oficialmente, con sign off y fecha de pago. Para el sistema es una fila DERIVADA: no se suma como cobro (sería contarlo dos veces) y sirve como control contra la planilla de fundings, que es la fuente de verdad (F-12).

**F-18. Dos filas "FUNDINGS SHEET".** → Emi
*Qué vi:* en S1 › PROYECCION PAGOS USA hay "FUNDINGS SHEET Proyectados" y "FUNDINGS SHEET Confirmados". El Anexo habla de una sola.
*Pregunta:* ¿Las dos separan bloques? ¿Qué hay entre una y otra?

**F-19. SleakOps factura por la S.A.** → Emi
*Qué vi:* S2 tiene "Pagos ARG" y una fila "TOTAL PAGOS ARG" (Xcons, ~USD 424/mes).
*Pregunta:* ¿Esas facturas siguen la misma regla que las de Craftech S.A. (R25, R23)?

**F-20. Datos sueltos en la fila de Broota.** → Emi
*Qué vi:* S1 › Pagos, fila de Broota: en AQ ("Forma de pago") dice "TARJETA DE CREDITO", y en AR–AW hay números sin encabezado: 2524, 0.3, 123.69, 2400.01, 2400.01, 123.99.
*Pregunta:* ¿Los números de AR–AW son un cálculo de trabajo (comisión de tarjeta) o un dato a importar? ¿"Forma de pago" se carga para otros clientes?

**F-21. Valor ilegible: `814,8` en S2.** → Emi
*Qué vi:* S2 › Pagos, Atlantics, feb-2026: texto `814,8` sin formato.
*Pregunta:* ¿Es USD 814,80? Lo pregunto como ejemplo del tipo de cosa que el sistema va a reportar (R30): ¿quieren que lo reporte y nada más, o que además lo excluya de los totales hasta que alguien lo corrija?

**F-22. Pestaña "Historia" de S1.** → Emi
*Qué vi:* una foto diaria de totales por mes desde el 2/1/2025, automática desde el 19/9/2025, cortada el 1/1/2026. No identifiqué qué total guarda.
*Pregunta:* ¿Qué guarda y quién la armó? ¿Sirve como semilla de historia o la ignoramos?

### No bloquean

**F-23. Objetivos de venta en VENTAS.** → Ro. Hay "Objetivo por Mes", "por Q" y "% Objetivo". ¿Los importamos como meta? ¿Quién los carga?

**F-24. "Pagos en disputa" en Cash Flow.** → Emi. ¿Qué es y se relaciona con RETRASO PAGO?

**F-25. Bloques de escenario en Cash Flow** ("con facturación mínima", "2025 aislado", "Para que modifique ARI"). → Emi. ¿Cuáles son vigentes? Para paridad propongo solo el "Resumen mensual Cash Flow ARG-USA".

**F-26. Regla para proyectar la ganancia imponible de Craftech-io Inc (impuesto del IRS).** → Emi. *(Agregada el 18-oct.)*
*Qué vi:* Ariel quiere preguntarle al sistema "¿cuánto está proyectado de ganancia para el pago de impuestos al IRS?". En Base informe hay pestañas "Tax EEUU 2021…2025" y "Tax EEUU 2025 - calculo para budget", que parecen papeles de trabajo.
*Por qué importa:* es una regla fiscal; el sistema no la puede inventar.
*Qué bloquea:* esa pregunta del chat. Nada de la v0 ni de la paridad.
*Pregunta:* ¿Cómo se calcula hoy la ganancia imponible proyectada de la Inc y en qué pestaña está? ¿Qué tasa y qué fechas de pago se usan? Sin propuesta.

### Lo verifico yo (no pregunto)

Verificado el 18-oct con la service account `finance-bot-ingest@prefab-isotope-287618.iam.gserviceaccount.com`, solo lectura:

- **Rubro "CAJA. Intercompany" en Base informe › Consolidado (D24): existe.** 18 movimientos. Hay 46 rubros distintos; "CCSS" aparece también como rubro propio (37 movimientos), además de como agrupador dentro de "01. Sueldos".
- **F-02, cuál de las dos filas MEP se usa (Ariel pidió que lo averiguara yo):** la conversión a USD de Pagos ARG (filas 29–45) divide por la **fila 27** en todas las celdas (`=B3/B$27`). Las pestañas Pagos y PROYECCION PAGOS USA de "Facturación - Craftech Total" no referencian las filas 23 ni 27: toman las filas 29–45 ya convertidas, así que heredan la fila 27. VENTAS y el Cash Flow no referencian ninguna de las dos. La fila 23 solo se usa dentro de Pagos ARG (157 referencias, en el bloque de proyección de IVA). Las dos filas son idénticas salvo jul-2025 (fila 23: 1.236,42; fila 27: 1.255, igual al "Dólar oficial" de ese mes). **Conclusión:** la MEP operativa es la fila 27; una diferencia entre 23 y 27 se reporta como discrepancia y Emi decide.
- **F-07, mitad verificada:** los rangos con nombre de Base informe son `total_operaciones, total_IT, total_sleakops, total_impuestos, total_legales, total_gerencial, total_comunes, total_GEN_IA, total_finanzas, total_contable, total_DATA, total_activos, total_comercial, total_rrhh, total_deuda_afip, total_marketing, ingresos_financieros`. **No existe `total_devs`.** Sigue abierta la pregunta a Emi de si la fila "Gastos Devs" del P&L es un error.
- **"Costos - Escenario 1": compartida y legible** (14 pestañas). "Costos" también (18 pestañas).
- **Qué expone Google sobre autoría y revisiones (P-06):** con permiso de Lector, `canReadRevisions` es `false` y la lista de revisiones vuelve vacía en las tres planillas probadas. Las planillas están en unidades compartidas (toda llamada a Drive necesita `supportsAllDrives=true`). La Drive Activity API, que da quién editó y cuándo a nivel archivo, estaba deshabilitada; Ariel la habilitó el 18-oct y verifiqué que funciona con permiso de Lector (actividad de la planilla de fundings desde marzo de 2026; los editores vienen como identificadores de perfil, no como nombres). Lo que sigue sin exponerse a un Lector es el historial de versiones; Ariel decidió que la historia de celdas empiece el día del arranque (propuesta, sección 4.4, decisión 3).
- **Fuente del dólar MEP:** Base informe › TC MEP importa de otra planilla (`1VJfYRAi1HWh25ox-xdzBG3fHTvKhBwRz9e3WadYarXw`, pestañas `dolar-mep` y `dolar-mep-completo`) que la service account **no puede abrir** (403). No bloquea: los valores llegan por IMPORTRANGE a Base informe. Es el papel de trabajo "Inflación / dólar" que el v0.9 dice que no se ingiere.

### Ya está en acciones del v0.9 §10 (no lo vuelvo a preguntar)

Sesión de aliases (D18), columna de fund claim ID en S7, fila 59 de S7, extracción de Zoho.

---

**Freno acá.** Espero las respuestas de Ariel (bloque A) y lo que pueda conseguir de Finanzas (bloque B). Con las del bloque A y las F-01 a F-11 ya se puede escribir la Etapa 3 completa; sin ellas, la Etapa 3 puede cubrir la v0 y dejar la paridad abierta.
