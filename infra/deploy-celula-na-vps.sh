#!/usr/bin/env bash
# Publica a aplicação: backup de todas as bases, troca de versão e prova da página inicial.
# IMAGEM e CODIGO vêm do publicador da VPS (base local + código montado).

set -eu

if (set -o pipefail) 2>/dev/null; then set -o pipefail; fi

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
cd "$RAIZ"
PUBLICACAO_LOCAL="${PUBLICACAO_LOCAL:-$RAIZ/publicacao-local.py}"

export CELULA=aplicacao
SERVICOS=aplicacao

python3 "$PUBLICACAO_LOCAL" preparar
trap 'CODIGO=$?; if [ "$CODIGO" -ne 0 ]; then python3 "$PUBLICACAO_LOCAL" abortar || true; fi; exit "$CODIGO"' EXIT
if [ -f "$RAIZ/publicacoes/imagens.json" ]; then
  export COMPOSE_FILE="$RAIZ/docker-compose.yml:$RAIZ/publicacoes/imagens.json"
fi

parar_o_deploy() {
  echo
  echo "PAROU POR SEGURANÇA: $1"
  echo
  echo "O QUE ESTA NO AR AGORA: nada mudou. A imagem nova NAO subiu e nenhuma"
  echo "migracao rodou, porque este passo vem antes de tudo isso. E por isso que"
  echo "ele para em vez de seguir. O site continua servindo a versao anterior."
  echo "O QUE FAZER: conserte o que a linha acima aponta e publique de novo."
  echo "Sem copia de seguranca do banco, esta casa nao migra."
  exit 1
}

# Cópia de segurança de todas as bases antes de qualquer migração. Ver infra/backup-do-banco.sh.
unset BASES
PRESERVAR_COPIAS=1 bash "$(dirname "$0")/backup-do-banco.sh" "${TAG:0:12}-$$" \
  || parar_o_deploy "a cópia de segurança do banco não saiu (motivo nas linhas acima)."
echo "BACKUP-ANTES-DA-MIGRACAO: o caminho de volta é infra/restaurar-backup.sh (guia em infra/COMO-RESTAURAR.md)"
python3 "$PUBLICACAO_LOCAL" backup-concluido

# --wait reprova se o contêiner não ficar de pé e saudável em 180 s.
python3 "$PUBLICACAO_LOCAL" aplicar
export COMPOSE_FILE="$RAIZ/docker-compose.yml:$RAIZ/publicacoes/imagens.json"
python3 "$PUBLICACAO_LOCAL" conferir-ultima
echo "CANDIDATA-APLICADA: $TAG"
docker compose up -d --wait --wait-timeout 180 $SERVICOS
python3 "$PUBLICACAO_LOCAL" servico-iniciado
docker compose ps $SERVICOS

python3 "$PUBLICACAO_LOCAL" aprovar
echo "ENTREGA-CONCLUIDA: $CELULA"
