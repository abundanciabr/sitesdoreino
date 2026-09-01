#!/usr/bin/env bash
# =============================================================================
# QUEM É DA EQUIPE DA ESCOLA — o passo do mantenedor para abrir a fila de marcos.
#
# A fila de validação (`/conquistas/interno`) é onde a equipe confere as provas
# que os alunos mandam de um marco real. Ela é FAIL-CLOSED por desenho: sem uma
# lista de pessoas no env da célula, ninguém entra — nem o mantenedor.
#
# Por que este passo é seu e não da esteira: a lista é de IDS DE PESSOAS REAIS,
# que só existem no banco de produção, e env de produção não viaja pelo Git
# (INV-P8, Lei 5; o `deploy-infra.yml` diz de si mesmo que JAMAIS toca
# `infra/env/` nem `/opt/plataforma/env/`).
#
# COMO RODAR (dentro da VPS, uma linha só, com o e-mail de quem entra na lista):
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-equipe-da-gamificacao.sh -o /tmp/e.sh && bash /tmp/e.sh seu-email@exemplo.com
#
# Pode passar mais de um e-mail, separados por espaço. Rodar de novo ACRESCENTA
# quem faltava e não remove ninguém — tirar alguém da equipe é editar o env à
# mão, de propósito: um script que remove é um script que remove errado numa
# madrugada.
#
# O QUE ELE FAZ, e só isto:
#   1. traduz cada e-mail no id opaco da pessoa, PERGUNTANDO À `identidade`
#      (que é quem sabe), nunca inventando;
#   2. escreve `IDS_DA_EQUIPE` em `env/gamificacao.env`;
#   3. reinicia a célula `gamificacao` e CONFERE que ela voltou.
#
# NÃO cria segredo, não mexe em outra célula, não liga regra de economia
# nenhuma e não concede conquista a ninguém.
#
# SE NADA FOR RODADO: a fila abre e diz, em português, que a pessoa não está na
# lista. Nada quebra, e o aluno continua podendo mandar a prova — ela fica
# esperando na fila até alguém poder olhar.
# =============================================================================

# O modo de falha de 24/08 em pessoa: carregado com `source`/`.`, um `exit` daqui
# derrubaria a sessão do mantenedor. Com `bash /tmp/e.sh` o exit morre no filho.
if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU POR SEGURANÇA: este arquivo foi carregado com 'source' (ou '.'), e assim um erro derrubaria a sua sessão. Rode com a palavra bash na frente: bash /tmp/e.sh seu-email@exemplo.com"
  return 1 2>/dev/null || exit 1
fi

set -u

parar() { echo "PAROU POR SEGURANÇA: $1"; exit 1; }

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
ENV_GAMIFICACAO="env/gamificacao.env"
CHAVE="IDS_DA_EQUIPE"

# -----------------------------------------------------------------------------
# 1. ONDE, e COM QUEM — tudo conferido ANTES de escrever coisa nenhuma.
# -----------------------------------------------------------------------------
[ "$#" -ge 1 ] || parar "faltou dizer QUEM entra na equipe. Rode assim: bash /tmp/e.sh seu-email@exemplo.com"

cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ — você está na VPS certa? (o prompt tem de começar com deploy@srv… ou root@srv…)"
[ -f "$ENV_GAMIFICACAO" ] || parar "não achei $RAIZ/$ENV_GAMIFICACAO — a célula gamificacao não está provisionada nesta máquina. Nada foi alterado."
[ -w "$ENV_GAMIFICACAO" ] || parar "não consigo escrever em $RAIZ/$ENV_GAMIFICACAO — rode como root ou como o dono dos env. Nada foi alterado."

docker compose ps identidade >/dev/null 2>&1 || parar "não consegui falar com o docker compose desta máquina. Nada foi alterado."

ler_de() {  # arquivo, chave — devolve o valor limpo, sem comentário nem espaços
  grep "^$2=" "$1" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' | tr -d '[:space:]'
}

# -----------------------------------------------------------------------------
# 2. A TRADUÇÃO — o id vem da `identidade`, e a ausência de resposta PARA o
#    script. Um id inventado entraria na lista e abriria a fila para ninguém,
#    sem erro em lugar nenhum: a falha silenciosa que este bloco existe para
#    impedir.
#
#    O e-mail viaja por VARIÁVEL DE AMBIENTE, nunca costurado dentro do código
#    Python: texto de fora interpolado em código é a família da `armadilhas/047`.
# -----------------------------------------------------------------------------
ATUAL="$(ler_de "$ENV_GAMIFICACAO" "$CHAVE")"
NOVOS=""
JA_ESTAVAM=""

echo "== traduzindo e-mail em id, perguntando à identidade =="
for EMAIL in "$@"; do
  case "$EMAIL" in
    *@*.*) : ;;
    *) parar "'$EMAIL' não parece um e-mail. Nada foi alterado." ;;
  esac

  ID="$(docker compose exec -T -e EMAIL_PROCURADO="$EMAIL" identidade \
        python manage.py shell -c \
        'import os
from apps.identidade.models import Identidade
achado = Identidade.objects.filter(email__iexact=os.environ["EMAIL_PROCURADO"]).values_list("id", flat=True).first()
print(achado or "")' 2>/dev/null | tr -d '[:space:]')"

  [ -n "$ID" ] || parar "a identidade não conhece '$EMAIL'. Essa pessoa já entrou no site alguma vez? Nada foi alterado."

  case ",$ATUAL,$NOVOS," in
    *",$ID,"*) JA_ESTAVAM="$JA_ESTAVAM $EMAIL"; printf '  %-34s %s\n' "$EMAIL" "já estava na lista" ;;
    *) NOVOS="$NOVOS,$ID"; printf '  %-34s %s\n' "$EMAIL" "id encontrado, vai entrar" ;;
  esac
done

if [ -z "$NOVOS" ]; then
  echo
  echo "PRONTO: ninguém novo a acrescentar.$JA_ESTAVAM já podia abrir a fila."
  echo "A fila da equipe fica em https://meshcraft.top/conquistas/interno"
  exit 0
fi

# Vírgula-e-vazio no começo some; a lista final nunca começa nem termina com
# vírgula, porque um item vazio casaria com um id vazio na leitura.
LISTA="$(printf '%s%s' "$ATUAL" "$NOVOS" | sed 's/^,*//; s/,,*/,/g; s/,*$//')"
[ -n "$LISTA" ] || parar "a lista final ficou vazia, o que não pode acontecer. Nada foi alterado."

echo
echo "== estado ANTES =="
printf '  %-24s %s\n' "$ENV_GAMIFICACAO" "encontrado ($(wc -l < "$ENV_GAMIFICACAO") linhas)"
printf '  %-24s %s\n' "$CHAVE" "${ATUAL:-vazia (ninguém abre a fila hoje)}"
echo

# -----------------------------------------------------------------------------
# 3. ESCRITA — com cópia de segurança, e com dono e modo copiados do próprio
#    arquivo. Rodando como root, uma edição pode deixar o env root:root, e o
#    usuário `deploy` (que é quem o pipeline usa) não lê um 600 de root
#    (`armadilhas/091`).
# -----------------------------------------------------------------------------
DONO_ANTES="$(stat -c '%U:%G %a' "$ENV_GAMIFICACAO" 2>/dev/null)"
COPIA="$ENV_GAMIFICACAO.bak-$(date +%s)"
cp -a "$ENV_GAMIFICACAO" "$COPIA" 2>/dev/null || parar "não consegui guardar a cópia de segurança. Não mexi em nada."

if grep -q "^$CHAVE=" "$ENV_GAMIFICACAO"; then
  sed -i "s|^$CHAVE=.*|$CHAVE=$LISTA|" "$ENV_GAMIFICACAO" \
    || parar "a edição falhou. A cópia intacta está em $RAIZ/$COPIA."
else
  # Sem esta guarda, um arquivo que não termina em quebra de linha grudaria a
  # chave nova no fim da última linha — e a última linha de um env é um valor.
  if [ -s "$ENV_GAMIFICACAO" ] && [ "$(tail -c 1 "$ENV_GAMIFICACAO" | wc -l)" -eq 0 ]; then
    printf '\n' >> "$ENV_GAMIFICACAO" || parar "não consegui escrever. A cópia intacta está em $RAIZ/$COPIA."
  fi
  {
    printf '\n# Quem é da EQUIPE da escola e pode decidir um pedido de validação.\n'
    printf '# Escrito por infra/provisionar-equipe-da-gamificacao.sh. Lista vazia = ninguém.\n'
    printf '%s=%s\n' "$CHAVE" "$LISTA"
  } >> "$ENV_GAMIFICACAO" || parar "não consegui escrever. A cópia intacta está em $RAIZ/$COPIA."
fi

DONO_DEPOIS="$(stat -c '%U:%G %a' "$ENV_GAMIFICACAO" 2>/dev/null)"
if [ "$DONO_ANTES" != "$DONO_DEPOIS" ]; then
  chown "${DONO_ANTES%% *}" "$ENV_GAMIFICACAO" 2>/dev/null
  chmod "${DONO_ANTES##* }" "$ENV_GAMIFICACAO" 2>/dev/null
fi

GRAVADO="$(ler_de "$ENV_GAMIFICACAO" "$CHAVE")"
[ "$GRAVADO" = "$LISTA" ] || parar "escrevi e o arquivo não confirma o valor. A cópia intacta está em $RAIZ/$COPIA."

# -----------------------------------------------------------------------------
# 4. O REINÍCIO, e a PROVA de que ele deu certo.
#
#    Perguntar `docker compose up -d` se deu certo pelo `$?` de um pipe é o
#    falso-verde de ARMADILHAS §5.10, que já fez este projeto anunciar PRONTO com
#    o reinício falhando. Aqui a prova é o estado do contêiner DEPOIS, lido à
#    parte.
# -----------------------------------------------------------------------------
echo "== reiniciando a gamificacao para ela ler a lista =="
docker compose up -d gamificacao >/dev/null 2>&1

PRONTA=""
for _ in $(seq 1 30); do
  ESTADO="$(docker compose ps --format '{{.Service}} {{.State}}' 2>/dev/null | grep '^gamificacao ' | head -1)"
  case "$ESTADO" in
    *running*) PRONTA="sim"; break ;;
  esac
  sleep 2
done
[ -n "$PRONTA" ] || parar "a gamificacao não voltou de pé depois do reinício. A cópia intacta do env está em $RAIZ/$COPIA, e 'docker compose logs gamificacao' diz o motivo."

QUANTOS="$(printf '%s' "$LISTA" | tr ',' '\n' | grep -c .)"
echo
echo "PRONTO: a equipe da escola tem $QUANTOS pessoa(s) que podem conferir marcos."
echo "A fila fica em https://meshcraft.top/conquistas/interno"
echo "Cópia de segurança do env em $RAIZ/$COPIA (pode apagar quando quiser)."
