#!/usr/bin/env bash
# Publica Liquidaciones_ESAP como espejo en GitHub (Rprimero93/liquidaciones-esap) desde el repo de la bóveda.
# La bóveda sigue siendo la fuente de verdad; este script solo genera y empuja la copia (patrón de Menu_Dial).
#   1. git subtree split: historia de la carpeta del proyecto.
#   2. En una carpeta temporal: correo de autor/committer → noreply de GitHub y fuera las cachés de Python.
#   3. Control de privacidad: aborta si la copia lleva el correo corporativo o un archivo de Excel.
#   4. Push a main (pide autorizar con la cuenta Rprimero93 la primera vez).
# Los datos reales (seed.json, secop.json) SÍ se publican: decisión de Ricardo del 2026-11-23 (06, Fase 7).
# Uso (desde cualquier carpeta):  bash scripts/publicar_github.sh [--dry-run]
set -euo pipefail

PREFIX="Entregables/Web/Liquidaciones_ESAP"
REMOTE="https://Rprimero93@github.com/Rprimero93/liquidaciones-esap.git"
EMAIL="Rprimero93@users.noreply.github.com"
BRANCH="tmp-liquidaciones-esap-publish"
DRY_RUN="${1:-}"

VAULT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"; git -C "$VAULT" branch -D "$BRANCH" >/dev/null 2>&1 || true' EXIT

# git subtree comprueba la ruta del prefijo contra la carpeta actual: se corre desde la raíz
(cd "$VAULT" && git subtree split --prefix="$PREFIX" -b "$BRANCH" >/dev/null)
git clone -q --branch "$BRANCH" --single-branch "$VAULT" "$WORK/repo"
cd "$WORK/repo"
git checkout -q -b main

export FILTER_BRANCH_SQUELCH_WARNING=1
git filter-branch -f \
  --env-filter "export GIT_AUTHOR_EMAIL='$EMAIL'; export GIT_COMMITTER_EMAIL='$EMAIL'" \
  --index-filter 'git rm -r -q --cached --ignore-unmatch scripts/__pycache__ pruebas/__pycache__' \
  -- main >/dev/null
rm -rf .git/refs/original  # respaldo de filter-branch: no se publica

# Control de privacidad, sobre todo el historial que se publica (no solo la última versión)
if git log --all --format='%ae%n%ce' | grep -qv "^$EMAIL$"; then
  echo "Control de privacidad: FALLA, queda un correo distinto del noreply en los commits"; exit 1
fi
if git log --all -p | grep -qi 'loscoches\.com\.co'; then
  echo "Control de privacidad: FALLA, el correo corporativo aparece en el contenido publicado"; exit 1
fi
if git log --all --name-only --format= | grep -qiE '\.(xlsx|xlsm|xls)$'; then
  echo "Control de privacidad: FALLA, la copia lleva un archivo de Excel"; exit 1
fi
echo "Control de privacidad: OK (solo correo noreply, sin correo corporativo ni Excel)"

echo "Commits a publicar: $(git rev-list --count main) · último: $(git log -1 --format='%h %s')"
if [ "$DRY_RUN" = "--dry-run" ]; then
  echo "Remoto actual:     $(git ls-remote "$REMOTE" refs/heads/main 2>/dev/null | cut -c1-7 || echo 'sin acceso o vacío')"
  echo "(ensayo: no se empujó nada)"
else
  git push "$REMOTE" main:main
fi
