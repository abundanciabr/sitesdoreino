"""O script que liga as duas conversas da Prancheta, EXECUTADO, não lido.

`infra/provisionar-pares-da-prancheta.sh` (degrau 06 de
`docs/decisoes/PLANO-PORTFOLIO-DO-ALUNO.md`) liga os dois pares que a célula
`pages` já consome no código (`services/pages/apps/core/clients.py`): a
`identidade`, que diz QUEM é a pessoa e libera o e-mail dela, e a `alunos`, que
diz se ela TEM MATRÍCULA ATIVA. São sete chaves em três `env` da VPS.

Ele roda **na máquina do mantenedor**, com uma linha, e um erro ali custa o pior
tipo de tempo que este projeto tem: o dele, no terminal, sem saber o que fazer
com a tela. Enquanto este guarda não existia, a prova de que o roteiro funciona
era a rodada manual de uma sessão, e prova de sessão morre com a sessão. Era o
único da família `provisionar-par*` sem guarda próprio (TAR-217).

Por isso ele **roda o script de verdade**, contra uma plataforma de mentira em
`tmp_path`, em vez de afirmar coisas sobre o texto dele. É irmão de
`test_provisionar_pares_da_sala_de_aula.py` e mede as mesmas promessas:

1. **Nenhum segredo aparece na tela** (`armadilhas/090`).
2. **Rodar de novo não rotaciona**, e um token que já existe no env do PROVEDOR
   é reusado, nunca substituído.
3. **Os pares ficam iguais dos dois lados**, e `TOKENS_COMPLETOS_PAGES` é CÓPIA
   de `TOKENS_ACEITOS_PAGES`: valores diferentes dariam 403 na resposta
   completa, a Prancheta ficaria sem o e-mail para perguntar à `alunos`, e ela
   fecharia para todo mundo em silêncio.
4. **Os endereços gravados são os dos contratos congelados**, lidos do
   `servers:` de `contracts/identidade.openapi.yaml` e
   `contracts/alunos.openapi.yaml`, e não de uma string fixa deste teste.
5. **Dois tokens distintos**: token é por par.
6. Os caminhos de recusa: pasta errada, `env/pages.env` ausente (a recusa tem de
   ensinar a linha do banco, `provisionar-pages.sh`, porque um env criado aqui
   antes dela travaria a trava de deriva daquele roteiro para sempre), env de
   provedor faltando, os dois pares com o mesmo token, chave repetida, arquivo
   sem quebra de linha no fim, e carregado com `source`.

Uma fronteira medida, e escrita aqui para ninguém a tomar por promessa: a
conferência de **chave repetida** acontece DEPOIS da escrita, não antes. Ela é a
última do roteiro, e o que ela garante é que o mantenedor não fica com um env
mentindo em silêncio (o Docker Compose usaria só a última ocorrência): a recusa
nomeia o arquivo e a chave e aponta as cópias de segurança intactas. Só as
outras recusas prometem não ter escrito nada.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "infra" / "provisionar-pares-da-prancheta.sh"
CONTRATOS = RAIZ / "contracts"

# O estado real da VPS ANTES deste script: a linha do banco
# (`infra/provisionar-pages.sh`) já criou `env/pages.env`, e nenhum dos dois
# pares existe ainda. É este script quem os gera.
SEMENTES = {
    "identidade.env": "DJANGO_SECRET_KEY=y\nTOKENS_ACEITOS_FUNIL=tok-funil\n",
    "alunos.env": "DJANGO_SECRET_KEY=x\nDATABASE_URL=postgres://a\n",
    # Sem quebra de linha no fim DE PROPÓSITO: é o caso que gruda a chave nova
    # no fim da última linha, e a última linha de um env é um valor.
    "pages.env": "DJANGO_SECRET_KEY=p\nDATABASE_URL=postgres://p\nSCRIPT_NAME=/pages",
}

# Os env de PROVEDOR são os únicos que podem chegar com o par já aberto (uma
# rodada anterior, ou uma rotação à mão). Longos de propósito: o script recusa
# token com menos de 32 caracteres.
PROVEDORES = ("identidade.env", "alunos.env")
TOK_IDENTIDADE = "tok-pages-para-identidade-0123456789abcdef"
TOK_ALUNOS = "tok-pages-para-alunos-0123456789abcdef"
JA_ABERTOS = {"identidade.env": TOK_IDENTIDADE, "alunos.env": TOK_ALUNOS}

# (provedor, chave no provedor, consumidor, chave no consumidor)
PARES = [
    ("identidade.env", "TOKENS_ACEITOS_PAGES", "pages.env", "IDENTIDADE_API_TOKEN"),
    ("alunos.env", "TOKENS_ACEITOS_PAGES", "pages.env", "ALUNOS_API_TOKEN"),
]

# (contrato congelado, consumidor, chave do endereço)
ENDERECOS = [
    ("identidade", "pages.env", "IDENTIDADE_API_URL"),
    ("alunos", "pages.env", "ALUNOS_API_URL"),
]

CHAVES_ESCRITAS = {
    "identidade.env": ["TOKENS_ACEITOS_PAGES", "TOKENS_COMPLETOS_PAGES"],
    "alunos.env": ["TOKENS_ACEITOS_PAGES"],
    "pages.env": [
        "IDENTIDADE_API_URL",
        "IDENTIDADE_API_TOKEN",
        "ALUNOS_API_URL",
        "ALUNOS_API_TOKEN",
    ],
}


def _bash() -> str:
    caminho = shutil.which("bash")
    assert caminho, (
        "não achei `bash` nesta máquina. Este guarda EXECUTA o script; sem "
        "interpretador ele não tem o que medir, e isso não é um OK ([INV-CI01])."
    )
    return caminho


def _plataforma(tmp_path: Path, faltando: str | None = None, ja_ligado: bool = False) -> Path:
    raiz = tmp_path / "plataforma"
    (raiz / "env").mkdir(parents=True)
    for nome, conteudo in SEMENTES.items():
        if nome == faltando:
            continue
        if ja_ligado and nome in JA_ABERTOS:
            conteudo = f"{conteudo}TOKENS_ACEITOS_PAGES={JA_ABERTOS[nome]}\n"
        (raiz / "env" / nome).write_text(conteudo, encoding="utf-8")
    return raiz


def _executar(argumentos: list[str], plataforma: str):
    """Roda o script e devolve a saída como TEXTO UTF-8.

    `text=True` sozinho decodifica pelo idioma do sistema (em Windows, cp1252) e
    estoura em `UnicodeDecodeError` na primeira mensagem acentuada. O env é
    HERDADO (com `PLATAFORMA_DIR` por cima), e não fabricado: o script usa
    `openssl`, `stat` e `date`, e um PATH inventado os esconderia.
    """
    ambiente = dict(os.environ)
    ambiente["PLATAFORMA_DIR"] = plataforma
    return subprocess.run(
        argumentos,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=ambiente,
    )


def _rodar(raiz: Path):
    return _executar([_bash(), str(SCRIPT)], str(raiz))


def _valor(raiz: Path, arquivo: str, chave: str) -> str | None:
    texto = (raiz / "env" / arquivo).read_text(encoding="utf-8")
    achado = re.search(rf"^{re.escape(chave)}=(.*)$", texto, re.MULTILINE)
    return achado.group(1).strip() if achado else None


def _fotografia(raiz: Path) -> dict[str, str]:
    """TODO arquivo da pasta `env`, e não só os `*.env`: a cópia de segurança
    que o script deixa para trás também é escrita, e um `.bak-` novo denuncia
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


def test_o_script_existe_e_e_executavel_por_bash():
    """[INV-CI01]: sem isto, os testes abaixo passariam medindo o nada."""
    assert SCRIPT.is_file(), SCRIPT
    texto = SCRIPT.read_text(encoding="utf-8")
    assert texto.startswith("#!/usr/bin/env bash"), "faltou o shebang"
    assert "PAROU POR SEGURANÇA" in texto, "o script não fala a língua fail-closed da casa"


# ------------------------------------------------------------ o caminho feliz


def test_liga_os_dois_pares_e_eles_batem_dos_dois_lados(tmp_path):
    """Promessas 3 e 5: iguais dos dois lados, e dois valores DISTINTOS."""
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
    assert len(set(valores)) == 2, (
        "os dois pares ficaram com o mesmo token. Token é por par: um só faria "
        "a rotação de um derrubar o outro, sem aviso."
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
    """Promessa 4. O `servers:` de cada contrato é a fonte; o script só copia.
    Mudar o contrato (Rito) e esquecer o script deixaria os dois lados coerentes
    consigo mesmos e incoerentes entre si."""
    raiz = _plataforma(tmp_path)
    assert _rodar(raiz).returncode == 0
    for celula, consumidor, chave in ENDERECOS:
        assert _valor(raiz, consumidor, chave) == _endereco_do_contrato(celula), chave


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
        assert segredo not in saida, f"o valor de {chave} foi impresso na tela"
        # Nem um pedaço grande dele: um "eco parcial" para depuração é o jeito
        # mais comum de este guarda ser contornado sem má intenção.
        assert segredo[:16] not in saida, f"um pedaço de {chave} foi impresso na tela"


def test_o_token_que_ja_existia_no_provedor_e_reusado(tmp_path):
    """Promessa 2. Quem manda é o PROVEDOR: o valor vem da lista de aceitos dele
    e o consumidor é realinhado a ela. Regerar aqui derrubaria as chamadas até o
    container do outro lado reiniciar, e o sintoma seria 401 intermitente."""
    raiz = _plataforma(tmp_path, ja_ligado=True)
    r = _rodar(raiz)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "JÁ existiam" in r.stdout, r.stdout
    assert _valor(raiz, "identidade.env", "TOKENS_ACEITOS_PAGES") == TOK_IDENTIDADE
    assert _valor(raiz, "identidade.env", "TOKENS_COMPLETOS_PAGES") == TOK_IDENTIDADE
    assert _valor(raiz, "pages.env", "IDENTIDADE_API_TOKEN") == TOK_IDENTIDADE
    assert _valor(raiz, "alunos.env", "TOKENS_ACEITOS_PAGES") == TOK_ALUNOS
    assert _valor(raiz, "pages.env", "ALUNOS_API_TOKEN") == TOK_ALUNOS


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
    rodada interrompida, ou uma edição à mão. Aí, sem ela,
    `ALUNOS_API_TOKEN=` nasceria colado no fim de `ALUNOS_API_URL=`.
    """
    raiz = _plataforma(tmp_path)
    assert _rodar(raiz).returncode == 0

    alvo = raiz / "env" / "pages.env"
    sobrou = [
        linha
        for linha in alvo.read_text(encoding="utf-8").splitlines()
        if not linha.startswith("ALUNOS_API_TOKEN=")
    ]
    alvo.write_text("\n".join(sobrou), encoding="utf-8")  # e SEM quebra no fim

    r = _rodar(raiz)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _valor(raiz, "pages.env", "ALUNOS_API_URL") == _endereco_do_contrato("alunos")
    assert _valor(raiz, "pages.env", "ALUNOS_API_TOKEN") == _valor(
        raiz, "alunos.env", "TOKENS_ACEITOS_PAGES"
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
    consumidor_chave = {
        "identidade.env": "IDENTIDADE_API_TOKEN",
        "alunos.env": "ALUNOS_API_TOKEN",
    }[provedor]
    raiz = _plataforma(tmp_path)
    assert _rodar(raiz).returncode == 0
    alvo = raiz / "env" / provedor
    novo = "n" * 40
    alvo.write_text(
        re.sub(
            r"^TOKENS_ACEITOS_PAGES=.*$",
            f"TOKENS_ACEITOS_PAGES={novo}",
            alvo.read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        ),
        encoding="utf-8",
    )
    assert _rodar(raiz).returncode == 0
    assert _valor(raiz, "pages.env", consumidor_chave) == novo


# ------------------------------------------------------- os caminhos de recusa


def test_pasta_errada_para_sem_escrever(tmp_path):
    r = _executar([_bash(), str(SCRIPT)], str(tmp_path / "nao-existe"))
    assert r.returncode != 0
    assert "PAROU POR SEGURANÇA" in r.stdout
    assert not (tmp_path / "nao-existe").exists(), "criou a pasta que não achou"


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
    outro, e o script confere isso ANTES de tocar em qualquer arquivo."""
    raiz = _plataforma(tmp_path)
    repetido = "r" * 40
    for arquivo in PROVEDORES:
        alvo = raiz / "env" / arquivo
        alvo.write_text(
            f"{alvo.read_text(encoding='utf-8')}TOKENS_ACEITOS_PAGES={repetido}\n",
            encoding="utf-8",
        )
    antes = _fotografia(raiz)
    r = _rodar(raiz)
    assert r.returncode != 0
    assert "MESMO token" in r.stdout, r.stdout
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
    alvo.write_text(
        f"{alvo.read_text(encoding='utf-8')}"
        f"TOKENS_ACEITOS_PAGES={repetido}\nTOKENS_ACEITOS_PAGES={repetido}\n",
        encoding="utf-8",
    )
    r = _rodar(raiz)
    assert r.returncode != 0, r.stdout
    assert "PAROU POR SEGURANÇA" in r.stdout
    assert "TOKENS_ACEITOS_PAGES aparece 2 vezes" in r.stdout, r.stdout
    assert "env/identidade.env" in r.stdout, r.stdout
    assert ".bak-" in r.stdout, "a recusa não disse onde estão as cópias intactas"


def test_carregado_com_source_recusa_em_vez_de_derrubar_a_sessao():
    """O modo de falha de 24/08: `exit` num shell carregado com `.` derruba a
    sessão interativa do mantenedor. Aconteceu, três vezes."""
    r = _executar([_bash(), "-c", f'. "{SCRIPT}"; echo SOBREVIVI'], "/tmp/nao-existe-mesmo")
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
