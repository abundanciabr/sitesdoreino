"""Agrupamento conservador, sem API paga e sem interpretar texto como instrução."""
import hashlib
import re
import unicodedata

STOP = set('a o os as um uma de da do das dos e em no na nos nas para por com que como meu minha eu ao se nao mais esta esse isso qual quando'.split())


def digest(texto):
    return hashlib.sha256(texto.encode()).hexdigest()


def limpar(texto):
    texto = str(texto or '')[:10000]
    texto = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[e-mail omitido]', texto)
    texto = re.sub(r'\b\d{3}\.?\d{3}\.?\d{3}[-.]?\d{2}\b', '[CPF omitido]', texto)
    texto = re.sub(r'\b(?:\+?\d[ ()-]*?){10,19}\b', '[número omitido]', texto)
    texto = re.sub(r'(?i)\b(?:bearer\s+\S+|sk-[\w-]+|(?:senha|password|token|api[_ -]?key|secret)\s*[:=]\s*\S+)', '[segredo omitido]', texto)
    texto = re.sub(r'https?://[^\s<>]+', '[endereço no fio de origem]', texto)
    return texto


def normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFKD', texto.lower()) if not unicodedata.combining(c))


def teste_identificado(texto, contexto=''):
    t = normalizar(texto)
    c = normalizar(contexto)
    return bool(re.search(r'^(?:\s*\[teste\]|\s*teste (?:tecnico|de integracao|automatizado|autorizado)|\s*ensaio (?:tecnico|administrativo|autorizado)|\s*e2e\b)', t)
                or 'este chamado e apenas uma conferencia' in t
                or re.search(r'(^|[- /])(?:teste|e2e)([- /]|$)', c))


def termos(texto):
    return sorted({p for p in re.findall(r'[a-z0-9]+', normalizar(texto)) if len(p) > 2 and p not in STOP})


def semelhantes(a, b):
    a, b = set(a), set(b)
    return bool(len(a & b) >= 3 and len(a & b) / max(1, len(a | b)) >= .55)
