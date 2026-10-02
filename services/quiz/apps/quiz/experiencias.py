"""Apresentação das experiências do quiz e cálculo aritmético limitado."""

import ast
import math
import re
from urllib.parse import urlsplit

from django.http import Http404


FORMATOS = frozenset({"text", "video", "hybrid", "calc", "ai"})
_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SEGMENT_FIELDS = frozenset({"headline", "subheadline", "video_url"})


def _video_url(url):
    """Aceita mídia direta HTTPS ou embed conhecido, nunca iframe arbitrário."""
    if not isinstance(url, str):
        raise Http404("Vídeo inválido.")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as error:
        raise Http404("Vídeo inválido.") from error
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username
        or parts.password
    ):
        raise Http404("Vídeo inválido.")
    if port not in (None, 443) or parts.fragment:
        raise Http404("Vídeo inválido.")
    host = parts.hostname.lower()
    if host in {
        "youtube.com",
        "www.youtube.com",
        "youtube-nocookie.com",
        "www.youtube-nocookie.com",
    }:
        if (
            parts.query
            or not parts.path.startswith("/embed/")
            or not _VIDEO_ID.fullmatch(parts.path[7:])
        ):
            raise Http404("Embed de vídeo inválido.")
        return "embed"
    if not parts.path.lower().endswith((".mp4", ".webm")):
        raise Http404("Arquivo de vídeo inválido.")
    return "file"


def resolver_experiencia(versao, fmt=None, seg=None):
    """Resolve formato e substituições cadastradas para uma QuizVersion."""
    experience = getattr(versao, "experience", None)
    if not isinstance(experience, dict):
        raise Http404("Experiência não configurada.")
    formats = experience.get("formats")
    if not isinstance(formats, dict):
        raise Http404("Formatos não configurados.")
    chosen = fmt or experience.get("default_format", "text")
    if chosen == "ai_agent":
        chosen = "ai"
    if chosen not in FORMATOS or not isinstance(formats.get(chosen), dict):
        raise Http404("Formato indisponível.")
    data = formats[chosen]
    resolved = {
        "fmt": chosen,
        "seg": seg or "",
        "headline": data.get("headline", ""),
        "subheadline": data.get("subheadline", ""),
        "video_url": data.get("video_url", ""),
        "calculator": data.get("calculator") if chosen == "calc" else None,
        "ai_disponivel": False,
    }
    if seg:
        segments = experience.get("segments", {})
        if not isinstance(segments, dict) or not isinstance(segments.get(seg), dict):
            raise Http404("Segmento não configurado.")
        for field in _SEGMENT_FIELDS:
            if field in segments[seg] and (
                field != "video_url" or segments[seg][field] is not None
            ):
                resolved[field] = segments[seg][field]
        resolved["results"] = segments[seg].get("results", {})
    if chosen in {"video", "hybrid"} and resolved["video_url"] in (None, ""):
        # Formato cadastrado com a VSL ainda em produção: a página abre com o
        # aviso no lugar do vídeo e a medição por formato já funciona.
        resolved["video_url"] = ""
        resolved["video_kind"] = "pendente"
    elif chosen in {"video", "hybrid"}:
        resolved["video_kind"] = _video_url(resolved["video_url"])
    else:
        resolved["video_url"] = ""
        resolved["video_kind"] = ""
    if chosen == "calc" and not isinstance(resolved["calculator"], dict):
        raise Http404("Calculadora não configurada.")
    return resolved


def _numero(value):
    if isinstance(value, bool):
        raise ValueError("Valor numérico inválido.")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("Valor numérico inválido.") from error
    if not math.isfinite(number):
        raise ValueError("Valor numérico inválido.")
    return number


def _avaliar(node, variables):
    if isinstance(node, ast.Expression):
        return _avaliar(node.body, variables)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return _numero(node.value)
    if isinstance(node, ast.Name) and node.id in variables:
        return variables[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _avaliar(node.operand, variables)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and isinstance(
        node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)
    ):
        left, right = _avaliar(node.left, variables), _avaliar(node.right, variables)
        if isinstance(node.op, ast.Add):
            result = left + right
        elif isinstance(node.op, ast.Sub):
            result = left - right
        elif isinstance(node.op, ast.Mult):
            result = left * right
        else:
            if right == 0:
                raise ValueError("Divisão por zero.")
            result = left / right
        return _numero(result)
    raise ValueError("Expressão não permitida.")


def calcular(calculator, values):
    """Calcula apenas +, -, * e / sobre entradas declaradas e finitas."""
    if not isinstance(calculator, dict) or not isinstance(values, dict):
        raise ValueError("Calculadora inválida.")
    inputs = calculator.get("inputs")
    expression = calculator.get("expression")
    if not isinstance(inputs, list) or not 1 <= len(inputs) <= 20:
        raise ValueError("Entradas inválidas.")
    if not isinstance(expression, str) or not 1 <= len(expression) <= 256:
        raise ValueError("Expressão inválida.")
    variables = {}
    for item in inputs:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("key"), str)
            or not _KEY.fullmatch(item["key"])
        ):
            raise ValueError("Entrada inválida.")
        key = item["key"]
        if key in variables:
            raise ValueError("Entrada repetida.")
        number = _numero(values.get(key, item.get("default")))
        if "min" in item and number < _numero(item["min"]):
            raise ValueError(f"{key} abaixo do mínimo.")
        if "max" in item and number > _numero(item["max"]):
            raise ValueError(f"{key} acima do máximo.")
        variables[key] = number
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError, RecursionError) as error:
        raise ValueError("Expressão inválida.") from error
    if sum(1 for _ in ast.walk(tree)) > 100:
        raise ValueError("Expressão extensa demais.")
    try:
        result = _avaliar(tree, variables)
    except RecursionError as error:
        raise ValueError("Expressão extensa demais.") from error
    return {
        "result": _numero(result),
        "result_label": str(calculator.get("result_label", "Resultado")),
    }
