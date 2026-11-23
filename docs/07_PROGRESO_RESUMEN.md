---
fase_actual: 1
estado_resumen: "Fase 1 cerrada (extracción de datos) — Fase 2 por iniciar"
tolerancias_excedidas: 0
fases_reabiertas: 0
---
# Progreso — Resumen — Liquidaciones_ESAP

> Cargar junto con `01_INDEX.md` al iniciar cualquier tarea sobre este proyecto.
> Última actualización: 2026-11-23.

## Estado actual

- Fase 0 (Setup de contexto): **completa** — 4 docs creados y fila en `INVENTARIO_Web.md`. Decisiones: estilo `minimalista-corporativo`, usuario único, prototipo con los datos del Excel (`localStorage` + exportar/importar JSON), Git en la bóveda, GitHub Pages a decidir tras la Fase 7.
- Fase 1 (Extracción de datos): **completa** (2026-11-23) — `scripts/extraer_excel.py` → `data/seed.json`: 26 contratos (25 con tarjeta), 12 pasos, 4 alertas, 284 entradas de bitácora (265 con fecha). Validación: `python -m pytest pruebas` 13/13.
  - Las tarjetas se ubican por la celda ancla "Perdida de competencia", no por filas fijas; el cruce tarjeta↔contrato es por contratista normalizado y el id del contrato se canoniza (`BOG- 1588 -2019` → `BOG-1588-2019`).
  - Hallazgo: el avance general del Excel (K2 = 72,2 %) omite la tarjeta J30 (`BOG-769-2022`, 25 %); sobre las 25 tarjetas es **70,3 %**. La app calculará este último.
  - Datos por revisar en la app (no se corrigen en la extracción): `BOG-588-2019` plazo "31/06/2022" (fecha inválida → vacío); `BOG-1220-2023` y `BOG-1190-2024` sin fecha de pérdida de competencia; `BOG-1836-2023` y `BOG-1843-2023` con plazo de cierre incoherente con la pérdida de competencia; 4 contratos con nota propia en el paso 10 ("No aplica"/"No requiere"), conservada en `etiqueta`.
- Fase 2 (Estructura y estilo): **pendiente**.

## Bloqueos

- Ninguno.

## Siguiente paso

Fase 2 — base de la app con Sidebar, tokens + `minimalista-corporativo`, capa de datos (semilla + `localStorage`) y navegación por `#ruta`.
