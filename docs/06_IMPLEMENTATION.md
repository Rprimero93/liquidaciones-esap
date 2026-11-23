# Implementación — Liquidaciones_ESAP

> Checklist de fases. Cada fase cierra solo al cumplir sus criterios y quedar registrada en `07_PROGRESO_RESUMEN.md`.
> Checkbox: `[ ]` no iniciada · `[~]` construida, validación pendiente (no es un cierre) · `[x]` cerrada — criterios cumplidos y validación registrada (Regla 2).

- [x] **Fase 0 — Setup de contexto.** `docs/` mínimo viable (`00_README`, `01_INDEX`, `06_IMPLEMENTATION`, `07_PROGRESO_RESUMEN`) y fila en `INVENTARIO_Web.md`. Con Git en la bóveda.
  - Criterio: los 4 docs existen y reflejan las decisiones de descubrimiento; la fila del inventario existe. **Cumplido.**

- [x] **Fase 1 — Extracción de datos.** Script `extraer_excel.py` (openpyxl, solo lectura) que genera `data/seed.json` normalizado: contratos, catálogo de pasos y alertas, avances por contrato y bitácora (observación/nota inicial).
  - Criterio: `seed.json` incluye todos los contratos de la hoja `Contratos` (los sin tarjeta, marcados como tal); la prueba compara contra el Excel el número de contratos y el avance por contrato, con conteos leídos de los datos.
  - **Cumplido: sí** — 26 contratos (25 con tarjeta, `BOG-759-2022` marcado sin tarjeta), 0 tarjetas sin cruzar, 284 entradas de bitácora; `pytest pruebas` 13/13 (contratos, cruce de tarjetas, avance = valor calculado por Excel en cada contrato, estructura, bitácora, fechas, seed al día).

- [x] **Fase 2 — Estructura y estilo.** Base de la app con Sidebar, tokens + `minimalista-corporativo`, capa de datos (semilla + `localStorage`) y navegación por `#ruta`.
  - Criterio: las 3 rutas cargan desde la Sidebar, el estilo activo es el minimalista y los datos se leen de la semilla; 0 errores de consola.
  - **Cumplido: sí** — `python pruebas/validar_app.py 2` 36/36 en escritorio y celular emulado: estilo activo, 3 rutas desde la Sidebar, ficha por enlace y por URL directa, ruta desconocida → tablero, conteos y avance general (70,3 %) leídos de la semilla, Sidebar (íconos, cerrar/reabrir, una fila en móvil), 0 errores de consola.

- [x] **Fase 3 — Consulta.** Lista de contratos con búsqueda (número, contratista) y filtros (responsable, estado) con Dropdown.
  - Criterio: búsqueda y filtros, solos y combinados, reducen la lista correctamente; conteo leído de los datos; estados vacíos correctos.
  - **Cumplido: sí** — `python pruebas/validar_app.py` 82/82 (fases 2 y 3, escritorio + celular emulado): búsqueda por número (con y sin espacios/guiones), por contratista sin tildes, sin resultados; filtro por responsable individual (incluidos los de celdas combinadas) y por cada estado, solos y combinados, contra lo esperado calculado desde la semilla; estado vacío, limpiar filtros, filtros conservados al volver de la ficha, contraste de chips ≥ 7:1, 0 errores de consola.

- [x] **Fase 4 — Ficha del contrato.** Stepper de 12 pasos, 4 alertas, bitácora con fecha, fechas editables con Datepicker, enlace a SECOP, Toast al guardar.
  - Criterio: marcar pasos recalcula el avance; los cambios persisten al recargar; la bitácora conserva el historial.
  - **Cumplido: sí** — `python pruebas/validar_app.py` 112/112 (fases 2-4, escritorio + celular emulado; 3 corridas seguidas en verde): estados de los 12 pasos según la semilla, marcar/desmarcar recalcula el avance, deshacer desde el aviso, alertas, fecha elegida en el calendario, bitácora (vacía no se agrega; nueva queda primera), todo persiste al recargar, la consulta refleja el avance editado, texto original del plazo ilegible, "Iniciar seguimiento" en el contrato sin tarjeta. Pasos con `<ds-step>` sin `<ds-stepper>` (ver `07`).

- [x] **Fase 5 — Tablero.** Avance general calculado de los datos, avance por responsable (barras animadas una por una, de mayor a menor) y semáforo por días a la pérdida de competencia.
  - Criterio: el avance general coincide con el promedio de todos los contratos; el semáforo clasifica según la fecha actual.
  - **Cumplido: sí** — `python pruebas/validar_app.py` 146/146 (fases 2-5, escritorio + celular emulado): KPIs (contratos, avance general, cerrados, competencia vencida) contra lo calculado desde la semilla; barras por responsable en orden y con su valor y etiqueta; animación una por una de mayor a menor (retardo creciente, la primera arranca antes que la última, todas llegan a su valor) y sin animación con movimiento reducido; tooltip; semáforo ordenado por urgencia, nivel y conteos según la fecha actual, con ícono y texto.

- [x] **Fase 6 — Respaldo.** Exportar e importar JSON.
  - Criterio: exportar → restablecer → importar deja los datos idénticos.
  - Decisiones aprobadas (2026-11-23): controles en una vista nueva **Respaldo** (`#/respaldo`, 4.ª entrada del menú; la insignia de origen enlaza a ella) con resumen de los datos y tres tarjetas: Exportar, Importar (confirmación con resumen del archivo frente a los datos actuales; archivo inválido se rechaza sin tocar nada) y Restablecer a los datos del Excel (confirmación con "Exportar antes"). Formato: sobre `{formato: "liquidaciones_esap.respaldo", version: 1, exportado, origen, datos}` con `datos` = el estado de `store.js` (6 claves), archivo `liquidaciones_esap_respaldo_AAAA-MM-DD_HHMM.json` (UTF-8, sangría 2). Al importar también se acepta un `seed.json` suelto (las 6 claves sin sobre). Validación: `validar_app.py` (escritorio + celular) compara campo a campo `datos` exportado con lo guardado tras importar, más archivo inválido, cancelar y origen de datos.
  - **Cumplido: sí** — `python pruebas/validar_app.py` 279/279 (fases 2-6, escritorio + celular emulado; 3 corridas seguidas en verde) y `python -m pytest pruebas` 13/13: con un cambio propio, el archivo exportado (nombre, sobre, UTF-8 con sangría 2) es igual a lo guardado; restablecer (cancelar no cambia nada, "Exportar antes" descarga sin cerrar el diálogo) vuelve a la semilla; 5 archivos inválidos se rechazan sin tocar los datos; importar el respaldo deja `localStorage` y el estado en memoria **idénticos** al `datos` exportado, el tablero vuelve a las mismas cifras y persiste al recargar; un `seed.json` suelto carga la semilla.

- [ ] **Fase 7 — Validación integral.** Script Playwright (Edge del sistema) guardado en el proyecto, escritorio y celular emulado.
  - Criterio: todo el recorrido en verde en ambos modos. Al cerrar, se decide la publicación en GitHub Pages (repo propio + datos anonimizados).
