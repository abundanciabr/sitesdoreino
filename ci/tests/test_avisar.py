"""infra/avisar.py: o aviso ao mantenedor por e-mail, com SMTP falso (nenhuma conexão real)."""

from __future__ import annotations

import importlib.util
import io
import smtplib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("avisar_sob_teste", ROOT / "infra" / "avisar.py")
avisar = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = avisar
spec.loader.exec_module(avisar)

SENHA = "xsmtpsib-SEGREDO-que-nunca-pode-aparecer"
USUARIO = "login-smtp@exemplo.test"
AGORA = datetime(2026, 10, 1, 11, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def sem_rede(monkeypatch):
    def proibido(*args, **kwargs):
        raise AssertionError("o teste tentou abrir conexão de verdade")

    monkeypatch.setattr(smtplib.SMTP, "__init__", proibido)
    monkeypatch.setattr(smtplib.SMTP_SSL, "__init__", proibido)


@pytest.fixture
def plataforma(tmp_path):
    raiz = tmp_path / "plataforma"
    (raiz / "env").mkdir(parents=True)
    (raiz / "env" / "mensageria.env").write_text(
        "DJANGO_SECRET_KEY=outro-segredo\n"
        "SMTP_HOST=smtp.exemplo.test\nSMTP_PORT=587\n"
        f"SMTP_USER={USUARIO}\nSMTP_PASSWORD={SENHA}\nSMTP_FROM=escola@exemplo.test\n"
        "WHATSAPP_GATEWAY_URL=\n",
        encoding="utf-8",
    )
    (raiz / "env" / "admin.env").write_text("ADMIN_EMAILS=dono@exemplo.test\n", encoding="utf-8")
    return raiz


class SmtpFalso:
    """O que `conectar` devolve: já autenticado, só registra o que lhe mandaram."""

    def __init__(self, falha=None, recusados=None):
        self.enviadas, self.noops, self.falha, self.recusados = [], 0, falha, recusados or {}
        self.conectou_com = None

    def __call__(self, cfg):
        self.conectou_com = cfg
        return self

    def __enter__(self):
        return self

    def __exit__(self, *erro):
        return False

    def send_message(self, mensagem):
        if self.falha:
            raise self.falha
        self.enviadas.append(mensagem)
        return self.recusados

    def noop(self):
        self.noops += 1
        return (250, b"ok")


def amb(plataforma, **extra):
    return {"PLATAFORMA_DIR": str(plataforma), "AVISAR_ESTADO": str(plataforma / "estado.json"), **extra}


# --------------------------------------------------------------------------- o env


def test_ler_env_no_formato_do_compose(tmp_path):
    caminho = tmp_path / "exemplo.env"
    caminho.write_text(
        "# comentário\n\nA=1\nexport B=dois\nC='com espaço'\nD=\"entre aspas\"\n"
        "E=valor # comentário no fim\nF=tem#cerquilha\nG=primeiro\nG=ultimo\nsem-igual\n9X=ignorada\n",
        encoding="utf-8",
    )
    assert avisar.ler_env(caminho) == {
        "A": "1", "B": "dois", "C": "com espaço", "D": "entre aspas",
        "E": "valor", "F": "tem#cerquilha", "G": "ultimo",
    }


def test_configuracao_usa_o_smtp_da_mensageria_e_o_admin_como_destino(plataforma):
    cfg = avisar.configuracao(plataforma, {})
    assert (cfg.host, cfg.porta, cfg.usuario, cfg.remetente) == (
        "smtp.exemplo.test", 587, USUARIO, "escola@exemplo.test"
    )
    assert cfg.destinatarios == ("dono@exemplo.test",)


def test_destinatarios_varios_invalidos_e_repetidos_sao_filtrados(plataforma):
    (plataforma / "env" / "admin.env").write_text(
        "ADMIN_EMAILS=A@x.test; lixo, a@x.test  b@y.test <c@z.test>\n", encoding="utf-8"
    )
    assert avisar.configuracao(plataforma, {}).destinatarios == ("a@x.test", "b@y.test")


def test_sem_admin_emails_cai_na_lista_da_identidade_e_a_variavel_manda_mais(plataforma):
    (plataforma / "env" / "admin.env").write_text("ADMIN_EMAILS=\n", encoding="utf-8")
    (plataforma / "env" / "identidade.env").write_text("IDENTIDADE_STAFF_EMAILS=staff@x.test\n", encoding="utf-8")
    assert avisar.configuracao(plataforma, {}).destinatarios == ("staff@x.test",)
    assert avisar.configuracao(plataforma, {"AVISAR_PARA": "so-eu@x.test"}).destinatarios == ("so-eu@x.test",)


def test_falta_de_configuracao_diz_o_nome_da_chave_e_nunca_o_valor(plataforma):
    (plataforma / "env" / "mensageria.env").write_text(
        f"SMTP_HOST=smtp.exemplo.test\nSMTP_PASSWORD={SENHA}\n", encoding="utf-8"
    )
    with pytest.raises(avisar.AvisoFalhou) as erro:
        avisar.configuracao(plataforma, {})
    texto = str(erro.value)
    assert "SMTP_USER" in texto and "SMTP_FROM" in texto and "SMTP_HOST" not in texto
    assert SENHA not in texto


def test_sem_destinatario_ou_sem_arquivo_falha_com_motivo(plataforma, tmp_path):
    (plataforma / "env" / "admin.env").write_text("OUTRA=1\n", encoding="utf-8")
    with pytest.raises(avisar.AvisoFalhou, match="nenhum destinatário"):
        avisar.configuracao(plataforma, {})
    with pytest.raises(avisar.AvisoFalhou, match="não achei"):
        avisar.configuracao(tmp_path / "nao-existe", {})


# --------------------------------------------------------------------------- o envio


def test_avisar_monta_a_carta_e_manda_uma_vez(plataforma):
    smtp = SmtpFalso()
    resultado = avisar.avisar(
        "O cadeado venceu.\nVeja o log.", ambiente=amb(plataforma), conectar=smtp, agora=AGORA
    )
    assert resultado == "enviado"
    (carta,) = smtp.enviadas
    assert carta["From"] == "escola@exemplo.test" and carta["To"] == "dono@exemplo.test"
    assert carta["Subject"] == "[sitesdoreino] O cadeado venceu."
    corpo = carta.get_content()
    assert "O cadeado venceu.\nVeja o log." in corpo and "infra/avisar.py" in corpo
    assert SENHA not in carta.as_string() and USUARIO not in carta.as_string()


def test_assunto_proprio_e_sem_quebra_de_linha_para_nao_injetar_cabecalho(plataforma):
    smtp = SmtpFalso()
    avisar.avisar(
        "texto", "Site fora\r\nBcc: alguem@x.test", ambiente=amb(plataforma), conectar=smtp, agora=AGORA
    )
    (carta,) = smtp.enviadas
    assert carta["Bcc"] is None and "\n" not in carta["Subject"] and "\r" not in carta["Subject"]
    assert carta["Subject"].startswith("[sitesdoreino] Site fora")


def test_texto_vazio_nao_manda_e_texto_enorme_e_cortado(plataforma):
    smtp = SmtpFalso()
    with pytest.raises(avisar.AvisoFalhou, match="vazio"):
        avisar.avisar("   \n", ambiente=amb(plataforma), conectar=smtp)
    avisar.avisar("x" * 50000, ambiente=amb(plataforma), conectar=smtp, agora=AGORA)
    assert "cortado" in smtp.enviadas[0].get_content()
    assert len(smtp.enviadas[0].get_content()) < 21000


def test_falha_do_provedor_levanta_sem_vazar_senha_nem_login(plataforma):
    erro = smtplib.SMTPAuthenticationError(535, f"recusou {USUARIO} com {SENHA}".encode())
    with pytest.raises(avisar.AvisoFalhou) as falhou:
        avisar.avisar("oi", ambiente=amb(plataforma), conectar=SmtpFalso(falha=erro), agora=AGORA)
    texto = str(falhou.value)
    assert "SMTPAuthenticationError" in texto and "***" in texto
    assert SENHA not in texto and USUARIO not in texto


def test_falha_de_rede_tambem_vira_aviso_falhou(plataforma):
    with pytest.raises(avisar.AvisoFalhou, match="TimeoutError"):
        avisar.avisar("oi", ambiente=amb(plataforma), conectar=SmtpFalso(falha=TimeoutError("lento")))


def test_destinatario_recusado_nao_e_sucesso(plataforma):
    smtp = SmtpFalso(recusados={"dono@exemplo.test": (550, b"nao")})
    with pytest.raises(avisar.AvisoFalhou, match="recusou 1"):
        avisar.avisar("oi", ambiente=amb(plataforma), conectar=smtp, agora=AGORA)


# --------------------------------------------------------------------------- não repetir


def test_mesma_chave_dentro_do_prazo_e_silenciada_e_depois_do_prazo_sai_de_novo(plataforma):
    smtp = SmtpFalso()
    ambiente = amb(plataforma)

    def chamar(quando):
        return avisar.avisar(
            "cadeado", chave="cadeado-vermelho", a_cada_horas=72, ambiente=ambiente, conectar=smtp, agora=quando
        )

    assert chamar(AGORA) == "enviado"
    assert chamar(AGORA + timedelta(hours=71)) == "silenciado"
    assert chamar(AGORA + timedelta(hours=73)) == "enviado"
    assert len(smtp.enviadas) == 2


def test_chaves_diferentes_nao_se_silenciam_e_falha_nao_grava_o_silencio(plataforma):
    smtp = SmtpFalso()
    ambiente = amb(plataforma)
    avisar.avisar("a", chave="a", a_cada_horas=24, ambiente=ambiente, conectar=smtp, agora=AGORA)
    assert avisar.avisar("b", chave="b", a_cada_horas=24, ambiente=ambiente, conectar=smtp, agora=AGORA) == "enviado"
    quebrado = SmtpFalso(falha=OSError("fora do ar"))
    with pytest.raises(avisar.AvisoFalhou):
        avisar.avisar("c", chave="c", a_cada_horas=24, ambiente=ambiente, conectar=quebrado, agora=AGORA)
    assert avisar.avisar("c", chave="c", a_cada_horas=24, ambiente=ambiente, conectar=smtp, agora=AGORA) == "enviado"


def test_sem_chave_nunca_silencia(plataforma):
    smtp = SmtpFalso()
    for _ in range(2):
        avisar.avisar("igual", ambiente=amb(plataforma), conectar=smtp, agora=AGORA)
    assert len(smtp.enviadas) == 2


# --------------------------------------------------------------------------- verificar e a conexão


def test_verificar_entra_no_smtp_e_nao_manda_carta(plataforma):
    smtp = SmtpFalso()
    resumo = avisar.verificar(plataforma, {}, conectar=smtp)
    assert smtp.enviadas == [] and smtp.noops == 1
    assert "smtp.exemplo.test:587" in resumo and "d***@exemplo.test" in resumo
    assert "dono@exemplo.test" not in resumo and SENHA not in resumo and USUARIO not in resumo


def test_verificar_com_login_recusado_diz_que_falhou_sem_segredo(plataforma):
    class Recusa(SmtpFalso):
        def noop(self):
            raise smtplib.SMTPServerDisconnected(f"caiu depois de {SENHA}")

    with pytest.raises(avisar.AvisoFalhou) as erro:
        avisar.verificar(plataforma, {}, conectar=Recusa())
    assert SENHA not in str(erro.value)


class SmtpDeVerdadeFalso:
    instancias = []

    def __init__(self, host, porta, timeout=None, context=None):
        self.host, self.porta, self.context, self.eventos = host, porta, context, []
        SmtpDeVerdadeFalso.instancias.append(self)

    def ehlo(self):
        self.eventos.append("ehlo")

    def starttls(self, context=None):
        self.eventos.append("starttls")

    def login(self, usuario, senha):
        self.eventos.append(("login", usuario, senha))

    def close(self):
        self.eventos.append("close")


def test_conectar_587_faz_starttls_antes_do_login(plataforma, monkeypatch):
    SmtpDeVerdadeFalso.instancias = []
    monkeypatch.setattr(smtplib, "SMTP", SmtpDeVerdadeFalso)
    cliente = avisar.conectar_smtp(avisar.configuracao(plataforma, {}))
    assert cliente.eventos == ["ehlo", "starttls", "ehlo", ("login", USUARIO, SENHA)]
    assert (cliente.host, cliente.porta) == ("smtp.exemplo.test", 587)


def test_conectar_465_usa_ssl_direto_e_login_recusado_fecha_a_conexao(plataforma, monkeypatch):
    (plataforma / "env" / "mensageria.env").write_text(
        (plataforma / "env" / "mensageria.env").read_text(encoding="utf-8") + "SMTP_PORT=465\n", encoding="utf-8"
    )
    monkeypatch.setattr(smtplib, "SMTP_SSL", SmtpDeVerdadeFalso)
    cliente = avisar.conectar_smtp(avisar.configuracao(plataforma, {}))
    assert cliente.eventos == [("login", USUARIO, SENHA)] and cliente.porta == 465

    class Recusa(SmtpDeVerdadeFalso):
        def login(self, usuario, senha):
            raise smtplib.SMTPAuthenticationError(535, b"no")

    monkeypatch.setattr(smtplib, "SMTP_SSL", Recusa)
    with pytest.raises(smtplib.SMTPAuthenticationError):
        avisar.conectar_smtp(avisar.configuracao(plataforma, {}))
    assert "close" in SmtpDeVerdadeFalso.instancias[-1].eventos


# --------------------------------------------------------------------------- a linha de comando


def test_cli_manda_o_texto_e_sai_zero(plataforma, capsys):
    smtp = SmtpFalso()
    codigo = avisar.main(
        ["cadeado vermelho", "--assunto", "Teste"], raiz=plataforma, ambiente=amb(plataforma), conectar=smtp
    )
    assert codigo == 0 and "avisar: enviado" in capsys.readouterr().out
    assert smtp.enviadas[0]["Subject"] == "[sitesdoreino] Teste"


def test_cli_le_o_texto_da_entrada_padrao(plataforma, monkeypatch):
    monkeypatch.setattr(avisar.sys, "stdin", io.StringIO("vindo do cron\n"))
    smtp = SmtpFalso()
    assert avisar.main(["-"], raiz=plataforma, ambiente=amb(plataforma), conectar=smtp) == 0
    assert "vindo do cron" in smtp.enviadas[0].get_content()


def test_cli_falha_com_codigo_1_e_mensagem_no_stderr(plataforma, capsys):
    smtp = SmtpFalso(falha=OSError("fora"))
    assert avisar.main(["oi"], raiz=plataforma, ambiente=amb(plataforma), conectar=smtp) == 1
    captura = capsys.readouterr()
    assert "FALHOU" in captura.err and SENHA not in captura.err + captura.out


def test_cli_verificar_e_silenciado_e_sem_texto_sao_tratados(plataforma, capsys):
    smtp = SmtpFalso()
    assert avisar.main(["--verificar"], raiz=plataforma, ambiente=amb(plataforma), conectar=smtp) == 0
    assert "canal ok" in capsys.readouterr().out and smtp.enviadas == []
    with pytest.raises(SystemExit) as saida:
        avisar.main([], raiz=plataforma, ambiente=amb(plataforma), conectar=smtp)
    assert saida.value.code == 2
