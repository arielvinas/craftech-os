# Craftech OS — Kickoff

Este archivo es el punto de partida de un proyecto nuevo. No existe código previo, ni PRDs, ni decisiones de diseño heredadas. Si encontrás en tu memoria, en otro repo o en cualquier documento referencias a un "Craftech OS" anterior (PRD-01, PRD-02, milestones, tickets T-xxx, relevamientos de planillas), ignoralas: fueron un experimento descartado.

Tu trabajo en esta primera etapa es **entender, preguntar y proponer**. No escribas código hasta que Ariel apruebe tu propuesta.

---

## 1. Quién soy y qué es Craftech

Soy Ariel Viñas, CEO y cofundador de Craftech (craftech.io): servicios cloud y DevOps sobre AWS para fintechs y scaleups de LatAm, ~57 personas, AWS Advanced Partner. Dos líneas de negocio:

- **Craftech Services:** equipos DevOps gestionados (cobro por horas reservadas + variable por exceso), proyectos de infraestructura a precio fijo, MSP. Mucho del negocio viene apalancado en programas de AWS (MAP, POCs, fundings).
- **SleakOps:** PaaS propia sobre AWS, vendida por suscripción vía AWS Marketplace.

Dos entidades legales: **Craftech S.A.** (Argentina, factura en ARS por Bejerman/AFIP) y **Craftech-io Inc** (EEUU, factura en USD). Todos los contratos son en USD.

## 2. La intención: qué quiero lograr

Quiero un **sistema operativo de Craftech**: el lugar donde todos entramos a trabajar, vemos nuestras prioridades y deadlines, y sabemos en tiempo real cómo viene la empresa.

**Empieza por finanzas y contabilidad**: ventas, facturación, cobros, pagos, gastos, cashflow, budgets, sueldos. Pero tiene que estar pensado desde el día uno para extenderse a otras áreas: AWS (programas, fundings, nuestro acuerdo SCA con sus metas, competencias en curso), comercial y ventas, marketing, RRHH, operaciones, delivery y proyectos de clientes, OKRs.

### El problema de hoy

- Toda la información financiera vive en Google Sheets que se cargan a mano, cada uno a su manera, con estados manejados por colores de celda. Nadie fuera de Finanzas lo entiende.
- No veo casi ninguna variable en tiempo real. Me entero de lo que pasa cuando alguien actualiza las planillas. No sé si alguien cargó un gasto nuevo, si alguien necesita plata para algo, si se atrasaron los pagos y por qué, cuánta plata hace falta para X. Todo lo estimo en mi cabeza o jugando con fórmulas.
- No sé por qué algo está frenado. Un deal puede no aparecer en los números porque falta firmar el contrato o porque falta cargar el funding en AWS Partner Central, y eso no está escrito en ningún lado.
- No hay historial: si alguien cambia un budget o una proyección, solo queda el historial de versiones de Google Sheets. No puedo ver cómo fue creciendo la facturación durante el año.
- Mucho conocimiento vive en cabezas, en Slack y en mails, no en un sistema.

### Lo que quiero

- **Que el sistema termine siendo la fuente de todo.** Cualquier movimiento, pedido de budget o gasto se registra ahí, y de ahí salen las vistas y la información que cada uno necesite.
- **Historial completo** de cada cambio: quién, cuándo, por qué. Poder ver cómo evolucionó cualquier número en el tiempo.
- **Flujos de aprobación y alertas** sobre lo que va pasando (un budget pedido, un pago atrasado, algo trabado).
- **Que lo frenado tenga dueño y motivo visible.** Ejemplo: cuando un deal pasa a Committed en HubSpot arranca lo operativo (escribir el contrato, que idealmente se genere solo; pedir el funding a AWS; pedir el upfront al cliente). Quiero ver qué falta y quién lo tiene.
- **Importar todo lo que hoy está en las planillas**, y poder agregar el conocimiento que todavía recordamos, para que quede en el sistema y siga creciendo ahí.
- **Escenarios y análisis:** hoy juego con estimaciones en los Excel. Quiero hacerlo en el sistema, o preguntándole a una IA que acceda a toda la información sabiendo que está bien estructurada. Las simulaciones nunca deben modificar los datos reales.
- **Medir lo que hoy no se ve**, por ejemplo horas que los equipos consumen por encima del contrato sin autorización del cliente y que no se facturan.
- Más adelante: un lugar para trabajar iniciativas de marketing (ideas para generar demanda o mejorar la marca, con dueño, revisión y medición de si rinden), incluyendo el trabajo sobre las cuentas que nos comparten los ejecutivos de AWS.
- Que sea **un lugar lindo para trabajar**, para estar al día y para pensar cómo mejorar la empresa cada día.

### Cómo tiene que convivir con la operación actual

- **Hoy no cambia nada de la operación.** Finanzas sigue cargando en sus planillas. El sistema ingiere los datos de las planillas de forma continua hasta que sea lo suficientemente robusto como para dejarlas. No hay fecha para eso; hay criterio.
- Las planillas de trabajo personales de Emiliana (proyecciones de inflación, cálculos para transferencias, etc.) no se tocan.
- El sistema nunca corrige una planilla: si encuentra algo raro, lo reporta y Finanzas decide.
- **Primera etapa: replicar al 100% lo que hace hoy Finanzas**, incluso lo que falta o se hace distinto de lo ideal (por ejemplo, el P&L actual no incluye cargas sociales). Si ves algo mejorable, lo anotás como mejora; no lo "arreglás" en el modelo. Las mejoras se aplican recién cuando el P&L y el cashflow del sistema coinciden con los de Finanzas.
- Además de ingerir, tiene que permitir **enriquecer** los datos con información que las planillas no tienen, sin que se pierda cuando la planilla cambia.

### Objetivo de la v0 (lo primero que tiene que funcionar)

1. **Importar todo** lo que hoy está en las Google Sheets de la sección 6, con toda su historia.
2. **Seguir importando de forma continua.** Las planillas se siguen cargando todos los días; el sistema tiene que reflejar cada cambio sin que nadie tenga que hacer nada distinto.
3. **Que cualquier cambio en las planillas se vea.** Qué cambió (celda, valor anterior y nuevo, color), en qué planilla y pestaña, cuándo y, si la fuente lo permite, quién. Un monto nuevo, una celda que cambia de color, una fila que se borra, una fórmula pisada a mano: todo queda registrado y visible para Ariel y Finanzas. Esto es lo que hoy no tenemos.
4. **Reportar lo que no se puede interpretar** (filas inválidas, valores ilegibles, contradicciones entre planillas) en vez de adivinar.

Ese es el piso. Sobre eso se construye la paridad (P&L y cashflow iguales a los de Finanzas) y después, de a poco, el sistema le va **sacando responsabilidad a los Excel**: un tipo de dato por vez pasa a cargarse y vivir en el sistema, y la planilla queda como vista o se deja de usar.

### Decisiones ya tomadas

- **HubSpot** sigue siendo el CRM. Para Craftech-io Inc, las facturas se van a emitir desde HubSpot y se deja de usar Zoho Invoice. **Bejerman/AFIP** sigue para Craftech S.A.
- Un deal en **Committed** dispara lo operativo; pasa a **Launched** cuando el proyecto arrancó, el funding está en cash claim, el contrato firmado y el upfront pagado. No se agregan stages en HubSpot.
- HubSpot, Notion, Jira, Slack y Partner Central se integran más adelante; no se reemplazan ahora.

## 3. Quiénes lo usan

- **Emiliana (Emi):** contadora. Dueña de las planillas financieras y del P&L.
- **Sofía (Sofi):** licenciada en administración. Opera Bejerman, bancos y conciliación.
- **Rocío (Ro):** Directora General, sin formación en administración. Carga ventas, pagos y el tracker de fundings de AWS casi a diario.
- **Ariel:** CEO. Quiere visibilidad, escenarios y análisis.
- Después: líderes de área (pedidos de budget), comercial, delivery, toda la empresa.

## 4. Restricciones

- **Lo construye Ariel con Claude Code**, pero tiene que poder evolucionarlo y mantenerlo cualquier persona de Craftech (equipo con perfil DevOps/AWS).
- **Sin licencias** que haya que pagar para que sea robusto. Customizable a nuestro gusto. Puede correr en nuestra cuenta de AWS.
- **Tiempos:** las primeras cosas útiles en pocas semanas (al menos estar por encima de las finanzas de la empresa de forma adecuada); el proyecto ambicioso completo hacia fin de año.
- **Gobernanza de reglas:** las reglas de negocio financieras las deciden y ratifican Emi y Ro. Ni Ariel ni vos las asumen. Si te falta una regla, la preguntás; no elegís un default.

## 5. Reglas de negocio

Están en el documento **"Craftech OS — Documento base v0.9"**:
https://docs.google.com/document/d/1_IosGkhd-mmv_77kpl-OR_aA22NxbHKyd58yWIIn_do/edit
(si no podés leer Drive, está exportado en `docs/v0.9.md`).

De ese documento, son **vinculantes**:

- **Sección 2 (Glosario):** el vocabulario de Craftech. Usalo; no lo "corrijas".
- **Sección 3 (Fuentes):** qué planilla tiene qué, quién la carga, qué se ingiere y qué no.
- **Sección 6 (Reglas R1–R39):** cada regla tiene estado. Las RATIFICADAS son ley. Las PROPUESTAS se respetan salvo que Finanzas diga otra cosa. Si alguna regla quedara ABIERTA, no se implementa hasta que se decida.
- **Sección 8.1 (Mejoras registradas):** cosas que Finanzas hoy no hace y que quedan para después de la paridad. No se implementan en la primera etapa, pero el modelo no debería impedirlas.
- **Sección 9 (Pendientes):** confirmaciones y datos que faltan; ninguno bloquea.
- **Anexo (Cuidados al editar las planillas):** para no romper la lectura de las planillas.

Son **referencia, no mandato** (fueron un diseño anterior; diseñá el tuyo y después, si querés, compará): sección 1.1 (principios), 4 (entidades), 5 (eventos) y 7 (workflows). La sección 0 es solo el changelog respecto de la versión anterior.

## 6. Fuentes de datos actuales (solo lectura)

| Fuente | Link |
|---|---|
| S1 — Facturación Craftech Total | https://docs.google.com/spreadsheets/d/19nWa8BtfYWAiJVb9njvBD9_c0Y8EbgZbS_aKR-4-cZM |
| S2 — Facturación SleakOps Total | https://docs.google.com/spreadsheets/d/1rPqqCF6bZ7m6u4ZwqLL93N_Zp2Uc-epEmGm6P3kMGV8 |
| S7 — Tracker de fundings (Ro) | pedírselo a Ariel |
| P&L Completo | https://docs.google.com/spreadsheets/d/163llheLfMbyf_2dcAD1eGRFBVYEvvhMM4eCE6oQnll4 |
| Cash Flow Mensual | https://docs.google.com/spreadsheets/d/1xHuASliiA2vVdPzqAanokAjouSof0vZz757fVMojBI4 |
| Base informe Craftech (movimientos bancarios) | https://docs.google.com/spreadsheets/d/1rB4LnQ14cf3kNxtkQKrC9QMAP5_6naMoZPqaRrnnOBQ |
| Proyección sueldos | https://docs.google.com/spreadsheets/d/1cwkrNg_SWDDDy_H_zsAqE05wOUFR-9XDVF42-IUvnb0 |
| Base sueldos (histórico y actual) | https://docs.google.com/spreadsheets/d/1qr0cxhxR9n0qbKP8taOgQ9MjkPpeKiD6podz7ypcatM |
| Sueldos EEUU | https://docs.google.com/spreadsheets/d/1RZF9nB6isLeupeMzpdI2t6C04PRog3On-n02lhIRnOw |
| Budget | https://docs.google.com/spreadsheets/d/1q6xyHfsF3t4n4hiz2Cb0vSCQlK2ksvrY0eIVjuLwI98 |

Nunca escribas en estas planillas.

## 7. Cómo trabajar

### Etapa 1 — Entender (sin código)

1. Leé este archivo y el v0.9 completos.
2. Si tenés acceso, recorré las planillas para entender su estructura real. Todo lo que encuentres que contradiga el v0.9, anotalo; no lo resuelvas vos.
3. Escribí `docs/01-understanding.md`: tu versión, con tus palabras, de la intención (sección 2) y de cómo funciona hoy el circuito financiero. Si algo de lo que entendiste no está escrito explícitamente en este archivo o en el v0.9, marcalo como inferencia.

### Etapa 2 — Preguntar

Escribí `docs/02-questions.md`, separado en dos:

- **Preguntas de producto para Ariel:** prioridades, alcance, experiencia de uso, qué significa "útil en pocas semanas".
- **Preguntas de reglas para Finanzas (Emi, Ro, Sofi):** todo lo que necesitás saber y el v0.9 no define, más las contradicciones que encontraste en las planillas. Cada pregunta con: qué viste, por qué importa, qué bloquea, y tu propuesta si tenés una.

Pará acá y esperá las respuestas de Ariel antes de seguir.

### Etapa 3 — Proponer

Con las respuestas, escribí `docs/03-proposal.md`:

- **Arquitectura y stack**, con el porqué de cada elección frente a las restricciones de la sección 4. Incluí qué descartaste y por qué.
- **Modelo de datos conceptual** que cumpla la intención: historial completo, ingesta continua desde planillas, enriquecimiento que sobreviva a cambios en la planilla, extensión a otras áreas sin rediseñar.
- **Cómo resolvés la v0** (sección 2, "Objetivo de la v0"): cómo importás la historia completa, cada cuánto y cómo leés las planillas después, cómo detectás qué cambió (incluidos colores y filas borradas), qué podés saber de quién lo cambió con las APIs de Google, y cómo lo ve la gente.
- **Cómo se va a ver y usar**: qué hace cada persona de la sección 3 en el sistema el día uno.
- **Desglose en etapas y entregables** que vos consideres correctos (módulos, PRDs o como prefieras organizarlo), con lo que se puede tener en pocas semanas y lo que va a fin de año.
- **Trazabilidad:** cada regla R1–R39 mapeada a la parte de la propuesta que la cumple, o marcada como fuera de la primera etapa con motivo.
- **Riesgos** y cómo los mitigás.

Pará y esperá la aprobación de Ariel. Recién con la propuesta aprobada se escriben especificaciones detalladas y código.

## 8. Reglas de comportamiento

- Nunca asumas una regla de negocio. Preguntá.
- Nunca escribas en las planillas ni en Drive.
- Si algo de este archivo te parece mal pensado o contradictorio, decilo. Prefiero que me cuestiones a que ejecutes algo que no cierra.
- Respondé en español a Ariel. La documentación técnica puede ir en inglés si lo proponés, preservando los términos de Craftech en español.
