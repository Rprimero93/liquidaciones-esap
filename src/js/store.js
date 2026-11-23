/**
 * Capa de datos: semilla (data/seed.json) + persistencia en localStorage.
 * Si hay datos guardados, mandan sobre la semilla; si no, se lee la semilla.
 * Las vistas nunca tocan localStorage directo: todo pasa por aquí.
 */
const SEED_URL = new URL('../../data/seed.json', import.meta.url);
const STORAGE_KEY = 'liquidaciones_esap.v1';

let state = null;
let source = 'semilla'; // 'semilla' | 'local'
const listeners = new Set();

function readLocal() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null; // almacenamiento bloqueado o JSON dañado: se cae a la semilla
  }
}

async function readSeed() {
  const res = await fetch(SEED_URL);
  if (!res.ok) throw new Error(`No se pudo leer la semilla (${res.status})`);
  return res.json();
}

export async function load() {
  const local = readLocal();
  if (local) {
    state = local;
    source = 'local';
  } else {
    state = await readSeed();
    source = 'semilla';
  }
  return state;
}

/**
 * Guarda el estado actual. No repinta la vista (la ficha se actualiza en el
 * lugar para no perder el foco ni el scroll); solo cambia el origen a 'local'.
 */
export function save() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    source = 'local';
  } catch (err) {
    console.warn('No se pudo guardar en localStorage', err);
    return false;
  }
  return true;
}

export async function reset() {
  try { localStorage.removeItem(STORAGE_KEY); } catch { /* sin almacenamiento */ }
  state = await readSeed();
  source = 'semilla';
  listeners.forEach((fn) => fn(state));
  return state;
}

export function onChange(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export const getState = () => state;
export const getSource = () => source;

// --- Consultas de solo lectura ---

export const contracts = () => state.contratos;
export const steps = () => state.pasos;
export const alerts = () => state.alertas;
export const contract = (id) => state.contratos.find((c) => c.id === id) || null;

export function itemsOf(id, type) {
  return state.avances.filter((a) => a.contrato === id && a.tipo === type);
}

/** Avance 0..1 de un contrato (pasos hechos / total de pasos); null si no tiene tarjeta. */
export function progressOf(id) {
  const rows = itemsOf(id, 'paso');
  if (!rows.length) return null;
  return rows.filter((r) => r.hecho).length / state.pasos.length;
}

/** Promedio del avance de todos los contratos con tarjeta. */
export function generalProgress() {
  const values = state.contratos.map((c) => progressOf(c.id)).filter((v) => v !== null);
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0;
}

export function logOf(id) {
  return state.bitacora.filter((b) => b.contrato === id);
}

// --- Datos derivados (no se guardan: se calculan de los avances) ---

/** Responsables individuales: la celda del Excel a veces junta varios ("A y B", "A - B", "A, B"). */
export function responsiblesOf(c) {
  return (c.responsable || '')
    .split(/\s*,\s*|\s+y\s+|\s+-\s+/)
    .map((name) => name.trim())
    .filter(Boolean);
}

export function allResponsibles() {
  const names = new Set(state.contratos.flatMap(responsiblesOf));
  return [...names].sort((a, b) => a.localeCompare(b, 'es'));
}

const PARALYZED_ALERT = 1; // "Proceso paralizado por falta de información"

export const STATUSES = [
  { id: 'en-tramite', nombre: 'En trámite' },
  { id: 'paralizado', nombre: 'Paralizado' },
  { id: 'cerrado', nombre: 'Cerrado' },
  { id: 'sin-seguimiento', nombre: 'Sin seguimiento' },
];

/** Estado derivado: sin tarjeta > 12/12 pasos > alerta de paralizado activa > en trámite. */
export function statusOf(id) {
  const progress = progressOf(id);
  if (progress === null) return 'sin-seguimiento';
  if (progress === 1) return 'cerrado';
  const paralyzed = itemsOf(id, 'alerta').some((a) => a.item === PARALYZED_ALERT && a.hecho);
  return paralyzed ? 'paralizado' : 'en-tramite';
}

export const statusName = (status) => STATUSES.find((s) => s.id === status)?.nombre || status;

// --- Edición (cada función guarda y devuelve true si pudo) ---

function findItem(id, type, item) {
  return state.avances.find((a) => a.contrato === id && a.tipo === type && a.item === item);
}

/** Marca o desmarca un paso o una alerta. */
export function setItem(id, type, item, done) {
  const row = findItem(id, type, item);
  if (!row) return false;
  row.hecho = !!done;
  return save();
}

/** Fecha ISO (o '' para vaciarla) en 'perdida_competencia' o 'plazo_cierre'. */
export function setDate(id, field, iso) {
  const c = contract(id);
  if (!c || !['perdida_competencia', 'plazo_cierre'].includes(field)) return false;
  c[field] = iso || null;
  return save();
}

/** Agrega una entrada a la bitácora (origen 'app' para distinguirla de las del Excel). */
export function addLog(id, fecha, texto) {
  const text = String(texto || '').trim();
  if (!contract(id) || !text) return false;
  state.bitacora.push({ contrato: id, fecha: fecha || null, texto: text, origen: 'app' });
  return save();
}

/** Crea los pasos y alertas (todos sin marcar) de un contrato que no tenía tarjeta en el Excel. */
export function startTracking(id) {
  const c = contract(id);
  if (!c || c.tiene_tarjeta) return false;
  state.pasos.forEach((p) => state.avances.push({ contrato: id, tipo: 'paso', item: p.id, hecho: false, etiqueta: '' }));
  state.alertas.forEach((a) => state.avances.push({ contrato: id, tipo: 'alerta', item: a.id, hecho: false, etiqueta: '' }));
  c.tiene_tarjeta = true;
  return save();
}

/** Bitácora ordenada: más reciente primero; las entradas sin fecha al final, en su orden original. */
export function sortedLogOf(id) {
  const rows = logOf(id).map((b, i) => ({ ...b, _i: i }));
  return rows.sort((a, b) => {
    if (a.fecha && b.fecha) return b.fecha.localeCompare(a.fecha) || b._i - a._i;
    if (a.fecha) return -1;
    if (b.fecha) return 1;
    return a._i - b._i;
  });
}

/** Etapa actual: primer paso sin marcar (null si no hay tarjeta o ya cerró). */
export function currentStep(id) {
  const pending = itemsOf(id, 'paso').filter((r) => !r.hecho).sort((a, b) => a.item - b.item)[0];
  return pending ? state.pasos.find((p) => p.id === pending.item) : null;
}
