"""Fase 7 — recorrido de punta a punta como un usuario (Playwright + Edge, escritorio y celular emulado).

A diferencia de validar_app.py (verificaciones por fase), aquí los pasos se encadenan y lo que se
cambia en una vista se comprueba en las demás. Las cifras esperadas se calculan en Python con un
modelo propio sobre los datos (la semilla o la semilla con las ediciones del recorrido), nunca se
leen de la app.

Uso:  python pruebas/recorrido.py [--url https://rprimero93.github.io/liquidaciones-esap]
"""
import copy
import json
import re
import sys
from datetime import date
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validar_app as va  # noqa: E402  (servidor, check(), helpers de la UI)

SHOTS = va.SHOTS
check = va.check
WARN_DAYS = 90       # mismo umbral que store.DEADLINE_WARN_DAYS
PARALYZED_ALERT = 1  # "Proceso paralizado por falta de información"


# --- Modelo en Python (misma regla que store.js, sobre cualquier versión de los datos) ---

def steps_of(data, cid):
    return [a for a in data["avances"] if a["contrato"] == cid and a["tipo"] == "paso"]


def done_of(data, cid):
    rows = steps_of(data, cid)
    return sum(r["hecho"] for r in rows) if rows else None


def status_of(data, c):
    done = done_of(data, c["id"])
    if done is None:
        return "sin-seguimiento"
    if done == len(data["pasos"]):
        return "cerrado"
    paralyzed = any(a["contrato"] == c["id"] and a["tipo"] == "alerta" and a["item"] == PARALYZED_ALERT and a["hecho"]
                    for a in data["avances"])
    return "paralizado" if paralyzed else "en-tramite"


def average(data, ids):
    """Promedio con enteros (pasos hechos / pasos posibles), igual que store.averageProgress."""
    done = [d for d in (done_of(data, i) for i in ids) if d is not None]
    return sum(done) / (len(done) * len(data["pasos"])) if done else None


def by_responsible(data):
    groups = {}
    for c in data["contratos"]:
        if done_of(data, c["id"]) is None:
            continue
        for name in va.responsibles(c):
            groups.setdefault(name, []).append(c["id"])
    rows = [(n, average(data, ids), len(ids)) for n, ids in groups.items()]
    rows.sort(key=lambda r: (-r[1], -r[2], va.norm(r[0])))
    return rows


def deadline_levels(data, today):
    out = []
    for c in data["contratos"]:
        if status_of(data, c) == "cerrado":
            continue
        if not c["perdida_competencia"]:
            out.append((c["id"], None, "sin-fecha"))
            continue
        days = (date.fromisoformat(c["perdida_competencia"]) - today).days
        out.append((c["id"], days, "vencido" if days < 0 else "proximo" if days <= WARN_DAYS else "en-plazo"))
    return sorted(out, key=lambda r: float("inf") if r[1] is None else r[1])


def expected_dashboard(page, data, today):
    """Cifras que debería mostrar el tablero para estos datos, con el formato de la app."""
    pct = lambda v: va.fmt_pct(page, v)
    levels = deadline_levels(data, today)
    return {
        "contratos": str(len(data["contratos"])),
        "avance": pct(average(data, [c["id"] for c in data["contratos"]]) or 0),
        "estados": {s: str(sum(status_of(data, c) == s for c in data["contratos"]))
                    for s in ("cerrado", "paralizado", "en-tramite")},
        "vencidos": str(sum(lv == "vencido" for _, _, lv in levels)),
        "niveles": {lv: str(sum(x == lv for _, _, x in levels)) for lv in ("vencido", "proximo", "en-plazo", "sin-fecha")},
        "barras": [(n, pct(v)) for n, v, _ in by_responsible(data)],
        "semaforo": [cid for cid, _, _ in levels],
    }


# --- Lectura de la UI ---

def read_dashboard(page):
    va.goto_route(page, "tablero")
    page.wait_for_selector("[data-bars] .bar-row")
    txt = lambda sel: page.text_content(sel).strip()
    return {
        "contratos": txt("[data-kpi='contratos'] .kpi-value"),
        "avance": txt("[data-kpi='avance'] .kpi-value"),
        "estados": {s: txt(f"[data-status-link='{s}'] .kpi-value") for s in ("cerrado", "paralizado", "en-tramite")},
        "vencidos": txt("[data-kpi='vencidos'] .kpi-value"),
        "niveles": {lv: txt(f"[data-level-count='{lv}']") for lv in ("vencido", "proximo", "en-plazo", "sin-fecha")},
        "barras": page.eval_on_selector_all("[data-bars] .bar-row", """els => els.map(e => [e.dataset.name,
            e.querySelector('.bar-value').textContent.trim()])"""),
        "semaforo": page.eval_on_selector_all("[data-deadlines] a[data-id]", "els => els.map(e => e.dataset.id)"),
    }


def compare_dashboard(page, label, step, data, today):
    got = read_dashboard(page)
    exp = expected_dashboard(page, data, today)
    got["barras"] = [tuple(b) for b in got["barras"]]
    diff = {k: (got[k], exp[k]) for k in exp if got[k] != exp[k]}
    check(f"{label}: {step} — tablero = cálculo en Python", not diff, str(diff)[:300])
    return got


def press(page, label, target):
    """Clic en escritorio, toque en celular."""
    loc = page.locator(target) if isinstance(target, str) else target
    loc.scroll_into_view_if_needed()
    if label == "movil":
        loc.tap()
    else:
        loc.click()


def browser_today(page):
    return date.fromisoformat(page.evaluate(
        "(() => { const d = new Date(); return [d.getFullYear(), String(d.getMonth()+1).padStart(2,'0'),"
        " String(d.getDate()).padStart(2,'0')].join('-'); })()"))


class Health:
    """Errores de consola, de página y solicitudes fallidas, más el desplazamiento horizontal."""

    def __init__(self, page):
        self.page = page
        self.errors = []
        page.on("console", lambda m: m.type == "error" and self.errors.append(m.text))
        page.on("pageerror", lambda e: self.errors.append(str(e)))
        page.on("requestfailed", lambda r: self.errors.append(f"{r.failure} {r.url[:120]}"))

    def check(self, label, step):
        over = self.page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        check(f"{label}: {step} — sin errores ni desplazamiento horizontal", not self.errors and over <= 0,
              f"errores {self.errors[:3]}; sobrante {over}px")
        self.errors.clear()


def shot(page, label, n, name):
    page.screenshot(path=str(SHOTS / f"fase7_{label}_{n:02d}_{name}.png"), full_page=True)


# --- El recorrido ---

def pick_contract(data):
    """Contrato paralizado al que le falten al menos 2 pasos: al completar uno sigue abierto."""
    for c in data["contratos"]:
        done = done_of(data, c["id"])
        if status_of(data, c) == "paralizado" and len(data["pasos"]) - done >= 2:
            return c
    raise RuntimeError("La semilla no tiene un contrato paralizado con 2 o más pasos pendientes")


def journey(page, label):
    health = Health(page)
    seed = va.SEED
    today = browser_today(page)
    page.wait_for_selector("[data-bars] .bar-row")

    # 1. Tablero con la semilla
    before = compare_dashboard(page, label, "1. inicio", seed, today)
    check(f"{label}: 1. origen de datos = semilla", page.get_attribute("#data-source", "data-source") == "semilla")
    shot(page, label, 1, "tablero")
    health.check(label, "1. tablero")

    # 2. Clic en "Paralizados" → Consulta filtrada
    press(page, label, "[data-status-link='paralizado']")
    page.wait_for_function("location.hash === '#/consulta'", timeout=5000)
    page.wait_for_selector("[data-list='contratos'] a[data-id]")
    paralyzed = [c["id"] for c in seed["contratos"] if status_of(seed, c) == "paralizado"]
    check(f"{label}: 2. Consulta filtrada por Paralizados", va.listed(page) == paralyzed
          and page.text_content("[data-count]").strip() == before["estados"]["paralizado"], f"{len(va.listed(page))}")
    shot(page, label, 2, "consulta_paralizados")
    health.check(label, "2. consulta")

    # 3. Búsqueda por número sin guiones → ficha
    c = pick_contract(seed)
    query = c["id"].replace("-", "")[:-4]  # ej. BOG1588 (sin año)
    page.fill("input[data-filter='q']", query)
    page.wait_for_selector(f"[data-list='contratos'] a[data-id='{c['id']}']", timeout=5000)
    check(f"{label}: 3. búsqueda '{query}' encuentra {c['id']}", c["id"] in va.listed(page), str(va.listed(page)))
    press(page, label, f"[data-list='contratos'] a[data-id='{c['id']}']")
    page.wait_for_selector(f"[data-contrato='{c['id']}'] ds-step", timeout=5000)
    shot(page, label, 3, "ficha_antes")
    health.check(label, "3. ficha")

    # 4. Ediciones del usuario, aplicadas también al modelo
    edited = copy.deepcopy(seed)
    n = len(seed["pasos"])
    pending = min(s["item"] for s in steps_of(seed, c["id"]) if not s["hecho"])
    press(page, label, f"[data-done='{pending}']")
    for a in edited["avances"]:
        if a["contrato"] == c["id"] and a["tipo"] == "paso" and a["item"] == pending:
            a["hecho"] = True
    check(f"{label}: 4a. completar la etapa actual sube el avance",
          va.avance(page) == va.fmt_pct(page, done_of(edited, c["id"]) / n), va.avance(page))

    alert = page.locator(f"[data-alert='{PARALYZED_ALERT}']")
    alert.scroll_into_view_if_needed()
    press(page, label, alert)
    for a in edited["avances"]:
        if a["contrato"] == c["id"] and a["tipo"] == "alerta" and a["item"] == PARALYZED_ALERT:
            a["hecho"] = False
    chip = page.get_attribute("[data-contrato] .ficha-head .chip[data-status]", "data-status")
    check(f"{label}: 4b. apagar la alerta deja el contrato en trámite", not alert.is_checked() and chip == "en-tramite", chip)

    dp = page.locator("ds-datepicker[data-date='perdida_competencia']")
    dp.evaluate("e => e.scrollIntoView({block: 'center'})")
    dp.locator(".trigger").click()
    dp.locator(".day:not(.day--vacio)", has_text=re.compile(r"^15$")).click()
    new_date = dp.evaluate("e => e.value")
    next(x for x in edited["contratos"] if x["id"] == c["id"])["perdida_competencia"] = new_date
    check(f"{label}: 4c. fecha elegida en el calendario", bool(re.fullmatch(r"\d{4}-\d{2}-15", new_date or "")), new_date)

    note = f"Recorrido Fase 7 ({label})"
    page.fill("[data-log-text]", note)
    press(page, label, "[data-log-add]")
    check(f"{label}: 4d. observación agregada", page.text_content("[data-log] li .log-text") == note)
    stored = va.stored(page)
    check(f"{label}: 4e. lo guardado coincide con las ediciones",
          stored["avances"] == edited["avances"] and stored["contratos"] == edited["contratos"]
          and stored["bitacora"][:-1] == seed["bitacora"] and stored["bitacora"][-1]["texto"] == note)
    edited["bitacora"] = stored["bitacora"]  # la entrada nueva lleva la fecha de hoy
    shot(page, label, 4, "ficha_editada")
    health.check(label, "4. ediciones")

    # 5. El tablero se recalcula con los datos editados
    after = compare_dashboard(page, label, "5. tras editar", edited, today)
    check(f"{label}: 5. el tablero cambió (un paralizado menos)",
          int(after["estados"]["paralizado"]) == int(before["estados"]["paralizado"]) - 1)
    shot(page, label, 5, "tablero_editado")
    health.check(label, "5. tablero")

    # 6. Recarga: todo persiste
    page.reload(wait_until="networkidle")
    compare_dashboard(page, label, "6. tras recargar", edited, today)
    check(f"{label}: 6. origen de datos = local", page.get_attribute("#data-source", "data-source") == "local")
    health.check(label, "6. recarga")

    # 7. Respaldo: exportar → restablecer → importar
    press(page, label, "ds-sidebar a[data-route='respaldo']")
    page.wait_for_selector("[data-backup-summary]")
    with page.expect_download() as dl:
        press(page, label, "[data-export]")
    exported_path = SHOTS / f"fase7_{label}_{dl.value.suggested_filename}"
    dl.value.save_as(str(exported_path))
    exported = json.loads(exported_path.read_text(encoding="utf-8"))
    check(f"{label}: 7a. respaldo exportado = datos editados", exported["datos"] == edited)
    press(page, label, "[data-reset]")
    page.wait_for_selector("dialog.confirm-dialog[open]")
    press(page, label, "dialog [data-dialog='confirm']")
    page.wait_for_function("document.getElementById('data-source').dataset.source === 'semilla'", timeout=5000)
    compare_dashboard(page, label, "7b. tras restablecer", seed, today)
    va.open_respaldo(page)
    page.set_input_files("[data-import-file]", str(exported_path))
    page.wait_for_selector("dialog.confirm-dialog[open]")
    press(page, label, "dialog [data-dialog='confirm']")
    page.wait_for_function("document.getElementById('data-source').dataset.source === 'local'", timeout=5000)
    check(f"{label}: 7c. importar deja los datos idénticos", va.stored(page) == edited)
    compare_dashboard(page, label, "7d. tras importar", edited, today)
    shot(page, label, 7, "tablero_importado")
    health.check(label, "7. respaldo")

    # 8. Solo teclado: menú con Tab/Enter y Escape cierra el diálogo sin cambiar nada
    page.focus("ds-sidebar a[data-route='tablero']")
    page.keyboard.press("Tab")
    focused = page.evaluate("document.activeElement.dataset.route")
    page.keyboard.press("Enter")
    page.wait_for_function("location.hash === '#/consulta'", timeout=5000)
    check(f"{label}: 8a. Tab lleva al siguiente enlace y Enter navega", focused == "consulta")
    va.open_respaldo(page)
    page.locator("[data-reset] button").focus()
    page.keyboard.press("Enter")
    page.wait_for_selector("dialog.confirm-dialog[open]")
    in_dialog = page.evaluate("!!document.activeElement.closest('dialog')")
    page.keyboard.press("Escape")
    check(f"{label}: 8b. Enter abre el diálogo (con el foco dentro) y Escape lo cierra sin cambios", in_dialog
          and page.locator("dialog.confirm-dialog[open]").count() == 0 and va.stored(page) == edited)
    health.check(label, "8. teclado")


def run(browser, url, label, **ctx):
    context = browser.new_context(accept_downloads=True, **ctx)
    page = context.new_page()
    page.goto(url, wait_until="networkidle")
    journey(page, label)
    context.close()


def main():
    SHOTS.mkdir(exist_ok=True)
    # --url <dirección>: corre contra la app publicada (ej. GitHub Pages) en lugar del servidor local
    args = sys.argv[1:]
    remote = args[args.index("--url") + 1] if "--url" in args else None
    httpd = None if remote else va.serve()
    url = (remote.rstrip("/") + "/src/index.html#/tablero") if remote         else f"http://127.0.0.1:{httpd.server_address[1]}/src/index.html#/tablero"
    print(f"Recorrido contra {url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")
        run(browser, url, "escritorio", viewport={"width": 1440, "height": 900})
        run(browser, url, "movil", viewport={"width": 390, "height": 844},
            is_mobile=True, has_touch=True, device_scale_factor=2)
        browser.close()
    if httpd:
        httpd.shutdown()
    failed = [r for r in va.results if not r[1]]
    print(f"\n{len(va.results) - len(failed)}/{len(va.results)} verificaciones del recorrido OK")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
