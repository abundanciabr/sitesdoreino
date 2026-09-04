"""`/admin/perpetuo/` — a área do lançamento perpétuo (02/09/2026).

Pedido do mantenedor, na frase dele: *"no painel do admin crie uma parte assim
`/admin/perpetuo` onde iremos criar várias coisas sobre o lançamento perpétuo,
teremos várias páginas, vários painéis"*. Este arquivo é a PORTA dessa área e a
primeira peça dela: **o mapa da máquina**.

## O que é um lançamento perpétuo, para quem lê esta pasta

Um lançamento comum abre as matrículas por alguns dias e fecha. O perpétuo não
fecha: cada pessoa que chega começa o próprio caminho, no relógio dela. Quem
entrou hoje encontra o mesmo convite que alguém encontrou semana passada, na
mesma ordem, porque quem conduz é a máquina e não o calendário.

Uma máquina dessas tem seis peças, e é isso que a tela desenha. As peças são
CONCEITO (o que cada etapa faz), e conceito não envelhece em silêncio.

## De onde vêm os endereços — e por que esta tela NÃO os escreve

Aqui embaixo, cada etapa lista só o **endereço** das portas que já a servem
hoje. O nome de cada porta, a explicação e o link clicável saem de
`painel/mapa-do-site.json`, que é a única fonte de endereços do projeto — o
`ci/mapa_do_site.py` a confere em todo PR, nos dois sentidos (rota sem entrada
no mapa reprova, entrada sem rota também).

É a lei anti-duplicação do `CLAUDE.md` aplicada: se o nome de uma tela mudasse,
uma cópia dele aqui continuaria mostrando o nome velho, e ninguém saberia qual
das duas está certa. Aqui só mora o que o mapa não sabe: **a qual peça da
máquina cada porta pertence**, que é uma decisão de negócio e não um fato
medível.

**Endereço escrito aqui que não existe no mapa é BURACO, e a tela grita.** A
linha vira um aviso à vista em vez de um link para lugar nenhum, e
`tests/test_perpetuo.py::test_toda_porta_existe_no_mapa_do_site` reprova o PR
antes disso chegar à tela do mantenedor. Um link que devolve 404 é pior que
link nenhum: ele faz o dono concluir que o site quebrou.

## O que esta área NÃO faz

Não guarda lista própria de "o que já está pronto" nem de "o que falta". Isso é
superfície paralela de acompanhamento, e o `CLAUDE.md` a proíbe: o que está
pronto se lê no livro de ocorrências, calculado, em `/admin/painel/`.
"""

from __future__ import annotations

import json

from django.shortcuts import render
from django.views.decorators.http import require_GET

# `_preparar` é REUSADA, e não copiada, de propósito: é ela que decide quando
# um endereço vira link clicável (endereço concreto, público, que não é gesto
# de botão) e quando não vira. Uma segunda cópia dessa regra aqui ofereceria
# link para um molde como `/quiz/quiz/<slug:slug>/`, que devolve 404.
from .mapa_do_site import _preparar, arquivo_do_mapa

# As seis peças da máquina, na ordem em que uma pessoa as atravessa: de quem
# nunca ouviu falar da escola até quem já está dentro dela.
#
# `portas` são os endereços EXATOS do `painel/mapa-do-site.json`. Escrever o
# endereço e nada mais é o que mantém esta lista pequena e verdadeira: tudo o
# que se pode medir, o mapa mede.
ETAPAS = (
    {
        "chave": "atrair",
        "nome": "Atrair",
        "pergunta": "Como alguém que nunca ouviu falar da escola chega até aqui?",
        "resumo": (
            "A primeira peça é a mais barata de errar e a mais cara de deixar "
            "parada: sem gente nova entrando, todo o resto da máquina funciona "
            "no vazio. É a vitrine do site e o que aparece no alto de cada "
            "página."
        ),
        "portas": ("/", "/admin/menu/"),
    },
    {
        "chave": "capturar",
        "nome": "Capturar o contato",
        "pergunta": "O que a pessoa ganha em troca de deixar o contato dela?",
        "resumo": (
            "Visitante que vai embora sem deixar nada não volta, e a máquina "
            "fica sem como falar com ele de novo. Aqui a troca acontece: a "
            "pessoa recebe algo de valor e deixa nome, e-mail ou WhatsApp."
        ),
        "portas": ("/cadastro", "/quiz/quiz/<slug:slug>/"),
    },
    {
        "chave": "aquecer",
        "nome": "Aquecer",
        "pergunta": "O que chega até a pessoa depois, sem você precisar mandar?",
        "resumo": (
            "É esta peça que faz o lançamento ser perpétuo: as mensagens saem "
            "sozinhas, na ordem certa, contadas a partir do dia em que aquela "
            "pessoa chegou. Os textos que convencem também moram aqui."
        ),
        "portas": ("/avisos/ligar", "/docs/", "/admin/documentos/"),
    },
    {
        "chave": "decidir",
        "nome": "Decidir a entrada",
        "pergunta": "Quem pediu para entrar, e o que você respondeu?",
        "resumo": (
            "O ponto em que a máquina para e espera por você. Toda pessoa que "
            "pede entrada fica numa fila, e cada dia parado nela é um dia de "
            "alguém animado esfriando."
        ),
        "portas": ("/login", "/admin/escola/alunos/", "/admin/escola/turmas/"),
    },
    {
        "chave": "entregar",
        "nome": "Entregar",
        "pergunta": "O que a pessoa encontra quando finalmente entra?",
        "resumo": (
            "A peça que decide se ela fica. Num perpétuo isso importa duas "
            "vezes: aluno satisfeito vira o boca a boca que alimenta a "
            "primeira peça, de graça."
        ),
        "portas": (
            "/forum/",
            "/conquistas/",
            "/forms/sugestoes/",
            "/admin/economia/",
            # 04/09/2026: o quadro de pontos nasceu depois desta área, e
            # entrega é onde ele responde ("quem está jogando, e quem parou").
            "/admin/escola/pontos/",
        ),
    },
    {
        "chave": "medir",
        "nome": "Medir",
        "pergunta": (
            "De cada cem pessoas que chegam, quantas passam para a etapa seguinte?"
        ),
        # O texto NÃO nomeia a tela para onde aponta, e o guarda
        # `test_o_codigo_nao_guarda_copia_do_nome_das_telas` reprovou a primeira
        # versão que nomeava — com razão. Nome de tela citado em prosa envelhece
        # no dia em que alguém a renomeia; o nome vivo vem do mapa, na porta
        # logo abaixo. Isto é a lei desta área funcionando contra quem a
        # escreveu, que é quando dá para confiar nela.
        "resumo": (
            "A peça que transforma melhorar a máquina em decisão, e não em "
            "palpite: quantas pessoas passam de uma etapa para a seguinte, e "
            "em quais delas a casa ainda não sabe medir."
        ),
        # `/admin/placar/` entra aqui em 04/09/2026, e a ordem importa: ele é
        # a tela do funil desta casa (a barra do mês, a meta e a restrição da
        # semana, com pedidos, liberações e tempo típico ao vivo da `alunos`).
        # A área do perpétuo NÃO monta um funil próprio — seria a segunda
        # definição do mesmo fato, e o `CLAUDE.md` a proíbe. Ela aponta.
        "portas": ("/admin/placar/", "/admin/escola/jornada/"),
    },
)


def _mapa_por_endereco() -> "dict | None":
    """O `painel/mapa-do-site.json` indexado pelo endereço, ou `None`.

    `None` é *"não consegui ler o mapa"*, e nunca um dicionário vazio: um vazio
    faria toda porta desta tela virar buraco, e o mantenedor leria "a máquina
    não tem nada" quando a verdade é que o arquivo não veio na imagem.
    """
    caminho = arquivo_do_mapa()
    if caminho is None:
        return None
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        entradas = dados["enderecos"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return None
    if not isinstance(entradas, list):
        return None
    return {str(e.get("endereco", "")): e for e in entradas if isinstance(e, dict)}


def etapas_com_portas(mapa: "dict | None") -> list[dict]:
    """As seis peças, cada uma com as portas que o mapa do site descreve.

    Porta que o mapa não conhece NÃO some: ela vira `faltando`, com o endereço
    à vista. Sumir em silêncio é a pior forma de perder um fato, e um endereço
    que mudou de nome sem ninguém avisar é exatamente o caso que esta linha
    existe para tornar visível.
    """
    montadas = []
    for etapa in ETAPAS:
        portas = []
        for endereco in etapa["portas"]:
            entrada = None if mapa is None else mapa.get(endereco)
            if entrada is None:
                portas.append({"endereco": endereco, "faltando": True})
                continue
            porta = _preparar(entrada)
            porta["faltando"] = False
            portas.append(porta)
        montadas.append({**etapa, "portas": portas})
    return montadas


@require_GET
def perpetuo(request):
    """A porta da área: o mapa da máquina do lançamento perpétuo.

    **Abre com 200 mesmo sem o mapa do site, e a diferença para
    `mapa_do_site.py` (que devolve 500) é deliberada.** Lá, o arquivo É a
    página: sem ele não sobra nada, e uma tela vazia diria "este site não tem
    endereço nenhum". Aqui o arquivo é só a metade dos links: as seis peças da
    máquina continuam verdadeiras sem ele, e a tela diz em voz alta que os
    endereços não puderam ser lidos. Esconder o aviso, esse sim, seria mentira.
    """
    mapa = _mapa_por_endereco()
    return render(
        request,
        "admin/perpetuo.html",
        {
            "admin": request.admin,
            "etapas": etapas_com_portas(mapa),
            "mapa_ausente": mapa is None,
        },
    )
