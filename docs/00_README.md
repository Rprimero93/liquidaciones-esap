---
tecnologia: Web
tipo: entregable
proyecto: Liquidaciones_ESAP
estado: completo
revisar_uso: 2026-12-23
estado_resumen: "Cerrado (2026-11-23) — publicado en https://rprimero93.github.io/liquidaciones-esap/"
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

Publicada: `https://rprimero93.github.io/liquidaciones-esap/` (Fase 8). En local, desde la carpeta del proyecto: `python -m http.server 8000` y abrir `http://localhost:8000/src/index.html` (los módulos JS y la semilla no cargan con doble clic en el archivo).

## Git

Se versiona en el repositorio de la bóveda (Regla 12, caso 1). Además se publica un **espejo** en GitHub (Fase 8): `bash scripts/publicar_github.sh` (`--dry-run` para ensayar) hace `git subtree split` de esta carpeta, cambia el correo de autor/committer por `Rprimero93@users.noreply.github.com`, quita las cachés de Python, aborta si la copia lleva el correo corporativo o un Excel, y empuja a `main` de `Rprimero93/liquidaciones-esap` (remoto con el usuario `Rprimero93@`: la cuenta de Git por defecto del equipo es otra). No hay `.git` anidado: la bóveda sigue siendo la fuente de verdad. `index.html` y `.nojekyll` de la raíz son para GitHub Pages.

## Pruebas

- Extracción: prueba que compara `seed.json` contra el Excel (mismos contratos, mismo avance por contrato), con los conteos leídos de los datos.
- App: Playwright con el Edge del sistema, escritorio y celular emulado (preferencias de `INVENTARIO_Web.md`).
  - `python pruebas/validar_app.py` — verificaciones por fase (2 a 6).
  - `python pruebas/recorrido.py` — recorrido de punta a punta como usuario (Fase 7), con cifras esperadas calculadas en Python.
- Enlaces SECOP: `python -m pytest pruebas` incluye el cruce de `scripts/consultar_secop.py` (sin red) y la tabla `data/secop.json`.

## Riesgos

- **Datos reales publicados (riesgo aceptado por Ricardo, 2026-11-23):** se publicarán en GitHub Pages con los datos reales completos — nombres de responsables, bitácora interna, contratistas y valores quedan públicos y en el historial de Git. Reemplaza la decisión de la Fase 0 (datos anonimizados); detalle en `06` (Fase 7).

## Lecciones aprendidas

_Cierre del 2026-11-23. Mini-retro de proceso: sin observaciones del usuario. Detalle por fase en `07_PROGRESO_RESUMEN.md`._

1. **El estilo se definió tarde.** Hubo 23 ajustes visuales después de cerrar fases (hover, píldoras, campos, cebra, navbar, KPIs), varios rehechos. En una app con interfaz, fijar al principio las referencias visuales, la paleta y la regla de contraste (pasó a preferencia de Web).
2. **Datos:** semilla extraída del Excel, una sola puerta (`store.js`), `localStorage` y respaldo JSON con sobre (`formato`/`version`). Lo verificado afuera va en una tabla aparte (`secop.json`) que manda sobre el dato del Excel sin entrar al estado guardado ni al respaldo: sirve con los datos ya guardados sin restablecer.
3. **Validación:** las cifras esperadas salen de un modelo propio en Python, nunca de la app; el recorrido encadenado (Fase 7) prueba lo que las verificaciones por fase no ven (pasó a preferencia de Web). En la prueba: servidor de varios hilos y esperar a que las transiciones terminen, no tiempos fijos.
4. **Design_System_Core en copia local:** se ajusta por fuera con `::part` y con parches comentados `var(--x, original)`, sin tocar el componente. Aparecieron 3 defectos del Core; 2 coinciden con Asistente_SGI (ver § Consumidores de Design_System_Core).
5. **SECOP:** los datos abiertos de datos.gov.co (SECOP II `jbjy-vk9h` filtrado por NIT, SECOP I `f789-7hwg`) permiten verificar los enlaces de forma reproducible; SECOP II bloquea la automatización (403 y CAPTCHA), así que el contenido del proceso lo revisa el usuario.
6. **Publicación:** espejo con `git subtree split`, correo noreply y control de privacidad sobre la rama que se envía (no `--all`: la copia conserva la rama temporal sin filtrar). Publicar datos reales fue una decisión explícita del usuario con el riesgo presentado y registrado.

## Uso real

_Revisiones después de entregar (fecha, si se usa, qué funcionó, qué faltó) — `03_TRD.md` § Herramientas y entregables._
