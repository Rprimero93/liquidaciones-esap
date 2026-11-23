/**
 * Vista Respaldo — exportar los datos a un archivo JSON, importarlos de vuelta
 * y restablecer a los datos del Excel (semilla). Formato en js/backup.js.
 */
import * as store from '../js/store.js';
import * as backup from '../js/backup.js';
import { confirmDialog, toast } from '../js/ui.js';
import { escapeHtml } from '../js/format.js';

export const title = 'Respaldo';

const SOURCE_TEXT = {
  semilla: 'los datos del Excel (semilla), sin cambios',
  local: 'los datos guardados en este navegador',
};

const dateTime = new Intl.DateTimeFormat('es-CO', { dateStyle: 'medium', timeStyle: 'short' });

function figures(s) {
  return `${s.contratos} contratos (${s.conSeguimiento} con seguimiento) · ${s.bitacora} entradas de bitácora`
    + (s.bitacoraApp ? ` (${s.bitacoraApp} ${s.bitacoraApp === 1 ? 'agregada' : 'agregadas'} en la app)` : '');
}

/** Descarga el estado actual como archivo de respaldo. */
export function exportBackup() {
  const now = new Date();
  const text = backup.serialize(backup.buildBackup(store.getState(), store.getSource(), now));
  const url = URL.createObjectURL(new Blob([text], { type: 'application/json' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = backup.backupFileName(now);
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return a.download;
}

async function importFile(file) {
  let parsed;
  try {
    parsed = backup.parseBackup(await file.text());
  } catch (err) {
    toast(`No se importó «${file.name}». ${err.message}`, { ms: 8000 });
    return;
  }
  const incoming = backup.summarize(parsed.datos);
  const current = backup.summarize(store.getState());
  const when = parsed.exportado && !Number.isNaN(Date.parse(parsed.exportado))
    ? `exportado el ${dateTime.format(new Date(parsed.exportado))}`
    : parsed.tipo === 'semilla' ? 'datos extraídos del Excel (semilla, sin sobre de respaldo)' : 'sin fecha de exportación';
  const ok = await confirmDialog({
    title: 'Importar respaldo',
    body: `
      <p><strong>${escapeHtml(file.name)}</strong> — ${escapeHtml(when)}</p>
      <dl class="confirm-compare">
        <dt>Archivo</dt><dd data-compare="archivo">${figures(incoming)}</dd>
        <dt>Datos actuales</dt><dd data-compare="actual">${figures(current)}</dd>
      </dl>
      <p>Los datos actuales se reemplazan por los del archivo.</p>`,
    confirmLabel: 'Importar',
  });
  if (!ok) return;
  if (store.replace(parsed.datos)) toast('Respaldo importado.');
  else toast('No se pudo guardar en este navegador: los datos no cambiaron.', { ms: 8000 });
}

async function resetData() {
  if (store.getSource() === 'semilla') return; // nada que restablecer (el botón queda deshabilitado)
  const ok = await confirmDialog({
    title: 'Restablecer a los datos del Excel',
    body: `
      <p>Se borran los datos guardados en este navegador y se vuelve a la semilla extraída del Excel.
      Los cambios hechos en la app (pasos, alertas, fechas y observaciones) se pierden.</p>
      <p class="muted">Si quieres conservarlos, exporta un respaldo antes.</p>`,
    confirmLabel: 'Restablecer',
    extra: {
      label: 'Exportar antes',
      run: (btn) => { exportBackup(); btn.textContent = 'Respaldo descargado ✓'; },
    },
  });
  if (!ok) return;
  await store.reset();
  toast('Datos restablecidos a los del Excel.');
}

export function render(container) {
  const source = store.getSource();
  container.innerHTML = `
    <div class="card backup-summary" data-backup-summary>
      <h2 class="card-title">Datos actuales</h2>
      <p>La app muestra ${SOURCE_TEXT[source]}.</p>
      <p class="muted">${figures(backup.summarize(store.getState()))}</p>
    </div>
    <div class="backup-cols">
      <section class="card backup-card">
        <h2 class="card-title">Exportar</h2>
        <p class="muted">Descarga un archivo JSON con todos los datos: contratos, pasos, alertas, fechas y bitácora.</p>
        <ds-button data-export>Exportar respaldo</ds-button>
      </section>
      <section class="card backup-card">
        <h2 class="card-title">Importar</h2>
        <p class="muted">Carga un respaldo exportado por la app (o un <code>seed.json</code> extraído del Excel). Reemplaza los datos actuales, previa confirmación.</p>
        <ds-button data-import>Importar archivo…</ds-button>
        <input type="file" accept=".json,application/json" data-import-file hidden>
      </section>
      <section class="card backup-card">
        <h2 class="card-title">Restablecer</h2>
        <p class="muted">Vuelve a los datos del Excel y descarta lo guardado en este navegador.</p>
        <ds-button data-reset${source === 'semilla' ? ' disabled' : ''}>Restablecer datos</ds-button>
        ${source === 'semilla' ? '<p class="backup-note muted">Ya se muestran los datos del Excel.</p>' : ''}
      </section>
    </div>`;

  const input = container.querySelector('[data-import-file]');
  container.querySelector('[data-export]').addEventListener('click', () => {
    toast(`Respaldo exportado: ${exportBackup()}`);
  });
  container.querySelector('[data-import]').addEventListener('click', () => input.click());
  input.addEventListener('change', () => {
    const file = input.files[0];
    input.value = ''; // permite volver a elegir el mismo archivo
    if (file) importFile(file);
  });
  container.querySelector('[data-reset]').addEventListener('click', resetData);
}
