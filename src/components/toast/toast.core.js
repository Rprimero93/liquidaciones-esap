/**
 * <ds-toast> — aviso flotante (Fase 10, adaptado desde Form_Comisiones).
 * Custom element AUTÓNOMO, Shadow DOM: envuelve un <div role="status"> (no
 * hay elemento nativo equivalente, a diferencia de <ds-button> que envuelve
 * un <button> real). Convención de .core.js: docs/05_BACKEND.md §4.
 *
 * Slots: por defecto (mensaje) + `actions` (opcional — botones, ej.
 * <ds-button density="compact">). El Core NO decide layout de página: no se
 * posiciona a sí mismo como capa fija en el borde de la ventana ni apila
 * varias instancias — eso es responsabilidad de quien lo monta (ver
 * stories/toast.story.js), igual que <ds-button> no decide el layout de fila
 * de botones (docs/05_BACKEND.md §9). Tampoco conoce lógica de "confirmación"
 * (Sí/No + callback): eso queda para el consumidor, que escucha los clicks
 * de lo que slotee en `actions` y llama a `dismiss()` cuando corresponda
 * (mismo patrón que `confirmarToast()` resolvía a mano en Form_Comisiones,
 * ahora fuera del Core — igual que el click de <ds-button> no se reenvía a
 * mano, es un evento compuesto que atraviesa el Shadow DOM solo).
 *
 * Atributos:
 * - `auto-dismiss` (ms, opcional): si está presente y es > 0, se autocierra
 *   solo tras ese tiempo (equivalente a `mostrarToast(mensaje, duracionMs)`).
 * Método público:
 * - `dismiss()`: dispara el evento `close` (bubbles, composed) y se quita a
 *   sí mismo del DOM tras la animación de salida (o de inmediato con
 *   `prefers-reduced-motion: reduce`, que no dispara `animationend`).
 *
 * Primer componente del Core que consume `--surface-blur` (vía
 * backdrop-filter) — definido en los 3 estilos desde la Fase 3 pero sin
 * consumidor real hasta ahora (`<ds-button>` no lo usa).
 */
class DsToast extends HTMLElement {
  connectedCallback() {
    if (this.shadowRoot) return; // ya montado (reconexión al DOM)
    const shadow = this.attachShadow({ mode: 'open' });
    shadow.innerHTML = `
      <style>
        :host {
          display: block;
          box-sizing: border-box;
          position: relative;
          z-index: var(--layer-toast, 500);
          max-width: min(90vw, var(--toast-max-width));
          animation: ds-toast-in var(--motion-duration-fast, .15s) var(--motion-easing-standard, ease);
        }
        :host([closing]) {
          animation: ds-toast-out var(--motion-duration-fast, .15s) var(--motion-easing-standard, ease) forwards;
        }
        .card {
          box-sizing: border-box;
          display: flex;
          align-items: center;
          gap: var(--toast-content-gap);
          background: var(--color-surface-panel, var(--color-surface, #fff));
          border: 1px solid var(--color-border, currentColor);
          border-radius: var(--radius-md, 4px);
          padding-inline: var(--toast-padding-inline);
          padding-block: var(--toast-padding-block);
          backdrop-filter: blur(var(--surface-blur, 0));
          -webkit-backdrop-filter: blur(var(--surface-blur, 0));
          box-shadow:
            var(--shadow-lg, none),
            var(--surface-inner-top, 0 0 transparent),
            var(--surface-inner-bottom, 0 0 transparent);
        }
        .msg {
          flex: 1;
          margin: 0;
          font-family: var(--font-family-base, inherit);
          font-size: var(--font-size-sm, .875rem);
          color: var(--color-text, inherit);
        }
        .actions {
          display: flex;
          gap: var(--toast-actions-gap);
          flex-shrink: 0;
        }
        .actions[hidden] {
          display: none;
        }
        @keyframes ds-toast-in {
          from { opacity: 0; transform: translateY(var(--space-2, .5rem)); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes ds-toast-out {
          from { opacity: 1; transform: translateY(0); }
          to   { opacity: 0; transform: translateY(var(--space-2, .5rem)); }
        }
        @media (prefers-reduced-motion: reduce) {
          :host, :host([closing]) { animation: none; }
        }
      </style>
      <div class="card" part="card">
        <p class="msg" part="message"><slot></slot></p>
        <div class="actions" part="actions" hidden><slot name="actions"></slot></div>
      </div>
    `;

    // ARIA: el host es el nodo real en el árbol de accesibilidad — se
    // completa solo si el consumidor no lo pisó a mano (ej. role="alert"
    // para un caso más urgente que el status/polite por defecto).
    if (!this.hasAttribute('role')) this.setAttribute('role', 'status');
    if (!this.hasAttribute('aria-live')) this.setAttribute('aria-live', 'polite');

    // El slot "actions" no debe dejar un gap vacío cuando nadie sloteó nada.
    const actionsSlot = shadow.querySelector('slot[name="actions"]');
    const actionsWrap = shadow.querySelector('.actions');
    const syncActions = () => {
      actionsWrap.hidden = actionsSlot.assignedElements().length === 0;
    };
    actionsSlot.addEventListener('slotchange', syncActions);
    syncActions();

    const ms = Number(this.getAttribute('auto-dismiss'));
    if (ms > 0) this._timer = setTimeout(() => this.dismiss(), ms);
  }

  disconnectedCallback() {
    clearTimeout(this._timer);
  }

  dismiss() {
    if (this._dismissing) return;
    this._dismissing = true;
    clearTimeout(this._timer);
    this.dispatchEvent(new CustomEvent('close', { bubbles: true, composed: true }));
    this.setAttribute('closing', '');
    const finish = () => this.remove();
    // Con prefers-reduced-motion la animación de salida queda anulada
    // (ver <style> arriba) y 'animationend' nunca llegaría a disparar.
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
      finish();
    } else {
      this.addEventListener('animationend', finish, { once: true });
    }
  }
}

customElements.define('ds-toast', DsToast);
