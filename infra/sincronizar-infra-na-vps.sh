#!/usr/bin/env bash
# =============================================================================
# O QUE RODA DENTRO DA VPS quando a INFRAESTRUTURA e sincronizada.
#
# Vive num arquivo, e nao embutido no YAML do `deploy-infra.yml`, pelo MESMO
# motivo pratico que tirou o script da celula do YAML em 28/08/2026
# (`infra/deploy-celula-na-vps.sh`): a sincronizacao passou a ser TENTADA MAIS
# DE UMA VEZ (armadilhas/127 — a VPS recusou a conexao do runner seis vezes em
# tres dias), e repetir ~120 linhas de shell tres vezes dentro do YAML seria a
# duplicacao que esta casa proibe. Com o script num arquivo, cada tentativa e
# uma chamada curta e existe UMA definicao do que a sincronizacao faz.
#
# De quebra: aqui ele e um `.sh` de verdade — revisavel, com fim de linha
# travado em LF pelo `.gitattributes`, e sem escapar de YAML.
#
# ENTRADA: nenhuma variavel. O material chega antes, por SCP, na area de
# staging `/opt/plataforma/infra.new` — e e esse staging que este script
# consome. Por isso a unidade de repeticao do workflow e o PAR (SCP + SSH), e
# nunca este script sozinho: rodado duas vezes seguidas sem um SCP no meio, ele
# para no primeiro `ls infra.new`, porque a primeira execucao ja levou o
# staging embora.
#
# AS DUAS SENTINELAS, E POR QUE SAO DUAS
# --------------------------------------
# `SINCRONIZACAO-INICIADA:` sai na PRIMEIRA linha; `SINCRONIZACAO-CONCLUIDA:`
# na ultima. O workflow le as duas na saida capturada e elas respondem a
# perguntas diferentes:
#
#   - CONCLUIDA ausente ⇒ a infraestrutura NAO foi sincronizada. Conectar sem
#     executar deixa de ser sucesso — e a casa ja pagou caro por confundir "a
#     porta abriu" com "o trabalho foi feito" (28/08/2026, o parametro com
#     nome errado que deixou o deploy-celula verde sem subir imagem nenhuma).
#   - INICIADA ausente ⇒ a VPS NAO EXECUTOU UMA LINHA SEQUER, e so nesse caso o
#     workflow repete o par. Esta e a diferenca de desenho em relacao ao
#     deploy-celula: la o script e trivialmente idempotente (`pull` e `up -d`
#     sobre o estado correto nao fazem nada), entao ele repete diante de
#     qualquer falha. Aqui o script faz troca de arquivos EM USO e backup
#     datado; repetir depois de ele ter comecado poderia datar um backup do
#     estado ja meio-trocado, e o caminho de volta impresso no passo 4 passaria
#     a apontar para um estado misto. Repetir so quando nada comecou fecha essa
#     porta por construcao, em vez de por argumento.
#
# ASCII de proposito nas duas: acento numa sentinela e um jeito barato de o
# grep falhar por codificacao e a trava virar decoracao.
#
# O QUE ESTE SCRIPT JAMAIS TOCA: infra/env/ e /opt/plataforma/env/. Os .env
# reais sao segredos escritos a mao pelo mantenedor (INV-P8); nenhum comando
# aqui menciona env/.
#
# set -eu, sem `|| true`: padrao da casa (armadilhas/040) — falha de ferramenta
# nunca pode virar "nada a fazer".
# =============================================================================
set -eu

# PRIMEIRA linha, antes ate do `cd`: a partir daqui a VPS executou alguma
# coisa, e o workflow para de repetir. Se o `cd` abaixo falhar, repetir nao
# ajudaria mesmo — o diretorio nao aparece por insistencia.
echo "SINCRONIZACAO-INICIADA: $(date -u +%Y%m%dT%H%M%SZ)"

cd /opt/plataforma

# ── 0) staging → caminhos temporários. Nada EM USO muda aqui. ──
#
# `rm -rf traefik.new` antes do `mv` nao e zelo: `mv origem destino` com o
# destino JA EXISTINDO como diretorio move a origem PARA DENTRO dele
# (`traefik.new/traefik`), e uma tentativa anterior que morreu depois deste
# bloco deixa exatamente esse resto. E o que torna o bloco re-executavel.
ls infra.new
rm -rf traefik.new
mv -f infra.new/docker-compose.yml docker-compose.yml.new
mv infra.new/traefik traefik.new
mv -f infra.new/sites.json sites.json.new
mv -f infra.new/sincronizar_sites.py sincronizar_sites.py.new
mv -f infra.new/provisionar-usuario-ponte.sh provisionar-usuario-ponte.sh
mv -f infra.new/instalar-provisionador-usuario-ponte.sh instalar-provisionador-usuario-ponte.sh
rmdir infra.new

# ── A PONTE, ANTES DE QUALQUER TROCA, E ELA NAO SEGURA A INFRAESTRUTURA ────
#
# A conta `ponte` e reconciliada aqui de proposito: nada EM USO mudou ainda
# (`TROCADO` nem existe), entao uma falha nesta altura deixa a VPS exatamente
# como estava — que e a regra 2 do brief da TAR-419, "erro de sintaxe para o
# lote ali, sem recarregar nada".
#
# O que roda como root NAO e o arquivo que acabou de chegar por SCP: e a copia
# congelada em /usr/local/sbin, pertencente ao root, que o mantenedor instalou
# uma vez com `infra/instalar-provisionador-usuario-ponte.sh`. A esteira entra
# como `deploy`, que nao e root, e so pode executar aquele caminho fixo, sem
# argumentos, pela regra estreita de sudo que o instalador escreveu.
#
# O `if` NAO E ZELO, E CONSERTO DE UMA QUEDA MEDIDA. Ate 16/09/2026 esta linha
# era um `sudo -n` incondicional. Sob `set -eu`, e depois de a sentinela
# `SINCRONIZACAO-INICIADA` ja ter saido (o que desliga a repeticao por
# desenho), numa VPS que ainda nao tinha a regra de sudo ela devolveu
# `sudo: a password is required` e derrubou a sincronizacao inteira: run
# 35047777635 do `deploy-infra`, vermelho nas tres tentativas, com o compose e
# o Traefik NAO sincronizados por causa de um recurso que nem tinha sido ligado
# ainda. A ponte e um recurso a mais, nao pre-requisito do Traefik; faltar a
# ponte nao pode custar uma plataforma desatualizada. Sem o instalador rodado,
# o log diz a linha exata e a sincronizacao segue.
#
# COM o instalador rodado, uma falha AQUI reprova o run: o provisionador desfaz
# sozinho o que tiver mexido, e defeito no sshd tem de ser visto, nao engolido.
PROVISIONADOR_DA_PONTE=/usr/local/sbin/provisionar-usuario-ponte
if [ -x "$PROVISIONADOR_DA_PONTE" ]; then
  sudo -n "$PROVISIONADOR_DA_PONTE"
else
  echo "PONTE: ainda nao ligada nesta VPS. A sincronizacao da infraestrutura segue normalmente."
  echo "       Os dois roteiros acabaram de chegar aqui. Para ligar a ponte, no"
  echo "       console root da VPS, uma linha, uma vez so:"
  echo "       bash /opt/plataforma/instalar-provisionador-usuario-ponte.sh /opt/plataforma/provisionar-usuario-ponte.sh"
fi

# ── 0.1) OS DOIS VALORES QUE O GATEWAY PRECISA, E MAIS NENHUM ──────────────
#
# Os roteadores da entrada privada injetam um Bearer por celula, e o valor vem
# do env REAL desta VPS. Este e o unico ponto do script que le `env/`, ele le
# DUAS chaves nominais e nunca imprime o valor: `--quiet` no compose existe
# exatamente para nenhum segredo interpolado cair no log do Actions.
#
# Sem esta leitura, a interpolacao do compose receberia vazio, o `:?` derrubaria
# a validacao e NADA seria trocado. E fail-closed de proposito: gateway sem
# token e melhor que gateway aberto.
for CHAVE in ALUNOS_API_TOKEN TOKEN_CATALOGO; do
  VALOR=$(grep -m1 "^$CHAVE=" env/admin.env | cut -d= -f2-) || VALOR=""
  if [ -z "$VALOR" ]; then
    echo "ERRO: $CHAVE ausente em /opt/plataforma/env/admin.env — a entrada privada nao pode nascer sem ele. NADA foi trocado."
    exit 1
  fi
  export "$CHAVE=$VALOR"
done
unset VALOR

# ── 1) VALIDAR ANTES DE TROCAR. O -f aponta para o .new, mas o
# project dir continua /opt/plataforma: a interpolação roda contra
# o .env e os env/*.env REAIS, que só existem aqui. --quiet para
# nenhum valor interpolado (segredo) ir ao log do Actions. ──
if ! docker compose -f docker-compose.yml.new config --quiet; then
  echo "ERRO: o compose novo reprovou na validação — NADA foi trocado."
  echo "O material recusado ficou em docker-compose.yml.new e traefik.new/ para inspeção."
  exit 1
fi
# sites.json malformado também não chega ao caminho final.
if ! python3 -m json.tool sites.json.new >/dev/null; then
  echo "ERRO: sites.json novo não é JSON válido — NADA foi trocado."
  exit 1
fi

# ── 1.1) A PASTA DE DADOS DO ADMIN, e a permissão de escrever nela, ANTES de
# qualquer troca. Ela ficava no meio do passo 3, depois dos `mv`: uma pasta sem
# permissão só era descoberta com os arquivos já trocados. Aqui a descoberta
# acontece enquanto ainda não há nada para desfazer.
mkdir -p admin-dados
touch admin-dados/.permissao-deploy-teste
rm -f admin-dados/.permissao-deploy-teste

# ── 2) BACKUP DATADO do que está em uso, antes de sobrescrever. ──
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
cp -a docker-compose.yml "docker-compose.yml.bak-$STAMP"
cp -a traefik "traefik.bak-$STAMP"
# sites.json pode não existir ainda (1º run desta mecânica).
if [ -f sites.json ]; then cp -a sites.json "sites.json.bak-$STAMP"; fi
echo "Backup: docker-compose.yml.bak-$STAMP e traefik.bak-$STAMP"

# ── 2.1) A VOLTA ATRAS, ARMADA ANTES DE QUALQUER TROCA ──────────────────────
#
# Ate 15/09/2026 este script IMPRIMIA o caminho de volta e nao o aplicava, com
# a frase "RESTAURACAO (voce, na VPS)". O pressuposto era que alguem com chave
# SSH leria o log e digitaria quatro comandos. O mantenedor nao usa terminal e
# o agente nao tem chave, entao uma troca ruim deixava as portas 80 e 443 de
# TODA a plataforma fora do ar por tempo indeterminado, porque o mesmo Traefik
# serve a borda publica inteira.
#
# Agora a volta acontece sozinha. TROCADO so vira 1 depois que os arquivos em
# uso mudaram: falha ANTES disso nao restaura nada, porque nada foi trocado, e
# restaurar por cima de um estado intacto seria estrago inventado.
TROCADO=0

restaurar_o_que_estava_no_ar() {
  # TROCADO=0 na PRIMEIRA linha: se a propria restauracao falhar, o trap nao
  # entra de novo e o laco nao existe.
  TROCADO=0
  echo "VOLTA ATRAS AUTOMATICA: a troca deu errado, devolvendo o que estava no ar."
  cp -a "docker-compose.yml.bak-$STAMP" docker-compose.yml
  rm -rf traefik
  cp -a "traefik.bak-$STAMP" traefik
  if [ -f "sites.json.bak-$STAMP" ]; then cp -a "sites.json.bak-$STAMP" sites.json; fi
  docker compose up -d
  docker compose up -d --force-recreate traefik
  echo "── docker compose ps depois da volta atras ──"
  docker compose ps
  echo "VOLTA ATRAS CONCLUIDA: a plataforma esta com a configuracao anterior."
}

# O trap cobre tambem a falha que ninguem previu, e nao so os dois `if` abaixo.
# `set -e` derruba o script em qualquer comando ruim, e sem trap essa queda
# passaria direto pela volta atras.
trap 'CODIGO=$?; if [ "$CODIGO" -ne 0 ] && [ "$TROCADO" = 1 ]; then restaurar_o_que_estava_no_ar; fi; exit $CODIGO' EXIT

# ── 3) TROCA + APLICAÇÃO. `up -d` é idempotente: só recria o que
# mudou no compose. Sem `docker compose pull`: sincronizar infra
# não pode, de carona, trocar a versão das células — imagem nova
# é assunto do deploy-celula. ──
mv -f docker-compose.yml.new docker-compose.yml
rm -rf traefik
mv traefik.new traefik
mv -f sites.json.new sites.json
mv -f sincronizar_sites.py.new sincronizar_sites.py
TROCADO=1
docker compose up -d

# O traefik monta ./traefik por bind mount, e bind mount prende o
# INODE: depois do mv acima, o container em execução continua lendo
# o diretório ANTIGO, e `up -d` não o recria (a definição do
# serviço no compose não mudou). Sem este recreate condicional,
# mudança de config do traefik viraria exatamente a divergência
# silenciosa que este workflow existe para matar. `diff` com erro
# também recria — na dúvida, aplicar é o lado fail-closed.
if ! diff -r "traefik.bak-$STAMP" traefik >/dev/null; then
  echo "traefik/ mudou — recriando o container para o bind mount enxergar os arquivos novos"
  docker compose up -d --force-recreate traefik
fi

# ── 4) VERIFICAÇÃO: todo serviço declarado precisa estar rodando.
# `docker compose ps` impresso SEMPRE — é a evidência do run. ──
sleep 20
ESPERADOS=$(docker compose config --services | sort)
RODANDO=$(docker compose ps --services --status running | sort)
echo "── docker compose ps (evidência do run) ──"
docker compose ps
if [ "$ESPERADOS" != "$RODANDO" ]; then
  echo "ERRO: divergência entre o compose e o que está em estado running."
  echo "Declarados: $(printf '%s' "$ESPERADOS" | tr '\n' ' ')"
  echo "Rodando:    $(printf '%s' "$RODANDO" | tr '\n' ' ')"
  FALHOS=""
  for s in $ESPERADOS; do
    if ! printf '%s\n' "$RODANDO" | grep -qx -- "$s"; then
      FALHOS="$FALHOS $s"
    fi
  done
  if [ -n "$FALHOS" ]; then
    echo "── logs (tail 60) dos serviços não-rodando:$FALHOS ──"
    docker compose logs --tail 60 $FALHOS
  fi
  exit 1
fi
echo "OK: infra sincronizada — todos os serviços declarados estão rodando."

# ── 5) SITES (R11 mecanizada): converge o catálogo da PRODUÇÃO ao
# sites.json do Git e prova cada host listado SERVINDO, por dentro
# da VPS. `shell -c` propaga exceção como exit != 0 (fail-closed);
# o funil cacheia a resolução de host por 60s INCLUSIVE o 404
# (CONV-SITE), então o smoke insiste por até ~80s antes de reprovar
# — 404 persistente é reprovação de verdade.
#
# POR QUE `-L --resolve` E NÃO `-H "Host:"` (medido em 23/08/2026):
# desde a fase 2 do PLANO-I18N a raiz de um site multilíngue
# responde 302 para /<idioma>/ DE PROPÓSITO. A sonda antiga exigia
# 200 na raiz e reprovava esse redirecionamento legítimo — o run
# 32682355021 ficou vermelho com a plataforma 100% saudável (16
# serviços de pé; /en/ e /pt-br/cadastro medidos em 200 da internet
# pública no mesmo minuto). Seguir o redirecionamento com `-L`
# mantém a exigência REAL ("o site serve") sem mentir sobre o
# desenho; `--resolve` prende o host em 127.0.0.1, então a prova
# continua acontecendo DENTRO da VPS (as duas portas presas, para
# um eventual redirecionamento para http:// também não sair da
# máquina) e não vira um teste da
# internet; `--max-redirs 3` impede laço de redirecionamento. ──
docker compose exec -T -e SITES_JSON="$(cat sites.json)" catalogo python manage.py shell -c "$(cat sincronizar_sites.py)"
for H in $(python3 -c "import json; print(' '.join(s['host'] for s in json.load(open('sites.json'))['sites']))"); do
  CODIGO=000
  for _ in 1 2 3 4 5 6 7 8; do
    CODIGO=$(curl -sk -L --max-redirs 3 --resolve "$H:443:127.0.0.1" --resolve "$H:80:127.0.0.1" -o /dev/null -w '%{http_code}' "https://$H/") || CODIGO=000
    if [ "$CODIGO" = "200" ]; then break; fi
    sleep 10
  done
  if [ "$CODIGO" != "200" ]; then
    echo "ERRO: a raiz de $H terminou em $CODIGO (esperava 200 ao seguir o redirecionamento) — cadastro convergiu mas o site não serve."
    exit 1
  fi
  echo "OK: $H serve 200 na raiz (seguindo redirecionamento; smoke por dentro da VPS)"
done
echo "OK: sites do sites.json cadastrados/convergidos e provados."

# A PROVA DE QUE ESTE SCRIPT RODOU ATE O FIM. Sem ela, um passo que nao executa
# nada devolve 0 e o deploy fica VERDE sem ter trocado nada — foi exatamente o
# que aconteceu com o deploy-celula em 28/08/2026, quando o parametro do
# workflow estava com o nome errado (script_file em vez de script_path): a acao
# avisou "Unexpected input", ignorou o script, conectou, nao rodou nada e saiu
# com sucesso. O workflow EXIGE esta linha na saida; sem ela, reprova.
# ── 6) SONDA DA ENTRADA PRIVADA. Container `running` NAO prova que a rota
# existe: a casa ja pagou por confundir "subiu" com "funciona". Aqui cada uma
# das quatro leituras tem de responder 200, e o que nao esta na lista tem de
# receber 404 do proprio Traefik. Falha aqui cai no trap e a plataforma volta
# sozinha para a configuracao anterior.
#
# A sonda roda POR DENTRO da VPS, contra 127.0.0.1:8443, que e onde a porta
# esta presa. Nenhum token aparece: quem injeta o Bearer e o middleware.
echo "── sonda da entrada privada (127.0.0.1:8443) ──"
PERMITIDOS="/alunos/api/alunos/pre-matriculas?status=aguardando
/alunos/api/alunos/pre-matriculas?status=recusada
/alunos/api/alunos/matriculas
/catalogo/api/catalogo/produtos"
printf '%s
' "$PERMITIDOS" | while IFS= read -r CAMINHO; do
  [ -n "$CAMINHO" ] || continue
  CODIGO=000
  for _ in 1 2 3 4 5 6; do
    CODIGO=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:8443$CAMINHO") || CODIGO=000
    if [ "$CODIGO" = "200" ]; then break; fi
    sleep 5
  done
  if [ "$CODIGO" != "200" ]; then
    echo "ERRO: a entrada privada respondeu $CODIGO em $CAMINHO (esperava 200)."
    exit 1
  fi
  echo "OK: 200 em $CAMINHO"
done || exit 1

recusar() {
  # $1 e o rotulo que aparece no log; do $2 em diante vao os argumentos do curl.
  ROTULO=$1
  shift
  CODIGO=$(curl -s -o /dev/null -w '%{http_code}' "$@") || CODIGO=000
  if [ "$CODIGO" != "404" ]; then
    echo "ERRO: a entrada privada respondeu $CODIGO em $ROTULO — o que nao esta na lista tem de receber 404."
    exit 1
  fi
  echo "OK: 404 em $ROTULO"
}

recusar "POST na lista de matriculas" -X POST "http://127.0.0.1:8443/alunos/api/alunos/matriculas"
recusar "caminho vizinho de matriculas" "http://127.0.0.1:8443/alunos/api/alunos/matriculas/1"
recusar "pre-matriculas sem o status permitido" "http://127.0.0.1:8443/alunos/api/alunos/pre-matriculas"
recusar "pre-matriculas com status fora da lista" "http://127.0.0.1:8443/alunos/api/alunos/pre-matriculas?status=ativa"
recusar "escrita no catalogo" -X POST "http://127.0.0.1:8443/catalogo/api/catalogo/produtos"
echo "OK: entrada privada com as quatro leituras servindo e o resto recusado."

echo "SINCRONIZACAO-CONCLUIDA: $STAMP"
