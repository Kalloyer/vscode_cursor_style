#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "==> Criando ambiente virtual Python local (.venv)"
python -m venv .venv

if [[ -f ".venv/bin/activate" ]]; then
  # Linux/macOS
  # shellcheck disable=SC1091
  source .venv/bin/activate
elif [[ -f ".venv/Scripts/activate" ]]; then
  # Git Bash no Windows
  # shellcheck disable=SC1091
  source .venv/Scripts/activate
fi

echo "==> Ambiente virtual pronto. Sem dependencias Python obrigatorias no momento."
echo "==> Instalando dependencias Node locais (inclui @vscode/vsce como devDependency)"
npm install

echo "==> Executando validacoes iniciais"
npm run build
echo "==> Convertendo tema a partir do exemplo"
npm run convert-theme -- --settings examples/settings.sample.json
echo "==> Gerando pacote VSIX"
npm run package

cat <<'EOF'

Proximos passos:
1. Edite "publisher" em package.json com seu publisher real do Marketplace.
2. Rode conversao com seu settings.json:
   npm run convert-theme -- --settings /caminho/para/settings.json
3. Teste o tema no VS Code (F5) e gere novo VSIX quando quiser.
4. Publique com:
   npm run publish:patch

EOF
