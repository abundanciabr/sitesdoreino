#!/usr/bin/env bash
# =============================================================================
# LIGAR A ESCADA DE DEGRAUS DA ESCOLA — para a página de conquistas deixar de
# dizer "a sua escada está sendo montada".
#
# POR QUE ELE EXISTE
# ------------------
# Em 01/09/2026 o mantenedor abriu `/conquistas` e leu três frases se
# contradizendo: "Nível 1", "você chegou ao último degrau desta escada" e "0 de
# experiência até aqui". O defeito da TELA foi corrigido nos PRs #838 e #840
# (`armadilhas/271`); a tela passou a dizer a verdade, e a verdade é que a
# escola ainda não ligou degrau nenhum.
#
# Ligar é decisão dele (lei §10.5), e ele a tomou. Só que `/admin/economia/` tem
# botão para REGRAS e para CONQUISTAS, e nenhum para DEGRAUS. Este script é a
# primeira metade da decisão dele: ligar agora, pelo pipeline. A segunda metade
# é o interruptor na tela, que vem em seguida — e é lá que desligar vai morar,
# porque gesto reversível pertence a uma tela, não a um disparo de agente.
#
# COMO RODA (normalmente NÃO é o mantenedor quem roda):
#   pelo pipeline, `.github/workflows/ligar-os-degraus.yml`, disparado à mão.
#   Nenhum terminal envolvido.
#
# E SE PRECISAR RODAR À MÃO, dentro da VPS (uma linha só, sem argumentos):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/ligar-os-degraus.sh -o /tmp/l.sh && bash /tmp/l.sh
#
#   O prompt tem de estar como `deploy@srv…` ou `root@srv…`. Se começar com
#   `PS C:\>`, você está no PC e este script não é para lá.
#
# O SITE SAI DE DENTRO DO CONTÊINER, pela mesma razão de `semear-economia.sh`:
# ligar degraus de um site que a tela não consulta seria a pior das falhas, a
# que responde 200 e não muda nada na tela de ninguém.
#
# O QUE ELE NÃO FAZ, e isto é a parte importante
# ----------------------------------------------
# Não liga regra de pontuação, missão, conquista, liga nem cosmético. Degrau não
# paga nada: é a régua com que o XP é lido. Quanto a escola PAGA continua sendo
# decisão de uma tela, uma regra de cada vez, com data e aviso. O comando Python
# tem teste afirmando exatamente isso, e este script CONFERE de fora depois de
# rodar.
#
# SEGURO DE RODAR DUAS VEZES: o comando é idempotente (a segunda vez liga zero e
# diz isso). NÃO escreve segredo, não toca env, não reinicia serviço, não faz
# deploy.
# =============================================================================
set -u

parar() { echo; echo "PAROU POR SEGURANÇA: $1"; echo "NADA foi alterado."; exit 1; }

cd /opt/plataforma 2>/dev/null || parar "não achei /opt/plataforma — você está na VPS certa? (o prompt precisa começar com deploy@srv… ou root@srv…, nunca PS C:\>)"
[ -f docker-compose.yml ] || parar "não achei docker-compose.yml em /opt/plataforma."
docker compose ps >/dev/null 2>&1 || parar "não consegui falar com o Docker Compose aqui."

echo "== 1/4 — conferindo se a gamificação está de pé =="
ESTADO=$(docker compose ps --status running --services 2>/dev/null | grep -Fx "gamificacao" || true)
[ -n "$ESTADO" ] || parar "o serviço 'gamificacao' não está rodando. Sem ele não há escada a ligar."
echo "  gamificacao ...... de pé"

echo
echo "== 2/4 — descobrindo de qual escola é a escada =="
SITE=$(docker compose exec -T gamificacao printenv SITE_ID 2>/dev/null | tr -d '\r[:space:]')
[ -n "$SITE" ] || parar "o contêiner da gamificação não declara SITE_ID. Sem ele eu ligaria uma escada que a tela nunca consulta — e isso não dá erro em lugar nenhum, que é o pior desfecho."
echo "  site lido do contêiner ...... ${SITE}"

echo
echo "== 3/4 — ligando SÓ os degraus =="
SAIDA=$(docker compose exec -T gamificacao python manage.py ligar_degraus --site "$SITE" 2>&1) \
  || { echo "$SAIDA"; parar "o comando ligar_degraus recusou. A saída acima diz por quê."; }
echo "$SAIDA"

# A PROVA, e não o eco (`armadilhas/114`): esta frase vem do PYTHON, do fim do
# caminho feliz dele, e não aparece no corpo deste script em lugar nenhum.
printf '%s' "$SAIDA" | grep -q 'ESCADA DE DEGRAUS LIGADA OK' \
  || parar "o comando rodou mas não imprimiu a linha de conclusão — não posso afirmar que ligou."

echo
echo "== 4/4 — conferindo do lado de fora do comando =="
# Conta de novo, por outro caminho, em vez de acreditar no que o comando disse
# ter feito. E conta PELO SITE, que é como a tela do aluno pergunta.
LIGADOS=$(docker compose exec -T gamificacao python manage.py shell -c \
  "from apps.gamificacao.models import NivelDefinicao as N; print(N.objects.filter(site_id='$SITE', ativa=True).count())" 2>/dev/null | tr -d '\r[:space:]')
case "$LIGADOS" in
  ''|*[!0-9]*) parar "não consegui contar os degraus ligados depois de ligar." ;;
esac
# DOIS é o mínimo que faz uma escada: com um só, a tela do aluno diz que o
# degrau seguinte ainda não abriu (`armadilhas/271`).
[ "$LIGADOS" -ge 2 ] || parar "esperava pelo menos 2 degraus ligados neste site e contei $LIGADOS."
echo "  degraus ligados ................... $LIGADOS"

# E a conferência que o mantenedor mais precisa: a escada subiu, o PAGAMENTO
# não. Se este número mudar sozinho um dia, é sinal de que alguém ampliou o
# comando para ligar economia — que é decisão de tela, nunca de disparo.
REGRAS=$(docker compose exec -T gamificacao python manage.py shell -c \
  "from apps.gamificacao.models import RegraDePontuacao as R; print(R.objects.filter(site_id='$SITE', ativa=True).count())" 2>/dev/null | tr -d '\r[:space:]')
case "$REGRAS" in
  ''|*[!0-9]*) parar "não consegui conferir quantas regras de pontuação estão ligadas." ;;
esac
echo "  regras de pontuação ligadas ....... $REGRAS"

echo
echo "PRONTO: a escada da escola esta de pe."
if [ "$REGRAS" = "0" ]; then
  echo "Nenhuma regra de pontuacao esta ligada, entao o aluno ve o degrau dele e a"
  echo "barra, mas ninguem sobe ainda: ligar a primeira regra e uma decisao sua, em"
  echo "https://meshcraft.top/admin/economia/"
else
  echo "$REGRAS regra(s) de pontuacao ja estao ligadas: o XP mexe, e agora tem escada"
  echo "para mostrar o que ele significa."
fi
