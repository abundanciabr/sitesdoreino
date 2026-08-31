#!/usr/bin/env bash
# =============================================================================
# SEMEAR A ECONOMIA DA ESCOLA — para a tela de ligar os pontos deixar de nascer
# vazia.
#
# POR QUE ELE EXISTE
# ------------------
# A tela `/admin/economia/` subiu em 31/08/2026 e abriu SEM NENHUMA LINHA. Não
# era defeito dela: as tabelas da economia existem (as migrações rodaram), mas
# as LINHAS nunca foram criadas em produção — `semear_economia` é um comando de
# gerência, e comando de gerência não roda no deploy. O que a memória do projeto
# chamava de "tudo semeado" era verdade no banco de TESTE.
#
# É o mesmo caso do fórum em 30/08 (`semear-areas-do-forum.sh`), que nasceu
# dizendo "ainda não há nenhuma área" pela mesma razão. Semear é CONTEÚDO, não
# esquema: por isso NÃO vira migração de dados — lá aquilo quebrou 20 testes,
# porque migração de dados entra no banco de todo teste.
#
# COMO RODA (normalmente NÃO é o mantenedor quem roda):
#   pelo pipeline, `.github/workflows/semear-economia.yml`, disparado à mão pelo
#   agente ou pelo mantenedor. Nenhum terminal envolvido.
#
# E SE PRECISAR RODAR À MÃO, dentro da VPS (uma linha só, sem argumentos):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/semear-economia.sh -o /tmp/s.sh && bash /tmp/s.sh
#
#   O prompt tem de estar como `deploy@srv…` ou `root@srv…`. Se começar com
#   `PS C:\>`, você está no PC e este script não é para lá.
#
# O SITE SAI DE DENTRO DO CONTÊINER, e essa é a decisão que faz o script valer.
# `semear_economia --site` é obrigatório, e o valor tem de ser EXATAMENTE o
# mesmo que a tela consulta — ela lê `SITE_ID` do env da célula
# (`apps/core/sessao.py::site_atual`). Passar um valor escolhido aqui criaria
# linhas que existem no banco e não aparecem para ninguém: a pior das falhas,
# porque tudo responde 200 e a tela continua vazia. Lendo do próprio contêiner,
# os dois lados não têm como divergir.
#
# SEGURO DE RODAR DUAS VEZES: `semear_economia` é idempotente por construção
# (`get_or_create` pelo par site+slug, e SEM atualizar o que já existe). Rodar de
# novo não duplica regra e NÃO DESLIGA o que o mantenedor tiver ligado — a
# edição dele fica de pé.
#
# NÃO escreve segredo, não toca env, não reinicia serviço, não faz deploy. A
# única escrita são as linhas da economia no banco da própria gamificação, e
# todas nascem DESLIGADAS.
# =============================================================================
set -u

parar() { echo; echo "PAROU POR SEGURANÇA: $1"; echo "NADA foi alterado."; exit 1; }

cd /opt/plataforma 2>/dev/null || parar "não achei /opt/plataforma — você está na VPS certa? (o prompt precisa começar com deploy@srv… ou root@srv…, nunca PS C:\>)"
[ -f docker-compose.yml ] || parar "não achei docker-compose.yml em /opt/plataforma."
docker compose ps >/dev/null 2>&1 || parar "não consegui falar com o Docker Compose aqui."

echo "== 1/4 — conferindo se a gamificação está de pé =="
ESTADO=$(docker compose ps --status running --services 2>/dev/null | grep -Fx "gamificacao" || true)
[ -n "$ESTADO" ] || parar "o serviço 'gamificacao' não está rodando. Sem ele não há banco a semear."
echo "  gamificacao ...... de pé"

echo
echo "== 2/4 — descobrindo de qual escola são as linhas =="
# `-T` porque não há terminal do outro lado (o pipeline não aloca TTY).
SITE=$(docker compose exec -T gamificacao printenv SITE_ID 2>/dev/null | tr -d '\r[:space:]')
[ -n "$SITE" ] || parar "o contêiner da gamificação não declara SITE_ID. Sem ele eu criaria linhas que a tela nunca acha — e isso não dá erro em lugar nenhum, que é justamente o pior desfecho."
echo "  site lido do contêiner ...... ${SITE}"

echo
echo "== 3/4 — semeando (tudo nasce DESLIGADO) =="
SAIDA=$(docker compose exec -T gamificacao python manage.py semear_economia --site "$SITE" 2>&1) \
  || { echo "$SAIDA"; parar "o comando semear_economia falhou. A saída acima diz por quê."; }
echo "$SAIDA"

# A PROVA, e não o eco. `armadilhas/114`: o log da ssh-action ecoa o script
# inteiro, então a frase que comprova execução não pode ser uma que também
# apareça aqui no corpo. Esta vem do PYTHON, do fim do caminho feliz dele.
printf '%s' "$SAIDA" | grep -q 'SEMEADURA DA ECONOMIA OK' \
  || parar "o comando rodou mas não imprimiu a linha de conclusão — não posso afirmar que semeou."

echo
echo "== 4/4 — conferindo do lado de fora do comando =="
# Conta de novo, por outro caminho, em vez de confiar no que o próprio comando
# disse ter feito. E conta PELO SITE, que é como a tela pergunta: contagem certa
# no site errado seria verde provando nada.
QUANTAS=$(docker compose exec -T gamificacao python manage.py shell -c \
  "from apps.gamificacao.models import RegraDePontuacao as R; print(R.objects.filter(site_id='$SITE').count())" 2>/dev/null | tr -d '\r[:space:]')
case "$QUANTAS" in
  ''|*[!0-9]*) parar "não consegui contar as regras depois de semear." ;;
esac
[ "$QUANTAS" -ge 6 ] || parar "esperava ao menos 6 regras de pontuação neste site e contei $QUANTAS."
echo "  regras de pontuação no banco ...... $QUANTAS"

# E a conferência que o mantenedor mais precisa: nenhuma ligada sozinha. Ligar é
# decisão DELE, com data e aviso (lei §10.5) — semear que ligasse alguma seria
# uma mudança de economia que ninguém decidiu.
LIGADAS=$(docker compose exec -T gamificacao python manage.py shell -c \
  "from apps.gamificacao.models import RegraDePontuacao as R; print(R.objects.filter(site_id='$SITE', ativa=True).count())" 2>/dev/null | tr -d '\r[:space:]')
case "$LIGADAS" in
  ''|*[!0-9]*) parar "não consegui conferir quantas regras estão ligadas." ;;
esac
echo "  dessas, ligadas ................... $LIGADAS"

echo
echo "PRONTO: a economia da escola existe."
if [ "$LIGADAS" = "0" ]; then
  echo "Nenhuma regra está ligada, que é como elas nascem: ligar a primeira é uma"
  echo "decisão sua, em https://meshcraft.top/admin/economia/"
else
  echo "ATENCAO: $LIGADAS regra(s) ja estavam LIGADAS neste site antes desta"
  echo "semeadura. Elas continuam como estavam — semear nao desliga nada."
fi
