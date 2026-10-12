"""Leitura dos formatos Hotmart preservados, sem alterar o JSON de origem."""
import re


def objeto(valor):
    return valor if isinstance(valor, dict) else {}


def extrair(registro):
    dados = objeto(registro.dados.get('data'))
    assinatura = objeto(dados.get('subscription'))
    comprador = (objeto(dados.get('buyer')) or objeto(dados.get('subscriber'))
                 or objeto(dados.get('user')) or objeto(assinatura.get('user')))
    produto = objeto(dados.get('product')) or objeto(assinatura.get('product'))
    compra = objeto(dados.get('purchase'))
    telefone = comprador.get('phone') or comprador.get('checkout_phone') or ''
    codigo = comprador.get('checkout_phone_code') or ''
    if isinstance(telefone, dict):
        codigo = telefone.get('dddCell') or telefone.get('dddPhone') or ''
        telefone = telefone.get('cell') or telefone.get('phone') or ''
    return {'registro': registro, 'nome': str(comprador.get('name') or ''),
            'email': str(comprador.get('email') or '').strip().lower(),
            'telefone': str(telefone), 'codigo_telefone': str(codigo),
            'produto': str(produto.get('name') or ''),
            'produto_id': str(produto.get('id') or ''),
            'transacao': str(compra.get('transaction') or '')}


def telefone_administrativo(valor):
    # O administrador fornece explicitamente DDI + DDD + número; não se deduz país.
    numero = re.sub(r'\D', '', valor or '')
    if not 10 <= len(numero) <= 15 or numero.startswith('0') or len(set(numero)) < 3:
        raise ValueError('Informe seu WhatsApp completo, com DDI, DDD e número.')
    return '+' + numero
