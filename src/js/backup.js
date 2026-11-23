/**
 * Formato del archivo de respaldo: armar el sobre, nombrar el archivo y validar
 * lo que se importa. No toca localStorage ni la vista (eso es de store.js y de
 * views/respaldo.js).
 *
 * Sobre: { formato, version, exportado, origen, datos } — `datos` es el estado
 * tal como lo guarda store.js. Al importar también se acepta un seed.json
 * suelto (las 6 claves sin sobre), para cargar una extracción nueva del Excel.
 */
export const FORMAT = 'liquidaciones_esap.respaldo';
export const VERSION = 1;

const KEYS = ['meta', 'pasos', 'alertas', 'contratos', 'avances', 'bitacora'];

/** Fecha local con desfase horario (ej. 2026-11-23T14:30:00-05:00). */
function localIso(d) {
  const pad = (n) => String(Math.abs(n)).padStart(2, '0');
  const off = -d.getTimezoneOffset();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
    + `${off >= 0 ? '+' : '-'}${pad(Math.trunc(off / 60))}:${pad(off % 60)}`;
}

export function buildBackup(data, source, now = new Date()) {
  return { formato: FORMAT, version: VERSION, exportado: localIso(now), origen: source, datos: data };
}

export function backupFileName(now = new Date()) {
  const pad = (n) => String(n).padStart(2, '0');
  return `liquidaciones_esap_respaldo_${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
    + `_${pad(now.getHours())}${pad(now.getMinutes())}.json`;
}

export const serialize = (backup) => JSON.stringify(backup, null, 2);

const isObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);

/** Lista de problemas del estado (vacía = válido). */
export function validateData(d) {
  if (!isObject(d)) return ['el contenido no es un objeto JSON'];
  const missing = KEYS.filter((k) => !(k in d));
  if (missing.length) return [`faltan claves: ${missing.join(', ')}`];
  const errors = [];
  if (!isObject(d.meta)) errors.push('"meta" debe ser un objeto');
  KEYS.slice(1).forEach((k) => { if (!Array.isArray(d[k])) errors.push(`"${k}" debe ser una lista`); });
  if (errors.length) return errors;

  const ids = new Set();
  d.contratos.forEach((c, i) => {
    if (!isObject(c) || typeof c.id !== 'string' || !c.id) errors.push(`el contrato ${i + 1} no tiene id`);
    else ids.add(c.id);
  });
  if (!d.pasos.length) errors.push('no hay pasos definidos');
  const orphanAvances = d.avances.filter((a) => !isObject(a) || !ids.has(a.contrato)).length;
  const orphanLog = d.bitacora.filter((b) => !isObject(b) || !ids.has(b.contrato)).length;
  if (orphanAvances) errors.push(`${orphanAvances} avances apuntan a contratos que no existen`);
  if (orphanLog) errors.push(`${orphanLog} entradas de bitácora apuntan a contratos que no existen`);
  return errors;
}

/**
 * Lee el texto de un archivo y devuelve { datos, tipo: 'respaldo' | 'semilla',
 * exportado }. Lanza Error con un mensaje legible si el archivo no sirve.
 */
export function parseBackup(text) {
  let json;
  try {
    json = JSON.parse(text);
  } catch {
    throw new Error('El archivo no es un JSON válido.');
  }
  let datos;
  let tipo;
  if (isObject(json) && 'formato' in json) {
    if (json.formato !== FORMAT) throw new Error('El archivo no es un respaldo de Liquidaciones ESAP.');
    if (json.version !== VERSION) throw new Error(`Versión de respaldo no compatible (${json.version}).`);
    datos = json.datos;
    tipo = 'respaldo';
  } else {
    datos = json;
    tipo = 'semilla';
  }
  const errors = validateData(datos);
  if (errors.length) throw new Error(`El archivo no tiene el formato esperado: ${errors.slice(0, 3).join('; ')}.`);
  return { datos, tipo, exportado: tipo === 'respaldo' ? json.exportado || null : null };
}

/** Cifras para el resumen y la confirmación. */
export function summarize(d) {
  return {
    contratos: d.contratos.length,
    conSeguimiento: d.contratos.filter((c) => c.tiene_tarjeta).length,
    bitacora: d.bitacora.length,
    bitacoraApp: d.bitacora.filter((b) => b.origen === 'app').length,
  };
}
