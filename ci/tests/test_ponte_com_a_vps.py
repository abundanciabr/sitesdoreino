from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
PROVISIONADOR = RAIZ / "infra" / "provisionar-usuario-ponte.sh"
INSTALADOR = RAIZ / "infra" / "instalar-provisionador-usuario-ponte.sh"
SINCRONIZADOR = RAIZ / "infra" / "sincronizar-infra-na-vps.sh"
WORKFLOW = RAIZ / ".github" / "workflows" / "deploy-infra.yml"


def test_provisionador_restringe_ponte_a_uma_entrada_local():
    texto = PROVISIONADOR.read_text(encoding="utf-8")
    assert "PermitOpen 127.0.0.1:8443" in texto
    assert "AllowTcpForwarding local" in texto
    assert "PermitTTY no" in texto
    assert "AllowAgentForwarding no" in texto
    assert "PermitTunnel no" in texto
    assert "ForceCommand /usr/bin/false" in texto
    assert "Match all" in texto
    assert "PasswordAuthentication no" in texto
    assert "sshd -t" in texto
    assert "systemctl reload sshd" in texto
    assert "systemctl restart" not in texto
    assert "no-port-forwarding" not in texto


def test_instalador_entrega_sudo_apenas_para_binario_root():
    texto = INSTALADOR.read_text(encoding="utf-8")
    assert "install -o root -g root -m 755" in texto
    assert "deploy ALL=(root) NOPASSWD: /usr/local/sbin/provisionar-usuario-ponte" in texto
    assert "visudo -cf" in texto
    assert "sudoers" in texto


def test_pipeline_nao_recebe_script_root_controlavel_por_deploy():
    texto = WORKFLOW.read_text(encoding="utf-8")
    assert texto.count("infra/provisionar-usuario-ponte.sh,infra/instalar-provisionador-usuario-ponte.sh") == 3
    sincronizador = SINCRONIZADOR.read_text(encoding="utf-8")
    assert "sudo -n /usr/local/sbin/provisionar-usuario-ponte" in sincronizador
    assert "sudo -n bash provisionar-usuario-ponte.sh" not in sincronizador
