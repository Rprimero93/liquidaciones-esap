---
fase_actual: 2
estado_resumen: "Fase 2 cerrada (estructura y estilo) — Fase 3 por iniciar"
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
- Fase 2 (Estructura y estilo): **completa** (2026-11-23) — `src/index.html` + `js/` (`app`, `store`, `router`, `format`) + `views/` (`tablero`, `consulta`, `ficha`, con contenido base) + `styles/app.css`; tokens, estilo y Sidebar/Button/Toast copiados de Design_System_Core. Validación: `python pruebas/validar_app.py 2` 36/36 (escritorio + celular emulado).
  - `store.js` es la única puerta a los datos: `localStorage` manda sobre la semilla; la insignia del encabezado muestra el origen.
  - Hallazgos en `<ds-sidebar>` de Design_System_Core (no se editó la referencia — Regla 3): (1) `::slotted(a) svg` no es un selector válido y los íconos salían sin tamaño → resuelto en `app.css`; (2) `display` de `.sidebar`/`.icon-button` anula `[hidden]` (el botón de reapertura se veía siempre y "cerrar" no ocultaba el menú) → parche comentado en la copia local; (3) `--color-accent-surface` no existe en `minimalista-corporativo` → el activo se marca desde `app.css`. Candidatos a llevar a Design_System_Core.
- Fase 3 (Consulta): **pendiente**.

## Bloqueos

- Ninguno.

## Siguiente paso

Fase 3 — búsqueda (número, contratista) y filtros (responsable, estado) con Dropdown en la Consulta.
