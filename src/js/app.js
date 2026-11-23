/** Arranque: carga datos, monta la navegación y pinta la vista de la ruta. */
import '../components/sidebar/sidebar.core.js';
import '../components/button/button.core.js';
import '../components/toast/toast.core.js';
import '../components/dropdown/dropdown.core.js';
import * as store from './store.js';
import { start } from './router.js';
import * as tablero from '../views/tablero.js';
import * as consulta from '../views/consulta.js';
import * as ficha from '../views/ficha.js';

const routes = { tablero, consulta, ficha };
const SOURCE_LABEL = { semilla: 'Datos de prueba (semilla)', local: 'Datos guardados en este navegador' };

const viewEl = document.getElementById('view');
const titleEl = document.getElementById('page-title');
const sourceEl = document.getElementById('data-source');

/** Aviso flotante; lo usan las vistas al guardar (Fase 4). */
export function toast(message, ms = 3000) {
  const el = document.createElement('ds-toast');
  el.setAttribute('auto-dismiss', String(ms));
  el.textContent = message;
  document.getElementById('toast-stack').append(el);
}

function markActive(name) {
  document.querySelectorAll('ds-sidebar a[data-route]').forEach((a) => {
    if (a.dataset.route === name) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  });
}

let current = null;
function show(name, view, param) {
  current = { name, view, param };
  markActive(name);
  titleEl.textContent = view.title;
  document.title = `${view.title} — Liquidaciones ESAP`;
  sourceEl.textContent = SOURCE_LABEL[store.getSource()];
  sourceEl.dataset.source = store.getSource();
  view.render(viewEl, param);
}

async function main() {
  try {
    await store.load();
  } catch (err) {
    viewEl.innerHTML = `<div class="card empty"><p>No se pudieron cargar los datos: ${err.message}</p></div>`;
    console.error(err);
    return;
  }
  // Al cambiar los datos se repinta la vista actual
  store.onChange(() => current && show(current.name, current.view, current.param));
  start(routes, show);
}

main();
