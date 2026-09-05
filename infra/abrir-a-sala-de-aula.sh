#!/usr/bin/env bash
# =============================================================================
# ABRIR A SALA DE AULA, o passo do mantenedor.
# Poe no env da celula `cursos` quem entra no plantao e a chave da IA, recria a
# celula para ela reler o arquivo, e semeia o ESQUELETO do curso (1 curso, 12
# blocos, 34 aulas, 13 instrumentos) para a lista de aulas deixar de nascer
# vazia.
#
# COMO O MANTENEDOR RODA (dentro da VPS, uma linha so, SEM argumentos):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/abrir-a-sala-de-aula.sh -o /tmp/sala.sh && bash /tmp/sala.sh
#
#   O prompt tem de comecar com `deploy@srv...` ou `root@srv...`. Se comecar
#   com `PS C:\>`, voce esta no PC e este script nao e para la.
#
# ELE NAO PERGUNTA NADA, e essa e a decisao que da forma ao arquivo. As tres
# variaveis que ele grava JA EXISTEM nesta maquina, escritas por outros
# roteiros que o mantenedor ja rodou: a lista de quem entra no /admin/ mora em
# `env/admin.env` e a chave da Anthropic mora em `env/forum.env` desde
# 02/09/2026. Pedir de novo o que a maquina ja sabe seria fazer o mantenedor
# colar um segredo a toa, e colar segredo a toa e como um segredo acaba num
# lugar errado (`armadilhas/090`). Nenhum valor passa por argumento de linha de
# comando aqui: argumento e lido por qualquer processo da maquina pelo
# `ps aux`, fica no `~/.bash_history` e vai junto no print que o mantenedor
# manda ao agente para provar que funcionou.
#
# POR QUE AS TRES VARIAVEIS SAO COPIA, e nao ligacao viva: cada celula le o
# proprio `env_file`, e nao existe um env comum na plataforma. A copia e uma
# FOTOGRAFIA: se a lista de admins mudar em `env/admin.env`, ou se a chave for
# trocada em `env/forum.env`, rode este script de novo para a sala de aula
# acompanhar.
#
# IDEMPOTENTE: rodar de novo e seguro, e e o jeito de atualizar a copia. O env
# antigo vira `.bak-<epoch>` antes de qualquer edicao, o bloco das tres linhas
# e reescrito inteiro (nunca duplicado), e o semeador e `get_or_create` pela
# chave natural, sem atualizar o que ja existe: se o mantenedor renomear uma
# aula pela tela, rodar de novo nao desfaz.
#
# O QUE ELE NAO FAZ, e a ausencia e decisao: nao escreve NENHUM texto de aula.
# O esqueleto e so numero, ordem e titulo exibido. O conteudo do curso e obra
# nao lancada do mantenedor e entra pela tela de `/admin/escola/aulas/`, por
# nenhum arquivo deste repositorio, que e publico ([INV-CUR-C2],
# `armadilhas/331`).
# =============================================================================

# O modo de falha de 24/08 em pessoa: carregado com `source`/`.`, um `exit` daqui
# derrubaria a sessao do mantenedor. Com `bash /tmp/sala.sh` o exit morre no filho.
if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU POR SEGURANÇA: este arquivo foi carregado com 'source' (ou '.'), e assim um erro derrubaria a sua sessao. Rode com a palavra bash na frente: bash /tmp/sala.sh"
  return 1 2>/dev/null || exit 1
fi

set -u

parar() { echo; echo "PAROU POR SEGURANÇA: $1"; exit 1; }

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
ENV_CURSOS="env/cursos.env"
ENV_ADMIN="env/admin.env"
ENV_FORUM="env/forum.env"
# A referência de dono/permissão: um env que JÁ funciona nesta máquina
# (`armadilhas/091`). Rodando como root, uma edição que recria o arquivo pode
# deixá-lo root:root, e aí o usuário `deploy` (que é quem o pipeline usa) não lê.
ENV_REF="env/identidade.env"

# A marca do bloco que este script escreve. Ela é filtrada na reescrita para o
# cabeçalho não empilhar a cada execução, e por isso é uma linha LITERAL e
# fixa: mudá-la aqui sem mudar o filtro lá embaixo deixaria duas.
MARCA="# escrito por infra/abrir-a-sala-de-aula.sh"

ler_de() {  # arquivo, chave: devolve o valor limpo, sem comentário nem espaços
  grep "^$2=" "$1" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' | tr -d '[:space:]'
}

# -----------------------------------------------------------------------------
# 1. ONDE, tudo conferido ANTES de tocar em arquivo nenhum.
#    Descobrir no meio do caminho que falta um arquivo deixaria meia-instalação
#    para desfazer, e é a metade que ninguém percebe que ficou.
# -----------------------------------------------------------------------------
cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ. Você está na VPS certa? (o prompt tem de começar com deploy@srv… ou root@srv…, nunca PS C:\\>)"
[ -f docker-compose.yml ] || parar "não achei docker-compose.yml em $RAIZ."
[ -f "$ENV_CURSOS" ] || parar "não achei $RAIZ/$ENV_CURSOS. A sala de aula ainda não foi provisionada nesta máquina: rode antes o infra/provisionar-cursos.sh. Nada foi alterado."
[ -w "$ENV_CURSOS" ] || parar "não consigo escrever em $RAIZ/$ENV_CURSOS. Rode como root ou como o dono dos env. Nada foi alterado."
[ -f "$ENV_ADMIN" ] || parar "não achei $RAIZ/$ENV_ADMIN, que é de onde eu copio a lista de quem entra no /admin/. Rode antes o infra/provisionar-admin.sh. Nada foi alterado."
[ -f "$ENV_FORUM" ] || parar "não achei $RAIZ/$ENV_FORUM, que é de onde eu copio a chave da IA. Rode antes o infra/provisionar-forum.sh e depois o infra/por-a-chave-da-ia-do-forum.sh. Nada foi alterado."
[ -f "$ENV_REF" ] || parar "não achei $RAIZ/$ENV_REF, que é de onde eu copio dono e permissão. Nada foi alterado."
command -v docker >/dev/null 2>&1 || parar "não achei o docker nesta máquina, e sem ele eu não consigo recarregar a sala de aula nem semear o curso. Nada foi alterado."
docker compose ps >/dev/null 2>&1 || parar "não consegui falar com o Docker Compose aqui. Nada foi alterado."
for SERVICO in cursos cursos-relay; do
  docker compose config --services 2>/dev/null | grep -qx "$SERVICO" \
    || parar "o serviço '$SERVICO' não está no docker-compose.yml desta máquina. A sala de aula ainda não foi entregue à VPS: espere o deploy da infraestrutura terminar e rode de novo. Nada foi alterado."
done

# -----------------------------------------------------------------------------
# 2. OS TRÊS VALORES, lidos e conferidos ANTES de escrever.
#
#    Nenhum deles é gerado aqui, e nenhum é digitado: os três já existem nesta
#    máquina. Ler antes de escrever é o que faz uma recusa significar "nada foi
#    alterado" de verdade.
# -----------------------------------------------------------------------------
echo "== 1/5: lendo o que esta maquina ja sabe =="

# A lista de direito de quem entra no /admin/ (DECISAO-celula-admin §2). É ela
# que o plantão da sala de aula soma a `CURSOS_PROFESSORES` para reconhecer o
# mantenedor sem ele ter de se pôr numa segunda lista à mão.
#
# VAZIA PARA: fail-closed por falta de valor é indistinguível de fail-closed por
# decisão (`armadilhas/111`), e aqui o efeito seria o mantenedor abrir o plantão
# e levar 404 na própria escola, sem nada explicando por quê.
ADMINS="$(ler_de "$ENV_ADMIN" ADMIN_EMAILS)"
[ -n "$ADMINS" ] || parar "o ADMIN_EMAILS de $RAIZ/$ENV_ADMIN está vazio ou não existe, e é dele que sai quem abre o plantão da sala de aula. Sem essa lista ninguém entraria em /cursos/plantao, nem você. Rode antes o infra/provisionar-admin.sh. Nada foi alterado."
# Só o que um e-mail em lista separada por vírgula precisa. Não é frescura de
# formato: é o que garante que o valor entra no arquivo como uma linha só.
case "$ADMINS" in
  *[!A-Za-z0-9_@.,+-]*) parar "o ADMIN_EMAILS de $ENV_ADMIN tem um caractere que não é de e-mail (espere letras, números, @ . _ + - e a vírgula que separa). Confira aquele arquivo. Nada foi alterado." ;;
esac

# A chave da Anthropic. Ela nasce na conta do mantenedor, custa dinheiro por uso
# e nenhum roteiro desta casa sabe inventá-la: aqui ela é só COPIADA do fórum,
# que é onde ele já a colou, em 02/09/2026.
CHAVE_DA_IA="$(ler_de "$ENV_FORUM" ANTHROPIC_API_KEY)"
[ -n "$CHAVE_DA_IA" ] || parar "o ANTHROPIC_API_KEY de $RAIZ/$ENV_FORUM está vazio, e é de lá que eu copio a chave da IA. Rode primeiro: curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/por-a-chave-da-ia-do-forum.sh -o /tmp/ia.sh && bash /tmp/ia.sh, e depois este de novo. Nada foi alterado."
case "$CHAVE_DA_IA" in
  *[!A-Za-z0-9_-]*) parar "a chave em $ENV_FORUM tem um caractere estranho e eu não a gravo assim. Rode de novo o infra/por-a-chave-da-ia-do-forum.sh, colando a chave direto do site da Anthropic. Nada foi alterado." ;;
esac

# O workspace da chave. VAZIO É RESPOSTA LEGÍTIMA e por isso não para aqui:
# quem usa chave clássica (de workspace) não tem esse número, e o fórum trata
# assim desde 02/09/2026. Só a chave nova, ligada à identidade de quem a criou,
# é recusada sem ele, com HTTP 400.
WORKSPACE_DA_IA="$(ler_de "$ENV_FORUM" ANTHROPIC_WORKSPACE_ID)"
case "$WORKSPACE_DA_IA" in
  *[!A-Za-z0-9_-]*) parar "o ANTHROPIC_WORKSPACE_ID de $ENV_FORUM tem um caractere estranho. Confira aquele arquivo. Nada foi alterado." ;;
esac

# De que site é esta sala de aula. É a variável mais perigosa do arquivo, e o
# perigo é ela FALTAR: sem ela o semeador criaria o curso amarrado a coisa
# nenhuma, e o mapa das portas de uma escola inteira responderia vazio sem
# nenhuma tela quebrar para avisar. Ela não é escolhida aqui: quem a escreveu
# foi o `provisionar-cursos.sh`, perguntando ao catálogo.
SITE_ID="$(ler_de "$ENV_CURSOS" SITE_ID)"
[ -n "$SITE_ID" ] || parar "o SITE_ID de $RAIZ/$ENV_CURSOS está vazio, e sem ele eu não sei a que site amarrar o curso. Rode de novo o infra/provisionar-cursos.sh, que é quem pergunta esse número ao catálogo. Nada foi alterado."
case "$SITE_ID" in
  *[!0-9a-fA-F-]*) parar "o SITE_ID de $ENV_CURSOS não parece o número de um site (esperava algo como 3f2b1c9a-…). Rode de novo o infra/provisionar-cursos.sh. Nada foi alterado." ;;
esac

echo "  quem entra no /admin/ ..... $ADMINS"
echo "  chave da IA ............... ${#CHAVE_DA_IA} caracteres (não mostro o conteúdo, de propósito)"
if [ -n "$WORKSPACE_DA_IA" ]; then
  echo "  workspace da IA ........... $WORKSPACE_DA_IA"
else
  echo "  workspace da IA ........... vazio (é o normal para chave de workspace)"
fi
echo "  site desta sala de aula ... $SITE_ID"
echo

# -----------------------------------------------------------------------------
# 3. GRAVAR, com cópia do arquivo antes e o bloco reescrito inteiro.
#
#    A reescrita tira as três linhas antigas e as põe de volta juntas, no fim.
#    É o que faz a segunda execução deixar o arquivo IGUAL à primeira, em vez de
#    empilhar cabeçalho e linha repetida.
#
#    NENHUM VALOR PASSA POR ARGUMENTO. O `sed -i "s|^X=.*|X=$valor|"` que esta
#    casa usa em outros roteiros põe o valor no argv do `sed`, e argv é lido por
#    qualquer processo da máquina (`armadilhas/090`). Aqui quem escreve é o
#    `printf`, que é palavra interna do shell e não cria processo nenhum.
# -----------------------------------------------------------------------------
echo "== 2/5: gravando em $ENV_CURSOS =="
umask 077
cp -a "$ENV_CURSOS" "$ENV_CURSOS.bak-$(date +%s)" || parar "não consegui guardar a cópia de segurança de $ENV_CURSOS. Nada foi alterado."

NOVO="$ENV_CURSOS.novo-$$"
# Dois filtros em vez de um só com alternância: o segundo é `-xF`, texto fixo e
# linha inteira, e assim a MARCA não precisa ser escapada como expressão. Um
# ponto sem escape numa expressão casa qualquer caractere, e é assim que um
# filtro come a linha errada sem ninguém perceber.
grep -vE '^(ADMIN_EMAILS|ANTHROPIC_API_KEY|ANTHROPIC_WORKSPACE_ID)=' "$ENV_CURSOS" \
  | grep -vxF "$MARCA" > "$NOVO"
# Saída vazia aqui só acontece se a leitura falhou: um `cursos.env` de verdade
# tem DATABASE_URL e SITE_ID, que acabaram de ser lidos. Escrever por cima com
# um arquivo vazio seria o pior desfecho possível, então eu paro antes.
[ -s "$NOVO" ] || { rm -f "$NOVO"; parar "a reescrita de $ENV_CURSOS saiu vazia, e eu não escrevo por cima assim. NADA foi alterado; há cópia intacta em $ENV_CURSOS.bak-*."; }

# Sem esta guarda, um arquivo que não termina em quebra de linha grudaria a
# primeira linha nova no fim da última, e a última linha de um env é um valor.
if [ "$(tail -c 1 "$NOVO" | wc -l)" -eq 0 ]; then
  printf '\n' >> "$NOVO" || { rm -f "$NOVO"; parar "não consegui escrever em $RAIZ. Nada foi alterado."; }
fi

{
  printf '%s\n' "$MARCA"
  printf 'ADMIN_EMAILS=%s\n' "$ADMINS"
  printf 'ANTHROPIC_API_KEY=%s\n' "$CHAVE_DA_IA"
  printf 'ANTHROPIC_WORKSPACE_ID=%s\n' "$WORKSPACE_DA_IA"
} >> "$NOVO" || { rm -f "$NOVO"; parar "não consegui escrever em $RAIZ. Nada foi alterado."; }

# `cat >` e não `mv`, de propósito: assim o arquivo mantém o mesmo inode, e com
# ele o dono e a permissão que já funcionavam. Um `mv` traria dono e modo do
# arquivo temporário (root:root, rodando como root) e o usuário `deploy`, que é
# quem o pipeline usa, deixaria de ler o env (`armadilhas/091`).
cat "$NOVO" > "$ENV_CURSOS" || { rm -f "$NOVO"; parar "a escrita de $ENV_CURSOS falhou no meio. Há cópia intacta em $ENV_CURSOS.bak-*: recupere-a com cp e mande esta tela ao agente."; }
rm -f "$NOVO"

# A conferência do dono, mesmo assim: se o arquivo já estava com dono errado
# antes de eu chegar, o problema não é meu mas o efeito seria (a sala de aula
# subiria sem env nenhum). Só age quando de fato divergiu.
if [ "$(stat -c '%U:%G %a' "$ENV_CURSOS" 2>/dev/null)" != "$(stat -c '%U:%G %a' "$ENV_REF" 2>/dev/null)" ]; then
  chown --reference="$ENV_REF" "$ENV_CURSOS" 2>/dev/null \
    || parar "não consegui ajustar o dono de $ENV_CURSOS. As linhas JÁ estão gravadas; rode este script de novo como root."
  chmod --reference="$ENV_REF" "$ENV_CURSOS" 2>/dev/null \
    || parar "não consegui ajustar as permissões de $ENV_CURSOS. As linhas JÁ estão gravadas; rode este script de novo como root."
fi
echo "  $ENV_CURSOS ..... escrito ($(grep -c '=' "$ENV_CURSOS") variáveis)"
echo

# -----------------------------------------------------------------------------
# 4. RECARREGAR. Sem isto, as linhas estão no arquivo e a sala de aula não sabe:
#    um container só relê o env dele quando renasce.
#
#    `--force-recreate` porque `up -d` sozinho vê a mesma imagem e a mesma
#    configuração de compose e não faz nada, e mudança de env_file não conta
#    como mudança para ele.
#
#    `--wait` porque a próxima coisa que este script faz é entrar no container
#    para semear, e entrar antes de o `migrate --noinput` do boot terminar daria
#    erro de tabela inexistente numa tela que ninguém entenderia.
#
#    JAMAIS `docker compose up -d` sem argumento: isso devolveria TODAS as
#    células à tag :main do compose (RITOS §4). Só estes dois, pelo nome.
# -----------------------------------------------------------------------------
echo "== 3/5: recarregando a sala de aula (leva um minuto) =="
docker compose up -d --force-recreate --wait --wait-timeout 180 cursos cursos-relay \
  || parar "não consegui recarregar a sala de aula. As linhas JÁ estão em $ENV_CURSOS e há cópia do anterior em $ENV_CURSOS.bak-*. Rode 'docker compose logs --tail 50 cursos' e mande esta tela ao agente."
echo "  cursos e cursos-relay ..... de pé"
echo

# -----------------------------------------------------------------------------
# 5. SEMEAR O ESQUELETO. Sem isto, /admin/escola/aulas/ abre uma lista vazia e
#    não há aula para o mantenedor escrever.
#
#    O comando é `--site`, e o número vem do próprio env da célula: digitá-lo
#    aqui seria a chance de amarrar a escola inteira ao site errado.
# -----------------------------------------------------------------------------
echo "== 4/5: semeando o esqueleto do curso =="
# `-T` porque não há terminal do outro lado quando isto roda por um pipeline.
SAIDA=$(docker compose exec -T cursos python manage.py semear_esqueleto --site "$SITE_ID" 2>&1) \
  || { echo "$SAIDA"; parar "o comando semear_esqueleto falhou. A saída acima diz por quê. O env JÁ está certo; só a semeadura não aconteceu, e rodar este script de novo é seguro."; }
echo "  $SAIDA"
echo

# -----------------------------------------------------------------------------
# 6. A PROVA, e ela é medida DE FORA do que cada passo disse ter feito.
#    "O comando devolveu zero" não é evidência de nada: contar depois, por
#    outro caminho, é o que separa um PRONTO honesto de um falso-verde.
# -----------------------------------------------------------------------------
echo "== 5/5: conferindo =="

QUANTAS=$(docker compose exec -T cursos python manage.py shell -c \
  "from apps.cursos.models import Aula; print(Aula.objects.filter(curso__site_id='$SITE_ID').count())" 2>/dev/null | tr -d '\r[:space:]')
case "$QUANTAS" in
  ''|*[!0-9]*) parar "semeei, mas não consegui contar as aulas depois para provar. Mande esta tela ao agente." ;;
esac
# AO MENOS 34, e não exatamente 34, de propósito: o esqueleto tem 34, mas quem
# manda nas aulas a partir do primeiro INSERT é o mantenedor, pela tela. Exigir
# o número exato faria este script recusar no dia em que ele criasse a aula 35,
# e recusar quem está certo é o pior defeito que um roteiro de colar pode ter.
[ "$QUANTAS" -ge 34 ] || parar "esperava ao menos as 34 aulas do esqueleto neste site depois de semear, e contei $QUANTAS. Não mexa em nada e mande esta tela ao agente."
echo "  aulas no banco ............ $QUANTAS"

# As duas variáveis, conferidas DENTRO do container. É esta medição que faz o
# PRONTO lá embaixo ser um fato e não uma gentileza: o arquivo estar certo e o
# processo estar com ele são duas coisas diferentes, e a segunda é a que vale.
# O valor da chave nunca aparece: só o tamanho dela.
LIDOS=$(docker compose exec -T cursos sh -c 'printf %s "${ADMIN_EMAILS:-}" | wc -c' 2>/dev/null | tr -d '\r[:space:]')
LIDA=$(docker compose exec -T cursos sh -c 'printf %s "${ANTHROPIC_API_KEY:-}" | wc -c' 2>/dev/null | tr -d '\r[:space:]')
[ "$LIDOS" = "${#ADMINS}" ] || parar "gravei e recarreguei, mas dentro do container o ADMIN_EMAILS chegou com '$LIDOS' caracteres e eu esperava '${#ADMINS}'. O plantão pode não abrir para você. Mande esta tela ao agente."
[ "$LIDA" = "${#CHAVE_DA_IA}" ] || parar "gravei e recarreguei, mas dentro do container a chave da IA chegou com '$LIDA' caracteres e eu esperava '${#CHAVE_DA_IA}'. Mande esta tela ao agente."
echo "  dentro do container ....... ADMIN_EMAILS e a chave da IA chegaram"
echo

echo "== PRONTO =="
echo "A sala de aula está aberta. O que existe agora, conferido e não prometido:"
echo
echo "  - o curso com 12 blocos, $QUANTAS aulas e 13 instrumentos, no site $SITE_ID"
echo "  - o plantão reconhece quem entra no /admin/: $ADMINS"
echo "  - a IA que rascunha o laudo está com a chave (mesma conta do fórum)"
echo
echo "As aulas nasceram SEM TEXTO, de propósito: o conteúdo do curso é seu e"
echo "não entra por arquivo nenhum deste repositório, que é público. Você"
echo "escreve cada aula em https://meshcraft.top/admin/escola/aulas/"
echo
echo "Rodar este comando de novo é seguro, e é o jeito de a sala de aula"
echo "acompanhar uma troca de chave ou uma mudança na lista de admins."
