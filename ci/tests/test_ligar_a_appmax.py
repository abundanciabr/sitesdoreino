"""O roteiro que LIGA a Appmax, EXECUTADO, não lido.

`infra/ligar-a-appmax.sh` grava no `env/pagamentos.env` da VPS quem é o nosso
aplicativo na Appmax e o par de credenciais dele, e recarrega a célula. Ele roda
**na máquina do mantenedor**, com uma linha só, e um erro ali custa o pior tipo
de tempo que este projeto tem: o dele, no terminal, sem saber o que fazer com a
tela.

Por isso este guarda **roda o roteiro de verdade**, contra uma plataforma de
mentira em `tmp_path`, com um `docker` e um `curl` de mentira no `PATH`, em vez
de afirmar coisas sobre o texto dele. É irmão de `test_por_a_chave_da_ia.py`, e
mede as promessas que o mantenedor não tem como conferir sozinho:

1. **O segredo NUNCA aparece na tela nem na linha de comando** (`armadilhas/090`).
   É a promessa que dá nome ao roteiro.
2. **Fail closed ANTES de perguntar.** Sem o env da célula, sem docker ou sem o
   catálogo respondendo, ele para sem ter pedido segredo nenhum: descobrir
   depois faria o mantenedor colar credencial à toa, e credencial colada à toa
   é como uma credencial acaba num lugar errado.
3. **O site vem do catálogo, não do teclado.** `APPMAX_INSTALACOES` leva o
   `site_id` interno, um UUID que o mantenedor não tem como saber de cabeça. O
   OAuth MERCHANT é validado por um transporte falso e não envia requisições
   externas nem exibe as credenciais.
4. **Cópia de segurança antes de qualquer edição**, e o resto do env sobrevive
   inteiro (`armadilhas/111`).
5. **Rodar de novo TROCA, nunca duplica.** Duas linhas da mesma chave no mesmo
   env fazem o valor depender da ordem de leitura.

[INV-CI01]: sem `bash` nesta máquina o guarda não tem o que medir, e isso é
ERRO, nunca um OK silencioso.
"""

from __future__ import annotations

import http.server
import json
import os
import shutil
import subprocess
import textwrap
import threading
import uuid
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "infra" / "ligar-a-appmax.sh"
EXEMPLO = RAIZ / "infra" / "env" / "pagamentos.env.exemplo"

# O site como o catálogo o devolve: o UUID é o `site_id` interno, e é ele que
# precisa entrar no env. O host nunca entra.
SITE_ID = "8f14e45f-ceea-467a-9d3b-c2a6f4b71d02"
SITE_HOST = "meshcraft.top"
SITE_NOME = "Meshcraft"

APP_ID = "1888"
CLIENT_ID = "app-client-de-mentira-0001"
SEGREDO = "s3gr3d0-de-mentira-que-nao-pode-aparecer-na-tela"
MERCHANT_CLIENT_ID = "merchant-client-de-mentira-0001"
MERCHANT_SECRET = "merchant-secret-de-mentira-que-nao-pode-aparecer"
AUTH_URL = "https://auth.sandboxappmax.com.br/oauth2/token"
API_URL = "https://api.sandboxappmax.com.br"

# O env da célula como o provisionamento o escreve, ANTES desta entrega.
PAGAMENTOS_ENV = (
    "DJANGO_SECRET_KEY=x\n"
    "DATABASE_URL=postgres://pagamentos_user:senha@postgres:5432/pagamentos_db\n"
    "MP_ACCESS_TOKEN=TEST-nao-e-para-mexer\n"
    "REDIS_STREAMS_URL=redis://redis:6379/0\n"
    "APPMAX_CARD_ENABLED_SITES=\n"
)

# Compose interpola o arquivo inteiro antes de executar qualquer subcomando.
# Estes dois marcadores falsos permitem provar o caminho sem ler segredos reais.
ADMIN_ENV = "ALUNOS_API_TOKEN=token-alunos-falso\nTOKEN_CATALOGO=token-catalogo-falso\n"

# As respostas do teclado, na ordem em que o roteiro pergunta.
RESPOSTAS = f"{APP_ID}\n{SITE_NOME}\n{CLIENT_ID}\n{SEGREDO}\n"


def _bash() -> str:
    caminho = shutil.which("bash")
    assert caminho, (
        "não achei `bash` nesta máquina. Este guarda EXECUTA o roteiro; sem "
        "interpretador ele não tem o que medir, e isso não é um OK ([INV-CI01])."
    )
    return caminho


# O docker de mentira. Sem ele, `docker compose` responderia o que a máquina de
# quem roda a suíte tiver a dizer, e a metade do roteiro que descobre o site,
# recarrega a célula e bate na rota nunca rodaria em teste nenhum. É justamente
# essa metade que roda na VPS do mantenedor.
DOCKER_DE_MENTIRA = r"""#!/usr/bin/env bash
[ "${1:-}" = "compose" ] || exit 0
shift
case "${1:-}" in
  ps)
    [ "${ALUNOS_API_TOKEN:-}" = "token-alunos-falso" ] && [ "${TOKEN_CATALOGO:-}" = "token-catalogo-falso" ] || {
      printf 'required gateway token missing\n' >&2
      exit 78
    }
    [ "${DOCKER_FALSO_PS:-OK}" = "FALHA" ] && {
      printf 'compose interpolation failed\n' >&2
      exit 1
    }
    printf '%s\n' ${DOCKER_FALSO_SERVICOS-catalogo pagamentos}
    exit 0
    ;;
  exec)
    if [ "${DOCKER_FALSO_EXEC:-0}" -ne 0 ]; then
      printf 'compose exec failed\n' >&2
      exit "${DOCKER_FALSO_EXEC}"
    fi
    if [ "${DOCKER_FALSO_ROTACAO_EXEC:-0}" -ne 0 ] && { [ "${3:-}" = "pagamentos" ] || [ "${4:-}" = "pagamentos" ]; }; then
      printf 'compose exec failed after dispatch\n' >&2
      exit "${DOCKER_FALSO_ROTACAO_EXEC}"
    fi
    if [ "${3:-}" = "pagamentos" ] || [ "${4:-}" = "pagamentos" ]; then
      exec python3 "$DOCKER_FALSO_DJANGO" "$@"
    fi
    case "$*" in
      *"print(s.id)"*) printf '%s' "${DOCKER_FALSO_ACTIVE_IDS-}"; exit 0 ;;
    esac
    printf '%s' "${DOCKER_FALSO_SITES-}"
    exit 0
    ;;
  up)
    exit "${DOCKER_FALSO_UP:-0}"
    ;;
esac
exit 0
"""

DJANGO_DE_MENTIRA = r'''import contextlib
import json
import os
import sys
import types
from pathlib import Path

rows = json.loads(os.environ.get("DOCKER_FALSO_DB_ROWS", "[]"))
saved = []
em_transacao = False
bloqueio_solicitado = False

class Instalacao:
    def __init__(self, dados):
        self.__dict__.update(dados)
    def save(self, *, update_fields):
        if not em_transacao:
            raise AssertionError("save sem transaction.atomic")
        self.update_fields = list(update_fields)
        saved.append(self)

objetos = [Instalacao(dados) for dados in rows]

class Gerenciador:
    def select_for_update(self):
        global bloqueio_solicitado
        if not em_transacao:
            raise AssertionError("select_for_update fora de transaction.atomic")
        bloqueio_solicitado = True
        return self
    def filter(self, **filtros):
        if not bloqueio_solicitado:
            raise AssertionError("a instalação não foi bloqueada antes da leitura")
        return [obj for obj in objetos if all(getattr(obj, chave) == valor for chave, valor in filtros.items())]

@contextlib.contextmanager
def atomic():
    global em_transacao
    if em_transacao:
        raise AssertionError("transação aninhada inesperada")
    em_transacao = True
    try:
        yield
    finally:
        em_transacao = False

transaction = types.SimpleNamespace(atomic=atomic)
settings = types.SimpleNamespace(
    APPMAX_INSTALACOES=json.loads(os.environ.get("DOCKER_FALSO_APP_CONFIG", "{}")),
    APPMAX_AUTH_URL=os.environ.get("DOCKER_FALSO_AUTH_URL", "https://auth.sandboxappmax.com.br/oauth2/token"),
    APPMAX_API_URL=os.environ.get("DOCKER_FALSO_API_URL", "https://api.sandboxappmax.com.br"),
    APPMAX_CARD_ENABLED_SITES=os.environ.get("DOCKER_FALSO_SETTING_CARD_ENABLED_SITES", ""),
)
os.environ["APPMAX_CARD_ENABLED_SITES"] = os.environ.get("DOCKER_FALSO_CARD_ENABLED_SITES", "")
django = types.ModuleType("django")
django_conf = types.ModuleType("django.conf")
django_conf.settings = settings
django_db = types.ModuleType("django.db")
django_db.transaction = transaction
sys.modules.update({"django": django, "django.conf": django_conf, "django.db": django_db})
for nome in ("pagamentos", "pagamentos.core"):
    sys.modules[nome] = types.ModuleType(nome)
modelos = types.ModuleType("pagamentos.core.models")
modelos.InstalacaoAppmax = types.SimpleNamespace(objects=Gerenciador())
sys.modules["pagamentos.core.models"] = modelos

argumentos = sys.argv[1:]
codigo = argumentos[argumentos.index("-c") + 1]
estado = {"rows": rows, "saved": []}
exit_code = 0
try:
    exec(compile(codigo, "manage.py shell -c", "exec"), {})
except SystemExit as erro:
    estado["exit"] = erro.code
    exit_code = erro.code if isinstance(erro.code, int) else 1
except Exception as erro:
    estado["exception"] = erro.__class__.__name__
    print("FAKE_DJANGO_EXCEPTION")
    exit_code = 1
finally:
    estado["rows"] = [obj.__dict__ for obj in objetos]
    estado["saved"] = [obj.update_fields for obj in saved]
    Path(os.environ["DOCKER_FALSO_DB_STATE"]).write_text(json.dumps(estado, default=str), encoding="utf-8")
sys.exit(exit_code)
'''

CURL_DE_MENTIRA = r"""#!/usr/bin/env bash
[ "${ALUNOS_API_TOKEN+x}${TOKEN_CATALOGO+x}${VALOR_GATEWAY+x}" = "" ] || exit 9
CONFIG=0
for ARG in "$@"; do [ "$ARG" = "--config" ] && CONFIG=1; done
cat >/dev/null
if [ "$CONFIG" -eq 1 ]; then
  case "${CURL_FALSO_API_RESULT:-OK}" in
    OK) printf '{"data":{"products":[]}}
200' ;;
    HTTP_401) printf '{"message":"unauthorized"}
401' ;;
    HTTP_404) printf '{"message":"not found"}
404' ;;
    FALHA_DE_REDE) exit 7 ;;
    *) printf '{"data":{"products":{}}}
200' ;;
  esac
else
  case "${CURL_FALSO_RESULT:-OK}" in
    OK) printf '{"access_token":"token-de-mentira","token_type":"Bearer","expires_in":604800}
200' ;;
    HTTP_401) printf '{"error":"invalid_client"}
401' ;;
    FALHA_DE_REDE) exit 7 ;;
    TOKEN_SEM_ACCESS) printf '{"token_type":"Bearer","expires_in":604800}
200' ;;
    CREDENCIAL_EXPORTADA) [ "${CLIENT_ID+x}${SEGREDO+x}${OAUTH+x}${VALOR+x}${TEMP+x}${LINHA+x}${linha+x}${saida+x}${valor+x}" = "" ] || exit 8; printf '{"access_token":"token-de-mentira","token_type":"Bearer","expires_in":604800}
200' ;;
    *) printf 'resposta quebrada
200' ;;
  esac
fi
"""


def _plataforma(
    tmp_path: Path,
    *,
    env: str | None = PAGAMENTOS_ENV,
    admin_env: str | None = ADMIN_ENV,
) -> Path:
    """Uma /opt/plataforma de mentira. `env=None` = célula não provisionada."""
    raiz = tmp_path / "plataforma"
    (raiz / "env").mkdir(parents=True, exist_ok=True)
    (raiz / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    if env is not None:
        (raiz / "env" / "pagamentos.env").write_text(env, encoding="utf-8")
    if admin_env is not None:
        (raiz / "env" / "admin.env").write_text(admin_env, encoding="utf-8")
    return raiz


def _ambiente(tmp_path: Path, raiz: Path, **ajustes: str) -> dict:
    """Instala os comandos `docker` e `curl` falsos no ambiente do teste.

    Sem ajuste nenhum, ambos os endpoints sandbox respondem no transporte falso.
    """
    pasta = tmp_path / "binarios-de-mentira"
    pasta.mkdir(exist_ok=True)
    for nome, fonte in (("docker", DOCKER_DE_MENTIRA), ("curl", CURL_DE_MENTIRA)):
        executavel = pasta / nome
        # Bytes, e não `write_text`: num Windows o modo texto trocaria cada
        # quebra de linha por CRLF e o `bash` recusaria o arquivo com "\r:
        # command not found", que é um erro que não se parece com a sua causa.
        executavel.write_bytes(fonte.encode("utf-8"))
        executavel.chmod(0o755)
    fake_django = pasta / "django_falso.py"
    fake_django.write_text(textwrap.dedent(DJANGO_DE_MENTIRA), encoding="utf-8")

    ambiente = dict(
        os.environ,
        PATH=str(pasta) + os.pathsep + os.environ.get("PATH", ""),
        PLATAFORMA_DIR=str(raiz),
        DOCKER_FALSO_SITES=f"{SITE_ID}\t{SITE_HOST}\t{SITE_NOME}\n",
        DOCKER_FALSO_ACTIVE_IDS=f"{SITE_ID}\n",
        CURL_FALSO_RESULT="OK",
        CURL_FALSO_API_RESULT="OK",
        DOCKER_FALSO_DJANGO=str(fake_django),
        DOCKER_FALSO_DB_STATE=str(tmp_path / "django-falso-state.json"),
        DOCKER_FALSO_APP_CONFIG=json.dumps({"1888": {"alias": SITE_NOME, "sites": [SITE_ID]}}),
        DOCKER_FALSO_DB_ROWS=json.dumps([{
            "app_id": "1888",
            "alias": SITE_NOME,
            "platform_site_ids": [SITE_ID],
            "external_id": "00000000-0000-4000-8000-000000000001",
        }]),
    )
    ambiente.update(ajustes)
    return ambiente


def _rodar(
    raiz: Path,
    digitado: str = RESPOSTAS,
    ambiente: dict | None = None,
    args: tuple[str, ...] = (),
) -> subprocess.CompletedProcess:
    """Roda o roteiro com as respostas chegando pelo teclado."""
    if ambiente is None:
        ambiente = _ambiente(raiz.parent, raiz)
    executavel = raiz.parent / "binarios-de-mentira"
    bash = _bash()
    comando = [
        bash,
        "-c",
        'PATH="$1:$PATH"; export PATH; shift; exec "$@"',
        "teste-appmax",
        str(executavel),
        bash,
        str(SCRIPT),
        *args,
    ]
    resultado = subprocess.run(
        comando,
        input=digitado.encode("utf-8"),
        capture_output=True,
        env=ambiente,
    )
    # Bytes preservam LF no pipe em Windows; text=True traduziria as entradas
    # em CRLF, que Bash lê como parte das credenciais invisíveis.
    return subprocess.CompletedProcess(
        resultado.args,
        resultado.returncode,
        resultado.stdout.decode("utf-8", errors="replace"),
        resultado.stderr.decode("utf-8", errors="replace"),
    )


def _valor(raiz: Path, chave: str) -> str | None:
    texto = (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8")
    for linha in texto.splitlines():
        if linha.startswith(chave + "="):
            return linha.split("=", 1)[1]
    return None


def _linhas(raiz: Path, chave: str) -> int:
    texto = (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8")
    return sum(1 for linha in texto.splitlines() if linha.startswith(chave + "="))


def _copias(raiz: Path) -> list[Path]:
    return sorted((raiz / "env").glob("pagamentos.env.bak-*"))


def _env_preparacao(**trocas: str) -> str:
    env = PAGAMENTOS_ENV.replace(
        "APPMAX_CARD_ENABLED_SITES=\n",
        f"APPMAX_AUTH_URL={AUTH_URL}\nAPPMAX_API_URL={API_URL}\nAPPMAX_CARD_ENABLED_SITES=\n",
    )
    for chave, valor in trocas.items():
        linhas = env.splitlines()
        if any(linha.startswith(chave + "=") for linha in linhas):
            env = "\n".join(
                f"{chave}={valor}" if linha.startswith(chave + "=") else linha
                for linha in linhas
            ) + "\n"
        else:
            env += f"{chave}={valor}\n"
    return env


# ---------------------------------------------------------------------------
# 1. A PROMESSA QUE DÁ NOME AO ROTEIRO
# ---------------------------------------------------------------------------


def test_o_segredo_nunca_aparece_na_tela(tmp_path):
    raiz = _plataforma(tmp_path)

    resultado = _rodar(raiz)

    tela = resultado.stdout + resultado.stderr
    assert resultado.returncode == 0, tela
    assert SEGREDO not in tela, (
        "o client_secret apareceu na tela. É por esse caminho que o segredo do "
        "OAuth vazou em 24/08/2026 (`armadilhas/090`): o mantenedor manda o "
        "print para provar que funcionou."
    )
    assert SEGREDO[:20] not in tela, "metade de um segredo ainda é meio segredo"
    assert CLIENT_ID not in tela, "o client_id é metade do par e também é segredo"
    # Mas o roteiro FALA: silêncio total seria indistinguível de travado.
    assert "caracteres" in tela


def test_ele_pergunta_o_par_com_digitacao_invisivel():
    """A leitura invisível é a peça, e um `read` sem `-s` a desfaz sem quebrar nada.

    Este é o único caso deste arquivo que lê o texto em vez de executar, e a
    razão é que o defeito é INVISÍVEL na execução: um `read` sem `-s` funciona
    perfeitamente, grava o valor certo, e só vaza quando há uma pessoa olhando
    a tela. Nenhuma asserção sobre o resultado o pegaria.
    """
    fonte = SCRIPT.read_text(encoding="utf-8")
    assert "read -r -s CLIENT_ID" in fonte
    assert "read -r -s SEGREDO" in fonte


def test_a_recarga_force_recreate_e_mostra_o_erro():
    """Os outros dois defeitos que a execução não pega, e pelo mesmo motivo.

    `up -d` sozinho vê a mesma imagem e a mesma configuração de compose e não
    faz nada: mudança DENTRO do env_file não conta como mudança para ele, e o
    par ficaria no arquivo e fora do processo. E um `>/dev/null 2>&1` na
    recarga apaga a única prova de que a célula caiu (`armadilhas/377`).
    """
    fonte = SCRIPT.read_text(encoding="utf-8")
    recarga = [x for x in fonte.splitlines() if "docker_compose up -d --" in x]
    assert len(recarga) == 2, recarga
    assert all("pagamentos" in x for x in recarga)
    assert "--force-recreate" in recarga[0]
    assert ">/dev/null" not in recarga[0]
    assert "pagamentos" in recarga[0], "recarregar tudo devolveria as outras células à tag :main"


# ---------------------------------------------------------------------------
# 2. FAIL CLOSED, E ANTES DE PEDIR O SEGREDO
# ---------------------------------------------------------------------------


def test_credencial_escrita_na_linha_de_comando_e_recusada(tmp_path):
    """O jeito errado de usar este comando é colar o segredo ao lado do nome
    dele, e é exatamente assim que o segredo do OAuth vazou (`armadilhas/090`)."""
    raiz = _plataforma(tmp_path)
    antes = (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8")

    resultado = subprocess.run(
        [_bash(), str(SCRIPT), SEGREDO],
        input=RESPOSTAS,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_ambiente(tmp_path, raiz),
    )

    assert resultado.returncode != 0
    assert "PAROU POR SEGURANÇA" in (resultado.stdout + resultado.stderr)
    assert (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8") == antes


def test_sem_o_env_da_celula_ele_para_sem_pedir_nada(tmp_path):
    raiz = _plataforma(tmp_path, env=None)

    resultado = _rodar(raiz)

    assert resultado.returncode != 0
    assert "PAROU POR SEGURANÇA" in (resultado.stdout + resultado.stderr)
    # A ordem importa: ele não pode ter pedido o par antes de descobrir.
    assert "client_secret" not in resultado.stdout
    assert not (raiz / "env" / "pagamentos.env").exists()


def test_sem_a_plataforma_ele_para(tmp_path):
    resultado = _rodar(tmp_path / "lugar-nenhum")

    assert resultado.returncode != 0
    assert "PAROU POR SEGURANÇA" in (resultado.stdout + resultado.stderr)


def test_sem_o_catalogo_de_pe_ele_para_sem_pedir_nada(tmp_path):
    """Sem o catálogo não há `site_id`, e sem `site_id` o env sairia pela metade."""
    raiz = _plataforma(tmp_path)
    antes = (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8")
    ambiente = _ambiente(tmp_path, raiz, DOCKER_FALSO_SERVICOS="pagamentos")

    resultado = _rodar(raiz, ambiente=ambiente)

    assert resultado.returncode != 0
    assert "PAROU POR SEGURANÇA" in (resultado.stdout + resultado.stderr)
    assert "client_secret" not in resultado.stdout
    assert "docker compose up -d" not in resultado.stdout
    assert (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8") == antes
    assert _copias(raiz) == [], "guardou cópia de um arquivo que nem chegou a mudar"


@pytest.mark.parametrize(
    "admin_env",
    [
        None,
        "TOKEN_CATALOGO=token-catalogo-falso\n",
        "ALUNOS_API_TOKEN=token-alunos-falso\n",
        "ALUNOS_API_TOKEN=token-alunos-falso\nTOKEN_CATALOGO=\n",
    ],
)
def test_sem_tokens_de_interpolacao_do_compose_para_antes_de_pedir_segredo(tmp_path, admin_env):
    raiz = _plataforma(tmp_path, admin_env=admin_env)
    antes = (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8")

    resultado = _rodar(raiz)
    tela = resultado.stdout + resultado.stderr

    assert resultado.returncode != 0
    assert "ALUNOS_API_TOKEN" in tela or "TOKEN_CATALOGO" in tela
    assert "client_secret" not in tela
    assert "token-alunos-falso" not in tela and "token-catalogo-falso" not in tela
    assert "compose ps" not in tela
    assert (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8") == antes
    assert _copias(raiz) == []


def test_falha_de_ps_nao_vira_servico_ausente_nem_recomenda_reinicio_global(tmp_path):
    raiz = _plataforma(tmp_path)
    ambiente = _ambiente(tmp_path, raiz, DOCKER_FALSO_PS="FALHA")

    resultado = _rodar(raiz, ambiente=ambiente)
    tela = resultado.stdout + resultado.stderr

    assert resultado.returncode != 0
    assert "não consegui consultar" in tela
    assert "não está rodando" not in tela
    assert "docker compose version" in tela
    assert "docker compose ps --services --status running" in tela
    assert "docker compose up -d" not in tela
    assert "token-alunos-falso" not in tela and "token-catalogo-falso" not in tela
    assert "client_secret" not in tela
    assert _copias(raiz) == []


def test_falha_de_ps_no_modo_merchant_para_antes_de_pedir_credenciais(tmp_path):
    raiz = _plataforma(tmp_path)
    assert _rodar(raiz).returncode == 0
    copias_antes = _copias(raiz)
    ambiente = _ambiente(tmp_path, raiz, DOCKER_FALSO_PS="FALHA")

    resultado = _rodar(raiz, ambiente=ambiente, args=("--oauth-merchant",))
    tela = resultado.stdout + resultado.stderr

    assert resultado.returncode != 0
    assert "não consegui consultar" in tela
    assert "MERCHANT sandbox" not in tela
    assert "não está rodando" not in tela
    assert "docker compose up -d" not in tela
    assert MERCHANT_CLIENT_ID not in tela and MERCHANT_SECRET not in tela
    assert _copias(raiz) == copias_antes


def test_tokens_preexportados_sao_substituidos_e_nao_herdados_pelo_curl(tmp_path):
    raiz = _plataforma(tmp_path)
    ambiente = _ambiente(
        tmp_path,
        raiz,
        ALUNOS_API_TOKEN="token-herdado-indevido",
        TOKEN_CATALOGO="catalogo-herdado-indevido",
        VALOR_GATEWAY="buffer-herdado-indevido",
    )

    instalacao = _rodar(raiz, ambiente=ambiente)
    assert instalacao.returncode == 0, instalacao.stdout + instalacao.stderr

    oauth = _rodar(
        raiz,
        digitado=f"{MERCHANT_CLIENT_ID}\n{MERCHANT_SECRET}\n",
        ambiente=ambiente,
        args=("--oauth-merchant",),
    )
    tela = oauth.stdout + oauth.stderr
    assert oauth.returncode == 0, tela
    assert "token-herdado-indevido" not in tela
    assert "catalogo-herdado-indevido" not in tela
    assert "buffer-herdado-indevido" not in tela
    assert _valor(raiz, "APPMAX_MERCHANT_CLIENT_ID") == MERCHANT_CLIENT_ID


def test_lista_valida_sem_catalogo_informa_ausencia_sem_reinicio_global(tmp_path):
    raiz = _plataforma(tmp_path)
    ambiente = _ambiente(tmp_path, raiz, DOCKER_FALSO_SERVICOS="")

    resultado = _rodar(raiz, ambiente=ambiente)
    tela = resultado.stdout + resultado.stderr

    assert resultado.returncode != 0
    assert "não aparece na lista de serviços em execução" in tela
    assert "não consegui consultar" not in tela
    assert "docker compose up -d" not in tela
    assert "client_secret" not in tela
    assert _copias(raiz) == []


def test_catalogo_sem_site_ativo_para_sem_escrever(tmp_path):
    raiz = _plataforma(tmp_path)
    antes = (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8")
    ambiente = _ambiente(tmp_path, raiz, DOCKER_FALSO_SITES="")

    resultado = _rodar(raiz, ambiente=ambiente)
    tela = resultado.stdout + resultado.stderr

    assert resultado.returncode != 0
    assert "NENHUM site ativo" in tela, (
        "parou, mas pelo motivo errado: quem lê precisa saber que o problema é "
        "o catálogo vazio, e não um formato que o roteiro não reconheceu"
    )
    assert (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8") == antes


def test_catalogo_mudo_para_sem_escrever(tmp_path):
    """O catálogo de pé e a pergunta falhando são duas telas diferentes."""
    raiz = _plataforma(tmp_path)
    ambiente = _ambiente(tmp_path, raiz, DOCKER_FALSO_EXEC="1")

    resultado = _rodar(raiz, ambiente=ambiente)

    assert resultado.returncode != 0
    assert "PAROU POR SEGURANÇA" in (resultado.stdout + resultado.stderr)
    assert _valor(raiz, "APPMAX_INSTALACOES") is None


def _com(**trocas: str) -> str:
    """As respostas certas, com uma ou outra trocada pela resposta errada."""
    respostas = {
        "app_id": APP_ID,
        "alias": SITE_NOME,
        "client_id": CLIENT_ID,
        "segredo": SEGREDO,
    }
    respostas.update(trocas)
    return "".join(f"{valor}\n" for valor in respostas.values())


# Cada caso diz também a FRASE que o mantenedor precisa ler. Sem ela o teste
# ficaria verde com a recusa vindo de outro lugar do roteiro, e uma recusa pelo
# motivo errado é uma recusa que ninguém consegue consertar.
@pytest.mark.parametrize(
    "digitado,frase,porque",
    [
        (_com(app_id="meshcraft"), "só números", "o app_id da Appmax é numérico"),
        ("\n" * 4, "não colou o client_id", "campos opcionais vazios deixam o par obrigatório ausente"),
        (_com(client_id=""), "não colou o client_id", "client_id vazio"),
        (_com(segredo=""), "não colou o client_secret", "segredo vazio"),
        (
            _com(alias='Loja "da" esquina'),
            "não pode ter aspas",
            "aspas no alias quebrariam o JSON de APPMAX_INSTALACOES",
        ),
    ],
)
def test_resposta_estranha_e_recusada_e_nada_e_escrito(tmp_path, digitado, frase, porque):
    raiz = _plataforma(tmp_path)
    antes = (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8")

    resultado = _rodar(raiz, digitado=digitado)
    tela = resultado.stdout + resultado.stderr

    assert resultado.returncode != 0, porque
    assert "PAROU POR SEGURANÇA" in tela
    assert frase in tela, f"parou por outro motivo que não {porque}: {tela[-400:]}"
    assert (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8") == antes, (
        "recusou e mesmo assim mexeu no arquivo: " + porque
    )


# ---------------------------------------------------------------------------
# 3. O QUE ELE ESCREVE, E A PORTA ABRINDO NA TELA
# ---------------------------------------------------------------------------


def test_escreve_as_cinco_variaveis_com_o_site_id_do_catalogo(tmp_path):
    raiz = _plataforma(tmp_path)

    resultado = _rodar(raiz)

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert _valor(raiz, "APPMAX_AUTH_URL") == AUTH_URL
    assert _valor(raiz, "APPMAX_API_URL") == API_URL
    assert _valor(raiz, "APPMAX_APP_CLIENT_ID") == CLIENT_ID
    assert _valor(raiz, "APPMAX_APP_CLIENT_SECRET") == SEGREDO

    instalacoes = json.loads(_valor(raiz, "APPMAX_INSTALACOES"))
    assert instalacoes == {APP_ID: {"alias": SITE_NOME, "sites": [SITE_ID]}}, (
        "o valor de `sites` é o site_id INTERNO do catálogo, nunca o host: "
        "`settings.APPMAX_INSTALACOES` compara com platform_site_id."
    )


def test_com_mais_de_um_site_ativo_ele_pergunta_em_vez_de_escolher(tmp_path):
    """Escolher sozinho poria a instalação na escola errada sem nenhuma tela
    quebrar para avisar."""
    raiz = _plataforma(tmp_path)
    outro = "1ff1de77-4005-4fde-a2b6-0f5f2a1c8bd3"
    ambiente = _ambiente(
        tmp_path,
        raiz,
        DOCKER_FALSO_SITES=(
            f"{outro}\toutra-escola.test\tOutra Escola\n"
            f"{SITE_ID}\t{SITE_HOST}\t{SITE_NOME}\n"
        ),
    )

    resultado = _rodar(raiz, digitado=f"{SITE_HOST}\n{RESPOSTAS}", ambiente=ambiente)

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert "outra-escola.test" in resultado.stdout, "não mostrou as opções"
    assert json.loads(_valor(raiz, "APPMAX_INSTALACOES")) == {
        APP_ID: {"alias": SITE_NOME, "sites": [SITE_ID]}
    }


def test_nome_de_loja_vazio_para_em_vez_de_gravar_uma_entrada_descartavel(tmp_path):
    """`settings.APPMAX_INSTALACOES` DESCARTA a entrada sem alias, e a porta
    seguiria recusando sem nada na tela explicando por quê."""
    raiz = _plataforma(tmp_path)
    antes = (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8")
    # O catálogo com o nome do site em branco, e o Enter aceitando esse padrão.
    ambiente = _ambiente(
        tmp_path, raiz, DOCKER_FALSO_SITES=f"{SITE_ID}\t{SITE_HOST}\t\n"
    )

    resultado = _rodar(raiz, digitado=_com(alias=""), ambiente=ambiente)
    tela = resultado.stdout + resultado.stderr

    assert resultado.returncode != 0
    assert "nome da loja ficou vazio" in tela
    assert (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8") == antes


def test_site_escolhido_que_nao_existe_para_sem_escrever(tmp_path):
    raiz = _plataforma(tmp_path)
    antes = (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8")
    ambiente = _ambiente(
        tmp_path,
        raiz,
        DOCKER_FALSO_SITES=(
            f"1ff1de77-4005-4fde-a2b6-0f5f2a1c8bd3\toutra-escola.test\tOutra\n"
            f"{SITE_ID}\t{SITE_HOST}\t{SITE_NOME}\n"
        ),
    )

    resultado = _rodar(raiz, digitado="escola-que-nao-existe.test\n", ambiente=ambiente)

    assert resultado.returncode != 0
    assert "PAROU POR SEGURANÇA" in (resultado.stdout + resultado.stderr)
    assert (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8") == antes


def test_prepara_instalacao_sem_post_publico_ou_declaracao_de_oauth(tmp_path):
    raiz = _plataforma(tmp_path)

    resultado = _rodar(raiz)
    tela = resultado.stdout

    assert resultado.returncode == 0, tela
    assert "CONFIGURAÇÃO DE INSTALAÇÃO PREPARADA" in tela
    assert "não chamou a rota pública" in tela
    assert "não comprova OAuth MERCHANT" in tela
    assert "APPMAX_CARD_ENABLED_SITES" not in tela
    assert SEGREDO not in tela
    fonte = SCRIPT.read_text(encoding="utf-8")
    assert "-X POST" not in fonte
    assert "APPMAX_CARD_ENABLED_SITES" in fonte


def test_recarga_que_falha_para_dizendo_que_o_env_ja_esta_gravado(tmp_path):
    raiz = _plataforma(tmp_path)
    ambiente = _ambiente(tmp_path, raiz, DOCKER_FALSO_UP="1")

    resultado = _rodar(raiz, ambiente=ambiente)
    tela = resultado.stdout + resultado.stderr

    assert resultado.returncode != 0
    assert "PAROU POR SEGURANÇA" in tela
    assert ".bak-" in tela, "não disse onde está a cópia de segurança"
    assert SEGREDO not in tela
    # O env JÁ está certo: mandar colar tudo de novo seria mentira.
    assert _valor(raiz, "APPMAX_APP_CLIENT_SECRET") == SEGREDO

@pytest.mark.parametrize("codigo", ["HTTP_401", "FALHA_DE_REDE", "RESPOSTA_INVALIDA", "TOKEN_SEM_ACCESS"])
def test_oauth_merchante_reprovado_nao_grava_credenciais(tmp_path, codigo):
    raiz = _plataforma(tmp_path)
    assert _rodar(raiz).returncode == 0
    antes = (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8")
    copias_antes = _copias(raiz)
    ambiente = _ambiente(tmp_path, raiz, CURL_FALSO_RESULT=codigo)

    resultado = _rodar(
        raiz,
        digitado=f"{MERCHANT_CLIENT_ID}\n{MERCHANT_SECRET}\n",
        ambiente=ambiente,
        args=("--oauth-merchant",),
    )
    tela = resultado.stdout + resultado.stderr

    assert resultado.returncode != 0
    assert "PAROU POR SEGURANÇA" in tela
    assert MERCHANT_CLIENT_ID not in tela and MERCHANT_SECRET not in tela
    assert (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8") == antes
    assert _copias(raiz) == copias_antes


@pytest.mark.parametrize("codigo", ["HTTP_401", "HTTP_404", "FALHA_DE_REDE", "RESPOSTA_INVALIDA"])
def test_token_sem_escopo_merchant_nao_grava_credenciais(tmp_path, codigo):
    raiz = _plataforma(tmp_path)
    assert _rodar(raiz).returncode == 0
    antes = (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8")
    copias_antes = _copias(raiz)
    ambiente = _ambiente(tmp_path, raiz, CURL_FALSO_API_RESULT=codigo)

    resultado = _rodar(
        raiz,
        digitado=f"{MERCHANT_CLIENT_ID}\n{MERCHANT_SECRET}\n",
        ambiente=ambiente,
        args=("--oauth-merchant",),
    )
    tela = resultado.stdout + resultado.stderr

    assert resultado.returncode != 0
    assert "PAROU POR SEGURANÇA" in tela
    assert "OAuth respondeu" in tela
    assert MERCHANT_CLIENT_ID not in tela and MERCHANT_SECRET not in tela
    assert (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8") == antes
    assert _copias(raiz) == copias_antes


def test_oauth_merchante_sandbox_grava_fora_do_repo_sem_exibir_segredo(tmp_path):
    raiz = _plataforma(tmp_path)
    assert _rodar(raiz).returncode == 0
    ambiente = _ambiente(tmp_path, raiz)

    resultado = _rodar(
        raiz,
        digitado=f"{MERCHANT_CLIENT_ID}\n{MERCHANT_SECRET}\n",
        ambiente=ambiente,
        args=("--oauth-merchant",),
    )
    tela = resultado.stdout + resultado.stderr

    assert resultado.returncode == 0, tela
    assert "OAuth sandbox e leitura de produtos MERCHANT validados" in tela
    assert "token-de-mentira" not in tela
    assert "data" not in tela
    assert MERCHANT_CLIENT_ID not in tela and MERCHANT_SECRET not in tela
    assert _valor(raiz, "APPMAX_MERCHANT_CLIENT_ID") == MERCHANT_CLIENT_ID
    assert _valor(raiz, "APPMAX_MERCHANT_CLIENT_SECRET") == MERCHANT_SECRET
    assert len(_copias(raiz)) == 2


def test_cobranca_habilitada_faz_o_script_parar_antes_de_pedir_segredo(tmp_path):
    # guarda: infra/ligar-a-appmax.sh:138
    env = PAGAMENTOS_ENV.replace("APPMAX_CARD_ENABLED_SITES=\n", "APPMAX_CARD_ENABLED_SITES=site-de-teste\n")
    raiz = _plataforma(tmp_path, env=env)
    antes = (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8")

    resultado = _rodar(raiz)
    tela = resultado.stdout + resultado.stderr

    assert resultado.returncode != 0
    assert "APPMAX_CARD_ENABLED_SITES" in tela
    assert "client_secret" not in tela
    assert (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8") == antes
    assert _copias(raiz) == []


@pytest.mark.parametrize(
    "linha",
    [
        "APPMAX_CARD_ENABLED_SITES = site-a",
        "APPMAX_CARD_ENABLED_SITES: site-a",
        "APPMAX_CARD_ENABLED_SITES=\nAPPMAX_CARD_ENABLED_SITES: site-a",
        "APPMAX_CARD_ENABLED_SITES",
        "APPMAX_CARD_ENABLED_SITES # sem delimitador",
    ],
)
def test_guardia_reconhece_formatos_compose_e_duplicatas_da_trava(tmp_path, linha):
    raiz = _plataforma(tmp_path, env=PAGAMENTOS_ENV + linha + "\n")
    antes = (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8")

    resultado = _rodar(raiz)
    tela = resultado.stdout + resultado.stderr

    assert resultado.returncode != 0
    assert "APPMAX_CARD_ENABLED_SITES" in tela
    assert "client_secret" not in tela
    assert (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8") == antes
    assert _copias(raiz) == []


def test_credenciais_exportadas_pelo_shell_nao_chegam_ao_curl(tmp_path):
    raiz = _plataforma(tmp_path)
    assert _rodar(raiz).returncode == 0
    ambiente = _ambiente(
        tmp_path,
        raiz,
        CURL_FALSO_RESULT="CREDENCIAL_EXPORTADA",
        CLIENT_ID="herdado-id",
        SEGREDO="herdado-segredo",
        OAUTH="herdado-token",
        VALOR="herdado-valor",
        TEMP="herdado-arquivo-env",
        linha="herdado-linha",
        saida="herdado-saida",
        valor="herdado-valor-lowercase",
    )

    resultado = _rodar(
        raiz,
        digitado=f"{MERCHANT_CLIENT_ID}\n{MERCHANT_SECRET}\n",
        ambiente=ambiente,
        args=("--oauth-merchant",),
    )
    tela = resultado.stdout + resultado.stderr

    assert resultado.returncode == 0, tela
    assert "OAuth sandbox e leitura de produtos MERCHANT validados" in tela
    assert "herdado-segredo" not in tela
    assert _valor(raiz, "APPMAX_MERCHANT_CLIENT_ID") == MERCHANT_CLIENT_ID
    assert _valor(raiz, "APPMAX_MERCHANT_CLIENT_SECRET") == MERCHANT_SECRET


# ---------------------------------------------------------------------------
# 4. CÓPIA ANTES, E O RESTO DO ENV INTACTO
# ---------------------------------------------------------------------------


def test_guarda_copia_do_env_antes_de_qualquer_edicao(tmp_path):
    raiz = _plataforma(tmp_path)

    assert _rodar(raiz).returncode == 0

    copias = _copias(raiz)
    assert len(copias) == 1, "a cópia .bak-<epoch> não nasceu"
    assert copias[0].read_text(encoding="utf-8") == PAGAMENTOS_ENV, (
        "a cópia guardou o arquivo DEPOIS da edição, e assim não serve de volta"
    )


def test_o_resto_do_env_sobrevive_inteiro(tmp_path):
    """`armadilhas/111`: variável que some do env é falha silenciosa com deploy
    verde. Este roteiro escreve cinco linhas e não encosta nas outras."""
    raiz = _plataforma(tmp_path)

    assert _rodar(raiz).returncode == 0

    assert _valor(raiz, "DJANGO_SECRET_KEY") == "x"
    assert _valor(raiz, "MP_ACCESS_TOKEN") == "TEST-nao-e-para-mexer"
    assert _valor(raiz, "REDIS_STREAMS_URL") == "redis://redis:6379/0"
    assert _valor(raiz, "APPMAX_CARD_ENABLED_SITES") == "", (
        "a trava do cartão nasce vazia e não é este roteiro que a liga"
    )
    assert _valor(raiz, "DATABASE_URL") == (
        "postgres://pagamentos_user:senha@postgres:5432/pagamentos_db"
    )


def test_configuracao_curl_do_oauth_e_aceita_pelo_curl_real_no_localhost():
    curl = shutil.which("curl")
    if not curl:
        pytest.skip("imagem mínima de CI não inclui curl real para testar a opção --config")

    class RespostaLocal(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"data":{"products":[]}}')

        def log_message(self, *_):
            pass

    servidor = http.server.HTTPServer(("127.0.0.1", 0), RespostaLocal)
    thread = threading.Thread(target=servidor.serve_forever, daemon=True)
    thread.start()
    try:
        endereco = f"http://127.0.0.1:{servidor.server_port}/products"
        configuracao = (
            "silent\nshow-error\nmax-time = 5\n"
            f'url = "{endereco}"\n'
            'header = "Authorization: Bearer token-falso"\n'
            'write-out = "\\n%{http_code}"\n'
        )
        resultado = subprocess.run(
            [curl, "--config", "-"],
            input=configuracao.encode(),
            capture_output=True,
            timeout=10,
            check=False,
        )
    finally:
        servidor.shutdown()
        thread.join(timeout=5)
        servidor.server_close()

    assert resultado.returncode == 0, resultado.stderr.decode(errors="replace")
    assert resultado.stdout.endswith(b"200")
    fonte = SCRIPT.read_text(encoding="utf-8")
    assert 'config = "silent\\nshow-error\\n' in fonte


def test_env_sem_quebra_de_linha_no_fim_nao_gruda_no_ultimo_valor(tmp_path):
    """A última linha de um env é um VALOR, e um `>>` sem a quebra o corromperia
    em silêncio."""
    raiz = _plataforma(tmp_path, env="DJANGO_SECRET_KEY=x\nMP_ACCESS_TOKEN=TEST-a")

    assert _rodar(raiz).returncode == 0

    assert _valor(raiz, "MP_ACCESS_TOKEN") == "TEST-a"
    assert _valor(raiz, "APPMAX_APP_CLIENT_SECRET") == SEGREDO


# ---------------------------------------------------------------------------
# 5. RODAR DE NOVO É O CASO NORMAL
# ---------------------------------------------------------------------------


def test_rodar_de_novo_troca_e_nao_duplica_nenhuma_linha(tmp_path):
    """É como se troca uma credencial revogada."""
    raiz = _plataforma(tmp_path)
    outro = "s3gund0-segredo-de-mentira"

    assert _rodar(raiz).returncode == 0
    segunda = f"{APP_ID}\n{SITE_NOME}\n{CLIENT_ID}\n{outro}\n"
    assert _rodar(raiz, digitado=segunda).returncode == 0

    for chave in (
        "APPMAX_INSTALACOES",
        "APPMAX_AUTH_URL",
        "APPMAX_API_URL",
        "APPMAX_APP_CLIENT_ID",
        "APPMAX_APP_CLIENT_SECRET",
    ):
        assert _linhas(raiz, chave) == 1, f"{chave} duplicou"
    assert _valor(raiz, "APPMAX_APP_CLIENT_SECRET") == outro
    assert len(_copias(raiz)) == 2, "cada execução guarda a sua cópia"


def test_duas_trocas_no_mesmo_segundo_guardam_as_duas_copias(tmp_path):
    """A marca da cópia é o epoch em SEGUNDOS, e o relógio não ajuda o guarda.

    Numa máquina rápida as duas execuções caem no mesmo segundo e a segunda
    cópia sobrescreve a primeira: o env anterior some justamente na hora em que
    ele mais importa, que é a de desfazer uma troca errada. O `date` de mentira
    congela o relógio para que a colisão aconteça sempre, em vez de depender de
    o computador estar com pressa.
    """
    raiz = _plataforma(tmp_path)
    ambiente = _ambiente(tmp_path, raiz)
    congelado = Path(ambiente["PATH"].split(os.pathsep)[0]) / "date"
    congelado.write_bytes(
        b'#!/usr/bin/env bash\n'
        b'if [ "$1" = "+%s" ]; then echo 1700000000; else exec /usr/bin/date "$@"; fi\n'
    )
    congelado.chmod(0o755)

    assert _rodar(raiz, ambiente=ambiente).returncode == 0
    segunda = f"{APP_ID}\n{SITE_NOME}\n{CLIENT_ID}\noutro-segredo\n"
    assert _rodar(raiz, digitado=segunda, ambiente=ambiente).returncode == 0

    assert len(_copias(raiz)) == 2, "a segunda troca apagou a cópia da primeira"
    guardados = {c.read_text(encoding="utf-8") for c in _copias(raiz)}
    assert len(guardados) == 2, "as duas cópias guardaram o mesmo conteúdo"


def test_env_com_endereco_nao_sandbox_para_sem_escrever(tmp_path):
    raiz = _plataforma(
        tmp_path,
        env=(
            "DJANGO_SECRET_KEY=x\n"
            "APPMAX_AUTH_URL=https://auth.appmax.com.br/oauth2/token\n"
            "APPMAX_API_URL=https://api.appmax.com.br\n"
            "MP_ACCESS_TOKEN=TEST-nao-e-para-mexer\n"
        ),
    )
    antes = (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8")

    resultado = _rodar(raiz)
    tela = resultado.stdout + resultado.stderr

    assert resultado.returncode != 0
    assert "outro endereço de autenticação" in tela
    assert CLIENT_ID not in tela and SEGREDO not in tela
    assert (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8") == antes
    assert _copias(raiz) == []


def test_rodar_de_novo_aceita_enter_para_manter_os_enderecos(tmp_path):
    """Os destinos permanecem fixos no sandbox ao trocar só as credenciais."""
    raiz = _plataforma(tmp_path)
    assert _rodar(raiz).returncode == 0

    segunda = f"\n\n{CLIENT_ID}\n{SEGREDO}\n"
    assert _rodar(raiz, digitado=segunda).returncode == 0

    assert _valor(raiz, "APPMAX_AUTH_URL") == AUTH_URL
    assert _valor(raiz, "APPMAX_API_URL") == API_URL
    assert json.loads(_valor(raiz, "APPMAX_INSTALACOES")) == {
        APP_ID: {"alias": SITE_NOME, "sites": [SITE_ID]}
    }


# ---------------------------------------------------------------------------
# 6. O EXEMPLO DE ENV DOCUMENTA A VARIÁVEL QUE O CÓDIGO LÊ
# ---------------------------------------------------------------------------


def _chaves_do_exemplo() -> set[str]:
    chaves = set()
    for linha in EXEMPLO.read_text(encoding="utf-8").splitlines():
        despida = linha.strip()
        if despida and not despida.startswith("#") and "=" in despida:
            chaves.add(despida.split("=", 1)[0])
    return chaves


def test_o_exemplo_documenta_appmax_instalacoes_com_o_formato_real():
    """Quem configurar a VPS pelo exemplo precisa ver a variável que o código lê."""
    texto = EXEMPLO.read_text(encoding="utf-8")

    assert "APPMAX_INSTALACOES" in _chaves_do_exemplo()
    assert '"alias"' in texto and '"sites"' in texto, (
        "o exemplo cita a variável sem mostrar o formato, e o formato é a "
        "única coisa que ninguém adivinha"
    )


def test_nenhuma_variavel_appmax_morta_sobrou_no_exemplo():
    """Duas variáveis concorrentes, uma lida e outra não, é como uma VPS fica
    configurada e recusando ao mesmo tempo."""
    assert "APPMAX_APP_ID" not in _chaves_do_exemplo(), (
        "APPMAX_APP_ID não é lido por nenhuma linha do código: quem preencher "
        "só ele vê a rota de instalação continuar respondendo 403."
    )


def test_prepara_uuid_novo_na_instalacao_existente_sem_ativar_cobranca(tmp_path):
    # guarda: infra/ligar-a-appmax.sh:303
    # guarda: infra/ligar-a-appmax.sh:311
    raiz = _plataforma(tmp_path, env=_env_preparacao())
    ambiente = _ambiente(tmp_path, raiz)

    resultado = _rodar(raiz, digitado="", ambiente=ambiente, args=("--preparar-reinstalacao",))

    assert resultado.returncode == 0, (
        resultado.stdout
        + resultado.stderr
        + (Path(ambiente["DOCKER_FALSO_DB_STATE"]).read_text(encoding="utf-8") if Path(ambiente["DOCKER_FALSO_DB_STATE"]).exists() else "STATE_ABSENT")
    )
    assert "preparação de reinstalação sandbox concluída" in resultado.stdout
    assert "finalize consentimento e OAuth MERCHANT" in resultado.stdout
    assert "cartão permanece desligado" in resultado.stdout
    estado = json.loads(Path(ambiente["DOCKER_FALSO_DB_STATE"]).read_text(encoding="utf-8"))
    assert len(estado["rows"]) == 1
    assert estado["rows"][0]["external_id"] != "00000000-0000-4000-8000-000000000001"
    assert estado["saved"] == [["external_id"]]
    uuid.UUID(estado["rows"][0]["external_id"])
    assert (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8") == _env_preparacao()
    tela = resultado.stdout + resultado.stderr
    assert MERCHANT_SECRET not in tela
    assert "curl" not in tela.lower()


@pytest.mark.parametrize(
    ("rows", "catalogo", "config", "esperado"),
    [
        ([], f"{SITE_ID}\t{SITE_HOST}\t{SITE_NOME}\n", {"1888": {"alias": SITE_NOME, "sites": [SITE_ID]}}, "instalação existente"),
        ([
            {"app_id": "1888", "alias": SITE_NOME, "platform_site_ids": [SITE_ID], "external_id": "00000000-0000-4000-8000-000000000001"},
            {"app_id": "1888", "alias": SITE_NOME, "platform_site_ids": [SITE_ID], "external_id": "00000000-0000-4000-8000-000000000002"},
        ], f"{SITE_ID}\t{SITE_HOST}\t{SITE_NOME}\n", {"1888": {"alias": SITE_NOME, "sites": [SITE_ID]}}, "instalação existente"),
        ([{"app_id": "1888", "alias": SITE_NOME, "platform_site_ids": [SITE_ID], "external_id": "00000000-0000-4000-8000-000000000001"}], "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa\tother.example\tOutra\n", {"1888": {"alias": SITE_NOME, "sites": [SITE_ID]}}, "site ativo autorizado"),
        ([{"app_id": "1888", "alias": SITE_NOME, "platform_site_ids": [SITE_ID], "external_id": "00000000-0000-4000-8000-000000000001"}], f"{SITE_ID}\t{SITE_HOST}\t{SITE_NOME}\n", {"1888": {"alias": SITE_NOME, "sites": [SITE_ID]}, "1889": {"alias": "Outra", "sites": [SITE_ID]}}, "configuração Appmax"),
        ([{"app_id": "1888", "alias": SITE_NOME, "platform_site_ids": ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"], "external_id": "00000000-0000-4000-8000-000000000001"}], f"{SITE_ID}\t{SITE_HOST}\t{SITE_NOME}\n", {"1888": {"alias": SITE_NOME, "sites": [SITE_ID]}}, "site ativo autorizado"),
    ],
)
def test_recusa_estado_ausente_ambiguo_ou_site_nao_autorizado_sem_rotacionar(
    tmp_path, rows, catalogo, config, esperado
):
    # guarda: infra/ligar-a-appmax.sh:294
    # guarda: infra/ligar-a-appmax.sh:300
    # guarda: infra/ligar-a-appmax.sh:304
    # guarda: infra/ligar-a-appmax.sh:306
    raiz = _plataforma(tmp_path, env=_env_preparacao())
    ambiente = _ambiente(
        tmp_path,
        raiz,
        DOCKER_FALSO_DB_ROWS=json.dumps(rows),
        DOCKER_FALSO_SITES=catalogo,
        DOCKER_FALSO_ACTIVE_IDS="\n".join(
            linha.split("\t", 1)[0] for linha in catalogo.splitlines() if linha.strip()
        ),
        DOCKER_FALSO_APP_CONFIG=json.dumps(config),
    )

    resultado = _rodar(raiz, digitado="", ambiente=ambiente, args=("--preparar-reinstalacao",))

    assert resultado.returncode != 0
    assert esperado in (resultado.stdout + resultado.stderr), (
        resultado.stdout
        + resultado.stderr
        + (Path(ambiente["DOCKER_FALSO_DB_STATE"]).read_text(encoding="utf-8") if Path(ambiente["DOCKER_FALSO_DB_STATE"]).exists() else "STATE_ABSENT")
    )
    assert "nada foi alterado" in (resultado.stdout + resultado.stderr).lower()
    estado = json.loads(Path(ambiente["DOCKER_FALSO_DB_STATE"]).read_text(encoding="utf-8"))
    assert estado["saved"] == []
    assert [r["external_id"] for r in estado["rows"]] == [r["external_id"] for r in rows]


@pytest.mark.parametrize(
    ("env", "ajustes", "esperado"),
    [
        (_env_preparacao(APPMAX_AUTH_URL="https://auth.appmax.com.br/oauth2/token"), {}, "autenticação não está fixada no sandbox"),
        (_env_preparacao(APPMAX_API_URL="https://api.appmax.com.br"), {}, "API não está fixada no sandbox"),
        (_env_preparacao(APPMAX_CARD_ENABLED_SITES="site-a"), {}, "há sites com cobrança Appmax habilitada"),
        (_env_preparacao(), {"DOCKER_FALSO_AUTH_URL": "https://auth.appmax.com.br/oauth2/token"}, "autenticação do processo pagamentos não está fixada no sandbox"),
        (_env_preparacao(), {"DOCKER_FALSO_API_URL": "https://api.appmax.com.br"}, "API do processo pagamentos não está fixada no sandbox"),
        (_env_preparacao(), {"DOCKER_FALSO_CARD_ENABLED_SITES": "site-a"}, "há sites com cobrança Appmax habilitada no processo pagamentos"),
        (_env_preparacao(), {"DOCKER_FALSO_SETTING_CARD_ENABLED_SITES": "site-a"}, "há sites com cobrança Appmax habilitada no processo pagamentos"),
        (_env_preparacao(), {"DOCKER_FALSO_EXEC": "17"}, "não consegui confirmar os sites ativos no catálogo"),
        (_env_preparacao(), {"DOCKER_FALSO_ROTACAO_EXEC": "17"}, "não consegui confirmar se o identificador foi trocado"),
    ],
)
def test_guardas_da_preparacao_bloqueiam_sem_confirmacao_de_rotacao(tmp_path, env, ajustes, esperado):
    # guarda: infra/ligar-a-appmax.sh:266
    # guarda: infra/ligar-a-appmax.sh:268
    # guarda: infra/ligar-a-appmax.sh:307
    # guarda: infra/ligar-a-appmax.sh:308
    # guarda: infra/ligar-a-appmax.sh:309
    raiz = _plataforma(tmp_path, env=env)
    ambiente = _ambiente(tmp_path, raiz, **ajustes)

    resultado = _rodar(raiz, digitado="", ambiente=ambiente, args=("--preparar-reinstalacao",))

    assert resultado.returncode != 0
    assert esperado in (resultado.stdout + resultado.stderr)
    estado = Path(ambiente["DOCKER_FALSO_DB_STATE"])
    if estado.exists():
        assert json.loads(estado.read_text(encoding="utf-8"))["saved"] == []
