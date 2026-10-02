#!/usr/bin/env bash
# =============================================================================
# DEIXAR O QUADRO DE CONTRIBUIÇÕES PERGUNTAR A MATRÍCULA À CÉLULA ALUNOS.
#
# Decisão do mantenedor de 27/09/2026: só quem tem matrícula ativa assume
# tarefa no quadro de contribuições (`/conquistas/contribuicoes`), a mesma
# regra do grupo e do desafio. Quem sabe da matrícula é a célula `alunos`, e ela
# responde por e-mail; o e-mail de quem clicou, só a `identidade` entrega.
# Falar com outra célula exige credencial, e credencial não viaja por esteira
# (INV-P8, segredo fica na VPS): o segredo nasce AQUI, dentro da VPS, e é gravado direto nos
# arquivos. Ele não aparece na tela, não passa por agente nenhum e não entra no
# Git (`armadilhas/090`).
#
# COMO RODAR: pelo botão, `.github/workflows/provisionar.yml` com o alvo
#   par-da-gamificacao-com-os-alunos
# ou, dentro da VPS, uma linha só, SEM argumentos:
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-par-da-gamificacao-com-os-alunos.sh -o /tmp/p.sh && bash /tmp/p.sh
#
# É IDEMPOTENTE E NÃO ROTACIONA. Se o par já existir, ele é REUSADO, nunca
# regerado: trocar um token em uso derrubaria as chamadas até o container do
# outro lado reiniciar. Rodar de novo é seguro.
#
# O QUE ELE LIGA (três chaves de provedor, depois as duas do consumidor):
#
#   1. env/alunos.env        TOKENS_ACEITOS_GAMIFICACAO    (token novo deste par)
#   2. env/identidade.env    TOKENS_COMPLETOS_GAMIFICACAO  (o grau do e-mail: o
#                            MESMO valor de TOKENS_ACEITOS_GAMIFICACAO que já
#                            está lá, escrito por infra/provisionar-gamificacao.sh)
#   3. env/gamificacao.env   ALUNOS_API_URL, ALUNOS_API_TOKEN
#
# Provedor antes de consumidor porque a ordem inversa tem janela ruim: o
# consumidor com token que o provedor ainda não aceita recebe 401. Um provedor
# que aceita um token que ninguém usa ainda não faz nada.
#
# O GRAU DO E-MAIL está registrado no §4 de
# `docs/decisoes/DECISAO-celula-de-identidade.md` ("O par `gamificacao`"), como
# o §6.3 daquela lei exige, e segue o molde de `cursos` e `pages`
# (`infra/provisionar-pares-da-sala-de-aula.sh`, `...-da-prancheta.sh`).
#
# A PROVA É POR FORA. Arquivo certo não é célula certa: no fim, de dentro do
# container da gamificação, o script faz as duas perguntas de verdade, com o
# token que o container enxerga, e só diz PRONTO se as duas respondem 200.
#
# SE NADA FOR RODADO: ver o quadro continua igual para todo mundo; só o botão
# Assumir responde que não deu para conferir a matrícula agora, e nada é
# criado. Nenhuma outra tela muda.
# =============================================================================

# Carregado com `source`/`.`, um `exit` daqui derrubaria a sessão de quem rodou.
if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU POR SEGURANÇA: este arquivo foi carregado com 'source' (ou '.'), e assim um erro derrubaria a sua sessão. Rode com a palavra bash na frente: bash /tmp/p.sh"
  return 1 2>/dev/null || exit 1
fi

set -u

parar() { echo "PAROU POR SEGURANÇA: $1"; exit 1; }

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
ENV_ALUNOS="env/alunos.env"
ENV_IDENTIDADE="env/identidade.env"
ENV_GAMIFICACAO="env/gamificacao.env"
# A referência de dono/permissão: um env que JÁ funciona nesta máquina.
ENV_REF="$ENV_ALUNOS"

# O endereço interno sai do `servers:` do contrato congelado da alunos
# (`contracts/alunos.openapi.yaml`), e não é escolha deste script.
ALUNOS_URL="http://alunos:8000/api/alunos"

# -----------------------------------------------------------------------------
# 1. ONDE: a pasta da plataforma e os três arquivos de que dependo.
#    Tudo conferido ANTES de gerar ou escrever coisa nenhuma.
# -----------------------------------------------------------------------------
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ. Você está na VPS certa? Nada foi alterado."
FONTE_OPERACAO="$RAIZ/codigo/ferramentas/atual/infra/operacao-aplicacao.sh"
[ -f "$FONTE_OPERACAO" ] || FONTE_OPERACAO="$(dirname "${BASH_SOURCE[0]}")/operacao-aplicacao.sh"
. "$FONTE_OPERACAO" || parar "não consegui carregar as operações da aplicação. Nada foi alterado."

for arquivo in "$ENV_ALUNOS" "$ENV_IDENTIDADE" "$ENV_GAMIFICACAO"; do
  [ -f "$arquivo" ] || parar "não achei $RAIZ/$arquivo: alguma das células não está provisionada nesta máquina. Nada foi criado, nada foi alterado."
  [ -w "$arquivo" ] || parar "não consigo escrever em $RAIZ/$arquivo. Rode como root ou como o dono dos env. Nada foi alterado."
done

ler_de() {  # arquivo, chave: devolve o valor limpo, sem comentário nem espaços
  grep "^$2=" "$1" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' | tr -d '[:space:]'
}

gerar_segredo() {
  # `openssl` primeiro; `/dev/urandom` como caminho alternativo. Sem nenhum dos
  # dois, o script para em vez de gravar um valor fraco.
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  elif [ -r /dev/urandom ]; then
    head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'
  else
    return 1
  fi
}

# -----------------------------------------------------------------------------
# 2. OS VALORES. O do par com a alunos é reusado se existe e gerado se falta.
#    O do grau NUNCA é gerado: é o token com que a gamificação JÁ fala com a
#    identidade, e ele precisa estar igual nos dois lados antes de ganhar grau.
# -----------------------------------------------------------------------------
T_IDENTIDADE="$(ler_de "$ENV_IDENTIDADE" TOKENS_ACEITOS_GAMIFICACAO)"
[ -n "$T_IDENTIDADE" ] || parar "o par gamificacao→identidade não existe em $ENV_IDENTIDADE, e o grau do e-mail só se dá a um par que já existe. Quem o cria é infra/provisionar-gamificacao.sh. Nada foi alterado."
[ "$(ler_de "$ENV_GAMIFICACAO" IDENTIDADE_API_TOKEN)" = "$T_IDENTIDADE" ] \
  || parar "o IDENTIDADE_API_TOKEN de $ENV_GAMIFICACAO não é o TOKENS_ACEITOS_GAMIFICACAO de $ENV_IDENTIDADE. Dar o grau agora seria dá-lo a um token que a gamificação não usa. Nada foi alterado."

T_PAR="$(ler_de "$ENV_ALUNOS" TOKENS_ACEITOS_GAMIFICACAO)"
NOVO=0
if [ -z "$T_PAR" ]; then
  T_PAR="$(gerar_segredo)" || parar "não achei openssl nem /dev/urandom nesta máquina, e eu não gravo um segredo fraco. Nada foi alterado."
  NOVO=1
fi
[ ${#T_PAR} -ge 32 ] || parar "o token do par gamificacao→alunos ficou curto demais. Nada foi alterado."

for outro in IDENTIDADE_API_TOKEN FORUM_API_TOKEN TOKEN_CATALOGO; do
  valor="$(ler_de "$ENV_GAMIFICACAO" "$outro")"
  if [ -n "$valor" ] && [ "$T_PAR" = "$valor" ]; then
    parar "o token do par com a alunos é IGUAL ao de $outro. Token é por par: um valor só faria a rotação de um derrubar o outro, sem aviso. Nada foi alterado."
  fi
done

echo "== estado ANTES =="
for arquivo in "$ENV_ALUNOS" "$ENV_IDENTIDADE" "$ENV_GAMIFICACAO"; do
  printf '  %-24s %s\n' "$arquivo" "encontrado ($(wc -l < "$arquivo") linhas)"
done
if [ "$NOVO" -eq 0 ]; then
  echo "  par com a alunos ........ JÁ existia; vou reusar, não regerar"
else
  echo "  par com a alunos ........ vou gerar um segredo novo, aqui dentro da VPS"
fi
if [ "$(ler_de "$ENV_IDENTIDADE" TOKENS_COMPLETOS_GAMIFICACAO)" = "$T_IDENTIDADE" ]; then
  echo "  grau do e-mail .......... JÁ existia"
else
  echo "  grau do e-mail .......... vou gravar, com o token que a gamificação já usa"
fi
echo

# -----------------------------------------------------------------------------
# 3. ESCRITA: uma chave por vez, com cópia de segurança por arquivo.
# -----------------------------------------------------------------------------
BACKUPS=""

garantir() {  # arquivo, chave, valor, cabeçalho-do-bloco
  arq="$1"; chave="$2"; valor="$3"; cabecalho="$4"
  atual="$(ler_de "$arq" "$chave")"
  [ "$atual" = "$valor" ] && return 0

  case "$BACKUPS" in
    *"$arq:"*) : ;;
    *)
      b="$arq.bak-$(date +%s)"
      cp -a "$arq" "$b" 2>/dev/null || parar "não consegui guardar a cópia de segurança de $arq. Não mexi em nada."
      BACKUPS="$BACKUPS $arq:$b"
      ;;
  esac

  if grep -q "^$chave=" "$arq"; then
    sed -i "s|^$chave=.*|$chave=$valor|" "$arq" \
      || parar "a edição de $arq falhou. As cópias intactas estão em $RAIZ ($BACKUPS)."
  else
    # Arquivo sem quebra de linha no fim grudaria a chave nova no último valor.
    if [ -s "$arq" ] && [ "$(tail -c 1 "$arq" | wc -l)" -eq 0 ]; then
      printf '\n' >> "$arq" || parar "não consegui escrever em $arq. As cópias intactas estão em $RAIZ ($BACKUPS)."
    fi
    grep -q "^# $cabecalho" "$arq" || printf '\n# %s\n# Escrito por infra/provisionar-par-da-gamificacao-com-os-alunos.sh (a matrícula no quadro de contribuições).\n' "$cabecalho" >> "$arq"
    printf '%s=%s\n' "$chave" "$valor" >> "$arq" \
      || parar "não consegui escrever em $arq. As cópias intactas estão em $RAIZ ($BACKUPS)."
  fi

  # DONO E MODO copiados de um env que JÁ FUNCIONA (`armadilhas/091`): rodando
  # como root, o `sed -i` recria o arquivo como root:root, e o usuário `deploy`
  # não lê um 600 de root.
  if [ "$(stat -c '%U:%G %a' "$arq" 2>/dev/null)" != "$(stat -c '%U:%G %a' "$ENV_REF" 2>/dev/null)" ]; then
    chown --reference="$ENV_REF" "$arq" 2>/dev/null \
      || parar "não consegui ajustar o dono de $arq. Rode como root ou como o dono dos env. As cópias intactas estão em $RAIZ ($BACKUPS)."
    chmod --reference="$ENV_REF" "$arq" 2>/dev/null \
      || parar "não consegui ajustar as permissões de $arq. Rode como root. As cópias intactas estão em $RAIZ ($BACKUPS)."
  fi
}

# PROVEDORES PRIMEIRO: ver o cabeçalho deste arquivo.
garantir "$ENV_ALUNOS" TOKENS_ACEITOS_GAMIFICACAO "$T_PAR" "par gamificacao→alunos: a matricula de quem assume tarefa no quadro"
garantir "$ENV_IDENTIDADE" TOKENS_COMPLETOS_GAMIFICACAO "$T_IDENTIDADE" "grau de e-mail da gamificacao (DECISAO-celula-de-identidade §4, par gamificacao): o MESMO token de TOKENS_ACEITOS_GAMIFICACAO"
garantir "$ENV_GAMIFICACAO" ALUNOS_API_URL "$ALUNOS_URL" "par gamificacao→alunos"
garantir "$ENV_GAMIFICACAO" ALUNOS_API_TOKEN "$T_PAR" "par gamificacao→alunos"

# -----------------------------------------------------------------------------
# 4. ESTADO DEPOIS: compara SEM imprimir segredo. Vai para a tela "confere" ou
#    "não confere", nunca o valor.
# -----------------------------------------------------------------------------
echo "== estado DEPOIS =="
A="$(ler_de "$ENV_ALUNOS" TOKENS_ACEITOS_GAMIFICACAO)"
[ -n "$A" ] || parar "TOKENS_ACEITOS_GAMIFICACAO não ficou gravado em $ENV_ALUNOS. As cópias intactas estão em $RAIZ ($BACKUPS)."
[ "$A" = "$(ler_de "$ENV_GAMIFICACAO" ALUNOS_API_TOKEN)" ] || parar "os dois lados do par com a alunos ficaram com valores DIFERENTES, e isso daria 401 a cada Assumir. As cópias intactas estão em $RAIZ ($BACKUPS)."
[ "$(ler_de "$ENV_GAMIFICACAO" ALUNOS_API_URL)" = "$ALUNOS_URL" ] || parar "ALUNOS_API_URL não ficou como esperado em $ENV_GAMIFICACAO. As cópias intactas estão em $RAIZ ($BACKUPS)."
[ "$(ler_de "$ENV_IDENTIDADE" TOKENS_COMPLETOS_GAMIFICACAO)" = "$T_IDENTIDADE" ] || parar "o grau TOKENS_COMPLETOS_GAMIFICACAO não ficou igual ao TOKENS_ACEITOS_GAMIFICACAO em $ENV_IDENTIDADE. As cópias intactas estão em $RAIZ ($BACKUPS)."

# Chave repetida é o modo de falha mais traiçoeiro de um env: o Docker Compose
# usa a ÚLTIMA, e um valor velho ficaria por baixo sem nada acusar.
for par in "$ENV_ALUNOS:TOKENS_ACEITOS_GAMIFICACAO" "$ENV_IDENTIDADE:TOKENS_ACEITOS_GAMIFICACAO" \
           "$ENV_IDENTIDADE:TOKENS_COMPLETOS_GAMIFICACAO" "$ENV_GAMIFICACAO:ALUNOS_API_URL" \
           "$ENV_GAMIFICACAO:ALUNOS_API_TOKEN"; do
  arq="${par%%:*}"; chave="${par##*:}"
  n="$(grep -c "^$chave=" "$arq")"
  [ "$n" -eq 1 ] || parar "a chave $chave aparece $n vezes em $arq, e o Docker Compose usaria só a última. As cópias intactas estão em $RAIZ ($BACKUPS)."
done
echo "  par gamificacao→alunos .. confere nos dois lados"
echo "  grau do e-mail .......... confere com o token que a gamificação usa"
echo "  endereco da alunos ...... $ALUNOS_URL"
echo "  chaves repetidas ........ nenhuma"
echo

# -----------------------------------------------------------------------------
# 5. REINICIAR só quem ainda não lê o valor novo. O gatilho é o que o container
#    em pé ENXERGA, e não o que este script escreveu: um reinício que falhou
#    numa execução é refeito na seguinte, pelo mesmo botão, e a identidade (que
#    atende o login do site inteiro) só reinicia se o grau for novo para ela.
#    Os consumidores e relays das três células não usam estas chaves.
# -----------------------------------------------------------------------------
recarregar_servicos provisionar-par-da-gamificacao-com-os-alunos || parar "os arquivos foram conferidos, mas a aplicação não passou na prova após a recarga."
echo

# -----------------------------------------------------------------------------
# 6. A PROVA POR FORA: as duas perguntas de verdade, de dentro do container da
#    gamificação, com os tokens que ELE enxerga. O e-mail de prova não existe:
#    a identidade responde 200 com `id: null` quando tem o grau (403 sem ele),
#    e a alunos responde 200 com `visitante` quando aceita o token (401 sem).
#    Sai só o código HTTP; nenhum token vai para a tela.
# -----------------------------------------------------------------------------
provar() {
  codigo_servico gamificacao - 2>/dev/null <<'PY'
import os

import httpx


def status(chamada):
    try:
        return chamada().status_code
    except Exception as erro:  # a prova diz o nome do tropeço, nunca o texto
        return type(erro).__name__


identidade = os.environ.get("IDENTIDADE_API_URL", "").rstrip("/")
alunos = os.environ.get("ALUNOS_API_URL", "").rstrip("/")
bearer = lambda nome: {"Authorization": "Bearer " + os.environ.get(nome, "")}
print("identidade", status(lambda: httpx.post(
    identidade + "/pessoas/por-email",
    json={"email": "prova-do-grau@exemplo.invalid"},
    headers=bearer("IDENTIDADE_API_TOKEN"), timeout=5)))
print("alunos", status(lambda: httpx.get(
    alunos + "/alunos/prova-do-par%40exemplo.invalid/situacao",
    headers=bearer("ALUNOS_API_TOKEN"), timeout=5)))
PY
}

echo "== prova por fora, de dentro da gamificação =="
# As células recém-recriadas levam alguns segundos para atender: até 12
# tentativas, 5 s entre elas, antes de dar o veredito.
tentativa=1
while :; do
  PROVA="$(provar)"
  R_IDENTIDADE="$(printf '%s\n' "$PROVA" | awk '$1 == "identidade" { print $2 }')"
  R_ALUNOS="$(printf '%s\n' "$PROVA" | awk '$1 == "alunos" { print $2 }')"
  if [ "$R_IDENTIDADE" = "200" ] && [ "$R_ALUNOS" = "200" ]; then break; fi
  [ "$tentativa" -ge 12 ] && break
  tentativa=$((tentativa + 1))
  sleep 5
done
echo "  identidade aceita o grau completo (findPersonByEmail) ... HTTP ${R_IDENTIDADE:-sem resposta}"
echo "  alunos aceita o par (getStudentStanding) ............... HTTP ${R_ALUNOS:-sem resposta}"
[ "$R_IDENTIDADE" = "200" ] || parar "a identidade não respondeu 200 ao token da gamificação (403 quer dizer grau não lido; o arquivo está certo). Rodar este mesmo provisionador de novo reinicia e prova outra vez."
[ "$R_ALUNOS" = "200" ] || parar "a alunos não respondeu 200 ao token da gamificação (401 quer dizer token não lido; o arquivo está certo). Rodar este mesmo provisionador de novo reinicia e prova outra vez."
echo
echo "PRONTO: par gamificacao→alunos e grau do e-mail gravados, conferidos e provados por fora."
echo "O quadro de contribuicoes ja confere a matricula de quem clica em Assumir."
