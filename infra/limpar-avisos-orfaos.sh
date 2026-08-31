#!/usr/bin/env bash
# =============================================================================
# LIMPAR OS AVISOS ÓRFÃOS — apaga da caixa central os recados sobre ideias que
# foram apagadas definitivamente da Caixa de Sugestões.
#
# POR QUE ESTE SCRIPT EXISTE
# --------------------------
# Em 31/08/2026, depois de esvaziar a Caixa, o mantenedor continuou vendo no
# perfil dele o aviso sobre uma das ideias apagadas: um cartão SEM TÍTULO
# (porque apagar esvazia o título) com a justificativa da equipe ainda legível
# ao lado, e um link para uma ideia que ninguém mais alcança. A pergunta dele
# foi a certa: *"verifique se outros usuários também têm e apague-os"*.
#
# POR QUE PRECISA DE DUAS CÉLULAS
# --------------------------------
# Quem sabe QUAIS ideias foram apagadas é a `sugestoes`. Quem guarda os recados
# de toda a plataforma é a `notificacoes`. Nenhuma alcança o banco da outra
# (Lei 3), e o contrato entre elas não tem operação de retirada — mudar isso é
# um Rito. Então este script faz o papel de carteiro: pergunta a lista de um
# lado, entrega do outro.
#
# ELE PERGUNTA ANTES DE APAGAR
# -----------------------------
# O passo 4 roda em SIMULAÇÃO e imprime quantas cartas existem e quantas
# PESSOAS têm alguma. É a resposta à pergunta do mantenedor, e ela sai antes de
# qualquer linha ser tocada. Só depois vem o passo que apaga.
#
# COMO O MANTENEDOR RODA (DENTRO da VPS — prompt `deploy@srv…` ou `root@srv…`):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/limpar-avisos-orfaos.sh -o /tmp/o.sh && bash /tmp/o.sh
#
# Se o seu prompt começa com `PS C:\>`, você está no PC e este script não é
# para lá. O caminho normal é o workflow
# `.github/workflows/limpar-avisos-orfaos.yml`, sem terminal nenhum.
#
# NÃO escreve segredo, não toca env, não reinicia serviço, não faz deploy.
# =============================================================================
set -u

parar() { echo; echo "PAROU POR SEGURANÇA: $1"; echo "NADA foi apagado."; exit 1; }

ASSUNTO="sugestao.status-alterado"

cd /opt/plataforma 2>/dev/null || parar "não achei /opt/plataforma — você está na VPS certa? (o prompt precisa começar com deploy@srv… ou root@srv…, nunca PS C:\\>)"
[ -f docker-compose.yml ] || parar "não achei docker-compose.yml em /opt/plataforma."
docker compose ps >/dev/null 2>&1 || parar "não consegui falar com o Docker Compose aqui."

echo "== 1/5 — conferindo se as duas peças estão de pé =="
for SERVICO in sugestoes notificacoes; do
  ESTADO=$(docker compose ps --status running --services 2>/dev/null | grep -Fx "$SERVICO" || true)
  [ -n "$ESTADO" ] || parar "o serviço '$SERVICO' não está rodando. Suba a plataforma antes (docker compose up -d) e rode de novo."
  echo "  $SERVICO ...... de pé"
done

echo
echo "== 2/5 — conferindo se a imagem já conhece o comando =="
# Fail-closed contra a ORDEM ERRADA: rodar isto antes do deploy faria o
# `manage.py` responder "Unknown command" em inglês cru, sem dizer que a
# resposta certa é "espere o deploy".
SABE=$(docker compose exec -T notificacoes python manage.py shell -c \
  "from django.core.management import get_commands; print('retirar_cartas' in get_commands())" 2>&1 | tr -d '\r[:space:]')
case "$SABE" in
  True) echo "  comando retirar_cartas ...... disponível" ;;
  False) parar "esta imagem da notificacoes ainda não conhece o comando 'retirar_cartas'. Espere o deploy da célula 'notificacoes' ficar verde e rode de novo." ;;
  *) echo "$SABE"; parar "não consegui perguntar à notificacoes se ela conhece o comando." ;;
esac

echo
echo "== 3/5 — perguntando à Caixa quais ideias foram apagadas =="
IDS=$(docker compose exec -T sugestoes python manage.py shell -c \
  "from apps.sugestoes.models import Sugestao
print(','.join(str(i) for i in Sugestao.objects.filter(apagada_em__isnull=False).values_list('id', flat=True)))" \
  2>/dev/null | tr -d '\r[:space:]')

if [ -z "$IDS" ]; then
  echo "  nenhuma ideia apagada na Caixa."
  echo
  echo "PRONTO. Não há aviso órfão possível: nenhuma ideia foi apagada."
  exit 0
fi

# Fail-closed contra resposta estranha: se o `shell` devolver texto em vez de
# números, o filtro do outro lado não casaria com nada e a limpeza terminaria
# "com sucesso" sem ter feito nada. Silêncio não é sucesso (INV-CI01).
case "$IDS" in
  *[!0-9,]*) echo "$IDS"; parar "a Caixa respondeu algo que não é uma lista de números." ;;
esac

QUANTAS_IDEIAS=$(printf '%s' "$IDS" | tr ',' '\n' | grep -c .)
echo "  ideias apagadas ...... $QUANTAS_IDEIAS"

echo
echo "== 4/5 — quem tem aviso dessas ideias (SIMULAÇÃO, nada é apagado) =="
ANTES=$(docker compose exec -T notificacoes python manage.py retirar_cartas \
  --assunto "$ASSUNTO" --parametro suggestion_id --valores "$IDS" --simular 2>&1 | tr -d '\r') \
  || { echo "$ANTES"; parar "não consegui simular a retirada."; }
echo "$ANTES"

printf '%s' "$ANTES" | grep -q 'SIMULACAO' \
  || parar "a simulação não imprimiu a linha de conclusão — não posso afirmar que ela rodou."

QUANTAS=$(printf '%s' "$ANTES" | sed -n 's/^ *cartas na caixa \.*  *\([0-9]*\)$/\1/p' | head -n1)
[ -n "$QUANTAS" ] || parar "não consegui ler quantas cartas a simulação encontrou."

if [ "$QUANTAS" -eq 0 ]; then
  echo
  echo "PRONTO. Nenhum aviso órfão na caixa central: ninguém tem recado de ideia apagada."
  exit 0
fi

echo
echo "== 5/5 — apagando =="
SAIDA=$(docker compose exec -T notificacoes python manage.py retirar_cartas \
  --assunto "$ASSUNTO" --parametro suggestion_id --valores "$IDS" --confirmo 2>&1 | tr -d '\r') \
  || { echo "$SAIDA"; parar "o comando falhou. A tela acima diz por quê — mande-a ao agente."; }
echo "$SAIDA"

printf '%s' "$SAIDA" | grep -q 'RETIRADA OK' \
  || parar "o comando rodou mas não imprimiu a linha de conclusão — não posso afirmar que apagou."

# A PROVA, por FORA do comando que apagou: pergunta de novo, do zero.
DEPOIS=$(docker compose exec -T notificacoes python manage.py retirar_cartas \
  --assunto "$ASSUNTO" --parametro suggestion_id --valores "$IDS" --simular 2>&1 | tr -d '\r')
RESTAM=$(printf '%s' "$DEPOIS" | sed -n 's/^ *cartas na caixa \.*  *\([0-9]*\)$/\1/p' | head -n1)

echo
echo "== conferência de fora =="
echo "  cartas órfãs restantes ...... ${RESTAM:-?}"

if [ "${RESTAM:-1}" -ne 0 ]; then
  echo "ATENÇÃO: ainda restam ${RESTAM:-?} carta(s) órfã(s)."
  echo "Mande esta tela ao agente."
  exit 1
fi

echo
echo "PRONTO. Os avisos de ideias apagadas sumiram da caixa central: $QUANTAS carta(s) retirada(s)."
echo "O sininho e a tela de avisos voltam a contar a mesma história."
