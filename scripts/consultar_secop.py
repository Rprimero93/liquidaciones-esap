"""Enlaces SECOP verificados en los datos abiertos de Colombia Compra Eficiente (datos.gov.co).

Cruza cada contrato de data/seed.json por número (sin espacios) con:
  - SECOP II — Contratos Electrónicos (jbjy-vk9h), filtrado por el NIT de la ESAP.
  - SECOP I — Procesos de Compra Pública (f789-7hwg), por número de contrato y de constancia.
Escribe data/secop.json, que la app usa por encima del enlace del Excel (la semilla no se toca).

Uso:  python scripts/consultar_secop.py
"""
import json
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "data" / "seed.json"
OUT = ROOT / "data" / "secop.json"

NIT_ESAP = "899999054"
API = "https://www.datos.gov.co/resource/{}.json"
SECOP2 = "jbjy-vk9h"
SECOP1 = "f789-7hwg"
SECOP1_URL = "https://www.contratos.gov.co/consultas/detalleProceso.do?numConstancia={}"


def fetch(dataset, params, timeout=180):
    url = API.format(dataset) + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "liquidaciones-esap/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.load(res)


def ref_key(text):
    """Número de contrato comparable: sin espacios y en mayúsculas ('BOG- 1588 -2019' → 'BOG-1588-2019')."""
    return re.sub(r"\s+", "", text or "").upper()


def name_key(text):
    """Nombre comparable: sin tildes ni signos, en mayúsculas."""
    plain = unicodedata.normalize("NFD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9 ]", " ", plain.upper()).split()


def same_party(a, b):
    """El contratista coincide si comparten al menos dos palabras (o una, si alguno tiene una sola)."""
    wa, wb = set(name_key(a)), set(name_key(b))
    return len(wa & wb) >= min(2, len(wa), len(wb))


def process_url(url):
    """URL pública del proceso en SECOP II sin los parámetros de vista emergente."""
    return re.sub(r"&.*$", "", url or "")


def constancia_from(url):
    """Número de constancia de un enlace SECOP I (el Excel lo trae con '*' en lugar de '-')."""
    m = re.search(r"numConstancia=([0-9*\-]+)", url or "")
    return m.group(1).replace("*", "-") if m else None


def match(contracts, secop2_rows, secop1_rows):
    """Devuelve {id: entrada} para cada contrato encontrado. Funciones puras: se prueban sin red."""
    by_ref2 = {}
    for r in secop2_rows:
        by_ref2.setdefault(ref_key(r.get("referencia_del_contrato")), []).append(r)
    by_ref1 = {}
    for r in secop1_rows:
        by_ref1.setdefault(ref_key(r.get("numero_de_contrato")), []).append(r)
        if r.get("numero_de_constancia"):
            by_ref1.setdefault("CONST:" + r["numero_de_constancia"], []).append(r)

    out = {}
    for c in contracts:
        hits = [r for r in by_ref2.get(c["id"], []) if r.get("urlproceso")]
        same = [r for r in hits if same_party(r.get("proveedor_adjudicado"), c["contratista"])]
        # Si el nombre no coincide (ej. sigla "IGAC" frente al nombre completo) pero el número es único
        # en la ESAP, se acepta y se marca para revisar el contratista
        chosen = same[0] if same else (hits[0] if len(hits) == 1 else None)
        if chosen:
            out[c["id"]] = {
                "plataforma": "SECOP II",
                "url": process_url(chosen["urlproceso"]["url"]),
                "proceso": chosen.get("proceso_de_compra"),
                "contrato": chosen.get("id_contrato"),
                "contratista_secop": chosen.get("proveedor_adjudicado"),
                "verificado": True,
                "contratista_coincide": bool(same),
            }
            continue
        const = constancia_from(c.get("secop"))
        hits1 = by_ref1.get(c["id"], []) + (by_ref1.get("CONST:" + const, []) if const else [])
        hits1 = [r for r in hits1 if same_party(r.get("nom_razon_social_contratista"), c["contratista"])]
        if hits1:
            r = hits1[0]
            out[c["id"]] = {
                "plataforma": "SECOP I",
                "url": SECOP1_URL.format(r["numero_de_constancia"]),
                "proceso": r["numero_de_constancia"],
                "contrato": r.get("numero_de_contrato"),
                "contratista_secop": r.get("nom_razon_social_contratista"),
                "verificado": True,
                "contratista_coincide": True,
            }
            continue
        if const:
            # No figura en los datos abiertos: se conserva el enlace SECOP I del Excel, limpio
            # (constancia con '-' y sin el token de reCAPTCHA), marcado como no verificado
            out[c["id"]] = {"plataforma": "SECOP I", "url": SECOP1_URL.format(const), "proceso": const,
                            "contrato": None, "contratista_secop": None,
                            "verificado": False, "contratista_coincide": None}
    return out


def main():
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    contracts = seed["contratos"]
    print("Descargando contratos de la ESAP en SECOP II…")
    secop2 = fetch(SECOP2, {
        "$select": "referencia_del_contrato,proceso_de_compra,id_contrato,urlproceso,proveedor_adjudicado",
        "$where": f"nit_entidad='{NIT_ESAP}'", "$limit": 100000})
    # SECOP I solo para los que no aparecen en SECOP II (consulta puntual por número y constancia)
    found2 = {ref_key(r.get("referencia_del_contrato")) for r in secop2}
    pending = [c for c in contracts if c["id"] not in found2]
    secop1 = []
    for c in pending:
        conds = [f"numero_de_contrato='{c['id']}'"]
        if constancia_from(c.get("secop")):
            conds.append(f"numero_de_constancia='{constancia_from(c['secop'])}'")
        secop1 += fetch(SECOP1, {
            "$select": "numero_de_constancia,numero_de_contrato,nom_razon_social_contratista",
            "$where": f"nit_de_la_entidad='{NIT_ESAP}' AND ({' OR '.join(conds)})", "$limit": 20})
    links = match(contracts, secop2, secop1)
    missing = [c["id"] for c in contracts if not links.get(c["id"], {}).get("verificado")]
    OUT.write_text(json.dumps({
        "fuente": "datos.gov.co — SECOP II Contratos Electrónicos (jbjy-vk9h) y SECOP I Procesos (f789-7hwg)",
        "generado": datetime.now().isoformat(timespec="seconds"),
        "sin_verificar": missing,
        "contratos": links,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    changed = [c["id"] for c in contracts if c["id"] in links and links[c["id"]]["url"] != c.get("secop")]
    print(f"{len(links)}/{len(contracts)} contratos con enlace ({len(links) - len(missing)} verificados) → {OUT.relative_to(ROOT)}")
    print(f"Distintos del Excel ({len(changed)}): {', '.join(changed)}")
    print(f"Sin verificar ({len(missing)}): {', '.join(missing) or 'ninguno'}")
    review = [k for k, v in links.items() if v["contratista_coincide"] is False]
    print(f"Contratista por revisar ({len(review)}): {', '.join(review) or 'ninguno'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
