# apps/core/clients.py  # [RECEITA:R2 v1]
# Fala SÓ o que está no contrato congelado da identidade
# (`contracts/identidade.openapi.yaml`). Nunca lê o banco dela (Lei 3).
import logging
import os
import time

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
    """contracts/identidade.openapi.yaml — `getSessionFull` (somente-leitura)."""

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

    def apagar_aluno(self, alvo: str) -> "tuple[str, str]":
        """[APAGAR] Apaga a ficha DE VEZ. Mesmos três desfechos das outras escritas.

        Irreversível do outro lado — e por isso o `NAO_RESPONDEU` importa ainda
        mais aqui: uma exclusão que talvez tenha acontecido não pode ser
        mostrada como "não deu certo", ou o mantenedor tenta de novo achando
        que a primeira não valeu.
        """
        config = self._configuracao()
        if config is None:
            return self.NAO_RESPONDEU, "o par de tokens com a alunos não está ligado"
        base, token = config

        try:
            r = http().delete(
                f"{base}/matriculas/{alvo}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("apagar: não deu para falar com a alunos: %s", erro)
            return self.NAO_RESPONDEU, "a parte que guarda os alunos não respondeu"

        if r.status_code == 204:
            return self.OK, ""
        if r.status_code == 404:
            return self.RECUSADO, "esta ficha já não existe"
        if r.status_code == 409:
            return self.RECUSADO, "esta pessoa ainda está na fila — decida por lá"
        logger.error("apagar: a alunos respondeu HTTP %s", r.status_code)
        return self.NAO_RESPONDEU, "a parte que guarda os alunos respondeu com erro"


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

    def ideias(self, por_email: str = "") -> "dict | None":
        """O quadro inteiro com os FATOS de cada ideia, ou `None`.

        `por_email` não filtra nada: ele responde uma pergunta só — *esta pessoa
        pode assinar?* — e a resposta vem no campo `pode_assinar`. Quem recusa de
        verdade é a Caixa, na escrita; isto serve para a tela não desenhar um
        botão que já se sabe que vai ser recusado.
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
                f"{base}/gestao/ideias",
                params={"por_email": por_email} if por_email else {},
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

    # -- escrita: diz o que aconteceu ----------------------------------------

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
