/**
 * Vista Ficha — datos del contrato, 12 pasos (clic para marcar/desmarcar),
 * 4 alertas, fechas editables y bitácora. Cada cambio se guarda solo y se
 * confirma con un aviso; la vista se actualiza por secciones, sin repintarse entera.
 *
 * Pasos: se usa <ds-step> SIN <ds-stepper>, con el estado puesto por la app
 * (completed = hecho, current = etapa actual, pending = el resto): el
 * contenedor impone avanzar en orden y el Excel tiene pasos marcados fuera
 * de orden (ej. "Modificación de pólizas — No requiere").
 */
import * as store from '../js/store.js';
import { href } from '../js/router.js';
import { currency, date, escapeHtml, percent } from '../js/format.js';
import { toast } from '../js/ui.js';

export const title = 'Ficha del contrato';

let lastId = null; // la ficha recuerda el último contrato abierto

function todayIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function saved(message, undo) {
  toast(message, undo ? { action: { label: 'Deshacer', run: undo } } : {});
}

function renderSummary(root, c) {
  const status = store.statusOf(c.id);
  root.querySelector('[data-summary]').innerHTML = `
    <span class="chip" data-status="${status}">${store.statusName(status)}</span>
    <span class="summary-pct"><strong data-avance>${percent(store.progressOf(c.id))}</strong> de avance</span>`;
}

function renderSteps(root, c) {
  const box = root.querySelector('[data-steps]');
  if (!c.tiene_tarjeta) {
    box.innerHTML = `
      <p class="muted">Este contrato no tenía tarjeta de seguimiento en el Excel.</p>
      <ds-button data-start>Iniciar seguimiento</ds-button>`;
    box.querySelector('[data-start]').addEventListener('click', () => {
      store.startTracking(c.id);
      saved('Seguimiento iniciado: 12 pasos y 4 alertas sin marcar.');
      renderAll(root, c);
    });
    return;
  }
  const rows = store.itemsOf(c.id, 'paso');
  const current = store.currentStep(c.id);
  box.innerHTML = `
    <p class="muted hint">Haz clic en un paso para marcarlo o desmarcarlo.</p>
    <div class="steps" role="list">
      ${store.steps().map((p) => {
        const row = rows.find((r) => r.item === p.id);
        const state = row?.hecho ? 'completed' : (current?.id === p.id ? 'current' : 'pending');
        return `<ds-step data-step="${p.id}" step="${p.id}" state="${state}"
          label="${escapeHtml(row?.etiqueta || p.nombre)}">${state === 'current'
          ? `<p class="step-note">Etapa actual. <ds-button density="compact" data-done="${p.id}">Marcar como completado</ds-button></p>`
          : ''}</ds-step>`;
      }).join('')}
    </div>`;
}

function renderAlerts(root, c) {
  const box = root.querySelector('[data-alerts]');
  if (!c.tiene_tarjeta) { box.innerHTML = '<p class="muted">Sin seguimiento.</p>'; return; }
  const rows = store.itemsOf(c.id, 'alerta');
  box.innerHTML = store.alerts().map((a) => {
    const on = rows.find((r) => r.item === a.id)?.hecho;
    return `<label class="check"><input type="checkbox" data-alert="${a.id}"${on ? ' checked' : ''}>
      <span>${escapeHtml(a.nombre)}</span></label>`;
  }).join('');
}

// Bitácora: se muestran los últimos LOG_PREVIEW eventos; "Ver más" despliega el resto
const LOG_PREVIEW = 5;
let logExpanded = false; // se reinicia al abrir otro contrato

function renderLog(root, c) {
  const all = store.sortedLogOf(c.id);
  const rows = logExpanded ? all : all.slice(0, LOG_PREVIEW);
  const hidden = all.length - LOG_PREVIEW;
  root.querySelector('[data-log-count]').textContent = all.length;
  const more = root.querySelector('[data-log-more]');
  more.hidden = hidden <= 0;
  more.textContent = logExpanded ? 'Ver menos' : `Ver más (${hidden})`;
  more.setAttribute('aria-expanded', String(logExpanded));
  root.querySelector('[data-log]').innerHTML = rows.length
    ? rows.map((b) => `
      <li data-origin="${b.origen}">
        <time class="log-date"${b.fecha ? ` datetime="${b.fecha}"` : ''}>${b.fecha ? date(b.fecha) : 'Sin fecha'}</time>
        <p class="log-text">${escapeHtml(b.texto)}</p>
        <span class="log-origin">${b.origen === 'app' ? 'App' : b.origen === 'nota' ? 'Nota (Excel)' : 'Excel'}</span>
      </li>`).join('')
    : '<li class="muted">Sin registros.</li>';
}

function renderAll(root, c) {
  renderSummary(root, c);
  renderSteps(root, c);
  renderAlerts(root, c);
  renderLog(root, c);
}

function toggleStep(root, c, item) {
  const row = store.itemsOf(c.id, 'paso').find((r) => r.item === item);
  if (!row) return;
  const before = row.hecho;
  const name = store.steps().find((p) => p.id === item).nombre;
  store.setItem(c.id, 'paso', item, !before);
  renderSummary(root, c);
  renderSteps(root, c);
  saved(`Paso ${item} ${before ? 'desmarcado' : 'marcado como hecho'}: ${name}.`, () => {
    store.setItem(c.id, 'paso', item, before);
    renderSummary(root, c);
    renderSteps(root, c);
  });
}

function closingHint(c) {
  // Texto original del Excel cuando la fecha no se pudo leer (ej. "31/06/2022")
  return !c.plazo_cierre && c.plazo_cierre_texto
    ? `<small class="muted">En el Excel: "${escapeHtml(c.plazo_cierre_texto)}"</small>` : '';
}

export function render(container, id) {
  const c = store.contract(id || lastId);
  if (!c) {
    container.innerHTML = `
      <div class="card empty">
        <p>Elige un contrato en <a href="${href('consulta')}">Consulta</a> para ver su ficha.</p>
      </div>`;
    return;
  }
  if (c.id !== lastId) logExpanded = false;
  lastId = c.id;
  container.innerHTML = `
    <div class="ficha" data-contrato="${escapeHtml(c.id)}">
      <article class="card ficha-head">
        <div class="ficha-title">
          <div>
            <h2 class="card-title">${escapeHtml(c.id)}</h2>
            <p class="muted">${escapeHtml(c.contratista)}</p>
          </div>
          <div class="summary" data-summary></div>
        </div>
        <dl class="facts">
          <div><dt>Responsable</dt><dd>${escapeHtml(c.responsable) || '—'}</dd></div>
          <div><dt>Valor</dt><dd>${currency(c.valor)}</dd></div>
          <div><dt>SECOP</dt><dd>${/^https?:\/\//.test(c.secop)
            ? `<a href="${escapeHtml(c.secop)}" target="_blank" rel="noopener" data-secop>Abrir en SECOP ↗</a>`
            : 'Sin enlace'}</dd></div>
        </dl>
      </article>

      <section class="card" aria-labelledby="h-fechas">
        <h3 class="section-title" id="h-fechas">Fechas</h3>
        <div class="date-grid">
          <div class="field">
            <span class="field-label" id="lbl-pc">Pérdida de competencia</span>
            <ds-datepicker data-date="perdida_competencia" aria-labelledby="lbl-pc"${c.perdida_competencia ? ` value="${c.perdida_competencia}"` : ''}></ds-datepicker>
          </div>
          <div class="field">
            <span class="field-label" id="lbl-pl">Plazo para cierre</span>
            <ds-datepicker data-date="plazo_cierre" aria-labelledby="lbl-pl"${c.plazo_cierre ? ` value="${c.plazo_cierre}"` : ''}></ds-datepicker>
            ${closingHint(c)}
          </div>
        </div>
      </section>

      <div class="ficha-cols">
        <section class="card" aria-labelledby="h-pasos">
          <h3 class="section-title" id="h-pasos">Pasos de la liquidación</h3>
          <div data-steps></div>
        </section>
        <section class="card" aria-labelledby="h-alertas">
          <h3 class="section-title" id="h-alertas">Alertas</h3>
          <div class="checks" data-alerts></div>
        </section>
      </div>

      <section class="card" aria-labelledby="h-bitacora">
        <h3 class="section-title" id="h-bitacora">Bitácora <span class="muted">(<span data-log-count></span>)</span></h3>
        <form class="log-form" data-log-form>
          <div class="field">
            <span class="field-label" id="lbl-lf">Fecha</span>
            <ds-datepicker data-log-date aria-labelledby="lbl-lf" value="${todayIso()}"></ds-datepicker>
          </div>
          <label class="field log-field">
            <span class="field-label">Observación</span>
            <textarea data-log-text rows="2" placeholder="Qué pasó, quién, qué sigue"></textarea>
          </label>
          <ds-button type="submit" data-log-add>Agregar</ds-button>
        </form>
        <ol class="log" data-log id="log-list"></ol>
        <div class="log-more"><ds-button density="compact" data-log-more aria-controls="log-list" hidden></ds-button></div>
      </section>
    </div>`;

  const root = container.querySelector('.ficha');
  renderAll(root, c);

  // Pasos: clic en el encabezado o en "Marcar como completado"
  root.querySelector('[data-steps]').addEventListener('ds-step-select', (e) => {
    toggleStep(root, c, Number(e.target.dataset.step));
  });
  root.querySelector('[data-steps]').addEventListener('click', (e) => {
    const btn = e.target.closest('[data-done]');
    if (btn) toggleStep(root, c, Number(btn.dataset.done));
  });

  // Alertas
  root.querySelector('[data-alerts]').addEventListener('change', (e) => {
    const item = Number(e.target.dataset.alert);
    if (!item) return;
    const on = e.target.checked;
    store.setItem(c.id, 'alerta', item, on);
    renderSummary(root, c);
    saved(`Alerta ${on ? 'activada' : 'desactivada'}: ${store.alerts().find((a) => a.id === item).nombre}.`, () => {
      store.setItem(c.id, 'alerta', item, !on);
      renderSummary(root, c);
      renderAlerts(root, c);
    });
  });

  // Fechas
  root.querySelectorAll('ds-datepicker[data-date]').forEach((dp) => {
    dp.addEventListener('change', () => {
      store.setDate(c.id, dp.dataset.date, dp.value);
      saved(`Fecha guardada: ${dp.dataset.date === 'plazo_cierre' ? 'plazo para cierre' : 'pérdida de competencia'} ${date(dp.value)}.`);
    });
  });

  // Bitácora
  root.querySelector('[data-log-more]').addEventListener('click', () => {
    logExpanded = !logExpanded;
    renderLog(root, c);
  });
  const form = root.querySelector('[data-log-form]');
  const text = form.querySelector('[data-log-text]');
  form.querySelector('[data-log-add]').addEventListener('click', () => form.requestSubmit());
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    if (!text.value.trim()) { text.focus(); toast('Escribe la observación antes de agregarla.'); return; }
    store.addLog(c.id, form.querySelector('[data-log-date]').value, text.value);
    text.value = '';
    renderLog(root, c);
    saved('Observación agregada a la bitácora.');
  });
}

export const currentId = () => lastId;
