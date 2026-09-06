"""O roteiro que deixa a Prancheta pronta, EXECUTADO, não lido.

`infra/provisionar-pares-da-prancheta.sh` (degrau 06 de
`docs/decisoes/PLANO-PORTFOLIO-DO-ALUNO.md`) liga os três pares que a célula
`pages` já consome no código: a `identidade`, que diz QUEM é a pessoa e libera o
e-mail dela; a `alunos`, que diz se ela TEM MATRÍCULA ATIVA; e o `catalogo`, que
dá o menu do topo do site. Além dos três, ele pergunta ao catálogo DE QUE ESCOLA
esta instalação é e grava o `SITE_ID`. São onze chaves em quatro `env` da VPS.

Ele roda **na máquina do mantenedor**, com uma linha, e um erro ali custa o pior
tipo de tempo que este projeto tem: o dele, no terminal, sem saber o que fazer
com a tela. Enquanto este guarda não existia, a prova de que o roteiro funciona
era a rodada manual de uma sessão, e prova de sessão morre com a sessão. Era o
único da família `provisionar-par*` sem guarda próprio (TAR-217).

Por isso ele **roda o roteiro de verdade**, contra uma plataforma de mentira em
`tmp_path` e com um `docker` de mentira no PATH (o mesmo desenho de
`test_provisionar_gamificacao.py`), em vez de afirmar coisas sobre o texto dele.
As promessas medidas são as do despacho da TAR-217:

1. **Nenhum segredo aparece na tela** (`armadilhas/090`).
2. **Rodar de novo não rotaciona**, e um token que já existe no env do PROVEDOR
   é reusado, nunca substituído.
3. **Os pares ficam iguais dos dois lados**, e `TOKENS_COMPLETOS_PAGES` é CÓPIA
   de `TOKENS_ACEITOS_PAGES`: valores diferentes dariam 403 na resposta
   completa, a Prancheta ficaria sem o e-mail para perguntar à `alunos`, e ela
   fecharia para todo mundo em silêncio.
4. **Os endereços gravados são os dos contratos congelados**, lidos do
   `servers:` de cada `contracts/*.openapi.yaml`, e não de uma string fixa deste
   teste.
5. **Três tokens distintos**: token é por par.
6. Os caminhos de recusa, e a régua deles é uma só: **quando o roteiro para, a
   máquina do mantenedor não fica com meia-instalação.** Pasta errada,
   `env/pages.env` ausente (a recusa tem de ensinar a linha do banco,
   `provisionar-pages.sh`, porque um env criado aqui antes dela travaria a trava
   de deriva daquele roteiro para sempre), env de provedor faltando, dois pares
   com o mesmo token, catálogo parado, catálogo que não responde, nenhum site
   ativo, mais de um site ativo sem o host no fim da linha, host pedido que não
   existe, chave repetida, arquivo sem quebra de linha no fim, e carregado com
   `source`.

DUAS FRONTEIRAS MEDIDAS, escritas na cara para ninguém as tomar por promessa:

- A conferência de **chave repetida** acontece DEPOIS da escrita: ela é a última
  do roteiro. O que ela promete não é "nada foi escrito", é dizer QUAL chave, em
  QUAL arquivo, e onde estão as cópias intactas. Só as outras recusas juram não
  ter tocado em nada, e essas são medidas com uma fotografia de TODOS os
  arquivos da pasta `env`, cópias `.bak-` incluídas.
- A recusa por **`docker` ausente na máquina** não é medida aqui. Ela depende de
  `command -v docker` falhar, e o único jeito de forçar isso seria montar um
  PATH sem o docker mas com `bash`, `openssl`, `sed`, `stat` e `date`. Nos
  runners de Linux o docker mora na MESMA pasta que essas ferramentas, então um
  PATH assim mediria a ausência delas, não o roteiro. Fica declarado em vez de
  simulado com um instrumento que mente.

FAIL-CLOSED DE INSTRUMENTAÇÃO ([INV-CI01]): sem `bash`, sem o script, ou com o
script vazio, estes testes REPROVAM em vez de passar por não ter o que medir.
"Não consegui olhar" nunca é "está limpo".
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "infra" / "provisionar-pares-da-prancheta.sh"
CONTRATOS = RAIZ / "contracts"

UM_SITE = "11111111-1111-1111-1111-111111111111\tmeshcraft.top\n"
OUTRA_ESCOLA_ID = "22222222-2222-2222-2222-222222222222"
OUTRA_ESCOLA_HOST = "basileiatoutheou.org"
DOIS_SITES = UM_SITE + f"{OUTRA_ESCOLA_ID}\t{OUTRA_ESCOLA_HOST}\n"

# O `docker` de mentira, governado por variáveis de ambiente para cada teste
# montar o seu cenário sem reescrever o stub. Mesmo desenho do irmão
# `test_provisionar_gamificacao.py`.
DOCKER_FALSO = """#!/usr/bin/env bash
[ "${1:-}" = "compose" ] || exit 0
shift
case "${1:-}" in
  ps)
    if [ "${2:-}" = "--status" ]; then
      printf 'postgres\\n'
      [ "${FAKE_CATALOGO_RODANDO:-1}" = "1" ] && printf 'catalogo\\n'
      printf 'identidade\\nalunos\\npages\\n'
    fi
    exit 0
    ;;
  config)
    printf 'postgres\\ncatalogo\\nidentidade\\nalunos\\npages\\n'
    exit 0
    ;;
  up)
    exit 0
    ;;
  exec)
    for arg in "$@"; do
      case "$arg" in
        catalogo)
          [ "${FAKE_CATALOGO_FALHA:-0}" = "1" ] && exit 1
          printf '%b' "${FAKE_SITES:-}"
          exit 0
          ;;
      esac
    done
    exit 0
    ;;
esac
exit 0
"""

# O estado real da VPS ANTES deste roteiro: a linha do banco
# (`infra/provisionar-pages.sh`) já criou `env/pages.env`, e nenhum dos três
# pares existe ainda. É este roteiro quem os gera.
SEMENTES = {
    "identidade.env": "DJANGO_SECRET_KEY=y\nTOKENS_ACEITOS_FUNIL=tok-funil\n",
    "alunos.env": "DJANGO_SECRET_KEY=x\nDATABASE_URL=postgres://a\n",
    "catalogo.env": "DJANGO_SECRET_KEY=k\nTOKENS_ACEITOS_ADMIN=tok-admin-catalogo\n",
    # Sem quebra de linha no fim DE PROPÓSITO: é o caso que gruda a chave nova
    # no fim da última linha, e a última linha de um env é um valor.
    "pages.env": "DJANGO_SECRET_KEY=p\nDATABASE_URL=postgres://p\nSCRIPT_NAME=/pages",
}

# Os env de PROVEDOR são os únicos que podem chegar com o par já aberto (uma
# rodada anterior, ou uma rotação à mão). Longos de propósito: o roteiro recusa
# token com menos de 32 caracteres.
PROVEDORES = ("identidade.env", "alunos.env", "catalogo.env")
JA_ABERTOS = {
    "identidade.env": "tok-pages-para-identidade-0123456789abcdef",
    "alunos.env": "tok-pages-para-alunos-0123456789abcdef",
    "catalogo.env": "tok-pages-para-catalogo-0123456789abcdef",
}

# (provedor, chave no provedor, consumidor, chave no consumidor)
PARES = [
    ("identidade.env", "TOKENS_ACEITOS_PAGES", "pages.env", "IDENTIDADE_API_TOKEN"),
    ("alunos.env", "TOKENS_ACEITOS_PAGES", "pages.env", "ALUNOS_API_TOKEN"),
    # Sem o sufixo `_API_` de propósito: é o nome que os outros consumidores do
    # catálogo já usam, e aqui vale a convenção que existe.
    ("catalogo.env", "TOKENS_ACEITOS_PAGES", "pages.env", "TOKEN_CATALOGO"),
]

# (contrato congelado, consumidor, chave do endereço)
ENDERECOS = [
    ("identidade", "pages.env", "IDENTIDADE_API_URL"),
    ("alunos", "pages.env", "ALUNOS_API_URL"),
    ("catalogo", "pages.env", "CATALOGO_API_URL"),
]

CHAVES_ESCRITAS = {
    "identidade.env": ["TOKENS_ACEITOS_PAGES", "TOKENS_COMPLETOS_PAGES"],
    "alunos.env": ["TOKENS_ACEITOS_PAGES"],
    "catalogo.env": ["TOKENS_ACEITOS_PAGES"],
    "pages.env": [
        "IDENTIDADE_API_URL",
        "IDENTIDADE_API_TOKEN",
        "ALUNOS_API_URL",
        "ALUNOS_API_TOKEN",
        "CATALOGO_API_URL",
        "TOKEN_CATALOGO",
        "SITE_ID",
    ],
}


def _escrever(caminho: Path, conteudo: str) -> None:
    """Sempre com LF: um shebang seguido de CRLF não roda em Linux."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write(conteudo)


def _bash() -> str:
    caminho = shutil.which("bash")
    assert caminho, (
        "não achei `bash` nesta máquina. Este guarda EXECUTA o roteiro; sem "
        "interpretador ele não tem o que medir, e isso não é um OK ([INV-CI01])."
    )
    return caminho


def _plataforma(tmp_path: Path, faltando: str | None = None, ja_ligado: bool = False) -> Path:
    raiz = tmp_path / "plataforma"
    (raiz / "env").mkdir(parents=True)
    _escrever(raiz / "docker-compose.yml", "services: {}\n")
    for nome, conteudo in SEMENTES.items():
        if nome == faltando:
            continue
        if ja_ligado and nome in JA_ABERTOS:
            conteudo = f"{conteudo}TOKENS_ACEITOS_PAGES={JA_ABERTOS[nome]}\n"
        _escrever(raiz / "env" / nome, conteudo)

    binario = tmp_path / "bin"
    _escrever(binario / "docker", DOCKER_FALSO)
    (binario / "docker").chmod((binario / "docker").stat().st_mode | stat.S_IEXEC)
    return raiz


def _executar(argumentos: list[str], plataforma: str, bin_falso: Path, **cenario: str):
    """Roda o roteiro e devolve a saída como TEXTO UTF-8.

    `encoding` explícito: `text=True` sozinho decodifica pelo idioma do sistema
    (em Windows, cp1252) e estoura na primeira mensagem acentuada. O env é
    HERDADO (com o `docker` falso na FRENTE do PATH) porque o roteiro usa
    `openssl`, `stat`, `sed` e `date`; um PATH inventado mediria a ausência das
    ferramentas, não o roteiro.
    """
    ambiente = dict(os.environ)
    ambiente["PLATAFORMA_DIR"] = plataforma
    ambiente["PATH"] = str(bin_falso) + os.pathsep + ambiente["PATH"]
    ambiente.setdefault("FAKE_SITES", UM_SITE)
    ambiente.update(cenario)
    return subprocess.run(
        argumentos,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=ambiente,
    )


def _rodar(raiz: Path, *args: str, **cenario: str):
    return _executar(
        [_bash(), str(SCRIPT), *args], str(raiz), raiz.parent / "bin", **cenario
    )


def _valor(raiz: Path, arquivo: str, chave: str) -> str | None:
    texto = (raiz / "env" / arquivo).read_text(encoding="utf-8")
    achado = re.search(rf"^{re.escape(chave)}=(.*)$", texto, re.MULTILINE)
    return achado.group(1).strip() if achado else None


def _fotografia(raiz: Path) -> dict[str, str]:
    """TODO arquivo da pasta `env`, e não só os `*.env`: a cópia de segurança
    que o roteiro deixa para trás também é escrita, e um `.bak-` novo denuncia
    uma recusa que jurou não ter tocado em nada."""
    return {
        p.name: p.read_text(encoding="utf-8")
        for p in sorted((raiz / "env").iterdir())
        if p.is_file()
    }


def _endereco_do_contrato(celula: str) -> str:
    """O primeiro `servers:` do contrato congelado, que é a fonte do endereço."""
    contrato = CONTRATOS / f"{celula}.openapi.yaml"
    assert contrato.is_file(), f"o contrato congelado sumiu: {contrato}"
    achado = re.search(
        r"^servers:\s*\n\s*-\s*url:\s*(\S+)", contrato.read_text(encoding="utf-8"), re.MULTILINE
    )
    assert achado, f"não achei o `servers:` em {contrato.name}"
    return achado.group(1)


# ------------------------------------------------------- [INV-CI01]: há o quê


def test_o_roteiro_existe_e_e_executavel_por_bash():
    """Sem isto, os testes abaixo passariam medindo o nada."""
    assert SCRIPT.is_file(), SCRIPT
    texto = SCRIPT.read_text(encoding="utf-8")
    assert texto.strip(), "o roteiro está vazio"
    assert texto.startswith("#!/usr/bin/env bash"), "faltou o shebang"
    assert "PAROU POR SEGURANÇA" in texto, "o roteiro não fala a língua fail-closed da casa"
    # A UMA LINHA que o mantenedor vai colar tem de estar no cabeçalho: é ela
    # que faz este passo não ser um texto para digitar.
    assert "curl -fsSL" in texto and "provisionar-pares-da-prancheta.sh" in texto
    saida = subprocess.run([_bash(), "-n", str(SCRIPT)], capture_output=True, text=True)
    assert saida.returncode == 0, saida.stderr


# ------------------------------------------------------------ o caminho feliz


def test_liga_os_tres_pares_e_eles_batem_dos_dois_lados(tmp_path):
    """Promessas 3 e 5: iguais dos dois lados, e três valores DISTINTOS."""
    raiz = _plataforma(tmp_path)
    r = _rodar(raiz)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PRONTO:" in r.stdout, r.stdout

    valores = []
    for provedor, chave, consumidor, chave2 in PARES:
        a, b = _valor(raiz, provedor, chave), _valor(raiz, consumidor, chave2)
        assert a and a == b, f"{chave} ({provedor}) != {chave2} ({consumidor})"
        assert len(a) >= 32, f"{chave} nasceu curto demais: {len(a)}"
        valores.append(a)
    assert len(set(valores)) == 3, (
        "dois pares ficaram com o mesmo token. Token é por par: um só faria a "
        "rotação de um derrubar o outro, sem aviso."
    )


def test_o_degrau_de_email_e_copia_do_token_aceito(tmp_path):
    """Promessa 3, a metade que ninguém vê falhar: dois degraus sobre o MESMO
    token (`DECISAO-celula-de-identidade.md` §6.3, item `pages`). Valores
    diferentes dariam 403 na resposta completa, a Prancheta ficaria sem o e-mail
    para perguntar à `alunos`, e fecharia para todo mundo em silêncio."""
    raiz = _plataforma(tmp_path)
    assert _rodar(raiz).returncode == 0
    aceito = _valor(raiz, "identidade.env", "TOKENS_ACEITOS_PAGES")
    assert aceito
    assert _valor(raiz, "identidade.env", "TOKENS_COMPLETOS_PAGES") == aceito


def test_os_enderecos_gravados_sao_os_dos_contratos_congelados(tmp_path):
    """Promessa 4. O `servers:` de cada contrato é a fonte; o roteiro só copia.
    Mudar o contrato (Rito) e esquecer o roteiro deixaria os dois lados
    coerentes consigo mesmos e incoerentes entre si."""
    raiz = _plataforma(tmp_path)
    assert _rodar(raiz).returncode == 0
    for celula, consumidor, chave in ENDERECOS:
        assert _valor(raiz, consumidor, chave) == _endereco_do_contrato(celula), chave


def test_a_escola_gravada_e_a_que_o_catalogo_respondeu(tmp_path):
    """`SITE_ID` não é par de ninguém: é de que escola esta instalação é. Sem
    ele a Prancheta mostra o roteiro e RECUSA a marcação do aluno com 503, e
    gravar com o campo em branco poria os alunos de duas escolas do mesmo lado
    da fronteira no dia em que a segunda chegasse."""
    raiz = _plataforma(tmp_path)
    assert _rodar(raiz).returncode == 0
    assert _valor(raiz, "pages.env", "SITE_ID") == UM_SITE.split("\t")[0]


def test_nenhum_segredo_aparece_na_tela(tmp_path):
    """Promessa 1: a `armadilhas/090` medida pelo resultado, e não pela leitura
    do código. O que vai para a tela vai para o histórico do shell e para o
    print que o mantenedor manda ao robô."""
    raiz = _plataforma(tmp_path)
    r = _rodar(raiz)
    assert r.returncode == 0, r.stdout + r.stderr

    saida = r.stdout + r.stderr
    for provedor, chave, _, _ in PARES:
        segredo = _valor(raiz, provedor, chave)
        assert segredo, chave
        assert segredo not in saida, f"o valor de {chave} ({provedor}) foi impresso na tela"
        # Nem um pedaço grande dele: um "eco parcial" para depuração é o jeito
        # mais comum de este guarda ser contornado sem má intenção.
        assert segredo[:16] not in saida, f"um pedaço de {chave} ({provedor}) foi impresso"


def test_o_token_que_ja_existia_no_provedor_e_reusado(tmp_path):
    """Promessa 2. Quem manda é o PROVEDOR: o valor vem da lista de aceitos dele
    e o consumidor é realinhado a ela. Regerar aqui derrubaria as chamadas até o
    container do outro lado reiniciar, e o sintoma seria 401 intermitente."""
    raiz = _plataforma(tmp_path, ja_ligado=True)
    r = _rodar(raiz)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "JÁ existiam" in r.stdout, r.stdout
    for provedor, chave, consumidor, chave2 in PARES:
        assert _valor(raiz, provedor, chave) == JA_ABERTOS[provedor]
        assert _valor(raiz, consumidor, chave2) == JA_ABERTOS[provedor]
    assert _valor(raiz, "identidade.env", "TOKENS_COMPLETOS_PAGES") == JA_ABERTOS["identidade.env"]


def test_rodar_de_novo_nao_rotaciona_nada(tmp_path):
    """Promessa 2 pelo outro lado: a segunda rodada não mexe em arquivo nenhum,
    nem deixa cópia de segurança nova para trás."""
    raiz = _plataforma(tmp_path)
    assert _rodar(raiz).returncode == 0
    antes = _fotografia(raiz)

    r = _rodar(raiz)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "nada: já estava tudo ligado" in r.stdout, r.stdout
    assert _fotografia(raiz) == antes, "a segunda rodada mexeu em algum arquivo"


def test_a_ultima_linha_de_um_env_sem_quebra_no_fim_sobrevive(tmp_path):
    """`pages.env` da semente termina SEM quebra de linha, e a última linha de um
    env é um valor. Se a chave nova grudasse nela, as duas virariam lixo de uma
    vez."""
    raiz = _plataforma(tmp_path)
    assert _rodar(raiz).returncode == 0
    texto = (raiz / "env" / "pages.env").read_text(encoding="utf-8")
    assert "SCRIPT_NAME=/pages\n" in texto, texto
    assert _valor(raiz, "pages.env", "SCRIPT_NAME") == "/pages"


def test_a_chave_nova_nao_gruda_quando_o_bloco_dela_ja_existe(tmp_path):
    """O caso em que a guarda da quebra de linha é a ÚNICA coisa de pé.

    Quando o bloco ainda não existe, quem separa é o `\\n` que abre o cabeçalho
    do bloco novo, e a guarda nem chega a ser necessária. Ela só trabalha
    sozinha no arquivo que JÁ tem o cabeçalho e perdeu a quebra do fim: uma
    rodada interrompida, ou uma edição à mão. Aí, sem ela, `TOKEN_CATALOGO=`
    nasceria colado no fim de `CATALOGO_API_URL=`, e as duas chaves virariam
    lixo de uma vez.
    """
    raiz = _plataforma(tmp_path)
    assert _rodar(raiz).returncode == 0

    alvo = raiz / "env" / "pages.env"
    sobrou = [
        linha
        for linha in alvo.read_text(encoding="utf-8").splitlines()
        if not linha.startswith("TOKEN_CATALOGO=")
    ]
    _escrever(alvo, "\n".join(sobrou))  # e SEM quebra no fim

    r = _rodar(raiz)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _valor(raiz, "pages.env", "CATALOGO_API_URL") == _endereco_do_contrato("catalogo")
    assert _valor(raiz, "pages.env", "TOKEN_CATALOGO") == _valor(
        raiz, "catalogo.env", "TOKENS_ACEITOS_PAGES"
    )


def test_nenhuma_chave_fica_repetida(tmp_path):
    """O Docker Compose usa a ÚLTIMA ocorrência: um valor velho ficaria por
    baixo do novo, sem nada acusar. Três rodadas, porque o bug apareceria na
    segunda."""
    raiz = _plataforma(tmp_path)
    for _ in range(3):
        assert _rodar(raiz).returncode == 0
    for arquivo, chaves in CHAVES_ESCRITAS.items():
        texto = (raiz / "env" / arquivo).read_text(encoding="utf-8")
        for chave in chaves:
            n = len(re.findall(rf"^{re.escape(chave)}=", texto, re.MULTILINE))
            assert n == 1, f"{chave} aparece {n} vezes em {arquivo}"


@pytest.mark.parametrize("provedor", PROVEDORES)
def test_o_par_dessincronizado_a_mao_e_curado_pelo_provedor(tmp_path, provedor):
    """É o caminho da rotação (`armadilhas/090`): troca-se o valor na lista de
    aceitos do provedor e roda-se a linha de novo. A direção importa: alinhar
    pelo consumidor deixaria uma célula qualquer mudar o que o provedor aceita."""
    chave_do_consumidor = {
        provedor: chave2 for provedor, _, _, chave2 in PARES
    }[provedor]
    raiz = _plataforma(tmp_path)
    assert _rodar(raiz).returncode == 0
    alvo = raiz / "env" / provedor
    novo = "n" * 40
    _escrever(
        alvo,
        re.sub(
            r"^TOKENS_ACEITOS_PAGES=.*$",
            f"TOKENS_ACEITOS_PAGES={novo}",
            alvo.read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        ),
    )
    assert _rodar(raiz).returncode == 0
    assert _valor(raiz, "pages.env", chave_do_consumidor) == novo


# ------------------------------------- os caminhos de recusa: o que a máquina
# ------------------------------------- do mantenedor NÃO fica depois deles


def test_pasta_errada_para_sem_escrever(tmp_path):
    raiz = _plataforma(tmp_path)
    r = _executar(
        [_bash(), str(SCRIPT)], str(tmp_path / "nao-existe"), tmp_path / "bin"
    )
    assert r.returncode != 0
    assert "PAROU POR SEGURANÇA" in r.stdout
    assert not (tmp_path / "nao-existe").exists(), "criou a pasta que não achou"
    assert (raiz / "env" / "pages.env").read_text(encoding="utf-8") == SEMENTES["pages.env"]


@pytest.mark.parametrize("faltando", PROVEDORES)
def test_env_de_provedor_faltando_para_e_nao_toca_em_nenhum_dos_outros(tmp_path, faltando):
    raiz = _plataforma(tmp_path, faltando=faltando)
    antes = _fotografia(raiz)
    r = _rodar(raiz)
    assert r.returncode != 0, r.stdout
    assert "PAROU POR SEGURANÇA" in r.stdout
    assert _fotografia(raiz) == antes, "parou, mas já tinha escrito em alguém"
    assert not (raiz / "env" / faltando).exists(), f"criou {faltando}, que não é dele"


def test_sem_o_env_das_paginas_a_recusa_ensina_a_linha_do_banco(tmp_path):
    """`env/pages.env` nasce com o banco (`provisionar-pages.sh`), que reescreve
    o env inteiro e PARA ao achar chave que não sabe gerar (a trava de deriva,
    `armadilhas/111`). Um env criado aqui antes dele o travaria para sempre; a
    recusa tem de dizer exatamente o que colar."""
    raiz = _plataforma(tmp_path, faltando="pages.env")
    antes = _fotografia(raiz)
    r = _rodar(raiz)
    assert r.returncode != 0
    assert "provisionar-pages.sh" in r.stdout, r.stdout
    assert "bash /tmp/p.sh" in r.stdout, r.stdout
    assert "Nada foi criado, nada foi alterado." in r.stdout, r.stdout
    assert not (raiz / "env" / "pages.env").exists(), "criou o env que não é dele"
    assert _fotografia(raiz) == antes, "parou, mas já tinha escrito em alguém"


def test_dois_pares_com_o_mesmo_token_param_sem_escrever(tmp_path):
    """Token é por par. Um valor compartilhado faria a rotação de um derrubar o
    outro, e o roteiro confere isso ANTES de tocar em qualquer arquivo."""
    raiz = _plataforma(tmp_path)
    repetido = "r" * 40
    for arquivo in ("identidade.env", "catalogo.env"):
        alvo = raiz / "env" / arquivo
        _escrever(
            alvo,
            f"{alvo.read_text(encoding='utf-8')}TOKENS_ACEITOS_PAGES={repetido}\n",
        )
    antes = _fotografia(raiz)
    r = _rodar(raiz)
    assert r.returncode != 0
    assert "MESMO token" in r.stdout, r.stdout
    assert _fotografia(raiz) == antes, "parou, mas já tinha escrito em alguém"


def test_catalogo_parado_para_antes_de_escrever(tmp_path):
    """Quem sabe o número do site é o catálogo. Com ele fora do ar o roteiro não
    tem como saber de que escola a instalação é, e escrever o resto deixaria uma
    Prancheta que mostra tudo e recusa toda marcação."""
    raiz = _plataforma(tmp_path)
    antes = _fotografia(raiz)
    r = _rodar(raiz, FAKE_CATALOGO_RODANDO="0")
    assert r.returncode != 0
    assert "não está rodando" in r.stdout, r.stdout
    assert "docker compose up -d" in r.stdout, "a recusa não ensina como subir a plataforma"
    assert _fotografia(raiz) == antes, "parou, mas já tinha escrito em alguém"


def test_catalogo_que_nao_responde_para_antes_de_escrever(tmp_path):
    """`armadilhas/240`: "não consegui perguntar" e "perguntei e não há site" são
    duas causas diferentes e precisam de duas telas diferentes."""
    raiz = _plataforma(tmp_path)
    antes = _fotografia(raiz)
    r = _rodar(raiz, FAKE_CATALOGO_FALHA="1")
    assert r.returncode != 0
    assert "não consegui perguntar ao catálogo" in r.stdout, r.stdout
    assert _fotografia(raiz) == antes, "parou, mas já tinha escrito em alguém"


def test_catalogo_sem_nenhum_site_ativo_para_antes_de_escrever(tmp_path):
    raiz = _plataforma(tmp_path)
    antes = _fotografia(raiz)
    r = _rodar(raiz, FAKE_SITES="")
    assert r.returncode != 0
    assert "NENHUM site ativo" in r.stdout, r.stdout
    assert _fotografia(raiz) == antes, "parou, mas já tinha escrito em alguém"


def test_com_mais_de_um_site_e_sem_host_ele_para_e_ensina_a_linha_com_o_host(tmp_path):
    """"O primeiro da lista" seria o chute que amarra o portfólio de todo mundo
    à escola errada. O roteiro para, lista o que achou, e imprime a linha pronta
    com o host no fim."""
    raiz = _plataforma(tmp_path)
    antes = _fotografia(raiz)
    r = _rodar(raiz, FAKE_SITES=DOIS_SITES)
    assert r.returncode != 0
    assert "mais de um site ativo" in r.stdout, r.stdout
    assert "meshcraft.top" in r.stdout and OUTRA_ESCOLA_HOST in r.stdout, r.stdout
    assert "bash /tmp/s.sh meshcraft.top" in r.stdout, "não ensinou a linha com o host"
    assert _fotografia(raiz) == antes, "parou, mas já tinha escrito em alguém"


def test_com_o_host_no_fim_da_linha_ele_grava_a_escola_pedida(tmp_path):
    """O desempate. Com o host, o roteiro segue mesmo havendo várias escolas, e
    grava a que foi pedida, não a primeira da lista."""
    raiz = _plataforma(tmp_path)
    r = _rodar(raiz, OUTRA_ESCOLA_HOST, FAKE_SITES=DOIS_SITES)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _valor(raiz, "pages.env", "SITE_ID") == OUTRA_ESCOLA_ID


def test_host_pedido_que_nao_existe_para_e_lista_os_que_existem(tmp_path):
    raiz = _plataforma(tmp_path)
    antes = _fotografia(raiz)
    r = _rodar(raiz, "escola-que-nao-existe.com", FAKE_SITES=DOIS_SITES)
    assert r.returncode != 0
    assert "não está entre os ativos" in r.stdout, r.stdout
    assert "meshcraft.top" in r.stdout and OUTRA_ESCOLA_HOST in r.stdout, r.stdout
    assert _fotografia(raiz) == antes, "parou, mas já tinha escrito em alguém"


def test_chave_repetida_e_recusada_nomeando_o_arquivo_e_a_copia_intacta(tmp_path):
    """A conferência de chave repetida é a ÚLTIMA do roteiro, e por isso é a
    única recusa que já escreveu quando fala. Ela existe porque o Docker Compose
    usa só a última ocorrência: um valor velho ficaria por baixo em silêncio. O
    que ela promete não é "nada foi escrito", é dizer QUAL chave, em QUAL
    arquivo, e onde estão as cópias intactas."""
    raiz = _plataforma(tmp_path)
    alvo = raiz / "env" / "identidade.env"
    repetido = "d" * 40
    _escrever(
        alvo,
        f"{alvo.read_text(encoding='utf-8')}"
        f"TOKENS_ACEITOS_PAGES={repetido}\nTOKENS_ACEITOS_PAGES={repetido}\n",
    )
    r = _rodar(raiz)
    assert r.returncode != 0, r.stdout
    assert "PAROU POR SEGURANÇA" in r.stdout
    assert "TOKENS_ACEITOS_PAGES aparece 2 vezes" in r.stdout, r.stdout
    assert "env/identidade.env" in r.stdout, r.stdout
    assert ".bak-" in r.stdout, "a recusa não disse onde estão as cópias intactas"


def test_carregado_com_source_recusa_em_vez_de_derrubar_a_sessao(tmp_path):
    """O modo de falha de 24/08: `exit` num shell carregado com `.` derruba a
    sessão interativa do mantenedor. Aconteceu, três vezes."""
    r = _executar(
        [_bash(), "-c", f'. "{SCRIPT}"; echo SOBREVIVI'],
        "/tmp/nao-existe-mesmo",
        tmp_path / "bin",
    )
    assert "PAROU POR SEGURANÇA" in r.stdout
    assert "SOBREVIVI" in r.stdout, "o `return` não protegeu a sessão de quem deu source"


# ---------------------------------------------------------- a ordem que importa


def test_o_provedor_e_escrito_antes_dos_consumidores():
    """Ordem inversa tem janela com sintoma: consumidor com token que o provedor
    ainda não aceita responde 401 para gente de verdade. Medido no texto porque
    é ordem de código: as duas ordens produzem o mesmo arquivo final."""
    texto = SCRIPT.read_text(encoding="utf-8")

    def posicao(arquivo: str, chave: str) -> int:
        return texto.index(f'garantir "$ENV_{arquivo}" {chave} ')

    assert posicao("IDENTIDADE", "TOKENS_ACEITOS_PAGES") < posicao("PAGES", "IDENTIDADE_API_TOKEN")
    assert posicao("IDENTIDADE", "TOKENS_COMPLETOS_PAGES") < posicao("PAGES", "IDENTIDADE_API_TOKEN")
    assert posicao("ALUNOS", "TOKENS_ACEITOS_PAGES") < posicao("PAGES", "ALUNOS_API_TOKEN")
    assert posicao("CATALOGO", "TOKENS_ACEITOS_PAGES") < posicao("PAGES", "TOKEN_CATALOGO")
