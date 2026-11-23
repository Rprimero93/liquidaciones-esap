/**
 * <ds-datepicker> — selector de fecha propio (Fase 14, adaptado desde
 * Form_Comisiones), reemplaza <input type="date"> donde el calendario
 * nativo del navegador no se puede restylear. Mismo patrón arquitectónico
 * que <ds-dropdown> (Fase 12) — panel flotante vía Popover API, form-
 * associated vía ElementInternals, reposicionamiento genérico en vez de
 * acoplarse a Stepper — así que este comentario documenta solo lo propio
 * de Datepicker; el resto está detallado en dropdown.core.js.
 * Convención de .core.js: docs/05_BACKEND.md §4.
 *
 * Valor: `value` (propiedad JS) en ISO `AAAA-MM-DD` — mismo formato que
 * `<input type="date">` nativo (más fácil de consumir después por
 * Power Automate/SharePoint que un texto libre), a diferencia del original
 * que necesitaba un `<input type="hidden">` aparte para cargar ese ISO.
 * Texto visible en el trigger: `DD-MM-AAAA`. Semana empieza en lunes
 * (convención local, no la del navegador) — igual que el original.
 *
 * Atributos: `required`, `placeholder` (default "dd-mm-aaaa"), `disabled`,
 * `value` (ISO, solo como valor inicial — ver connectedCallback).
 */
const MESES = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
];

function pad(n) {
  return String(n).padStart(2, '0');
}

function aIso(anio, mes, dia) {
  return `${anio}-${pad(mes + 1)}-${pad(dia)}`;
}

function aVisible(anio, mes, dia) {
  return `${pad(dia)}-${pad(mes + 1)}-${anio}`;
}

function parseIso(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '');
  if (!m) return null;
  return { anio: Number(m[1]), mes: Number(m[2]) - 1, dia: Number(m[3]) };
}

class DsDatepicker extends HTMLElement {
  static formAssociated = true;

  static get observedAttributes() {
    return ['required', 'placeholder', 'disabled'];
  }

  constructor() {
    super();
    this._internals = this.attachInternals();
    this._value = '';
    this._open = false;
    const hoy = new Date();
    this._vistaAnio = hoy.getFullYear();
    this._vistaMes = hoy.getMonth();
  }

  connectedCallback() {
    if (!this.shadowRoot) this._build();
    const inicial = parseIso(this.getAttribute('value'));
    if (inicial) this._selectDate(inicial.anio, inicial.mes, inicial.dia, { emit: false });
    this._updateValidity();
  }

  disconnectedCallback() {
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

  set value(iso) {
    const parsed = parseIso(iso);
    if (parsed) this._selectDate(parsed.anio, parsed.mes, parsed.dia, { emit: false });
    else {
      this._value = '';
      this._internals.setFormValue('');
      this._syncValueDisplay();
      this._updateValidity();
    }
  }

  formResetCallback() {
    this.value = '';
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
          gap: var(--datepicker-trigger-gap);
          width: 100%;
          box-sizing: border-box;
          padding-inline: var(--datepicker-trigger-padding-inline);
          padding-block: var(--datepicker-trigger-padding-block);
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
        .trigger:disabled { opacity: .5; cursor: not-allowed; }
        .trigger:focus-visible {
          outline: var(--focus-offset-sm, 2px) solid var(--color-focus, currentColor);
          outline-offset: var(--focus-offset-sm, 2px);
        }
        :host(:user-invalid) .trigger { border-color: #ff8080; }
        :host([data-open]) .trigger {
          background: var(--color-surface, transparent);
          border-color: var(--color-accent, currentColor);
        }
        .value[data-empty] { color: var(--color-text-muted, inherit); }

        .panel {
          position: fixed;
          inset: auto;
          margin: 0;
          z-index: var(--layer-dropdown, 200);
          width: var(--datepicker-panel-width);
          max-width: 90vw;
          box-sizing: border-box;
          padding: var(--datepicker-panel-padding);
          background: var(--color-surface-panel, var(--color-surface, #fff));
          border: 1px solid var(--color-border, currentColor);
          border-radius: var(--radius-sm, 4px);
          backdrop-filter: blur(var(--surface-blur, 0));
          -webkit-backdrop-filter: blur(var(--surface-blur, 0));
          box-shadow: var(--shadow-md, none);
        }
        .nav {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: var(--datepicker-nav-gap);
          margin-block-end: var(--datepicker-nav-margin-block-end);
        }
        .month-label {
          font-size: var(--font-size-sm, .875rem);
          font-weight: var(--font-weight-medium, 500);
          color: var(--color-text, inherit);
          text-transform: capitalize;
        }
        .nav-btn {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: var(--datepicker-nav-btn-size);
          height: var(--datepicker-nav-btn-size);
          padding: 0;
          font: inherit;
          color: var(--color-text, inherit);
          background: transparent;
          border: 1px solid var(--color-border, currentColor);
          border-radius: var(--radius-sm, 4px);
          cursor: pointer;
          transition: background var(--motion-duration-fast, .15s) var(--motion-easing-standard, ease);
        }
        .nav-btn:hover { background: var(--color-hover, var(--color-surface-alt, transparent)); } /* Ajuste Liquidaciones_ESAP */
        .nav-btn:focus-visible {
          outline: var(--focus-offset-sm, 2px) solid var(--color-focus, currentColor);
          outline-offset: var(--focus-offset-sm, 2px);
        }
        .weekdays {
          display: grid;
          grid-template-columns: repeat(7, 1fr);
          gap: var(--datepicker-grid-gap);
          margin-block-end: var(--datepicker-weekdays-margin-block-end);
        }
        .weekdays span {
          font-size: .7rem;
          text-align: center;
          color: var(--color-text-muted, inherit);
        }
        .days {
          display: grid;
          grid-template-columns: repeat(7, 1fr);
          gap: var(--datepicker-grid-gap);
        }
        .day {
          aspect-ratio: 1;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          padding: 0;
          font: inherit;
          font-size: var(--font-size-sm, .875rem);
          color: var(--color-text, inherit);
          background: transparent;
          border: 1px solid transparent;
          border-radius: var(--radius-sm, 4px);
          cursor: pointer;
          transition: background var(--motion-duration-fast, .15s) var(--motion-easing-standard, ease);
        }
        .day:hover { background: var(--color-hover, var(--color-surface-alt, transparent)); } /* Ajuste Liquidaciones_ESAP */
        .day:focus-visible {
          outline: var(--focus-offset-sm, 2px) solid var(--color-focus, currentColor);
          outline-offset: var(--focus-offset-sm, 2px);
        }
        .day.is-today { border-color: var(--color-border, currentColor); }
        .day.is-selected {
          background: var(--color-accent-surface, var(--color-surface-alt, transparent));
          border-color: var(--color-accent, currentColor);
          font-weight: var(--font-weight-bold, 700);
        }
        .day--vacio { cursor: default; visibility: hidden; }
      </style>
      <button type="button" class="trigger" part="trigger" aria-haspopup="dialog" aria-expanded="false">
        <span class="value" part="value" data-empty></span>
        <span aria-hidden="true">📅</span>
      </button>
      <div class="panel" part="panel" role="dialog" aria-label="Elegir fecha" popover="manual">
        <div class="nav" part="nav">
          <button type="button" class="nav-btn prev" part="prev-button" aria-label="Mes anterior">‹</button>
          <span class="month-label" part="month-label"></span>
          <button type="button" class="nav-btn next" part="next-button" aria-label="Mes siguiente">›</button>
        </div>
        <div class="weekdays" part="weekdays">
          <span>Lu</span><span>Ma</span><span>Mi</span><span>Ju</span><span>Vi</span><span>Sá</span><span>Do</span>
        </div>
        <div class="days" part="days" role="grid"></div>
      </div>
    `;
    this._trigger = shadow.querySelector('.trigger');
    this._valueEl = shadow.querySelector('.value');
    this._panel = shadow.querySelector('.panel');
    this._monthLabel = shadow.querySelector('.month-label');
    this._daysEl = shadow.querySelector('.days');

    this._trigger.addEventListener('click', () => this._togglePanel());
    shadow.querySelector('.prev').addEventListener('click', () => this._changeMonth(-1));
    shadow.querySelector('.next').addEventListener('click', () => this._changeMonth(1));
    this._panel.addEventListener('toggle', (e) => {
      if (e.newState === 'closed' && this._open) this._closePanel();
    });

    this._onDocClick = (e) => {
      if (!this._open) return;
      const path = e.composedPath();
      if (!path.includes(this._trigger) && !path.includes(this._panel)) this._closePanel();
    };
    this._onScroll = () => { if (this._open) this._closePanel(); };
    this._onAncestorTransition = () => { if (this._open) this._positionPanel(); };

    document.addEventListener('click', this._onDocClick, true);
    window.addEventListener('scroll', this._onScroll, true);
    document.addEventListener('transitionend', this._onAncestorTransition, true);
    document.addEventListener('animationend', this._onAncestorTransition, true);
    this.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this._open) {
        this._closePanel();
        this._trigger.focus();
      }
    });

    this._syncValueDisplay();
    this._renderCalendar();
  }

  _changeMonth(delta) {
    this._vistaMes += delta;
    if (this._vistaMes < 0) {
      this._vistaMes = 11;
      this._vistaAnio -= 1;
    } else if (this._vistaMes > 11) {
      this._vistaMes = 0;
      this._vistaAnio += 1;
    }
    this._renderCalendar();
  }

  _renderCalendar() {
    if (!this._daysEl) return;
    const hoy = new Date();
    const seleccionado = parseIso(this._value);

    this._monthLabel.textContent = `${MESES[this._vistaMes]} ${this._vistaAnio}`;
    this._daysEl.innerHTML = '';

    // getDay(): 0=domingo..6=sábado -> se rota para que 0=lunes.
    const primerDiaSemana = (new Date(this._vistaAnio, this._vistaMes, 1).getDay() + 6) % 7;
    const diasEnMes = new Date(this._vistaAnio, this._vistaMes + 1, 0).getDate();

    for (let i = 0; i < primerDiaSemana; i++) {
      const relleno = document.createElement('span');
      relleno.className = 'day day--vacio';
      relleno.setAttribute('aria-hidden', 'true');
      this._daysEl.appendChild(relleno);
    }

    for (let dia = 1; dia <= diasEnMes; dia++) {
      const boton = document.createElement('button');
      boton.type = 'button';
      boton.className = 'day';
      boton.setAttribute('role', 'gridcell');
      boton.textContent = String(dia);

      if (this._vistaAnio === hoy.getFullYear() && this._vistaMes === hoy.getMonth() && dia === hoy.getDate()) {
        boton.classList.add('is-today');
      }
      if (seleccionado && seleccionado.anio === this._vistaAnio && seleccionado.mes === this._vistaMes && seleccionado.dia === dia) {
        boton.classList.add('is-selected');
        boton.setAttribute('aria-selected', 'true');
      }

      boton.addEventListener('click', () => this._selectDate(this._vistaAnio, this._vistaMes, dia, { emit: true }));
      this._daysEl.appendChild(boton);
    }
  }

  _selectDate(anio, mes, dia, { emit }) {
    this._value = aIso(anio, mes, dia);
    this._vistaAnio = anio;
    this._vistaMes = mes;
    this._internals.setFormValue(this._value);
    this._syncValueDisplay();
    this._updateValidity();
    this._renderCalendar();
    if (emit) {
      this._closePanel();
      this.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
    }
  }

  _syncValueDisplay() {
    if (!this._valueEl) return;
    const parsed = parseIso(this._value);
    if (parsed) {
      this._valueEl.textContent = aVisible(parsed.anio, parsed.mes, parsed.dia);
      this._valueEl.removeAttribute('data-empty');
    } else {
      this._valueEl.textContent = this.getAttribute('placeholder') || 'dd-mm-aaaa';
      this._valueEl.setAttribute('data-empty', '');
    }
  }

  _updateValidity() {
    if (!this._internals) return;
    if (this.hasAttribute('required') && !this._value) {
      this._internals.setValidity({ valueMissing: true }, 'Elegí una fecha.', this._trigger);
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
    // 4px: mismo criterio que un hairline border (ver dropdown.core.js) —
    // separación mínima entre trigger y panel, geometría de runtime.
    this._panel.style.top = `${rect.bottom + 4}px`;

    const panelRect = this._panel.getBoundingClientRect();
    if (panelRect.bottom > window.innerHeight) {
      this._panel.style.top = `${rect.top - panelRect.height - 4}px`;
    }
  }
}

customElements.define('ds-datepicker', DsDatepicker);
