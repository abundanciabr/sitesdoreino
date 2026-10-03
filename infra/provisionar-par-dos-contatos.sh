#!/usr/bin/env bash
# Liga a tela de contatos do admin à API interna da leads.
# Rode na VPS, uma linha só, depois da aplicação com o CRM estar publicada:
#   curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-par-dos-contatos.sh -o /tmp/p.sh && bash /tmp/p.sh
#
# O par é admin→leads: a leads aceita TOKENS_ACEITOS_ADMIN e o admin envia
# LEADS_API_TOKEN. O endereço interno vem do contrato da API: não usa a borda.
# Tokens iguais já presentes são reaproveitados; tokens divergentes param sem
# editar os envs. Se nenhum existe, o segredo nasce na VPS e nunca é exibido.
set -u

if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU: rode este arquivo com bash, sem carregá-lo com source."
  return 1 2>/dev/null || exit 1
fi
if [ -z "${BASH_VERSION:-}" ]; then
  echo "PAROU: rode este arquivo com bash."
  exit 1
fi

FONTE_OPERACAO="${PLATAFORMA_DIR:-/opt/plataforma}/codigo/ferramentas/atual/infra/operacao-aplicacao.sh"
[ -f "$FONTE_OPERACAO" ] || FONTE_OPERACAO="$(dirname "${BASH_SOURCE[0]}")/operacao-aplicacao.sh"
[ -f "$FONTE_OPERACAO" ] || { echo "PAROU: não achei as operações da aplicação. Nada foi alterado."; exit 1; }
. "$FONTE_OPERACAO" || { echo "PAROU: não consegui carregar as operações da aplicação. Nada foi alterado."; exit 1; }

parar() { echo "PAROU: $1"; exit 1; }

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
ENV_LEADS="env/leads.env"
ENV_ADMIN="env/admin.env"
LEADS_URL="http://leads:8000/api/leads"

cd "$RAIZ" 2>/dev/null || parar "não achei $RAIZ; rode na VPS da plataforma."
for arquivo in "$ENV_LEADS" "$ENV_ADMIN"; do
  [ -f "$arquivo" ] || parar "não achei $RAIZ/$arquivo; provisione as duas células antes. Nada foi alterado."
  [ -w "$arquivo" ] || parar "não consigo escrever em $RAIZ/$arquivo. Nada foi alterado."
done

ler_de() {
  grep "^$2=" "$1" 2>/dev/null | head -1 | cut -d= -f2- \
    | sed 's/[[:space:]]*#.*$//' | tr -d '[:space:]'
}

quantidade() { grep -c "^$2=" "$1" 2>/dev/null || true; }

for par in "$ENV_LEADS:TOKENS_ACEITOS_ADMIN" "$ENV_ADMIN:LEADS_API_TOKEN" "$ENV_ADMIN:LEADS_API_URL"; do
  arquivo="${par%%:*}"
  chave="${par##*:}"
  n="$(quantidade "$arquivo" "$chave")"
  [ "$n" -le 1 ] || parar "$chave aparece mais de uma vez em $arquivo. Nada foi alterado."
done

# Nunca escolher um lado e sobrescrever o outro: isso rotacionaria credencial
# que pode estar em uso. Um único valor existente é a fonte para os dois lados.
T_LEADS="$(ler_de "$ENV_LEADS" TOKENS_ACEITOS_ADMIN)"
T_ADMIN="$(ler_de "$ENV_ADMIN" LEADS_API_TOKEN)"
if [ -n "$T_LEADS" ] && [ -n "$T_ADMIN" ] && [ "$T_LEADS" != "$T_ADMIN" ]; then
  parar "os tokens atuais do par admin→leads divergem. Nada foi alterado; alinhe a causa sem rotacionar credenciais em uso."
fi
TOKEN="${T_LEADS:-$T_ADMIN}"
NOVO=0
if [ -z "$TOKEN" ]; then
  command -v openssl >/dev/null 2>&1 || parar "openssl não está disponível para gerar o primeiro segredo. Nada foi alterado."
  TOKEN="$(openssl rand -hex 32)" || parar "não consegui gerar o segredo. Nada foi alterado."
  NOVO=1
fi
[ "${#TOKEN}" -ge 32 ] || parar "o token existente do par é curto demais. Nada foi alterado."

# Um token de outro consumidor também não pode abrir esta API por acidente.
for chave in $(grep -oE '^TOKENS_ACEITOS_[A-Z0-9_]+=' "$ENV_LEADS" 2>/dev/null | tr -d '='); do
  [ "$chave" = TOKENS_ACEITOS_ADMIN ] && continue
  [ "$(ler_de "$ENV_LEADS" "$chave")" != "$TOKEN" ] \
    || parar "o token admin→leads também está registrado como $chave em $ENV_LEADS. Nada foi alterado."
done
for chave in $(grep -oE '^[A-Z][A-Z0-9_]*_API_TOKEN=' "$ENV_ADMIN" 2>/dev/null | tr -d '='); do
  [ "$chave" = LEADS_API_TOKEN ] && continue
  [ "$(ler_de "$ENV_ADMIN" "$chave")" != "$TOKEN" ] \
    || parar "o token admin→leads também está usado por $chave em $ENV_ADMIN. Nada foi alterado."
done

echo "== estado ANTES =="
echo "  env/leads.env ............ encontrado"
echo "  env/admin.env ............ encontrado"
if [ "$NOVO" -eq 1 ]; then
  echo "  segredo .................. primeiro valor; será criado na VPS"
else
  echo "  segredo .................. valor existente será preservado"
fi

MEXIDOS=""
BACKUPS=""
garantir() {
  arquivo="$1"; chave="$2"; valor="$3"; cabecalho="$4"
  atual="$(ler_de "$arquivo" "$chave")"
  [ "$atual" = "$valor" ] && return 0

  backup="$arquivo.bak-$(date +%s)"
  [ ! -e "$backup" ] || backup="$arquivo.bak-$(date +%s)-$$"
  cp -a "$arquivo" "$backup" 2>/dev/null \
    || parar "não consegui guardar cópia de $arquivo. Nada foi alterado."
  BACKUPS="$BACKUPS $backup"

  if [ "$(quantidade "$arquivo" "$chave")" -eq 1 ]; then
    sed -i "s|^$chave=.*|$chave=$valor|" "$arquivo" \
      || parar "a edição de $arquivo falhou; cópias intactas: $BACKUPS."
  else
    if [ -s "$arquivo" ] && [ "$(tail -c 1 "$arquivo" | wc -l)" -eq 0 ]; then
      printf '\n' >> "$arquivo" || parar "não consegui editar $arquivo; cópias intactas: $BACKUPS."
    fi
    if ! grep -q "^# $cabecalho" "$arquivo"; then
      printf '\n# %s\n# Escrito por infra/provisionar-par-dos-contatos.sh.\n' "$cabecalho" >> "$arquivo" \
        || parar "não consegui editar $arquivo; cópias intactas: $BACKUPS."
    fi
    printf '%s=%s\n' "$chave" "$valor" >> "$arquivo" \
      || parar "não consegui editar $arquivo; cópias intactas: $BACKUPS."
  fi

  # sed -i pode recriar o arquivo; restaura exatamente dono e modo da cópia.
  chown --reference="$backup" "$arquivo" 2>/dev/null \
    || parar "não consegui preservar o dono de $arquivo; cópia intacta: $backup."
  chmod --reference="$backup" "$arquivo" 2>/dev/null \
    || parar "não consegui preservar as permissões de $arquivo; cópia intacta: $backup."
  case " $MEXIDOS " in *" $arquivo "*) : ;; *) MEXIDOS="$MEXIDOS $arquivo" ;; esac
}

# O provedor aceita primeiro; só então o consumidor começa a enviar o token.
garantir "$ENV_LEADS" TOKENS_ACEITOS_ADMIN "$TOKEN" "par admin→leads: a leads aceita a consulta de contatos"
garantir "$ENV_ADMIN" LEADS_API_URL "$LEADS_URL" "par admin→leads"
garantir "$ENV_ADMIN" LEADS_API_TOKEN "$TOKEN" "par admin→leads"

echo "== estado DEPOIS =="
if [ -z "$MEXIDOS" ]; then
  echo "  arquivos ................. já estavam ligados"
else
  echo "  arquivos alterados .......$MEXIDOS"
  echo "  cópias de segurança ......$BACKUPS"
fi
ACEITO="$(ler_de "$ENV_LEADS" TOKENS_ACEITOS_ADMIN)"
ENVIADO="$(ler_de "$ENV_ADMIN" LEADS_API_TOKEN)"
[ -n "$ACEITO" ] && [ "$ACEITO" = "$ENVIADO" ] && [ "$ACEITO" = "$TOKEN" ] \
  || parar "o par admin→leads não confere; cópias intactas: $BACKUPS."
[ "$(ler_de "$ENV_ADMIN" LEADS_API_URL)" = "$LEADS_URL" ] \
  || parar "LEADS_API_URL não ficou no endereço interno previsto; cópias intactas: $BACKUPS."
for par in "$ENV_LEADS:TOKENS_ACEITOS_ADMIN" "$ENV_ADMIN:LEADS_API_TOKEN" "$ENV_ADMIN:LEADS_API_URL"; do
  arquivo="${par%%:*}"; chave="${par##*:}"
  [ "$(quantidade "$arquivo" "$chave")" -eq 1 ] \
    || parar "$chave não aparece uma única vez em $arquivo; cópias intactas: $BACKUPS."
done
echo "  par e endereço ........... conferem"

echo "== recarregando a aplicação =="
recarregar_servicos "provisionar-par-dos-contatos.sh" \
  || parar "os env conferem, mas a aplicação não passou na prova; rode novamente depois de corrigir a falha."
echo "PRONTO: a tela de contatos pode consultar a leads."
