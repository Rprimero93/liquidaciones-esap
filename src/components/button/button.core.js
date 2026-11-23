/**
 * <ds-button> — primer componente real del sistema (Fase 5, piloto).
 * Custom element AUTÓNOMO (no "customized built-in": Safari no soporta
 * `class extends HTMLButtonElement`, Regla 10) que envuelve un <button> real
 * dentro de su Shadow DOM — conserva la semántica nativa (teclado, :disabled,
 * :focus-visible) sin reimplementar nada de eso a mano.
 * Convención de .core.js: docs/05_BACKEND.md §4.
 *
 * Atributos reenvía al <button> interno: `disabled`, `type`.
 * `density="compact"|"comfortable"` (sin atributo = Default) se resuelve
 * solo con CSS (`:host([density=...])`), no reenvía nada al <button>.
 * El evento `click` no necesita reenvío manual: `click` es un evento
 * compuesto (composed: true) y atraviesa el límite del Shadow DOM solo.
 */
class DsButton extends HTMLElement {
  static get observedAttributes() {
    return ['disabled', 'type'];
  }

  connectedCallback() {
    if (this.shadowRoot) return; // ya montado (reconexión al DOM)
    const shadow = this.attachShadow({ mode: 'open' });
    shadow.innerHTML = `
      <style>
        :host {
          display: inline-block;
          --_padding-inline: var(--button-padding-inline);
          --_padding-block: var(--button-padding-block);
          --_gap: var(--button-content-gap);
        }
        :host([density="compact"]) {
          --_padding-inline: var(--button-padding-inline-compact);
          --_padding-block: var(--button-padding-block-compact);
          --_gap: var(--button-content-gap-compact);
        }
        :host([density="comfortable"]) {
          --_padding-inline: var(--button-padding-inline-comfortable);
          --_padding-block: var(--button-padding-block-comfortable);
          --_gap: var(--button-content-gap-comfortable);
        }
        button {
          all: unset;
          box-sizing: border-box;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: var(--_gap);
          padding-inline: var(--_padding-inline);
          padding-block: var(--_padding-block);
          min-height: var(--target-size-min);
          min-width: var(--target-size-min);
          font-family: var(--font-family-base, inherit);
          font-size: var(--font-size-md, 1rem);
          font-weight: var(--font-weight-medium, 500);
          color: var(--color-text, inherit);
          background: var(--color-surface, transparent);
          border: 1px solid var(--color-border, currentColor);
          border-radius: var(--radius-md, 4px);
          cursor: pointer;
          box-shadow:
            var(--shadow-sm, none),
            var(--surface-inner-bottom, 0 0 transparent);
          transition:
            transform var(--motion-duration-fast, .15s) var(--motion-easing-standard, ease),
            box-shadow var(--motion-duration-fast, .15s) var(--motion-easing-standard, ease),
            background var(--motion-duration-fast, .15s) var(--motion-easing-standard, ease),
            border-color var(--motion-duration-fast, .15s) var(--motion-easing-standard, ease);
        }
        button:hover:not(:disabled) {
          background: var(--color-surface-alt, var(--color-surface));
          border-color: var(--color-accent, var(--color-border));
          transform: var(--transform-hover-lift, translateY(-2px));
          /* Hover activa el rim-light completo (glassmorphism) — Default
             solo usa --surface-inner-bottom (docs/05_BACKEND.md §7). */
          box-shadow:
            var(--shadow-md, var(--shadow-sm)),
            var(--surface-inner-top, 0 0 transparent),
            var(--surface-inner-bottom, 0 0 transparent),
            var(--surface-inner-glow, 0 0 transparent);
        }
        button:active:not(:disabled) {
          transform: var(--transform-active-press, scale(.97));
          box-shadow: var(--shadow-sm, none), var(--surface-inner-bottom, 0 0 transparent);
        }
        button:focus-visible {
          outline: var(--focus-offset-sm, 2px) solid var(--color-focus, currentColor);
          outline-offset: var(--focus-offset-sm, 2px);
        }
        button:disabled {
          opacity: .5;
          cursor: not-allowed;
          transform: none;
        }
      </style>
      <button type="button" part="button">
        <slot></slot>
      </button>
    `;
    this._button = shadow.querySelector('button');
    this._syncFromAttributes();
  }

  attributeChangedCallback() {
    this._syncFromAttributes();
  }

  _syncFromAttributes() {
    if (!this._button) return;
    this._button.disabled = this.hasAttribute('disabled');
    this._button.type = this.getAttribute('type') || 'button';
  }
}

customElements.define('ds-button', DsButton);
