#!/usr/bin/env bash
# Comandos de manutenção dos módulos no contêiner único. Durante a primeira
# transição, os mesmos roteiros ainda operam a topologia anterior.

aplicacao_ativa() {
  [ -f "${PLATAFORMA_DIR:-/opt/plataforma}/publicacoes/aplicacao.json" ]
}

comando_servico() {
  local servico="$1"
  shift
  if aplicacao_ativa; then
    docker compose exec -T aplicacao python -m config.comando "$servico" "$@"
  else
    docker compose exec -T "$servico" python manage.py "$@"
  fi
}

env_servico() {
  local servico="$1" chave="$2"
  if aplicacao_ativa; then
    docker compose exec -T aplicacao python -m config.comando "$servico" env "$chave"
  else
    docker compose exec -T "$servico" printenv "$chave"
  fi
}

servicos_rodando() {
  local rodando
  rodando="$(docker compose ps --status running --services)" || return
  if ! aplicacao_ativa; then
    printf '%s\n' "$rodando"
    return
  fi
  if printf '%s\n' "$rodando" | grep -qx aplicacao; then
    printf '%s\n' admin alunos catalogo checkout cursos encomendas forum funil \
      gamificacao identidade leads mensageria metricas notificacoes pagamentos \
      pages quiz sugestoes aplicacao
  fi
}

# Forma: comando_servico_env SERVICO CHAVE=valor [...] -- COMANDO [args...]
comando_servico_env() {
  local servico="$1" item
  local -a ambientes=() chaves=()
  shift
  while [ "$#" -gt 0 ] && [ "$1" != -- ]; do
    item="$1"
    ambientes+=(-e "$item")
    chaves+=(--env "${item%%=*}")
    shift
  done
  [ "${1:-}" = -- ] || return 2
  shift
  if aplicacao_ativa; then
    docker compose exec -T "${ambientes[@]}" aplicacao python -m config.comando \
      "${chaves[@]}" "$servico" "$@"
  else
    docker compose exec -T "${ambientes[@]}" "$servico" python manage.py "$@"
  fi
}
