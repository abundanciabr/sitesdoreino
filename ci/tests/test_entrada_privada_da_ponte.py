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
