"""Validação e importação de campanhas direcionadas a partir de JSON."""

import ast
import re
from types import SimpleNamespace
from urllib.parse import urlparse

from django.db import transaction
from django.http import Http404

from apps.core.middleware import CAMINHOS_SEM_SITE
from apps.quiz.experiencias import resolver_experiencia
from apps.quiz.models import Option, Question, Quiz, QuizVersion, ResultBand


FORMATO = "quiz-low-ticket/2"
CHAVE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
CHAVE_VERSAO = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
CHAVE_CALCULO = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
RESERVADOS = {
    "quiz",
    "telemetry",
    "healthz",
    "static",
    "admin",
    "api",
    "resultado",
    "observacao",
}
FORMATOS = {"text", "video", "hybrid", "calc", "ai"}


def _erro(caminho, descricao):
    raise ValueError(f"{caminho}: {descricao}")


def _obj(valor, caminho):
    if not isinstance(valor, dict):
        _erro(caminho, "precisa ser objeto")
    return valor


def _lista(valor, caminho, minimo=1, maximo=100):
    if not isinstance(valor, list) or not minimo <= len(valor) <= maximo:
        _erro(caminho, f"precisa ter entre {minimo} e {maximo} itens")
    return valor


def _texto(valor, caminho, maximo, vazio=False):
    if (
        not isinstance(valor, str)
        or len(valor) > maximo
        or (not vazio and not valor.strip())
    ):
        _erro(caminho, f"precisa ser texto de até {maximo} caracteres")
    return valor


def _chave(valor, caminho):
    _texto(valor, caminho, 100)
    if (
        not CHAVE.fullmatch(valor)
        or valor in RESERVADOS
        or f"/{valor}/".startswith(CAMINHOS_SEM_SITE)
    ):
        _erro(caminho, "use identificador legível, iniciado por letra, não reservado")
    return valor


def _chave_versao(valor, caminho):
    _texto(valor, caminho, 100)
    if not CHAVE_VERSAO.fullmatch(valor) or valor.lower() in RESERVADOS:
        _erro(caminho, "use identificador legível, iniciado por letra, não reservado")
    return valor


def _inteiro(valor, caminho, minimo=-100000, maximo=100000):
    if type(valor) is not int or not minimo <= valor <= maximo:
        _erro(caminho, f"precisa ser inteiro entre {minimo} e {maximo}")
    return valor


def _url(valor, caminho, opcional=False):
    if opcional and valor is None:
        return
    _texto(valor, caminho, 500)
    parsed = urlparse(valor)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        _erro(caminho, "precisa ser URL HTTPS válida")


def _unicos(itens, campo, caminho):
    valores = [item[campo] for item in itens]
    if len(valores) != len(set(valores)):
        _erro(caminho, f"{campo} repetido")


def _expressao(expressao, chaves, caminho):
    _texto(expressao, caminho, 256)
    try:
        arvore = ast.parse(expressao, mode="eval")
    except SyntaxError:
        _erro(caminho, "expressão aritmética inválida")
    nos = list(ast.walk(arvore))
    if len(nos) > 100:
        _erro(caminho, "expressão extensa demais")
    permitidos = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.UAdd,
        ast.USub,
        ast.Constant,
        ast.Name,
        ast.Load,
    )
    for no in nos:
        if not isinstance(no, permitidos):
            _erro(caminho, "somente aritmética com entradas declaradas é permitida")
        if isinstance(no, ast.Name) and no.id not in chaves:
            _erro(caminho, f"entrada desconhecida: {no.id}")
        if isinstance(no, ast.Constant) and (
            type(no.value) not in (int, float) or abs(no.value) > 1000000
        ):
            _erro(caminho, "constante inválida")


def _conferir_formatos(versao, caminho):
    formatos = _obj(versao.get("formats"), f"{caminho}.formats")
    if not formatos or set(formatos) - FORMATOS:
        _erro(f"{caminho}.formats", "formatos desconhecidos ou vazios")
    padrao = versao.get("default_format")
    if padrao not in formatos:
        _erro(f"{caminho}.default_format", "precisa existir em formats")
    for nome, dados in formatos.items():
        base = f"{caminho}.formats.{nome}"
        dados = _obj(dados, base)
        _texto(dados.get("headline"), f"{base}.headline", 200)
        _texto(dados.get("subheadline"), f"{base}.subheadline", 1000)
        if nome in ("video", "hybrid"):
            # null = VSL ainda em produção; a página mostra o aviso no lugar.
            _url(dados.get("video_url"), f"{base}.video_url", opcional=True)
        if nome == "ai":
            _texto(dados.get("instructions"), f"{base}.instructions", 4000)
        if nome == "calc":
            calc = _obj(dados.get("calculator"), f"{base}.calculator")
            entradas = _lista(
                calc.get("inputs"), f"{base}.calculator.inputs", maximo=20
            )
            for i, entrada in enumerate(entradas):
                e = _obj(entrada, f"{base}.calculator.inputs[{i}]")
                chave = e.get("key")
                _texto(chave, f"{base}.calculator.inputs[{i}].key", 100)
                if not CHAVE_CALCULO.fullmatch(chave):
                    _erro(
                        f"{base}.calculator.inputs[{i}].key",
                        "variável aritmética inválida",
                    )
                _texto(e.get("label"), f"{base}.calculator.inputs[{i}].label", 100)
                minimo = _inteiro(e.get("min"), f"{base}.calculator.inputs[{i}].min")
                maximo = _inteiro(e.get("max"), f"{base}.calculator.inputs[{i}].max")
                padrao = _inteiro(
                    e.get("default"), f"{base}.calculator.inputs[{i}].default"
                )
                if not minimo <= padrao <= maximo:
                    _erro(
                        f"{base}.calculator.inputs[{i}]",
                        "min ≤ default ≤ max obrigatório",
                    )
            _unicos(entradas, "key", f"{base}.calculator.inputs")
            _expressao(
                calc.get("expression"),
                {e["key"] for e in entradas},
                f"{base}.calculator.expression",
            )
            _texto(calc.get("result_label"), f"{base}.calculator.result_label", 100)


def conferir_documento(dados):
    """Retorna o documento validado; lança ValueError antes de qualquer escrita."""
    dados = _obj(dados, "documento")
    if dados.get("formato") != FORMATO:
        _erro("formato", f"precisa ser {FORMATO}")
    quiz = _obj(dados.get("quiz"), "quiz")
    _chave(quiz.get("slug"), "quiz.slug")
    _texto(quiz.get("title"), "quiz.title", 200)
    ofertas = _lista(dados.get("ofertas"), "ofertas", minimo=2, maximo=2)
    for i, oferta in enumerate(ofertas):
        oferta = _obj(oferta, f"ofertas[{i}]")
        _chave(oferta.get("id"), f"ofertas[{i}].id")
        _texto(oferta.get("nome"), f"ofertas[{i}].nome", 200)
        _url(oferta.get("checkout_url"), f"ofertas[{i}].checkout_url", opcional=True)
    _unicos(ofertas, "id", "ofertas")
    ids_ofertas = {o["id"] for o in ofertas}
    versoes = _lista(dados.get("versoes"), "versoes", maximo=50)
    for i, versao in enumerate(versoes):
        base = f"versoes[{i}]"
        versao = _obj(versao, base)
        _chave_versao(versao.get("key"), f"{base}.key")
        _conferir_formatos(versao, base)
        perguntas = _lista(versao.get("perguntas"), f"{base}.perguntas", maximo=50)
        alcancaveis = {0}
        for j, pergunta in enumerate(perguntas):
            pbase = f"{base}.perguntas[{j}]"
            pergunta = _obj(pergunta, pbase)
            _chave(pergunta.get("id"), f"{pbase}.id")
            _texto(pergunta.get("texto"), f"{pbase}.texto", 500)
            opcoes = _lista(
                pergunta.get("opcoes"), f"{pbase}.opcoes", minimo=2, maximo=20
            )
            for k, opcao in enumerate(opcoes):
                obase = f"{pbase}.opcoes[{k}]"
                opcao = _obj(opcao, obase)
                _chave(opcao.get("id"), f"{obase}.id")
                _texto(opcao.get("texto"), f"{obase}.texto", 300)
                _inteiro(opcao.get("pontos"), f"{obase}.pontos", -1000, 1000)
            _unicos(opcoes, "id", f"{pbase}.opcoes")
            alcancaveis = {s + o["pontos"] for s in alcancaveis for o in opcoes}
        _unicos(perguntas, "id", f"{base}.perguntas")
        faixas = _lista(versao.get("faixas"), f"{base}.faixas", maximo=100)
        for j, faixa in enumerate(faixas):
            fbase = f"{base}.faixas[{j}]"
            faixa = _obj(faixa, fbase)
            _chave(faixa.get("key"), f"{fbase}.key")
            _texto(faixa.get("title"), f"{fbase}.title", 200)
            _texto(faixa.get("description"), f"{fbase}.description", 10000, vazio=True)
            minimo = _inteiro(faixa.get("min_score"), f"{fbase}.min_score")
            maximo = _inteiro(faixa.get("max_score"), f"{fbase}.max_score")
            if minimo > maximo:
                _erro(fbase, "min_score excede max_score")
            if faixa.get("oferta_id") not in ids_ofertas:
                _erro(f"{fbase}.oferta_id", "oferta desconhecida")
            _texto(faixa.get("botao_rotulo"), f"{fbase}.botao_rotulo", 80)
        _unicos(faixas, "key", f"{base}.faixas")
        ordenadas = sorted(faixas, key=lambda f: f["min_score"])
        if any(
            a["max_score"] >= b["min_score"] for a, b in zip(ordenadas, ordenadas[1:])
        ):
            _erro(f"{base}.faixas", "faixas sobrepostas")
        if any(
            not any(f["min_score"] <= s <= f["max_score"] for f in faixas)
            for s in alcancaveis
        ):
            _erro(f"{base}.faixas", "não cobrem todas as pontuações alcançáveis")
        segmentos = _obj(versao.get("segments"), f"{base}.segments")
        for nome, segmento in segmentos.items():
            _chave(nome, f"{base}.segments.nome")
            sbase = f"{base}.segments.{nome}"
            segmento = _obj(segmento, sbase)
            _texto(segmento.get("headline"), f"{sbase}.headline", 200)
            _texto(segmento.get("subheadline"), f"{sbase}.subheadline", 1000)
            _url(segmento.get("video_url"), f"{sbase}.video_url", opcional=True)
            resultados = _obj(segmento.get("results"), f"{sbase}.results")
            for banda, resultado in resultados.items():
                if banda not in {f["key"] for f in faixas}:
                    _erro(f"{sbase}.results", f"faixa desconhecida: {banda}")
                resultado = _obj(resultado, f"{sbase}.results.{banda}")
                _texto(resultado.get("title"), f"{sbase}.results.{banda}.title", 200)
                _texto(
                    resultado.get("description"),
                    f"{sbase}.results.{banda}.description",
                    10000,
                    vazio=True,
                )
                _texto(
                    resultado.get("botao_rotulo"),
                    f"{sbase}.results.{banda}.botao_rotulo",
                    80,
                )
        candidata = SimpleNamespace(
            experience={
                "default_format": versao["default_format"],
                "formats": versao["formats"],
                "segments": segmentos,
            }
        )
        for fmt in versao["formats"]:
            for seg in (None, *segmentos):
                try:
                    resolver_experiencia(candidata, fmt=fmt, seg=seg)
                except Http404 as erro:
                    _erro(
                        f"{base}.formats.{fmt}",
                        f"configuração de vídeo/segmento inválida: {erro}",
                    )
    _unicos(versoes, "key", "versoes")
    return dados


@transaction.atomic
def importar_documento(dados, site):
    """Importa versões novas sem alterar conteúdo já plantado."""
    dados = conferir_documento(dados)
    slug = dados["quiz"]["slug"]
    quiz = Quiz.objects.filter(site=site, slug=slug).first()
    if quiz is not None:
        if not quiz.directed or quiz.title != dados["quiz"]["title"]:
            _erro("quiz", "slug já pertence a outro quiz; escolha novo slug")
    ofertas = {o["id"]: o for o in dados["ofertas"]}
    for versao in dados["versoes"]:
        existente = (
            QuizVersion.objects.filter(quiz=quiz, key=versao["key"]).first()
            if quiz
            else None
        )
        if existente is not None:
            original = {
                "formato": FORMATO,
                "quiz": dados["quiz"],
                "ofertas": dados["ofertas"],
                "versao": versao,
            }
            if existente.experience.get("documento") != original:
                _erro(f"versoes.{versao['key']}", "conteúdo diferente; crie nova key")
    if quiz is None:
        quiz = Quiz.objects.create(
            site=site, slug=slug, title=dados["quiz"]["title"], directed=True
        )
    for versao in dados["versoes"]:
        if QuizVersion.objects.filter(quiz=quiz, key=versao["key"]).exists():
            continue
        original = {
            "formato": FORMATO,
            "quiz": dados["quiz"],
            "ofertas": dados["ofertas"],
            "versao": versao,
        }
        experience = {
            "default_format": versao["default_format"],
            "formats": versao["formats"],
            "segments": versao["segments"],
            "ofertas": ofertas,
            "band_offers": {f["key"]: f["oferta_id"] for f in versao["faixas"]},
            "documento": original,
        }
        nova = QuizVersion.objects.create(
            quiz=quiz, key=versao["key"], active=True, weight=0, experience=experience
        )
        for ordem, pergunta in enumerate(versao["perguntas"], start=1):
            p = Question.objects.create(
                version=nova, order=ordem, text=pergunta["texto"]
            )
            for ordem_opt, opcao in enumerate(pergunta["opcoes"], start=1):
                Option.objects.create(
                    question=p,
                    order=ordem_opt,
                    text=opcao["texto"],
                    points=opcao["pontos"],
                )
        for faixa in versao["faixas"]:
            checkout = ofertas[faixa["oferta_id"]]["checkout_url"]
            ResultBand.objects.create(
                version=nova,
                key=faixa["key"],
                title=faixa["title"],
                description=faixa["description"],
                min_score=faixa["min_score"],
                max_score=faixa["max_score"],
                botao_destino=checkout or "",
                botao_rotulo=faixa["botao_rotulo"] if checkout else "",
            )
    return quiz
