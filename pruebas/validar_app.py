"""Validación de la app con Playwright + Edge del sistema (escritorio y celular emulado).

Sirve la carpeta del proyecto por HTTP y recorre los criterios de la fase indicada en
06_IMPLEMENTATION.md. Los conteos se leen de data/seed.json, no se fijan en la prueba.
Uso:  python pruebas/validar_app.py [fase]      (por defecto, todas las fases construidas)
"""
import http.server
import json
import socketserver
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


PHASES = {"2": phase2}


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
