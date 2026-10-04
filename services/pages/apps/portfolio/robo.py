"""Cliente do robô dos alunos; envia só material do próprio portfólio."""
import os
import base64
from io import BytesIO
from PIL import Image
import httpx
from .quiz_client import quiz, QuizIndisponivel, QuizRecusado
from .models import Peca, Portfolio, ProjetoAutoral, ImagemDoPortfolio
from . import comercial

CAMPOS = {"apresentacao_publica", "servico_publico", "completo", "pagina.legendas"} | {
    "pagina." + campo for campo in comercial.PAGINA if campo != "trabalho_destaque"
} | {"kit." + campo for campo in comercial.KIT}

class RoboIndisponivel(Exception):
    pass

def contexto(dono, textos):
    portfolio = Portfolio.objects.do_aluno(**dono).first()
    trabalhos = list(Peca.objects.do_aluno(**dono).order_by("-mostrar_na_pagina_publica", "ordem"))
    ids = [i.pk for i in trabalhos]
    selecionados = {str(i.pk) for i in trabalhos if i.mostrar_na_pagina_publica}
    if "selecao_trabalhos" in textos:
        selecionados = set(textos.getlist("trabalhos_ids")) & {str(i) for i in ids}
        trabalhos = [i for i in trabalhos if str(i.pk) in selecionados]
    trabalhos = trabalhos[:24]
    dados = {
        "textos_em_edicao": {k: str(textos.get(k, ""))[:3000] for k in ("apresentacao_publica", "servico_publico")},
        "trabalhos": [{"id": str(i.pk), "link": comercial.url_publica(i.link), "legenda": i.titulo or i.legenda,
            "descricao": i.descricao, "triangulos_informados": i.triangulos, "textura_informada": i.textura,
            "uso_pretendido": i.uso_pretendido, "contribuicao": i.contribuicao, "tipo": i.tipo,
            "provas": comercial.provas_de(textos.get("provas_" + str(i.pk), i.provas_comerciais))} for i in trabalhos],
        "projetos_planejados": list(
            ProjetoAutoral.objects.do_aluno(**dono).order_by("-atualizado_em")
            .values("titulo", "descricao", "servico", "primeira_entrega")[:3]
        ),
    }
    try:
        tentativa = quiz.chamar("exploracoes/atual", **dono) or {}
        respostas = tentativa.get("respostas", {})
        dados["quiz"] = {k: v for k, v in respostas.items() if k in {
            "experiencia", "andamento_curso", "experiencia_comercial", "tem_trabalhos",
            "caminho_comercial", "publico", "servico_proprio", "pronta_entrega",
            "modelos_prontos", "ideia_propria", "trabalhos_selecionados",
        } or k.startswith("oferta_")}
    except (QuizIndisponivel, QuizRecusado):
        dados["quiz"] = {}
        respostas = {}
    dados["oferta"] = comercial.oferta_de(portfolio, respostas, textos)
    dados["prospeccao"] = comercial.prospeccao_de(portfolio, textos)
    dados["conteudo_atual"] = comercial.conteudo_de(portfolio, textos, ids=ids)
    # O contrato só recebe referências das peças incluídas nesta geração.
    dados["conteudo_atual"] = comercial.normalizar_conteudo(dados["conteudo_atual"], [i.pk for i in trabalhos])
    dados["orientacao"] = comercial.texto(textos.get("orientacao"), 2000)
    dados["imagens"] = []
    uploads = {str(i.peca_id): i for i in ImagemDoPortfolio.objects.filter(peca__portfolio=portfolio)} if portfolio else {}
    fontes = [(str(i.pk), uploads.get(str(i.pk)), comercial.url_publica(i.link)) for i in trabalhos[:4]]
    if "materiais_selecao" in textos:
        from .vitrine import materiais_de
        from .imagens import imagem_do_portfolio
        escolhidos = set(textos.getlist("materiais_ids"))
        fontes = []
        for trabalho in trabalhos:
            materiais = [m for m in materiais_de(trabalho) if m["id"] in escolhidos]
            materiais.sort(key=lambda m: not m["principal"])
            for material in materiais:
                imagem = None if material["id"].startswith("externo:") else imagem_do_portfolio(material["id"], portfolio)
                fontes.append((str(trabalho.pk), imagem, comercial.url_publica(material["url"])))
    proprias_por_link = {i.link: i for i in Peca.objects.do_aluno(**dono)}
    for trabalho in dados["trabalhos"] if "materiais_selecao" not in textos else []:
        for prova in trabalho["provas"]:
            if prova["tipo"] == "video":
                continue
            origem = proprias_por_link.get(prova["link"])
            fontes.append((trabalho["id"], uploads.get(str(origem.pk)) if origem else None, prova["link"]))
    for peca_id, imagem, link in fontes[:8]:
        if not imagem:
            if link:
                dados["imagens"].append({"peca_id": peca_id, "data_url": link})
            continue
        try:
            with Image.open(BytesIO(bytes(imagem.bytes))) as original:
                original.thumbnail((768, 768))
                saida = BytesIO()
                original.convert("RGB").save(saida, format="WEBP", quality=72)
                dados["imagens"].append({"peca_id": peca_id,
                    "data_url": "data:image/webp;base64," + base64.b64encode(saida.getvalue()).decode("ascii")})
        except (OSError, ValueError):
            continue
    # Só o resumo necessário para um parágrafo; portfólios longos também cabem.
    for item in dados["trabalhos"] + dados["projetos_planejados"]:
        for chave, valor in item.items():
            if isinstance(valor, str):
                item[chave] = valor[:1200]
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
        if campo not in {"apresentacao_publica", "servico_publico"}:
            try:
                conteudo = comercial.normalizar_conteudo(corpo.get("conteudo"), [i["id"] for i in dados["trabalhos"]])
                conteudo["_visao"] = bool(corpo.get("visao"))
                return conteudo
            except ValueError:
                raise RoboIndisponivel("A apresentação não ficou pronta. Seus textos foram mantidos; tente novamente.") from None
        texto = corpo.get("texto")
        if not isinstance(texto, str) or not texto.strip() or len(texto) > 3000:
            raise ValueError
        return texto.strip()
    except (httpx.HTTPError, ValueError):
        raise RoboIndisponivel("Não foi possível gerar o exemplo agora. Seu texto foi mantido.")
