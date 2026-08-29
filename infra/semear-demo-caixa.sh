#!/usr/bin/env bash
# =============================================================================
# IDEIAS DE VITRINE NA CAIXA — põe (e tira) um quadro cheio, para o dono ver
# como a Caixa fica com gente dentro antes de a turma entrar.
#
# POR QUE ESTE SCRIPT EXISTE
# --------------------------
# Um quadro vazio não se avalia. Em 29/08/2026, dois dias antes da inauguração
# de 31/08, o mantenedor pediu para ver a Caixa com ideias em TODOS os estados —
# em análise, planejado, em desenvolvimento, implementado, não planejado e
# mesclado — com voto e comentário. Sem isso, a única forma de julgar a tela era
# imaginar, e imaginar não pega faixa vazia nem contador que não cabe na coluna.
#
# COMO SE DESFAZ, E POR QUE ISSO VEM ANTES DE TUDO
# ------------------------------------------------
# `remover` é a segunda ação e é a razão de o resto existir. Dado de vitrine que
# não sabe sair vira dado de produção por omissão — e aqui ele apareceria para
# os alunos no dia da inauguração, com voto inventado ao lado de ideia de gente.
#
# Tudo que a demo cria pendura numa identidade `@demo.invalid` (domínio
# reservado pela RFC 2606: não resolve, não é de ninguém, não colide com aluno).
# `remover` acha por esse domínio e desmonta. Se o mantenedor tiver mexido no
# status de uma ideia pelo painel, ela ganhou histórico append-only e não pode
# mais ser apagada — nesse caso o comando ARQUIVA (some do quadro do aluno do
# mesmo jeito) e diz na tela quantas caíram nesse caminho.
#
# COMO O MANTENEDOR RODA (DENTRO da VPS — prompt `deploy@srv…` ou `root@srv…`):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/semear-demo-caixa.sh -o /tmp/d.sh && bash /tmp/d.sh criar meshcraft.top
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/semear-demo-caixa.sh -o /tmp/d.sh && bash /tmp/d.sh remover meshcraft.top
#
# Se o seu prompt começa com `PS C:\>`, você está no PC e este script não é
# para lá. O caminho normal, aliás, não é este: é o workflow
# `.github/workflows/semear-demo-caixa.yml`, que roda ESTE arquivo pelo pipeline
# sem ninguém abrir terminal nenhum.
#
# NÃO ESCREVE SEGREDO, não toca env, não reinicia serviço, não faz deploy. As
# únicas escritas são linhas de ideia, voto, comentário e pessoa fictícia no
# banco da própria Caixa.
# =============================================================================
set -u

parar() { echo; echo "PAROU POR SEGURANÇA: $1"; echo "NADA foi alterado."; exit 1; }

# Duas portas para os mesmos dois argumentos, e nenhuma interpola texto de fora
# dentro do script: $1/$2 é a linha de colar do mantenedor; ACAO_DEMO/HOST_CAIXA
# é o pipeline, que os entrega pelo `envs:` da ssh-action — `${{ inputs.* }}`
# dentro de `script:` é injeção de comando na VPS (armadilhas/047).
ACAO="${1:-${ACAO_DEMO:-}}"
HOST_PEDIDO="${2:-${HOST_CAIXA:-}}"

case "$ACAO" in
  criar|remover) ;;
  "") parar "não disse o que fazer. Use 'criar' ou 'remover' como primeira palavra." ;;
  *)  parar "não conheço a ação '$ACAO'. Só existem 'criar' e 'remover'." ;;
esac

cd /opt/plataforma 2>/dev/null || parar "não achei /opt/plataforma — você está na VPS certa? (o prompt precisa começar com deploy@srv… ou root@srv…, nunca PS C:\\>)"
[ -f docker-compose.yml ] || parar "não achei docker-compose.yml em /opt/plataforma."
docker compose ps >/dev/null 2>&1 || parar "não consegui falar com o Docker Compose aqui."

echo "== 1/4 — conferindo se as duas peças estão de pé =="
for SERVICO in catalogo sugestoes; do
  ESTADO=$(docker compose ps --status running --services 2>/dev/null | grep -Fx "$SERVICO" || true)
  [ -n "$ESTADO" ] || parar "o serviço '$SERVICO' não está rodando. Suba a plataforma antes (docker compose up -d) e rode de novo."
  echo "  $SERVICO ...... de pé"
done

echo
echo "== 2/4 — descobrindo o site no catálogo =="
# A MESMA regra do `semear-caixa.sh` e do `quadro_atual()` da célula, de
# propósito: um site ativo serve; zero ou vários PARAM. Escolher "o primeiro"
# aqui seria este script inventando um site padrão.
SITES=$(docker compose exec -T catalogo python manage.py shell -c \
  "from apps.sites.models import Site
for s in Site.objects.filter(active=True).order_by('host'):
    print(f'{s.id}\t{s.host}')" 2>/dev/null | tr -d '\r' | grep -E '^[0-9a-fA-F-]{36}\s') \
  || parar "não consegui perguntar ao catálogo quais sites existem."

QUANTOS=$(printf '%s\n' "$SITES" | grep -c . || true)
[ "${QUANTOS:-0}" -ge 1 ] || parar "o catálogo não tem NENHUM site ativo."

listar_sites() {
  printf '%s\n' "$SITES" | while IFS="$(printf '\t')" read -r ID HOST; do
    echo "     - $HOST  ($ID)"
  done
}

if [ -n "$HOST_PEDIDO" ]; then
  LINHA=$(printf '%s\n' "$SITES" | awk -F"\t" -v h="$HOST_PEDIDO" '$2==h {print; exit}')
  if [ -z "$LINHA" ]; then
    echo "  O site '$HOST_PEDIDO' não está entre os ativos do catálogo. Os que estão:"
    listar_sites
    parar "host pedido não encontrado. Confira a grafia (sem https://, sem barra no fim)."
  fi
  SITE_ID=$(printf '%s' "$LINHA" | cut -f1)
  SITE_HOST=$(printf '%s' "$LINHA" | cut -f2)
elif [ "$QUANTOS" -gt 1 ]; then
  echo "  Achei mais de um site ativo:"
  listar_sites
  echo
  echo "  Rode de novo dizendo QUAL, por exemplo:"
  echo "     bash /tmp/d.sh $ACAO meshcraft.top"
  parar "há $QUANTOS sites ativos e eu não escolho por você."
else
  SITE_ID=$(printf '%s\n' "$SITES" | head -n1 | cut -f1)
  SITE_HOST=$(printf '%s\n' "$SITES" | head -n1 | cut -f2)
fi

[ -n "$SITE_ID" ] || parar "li a resposta do catálogo mas não consegui extrair o número do site."
echo "  site ...... $SITE_HOST"
echo "  número .... $SITE_ID"

# Conta as ideias de demonstração e as de gente, separadas. Duas contas e não
# uma: o número que prova a ação é o das FICTÍCIAS, e o das reais é a
# testemunha de que nada de aluno foi tocado no caminho.
contar() {
  docker compose exec -T sugestoes python manage.py shell -c \
    "from apps.sugestoes.models import Sugestao
demo = Sugestao.objects.filter(autor__email__endswith='demo.invalid')
print(f'{demo.count()}\t{Sugestao.objects.exclude(autor__email__endswith=\"demo.invalid\").count()}')" \
    2>/dev/null | tr -d '\r' | grep -E '^[0-9]+\s+[0-9]+$' | head -n1
}

echo
echo "== 3/4 — estado ANTES =="
ANTES=$(contar) || parar "não consegui perguntar à Caixa quantas ideias ela tem."
DEMO_ANTES=$(printf '%s' "$ANTES" | cut -f1)
REAIS_ANTES=$(printf '%s' "$ANTES" | cut -f2)
echo "  ideias de demonstração .... $DEMO_ANTES"
echo "  ideias de gente de verdade  $REAIS_ANTES"

echo
if [ "$ACAO" = "criar" ]; then
  echo "== 4/4 — semeando a vitrine =="
  docker compose exec -T sugestoes python manage.py semear_demo --site-id "$SITE_ID" \
    || parar "o comando falhou. A tela acima diz por quê — mande-a ao agente."
else
  echo "== 4/4 — retirando a vitrine =="
  docker compose exec -T sugestoes python manage.py semear_demo --site-id "$SITE_ID" --remover \
    || parar "o comando falhou. A tela acima diz por quê — mande-a ao agente."
fi

DEPOIS=$(contar)
DEMO_DEPOIS=$(printf '%s' "$DEPOIS" | cut -f1)
REAIS_DEPOIS=$(printf '%s' "$DEPOIS" | cut -f2)

echo
echo "== estado DEPOIS =="
echo "  ideias de demonstração .... $DEMO_DEPOIS"
echo "  ideias de gente de verdade  $REAIS_DEPOIS"
echo

# A TESTEMUNHA, e ela vale para as duas ações: o número de ideias de gente de
# verdade não pode ter mudado. Se mudou, alguma coisa encostou onde não devia e
# o "PRONTO." não sai — ausência de erro não é sucesso (INV-CI01).
if [ "$REAIS_DEPOIS" != "$REAIS_ANTES" ]; then
  echo "ATENÇÃO: as ideias de gente de verdade eram $REAIS_ANTES e agora são $REAIS_DEPOIS."
  echo "Isto NÃO devia acontecer. Mande esta tela ao agente antes de mexer na Caixa."
  exit 1
fi

if [ "$ACAO" = "criar" ]; then
  if [ "${DEMO_DEPOIS:-0}" -gt 0 ]; then
    echo "PRONTO. Abra https://$SITE_HOST/forms/sugestoes/ — o quadro tem $DEMO_DEPOIS ideias de demonstração."
    echo "Quando terminar de olhar, rode a mesma coisa com 'remover' ANTES de a turma entrar."
  else
    echo "ATENÇÃO: semeei e o quadro continua com 0 ideias de demonstração."
    exit 1
  fi
else
  if [ "${DEMO_DEPOIS:-1}" -eq 0 ]; then
    echo "PRONTO. Não sobrou nenhuma ideia de demonstração no quadro."
  else
    echo "ATENÇÃO: ainda restam $DEMO_DEPOIS ideias de demonstração."
    echo "Mande esta tela ao agente."
    exit 1
  fi
fi
