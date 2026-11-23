---
fase_actual: 5
estado_resumen: "Fase 5 cerrada (tablero) — Fase 6 por iniciar"
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
- Fase 3 (Consulta): **completa** (2026-11-23) — búsqueda sin tildes (número, contratista, responsable), filtros por responsable y estado con `<ds-dropdown>`, chips de estado, etapa actual por contrato, filtros conservados al volver de la ficha. Validación: `python pruebas/validar_app.py` 82/82.
  - **Estado derivado** (la columna Estado del Excel está vacía en los 26): Sin seguimiento (sin tarjeta) > Cerrado (12/12) > Paralizado (alerta 1 activa) > En trámite. Resultado en la semilla: 12 en trámite, 5 paralizados, 8 cerrados, 1 sin seguimiento. Etapa actual = primer paso sin marcar.
  - Responsables separados de las celdas combinadas (", ", " y ", " - "): 14 individuales. Se calcula en `store.js`; la semilla queda fiel al Excel.
  - Tokens propios de la app para colores de estado (`--status-*`, el estilo no los trae), contraste verificado ≥ 7:1.
  - Hallazgo en `<ds-dropdown>` de Design_System_Core: `.panel { display: flex }` anula el `display: none` de un popover cerrado → el panel cerrado quedaba fijo en pantalla tapando los clics de la lista. Parche comentado en la copia local; mismo patrón que el `[hidden]` de la Sidebar (Fase 2). Candidato a llevar a Design_System_Core.
- Fase 4 (Ficha del contrato): **completa** (2026-11-23) — ficha editable: 12 pasos (clic para marcar/desmarcar, botón "Marcar como completado" en la etapa actual), 4 alertas, fechas con `<ds-datepicker>` (con el texto original del Excel cuando la fecha era ilegible), enlace a SECOP, bitácora (más reciente primero, origen Excel/Nota/App) con alta de observaciones, "Iniciar seguimiento" para el contrato sin tarjeta. Cada cambio se guarda solo y se confirma con un aviso (con "Deshacer" en pasos y alertas). Validación: `python pruebas/validar_app.py` 112/112.
  - **Decisión — pasos con `<ds-step>` sin `<ds-stepper>`:** el contenedor es un asistente que obliga a avanzar en orden y fija el estado de cada paso por navegación; el Excel tiene pasos marcados fuera de orden. Se usa `<ds-step>` suelto con el estado puesto por la app (completed / current = etapa actual / pending). Alternativa descartada: checklist propio (perdía la coherencia visual con el sistema). Impacto: ninguno en el Core; reversible.
  - `store.save()` ya no repinta la vista (la ficha se actualiza por secciones, sin perder foco ni scroll); `reset()` sí avisa. El aviso flotante pasó a `js/ui.js` para evitar una importación circular con `app.js`.
  - Validación: se corrigieron dos carreras de la prueba (no de la app): el calendario se cierra al hacer scroll, así que se centra el campo antes de abrirlo; y el enlace activo se espera tras `hashchange`. Un `ERR_CONNECTION_REFUSED` apareció una vez en móvil y no se repitió en 5 corridas: la prueba ahora registra la URL de toda solicitud fallida.
- Fase 5 (Tablero): **completa** (2026-11-23) — 4 KPIs (contratos, avance general, cerrados con paralizados/en trámite, competencia vencida), barras horizontales de avance por responsable (una serie, color de acento, etiqueta directa, tooltip con cursor o foco; entran una por una de mayor a menor con barrido a la derecha, sin animación con movimiento reducido) y semáforo de pérdida de competencia de los contratos sin cerrar (Vencido / Menos de 90 días / En plazo / Sin fecha, con ícono y texto). Validación: `python pruebas/validar_app.py` 146/146.
  - **Corrección de cálculo:** los promedios se calculaban sumando fracciones (0,5833…) y el error de punto flotante cambiaba el redondeo (68,75 % se mostraba 68,7 %). Ahora `store.js` promedia con enteros: pasos hechos / pasos posibles. Lo detectó la prueba al comparar contra Python.
  - Umbral "próximo a vencer" = 90 días (`store.DEADLINE_WARN_DAYS`), ajustable en un solo punto.
  - Dato a la vista con la semilla (2026-11-23): 11 de los 17 contratos sin cerrar ya pasaron su fecha de pérdida de competencia, 0 vencen en los próximos 90 días, 4 en plazo y 3 sin fecha.
- Fase 6 (Respaldo): **pendiente**.

## Bloqueos

- Ninguno.

## Siguiente paso

Fase 6 — exportar e importar JSON (y restablecer a los datos del Excel).
