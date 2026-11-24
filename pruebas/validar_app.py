"""Validación de la app con Playwright + Edge del sistema (escritorio y celular emulado).

Sirve la carpeta del proyecto por HTTP y recorre los criterios de la fase indicada en
06_IMPLEMENTATION.md. Los conteos se leen de data/seed.json, no se fijan en la prueba.
Uso:  python pruebas/validar_app.py [fase]      (por defecto, todas las fases construidas)
"""
import http.server
import json
import re
import socketserver
import unicodedata
from datetime import date
import sys
import threading
from functools import partial
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SHOTS = Path(__file__).resolve().parent / "capturas"
SEED = json.loads((ROOT / "data" / "seed.json").read_text(encoding="utf-8"))
STYLE = "minimalista-corporativo.css"
results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"[{'OK' if ok else 'FALLA'}] {name}{' — ' + detail if detail else ''}")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class TestServer(http.server.ThreadingHTTPServer):
    # Atiende en paralelo y con cola amplia: el navegador pide muchos CSS/JS a la vez y el
    # TCPServer de un hilo (cola de 5) rechazaba conexiones de vez en cuando (ERR_CONNECTION_REFUSED)
    request_queue_size = 64
    daemon_threads = True


def serve():
    handler = partial(QuietHandler, directory=str(ROOT))
    httpd = TestServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def general_progress():
    """Avance general esperado, calculado desde la semilla."""
    n = len(SEED["pasos"])
    values = []
    for c in SEED["contratos"]:
        rows = [a for a in SEED["avances"] if a["contrato"] == c["id"] and a["tipo"] == "paso"]
        if rows:
            values.append(sum(r["hecho"] for r in rows) / n)
    return sum(values) / len(values)


def goto_route(page, route):
    page.evaluate(f"location.hash = '#/{route}'")
    page.wait_for_function(f"document.querySelector('ds-sidebar a[data-route=\"{route.split('/')[0]}\"]')"
                           ".getAttribute('aria-current') === 'page'", timeout=5000)


def navbar_checks(page, label):
    """Celular: navbar inferior fija (video navbar.mp4); solo la pestaña activa muestra su texto en una píldora."""
    sr = "document.querySelector('ds-sidebar').shadowRoot"
    bar = page.evaluate(f"""(() => {{ const r = {sr}.querySelector('.sidebar').getBoundingClientRect();
        const s = getComputedStyle({sr}.querySelector('.sidebar'));
        return {{ top: r.top, bottom: r.bottom, left: r.left, right: r.right, pos: s.position,
                 head: {sr}.querySelector('.head').getBoundingClientRect().height }}; }})()""")
    vw, vh = page.evaluate("[innerWidth, innerHeight]")
    check(f"{label}: navbar fija abajo, dentro de la pantalla y sin encabezado", bar["pos"] == "fixed"
          and 0 < vh - bar["bottom"] <= 24 and bar["left"] >= 8 and vw - bar["right"] >= 8 and bar["head"] == 0, str(bar))
    tops = page.eval_on_selector_all("ds-sidebar > a", "els => els.map(e => Math.round(e.getBoundingClientRect().top))")
    check(f"{label}: 4 pestañas en una sola fila", len(tops) == 4 and len(set(tops)) == 1, str(tops))
    for route in ("tablero", "consulta", "ficha", "respaldo"):
        page.locator(f"ds-sidebar a[data-route='{route}']").tap()
        page.wait_for_selector(f"ds-sidebar a[data-route='{route}'][aria-current='page']", timeout=5000)
        try:  # la píldora se expande con transición: esperar al estado final (tope 2 s), no un tiempo fijo
            page.wait_for_function("""route => [...document.querySelectorAll('ds-sidebar > a')].every(a => {
                const l = a.querySelector('.nav-label'), on = a.dataset.route === route;
                return on ? getComputedStyle(l).opacity === '1' && l.getBoundingClientRect().width > 20
                          : l.getBoundingClientRect().width === 0; })""", arg=route, timeout=2000)
        except Exception:
            pass  # el check de abajo reporta la falla
        st = page.eval_on_selector_all("ds-sidebar > a", """els => els.map(e => { const l = e.querySelector('.nav-label');
            return [e.dataset.route, Math.round(l.getBoundingClientRect().width), getComputedStyle(l).opacity,
                    getComputedStyle(e).backgroundColor, getComputedStyle(e).color, e.scrollWidth <= e.clientWidth + 1]; })""")
        active = next(s for s in st if s[0] == route)
        others = [s for s in st if s[0] != route]
        ok = (active[1] > 20 and active[2] == "1" and active[3] == HOVER_BG and contrast(active[4], active[3]) >= 7
              and all(o[1] == 0 for o in others) and all(s[5] for s in st))
        check(f"{label}: navbar con '{route}' activa en píldora azul y texto ≥ 7:1", ok,
              f"activa {active[1:5]}; contraste {contrast(active[4], active[3]):.2f}")
    # El final de la página queda por encima de la barra al bajar del todo
    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    page.wait_for_function("Math.ceil(scrollY + innerHeight) >= document.documentElement.scrollHeight - 1", timeout=2000)
    gap = page.evaluate(f"""(() => {{ const bar = {sr}.querySelector('.sidebar').getBoundingClientRect();
        const last = document.querySelector('#view').getBoundingClientRect(); return bar.top - last.bottom; }})()""")
    check(f"{label}: la navbar no tapa el final del contenido", gap >= 0, f"{gap:.0f}px")
    page.evaluate("window.scrollTo(0, 0)")
    # Accesibilidad: los textos ocultos siguen en el árbol (nombre accesible de cada pestaña)
    names = page.eval_on_selector_all("ds-sidebar > a", "els => els.map(e => e.textContent.trim())")
    check(f"{label}: cada pestaña conserva su nombre accesible", names == ["Tablero", "Consulta", "Ficha", "Respaldo"], str(names))


def phase2(page, label):
    # Estilo activo
    href = page.eval_on_selector("#style-link", "el => el.getAttribute('href')")
    check(f"{label}: estilo activo minimalista", href.endswith(STYLE), href)
    bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
    check(f"{label}: fondo de página gris claro (Cotizaciones_simple)", bg == "rgb(245, 247, 250)", bg)

    # Sidebar: íconos al tamaño del token, botón de reapertura oculto, cerrar/reabrir funciona
    icon = page.evaluate("""(() => {
        const s = getComputedStyle(document.querySelector('ds-sidebar > a > svg'));
        const t = getComputedStyle(document.documentElement).getPropertyValue('--sidebar-link-icon-size').trim();
        return [s.width, t];
    })()""")
    check(f"{label}: íconos de la Sidebar al tamaño del token", icon[0] == icon[1], str(icon))
    reopen = "document.querySelector('ds-sidebar').shadowRoot.querySelector('.reopen')"
    nav = "document.querySelector('ds-sidebar').shadowRoot.querySelector('.sidebar')"
    visible = lambda sel: page.evaluate(f"{sel}.getBoundingClientRect().width > 0")
    check(f"{label}: botón de reapertura oculto con el menú abierto", not visible(reopen))
    if label == "escritorio":
        # Encabezado del menú: contraer a la izquierda, marca centrada entre los botones, cerrar a la derecha
        head = page.evaluate("""(() => { const sr = document.querySelector('ds-sidebar').shadowRoot;
            const box = s => sr.querySelector(s).getBoundingClientRect();
            const c = box('.collapse'), x = box('.close'), b = box('.brand');
            const r = document.createRange(); r.selectNodeContents(sr.querySelector('.brand'));
            const t = r.getBoundingClientRect();
            return { order: c.right <= b.left && b.right <= x.left,
                     centerDiff: Math.abs((t.left + t.right) / 2 - (c.right + x.left) / 2) }; })()""")
        check(f"{label}: encabezado del menú ‹ Liquidaciones ×", head["order"] and head["centerDiff"] < 2,
              f"desfase del centro {head['centerDiff']:.1f}px")
        page.evaluate("document.querySelector('ds-sidebar').shadowRoot.querySelector('.close').click()")
        check(f"{label}: cerrar oculta el menú", not visible(nav) and visible(reopen))
        page.evaluate(f"{reopen}.click()")
        check(f"{label}: reabrir muestra el menú", visible(nav) and not visible(reopen))
    else:
        navbar_checks(page, label)

    # Símbolo ESAP a la izquierda del título: cargado, ≥ 32 px, sin deformar, con área de protección
    sym = page.eval_on_selector(".brand-symbol", """e => { const r = e.getBoundingClientRect();
        const t = document.querySelector('.page-head h1').getBoundingClientRect();  // bloque antetítulo + título
        return { loaded: e.complete && e.naturalWidth > 0, w: r.width, h: r.height, right: r.right, titleLeft: t.left,
                 midDiff: Math.abs((r.top + r.height / 2) - (t.top + t.height / 2)), alt: e.alt }; }""")
    ratio_ok = abs(sym["w"] / sym["h"] - 512 / 467) < 0.03   # proporción del viewBox del símbolo
    clearance = sym["h"] * 75.86 / 467                       # área de protección = diámetro de un círculo
    # El símbolo mide lo mismo que el bloque antetítulo + título (±3 px) y queda centrado con él
    block_h = page.eval_on_selector(".page-head h1", "e => e.getBoundingClientRect().height")
    check(f"{label}: símbolo a la altura del antetítulo y el título", abs(sym["h"] - block_h) <= 3,
          f"símbolo {sym['h']:.0f}px, bloque {block_h:.0f}px")
    check(f"{label}: símbolo ESAP junto al título", sym["loaded"] and sym["h"] >= 32 and ratio_ok
          and sym["right"] <= sym["titleLeft"] - clearance and sym["midDiff"] < 4 and sym["alt"] == "ESAP",
          f"{sym['w']:.0f}x{sym['h']:.0f}, separación {sym['titleLeft'] - sym['right']:.1f} ≥ {clearance:.1f}")

    # Antetítulo con el tema de la app sobre el título, visible en escritorio y celular, contraste ≥ 7:1
    eb = page.eval_on_selector(".page-head h1 .eyebrow", """e => { const r = e.getBoundingClientRect();
        const t = document.getElementById('page-title').getBoundingClientRect(); const s = getComputedStyle(e);
        return { text: e.textContent.trim(), visible: r.width > 0 && r.height > 0, above: r.bottom <= t.top + 1,
                 color: s.color, bg: getComputedStyle(document.body).backgroundColor,
                 h1: document.querySelector('.page-head h1').textContent.replace(/\\s+/g, ' ').trim() }; }""")
    check(f"{label}: antetítulo «Liquidación de contratos» sobre el título", eb["text"] == "Liquidación de contratos"
          and eb["visible"] and eb["above"] and contrast(eb["color"], eb["bg"]) >= 7 and eb["h1"].startswith("Liquidación de contratos"),
          f"{eb['text']}; contraste {contrast(eb['color'], eb['bg']):.2f}; h1 «{eb['h1']}»")

    # Favicon ESAP: declarado y servido (SVG + PNG de respaldo)
    icons = page.eval_on_selector_all("link[rel='icon']", "els => els.map(e => e.href)")
    served = [page.request.get(h).status for h in icons]
    check(f"{label}: favicon ESAP", len(icons) == 2 and all(s == 200 for s in served)
          and any(h.endswith("favicon.svg") for h in icons), f"{[h.rsplit('/', 1)[-1] for h in icons]} {served}")

    # Las 3 rutas desde la Sidebar
    for route in ("tablero", "consulta", "ficha"):
        page.click(f"ds-sidebar a[data-route='{route}']")
        page.wait_for_function(f"location.hash === '#/{route}'", timeout=5000)
        # hashchange llega después del cambio de URL: esperar a que la app marque el enlace
        try:
            page.wait_for_selector(f"ds-sidebar a[data-route='{route}'][aria-current='page']", timeout=5000)
        except Exception:
            pass  # el check de abajo reporta la falla
        current = page.eval_on_selector_all("ds-sidebar a[aria-current='page']", "els => els.map(e => e.dataset.route)")
        check(f"{label}: ruta {route} desde la Sidebar", current == [route], str(current))

    # Datos leídos de la semilla
    goto_route(page, "tablero")
    total = page.text_content("[data-kpi='contratos'] .kpi-value").strip()
    check(f"{label}: tablero muestra los contratos de la semilla",
          total == str(len(SEED["contratos"])), f"{total} vs {len(SEED['contratos'])}")
    avance = page.text_content("[data-kpi='avance'] .kpi-value").strip()
    esperado = page.evaluate(f"new Intl.NumberFormat('es-CO', {{style:'percent', maximumFractionDigits:1}}).format({general_progress()})")
    check(f"{label}: avance general calculado de la semilla", avance == esperado, f"{avance} vs {esperado}")
    source = page.get_attribute("#data-source", "data-source")
    check(f"{label}: origen de datos = semilla", source == "semilla", source)

    goto_route(page, "consulta")
    items = page.locator("[data-list='contratos'] li").count()
    check(f"{label}: consulta lista todos los contratos", items == len(SEED["contratos"]), str(items))

    # Ficha de un contrato por enlace y por URL directa
    first = SEED["contratos"][0]
    page.click("[data-list='contratos'] li >> nth=0 >> a")
    page.wait_for_selector(f"[data-contrato='{first['id']}']", timeout=5000)
    check(f"{label}: ficha abre desde la consulta", True, first["id"])
    last = SEED["contratos"][-1]
    goto_route(page, f"ficha/{last['id']}")
    page.wait_for_selector(f"[data-contrato='{last['id']}']", timeout=5000)
    check(f"{label}: ficha por URL directa", True, last["id"])
    page.screenshot(path=str(SHOTS / f"fase2_{label}_ficha.png"), full_page=True)

    # Ruta desconocida → tablero
    page.evaluate("location.hash = '#/no-existe'")
    page.wait_for_selector("[data-kpi='contratos']", timeout=5000)
    check(f"{label}: ruta desconocida cae en el tablero", True)
    page.screenshot(path=str(SHOTS / f"fase2_{label}_tablero.png"), full_page=True)


# --- Fase 3: réplica en Python de la lógica de consulta, para calcular lo esperado ---

def norm(text):
    text = unicodedata.normalize("NFD", str(text or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text.lower()).strip()


def responsibles(c):
    return [n.strip() for n in re.split(r"\s*,\s*|\s+y\s+|\s+-\s+", c["responsable"] or "") if n.strip()]


def status(c):
    rows = [a for a in SEED["avances"] if a["contrato"] == c["id"]]
    steps = [a for a in rows if a["tipo"] == "paso"]
    if not steps:
        return "sin-seguimiento"
    if all(a["hecho"] for a in steps):
        return "cerrado"
    paralyzed = any(a["tipo"] == "alerta" and a["item"] == 1 and a["hecho"] for a in rows)
    return "paralizado" if paralyzed else "en-tramite"


def expected(q="", resp="", est=""):
    out = []
    for c in SEED["contratos"]:
        if resp and resp not in responsibles(c):
            continue
        if est and status(c) != est:
            continue
        if q:
            hay = norm(" ".join([c["numero"], c["contratista"], c["responsable"]]))
            compact = norm(q).replace(" ", "").replace("-", "")
            if norm(q) not in hay and compact not in c["id"].lower().replace("-", ""):
                continue
        out.append(c["id"])
    return out


def listed(page):
    return page.eval_on_selector_all("[data-list='contratos'] a[data-id]", "els => els.map(e => e.dataset.id)")


def pick(page, name, value):
    dd = page.locator(f"ds-dropdown[data-filter='{name}']")
    # El panel se cierra al hacer scroll: centrar el campo antes de abrirlo
    dd.evaluate("e => e.scrollIntoView({block: 'center'})")
    dd.locator(".trigger").click()
    dd.locator(f".option[data-value='{value}']").click()


def contrast(fg, bg):
    def lum(rgb):
        vals = [int(v) / 255 for v in re.findall(r"\d+", rgb)[:3]]
        lin = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in vals]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    a, b = sorted([lum(fg), lum(bg)], reverse=True)
    return (a + 0.05) / (b + 0.05)


def phase3(page, label):
    goto_route(page, "consulta")
    page.wait_for_selector("[data-list='contratos'] a[data-id]")
    total = len(SEED["contratos"])
    check(f"{label}: consulta inicia con todos", len(listed(page)) == total, f"{len(listed(page))}/{total}")

    # Opciones del filtro de responsable = responsables individuales + "Todos"
    names = sorted({n for c in SEED["contratos"] for n in responsibles(c)}, key=norm)
    opts = page.locator("ds-dropdown[data-filter='responsable'] .option").count()
    check(f"{label}: responsables separados en el filtro", opts == len(names) + 1, f"{opts} vs {len(names) + 1}")

    search = page.locator("input[data-filter='q']")
    # Búsqueda por número (con el número escrito con espacios en el Excel) y sin tildes
    spaced = next((c for c in SEED["contratos"] if " " in c["numero"]), SEED["contratos"][0])
    num = re.findall(r"\d{3,}", spaced["numero"])[0]
    accented = next(c for c in SEED["contratos"] if norm(c["contratista"]) != c["contratista"].lower())
    word = next(w for w in accented["contratista"].split() if norm(w) != w.lower())
    for q in (num, spaced["id"], norm(word), "zzzz-sin-resultado"):
        search.fill(q)
        got, exp = listed(page), expected(q=q)
        check(f"{label}: búsqueda '{q}'", got == exp, f"{len(got)} vs {len(exp)}")
    empty_ok = page.is_visible("[data-empty]") and not page.is_visible("[data-list='contratos']")
    check(f"{label}: estado vacío sin coincidencias", empty_ok)
    page.locator("[data-clear]").click()
    check(f"{label}: limpiar filtros restaura todo", len(listed(page)) == total and search.input_value() == "")

    # Responsable que aparece dentro de una celda combinada
    combined = next(c for c in SEED["contratos"] if len(responsibles(c)) > 1)
    resp = responsibles(combined)[-1]
    pick(page, "responsable", resp)
    got, exp = listed(page), expected(resp=resp)
    check(f"{label}: filtro responsable '{resp}'", got == exp and combined["id"] in got, f"{len(got)} vs {len(exp)}")

    # Cada estado, combinado con el responsable y solo
    for est in ("en-tramite", "paralizado", "cerrado", "sin-seguimiento"):
        pick(page, "estado", est)
        got, exp = listed(page), expected(resp=resp, est=est)
        check(f"{label}: responsable + estado {est}", got == exp, f"{len(got)} vs {len(exp)}")
    pick(page, "responsable", "")
    for est in ("en-tramite", "paralizado", "cerrado", "sin-seguimiento"):
        pick(page, "estado", est)
        got, exp = listed(page), expected(est=est)
        check(f"{label}: estado {est}", got == exp, f"{len(got)} vs {len(exp)}")
    count = page.text_content("[data-count]")
    check(f"{label}: conteo visible = filas", count == str(len(listed(page))), count)

    # Contraste de los chips de estado
    pick(page, "estado", "")
    # Excepción del proyecto: píldoras de estado con tonos vivos y contraste AA (>= 4,5:1), no 7:1
    for est in ("en-tramite", "cerrado", "paralizado", "sin-seguimiento"):
        if not page.locator(f".chip[data-status='{est}']").count():
            continue
        fg, bg = page.eval_on_selector(f".chip[data-status='{est}']",
                                       "e => [getComputedStyle(e).color, getComputedStyle(e).backgroundColor]")
        ratio = contrast(fg, bg)
        check(f"{label}: contraste chip {est} >= 4,5:1 (AA)", ratio >= 4.5 and bg != "rgba(0, 0, 0, 0)", f"{ratio:.2f}")

    # Píldoras de estado: todas del mismo ancho, texto centrado y sin desbordar (con los 4 estados en pantalla)
    chips = page.eval_on_selector_all("[data-list='contratos'] .chip[data-status]", """els => els.map(e => {
        const r = e.getBoundingClientRect(), s = getComputedStyle(e);
        return [e.dataset.status, Math.round(r.width * 10) / 10, s.textAlign, e.scrollWidth <= e.clientWidth]; })""")
    kinds = {c[0] for c in chips}
    widths = {c[1] for c in chips}
    check(f"{label}: píldoras de estado del mismo ancho", len(kinds) == 4 and len(widths) == 1
          and all(c[2] == "center" and c[3] for c in chips), f"{sorted(kinds)}; anchos {sorted(widths)}")

    # Paneles cerrados no ocupan pantalla (no tapan clics de la lista)
    pick(page, "estado", "cerrado")
    hidden_panels = page.evaluate("""[...document.querySelectorAll('ds-dropdown')]
        .every(d => d.shadowRoot.querySelector('.panel').getBoundingClientRect().height === 0)""")
    check(f"{label}: paneles cerrados del Dropdown ocultos", hidden_panels)

    # Los filtros se conservan al abrir una ficha y volver
    before = listed(page)
    page.locator("[data-list='contratos'] a[data-id] >> nth=0").click()
    page.wait_for_selector("[data-contrato]")
    page.click("ds-sidebar a[data-route='consulta']")
    page.wait_for_selector("[data-list='contratos'] a[data-id]")
    shown = page.locator("ds-dropdown[data-filter='estado']").evaluate("e => e.value")
    check(f"{label}: filtros se conservan al volver de la ficha", listed(page) == before and shown == "cerrado")
    page.screenshot(path=str(SHOTS / f"fase3_{label}_consulta.png"), full_page=True)
    page.locator("[data-clear]").click()


# --- Fase 4: ficha editable ---

def fmt_pct(page, value):
    return page.evaluate(f"new Intl.NumberFormat('es-CO', {{style:'percent', maximumFractionDigits:1}}).format({value})")


def seed_steps(cid):
    return [a for a in SEED["avances"] if a["contrato"] == cid and a["tipo"] == "paso"]


def open_ficha(page, cid):
    goto_route(page, f"ficha/{cid}")
    page.wait_for_selector(f"[data-contrato='{cid}'] ds-step, [data-contrato='{cid}'] [data-start]", timeout=5000)


def avance(page):
    return page.text_content("[data-avance]").strip()


def step_states(page):
    return page.eval_on_selector_all("[data-steps] ds-step", "els => els.map(e => e.getAttribute('state'))")


def last_toast(page):
    page.wait_for_selector("#toast-stack ds-toast", timeout=5000)
    return page.locator("#toast-stack ds-toast").last


def phase4(page, label):
    n = len(SEED["pasos"])
    # Contrato en trámite con pasos marcados y pendientes
    c = next(c for c in SEED["contratos"] if status(c) == "en-tramite")
    steps = seed_steps(c["id"])
    done = sum(s["hecho"] for s in steps)
    first_pending = min(s["item"] for s in steps if not s["hecho"])
    open_ficha(page, c["id"])

    states = step_states(page)
    exp_states = ["completed" if s["hecho"] else ("current" if s["item"] == first_pending else "pending")
                  for s in sorted(steps, key=lambda s: s["item"])]
    check(f"{label}: {n} pasos con el estado de la semilla", states == exp_states, f"{states.count('completed')} hechos")
    # Círculo relleno con el cian claro de Cotizaciones_simple (#DDFCFF) solo en los completados
    fills = page.eval_on_selector_all("ds-step", """els => els.map(e => [e.getAttribute('state'),
        getComputedStyle(e.shadowRoot.querySelector('[part~=circle]')).backgroundColor])""")
    check(f"{label}: pasos completados con círculo cian claro",
          all((bg == "rgb(221, 252, 255)") == (st == "completed") for st, bg in fills), str(sorted(set(map(tuple, fills)))))
    check(f"{label}: avance de la ficha", avance(page) == fmt_pct(page, done / n), avance(page))

    # Marcar la etapa actual con el botón, luego deshacer desde el aviso
    page.click(f"[data-done='{first_pending}']")
    check(f"{label}: marcar paso sube el avance", avance(page) == fmt_pct(page, (done + 1) / n), avance(page))
    check(f"{label}: guardar muestra aviso y origen local",
          last_toast(page).is_visible() and page.get_attribute("#data-source", "data-source") == "local")
    last_toast(page).locator("ds-button").click()
    check(f"{label}: deshacer revierte el paso", avance(page) == fmt_pct(page, done / n)
          and step_states(page) == exp_states, avance(page))

    # Desmarcar un paso hecho haciendo clic en su encabezado
    done_item = next(s["item"] for s in steps if s["hecho"])
    page.locator(f"ds-step[data-step='{done_item}']").locator(".header").click()
    check(f"{label}: clic en paso hecho lo desmarca", avance(page) == fmt_pct(page, (done - 1) / n), avance(page))

    # Alerta 2
    alert = page.locator("[data-alert='2']")
    was = alert.is_checked()
    alert.click()
    check(f"{label}: alerta cambia", alert.is_checked() != was)

    # Fecha de pérdida de competencia: elegir el día 15 del mes mostrado
    dp = page.locator("ds-datepicker[data-date='perdida_competencia']")
    # El panel se cierra al hacer scroll (comportamiento del componente): se centra
    # el campo antes de abrirlo para que el calendario quepa sin desplazar la página
    dp.evaluate("e => e.scrollIntoView({block: 'center'})")
    dp.locator(".trigger").click()
    dp.locator(".day:not(.day--vacio)", has_text=re.compile(r"^15$")).click()
    new_date = dp.evaluate("e => e.value")
    check(f"{label}: fecha elegida en el calendario", new_date.endswith("-15"), new_date)

    # Bitácora: vacío no agrega; texto sí, y queda primero
    count0 = int(page.text_content("[data-log-count]"))
    page.click("[data-log-add]")
    check(f"{label}: observación vacía no se agrega", int(page.text_content("[data-log-count]")) == count0)
    note = f"Prueba automática {label}"
    page.fill("[data-log-text]", note)
    page.click("[data-log-add]")
    first = page.text_content("[data-log] li .log-text")
    check(f"{label}: observación agregada primero", int(page.text_content("[data-log-count]")) == count0 + 1
          and first == note, first)

    # Persistencia al recargar
    page.reload(wait_until="networkidle")
    open_ficha(page, c["id"])
    persisted = (avance(page) == fmt_pct(page, (done - 1) / n)
                 and page.locator("[data-alert='2']").is_checked() != was
                 and page.locator("ds-datepicker[data-date='perdida_competencia']").evaluate("e => e.value") == new_date
                 and page.text_content("[data-log] li .log-text") == note
                 and page.get_attribute("#data-source", "data-source") == "local")
    check(f"{label}: cambios persisten al recargar", persisted)
    page.screenshot(path=str(SHOTS / f"fase4_{label}_ficha.png"), full_page=True)

    # La consulta refleja el cambio
    goto_route(page, "consulta")
    page.wait_for_selector(f"a[data-id='{c['id']}']")
    pct = page.text_content(f"a[data-id='{c['id']}'] .list-pct").strip()
    check(f"{label}: consulta refleja el avance editado", pct == fmt_pct(page, (done - 1) / n), pct)

    # Bitácora: últimos 5 eventos + "Ver más (N)" / "Ver menos"
    preview = 5
    log_n = {}
    for b in SEED["bitacora"]:
        log_n[b["contrato"]] = log_n.get(b["contrato"], 0) + 1
    many = max(log_n, key=log_n.get)
    open_ficha(page, many)
    log_total = int(page.text_content("[data-log-count]"))
    more = page.locator("[data-log-more]")
    items = lambda: page.locator("[data-log] li").count()
    check(f"{label}: bitácora muestra los últimos {preview}", items() == preview and more.is_visible()
          and more.text_content().strip() == f"Ver más ({log_total - preview})",
          f"{items()} de {log_total}; botón '{more.text_content().strip()}'")
    more.click()
    check(f"{label}: 'Ver más' despliega toda la bitácora", items() == log_total and more.text_content().strip() == "Ver menos"
          and more.get_attribute("aria-expanded") == "true", f"{items()} de {log_total}")
    more.click()
    check(f"{label}: 'Ver menos' vuelve a {preview}", items() == preview)
    few = next((c["id"] for c in SEED["contratos"] if log_n.get(c["id"], 0) <= preview), None)
    if few:
        open_ficha(page, few)
        check(f"{label}: sin botón con {preview} eventos o menos", not page.locator("[data-log-more]").is_visible())

    # Fecha ilegible del Excel: se muestra el texto original
    bad = next((c for c in SEED["contratos"] if c["plazo_cierre_texto"] and not c["plazo_cierre"]), None)
    if bad:
        open_ficha(page, bad["id"])
        hint = page.locator(".date-grid small").text_content() or ""
        check(f"{label}: texto original del plazo ilegible", bad["plazo_cierre_texto"] in hint, hint)

    # Contrato sin tarjeta: iniciar seguimiento
    nocard = next((c for c in SEED["contratos"] if not c["tiene_tarjeta"]), None)
    if nocard:
        open_ficha(page, nocard["id"])
        page.click("[data-start]")
        page.wait_for_selector("[data-steps] ds-step")
        states = step_states(page)
        check(f"{label}: iniciar seguimiento crea {n} pasos sin marcar",
              len(states) == n and states.count("completed") == 0 and states[0] == "current", str(states[:2]))
        chip = page.get_attribute("[data-summary] .chip", "data-status")
        check(f"{label}: el contrato pasa a en trámite", chip == "en-tramite", chip)


# --- Fase 5: tablero ---

WARN_DAYS = 90  # mismo umbral que store.DEADLINE_WARN_DAYS


def progress(c):
    steps = seed_steps(c["id"])
    return sum(s["hecho"] for s in steps) / len(SEED["pasos"]) if steps else None


def by_responsible():
    groups = {}
    for c in SEED["contratos"]:
        p = progress(c)
        if p is None:
            continue
        for name in responsibles(c):
            groups.setdefault(name, []).append(p)
    rows = [(n, sum(v) / len(v), len(v)) for n, v in groups.items()]
    # Mismo orden que la app: avance desc, contratos desc, nombre
    rows.sort(key=lambda r: (-r[1], -r[2], norm(r[0])))
    return rows


def deadlines(today):
    out = []
    for c in SEED["contratos"]:
        if status(c) == "cerrado":
            continue
        if not c["perdida_competencia"]:
            out.append((c["id"], None, "sin-fecha"))
            continue
        days = (date.fromisoformat(c["perdida_competencia"]) - today).days
        level = "vencido" if days < 0 else "proximo" if days <= WARN_DAYS else "en-plazo"
        out.append((c["id"], days, level))
    return sorted(out, key=lambda r: float("inf") if r[1] is None else r[1])


def phase5(page, label):
    # Datos limpios (la fase 4 los modifica)
    page.evaluate("localStorage.clear()")
    page.goto(page.url.split("#")[0] + "#/tablero", wait_until="networkidle")
    page.reload(wait_until="networkidle")
    page.wait_for_selector("[data-bars] .bar")
    today = date.fromisoformat(page.evaluate(
        "(() => { const d = new Date(); return [d.getFullYear(), String(d.getMonth()+1).padStart(2,'0'), String(d.getDate()).padStart(2,'0')].join('-'); })()"))

    # Tarjeta Avance general: anillo con el valor al centro; la descripción solo al pasar el cursor / tocar
    gp = general_progress()
    page.wait_for_function("""(() => { const c = document.querySelector('.ring-value'); const C = 2 * Math.PI * 40;
        return Math.abs(parseFloat(getComputedStyle(c).strokeDashoffset) - C * (1 - Number(c.dataset.value))) < 0.5; })()""",
                           timeout=5000)
    arc = page.eval_on_selector(".ring-value", "c => 1 - parseFloat(getComputedStyle(c).strokeDashoffset) / (2 * Math.PI * 40)")
    check(f"{label}: anillo de avance general proporcional", abs(arc - gp) < 0.005, f"{arc:.3f} vs {gp:.3f}")
    ring_box = page.eval_on_selector(".ring", "e => e.getBoundingClientRect().toJSON()")
    lbl_box = page.eval_on_selector(".ring-label", "e => { const r = document.createRange(); r.selectNodeContents(e); return r.getBoundingClientRect().toJSON(); }")
    centered = (abs((lbl_box["x"] + lbl_box["width"] / 2) - (ring_box["x"] + ring_box["width"] / 2)) < 2
                and abs((lbl_box["y"] + lbl_box["height"] / 2) - (ring_box["y"] + ring_box["height"] / 2)) < 3)
    check(f"{label}: porcentaje en el centro del anillo", centered)
    tip_op = lambda: page.eval_on_selector("#tip-avance", "e => getComputedStyle(e).opacity")
    check(f"{label}: descripción oculta sin cursor", tip_op() == "0")
    card = page.locator("[data-kpi='avance']")
    if label == "escritorio":
        card.hover()
    else:
        card.tap()
    page.wait_for_function("getComputedStyle(document.getElementById('tip-avance')).opacity === '1'", timeout=3000)
    tip_text = page.text_content("#tip-avance").strip()
    with_card = sum(c["tiene_tarjeta"] for c in SEED["contratos"])
    check(f"{label}: descripción al {'pasar el cursor' if label == 'escritorio' else 'tocar'}",
          tip_text == f"Promedio de los {with_card} contratos con seguimiento", tip_text)
    page.mouse.move(0, 0)
    page.evaluate("document.activeElement.blur()")

    # Tarjeta Estados: tres cifras en fila, al mismo nivel que las cifras de las otras tarjetas
    for est in ("cerrado", "paralizado", "en-tramite"):
        n = sum(status(c) == est for c in SEED["contratos"])
        got = page.text_content(f"[data-status-link='{est}'] .kpi-value").strip()
        check(f"{label}: KPI {est}", got == str(n), f"{got} vs {n}")
    tops = page.eval_on_selector_all("[data-kpi='estados'] .kpi-value", "els => els.map(e => Math.round(e.getBoundingClientRect().top))")
    check(f"{label}: cifras de Estados en una misma fila", len(set(tops)) == 1, str(tops))
    if label == "escritorio":
        # Títulos a la misma altura; el contenido de cada tarjeta centrado a la altura del centro del anillo
        heights = page.eval_on_selector_all(".kpi-row > .kpi", "els => els.map(e => Math.round(e.getBoundingClientRect().height))")
        title_tops = page.eval_on_selector_all(".kpi-row > .kpi > .kpi-label", "els => els.map(e => Math.round(e.getBoundingClientRect().top))")
        check(f"{label}: tarjetas de igual alto y títulos en su posición", len(set(heights)) == 1 and len(set(title_tops)) == 1,
              f"alturas {heights}; títulos {title_tops}")
        centers = page.eval_on_selector_all(".kpi-row > .kpi", """els => els.map(card => {
            const body = card.querySelector('.kpi-body');
            const kids = [...body.children];
            const top = Math.min(...kids.map(k => k.getBoundingClientRect().top));
            const bottom = Math.max(...kids.map(k => k.getBoundingClientRect().bottom));
            return [card.dataset.kpi, Math.round((top + bottom) / 2)];
        })""")
        ring_c = page.eval_on_selector(".ring", "e => { const r = e.getBoundingClientRect(); return Math.round(r.top + r.height / 2); }")
        off = [(k, c) for k, c in centers if abs(c - ring_c) > 3]
        check(f"{label}: contenido de las tarjetas centrado con el anillo", not off, f"anillo {ring_c}; fuera {off}")

    # Íconos de los títulos: uno por tarjeta, del tamaño de la letra del título y del mismo color
    icons = page.eval_on_selector_all(".kpi-row > .kpi > .kpi-label", """els => els.map(l => {
        const i = l.querySelector('svg.kpi-icon'); if (!i) return null;
        const s = getComputedStyle(l), r = i.getBoundingClientRect();
        return [Math.round(r.width), Math.round(r.height), Math.round(parseFloat(s.fontSize)),
                getComputedStyle(i).color === s.color, i.getAttribute('aria-hidden')]; })""")
    ok = len(icons) == 4 and all(i and i[0] == i[1] == i[2] and i[3] and i[4] == "true" for i in icons)
    check(f"{label}: ícono en cada título, del tamaño del texto", ok, str(icons))

    # Títulos en una sola línea a cualquier ancho; "Vencida" solo cuando "Competencia vencida" no cabe
    if label == "escritorio":
        size = page.viewport_size
        # Mide el título visible (largo o corto) contra el espacio útil de la tarjeta
        title_js = """() => { const l = document.querySelector("[data-kpi='vencidos'] .kpi-label");
            const card = l.closest('.kpi'), s = getComputedStyle(card);
            const room = card.clientWidth - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight);
            const short = l.classList.contains('is-short');
            const shown = l.querySelector(short ? '.kpi-title-short' : '.kpi-title-long');
            const icon = l.querySelector('.kpi-icon').getBoundingClientRect();
            const txt = shown.getBoundingClientRect();
            const gap = parseFloat(getComputedStyle(l).columnGap) || 0;
            const need = txt.width + icon.width + gap;
            const needLong = l.querySelector('.kpi-title-long').scrollWidth + icon.width + gap;
            return { short, oneLine: Math.abs(txt.top - icon.top) < txt.height && txt.height < parseFloat(getComputedStyle(l).fontSize) * 1.6,
                     fits: need <= room, longFits: needLong + 4 <= room, need: Math.round(need), room: Math.round(room) }; }"""
        settle = "new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"  # deja actuar al ResizeObserver
        results_w = []
        for w in (1440, 1280, 1150, 1100, 900, 800):
            page.set_viewport_size({"width": w, "height": size["height"]})
            page.evaluate(settle)
            t = page.evaluate(title_js)
            results_w.append((w, t["short"], t["oneLine"], t["fits"], t["longFits"], t["need"], t["room"]))
        ok = all(one and fits and short == (not long_fits) for _, short, one, fits, long_fits, _, _ in results_w)
        check(f"{label}: título en una línea y dentro de la tarjeta a todo ancho ('Vencida' solo si el largo no cabe)",
              ok, str([(w, "corto" if s else "largo", n, r) for w, s, _, _, _, n, r in results_w]))
        page.set_viewport_size(size)
        page.evaluate(settle)
        # Tarjeta forzada a angosta: debe pasar a "Vencida", en una línea y dentro; al soltarla, vuelve al largo
        page.eval_on_selector("[data-kpi='vencidos']", "e => e.style.maxWidth = '170px'")
        page.evaluate(settle)
        t = page.evaluate(title_js)
        page.eval_on_selector("[data-kpi='vencidos']", "e => e.style.maxWidth = ''")
        page.evaluate(settle)
        back = page.evaluate(title_js)
        check(f"{label}: tarjeta angosta muestra 'Vencida' y luego vuelve al título completo",
              t["short"] and t["oneLine"] and t["fits"] and not back["short"], f"angosta {t}; normal {back}")

    # Competencia vencida: la descripción solo en el mensaje flotante
    vtip = lambda: page.eval_on_selector("#tip-vencidos", "e => getComputedStyle(e).opacity")
    no_note = page.locator("[data-kpi='vencidos'] .kpi-note").count() == 0
    check(f"{label}: Competencia vencida sin descripción visible", no_note and vtip() == "0")
    vcard = page.locator("[data-kpi='vencidos']")
    if label == "escritorio":
        vcard.hover()
    else:
        vcard.tap()
    page.wait_for_function("getComputedStyle(document.getElementById('tip-vencidos')).opacity === '1'", timeout=3000)
    check(f"{label}: mensaje de Competencia vencida", page.text_content("#tip-vencidos").strip()
          == "Contratos sin cerrar con la fecha ya pasada")
    page.mouse.move(0, 0)
    page.evaluate("document.activeElement.blur()")

    dl = deadlines(today)
    overdue = sum(r[2] == "vencido" for r in dl)
    check(f"{label}: KPI competencia vencida", page.text_content("[data-kpi='vencidos'] .kpi-value").strip() == str(overdue), str(overdue))

    # Barras: orden y valores
    exp = by_responsible()
    names = page.eval_on_selector_all("[data-bars] .bar-row", "els => els.map(e => e.dataset.name)")
    check(f"{label}: responsables ordenados de mayor a menor avance", names == [r[0] for r in exp], f"{len(names)} barras")
    values = page.eval_on_selector_all("[data-bars] .bar", "els => els.map(e => Number(e.dataset.value))")
    check(f"{label}: valor de cada barra", all(abs(a - b[1]) < 1e-9 for a, b in zip(values, exp)) and len(values) == len(exp))
    texts = page.eval_on_selector_all("[data-bars] .bar-value", "els => els.map(e => e.textContent.trim())")
    exp_texts = [fmt_pct(page, r[1]) for r in exp]
    check(f"{label}: etiqueta directa de cada barra", texts == exp_texts, str([(a, b) for a, b in zip(texts, exp_texts) if a != b][:3]))

    # Animación: una por una, de mayor a menor (retardo creciente por posición)
    delays = page.eval_on_selector_all("[data-bars] .bar", "els => els.map(e => parseFloat(getComputedStyle(e).transitionDelay))")
    check(f"{label}: barras entran una por una (retardo creciente)",
          all(b > a for a, b in zip(delays, delays[1:])) and delays[0] == 0, str(delays[:3]))
    # Recargar para observar el inicio de la animación
    page.reload(wait_until="domcontentloaded")
    page.wait_for_function("document.querySelector('[data-bars] .bar')?.getBoundingClientRect().width > 0", timeout=5000)
    last_w = page.evaluate("(() => { const b = document.querySelectorAll('[data-bars] .bar'); return b[b.length - 1].getBoundingClientRect().width; })()")
    check(f"{label}: la primera barra arranca antes que la última", last_w == 0, str(last_w))
    page.wait_for_function("""[...document.querySelectorAll('[data-bars] .bar')].every(b =>
        Math.abs(b.getBoundingClientRect().width - b.parentElement.getBoundingClientRect().width * Number(b.dataset.value)) < 1)""",
                           timeout=10000)
    check(f"{label}: todas las barras llegan a su valor", True)

    # Tooltip al pasar el cursor / foco
    first = page.locator("[data-bars] .bar-row").first
    if label == "escritorio":
        first.hover()
    else:
        first.locator(".bar-link").focus()
    tip = page.locator("[data-tooltip]")
    check(f"{label}: tooltip de la barra", tip.is_visible() and exp[0][0] in tip.text_content(), tip.text_content()[:60])

    # Clic en un responsable → Consulta filtrada solo por él (limpia búsqueda y estado previos)
    def consulta_state():
        page.wait_for_selector("[data-list='contratos'] a[data-id]")
        return (page.locator("ds-dropdown[data-filter='responsable']").evaluate("e => e.value"),
                page.locator("ds-dropdown[data-filter='estado']").evaluate("e => e.value"),
                page.input_value("input[data-filter='q']"), listed(page))

    combined = next(c for c in SEED["contratos"] if len(responsibles(c)) > 1)
    for resp, target in ((responsibles(combined)[-1], ".bar-link"), (exp[-1][0], ".bar-track")):
        goto_route(page, "consulta")
        page.wait_for_selector("[data-list='contratos'] a[data-id]")
        pick(page, "estado", "cerrado")  # filtro previo que debe limpiarse
        page.locator("input[data-filter='q']").fill("bog")
        goto_route(page, "tablero")
        page.locator(f"[data-bars] .bar-row[data-name='{resp}'] {target}").click()
        page.wait_for_function("location.hash === '#/consulta'", timeout=5000)
        got_resp, got_est, got_q, rows = consulta_state()
        check(f"{label}: clic en {'nombre' if target == '.bar-link' else 'barra'} de '{resp}' filtra la consulta",
              got_resp == resp and got_est == "" and got_q == "" and rows == expected(resp=resp), f"{len(rows)} contratos")
    # Clic en una cifra de la tarjeta Estados → Consulta filtrada solo por ese estado
    for est in ("cerrado", "paralizado", "en-tramite"):
        goto_route(page, "consulta")
        page.wait_for_selector("[data-list='contratos'] a[data-id]")
        page.locator("input[data-filter='q']").fill("bog")
        goto_route(page, "tablero")
        page.click(f"[data-status-link='{est}']")
        page.wait_for_function("location.hash === '#/consulta'", timeout=5000)
        got_resp, got_est, got_q, rows = consulta_state()
        check(f"{label}: cifra {est} filtra la consulta", got_est == est and got_resp == "" and got_q == ""
              and rows == expected(est=est), f"{len(rows)} contratos")
    page.locator("[data-clear]").click()
    goto_route(page, "tablero")
    page.wait_for_selector("[data-deadlines] a[data-id]")

    # Semáforo
    ids = page.eval_on_selector_all("[data-deadlines] a[data-id]", "els => els.map(e => e.dataset.id)")
    check(f"{label}: semáforo ordenado por urgencia", ids == [r[0] for r in dl], f"{len(ids)} contratos")
    levels = page.eval_on_selector_all("[data-deadlines] a[data-id]", "els => els.map(e => e.dataset.level)")
    check(f"{label}: nivel de cada contrato", levels == [r[2] for r in dl])
    for lvl in ("vencido", "proximo", "en-plazo", "sin-fecha"):
        got = page.text_content(f"[data-level-count='{lvl}']").strip()
        check(f"{label}: conteo {lvl}", got == str(sum(r[2] == lvl for r in dl)), got)
    # Etiquetas del semáforo con los mismos tonos vivos de estado: contraste AA (>= 4,5:1)
    lv = page.eval_on_selector_all("[data-deadlines] .level", """els => els.map(e => [e.closest('[data-level]')?.dataset.level,
        getComputedStyle(e).color, getComputedStyle(e).backgroundColor])""")
    low = [f"{l}: {contrast(fg, bg):.2f}" for l, fg, bg in lv if contrast(fg, bg) < 4.5 or bg == "rgba(0, 0, 0, 0)"]
    check(f"{label}: contraste de las etiquetas del semáforo >= 4,5:1 (AA)", lv and not low, "; ".join(sorted(set(low))))
    no_color_only = page.eval_on_selector_all("[data-deadlines] .level",
                                              "els => els.every(e => e.querySelector('.level-icon').textContent.trim() && e.textContent.trim().length > 2)")
    check(f"{label}: semáforo con ícono y texto (no solo color)", no_color_only)

    # Chips del semáforo como filtro: un clic filtra, otro clic quita el filtro
    for lvl in ("vencido", "proximo", "en-plazo", "sin-fecha"):
        n = sum(r[2] == lvl for r in dl)
        chip = page.locator(f"[data-level-filter='{lvl}']")
        if not n:
            check(f"{label}: chip {lvl} sin contratos deshabilitado", chip.is_disabled())
            continue
        chip.click()
        shown = page.eval_on_selector_all("[data-deadlines] a[data-id]", "els => els.map(e => e.dataset.id)")
        check(f"{label}: chip {lvl} filtra la lista", shown == [r[0] for r in dl if r[2] == lvl]
              and chip.get_attribute("aria-pressed") == "true"
              and page.text_content("[data-deadline-shown]") == str(n), f"{len(shown)} vs {n}")
    page.screenshot(path=str(SHOTS / f"fase5_{label}_tablero_filtro.png"), full_page=True)
    active = page.locator("[data-level-filter][aria-pressed='true']")
    lvl = active.get_attribute("data-level-filter")
    active.click()
    shown = page.locator("[data-deadlines] a[data-id]").count()
    check(f"{label}: segundo clic quita el filtro", shown == len(dl)
          and not page.locator("[data-level-filter][aria-pressed='true']").count(), str(shown))
    # El filtro se recuerda al volver de una ficha
    page.click("[data-level-filter='vencido']")
    page.locator("[data-deadlines] a[data-id]").first.click()
    page.wait_for_selector("[data-contrato]")
    page.click("ds-sidebar a[data-route='tablero']")
    page.wait_for_selector("[data-deadlines] a[data-id]")
    kept = page.get_attribute("[data-level-filter='vencido']", "aria-pressed") == "true"
    check(f"{label}: filtro del semáforo se conserva al volver", kept
          and page.locator("[data-deadlines] a[data-id]").count() == overdue)
    page.click("[data-level-filter='vencido']")
    # Captura con las barras ya completas (esperar a que termine la animación, con tope)
    page.wait_for_function("""[...document.querySelectorAll('[data-bars] .bar')].every(b =>
        Math.abs(b.getBoundingClientRect().width - b.parentElement.getBoundingClientRect().width * Number(b.dataset.value)) < 1)""",
                           timeout=10000)
    page.screenshot(path=str(SHOTS / f"fase5_{label}_tablero.png"), full_page=True)

    # Movimiento reducido: sin animación
    page.emulate_media(reduced_motion="reduce")
    page.reload(wait_until="networkidle")
    page.wait_for_selector("[data-bars] .bar")
    dur = page.eval_on_selector("[data-bars] .bar", "e => getComputedStyle(e).transitionDuration")
    check(f"{label}: movimiento reducido sin animación", dur == "0s", dur)
    page.emulate_media(reduced_motion="no-preference")


HOVER_BG = "rgb(221, 240, 255)"  # variante azul del cian de Cotizaciones_simple (#DDF0FF) — token --color-hover

# Aspecto de un campo: lo que debe coincidir entre caja de texto, desplegable y fecha
FIELD_LOOK_JS = """e => { const s = getComputedStyle(e); return [s.borderTopWidth, s.borderTopColor, s.backgroundColor,
    s.borderTopLeftRadius, s.paddingLeft, s.fontSize, Math.round(e.getBoundingClientRect().height)]; }"""
TRIGGER_LOOK_JS = "e => (" + FIELD_LOOK_JS + ")(e.shadowRoot.querySelector('.trigger'))"
HOST_BORDER_JS = "e => getComputedStyle(e).borderTopWidth"


def table_checks(page, label):
    """Estilo Cotizaciones_simple: tarjetas blancas, encabezado de tabla, columnas alineadas; tabla sin cebra."""
    goto_route(page, "consulta")
    page.wait_for_selector("[data-list='contratos'] a[data-id]")
    page.mouse.move(0, 0)
    cards = page.eval_on_selector_all(".card", "els => [...new Set(els.map(e => getComputedStyle(e).backgroundColor))]")
    side = page.eval_on_selector("ds-sidebar", "e => getComputedStyle(e.shadowRoot.querySelector('.sidebar')).backgroundColor")
    check(f"{label}: tarjetas y menú blancos", cards == ["rgb(255, 255, 255)"] and side == "rgb(255, 255, 255)", f"{cards} {side}")
    try:  # si el cursor estaba sobre una fila, su fondo vuelve con transición: esperar al final (tope 2 s)
        page.wait_for_function("""[...document.querySelectorAll("[data-list='contratos'] li > a")]
            .every(a => ['rgba(0, 0, 0, 0)', 'rgb(255, 255, 255)'].includes(getComputedStyle(a).backgroundColor))""", timeout=2000)
    except Exception:
        pass  # el check de abajo reporta la falla
    # Tabla de la Consulta toda en blanco: sin cebra, filas separadas por una línea de 1 px
    rows = page.eval_on_selector_all("[data-list='contratos'] li", """els => els.map((li, i) => [
        getComputedStyle(li.querySelector(':scope > a')).backgroundColor, i ? getComputedStyle(li).borderTopWidth : '1px'])""")
    bgs = {bg for bg, _ in rows}
    check(f"{label}: tabla en blanco con líneas separadoras", bgs <= {"rgba(0, 0, 0, 0)", "rgb(255, 255, 255)"}
          and all(w == "1px" for _, w in rows), f"fondos {bgs}")
    if label != "escritorio":
        hidden = not page.is_visible(".table-head")
        check(f"{label}: sin encabezado de tabla en móvil", hidden)
        return
    head = page.eval_on_selector(".table-head", """e => { const s = getComputedStyle(e);
        return [s.backgroundColor, s.borderBottomWidth, s.borderBottomColor, s.textTransform, s.color]; }""")
    accent = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--color-accent').trim()")
    ratio = contrast(head[4], head[0])
    check(f"{label}: encabezado de tabla en azul ESAP", head[0] == "rgb(4, 71, 122)" and head[1] == "2px" and head[2] == "rgb(6, 101, 174)"
          and head[3] == "uppercase" and ratio >= 7, f"{head}; contraste {ratio:.2f}; acento {accent}")
    cols = page.evaluate("""(() => {
        const h = [...document.querySelectorAll('.table-head > span')].map(s => s.getBoundingClientRect());
        const r = [...document.querySelector("[data-list='contratos'] li > a").children].map(s => s.getBoundingClientRect());
        return h.map((b, i) => Math.round(Math.abs(b.left - r[i].left) + Math.abs(b.right - r[i].right))); })()""")
    check(f"{label}: columnas alineadas con el encabezado", all(d <= 1 for d in cols), f"desfase {cols}")


def field_checks(page, label):
    goto_route(page, "consulta")
    page.wait_for_selector("input[data-filter='q']")
    ref = page.eval_on_selector("input[data-filter='q']", FIELD_LOOK_JS)
    ref_box = ref_radius(page)
    for name in ("responsable", "estado"):
        sel = f"ds-dropdown[data-filter='{name}']"
        look = page.eval_on_selector(sel, TRIGGER_LOOK_JS)
        host = page.eval_on_selector(sel, HOST_BORDER_JS)
        check(f"{label}: desplegable {name} con el mismo borde que la caja de texto", look == ref and host == "0px",
              f"{look} vs {ref}; borde extra {host}")
    cid = next(c["id"] for c in SEED["contratos"] if c["tiene_tarjeta"])
    open_ficha(page, cid)
    for sel in ("ds-datepicker[data-date='perdida_competencia']", "ds-datepicker[data-log-date]"):
        look = page.eval_on_selector(sel, TRIGGER_LOOK_JS)
        host = page.eval_on_selector(sel, HOST_BORDER_JS)
        check(f"{label}: fecha {sel.split('[')[1][:-1]} con el mismo borde que la caja de texto",
              look == ref and host == "0px", f"{look} vs {ref}; borde extra {host}")

    # Estilo de Cotizaciones_simple: esquinas de 8 px, borde 1,5 px e íconos de trazo de 16 px
    box = page.eval_on_selector("textarea", "e => { const s = getComputedStyle(e); return [s.borderTopLeftRadius, s.borderTopStyle]; }")
    check(f"{label}: campos con esquinas de 8 px y borde de 1,5 px", ref_box == ["8px", "1.5px"]
          and box == ["8px", "solid"], f"{ref_box} / textarea {box}")
    icon_js = """(e, part) => { const i = e.shadowRoot.querySelector(`[part~='${part}']`); const s = getComputedStyle(i);
        const r = i.getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height), font: s.fontSize,
        mask: (s.maskImage || s.webkitMaskImage).startsWith('url('), color: s.backgroundColor }; }"""
    accent = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--color-accent').trim()")
    for sel, part in (("ds-datepicker[data-date='perdida_competencia']", "icon"),):
        ic = page.eval_on_selector(sel, icon_js, part)
        check(f"{label}: ícono de calendario de trazo, 16 px", ic["w"] == 16 and ic["h"] == 16
              and ic["font"] == "0px" and ic["mask"], str(ic))
    goto_route(page, "consulta")
    page.wait_for_selector("ds-dropdown[data-filter='estado']")
    ic = page.eval_on_selector("ds-dropdown[data-filter='estado']", icon_js, "chevron")
    check(f"{label}: chevron de trazo en color de acento, 16 px", ic["w"] == 16 and ic["h"] == 16 and ic["font"] == "0px"
          and ic["mask"] and ic["color"] == hex_rgb(accent), f"{ic} vs {accent}")
    page.focus("input[data-filter='q']")
    page.keyboard.press("Shift+Tab"); page.keyboard.press("Tab")  # foco por teclado (:focus-visible)
    try:  # el halo entra con transición: esperar al valor final
        page.wait_for_function("getComputedStyle(document.querySelector(\"input[data-filter='q']\")).boxShadow.endsWith(' 3px')", timeout=2000)
    except Exception:
        pass  # el check de abajo reporta la falla
    focus = page.eval_on_selector("input[data-filter='q']", "e => { const s = getComputedStyle(e); return [s.borderTopColor, s.boxShadow]; }")
    check(f"{label}: foco con borde de acento y halo", focus[0] == hex_rgb(accent) and focus[1].endswith(" 3px"), str(focus))
    page.evaluate("document.activeElement.blur()")

    # Etiquetas en seminegrita gris oscuro y texto de ejemplo #6B7585 (≥ 4,5:1)
    lbl = page.eval_on_selector(".field-label", "e => { const s = getComputedStyle(e); return [s.fontWeight, s.color]; }")
    check(f"{label}: etiquetas en seminegrita gris oscuro", lbl == ["600", "rgb(54, 54, 54)"], str(lbl))
    ph = page.eval_on_selector("input[data-filter='q']", "e => getComputedStyle(e, '::placeholder').color")
    check(f"{label}: texto de ejemplo #6B7585 con contraste AA", ph == "rgb(107, 117, 133)"
          and contrast(ph, "rgb(255, 255, 255)") >= 4.5, f"{ph} {contrast(ph, 'rgb(255, 255, 255)'):.2f}")
    goto_route(page, "tablero")  # deja la Consulta para que la siguiente prueba la pinte de nuevo


def ref_radius(page):
    # El borde se lee de la variable declarada: Edge dibuja 1,5 px como 1 px de dispositivo (igual que la referencia)
    return page.eval_on_selector("input[data-filter='q']", """e => [getComputedStyle(e).borderTopLeftRadius,
        getComputedStyle(document.documentElement).getPropertyValue('--field-border').trim().split(' ')[0]]""")


def hex_rgb(h):
    h = h.lstrip("#")
    return f"rgb({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)})"


def check_hover(page, label, name, hover_loc, bg_js, text_js=None):
    """Pasa el cursor y compara el fondo; si se indica, mide el contraste del texto sobre ese fondo."""
    hover_loc.hover()
    # Varios componentes animan el fondo: esperar a que llegue al color final (tope ~1 s)
    for _ in range(20):
        bg = bg_js()
        if bg == HOVER_BG:
            break
        page.wait_for_timeout(50)
    ok = bg == HOVER_BG
    detail = bg
    if ok and text_js:
        ratio = contrast(text_js(), bg)
        ok = ratio >= 7
        detail = f"contraste {ratio:.2f}"
    check(f"{label}: hover azul claro en {name}", ok, detail)


def hover_checks(page, label):
    if label != "escritorio":
        return  # sin cursor en móvil
    css = lambda sel, prop: (lambda: page.eval_on_selector(sel, f"e => getComputedStyle(e).{prop}"))
    goto_route(page, "tablero")
    page.wait_for_selector("[data-bars] .bar-row")
    check_hover(page, label, "barra de responsable", page.locator("[data-bars] .bar-row").first,
                css("[data-bars] .bar-row", "backgroundColor"), css("[data-bars] .bar-link", "color"))
    check_hover(page, label, "cifra de Estados", page.locator("[data-status-link='cerrado']"),
                css("[data-status-link='cerrado']", "backgroundColor"),
                css("[data-status-link='cerrado'] .kpi-note", "color"))
    check_hover(page, label, "fila del semáforo", page.locator("[data-deadlines] a[data-id]").first,
                css("[data-deadlines] a[data-id]", "backgroundColor"),
                css("[data-deadlines] a[data-id] .list-meta", "color"))
    check_hover(page, label, "enlace del menú", page.locator("ds-sidebar a[data-route='consulta']"),
                css("ds-sidebar a[data-route='consulta']", "backgroundColor"),
                css("ds-sidebar a[data-route='consulta']", "color"))
    # Enlace activo del menú: mismo fondo azul, texto oscuro ≥ 7:1 e ícono en acento
    act = page.eval_on_selector("ds-sidebar a[aria-current='page']", """e => { const s = getComputedStyle(e);
        return [s.backgroundColor, s.color, getComputedStyle(e.querySelector('svg')).color]; }""")
    accent = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--color-accent').trim()")
    check(f"{label}: enlace activo del menú con fondo azul", act[0] == HOVER_BG and contrast(act[1], act[0]) >= 7
          and act[2] == hex_rgb(accent), f"{act} contraste {contrast(act[1], act[0]):.2f}")
    goto_route(page, "consulta")
    page.wait_for_selector("[data-list='contratos'] a[data-id]")
    check_hover(page, label, "fila de la consulta", page.locator("[data-list='contratos'] a[data-id]").first,
                css("[data-list='contratos'] a[data-id]", "backgroundColor"),
                css("[data-list='contratos'] a[data-id] .list-sub", "color"))
    dd = page.locator("ds-dropdown[data-filter='estado']")
    dd.evaluate("e => e.scrollIntoView({block: 'center'})")
    dd.locator(".trigger").click()
    opt = dd.locator(".option").nth(1)
    check_hover(page, label, "opción del desplegable", opt, lambda: opt.evaluate("e => getComputedStyle(e).backgroundColor"))
    page.keyboard.press("Escape")
    cid = next(c["id"] for c in SEED["contratos"] if c["tiene_tarjeta"])
    open_ficha(page, cid)
    head = page.locator("ds-step").first.locator(".header")
    check_hover(page, label, "paso de la ficha", head, lambda: head.evaluate("e => getComputedStyle(e).backgroundColor"))
    btn = page.locator("[data-log-add]")
    check_hover(page, label, "botón", btn,
                lambda: btn.evaluate("e => getComputedStyle(e.shadowRoot.querySelector('button')).backgroundColor"))


def secop_checks(page, label):
    """La ficha enlaza al SECOP de data/secop.json (no al del Excel) y nombra la plataforma."""
    table = json.loads((ROOT / "data" / "secop.json").read_text(encoding="utf-8"))["contratos"]
    by_id = {c["id"]: c for c in SEED["contratos"]}
    changed = [cid for cid, v in table.items() if v["url"] != by_id[cid]["secop"]]
    wrong = []
    for cid in changed:
        open_ficha(page, cid)
        a = page.locator("[data-secop]")
        got = (a.get_attribute("href"), a.text_content().strip(), page.locator("[data-secop-unverified]").count())
        exp = (table[cid]["url"], f"Abrir en {table[cid]['plataforma']} ↗", 0 if table[cid]["verificado"] else 1)
        if got != exp:
            wrong.append(f"{cid}: {got}")
    check(f"{label}: {len(changed)} enlaces SECOP corregidos desde datos.gov.co", not wrong and len(changed) > 0,
          "; ".join(wrong)[:300])


def phase4_and_secop(page, label):
    phase4(page, label)
    secop_checks(page, label)


def phase5_and_hover(page, label):
    phase5(page, label)
    hover_checks(page, label)
    field_checks(page, label)
    table_checks(page, label)


STORAGE_KEY = "liquidaciones_esap.v1"
STORE_JS = "import(new URL('js/store.js', location.href).href)"  # misma instancia que usa la app


def stored(page):
    """Estado guardado en localStorage (None si no hay)."""
    raw = page.evaluate(f"localStorage.getItem('{STORAGE_KEY}')")
    return json.loads(raw) if raw else None


def kpis(page):
    goto_route(page, "tablero")
    page.wait_for_selector("[data-kpi='avance'] .kpi-value")
    return {k: page.text_content(f"[data-kpi='{k}'] .kpi-value").strip() for k in ("contratos", "avance")}


def open_respaldo(page):
    goto_route(page, "respaldo")
    page.wait_for_selector("[data-backup-summary]")


def choose_file(page, name, content):
    """Elige un archivo en el selector de Importar (sin abrir el diálogo del sistema)."""
    page.set_input_files("[data-import-file]", files=[{
        "name": name, "mimeType": "application/json", "buffer": content.encode("utf-8")}])


def dialog_open(page):
    return page.locator("dialog.confirm-dialog[open]").count() == 1


def phase6(page, label):
    tmp = SHOTS / f"respaldo_{label}"
    tmp.mkdir(exist_ok=True)

    # Vista desde el menú y desde la insignia de origen
    page.click("#data-source")
    page.wait_for_selector("[data-backup-summary]", timeout=5000)
    current = page.eval_on_selector_all("ds-sidebar a[aria-current='page']", "els => els.map(e => e.dataset.route)")
    check(f"{label}: la insignia de origen abre Respaldo", current == ["respaldo"], str(current))

    # Un cambio propio, para que exportado ≠ semilla
    page.evaluate(f"""async () => {{ const s = await {STORE_JS};
        s.addLog(s.contracts()[0].id, '2026-11-23', 'Prueba de respaldo {label}'); }}""")
    before_kpis = kpis(page)
    open_respaldo(page)
    summary = page.text_content("[data-backup-summary]")
    check(f"{label}: resumen con origen local y cifras", "guardados en este navegador" in summary
          and f"{len(SEED['contratos'])} contratos" in summary, " ".join(summary.split())[:120])

    # Exportar
    with page.expect_download() as dl:
        page.click("[data-export]")
    download = dl.value
    exported_path = tmp / download.suggested_filename
    download.save_as(str(exported_path))
    exported_text = exported_path.read_text(encoding="utf-8")
    exported = json.loads(exported_text)
    check(f"{label}: nombre del archivo de respaldo",
          re.fullmatch(r"liquidaciones_esap_respaldo_\d{4}-\d{2}-\d{2}_\d{4}\.json", download.suggested_filename),
          download.suggested_filename)
    check(f"{label}: sobre del respaldo", exported.get("formato") == "liquidaciones_esap.respaldo"
          and exported.get("version") == 1 and exported.get("origen") == "local"
          and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}", exported.get("exportado", "")),
          str({k: exported.get(k) for k in ("formato", "version", "origen", "exportado")}))
    check(f"{label}: exportado = datos guardados", exported["datos"] == stored(page))
    check(f"{label}: exportado incluye el cambio propio", exported["datos"] != SEED
          and any(b["texto"] == f"Prueba de respaldo {label}" for b in exported["datos"]["bitacora"]))
    check(f"{label}: archivo legible (UTF-8, sangría 2)", exported_text.startswith('{\n  "formato"')
          and ("á" in exported_text or "é" in exported_text))

    # Restablecer: cancelar no cambia nada
    page.click("[data-reset]")
    page.wait_for_selector("dialog.confirm-dialog[open]")
    page.keyboard.press("Escape")
    check(f"{label}: cancelar restablecer no cambia los datos",
          not dialog_open(page) and stored(page) == exported["datos"])
    # "Exportar antes" descarga sin cerrar el diálogo; confirmar vuelve a la semilla
    page.click("[data-reset]")
    page.wait_for_selector("dialog.confirm-dialog[open]")
    with page.expect_download() as dl2:
        page.click("dialog [data-dialog='extra']")
    pre = json.loads(Path(dl2.value.path()).read_text(encoding="utf-8"))
    check(f"{label}: 'Exportar antes' descarga y deja el diálogo abierto",
          dialog_open(page) and pre["datos"] == exported["datos"]
          and "descargado" in page.text_content("dialog [data-dialog='extra']"))
    page.click("dialog [data-dialog='confirm']")
    page.wait_for_function("document.getElementById('data-source').dataset.source === 'semilla'", timeout=5000)
    state = page.evaluate(f"async () => (await {STORE_JS}).getState()")
    check(f"{label}: restablecer vuelve a la semilla", stored(page) is None and state == SEED)
    check(f"{label}: restablecer queda deshabilitado con la semilla",
          page.get_attribute("[data-reset]", "disabled") is not None)

    # Importar archivos inválidos: se rechazan sin tocar los datos
    bad_files = {
        "no_json.json": "esto no es JSON",
        "otro_formato.json": json.dumps({"formato": "otra.app", "version": 1, "datos": {}}),
        "version_2.json": json.dumps({**exported, "version": 2}),
        "huerfanos.json": json.dumps({**SEED, "bitacora": SEED["bitacora"] + [{"contrato": "NO-EXISTE", "texto": "x"}]}),
        "incompleto.json": json.dumps({k: v for k, v in SEED.items() if k != "avances"}),
    }
    for name, content in bad_files.items():
        choose_file(page, name, content)
        page.wait_for_function(f"[...document.querySelectorAll('ds-toast')].some(t => t.textContent.includes('{name}'))",
                               timeout=5000)
        check(f"{label}: importar {name} se rechaza", not dialog_open(page)
              and stored(page) is None and page.get_attribute("#data-source", "data-source") == "semilla")

    # Importar el respaldo: cancelar no cambia nada; confirmar deja los datos idénticos
    choose_file(page, download.suggested_filename, exported_text)
    page.wait_for_selector("dialog.confirm-dialog[open]")
    archivo = page.text_content("dialog [data-compare='archivo']")
    actual = page.text_content("dialog [data-compare='actual']")
    n_log = len(exported["datos"]["bitacora"])
    check(f"{label}: confirmación compara archivo y datos actuales",
          f"{n_log} entradas" in archivo and f"{len(SEED['bitacora'])} entradas" in actual, f"{archivo} | {actual}")
    page.click("dialog [data-dialog='cancel']")
    check(f"{label}: cancelar importar no cambia los datos", not dialog_open(page) and stored(page) is None)
    choose_file(page, download.suggested_filename, exported_text)
    page.wait_for_selector("dialog.confirm-dialog[open]")
    page.click("dialog [data-dialog='confirm']")
    page.wait_for_function("document.getElementById('data-source').dataset.source === 'local'", timeout=5000)
    state = page.evaluate(f"async () => (await {STORE_JS}).getState()")
    check(f"{label}: exportar, restablecer e importar = datos idénticos",
          stored(page) == exported["datos"] and state == exported["datos"])
    check(f"{label}: el tablero vuelve a las mismas cifras", kpis(page) == before_kpis, str(before_kpis))
    open_respaldo(page)
    page.reload(wait_until="networkidle")
    page.wait_for_selector("[data-backup-summary]")
    check(f"{label}: lo importado persiste al recargar", stored(page) == exported["datos"]
          and page.get_attribute("#data-source", "data-source") == "local")

    # Importar un seed.json suelto (sin sobre)
    choose_file(page, "seed.json", (ROOT / "data" / "seed.json").read_text(encoding="utf-8"))
    page.wait_for_selector("dialog.confirm-dialog[open]")
    check(f"{label}: seed.json se reconoce como semilla", "semilla" in page.text_content("dialog .confirm-body"))
    page.click("dialog [data-dialog='confirm']")
    page.wait_for_function(f"localStorage.getItem('{STORAGE_KEY}') !== null && "
                           f"JSON.parse(localStorage.getItem('{STORAGE_KEY}')).bitacora.length === {len(SEED['bitacora'])}",
                           timeout=5000)
    check(f"{label}: importar seed.json carga la semilla", stored(page) == SEED)
    page.screenshot(path=str(SHOTS / f"fase6_{label}_respaldo.png"), full_page=True)


PHASES = {"2": phase2, "3": phase3, "4": phase4_and_secop, "5": phase5_and_hover, "6": phase6}


def run(browser, url, label, phases, **ctx):
    context = browser.new_context(**ctx)
    page = context.new_page()
    errors = []
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("requestfailed", lambda r: errors.append(f"{r.failure} {r.url[:120]}"))
    page.goto(url, wait_until="networkidle")
    page.wait_for_selector("#view > *", timeout=10000)
    if label == "movil":
        mobile = page.evaluate("matchMedia('(max-width: 768px)').matches")
        check("movil: modo móvil detectado por matchMedia", mobile)
    for ph in phases:
        PHASES[ph](page, label)
    check(f"{label}: 0 errores de consola", not errors, "; ".join(errors)[:300])
    context.close()


def main():
    phases = [sys.argv[1]] if len(sys.argv) > 1 else sorted(PHASES)
    SHOTS.mkdir(exist_ok=True)
    httpd = serve()
    url = f"http://127.0.0.1:{httpd.server_address[1]}/src/index.html"
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")
        run(browser, url, "escritorio", phases, viewport={"width": 1440, "height": 900})
        run(browser, url, "movil", phases, viewport={"width": 390, "height": 844},
            is_mobile=True, has_touch=True, device_scale_factor=2)
        browser.close()
    httpd.shutdown()
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} verificaciones OK")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
