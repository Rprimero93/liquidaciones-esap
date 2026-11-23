"""Extrae liquidacion.xlsm a data/seed.json normalizado (solo lectura del Excel).

Uso: python scripts/extraer_excel.py [ruta_excel] [ruta_salida]
"""
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

import openpyxl

# Rutas por defecto
EXCEL_DEFAULT = Path(r"C:\Users\Rprim\Documents\proyectos esap\liquidacion.xlsm")
SEED_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "seed.json"

SHEET_CONTRACTS = "Contratos"
SHEET_CARDS = "Liquidaciones "
ANCHOR = "Perdida de competencia"  # celda ancla de cada tarjeta

# Desplazamientos de cada tarjeta respecto de la fila ancla
OFF_CONTRACTOR = -2
OFF_DEADLINE = 0
OFF_CLOSING = 1
OFF_STEPS = 4
N_STEPS = 12
OFF_OBSERVATION = 16
OFF_NOTE = 17
OFF_ALERTS = 18
N_ALERTS = 4
OFF_VALUE = 22
OFF_SECOP = 23
OFF_PERCENT = 25

ENTRY_RE = re.compile(r"(?m)^\s*([a-zA-Z])\)\s*")
# dd/mm/aaaa, d-m-aaaa, d/m/aa, '29/7/ 2025' y '31/072025' (separador final omitido)
DATE_RE = re.compile(r"(\d{1,2})[/-](\d{1,2})(?:[/-]\s*)?(\d{4}|\d{2})(?!\d)")


def clean(value):
    """Normaliza texto: espacios duros, tabuladores y saltos internos a un espacio."""
    if value is None:
        return ""
    text = str(value).replace("\xa0", " ").replace("\u202f", " ")
    return re.sub(r"\s+", " ", text).strip()


def key(value):
    """Clave de comparación para cruzar contratista de la tarjeta con la hoja Contratos."""
    return clean(value).casefold()


def contract_id(value):
    """Número de contrato canónico: 'BOG- 1588 -2019' -> 'BOG-1588-2019'."""
    return re.sub(r"\s*-\s*", "-", clean(value)).upper()


def iso(value):
    if isinstance(value, (datetime, date)):
        return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
    return None


def parse_date(text):
    """Primera fecha dd/mm/aaaa del texto (tolera '31/072025'); None si no hay o es inválida."""
    m = DATE_RE.search(text or "")
    if not m:
        return None
    d, mth, y = (int(g) for g in m.groups())
    if y < 100:
        y += 2000
    try:
        return date(y, mth, d).isoformat()
    except ValueError:
        return None


def split_log(text, source):
    """Divide la observación 'a) ... b) ...' en entradas de bitácora."""
    raw = (text or "").replace("\xa0", " ").strip()
    if not raw:
        return []
    parts = ENTRY_RE.split(raw)
    entries = []
    if len(parts) == 1:
        entries.append(raw)
    else:
        if parts[0].strip():
            entries.append(parts[0].strip())
        entries += [parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)]
    return [
        {"fecha": parse_date(e), "texto": clean(e), "origen": source}
        for e in entries if clean(e)
    ]


def strip_label(label):
    return clean(label).rstrip(" :")


def find_cards(ws):
    """Devuelve (fila_ancla, columna) de cada tarjeta, en orden de lectura."""
    anchors = []
    for row in ws.iter_rows():
        for c in row:
            if isinstance(c.value, str) and clean(c.value) == ANCHOR:
                anchors.append((c.row, c.column))
    return sorted(anchors)


def extract(excel_path):
    wb = openpyxl.load_workbook(excel_path)
    wb_values = openpyxl.load_workbook(excel_path, data_only=True)
    ws_c = wb[SHEET_CONTRACTS]
    ws_l = wb[SHEET_CARDS]
    ws_lv = wb_values[SHEET_CARDS]

    # Contratos (hoja maestra)
    contracts = []
    by_name = {}
    for r in range(2, ws_c.max_row + 1):
        num = clean(ws_c.cell(r, 1).value)
        if not num:
            continue
        item = {
            "id": contract_id(num),
            "numero": num,
            "contratista": clean(ws_c.cell(r, 2).value),
            "responsable": clean(ws_c.cell(r, 3).value),
            "estado": clean(ws_c.cell(r, 5).value),
            "documento_activo": clean(ws_c.cell(r, 7).value),
            "perdida_competencia": None,
            "plazo_cierre": None,
            "plazo_cierre_texto": "",
            "valor": None,
            "secop": "",
            "tiene_tarjeta": False,
            "fila_excel": r,
        }
        contracts.append(item)
        by_name[key(item["contratista"])] = item

    cards = find_cards(ws_l)
    if not cards:
        raise ValueError("No se encontraron tarjetas en la hoja Liquidaciones")

    # Catálogos tomados de la primera tarjeta
    r0, c0 = cards[0]
    steps = [
        {"id": i + 1, "nombre": strip_label(ws_l.cell(r0 + OFF_STEPS + i, c0 + 1).value)}
        for i in range(N_STEPS)
    ]
    steps[-1]["nombre"] = steps[-1]["nombre"] or "Cierre"
    alerts = [
        {"id": i + 1, "nombre": strip_label(ws_l.cell(r0 + OFF_ALERTS + i, c0 + 1).value)}
        for i in range(N_ALERTS)
    ]

    progress = []
    log = []
    unmatched = []
    for r, c in cards:
        name = ws_l.cell(r + OFF_CONTRACTOR, c).value
        contract = by_name.get(key(name))
        if contract is None:
            unmatched.append({"contratista": clean(name), "celda": ws_l.cell(r, c).coordinate})
            continue
        cid = contract["id"]
        contract["tiene_tarjeta"] = True
        contract["celda_tarjeta"] = ws_l.cell(r + OFF_CONTRACTOR, c).coordinate
        contract["perdida_competencia"] = iso(ws_l.cell(r + OFF_DEADLINE, c + 1).value)
        closing = ws_l.cell(r + OFF_CLOSING, c + 1).value
        contract["plazo_cierre"] = iso(closing) or parse_date(clean(closing))
        contract["plazo_cierre_texto"] = clean(closing)
        value = ws_l.cell(r + OFF_VALUE, c + 1).value
        contract["valor"] = value if isinstance(value, (int, float)) else None
        contract["secop"] = clean(ws_l.cell(r + OFF_SECOP, c + 1).value)
        cached = ws_lv.cell(r + OFF_PERCENT, c).value  # valor calculado de =COUNTIF(...)/12
        contract["avance_excel"] = cached if isinstance(cached, (int, float)) else None

        for i, step in enumerate(steps):
            label = strip_label(ws_l.cell(r + OFF_STEPS + i, c + 1).value)
            progress.append({
                "contrato": cid,
                "tipo": "paso",
                "item": step["id"],
                "hecho": ws_l.cell(r + OFF_STEPS + i, c).value is True,
                "etiqueta": label if label and label != step["nombre"] else "",
            })
        for i, alert in enumerate(alerts):
            progress.append({
                "contrato": cid,
                "tipo": "alerta",
                "item": alert["id"],
                "hecho": ws_l.cell(r + OFF_ALERTS + i, c).value is True,
                "etiqueta": "",
            })
        for src, off in (("observacion", OFF_OBSERVATION), ("nota", OFF_NOTE)):
            for entry in split_log(ws_l.cell(r + off, c + 1).value, src):
                log.append({"contrato": cid, **entry})

    return {
        "meta": {
            "fuente": Path(excel_path).name,
            "generado": datetime.now().isoformat(timespec="seconds"),
            "avance_general_excel": ws_lv["K2"].value,
            "tarjetas_sin_contrato": unmatched,
        },
        "pasos": steps,
        "alertas": alerts,
        "contratos": contracts,
        "avances": progress,
        "bitacora": log,
    }


def main(argv):
    excel = Path(argv[1]) if len(argv) > 1 else EXCEL_DEFAULT
    out = Path(argv[2]) if len(argv) > 2 else SEED_DEFAULT
    data = extract(excel)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    with_card = sum(c["tiene_tarjeta"] for c in data["contratos"])
    print(f"{len(data['contratos'])} contratos ({with_card} con tarjeta), "
          f"{len(data['bitacora'])} entradas de bitácora, "
          f"{len(data['meta']['tarjetas_sin_contrato'])} tarjetas sin contrato -> {out}")


if __name__ == "__main__":
    main(sys.argv)
