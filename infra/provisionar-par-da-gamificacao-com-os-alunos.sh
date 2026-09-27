#!/usr/bin/env bash
# =============================================================================
# DEIXAR O QUADRO DE CONTRIBUIÇÕES PERGUNTAR A MATRÍCULA À CÉLULA ALUNOS.
#
# Decisão do mantenedor de 27/09/2026: só quem tem matrícula ativa assume
# tarefa no quadro de contribuições (`/conquistas/contribuicoes`), a mesma
# regra do grupo e do desafio. Quem sabe da matrícula é a célula `alunos`, e a
# parte das conquistas precisa perguntar a ela. Falar com outra célula exige
# credencial, e credencial não viaja por esteira (INV-P8, Lei 5): o segredo
# nasce AQUI, dentro da VPS, e é gravado direto nos dois arquivos. Ele não
# aparece na tela, não passa por agente nenhum e não entra no Git
# (`armadilhas/090`).
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
# O QUE ELE LIGA (dois degraus, PROVEDOR PRIMEIRO):
#
#   1. env/alunos.env        TOKENS_ACEITOS_GAMIFICACAO
#   2. env/gamificacao.env   ALUNOS_API_URL, ALUNOS_API_TOKEN
#
# Provedor antes de consumidor porque a ordem inversa tem janela ruim: o
# consumidor com token que o provedor ainda não aceita recebe 401. Um provedor
# que aceita um token que ninguém usa ainda não faz nada.
#
# O QUE ELE NÃO LIGA, E POR QUÊ. A pergunta à `alunos` vai por e-mail, e o
# e-mail real de quem clica só a `identidade` entrega (`getSessionFull`), ao
# par que está também em TOKENS_COMPLETOS_GAMIFICACAO no env DELA. Conceder
# esse grau é decisão do mantenedor, registrada no §6.3 de
# `docs/decisoes/DECISAO-celula-de-identidade.md`, e este script não a toma.
# Ele só CONFERE o grau e diz na saída se ele existe, sem imprimir valor.
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
ENV_GAMIFICACAO="env/gamificacao.env"
ENV_IDENTIDADE="env/identidade.env"
# A referência de dono/permissão: um env que JÁ funciona nesta máquina.
ENV_REF="$ENV_ALUNOS"

# O endereço interno sai do `servers:` do contrato congelado da alunos
# (`contracts/alunos.openapi.yaml`), e não é escolha deste script.
ALUNOS_URL="http://alunos:8000/api/alunos"

# -----------------------------------------------------------------------------
# 1. ONDE: a pasta da plataforma e os dois arquivos de que dependo.
#    Tudo conferido ANTES de gerar ou escrever coisa nenhuma.
# -----------------------------------------------------------------------------
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ. Você está na VPS certa? Nada foi alterado."
for arquivo in "$ENV_ALUNOS" "$ENV_GAMIFICACAO"; do
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
# 2. O VALOR: reusado se já existe, gerado só se falta, e diferente de todo
#    outro par que a gamificação já tem do lado dela.
# -----------------------------------------------------------------------------
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
    parar "o token deste par é IGUAL ao de $outro. Token é por par: um valor só faria a rotação de um derrubar o outro, sem aviso. Nada foi alterado."
  fi
done

echo "== estado ANTES =="
printf '  %-24s %s\n' "$ENV_ALUNOS" "encontrado ($(wc -l < "$ENV_ALUNOS") linhas)"
printf '  %-24s %s\n' "$ENV_GAMIFICACAO" "encontrado ($(wc -l < "$ENV_GAMIFICACAO") linhas)"
if [ "$NOVO" -eq 0 ]; then
  echo "  segredo ................. o par JÁ existia; vou reusar, não regerar"
else
  echo "  segredo ................. vou gerar um novo, aqui dentro da VPS"
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

# PROVEDOR PRIMEIRO: ver o cabeçalho deste arquivo.
garantir "$ENV_ALUNOS" TOKENS_ACEITOS_GAMIFICACAO "$T_PAR" "par gamificacao→alunos: a matricula de quem assume tarefa no quadro"
garantir "$ENV_GAMIFICACAO" ALUNOS_API_URL "$ALUNOS_URL" "par gamificacao→alunos"
garantir "$ENV_GAMIFICACAO" ALUNOS_API_TOKEN "$T_PAR" "par gamificacao→alunos"

# -----------------------------------------------------------------------------
# 4. ESTADO DEPOIS: compara SEM imprimir segredo. Vai para a tela "confere" ou
#    "não confere", nunca o valor.
# -----------------------------------------------------------------------------
echo "== estado DEPOIS =="
A="$(ler_de "$ENV_ALUNOS" TOKENS_ACEITOS_GAMIFICACAO)"
B="$(ler_de "$ENV_GAMIFICACAO" ALUNOS_API_TOKEN)"
U="$(ler_de "$ENV_GAMIFICACAO" ALUNOS_API_URL)"
[ -n "$A" ] || parar "TOKENS_ACEITOS_GAMIFICACAO não ficou gravado em $ENV_ALUNOS. As cópias intactas estão em $RAIZ ($BACKUPS)."
[ "$A" = "$B" ] || parar "os dois lados do par ficaram com valores DIFERENTES, e isso daria 401 a cada Assumir. As cópias intactas estão em $RAIZ ($BACKUPS)."
[ "$U" = "$ALUNOS_URL" ] || parar "ALUNOS_API_URL não ficou como esperado em $ENV_GAMIFICACAO. As cópias intactas estão em $RAIZ ($BACKUPS)."
echo "  par gamificacao→alunos .. confere nos dois lados"
echo "  endereco da alunos ...... $ALUNOS_URL"

# O grau do e-mail na identidade: só lido e comparado, nunca escrito.
ACEITO_NA_IDENTIDADE="$(ler_de "$ENV_IDENTIDADE" TOKENS_ACEITOS_GAMIFICACAO)"
GRAU_NA_IDENTIDADE="$(ler_de "$ENV_IDENTIDADE" TOKENS_COMPLETOS_GAMIFICACAO)"
if [ -n "$GRAU_NA_IDENTIDADE" ] && [ "$GRAU_NA_IDENTIDADE" = "$ACEITO_NA_IDENTIDADE" ]; then
  echo "  e-mail pela identidade .. o grau TOKENS_COMPLETOS_GAMIFICACAO existe"
  QUADRO="O quadro de contribuicoes ja confere a matricula de quem clica em Assumir."
else
  echo "  e-mail pela identidade .. o grau TOKENS_COMPLETOS_GAMIFICACAO NAO existe"
  QUADRO="O botao Assumir continua fechado ate o mantenedor conceder o grau TOKENS_COMPLETOS_GAMIFICACAO na identidade."
fi
echo

# -----------------------------------------------------------------------------
# 5. REINICIAR quem lê as chaves novas: a porta da `alunos` (o conjunto de
#    tokens aceitos) e a tela da `gamificacao` (o par). Os consumidores e relays
#    das duas células não usam estas chaves e ficam como estão.
#
#    O gatilho é o que os containers LEEM, e não o que este script escreveu:
#    assim um reinício que falhou numa execução é refeito na seguinte, pelo
#    mesmo botão. A comparação não imprime valor nenhum.
# -----------------------------------------------------------------------------
lido_por() {  # serviço, chave: o valor que o container em pé enxerga
  docker compose exec -T "$1" printenv "$2" 2>/dev/null | tr -d '[:space:]'
}
as_duas_leem_o_par() {
  [ "$(lido_por alunos TOKENS_ACEITOS_GAMIFICACAO)" = "$A" ]     && [ "$(lido_por gamificacao ALUNOS_API_TOKEN)" = "$A" ]     && [ "$(lido_por gamificacao ALUNOS_API_URL)" = "$ALUNOS_URL" ]
}

if as_duas_leem_o_par; then
  echo "PRONTO: o par gamificacao→alunos ja estava gravado e lido pelas duas celulas; nada foi reiniciado."
else
  echo "== reiniciando as celulas para que leiam o env novo =="
  # O VEREDITO VEM DO COMANDO, NUNCA DO PIPE (ARMADILHAS §5.10): a saída é
  # guardada e só depois impressa, para o estado medido ser o do compose.
  saida_do_reinicio="$(docker compose up -d --force-recreate alunos gamificacao 2>&1)"
  estado_do_reinicio=$?
  printf '%s
' "$saida_do_reinicio" | tail -5
  [ "$estado_do_reinicio" -eq 0 ]     || parar "os arquivos ficaram certos e conferidos, mas o reinício das células falhou. Rodar este mesmo provisionador de novo refaz o reinício."
  as_duas_leem_o_par     || parar "as células reiniciaram, mas não leem o par gravado. Rodar este mesmo provisionador de novo confere e reinicia outra vez."
  echo
  echo "PRONTO: par gamificacao→alunos gravado, conferido e lido pelas duas celulas."
fi
echo "$QUADRO"
