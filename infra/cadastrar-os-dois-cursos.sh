#!/usr/bin/env bash
# =============================================================================
# CADASTRAR OS DOIS CURSOS, e apontar as matriculas de hoje para o primeiro.
#
# Executa a `docs/decisoes/DECISAO-cursos-matriculas-e-alunos.md` (06/09/2026)
# na parte que so pode acontecer dentro da VPS: os cursos existirem de verdade
# no catalogo, e toda matricula que ja existe passar a dizer de qual curso a
# pessoa e aluna.
#
# COMO O MANTENEDOR RODA (dentro da VPS, uma linha so, SEM argumentos):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/cadastrar-os-dois-cursos.sh -o /tmp/cursos.sh && bash /tmp/cursos.sh
#
#   O prompt tem de comecar com `deploy@srv...` ou `root@srv...`. Se comecar
#   com `PS C:\>`, voce esta no PC e este script nao e para la.
#
# OS DOIS CURSOS, com os nomes que o sistema JA usa (nada e inventado aqui):
#   1. primeiros-dolares  "Primeiros Dolares com Roblox"  <- o curso de TODOS
#      os alunos que ja estao no site hoje
#   2. profissional       "Profissional"                  <- o curso do livro,
#      mesmo apelido que a sala de aula ja usa em /cursos/profissional/
#
# IDEMPOTENTE, nos dois passos. `criar_curso` nao duplica e nao renomeia o que
# ja existe; `apontar_o_curso_das_matriculas` nunca toca em linha que ja tem
# curso. Rodar de novo depois de pronto nao muda mais nada, e e assim que se
# sabe que acabou.
#
# O PRECO DOS CURSOS NASCE EM ZERO, e isso e decisao escrita: quem cobra e a
# oferta do site, e a plataforma ainda nao vende. Zero aqui significa "nao esta
# a venda por este produto", nunca "de graca".
#
# ELE TAMBEM LIGA A SALA DE AULA ao curso do livro. Sem essa ligacao a sala
# nao tem como saber de qual curso a pessoa e aluna, e por seguranca ela nao
# deixa ninguem entrar: e a mesma lei do arquivo, de que nao conseguir conferir
# nunca e "pode entrar".
#
# O QUE ELE NAO FAZ, e a ausencia e decisao: nao cria oferta, nao poe preco,
# nao mexe em quem esta na fila esperando entrada. O curso de quem esta
# esperando e escolhido na hora de liberar, um a um, na tela do painel
# (lei §6) - e essa tela e o outro lado desta mesma decisao.
# =============================================================================

# O modo de falha de 24/08 em pessoa: carregado com `source`/`.`, um `exit` daqui
# derrubaria a sessao do mantenedor. Com `bash /tmp/cursos.sh` o exit morre no filho.
if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU POR SEGURANÇA: este arquivo foi carregado com 'source' (ou '.'), e assim um erro derrubaria a sua sessao. Rode com a palavra bash na frente: bash /tmp/cursos.sh"
  return 1 2>/dev/null || exit 1
fi

set -u

parar() { echo; echo "PAROU POR SEGURANÇA: $1"; exit 1; }

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"

APELIDO_1="primeiros-dolares"
NOME_1="Primeiros Dolares com Roblox"
APELIDO_2="profissional"
NOME_2="Profissional"

# -----------------------------------------------------------------------------
# 1. ONDE, tudo conferido ANTES de escrever qualquer coisa no banco.
#
#    Descobrir no meio do caminho que falta um comando deixaria os cursos
#    criados e as matriculas sem apontar, que e a meia-instalacao mais dificil
#    de enxergar: tudo parece pronto e nao esta.
# -----------------------------------------------------------------------------
echo "== 1/5: conferindo a maquina =="

cd "$RAIZ" 2>/dev/null || parar "nao achei $RAIZ. Voce esta na VPS certa? (o prompt tem de comecar com deploy@srv… ou root@srv…, nunca PS C:\\>)"
[ -f docker-compose.yml ] || parar "nao achei docker-compose.yml em $RAIZ."
command -v docker >/dev/null 2>&1 || parar "nao achei o docker nesta maquina. Nada foi alterado."
docker compose ps >/dev/null 2>&1 || parar "nao consegui falar com o Docker Compose aqui. Nada foi alterado."

for SERVICO in catalogo alunos cursos; do
  docker compose config --services 2>/dev/null | grep -qx "$SERVICO" \
    || parar "o servico '$SERVICO' nao esta no docker-compose.yml desta maquina. Nada foi alterado."
done

# Os dois comandos chegam por deploy, cada um da sua celula. Se um deles ainda
# nao chegou, a metade que rodasse deixaria o trabalho pela metade em silencio.
docker compose exec -T catalogo python manage.py help criar_curso >/dev/null 2>&1 \
  || parar "a celula 'catalogo' desta maquina ainda nao conhece o comando criar_curso. Ele viaja no deploy: espere o deploy do catalogo terminar (alguns minutos) e rode este script de novo. Nada foi alterado."
docker compose exec -T alunos python manage.py help apontar_o_curso_das_matriculas >/dev/null 2>&1 \
  || parar "a celula 'alunos' desta maquina ainda nao conhece o comando apontar_o_curso_das_matriculas. Ele viaja no deploy: espere o deploy dos alunos terminar (alguns minutos) e rode este script de novo. Nada foi alterado."
docker compose exec -T cursos python manage.py help apontar_o_produto_do_curso >/dev/null 2>&1 \
  || parar "a celula 'cursos' desta maquina ainda nao conhece o comando apontar_o_produto_do_curso. Ele viaja no deploy: espere o deploy da sala de aula terminar (alguns minutos) e rode este script de novo. Nada foi alterado."

# -----------------------------------------------------------------------------
# 2. QUAL ESCOLA. Sem isso, o passo 4 escreveria o curso de uma escola nas
#    matriculas de outra, e essa e a unica coisa aqui que nao tem desfazer.
# -----------------------------------------------------------------------------
echo "== 2/5: descobrindo de qual escola sao as matriculas =="

SITE="${SITE:-}"
if [ -z "$SITE" ]; then
  SITES="$(docker compose exec -T catalogo python manage.py shell -c "
from apps.sites.models import Site
for s in Site.objects.filter(active=True).order_by('host'):
    print(f'{s.id} {s.host}')
" 2>/dev/null | tr -d '\r' | grep -E '^[0-9a-f-]{36} ')"

  QUANTOS="$(printf '%s\n' "$SITES" | grep -c . )"

  # Zero tem causa e conserto DIFERENTES de dois, e por isso mensagem propria:
  # mandar escolher de uma lista vazia nao diz o que fazer, e essa e a metade
  # que so aparece quando se roda a recusa em vez de imagina-la.
  [ "$QUANTOS" = "0" ] && parar "o catalogo desta maquina nao tem nenhum site ativo, entao nao existe escola cujas matriculas apontar. Ou o catalogo ainda nao foi semeado, ou o site esta desativado. Confira em https://meshcraft.top/admin/ e rode de novo. Nada foi alterado."

  [ "$QUANTOS" = "1" ] || parar "esta maquina tem $QUANTOS sites ativos, e eu nao adivinho de qual escola sao as matriculas. Rode de novo dizendo qual, assim:

$(printf '%s\n' "$SITES" | sed 's/^/    /')

    SITE=<o codigo da esquerda> bash /tmp/cursos.sh

Nada foi alterado."

  SITE="$(printf '%s\n' "$SITES" | cut -d' ' -f1)"
  HOST="$(printf '%s\n' "$SITES" | cut -d' ' -f2)"
  echo "   a escola e: $HOST"
else
  echo "   voce disse qual escola: $SITE"
fi
[ -n "$SITE" ] || parar "nao consegui descobrir o codigo da escola. Nada foi alterado."

# -----------------------------------------------------------------------------
# 3. OS DOIS CURSOS.
# -----------------------------------------------------------------------------
echo
echo "== 3/5: cadastrando os dois cursos =="

docker compose exec -T catalogo python manage.py criar_curso "$APELIDO_1" "$NOME_1" \
  || parar "nao consegui cadastrar o curso '$NOME_1'. A mensagem acima diz o que houve. Nada mais foi alterado."
docker compose exec -T catalogo python manage.py criar_curso "$APELIDO_2" "$NOME_2" \
  || parar "nao consegui cadastrar o curso '$NOME_2'. O curso '$NOME_1' JA FOI cadastrado e nao precisa ser refeito: rode este script de novo depois de resolver a mensagem acima."

CURSO_1="$(docker compose exec -T catalogo python manage.py shell -c "
from apps.produtos.models import Product
print(Product.objects.get(slug='$APELIDO_1').id)
" 2>/dev/null | tr -d '\r' | grep -E '^[0-9a-f-]{36}$')"

[ -n "$CURSO_1" ] || parar "cadastrei os cursos mas nao consegui reler o codigo do '$NOME_1' para apontar as matriculas. Os cursos ESTAO criados; rode este script de novo, que ele retoma daqui. Nenhuma matricula foi alterada."

CURSO_2="$(docker compose exec -T catalogo python manage.py shell -c "
from apps.produtos.models import Product
print(Product.objects.get(slug='$APELIDO_2').id)
" 2>/dev/null | tr -d '\r' | grep -E '^[0-9a-f-]{36}$')"

[ -n "$CURSO_2" ] || parar "cadastrei os cursos mas nao consegui reler o codigo do '$NOME_2' para ligar a sala de aula a ele. Os cursos ESTAO criados; rode este script de novo, que ele retoma daqui. Nenhuma matricula foi alterada."

# -----------------------------------------------------------------------------
# 4. AS MATRICULAS QUE JA EXISTEM.
#
#    Primeiro sem escrever, para o numero aparecer na tela ANTES de virar fato.
#    Depois de verdade. As duas saidas ficam visiveis, e por isso da para
#    conferir que o numero aplicado e o numero anunciado.
# -----------------------------------------------------------------------------
echo
echo "== 4/5: ligando a sala de aula ao curso do livro =="
echo
echo "   Sem esta ligacao a sala nao sabe de qual curso a pessoa e aluna, e"
echo "   por seguranca ela nao deixa ninguem entrar."
docker compose exec -T cursos python manage.py apontar_o_produto_do_curso --site "$SITE" --curso "$APELIDO_2" --produto "$CURSO_2" \
  || parar "nao consegui ligar a sala de aula ao curso '$NOME_2'. A mensagem acima diz o que houve. Os dois cursos ESTAO cadastrados e NENHUMA matricula foi alterada: rode este script de novo depois de resolver."

echo
echo "== 5/5: apontando as matriculas de hoje para '$NOME_1' =="
echo
echo "-- primeiro so olhando, sem escrever nada --"
docker compose exec -T alunos python manage.py apontar_o_curso_das_matriculas --site "$SITE" --curso "$CURSO_1" \
  || parar "a conferencia falhou e por isso eu nao escrevi nada. A mensagem acima diz o que houve. Os dois cursos ESTAO cadastrados; nenhuma matricula foi alterada."

echo
echo "-- agora escrevendo --"
docker compose exec -T alunos python manage.py apontar_o_curso_das_matriculas --site "$SITE" --curso "$CURSO_1" --confirmar \
  || parar "a escrita falhou. A mensagem acima diz o que houve, e o comando so escreve tudo ou nada. Rode este script de novo depois de resolver."

echo
echo "== PRONTO =="
echo
echo "Os dois cursos existem, e todo aluno que ja estava no site agora esta"
echo "matriculado em '$NOME_1'."
echo
echo "Rodar este script de novo e seguro e nao muda mais nada."
echo
echo "A sala de aula ja sabe que /cursos/$APELIDO_2/ e o curso '$NOME_2', e"
echo "so deixa entrar quem esta matriculado NELE."
echo
echo "O curso do livro ainda nao tem nenhum aluno, e e o proximo passo: voce"
echo "escolhe esse curso na hora de liberar alguem, em"
echo "https://meshcraft.top/admin/escola/alunos/"
