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
