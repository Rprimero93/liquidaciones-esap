---
tecnologia: Web
tipo: entregable
proyecto: Liquidaciones_ESAP
estado: pendiente
estado_resumen: "Fase 5 cerrada (tablero) — Fase 6 (respaldo) por iniciar"
stack: "HTML/CSS/JS vanilla + Design_System_Core (minimalista-corporativo) + localStorage; extracción con Python (openpyxl)"
descripcion: "Micro app web de seguimiento de la liquidación de contratos ESAP (12 pasos, alertas, pérdida de competencia, bitácora, SECOP), migrada desde liquidacion.xlsm"
aliases: [Liquidaciones_ESAP]
---

# Liquidaciones_ESAP — README

> Ubicación: `Entregables/Web/`.
> Última revisión: 2026-11-23.

## Propósito

Reemplazar el libro `liquidacion.xlsm` (seguimiento de la liquidación de contratos de la ESAP) por una micro app web con tres pantallas: **Tablero** (avance general, avance por responsable, semáforo de pérdida de competencia), **Consulta** (búsqueda y filtros) y **Ficha del contrato** (12 pasos, 4 alertas, bitácora de observaciones, fechas, enlace a SECOP).

## Origen

Fuente: `C:\Users\Rprim\Documents\proyectos esap\liquidacion.xlsm` — solo lectura, nunca se modifica.

| Hoja | Contenido |
|---|---|
| `Contratos` | 26 filas: N° contrato, contratista, responsable, porcentaje (enlazado), estado, última observación, documento activo |
| `Liquidaciones ` | Una tarjeta por contrato en celdas (4 por bloque de 30 filas): pérdida de competencia, plazo de cierre, 12 pasos con casilla, observación, nota, 4 alertas, valor, link SECOP; avance = casillas marcadas / 12 |
| `Consultar` | Vacía |
| Macros | Sin código; solo un `UserForm1` sin terminar (Contrato, Objeto, Avances, casillas) |

Hallazgos que la app corrige:

- El porcentaje general suma 24 celdas fijas y divide entre 24, con 26 contratos; `BOG-759-2022` no tiene tarjeta.
- Las tarjetas buscan el contrato por el nombre del contratista escrito dos veces (`XLOOKUP` por texto).
- El plazo de cierre es texto, no fecha.
- La observación es una sola celda: se pierde el historial.

## Alcance

- Prototipo para un solo usuario (Ricardo), sin autenticación ni backend.
- Datos de prueba = los del Excel, extraídos por `extraer_excel.py` a `data/seed.json` (reproducible).
- Edición en la app; los cambios persisten en `localStorage`, con exportar/importar JSON como respaldo.
- Estilo `minimalista-corporativo` de Design_System_Core; componentes: Sidebar, Stepper, Dropdown, Datepicker, Toast, Button.

**Fuera de alcance:** SharePoint, Power Automate, multiusuario, publicación (se decide después de la Fase 7).

## Referencias (Regla 3 — no se editan)

- [[Herramientas/Web/Design_System_Core/docs/00_README|Design_System_Core]] — fuente de componentes y estilo.
- [[Entregables/Web/Form_Comisiones/docs/00_README|Form_Comisiones]] — guía de estructura (ESAP, 6 componentes adaptados, historial/tablero).

## Cómo abrirla

Desde la carpeta del proyecto: `python -m http.server 8000` y abrir `http://localhost:8000/src/index.html` (los módulos JS y la semilla no cargan con doble clic en el archivo).

## Git

Se versiona en el repositorio de la bóveda (Regla 12, caso 1).

## Pruebas

- Extracción: prueba que compara `seed.json` contra el Excel (mismos contratos, mismo avance por contrato), con los conteos leídos de los datos.
- App: Playwright con el Edge del sistema, escritorio y celular emulado (preferencias de `INVENTARIO_Web.md`).

## Riesgos

- **Datos reales:** nombres de contratistas, responsables y valores. Si se publica en GitHub Pages, hace falta repo propio (Regla 12, caso 3) y datos anonimizados. Se decide al terminar la Fase 7.
