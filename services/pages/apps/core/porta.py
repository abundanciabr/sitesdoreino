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

Cinco respostas, e cada uma diz o que aconteceu E o que fazer:

| Quem bate                            | Resposta                            |
|--------------------------------------|-------------------------------------|
| sem cookie, ou sessão de visitante   | 200, o convite para entrar          |
| entrou, sem matrícula ativa          | 403, e a frase diz que foi isso     |
| entrou, e não deu para conferir      | 503, com `Retry-After`              |
| entrou, com matrícula ativa          | a página, e `request.aluno` posto   |
| entrou, na fila da equipe, fora dela | 403, e a frase diz que foi isso     |

A última linha é a área da equipe (`PREFIXO_DA_FILA_DA_EQUIPE`), que troca a
pergunta da matrícula por outra: **esta pessoa é administradora da escola?**,
feita à `admin` pelo contrato congelado. Quem confere o portfólio de um aluno
não é aluno. Ela passa por esta porta como todo o resto, e a página dela recebe
`request.membro_da_equipe` no lugar de `request.aluno`.

**E o 503 vale para as DUAS perguntas de permissão desta porta.** Não conseguir
falar com a `admin` fecha a fila com 503, nunca com 403 e nunca com "então pode
entrar", pela mesma razão escrita abaixo: 403 diria a um professor de verdade
uma frase falsa sobre ele, e o mandaria pedir uma promoção que ele já tem.

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
    AdminIndisponivel,
    AlunosClient,
    AlunosIndisponivel,
    ConfiguracaoAusente,
    IdentidadeClient,
    IdentidadeIndisponivel,
)
from .equipe import e_da_equipe
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

#: A FILA DA EQUIPE, e ela NÃO é isenta: é a mesma porta, com outra pergunta.
#:
#: Quem confere o portfólio de um aluno é um monitor ou um professor da escola,
#: e essa pessoa **não tem matrícula ativa** (critério AC-11, degrau 11). Passar
#: esta área pela pergunta da matrícula fecharia a fila justamente para quem ela
#: existe para atender, e a única prova disso seria a equipe olhando um 403.
#:
#: Então o caminho continua atrás da porta e troca de régua: a `identidade`
#: continua dizendo QUEM é a pessoa, e quem diz se ela pode conferir é a `admin`
#: (`apps/core/equipe.py`), fail-CLOSED. Uma isenção aqui seria pior de duas
#: formas: a fila abriria para qualquer visitante, e a decisão de quem entra
#: sairia da porta para dentro de uma view.
PREFIXO_DA_FILA_DA_EQUIPE = "/equipe"


def _sob(caminho: str, prefixo: str) -> bool:
    """O caminho é o prefixo, ou está debaixo dele?

    A barra entra na comparação, e nunca um `startswith` cru: sem ela, uma rota
    futura chamada `/estudiosecreto` herdaria a isenção da vitrine sem ninguém
    decidir. Escrita uma vez e usada pelas três áreas especiais desta porta,
    porque a mesma regra em duas expressões é a que diverge na terceira cópia.
    """
    return caminho == prefixo or caminho.startswith(prefixo + "/")


def _isento(caminho: str) -> bool:
    """O caminho responde sem passar pela porta?"""
    if caminho in CAMINHOS_ISENTOS:
        return True
    return any(
        _sob(caminho, prefixo)
        for prefixo in (PREFIXO_DA_PORTA_DE_MAQUINA, PREFIXO_PUBLICO_DA_VITRINE)
    )


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

        # Até aqui só sabemos QUEM é. Se ela é aluna desta escola ou monitora
        # dela é a pergunta seguinte, e ela muda conforme a área.
        pessoa_id = sessao.get("id")
        nome = (sessao.get("nome_exibido") or "").strip()
        # O e-mail é lido UMA vez, aqui, e serve às duas perguntas de permissão
        # desta porta: a matrícula, à `alunos`, e a conferência do portfólio, à
        # `admin`. Ele morre nelas: nada desta casa o guarda nem o exibe.
        email = (sessao.get("email") or "").strip().lower()

        if _sob(request.path_info, PREFIXO_DA_FILA_DA_EQUIPE):
            # A FILA DA EQUIPE não pergunta matrícula: quem confere o portfólio
            # de um aluno não é aluno. Quem abre é a `admin`, perguntada por
            # e-mail (`apps/core/equipe.py`).
            if not pessoa_id or not email:
                logger.warning("porta: sessão autenticada sem id ou sem e-mail")
                return self._sem_resposta(request)
            try:
                confere_portfolio = e_da_equipe(email)
            except (AdminIndisponivel, ConfiguracaoAusente) as erro:
                # FECHA, e com 503. Não conseguir perguntar nunca é "pode
                # entrar", e também não é o 403 que fala sobre a pessoa.
                logger.warning(
                    "porta: não deu para perguntar quem confere o portfólio: %s", erro
                )
                return self._sem_resposta(request)
            if not confere_portfolio:
                return self._nao_e_da_equipe(request)
            # O id, e nunca o e-mail, é o que fica na resposta e na assinatura
            # da conferência: é ele que a fila grava em `respondido_por`.
            request.membro_da_equipe = {"id": pessoa_id, "nome": nome}
            return self.get_response(request)

        aluno_id = pessoa_id
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
        request.aluno = {"id": aluno_id, "nome": nome}
        return self.get_response(request)

    # ---------------------------------------------------------------- respostas

    def _convite(self, request) -> HttpResponse:
        """200, e não um erro: uma página que convida a entrar é uma página."""
        return self._recusar(request, "entrar", status=200)

    def _sem_matricula(self, request) -> HttpResponse:
        return self._recusar(request, "sem-matricula", status=403)

    def _nao_e_da_equipe(self, request) -> HttpResponse:
        """403 com frase, e não tela vazia.

        Uma tela vazia diria "não há nada aqui" a quem deveria ver a fila, e um
        professor passaria a tarde achando que a escola não tem pedidos. O 403
        diz o que é: a área existe, e a `admin` respondeu que esta pessoa não é
        administradora da escola.

        **Só chega aqui quem RECEBEU a resposta.** Quem não conseguiu perguntar
        sai pelo 503 logo acima, porque as duas frases são diferentes e mandam a
        pessoa fazer coisas diferentes.
        """
        return self._recusar(request, "nao-e-da-equipe", status=403)

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
