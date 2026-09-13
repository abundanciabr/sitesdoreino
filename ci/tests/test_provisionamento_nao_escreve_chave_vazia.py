"""Script de provisionamento não pode gravar em branco um valor que ele não sabe gerar.

O DEFEITO, MEDIDO EM 05/09/2026 NO `origin/main` (TAR-172)
----------------------------------------------------------
`infra/provisionar-forum.sh` reescreve `env/forum.env` inteiro, e a linha 226 do
heredoc era, literalmente:

    FORUM_PROFESSORES=

Nenhuma releitura em lugar nenhum do arquivo. Logo acima, no MESMO script,
`ADMIN_EMAILS`, `ANTHROPIC_API_KEY` e `ANTHROPIC_WORKSPACE_ID` já eram
preservadas por `ler_de`. Ou seja: reinstalar o fórum apagava a lista de
professores que o mantenedor tivesse escrito à mão, em silêncio, com a
publicação verde. Quem estava na lista e não é administrador perdia o acesso, e
ninguém descobria até alguém reclamar.

É a `armadilhas/111` viva dentro do próprio script que esta casa usava como
MOLDE de preservação (a TAR-170 o copiou para a `cursos`). Fail-closed por falta
de valor é indistinguível de fail-closed por decisão, e é isso que torna esta
classe cara.

POR QUE ESTE GUARDA É SEPARADO DO `test_provisionamento_nao_perde_variavel.py`
------------------------------------------------------------------------------
Aquele guarda vigia a DERIVA entre duas cópias conscientes: a lista
`CHAVES_QUE_EU_GERO` e as chaves do heredoc. Ele estava verde neste caso, e
corretamente: `FORUM_PROFESSORES` estava nos dois lados. O que faltava medir era
o VALOR, não a presença da chave. Uma chave presente e gravada em branco passa
por toda conferência de presença, e é por isso que o defeito sobreviveu oito
dias no `origin/main`.

A REGRA, EM UMA FRASE
---------------------
Todo valor que o heredoc grava tem de vir de algum lugar DENTRO do script: um
literal constante, um segredo que ele gera, ou uma releitura do arquivo vivo.
Chave gravada em branco, ou apontando para variável que o script nunca atribui,
é dado do mantenedor sendo apagado.

E a regra é aplicada a TODOS os `infra/provisionar-*.sh`, não só ao do fórum,
porque a classe é maior que o caso: cada célula nova copia o roteiro da anterior.

COMENTÁRIO NÃO CONTA COMO ATRIBUIÇÃO
------------------------------------
As linhas de comentário são retiradas antes de procurar as atribuições, e isso é
o coração do guarda, não um detalhe: a sabotagem mais provável (e a que o rito
de mutação desta casa manda encenar) é comentar a linha da releitura. Se o
comentário contasse, o guarda ficaria verde exatamente no instante em que o dado
voltasse a ser apagado.

FAIL-CLOSED DE INSTRUMENTAÇÃO ([INV-CI01])
------------------------------------------
Nenhum script encontrado, heredoc aberto e não fechado, ou heredoc sem chave
nenhuma REPROVAM, em vez de o teste passar por não ter o que medir. "Não
consegui olhar" nunca é "está limpo".
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

# O piso existe para o caso em que o glob para de achar os scripts (pasta
# renomeada, teste rodado de outro lugar): zero script é ERRO de instrumento, e
# um guarda que colete zero caso passaria calado.
MINIMO_DE_SCRIPTS_COM_HEREDOC = 10

RE_ABERTURA = re.compile(r"cat > (\S+) <<(\w+)\n")
RE_LINHA_DE_CHAVE = re.compile(r"^([A-Z_][A-Z0-9_]*)=(.*)$")
RE_REFERENCIA = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)")
# Atribuição de shell. O valor para no `;` de propósito: uma linha inteira como
# valor engoliria a segunda atribuição de `ID="${1:-}"; STAFF="${2:-}"`, e o
# guarda acusaria `$STAFF` de órfã sem ela ser.
RE_ATRIBUICAO = re.compile(r"(?:^|[\s;])(?:export\s+)?([A-Z_][A-Z0-9_]*)=([^;\n]*)")
# `read -r -s SEGREDO` também atribui, e é como o mantenedor digita um segredo
# sem ele aparecer na tela. Ignorá-la acusaria de órfã uma variável que existe.
RE_LEITURA_DO_TECLADO = re.compile(r"(?:^|[\s;])read\s+(?:-\S+\s+)*([A-Z_][A-Z0-9_]*)")
DIGITADO = "(digitado pelo mantenedor)"


def _scripts() -> list[Path]:
    achados = sorted((RAIZ / "infra").glob("provisionar-*.sh"))
    assert achados, (
        "não achei nenhum infra/provisionar-*.sh. Este guarda não tem o que "
        "medir, e isso não é um OK: [INV-CI01]."
    )
    return achados


def _heredocs(fonte: str, nome: str) -> list[tuple[str, str]]:
    """Cada `cat > <env> <<MARCA … MARCA` do script, como (env, corpo)."""
    saida = []
    for abertura in RE_ABERTURA.finditer(fonte):
        env, marca = abertura.group(1), abertura.group(2)
        fim = re.search(rf"^{marca}$", fonte[abertura.end():], re.MULTILINE)
        assert fim, f"{nome}: heredoc `cat > {env} <<{marca}` aberto e não fechado."
        saida.append((env, fonte[abertura.end(): abertura.end() + fim.start()]))
    return saida


def _sem_comentarios_nem_heredocs(fonte: str, nome: str) -> str:
    """A fonte onde as atribuições contam: fora dos comentários e dos heredocs.

    Os heredocs saem porque as próprias linhas `CHAVE=valor` que eles gravam
    pareceriam atribuições de shell, e aí toda chave se declararia atribuída por
    si mesma. Os comentários saem pelo motivo escrito no topo deste arquivo.
    """
    limpa = fonte
    for _env, corpo in _heredocs(fonte, nome):
        limpa = limpa.replace(corpo, "\n")
    return "\n".join(
        linha for linha in limpa.splitlines() if not linha.lstrip().startswith("#")
    )


def _valores_atribuidos(limpa: str) -> dict[str, list[str]]:
    """Cada variável do script e TODOS os valores que ele lhe atribui."""
    valores: dict[str, list[str]] = {}
    for achado in RE_ATRIBUICAO.finditer(limpa):
        valores.setdefault(achado.group(1), []).append(achado.group(2))
    for achado in RE_LEITURA_DO_TECLADO.finditer(limpa):
        valores.setdefault(achado.group(1), []).append(DIGITADO)
    return valores


def _com_heredoc() -> list[tuple[str, str, str]]:
    """(caminho do script, env que ele grava, corpo do heredoc)."""
    casos = []
    for script in _scripts():
        nome = f"infra/{script.name}"
        fonte = script.read_text(encoding="utf-8")
        for env, corpo in _heredocs(fonte, nome):
            casos.append((nome, env, corpo))
    return casos


CASOS = _com_heredoc()
# O corpo do heredoc no id deixaria a saída do pytest ilegível; o nome do script
# com o env que ele grava identifica o caso sem ambiguidade.
NOMES = [f"{Path(nome).name}->{env}" for nome, env, _corpo in CASOS]


def test_o_guarda_esta_medindo_a_familia_inteira():
    """Instrumento conferido antes do veredito.

    Se um dia o glob parar de achar os scripts, ou o `cat >` mudar de forma, os
    testes abaixo passariam por não ter caso nenhum coletado. Aqui isso vira
    vermelho, com o número medido na tela.
    """
    assert len(CASOS) >= MINIMO_DE_SCRIPTS_COM_HEREDOC, (
        f"só achei {len(CASOS)} heredoc(s) de env em infra/provisionar-*.sh, e "
        f"esperava pelo menos {MINIMO_DE_SCRIPTS_COM_HEREDOC}. Ou os scripts "
        "sumiram, ou a forma de escrever o env mudou e este guarda precisa "
        "aprender a nova. Não o apague, ensine-o."
    )
    nomes = {nome for nome, _env, _corpo in CASOS}
    assert "infra/provisionar-forum.sh" in nomes, (
        "o script que originou este guarda saiu da medição."
    )


@pytest.mark.parametrize("script,env,corpo", CASOS, ids=NOMES)
def test_nenhuma_chave_do_heredoc_nasce_em_branco(script, env, corpo):
    """O caso exato da TAR-172: `CHAVE=` e nada do outro lado do igual.

    Uma linha assim grava em branco em TODA execução. Se o valor é do
    mantenedor, o script o apaga; se é da célula, ela sobe sem ele. Nos dois
    casos o deploy fica verde.
    """
    linhas = [
        achado.group(1)
        for achado in (RE_LINHA_DE_CHAVE.match(l) for l in corpo.splitlines())
        if achado and not achado.group(2).strip()
    ]
    assert not linhas, (
        f"{script} grava em {env} chave(s) SEMPRE em branco: {sorted(linhas)}.\n"
        "Se o valor é escrito à mão pelo mantenedor, releia-o do arquivo vivo "
        'antes do heredoc (`CHAVE="$(ler_de "$ENV_…" CHAVE)"`) e grave a '
        "variável. Rodar de novo não pode apagar o que ele digitou."
    )


@pytest.mark.parametrize("script,env,corpo", CASOS, ids=NOMES)
def test_todo_valor_do_heredoc_vem_de_algum_lugar_do_script(script, env, corpo):
    """A mesma perda, com uma variável no lugar do branco.

    Trocar `CHAVE=` por `CHAVE=$VALOR` sem nunca atribuir `$VALOR` não conserta
    nada: com `set -u` o script morre no meio, e sem ele grava branco do mesmo
    jeito. É esta asserção que fica vermelha quando alguém apaga (ou comenta) a
    linha da releitura, que é a sabotagem que o rito manda encenar.
    """
    fonte = (RAIZ / script).read_text(encoding="utf-8")
    atribuidas = set(_valores_atribuidos(_sem_comentarios_nem_heredocs(fonte, script)))

    orfas = {}
    for linha in corpo.splitlines():
        achado = RE_LINHA_DE_CHAVE.match(linha)
        if not achado:
            continue
        faltando = sorted(
            nome
            for nome in RE_REFERENCIA.findall(achado.group(2))
            if nome not in atribuidas
        )
        if faltando:
            orfas[achado.group(1)] = faltando

    assert not orfas, (
        f"{script} grava em {env} chave(s) cujo valor não vem de lugar nenhum "
        f"do script: {orfas}.\nOu o script gera esse valor, ou o relê do "
        'arquivo vivo com `ler_de`. Se a linha da releitura foi apagada ou '
        "comentada, é isso que este guarda está acusando: rodar de novo voltaria "
        "a apagar o que estava lá."
    )


@pytest.mark.parametrize("script,env,corpo", CASOS, ids=NOMES)
def test_variavel_do_heredoc_nao_e_so_um_branco_com_chapeu(script, env, corpo):
    """A terceira forma da mesma perda, e a mais fácil de escrever sem perceber.

    `PROFESSORES=""` no alto do arquivo e `FORUM_PROFESSORES=$PROFESSORES` no
    heredoc gravam exatamente o mesmo branco que a linha original da TAR-172,
    e passariam pelos dois testes acima. Variável cujas ÚNICAS atribuições são
    vazias é o defeito usando chapéu.

    Atribuir vazio faz parte de vários caminhos legítimos (o `else` de um `if`,
    o valor inicial de algo que a seguir recebe conteúdo). Por isso a régua é
    "nenhuma atribuição não vazia", e não "existe uma atribuição vazia".
    """
    fonte = (RAIZ / script).read_text(encoding="utf-8")
    valores = _valores_atribuidos(_sem_comentarios_nem_heredocs(fonte, script))

    def so_vazia(nome: str) -> bool:
        atribuicoes = valores.get(nome)
        if not atribuicoes:
            return False  # a órfã é assunto do teste acima
        return all(v.strip() in ("", '""', "''") for v in atribuicoes)

    culpadas = {}
    for linha in corpo.splitlines():
        achado = RE_LINHA_DE_CHAVE.match(linha)
        if not achado:
            continue
        referencias = RE_REFERENCIA.findall(achado.group(2))
        # Só quando a linha inteira é a variável: dentro de uma URL, um pedaço
        # vazio é do dono do outro pedaço, não desta medição.
        if len(referencias) == 1 and achado.group(2).strip().strip('"') in (
            f"${referencias[0]}",
            f"${{{referencias[0]}}}",
            f"${{{referencias[0]}:-}}",
        ) and so_vazia(referencias[0]):
            culpadas[achado.group(1)] = referencias[0]

    assert not culpadas, (
        f"{script} grava em {env} chave(s) a partir de variável que ele só "
        f"atribui vazia: {culpadas}.\nÉ o mesmo branco da TAR-172 com outro "
        "nome. Releia o valor do arquivo vivo, ou gere-o."
    )


def test_a_conferencia_do_forum_compara_com_a_copia_e_nao_consigo_mesma():
    """A lição mais cara do PR #1267, agora com dentes.

    Conferir a preservação comparando o arquivo escrito com a VARIÁVEL que
    escreveu a linha é a variável se conferindo a si mesma: apagar a releitura
    zera os dois lados ao mesmo tempo, e a conferência fica VERDE no exato
    instante em que apaga o dado. O outro lado da comparação tem de ser a cópia
    `.bak-<epoch>`, que é o único registro do estado anterior.
    """
    fonte = (RAIZ / "infra/provisionar-forum.sh").read_text(encoding="utf-8")

    assert 'BAK="$ENV_FORUM.bak-$(date +%s)"' in fonte, (
        "provisionar-forum.sh não guarda o NOME da cópia de segurança numa "
        "variável. Sem esse nome não há com o que comparar depois."
    )
    assert 'ANTES_PROFESSORES="$(ler_de "$BAK" FORUM_PROFESSORES)"' in fonte, (
        "provisionar-forum.sh não lê a lista de professores DA CÓPIA. Comparar "
        "com a variável que escreveu a linha não testa nada."
    )
    assert (
        '[ "$(ler_de "$ENV_FORUM" FORUM_PROFESSORES)" = "$ANTES_PROFESSORES" ]'
        in fonte
    ), (
        "provisionar-forum.sh não compara o que FICOU no arquivo com o que "
        "estava na cópia."
    )
    assert "PERDI A LISTA DE PROFESSORES" in fonte, (
        "a conferência não avisa em português que perdeu a lista. Uma perda "
        "silenciosa é o defeito inteiro de volta."
    )


def test_cursos_preserva_as_tres_chaves_que_o_roteiro_de_pares_acrescenta():
    """O roteiro principal não pode apagar o que o roteiro de pares escreve."""
    script = "infra/provisionar-cursos.sh"
    fonte = (RAIZ / script).read_text(encoding="utf-8")
    esperado = {
        "TOKENS_ACEITOS_ADMIN": "T_ADMIN",
        "CATALOGO_API_URL": "CATALOGO_URL",
        "TOKEN_CATALOGO": "T_CATALOGO",
    }
    for chave, variavel in esperado.items():
        assert f"{chave}=${variavel}" in fonte
        assert f'ler_de "$ENV_CURSOS" {chave}' in fonte or chave == "CATALOGO_API_URL"

    def orfas(texto: str) -> set[str]:
        corpo = _heredocs(texto, script)[0][1]
        valores = set(
            _valores_atribuidos(_sem_comentarios_nem_heredocs(texto, script))
        )
        resultado = set()
        for linha in corpo.splitlines():
            achado = RE_LINHA_DE_CHAVE.match(linha)
            if not achado:
                continue
            resultado.update(
                chave
                for chave in RE_REFERENCIA.findall(achado.group(2))
                if chave not in valores
            )
        return resultado

    assert not orfas(fonte)
    def preservacoes_ausentes(texto: str) -> set[str]:
        return {
            chave
            for linha, chave in (
                (
                    'T_ADMIN="$(ler_de "$ENV_CURSOS" TOKENS_ACEITOS_ADMIN)"',
                    "TOKENS_ACEITOS_ADMIN",
                ),
                (
                    'T_CATALOGO="$(ler_de "$ENV_CURSOS" TOKEN_CATALOGO)"',
                    "TOKEN_CATALOGO",
                ),
            )
            if linha not in texto.splitlines()
        }

    assert not preservacoes_ausentes(fonte)
    for linha, chave in (
        (
            'T_ADMIN="$(ler_de "$ENV_CURSOS" TOKENS_ACEITOS_ADMIN)"',
            "TOKENS_ACEITOS_ADMIN",
        ),
        (
            'T_CATALOGO="$(ler_de "$ENV_CURSOS" TOKEN_CATALOGO)"',
            "TOKEN_CATALOGO",
        ),
        ):
        sabotada = fonte.replace(f"{linha}\n", "")
        assert chave in preservacoes_ausentes(sabotada)


SCRIPT_DE_MENTIRA = """#!/usr/bin/env bash
RELIDA="$(ler_de "$ENV_X" X_RELIDA)"
NASCE_VAZIA=""
cat > env/mentira.env <<ENV
EM_BRANCO=
ORFA=$NUNCA_ATRIBUIDA
PRESERVADA=$RELIDA
BRANCO_COM_CHAPEU=$NASCE_VAZIA
ENV
"""


def test_o_guarda_tem_dentes():
    """Prova que as três regras acusam, com o defeito fabricado em memória.

    Guarda que nunca fica vermelho é decoração. E a prova roda pelas MESMAS
    funções que os testes de cima usam, de propósito: reescrever a lógica aqui
    faria este teste continuar verde no dia em que alguém quebrasse aquela, que
    é justamente o buraco que ele existe para não ter.
    """
    heredocs = _heredocs(SCRIPT_DE_MENTIRA, "mentira.sh")
    assert len(heredocs) == 1
    corpo = heredocs[0][1]
    valores = _valores_atribuidos(
        _sem_comentarios_nem_heredocs(SCRIPT_DE_MENTIRA, "mentira.sh")
    )

    em_branco = [
        m.group(1)
        for m in (RE_LINHA_DE_CHAVE.match(l) for l in corpo.splitlines())
        if m and not m.group(2).strip()
    ]
    assert em_branco == ["EM_BRANCO"], "a chave gravada em branco passou batida."

    assert "NUNCA_ATRIBUIDA" not in valores, "a órfã foi dada como atribuída."
    assert "RELIDA" in valores, "a releitura não foi reconhecida como atribuição."
    assert valores["NASCE_VAZIA"] == ['""'], "o branco com chapéu se escondeu."

    # E a sabotagem do rito: comentar a linha da releitura tem de valer o mesmo
    # que apagá-la, senão o guarda fica verde no instante em que o dado volta a
    # ser apagado.
    comentado = SCRIPT_DE_MENTIRA.replace(
        'RELIDA="$(ler_de', '# RELIDA="$(ler_de'
    )
    assert "RELIDA" not in _valores_atribuidos(
        _sem_comentarios_nem_heredocs(comentado, "mentira.sh")
    ), "comentar a linha da releitura precisa contar como apagá-la."
