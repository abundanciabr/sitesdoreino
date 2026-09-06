"""A PORTA da casa das Páginas do aluno, fail-CLOSED (critério AC-05).

**A regra que organiza este arquivo inteiro: reconhecer não é autorizar.**
A `identidade` diz quem é; a `alunos` diz em que categoria está; **quem decide
se a pessoa vê a Prancheta é esta célula**, aqui, e só a matrícula ativa abre.
Não conseguir perguntar nunca vira "então pode entrar"
(`DECISAO-celula-de-identidade.md` §6.2; constituição da célula).

**Esta célula NÃO assina sessão** ([INV-P12]). O cookie recebido é repassado
OPACO à `identidade`; não há `SessionMiddleware`, não há `request.session`, e o
progresso da Prancheta mora no MODELO, por aluno. Duas células assinando o
mesmo cookie produzem um cabo de guerra invisível: abrir a Prancheta deslogaria
do site inteiro, sem erro, sem log e sem alarme (`armadilhas/143`). Guarda:
`tests/test_inv_pages_nao_assina_sessao.py`.

Quatro respostas, e cada uma diz o que aconteceu E o que fazer:

| Quem bate                          | Resposta                          |
|------------------------------------|-----------------------------------|
| sem cookie, ou sessão de visitante | 200, o convite para entrar        |
| entrou, sem matrícula ativa        | 403, e a frase diz que foi isso   |
| entrou, e não deu para conferir    | 503, com `Retry-After`            |
| entrou, com matrícula ativa        | a página, e `request.aluno` posto |

**Por que 503, e não o 403 que a `cursos` usa no mesmo caso.** As duas formas
existem nesta casa, e a diferença é o fato que cada uma descreve: 403 é
*perguntei e a resposta foi não*; 503 é *a parte que responde por isso está
fora do ar*. Aqui os dois casos já estão separados em frases diferentes, então
separá-los também no código do estado custa nada e ganha duas coisas: o
navegador (e qualquer cache no caminho) não guarda uma recusa temporária, e o
alarme de fora enxerga uma indisponibilidade como indisponibilidade. É o mesmo
raciocínio que a porta da `admin` já escreveu para si.

**Isso não contraria "reconhecimento falha ABERTO".** O que aquela lei protege
é a vitrine pública, e ela está isenta desta porta ANTES de qualquer pergunta
de rede: `/estudio/<apelido>` é para um cliente que nunca vai entrar na
plataforma (AC-13). Fechado é o que é do aluno logado, que é o que o AC-05
manda fechar.
"""

from __future__ import annotations

import logging

from django.http import HttpResponse
from django.shortcuts import render

from .clients import (
    AlunosClient,
    AlunosIndisponivel,
    ConfiguracaoAusente,
    IdentidadeClient,
    IdentidadeIndisponivel,
)
from .views import de_fora

logger = logging.getLogger("pages.porta")

# A categoria que a `alunos` devolve para quem tem matrícula ativa
# (`DECISAO-categorias-de-usuario.md`). Escrita aqui como dado desta célula: um
# renomeamento silencioso do outro lado aparece como teste vermelho aqui.
CATEGORIA_ALUNO = "aluno"

# Os únicos caminhos que respondem sem cookie. É `frozenset` e é conferido por
# igualdade EXATA em `tests/test_porta_fail_closed.py`: rota nova não escapa em
# silêncio — ou ela está aqui de propósito, ou a porta a protege.
#
# Compara-se `request.path_info`, NUNCA `request.path`: pela borda pública o
# Traefik não remove o prefixo, e `request.path` chega como `/pages/healthz`
# (`armadilhas/029`, medido ao vivo em duas células). `path_info` é `/healthz`
# nos dois caminhos de entrada, e o guarda disso é
# `tests/test_healthz_script_name.py`, plantado na gênese antes desta porta
# existir.
#
# `/healthz` é rota de MÁQUINA, exigida pelo healthcheck do compose, que não
# tem cookie nenhum para apresentar. Fechá-la mata a sonda, o container nunca
# fica `healthy` e o deploy passa a reprovar.
CAMINHOS_ISENTOS = frozenset({"/healthz"})

#: A PORTA DE MÁQUINA, que tem cadeado PRÓPRIO e mais forte que este.
#:
#: `/interno/` responde a outras células, máquina para máquina, e o que a fecha
#: é o Bearer do par (`apps/core/auth.py`): conjunto de tokens vazio recusa
#: todo mundo, e o guarda é o 401 em TODAS as operações
#: (`tests/test_porta_de_maquina.py`). Uma máquina não tem cookie de navegador
#: para apresentar, então passá-la por esta porta trocaria aquele 401 por uma
#: página HTML de convite com HTTP 200 — afrouxando a porta e quebrando o
#: contrato congelado no mesmo gesto.
PREFIXO_DA_PORTA_DE_MAQUINA = "/interno"

#: A VITRINE PÚBLICA, e ela é a exceção que nenhuma célula vizinha tem.
#:
#: `/estudio/<apelido>` é o link que o aluno manda ao cliente pagante, para
#: alguém que nunca vai entrar na plataforma (plano §4, critério AC-13). Quem
#: decide se ela existe é o aluno, por opt-in, DENTRO da célula, e o `noindex`
#: sai do Django. Uma porta escrita sem esta distinção FECHA a vitrine, e a
#: única prova disso seria o cliente do aluno vendo um pedido de login.
#:
#: O `path_info` chega com `/estudio` por extenso porque o degrau 05 escolheu
#: NÃO remover esse prefixo no Traefik, justamente para que esta porta tivesse
#: como distinguir os dois endereços públicos da casa
#: (`infra/traefik/dynamic/plataforma.yml`, roteador `estudio`).
PREFIXO_PUBLICO_DA_VITRINE = "/estudio"


def _isento(caminho: str) -> bool:
    """O caminho responde sem passar pela porta?

    Prefixo comparado com a barra (ou por igualdade exata), e nunca por
    `startswith("/estudio")` cru: sem isso, uma rota futura chamada
    `/estudiosecreto` herdaria a isenção da vitrine sem ninguém decidir.
    """
    if caminho in CAMINHOS_ISENTOS:
        return True
    for prefixo in (PREFIXO_DA_PORTA_DE_MAQUINA, PREFIXO_PUBLICO_DA_VITRINE):
        if caminho == prefixo or caminho.startswith(prefixo + "/"):
            return True
    return False


class PortaDaCasa:
    """Middleware que decide quem passa. Único ponto de autorização da célula.

    Vem por ÚLTIMO em `MIDDLEWARE`, depois do CSRF: a pergunta "quem é" custa
    uma ida à rede, e não se paga esse preço por uma requisição que as camadas
    de cima já vão recusar.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.identidade = IdentidadeClient()
        self.alunos = AlunosClient()

    def __call__(self, request):
        if _isento(request.path_info):
            return self.get_response(request)

        cookie = request.META.get("HTTP_COOKIE", "")
        if not cookie:
            # Sem cookie nenhum não há o que perguntar, e perguntar custaria
            # uma ida à rede para receber "visitante".
            return self._convite(request)

        try:
            sessao = self.identidade.sessao_completa(cookie)
        except (IdentidadeIndisponivel, ConfiguracaoAusente) as erro:
            logger.warning("porta: não deu para reconhecer a sessão: %s", erro)
            return self._sem_resposta(request)

        if not sessao.get("autenticado"):
            return self._convite(request)

        aluno_id = sessao.get("id")
        email = (sessao.get("email") or "").strip().lower()
        if not aluno_id or not email:
            # Autenticado sem id ou sem e-mail é resposta fora de forma: não dá
            # para identificar o dono do portfólio nem para perguntar à
            # `alunos`. Fecha, e diz que foi a conferência que falhou.
            logger.warning("porta: sessão autenticada sem id ou sem e-mail")
            return self._sem_resposta(request)

        try:
            categoria = self.alunos.categoria_de(email)
        except (AlunosIndisponivel, ConfiguracaoAusente) as erro:
            # FECHA. Não conseguir conferir a matrícula nunca é "pode entrar".
            logger.warning("porta: não deu para conferir a matrícula: %s", erro)
            return self._sem_resposta(request)

        if categoria != CATEGORIA_ALUNO:
            return self._sem_matricula(request)

        # A partir daqui a pessoa está dentro. O que as páginas recebem é o
        # necessário para exibição e o id opaco que é a chave do portfólio dela
        # — nunca o e-mail, que foi usado na pergunta e descartado, e nunca um
        # objeto de permissão: quem decide o que ela pode é cada tela, na hora.
        request.aluno = {
            "id": aluno_id,
            "nome": (sessao.get("nome_exibido") or "").strip(),
        }
        return self.get_response(request)

    # ---------------------------------------------------------------- respostas

    def _convite(self, request) -> HttpResponse:
        """200, e não um erro: uma página que convida a entrar é uma página."""
        return self._recusar(request, "entrar", status=200)

    def _sem_matricula(self, request) -> HttpResponse:
        return self._recusar(request, "sem-matricula", status=403)

    def _sem_resposta(self, request) -> HttpResponse:
        resposta = self._recusar(request, "sem-resposta", status=503)
        # Diz ao navegador (e a qualquer cache no caminho) que isto é
        # temporário: 503 sem estas duas linhas pode ser guardado, e o aluno
        # continuaria vendo a recusa depois de a plataforma voltar.
        resposta["Retry-After"] = "30"
        resposta["Cache-Control"] = "no-store"
        return resposta

    @staticmethod
    def _recusar(request, motivo: str, *, status: int) -> HttpResponse:
        return render(
            request,
            "pages/porta.html",
            {"motivo": motivo, **de_fora()},
            status=status,
        )
