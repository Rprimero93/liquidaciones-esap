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


def serve():
    handler = partial(QuietHandler, directory=str(ROOT))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
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


def phase2(page, label):
    # Estilo activo
    href = page.eval_on_selector("#style-link", "el => el.getAttribute('href')")
    check(f"{label}: estilo activo minimalista", href.endswith(STYLE), href)
    bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
    check(f"{label}: fondo del estilo aplicado", bg == "rgb(255, 255, 255)", bg)

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
    page.evaluate("document.querySelector('ds-sidebar').shadowRoot.querySelector('.close').click()")
    check(f"{label}: cerrar oculta el menú", not visible(nav) and visible(reopen))
    page.evaluate(f"{reopen}.click()")
    check(f"{label}: reabrir muestra el menú", visible(nav) and not visible(reopen))
    if label == "movil":
        tops = page.eval_on_selector_all("ds-sidebar > a", "els => els.map(e => Math.round(e.getBoundingClientRect().top))")
        check(f"{label}: enlaces en una sola fila", len(set(tops)) == 1, str(tops))

    # Las 3 rutas desde la Sidebar
    for route in ("tablero", "consulta", "ficha"):
        page.click(f"ds-sidebar a[data-route='{route}']")
        page.wait_for_function(f"location.hash === '#/{route}'", timeout=5000)
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
    for est in ("en-tramite", "cerrado", "paralizado"):
        if not page.locator(f".chip[data-status='{est}']").count():
            continue
        fg, bg = page.eval_on_selector(f".chip[data-status='{est}']",
                                       "e => [getComputedStyle(e).color, getComputedStyle(e).backgroundColor]")
        ratio = contrast(fg, bg)
        check(f"{label}: contraste chip {est} >= 7:1", ratio >= 7, f"{ratio:.2f}")

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


PHASES = {"2": phase2, "3": phase3}


def run(browser, url, label, phases, **ctx):
    context = browser.new_context(**ctx)
    page = context.new_page()
    errors = []
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.on("pageerror", lambda e: errors.append(str(e)))
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
