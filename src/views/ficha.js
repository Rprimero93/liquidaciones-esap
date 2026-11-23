/** Vista Ficha — base de la Fase 2 (datos generales); pasos, alertas y bitácora en la Fase 4. */
import * as store from '../js/store.js';
import { href } from '../js/router.js';
import { currency, date, escapeHtml, percent } from '../js/format.js';

export const title = 'Ficha del contrato';

let lastId = null; // la ficha recuerda el último contrato abierto

export function render(container, id) {
  const c = store.contract(id || lastId);
  if (!c) {
    container.innerHTML = `
      <div class="card empty">
        <p>Elige un contrato en <a href="${href('consulta')}">Consulta</a> para ver su ficha.</p>
      </div>`;
    return;
  }
  lastId = c.id;
  container.innerHTML = `
    <article class="card" data-contrato="${escapeHtml(c.id)}">
      <h2 class="card-title">${escapeHtml(c.id)}</h2>
      <p class="muted">${escapeHtml(c.contratista)}</p>
      <dl class="facts">
        <div><dt>Responsable</dt><dd>${escapeHtml(c.responsable) || '—'}</dd></div>
        <div><dt>Avance</dt><dd>${percent(store.progressOf(c.id))}</dd></div>
        <div><dt>Pérdida de competencia</dt><dd>${date(c.perdida_competencia)}</dd></div>
        <div><dt>Plazo de cierre</dt><dd>${date(c.plazo_cierre)}</dd></div>
        <div><dt>Valor</dt><dd>${currency(c.valor)}</dd></div>
      </dl>
    </article>
  `;
}

export const currentId = () => lastId;
