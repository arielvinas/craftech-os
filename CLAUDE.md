# Craftech OS — índice del repo

Sistema de registro de los compromisos financieros de Craftech. Este archivo es un índice; el contenido vive en los documentos.

## Dónde está cada cosa

- `docs/KICKOFF.md`: el encargo original y las reglas de trabajo (etapas, nunca escribir en las planillas, preguntar antes de asumir).
- `docs/v0.9.md`: reglas de negocio vinculantes (glosario, fuentes, reglas R1–R39, anexo).
- `docs/01-understanding.md`, `docs/02-questions.md`, `docs/03-proposal.md`: las tres etapas del arranque. La propuesta está **aprobada por Ariel el 18-oct-2026** con sus diez decisiones en la sección 11.
- `plan/`: PRDs, ADRs y tickets producidos por las skills (`/architect`, `/ticket`, `/coordinate`). Es la fuente de verdad del desarrollo a partir de acá.

## Estado (18-oct-2026)

Siguiente paso: `/architect docs/03-proposal.md`. Todavía no hay código aprobado ni PRDs.

## Spike descartado: no usar

La rama `spike/stage-a` contiene un intento de especificaciones (`docs/specs/`) y código (`app/`, `infra/`, `config/`, `scripts/`) escrito el 18-oct-2026 directamente desde la propuesta, **antes de la revisión de arquitectura y sin PRDs**. Ariel lo descartó para empezar fresco. Para cualquier agente, arquitecto o skill: **esa rama no es un diseño vigente ni una restricción**; no la leas como base, no la cites como "lo que ya existe" y no la reutilices sin que Ariel lo pida explícitamente. Lo único que vale de ese intento son los hechos medidos, que ya están registrados en `docs/03-proposal.md` (Anexo B) y en `docs/02-questions.md`.

Quedaron en la máquina de Ariel, fuera del repo: un volumen de Docker `craftech-os_pgdata_v1` con una importación de prueba de las planillas (se puede borrar con `docker volume rm craftech-os_pgdata_v1`), las imágenes `craftech-os-worker` y `craftech-os-api`, y `infra/.env` (ignorado por git).

## Reglas que no cambian

- Español con Ariel y en `docs/` y `plan/`; código y commits en inglés con los términos de Craftech en español.
- Nunca escribir en Google Sheets ni en Drive; nada instalado en las planillas.
- Las reglas financieras las ratifican Emi y Ro; lo no ratificado se guarda, no se interpreta.
- Datos de clientes, sueldos y la clave de la cuenta de servicio nunca entran al repo.
- Chat e inteligencia artificial sobre los datos: desde Claude Desktop vía un servidor MCP; la app propia es solo visualización.
