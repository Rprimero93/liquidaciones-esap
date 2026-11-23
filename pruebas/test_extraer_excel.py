"""Prueba la extracción contra el Excel original (conteos leídos de los datos, sin números fijos)."""
import json
import sys
from pathlib import Path

import openpyxl
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import extraer_excel as ex  # noqa: E402

EXCEL = ex.EXCEL_DEFAULT
SEED = ex.SEED_DEFAULT

pytestmark = pytest.mark.skipif(not EXCEL.exists(), reason="Excel de origen no disponible")


@pytest.fixture(scope="module")
def data():
    return ex.extract(EXCEL)


@pytest.fixture(scope="module")
def sheet_contracts():
    ws = openpyxl.load_workbook(EXCEL)[ex.SHEET_CONTRACTS]
    return [ex.clean(ws.cell(r, 1).value) for r in range(2, ws.max_row + 1) if ex.clean(ws.cell(r, 1).value)]


def test_todos_los_contratos(data, sheet_contracts):
    # Mismo conjunto de contratos que la hoja Contratos, sin duplicados
    ids = [c["id"] for c in data["contratos"]]
    assert ids == [ex.contract_id(n) for n in sheet_contracts]
    assert len(set(ids)) == len(ids)


def test_toda_tarjeta_cruza_con_un_contrato(data):
    ws = openpyxl.load_workbook(EXCEL)[ex.SHEET_CARDS]
    assert data["meta"]["tarjetas_sin_contrato"] == []
    assert sum(c["tiene_tarjeta"] for c in data["contratos"]) == len(ex.find_cards(ws))


def test_avance_igual_al_excel(data):
    # Avance recalculado desde los pasos = valor calculado por Excel (=COUNTIF(...)/12)
    n_steps = len(data["pasos"])
    for c in data["contratos"]:
        if not c["tiene_tarjeta"]:
            continue
        done = sum(a["hecho"] for a in data["avances"]
                   if a["contrato"] == c["id"] and a["tipo"] == "paso")
        assert done / n_steps == pytest.approx(c["avance_excel"]), c["id"]


def test_estructura_por_contrato(data):
    for c in data["contratos"]:
        rows = [a for a in data["avances"] if a["contrato"] == c["id"]]
        expected = (len(data["pasos"]) + len(data["alertas"])) if c["tiene_tarjeta"] else 0
        assert len(rows) == expected, c["id"]


def test_bitacora_referencia_contratos(data):
    ids = {c["id"] for c in data["contratos"]}
    assert data["bitacora"]
    assert all(b["contrato"] in ids and b["texto"] for b in data["bitacora"])


@pytest.mark.parametrize("text,expected", [
    ("08/07/2025 se solicitó", "2025-07-08"),
    ("8/7/25, se envía", "2025-07-08"),
    ("7-11-2025, se subió", "2025-11-07"),
    ("29/7/ 2025 En mesa", "2025-07-29"),
    ("31/072025, se remite", "2025-07-31"),
    ("A partir del 31/06/2022", None),
    ("Sin fecha", None),
])
def test_parse_date(text, expected):
    assert ex.parse_date(text) == expected


def test_seed_actualizado(data):
    # El seed versionado corresponde al Excel actual (sin contar la marca de tiempo)
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    for k in ("generado",):
        seed["meta"].pop(k)
        data = {**data, "meta": {kk: v for kk, v in data["meta"].items() if kk != k}}
    assert seed == data
