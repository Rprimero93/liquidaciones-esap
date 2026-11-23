/**
 * <ds-sidebar> — sidebar de navegación (Fase 13, adaptado desde
 * Form_Comisiones). Custom element AUTÓNOMO, Shadow DOM. Convención de
 * .core.js: docs/05_BACKEND.md §4.
 *
 * `:host { display: contents }` a propósito: el host no participa como caja
 * en el layout del consumidor — sus hijos reales de Shadow DOM (`.sidebar`
 * y el botón de reapertura) sí, como si fueran hijos directos de quien lo
 * monte (ej. un contenedor flex `Sidebar | Main`, docs/referencias/
 * Sistema_Maquetado_UI_Layout_System.md §10). El Core NO decide su propia
 * posición de página (nada de position:sticky/fixed) — eso es responsabilidad
 * de quien lo monta, mismo criterio que Toast/Button no deciden layout de
 * página (docs/05_BACKEND.md §9).
 *
 * Enlaces: hijos livianos <a>/<span> en el slot por defecto — se SLOTEAN de
 * verdad (a diferencia de Dropdown, que solo lee sus <option> como datos):
 * un <a> real conserva semántica nativa (click derecho, Ctrl+click, foco,
 * SEO) que reconstruirlo en el Shadow DOM perdería. `::slotted(a)` da estilo
 * a los enlaces reales; `::slotted(:not(a))` (ej. un <span>) es el mismo
 * tratamiento "sección todavía no construida" del original — sin href, sin
 * foco ni click, no necesita ningún atributo extra: un <span> ya carece de
 * esas capacidades de por sí.
 *
 * 3 mecanismos independientes (nunca una sola alternancia para más de un
 * estado — lección del proyecto de origen, ver comentario del sidebar.js
 * original): colapsar a solo íconos (atributo `collapsed`), cerrar del todo
 * (oculta `.sidebar`, muestra el botón de reapertura) y reabrir.
 *
 * Mobile (< 768px, breakpoint `md` de referencia — docs/05_BACKEND.md §5):
 * pasa a barra horizontal en el flujo normal, no a un overlay superpuesto —
 * desviación consciente del "Sidebar Overlay" que sugiere
 * Sistema_Maquetado_UI_Layout_System.md §10 (decisión de descubrimiento de
 * esta fase): se porta el comportamiento real y ya verificado de
 * Form_Comisiones, no un mecanismo nuevo (drawer con backdrop) que ese
 * proyecto nunca construyó ni probó. El breakpoint del original era 720px
 * (un valor propio, no una referencia del sistema) — se ajustó a 768px
 * (`md`) para no inventar un corte fuera de la escala ya establecida.
 */
class DsSidebar extends HTMLElement {
  static get observedAttributes() {
    return ['brand', 'collapsed'];
  }

  connectedCallback() {
    if (!this.shadowRoot) this._build();
    this._syncBrand();
    this._syncCollapsed();
  }

  attributeChangedCallback(name) {
    if (!this._nav) return; // upgrade: attributeChangedCallback puede llegar antes que connectedCallback
    if (name === 'brand') this._syncBrand();
    if (name === 'collapsed') this._syncCollapsed();
  }

  _build() {
    const shadow = this.attachShadow({ mode: 'open' });
    shadow.innerHTML = `
      <style>
        :host { display: contents; }

        .sidebar {
          position: relative;
          flex-shrink: 0;
          width: var(--sidebar-width-expanded);
          box-sizing: border-box;
          display: flex;
          flex-direction: column;
          gap: var(--sidebar-gap);
          padding: var(--sidebar-padding);
          background: var(--color-surface, transparent);
          border: 1px solid var(--color-border, currentColor);
          border-radius: var(--radius-lg, 4px);
          backdrop-filter: blur(var(--surface-blur, 0));
          -webkit-backdrop-filter: blur(var(--surface-blur, 0));
          box-shadow:
            var(--surface-inner-top, 0 0 transparent),
            var(--surface-inner-bottom, 0 0 transparent);
          transition: width var(--motion-duration-fast, .15s) var(--motion-easing-standard, ease);
          /* overflow:hidden recorta el rim-light de abajo a la curva del
             border-radius en las esquinas (mismo motivo que el original). */
          overflow: hidden;
        }

        /* Rim-light en los 4 bordes — mismo mecanismo que el resto de las
           superficies de vidrio (docs/05_BACKEND.md §7). */
        .sidebar::before {
          content: '';
          position: absolute;
          inset: 0;
          pointer-events: none;
          background:
            linear-gradient(90deg, transparent, var(--surface-highlight-top, transparent), transparent) top / 100% 1px no-repeat,
            linear-gradient(90deg, transparent, var(--surface-highlight-top, transparent), transparent) bottom / 100% 1px no-repeat;
        }
        .sidebar::after {
          content: '';
          position: absolute;
          inset: 0;
          pointer-events: none;
          background:
            linear-gradient(180deg, var(--surface-highlight-edge-top, transparent), transparent, var(--surface-highlight-edge-bottom, transparent)) left / 1px 100% no-repeat,
            linear-gradient(180deg, var(--surface-highlight-edge-top, transparent), transparent, var(--surface-highlight-edge-bottom, transparent)) right / 1px 100% no-repeat;
        }

        .head {
          position: relative;
          z-index: 1;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: var(--spacing-inline-sm, .5rem);
        }
        .brand {
          font-family: var(--font-family-heading, inherit);
          font-weight: var(--font-weight-bold, 700);
          color: var(--color-text, inherit);
          font-size: var(--font-size-sm, .875rem);
        }
        .icon-button {
          appearance: none;
          -webkit-appearance: none;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: var(--sidebar-icon-button-size);
          height: var(--sidebar-icon-button-size);
          flex-shrink: 0;
          color: var(--color-text, inherit);
          cursor: pointer;
          background: var(--color-surface-alt, transparent);
          border: 1px solid var(--color-border, currentColor);
          border-radius: var(--radius-sm, 4px);
          transition:
            transform var(--motion-duration-fast, .15s) var(--motion-easing-standard, ease),
            background var(--motion-duration-fast, .15s) var(--motion-easing-standard, ease);
        }
        .icon-button svg {
          width: var(--sidebar-icon-button-icon-size);
          height: var(--sidebar-icon-button-icon-size);
        }
        .icon-button:hover {
          background: var(--color-hover, var(--color-surface, transparent)); /* Ajuste Liquidaciones_ESAP */
        }
        .icon-button:focus-visible {
          outline: none;
          border-width: 2px;
          border-color: var(--color-focus, currentColor);
        }
        :host([collapsed]) .collapse {
          transform: rotate(180deg);
        }
        /* Ajuste Liquidaciones_ESAP: display de .sidebar/.icon-button anulaba
           [hidden], así que el botón de reapertura se veía siempre y
           "cerrar" no ocultaba el menú. Pendiente de llevar a Design_System_Core. */
        .sidebar[hidden],
        .icon-button[hidden] {
          display: none;
        }

        .links {
          position: relative;
          z-index: 1;
          display: flex;
          flex-direction: column;
          gap: var(--sidebar-links-gap);
        }
        ::slotted(a) {
          display: flex;
          align-items: center;
          gap: var(--sidebar-link-gap);
          color: var(--color-text-muted, inherit);
          text-decoration: none;
          font-size: var(--font-size-sm, .875rem);
          font-weight: var(--font-weight-medium, 500);
          padding: var(--sidebar-link-padding-block) var(--sidebar-link-padding-inline);
          min-height: var(--target-size-comfort, 2.75rem);
          box-sizing: border-box;
          border-radius: var(--radius-sm, 4px);
          border: 1px solid transparent;
          transition:
            color var(--motion-duration-fast, .15s) var(--motion-easing-standard, ease),
            background var(--motion-duration-fast, .15s) var(--motion-easing-standard, ease);
        }
        ::slotted(a:hover) {
          color: var(--color-text, inherit);
          background: var(--color-surface-alt, transparent);
        }
        ::slotted(a:focus-visible) {
          outline: none;
          border-color: var(--color-focus, currentColor);
        }
        ::slotted(a[aria-current="page"]) {
          color: var(--color-text, inherit);
          background: var(--color-accent-surface, var(--color-surface-alt, transparent));
        }
        /* Sección todavía no construida: un <span> (o cualquier no-<a>) en
           vez de un link muerto — sin foco/click, mismo criterio que el
           original (docs/05_BACKEND.md, ver comentario de la clase). */
        ::slotted(:not(a)) {
          display: flex;
          align-items: center;
          gap: var(--sidebar-link-gap);
          padding: var(--sidebar-link-padding-block) var(--sidebar-link-padding-inline);
          min-height: var(--target-size-comfort, 2.75rem);
          box-sizing: border-box;
          color: var(--color-text-muted, inherit);
          font-size: var(--font-size-sm, .875rem);
          font-weight: var(--font-weight-medium, 500);
          opacity: .5;
        }
        ::slotted(a) svg,
        ::slotted(:not(a)) svg {
          width: var(--sidebar-link-icon-size);
          height: var(--sidebar-link-icon-size);
          flex-shrink: 0;
        }

        /* ===== Colapsada a íconos ===== */
        :host([collapsed]) .sidebar {
          width: var(--sidebar-width-collapsed);
          padding-inline: var(--sidebar-padding-inline-collapsed);
        }
        :host([collapsed]) .head {
          flex-direction: column;
          gap: var(--spacing-inline-xs, .25rem);
        }
        :host([collapsed]) .brand {
          display: none;
        }
        /* ::slotted() no admite combinadores hacia adentro del contenido
           sloteado (no hay forma de seleccionar "el <span> de texto dentro
           del <a>" desde acá) — en vez de eso, font-size:0 colapsa
           visualmente cualquier texto directo a 0 sin tocar el <svg> del
           ícono (que mide en px fijos, no en em). El texto sigue en el DOM,
           así que el nombre accesible del link NO desaparece — a diferencia
           del original, que usaba display:none y sí lo perdía. */
        :host([collapsed]) ::slotted(a),
        :host([collapsed]) ::slotted(:not(a)) {
          justify-content: center;
          gap: 0;
          font-size: 0;
        }

        /* ===== Cerrada del todo ===== */
        .reopen {
          backdrop-filter: blur(var(--surface-blur, 0));
          -webkit-backdrop-filter: blur(var(--surface-blur, 0));
        }

        /* ===== Mobile — barra horizontal (decisión de esta fase, ver
           comentario de la clase) ===== */
        @media (max-width: 768px) {
          .sidebar {
            width: 100%;
            flex-direction: row;
            align-items: center;
            flex-wrap: wrap;
          }
          .links {
            flex: 1;
            flex-direction: row;
            flex-wrap: wrap;
          }
          :host([collapsed]) .sidebar {
            width: 100%;
          }
        }
      </style>
      <nav class="sidebar" part="sidebar" aria-label="Navegación principal">
        <div class="head" part="head">
          <span class="brand" part="brand"></span>
          <button type="button" class="icon-button collapse" part="collapse-button" aria-expanded="true" aria-label="Colapsar menú">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 6l-6 6 6 6"/></svg>
          </button>
          <button type="button" class="icon-button close" part="close-button" aria-label="Cerrar menú">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>
          </button>
        </div>
        <div class="links" part="links">
          <slot></slot>
        </div>
      </nav>
      <button type="button" class="icon-button reopen" part="reopen-button" aria-label="Mostrar menú de navegación" hidden>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/></svg>
      </button>
    `;
    this._nav = shadow.querySelector('.sidebar');
    this._brandEl = shadow.querySelector('.brand');
    this._collapseBtn = shadow.querySelector('.collapse');
    this._closeBtn = shadow.querySelector('.close');
    this._reopenBtn = shadow.querySelector('.reopen');

    this._collapseBtn.addEventListener('click', () => {
      this.toggleAttribute('collapsed', !this.hasAttribute('collapsed'));
    });
    this._closeBtn.addEventListener('click', () => {
      this._nav.hidden = true;
      this._reopenBtn.hidden = false;
      this._reopenBtn.focus();
    });
    this._reopenBtn.addEventListener('click', () => {
      this._nav.hidden = false;
      this._reopenBtn.hidden = true;
    });
  }

  _syncBrand() {
    if (this._brandEl) this._brandEl.textContent = this.getAttribute('brand') || '';
  }

  _syncCollapsed() {
    if (!this._collapseBtn) return;
    const collapsed = this.hasAttribute('collapsed');
    this._collapseBtn.setAttribute('aria-expanded', String(!collapsed));
    this._collapseBtn.setAttribute('aria-label', collapsed ? 'Expandir menú' : 'Colapsar menú');
  }
}

customElements.define('ds-sidebar', DsSidebar);
