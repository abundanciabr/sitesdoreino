"""GUARDAS do dossiê em PDF (degrau 14, critério AC-16 do `CS-PAGES-0001`).

O dossiê é o ARQUIVO que o aluno anexa num e-mail, imprime ou leva a uma
reunião. A vitrine do degrau 13 já lhe deu o link; este degrau lhe dá o anexo.

**Este arquivo lê o PDF de FORA**, com um leitor próprio (`textos_do_pdf` e
`enderecos_clicaveis`, aqui embaixo), e nunca chamando o montador. Um teste que
perguntasse ao `apps.portfolio.dossie` o que ele acabou de escrever mediria o
montador contra ele mesmo, e passaria verde com um arquivo que nenhum leitor
abre. O que estes guardas afirmam sai dos BYTES da resposta.

As seis perguntas que este arquivo responde:

1. **É um PDF de verdade** (AC-16), com página e conteúdo, e não um arquivo
   vazio com o cabeçalho certo.
2. **A ordem é a que o ALUNO escolheu**, e o conjunto de obras é o MESMO da
   vitrine. Duas respostas para a mesma pergunta seria o defeito mais caro
   deste degrau: o cliente receberia um link e um anexo que se contradizem.
3. **Nada de pessoal sai no arquivo** (AC-14, plano §7): nem e-mail, nem nome
   completo, nem o id do aluno. O que vale para a página pública vale para o
   anexo, que vai para as mesmas mãos.
4. **Um aluno nunca baixa o dossiê de outro** (AC-07), e quem não tem crachá
   não baixa nenhum.
5. **Montado no SERVIDOR**: o mesmo pedido, duas vezes, produz o mesmo arquivo,
   byte a byte. É isso que faz o resultado não depender da máquina de quem
   abre.
6. **Cada obra é um clique**: o endereço da peça é uma âncora clicável dentro do
   arquivo, e não só texto impresso.
"""

from __future__ import annotations

import re

import pytest

from apps.portfolio.models import EstadoDoLink

from conftest import ANA, agora

ENDERECO = "/dossie"

APELIDO = "ana-3d"
LINK_UM = "https://cdn.exemplo.test/ana/dragao.png"
LINK_DOIS = "https://cdn.exemplo.test/ana/espada.png"
LINK_TRES = "https://cdn.exemplo.test/ana/castelo.png"
LINK_QUEBRADO = "https://cdn.exemplo.test/ana/sumiu.png"


# ---------------------------------------------------------------------------
# O LEITOR DE PDF DESTE ARQUIVO
# ---------------------------------------------------------------------------
# Vinte linhas, e elas existem para que o guarda leia o arquivo em vez de
# perguntar ao código que o escreveu. O montador desta casa escreve o texto sem
# compressão, de propósito (`apps/portfolio/dossie.py`), e é isso que torna a
# leitura de fora possível sem uma dependência nova só para os testes.

TEXTO_NO_FLUXO = re.compile(rb"\(((?:[^()\\]|\\.)*)\)\s*Tj")
ENDERECO_CLICAVEL = re.compile(rb"/URI\s*\(((?:[^()\\]|\\.)*)\)")
PAGINA = re.compile(rb"/Type\s*/Page\b")


def _sem_escape(cru: bytes) -> str:
    solto = cru.replace(rb"\(", b"(").replace(rb"\)", b")").replace(rb"\\", b"\\")
    return solto.decode("cp1252")


def textos_do_pdf(arquivo: bytes) -> list[str]:
    """Cada pedaço de texto desenhado no arquivo, na ordem em que foi desenhado."""
    return [_sem_escape(achado) for achado in TEXTO_NO_FLUXO.findall(arquivo)]


def enderecos_clicaveis(arquivo: bytes) -> list[str]:
    """Os endereços das âncoras do arquivo, na ordem em que aparecem."""
    return [_sem_escape(achado) for achado in ENDERECO_CLICAVEL.findall(arquivo)]


def quantas_paginas(arquivo: bytes) -> int:
    return len(PAGINA.findall(arquivo))


# ---------------------------------------------------------------------------
# O CENÁRIO
# ---------------------------------------------------------------------------


@pytest.fixture
def logada(client, aluna, site_declarado):
    """A aluna com crachá, na escola declarada."""
    client.cookies["meshcraft_sessao"] = "cookie-opaco-de-ana"
    return client


@pytest.fixture
def portfolio_da_ana(criar_portfolio, criar_peca, site_declarado):
    """Três obras guardadas FORA de ordem, e a ordem que a Ana escolheu."""
    portfolio = criar_portfolio(ANA["id"], apelido=APELIDO, publicada=True)
    criar_peca(
        portfolio,
        ordem=3,
        link=LINK_TRES,
        legenda="Castelo de pedra",
        estado_do_link=EstadoDoLink.RESPONDENDO,
    )
    criar_peca(
        portfolio,
        ordem=1,
        link=LINK_UM,
        legenda="Dragão de escamas",
        destaque=True,
        estado_do_link=EstadoDoLink.RESPONDENDO,
    )
    criar_peca(
        portfolio,
        ordem=2,
        link=LINK_DOIS,
        legenda="Espada élfica",
        estado_do_link=EstadoDoLink.RESPONDENDO,
    )
    return portfolio


# ---------------------------------------------------------------------------
# 1. É UM PDF DE VERDADE (AC-16)
# ---------------------------------------------------------------------------


def test_o_aluno_baixa_um_pdf_com_pagina_e_conteudo(logada, portfolio_da_ana):
    resposta = logada.get(ENDERECO)

    assert resposta.status_code == 200
    assert resposta["Content-Type"] == "application/pdf"
    assert "attachment" in resposta["Content-Disposition"]

    arquivo = resposta.content
    assert arquivo.startswith(b"%PDF-"), "o arquivo não começa como um PDF"
    assert arquivo.rstrip().endswith(b"%%EOF"), "o arquivo não termina como um PDF"
    assert quantas_paginas(arquivo) >= 1, "o arquivo não tem nenhuma página"
    assert textos_do_pdf(arquivo), "o arquivo não tem nenhum texto desenhado"


def test_o_nome_do_arquivo_e_o_apelido_do_aluno(logada, portfolio_da_ana):
    """Quem recebe o anexo vê o nome do arquivo antes de abrir."""
    resposta = logada.get(ENDERECO)

    assert f"portfolio-{APELIDO}.pdf" in resposta["Content-Disposition"]


def test_as_tres_obras_e_o_selo_da_escola_estao_escritos_no_arquivo(
    logada, portfolio_da_ana, criar_estado
):
    criar_estado(
        portfolio_da_ana,
        selo_conferido_em=agora(),
        selo_conferido_por="p_monitora",
    )

    escrito = " ".join(textos_do_pdf(logada.get(ENDERECO).content))

    assert "Dragão de escamas" in escrito
    assert "Espada élfica" in escrito
    assert "Castelo de pedra" in escrito
    assert "Conferido pela escola" in escrito
    assert APELIDO in escrito


def test_a_obra_em_destaque_e_anunciada_no_arquivo(logada, portfolio_da_ana):
    escrito = " ".join(textos_do_pdf(logada.get(ENDERECO).content))

    assert "Em destaque" in escrito


# ---------------------------------------------------------------------------
# 2. A ORDEM DO ALUNO, E O MESMO CONJUNTO DA VITRINE
# ---------------------------------------------------------------------------


def test_as_obras_saem_na_ordem_que_o_aluno_escolheu(logada, portfolio_da_ana):
    """A ordem é a coluna `ordem`, e nunca a ordem em que ele guardou."""
    assert enderecos_clicaveis(logada.get(ENDERECO).content) == [
        LINK_UM,
        LINK_DOIS,
        LINK_TRES,
    ]


def test_o_dossie_mostra_AS_MESMAS_obras_que_a_vitrine_publica(
    client, logada, portfolio_da_ana, criar_peca
):
    """Uma pergunta, uma resposta: o link e o anexo não podem se contradizer.

    O cliente do aluno recebe os dois, e uma obra a mais (ou a menos) num deles
    seria a escola desmentindo o próprio aluno na frente de quem paga.
    """
    criar_peca(
        portfolio_da_ana,
        ordem=4,
        link=LINK_QUEBRADO,
        legenda="Endereço que caiu",
        estado_do_link=EstadoDoLink.QUEBRADO,
        quebrado_desde=agora(),
    )

    no_dossie = enderecos_clicaveis(logada.get(ENDERECO).content)
    pagina = client.get(f"/estudio/{APELIDO}").content.decode()
    na_vitrine = re.findall(r'<img src="([^"]+)"', pagina)

    assert no_dossie == na_vitrine


def test_a_peca_com_o_link_quebrado_fica_de_fora(logada, portfolio_da_ana, criar_peca):
    """Mesma regra da vitrine: endereço que não abre viraria buraco no anexo."""
    criar_peca(
        portfolio_da_ana,
        ordem=4,
        link=LINK_QUEBRADO,
        legenda="Endereço que caiu",
        estado_do_link=EstadoDoLink.QUEBRADO,
        quebrado_desde=agora(),
    )

    arquivo = logada.get(ENDERECO).content

    assert LINK_QUEBRADO not in enderecos_clicaveis(arquivo)
    assert "Endereço que caiu" not in " ".join(textos_do_pdf(arquivo))


# ---------------------------------------------------------------------------
# 3. NADA DE PESSOAL SAI NO ARQUIVO (AC-14, plano §7)
# ---------------------------------------------------------------------------


def test_o_arquivo_nao_leva_email_nome_completo_nem_o_id_do_aluno(
    logada, portfolio_da_ana
):
    """O anexo vai para as mesmas mãos que a página pública, e cala o mesmo."""
    arquivo = logada.get(ENDERECO).content

    assert ANA["email"].encode() not in arquivo
    assert ANA["nome_exibido"].encode() not in arquivo
    assert ANA["id"].encode() not in arquivo


# ---------------------------------------------------------------------------
# 4. A PORTA: um aluno nunca baixa o dossiê de outro (AC-07)
# ---------------------------------------------------------------------------


def test_um_aluno_nao_baixa_o_dossie_de_outro(
    logada, criar_portfolio, criar_peca, site_declarado
):
    """O portfólio do Bruno nasce ANTES do da Ana, e a ordem é o teste.

    Com a porta do isolamento aberta (`do_aluno` devolvendo tudo), a consulta
    entrega a PRIMEIRA linha da tabela, que é a do Bruno. Se a Ana fosse a
    primeira, a mesma falha devolveria o portfólio certo por acidente e este
    guarda passaria verde com a porta arrombada.
    """
    de_bruno = criar_portfolio("p_bruno", apelido="bruno-3d", publicada=True)
    criar_peca(
        de_bruno,
        ordem=1,
        link="https://cdn.exemplo.test/bruno/nave.png",
        legenda="Nave do Bruno",
        estado_do_link=EstadoDoLink.RESPONDENDO,
    )

    da_ana = criar_portfolio(ANA["id"], apelido=APELIDO, publicada=True)
    criar_peca(
        da_ana,
        ordem=1,
        link=LINK_UM,
        legenda="Dragão de escamas",
        estado_do_link=EstadoDoLink.RESPONDENDO,
    )

    arquivo = logada.get(ENDERECO).content

    assert enderecos_clicaveis(arquivo) == [LINK_UM]
    assert "Nave do Bruno" not in " ".join(textos_do_pdf(arquivo))
    assert "bruno-3d" not in " ".join(textos_do_pdf(arquivo))


def test_quem_nao_tem_cracha_nao_baixa_dossie_nenhum(client, portfolio_da_ana):
    """A porta fail-closed da casa responde antes de qualquer montagem (AC-05)."""
    resposta = client.get(ENDERECO)

    assert resposta["Content-Type"] != "application/pdf"
    assert not resposta.content.startswith(b"%PDF-")


def test_sem_obras_a_tela_explica_em_vez_de_baixar_um_arquivo_vazio(
    logada, criar_portfolio
):
    """Anexo vazio num e-mail para um cliente seria pior que não ter botão."""
    criar_portfolio(ANA["id"])

    resposta = logada.get(ENDERECO)

    assert not resposta.content.startswith(b"%PDF-")
    assert "ainda não tem nenhuma obra" in resposta.content.decode()


# ---------------------------------------------------------------------------
# 5. MONTADO NO SERVIDOR: o mesmo arquivo em qualquer máquina (AC-16)
# ---------------------------------------------------------------------------


def test_baixar_duas_vezes_da_o_mesmo_arquivo_byte_a_byte(logada, portfolio_da_ana):
    """Nenhum relógio nem nenhuma máquina entra no arquivo montado."""
    primeiro = logada.get(ENDERECO).content
    segundo = logada.get(ENDERECO).content

    assert primeiro == segundo


def test_uma_estante_grande_vira_mais_de_uma_pagina(
    logada, portfolio_da_ana, criar_peca
):
    """Obra que não cabe desce para a folha seguinte, e não some da última."""
    for numero in range(4, 40):
        criar_peca(
            portfolio_da_ana,
            ordem=numero,
            link=f"https://cdn.exemplo.test/ana/obra-{numero}.png",
            legenda=f"Obra número {numero}",
            estado_do_link=EstadoDoLink.RESPONDENDO,
        )

    arquivo = logada.get(ENDERECO).content

    assert quantas_paginas(arquivo) > 1
    assert "Obra número 39" in " ".join(textos_do_pdf(arquivo))
    assert len(enderecos_clicaveis(arquivo)) == 39


def test_a_legenda_comprida_e_quebrada_em_linhas_e_nao_cortada(
    logada, portfolio_da_ana, criar_peca
):
    """Legenda de 200 letras cabe na coluna, inteira, em mais de uma linha."""
    comprida = (
        "Diorama completo de uma oficina de ferreiro com bancada, martelos, "
        "bigorna, tenaz, brasas acesas, barris de água, prateleira de espadas "
        "e um telhado de madeira envelhecida pela chuva"
    )
    criar_peca(
        portfolio_da_ana,
        ordem=4,
        link="https://cdn.exemplo.test/ana/oficina.png",
        legenda=comprida,
        estado_do_link=EstadoDoLink.RESPONDENDO,
    )

    escrito = textos_do_pdf(logada.get(ENDERECO).content)
    juntos = " ".join(escrito)

    for palavra in ("bigorna", "brasas", "envelhecida", "chuva"):
        assert palavra in juntos, f"a legenda perdeu a palavra {palavra!r}"
    assert not any(
        len(linha) > 120 for linha in escrito
    ), "há linha longa demais para a coluna: a legenda não foi quebrada"


# ---------------------------------------------------------------------------
# 6. CADA OBRA É UM CLIQUE
# ---------------------------------------------------------------------------


def test_o_endereco_de_cada_obra_e_clicavel_dentro_do_arquivo(logada, portfolio_da_ana):
    """Num anexo, o endereço impresso sem âncora obriga o cliente a digitá-lo."""
    arquivo = logada.get(ENDERECO).content

    assert enderecos_clicaveis(arquivo) == [LINK_UM, LINK_DOIS, LINK_TRES]
    assert b"/Subtype /Link" in arquivo
