/** Vista Consulta — base de la Fase 2 (lista simple); búsqueda y filtros en la Fase 3. */
import * as store from '../js/store.js';
import { href } from '../js/router.js';
import { escapeHtml, percent } from '../js/format.js';

export const title = 'Consulta';

export function render(container) {
  const rows = store.contracts().map((c) => `
    <li>
      <a class="list-link" href="${href('ficha', c.id)}">
        <span class="list-main">${escapeHtml(c.numero)}</span>
        <span class="list-sub">${escapeHtml(c.contratista)}</span>
        <span class="list-end">${percent(store.progressOf(c.id))}</span>
      </a>
    </li>`).join('');
  container.innerHTML = `
    <p class="muted"><span data-count>${store.contracts().length}</span> contratos</p>
    <ul class="card list" data-list="contratos">${rows}</ul>
  `;
}
