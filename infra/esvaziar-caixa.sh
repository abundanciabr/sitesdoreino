#!/usr/bin/env bash
# =============================================================================
# ESVAZIAR A CAIXA DE SUGESTÕES — apaga DEFINITIVAMENTE toda ideia que ainda
# tem conteúdo no quadro de um site. Sem volta.
#
# POR QUE ESTE SCRIPT EXISTE
# --------------------------
# Em 31/08/2026, depois de a vitrine de demonstração sair pelo
# `semear-demo-caixa.sh`, sobraram no quadro duas ideias escritas por conta de
# gente de verdade. A retirada da vitrine é cega para elas de propósito: ela só
# acha o que nasceu no domínio `@demo.invalid`. Perguntado se preferia olhá-las
# pelo Admin ou mandar o robô apagar tudo, o mantenedor escolheu o robô.
#
# O QUE "APAGAR" SIGNIFICA AQUI — e não é o que a palavra sugere
# --------------------------------------------------------------
# `DECISAO-apagar-ideia.md` (29/08/2026): a "lousa apagada". Título, problema e
# solução viram vazio; votos e comentários de TODA pessoa que participou somem
# de verdade; e a LINHA da ideia continua no banco, porque o histórico da
# equipe é append-only com trigger no Postgres e aponta para ela. Ninguém
# alcança o conteúdo de novo, nem pelo link direto. Não há restauração.
#
# O comando por dentro chama a MESMA função do botão "Apagar definitivamente"
# do Admin, então este caminho e aquele não podem divergir.
#
# A TRAVA, QUE É A RAZÃO DE O SCRIPT TER DOIS ARGUMENTOS
# -------------------------------------------------------
# O segundo argumento é QUANTAS ideias com conteúdo você espera encontrar. Se a
# realidade não bater exatamente, o comando recusa e nada é apagado.
#
# Sem ela, este seria um botão de destruir a Caixa inteira apontado para o
# futuro: a turma entra em 31/08/2026, e daqui a um mês um disparo distraído
# levaria quarenta ideias de aluno de uma vez. Com ela, o disparo distraído
# encontra quarenta onde esperava duas e para antes de tocar em qualquer linha.
#
# COMO O MANTENEDOR RODA (DENTRO da VPS — prompt `deploy@srv…` ou `root@srv…`):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/esvaziar-caixa.sh -o /tmp/e.sh && bash /tmp/e.sh meshcraft.top 2
#
# Se o seu prompt começa com `PS C:\>`, você está no PC e este script não é
# para lá. O caminho normal, aliás, não é este: é o workflow
# `.github/workflows/esvaziar-caixa.yml`, que roda ESTE arquivo pelo pipeline
# sem ninguém abrir terminal nenhum.
#
# NÃO escreve segredo, não toca env, não reinicia serviço, não faz deploy. A
# única escrita é dentro do banco da própria Caixa.
# =============================================================================
set -u

parar() { echo; echo "PAROU POR SEGURANÇA: $1"; echo "NADA foi apagado."; exit 1; }

# Duas portas para os mesmos dois argumentos, e nenhuma interpola texto de fora
# dentro do script: $1/$2 é a linha de colar do mantenedor; HOST_CAIXA/QUANTAS
# é o pipeline, que os entrega pelo `envs:` da ssh-action — `${{ inputs.* }}`
# dentro de `script:` é injeção de comando na VPS (armadilhas/047).
HOST_PEDIDO="${1:-${HOST_CAIXA:-}}"
QUANTAS_ESPERO="${2:-${QUANTAS:-}}"

[ -n "$HOST_PEDIDO" ] || parar "não disse em qual site. Use, por exemplo: bash /tmp/e.sh meshcraft.top 2"
case "$QUANTAS_ESPERO" in
  '') parar "não disse QUANTAS ideias você espera apagar. É a trava deste script: sem ela, um disparo distraído levaria o quadro inteiro." ;;
  *[!0-9]*) parar "'$QUANTAS_ESPERO' não é um número. O segundo argumento é quantas ideias com conteúdo você espera encontrar." ;;
esac

cd /opt/plataforma 2>/dev/null || parar "não achei /opt/plataforma — você está na VPS certa? (o prompt precisa começar com deploy@srv… ou root@srv…, nunca PS C:\\>)"
[ -f docker-compose.yml ] || parar "não achei docker-compose.yml em /opt/plataforma."
docker compose ps >/dev/null 2>&1 || parar "não consegui falar com o Docker Compose aqui."

echo "== 1/5 — conferindo se as duas peças estão de pé =="
for SERVICO in catalogo sugestoes; do
  ESTADO=$(docker compose ps --status running --services 2>/dev/null | grep -Fx "$SERVICO" || true)
  [ -n "$ESTADO" ] || parar "o serviço '$SERVICO' não está rodando. Suba a plataforma antes (docker compose up -d) e rode de novo."
  echo "  $SERVICO ...... de pé"
done

echo
echo "== 2/5 — conferindo se a imagem já conhece o comando =="
# Fail-closed contra a ORDEM ERRADA, na forma do `semear-duvidas-do-forum.sh`:
# se este script rodar antes de o deploy da célula subir a imagem nova, o
# `manage.py` responde "Unknown command" em inglês cru, e quem estiver lendo não
# tem como saber que a resposta é "espere o deploy". A recusa daqui diz isso em
# português, e diz antes de qualquer conta ser feita.
SABE=$(docker compose exec -T sugestoes python manage.py shell -c \
  "from django.core.management import get_commands; print('esvaziar_caixa' in get_commands())" 2>&1 | tr -d '\r[:space:]')
case "$SABE" in
  True) echo "  comando esvaziar_caixa ...... disponível" ;;
  False) parar "esta imagem da Caixa ainda não conhece o comando 'esvaziar_caixa'. Espere o deploy da célula 'sugestoes' ficar verde e rode de novo." ;;
  *) echo "$SABE"; parar "não consegui perguntar à Caixa se ela conhece o comando." ;;
esac

echo
echo "== 3/5 — descobrindo o site no catálogo =="
# A MESMA regra do `semear-demo-caixa.sh`, de propósito: um site ativo serve;
# zero ou vários PARAM. Escolher "o primeiro" aqui seria este script inventando
# um site padrão — e, num comando sem volta, inventar é o pior que ele podia
# fazer.
SITES=$(docker compose exec -T catalogo python manage.py shell -c \
  "from apps.sites.models import Site
for s in Site.objects.filter(active=True).order_by('host'):
    print(f'{s.id}\t{s.host}')" 2>/dev/null | tr -d '\r' | grep -E '^[0-9a-fA-F-]{36}\s') \
  || parar "não consegui perguntar ao catálogo quais sites existem."

LINHA=$(printf '%s\n' "$SITES" | awk -F"\t" -v h="$HOST_PEDIDO" '$2==h {print; exit}')
if [ -z "$LINHA" ]; then
  echo "  O site '$HOST_PEDIDO' não está entre os ativos do catálogo. Os que estão:"
  printf '%s\n' "$SITES" | while IFS="$(printf '\t')" read -r ID HOST; do
    echo "     - $HOST  ($ID)"
  done
  parar "host pedido não encontrado. Confira a grafia (sem https://, sem barra no fim)."
fi
SITE_ID=$(printf '%s' "$LINHA" | cut -f1)
SITE_HOST=$(printf '%s' "$LINHA" | cut -f2)
echo "  site ...... $SITE_HOST"
echo "  número .... $SITE_ID"

# Duas contas, não uma: as ideias que ainda têm conteúdo (o alvo) e as que já
# foram apagadas antes (a testemunha de que a segunda conta não encolheu no
# caminho — nada aqui pode DESapagar coisa nenhuma).
contar() {
  docker compose exec -T sugestoes python manage.py shell -c \
    "from apps.sugestoes.models import Sugestao
com = Sugestao.objects.filter(apagada_em__isnull=True)
sem = Sugestao.objects.filter(apagada_em__isnull=False)
print(f'{com.count()}\t{sem.count()}')" \
    2>/dev/null | tr -d '\r' | grep -E '^[0-9]+\s+[0-9]+$' | head -n1
}

echo
echo "== 4/5 — estado ANTES =="
ANTES=$(contar) || parar "não consegui perguntar à Caixa quantas ideias ela tem."
COM_ANTES=$(printf '%s' "$ANTES" | cut -f1)
SEM_ANTES=$(printf '%s' "$ANTES" | cut -f2)
echo "  ideias com conteúdo ....... $COM_ANTES  (é o que vai ser apagado)"
echo "  ideias já apagadas antes .. $SEM_ANTES"

if [ "$COM_ANTES" != "$QUANTAS_ESPERO" ]; then
  echo
  echo "Você disse esperar $QUANTAS_ESPERO ideia(s) com conteúdo, e o quadro tem $COM_ANTES."
  parar "o número não bate. Isto é a trava funcionando: olhe o quadro em https://$SITE_HOST/admin/caixa/ antes de repetir com o número certo."
fi

echo
echo "== 5/5 — apagando definitivamente =="
docker compose exec -T sugestoes python manage.py esvaziar_caixa \
  --site-id "$SITE_ID" --confirmo "$QUANTAS_ESPERO" \
  || parar "o comando falhou. A tela acima diz por quê — mande-a ao agente."

DEPOIS=$(contar)
COM_DEPOIS=$(printf '%s' "$DEPOIS" | cut -f1)
SEM_DEPOIS=$(printf '%s' "$DEPOIS" | cut -f2)

echo
echo "== estado DEPOIS =="
echo "  ideias com conteúdo ....... $COM_DEPOIS"
echo "  ideias já apagadas ........ $SEM_DEPOIS"
echo

# A TESTEMUNHA. Ausência de erro não é sucesso (INV-CI01): o "PRONTO." só sai
# depois de o banco confirmar as DUAS metades — que não sobrou conteúdo, e que
# as apagadas de antes continuam apagadas mais as de agora.
if [ "${COM_DEPOIS:-1}" -ne 0 ]; then
  echo "ATENÇÃO: ainda restam $COM_DEPOIS ideia(s) com conteúdo."
  echo "Mande esta tela ao agente."
  exit 1
fi

ESPERADO=$((SEM_ANTES + COM_ANTES))
if [ "${SEM_DEPOIS:-0}" -ne "$ESPERADO" ]; then
  echo "ATENÇÃO: esperava $ESPERADO ideia(s) apagada(s) no total e contei $SEM_DEPOIS."
  echo "Isto NÃO devia acontecer. Mande esta tela ao agente antes de mexer na Caixa."
  exit 1
fi

echo "PRONTO. A Caixa está vazia: $COM_ANTES ideia(s) apagada(s) definitivamente."
echo "O quadro em https://$SITE_HOST/forms/sugestoes/ abre limpo, esperando a primeira ideia de aluno."
