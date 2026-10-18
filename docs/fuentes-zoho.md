# Fuente externa: Zoho Invoice (Craftech-io Inc)

**Fecha del backup:** 17 oct 2026 · **Origen:** Zoho Invoice › Settings › Data Backup, pedido por Ariel.
**Dónde está:** el zip original en `~/Downloads/Craftech-io, Inc._2026-10-17.zip`. Conviene moverlo a una carpeta fuera del repo (por ejemplo `~/repos/craftech-os-data/zoho/`). No se sube al repo porque tiene razones sociales, direcciones y montos por cliente.

Este documento describe la estructura y lo que encontré. No tiene datos de clientes.

## Qué trae el backup

| Archivo | Filas útiles | Qué es |
|---|---|---|
| `Contacts.csv` | 54 clientes | Razón social (Company Name), nombre visible (Display Name), plazo de pago, moneda, dirección de facturación, país, tipo y número de Tax ID (campos custom "CF.Código Tax ID" y "CF.TIPO DE TAX ID"), mail del contacto. |
| `Contact_Persons.csv` | 53 | Personas de contacto por cliente. |
| `Invoice.csv` | 432 facturas (526 líneas) | Feb-2024 a oct-2026. Una fila por ítem; la factura se identifica por Invoice Number. Fecha, vencimiento, estado, total, saldo, plazo de pago, ítem, cantidad, precio, nombre del perfil recurrente si lo hay. |
| `Customer_Payment.csv` | 422 pagos | Fecha, monto, modo (390 transferencia, 16 efectivo, 9 Stripe, 7 remesa), factura a la que se aplicó. |
| `Recurring_Invoice.csv` | 33 perfiles | 10 activos, 18 vencidos, 5 inactivos. Mensuales salvo uno semanal. Son lo que HubSpot Invoices tiene que reemplazar. |
| `Credit_Note.csv` | 12 | Notas de crédito. |
| `Item.csv` | 9 | Catálogo de servicios (Managed DevOps Team full/part time, Cloud Infrastructure Project, MSP, Support, Extra hours, etc.). |
| `Activity Logs.csv` | ~3.000 | Historial de acciones en Zoho (quién hizo qué y cuándo). Útil para historia. |
| Quote, Expense, Projects, Timesheet, Sales Receipt, Refund, Price lists | vacíos | No se usan. |

## Lo que resuelve

- **Razones sociales de los clientes de la Inc** (acción pendiente de Emi en el documento base): están en `Contacts.csv`. 54 clientes, todos activos, todos en USD. Solo en 1 caso el nombre visible difiere de la razón social.
- **Plazos de pago por cliente:** 33 clientes "Net 10" y 21 "Due on Receipt". El documento base asume 10 días por default con excepciones de 30: en Zoho **no hay ningún cliente a 30 días** entre los contactos; sí hay un perfil recurrente "Net 30 days" y 3 con plazo "Custom". A confirmar con Emi.
- **Tax ID:** el tipo está cargado en 15 clientes (EIN, RFC, RUT, NIF; uno dice "IBM", que parece error de tipeo). El resto está vacío.
- **Historia de facturación de la Inc 2024–2026** con fecha de emisión, vencimiento y pago real por factura. Es una fuente independiente de la planilla para validar la pestaña Pagos.

## Lo que encontré y queda para preguntar

- **Los totales mensuales de Zoho no coinciden exactamente con la fila "TOTAL PAGOS USA" de Facturación - Craftech Total › Pagos.** Ejemplos: ene-2025 Zoho 51.012 vs planilla 55.500; jun-2025 Zoho 135.442 vs planilla 139.175; sep-2026 Zoho 44.933 vs planilla 49.821. La diferencia puede ser por facturas que no pasan por Zoho (Marketplace, Stripe directo) o por el mes en que se cuenta cada factura. Hay que entenderlo antes de usar Zoho como control de paridad.
- **Ninguna factura tiene vendedor cargado** (campo "Sales person" vacío en las 432). Zoho no sirve para la atribución de comisiones.
- **144 líneas de factura no tienen ítem** (texto libre en la descripción). Para mapear facturas a líneas de servicio hace falta leer la descripción.
- **Nombres:** los Display Name de Zoho son razones sociales, no los nombres de fantasía de las planillas. La sesión de aliases (nombre de fantasía ↔ razón social) sigue siendo necesaria; Zoho aporta el lado legal.

## Uso previsto en la propuesta

- `Contacts.csv` → semilla de `Client.legalName`, `Client.paymentTermsDays`, `Client.taxId` para clientes de la Inc.
- `Invoice.csv` + `Customer_Payment.csv` → segunda fuente para reconstruir `Invoice` e `InvoicePayment` de la Inc 2024–2026 y cruzarlas con la grilla de colores de la planilla.
- `Recurring_Invoice.csv` → lista de lo recurrente que HubSpot Invoices tiene que cubrir (riesgo anotado en el documento base).
