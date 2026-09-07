"""`painel/fila.json` — a fila dos robôs chegando à aba "Prioridades" do painel.

O painel do dono (`/admin/painel/`) ganha uma aba que lista, por área do site,
o que os robôs estão fazendo e o que só o mantenedor decide. Os robôs vivem na
fila (`fila/`), cujos estados o deploy já materializa em
`fila_embutida/estados.json` (escritor único: `ci/fila.py listar --json`). A
página busca `fetch("fila.json")` só quando a aba abre — esta rota é essa
porta.

**Esta rota NÃO recalcula estado nenhum.** Ela lê o que o build materializou
(a MESMA pasta que `apps.core.robos` já serve) e traduz com as MESMAS funções
que `robos.py` já tem: `e_deste_grupo`/`COLUNAS` decidem a situação,
`importancia_declarada`/`selo_da_importancia` decidem o selo,
`onde_isso_mexe`/`area_do_toca` decidem o lugar. Reescrever qualquer uma delas
aqui seria a segunda definição que a lei anti-duplicação do `CLAUDE.md` proíbe
— as duas divergiriam no primeiro caso de borda (`armadilhas/379`).

**Sempre 200.** Como `divida.json`: uma medição auxiliar não pode derrubar o
painel inteiro. Fila ausente ou `areas.json` ausente viram `erro`/`aviso` no
corpo da resposta, nunca 500.

**`area` falha ABERTO.** Uma tarefa cuja primeira célula não está em nenhuma
`celulas` de `painel/areas.json` chega com `area: null`, e não some da lista —
é a mesma lei do `ONDE_ISSO_MEXE` de `robos.py`: o que a tela não reconhece ela
mostra, nunca engole (`armadilhas/289`, na outra direção: aqui quem cita é o
JSON, não o HTML, mas o princípio — nada some em silêncio — é o mesmo).
"""

from pathlib import Path

from django.http import JsonResponse
from django.views.decorators.http import require_safe

from . import robos
from .painel import diretorio_do_painel

# Estados que não aparecem mais na fila: já têm desfecho, não pedem mais nada
# de ninguém. O vocabulário é o de `ci/fila.py` (contrato, com acento).
_ESTADOS_FECHADOS = frozenset({"concluída", "cancelada"})

_AVISO_SEM_AREAS = "painel/areas.json não veio nesta imagem: as tarefas chegam sem área"
_ERRO_SEM_FILA = "a fila dos robôs não veio nesta imagem"


def _celula_para_area(
    pasta_do_painel: Path | None,
) -> tuple[dict[str, str], str | None]:
    """`{celula: area_id}` a partir de `painel/areas.json`, e o aviso se faltar."""
    areas = robos._ler_json(pasta_do_painel / "areas.json") if pasta_do_painel else None
    if not isinstance(areas, dict) or not isinstance(areas.get("areas"), list):
        return {}, _AVISO_SEM_AREAS

    mapa: dict[str, str] = {}
    for area in areas["areas"]:
        if not isinstance(area, dict) or not isinstance(area.get("id"), str):
            continue
        for celula in area.get("celulas") or []:
            mapa.setdefault(str(celula), area["id"])
    return mapa, None


def _tarefa_para_o_painel(tarefa_id: str, dados: dict, celula_para_area: dict) -> dict:
    grupo = next((g for g in robos.COLUNAS if robos.e_deste_grupo(dados, g)), None)
    toca = dados.get("toca") or []
    importancia = robos.importancia_declarada(dados)

    area = None
    if toca:
        area = celula_para_area.get(robos.area_do_toca(toca[0]))

    return {
        "id": tarefa_id,
        "titulo": dados.get("titulo"),
        "estado": dados.get("estado"),
        "espera": dados.get("espera"),
        "situacao": grupo["rotulo"] if grupo else None,
        "para_o_dono": bool(grupo) and grupo.get("espera") == "mantenedor",
        "importancia": importancia,
        "selo": robos.selo_da_importancia(importancia),
        "area": area,
        "toca": toca,
        "onde": robos.onde_isso_mexe(toca),
        "o_que_muda": dados.get("o_que_muda"),
        "motivo": dados.get("motivo"),
    }


def fila_para_o_painel(
    pasta_da_fila: Path | None, pasta_do_painel: Path | None
) -> dict:
    """A forma exata que a aba "Prioridades" consome. Nunca levanta."""
    if pasta_da_fila is None:
        return {"erro": _ERRO_SEM_FILA, "aviso": None, "tarefas": []}

    estados = robos._ler_json(pasta_da_fila / "estados.json")
    if not isinstance(estados, dict):
        return {"erro": _ERRO_SEM_FILA, "aviso": None, "tarefas": []}

    celula_para_area, aviso = _celula_para_area(pasta_do_painel)

    tarefas = [
        _tarefa_para_o_painel(tarefa_id, dados, celula_para_area)
        for tarefa_id, dados in sorted(estados.items())
        if isinstance(dados, dict) and dados.get("estado") not in _ESTADOS_FECHADOS
    ]
    return {"erro": None, "aviso": aviso, "tarefas": tarefas}


@require_safe
def fila_json(request):
    """A fila que a aba "Prioridades" busca ao abrir.

    Protegida pela porta como toda rota desta célula (não está em
    `CAMINHOS_ISENTOS`): sem sessão, não entrega a fila.
    """
    resposta = JsonResponse(
        fila_para_o_painel(robos.diretorio_da_fila(), diretorio_do_painel())
    )
    resposta["Cache-Control"] = "no-store"
    return resposta
