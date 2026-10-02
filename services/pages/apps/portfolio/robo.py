"""Cliente do robô dos alunos; envia só material do próprio portfólio."""
import os
import httpx
from .quiz_client import quiz, QuizIndisponivel, QuizRecusado
from .models import Peca, ProjetoAutoral

CAMPOS = {"apresentacao_publica", "servico_publico"}

class RoboIndisponivel(Exception):
    pass

def contexto(dono, textos):
    dados = {
        "textos_em_edicao": {k: str(textos.get(k, ""))[:3000] for k in CAMPOS},
        "trabalhos": list(
            Peca.objects.do_aluno(**dono).order_by("-mostrar_na_pagina_publica", "ordem")
            .values("legenda", "uso_pretendido", "contribuicao", "tipo")[:12]
        ),
        "projetos_planejados": list(
            ProjetoAutoral.objects.do_aluno(**dono).order_by("-atualizado_em")
            .values("titulo", "descricao", "servico", "primeira_entrega")[:3]
        ),
    }
    try:
        tentativa = quiz.chamar("exploracoes/atual", **dono) or {}
        dados["quiz"] = {k: v for k, v in tentativa.get("respostas", {}).items() if k in {
            "experiencia", "andamento_curso", "experiencia_comercial", "tem_trabalhos",
            "caminho_comercial", "publico", "servico_proprio", "pronta_entrega",
            "modelos_prontos", "ideia_propria", "trabalhos_selecionados",
        }}
    except (QuizIndisponivel, QuizRecusado):
        dados["quiz"] = {}
    # Só o resumo necessário para um parágrafo; portfólios longos também cabem.
    for item in dados["trabalhos"] + dados["projetos_planejados"]:
        for chave, valor in item.items():
            if isinstance(valor, str):
                item[chave] = valor[:300]
    for chave, valor in dados["quiz"].items():
        if isinstance(valor, str):
            dados["quiz"][chave] = valor[:600]
        elif isinstance(valor, list):
            dados["quiz"][chave] = [str(item)[:120] for item in valor[:12]]
    return dados

def gerar(campo, dados):
    base = os.environ.get("ADMIN_API_URL", "").rstrip("/")
    token = os.environ.get("ADMIN_API_TOKEN", "")
    if not base or not token:
        raise RoboIndisponivel("A geração de exemplos está indisponível agora.")
    try:
        resposta = httpx.post(
            base + "/robo-dos-alunos/gerar",
            headers={"Authorization": "Bearer " + token},
            json={"campo": campo, "contexto": dados},
            timeout=130,
        )
        corpo = resposta.json()
        if resposta.status_code != 200:
            raise RoboIndisponivel(corpo.get("erro") or "Não foi possível gerar o exemplo agora.")
        texto = corpo.get("texto")
        if not isinstance(texto, str) or not texto.strip() or len(texto) > 3000:
            raise ValueError
        return texto.strip()
    except (httpx.HTTPError, ValueError):
        raise RoboIndisponivel("Não foi possível gerar o exemplo agora. Seu texto foi mantido.")
