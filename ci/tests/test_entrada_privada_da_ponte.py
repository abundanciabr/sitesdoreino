"""A entrada privada abre QUATRO leituras, e o segredo não mora no repositório.

Esta é a fase 2 do plano da ponte: a porta pela qual o painel localhost do
mantenedor lê os dados reais da VPS. O raio de explosão dela é a borda pública
inteira, porque o mesmo Traefik serve as portas 80 e 443 de todos os sites.

O que este arquivo mede é o que um YAML errado custaria caro: uma operação a
mais, um verbo de escrita, a porta publicada para fora do loopback, ou um token
literal versionado. O comportamento do Traefik diante destas regras foi medido
em 15/09/2026 com a imagem `traefik:v3.4` de verdade, e está registrado na
seção 14.1 do roadmap 54.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[2]
DINAMICO = RAIZ / "infra" / "traefik" / "dynamic" / "entrada-privada.yml"
ESTATICO = RAIZ / "infra" / "traefik" / "traefik.yml"
COMPOSE = RAIZ / "infra" / "docker-compose.yml"
SINCRONIZADOR = RAIZ / "infra" / "sincronizar-infra-na-vps.sh"
PROVISIONADOR = RAIZ / "infra" / "provisionar-usuario-ponte.sh"
INSTALADOR = RAIZ / "infra" / "instalar-provisionador-da-ponte.sh"

# A chave que abre a ponte, e a única. Trocá-la aponta o cano para outra
# máquina, e é a mudança mais silenciosa que este lote admite: nada quebra,
# nada fica vermelho, e o acesso passa a ser de outra pessoa.
CHAVE_DESTE_PC = (
    "ssh-ed25519 "
    "AAAAC3NzaC1lZDI1NTE5AAAAIDFmhu8QkiIPwN0gqmYSmSrN9E2Wr8PdAk2N3qglquu6 "
    "davi@DESKTOP-V8F32JA"
)

AS_QUATRO_LEITURAS = {
    ("GET", "/alunos/api/alunos/pre-matriculas", ("status", "aguardando")),
    ("GET", "/alunos/api/alunos/pre-matriculas", ("status", "recusada")),
    ("GET", "/alunos/api/alunos/matriculas", None),
    ("GET", "/catalogo/api/catalogo/produtos", None),
}


def dinamico() -> dict:
    """O YAML das rotas, com o `{{ env }}` neutralizado só para poder ler.

    O template é do Traefik, não do YAML: ele é resolvido dentro da VPS. Aqui
    ele vira texto para a leitura não quebrar, e o teste do segredo confere o
    arquivo CRU, não esta versão.
    """
    cru = DINAMICO.read_text(encoding="utf-8")
    return yaml.safe_load(re.sub(r"\{\{[^}]*\}\}", "TEMPLATE", cru))


def regras() -> list[str]:
    return [r["rule"] for r in dinamico()["http"]["routers"].values()]


def lida(regra: str):
    metodo = re.search(r"Method\(`([A-Z]+)`\)", regra)
    caminho = re.search(r"Path\(`([^`]+)`\)", regra)
    query = re.search(r"Query\(`([^`]+)`,\s*`([^`]+)`\)", regra)
    return (
        metodo.group(1) if metodo else None,
        caminho.group(1) if caminho else None,
        (query.group(1), query.group(2)) if query else None,
    )


def test_sao_exatamente_as_quatro_leituras_da_tela_de_alunos():
    assert {lida(r) for r in regras()} == AS_QUATRO_LEITURAS


def test_nenhum_roteador_abre_verbo_de_escrita():
    for regra in regras():
        metodo, _, _ = lida(regra)
        assert metodo == "GET", (
            f"a regra {regra!r} abre {metodo}. Escrita é obra própria, depois "
            "das fases 7 e 8 do plano da ponte."
        )


def test_nenhum_roteador_usa_prefixo_amplo():
    for regra in regras():
        assert "PathPrefix" not in regra, (
            f"a regra {regra!r} usa PathPrefix: um prefixo abre a célula "
            "inteira, e a permissão aqui é por operação."
        )


def test_o_token_nao_esta_versionado_so_o_nome_da_variavel():
    cru = DINAMICO.read_text(encoding="utf-8")
    for autorizacao in re.findall(r"Authorization:.*", cru):
        assert "{{ env" in autorizacao, (
            f"{autorizacao!r} tem valor literal. O repositório guarda o NOME "
            "da variável; o valor é injetado dentro da VPS."
        )


def test_a_porta_privada_fica_presa_ao_loopback_do_host():
    publicadas = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]["traefik"]["ports"]
    privadas = [p for p in publicadas if "8443" in str(p)]
    assert privadas, "o compose precisa publicar a entrada privada"
    for porta in privadas:
        assert str(porta).startswith("127.0.0.1:"), (
            f"{porta!r} publica a entrada privada para fora do loopback: "
            "outra máquina da rede alcançaria a porta."
        )


def test_o_gateway_recebe_dois_valores_e_nao_o_admin_env_inteiro():
    traefik = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]["traefik"]
    assert "env_file" not in traefik, "o gateway nunca recebe um arquivo de ambiente inteiro"
    assert set(traefik["environment"]) == {"ALUNOS_API_TOKEN", "TOKEN_CATALOGO"}


def test_o_entrypoint_privado_existe_e_nao_e_publico():
    entradas = yaml.safe_load(ESTATICO.read_text(encoding="utf-8"))["entryPoints"]
    assert entradas["privada"]["address"] == ":8443"


def test_a_sincronizacao_sonda_a_entrada_privada_antes_de_dizer_concluida():
    texto = SINCRONIZADOR.read_text(encoding="utf-8")
    assert "127.0.0.1:8443" in texto, (
        "container em `running` não prova que a rota existe; a sonda é o que prova."
    )
    assert texto.index("sonda da entrada privada") < texto.index("SINCRONIZACAO-CONCLUIDA: $STAMP"), (
        "a sonda tem de acontecer ANTES da sentinela, senão a sincronização "
        "fica verde sem a porta funcionar."
    )
    for _, caminho, _ in (lida(r) for r in regras()):
        assert caminho in texto, f"a sonda não prova {caminho}"


def test_a_sonda_exige_404_no_que_esta_fora_da_lista():
    texto = SINCRONIZADOR.read_text(encoding="utf-8")
    assert "-X POST" in texto and '"404"' in texto, (
        "sem provar a recusa, uma lista positiva quebrada passa despercebida."
    )


# ---------------------------------------------------------------------------
# O Traefik lê o arquivo ANTES do YAML: os testes acima, não.
#
# Em 15/09/2026 a publicação da fase 2 derrubou o roteamento público inteiro,
# com 404 em TODOS os hosts, e nenhum dos testes acima viu. O motivo é que eles
# medem o resultado de `yaml.safe_load`, que descarta comentários, enquanto o
# provedor de arquivo do Traefik renderiza o texto CRU como template Go antes
# de interpretar o YAML. Um `{{ ... }}` dentro de um comentário é ação de
# template para ele. O que derrubou foi uma linha que documentava o ensaio:
#
#     #   - `{{ env }}` funciona no provedor de arquivo, ...
#
# `env` sem argumento reprova o template, o arquivo inteiro é recusado, e o
# provedor `file` cai junto com ele, levando `plataforma.yml` e a raiz do site.
# Medido com `traefik:v3.4` de verdade: com essa linha, ZERO roteadores sobem;
# sem ela, `funil@file` e os demais sobem.
# ---------------------------------------------------------------------------
ACAO_DE_TEMPLATE = re.compile(r"\{\{(.*?)\}\}", re.DOTALL)
INJECAO_DE_VARIAVEL = re.compile(r'^\s*env\s+"[A-Z0-9_]+"\s*$')
PASTA_DINAMICA = RAIZ / "infra" / "traefik" / "dynamic"


def test_todo_template_dos_arquivos_dinamicos_e_uma_injecao_de_variavel():
    """Qualquer `{{ ... }}`, mesmo em comentário, derruba o Traefik se for inválido."""
    fora_do_contrato = [
        (arquivo.name, acao.strip())
        for arquivo in sorted(PASTA_DINAMICA.glob("*.yml"))
        for acao in ACAO_DE_TEMPLATE.findall(arquivo.read_text(encoding="utf-8"))
        if not INJECAO_DE_VARIAVEL.match(acao)
    ]
    assert not fora_do_contrato, (
        "Estes `{{ ... }}` não são uma injeção `env \"NOME\"` e o Traefik vai "
        "recusar o arquivo inteiro, derrubando a borda pública com 404 em todos "
        f"os hosts: {fora_do_contrato}. Se está num comentário, reescreva o "
        "comentário sem as chaves duplas."
    )


def so_codigo(caminho: Path) -> str:
    """O roteiro sem os comentarios: medir ordem no texto inteiro mede a prosa.

    Os cabecalhos desta casa citam os proprios comandos ao explicar por que
    existem, entao `texto.index("systemctl reload")` acha a explicacao, e nao a
    linha que recarrega.
    """
    return "\n".join(
        linha for linha in caminho.read_text(encoding="utf-8").splitlines()
        if not linha.lstrip().startswith("#")
    )


def test_a_chave_da_ponte_e_a_deste_pc_e_so_ela():
    """Uma chave a mais, ou outra chave, abre o cano para outra maquina."""
    texto = PROVISIONADOR.read_text(encoding="utf-8")
    assert CHAVE_DESTE_PC in texto, (
        "a chave autorizada da ponte deixou de ser a do PC do mantenedor"
    )
    assert texto.count("ssh-ed25519 ") == 1, (
        "o provisionador tem de autorizar exatamente UMA chave publica"
    )


def test_o_provisionador_nunca_reinicia_o_sshd_nem_edita_o_arquivo_principal():
    """`restart` derruba as sessoes abertas, e a sessao viva e o desfazer."""
    codigo = so_codigo(PROVISIONADOR)
    # O que se proibe e EXECUTAR o restart. A mensagem de ultimo recurso cita o
    # comando para o mantenedor digitar no console do provedor, e citar nao e
    # executar: por isso o texto entre aspas sai antes da medicao.
    executavel = re.sub(r'"[^"]*"', '""', codigo)
    assert "systemctl restart" not in executavel, (
        "restart mata a sessao da esteira, que e o unico caminho de volta"
    )
    tocados = re.findall(r"/etc/ssh/sshd_config[^\s\"']*", codigo)
    assert tocados, "o provisionador precisa escrever o drop-in do sshd"
    for caminho in tocados:
        assert caminho.startswith("/etc/ssh/sshd_config.d/"), (
            f"{caminho} nao esta em sshd_config.d/: a mudanca e um arquivo de "
            "acrescimo, nunca uma edicao do arquivo principal"
        )


def test_o_provisionador_mede_o_deploy_antes_de_recarregar():
    """Sem comparar a configuracao efetiva do deploy, o reload e uma aposta."""
    codigo = so_codigo(PROVISIONADOR)
    assert codigo.index("DEPLOY_ANTES=") < codigo.index("systemctl reload"), (
        "a fotografia do deploy tem de ser tirada antes de escrever e recarregar"
    )
    assert codigo.index("sshd -t") < codigo.index("systemctl reload"), (
        "sshd -t vem antes do reload, sempre"
    )


def test_a_ponte_nao_derruba_a_sincronizacao_quando_ainda_nao_foi_ligada():
    """Faltar a ponte e um recurso a menos; parar a infra seria estrago novo."""
    codigo = so_codigo(SINCRONIZADOR)
    assert codigo.index("PROVISIONADOR_DA_PONTE=") < codigo.index("ls infra.new"), (
        "a ponte nasce antes de qualquer troca, quando nada em uso mudou ainda"
    )
    assert "instalar-provisionador-da-ponte.sh" in codigo, (
        "o log tem de dizer a linha exata que liga a ponte"
    )


def test_o_deploy_so_pode_executar_o_caminho_congelado():
    """Coringa no sudoers daria root irrestrito ao usuario da esteira."""
    texto = INSTALADOR.read_text(encoding="utf-8")
    assert "deploy ALL=(root) NOPASSWD: $DESTINO" in texto
    assert "install -o root -g root -m 755" in texto, (
        "o que roda como root nao pode ser gravavel pelo deploy"
    )
    regra = texto.split("NOPASSWD:")[1].splitlines()[0]
    assert "*" not in regra, (
        f"a regra do sudo {regra!r} tem coringa: isso e root irrestrito para o deploy"
    )
    assert "visudo -cf" in texto, (
        "sudoers invalido em /etc/sudoers.d quebra o sudo da maquina inteira"
    )

