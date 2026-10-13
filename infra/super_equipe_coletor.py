#!/usr/bin/env python3
"""Lê a operação local e grava só totais, nunca linhas de log ou ambiente."""
from collections import Counter
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.request
import urllib.error

DESTINO = Path("/run/meshcraft-super-equipe/telemetria.json")
ACESSO = re.compile(r'HTTP/[12](?:\.[01])?"\s+(\d{3})\b')
ENTREGAS = Path("/var/lib/meshcraft-integrador/entregas")


def capacidade(agora, anterior, proc=Path('/proc')):
    """Contadores do host entre coletas; não atribui uso a um serviço."""
    saida = dict(cpu_ocupada_percentual=None, cpu_iowait_percentual=None,
        memoria_total_mb=None, memoria_disponivel_mb=None, memoria_usada_mb=None,
        io_leitura_bytes_s=None, io_escrita_bytes_s=None, intervalo_capacidade_segundos=None)
    contadores = {'instante': agora}
    try:
        cpu = [int(x) for x in (proc/'stat').read_text().splitlines()[0].split()[1:9]]
        if len(cpu) != 8:
            raise ValueError()
        contadores['cpu'] = cpu
        memoria = {l.split(':')[0]: int(l.split()[1]) for l in (proc/'meminfo').read_text().splitlines() if l.split()[1].isdigit()}
        total, disponivel = memoria['MemTotal'], memoria['MemAvailable']
        if not 0 <= disponivel <= total:
            raise ValueError()
        saida.update(memoria_total_mb=round(total/1024, 3),
            memoria_disponivel_mb=round(disponivel/1024, 3), memoria_usada_mb=round((total-disponivel)/1024, 3))
    except (OSError, ValueError, KeyError, IndexError):
        pass
    try:
        discos = {}
        for linha in (proc/'diskstats').read_text().splitlines():
            campos = linha.split()
            # Somente discos inteiros físicos/virtuais; exclui partições e camadas dm/loop.
            if re.fullmatch(r'(?:sd|vd|xvd)[a-z]+|nvme[0-9]+n[0-9]+', campos[2]):
                discos[campos[2]] = [int(campos[5])*512, int(campos[9])*512]
        if discos:
            contadores['discos'] = discos
    except (OSError, ValueError, IndexError):
        pass
    antes = anterior.get('_capacidade_contadores') or {}
    janela = agora - antes.get('instante', agora)
    if 0 < janela <= 300:
        saida['intervalo_capacidade_segundos'] = round(janela, 3)
        cpu_antes = antes.get('cpu')
        if len(contadores.get('cpu', [])) == 8 and isinstance(cpu_antes, list) and len(cpu_antes) == 8:
            delta = [b-a for a, b in zip(cpu_antes, contadores['cpu'])]
            total = sum(delta)
            if min(delta) >= 0 and total > 0:
                saida['cpu_ocupada_percentual'] = round(100*(total-delta[3]-delta[4])/total, 3)
                saida['cpu_iowait_percentual'] = round(100*delta[4]/total, 3)
        discos, velhos = contadores.get('discos'), antes.get('discos')
        if discos and velhos and discos.keys() == velhos.keys():
            delta = [[b-a for a,b in zip(velhos[n], discos[n])] for n in discos]
            if all(min(d) >= 0 for d in delta):
                saida['io_leitura_bytes_s'] = round(sum(d[0] for d in delta)/janela, 3)
                saida['io_escrita_bytes_s'] = round(sum(d[1] for d in delta)/janela, 3)
    saida['_capacidade_contadores'] = contadores
    return saida


class SemRedirecionar(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def sondas():
    """Dois GETs fixos públicos: tempo até cabeçalhos, sem guardar corpo."""
    itens = []
    for alvo, url in (('inicio', 'https://meshcraft.top/'), ('robots', 'https://meshcraft.top/robots.txt')):
        inicio = time.monotonic()
        http = None
        try:
            with urllib.request.build_opener(SemRedirecionar()).open(url, timeout=5) as resposta:
                http = resposta.status
        except urllib.error.HTTPError as erro:
            http = erro.code
        except (OSError, ValueError):
            pass
        itens.append({'alvo': alvo, 'http': http,
            'tempo_ms': round((time.monotonic()-inicio)*1000, 3) if http is not None else None,
            'estado': 'medido' if http is not None else 'indisponivel'})
    return itens


def ler_json(path, default=None):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def armazenamento(agora, disco, anterior, pasta=ENTREGAS):
    """Lê registros pequenos. Nenhum du, count-objects ou varredura de blobs."""
    if not pasta.is_dir():
        raise FileNotFoundError(pasta)
    historico = [x for x in anterior.get("historico_disco", [])
                 if 0 < agora - x[0] <= 1800][-29:]
    historico.append([agora, disco.used])
    janela = agora - historico[0][0]
    crescimento = disco.used - historico[0][1]
    taxa = crescimento / janela if janela >= 60 else None
    pico = max([max(0, b[1]-a[1]) for a, b in zip(historico, historico[1:])] or [0])
    saida = {"disco_total_mb": disco.total//1048576, "disco_usado_mb": disco.used//1048576,
             "janela_segundos": int(janela), "crescimento_mb_h": round(taxa*3600/1048576, 2) if taxa is not None else None,
             "horas_ate_esgotar": round(disco.free/taxa/3600, 2) if taxa and taxa > 0 else None,
             "pico_entre_coletas_mb": round(pico/1048576, 2), "historico_disco": historico}
    medicao = ler_json(pasta/"medicoes/combinacoes.json", {})
    regs = [ler_json(p, {}) for p in pasta.glob("[0-9a-f]*.json")]
    conflito = [r for r in regs if r.get("estado") == "conflito"]
    amostra = {}
    repeticoes = 0
    for reg in conflito:
        entradas = {k: reg.get(k) for k in ("commit", "base", "main_observada", "depende_de")}
        entradas["combinacao"] = (reg.get("combinacao") or {}).get("chave")
        chave = hashlib.sha256(json.dumps(entradas, sort_keys=True).encode()).hexdigest()
        atual = {"chave": chave, "tentativas": reg.get("tentativas", 0)}
        antes = anterior.get("amostra_integrador", {}).get(reg["id"], {})
        if antes.get("chave") == chave:
            repeticoes += max(0, atual["tentativas"] - antes.get("tentativas", 0))
        amostra[reg["id"]] = atual
    fases = [ler_json(p, {}) for p in (pasta/"fases").glob("[0-9a-f]*.json")]
    concluidas = [f.get("concluida_em") for f in fases
                 if f.get("fase") in ("ativa", "preservada em versão posterior") and f.get("concluida_em")]
    saida["amostra_integrador"] = amostra
    saida["integrador"] = {"coletada_em": medicao.get("coletada_em"),
        "conflitos": len(conflito), "repeticoes_identicas": repeticoes if anterior.get("amostra_integrador") is not None else None,
        "conflitos_protegidos": sum(bool((r.get("combinacao") or {}).get("chave"))
                                    and r.get("main_observada") == medicao.get("main") for r in conflito),
        "totais": medicao.get("totais", {}), "rodada": medicao.get("rodada", {}),
        "ultima_ativacao_em": max(concluidas, default=None),
        "entregas_concluidas": len(concluidas)}
    return saida


def contar(linhas):
    codigos = Counter()
    for linha in linhas:
        encontrado = ACESSO.search(linha)
        if encontrado:
            codigos[int(encontrado[1])] += 1
    return {"http_5xx_15m": sum(n for s, n in codigos.items() if 500 <= s < 600) if codigos else None,
            "http_404_15m": codigos[404] if codigos else None}


def coletar():
    agora = datetime.now(timezone.utc)
    disco = shutil.disk_usage("/opt/plataforma")
    anterior = ler_json(DESTINO, {})
    dados = {"coletada_em": agora.isoformat(), "coletor": "ativo",
             "disco_livre_mb": disco.free//(1024*1024),
             "aplicacao": "indisponivel", "funil": "indisponivel",
             "http_5xx_15m": None, "http_404_15m": None}
    dados.update(capacidade(agora.timestamp(), anterior))
    dados['sondas_http'] = sondas()
    try:
        dados.update(armazenamento(agora.timestamp(), disco, anterior))
        dados["imagens_manutencao"] = ler_json(Path("/opt/plataforma/objetos-imagens-manutencao/uso.json"), {})
    except (OSError, ValueError, KeyError, TypeError):
        dados["integrador"] = {"estado": "indisponivel"}
    try:
        r = subprocess.run(["docker", "ps", "-a", "--format", "{{json .}}"],
                           capture_output=True, text=True, timeout=20, check=True)
        containers = [json.loads(l) for l in r.stdout.splitlines()]
        for nome, prefixo in (("aplicacao", "plataforma-aplicacao-1"), ("funil", "meshcraft-funil-")):
            encontrados = [c for c in containers if (c["Names"] == prefixo if nome == "aplicacao"
                              else re.fullmatch(r"meshcraft-funil-[0-9a-f]+-[0-9a-f]+", c["Names"]))]
            dados[nome] = "ativo" if any(c.get("State") == "running" and "unhealthy" not in c.get("Status", "") for c in encontrados) else "inativo"
        # O acesso ao Docker fica só neste coletor de comando fixo. A saída bruta
        # não é gravada nem fornecida ao executor ou ao modelo.
        logs = subprocess.run(["docker", "logs", "--since", "15m", "--tail", "30000", "plataforma-aplicacao-1"],
                              capture_output=True, text=True, errors="replace", timeout=30, check=True)
        dados.update(contar((logs.stdout+logs.stderr).splitlines()))
    except (subprocess.SubprocessError, OSError, ValueError, KeyError):
        dados["coletor"] = "indisponivel"
    return dados


def main():
    temporario = DESTINO.with_suffix(".novo")
    temporario.write_text(json.dumps(coletar()), encoding="utf-8")
    temporario.chmod(0o644)  # somente totais; não contém identificadores pessoais
    temporario.replace(DESTINO)


if __name__ == "__main__":
    main()
