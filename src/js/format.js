/** Utilidades de formato y escape compartidas por las vistas. */
const pct = new Intl.NumberFormat('es-CO', { style: 'percent', maximumFractionDigits: 1 });
const money = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });
const day = new Intl.DateTimeFormat('es-CO', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' });

export const percent = (v) => (v === null || v === undefined ? '—' : pct.format(v));
export const currency = (v) => (typeof v === 'number' && v > 0 ? money.format(v) : '—');
export const date = (iso) => (iso ? day.format(new Date(iso + 'T00:00:00Z')) : '—');

export function escapeHtml(text) {
  return String(text ?? '').replace(/[&<>"']/g, (ch) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]
  ));
}
