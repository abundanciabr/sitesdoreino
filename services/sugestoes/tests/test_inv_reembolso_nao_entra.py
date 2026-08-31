"""INV-SUG09 — quem foi REEMBOLSADO não entra, e a porta diz por quê.

`docs/decisoes/DECISAO-reembolso-tira-o-acesso.md` (31/08/2026). Substitui o
`test_inv_matricula_reembolsada_entra.py`, que afirmava exatamente o contrário
por decisão do mantenedor em 24/08/2026. **Ele mesmo reverteu**, ao encontrar o
texto antigo publicado no site. Uma terceira mudança é decisão dele, nunca de um
despacho.

------------------------------------------------------------------------------
POR QUE O GUARDA ANTIGO FOI APAGADO E NÃO ADAPTADO — leia isto antes de escrever
o próximo guarda contra uma dependência, porque a lição não é sobre reembolso
------------------------------------------------------------------------------

Ele **tinha parado de medir o que dizia medir**, em silêncio, desde 28/08/2026.

Ele chamava `rede.alunos_diz(email, [{..., "status": "reembolsada"}])`. Quando a
porta migrou de *"tem matrícula?"* para *"em que situação está?"*
(`DECISAO-ex-aluno-e-a-porta-que-explica.md`), `alunos_diz` virou um atalho
legado que traduz **"lista não-vazia = aluno"** e **joga o status fora**. A
partir daquele dia o teste mandava a mesma categoria `aluno` nos cinco casos
parametrizados: ele afirmava que um aluno entra — verdade, e nada a ver com
reembolso.

**Medido em 31/08/2026, e não deduzido:** trocando a lista inteira de status por
`["ISTO-NAO-E-UM-STATUS-DE-VERDADE"]`, o arquivo continuava **verde**. Um
parâmetro que pode virar lixo sem ninguém notar não é um parâmetro.

Ninguém percebeu porque **guarda vazio é verde**, e verde parece saúde. A lei,
os registros do painel e três documentos citaram aquela trava como a prova viva
da decisão de 24/08 por três dias, enquanto quem realmente segurava a regra era
`STATUS_QUE_VALEM`, lá na `alunos`.

**A regra que fica:** dublê que "traduz para o formato antigo" apaga exatamente
a variável que o teste parametriza. Quando o contrato de uma dependência muda de
forma, os guardas escritos contra a forma velha não quebram — eles **emudecem**.
Por isso este arquivo usa `alunos_diz_reembolsado()`, um dublê que fala a língua
de hoje, e por isso cada teste daqui foi visto **vermelho** antes de ser dado
como pronto.
"""

import pytest

from apps.core import sessao as ses
from apps.sugestoes.models import Identidade
from tests.conftest import sessao_do_site

PESSOA = "reembolsado@exemplo.test"


@pytest.fixture(autouse=True)
def cache_limpo():
    # [armadilhas/026] Os caches desta porta são de MÓDULO e vazam entre
    # testes: sem isto, o segundo teste lê a categoria que o primeiro guardou.
    ses.limpar_caches()
    yield
    ses.limpar_caches()


def _abrir(pessoa):
    return pessoa.abrir()


def test_a_categoria_reembolsado_esta_no_mapa_e_nao_da_acesso():
    """Mede a CONSTANTE, e não o comportamento, e isso é de propósito.

    `ESTADO_POR_CATEGORIA` é lista de PERMISSÃO: categoria que não estivesse ali
    já cairia fora do acesso. Ou seja, **o reembolsado seria barrado mesmo se eu
    não tivesse escrito nada aqui** — e é justamente por isso que a linha
    precisa existir e ser medida: sem ela, ele seria barrado com a tela de
    *desconhecido*, e não com a tela que nomeia o reembolso.
    """
    assert ses.ESTADO_POR_CATEGORIA["reembolsado"] == ses.REEMBOLSADO
    assert ses.ESTADO_POR_CATEGORIA["reembolsado"] != ses.DENTRO
    # E não virou apelido do ex-aluno: as telas e os direitos são diferentes.
    assert ses.REEMBOLSADO != ses.EX_ALUNO


def test_quem_foi_reembolsado_nao_entra_na_caixa(rede, db, quadro):
    rede.alunos_diz_reembolsado(PESSOA)
    pessoa = sessao_do_site(rede, email=PESSOA)

    assert not pessoa.esta_dentro
    # 403, e não um redirecionamento mudo: quem está aqui não entrou, e a
    # página precisa dizer isso com o código certo.
    assert _abrir(pessoa).status_code == 403


def test_a_tela_nomeia_o_reembolso_em_vez_de_so_fechar(rede, db, quadro):
    """A escolha do mantenedor entre reusar a tela do ex-aluno e escrever esta.

    Ele recusou reusar: a pessoa ficaria sem saber que o motivo foi o reembolso
    dela. Uma porta que fecha sem dizer por quê é a mesma exclusão com outro
    nome, e é o que este teste impede que volte por conveniência.
    """
    rede.alunos_diz_reembolsado(PESSOA)
    corpo = _abrir(sessao_do_site(rede, email=PESSOA)).content.decode()

    assert "reembolso" in corpo.lower()
    # E NÃO a tela do ex-aluno, que fala de encerramento e oferece a volta.
    assert "Seu acesso à escola foi encerrado" not in corpo
    # A tela NOMEIA o e-mail: quem entrou com a conta errada precisa ver qual.
    assert PESSOA in corpo


def test_o_reembolsado_nao_recebe_o_formulario_de_pedir_para_voltar(rede, db, quadro):
    """O que separa esta tela da do ex-aluno, que TEM o botão desde 29/08.

    O argumento que devolveu o formulário ao ex-aluno é o que o nega aqui: quem
    terminou um curso e quer o do semestre seguinte não está insistindo contra
    uma decisão; quem foi reembolsado está. A recusa também mora na `alunos`
    (`STATUS_QUE_BARRAM_A_FILA`), e as duas camadas são de propósito: esta
    esconde, aquela impede.
    """
    rede.alunos_diz_reembolsado(PESSOA)
    corpo = _abrir(sessao_do_site(rede, email=PESSOA)).content.decode()

    assert "Pedir para voltar" not in corpo
    assert "Pedir liberação" not in corpo


def test_a_ficha_de_identidade_nao_e_cunhada_para_quem_nao_entra(rede, db, quadro):
    """Quem não entra não vira participante da Caixa.

    Cunhar a identidade de alguém barrado encheria a base de gente que não
    participa, e faria a contagem de participantes mentir para o mantenedor.
    """
    rede.alunos_diz_reembolsado(PESSOA)
    sessao_do_site(rede, email=PESSOA)

    assert not Identidade.objects.filter(email=PESSOA).exists()


def test_o_aluno_continua_entrando(rede, db, quadro, matricula):
    """O contraste, sem o qual os testes acima passariam com a porta quebrada.

    Um guarda que só prova que alguém NÃO entra fica verde numa porta que não
    deixa ninguém entrar. Este é o par dele.
    """
    rede.alunos_diz(PESSOA, [matricula])
    pessoa = sessao_do_site(rede, email=PESSOA)

    assert pessoa.esta_dentro
