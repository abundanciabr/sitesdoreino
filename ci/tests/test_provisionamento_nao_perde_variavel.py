"""Script de provisionamento que REESCREVE um env não pode perder variável.

O DEFEITO, MEDIDO EM 25/08/2026
-------------------------------
`infra/provisionar-sugestoes.sh` escreve `env/sugestoes.env` com um `cat >` —
o arquivo inteiro, do zero. O cabeçalho dele prometia *"IDEMPOTENTE: rodar de
novo é seguro"*.

Deixou de ser verdade sem ninguém perceber. O login do site nasceu em 24/08 e
pôs `IDENTIDADE_API_URL` e `IDENTIDADE_API_TOKEN` no env **vivo** da Caixa; o
heredoc daquele script nunca soube delas. Medido no repositório:

    variáveis no molde  (infra/env/sugestoes.env.exemplo) : 13
    variáveis no heredoc (infra/provisionar-sugestoes.sh)  : 11
    diferença: IDENTIDADE_API_TOKEN, IDENTIDADE_API_URL

E o efeito não é cosmético: `services/sugestoes/apps/core/clients.py` lê as duas
com `exigir()` **fora** do bloco que traduz falha em tela amigável. Sem elas, a
porta da Caixa devolve **HTTP 500 em toda visita** — com o deploy verde, porque
o pipeline nunca toca env (INV-P8, Lei 5). É a família da `armadilhas/097`.

O REMÉDIO, E POR QUE ELE É UMA LISTA E NÃO UMA LEITURA
------------------------------------------------------
Cada script ganhou uma **trava de deriva**: antes de reescrever, ele compara as
chaves do arquivo vivo com uma lista `CHAVES_QUE_EU_GERO` e **para** se sobrar
alguma que ele não sabe gerar. Parar é a resposta certa — o token do par
`sugestoes↔identidade` pertence ao `provisionar-identidade.sh`, e um script
adivinhar valor que não é dele seria pior que não rodar.

A lista existe porque o script roda **na VPS**, onde não há Python nem este
repositório: ele não pode "ler o heredoc de si mesmo" de forma confiável em
shell puro. Então a lista é uma cópia consciente — e **cópia consciente sem
guarda é armadilha com data marcada** (§5.11, a mesma lição que fez
`orcamento-de-mudanca.sh` e `mergear.py` ganharem testes que se leem).

Este arquivo é esse guarda. Ele roda no `muralhas` e no `alarme-main` de graça,
porque os dois chamam `python ci/ci.py --apenas testador` (= `pytest ci/tests`).

FAIL-CLOSED DE INSTRUMENTAÇÃO ([INV-CI01])
------------------------------------------
Script ausente, heredoc não encontrado, lista não encontrada ou heredoc vazio
**reprovam**, em vez de o teste passar por não ter o que medir. "Não consegui
olhar" nunca é "está limpo".
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

# (script, arquivo de env que ele reescreve, molde correspondente)
SCRIPTS = [
    (
        "infra/provisionar-sugestoes.sh",
        "env/sugestoes.env",
        "infra/env/sugestoes.env.exemplo",
    ),
    (
        "infra/provisionar-identidade.sh",
        "env/identidade.env",
        "infra/env/identidade.env.exemplo",
    ),
    # A terceira da família (25/08/2026, gênese da área administrativa). Entrou
    # aqui no MESMO PR que lhe deu a trava, e é essa simultaneidade que importa:
    # script que reescreve env inteiro e não está nesta lista é a
    # `armadilhas/111` com data marcada — a trava dele seria uma convenção
    # lembrada, e convenção lembrada não sobrevive ao próximo despacho.
    (
        "infra/provisionar-admin.sh",
        "env/admin.env",
        "infra/env/admin.env.exemplo",
    ),
    # A quarta da família (26/08/2026, gênese da caixa central de avisos).
    # Entrou aqui no MESMO PR do script, pelo motivo escrito acima: script que
    # reescreve env inteiro e não está nesta lista é a `armadilhas/111` com data
    # marcada. E aqui a data é PREVISÍVEL — a Fase 4 do PLANO-MESTRE vai
    # acrescentar um `TOKENS_ACEITOS_FUNIL` a este env, e é exatamente aí que a
    # trava precisa já existir.
    (
        "infra/provisionar-notificacoes.sh",
        "env/notificacoes.env",
        "infra/env/notificacoes.env.exemplo",
    ),
    # A quinta da família (28/08/2026, gênese do fórum da escola). Entrou aqui
    # no MESMO PR do script, pelo motivo escrito acima. E aqui a data também é
    # PREVISÍVEL, por dois lados: `FORUM_PROFESSORES` ganha nome de gente assim
    # que a escola tiver professor, e a lei do fórum já prevê variáveis novas de
    # moderação e de anexo — cada uma é uma chance de o script apagar o que não
    # conhece.
    (
        "infra/provisionar-forum.sh",
        "env/forum.env",
        "infra/env/forum.env.exemplo",
    ),
    # A sexta da família (31/08/2026, provisionamento da gamificação). Entrou
    # aqui no MESMO PR do script, pelo motivo escrito acima. E nesta célula a
    # data é a mais previsível de todas: a escada do
    # `PLANO-CELULA-GAMIFICACAO.md` §6 tem doze degraus pela frente, e dois
    # deles já sabem o nome da variável que vão pedir a este env
    # (`TOKENS_ACEITOS_FORUM` no degrau 18, `TOKENS_ACEITOS_FUNIL` no 20).
    # Cada uma é uma chance de o script apagar o que não conhece.
    (
        "infra/provisionar-gamificacao.sh",
        "env/gamificacao.env",
        "infra/env/gamificacao.env.exemplo",
    ),
    # A sétima da família (04/09/2026, provisionamento das encomendas). Entrou
    # aqui no MESMO PR do script, pelo motivo escrito acima — e nesta célula a
    # data é a mais previsível de toda a lista: a escada da
    # `DECISAO-fila-do-primeiro-dolar.md` §7 tem os degraus 2.2 a 2.14 pela
    # frente, e TRÊS deles já sabem o nome da variável que vão pedir a este env
    # (`TOKENS_ACEITOS_ADMIN` no degrau 2.14, `REDIS_STREAMS_URL` quando o relay
    # nascer, e a lista do plantão na Fase 7). Cada uma é uma chance de o script
    # apagar o que não conhece.
    # A oitava da família (04/09/2026, provisionamento da medição). Entrou aqui
    # no MESMO PR do script, pelo motivo escrito acima. Este é o env mais curto
    # da plataforma (três chaves), e é justamente por isso que a trava importa:
    # o degrau 7.4 da escada do painel de gestão já sabe o nome da variável que
    # vai pedir a ele (`TOKENS_ACEITOS_ADMIN`, quando a admin passar a ler os
    # números daqui), e um arquivo de três linhas é o mais fácil de reescrever
    # sem pensar.
    (
        "infra/provisionar-metricas.sh",
        "env/metricas.env",
        "infra/env/metricas.env.exemplo",
    ),
    (
        "infra/provisionar-encomendas.sh",
        "env/encomendas.env",
        "infra/env/encomendas.env.exemplo",
    ),
    # A nona da família (05/09/2026, provisionamento da sala de aula). Entrou
    # aqui no MESMO PR do script, pelo motivo escrito acima. E a data é
    # previsível por quatro lados: a escada do `PLANO-CELULA-CURSOS.md` §10 já
    # sabe o nome de quatro variáveis que vão pedir a este env
    # (`TOKENS_ACEITOS_ADMIN` no editor de aulas, `CURSOS_PROFESSORES` no
    # plantão do degrau 2.2, `ANTHROPIC_API_KEY` e `ANTHROPIC_WORKSPACE_ID` no
    # Assistente de laudo do 2.3). Cada uma é uma chance de o script apagar o
    # que não conhece.
    (
        "infra/provisionar-cursos.sh",
        "env/cursos.env",
        "infra/env/cursos.env.exemplo",
    ),
    # A décima da família (05/09/2026, provisionamento das Páginas do aluno).
    # Esta é a ÚNICA que não entrou no mesmo PR do script, e a exceção está
    # dita na cara em vez de escondida: o mandato do PR #1148 autorizava
    # `infra/` e proibia `ci/`, então aquele robô parou e declarou a dívida em
    # vez de atravessar a cerca. Ele estava certo, e o intervalo entre os dois
    # PRs é justamente a janela em que a convenção era só lembrança — que é o
    # que esta lista existe para não depender.
    #
    # A data da deriva é previsível por três lados, todos escritos no próprio
    # roteiro: o degrau 06 do `PLANO-PORTFOLIO-DO-ALUNO.md` vai pedir
    # `IDENTIDADE_API_URL` e `IDENTIDADE_API_TOKEN` a este env (a porta que
    # pergunta quem é a pessoa), o mesmo degrau vai pedir o par com a `alunos`
    # (a matrícula ativa), e a tela da equipe do degrau 11 vai pedir um
    # `TOKENS_ACEITOS_ADMIN`. Cada uma é uma chance de o roteiro apagar o que
    # não conhece.
    (
        "infra/provisionar-pages.sh",
        "env/pages.env",
        "infra/env/pages.env.exemplo",
    ),
]

RE_LISTA = re.compile(r'^CHAVES_QUE_EU_GERO="([^"]*)"', re.MULTILINE)
RE_CHAVE = re.compile(r"^([A-Z_][A-Z0-9_]*)=", re.MULTILINE)


def _texto(caminho: str) -> str:
    alvo = RAIZ / caminho
    assert alvo.is_file(), (
        f"{caminho} não existe. Este guarda não tem o que medir, e isso não é "
        "um OK — [INV-CI01]."
    )
    conteudo = alvo.read_text(encoding="utf-8")
    assert conteudo.strip(), f"{caminho} está vazio."
    return conteudo


def _chaves_do_heredoc(fonte: str, script: str, env: str) -> set[str]:
    """As chaves que o `cat > <env> <<ENV … ENV` realmente escreve."""
    abertura = re.search(
        rf"cat > {re.escape(env)} <<(\w+)\n", fonte
    )
    assert abertura, (
        f"não achei o heredoc `cat > {env} <<…` em {script}. Se a forma de "
        "escrever o env mudou, este guarda precisa aprender a nova — não o "
        "apague, ensine-o."
    )
    fim = re.search(rf"^{abertura.group(1)}$", fonte[abertura.end():], re.MULTILINE)
    assert fim, f"heredoc de {script} aberto e não fechado."
    corpo = fonte[abertura.end(): abertura.end() + fim.start()]
    chaves = set(RE_CHAVE.findall(corpo))
    assert chaves, f"o heredoc de {script} não escreve chave nenhuma."
    return chaves


def _chaves_da_lista(fonte: str, script: str) -> set[str]:
    achado = RE_LISTA.search(fonte)
    assert achado, (
        f"{script} não declara `CHAVES_QUE_EU_GERO`. É essa lista que faz a "
        "trava de deriva funcionar na VPS; sem ela o script volta a poder "
        "apagar variável em silêncio."
    )
    chaves = set(achado.group(1).split())
    assert chaves, f"`CHAVES_QUE_EU_GERO` de {script} está vazia."
    return chaves


@pytest.mark.parametrize("script,env,molde", SCRIPTS, ids=lambda v: Path(v).name)
def test_a_lista_da_trava_e_o_heredoc_nao_derivaram(script, env, molde):
    """A cópia consciente, vigiada.

    Se alguém acrescentar uma variável ao heredoc e esquecer a lista, a trava
    passaria a acusar falsamente essa variável como "não sei gerar" e o script
    pararia sempre. Se remover do heredoc e esquecer a lista, a trava deixaria
    passar um arquivo que o script vai truncar. Os dois lados quebram.
    """
    fonte = _texto(script)
    do_heredoc = _chaves_do_heredoc(fonte, script, env)
    da_lista = _chaves_da_lista(fonte, script)
    assert do_heredoc == da_lista, (
        f"{script}: o heredoc e a `CHAVES_QUE_EU_GERO` divergiram.\n"
        f"  só no heredoc: {sorted(do_heredoc - da_lista) or '—'}\n"
        f"  só na lista:   {sorted(da_lista - do_heredoc) or '—'}\n"
        "Atualize os DOIS na mesma edição."
    )


@pytest.mark.parametrize("script,env,molde", SCRIPTS, ids=lambda v: Path(v).name)
def test_tudo_que_o_script_escreve_esta_declarado_no_molde(script, env, molde):
    """O `.env.exemplo` é a documentação do que a célula precisa para subir.

    A direção é só esta: **heredoc ⊆ molde**. O contrário é legítimo e
    acontece hoje — `sugestoes.env.exemplo` declara `IDENTIDADE_API_*` e
    `SUGESTOES_APROVADORES`, que pertencem a OUTROS scripts. Exigir igualdade
    obrigaria cada script a gerar chave que não é dele, que é exatamente o erro
    que a trava de deriva existe para impedir.
    """
    do_heredoc = _chaves_do_heredoc(_texto(script), script, env)
    do_molde = set(RE_CHAVE.findall(_texto(molde)))
    assert do_molde, f"{molde} não declara chave nenhuma."
    faltando = do_heredoc - do_molde
    assert not faltando, (
        f"{script} escreve em {env} chave(s) que {molde} não documenta: "
        f"{sorted(faltando)}.\nQuem lê o molde para saber o que a célula "
        "precisa ficaria sem saber."
    )


@pytest.mark.parametrize("script,env,molde", SCRIPTS, ids=lambda v: Path(v).name)
def test_a_trava_de_deriva_existe_e_para_o_script(script, env, molde):
    """A lista sem o `if` que a usa seria decoração.

    Não basta declarar as chaves: o script tem de comparar o arquivo vivo com
    elas e **sair diferente de zero** quando sobrar chave. Sem esta asserção,
    alguém poderia apagar o bloco `if` e o teste acima continuaria verde.
    """
    fonte = _texto(script)
    assert f"if [ -f {env} ]; then" in fonte, (
        f"{script}: não achei o `if [ -f {env} ]` da trava de deriva."
    )
    assert "SOBRANDO" in fonte, f"{script}: a trava não acumula as chaves que sobram."
    assert "PAROU POR SEGURANÇA" in fonte, (
        f"{script}: a trava não fala a língua fail-closed da casa."
    )
    assert re.search(r"^\s*exit 1$", fonte, re.MULTILINE), (
        f"{script}: a trava não sai com código de erro — avisar e continuar "
        "escrevendo por cima seria pior que não avisar."
    )


def test_o_guarda_tem_dentes():
    """Prova que a comparação REPROVA quando as cópias divergem.

    Guarda que nunca fica vermelho é decoração. Aqui a divergência é fabricada
    em memória, sem tocar nos scripts reais.
    """
    fonte_falsa = (
        'CHAVES_QUE_EU_GERO="A B"\n'
        "cat > env/falso.env <<ENV\n"
        "A=1\n"
        "B=2\n"
        "C=3\n"
        "ENV\n"
    )
    do_heredoc = _chaves_do_heredoc(fonte_falsa, "falso.sh", "env/falso.env")
    da_lista = _chaves_da_lista(fonte_falsa, "falso.sh")
    assert do_heredoc != da_lista
    assert do_heredoc - da_lista == {"C"}


def test_o_caso_real_que_originou_este_guarda_esta_fechado():
    """A regressão exata: o heredoc da Caixa não escreve as chaves do login.

    Ele continua não escrevendo — e está CERTO, porque o token do par é gerado
    pelo `provisionar-identidade.sh`. O que não pode voltar é o script rodar
    assim mesmo: as duas chaves têm de estar no molde (documentadas) e a trava
    tem de existir para barrar a re-execução.
    """
    fonte = _texto("infra/provisionar-sugestoes.sh")
    do_heredoc = _chaves_do_heredoc(
        fonte, "infra/provisionar-sugestoes.sh", "env/sugestoes.env"
    )
    do_molde = set(RE_CHAVE.findall(_texto("infra/env/sugestoes.env.exemplo")))

    assert {"IDENTIDADE_API_URL", "IDENTIDADE_API_TOKEN"} <= do_molde, (
        "o molde da Caixa deixou de documentar as chaves do login — quem for "
        "provisionar do zero vai subir a célula com a porta quebrada."
    )
    assert not ({"IDENTIDADE_API_URL", "IDENTIDADE_API_TOKEN"} & do_heredoc), (
        "o provisionar-sugestoes.sh passou a escrever as chaves do login. Se "
        "isso foi de propósito, ele precisa saber GERAR o token do par — que "
        "hoje pertence ao provisionar-identidade.sh — e a trava de deriva e "
        "este teste precisam ser atualizados juntos."
    )
