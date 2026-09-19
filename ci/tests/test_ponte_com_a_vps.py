"""A conta `ponte` abre UMA porta, e nada aqui pode trancar a casa para fora.

Este arquivo mede as três coisas que custariam caro em silêncio:

1. a chave autorizada deixar de ser a do PC do mantenedor, o que apontaria o
   cano para outra máquina sem quebrar nada nem ficar vermelho;
2. o provisionador ganhar um `restart`, editar o `sshd_config` principal ou
   recarregar antes de medir, que é como se perde o acesso à VPS sem volta;
3. a ponte, que é um recurso a mais, passar a segurar a sincronização da
   infraestrutura inteira. Isso não é hipótese: aconteceu em 16/09/2026, no
   run 35047777635 do `deploy-infra`, com `sudo: a password is required`
   derrubando compose e Traefik por causa de uma ponte que nem tinha sido
   ligada ainda.

O comportamento do `sshd` diante desta configuração foi medido em 16/09/2026
num `ubuntu:24.04` com o `sshd_config` real da VPS reproduzido, rodando o
próprio `infra/provisionar-usuario-ponte.sh`.
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PROVISIONADOR = RAIZ / "infra" / "provisionar-usuario-ponte.sh"
INSTALADOR = RAIZ / "infra" / "instalar-provisionador-usuario-ponte.sh"
SINCRONIZADOR = RAIZ / "infra" / "sincronizar-infra-na-vps.sh"
WORKFLOW = RAIZ / ".github" / "workflows" / "deploy-infra.yml"

CAMINHO_CONGELADO = "/usr/local/sbin/provisionar-usuario-ponte"

# A chave que abre a ponte, e a única. Trocá-la é a mudança mais silenciosa que
# este lote admite: nada quebra, nada fica vermelho, e o acesso passa a ser de
# outra máquina.
CHAVE_DESTE_PC = (
    "ssh-ed25519 "
    "AAAAC3NzaC1lZDI1NTE5AAAAIDFmhu8QkiIPwN0gqmYSmSrN9E2Wr8PdAk2N3qglquu6 "
    "davi@DESKTOP-V8F32JA"
)


def so_codigo(caminho: Path) -> str:
    """O roteiro sem os comentários: medir ordem no texto inteiro mede a prosa.

    Os cabeçalhos desta casa citam os próprios comandos ao explicar por que
    existem, então `texto.index("systemctl reload")` acharia a explicação, e não
    a linha que recarrega.
    """
    return "\n".join(
        linha
        for linha in caminho.read_text(encoding="utf-8").splitlines()
        if not linha.lstrip().startswith("#")
    )


def bloco_do_sshd() -> str:
    """O `Match` que o provisionador escreve, com as variáveis já resolvidas.

    Medir o texto do roteiro procurando `PermitOpen 127.0.0.1:8443` amarraria o
    teste à forma de escrever, e não ao que o `sshd` recebe. Aqui a atribuição é
    lida e expandida, então trocar um literal por variável não quebra o teste, e
    trocar o DESTINO quebra.
    """
    codigo = so_codigo(PROVISIONADOR)
    valores = dict(re.findall(r"^(USUARIO|DESTINO_UNICO)=[\"']?([^\"'\n]+)", codigo, re.M))
    bloco = re.search(r'CONFIG_DESEJADA="(.*?)"\n', codigo, re.S).group(1)
    for nome, valor in valores.items():
        bloco = bloco.replace(f"${nome}", valor)
    return bloco


def test_a_chave_da_ponte_e_a_deste_pc_e_so_ela():
    codigo = so_codigo(PROVISIONADOR)
    assert CHAVE_DESTE_PC in codigo, (
        "a chave autorizada da ponte deixou de ser a do PC do mantenedor"
    )
    assert codigo.count("ssh-ed25519 ") == 1, (
        "o provisionador tem de autorizar exatamente UMA chave pública"
    )


def test_o_sshd_concede_a_ponte_uma_porta_e_nada_mais():
    bloco = bloco_do_sshd()
    assert bloco.startswith("Match User ponte"), (
        "sem o `Match User ponte` na primeira linha, a restrição valeria para todos"
    )
    assert re.findall(r"^\s*PermitOpen (.+)$", bloco, re.M) == ["127.0.0.1:8443"], (
        "a ponte tem UM destino, e qualquer outro é recusa"
    )
    for diretiva in (
        "AllowTcpForwarding local",
        "PermitTTY no",
        "X11Forwarding no",
        "AllowAgentForwarding no",
        "PermitTunnel no",
        "PasswordAuthentication no",
        "AuthenticationMethods publickey",
        # O `Subsystem sftp` é executado pelo próprio sshd, e não pelo shell do
        # usuário: sem esta linha o `/usr/sbin/nologin` não recusaria o SFTP.
        "ForceCommand /usr/bin/false",
    ):
        assert re.search(rf"^\s*{re.escape(diretiva)}$", bloco, re.M), (
            f"o bloco da ponte perdeu `{diretiva}`"
        )


def test_a_chave_carrega_a_mesma_restricao_que_o_sshd():
    """Duas travas independentes: um erro de digitação numa não abre a porta."""
    codigo = so_codigo(PROVISIONADOR)
    opcoes = re.search(r'CHAVES_DESEJADAS="(.*?) \$CHAVE_AUTORIZADA"', codigo).group(1)
    assert opcoes.startswith("restrict,"), (
        "sem `restrict` a chave herda tudo o que o sshd não tiver proibido"
    )
    assert 'permitopen=\\"$DESTINO_UNICO\\"' in opcoes, (
        "a chave tem de prender o mesmo destino único do bloco do sshd"
    )
    assert "no-port-forwarding" not in opcoes, (
        "`no-port-forwarding` mataria a única coisa que a ponte precisa fazer"
    )


def test_o_provisionador_nunca_reinicia_o_sshd_nem_edita_o_arquivo_principal():
    codigo = so_codigo(PROVISIONADOR)
    # O que se proíbe é EXECUTAR o restart. A mensagem de último recurso cita o
    # comando para o mantenedor digitar no console do provedor, e citar não é
    # executar: por isso o texto entre aspas sai antes da medição.
    executavel = re.sub(r'"[^"]*"', '""', codigo)
    assert "systemctl restart" not in executavel, (
        "restart mata a sessão da esteira, que é o único caminho de volta"
    )
    tocados = re.findall(r"/etc/ssh/sshd_config[^\s\"']*", codigo)
    assert tocados, "o provisionador precisa escrever o drop-in do sshd"
    for caminho in tocados:
        assert caminho.startswith("/etc/ssh/sshd_config.d/"), (
            f"{caminho} não está em sshd_config.d/: a mudança é um arquivo de "
            "acréscimo, nunca uma edição do arquivo principal"
        )


def test_o_provisionador_mede_o_deploy_antes_de_recarregar():
    """Sem comparar a configuração efetiva do deploy, o reload é uma aposta."""
    codigo = so_codigo(PROVISIONADOR)
    assert codigo.index("DEPLOY_ANTES=") < codigo.index("systemctl reload"), (
        "a fotografia do deploy tem de ser tirada antes de escrever e recarregar"
    )
    assert codigo.index("sshd -t") < codigo.index("systemctl reload"), (
        "`sshd -t` vem antes do reload, sempre"
    )
    assert codigo.index("systemctl reload") < codigo.index("o_sshd_atende"), (
        "a prova de vida só significa alguma coisa depois do reload"
    )


def test_a_ponte_nao_segura_a_sincronizacao_da_infraestrutura():
    """A queda medida no run 35047777635 não pode voltar."""
    codigo = so_codigo(SINCRONIZADOR)
    chamada = re.search(r"^\s*sudo -n .*$", codigo, re.M)
    assert chamada, "a esteira precisa chamar o provisionador congelado"
    guarda = re.search(r'^\s*if \[ -x "?\$PROVISIONADOR_DA_PONTE"? \]; then$', codigo, re.M)
    assert guarda and guarda.start() < chamada.start(), (
        "o `sudo -n` tem de estar atrás da guarda de existência: sem a regra de "
        "sudo instalada ele devolve `sudo: a password is required` e, sob "
        "`set -eu` e depois da sentinela SINCRONIZACAO-INICIADA, derruba a "
        "sincronização inteira sem repetição"
    )
    assert "instalar-provisionador-usuario-ponte.sh" in codigo, (
        "o log tem de dizer a linha exata que liga a ponte"
    )
    assert codigo.index("PROVISIONADOR_DA_PONTE=") < codigo.index("docker-compose.yml.new docker-compose.yml"), (
        "a ponte é reconciliada antes de qualquer troca, quando nada em uso mudou ainda"
    )


def test_o_deploy_so_executa_o_caminho_congelado_que_ele_nao_pode_alterar():
    codigo = so_codigo(INSTALADOR)
    assert f"deploy ALL=(root) NOPASSWD: {CAMINHO_CONGELADO}" in codigo.replace(
        "$DESTINO", CAMINHO_CONGELADO
    ), "a regra de sudo tem de nomear o caminho congelado"
    regra = codigo.split("NOPASSWD:")[1].splitlines()[0]
    assert "*" not in regra, (
        f"a regra do sudo {regra!r} tem coringa: isso é root irrestrito para o deploy"
    )
    assert "install -o root -g root -m 755" in codigo, (
        "o que roda como root não pode ser gravável pelo deploy"
    )
    assert CAMINHO_CONGELADO in so_codigo(SINCRONIZADOR), (
        "a esteira tem de executar a cópia congelada, nunca o arquivo que ela mesma acabou de receber"
    )


def test_a_regra_de_sudo_e_conferida_antes_de_entrar_em_sudoers_d():
    """Sudoers inválido em /etc/sudoers.d quebra o `sudo` da máquina inteira."""
    codigo = so_codigo(INSTALADOR)
    conferencia = codigo.index("visudo -cf")
    instalacao = codigo.index('install -o root -g root -m 440')
    assert conferencia < instalacao, (
        "conferir depois de escrever é descobrir o estrago com ele já feito"
    )
    assert "visudo -c " in codigo or "visudo -c\n" in codigo or "visudo -c >" in codigo, (
        "o conjunto INTEIRO do sudo também precisa continuar válido depois da regra nova"
    )


def test_o_pipeline_leva_os_dois_roteiros_para_a_vps():
    texto = WORKFLOW.read_text(encoding="utf-8")
    assert texto.count(
        "infra/provisionar-usuario-ponte.sh,infra/instalar-provisionador-usuario-ponte.sh"
    ) == 3, "as três tentativas do SCP têm de levar os dois roteiros"
