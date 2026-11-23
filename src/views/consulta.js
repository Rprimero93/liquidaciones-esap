/**
 * Vista Consulta — búsqueda (número, contratista, responsable) y filtros por
 * responsable y estado. Los filtros se recuerdan al ir y volver de la ficha.
 */
import * as store from '../js/store.js';
import { href } from '../js/router.js';
import { escapeHtml, percent } from '../js/format.js';

export const title = 'Consulta';

const filters = { q: '', responsable: '', estado: '' };

/** Minúsculas sin tildes ni espacios repetidos, para comparar texto. */
export function normalize(text) {
  return String(text || '').normalize('NFD').replace(/[̀-ͯ]/g, '')
    .toLowerCase().replace(/\s+/g, ' ').trim();
}

export function matches(c, { q, responsable, estado }) {
  if (responsable && !store.responsiblesOf(c).includes(responsable)) return false;
  if (estado && store.statusOf(c.id) !== estado) return false;
  if (!q) return true;
  const needle = normalize(q);
  const compact = needle.replace(/[\s-]/g, '');
  const haystack = normalize([c.numero, c.contratista, c.responsable].join(' '));
  return haystack.includes(needle) || c.id.toLowerCase().replace(/-/g, '').includes(compact);
}

function option(value, label, selected) {
  return `<option value="${escapeHtml(value)}"${selected ? ' selected' : ''}>${escapeHtml(label)}</option>`;
}

function row(c) {
  const status = store.statusOf(c.id);
  const step = store.currentStep(c.id);
  return `
    <li>
      <a class="list-link" href="${href('ficha', c.id)}" data-id="${escapeHtml(c.id)}">
        <span class="list-main">${escapeHtml(c.id)}</span>
        <span class="list-sub">${escapeHtml(c.contratista)}
          ${step ? `<small class="list-meta">Etapa: ${escapeHtml(step.nombre)}</small>` : ''}
        </span>
        <span class="list-end">
          <span class="chip" data-status="${status}">${store.statusName(status)}</span>
          <span class="list-pct">${percent(store.progressOf(c.id))}</span>
        </span>
      </a>
    </li>`;
}

function update(container) {
  const all = store.contracts();
  const found = all.filter((c) => matches(c, filters));
  const listEl = container.querySelector('[data-list="contratos"]');
  const emptyEl = container.querySelector('[data-empty]');
  container.querySelector('[data-count]').textContent = found.length;
  container.querySelector('[data-total]').textContent = all.length;
  container.querySelector('[data-clear]').hidden = !(filters.q || filters.responsable || filters.estado);
  listEl.innerHTML = found.map(row).join('');
  listEl.hidden = !found.length;
  emptyEl.hidden = !!found.length;
  emptyEl.querySelector('p').textContent = all.length
    ? 'Ningún contrato coincide con la búsqueda y los filtros.'
    : 'No hay contratos registrados.';
}

export function render(container) {
  const responsibles = store.allResponsibles();
  container.innerHTML = `
    <div class="card filters" role="search">
      <label class="field field-search">
        <span class="field-label">Buscar</span>
        <input type="search" data-filter="q" placeholder="Número, contratista o responsable" autocomplete="off" value="${escapeHtml(filters.q)}">
      </label>
      <div class="field">
        <span class="field-label" id="lbl-resp">Responsable</span>
        <ds-dropdown data-filter="responsable" placeholder="Todos" aria-labelledby="lbl-resp">
          ${option('', 'Todos', !filters.responsable)}
          ${responsibles.map((r) => option(r, r, r === filters.responsable)).join('')}
        </ds-dropdown>
      </div>
      <div class="field">
        <span class="field-label" id="lbl-estado">Estado</span>
        <ds-dropdown data-filter="estado" placeholder="Todos" aria-labelledby="lbl-estado">
          ${option('', 'Todos', !filters.estado)}
          ${store.STATUSES.map((s) => option(s.id, s.nombre, s.id === filters.estado)).join('')}
        </ds-dropdown>
      </div>
    </div>
    <div class="result-bar">
      <p class="muted"><span data-count></span> de <span data-total></span> contratos</p>
      <ds-button density="compact" data-clear hidden>Limpiar filtros</ds-button>
    </div>
    <ul class="card list" data-list="contratos"></ul>
    <div class="card empty" data-empty hidden><p></p></div>
  `;

  // Valor inicial de los dropdowns (el atributo selected no lo lee el componente)
  container.querySelectorAll('ds-dropdown[data-filter]').forEach((dd) => {
    customElements.whenDefined('ds-dropdown').then(() => { dd.value = filters[dd.dataset.filter]; });
    dd.addEventListener('change', () => { filters[dd.dataset.filter] = dd.value; update(container); });
  });
  container.querySelector('input[data-filter="q"]').addEventListener('input', (e) => {
    filters.q = e.target.value;
    update(container);
  });
  container.querySelector('[data-clear]').addEventListener('click', () => {
    Object.keys(filters).forEach((k) => { filters[k] = ''; });
    render(container);
  });
  update(container);
}
