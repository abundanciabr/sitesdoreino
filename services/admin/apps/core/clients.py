# apps/core/clients.py  # [RECEITA:R2 v1]
# Fala SÓ o que está no contrato congelado da identidade
# (`contracts/identidade.openapi.yaml`). Nunca lê o banco dela (Lei 3).
import datetime as dt
import logging
import os
import time
from urllib.parse import quote

import httpx

from . import medidor

logger = logging.getLogger("admin.porta")

_cliente: httpx.Client | None = None


def http() -> httpx.Client:
    """Um `httpx.Client` por processo, em vez de `httpx.get()` a cada chamada.

    A forma direta constrói um `Client` descartável — e com ele um
    `ssl.SSLContext` novo, que recarrega os certificados raiz do sistema — a
    cada chamada de rede interna (`armadilhas/082`, medido em 0,4s por
    chamada). `httpx.Client` é seguro entre threads, que é o que o uvicorn
    precisa.
    """
    global _cliente
    if _cliente is None:
        _cliente = httpx.Client()
    return _cliente


def _anota(registrar, *args) -> None:
    """Medir JAMAIS derruba esta chamada. Nem por defeito, nem por assinatura.

    O `try` de dentro do medidor cobre um erro no corpo dele. Não cobre a
    chamada em si: se um dia alguém acrescentar um parâmetro obrigatório lá, a
    chamada estoura ANTES de entrar na função, e um TypeError sobe pelo
    middleware — transformando um 302 para o login num 500. Numa área
    fail-closed isso é o mantenedor trancado para fora das próprias ferramentas
    por causa de um contador.

    Por isso a fronteira é guardada AQUI, no lado que sofre a consequência.
    Provado em `tests/test_medidor.py::test_medidor_quebrado_nao_muda_a_porta`,
    que substitui o medidor por um que explode e exige a mesma resposta.
    """
    try:
        registrar(*args)
    except Exception:  # noqa: BLE001 — observar não pode derrubar quem decide
        logger.warning("porta: a medição falhou e foi ignorada", exc_info=True)


class IdentidadeIndisponivel(Exception):
    """Não deu para perguntar quem é a pessoa.

    Existe como exceção NOMEADA, e não como `None`, porque nesta célula as
    duas situações levam a respostas diferentes e a confusão entre elas é
    exatamente o modo de falha que a lei proíbe:

    - **"não há sessão"** ⇒ 302 para o login (a pessoa pode entrar e voltar);
    - **"não consegui perguntar"** ⇒ 503 (não adianta mandar para um login que
      provavelmente também está fora do ar — `DECISAO-celula-admin` §2).

    O `funil` funde as duas em `None` de propósito, e está certo: lá a resposta
    decide um nome no canto da tela (fail-OPEN). Aqui ela decide ACESSO, e
    `reconhecer não é autorizar` corta para o outro lado.
    """


class IdentidadeClient:
    """contracts/identidade.openapi.yaml — `getSessionFull` (leitura, quem
    entrou) e, desde `DECISAO-login-por-senha.md`, `resetPassword` (escrita,
    o reset manual de senha). Estilos DIFERENTES por desenho, não por
    inconsistência: `sessao_completa` decide ACESSO a esta área inteira e
    levanta em qualquer falha (fail-CLOSED); `resetar_senha` é uma ação de
    UMA tela, sempre auditada — quem chama precisa do desfecho aconteça o
    que acontecer, então ela segue o padrão `(desfecho, detalhe, ...)` que
    `AlunosClient.decidir` já usa neste mesmo arquivo, nunca levanta."""

    # Curto de propósito: isto está no caminho de alguém esperando uma página
    # abrir. A diferença para o `funil` (que também usa 2s) não é o número —
    # é o que acontece quando estoura: lá, "Entrar"; aqui, 503.
    TIMEOUT = 2.0

    def _configuracao(self) -> "tuple[str, str] | None":
        """Endereço e token do par, ou `None` se o env não os tiver.

        Lido NO PONTO DE USO, com `.get()` — nunca `os.environ[...]` no
        `__init__` (`armadilhas/097`). `KeyError` não é `httpx.HTTPError`:
        atravessaria intacto o `try` abaixo e o middleware, virando HTTP 500
        em vez do 503 nomeado — e falha de configuração é MAIS provável que
        falha de rede (basta uma variável não colada no servidor).
        """
        base = (os.environ.get("IDENTIDADE_API_URL") or "").strip().rstrip("/")
        token = (os.environ.get("IDENTIDADE_API_TOKEN") or "").strip()
        return (base, token) if base and token else None

    def sessao_completa(self, cookie: str) -> dict:
        """Quem é a pessoa desta requisição, COM e-mail.

        Devolve o corpo de `SessionFull`. **Levanta `IdentidadeIndisponivel`
        em qualquer falha** — rede, configuração, status inesperado, corpo
        fora do contrato. Nada aqui devolve "visitante" por omissão: quem
        decide o que fazer com a indisponibilidade é o middleware, e ele
        fecha.

        Usa `/sessao/completa` (e não `/sessao`) porque a autorização desta
        célula é por LISTA DE E-MAILS — o par está registrado em
        `TOKENS_COMPLETOS_ADMIN`, com o porquê escrito em
        `DECISAO-celula-de-identidade.md` §4.
        """
        config = self._configuracao()
        if config is None:
            # ERROR nomeando as variáveis: quem vai ler este log é o mantenedor.
            logger.error(
                "porta: IDENTIDADE_API_URL/IDENTIDADE_API_TOKEN ausentes no env "
                "desta célula — a área administrativa está fechada para todos"
            )
            _anota(medidor.registrar_chamada, "sem_configuracao", 0.0)
            raise IdentidadeIndisponivel("configuração ausente")
        base, token = config

        # A partir daqui, cada saída ANOTA o próprio desfecho. Os cinco são
        # contadores diferentes de propósito: "estourou o tempo" e "a identidade
        # recusou" chegam idênticos na tela (503 nos dois casos), e foi essa
        # indistinção que fez o diagnóstico de 27/08/2026 levar um dia inteiro.
        # Anotar é tudo o que acontece aqui — nenhuma decisão muda.
        comeco = time.perf_counter()
        try:
            r = http().get(
                f"{base}/sessao/completa",
                headers={"Authorization": f"Bearer {token}", "Cookie": cookie},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            _anota(
                medidor.registrar_chamada,
                "estourou_o_tempo",
                (time.perf_counter() - comeco) * 1000,
            )
            logger.error("porta: não deu para perguntar à identidade: %s", erro)
            raise IdentidadeIndisponivel(str(erro)) from erro

        decorrido_ms = (time.perf_counter() - comeco) * 1000

        if r.status_code != 200:
            # 403 aqui significa que o par não está em TOKENS_COMPLETOS_ADMIN —
            # o modo de falha que o script de provisionamento confere, porque
            # de dentro ele é indistinguível de "você não está na lista".
            logger.error("porta: a identidade respondeu HTTP %s", r.status_code)
            _anota(medidor.registrar_chamada, "recusou", decorrido_ms)
            raise IdentidadeIndisponivel(f"HTTP {r.status_code}")

        try:
            corpo = r.json()
        except ValueError as erro:
            # 200 com corpo que não é JSON: proxy interposto, resposta
            # truncada. `json.JSONDecodeError` é `ValueError`, NÃO é
            # `httpx.HTTPError` — sem este `except` ela viraria 500.
            # *Status 2xx não é sucesso* (RETROSPECTIVA §4).
            logger.error("porta: a identidade respondeu fora do contrato: %s", erro)
            _anota(medidor.registrar_chamada, "fora_do_contrato", decorrido_ms)
            raise IdentidadeIndisponivel("corpo fora do contrato") from erro

        if not isinstance(corpo, dict):
            logger.error("porta: a identidade respondeu um corpo que não é objeto")
            _anota(medidor.registrar_chamada, "fora_do_contrato", decorrido_ms)
            raise IdentidadeIndisponivel("corpo fora do contrato")

        _anota(medidor.registrar_chamada, "respondeu", decorrido_ms)
        return corpo

    # ------------------------------------------------------------------ escrita
    #
    # O reset manual (DECISAO-login-por-senha.md §1.4, §4): o mantenedor
    # confirma quem é a pessoa pelo WhatsApp que ela já deixou no cadastro,
    # aciona esta porta, e repassa a senha nova por fora. Exige o grau
    # TOKENS_SENHA_ADMIN, além do par aceito.

    #: A `identidade` gerou a senha nova e a devolveu.
    OK = "ok"
    #: A `identidade` respondeu e RECUSOU — 404, nenhuma Identidade com este
    #: e-mail (a pessoa nunca entrou nem pelo Google nem por senha, então não
    #: há o que resetar).
    RECUSADO = "recusado"
    #: Não deu para saber — rede, configuração ausente, 5xx, corpo fora do
    #: contrato. Nome próprio pelo mesmo motivo de `AlunosClient.NAO_RESPONDEU`:
    #: "não deu certo" quando pode ter dado faria o mantenedor tentar de novo
    #: sem necessidade.
    NAO_RESPONDEU = "nao_respondeu"

    def resetar_senha(self, email: str) -> "tuple[str, str, str]":
        """Devolve `(desfecho, detalhe, senha_nova)`. `senha_nova` só vem
        preenchida em `OK` — nos outros dois é `""`. **Nunca levanta**: quem
        chama grava a linha de auditoria aconteça o que acontecer, e a
        senha NUNCA entra nela (só a tela mostra, uma vez)."""
        config = self._configuracao()
        if config is None:
            return (
                self.NAO_RESPONDEU,
                "o par de tokens com a identidade não está ligado",
                "",
            )
        base, token = config

        try:
            r = http().post(
                f"{base}/pessoas/resetar-senha",
                json={"email": email},
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("resetar senha: não deu para falar com a identidade: %s", erro)
            return self.NAO_RESPONDEU, "a identidade não respondeu", ""

        if r.status_code == 404:
            return (
                self.RECUSADO,
                "esta pessoa ainda não tem conta nenhuma para resetar",
                "",
            )
        if r.status_code != 200:
            logger.error("resetar senha: a identidade respondeu HTTP %s", r.status_code)
            return self.NAO_RESPONDEU, "a identidade respondeu com erro", ""

        try:
            corpo = r.json()
        except ValueError as erro:
            logger.error("resetar senha: resposta fora do contrato: %s", erro)
            return self.NAO_RESPONDEU, "a identidade respondeu fora do contrato", ""

        senha_nova = corpo.get("senha_nova") if isinstance(corpo, dict) else None
        if not senha_nova:
            logger.error("resetar senha: resposta sem senha_nova")
            return self.NAO_RESPONDEU, "a identidade não devolveu a senha nova", ""
        return self.OK, "", senha_nova

    # ------------------------------------------------------------ leitura de tela
    #
    # `pessoa_por_id` serve a UMA tela (o quadro de pontos, `escola_pontos.py`),
    # não a porta de entrada desta área — por isso **fail-OPEN**, ao contrário de
    # `sessao_completa`: a diferença não é gosto, é a mesma do `AlunosClient`
    # logo abaixo. Aquele método decide ACESSO (quem entra); este decide o que
    # UMA LINHA de uma lista mostra, dentro de uma área em que a pessoa já
    # entrou. `findPersonById` exige o MESMO grau `TOKENS_COMPLETOS_ADMIN` que
    # `getSessionFull` já usa — o par que fala com a identidade já está elevado.

    def pessoa_por_id(self, pessoa_id: str) -> "str | None":
        """O e-mail de um id opaco de plataforma, ou `None`.

        `None` cobre DOIS casos que esta chamada colapsa de propósito: "a
        identidade não respondeu" e "este id não tem e-mail" (`email: null` é
        RESPOSTA no contrato, não erro). Quem chama (`escola_pontos.py`) trata
        os dois do mesmo jeito — pula a linha —, e distinguir os dois exigiria
        um terceiro estado que ninguém consome ainda.
        """
        config = self._configuracao()
        if config is None:
            return None
        base, token = config

        try:
            r = http().post(
                f"{base}/pessoas/por-id",
                json={"id": pessoa_id},
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error(
                "quadro: não deu para perguntar o e-mail à identidade: %s", erro
            )
            return None
        if r.status_code != 200:
            logger.error("quadro: a identidade respondeu HTTP %s", r.status_code)
            return None
        try:
            corpo = r.json()
        except ValueError as erro:
            logger.error("quadro: resposta da identidade fora do contrato: %s", erro)
            return None
        if not isinstance(corpo, dict):
            return None
        email = corpo.get("email")
        return email if isinstance(email, str) and email else None


class AlunosClient:
    """`contracts/alunos.openapi.yaml` — a fila de liberação (somente leitura).

    **Fail-OPEN, e é o inverso do `IdentidadeClient` deste mesmo arquivo.** A
    diferença não é gosto: aquele decide ACESSO (quem entra na área), e por
    isso qualquer dúvida fecha. Este decide o que UMA TELA mostra, dentro de
    uma área em que a pessoa já entrou — e uma tela que não abre porque uma
    célula vizinha caiu é o oposto do que a área administrativa serve para
    fazer (`PLANO-AREA-ADMIN.md` §5: fail-open por tile, com orçamento de
    tempo).

    Por isso os métodos aqui devolvem `None` em vez de levantar: `None` é
    *"não consegui perguntar"*, e a tela diz isso com todas as letras — nunca
    lista vazia, que se leria como *"não há ninguém esperando"*.
    """

    # Mesmo orçamento do `IdentidadeClient`, e pelo mesmo motivo: alguém está
    # esperando uma página abrir. A diferença é o que acontece ao estourar —
    # lá, 503; aqui, um aviso no lugar da lista.
    TIMEOUT = 2.0

    def _configuracao(self) -> "tuple[str, str] | None":
        """Endereço e token do par, ou `None` se o env não os tiver.

        Lido NO PONTO DE USO, com `.get()` — `armadilhas/097`. Enquanto o
        mantenedor não rodar `infra/provisionar-pares-de-categorias.sh`, estas
        duas variáveis simplesmente não existem, e este é o caminho normal por
        onde a célula passa: sem elas a área abre igual, e só a lista da fila
        diz que ainda não consegue perguntar.
        """
        base = (os.environ.get("ALUNOS_API_URL") or "").strip().rstrip("/")
        token = (os.environ.get("ALUNOS_API_TOKEN") or "").strip()
        return (base, token) if base and token else None

    def _buscar(self, caminho: str, params: dict) -> "list[dict] | None":
        """Uma leitura de lista, com o mesmo fail-OPEN das duas que a usam.

        Existe porque `fila()` e `alunos()` diferem em UMA linha (o caminho), e
        duas cópias do mesmo tratamento de erro divergem no primeiro caso de
        borda que alguém corrige só de um lado.
        """
        config = self._configuracao()
        if config is None:
            logger.info(
                "leitura: ALUNOS_API_URL/ALUNOS_API_TOKEN ainda não estão no env "
                "desta célula — a tela vai dizer que não consegue perguntar. "
                "Rode infra/provisionar-pares-de-categorias.sh."
            )
            return None
        base, token = config

        try:
            r = http().get(
                f"{base}{caminho}",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("leitura %s: não deu para perguntar: %s", caminho, erro)
            return None

        if r.status_code != 200:
            # 401 aqui significa que o par não está em `TOKENS_ACEITOS_ADMIN` do
            # lado da `alunos` — de fora, indistinguível de "não há ninguém".
            logger.error(
                "leitura %s: a alunos respondeu HTTP %s", caminho, r.status_code
            )
            return None

        try:
            corpo = r.json()
        except ValueError as erro:
            # *Status 2xx não é sucesso* (RETROSPECTIVA §4).
            logger.error("leitura %s: resposta fora do contrato: %s", caminho, erro)
            return None

        if not isinstance(corpo, list):
            logger.error(
                "leitura %s: a alunos respondeu um corpo que não é lista", caminho
            )
            return None
        return corpo

    def fila(self, status: str) -> "list[dict] | None":
        """Quem está na fila, de TODAS as escolas (`site_id` omitido de propósito).

        Devolve a lista, ou `None` quando não deu para perguntar. **Nunca
        levanta** — quem chama é uma view, e a página tem de abrir.

        `site_id` fica de fora porque o painel do dono é plataforma-inteira
        (Lei 9), e cada linha já diz de qual escola veio
        (`DECISAO-categorias-de-usuario`).
        """
        return self._buscar("/pre-matriculas", {"status": status})

    def prontuario(self, email: str) -> "dict | None":
        """[PRONTUARIO] A história de UMA pessoa — todas as passagens dela.

        Mesmo fail-OPEN das listas acima: `None` é *"não consegui perguntar"*, e
        a tela diz isso com todas as letras. Nunca levanta.

        Não passa pelo `_buscar` porque aquele exige LISTA, e esta porta
        devolve um objeto — afrouxar a conferência de lá para caber os dois
        tiraria de `fila()` e `alunos()` a garantia que elas têm hoje: se a
        `alunos` responder um objeto onde a tela espera lista, o `for` do
        template iteraria as CHAVES do dicionário em silêncio.
        """
        config = self._configuracao()
        if config is None:
            logger.info(
                "prontuario: ALUNOS_API_URL/ALUNOS_API_TOKEN ainda não estão no "
                "env desta célula — a tela vai dizer que não consegue perguntar."
            )
            return None
        base, token = config

        try:
            r = http().get(
                # `email` vai no caminho, e o `quote` não é enfeite: um "+" num
                # endereço (`fulano+curso@exemplo.com`) vira espaço sem ele, e a
                # tela mostraria o prontuário vazio de uma pessoa que existe.
                f"{base}/alunos/{quote(email, safe='')}/prontuario",
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("prontuario: não deu para perguntar: %s", erro)
            return None

        if r.status_code != 200:
            logger.error("prontuario: a alunos respondeu HTTP %s", r.status_code)
            return None

        try:
            corpo = r.json()
        except ValueError as erro:
            # *Status 2xx não é sucesso* (RETROSPECTIVA §4).
            logger.error("prontuario: resposta fora do contrato: %s", erro)
            return None

        if not isinstance(corpo, dict) or not isinstance(corpo.get("passagens"), list):
            logger.error("prontuario: a alunos respondeu um corpo fora da forma")
            return None
        return corpo

    # ------------------------------------------------------------------ escrita
    #
    # A ÚNICA escrita que esta célula faz em outra (`DECISAO-fila-de-liberacao`
    # §8, fase 2). Ela não é fail-open como as leituras acima, e não é
    # fail-closed como a porta: ela é **fail-CONTADO**. Uma decisão que não
    # chegou não pode ser mostrada como feita, e também não pode sumir — quem
    # chama grava o desfecho na auditoria, seja qual for.

    #: A decisão chegou e a `alunos` a aplicou.
    OK = "ok"
    #: A `alunos` respondeu e RECUSOU — 404 (linha não existe), 409 (já
    #: decidida) ou 422 (payload inválido). É resposta, não falha: a decisão
    #: não valeu, e o motivo é conhecido.
    RECUSADO = "recusado"
    #: Não deu para saber. Rede, configuração ausente, 5xx, corpo fora do
    #: contrato. **Pode ter sido aplicada do outro lado** — é por isso que este
    #: desfecho tem nome próprio em vez de virar "recusado": dizer ao
    #: mantenedor "não deu certo" quando pode ter dado é como ele acaba
    #: decidindo duas vezes sobre a mesma pessoa.
    NAO_RESPONDEU = "nao_respondeu"

    def decidir(
        self, alvo: str, decisao: str, decidido_por: str, motivo: str = ""
    ) -> "tuple[str, str]":
        """Libera ou recusa quem está na fila. Devolve `(desfecho, detalhe)`.

        `detalhe` é curto e para HUMANO — vai para a auditoria e para a tela.
        **Nunca levanta**: quem chama precisa gravar a linha de auditoria
        aconteça o que acontecer.
        """
        config = self._configuracao()
        if config is None:
            return self.NAO_RESPONDEU, "o par de tokens com a alunos não está ligado"
        base, token = config

        corpo = {"decisao": decisao, "decidido_por": decidido_por}
        if motivo:
            corpo["motivo"] = motivo

        try:
            r = http().post(
                f"{base}/pre-matriculas/{alvo}/decisao",
                json=corpo,
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("decisao: não deu para falar com a alunos: %s", erro)
            return self.NAO_RESPONDEU, "a parte que guarda os alunos não respondeu"

        if r.status_code == 200:
            return self.OK, ""
        if r.status_code == 404:
            return self.RECUSADO, "este pedido não existe mais"
        if r.status_code == 409:
            # O caso REAL de duas abas abertas, e o mais provável dos três.
            return self.RECUSADO, "este pedido já tinha sido decidido"
        if r.status_code == 422:
            return self.RECUSADO, "faltou o motivo da recusa"
        logger.error("decisao: a alunos respondeu HTTP %s", r.status_code)
        return self.NAO_RESPONDEU, "a parte que guarda os alunos respondeu com erro"

    def apagar_recusado(self, alvo: str) -> "tuple[str, str]":
        """[APAGAR-RECUSADO] Apaga de vez um pedido recusado. Devolve `(desfecho, detalhe)`.

        `docs/decisoes/DECISAO-apagar-recusado-definitivamente.md` (03/09/2026).
        Mesma disciplina fail-CONTADO de `decidir`: **nunca levanta**, e
        `NAO_RESPONDEU` continua significando *"pode ter sido aplicado do outro
        lado"* — um apagar que a rede não confirmou pode ter apagado mesmo
        assim, e chamar isso de "não valeu" faria o mantenedor tentar de novo
        sobre uma linha que já não existe.

        IRREVERSÍVEL do lado da `alunos`: ao contrário de `decidir`, não há
        dado nenhum para reler depois — a linha deixa de existir.
        """
        config = self._configuracao()
        if config is None:
            return self.NAO_RESPONDEU, "o par de tokens com a alunos não está ligado"
        base, token = config

        try:
            r = http().delete(
                f"{base}/pre-matriculas/{alvo}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("apagar-recusado: não deu para falar com a alunos: %s", erro)
            return self.NAO_RESPONDEU, "a parte que guarda os alunos não respondeu"

        if r.status_code == 200:
            return self.OK, ""
        if r.status_code == 404:
            return self.RECUSADO, "este pedido não está mais entre os recusados"
        if r.status_code == 409:
            return self.RECUSADO, "esta pessoa deixou de estar recusada"
        logger.error("apagar-recusado: a alunos respondeu HTTP %s", r.status_code)
        return self.NAO_RESPONDEU, "a parte que guarda os alunos respondeu com erro"

    def criar_na_fila(self, dados: dict) -> "tuple[str, str, str]":
        """[A MAO] Poe uma pessoa na fila em nome do mantenedor.

        Devolve `(desfecho, detalhe, id_da_linha)` — o id e `""` quando nao
        houve linha. Mesma disciplina de `decidir`: **nunca levanta**, e
        `NAO_RESPONDEU` continua significando *"pode ter sido aplicado do outro
        lado"*.

        E a MESMA porta que o formulario do site usa (`POST /pre-matriculas`),
        de proposito. Uma porta so para o mantenedor criar matricula direto
        seria uma segunda forma de virar aluno, com outras regras — e as duas
        discordariam na primeira mudanca (`DECISAO-cadastrar-alguem-a-mao.md`
        §2). Aqui ele faz o mesmo caminho de todo mundo, so que depressa.

        O `200` (ja estava na fila, dados atualizados) e desfecho de SUCESSO:
        significa que a pessoa esta na fila com os dados de agora, que e
        exatamente o que quem preencheu o formulario queria.
        """
        config = self._configuracao()
        if config is None:
            return (
                self.NAO_RESPONDEU,
                "o par de tokens com a alunos não está ligado",
                "",
            )
        base, token = config

        try:
            r = http().post(
                f"{base}/pre-matriculas",
                json=dados,
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("cadastrar: não deu para falar com a alunos: %s", erro)
            return self.NAO_RESPONDEU, "a parte que guarda os alunos não respondeu", ""

        if r.status_code in (200, 201):
            try:
                corpo = r.json()
            except ValueError as erro:
                # *Status 2xx não é sucesso* (RETROSPECTIVA §4). Sem o id não há
                # como liberar — e chamar isto de OK deixaria a pessoa parada na
                # fila com a tela dizendo que ela já é aluna.
                logger.error("cadastrar: a alunos respondeu fora do contrato: %s", erro)
                return (
                    self.NAO_RESPONDEU,
                    "a parte que guarda os alunos respondeu de um jeito estranho",
                    "",
                )
            id_da_linha = str((corpo or {}).get("id") or "")
            if not id_da_linha:
                return (
                    self.NAO_RESPONDEU,
                    "a parte que guarda os alunos não disse qual linha criou",
                    "",
                )
            return self.OK, "", id_da_linha
        if r.status_code == 409:
            return (
                self.RECUSADO,
                "esta pessoa já é aluna — procure por ela na lista",
                "",
            )
        if r.status_code == 422:
            return (
                self.RECUSADO,
                "algum campo veio errado para a parte que guarda os alunos",
                "",
            )
        logger.error("cadastrar: a alunos respondeu HTTP %s", r.status_code)
        return self.NAO_RESPONDEU, "a parte que guarda os alunos respondeu com erro", ""

    def alunos(self, status: str = None) -> "list[dict] | None":
        """[GESTAO] Quem já é aluno, de TODAS as escolas. `None` = não perguntei.

        Mesma disciplina da `fila()` acima: fail-OPEN, nunca levanta, e `None`
        é *"não consegui perguntar"* — jamais lista vazia, que a tela leria
        como "não há nenhum aluno".
        """
        return self._buscar("/matriculas", {"status": status} if status else {})

    def atualizar_aluno(
        self, alvo: str, mudancas: dict, decidido_por: str
    ) -> "tuple[str, str]":
        """[GESTAO] Muda o estado de um aluno, ou corrige os dados dele.

        Devolve `(desfecho, detalhe)`, com os MESMOS três desfechos da decisão
        da fila — e pelo mesmo motivo: quem chama grava a linha de auditoria
        aconteça o que acontecer, e "não respondeu" não pode virar "recusado"
        (a mudança pode ter sido aplicada do outro lado).
        """
        config = self._configuracao()
        if config is None:
            return self.NAO_RESPONDEU, "o par de tokens com a alunos não está ligado"
        base, token = config

        try:
            r = http().patch(
                f"{base}/matriculas/{alvo}",
                json={**mudancas, "decidido_por": decidido_por},
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("gestao: não deu para falar com a alunos: %s", erro)
            return self.NAO_RESPONDEU, "a parte que guarda os alunos não respondeu"

        if r.status_code == 200:
            return self.OK, ""
        if r.status_code == 404:
            return self.RECUSADO, "este aluno não existe mais"
        if r.status_code == 409:
            return self.RECUSADO, "esta pessoa ainda está na fila — decida por lá"
        if r.status_code == 422:
            return self.RECUSADO, "não havia nada para mudar, ou um campo veio errado"
        logger.error("gestao: a alunos respondeu HTTP %s", r.status_code)
        return self.NAO_RESPONDEU, "a parte que guarda os alunos respondeu com erro"

    # NAO existe metodo para apagar uma ficha, e a ausencia e a lei:
    # `DECISAO-a-ficha-nao-se-apaga.md` (29/08/2026). O metodo que morava aqui
    # chamava `DELETE /matriculas/{id}`, e a porta saiu do contrato da `alunos`
    # no mesmo dia. Tirar o acesso e `atualizar_aluno` com `status="encerrada"`
    # — a ficha fica, e o prontuario a mostra.


class CaixaClient:
    """`contracts/sugestoes.openapi.yaml` — a gestão das ideias dos alunos.

    Lei: `docs/decisoes/DECISAO-a-gestao-da-caixa-mora-no-admin.md`. A gestão
    mudou de casa para `/admin/caixa/` em 28/08/2026 (*"tudo será em /admin"*), e
    pela Lei 3 esta célula não lê o banco da Caixa: ela pergunta.

    **Fail-OPEN na leitura, como a `AlunosClient` — e pelo mesmo motivo.** A
    Caixa fora do ar deixa a tela com um aviso honesto e a página abre igual;
    `None` é *"não consegui perguntar"*, nunca lista vazia, que se leria como
    *"não há ideia nenhuma"*.

    **Na ESCRITA é diferente, e a diferença é deliberada:** ali `None` seria
    mentira perigosa — a pessoa clicou em algo que muda a vida de um aluno. As
    escritas devolvem o par `(desfecho, recado)` como a `AlunosClient.decidir`,
    para a tela poder dizer *o que* aconteceu.
    """

    TIMEOUT = 2.0

    OK = "ok"
    RECUSADO = "recusado"
    NAO_RESPONDEU = "nao_respondeu"

    def _configuracao(self) -> "tuple[str, str] | None":
        """Endereço e token do par, ou `None` — lido NO PONTO DE USO
        (`armadilhas/097`). Enquanto o par não estiver no env, a área abre e só
        a tela da Caixa diz que ainda não consegue perguntar."""
        base = (os.environ.get("SUGESTOES_API_URL") or "").strip().rstrip("/")
        token = (os.environ.get("SUGESTOES_API_TOKEN") or "").strip()
        return (base, token) if base and token else None

    # -- leitura: fail-OPEN --------------------------------------------------

    def ideias(self, por_email: str = "", com_conversa: bool = False) -> "dict | None":
        """O quadro inteiro com os FATOS de cada ideia, ou `None`.

        `por_email` não filtra nada: ele responde uma pergunta só — *esta pessoa
        pode assinar?* — e a resposta vem no campo `pode_assinar`. Quem recusa de
        verdade é a Caixa, na escrita; isto serve para a tela não desenhar um
        botão que já se sabe que vai ser recusado.

        `com_conversa` pede o TEXTO dos comentários de cada ideia (contrato de
        02/09/2026, RITOS §3). Ele é opcional aqui pelo mesmo motivo que é
        opcional lá: a conversa cresce com o uso, e as telas de operação só
        mostram a contagem. Quem pede é a exportação, que existe justamente
        para levar o texto inteiro embora.
        """
        config = self._configuracao()
        if config is None:
            logger.info(
                "caixa: SUGESTOES_API_URL/SUGESTOES_API_TOKEN ainda não estão no "
                "env desta célula — a tela vai dizer que não consegue perguntar."
            )
            return None
        base, token = config
        # Só o que foi PEDIDO viaja na URL: mandar `incluir_conversa=false` para
        # quem não quer a conversa seria descrever o padrão como se fosse
        # escolha, e o padrão já é esse do outro lado.
        params = {}
        if por_email:
            params["por_email"] = por_email
        if com_conversa:
            params["incluir_conversa"] = "true"
        try:
            r = http().get(
                f"{base}/gestao/ideias",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("caixa: não deu para perguntar: %s", erro)
            return None
        if r.status_code != 200:
            logger.error("caixa: a Caixa respondeu HTTP %s", r.status_code)
            return None
        try:
            corpo = r.json()
        except ValueError as erro:
            # 200 com corpo que não é JSON. *Status 2xx não é sucesso*
            # (RETROSPECTIVA §4) — e `JSONDecodeError` não é `httpx.HTTPError`,
            # então sem este `except` viraria 500 na cara de quem abriu a tela.
            logger.error("caixa: resposta fora do contrato: %s", erro)
            return None
        if not isinstance(corpo, dict) or not isinstance(corpo.get("ideias"), list):
            logger.error("caixa: resposta com forma inesperada")
            return None
        return corpo

    def uma_ideia(self, ideia_id: int) -> "dict | None":
        """Uma ideia com a história dela, ou `None` — fail-OPEN como a lista.

        A história só vem por aqui, e nunca na listagem: ela cresce com o uso, e
        na lista multiplicaria a resposta por algo que nenhuma tela de lista
        mostra (é a decisão escrita no contrato, e há guarda dos dois lados).
        """
        config = self._configuracao()
        if config is None:
            logger.info(
                "caixa: SUGESTOES_API_URL/SUGESTOES_API_TOKEN ainda não estão no "
                "env desta célula — a tela vai dizer que não consegue perguntar."
            )
            return None
        base, token = config
        try:
            r = http().get(
                f"{base}/gestao/ideias/{ideia_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("caixa: não deu para perguntar pela ideia: %s", erro)
            return None
        if r.status_code != 200:
            # 404 é resposta legítima ("essa ideia não existe") e não erro de
            # rede, mas para a TELA os dois viram a mesma coisa: não há o que
            # mostrar. Quem distingue é o log, que registra o código.
            logger.error("caixa: a Caixa respondeu HTTP %s pela ideia", r.status_code)
            return None
        try:
            corpo = r.json()
        except ValueError as erro:
            logger.error("caixa: resposta fora do contrato: %s", erro)
            return None
        if not isinstance(corpo, dict) or "id" not in corpo:
            logger.error("caixa: resposta com forma inesperada")
            return None
        return corpo

    # -- escrita: diz o que aconteceu ----------------------------------------

    def previas_de_fusao(self, grupos: list) -> "list | None":
        """Como ficariam estas junções, sem juntar nada. `None` = não perguntei.

        Uma chamada para TODOS os grupos, e não uma por grupo: a tela mostra a
        lista inteira de junções propostas de uma vez, e cinco idas seriam cinco
        vezes o tempo de espera do mantenedor na abertura da página.

        Fail-OPEN como as outras leituras: sem prévia a tela diz que não
        conseguiu perguntar, e não desenha um botão de juntar — confirmar uma
        junção sem ver o resultado é exatamente o que o modal existe para evitar.
        """
        config = self._configuracao()
        if config is None:
            return None
        base, token = config
        try:
            r = http().post(
                f"{base}/gestao/fusoes/previas",
                json={"grupos": grupos},
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
            r.raise_for_status()
            return r.json()["previas"]
        except (httpx.HTTPError, KeyError, ValueError) as erro:
            logger.error("caixa: não deu para pedir as prévias de fusão: %s", erro)
            return None

    def fusoes(self) -> "list | None":
        """As junções em vigor, para a tela poder oferecer o desfazer."""
        config = self._configuracao()
        if config is None:
            return None
        base, token = config
        try:
            r = http().get(
                f"{base}/gestao/fusoes",
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
            r.raise_for_status()
            return r.json()["fusoes"]
        except (httpx.HTTPError, KeyError, ValueError) as erro:
            logger.error("caixa: não deu para listar as junções: %s", erro)
            return None

    def fundir(self, *, canonica: int, absorvidas: list, nota: str, quem: dict):
        """Junta de verdade. Devolve o par `(desfecho, recado)` das escritas."""
        return self._escrever(
            "/gestao/fusoes",
            {"canonica": canonica, "absorvidas": absorvidas, "nota": nota, **quem},
        )

    def desfazer_fusao(self, fusao_id: int, *, quem: dict):
        return self._escrever(f"/gestao/fusoes/{fusao_id}/desfazer", quem)

    def _escrever(self, caminho: str, corpo: dict) -> "tuple[str, str]":
        """Uma escrita, com o tratamento que as três compartilham.

        As três diferem no caminho e no corpo; o que fazer com cada código de
        resposta é idêntico, e duas cópias divergiriam no primeiro caso de borda
        corrigido de um lado só.
        """
        config = self._configuracao()
        if config is None:
            return self.NAO_RESPONDEU, "o par de tokens com a Caixa não está ligado"
        base, token = config
        try:
            r = http().post(
                f"{base}{caminho}",
                json=corpo,
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("caixa: não deu para escrever em %s: %s", caminho, erro)
            return self.NAO_RESPONDEU, "a Caixa não respondeu"

        if r.status_code == 200:
            return self.OK, ""
        if r.status_code in (403, 422):
            # A Caixa recusou com uma frase que ENSINA o caminho. Repassá-la
            # inteira é o ponto: reescrevê-la aqui daria duas redações para a
            # mesma recusa, e a que ninguém testa é a que fica errada.
            try:
                return self.RECUSADO, str(r.json().get("erro", "")).strip()
            except ValueError:
                return self.RECUSADO, "a Caixa recusou, sem dizer o motivo"
        logger.error("caixa: escrita em %s respondeu HTTP %s", caminho, r.status_code)
        return self.NAO_RESPONDEU, "a Caixa respondeu com erro"

    def mudar_status(self, ideia_id: int, *, status: str, nota: str, quem: dict):
        return self._escrever(
            f"/gestao/ideias/{ideia_id}/status",
            {"status": status, "nota": nota, **quem},
        )

    def avaliar(self, ideia_id: int, *, campos: dict, quem: dict):
        return self._escrever(
            f"/gestao/ideias/{ideia_id}/avaliacao", {**campos, **quem}
        )

    def registrar_changespec(self, ideia_id: int, *, campos: dict, quem: dict):
        return self._escrever(
            f"/gestao/ideias/{ideia_id}/changespec", {**campos, **quem}
        )

    def arquivar(self, ideia_id: int, *, motivo: str, quem: dict):
        """`DECISAO-arquivar-ideia.md`: some do aluno, nada se perde no banco."""
        return self._escrever(
            f"/gestao/ideias/{ideia_id}/arquivar", {"motivo": motivo, **quem}
        )

    def desarquivar(self, ideia_id: int, *, quem: dict):
        return self._escrever(f"/gestao/ideias/{ideia_id}/desarquivar", quem)

    def apagar(self, ideia_id: int, *, quem: dict):
        """`DECISAO-apagar-ideia.md`: sem volta, nem para quem criou."""
        return self._escrever(f"/gestao/ideias/{ideia_id}/apagar", quem)

    def corrigir_texto(self, ideia_id: int, *, campos: dict, quem: dict):
        """`DECISAO-corrigir-o-texto-de-uma-ideia.md`: o erro de digitação some.

        `campos` traz os TRÊS textos inteiros (`titulo`, `problema`,
        `solucao_proposta`), como o contrato pede — e não só o que mudou. Quem
        decide o que de fato mudou é a Caixa, comparando com o que está gravado;
        fazer essa conta aqui seria a tela decidindo, com dados de segundos
        atrás, uma coisa que só a dona do dado sabe agora.
        """
        return self._escrever(f"/gestao/ideias/{ideia_id}/texto", {**campos, **quem})


class CatalogoClient:
    """O catálogo, que é onde mora o MENU do topo do site.

    Fala só o que está no contrato congelado (`contracts/catalogo.openapi.yaml`,
    operações `getSiteByHost`, `getSiteMenu` e `putSiteMenu`). Nunca lê o banco
    dele (Lei 3).

    **Fail-OPEN na leitura, e a mensagem é honesta.** O par de tokens
    `admin→catalogo` é um passo do mantenedor na VPS (INV-P8, Lei 5): enquanto
    ele não existir, esta tela abre dizendo o que falta, em português, em vez de
    500. Uma tela de operação que não abre é inútil justamente quando você
    precisa dela.

    As variáveis são lidas no PONTO DE USO, nunca no `__init__`
    (`armadilhas/097`: env ausente no construtor vira HTTP 500 em toda página).
    """

    TIMEOUT = 4.0
    OK = "ok"
    RECUSADO = "recusado"
    NAO_RESPONDEU = "nao_respondeu"

    def _configuracao(self) -> "tuple[str, str] | None":
        base = (os.environ.get("CATALOGO_API_URL") or "").strip().rstrip("/")
        token = (os.environ.get("TOKEN_CATALOGO") or "").strip()
        if not base or not token:
            return None
        return base, token

    def site_por_host(self, host: str) -> "dict | None":
        """O site deste domínio, com o menu dentro. `None` = não deu para saber.

        Host, e não um id guardado aqui: [INV-P11] manda o site sair do domínio
        pelo qual a requisição chegou, e essa é também a resposta certa para o
        multissítio — quem abre `/admin` em outro domínio configura o menu
        daquele site, sem escolher nada numa lista.
        """
        config = self._configuracao()
        if config is None:
            logger.warning(
                "menu: CATALOGO_API_URL/TOKEN_CATALOGO ainda não estão no env "
                "desta célula (par admin→catalogo não provisionado)"
            )
            return None
        base, token = config
        try:
            r = http().get(
                f"{base}/sites/by-host/{quote(host, safe='')}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("menu: o catálogo não respondeu: %s", erro)
            return None
        if r.status_code != 200:
            logger.error("menu: o catálogo respondeu HTTP %s", r.status_code)
            return None
        try:
            corpo = r.json()
        except ValueError as erro:
            logger.error("menu: resposta fora do contrato: %s", erro)
            return None
        if not isinstance(corpo, dict) or "id" not in corpo:
            logger.error("menu: resposta com forma inesperada")
            return None
        return corpo

    def gravar_menu(self, site_id: str, menu: dict) -> "tuple[str, str]":
        """Grava o documento INTEIRO. Devolve (situação, frase para a tela)."""
        config = self._configuracao()
        if config is None:
            return self.NAO_RESPONDEU, "o par de tokens com o catálogo não está ligado"
        base, token = config
        try:
            r = http().put(
                f"{base}/sites/{quote(str(site_id), safe='')}/menu",
                json={"menu": menu},
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("menu: não deu para gravar: %s", erro)
            return self.NAO_RESPONDEU, "o catálogo não respondeu"
        if r.status_code == 200:
            return self.OK, ""
        if r.status_code == 422:
            # A recusa do catálogo é escrita para esta tela mostrar. Reescrevê-la
            # aqui daria duas redações para o mesmo "não", e a que ninguém testa
            # é a que fica errada.
            try:
                return self.RECUSADO, str(r.json().get("detail", "")).strip()
            except ValueError:
                return self.RECUSADO, "o catálogo recusou, sem dizer o motivo"
        logger.error("menu: a gravação respondeu HTTP %s", r.status_code)
        return self.NAO_RESPONDEU, "o catálogo respondeu com erro"


class GamificacaoClient:
    """A economia da escola — quanto vale cada coisa, e o que está ligado.

    Fala só o que está no contrato congelado (`contracts/gamificacao.openapi.yaml`,
    operações `listEconomySwitches` e `setEconomySwitch`, do Rito de 31/08/2026).
    Nunca lê o banco dela (Lei 3), e **nunca guarda uma cópia** das regras aqui:
    a economia é dado da `gamificacao`, e o mesmo fato em dois lugares é a lei
    anti-duplicação do `CLAUDE.md` sendo quebrada — no dia em que as duas
    discordassem, esta tela mostraria uma coisa e o motor pagaria outra.

    **É AQUI que a autorização mora, e não do outro lado.** A `gamificacao` não
    assina sessão ([INV-P12]) e o `papel` que a `identidade` devolve nunca
    autoriza rota ("reconhecer não é autorizar", `DECISAO-onde-mora-a-sessao`
    §4). Quem confere que é o mantenedor é esta célula, sobre a lista DELA — o
    crachá que a porta desta área já exige. O Bearer daqui prova só QUEM CHAMA.

    **Fail-OPEN na leitura, e a mensagem é honesta.** O par de tokens
    `admin→gamificacao` é um passo do mantenedor na VPS (INV-P8, Lei 5): enquanto
    ele não existir, esta tela abre dizendo o que falta, em português, em vez de
    500. Uma tela de operação que não abre é inútil justamente quando você
    precisa dela. Na ESCRITA a falha é fechada: dizer "liguei" sem ter ligado
    seria pior que recusar.

    As variáveis são lidas no PONTO DE USO, nunca no `__init__`
    (`armadilhas/097`: env ausente no construtor vira HTTP 500 em toda página).
    """

    TIMEOUT = 4.0
    OK = "ok"
    RECUSADO = "recusado"
    NAO_RESPONDEU = "nao_respondeu"

    def _configuracao(self) -> "tuple[str, str] | None":
        base = (os.environ.get("GAMIFICACAO_API_URL") or "").strip().rstrip("/")
        token = (os.environ.get("TOKEN_GAMIFICACAO") or "").strip()
        if not base or not token:
            return None
        return base, token

    def regras(self) -> "list | None":
        """As regras de pontuação, ligadas e desligadas. `None` = não deu."""
        return self._listar("economia/regras", "regras")

    def conquistas(self) -> "list | None":
        """As medalhas e os marcos, ligados e desligados. `None` = não deu.

        Operação `listAchievementSwitches`, do Rito de Contrato de 01/09/2026.
        Diferente das regras, aqui vêm `nome` e `descricao` prontos — é a exceção
        declarada no contrato, porque estas duas operações servem o bastidor do
        mantenedor, que é só em português, e o texto de uma conquista é dado que
        ele mesmo edita.
        """
        return self._listar("economia/conquistas", "conquistas")

    def mudar_conquista(self, slug: str, ativa: bool) -> "tuple[str, str]":
        """Liga ou desliga UMA medalha ou marco. Devolve (situação, frase)."""
        return self._mudar("economia/conquistas", slug, ativa, "conquista")

    def degraus(self) -> "list | None":
        """Os degraus da escada, ligados e desligados. `None` = não deu.

        Operação `listLevelSwitches`, do Rito de Contrato de 02/09/2026. Como
        nas conquistas, `titulo` vem pronto: é a mesma exceção declarada no
        contrato, porque esta operação serve o bastidor do mantenedor, que é só
        em português, e o título de um degrau é dado que ele mesmo edita.
        """
        return self._listar("economia/degraus", "degraus")

    def quadro(self) -> "list | None":
        """A escola inteira, aluno por aluno: pontos, nível, última atividade
        e conquistas. `None` = não deu.

        Operação `listStudentStandings`, do Rito de Contrato de 03/09/2026 — a
        primeira que fura o invariante 2 daquela porta (nunca XP de terceiro),
        por exceção declarada: serve só este bastidor. Só quem já tem PerfilJogador
        aparece (a linha é preguiçosa, Lei 7 da gamificação); quem monta a tela
        cruza com `AlunosClient().alunos()` para saber quem falta na lista.

        NÃO traz `título` nem `nome` de conquista — só `nível` e `slug`. Quem
        chama (`escola_pontos.py`) traduz os dois cruzando com `degraus()` e
        `conquistas()`, que já busca para a metade de cima desta mesma tela.
        """
        return self._listar("quadro", "quadro")

    def mudar_degrau(self, nivel: int, ativa: bool) -> "tuple[str, str]":
        """Liga ou desliga UM degrau. Devolve (situação, frase).

        O endereço leva o NÚMERO do degrau, e não um slug: é o número que
        identifica a linha dentro do site (o `Unique` do outro lado é o par
        site + nível).
        """
        return self._mudar("economia/degraus", str(nivel), ativa, "degrau")

    def _listar(self, caminho: str, rotulo: str) -> "list | None":
        config = self._configuracao()
        if config is None:
            logger.warning(
                "economia: GAMIFICACAO_API_URL/TOKEN_GAMIFICACAO ainda não estão "
                "no env desta célula (par admin→gamificacao não provisionado)"
            )
            return None
        base, token = config
        try:
            r = http().get(
                f"{base}/{caminho}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("economia: a gamificação não respondeu: %s", erro)
            return None
        if r.status_code != 200:
            logger.error("economia: a gamificação respondeu HTTP %s", r.status_code)
            return None
        try:
            corpo = r.json()
        except ValueError as erro:
            logger.error("economia: resposta fora do contrato: %s", erro)
            return None
        if not isinstance(corpo, list):
            logger.error("economia: resposta de %s com forma inesperada", rotulo)
            return None
        return corpo

    def mudar(self, slug: str, ativa: bool) -> "tuple[str, str]":
        """Liga ou desliga UMA regra. Devolve (situação, frase para a tela)."""
        return self._mudar("economia/regras", slug, ativa, "regra")

    def _mudar(
        self, caminho: str, slug: str, ativa: bool, rotulo: str
    ) -> "tuple[str, str]":
        config = self._configuracao()
        if config is None:
            return (
                self.NAO_RESPONDEU,
                "o par de tokens com a gamificação não está ligado",
            )
        base, token = config
        try:
            r = http().post(
                f"{base}/{caminho}/{quote(slug, safe='')}",
                json={"ativa": ativa},
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("economia: não deu para mudar a %s: %s", rotulo, erro)
            return self.NAO_RESPONDEU, "a gamificação não respondeu"
        if r.status_code == 200:
            return self.OK, ""
        if r.status_code == 404:
            return self.RECUSADO, f"essa {rotulo} não existe nesta escola"
        logger.error("economia: a mudança respondeu HTTP %s", r.status_code)
        return self.NAO_RESPONDEU, "a gamificação respondeu com erro"


class NotificacoesClient:
    """`contracts/notificacoes.openapi.yaml`, operação `enviarAvisoDeTeste`.

    Rito de Contrato de 03/09/2026 (PR #907, corrigido no #908): a porta que
    responde "o aviso saiu daqui, e para quantos aparelhos". Nasceu de um caso
    real — o botão de ligar os avisos falhava no navegador do mantenedor com o
    servidor verde, e não havia como distinguir "não foi enviado" de "foi
    enviado e não chegou" sem entrar na VPS (Lei 5).

    **Escrita, e por isso `(desfecho, aparelhos)`, nunca `None`.** A pessoa
    clicou num botão esperando saber alguma coisa: `None` aqui seria a mesma
    mentira que `AlunosClient` e `CaixaClient` evitam na escrita — dizer "não
    sei" quando o certo é dizer o que aconteceu, mesmo que seja "zero".
    """

    TIMEOUT = 4.0
    OK = "ok"
    NAO_RESPONDEU = "nao_respondeu"

    def _configuracao(self) -> "tuple[str, str] | None":
        base = (os.environ.get("NOTIFICACOES_API_URL") or "").strip().rstrip("/")
        token = (os.environ.get("NOTIFICACOES_API_TOKEN") or "").strip()
        return (base, token) if base and token else None

    def enviar_aviso_de_teste(
        self, *, site_id: str, destinatario_id: str
    ) -> "tuple[str, int]":
        """`(OK, N)` ou `(NAO_RESPONDEU, 0)`. `N=0` com `OK` é resultado
        legítimo — a pessoa não ligou os avisos em aparelho nenhum, e é
        justamente esse o diagnóstico que a porta existe para dar."""
        config = self._configuracao()
        if config is None:
            logger.error(
                "aviso de teste: NOTIFICACOES_API_URL/NOTIFICACOES_API_TOKEN "
                "ausentes no env desta célula — o botão não pode ser usado"
            )
            return self.NAO_RESPONDEU, 0
        base, token = config
        try:
            r = http().post(
                f"{base}/aviso-de-teste",
                json={"site_id": site_id, "destinatario_id": destinatario_id},
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error(
                "aviso de teste: não deu para falar com a notificacoes: %s", erro
            )
            return self.NAO_RESPONDEU, 0
        if r.status_code != 200:
            logger.error(
                "aviso de teste: a notificacoes respondeu HTTP %s", r.status_code
            )
            return self.NAO_RESPONDEU, 0
        try:
            aparelhos = r.json().get("aparelhos")
        except ValueError:
            logger.error(
                "aviso de teste: a notificacoes respondeu um corpo fora do contrato"
            )
            return self.NAO_RESPONDEU, 0
        if not isinstance(aparelhos, int):
            logger.error("aviso de teste: 'aparelhos' fora do contrato: %r", aparelhos)
            return self.NAO_RESPONDEU, 0
        return self.OK, aparelhos


class MedicaoClient:
    """contracts/metricas.openapi.yaml — `listCoverage` e `listDeadLetters`.

    A `metricas` é o LIVRO DE FATOS da plataforma: ela guarda o que aconteceu,
    para esta tela poder dizer o que MUDOU e não só o que é. Pela Lei 3 o Admin
    não lê o banco dela (o papel `admin_user` sequer o enxerga); pergunta por
    aqui, com o Bearer do par que o mantenedor provisionou.

    FALHA ABERTA, ao contrário da `IdentidadeClient`. A diferença não é gosto: a
    identidade decide ACESSO a esta área, e sem resposta a porta fecha; esta
    responde uma LINHA DE CONFIANÇA no cabeçalho do placar, e derrubar a tela
    inteira porque a memória não respondeu seria trocar um aviso por um apagão.
    Mas fail-open aqui NÃO é fingir zero: cada desfecho tem nome próprio, e a
    tela diz qual deles aconteceu. "Não perguntei" e "perguntei e não há nada"
    são coisas diferentes, e confundi-las é a mentira que esta célula existe
    para não contar.
    """

    TIMEOUT = 2.0

    OK = "ok"
    NAO_RESPONDEU = "nao-respondeu"
    SEM_CONFIGURACAO = "sem-configuracao"
    #: Só a inspeção de UM evento morto usa este: o contrato promete 404 para
    #: id que não existe, e a tela precisa saber a diferença entre "esse evento
    #: não existe" (endereço digitado errado, ou fila já limpa) e "a medição
    #: não respondeu". Achatar os dois num erro só mandaria o mantenedor
    #: procurar defeito onde não há nenhum.
    NAO_EXISTE = "nao-existe"

    def _configuracao(self) -> "tuple[str, str] | None":
        """Endereço e token do par, ou `None` se o env não os tiver.

        Lido NO PONTO DE USO (`armadilhas/097`): o par nasce vazio e é escrito
        na VPS por `infra/provisionar-par-da-medicao.sh`, depois do deploy. Ler
        no import transformaria a janela entre as duas coisas em HTTP 500 em
        toda abertura do placar.
        """
        base = (os.environ.get("METRICAS_API_URL") or "").strip().rstrip("/")
        token = (os.environ.get("METRICAS_API_TOKEN") or "").strip()
        if not base or not token:
            return None
        return base, token

    def _pedir(
        self, caminho: str, params: dict, *, aceita_404: bool = False
    ) -> "tuple[str, object]":
        """`aceita_404` é opt-in de propósito: para a cobertura e para a fila,
        um 404 é a porta fora do lugar, e vira `NAO_RESPONDEU` como qualquer
        outra resposta estranha. Só quem pede UM evento por id tem um 404 que
        significa alguma coisa."""
        config = self._configuracao()
        if config is None:
            logger.warning(
                "medicao: METRICAS_API_URL/METRICAS_API_TOKEN ainda não estão no "
                "env desta célula (par admin→metricas não provisionado)"
            )
            return self.SEM_CONFIGURACAO, None
        base, token = config
        try:
            r = http().get(
                f"{base}{caminho}",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("medicao: a medição não respondeu: %s", erro)
            return self.NAO_RESPONDEU, None
        if aceita_404 and r.status_code == 404:
            return self.NAO_EXISTE, None
        if r.status_code != 200:
            logger.error("medicao: a medição respondeu HTTP %s", r.status_code)
            return self.NAO_RESPONDEU, None
        try:
            return self.OK, r.json()
        except ValueError as erro:
            logger.error("medicao: resposta fora do contrato: %s", erro)
            return self.NAO_RESPONDEU, None

    def cobertura(self, site_id: str) -> "tuple[str, list | None]":
        """De cada assunto já recebido: quantos, e quando foi o último."""
        desfecho, corpo = self._pedir("/cobertura", {"site_id": site_id})
        if desfecho != self.OK:
            return desfecho, None
        tipos = (corpo or {}).get("tipos")
        if not isinstance(tipos, list):
            logger.error("medicao: 'tipos' fora do contrato: %r", tipos)
            return self.NAO_RESPONDEU, None
        return self.OK, tipos

    def conquistas(self, de: "dt.date", ate: "dt.date") -> "tuple[str, list | None]":
        """`countMilestones`: quantas conquistas de cada tipo, por dia.

        SEM filtro de tipo nem de sujeito, e é decisão: a porta devolve todas
        as linhas de uma vez, e quem chama (a tela das coortes) precisa das
        seis. Pedir uma por uma seriam seis viagens de rede para montar a mesma
        tabela, e a resposta sairia costurada de seis instantes diferentes.

        A lista NÃO É ESCOPADA POR SITE, e o contrato diz por quê: a tabela de
        marcos não guarda o site. Quem mostrar estes números tem de dizer que
        são da plataforma inteira, em vez de deixar o leitor supor uma escola.
        """
        desfecho, corpo = self._pedir(
            "/marcos/contagens", {"de": de.isoformat(), "ate": ate.isoformat()}
        )
        if desfecho != self.OK:
            return desfecho, None
        linhas = (corpo or {}).get("conquistas")
        if not isinstance(linhas, list):
            logger.error("medicao: 'conquistas' fora do contrato: %r", linhas)
            return self.NAO_RESPONDEU, None
        return self.OK, linhas

    def mortos(self, limite: int = 30) -> "tuple[str, dict | None]":
        """A fila do que chegou e não pôde ser afirmado: o total e o topo dela.

        `{"total": int, "itens": [...]}`. O `corpo` cru NÃO vem aqui, e não é
        economia de bytes: o contrato o esconde da lista de propósito, porque
        um envelope quebrado pode conter o que esta casa não guarda (nome,
        e-mail, texto de mensagem). Quem precisa ver um corpo pede UM, por
        `morto`, e aí é inspeção deliberada.
        """
        desfecho, corpo = self._pedir("/eventos-mortos", {"limite": limite})
        if desfecho != self.OK:
            return desfecho, None
        total = (corpo or {}).get("total")
        itens = (corpo or {}).get("itens")
        if not isinstance(total, int) or not isinstance(itens, list):
            logger.error("medicao: a fila de mortos veio fora do contrato: %r", corpo)
            return self.NAO_RESPONDEU, None
        return self.OK, {"total": total, "itens": itens}

    def morto(self, morto_id: int) -> "tuple[str, dict | None]":
        """UM evento morto, com o corpo cru: a ação "inspecionar" do plano.

        Devolve `NAO_EXISTE` para id que não existe, e nunca um dicionário
        vazio: resposta vazia que parece resposta é o pior desfecho possível
        numa tela onde se decide o que fazer com um fato que se perdeu.
        """
        desfecho, corpo = self._pedir(
            f"/eventos-mortos/{int(morto_id)}", {}, aceita_404=True
        )
        if desfecho != self.OK:
            return desfecho, None
        if not isinstance(corpo, dict) or "corpo" not in corpo:
            logger.error("medicao: o evento morto veio fora do contrato: %r", corpo)
            return self.NAO_RESPONDEU, None
        return self.OK, corpo

    def quebrados(self) -> "tuple[str, int | None]":
        """Quantos eventos chegaram e não puderam ser afirmados.

        `limite=1` de propósito: quem chama é a linha do placar, que usa só o
        `total`, e a fila pode ter milhares de linhas num incidente. Pedir a
        página inteira para mostrar um número seria pagar o pior caso por nada.
        A conferência da forma é a de `mortos`, e não uma segunda: dois lugares
        decidindo o que é "fora do contrato" divergem no primeiro campo novo.
        """
        desfecho, fila = self.mortos(limite=1)
        return desfecho, None if fila is None else fila["total"]


class MensageriaClient:
    """As sequências de mensagens da escola: o que existe, quem está dentro, o
    que saiu, o que NÃO saiu, e as duas escritas.

    Fala só o que está no contrato congelado (`contracts/mensageria.openapi.yaml`,
    Rito de Contrato de 04/09/2026, com o mantenedor presente). Nunca lê o
    `mensageria_db` (Lei 3), e **nunca guarda uma cópia** de nada aqui: a
    sequência é dado da `mensageria`, e o mesmo fato em dois lugares é a lei
    anti-duplicação do `CLAUDE.md` sendo quebrada. No dia em que os dois
    discordassem, esta tela mostraria um texto e o aluno receberia outro.

    ## Os desfechos são cinco, e não dois, porque a tela precisa dos cinco

    Um `None` genérico obrigaria a tela a dizer "não deu" para cinco situações
    que pedem cinco frases diferentes ao mantenedor. As três recusas do contrato
    são fatos que ele PODE resolver sozinho, e uma tela que as achatasse num
    erro só o mandaria procurar ajuda para algo que está a um clique:

    - **`SEM_VERSAO`** (409 ao ligar): a sequência não tem versão publicada.
      Ligada assim ela não inscreveria ninguém, e a tela mostraria "no ar" para
      uma sequência muda.
    - **`DESATUALIZADO`** (409 ao publicar): alguém publicou entre a leitura
      desta tela e o clique. O `versao_base` é a trava que impede sobrescrever
      em silêncio quem publicou primeiro.
    - **`SEM_GRAU`** (403): o par tem só `TOKENS_SOMENTE_LEITURA_ADMIN`, e falta
      `TOKENS_PUBLICACAO_ADMIN`. A tela lê tudo certo e só a escrita recusa: é o
      modo de falha exato que os dois conjuntos de token existem para tornar
      diagnosticável (`services/mensageria/apps/core/auth.py`).

    ## Fail-OPEN na leitura, fail-CLOSED na escrita

    Mesmo desenho de `GamificacaoClient`, pelo mesmo motivo. O par de tokens
    `admin→mensageria` é um passo do mantenedor na VPS (Lei 5): enquanto ele não
    existir, a tela abre dizendo o que falta, em português, em vez de 500. Uma
    tela de operação que não abre é inútil justamente quando você precisa dela.
    Na escrita a falha é fechada: dizer "publiquei" sem ter publicado mandaria
    o mantenedor embora achando que a correção pegou.

    As variáveis são lidas no PONTO DE USO, nunca no `__init__`
    (`armadilhas/097`: env ausente no construtor vira HTTP 500 em toda página).
    """

    TIMEOUT = 4.0
    OK = "ok"
    RECUSADO = "recusado"
    SEM_VERSAO = "sem_versao"
    DESATUALIZADO = "desatualizado"
    SEM_GRAU = "sem_grau"
    NAO_RESPONDEU = "nao_respondeu"

    def _configuracao(self) -> "tuple[str, str] | None":
        base = (os.environ.get("MENSAGERIA_API_URL") or "").strip().rstrip("/")
        token = (os.environ.get("MENSAGERIA_API_TOKEN") or "").strip()
        return (base, token) if base and token else None

    def ligado(self) -> bool:
        """O par existe no env desta célula? A tela pergunta antes de desenhar."""
        return self._configuracao() is not None

    # -- as quatro leituras --------------------------------------------------
    def jornadas(self, site_id: str) -> "dict | None":
        """`listJourneys`: as sequências deste site. `None` = não deu."""
        return self._ler("jornadas", {"site_id": site_id})

    def jornada(self, site_id: str, slug: str, versao: "int | None" = None):
        """`getJourney`: os passos de uma versão, na ordem. `None` = não deu.

        Sem `versao`, a porta devolve a PUBLICADA CORRENTE. Quem chama só pede
        isto depois de saber, pela lista, que existe versão publicada: assim o
        404 de "sequência não existe" nunca se confunde com o de "ainda não tem
        versão", e a tela não precisa adivinhar lendo o texto de um erro.
        """
        parametros = {"site_id": site_id}
        if versao is not None:
            parametros["versao"] = versao
        return self._ler("jornadas/" + quote(slug, safe=""), parametros)

    def inscricoes(self, site_id: str, slug: str, estado: str = ""):
        """`listEnrollments`: quem está dentro, e em que passo. `None` = não deu."""
        parametros = {"site_id": site_id}
        if estado:
            parametros["estado"] = estado
        return self._ler("jornadas/" + quote(slug, safe="") + "/inscricoes", parametros)

    def entregas(self, site_id: str, inscricao_id: str) -> "dict | None":
        """`listDeliveries`: o que saiu, o que NÃO saiu, e por quê.

        É a operação que responde "por que o aluno X não recebeu?", e é a metade
        que faz esta tela valer.
        """
        return self._ler(
            "inscricoes/" + quote(inscricao_id, safe="") + "/entregas",
            {"site_id": site_id},
        )

    def _ler(self, caminho: str, parametros: dict) -> "dict | None":
        config = self._configuracao()
        if config is None:
            logger.warning(
                "sequencias: MENSAGERIA_API_URL/MENSAGERIA_API_TOKEN ainda não "
                "estão no env desta célula (par admin->mensageria não provisionado)"
            )
            return None
        base, token = config
        try:
            r = http().get(
                base + "/" + caminho,
                params=parametros,
                headers={"Authorization": "Bearer " + token},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("sequencias: a mensageria não respondeu: %s", erro)
            return None
        if r.status_code != 200:
            logger.error("sequencias: a mensageria respondeu HTTP %s", r.status_code)
            return None
        try:
            corpo = r.json()
        except ValueError as erro:
            logger.error("sequencias: resposta fora do contrato: %s", erro)
            return None
        if not isinstance(corpo, dict):
            logger.error("sequencias: resposta de %s com forma inesperada", caminho)
            return None
        return corpo

    # -- as duas escritas ----------------------------------------------------
    def publicar_texto(
        self,
        *,
        site_id: str,
        slug: str,
        ordem: int,
        idioma: str,
        assunto_visivel: str,
        corpo: str,
        versao_base: "int | None",
    ) -> "tuple[str, dict, str]":
        """`publishJourneyText`: grava a frase PUBLICANDO uma versão nova.

        Devolve `(situação, corpo da resposta, frase para a tela)`. O corpo traz
        o NÚMERO da versão que nasceu, e a tela precisa dele: é com ele que ela
        diz ao mantenedor, em português, que quem já estava no meio da sequência
        termina com o texto antigo.
        """
        return self._escrever(
            "jornadas/" + quote(slug, safe="") + "/textos",
            {
                "site_id": site_id,
                "ordem": ordem,
                "idioma": idioma,
                "assunto_visivel": assunto_visivel,
                "corpo": corpo,
                "versao_base": versao_base,
            },
            publicando=True,
        )

    def ligar(self, *, site_id: str, slug: str, ativa: bool) -> "tuple[str, dict, str]":
        """`setJourneyActive`: liga ou desliga, sem tocar no texto.

        O pedido descreve o ESTADO desejado, não um verbo, então mandar o mesmo
        duas vezes é 200 nas duas. A resposta traz `mudou` (que separa "acabei
        de ligar" de "já estava ligada") e `inscricoes_andando` (quantas pessoas
        continuam recebendo depois de desligada). A tela usa os dois.
        """
        return self._escrever(
            "jornadas/" + quote(slug, safe="") + "/ativa",
            {"site_id": site_id, "ativa": ativa},
            publicando=False,
        )

    def _escrever(
        self, caminho: str, corpo: dict, *, publicando: bool
    ) -> "tuple[str, dict, str]":
        config = self._configuracao()
        if config is None:
            return (
                self.NAO_RESPONDEU,
                {},
                "o par de tokens com o motor das mensagens não está ligado",
            )
        base, token = config
        try:
            r = http().post(
                base + "/" + caminho,
                json=corpo,
                headers={"Authorization": "Bearer " + token},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("sequencias: não deu para escrever: %s", erro)
            return self.NAO_RESPONDEU, {}, "o motor das mensagens não respondeu"

        if r.status_code == 200:
            try:
                resposta = r.json()
            except ValueError:
                logger.error("sequencias: a escrita respondeu fora do contrato")
                return self.NAO_RESPONDEU, {}, "o motor das mensagens não respondeu"
            if not isinstance(resposta, dict):
                logger.error("sequencias: a escrita respondeu uma forma inesperada")
                return self.NAO_RESPONDEU, {}, "o motor das mensagens não respondeu"
            return self.OK, resposta, ""

        if r.status_code == 403:
            # O par existe e lê tudo, mas não tem o grau de publicação. É o modo
            # de falha silencioso que os DOIS conjuntos de token existem para
            # tornar visível: sem esta linha a tela diria "não respondeu", e o
            # mantenedor iria procurar um problema de rede que não existe.
            logger.error(
                "sequencias: o par admin->mensageria não tem o grau de publicação "
                "(falta TOKENS_PUBLICACAO_ADMIN no env da mensageria)"
            )
            return self.SEM_GRAU, {}, ""
        if r.status_code == 404:
            return self.RECUSADO, {}, "essa sequência não existe nesta escola"
        if r.status_code == 409:
            # Os dois 409 do contrato são situações diferentes, e só quem chamou
            # sabe qual delas pediu: ligar sem versão publicada contra publicar
            # sobre uma base que já andou. Distinguir pelo TEXTO da resposta
            # seria amarrar esta tela à redação de uma mensagem de erro.
            return (self.DESATUALIZADO if publicando else self.SEM_VERSAO), {}, ""
        if r.status_code == 422:
            return self.RECUSADO, {}, "faltou preencher alguma coisa"
        logger.error("sequencias: a escrita respondeu HTTP %s", r.status_code)
        return self.NAO_RESPONDEU, {}, "o motor das mensagens respondeu com erro"


class CursosClient:
    """A sala de aula: as encomendas do curso e os instrumentos de avaliação.

    Fala só o que está no contrato congelado (`contracts/cursos.openapi.yaml`,
    degrau 1.4 da escada do `PLANO-CELULA-CURSOS.md`): as sete operações do
    editor, e das aulas SEMPRE as que sabem de curso (`listLessons`,
    `getLesson`, `putLesson`, `publishLesson`, sob `/cursos/{curso}/aulas`).
    Nunca lê o `cursos_db` (Lei 3), e **nunca guarda uma cópia** de
    nada aqui. O peso disso é maior do que nas outras portas deste arquivo: o
    texto das aulas é obra NÃO LANÇADA do mantenedor, o repositório é público,
    e o único lugar em que esse texto existe é o banco da `cursos`
    ([INV-CUR-C2], `armadilhas/331`). Uma tabela de aulas aqui seria o mesmo
    fato em dois lugares, e no dia em que os dois discordassem o editor
    mostraria um texto e o aluno leria outro.

    ## Os desfechos são seis, porque a tela precisa de seis frases

    Um `None` genérico obrigaria a tela a dizer "não deu" para situações que o
    mantenedor resolve de jeitos diferentes, e três delas ele resolve sozinho:

    - **`SEM_CONFIGURACAO`**: o par (`CURSOS_API_URL`/`CURSOS_API_TOKEN`) não
      está no env desta célula. É um passo dele na VPS (Lei 5), e a tela nomeia
      o passo. Nenhuma ida à rede acontece neste caso (`armadilhas/097`).
    - **`RECUSOU`** (401/403): o par existe aqui, mas a `cursos` não o aceita.
      De fora é indistinguível de "não há aula nenhuma", e é por isso que tem
      nome próprio: o conserto é conferir `TOKENS_ACEITOS_ADMIN` do outro lado,
      e não procurar um problema de rede que não existe.
    - **`NAO_EXISTE`** (404): a aula ou o instrumento não existe. É resposta,
      não falha.
    - **`RECUSADO`** (422): a `cursos` leu o corpo e recusou, e o segundo item
      é o `detail` do contrato, com a lista de erros campo por campo. Quem o
      traduz para português, ao lado de cada campo, é `apps/core/aulas.py`.
    - **`NAO_RESPONDEU`**: rede, 5xx, corpo fora do contrato. Na escrita isto
      NÃO vira "recusado": a gravação pode ter acontecido do outro lado, e a
      tela precisa dizer "não sei" em vez de "não valeu".

    ## Fail-OPEN na leitura, fail-CLOSED na escrita

    Mesmo desenho de `MensageriaClient` e `GamificacaoClient`. Uma tela de
    operação que não abre é inútil justamente quando você precisa dela; mas
    dizer "salvei" sem ter salvado mandaria a professora embora achando que a
    aula está guardada. As variáveis são lidas no PONTO DE USO, nunca no
    `__init__` (`armadilhas/097`).
    """

    TIMEOUT = 4.0
    OK = "ok"
    SEM_CONFIGURACAO = "sem_configuracao"
    RECUSOU = "recusou"
    NAO_EXISTE = "nao_existe"
    RECUSADO = "recusado"
    NAO_RESPONDEU = "nao_respondeu"

    def _configuracao(self) -> "tuple[str, str] | None":
        base = (os.environ.get("CURSOS_API_URL") or "").strip().rstrip("/")
        token = (os.environ.get("CURSOS_API_TOKEN") or "").strip()
        return (base, token) if base and token else None

    def _caminho(self, curso: str, *resto: str) -> str:
        """As quatro operações da encomenda moram sob o SLUG do curso.

        As irmãs sem curso (`listSiteLessons` e companhia) continuam no
        contrato, e esta célula não as chama mais: elas varrem o site inteiro, e
        no dia do segundo curso devolveriam as aulas dos dois misturadas, sem
        nada na resposta que diga de qual curso é cada linha.
        """
        return "/".join(["cursos", quote(curso, safe=""), "aulas", *resto])

    def _com_parte(self, site_id: str, parte: "int | None") -> dict:
        params: dict = {"site_id": site_id}
        if parte is not None:
            params["parte"] = int(parte)
        return params

    # -- as quatro leituras --------------------------------------------------
    def aulas(
        self, site_id: str, curso: str, parte: "int | None" = None
    ) -> "tuple[str, list | None]":
        """`listLessons`: as encomendas de UM curso, na ordem do aluno.

        `parte` aqui é FILTRO: com ela vem só aquela Parte do livro; sem ela,
        o curso inteiro. Slug que não existe naquele site é `NAO_EXISTE`.
        """
        return self._pedir(
            "get",
            self._caminho(curso),
            params=self._com_parte(site_id, parte),
            forma=list,
        )

    def aula(
        self, site_id: str, curso: str, numero: str, parte: "int | None" = None
    ) -> "tuple[str, dict | None]":
        """`getLesson`: uma encomenda inteira, com as 18 peças e as pausas.

        `parte` aqui NÃO é filtro: é GUARDA. Parte que não casa com o bloco da
        encomenda é `NAO_EXISTE`, por contrato: um endereço que aponta certo
        para a encomenda errada é pior do que um endereço quebrado.
        """
        return self._pedir(
            "get",
            self._caminho(curso, quote(numero, safe="")),
            params=self._com_parte(site_id, parte),
        )

    def instrumentos(self) -> "tuple[str, list | None]":
        """`listInstruments`: os 13 cartões, na ordem. Sem `site_id`: os
        instrumentos são de plataforma inteira, por contrato."""
        return self._pedir("get", "instrumentos", forma=list)

    def instrumento(self, slug: str) -> "tuple[str, dict | None]":
        """`getInstrument`: um cartão inteiro, pelo slug."""
        return self._pedir("get", "instrumentos/" + quote(slug, safe=""))

    # -- as três escritas ----------------------------------------------------
    def gravar_aula(
        self,
        site_id: str,
        curso: str,
        numero: str,
        corpo: dict,
        parte: "int | None" = None,
    ):
        """`putLesson`: grava a encomenda INTEIRA; a versão volta incrementada.

        Em `RECUSADO` o segundo item é o `detail` do 422 (a lista de erros do
        contrato), e não a aula: é com ele que a tela põe a frase ao lado do
        campo certo. `parte` é o mesmo guarda de `aula`, e vale aqui pelo motivo
        mais pesado: gravar pela encomenda errada sobrescreveria texto.
        """
        return self._pedir(
            "put",
            self._caminho(curso, quote(numero, safe="")),
            params=self._com_parte(site_id, parte),
            json=corpo,
        )

    def publicar_aula(
        self, site_id: str, curso: str, numero: str, parte: "int | None" = None
    ) -> "tuple[str, dict | None]":
        """`publishLesson`: estado `publicada`, data de agora, versão inalterada.
        Idempotente do outro lado: publicar o publicado devolve como está."""
        return self._pedir(
            "post",
            self._caminho(curso, quote(numero, safe=""), "publicar"),
            params=self._com_parte(site_id, parte),
        )

    def gravar_instrumento(self, slug: str, corpo: dict):
        """`putInstrument`: a escala, os mínimos, a seção e os descritores.
        `nome_canonico` e `cartao` nunca vão no corpo: são da lei, e a porta
        recusa com 422 se forem."""
        return self._pedir("put", "instrumentos/" + quote(slug, safe=""), json=corpo)

    def _pedir(self, metodo: str, caminho: str, *, params=None, json=None, forma=dict):
        """Uma ida à porta, com o tratamento que as sete operações compartilham.

        Devolve `(desfecho, corpo)`. Sete cópias do mesmo `try` divergiriam no
        primeiro caso de borda corrigido de um lado só.
        """
        config = self._configuracao()
        if config is None:
            logger.warning(
                "aulas: CURSOS_API_URL/CURSOS_API_TOKEN ainda não estão no env "
                "desta célula (par admin->cursos não provisionado)"
            )
            return self.SEM_CONFIGURACAO, None
        base, token = config
        try:
            r = http().request(
                metodo.upper(),
                base + "/" + caminho,
                params=params,
                json=json,
                headers={"Authorization": "Bearer " + token},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("aulas: a sala de aula não respondeu: %s", erro)
            return self.NAO_RESPONDEU, None

        if r.status_code in (401, 403):
            logger.error(
                "aulas: a cursos recusou o par admin->cursos (HTTP %s); confira "
                "TOKENS_ACEITOS_ADMIN do lado da cursos",
                r.status_code,
            )
            return self.RECUSOU, None
        if r.status_code == 404:
            return self.NAO_EXISTE, None
        if r.status_code == 422:
            try:
                detalhe = r.json().get("detail")
            except (ValueError, AttributeError):
                detalhe = None
            return self.RECUSADO, detalhe
        if r.status_code != 200:
            logger.error("aulas: a sala de aula respondeu HTTP %s", r.status_code)
            return self.NAO_RESPONDEU, None

        try:
            corpo = r.json()
        except ValueError as erro:
            # *Status 2xx não é sucesso* (RETROSPECTIVA §4).
            logger.error("aulas: resposta fora do contrato: %s", erro)
            return self.NAO_RESPONDEU, None
        if not isinstance(corpo, forma):
            logger.error("aulas: resposta de %s com forma inesperada", caminho)
            return self.NAO_RESPONDEU, None
        return self.OK, corpo
