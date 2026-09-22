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

CURL_DE_MENTIRA = r"""#!/usr/bin/env bash
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
    *) printf 'resposta quebrada
200' ;;
  esac
fi
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

    ambiente = dict(
        os.environ,
        PATH=str(pasta) + os.pathsep + os.environ.get("PATH", ""),
        PLATAFORMA_DIR=str(raiz),
        DOCKER_FALSO_SITES=f"{SITE_ID}\t{SITE_HOST}\t{SITE_NOME}\n",
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
    return subprocess.run(
        [_bash(), str(SCRIPT), *args],
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

@pytest.mark.parametrize("codigo", ["HTTP_401", "FALHA_DE_REDE", "RESPOSTA_INVALIDA"])
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
    raiz = _plataforma(tmp_path, env=PAGAMENTOS_ENV + "APPMAX_CARD_ENABLED_SITES=site-de-teste\n")
    antes = (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8")

    resultado = _rodar(raiz)
    tela = resultado.stdout + resultado.stderr

    assert resultado.returncode != 0
    assert "APPMAX_CARD_ENABLED_SITES" in tela
    assert "client_secret" not in tela
    assert (raiz / "env" / "pagamentos.env").read_text(encoding="utf-8") == antes
    assert _copias(raiz) == []


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
