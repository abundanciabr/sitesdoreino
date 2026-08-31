# apps/core/clients.py  # [RECEITA:R2 v1]
# Fala SÓ o que está nos contratos congelados de catalogo, leads e identidade.
# Em dev, aponte CATALOGO_API_URL/LEADS_API_URL/IDENTIDADE_API_URL para os mocks
# prism (make mocks) — nunca suba a outra célula, nunca leia o banco dela.
import logging
import os

import httpx

logger = logging.getLogger("funil.sessao")

_cliente: httpx.Client | None = None


def http() -> httpx.Client:
    """Um `httpx.Client` por processo, em vez de `httpx.get()`/`httpx.post()` a
    cada chamada. A forma direta constrói um `Client` descartável — e com ele
    um `ssl.SSLContext` novo, que recarrega os certificados raiz do sistema —
    a cada chamada de rede interna (armadilhas/082, medido em 0,4s por
    chamada). `httpx.Client` é seguro entre threads, que é o que o uvicorn
    precisa.
    """
    global _cliente
    if _cliente is None:
        _cliente = httpx.Client()
    return _cliente


class CatalogoClient:
    """contracts/catalogo.openapi.yaml (somente-leitura)."""

    def __init__(self) -> None:
        self.base = os.environ["CATALOGO_API_URL"].rstrip("/")
        self.token = os.environ["TOKEN_CATALOGO"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def obter_site_por_host(self, host: str) -> dict | None:
        """[INV-P11] 404 do catálogo é 'site desconhecido', nunca um site padrão."""
        r = http().get(
            f"{self.base}/sites/by-host/{host}",
            headers=self._headers(),
            timeout=5.0,  # timeout SEMPRE explícito
        )
        return r.json() if r.status_code == 200 else None

    def obter_oferta(self, site_id: str, slug: str) -> dict | None:
        """Slugs são únicos POR site — o site_id na rota é o que impede vazamento."""
        r = http().get(
            f"{self.base}/sites/{site_id}/ofertas/{slug}",
            headers=self._headers(),
            timeout=5.0,
        )
        return r.json() if r.status_code == 200 else None


class LeadsClient:
    """contracts/leads.openapi.yaml (somente-escrita, do ponto de vista do funil)."""

    def __init__(self) -> None:
        self.base = os.environ["LEADS_API_URL"].rstrip("/")
        self.token = os.environ["TOKEN_LEADS"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def upsert_lead(self, payload: dict) -> dict:
        r = http().post(
            f"{self.base}/leads",
            json=payload,
            headers=self._headers(),
            timeout=10.0,
        )
        r.raise_for_status()
        return r.json()


class IdentidadeClient:
    """`contracts/identidade.openapi.yaml` — quem é a pessoa, e (desde
    `DECISAO-login-por-senha.md`) o segundo jeito de ela provar quem é.

    `obter_sessao`/`obter_email` são leitura pura e fail-OPEN.
    `emitir_token_de_senha`/`definir_senha` são diferentes por natureza —
    ver o docstring de cada um.

    Lei do assunto: `docs/decisoes/DECISAO-onde-mora-a-sessao.md`. O site não lê
    o cookie de sessão: ele **pergunta** quem é o dono dele. O cookie é assinado
    com a chave da `identidade` e aponta para uma linha no banco DELA — o `funil`
    não tem chave nem banco (Lei 2, Lei 3). Perguntar é a única forma legal, e é
    também a que faz a identidade poder mudar de casa um dia sem que este
    arquivo mude: troca-se o endereço no env.

    **Duas credenciais viajam juntas, e provam coisas diferentes:**

    - o `Bearer` do par prova que **quem chama** é esta célula;
    - o `Cookie` repassado prova quem é **a pessoa** do outro lado do navegador.

    Nenhuma das duas substitui a outra, e o cookie **nunca** é interpretado
    aqui — ele é carregado de um lado para o outro, opaco.
    """

    TIMEOUT = 2.0

    def _configuracao(self) -> "tuple[str, str] | None":
        """Endereço e token do par, ou `None` se o env não os tiver.

        Lido NO PONTO DE USO, com `.get()` — nunca `os.environ[...]` no
        `__init__`. A diferença é a linha que separa esta célula de cair:
        `os.environ["X"]` levanta `KeyError`, que **não** é `httpx.HTTPError`
        e portanto atravessaria intacto o `try` de `obter_sessao`, o
        middleware e o `{% if request.ator %}` — virando **HTTP 500 em toda
        página multilíngue** para qualquer visitante que carregue um cookie
        qualquer (o de idioma, o de analytics, um do Cloudflare).

        A auditoria de 25/08/2026 achou isso em quatro cadeiras independentes,
        e o modo de falha era pior do que o nome sugere: falha de configuração
        é MAIS provável que falha de rede (basta uma variável não colada no
        servidor), e é invisível para quem testa num navegador limpo — só
        quem já tem cookie recebe o erro.
        """
        base = (os.environ.get("IDENTIDADE_API_URL") or "").strip().rstrip("/")
        token = (os.environ.get("IDENTIDADE_API_TOKEN") or "").strip()
        return (base, token) if base and token else None

    def obter_sessao(self, cookie: str) -> dict | None:
        """Quem é a pessoa desta requisição, ou `None`.

        **Falha ⇒ `None`, e isso é DELIBERADO** (DECISAO-onde-mora-a-sessao §4:
        *reconhecer não é autorizar*). Não conseguir perguntar significa que o
        site mostra "Entrar" e a página abre normal — a vitrine não pode cair
        porque a Caixa está reiniciando. É o oposto exato do
        `AlunosIndisponivel` da outra ponta, que fecha a porta quando não
        consegue perguntar: lá a resposta decide ACESSO, aqui decide um nome no
        canto da tela.

        Quem quiser autorizar alguma coisa um dia **não pode** partir daqui:
        autorização é fail-closed, na célula dona do recurso.

        Timeout curto (2s, contra os 5s do catálogo): isto está no caminho de
        alguém esperando uma página abrir, e a resposta certa para "demorou" é
        desistir depressa e mostrar "Entrar" — nunca pendurar a página.
        """
        config = self._configuracao()
        if config is None:
            # Nem tenta a rede: sem endereço ou sem token não há pergunta a
            # fazer, e esperar um timeout de 2s para descobrir isso atrasaria
            # toda página. ERROR nomeando as variáveis, porque o leitor do log
            # vai ser o mantenedor.
            logger.error(
                "sessao: IDENTIDADE_API_URL/IDENTIDADE_API_TOKEN ausentes no "
                "env desta célula — mostrando 'Entrar' para todo mundo"
            )
            return None
        base, token = config

        try:
            r = http().get(
                f"{base}/sessao",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Cookie": cookie,
                },
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            # ERROR e não silêncio: fail-open é decisão de produto, não licença
            # para a Caixa cair sem ninguém saber (RETROSPECTIVA §1).
            logger.error("sessao: não deu para perguntar à identidade: %s", erro)
            return None

        if r.status_code != 200:
            logger.error("sessao: a identidade respondeu HTTP %s", r.status_code)
            return None

        try:
            corpo = r.json()
        except ValueError as erro:
            # `200` com corpo que não é JSON — página de erro de um proxy
            # interposto, resposta truncada, `Content-Length` mentiroso.
            # `json.JSONDecodeError` é `ValueError`, NÃO é `httpx.HTTPError`:
            # fora deste `try` ela furaria o fail-open e derrubaria a vitrine.
            # É a família do bug mais caro da Fase D — *status 2xx não é
            # sucesso* (RETROSPECTIVA §4).
            logger.error("sessao: a identidade respondeu fora do contrato: %s", erro)
            return None

        # O contrato garante o campo; um corpo fora do contrato é tratado como
        # visitante, nunca como "provavelmente logado".
        if not isinstance(corpo, dict) or not corpo.get("autenticado"):
            return None
        return corpo

    def obter_email(self, cookie: str) -> "str | None":
        """O e-mail da sessão — e SÓ ele, para uma pergunta só.

        Existe porque a categoria de uma pessoa é calculada por e-mail: é por
        e-mail que a `alunos` guarda matrícula, e não há outro identificador
        comum entre as duas células (`DECISAO-categorias-de-usuario` §4).

        **Este é o degrau a mais que a `identidade` cobra por escrito**
        (`DECISAO-celula-de-identidade` §6.3): além de `TOKENS_ACEITOS_FUNIL`,
        o par precisa estar em `TOKENS_COMPLETOS_FUNIL`. Sem o segundo, esta
        chamada volta 403 — e o efeito é a home tratar todo mundo como
        cadastrado, nunca um erro na tela.

        **O e-mail NÃO é guardado em lugar nenhum desta célula**: não vai para
        o template, não entra no cache, não entra em log. Ele existe dentro da
        requisição, o tempo de fazer uma pergunta. Guarda:
        `tests/test_categorias_na_home.py`.
        """
        config = self._configuracao()
        if config is None:
            return None
        base, token = config

        try:
            r = http().get(
                f"{base}/sessao/completa",
                headers={"Authorization": f"Bearer {token}", "Cookie": cookie},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("sessao completa: não deu para perguntar: %s", erro)
            return None

        if r.status_code != 200:
            # 403 aqui = o par não está em TOKENS_COMPLETOS_FUNIL. De fora é
            # indistinguível de "não há sessão", e por isso o log nomeia a
            # variável: quem vai ler é o mantenedor.
            logger.error(
                "sessao completa: a identidade respondeu HTTP %s "
                "(403 = falta TOKENS_COMPLETOS_FUNIL do lado dela)",
                r.status_code,
            )
            return None

        try:
            corpo = r.json()
        except ValueError as erro:
            logger.error("sessao completa: resposta fora do contrato: %s", erro)
            return None

        if not isinstance(corpo, dict) or not corpo.get("autenticado"):
            return None
        return (corpo.get("email") or "").strip() or None

    # [LOGIN-POR-SENHA] `DECISAO-login-por-senha.md` — as duas operações que
    # o /cadastro e o /login precisam para o segundo jeito de entrar.
    RESULTADO_SENHA_OK = "ok"
    RESULTADO_SENHA_FALHOU = "falhou"

    def emitir_token_de_senha(self) -> "str | None":
        """O token que defende `/entrar/senha` de CSRF (`issueLoginToken`).

        **Fail-OPEN, ao contrário de `definir_senha` logo abaixo** — mesma
        lei de `obter_sessao`: isto está no caminho de alguém abrindo
        `/login`, e a página não pode cair porque a identidade está fora do
        ar. `None` faz o mini-formulário de senha simplesmente não
        aparecer; o botão do Google continua funcionando sozinho.
        """
        config = self._configuracao()
        if config is None:
            logger.error(
                "token de senha: IDENTIDADE_API_URL/IDENTIDADE_API_TOKEN "
                "ausentes no env desta célula — mini-formulário de senha some"
            )
            return None
        base, token = config

        try:
            r = http().post(
                f"{base}/tokens-de-entrada",
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("token de senha: não deu para perguntar: %s", erro)
            return None

        if r.status_code != 200:
            logger.error(
                "token de senha: a identidade respondeu HTTP %s", r.status_code
            )
            return None

        try:
            corpo = r.json()
        except ValueError as erro:
            logger.error("token de senha: resposta fora do contrato: %s", erro)
            return None

        if not isinstance(corpo, dict) or not corpo.get("token"):
            return None
        return corpo["token"]

    def definir_senha(
        self, *, email: str, senha: str, nome: str = "", site_id: str = ""
    ) -> str:
        """`setPassword` — grava a senha escolhida no `/cadastro`.

        **Fail-CLOSED, ao contrário de `emitir_token_de_senha` acima e de
        `obter_sessao`/`obter_email`** — decisão do mantenedor
        (`DECISAO-login-por-senha.md` §1.3): se isto falhar, quem chama
        (a view `cadastro`) trata o pedido inteiro como não enviado (502,
        formulário preservado), mesmo que o pedido de vaga em si
        (`AlunosClient.criar_pre_matricula`) já tenha ido. É seguro
        reenviar: `entrar_na_fila` do lado da `alunos` é idempotente por
        e-mail, então tentar de novo nunca duplica ninguém na fila.
        """
        config = self._configuracao()
        if config is None:
            logger.error(
                "definir senha: IDENTIDADE_API_URL/IDENTIDADE_API_TOKEN "
                "ausentes no env desta célula — a senha não foi gravada"
            )
            return self.RESULTADO_SENHA_FALHOU
        base, token = config

        try:
            r = http().post(
                f"{base}/pessoas/definir-senha",
                json={
                    "email": email,
                    "senha": senha,
                    "nome": nome,
                    "site_id": site_id,
                },
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("definir senha: não deu para falar com a identidade: %s", erro)
            return self.RESULTADO_SENHA_FALHOU

        if r.status_code != 200:
            logger.error("definir senha: a identidade respondeu HTTP %s", r.status_code)
            return self.RESULTADO_SENHA_FALHOU

        return self.RESULTADO_SENHA_OK


class NotificacoesClient:
    """`contracts/notificacoes.openapi.yaml`, operação `obterResumo` — leitura pura.

    Lei do assunto: `docs/decisoes/DECISAO-fase-4-do-sininho.md` (Escolha 1) e a
    Fase 5 de `docs/notificacoes/PLANO-MESTRE.md` — **falha ABERTA, sem
    exceção**: *"notificações fora do ar ⇒ o site mostra o nome sem sino e a
    página abre normal"*. Cópia peça por peça do padrão de
    `IdentidadeClient.obter_sessao` (Lei 7 — copia-se o PADRÃO, nunca o
    arquivo): mesma forma de ler config, mesmo timeout curto, mesma separação
    entre `httpx.HTTPError` e `ValueError` no `.json()`.

    Auth: Bearer estático do par `funil→notificacoes`
    (`services/notificacoes/apps/core/auth.py`, `TOKENS_ACEITOS_FUNIL` do lado
    de lá) — o MESMO mecanismo de par que `IdentidadeClient` já usa.
    """

    TIMEOUT = 2.0

    def _configuracao(self) -> "tuple[str, str] | None":
        """Ver o comentário gêmeo em `IdentidadeClient._configuracao` — a mesma
        razão de ser, a mesma forma: `.get()`, nunca `os.environ[...]`, lido NO
        PONTO DE USO. Falta de config é MAIS provável que falha de rede (basta
        uma variável não colada no servidor) e não pode furar o fail-open
        (RETROSPECTIVA-FASE-D §1/§4)."""
        base = (os.environ.get("NOTIFICACOES_API_URL") or "").strip().rstrip("/")
        token = (os.environ.get("NOTIFICACOES_API_TOKEN") or "").strip()
        return (base, token) if base and token else None

    def obter_resumo(self, destinatario_id: str, site_id: str) -> "int | None":
        """Quantos avisos não lidos esta pessoa tem NESTE site, ou `None`.

        `None` é o sinal de "não sei" — quem chama (o sino) não desenha nada.
        É DIFERENTE de `0`, que é "perguntei e a resposta é zero". Confundir
        os dois transformaria uma `notificacoes` fora do ar num "sem avisos"
        mentiroso — a mesma família do bug mais caro da Fase D (*2xx não é
        sucesso*: o corpo tem de descrever o que foi pedido, ou é erro).
        """
        config = self._configuracao()
        if config is None:
            # Nem tenta a rede — mesmo raciocínio de `IdentidadeClient`: sem
            # endereço ou token não há pergunta a fazer, e esperar 2s de
            # timeout para descobrir isso atrasaria toda página do site.
            logger.error(
                "resumo: NOTIFICACOES_API_URL/NOTIFICACOES_API_TOKEN ausentes "
                "no env desta célula — sino não aparece"
            )
            return None
        base, token = config

        try:
            r = http().get(
                f"{base}/resumo",
                params={"destinatario_id": destinatario_id, "site_id": site_id},
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("resumo: não deu para perguntar à notificacoes: %s", erro)
            return None

        if r.status_code != 200:
            logger.error("resumo: a notificacoes respondeu HTTP %s", r.status_code)
            return None

        try:
            corpo = r.json()
        except ValueError as erro:
            # `json.JSONDecodeError` é `ValueError`, NÃO `httpx.HTTPError` — a
            # mesma distinção que furou o fail-open na Fase D se ficasse fora
            # deste `try`.
            logger.error("resumo: a notificacoes respondeu fora do contrato: %s", erro)
            return None

        if not isinstance(corpo, dict):
            return None
        valor = corpo.get("nao_lidas")
        # O contrato promete inteiro ≥0 (`nao_lidas: {type: integer, minimum:
        # 0}`). `bool` é subclasse de `int` em Python — excluí-lo explicitamente
        # evita que um `true`/`false` fora do contrato vire "1 aviso"/"0 avisos"
        # por acidente de tipagem. Fora do contrato é tratado como "não sei",
        # nunca como um número adivinhado.
        if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
            return None
        return valor

    # -----------------------------------------------------------------------
    # O aviso na tela do celular (Fase 7, 31/08/2026) — as duas ESCRITAS
    # -----------------------------------------------------------------------
    # Ao contrário do `obter_resumo` acima, estas duas não são leitura de
    # enfeite: quem chama é a pessoa apertando um botão, e ela precisa saber se
    # deu certo. Continuam sem derrubar página nenhuma (devolvem `False` em vez
    # de levantar), mas o `False` VIAJA até a tela, que diz que não deu.
    def inscrever_aparelho(
        self, *, destinatario_id: str, site_id: str, inscricao: dict
    ) -> bool:
        """`inscreverAparelhoParaPush`. `inscricao` é o que o navegador deu:
        `endpoint`, `p256dh` e `auth`, repassados sem interpretação — são
        opacos para esta célula, e é assim que devem continuar."""
        return self._escrever(
            "post",
            "/inscricoes-push",
            {
                "destinatario_id": destinatario_id,
                "site_id": site_id,
                "endpoint": inscricao["endpoint"],
                "p256dh": inscricao["p256dh"],
                "auth": inscricao["auth"],
            },
        )

    def esquecer_aparelho(self, *, site_id: str, endpoint: str) -> bool:
        """`cancelarInscricaoDeAparelho`. Não manda `destinatario_id` porque o
        contrato não o pede: desligar os avisos de um aparelho acontece
        justamente quando pode não haver mais sessão viva."""
        return self._escrever(
            "delete", "/inscricoes-push", {"site_id": site_id, "endpoint": endpoint}
        )

    def _escrever(self, metodo: str, caminho: str, corpo: dict) -> bool:
        config = self._configuracao()
        if config is None:
            logger.error(
                "%s: NOTIFICACOES_API_URL/NOTIFICACOES_API_TOKEN ausentes no env "
                "desta célula — o aviso no celular não pode ser ligado",
                caminho,
            )
            return False
        base, token = config
        try:
            r = http().request(
                metodo.upper(),
                f"{base}{caminho}",
                json=corpo,
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("%s: não deu para falar com a notificacoes: %s", caminho, erro)
            return False
        if r.status_code != 200:
            logger.error("%s: a notificacoes respondeu HTTP %s", caminho, r.status_code)
            return False
        return True


class AlunosClient:
    """`contracts/alunos.openapi.yaml` — em que categoria a pessoa está, e o
    pedido de entrada de quem ainda não é.

    `situacao_de` é somente leitura e **fail-OPEN**: qualquer falha devolve
    `None`, que o chamador trata como `cadastrado`. É a mesma lei do
    `IdentidadeClient` acima e pelo mesmo motivo — esta resposta decide o que
    a HOME mostra, nunca o que alguém pode fazer. A Caixa continua conferindo
    matrícula na entrada dela; esconder um botão nunca protegeu nada, e
    mostrá-lo nunca liberou nada (`DECISAO-categorias-de-usuario` §6).

    `criar_pre_matricula` é diferente por natureza: é uma ESCRITA que a
    página de cadastro precisa ver confirmada, então ela é **fail-CLOSED** —
    ver o docstring do método.
    """

    # Mesmo orçamento da sessão, e pelo mesmo motivo: isto está no caminho de
    # alguém esperando a home abrir. Estourou ⇒ a pessoa vê a home de quem
    # ainda não pediu nada, que é o pior caso aceitável.
    TIMEOUT = 2.0

    def _configuracao(self) -> "tuple[str, str] | None":
        """Endereço e token do par, lidos NO PONTO DE USO (`armadilhas/097`).

        Enquanto `infra/provisionar-pares-de-categorias.sh` não rodar na VPS,
        estas variáveis não existem — e este é um caminho NORMAL, não um erro:
        a home volta a se comportar como antes desta mudança.
        """
        base = (os.environ.get("ALUNOS_API_URL") or "").strip().rstrip("/")
        token = (os.environ.get("ALUNOS_API_TOKEN") or "").strip()
        return (base, token) if base and token else None

    def situacao_de(self, email: str) -> "dict | None":
        """Em que categoria esta pessoa está, ou `None` se não deu para saber.

        **Nunca levanta.** Quem chama está montando a home de alguém.
        """
        config = self._configuracao()
        if config is None:
            logger.info(
                "categoria: ALUNOS_API_URL/ALUNOS_API_TOKEN ausentes no env "
                "desta célula — a home trata todo mundo como cadastrado"
            )
            return None
        base, token = config

        try:
            r = http().get(
                f"{base}/alunos/{email}/situacao",
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("categoria: não deu para perguntar à alunos: %s", erro)
            return None

        if r.status_code != 200:
            logger.error("categoria: a alunos respondeu HTTP %s", r.status_code)
            return None

        try:
            corpo = r.json()
        except ValueError as erro:
            # *Status 2xx não é sucesso* (RETROSPECTIVA §4). Fora deste `try`,
            # `json.JSONDecodeError` furaria o fail-open e derrubaria a home.
            logger.error("categoria: a alunos respondeu fora do contrato: %s", erro)
            return None

        if not isinstance(corpo, dict) or not corpo.get("categoria"):
            logger.error("categoria: a alunos respondeu um corpo fora do contrato")
            return None
        return corpo

    # Os três desfechos possíveis de `criar_pre_matricula` — nenhum é `None`,
    # ao contrário de `situacao_de` acima. Esta é uma ESCRITA que a página de
    # cadastro espera ver confirmada: quem preencheu o formulário não pode
    # receber um "recebemos" educado quando o pedido nunca chegou à fila do
    # mantenedor.
    RESULTADO_NA_FILA = "na_fila"
    RESULTADO_JA_TEM_MATRICULA = "ja_tem_matricula"
    RESULTADO_FALHOU = "falhou"

    def criar_pre_matricula(
        self, *, site_id: str, email: str, nome_completo: str, whatsapp: str
    ) -> str:
        """`createPreEnrollment` — a pessoa pede entrada e fica AGUARDANDO.

        Mesma porta que o `admin` (cadastro à mão) e a `sugestoes` (pedido de
        entrada de quem já logou com o Google) já usam — esta célula só ganha
        um terceiro chamador do mesmo endpoint congelado, nunca contrato novo.

        `RESULTADO_NA_FILA`: o contrato responde 201 na primeira vez e 200 no
        reenvio (`entrar_na_fila` do lado de lá é idempotente por e-mail);
        para quem preencheu o formulário os dois significam a mesma coisa — o
        pedido está registrado.
        `RESULTADO_JA_TEM_MATRICULA`: 409, este e-mail já é aluno (ou já foi,
        e o reembolso tirou o acesso — a porta não distingue os dois casos).
        `RESULTADO_FALHOU`: config ausente, rede fora, ou resposta fora do
        contrato — "não consegui registrar" nunca pode virar "registrei"
        (RETROSPECTIVA-FASE-D §1: 2xx não é sucesso).
        """
        config = self._configuracao()
        if config is None:
            logger.error(
                "pre-matricula: ALUNOS_API_URL/ALUNOS_API_TOKEN ausentes no "
                "env desta célula — o pedido de entrada não foi enviado"
            )
            return self.RESULTADO_FALHOU
        base, token = config

        try:
            r = http().post(
                f"{base}/pre-matriculas",
                json={
                    "site_id": site_id,
                    "email": email,
                    "nome_completo": nome_completo,
                    "whatsapp": whatsapp,
                },
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("pre-matricula: não deu para falar com a alunos: %s", erro)
            return self.RESULTADO_FALHOU

        if r.status_code in (200, 201):
            return self.RESULTADO_NA_FILA
        if r.status_code == 409:
            return self.RESULTADO_JA_TEM_MATRICULA
        logger.error("pre-matricula: a alunos respondeu HTTP %s", r.status_code)
        return self.RESULTADO_FALHOU
