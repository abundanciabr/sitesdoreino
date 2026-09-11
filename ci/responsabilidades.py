"""Guarda a cobertura de responsabilidade e a conclusão de entregas novas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mapa_de_celulas
import mapa_do_site


FUNCOES = {
    "estrategia-conteudo",
    "operacoes-trafego",
    "ensino-comunidade",
    "comercial-relacionamento",
}

UNIDADE_CAMPOS_OBRIGATORIOS = (
    "tipo", "finalidade", "titular_funcao", "acompanhamento", "fonte",
    "prepara", "executa", "aprova", "excecoes", "autoridade", "evidencia",
)

NOMES_DE_FUNCOES = {
    "estrategia-conteudo": "Estratégia e Conteúdo",
    "operacoes-trafego": "Operações e Tráfego",
    "ensino-comunidade": "Ensino e Comunidade",
    "comercial-relacionamento": "Comercial e Relacionamento",
}


def identidade_ia(valor: object) -> bool:
    return isinstance(valor, str) and valor.strip().casefold() in {"ia", "agente de ia", "agente ia"}


def sem_substituto_valido(funcao: dict) -> bool:
    valor = funcao.get("sem_substituto")
    return valor is True and not funcao.get("substituto")


def pessoa_valida(valor: object, permitir_vazio: bool = False) -> bool:
    return (permitir_vazio and valor is None) or (isinstance(valor, str) and bool(valor.strip()))


def carregar(raiz: Path) -> dict:
    registro = json.loads((raiz / "painel" / "responsabilidades.json").read_text(encoding="utf-8"))
    if not isinstance(registro, dict) or not isinstance(registro.get("funcoes"), dict) or not all(isinstance(valor, dict) for valor in registro["funcoes"].values()) or not isinstance(registro.get("unidades"), list):
        raise ValueError("o cadastro precisa conter funcoes e unidades")
    return registro


def resolver_unidade(registro: dict, identificador: str) -> tuple[dict | None, list[str]]:
    unidades = {
        item["id"]: item
        for item in registro.get("unidades", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip()
    }
    atual = identificador
    vistos = []
    cadeia = []
    while atual:
        if atual in vistos:
            return None, [f"herança circular em {identificador}"]
        vistos.append(atual)
        unidade = unidades.get(atual)
        if unidade is None:
            return None, [f"responsabilidade {atual} não foi cadastrada"]
        cadeia.append(unidade)
        atual = unidade.get("herda_de")
    efetiva = {}
    for unidade in reversed(cadeia):
        efetiva.update(unidade)
    if efetiva.get("titular_funcao") in FUNCOES:
        return efetiva, []
    return None, [f"responsabilidade {identificador} não tem titular explícito ou herdado"]


def texto_preenchido(valor: object) -> bool:
    return isinstance(valor, str) and bool(valor.strip())


def validar_campos_concretos(unidade: dict, identificador: str) -> list[str]:
    erros = []
    fonte = unidade.get("fonte")
    if not texto_preenchido(fonte) or not any(
        f"{diretorio}/" in fonte for diretorio in ("services", "painel", "infra", "docs", "ci")
    ):
        erros.append(f"{identificador}: fonte precisa listar referências concretas")

    aprova = unidade.get("aprova")
    if aprova not in NOMES_DE_FUNCOES.values():
        erros.append(f"{identificador}: aprova precisa identificar funções responsáveis")

    autoridade = unidade.get("autoridade")
    destino = autoridade.partition("Escala para:")[2] if texto_preenchido(autoridade) else ""
    if not autoridade.startswith("Decide:") or not texto_preenchido(destino) or not any(
        nome.casefold() in destino.casefold() for nome in (*NOMES_DE_FUNCOES.values(), "mantenedor")
    ):
        erros.append(f"{identificador}: autoridade precisa declarar decisão e escalonamento")
    return erros


def inventario_de_recursos(raiz: Path) -> tuple[set[str], list[tuple[str, str]], list[str]]:
    caminho_celulas = raiz / "celulas.yml"
    caminho_rotas = raiz / "painel" / "mapa-do-site.json"
    if not caminho_celulas.exists() and not caminho_rotas.exists():
        return set(), [], []
    if not caminho_celulas.exists() or not caminho_rotas.exists():
        return set(), [], ["inventário de recursos incompleto"]
    try:
        celulas = set(mapa_de_celulas.carregar(raiz))
        rotas = mapa_do_site.carregar(raiz)
    except Exception as exc:  # noqa: BLE001 - o portão recusa inventário ilegível
        return set(), [], [f"inventário de recursos ilegível: {exc}"]
    erros = []
    recursos = []
    for rota in rotas:
        celula = rota.get("celula") if isinstance(rota, dict) else None
        identificador = rota.get("rota") if isinstance(rota, dict) else None
        if celula not in celulas or not isinstance(identificador, str):
            erros.append("inventário de rotas contém recurso sem célula válida")
            continue
        recursos.append((celula, identificador))
    return celulas, recursos, erros


def cobertura_de_celulas(unidade: dict, identificador: str) -> tuple[list[str], list[str]]:
    if "recursos" not in unidade:
        return [], []
    recursos = unidade.get("recursos")
    celulas = recursos.get("celulas") if isinstance(recursos, dict) else None
    if not isinstance(celulas, list) or not all(texto_preenchido(celula) for celula in celulas):
        return [], [f"{identificador}: recursos precisa listar células conhecidas"]
    if len(set(celulas)) != len(celulas):
        return [], [f"{identificador}: recursos repete célula"]
    return celulas, []


def validar_entrega(raiz: Path, identificador: str) -> list[str]:
    registro = carregar(raiz)
    unidade, erros = resolver_unidade(registro, identificador)
    if erros:
        return erros
    assert unidade is not None
    funcao = registro["funcoes"].get(unidade["titular_funcao"], {})
    if not isinstance(funcao, dict):
        return [f"função {unidade['titular_funcao']} tem cadastro inválido"]
    if not pessoa_valida(funcao.get("pessoa")):
        erros.append(f"função {unidade['titular_funcao']} não tem pessoa ocupante")
    if identidade_ia(funcao.get("pessoa")):
        erros.append(f"função {unidade['titular_funcao']} não pode ter IA como pessoa ocupante")
    if identidade_ia(funcao.get("substituto")):
        erros.append(f"função {unidade['titular_funcao']} não pode ter IA como substituto")
    if funcao.get("sem_substituto") not in (None, True, False):
        erros.append(f"função {unidade['titular_funcao']} tem sem_substituto inválido")
    if not pessoa_valida(funcao.get("substituto"), permitir_vazio=True):
        erros.append(f"função {unidade['titular_funcao']} tem substituto inválido")
    if not funcao.get("substituto") and not sem_substituto_valido(funcao):
        erros.append(f"função {unidade['titular_funcao']} não tem substituto aceito")
    for campo in ("aprova", "autoridade"):
        if identidade_ia(unidade.get(campo)):
            erros.append(f"{identificador}: IA não pode ocupar o campo {campo}")
    for campo in UNIDADE_CAMPOS_OBRIGATORIOS:
        if not unidade.get(campo):
            erros.append(f"{identificador}: campo obrigatório ausente: {campo}")
    erros.extend(validar_campos_concretos(unidade, identificador))
    return erros


def auditar(raiz: Path) -> list[str]:
    registro = carregar(raiz)
    erros = []
    if set(registro.get("funcoes", {})) != FUNCOES:
        erros.append("o cadastro precisa conter exatamente as quatro funções")
    for identificador, funcao in registro.get("funcoes", {}).items():
        if not isinstance(funcao, dict):
            erros.append(f"{identificador}: cadastro de função inválido")
            continue
        if not pessoa_valida(funcao.get("pessoa")):
            erros.append(f"{identificador}: pessoa ocupante ausente")
        if identidade_ia(funcao.get("pessoa")):
            erros.append(f"{identificador}: IA não pode ser pessoa ocupante")
        if identidade_ia(funcao.get("substituto")):
            erros.append(f"{identificador}: IA não pode ser substituto")
        if funcao.get("sem_substituto") not in (None, True, False):
            erros.append(f"{identificador}: sem_substituto precisa ser booleano")
        if not pessoa_valida(funcao.get("substituto"), permitir_vazio=True):
            erros.append(f"{identificador}: substituto inválido")
        if not funcao.get("substituto") and not sem_substituto_valido(funcao):
            erros.append(f"{identificador}: substituto ausente")
    identificadores = [
        unidade.get("id")
        for unidade in registro.get("unidades", [])
        if isinstance(unidade, dict) and texto_preenchido(unidade.get("id"))
    ]
    for identificador in sorted({item for item in identificadores if identificadores.count(item) > 1}):
        erros.append(f"identificador de responsabilidade duplicado: {identificador}")

    celulas_conhecidas, rotas_conhecidas, erros_inventario = inventario_de_recursos(raiz)
    erros.extend(erros_inventario)
    vinculos: dict[str, list[str]] = {celula: [] for celula in celulas_conhecidas}
    for unidade in registro.get("unidades", []):
        if not isinstance(unidade, dict) or not isinstance(unidade.get("id"), str) or not unidade["id"].strip():
            erros.append("unidade sem id válido")
            continue
        if celulas_conhecidas:
            celulas, problemas_de_cobertura = cobertura_de_celulas(unidade, unidade["id"])
            erros.extend(problemas_de_cobertura)
            for celula in celulas:
                if celula not in vinculos:
                    erros.append(f"{unidade['id']}: recurso desconhecido: celula:{celula}")
                else:
                    vinculos[celula].append(unidade["id"])
        efetiva, problemas = resolver_unidade(registro, unidade["id"])
        if problemas:
            erros.extend(f"{unidade['id']}: {erro}" for erro in problemas)
            continue
        assert efetiva is not None
        for campo in UNIDADE_CAMPOS_OBRIGATORIOS:
            if not efetiva.get(campo):
                erros.append(f"{unidade.get('id', 'sem id')}: campo obrigatório ausente: {campo}")
        for erro in validar_entrega(raiz, unidade["id"]):
            erros.append(erro if erro.startswith(f"{unidade['id']}:") else f"{unidade['id']}: {erro}")
    for celula, unidades in sorted(vinculos.items()):
        if not unidades:
            erros.append(f"recurso conhecido sem responsabilidade: celula:{celula}")
        elif len(unidades) > 1:
            erros.append(f"recurso conhecido com vínculo ambíguo: celula:{celula}")
    for celula, rota in rotas_conhecidas:
        unidades = vinculos[celula]
        recurso = f"rota:{celula}:{rota}"
        if not unidades:
            erros.append(f"recurso conhecido sem responsabilidade: {recurso}")
        elif len(unidades) > 1:
            erros.append(f"recurso conhecido com vínculo ambíguo: {recurso}")
    return sorted(set(erros))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--entrega", metavar="RESPONSABILIDADE")
    parser.add_argument("--auditar", action="store_true")
    args = parser.parse_args()
    erros = validar_entrega(args.raiz, args.entrega) if args.entrega and not args.auditar else auditar(args.raiz)
    if erros:
        print("RESPONSABILIDADE NÃO COMPROVADA")
        for erro in erros:
            print(f"- {erro}")
        return 1
    print("RESPONSABILIDADE COMPROVADA")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
