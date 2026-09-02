#!/usr/bin/env bash
# =============================================================================
# CONFERIR AS FICHAS DOS ALUNOS contra o histórico de pontos — e, se pedirem,
# acertar as que estiverem fora do lugar.
#
# POR QUE ELE EXISTE
# ------------------
# `PerfilJogador.xp_total` e `.nivel` são cópias desnormalizadas do razão de XP.
# Toda cópia é uma promessa, e promessa sem mecanismo apodrece: `reconciliar_
# perfis` é o mecanismo, e até 02/09/2026 não havia como rodá-lo em produção sem
# alguém entrar na VPS à mão.
#
# O DIA QUE PEDIU ISTO: 02/09/2026, o dia em que a escada de degraus foi ligada
# (`ligar-os-degraus.yml`). Antes dela, `nivel_para` devolvia 1 para todo mundo,
# porque não havia degrau ativo nenhum; depois, quem já tinha XP passou a estar
# num degrau que até então não existia. A cópia não atrasou: a régua nasceu
# depois da altura.
#
# COMO RODA: pelo pipeline, `.github/workflows/conferir-as-fichas.yml`. Dois
# botões, e o padrão é o seguro:
#
#   CONSERTAR=nao  (padrão) → só OLHA e conta. Não escreve nada.
#   CONSERTAR=sim           → reescreve as fichas divergentes.
#   AVISAR=sim              → e manda a carta de nível a quem subiu. Só faz
#                             sentido junto de CONSERTAR=sim, e o comando
#                             recusa a combinação sem sentido.
#
# E SE PRECISAR RODAR À MÃO, dentro da VPS (uma linha só):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/conferir-as-fichas.sh -o /tmp/c.sh && CONSERTAR=nao bash /tmp/c.sh
#
#   O prompt tem de estar como `deploy@srv…` ou `root@srv…`. Se começar com
#   `PS C:\>`, você está no PC e este script não é para lá.
#
# NÃO escreve segredo, não toca env, não reinicia serviço, não faz deploy. Com
# CONSERTAR=nao ele não escreve NADA em lugar nenhum.
# =============================================================================
set -u

parar() { echo; echo "PAROU POR SEGURANÇA: $1"; echo "NADA foi alterado."; exit 1; }

CONSERTAR="${CONSERTAR:-nao}"
AVISAR="${AVISAR:-nao}"

case "$CONSERTAR" in sim|nao) ;; *) parar "CONSERTAR precisa ser 'sim' ou 'nao', e veio '$CONSERTAR'." ;; esac
case "$AVISAR" in sim|nao) ;; *) parar "AVISAR precisa ser 'sim' ou 'nao', e veio '$AVISAR'." ;; esac
if [ "$AVISAR" = "sim" ] && [ "$CONSERTAR" = "nao" ]; then
  parar "AVISAR=sim sem CONSERTAR=sim não avisaria ninguém: sem consertar, nenhuma ficha muda."
fi

cd /opt/plataforma 2>/dev/null || parar "não achei /opt/plataforma — você está na VPS certa? (o prompt precisa começar com deploy@srv… ou root@srv…, nunca PS C:\>)"
[ -f docker-compose.yml ] || parar "não achei docker-compose.yml em /opt/plataforma."
docker compose ps >/dev/null 2>&1 || parar "não consegui falar com o Docker Compose aqui."

echo "== 1/3 — conferindo se a gamificação está de pé =="
ESTADO=$(docker compose ps --status running --services 2>/dev/null | grep -Fx "gamificacao" || true)
[ -n "$ESTADO" ] || parar "o serviço 'gamificacao' não está rodando. Sem ele não há ficha a conferir."
echo "  gamificacao ...... de pé"

echo
echo "== 2/3 — o que vai ser feito =="
if [ "$CONSERTAR" = "nao" ]; then
  echo "  modo ...... SÓ OLHAR (nada será escrito)"
  ARGS=""
elif [ "$AVISAR" = "sim" ]; then
  echo "  modo ...... CONSERTAR, e avisar quem subir"
  ARGS="--consertar --avisar"
else
  echo "  modo ...... CONSERTAR, em silêncio (sem carta para ninguém)"
  ARGS="--consertar"
fi

echo
echo "== 3/3 — conferindo as fichas contra o histórico de pontos =="
# `$ARGS` sem aspas de propósito: são duas opções fixas escolhidas acima, nunca
# texto de fora. O conjunto possível é o das três linhas do bloco anterior.
SAIDA=$(docker compose exec -T gamificacao python manage.py reconciliar_perfis $ARGS 2>&1) \
  || { echo "$SAIDA"; parar "o comando reconciliar_perfis recusou. A saída acima diz por quê."; }
echo "$SAIDA"

# A PROVA, e não o eco (`armadilhas/114`). As duas frases abaixo vêm do PYTHON,
# e nenhuma delas aparece no corpo deste script em outro lugar.
if printf '%s' "$SAIDA" | grep -q '^OK: '; then
  echo
  echo "PRONTO: a conferencia das fichas terminou."
  echo "Nenhuma ficha diverge do historico: nao ha nada a acertar."
  exit 0
fi
printf '%s' "$SAIDA" | grep -q 'DIVERGE:' \
  || parar "o comando rodou mas não disse nem 'OK:' nem 'DIVERGE:' — não posso afirmar o que aconteceu."

QUANTAS=$(printf '%s' "$SAIDA" | grep -c 'DIVERGE:' || true)
echo
echo "PRONTO: a conferencia das fichas terminou."
echo "Fichas fora do lugar: $QUANTAS"
if [ "$CONSERTAR" = "nao" ]; then
  echo "NADA foi escrito: este foi o modo de so olhar. Para acertar, rode de novo"
  echo "com CONSERTAR=sim."
else
  printf '%s' "$SAIDA" | grep -q '^consertados: ' \
    || parar "o comando disse que havia divergência mas não confirmou o conserto."
  echo "Elas foram acertadas."
fi
