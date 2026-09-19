"""GUARDA — as fichas de robô em `.claude/agents/` existem e estão bem formadas.

Decisão do mantenedor em 05/09/2026 (registro 20260905-013): todo pedido dele
vira um time na hora, e os sub-agentes desse time nascem prontos porque o rito
fixo mora em três fichas versionadas (construtor, revisor, escrivão), não no
brief que a maestro redige a cada vez. Lei em
`docs/decisoes/PLANO-ORQUESTRACAO-AUTONOMA-DOS-ROBOS.md`, degrau 1.

Em 18/09/2026 entraram cinco fichas novas (conferente, maquinista, procurador,
provador, adversario) pelas frentes da equipe especialista, e nenhuma delas era
conferida aqui: a lista deste guarda continuava fechada nas três primeiras. A
TAR-464 abriu a lista, com a palavra escrita do mantenedor, porque ficha que
ninguém mede vale menos do que parece.

O que este teste prova, e só isto:

1. Cada ficha declarada existe, tem `name` igual ao nome do arquivo e
   `description` preenchida.
2. O frontmatter só usa campos que o Claude Code reconhece: um campo com erro
   de digitação é ignorado em silêncio pelo harness, e a ficha passa a valer
   menos do que parece.
3. Nenhuma ficha pode abrir a caixa de pergunta: sub-agente nunca fala com o
   mantenedor (CLAUDE.md, "Como trabalhar com o mantenedor"); quem pergunta é
   a maestro. Nenhuma pode disparar outros sub-agentes: o time é plano.
4. Quem só mede e relata não tem ferramenta de escrita: quem corrige é o
   despacho.
5. Toda ficha, menos o despacho, declara `model`, e quem preenche molde fixo
   declara modelo de rotina.
6. Cada ficha nova diz em seção própria o que devolve, e bloqueia na fila em
   vez de perguntar ao mantenedor.

O que ele NÃO prova: que a maestro divide o pedido e dispara as fichas em
paralelo. Isso é julgamento de sessão, sem mecanismo, e a seção do CLAUDE.md
diz isso com todas as letras.
"""

from __future__ import annotations

from pathlib import Path
import re

RAIZ = Path(__file__).resolve().parents[2]
FICHAS = RAIZ / ".claude" / "agents"
NOMES = (
    "despacho", "revisor", "escrivao",
    "conferente", "maquinista", "procurador", "provador", "adversario",
)

# As cinco que entraram em 18/09/2026 pelas frentes da equipe especialista, e
# cujo brief exigiu os dois gestos que substituem a pergunta ao mantenedor. As
# três primeiras são anteriores a essa convenção.
DEVOLVEM_E_BLOQUEIAM = ("conferente", "maquinista", "procurador", "provador",
                        "adversario")

# Quem mede e relata, sem corrigir: a própria descrição de cada uma diz "só lê",
# e o despacho é quem aplica a correção que elas apontam.
SO_LEEM = ("revisor", "conferente", "maquinista", "procurador", "adversario")

# Quem preenche molde fixo não usa o modelo de cima. O conferente fica de fora
# de propósito: a ficha dele declara `opus` porque comparar duas fontes e dizer
# qual venceu é julgamento, não preenchimento de molde.
MODELO_DE_ROTINA = ("escrivao", "revisor", "provador", "adversario")

SECAO_DE_DEVOLUCAO = re.compile(r"^#{2,3} (?:\d+\. )?O que você devolve", re.M)

# A tabela de campos da documentação oficial de sub-agentes, lida em 05/09/2026.
CAMPOS_CONHECIDOS = {
    "name", "description", "tools", "disallowedTools", "model",
    "permissionMode", "maxTurns", "skills", "mcpServers", "hooks", "memory",
    "background", "effort", "isolation", "color", "initialPrompt",
    "experimental",
}
FERRAMENTAS_DE_ESCRITA = {"Edit", "Write", "NotebookEdit"}
FERRAMENTAS_PROIBIDAS_A_TODOS = {"AskUserQuestion", "Agent"}


def _frontmatter(caminho: Path) -> dict[str, str]:
    texto = caminho.read_text(encoding="utf-8")
    assert texto.startswith("---\n"), f"{caminho.name}: não começa com frontmatter"
    fim = texto.index("\n---", 4)
    campos: dict[str, str] = {}
    for linha in texto[4:fim].splitlines():
        if not linha.strip():
            continue
        chave, _, valor = linha.partition(":")
        campos[chave.strip()] = valor.strip()
    return campos


def _lista(valor: str) -> set[str]:
    return {item.strip() for item in valor.split(",") if item.strip()}


def test_cada_ficha_declarada_existe_com_o_nome_do_arquivo() -> None:
    for nome in NOMES:
        caminho = FICHAS / f"{nome}.md"
        assert caminho.is_file(), f"falta a ficha {caminho.relative_to(RAIZ)}"
        campos = _frontmatter(caminho)
        assert campos.get("name") == nome, (
            f"{caminho.name}: name={campos.get('name')!r}, esperado {nome!r}"
        )
        assert campos.get("description"), f"{caminho.name}: sem description"


def test_o_frontmatter_so_usa_campos_que_o_harness_reconhece() -> None:
    for nome in NOMES:
        campos = _frontmatter(FICHAS / f"{nome}.md")
        desconhecidos = set(campos) - CAMPOS_CONHECIDOS
        assert not desconhecidos, (
            f"{nome}.md: campo(s) que o Claude Code ignora em silêncio: "
            f"{', '.join(sorted(desconhecidos))}"
        )


def test_nenhuma_ficha_pergunta_ao_mantenedor_nem_dispara_sub_agentes() -> None:
    for nome in NOMES:
        campos = _frontmatter(FICHAS / f"{nome}.md")
        negadas = _lista(campos.get("disallowedTools", ""))
        permitidas = _lista(campos.get("tools", ""))
        faltando = FERRAMENTAS_PROIBIDAS_A_TODOS - negadas
        assert not faltando, (
            f"{nome}.md: disallowedTools precisa negar {', '.join(sorted(faltando))}"
        )
        vazando = FERRAMENTAS_PROIBIDAS_A_TODOS & permitidas
        assert not vazando, f"{nome}.md: tools permite {', '.join(sorted(vazando))}"


def test_toda_ficha_declara_o_modelo_menos_o_despacho() -> None:
    """Sub-agente sem `model` herda o da maestro, que é o modelo de cima.

    Em 06/09/2026 a medição mostrou 53 dos 81 sub-agentes de um fim de semana
    rodando no modelo mais caro sem ninguém ter escolhido (CLAUDE.md, "O que uma
    chamada custa"). Herdar em silêncio não é decisão. O despacho é a exceção
    declarada: o modelo dele vem do brief, e o guarda logo abaixo cobra isso.
    """
    for nome in NOMES:
        if nome == "despacho":
            continue
        modelo = _frontmatter(FICHAS / f"{nome}.md").get("model", "")
        assert modelo, (
            f"{nome}.md: sem `model` no frontmatter, herda o modelo da maestro "
            "(o mais caro) sem ninguém ter escolhido. Declare o modelo na ficha."
        )


def test_quem_preenche_molde_declara_modelo_de_rotina() -> None:
    """Molde fixo não paga o modelo de cima.

    O escrivão preenche registro, evento de fila e armadilha; o revisor lê diff
    contra checklist fechado; o provador sabota linha e lê o resultado; o
    adversário roda golpe já escrito em `02-RED-TEAM.md`. Em nenhum desses o
    modelo caro compra resultado melhor, e risco semântico volta para a maestro.
    """
    for nome in MODELO_DE_ROTINA:
        modelo = _frontmatter(FICHAS / f"{nome}.md").get("model", "")
        assert "opus" not in modelo.lower(), (
            f"{nome}.md: model={modelo!r}. A ficha que segue molde fechado não "
            "usa o modelo de cima; veja CLAUDE.md, \"O que uma chamada custa\"."
        )


def test_o_despacho_sem_model_exige_brief_roteado() -> None:
    texto = (FICHAS / "despacho.md").read_text(encoding="utf-8")
    campos = _frontmatter(FICHAS / "despacho.md")
    if campos.get("model"):
        return
    assert "modelo_recomendado" in texto, (
        "despacho.md: se a ficha não fixa `model`, ela precisa exigir "
        "`modelo_recomendado` no brief. Herdar modelo caro não é decisão."
    )


def test_quem_so_mede_nao_tem_ferramenta_de_escrita() -> None:
    """Quem mede e relata não corrige: quem aplica a correção é o despacho."""
    for nome in SO_LEEM:
        campos = _frontmatter(FICHAS / f"{nome}.md")
        permitidas = _lista(campos.get("tools", ""))
        negadas = _lista(campos.get("disallowedTools", ""))
        assert permitidas, (
            f"{nome}.md: sem lista `tools`, herdaria tudo, inclusive escrita"
        )
        assert not (permitidas & FERRAMENTAS_DE_ESCRITA), (
            f"{nome}.md: tools permite escrita: "
            f"{sorted(permitidas & FERRAMENTAS_DE_ESCRITA)}"
        )
        assert FERRAMENTAS_DE_ESCRITA <= negadas, (
            f"{nome}.md: disallowedTools precisa negar "
            f"{sorted(FERRAMENTAS_DE_ESCRITA - negadas)}"
        )


def test_ficha_nova_devolve_em_secao_propria_e_bloqueia_em_vez_de_perguntar() -> None:
    """A regra que não pode sumir da ficha nova, medida pelo mecanismo dela.

    Sub-agente nunca fala com o mantenedor: bloqueio vira evento na fila mais
    registro com `precisa_do_dono: true` (CLAUDE.md, "Como trabalhar com o
    mantenedor"). Este guarda mede os dois gestos e a seção de devolução, não a
    prosa em volta, porque cada ficha escreve a frase com palavras próprias.
    """
    for nome in DEVOLVEM_E_BLOQUEIAM:
        texto = (FICHAS / f"{nome}.md").read_text(encoding="utf-8")
        assert SECAO_DE_DEVOLUCAO.search(texto), (
            f"{nome}.md: sem a seção \"O que você devolve\"; quem lê o relatório "
            "fica sem o formato exato da devolução."
        )
        assert "python ci/fila.py bloquear" in texto, (
            f"{nome}.md: sem o comando que registra bloqueio na fila. Sem ele a "
            "ficha não tem para onde mandar o que trava, e acaba perguntando."
        )
        assert "precisa_do_dono: true" in texto, (
            f"{nome}.md: sem `precisa_do_dono: true`, o que espera pelo "
            "mantenedor não chega ao livro de ocorrências."
        )


def test_receitas_operacionais_seguem_as_emendas_da_constituicao() -> None:
    for nome in ("RUNBOOK-LOTES.md", "PLAYBOOK.md", "ARMADILHAS-OPERACAO.md"):
        texto = (RAIZ / nome).read_text(encoding="utf-8")
        if nome == "RUNBOOK-LOTES.md":
            texto = texto.split("## §9", 1)[0]
        for linha in texto.splitlines():
            assert not re.search(r"python ci/mergear\.py[^`\n]*--confirmo", linha), (
                f"{nome}: receita de agente induz merge reservado à pista: {linha}"
            )
    for nome in ("despacho", "revisor"):
        texto = (FICHAS / f"{nome}.md").read_text(encoding="utf-8")
        assert "CONSTITUICAO.md" in texto and "Lei 2" in texto
        assert "1 PR = 1 célula" not in texto
        assert "Uma célula por PR;" not in texto


def test_ficha_de_abertura_usa_o_bootstrap_e_preserva_a_regua() -> None:
    texto = (FICHAS / "despacho.md").read_text(encoding="utf-8")
    abertura = texto.split("## 1.", 1)[1].split("## 3.", 1)[0]
    assert "make sessao" in abertura
    assert "ci/sessao.py" in abertura
    assert "git worktree add" not in abertura
    assert "ci/fila.py pegar" not in abertura
    assert "não medido" in abertura
    assert "armadilhas/INDICE.md" in texto
    assert "Padrão de Trabalho" in texto
    receita_contexto = texto.split("--contexto", 1)[1].split("`", 1)[0]
    assert "--sem-container" in receita_contexto


def test_ficha_fecha_pelo_comando_existente_sem_dispensa_de_revisao() -> None:
    texto = (FICHAS / "despacho.md").read_text(encoding="utf-8")
    fechamento = texto.split("## 6.", 1)[1].split("## 7.", 1)[0]
    assert "make pr" in fechamento and "VALIDACAO=" in fechamento
    assert "CONTINUAR=1" in fechamento and "--continuar" in fechamento
    assert "gh pr create" not in fechamento
    assert "revisão de código" in fechamento
    assert "não se equivalem" in fechamento


def test_regra_de_parada_preserva_arquivos_e_commits() -> None:
    arquivos = ('RITOS.md', 'PLAYBOOK.md', 'RUNBOOK-LOTES.md',
                '.claude/agents/despacho.md', 'painel/ia/01-leis-ritos-e-invariantes.md')
    for nome in arquivos:
        texto = (RAIZ / nome).read_text(encoding='utf-8')
        assert 'reset --hard' not in texto, f'{nome}: a parada não pode apagar trabalho'
        assert 'preserve os arquivos e commits' in texto, f'{nome}: a parada precisa preservar a bancada'


# Fontes operacionais, incluindo moldes que voltam a virar instruções.
# 00-LEIA-PRIMEIRO é história declarada no PLAYBOOK; RUNBOOK §9 é retrospectiva.
FONTES_DE_CONTEXTO = (
    "CLAUDE.md", "ARMADILHAS.md", "PLAYBOOK.md", "CAMINHO-DOURADO.md",
    ".claude/agents/despacho.md", "docs/decisoes/RETROSPECTIVA-FASE-D.md",
    "docs/caixa-de-sugestoes/MODELO-DESPACHO.md",
    "docs/despachos/DESPACHO-PARTE-DO-SITE.md",
)


def test_fontes_ativas_usam_contexto_e_indice_so_para_aprofundamento():
    for nome in FONTES_DE_CONTEXTO:
        texto = (RAIZ / nome).read_text(encoding="utf-8")
        assert "contexto direcionado" in texto.lower(), nome
        assert "aprofundamento" in texto.lower(), nome
        normalizado = re.sub(r"[\s`*>]+", " ", texto.lower())
        for proibido in (
            r"leia (?:o )?armadilhas/indice\.md",
            r"ler armadilhas/indice\.md",
            r"armadilhas/indice\.md \| sempre",
            r"antes:.*?\+ armadilhas/indice\.md",
            r"depois deste arquivo e do armadilhas/indice\.md",
        ):
            assert not re.search(proibido, normalizado), (nome, proibido)


def test_escrivao_nao_repete_fechamento_automatizado():
    for nome in ("CLAUDE.md", "RUNBOOK-LOTES.md", ".claude/agents/escrivao.md"):
        texto = (RAIZ / nome).read_text(encoding="utf-8").split("## §9", 1)[0]
        assert "make pr" in texto and "não repita" in texto.lower(), nome
    ficha = (FICHAS / "escrivao.md").read_text(encoding="utf-8")
    assert "Use proactively no fim de todo despacho" not in ficha


def test_receitas_ativas_nao_reconstroem_abertura_nem_merge():
    for nome in ("ARMADILHAS.md", "RITOS.md", "docs/despachos/DESPACHO-PARTE-DO-SITE.md",
                 "docs/caixa-de-sugestoes/MODELO-DESPACHO.md"):
        texto = (RAIZ / nome).read_text(encoding="utf-8")
        assert "git worktree add" not in texto, nome
        assert not re.search(r"python ci/mergear\.py[^`\n]*--confirmo", texto), nome
        assert "make sessao" in texto, nome
