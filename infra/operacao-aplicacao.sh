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

# Código Python pelo stdin, com os imports originais do módulo reescritos no
# runtime único. Aceita o '-' opcional usado por `python -` nos roteiros antigos.
codigo_servico() {
  local servico="$1"
  shift
  if [ "${1:-}" = - ]; then shift; fi
  [ "$#" -eq 0 ] || return 2
  if aplicacao_ativa; then
    docker compose exec -T aplicacao python -m config.executar "$servico" -
  else
    docker compose exec -T "$servico" python -
  fi
}

# Recria somente a aplicação vigente, ou os serviços correspondentes à origem
# depois de uma recuperação. O helper Python sempre prova as rotas públicas.
#
# Recriar contêiner à mão enquanto o publicador troca a aplicação derruba o site:
# em 04/10/2026 um provisionamento coincidiu com uma publicação e deu conflito
# de nome de contêiner (~2 min fora do ar). Por isso este passo pega a MESMA
# trava do publicador (infra/publicar.py, LOTES / ".lote.lock") e espera a
# publicação acabar antes de mexer. Sem `flock` na máquina (só a VPS importa),
# segue sem trava, como o publicador faz sem `fcntl`.
recarregar_servicos() {
  [ "$#" -eq 1 ] || return 2
  local origem="$1"
  case "$origem" in *.sh) ;; *) origem="$origem.sh" ;; esac
  local aqui trava
  aqui="$(dirname "${BASH_SOURCE[0]}")"
  trava="${PLATAFORMA_DIR:-/opt/plataforma}/publicacoes/lotes/.lote.lock"
  if ! command -v flock >/dev/null 2>&1; then
    python3 "$aqui/recarregar-aplicacao.py" "$origem"
    return
  fi
  mkdir -p "$(dirname "$trava")" || return
  (
    if ! flock -n 9; then
      echo "Há uma publicação em andamento; espero ela terminar antes de recarregar a aplicação..."
      flock 9
    fi
    python3 "$aqui/recarregar-aplicacao.py" "$origem"
  ) 9>>"$trava"
}
