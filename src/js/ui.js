/** Piezas de interfaz compartidas por las vistas: aviso flotante e insignia de origen de datos. */
import * as store from './store.js';

const SOURCE_LABEL = { semilla: 'Datos de prueba (semilla)', local: 'Datos guardados en este navegador' };

/** Actualiza la insignia de origen de datos (cambia a 'local' tras el primer guardado). */
export function refreshSource() {
  const el = document.getElementById('data-source');
  if (!el) return;
  el.textContent = SOURCE_LABEL[store.getSource()];
  el.dataset.source = store.getSource();
}

/**
 * Confirmación modal con <dialog> nativo (Design_System_Core no trae modal).
 * `body` es HTML ya escapado. Devuelve una promesa: true = confirmar, false =
 * cancelar (botón, Escape o clic fuera). Si se pasa `extra: { label, run }`,
 * se agrega un botón que ejecuta run(button) sin cerrar el diálogo.
 */
export function confirmDialog({ title, body, confirmLabel, cancelLabel = 'Cancelar', extra }) {
  const dlg = document.createElement('dialog');
  dlg.className = 'confirm-dialog';
  dlg.setAttribute('aria-labelledby', 'confirm-title');
  dlg.innerHTML = `
    <h2 id="confirm-title" class="card-title">${title}</h2>
    <div class="confirm-body">${body}</div>
    <div class="confirm-actions">
      ${extra ? '<ds-button data-dialog="extra"></ds-button>' : ''}
      <ds-button data-dialog="cancel">${cancelLabel}</ds-button>
      <ds-button data-dialog="confirm">${confirmLabel}</ds-button>
    </div>`;
  if (extra) dlg.querySelector('[data-dialog="extra"]').textContent = extra.label;
  document.body.append(dlg);
  return new Promise((resolve) => {
    const close = (value) => { dlg.close(); dlg.remove(); resolve(value); };
    dlg.addEventListener('cancel', (e) => { e.preventDefault(); close(false); });
    dlg.addEventListener('click', (e) => {
      if (e.target === dlg) return close(false); // clic en el fondo
      const btn = e.target.closest('[data-dialog]');
      if (!btn) return;
      if (btn.dataset.dialog === 'extra') extra.run(btn);
      else close(btn.dataset.dialog === 'confirm');
    });
    dlg.showModal();
    dlg.querySelector('[data-dialog="cancel"]').focus();
  });
}

/**
 * Aviso flotante. `action` opcional: { label, run } — agrega un botón (ej.
 * "Deshacer") que ejecuta run() y cierra el aviso.
 */
export function toast(message, { ms = 4000, action } = {}) {
  const el = document.createElement('ds-toast');
  el.setAttribute('auto-dismiss', String(ms));
  el.append(message);
  if (action) {
    const btn = document.createElement('ds-button');
    btn.setAttribute('density', 'compact');
    btn.setAttribute('slot', 'actions');
    btn.textContent = action.label;
    btn.addEventListener('click', () => { action.run(); el.dismiss(); });
    el.append(btn);
  }
  document.getElementById('toast-stack').append(el);
  refreshSource();
  return el;
}
