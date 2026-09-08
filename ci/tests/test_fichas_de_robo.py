"""GUARDA — as fichas de robô em `.claude/agents/` existem e estão bem formadas.

Decisão do mantenedor em 05/09/2026 (registro 20260905-013): todo pedido dele
vira um time na hora, e os sub-agentes desse time nascem prontos porque o rito
fixo mora em três fichas versionadas (construtor, revisor, escrivão), não no
brief que a maestro redige a cada vez. Lei em
`docs/decisoes/PLANO-ORQUESTRACAO-AUTONOMA-DOS-ROBOS.md`, degrau 1.

O que este teste prova, e só isto:

1. As três fichas existem, e cada uma tem `name` igual ao nome do arquivo.
2. O frontmatter só usa campos que o Claude Code reconhece: um campo com erro
   de digitação é ignorado em silêncio pelo harness, e a ficha passa a valer
   menos do que parece.
3. Nenhuma ficha pode abrir a caixa de pergunta: sub-agente nunca fala com o
   mantenedor (CLAUDE.md, "Como trabalhar com o mantenedor"); quem pergunta é
   a maestro. Nenhuma pode disparar outros sub-agentes: o time é plano.
4. O revisor só lê: sem ferramenta de escrita.

O que ele NÃO prova: que a maestro divide o pedido e dispara as fichas em
paralelo. Isso é julgamento de sessão, sem mecanismo, e a seção do CLAUDE.md
diz isso com todas as letras.
"""

from __future__ import annotations

from pathlib import Path
import re

RAIZ = Path(__file__).resolve().parents[2]
FICHAS = RAIZ / ".claude" / "agents"
NOMES = ("despacho", "revisor", "escrivao")

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


def test_as_tres_fichas_existem_com_o_nome_do_arquivo() -> None:
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


def test_o_escrivao_declara_o_modelo_em_vez_de_herdar_o_mais_caro() -> None:
    """Sub-agente sem `model` herda o da maestro, que é o modelo de cima.

    Em 06/09/2026 a medição mostrou 53 dos 81 sub-agentes de um fim de semana
    rodando no modelo mais caro sem ninguém ter escolhido (CLAUDE.md, "O que uma
    chamada custa"). O escrivão preenche molde fixo: registro, evento de fila,
    armadilha. Herdar o modelo de cima para isso é gasto sem contrapartida.
    """
    campos = _frontmatter(FICHAS / "escrivao.md")
    modelo = campos.get("model", "")
    assert modelo, (
        "escrivao.md: sem `model` no frontmatter, herda o modelo da maestro "
        "(o mais caro) para preencher molde. Declare `model: sonnet`."
    )
    assert "opus" not in modelo.lower(), (
        f"escrivao.md: model={modelo!r}. A ficha que só preenche molde não usa "
        "o modelo de cima; veja CLAUDE.md, \"O que uma chamada custa\"."
    )


def test_o_revisor_declara_modelo_de_rotina() -> None:
    campos = _frontmatter(FICHAS / "revisor.md")
    modelo = campos.get("model", "")
    assert modelo, "revisor.md: sem `model`, herda o modelo da maestro para ler diff."
    assert "opus" not in modelo.lower(), (
        f"revisor.md: model={modelo!r}. Revisão de checklist fechado começa em "
        "modelo de rotina; risco semântico volta para a maestro."
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


def test_o_revisor_so_le() -> None:
    campos = _frontmatter(FICHAS / "revisor.md")
    permitidas = _lista(campos.get("tools", ""))
    negadas = _lista(campos.get("disallowedTools", ""))
    assert permitidas, "revisor.md: sem lista `tools`, herdaria tudo, inclusive escrita"
    assert not (permitidas & FERRAMENTAS_DE_ESCRITA), (
        f"revisor.md: tools permite escrita: {sorted(permitidas & FERRAMENTAS_DE_ESCRITA)}"
    )
    assert FERRAMENTAS_DE_ESCRITA <= negadas, (
        f"revisor.md: disallowedTools precisa negar {sorted(FERRAMENTAS_DE_ESCRITA - negadas)}"
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


def test_ficha_fecha_pelo_comando_existente_sem_dispensa_de_revisao() -> None:
    texto = (FICHAS / "despacho.md").read_text(encoding="utf-8")
    fechamento = texto.split("## 6.", 1)[1].split("## 7.", 1)[0]
    assert "make pr" in fechamento and "VALIDACAO=" in fechamento
    assert "CONTINUAR=1" in fechamento and "--continuar" in fechamento
    assert "gh pr create" not in fechamento
    assert "revisão de código" in fechamento
    assert "não se equivalem" in fechamento
