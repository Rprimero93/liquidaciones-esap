"""Prueba el cruce de enlaces SECOP (sin red) y la tabla generada data/secop.json."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import consultar_secop as cs  # noqa: E402

SEED = json.loads((ROOT / "data" / "seed.json").read_text(encoding="utf-8"))
TABLE_PATH = ROOT / "data" / "secop.json"
NTC = "https://community.secop.gov.co/Public/Tendering/OpportunityDetail/Index?noticeUID=CO1.NTC.{}"


def row2(ref, prov, ntc):
    return {"referencia_del_contrato": ref, "proveedor_adjudicado": prov, "proceso_de_compra": "CO1.BDOS.1",
            "id_contrato": "CO1.PCCNTR.1",
            "urlproceso": {"url": NTC.format(ntc) + "&isFromPublicArea=True&isModal=true&asPopupView=true"}}


def test_numero_con_espacios_y_url_limpia():
    out = cs.match([{"id": "BOG-1588-2019", "contratista": "ABCONTROL INGENIERIA", "secop": ""}],
                   [row2("BOG- 1588 -2019", "ABCONTROL INGENIERIA SAS", 1002823)], [])
    assert out["BOG-1588-2019"]["url"] == NTC.format(1002823)
    assert out["BOG-1588-2019"]["verificado"] and out["BOG-1588-2019"]["contratista_coincide"]


def test_numero_unico_con_nombre_distinto_se_marca():
    out = cs.match([{"id": "BOG-594-2022", "contratista": "INSTITUTO GEOGRÁFICO AGUSTÍN CODAZZI", "secop": ""}],
                   [row2("BOG-594-2022", "IGAC Sede Central *", 2767375)], [])
    assert out["BOG-594-2022"]["contratista_coincide"] is False


def test_numero_repetido_exige_contratista():
    rows = [row2("BOG-1-2020", "OTRA EMPRESA SAS", 1), row2("BOG-1-2020", "TERCERA LTDA", 2)]
    assert cs.match([{"id": "BOG-1-2020", "contratista": "ACME SAS", "secop": ""}], rows, []) == {}


def test_secop1_verificado_y_sin_verificar():
    excel = "https://www.contratos.gov.co/consultas/detalleProceso.do?numConstancia=19*12*10144449&g*recaptcha*response=x"
    rows1 = [{"numero_de_constancia": "19-12-10144449", "numero_de_contrato": "BOG-1539-2019",
              "nom_razon_social_contratista": "MARLEN RUIZ MEDINA"}]
    out = cs.match([{"id": "BOG-1539-2019", "contratista": "MARLEN RUIZ MEDINA", "secop": excel},
                    {"id": "BOG-244-2016", "contratista": "FUNDACIÓN UNIVERSIDAD DEL VALLE",
                     "secop": excel.replace("19*12*10144449", "16*12*4734928")}], [], rows1)
    assert out["BOG-1539-2019"]["url"] == cs.SECOP1_URL.format("19-12-10144449")
    assert out["BOG-1539-2019"]["verificado"]
    assert out["BOG-244-2016"]["url"] == cs.SECOP1_URL.format("16-12-4734928")
    assert out["BOG-244-2016"]["verificado"] is False


def test_tabla_generada_cubre_la_semilla():
    table = json.loads(TABLE_PATH.read_text(encoding="utf-8"))["contratos"]
    ids = {c["id"] for c in SEED["contratos"]}
    assert set(table) <= ids
    assert ids - set(table) == set()  # los 26 tienen enlace
    for cid, v in table.items():
        assert v["url"].startswith("https://"), cid
        assert "*" not in v["url"] and "recaptcha" not in v["url"] and "&" not in v["url"], cid
    # Casos revisados a mano: proceso distinto del Excel y enlace SECOP I roto
    assert table["BOG-1311-2019"]["url"] == NTC.format(888220)
    assert table["BOG-1539-2019"]["url"] == cs.SECOP1_URL.format("19-12-10144449")
