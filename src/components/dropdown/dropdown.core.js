/**
 * <ds-dropdown> — selector estilo "glass" con panel flotante (Fase 12,
 * adaptado desde Form_Comisiones). Custom element AUTÓNOMO y
 * FORM-ASSOCIATED (participa en <form> como un <select> real, vía
 * ElementInternals) — a diferencia del original, que necesitaba un
 * <input type="hidden"> aparte emparejado a mano por id.
 * Convención de .core.js: docs/05_BACKEND.md §4.
 *
 * Opciones: hijos livianos <option value="...">Texto</option> — reutiliza
 * la etiqueta nativa como fuente de datos (no se renderiza tal cual; este
 * componente solo lee su value/textContent y dibuja su propia lista dentro
 * del Shadow DOM). Se releen solas por MutationObserver: reemplaza a la
 * función global `llenarDropdown()` del original — basta con mutar los
 * <option> hijos (ej. `dropdown.innerHTML = '<option>...</option>'`).
 *
 * Panel flotante: en vez de "moverlo a <body>" (el truco del original para
 * escapar de un ancestro con overflow:hidden y evitar un glitch de
 * backdrop-filter), usa la Popover API (`popover="manual"`) — promueve el
 * panel a la "top layer" del navegador sin sacarlo del Shadow DOM (mantiene
 * el CSS encapsulado) y sin depender de qué ancestro lo contenga. La
 * posición (arriba/abajo del trigger) se sigue calculando a mano con
 * getBoundingClientRect(), igual que el original. Requiere un navegador con
 * Popover API (Chrome/Edge 114+, Firefox 125+, Safari 17+) — sin polyfill,
 * mismo criterio de "sin dependencias externas" de docs/05_BACKEND.md §4.
 *
 * A diferencia del original (que reubicaba el panel enganchándose a
 * `.ui-stepper__panel` específicamente), la reubicación por animación de un
 * ancestro es genérica: escucha `transitionend`/`animationend` en captura
 * mientras está abierto, sin que este componente conozca a Stepper ni a
 * ningún otro en particular.
 *
 * Validación: `required` se reporta vía ElementInternals — el estado de
 * error se ve con `:user-invalid` (pseudo-clase nativa), no con una clase
 * `.has-error` puesta a mano. `formResetCallback` limpia el valor;
 * `formDisabledCallback`/atributo `disabled` deshabilitan el trigger.
 */
class DsDropdown extends HTMLElement {
  static formAssociated = true;

  static get observedAttributes() {
    return ['required', 'placeholder', 'disabled'];
  }

  constructor() {
    super();
    this._internals = this.attachInternals();
    this._value = '';
    this._open = false;
  }

  connectedCallback() {
    if (!this.shadowRoot) this._build();
    this._syncOptions();
    this._updateValidity();
    this._observer = new MutationObserver(() => this._syncOptions());
    this._observer.observe(this, { childList: true });
  }

  disconnectedCallback() {
    this._observer?.disconnect();
    this._closePanel();
    document.removeEventListener('click', this._onDocClick, true);
    window.removeEventListener('scroll', this._onScroll, true);
    document.removeEventListener('transitionend', this._onAncestorTransition, true);
    document.removeEventListener('animationend', this._onAncestorTransition, true);
  }

  attributeChangedCallback(name) {
    if (!this._trigger) return; // upgrade: attributeChangedCallback puede llegar antes que connectedCallback
    if (name === 'required') this._updateValidity();
    if (name === 'placeholder') this._syncValueDisplay();
    if (name === 'disabled') {
      this._trigger.disabled = this.hasAttribute('disabled');
      if (this.hasAttribute('disabled')) this._closePanel();
    }
  }

  get value() {
    return this._value;
  }

  set value(v) {
    this._selectValue(v ?? '', { emit: false });
  }

  formResetCallback() {
    this._selectValue('', { emit: false });
  }

  formDisabledCallback(disabled) {
    this._trigger.disabled = disabled;
    if (disabled) this._closePanel();
  }

  _build() {
    const shadow = this.attachShadow({ mode: 'open' });
    shadow.innerHTML = `
      <style>
        :host { display: block; position: relative; width: 100%; }
        .trigger {
          appearance: none;
          -webkit-appearance: none;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: var(--dropdown-trigger-gap);
          width: 100%;
          box-sizing: border-box;
          padding-inline: var(--dropdown-trigger-padding-inline);
          padding-block: var(--dropdown-trigger-padding-block);
          min-height: var(--target-size-min);
          font: inherit;
          font-size: var(--font-size-md, 1rem);
          color: var(--color-text, inherit);
          text-align: left;
          cursor: pointer;
          background: var(--color-surface-alt, transparent);
          border: 1px solid var(--color-border, currentColor);
          border-radius: var(--radius-sm, 4px);
          backdrop-filter: blur(var(--surface-blur, 0));
          -webkit-backdrop-filter: blur(var(--surface-blur, 0));
          transition:
            background var(--motion-duration-fast, .15s) var(--motion-easing-standard, ease),
            border-color var(--motion-duration-fast, .15s) var(--motion-easing-standard, ease);
        }
        .trigger:disabled {
          opacity: .5;
          cursor: not-allowed;
        }
        .trigger:focus-visible {
          outline: var(--focus-offset-sm, 2px) solid var(--color-focus, currentColor);
          outline-offset: var(--focus-offset-sm, 2px);
        }
        :host(:user-invalid) .trigger {
          border-color: #ff8080;
        }
        :host([data-open]) .trigger {
          background: var(--color-surface, transparent);
          border-color: var(--color-accent, currentColor);
        }
        .value[data-empty] {
          color: var(--color-text-muted, inherit);
        }
        .chevron {
          flex-shrink: 0;
          transition: transform var(--motion-duration-fast, .15s) var(--motion-easing-standard, ease);
        }
        :host([data-open]) .chevron {
          transform: rotate(180deg);
        }
        .panel {
          position: fixed;
          inset: auto;
          margin: 0;
          z-index: var(--layer-dropdown, 200);
          box-sizing: border-box;
          max-height: var(--dropdown-panel-max-height);
          overflow-y: auto;
          padding: var(--dropdown-panel-padding);
          list-style: none;
          display: flex;
          flex-direction: column;
          gap: var(--space-1);
          background: var(--color-surface-panel, var(--color-surface, #fff));
          border: 1px solid var(--color-border, currentColor);
          border-radius: var(--radius-sm, 4px);
          backdrop-filter: blur(var(--surface-blur, 0));
          -webkit-backdrop-filter: blur(var(--surface-blur, 0));
        }
        /* Ajuste Liquidaciones_ESAP: display:flex anulaba el display:none del
           navegador para un popover cerrado — el panel cerrado seguía fijo en
           pantalla tapando los clics. Pendiente de llevar a Design_System_Core. */
        .panel:not(:popover-open) {
          display: none;
        }
        .option {
          display: flex;
          align-items: center;
          justify-content: space-between;
          width: 100%;
          box-sizing: border-box;
          padding-inline: var(--dropdown-option-padding-inline);
          padding-block: var(--dropdown-option-padding-block);
          font: inherit;
          font-size: var(--font-size-sm, .875rem);
          color: var(--color-text, inherit);
          text-align: left;
          background: transparent;
          border: 1px solid transparent;
          border-radius: var(--radius-sm, 4px);
          cursor: pointer;
          transition: background var(--motion-duration-fast, .15s) var(--motion-easing-standard, ease);
        }
        .option:hover {
          background: var(--color-hover, var(--color-surface-alt, transparent)); /* Ajuste Liquidaciones_ESAP */
          box-shadow:
            var(--surface-inner-top, 0 0 transparent),
            var(--surface-inner-bottom, 0 0 transparent),
            var(--surface-inner-glow, 0 0 transparent);
        }
        .option[aria-selected="true"] {
          background: var(--color-accent-surface, var(--color-surface-alt, transparent));
          border-color: var(--color-accent, currentColor);
          font-weight: var(--font-weight-medium, 500);
        }
        .option[aria-selected="true"]::after {
          content: '✓';
          margin-inline-start: var(--spacing-inline-sm, .5rem);
        }
        .option:focus-visible {
          outline: var(--focus-offset-sm, 2px) solid var(--color-focus, currentColor);
          outline-offset: var(--focus-offset-sm, 2px);
        }
      </style>
      <button type="button" class="trigger" part="trigger" aria-haspopup="listbox" aria-expanded="false">
        <span class="value" part="value" data-empty></span>
        <span class="chevron" part="chevron" aria-hidden="true">▾</span>
      </button>
      <ul class="panel" part="panel" role="listbox" popover="manual"></ul>
    `;
    this._trigger = shadow.querySelector('.trigger');
    this._valueEl = shadow.querySelector('.value');
    this._panel = shadow.querySelector('.panel');

    this._trigger.addEventListener('click', () => this._togglePanel());
    this._panel.addEventListener('click', (e) => {
      const opt = e.target.closest('[data-value]');
      if (opt) this._selectValue(opt.dataset.value, { emit: true });
    });
    this._panel.addEventListener('toggle', (e) => {
      // El navegador puede cerrar el popover por su cuenta (ej. Escape) —
      // mantiene _open/aria-expanded sincronizados en ese caso.
      if (e.newState === 'closed' && this._open) this._closePanel();
    });

    this._onDocClick = (e) => {
      if (!this._open) return;
      const path = e.composedPath();
      if (!path.includes(this._trigger) && !path.includes(this._panel)) this._closePanel();
    };
    this._onScroll = () => {
      if (this._open) this._closePanel();
    };
    this._onAncestorTransition = () => {
      if (this._open) this._positionPanel();
    };
    this.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this._open) {
        this._closePanel();
        this._trigger.focus();
      }
    });

    document.addEventListener('click', this._onDocClick, true);
    window.addEventListener('scroll', this._onScroll, true);
    document.addEventListener('transitionend', this._onAncestorTransition, true);
    document.addEventListener('animationend', this._onAncestorTransition, true);

    this._syncValueDisplay();
  }

  _syncOptions() {
    const options = Array.from(this.querySelectorAll(':scope > option'));
    this._panel.innerHTML = '';
    options.forEach((opt) => {
      const value = opt.getAttribute('value') ?? opt.textContent.trim();
      const li = document.createElement('li');
      li.setAttribute('role', 'presentation');
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'option';
      btn.setAttribute('role', 'option');
      btn.dataset.value = value;
      btn.textContent = opt.textContent.trim();
      btn.setAttribute('aria-selected', String(value === this._value));
      li.appendChild(btn);
      this._panel.appendChild(li);
    });
    this._syncValueDisplay();
  }

  _syncValueDisplay() {
    if (!this._valueEl) return;
    const options = Array.from(this.querySelectorAll(':scope > option'));
    const selected = options.find((o) => (o.getAttribute('value') ?? o.textContent.trim()) === this._value);
    if (selected) {
      this._valueEl.textContent = selected.textContent.trim();
      this._valueEl.removeAttribute('data-empty');
    } else {
      this._valueEl.textContent = this.getAttribute('placeholder') || 'Seleccione...';
      this._valueEl.setAttribute('data-empty', '');
    }
  }

  _selectValue(value, { emit }) {
    this._value = value;
    this._internals.setFormValue(value);
    this._panel.querySelectorAll('[data-value]').forEach((btn) => {
      btn.setAttribute('aria-selected', String(btn.dataset.value === value));
    });
    this._syncValueDisplay();
    this._updateValidity();
    if (emit) {
      this._closePanel();
      this.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
    }
  }

  _updateValidity() {
    if (!this._internals) return;
    if (this.hasAttribute('required') && !this._value) {
      this._internals.setValidity({ valueMissing: true }, 'Seleccioná una opción.', this._trigger);
    } else {
      this._internals.setValidity({});
    }
  }

  _togglePanel() {
    if (this._open) this._closePanel();
    else this._openPanel();
  }

  _openPanel() {
    if (this.hasAttribute('disabled')) return;
    this._open = true;
    this.setAttribute('data-open', '');
    this._trigger.setAttribute('aria-expanded', 'true');
    this._panel.showPopover();
    this._positionPanel();
  }

  _closePanel() {
    if (!this._open) return;
    this._open = false;
    this.removeAttribute('data-open');
    this._trigger.setAttribute('aria-expanded', 'false');
    if (this._panel.matches(':popover-open')) this._panel.hidePopover();
  }

  _positionPanel() {
    const rect = this._trigger.getBoundingClientRect();
    this._panel.style.left = `${rect.left}px`;
    this._panel.style.width = `${rect.width}px`;
    // 4px: mismo criterio que un hairline border (button.core.js usa "1px"
    // sin token) — separación mínima entre trigger y panel, geometría de
    // posicionamiento en runtime, no una decisión de spacing del sistema.
    this._panel.style.top = `${rect.bottom + 4}px`;

    const panelRect = this._panel.getBoundingClientRect();
    if (panelRect.bottom > window.innerHeight) {
      this._panel.style.top = `${rect.top - panelRect.height - 4}px`;
    }
  }
}

customElements.define('ds-dropdown', DsDropdown);
