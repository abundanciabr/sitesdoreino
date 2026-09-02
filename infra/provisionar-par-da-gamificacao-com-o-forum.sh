#!/usr/bin/env bash
# =============================================================================
# DEIXAR A PARTE DAS CONQUISTAS PERGUNTAR AO FÓRUM — o passo do mantenedor.
#
# Os Destaques da semana são alguém da equipe escolhendo até três trabalhos por
# semana e escrevendo por que escolheu. Para escolher é preciso VER, e ver quer
# dizer ler o TÍTULO da conversa. O título mora no fórum, e a parte das
# conquistas precisa perguntar por ele. Falar com outra célula exige credencial,
# e credencial não viaja por esteira (INV-P8, Lei 5): o `deploy-infra.yml` diz
# de si mesmo que JAMAIS toca `infra/env/` nem `/opt/plataforma/env/`. Por isso
# este passo é seu, e por isso este arquivo existe: para ele ser UMA linha, e
# não um texto para colar.
#
# COMO RODAR (dentro da VPS, uma linha só, SEM argumentos):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-par-da-gamificacao-com-o-forum.sh -o /tmp/p.sh && bash /tmp/p.sh
#
# NÃO PERGUNTA NADA e NÃO PEDE NADA. O segredo que falta é gerado AQUI, dentro
# da VPS, e gravado direto nos arquivos: ele não aparece na tela, não passa por
# agente nenhum e não entra no Git (`armadilhas/090`).
#
# É IDEMPOTENTE E NÃO ROTACIONA. Se o par já existir, ele é REUSADO, nunca
# regerado — trocar um token em uso derrubaria as chamadas até o container do
# outro lado reiniciar, e o sintoma seria 401 intermitente. Rodar de novo é
# seguro, e é a cura de qualquer dúvida.
#
# O QUE ELE LIGA (dois degraus, e a ordem é deliberada: PROVEDOR PRIMEIRO):
#
#   1. env/forum.env         TOKENS_ACEITOS_GAMIFICACAO
#   2. env/gamificacao.env   FORUM_API_URL, FORUM_API_TOKEN
#
# Provedor antes de consumidor porque a ordem inversa tem janela ruim: o
# consumidor com token que o provedor ainda não aceita responde 401 para gente
# de verdade. Ao contrário, um provedor que aceita um token que ninguém usa
# ainda não faz nada, e é uma janela sem sintoma.
#
# ATENÇÃO — JÁ EXISTE UM PAR ENTRE ESTAS DUAS CÉLULAS, E ESTE É O OUTRO.
# Desde 01/09/2026 o FÓRUM pergunta à gamificação qual é o nível de quem
# escreve (a etiqueta "Nv 7 · Artesão"), e quem ligou aquilo foi
# `infra/provisionar-par-do-forum-com-a-gamificacao.sh` — nome parecido,
# sentido contrário. Este script liga a conversa no sentido inverso: a
# gamificação perguntando títulos ao fórum. **São dois pares e são DOIS
# TOKENS.** Reusar o mesmo valor faria "trocar a credencial da etiqueta" e
# "trocar a credencial dos destaques" serem o mesmo gesto, e no dia de
# rotacionar um deles o outro cairia junto, sem aviso. As conferências do §2
# abaixo existem para o caso de alguém "consertar" isso um dia copiando um
# valor do outro par.
#
# OS NOMES SEGUEM A CONVENÇÃO DAS DUAS CÉLULAS. Do lado da `gamificacao` as
# variáveis já são `IDENTIDADE_API_URL`/`IDENTIDADE_API_TOKEN`
# (`services/gamificacao/apps/core/sessao.py`) — por isso `FORUM_API_URL` e
# `FORUM_API_TOKEN`, e não o `TOKEN_<CELULA>` que a `admin` usa. Do lado do
# `forum`, `TOKENS_ACEITOS_GAMIFICACAO` é o formato que ele lê
# (`config/settings.py`: toda variável começada em `TOKENS_ACEITOS_` vira um
# token do par aceito). Trocar qualquer um dos três nomes é 401 silencioso.
#
# SE NADA FOR RODADO: **nada muda, e nada quebra.** O fórum continua servindo
# ler, escrever, moderar e buscar, com as etiquetas de nível funcionando como
# hoje (elas são do OUTRO par, e este script não encosta nelas). A parte das
# conquistas continua contando XP e guardando de quem é cada conversa, porque
# isso ela faz sozinha, sem perguntar nada a ninguém. O que fica sem
# funcionar é UMA tela, e ela nem existe ainda: a tela de escolher os
# destaques da semana, que vem no próximo passo. Quando ela chegar, sem este
# script ela abre dizendo que ainda não consegue falar com o fórum, e a lista
# de trabalhos vem vazia. Nenhum aluno vê erro nenhum.
# =============================================================================

# O modo de falha de 24/08 em pessoa: carregado com `source`/`.`, um `exit` daqui
# derrubaria a sessão do mantenedor. Com `bash /tmp/p.sh` o exit morre no filho.
if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU POR SEGURANÇA: este arquivo foi carregado com 'source' (ou '.'), e assim um erro derrubaria a sua sessão. Rode com a palavra bash na frente: bash /tmp/p.sh"
  return 1 2>/dev/null || exit 1
fi

set -u

parar() { echo "PAROU POR SEGURANÇA: $1"; exit 1; }

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
ENV_FORUM="env/forum.env"
ENV_GAMIFICACAO="env/gamificacao.env"
# A referência de dono/permissão: um env que JÁ funciona nesta máquina.
ENV_REF="$ENV_FORUM"

# O endereço interno sai do `servers:` do contrato congelado do fórum
# (`contracts/forum.openapi.yaml`), e não é escolha deste script.
FORUM_URL="http://forum:8000/interno"

# -----------------------------------------------------------------------------
# 1. ONDE — a pasta da plataforma e os dois arquivos de que dependo.
#    Tudo conferido ANTES de gerar ou escrever coisa nenhuma.
# -----------------------------------------------------------------------------
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ — você está na VPS certa? (o prompt tem de começar com deploy@srv… ou root@srv…)"
for arquivo in "$ENV_FORUM" "$ENV_GAMIFICACAO"; do
  [ -f "$arquivo" ] || parar "não achei $RAIZ/$arquivo — alguma das células não está provisionada nesta máquina. Nada foi criado, nada foi alterado."
  [ -w "$arquivo" ] || parar "não consigo escrever em $RAIZ/$arquivo — rode como root ou como o dono dos env. Nada foi alterado."
done

ler_de() {  # arquivo, chave — devolve o valor limpo, sem comentário nem espaços
  grep "^$2=" "$1" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' | tr -d '[:space:]'
}

gerar_segredo() {
  # `openssl` primeiro; `/dev/urandom` como caminho alternativo MEDIDO, nunca
  # silencioso — se nenhum dos dois existir, o script para em vez de gravar um
  # valor fraco.
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  elif [ -r /dev/urandom ]; then
    head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'
  else
    return 1
  fi
}

# -----------------------------------------------------------------------------
# 2. O VALOR — reusado se já existe, gerado só se falta. E CONFERIDO contra o
#    par que já liga estas mesmas duas células no sentido contrário.
# -----------------------------------------------------------------------------
T_GAMIFICACAO="$(ler_de "$ENV_FORUM" TOKENS_ACEITOS_GAMIFICACAO)"
NOVO=0
if [ -z "$T_GAMIFICACAO" ]; then
  T_GAMIFICACAO="$(gerar_segredo)" || parar "não achei openssl nem /dev/urandom nesta máquina, e eu não gravo um segredo fraco. Nada foi alterado."
  NOVO=1
fi
[ ${#T_GAMIFICACAO} -ge 32 ] || parar "o token do par gamificacao→forum ficou curto demais. Nada foi alterado."

# O PRIMEIRO da lista é o par INVERSO (`forum→gamificacao`, a etiqueta de nível),
# e é o erro mais fácil de cometer aqui: os dois pares ligam as mesmas duas
# células, com nomes de script quase iguais. Os outros dois são os pares que a
# `gamificacao` já tem do lado dela.
for outro in TOKENS_ACEITOS_FORUM IDENTIDADE_API_TOKEN ALUNOS_API_TOKEN; do
  valor="$(ler_de "$ENV_GAMIFICACAO" "$outro")"
  if [ -n "$valor" ] && [ "$T_GAMIFICACAO" = "$valor" ]; then
    parar "o token deste par é IGUAL ao de $outro. Token é por par: um valor só faria a rotação de um derrubar o outro, sem aviso — e no caso do TOKENS_ACEITOS_FORUM seriam justamente as duas conversas entre estas mesmas duas células. Nada foi alterado."
  fi
done

echo "== estado ANTES =="
printf '  %-24s %s\n' "$ENV_FORUM" "encontrado ($(wc -l < "$ENV_FORUM") linhas)"
printf '  %-24s %s\n' "$ENV_GAMIFICACAO" "encontrado ($(wc -l < "$ENV_GAMIFICACAO") linhas)"
if [ "$NOVO" -eq 0 ]; then
  echo "  segredo ................. o par JÁ existia; vou reusar, não regerar"
else
  echo "  segredo ................. vou gerar um novo, aqui dentro da VPS"
fi
echo

# -----------------------------------------------------------------------------
# 3. ESCRITA — uma chave por vez, com cópia de segurança por arquivo.
# -----------------------------------------------------------------------------
MEXIDOS=""
BACKUPS=""

garantir() {  # arquivo, chave, valor, cabeçalho-do-bloco
  arq="$1"; chave="$2"; valor="$3"; cabecalho="$4"
  atual="$(ler_de "$arq" "$chave")"
  [ "$atual" = "$valor" ] && return 0

  case "$BACKUPS" in
    *"$arq:"*) : ;;  # já tem cópia deste arquivo nesta execução
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
    # Sem esta guarda, um arquivo que não termina em quebra de linha grudaria a
    # chave nova no fim da última linha — e a última linha de um env é um valor.
    if [ -s "$arq" ] && [ "$(tail -c 1 "$arq" | wc -l)" -eq 0 ]; then
      printf '\n' >> "$arq" || parar "não consegui escrever em $arq. As cópias intactas estão em $RAIZ ($BACKUPS)."
    fi
    grep -q "^# $cabecalho" "$arq" || printf '\n# %s\n# Escrito por infra/provisionar-par-da-gamificacao-com-o-forum.sh (os destaques da semana).\n' "$cabecalho" >> "$arq"
    printf '%s=%s\n' "$chave" "$valor" >> "$arq" \
      || parar "não consegui escrever em $arq. As cópias intactas estão em $RAIZ ($BACKUPS)."
  fi

  # DONO E MODO copiados de um env que JÁ FUNCIONA, nunca escolhidos por mim
  # (`armadilhas/091`): rodando como root, o `sed -i` recria o arquivo e pode
  # deixá-lo root:root — e o usuário `deploy`, que é quem o pipeline usa, não lê
  # um 600 de root.
  if [ "$(stat -c '%U:%G %a' "$arq" 2>/dev/null)" != "$(stat -c '%U:%G %a' "$ENV_REF" 2>/dev/null)" ]; then
    chown --reference="$ENV_REF" "$arq" 2>/dev/null \
      || parar "não consegui ajustar o dono de $arq — rode como root ou como o dono dos env. As cópias intactas estão em $RAIZ ($BACKUPS)."
    chmod --reference="$ENV_REF" "$arq" 2>/dev/null \
      || parar "não consegui ajustar as permissões de $arq — rode como root. As cópias intactas estão em $RAIZ ($BACKUPS)."
  fi

  case "$MEXIDOS" in *" $arq"*) : ;; *) MEXIDOS="$MEXIDOS $arq" ;; esac
}

# PROVEDOR PRIMEIRO — ver o cabeçalho deste arquivo.
garantir "$ENV_FORUM" TOKENS_ACEITOS_GAMIFICACAO "$T_GAMIFICACAO" "par gamificacao→forum: os titulos das conversas, para os destaques da semana"
garantir "$ENV_GAMIFICACAO" FORUM_API_URL "$FORUM_URL" "par gamificacao→forum"
garantir "$ENV_GAMIFICACAO" FORUM_API_TOKEN "$T_GAMIFICACAO" "par gamificacao→forum"

# -----------------------------------------------------------------------------
# 4. ESTADO DEPOIS — a conferência que fecha o assunto. Compara SEM imprimir
#    segredo: o que vai para a tela é "confere / não confere", nunca o valor.
# -----------------------------------------------------------------------------
echo "== estado DEPOIS =="
A="$(ler_de "$ENV_FORUM" TOKENS_ACEITOS_GAMIFICACAO)"
B="$(ler_de "$ENV_GAMIFICACAO" FORUM_API_TOKEN)"
U="$(ler_de "$ENV_GAMIFICACAO" FORUM_API_URL)"
[ -n "$A" ] || parar "TOKENS_ACEITOS_GAMIFICACAO não ficou gravado em $ENV_FORUM. As cópias intactas estão em $RAIZ ($BACKUPS)."
[ "$A" = "$B" ] || parar "os dois lados do par ficaram com valores DIFERENTES — isso daria 401 em toda consulta de titulo, e a tela de escolher os destaques abriria com a lista vazia, calada. As cópias intactas estão em $RAIZ ($BACKUPS)."
[ "$U" = "$FORUM_URL" ] || parar "FORUM_API_URL não ficou como esperado em $ENV_GAMIFICACAO. As cópias intactas estão em $RAIZ ($BACKUPS)."
INVERSO="$(ler_de "$ENV_GAMIFICACAO" TOKENS_ACEITOS_FORUM)"
if [ -n "$INVERSO" ] && [ "$INVERSO" = "$A" ]; then
  parar "os DOIS pares entre estas células ficaram com o mesmo token. Rotacionar um derrubaria o outro em silêncio. As cópias intactas estão em $RAIZ ($BACKUPS)."
fi
echo "  par gamificacao→forum ... confere nos dois lados"
echo "  endereco do forum ....... $FORUM_URL"
if [ -n "$INVERSO" ]; then
  echo "  par forum→gamificacao ... intacto, e com token PROPRIO (a etiqueta de nivel)"
fi
echo

# -----------------------------------------------------------------------------
# 5. REINICIAR quem precisa ler o env novo.
#    O `gamificacao-consumer` entra junto porque ele roda a MESMA imagem e lê o
#    MESMO env: deixá-lo para trás faria o processo que escuta os eventos ficar
#    com uma cópia velha do ambiente, e isso é o tipo de diferença que só
#    aparece semanas depois.
# -----------------------------------------------------------------------------
if [ -n "$MEXIDOS" ]; then
  echo "== reiniciando as celulas para que leiam o env novo =="
  # O VEREDITO VEM DO COMANDO, NUNCA DO PIPE. `if docker compose … | tail -5`
  # pergunta o estado do `tail`, que dá 0 quase sempre — e o ramo de erro
  # abaixo viraria código morto: o script diria PRONTO com as células paradas.
  # É o falso-verde do ARMADILHAS §5.10, o mesmo que fez os greens do
  # deploy-celula mentirem até 21/08/2026 (H13). A saída é guardada e só depois
  # impressa, para que o estado medido seja o do `docker compose`.
  saida_do_reinicio="$(docker compose up -d --force-recreate forum gamificacao gamificacao-consumer 2>&1)"
  estado_do_reinicio=$?
  printf '%s\n' "$saida_do_reinicio" | tail -5
  if [ "$estado_do_reinicio" -eq 0 ]; then
    echo
    echo "PRONTO. A parte das conquistas ja consegue perguntar ao forum quais sao"
    echo "as conversas mais recentes e como elas se chamam."
    echo "Nada muda na tela de ninguem hoje: quem vai usar isso e a tela de"
    echo "escolher os destaques da semana, que vem no proximo passo."
  else
    echo
    echo "Os arquivos ficaram certos, mas o reinicio das celulas FALHOU."
    echo "Nada foi perdido: os dois lados do par estao gravados e conferidos."
    echo "O forum e a parte das conquistas continuam no ar como estavam."
    echo "Rode a linha abaixo e me mande a saida:"
    echo "  cd $RAIZ && docker compose up -d --force-recreate forum gamificacao gamificacao-consumer"
  fi
else
  echo "Nada a fazer: os dois lados ja estavam ligados."
  echo "PRONTO."
fi
