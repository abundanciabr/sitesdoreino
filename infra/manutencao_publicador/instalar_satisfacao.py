"""Instala a proteção autorizada da pesquisa; não substitui aplicação nem banco."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

PUB = Path('/usr/local/lib/meshcraft-publicador/atual')
RAIZ = Path('/opt/plataforma')


def carregar(nome, caminho):
    spec = importlib.util.spec_from_file_location(nome, caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def gravar(caminho, dados, modo=0o444):
    temporario = caminho.with_name(caminho.name + '.pesquisa-nova')
    with temporario.open('wb') as arquivo:
        arquivo.write(dados)
        arquivo.flush()
        os.fsync(arquivo.fileno())
    os.chown(temporario, 0, 0)
    temporario.chmod(modo)
    os.replace(temporario, caminho)


def instalar(backup):
    if os.geteuid() != 0:
        raise RuntimeError('instalação administrativa exige o canal autorizado')
    backup = Path(backup)
    if backup.is_symlink() or backup.stat().st_uid != 0 or backup.stat().st_mode & 0o077:
        raise RuntimeError('pasta privada do backup inválida')
    prova = json.loads((backup / 'backup-concluido.json').read_text())
    if not all(prova.get(k) is True for k in ('codigo', 'publicador', 'imagem', 'configuracao', 'bancos')):
        raise RuntimeError('backup completo não comprovado')
    ferramentas = PUB.resolve(strict=True)
    if ferramentas.parent != PUB.parent or ferramentas.stat().st_uid != 0 or ferramentas.stat().st_mode & 0o022:
        raise RuntimeError('ferramentas independentes inválidas')
    guarda = carregar('guarda_pesquisa_preparada', backup / 'satisfacao_congelada.py')
    politica = json.loads((backup / 'politica.json').read_text())
    if politica.get('commit_aprovado') != '120efd440db47993889f7bb12fc7e846bf89962c':
        raise RuntimeError('referência distinta da pesquisa aprovada')
    ativa = json.loads(subprocess.check_output(['docker', 'inspect', 'plataforma-aplicacao-1']))[0]
    codigo = Path(next(m['Source'] for m in ativa['Mounts'] if m['Destination'] == '/app'))
    guarda.comparar(guarda.resumo(codigo, pacote=True), politica['resumo'])
    antes = json.loads((backup / 'ativa.json').read_text())
    if antes != {'codigo': str(codigo), 'imagem': ativa['Image']}:
        raise RuntimeError('aplicação mudou durante o backup; instalação adiada')
    protegidos = ('mercadopago/politica.json', 'infra/mercadopago_congelado.py',
        'docs/politica.json', 'infra/docs_somente_admin.py')
    hashes = {n: hashlib.sha256((ferramentas / n).read_bytes()).hexdigest() for n in protegidos}
    arquivos = ('infra/publicar.py', 'infra/publicacao-local.py', 'infra/ativar-aplicacao.py')
    originais = {n: (ferramentas / n).read_bytes() for n in arquivos}
    modos = {n: (ferramentas / n).stat().st_mode & 0o777 for n in arquivos}
    novos = {}
    for nome, dados in originais.items():
        texto = dados.decode('utf-8')
        if 'conferir_codigo_satisfacao' in texto:
            raise RuntimeError('proteção já presente; não substituir por outra referência')
        linhas = texto.splitlines()
        nova, chamadas = [], 0
        for linha in linhas:
            nova.append(linha)
            if linha.startswith('from docs_somente_admin import '):
                nova.append('from satisfacao_congelada import conferir_fontes_satisfacao, conferir_codigo_satisfacao')
            elif nome.endswith('ativar-aplicacao.py') and linha.startswith('from mercadopago_congelado import '):
                nova.append('from satisfacao_congelada import conferir_codigo_satisfacao')
            elif linha.strip().startswith(('conferir_codigo_docs(', 'conferir_fontes_docs(')):
                nova.append(linha.replace('conferir_codigo_docs(', 'conferir_codigo_satisfacao(')
                    .replace('conferir_fontes_docs(', 'conferir_fontes_satisfacao('))
                chamadas += 1
            elif nome.endswith('ativar-aplicacao.py') and linha.strip().startswith('conferir_mp_pacote('):
                nova.append('    conferir_codigo_satisfacao(Path(versao["codigo"]))')
                chamadas += 1
        if chamadas != (1 if nome.endswith('ativar-aplicacao.py') else 4):
            raise RuntimeError('pontos de ativação diferentes dos conferidos: ' + nome)
        novo = ('\n'.join(nova) + '\n').encode()
        ast.parse(novo)
        novos[nome] = novo
    destino = ferramentas / 'satisfacao'
    if destino.exists():
        raise RuntimeError('referência da pesquisa já instalada; preservada')
    destino.mkdir(mode=0o755)
    try:
        gravar(ferramentas / 'infra/satisfacao_congelada.py', (backup / 'satisfacao_congelada.py').read_bytes())
        gravar(destino / 'politica.json', (backup / 'politica.json').read_bytes())
        instalada = carregar('guarda_pesquisa_instalada', ferramentas / 'infra/satisfacao_congelada.py')
        instalada.conferir_codigo_satisfacao(codigo)
        for nome, dados in novos.items():
            gravar(ferramentas / nome, dados, modos[nome])
        for nome, esperado in hashes.items():
            if hashlib.sha256((ferramentas / nome).read_bytes()).hexdigest() != esperado:
                raise RuntimeError('proteção anterior mudou: ' + nome)
        # Prova uma alteração real em cópia privada; nunca ativa a cópia alterada.
        candidata = backup / 'candidata-recusa'
        shutil.copytree(backup / 'codigo-aprovado', candidata, symlinks=True)
        pagina = candidata / 'modules/cursos/apps/core/templates/cursos/satisfacao.html'
        pagina.chmod(0o600)
        pagina.write_bytes(pagina.read_bytes() + b'\n<p>Alteracao de prova</p>\n')
        try:
            instalada.conferir_codigo_satisfacao(candidata)
        except instalada.IntegridadePesquisaErro:
            recusada = True
        else:
            raise RuntimeError('candidata alterada foi aceita')
        # Verificação existente, com sua própria política e sem qualquer exceção.
        mp = carregar('mp_preservado_pesquisa', ferramentas / 'infra/mercadopago_congelado.py')
        politica_mp = json.loads((ferramentas / 'mercadopago/politica.json').read_text())
        mp.conferir_ambiente(RAIZ, politica_mp)
        mp.conferir_pacote(codigo, ativa['Image'], politica_mp)
        sem_escrita = {}
        for usuario in ('robo', 'integrador', 'deploy'):
            for caminho in (destino, destino / 'politica.json', ferramentas / 'infra/satisfacao_congelada.py'):
                resultado = subprocess.run(['runuser', '-u', usuario, '--', 'test', '-w', str(caminho)])
                if resultado.returncode != 1:
                    raise RuntimeError('permissão de escrita inesperada ou usuário não conferido')
            sem_escrita[usuario] = True
        instalada.conferir_codigo_satisfacao(codigo)
        resultado = {'instalada': True, 'pesquisa_ativa_igual_aprovada': True,
            'alteracao_recusada': recusada, 'sem_escrita': sem_escrita,
            'protecao_anterior_preservada': True, 'pontos_conferidos': 9,
            'publicador': str(ferramentas), 'backup': str(backup), 'referencia': politica['commit_aprovado']}
        (backup / 'instalacao-comprovada.json').write_text(json.dumps(resultado, ensure_ascii=False, indent=2))
        print(json.dumps(resultado, ensure_ascii=False))
    except BaseException:
        # Volta exclusivamente os controles; aplicação e bancos não são restaurados.
        for nome, dados in originais.items():
            gravar(ferramentas / nome, dados, modos[nome])
        (backup / 'instalacao-desfeita.json').write_text(json.dumps({'controles_restaurados': True}))
        raise


if __name__ == '__main__':
    instalar(sys.argv[1])
