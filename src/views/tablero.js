/** Vista Tablero — base de la Fase 2; KPIs completos, barras y semáforo en la Fase 5. */
import * as store from '../js/store.js';
import { percent } from '../js/format.js';

export const title = 'Tablero';

export function render(container) {
  const all = store.contracts();
  const withCard = all.filter((c) => c.tiene_tarjeta).length;
  container.innerHTML = `
    <div class="kpi-row">
      <article class="card kpi" data-kpi="contratos">
        <span class="kpi-label">Contratos</span>
        <strong class="kpi-value">${all.length}</strong>
        <span class="kpi-note">${withCard} con seguimiento</span>
      </article>
      <article class="card kpi" data-kpi="avance">
        <span class="kpi-label">Avance general</span>
        <strong class="kpi-value">${percent(store.generalProgress())}</strong>
        <span class="kpi-note">Promedio de los ${withCard} contratos con seguimiento</span>
      </article>
    </div>
    <p class="muted">Avance por responsable y semáforo de pérdida de competencia: Fase 5.</p>
  `;
}
