"""O cartaz que pergunta se a pessoa quer o aviso na tela do celular.

Processador de contexto, e não `{% include %}` escrito em cada template, pelo
mesmo motivo do rodapé (`apps/core/rodape.py`): "em todas as páginas" não pode
depender de alguém lembrar de incluir a peça. Página nova nasce com o cartaz.

**Ele devolve vazio na maior parte das visitas, e isso é o desenho.** Quatro
condições, todas necessárias:

1. **site registrado no i18n** — o app é do site da escola; os domínios
   monolíngues seguem byte a byte como estavam (o golden da fase 1);
2. **tem gente entrando** — um aviso é de alguém. Sem `request.ator`, não há a
   quem endereçar, e pedir permissão a um visitante anônimo gastaria a única
   chance que o navegador dá;
3. **a chave pública do push está configurada** — sem ela o navegador não tem
   como se inscrever, e mostrar o botão seria prometer o que não funciona.
   Fail-CLOSED, ao contrário do sino: aqui o silêncio é o certo;
4. o resto (é celular? já está instalado? já respondeu antes?) só o aparelho
   sabe, e quem decide é `static/funil/avisos.js`.

A chave PÚBLICA no HTML não é vazamento: ela existe para ser lida pelo
navegador de quem se inscreve. A privada mora na célula `notificacoes`, e
nunca sai de lá.
"""

import os

from apps.i18n.idiomas import caminho_publico


def chave_publica_do_push() -> str:
    """Lida NO PONTO DE USO, com `.get()`, nunca no import.

    Mesma razão do `_configuracao` dos clientes: falta de variável é mais
    provável que falha de rede (basta uma linha não colada no servidor), e uma
    leitura no import transformaria isso em célula que não sobe.
    """
    return (os.environ.get("VAPID_PUBLIC_KEY") or "").strip()


def avisos_do_contexto(request) -> dict:
    if getattr(request, "idioma", None) is None:
        return {}
    # `getattr` nos DOIS níveis: o `ator` desta célula é preguiçoso e tem
    # formas diferentes conforme quem monta a requisição (há teste com um ator
    # dublado que só carrega o nome). Um `.id` cru aqui derrubaria a página de
    # quem entrou por causa de um atributo ausente — e esta peça é enfeite:
    # nada nela vale uma exceção no caminho de renderizar o site.
    ator = getattr(request, "ator", None)
    if not ator or not getattr(ator, "id", None):
        return {}
    chave = chave_publica_do_push()
    if not chave:
        return {}
    cfg = getattr(request, "i18n", None)
    if cfg is None:
        return {}
    return {
        "avisos_no_celular": {
            "chave": chave,
            # Os dois endereços saem do `caminho_publico`, como toda URL desta
            # célula: no idioma padrão a página mora na raiz nua, e escrever
            # `/{idioma}/avisos/ligar` à mão daria 404 justamente para quem lê
            # em inglês (D1 revisto, 25/08/2026).
            "ligar": caminho_publico(cfg, request.idioma, "/avisos/ligar"),
            "desligar": caminho_publico(cfg, request.idioma, "/avisos/desligar"),
        }
    }
