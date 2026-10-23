"""Leituras existentes da jornada, com escopo e cobertura explícitos."""
import datetime as dt
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context

import httpx

from .clients import AlunosClient, MedicaoClient, http

CHAVES = ('cadastros', 'pedidos', 'liberacoes', 'forum')
NOMES = {
    'cadastros': ('Cadastros', 'pessoas distintas nos fatos de cadastro'),
    'pedidos': ('Pedidos de entrada', 'matrículas distintas que chegaram à fila'),
    'liberacoes': ('Liberações da fila', 'matrículas distintas liberadas'),
    'forum': ('Participação no fórum', 'autores distintos de tópicos ou mensagens'),
}


def _inteiro(valor):
    return type(valor) is int and valor >= 0


def _escopo(corpo, site_id, de, ate):
    return (isinstance(corpo, dict) and corpo.get('site_id') == site_id
            and corpo.get('de') == de.isoformat() and corpo.get('ate') == ate.isoformat())


class FatosDaJornada(MedicaoClient):
    def ler(self, site_id, de, ate):
        estado, corpo = self._pedir('/jornada-acesso', {'site_id': site_id, 'de': de.isoformat(), 'ate': ate.isoformat()})
        if estado != self.OK:
            return estado, None
        if not _escopo(corpo, site_id, de, ate):
            return self.NAO_RESPONDEU, None
        linhas = corpo.get('leituras')
        if not isinstance(linhas, list) or len(linhas) != len(CHAVES):
            return self.NAO_RESPONDEU, None
        if {l.get('chave') for l in linhas if isinstance(l, dict)} != set(CHAVES):
            return self.NAO_RESPONDEU, None
        for linha in linhas:
            n = linha.get('quantidade')
            if n is not None and not _inteiro(n):
                return self.NAO_RESPONDEU, None
            if not _inteiro(linha.get('sem_identificador')):
                return self.NAO_RESPONDEU, None
            datas = []
            for campo in ('primeiro', 'ultimo'):
                try:
                    data = dt.datetime.fromisoformat(linha[campo]) if linha.get(campo) else None
                except (ValueError, TypeError):
                    return self.NAO_RESPONDEU, None
                if data is not None and data.tzinfo is None:
                    return self.NAO_RESPONDEU, None
                datas.append(data)
            if (n is None) != (datas == [None, None]) or (n is not None and (None in datas or datas[0] > datas[1])):
                return self.NAO_RESPONDEU, None
            linha['primeiro'], linha['ultimo'] = datas
        return self.OK, {l['chave']: l for l in linhas}


class LinksDaJornada(AlunosClient):
    def ler(self, site_id, de, ate):
        config = self._configuracao()
        if config is None:
            return MedicaoClient.SEM_CONFIGURACAO, None
        base, token = config
        try:
            r = http().get(base + '/jornada-acesso/medicoes',
                params={'site_id': site_id, 'de': de.isoformat(), 'ate': ate.isoformat()},
                headers={'Authorization': 'Bearer ' + token}, timeout=self.TIMEOUT)
            corpo = r.json() if r.status_code == 200 else None
        except (httpx.HTTPError, ValueError):
            corpo = None
        if not _escopo(corpo, site_id, de, ate):
            return MedicaoClient.NAO_RESPONDEU, None
        if not all(_inteiro(corpo.get(k)) for k in ('liberadas', 'com_link', 'usaram_link')):
            return MedicaoClient.NAO_RESPONDEU, None
        if not corpo['usaram_link'] <= corpo['com_link'] <= corpo['liberadas']:
            return MedicaoClient.NAO_RESPONDEU, None
        if 'inicio_coleta' in corpo:
            n = corpo.get('observadas_periodo')
            coorte = corpo.get('autenticadas')
            if (coorte is not None and not _inteiro(coorte)) or (n is not None and coorte is not None and coorte > n):
                return MedicaoClient.NAO_RESPONDEU, None
            if n is not None and not _inteiro(n):
                return MedicaoClient.NAO_RESPONDEU, None
            for campo in ('inicio_coleta', 'primeiro_observado', 'ultimo_observado'):
                valor = corpo.get(campo)
                try:
                    data = dt.datetime.fromisoformat(valor) if valor else None
                except (ValueError, TypeError):
                    return MedicaoClient.NAO_RESPONDEU, None
                if data is not None and data.tzinfo is None:
                    return MedicaoClient.NAO_RESPONDEU, None
                corpo[campo] = data
            sem_cobertura = corpo['inicio_coleta'] is None or corpo['inicio_coleta'].astimezone(ZoneInfo('America/Sao_Paulo')).date() > ate
            if ((n is None) != sem_cobertura or (coorte is None) != sem_cobertura
                    or (n == 0 and (corpo['primeiro_observado'] or corpo['ultimo_observado']))
                    or (n and (not corpo['primeiro_observado'] or not corpo['ultimo_observado']
                        or corpo['primeiro_observado'] < corpo['inicio_coleta']
                        or corpo['primeiro_observado'] > corpo['ultimo_observado']))):
                return MedicaoClient.NAO_RESPONDEU, None
        return MedicaoClient.OK, corpo


def ler(site_id, hoje):
    de = hoje - dt.timedelta(days=27)
    resultado = {'de': de, 'ate': hoje, 'fatos_estado': 'sem-site', 'links_estado': 'sem-site', 'linhas': [], 'links': None}
    if not site_id:
        return resultado
    with ThreadPoolExecutor(max_workers=2) as executor:
        fatos = executor.submit(copy_context().run, FatosDaJornada().ler, site_id, de, hoje)
        links = executor.submit(copy_context().run, LinksDaJornada().ler, site_id, de, hoje)
        resultado['fatos_estado'], leituras = fatos.result()
        resultado['links_estado'], resultado['links'] = links.result()
    for chave in CHAVES:
        nome, unidade = NOMES[chave]
        leitura = (leituras or {}).get(chave, {})
        resultado['linhas'].append({'nome': nome, 'unidade': unidade, 'quantidade': None,
            'primeiro': None, 'ultimo': None, 'sem_identificador': 0, **leitura})
    return resultado
