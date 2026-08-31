# apps/core/clients.py  # [RECEITA:R2 v1]
# Fala SÓ o que está no contrato congelado da identidade
# (`contracts/identidade.openapi.yaml`). Nunca lê o banco dela (Lei 3).
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
                f"{base}/economia/regras",
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
            logger.error("economia: resposta com forma inesperada")
            return None
        return corpo

    def mudar(self, slug: str, ativa: bool) -> "tuple[str, str]":
        """Liga ou desliga UMA regra. Devolve (situação, frase para a tela)."""
        config = self._configuracao()
        if config is None:
            return (
                self.NAO_RESPONDEU,
                "o par de tokens com a gamificação não está ligado",
            )
        base, token = config
        try:
            r = http().post(
                f"{base}/economia/regras/{quote(slug, safe='')}",
                json={"ativa": ativa},
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("economia: não deu para mudar a regra: %s", erro)
            return self.NAO_RESPONDEU, "a gamificação não respondeu"
        if r.status_code == 200:
            return self.OK, ""
        if r.status_code == 404:
            return self.RECUSADO, "essa regra não existe nesta escola"
        logger.error("economia: a mudança respondeu HTTP %s", r.status_code)
        return self.NAO_RESPONDEU, "a gamificação respondeu com erro"
