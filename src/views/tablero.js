/**
 * Vista Tablero — KPIs, avance por responsable (barras horizontales que entran
 * una por una, de mayor a menor, con barrido hacia la derecha) y semáforo de
 * pérdida de competencia de los contratos sin cerrar.
 */
import * as store from '../js/store.js';
import { href } from '../js/router.js';
import { date, escapeHtml, percent } from '../js/format.js';

export const title = 'Tablero';

const BAR_STAGGER_MS = 120; // retardo entre barras

function kpis() {
  const all = store.contracts();
  const withCard = all.filter((c) => c.tiene_tarjeta).length;
  const count = (s) => all.filter((c) => store.statusOf(c.id) === s).length;
  const overdue = store.openDeadlines().filter((d) => d.nivel === 'vencido').length;
  return `
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
      <article class="card kpi" data-kpi="cerrados">
        <span class="kpi-label">Cerrados</span>
        <strong class="kpi-value">${count('cerrado')}</strong>
        <span class="kpi-note">${count('paralizado')} paralizados · ${count('en-tramite')} en trámite</span>
      </article>
      <article class="card kpi" data-kpi="vencidos">
        <span class="kpi-label">Competencia vencida</span>
        <strong class="kpi-value">${overdue}</strong>
        <span class="kpi-note">Contratos sin cerrar con la fecha ya pasada</span>
      </article>
    </div>`;
}

function bars() {
  const rows = store.progressByResponsible();
  return `
    <section class="card" aria-labelledby="h-resp">
      <h2 class="section-title" id="h-resp">Avance por responsable</h2>
      <p class="muted hint">Promedio de avance de sus contratos con seguimiento. Un contrato compartido cuenta para cada responsable.</p>
      <ol class="bars" data-bars style="--stagger:${BAR_STAGGER_MS}ms">
        ${rows.map((r, i) => {
          const tip = `${r.nombre}: ${percent(r.avance)} de avance promedio · ${r.contratos} contrato${r.contratos === 1 ? '' : 's'}, ${r.cerrados} cerrado${r.cerrados === 1 ? '' : 's'}`;
          return `
          <li class="bar-row" tabindex="0" data-name="${escapeHtml(r.nombre)}" data-tip="${escapeHtml(tip)}" aria-label="${escapeHtml(tip)}">
            <span class="bar-label">${escapeHtml(r.nombre)} <small class="muted">(${r.contratos})</small></span>
            <span class="bar-track"><span class="bar" style="--w:${r.avance};--i:${i}" data-value="${r.avance}"></span></span>
            <span class="bar-value">${percent(r.avance)}</span>
          </li>`;
        }).join('')}
      </ol>
      <div class="tooltip" role="tooltip" data-tooltip hidden></div>
    </section>`;
}

function daysText(d) {
  if (d.dias === null) return 'Sin fecha registrada';
  if (d.dias < 0) return `Venció hace ${-d.dias} día${d.dias === -1 ? '' : 's'}`;
  if (d.dias === 0) return 'Vence hoy';
  return `Faltan ${d.dias} día${d.dias === 1 ? '' : 's'}`;
}

// Nivel del semáforo elegido como filtro ('' = todos); se recuerda al volver de una ficha
let levelFilter = '';

function deadlineRows(rows) {
  const shown = levelFilter ? rows.filter((r) => r.nivel === levelFilter) : rows;
  return shown.map((r) => {
          const level = store.DEADLINE_LEVELS.find((l) => l.id === r.nivel);
          return `
          <li>
            <a class="list-link" href="${href('ficha', r.contrato.id)}" data-id="${escapeHtml(r.contrato.id)}" data-level="${r.nivel}">
              <span class="list-main">${escapeHtml(r.contrato.id)}</span>
              <span class="list-sub">${escapeHtml(r.contrato.contratista)}
                <small class="list-meta">${r.dias === null ? '' : `${date(r.contrato.perdida_competencia)} · `}${daysText(r)}</small>
              </span>
              <span class="list-end">
                <span class="level" data-level="${r.nivel}"><span class="level-icon" aria-hidden="true">${level.icono}</span>${level.nombre}</span>
              </span>
            </a>
          </li>`;
  }).join('');
}

function traffic() {
  const rows = store.openDeadlines();
  const counts = Object.fromEntries(store.DEADLINE_LEVELS.map((l) => [l.id, rows.filter((r) => r.nivel === l.id).length]));
  if (levelFilter && !counts[levelFilter]) levelFilter = ''; // el nivel elegido se quedó sin contratos
  return `
    <section class="card" aria-labelledby="h-semaforo">
      <h2 class="section-title" id="h-semaforo">Pérdida de competencia</h2>
      <p class="muted hint">Contratos sin cerrar, del más urgente al menos urgente. Próximo a vencer = ${store.DEADLINE_WARN_DAYS} días o menos. Toca un nivel para filtrar.</p>
      <div class="levels" data-levels role="group" aria-label="Filtrar por nivel">
        ${store.DEADLINE_LEVELS.map((l) => `
          <button type="button" class="level level-filter" data-level="${l.id}" data-level-filter="${l.id}"
            aria-pressed="${levelFilter === l.id}"${counts[l.id] ? '' : ' disabled'}>
            <span class="level-icon" aria-hidden="true">${l.icono}</span>
            ${l.nombre}: <strong data-level-count="${l.id}">${counts[l.id]}</strong>
          </button>`).join('')}
      </div>
      <p class="muted deadline-count"><span data-deadline-shown></span> de ${rows.length} contratos sin cerrar</p>
      <ul class="card list deadline-list" data-deadlines></ul>
    </section>`;
}

function bindLevels(container) {
  const rows = store.openDeadlines();
  const list = container.querySelector('[data-deadlines]');
  const paint = () => {
    list.innerHTML = deadlineRows(rows);
    container.querySelector('[data-deadline-shown]').textContent = list.querySelectorAll('a[data-id]').length;
    container.querySelectorAll('[data-level-filter]').forEach((b) => {
      b.setAttribute('aria-pressed', String(b.dataset.levelFilter === levelFilter));
    });
  };
  container.querySelector('[data-levels]').addEventListener('click', (e) => {
    const btn = e.target.closest('[data-level-filter]');
    if (!btn || btn.disabled) return;
    levelFilter = levelFilter === btn.dataset.levelFilter ? '' : btn.dataset.levelFilter; // segundo clic quita el filtro
    paint();
  });
  paint();
}

function bindTooltip(container) {
  const tip = container.querySelector('[data-tooltip]');
  const box = tip.parentElement;
  const show = (row, x, y) => {
    tip.textContent = row.dataset.tip;
    tip.hidden = false;
    const b = box.getBoundingClientRect();
    tip.style.left = `${Math.min(x - b.left + 12, b.width - tip.offsetWidth - 8)}px`;
    tip.style.top = `${y - b.top + 16}px`;
  };
  const hide = () => { tip.hidden = true; };
  container.querySelectorAll('.bar-row').forEach((row) => {
    row.addEventListener('mousemove', (e) => show(row, e.clientX, e.clientY));
    row.addEventListener('mouseleave', hide);
    row.addEventListener('focus', () => {
      const r = row.querySelector('.bar-track').getBoundingClientRect();
      show(row, r.left, r.bottom - 8);
    });
    row.addEventListener('blur', hide);
  });
}

export function render(container) {
  container.innerHTML = `${kpis()}<div class="dash-cols">${bars()}${traffic()}</div>`;
  bindTooltip(container);
  bindLevels(container);
  // Arranca la animación en el siguiente cuadro (las barras parten en ancho 0)
  requestAnimationFrame(() => requestAnimationFrame(() => container.querySelector('[data-bars]')?.classList.add('is-in')));
}
