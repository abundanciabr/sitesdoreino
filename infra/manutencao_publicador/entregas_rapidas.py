#!/usr/bin/env python3
"""Instala somente a ordem da fila, usando backup/retorno do instalador existente."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil

ANTES = '29d347511a6ac6bde693b4f9cab7a7c5c76194a789dccfa5c7002020dda8311d'
DEPOIS = '2a6de6f9971e5820f5799e8e650d697d85f8be303c701e752a5e7a7f72b554b0'
PROVA_ID = 'e2dbc7098214'
INSTALADOR = Path('/opt/plataforma/manutencoes/publicacao-estrutural-c19960b9e7c1/aplicar_canal.py')


def preparar(origem, destino):
    fonte = origem / 'infra/integrador_servico.py'
    dados = fonte.read_bytes()
    if hashlib.sha256(dados).hexdigest() != DEPOIS:
        raise RuntimeError('Fonte difere da correção testada; nenhuma instalação feita.')
    compile(dados, str(fonte), 'exec')
    arquivo = 'fontes/integrador/integrador_servico.py'
    alvo = destino / arquivo
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_bytes(dados)
    manifesto = {'prova_id': PROVA_ID, 'arquivos': [{
        'alvo': 'integrador/integrador_servico.py', 'antes': ANTES,
        'depois': DEPOIS, 'origem': arquivo}]}
    (destino / 'manifest.json').write_text(json.dumps(manifesto, indent=2), encoding='utf-8')
    return destino


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparar', type=Path)
    parser.add_argument('--aplicar', action='store_true')
    args = parser.parse_args()
    origem = Path(__file__).resolve().parents[2]
    if args.aplicar:
        if os.geteuid() != 0:
            raise RuntimeError('Instalação exige o console administrativo autorizado.')
        destino = Path('/opt/plataforma/manutencoes/entregas-rapidas-20261013/pacote')
    elif args.preparar:
        destino = args.preparar.resolve()
    else:
        parser.error('Informe --preparar DIRETORIO ou --aplicar.')
    preparar(origem, destino)
    if args.aplicar:
        spec = importlib.util.spec_from_file_location('instalador_existente', INSTALADOR)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.apply(destino)  # Confere hash anterior, backup, Mercado Pago e recuperação.
    else:
        print(json.dumps({'pacote': str(destino), 'instalado': False}))


if __name__ == '__main__':
    main()
