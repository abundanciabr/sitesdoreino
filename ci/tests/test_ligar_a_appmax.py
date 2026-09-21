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
   `curl` de mentira responde lendo o env recém-escrito, então um app_id ou um
   site errado viram 403 aqui, do mesmo jeito que virariam na VPS.
4. **Cópia de segurança antes de qualquer edição**, e o resto do env sobrevive
   inteiro (`armadilhas/111`).
5. **Rodar de novo TROCA, nunca duplica.** Duas linhas da mesma chave no mesmo
   env fazem o valor depender da ordem de leitura.

[INV-CI01]: sem `bash` nesta máquina o guarda não tem o que medir, e isso é
ERRO, nunca um OK silencioso.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
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
AUTH_URL = "https://auth.exemplo-appmax.test/oauth/token"
API_URL = "https://api.exemplo-appmax.test/v3"

# O env da célula como o provisionamento o escreve, ANTES desta entrega.
PAGAMENTOS_ENV = (
    "DJANGO_SECRET_KEY=x\n"
    "DATABASE_URL=postgres://pagamentos_user:senha@postgres:5432/pagamentos_db\n"
    "MP_ACCESS_TOKEN=TEST-nao-e-para-mexer\n"
    "REDIS_STREAMS_URL=redis://redis:6379/0\n"
    "APPMAX_CARD_ENABLED_SITES=\n"
)

# As respostas do teclado, na ordem em que o roteiro pergunta.
RESPOSTAS = f"{APP_ID}\n{SITE_NOME}\n{AUTH_URL}\n{API_URL}\n{CLIENT_ID}\n{SEGREDO}\n"


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
    printf '%s\n' ${DOCKER_FALSO_SERVICOS-catalogo pagamentos}
    exit 0
    ;;
  exec)
    if [ "${DOCKER_FALSO_EXEC:-0}" -ne 0 ]; then
      printf 'service "catalogo" is not running\n' >&2
      exit "${DOCKER_FALSO_EXEC}"
    fi
    printf '%s' "${DOCKER_FALSO_SITES-}"
    exit 0
    ;;
  up)
    exit "${DOCKER_FALSO_UP:-0}"
    ;;
esac
exit 0
"""

# O curl de mentira É a rota de instalação: ele lê o env que o roteiro acabou de
# escrever e responde como `pagamentos/api/appmax.py` responderia. Assim o teste
# MEDE em vez de afirmar: app_id fora do env vira 403 aqui, igual à VPS.
CURL_DE_MENTIRA = r"""#!/usr/bin/env bash
CORPO=""
PROXIMO=""
for ARG in "$@"; do
  [ "$PROXIMO" = "data" ] && { CORPO="$ARG"; PROXIMO=""; }
  [ "$ARG" = "--data" ] && PROXIMO="data"
done
if [ "${CURL_FALSO_FALHA:-0}" -ne 0 ]; then
  printf 'curl: (7) Failed to connect\n' >&2
  exit "$CURL_FALSO_FALHA"
fi
if [ -n "${CURL_FALSO_CODIGO-}" ]; then
  printf '{"detail": "app_id nao autorizado nesta instalacao"}\n%s\n' "$CURL_FALSO_CODIGO"
  exit 0
fi
PEDIDO=$(printf '%s' "$CORPO" | sed 's/.*"app_id":"\([0-9]*\)".*/\1/')
LINHA=$(grep '^APPMAX_INSTALACOES=' "$CURL_FALSO_ENV" | head -1 | cut -d= -f2-)
case "$LINHA" in
  *"\"$PEDIDO\":"*)
    ALIAS=$(printf '%s' "$LINHA" | sed 's/.*"alias":"\([^"]*\)".*/\1/')
    printf '{"external_id": "b1946ac9-2492-4a04-b4d6-4c1f9e9b0f77", "alias": "%s"}\n200\n' "$ALIAS"
    ;;
  *)
    printf '{"detail": "app_id nao autorizado nesta instalacao"}\n403\n'
    ;;
esac
exit 0
"""


def _plataforma(tmp_path: Path, *, env: str | None = PAGAMENTOS_ENV) -> Path:
    """Uma /opt/plataforma de mentira. `env=None` = célula não provisionada."""
    raiz = tmp_path / "plataforma"
    (raiz / "env").mkdir(parents=True, exist_ok=True)
    (raiz / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    if env is not None:
        (raiz / "env" / "pagamentos.env").write_text(env, encoding="utf-8")
    return raiz


def _ambiente(tmp_path: Path, raiz: Path, **ajustes: str) -> dict:
    """Instala o docker e o curl de mentira e devolve o ambiente do roteiro.

    Sem ajuste nenhum os dois FUNCIONAM: o catálogo tem um site ativo, a célula
    recarrega, e a rota responde lendo o env recém-escrito.
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

    ambiente = dict(
        os.environ,
        PATH=str(pasta) + os.pathsep + os.environ.get("PATH", ""),
        PLATAFORMA_DIR=str(raiz),
        DOCKER_FALSO_SITES=f"{SITE_ID}\t{SITE_HOST}\t{SITE_NOME}\n",
        CURL_FALSO_ENV=str(raiz / "env" / "pagamentos.env"),
    )
    ambiente.update(ajustes)
    return ambiente


def _rodar(
    raiz: Path,
    digitado: str = RESPOSTAS,
    ambiente: dict | None = None,
) -> subprocess.CompletedProcess:
    """Roda o roteiro SEM ARGUMENTO, com `digitado` chegando pelo teclado."""
    if ambiente is None:
        ambiente = _ambiente(raiz.parent, raiz)
    return subprocess.run(
        [_bash(), str(SCRIPT)],
        input=digitado,
        capture_output=True,
        text=True,
        # O roteiro fala PORTUGUÊS, com acento e com o "PAROU POR SEGURANÇA".
        # Sem dizer o encoding aqui, o Python de uma máquina Windows tenta
        # cp1252 e a leitura da tela estoura antes de qualquer asserção.
        encoding="utf-8",
        errors="replace",
        env=ambiente,
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
    recarga = [x for x in fonte.splitlines() if "docker compose up -d --" in x]
    assert len(recarga) == 1, recarga
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
    assert (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8") == antes
    assert _copias(raiz) == [], "guardou cópia de um arquivo que nem chegou a mudar"


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
        "auth": AUTH_URL,
        "api": API_URL,
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
        ("\n" * 6, "você não respondeu", "tudo em branco e nada gravado para manter"),
        (_com(auth="ftp://x"), "não parece um endereço", "endereço que não é https"),
        (_com(api="nao-e-endereco"), "não parece um endereço", "o segundo endereço também é conferido"),
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


def test_a_tela_final_mostra_a_rota_respondendo_200(tmp_path):
    """É o que o mantenedor precisa VER: a porta que recusava passou a aceitar."""
    raiz = _plataforma(tmp_path)

    resultado = _rodar(raiz)

    tela = resultado.stdout
    assert "200" in tela
    assert "b1946ac9-2492-4a04-b4d6-4c1f9e9b0f77" in tela, (
        "o external_id da resposta não apareceu na tela"
    )
    assert "403" not in tela
    assert SEGREDO not in tela


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


def test_rota_fora_do_ar_avisa_sem_desfazer_o_que_gravou(tmp_path):
    raiz = _plataforma(tmp_path)
    ambiente = _ambiente(tmp_path, raiz, CURL_FALSO_FALHA="7")

    resultado = _rodar(raiz, ambiente=ambiente)
    tela = resultado.stdout + resultado.stderr

    assert resultado.returncode != 0
    assert "não consegui falar com" in tela, (
        "o site fora do ar e a porta recusando são duas telas diferentes, e "
        "quem lê só sabe o que fazer se elas não se confundirem"
    )
    assert SEGREDO not in tela
    assert _valor(raiz, "APPMAX_APP_CLIENT_SECRET") == SEGREDO


def test_porta_que_continua_recusando_manda_conferir_o_app_id(tmp_path):
    """É o desfecho mais provável de um erro de digitação, e o único que o
    mantenedor consegue consertar sozinho."""
    raiz = _plataforma(tmp_path)
    ambiente = _ambiente(tmp_path, raiz, CURL_FALSO_CODIGO="403")

    resultado = _rodar(raiz, ambiente=ambiente)
    tela = resultado.stdout + resultado.stderr

    assert resultado.returncode != 0
    assert "PAROU POR SEGURANÇA" in tela
    assert APP_ID in tela, "não disse qual app_id foi gravado, que é o que ele confere"
    assert "NÃO é para colar as credenciais de novo" in tela
    assert SEGREDO not in tela


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
    segunda = f"{APP_ID}\n{SITE_NOME}\n{AUTH_URL}\n{API_URL}\n{CLIENT_ID}\n{outro}\n"
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


def test_env_com_a_chave_repetida_volta_a_ter_uma_linha_so(tmp_path):
    """O env que alguém já tentou configurar à mão antes deste roteiro existir.
    Duas linhas da mesma chave fazem o valor depender da ordem de leitura."""
    raiz = _plataforma(
        tmp_path,
        env=(
            "DJANGO_SECRET_KEY=x\n"
            "APPMAX_AUTH_URL=https://antigo.test/1\n"
            "MP_ACCESS_TOKEN=TEST-nao-e-para-mexer\n"
            "APPMAX_AUTH_URL=https://antigo.test/2\n"
        ),
    )

    assert _rodar(raiz).returncode == 0

    assert _linhas(raiz, "APPMAX_AUTH_URL") == 1
    assert _valor(raiz, "APPMAX_AUTH_URL") == AUTH_URL
    assert _valor(raiz, "MP_ACCESS_TOKEN") == "TEST-nao-e-para-mexer"


def test_rodar_de_novo_aceita_enter_para_manter_os_enderecos(tmp_path):
    """Trocar só o segredo não pode obrigar a redigitar o que já está certo."""
    raiz = _plataforma(tmp_path)
    assert _rodar(raiz).returncode == 0

    segunda = f"\n\n\n\n{CLIENT_ID}\n{SEGREDO}\n"
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
