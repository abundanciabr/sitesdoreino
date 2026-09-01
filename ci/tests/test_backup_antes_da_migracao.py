"""A cópia de segurança do banco acontece ANTES da migração, e a ordem é a feature.

TAR-003 (01/09/2026), recomendação O15 do `PLANO-MESTRE-ROBOS-SEM-COLISAO.md`.

**O fato que decide o desenho:** as migrações do Django não rodam em passo nenhum
do deploy. Elas rodam no BOOT de cada contêiner (todo `services/*/Dockerfile`
termina em `migrate --noinput && uvicorn ...`). Quando o `docker compose up -d`
do `infra/deploy-celula-na-vps.sh` devolve, a migração JÁ ACONTECEU. Um backup
depois dele é um backup do estrago, e vale zero. Por isso o que estes guardas
medem não é "existe uma linha de backup", e sim **onde ela está em relação ao
`up -d`** — uma asserção de existência passaria com o bloco inteiro movido para
o fim do arquivo, que é exatamente a mutação que destrói a funcionalidade.

**E por que o backup mora DENTRO do script de deploy, e não num `.sh` só dele:**
o `deploy-celula.yml` não copia arquivo nenhum para a VPS. A `appleboy/ssh-action`
recebe `script_path: infra/deploy-celula-na-vps.sh` e envia o CONTEÚDO desse
arquivo pelo canal SSH; o `deploy-infra` copia uma lista fixa que não inclui `.sh`
avulso. Um `infra/backup-antes-da-migracao.sh` separado não existiria em
`/opt/plataforma` na hora do deploy e, como o backup é fail-closed, o deploy
pararia em toda entrega. O `test_o_workflow_ainda_envia_este_arquivo` abaixo é o
alarme que dispara se essa premissa mudar.

-------------------------------------------------------------------------------
O QUE ESTA SUÍTE **NÃO** PROVA, declarado em vez de fingido (INV-CI01)
-------------------------------------------------------------------------------
Nada aqui prova que um dump RESTAURA. Guarda estático não mede isso, e o job que
roda estes testes instala só `pytest` e `pyyaml`: não há Postgres, não há Docker
no lado certo, e o `pg_dump` do runner não é o do contêiner do banco.

A prova de ida e volta foi feita à mão em 01/09/2026, antes deste PR entrar,
contra uma plataforma de mentira (um `docker-compose.yml` de teste com um
`postgres:17` de verdade), rodando o `deploy-celula-na-vps.sh` INTEIRO:

  1. base `admin_db` com uma tabela `auditoria` e uma linha dentro;
  2. `CELULA=admin` + o script inteiro  -> `BACKUP-ANTES-DA-MIGRACAO: admin_db-20260901-210128Z.dump`
     impresso ANTES da subida dos contêineres, e `ENTREGA-CONCLUIDA` no fim;
  3. `DROP TABLE auditoria`  -> a tabela deixou de existir;
  4. `infra/restaurar-backup.sh <dump> --sim-eu-quero-sobrescrever`  -> `RESTAURACAO-CONCLUIDA`;
  5. `SELECT * FROM auditoria`  -> a linha de volta, idêntica.

Medido na mesma sessão, e é o que garante que o passo 2 não mente: um dump
cortado ao meio faz `pg_restore -l` sair 1 com "could not read from input file:
end of file". É essa conferência, no script, que impede um arquivo pela metade de
receber o nome final.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
DEPLOY = RAIZ / "infra" / "deploy-celula-na-vps.sh"
RESTAURADOR = RAIZ / "infra" / "restaurar-backup.sh"
WORKFLOW = RAIZ / ".github" / "workflows" / "deploy-celula.yml"


def linhas_de_codigo(caminho: Path) -> list[tuple[int, str]]:
    """As linhas que o shell EXECUTA: sem comentário e sem linha em branco.

    Despir os comentários não é zelo, é o que separa um guarda de uma decoração.
    Este arquivo explica o desenho em comentários longos, e vários deles citam
    `up -d` e `pg_dump` em prosa. Um guarda que contasse essas ocorrências
    continuaria verde com o bloco de backup movido para depois da subida dos
    contêineres, porque a prosa não se move junto.
    """
    saida = []
    for numero, linha in enumerate(
        caminho.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not linha.strip() or linha.lstrip().startswith("#"):
            continue
        saida.append((numero, linha))
    return saida


def indice_unico(linhas: list[tuple[int, str]], padrao: str, rotulo: str) -> int:
    """A posição da ÚNICA linha de código que casa com o padrão.

    Exigir unicidade é parte da medição: duas linhas de `docker compose up -d`
    fariam qualquer comparação de ordem virar loteria, e o teste diria "passou"
    apoiado na cópia certa enquanto a errada roda em produção.
    """
    achados = [i for i, (_, linha) in enumerate(linhas) if re.search(padrao, linha)]
    assert achados, f"não achei nenhuma linha de código com {rotulo} ({padrao!r})"
    assert len(achados) == 1, (
        f"esperava UMA linha de código com {rotulo}, achei {len(achados)}: "
        + ", ".join(f"linha {linhas[i][0]}" for i in achados)
    )
    return achados[0]


# ---------------------------------------------------------------------------
# (a) A ORDEM É A FEATURE
# ---------------------------------------------------------------------------
def test_o_dump_acontece_antes_da_subida_dos_conteineres():
    """A migração roda no boot do contêiner. Depois do `up -d` é tarde."""
    linhas = linhas_de_codigo(DEPLOY)
    i_dump = indice_unico(linhas, r"exec -T postgres pg_dump", "o comando pg_dump")
    i_up = indice_unico(linhas, r"docker compose up -d", "o docker compose up -d")

    assert i_dump < i_up, (
        "O pg_dump está na linha "
        f"{linhas[i_dump][0]} e o `docker compose up -d` na linha {linhas[i_up][0]}: "
        "a cópia de segurança acontece DEPOIS da subida dos contêineres.\n"
        "Como o `migrate` roda no boot da imagem (veja o CMD de qualquer "
        "services/*/Dockerfile), quando o `up -d` devolve o banco JÁ mudou — e um "
        "backup feito nesse ponto é um backup do estrago. Mova o bloco de volta "
        "para antes do `up -d`."
    )


def test_a_sentinela_do_backup_sai_antes_da_subida_dos_conteineres():
    """A evidência que a fila pediu para a TAR-003 é uma linha no log do run.

    Ela precisa aparecer ANTES da subida, e não só existir em algum lugar: é
    lendo essa ordem no log que alguém confirma, de fora, que a cópia antecedeu a
    migração.
    """
    linhas = linhas_de_codigo(DEPLOY)
    i_up = indice_unico(linhas, r"docker compose up -d", "o docker compose up -d")
    sentinelas = [
        i for i, (_, linha) in enumerate(linhas) if "BACKUP-ANTES-DA-MIGRACAO:" in linha
    ]
    assert sentinelas, (
        "sumiu a sentinela BACKUP-ANTES-DA-MIGRACAO do script de deploy — sem ela "
        "o log do run não prova que a cópia aconteceu, e a evidência da TAR-003 "
        "deixa de existir"
    )
    ultima = max(sentinelas)
    assert ultima < i_up, (
        f"a última linha BACKUP-ANTES-DA-MIGRACAO está na {linhas[ultima][0]}, "
        f"depois do `up -d` da linha {linhas[i_up][0]}"
    )


def test_a_ordem_interna_do_bloco_limpeza_espaco_dump():
    """Limpar, depois medir o disco, depois escrever. Nesta ordem, e por motivo.

    Medir o disco antes de aplicar a retenção faria o script recusar um deploy
    que caberia perfeitamente; escrever antes de medir é o dump truncado que
    mente no dia do desespero.
    """
    linhas = linhas_de_codigo(DEPLOY)
    i_limpeza = indice_unico(linhas, r"^\s*A_APAGAR=", "a limpeza dos dumps antigos")
    i_espaco = indice_unico(linhas, r"^\s*SAIDA_DO_DF=", "a medição do espaço livre")
    i_dump = indice_unico(linhas, r"exec -T postgres pg_dump", "o comando pg_dump")

    assert i_limpeza < i_espaco, (
        "o espaço em disco está sendo medido ANTES da limpeza das cópias antigas: "
        "assim o deploy pode ser recusado por falta de espaço que ele mesmo "
        "liberaria um instante depois"
    )
    assert i_espaco < i_dump, (
        "o dump está sendo escrito ANTES da conferência de espaço em disco. "
        "Disco cheio tem de virar uma mensagem clara, nunca um arquivo pela metade"
    )


def test_o_dump_so_ganha_o_nome_final_depois_de_provado():
    """Escreve em `.parcial`, confere que abre, e só então renomeia.

    O nome final nunca pode existir apontando para um arquivo incompleto: é o
    arquivo que alguém vai escolher no pior dia do projeto.
    """
    linhas = linhas_de_codigo(DEPLOY)
    i_dump = indice_unico(linhas, r"exec -T postgres pg_dump", "o comando pg_dump")
    i_prova = indice_unico(linhas, r"pg_restore -l", "a prova de integridade")
    i_mv = indice_unico(linhas, r'^\s*mv "\$ARQUIVO_PARCIAL"', "o mv para o nome final")

    assert i_dump < i_prova < i_mv, (
        "a sequência tem de ser: escrever o .parcial, provar que ele abre "
        "(pg_restore -l), e só então renomear para o nome final"
    )

    # A asserção olha a LINHA do pg_dump, e não o arquivo inteiro. A primeira
    # versão deste teste procurava `"$ARQUIVO_PARCIAL"` em qualquer lugar do
    # script e passou com o dump escrevendo direto no nome final — a variável
    # ainda aparecia no `rm -f` e no `wc -c` logo abaixo. Duas causas suficientes
    # para a mesma asserção é como um guarda morre sem ninguém notar; este foi
    # pego por mutação deliberada em 01/09/2026, antes de o PR entrar.
    _, linha_do_dump = linhas[i_dump]
    assert '> "$ARQUIVO_PARCIAL"' in linha_do_dump, (
        "o pg_dump não está escrevendo no arquivo .parcial:\n"
        f"    {linha_do_dump.strip()}\n"
        "Escrever direto no nome final faz o dump ganhar o nome de backup antes "
        "de alguém provar que ele abre — e um deploy interrompido no meio deixa "
        "para trás um arquivo pela metade com nome de coisa pronta"
    )


# ---------------------------------------------------------------------------
# (b) O VEREDITO NUNCA VEM DE UM PIPE (ARMADILHAS §5.10)
# ---------------------------------------------------------------------------
def test_o_script_liga_pipefail():
    codigo = "\n".join(linha for _, linha in linhas_de_codigo(DEPLOY))
    assert "set -o pipefail" in codigo, (
        "sumiu o `set -o pipefail` do script de deploy. Sem ele, `a | b` devolve o "
        "estado de `b`: um `pg_dump` que morreu no meio de um pipe passa por "
        "sucesso. É a §5.10 desta casa, a mesma que fez os greens do deploy-celula "
        "mentirem até 21/08/2026"
    )


def test_o_pg_dump_nao_passa_por_pipe():
    """`pg_dump ... | gzip > arquivo` devolve o veredito do gzip. É a §5.10.

    O formato `-Fc` já é comprimido, então não existe motivo para o pipe existir
    — e este guarda é o que impede alguém de "melhorar" isso mais tarde.
    """
    linhas = linhas_de_codigo(DEPLOY)
    _, linha_do_dump = linhas[indice_unico(linhas, r"exec -T postgres pg_dump", "o comando pg_dump")]
    assert "|" not in linha_do_dump.replace("||", ""), (
        "o pg_dump está dentro de um pipe:\n"
        f"    {linha_do_dump.strip()}\n"
        "O exit de um pipeline é o do ÚLTIMO comando, então um pg_dump que morreu "
        "no meio sairia como sucesso e o arquivo truncado receberia o nome de "
        "backup. Use `-Fc` e redirecione direto para o arquivo"
    )


def test_nenhuma_medicao_do_postgres_vem_de_um_pipe():
    """As respostas que DECIDEM saem do comando, não do último elo de um cano."""
    linhas = linhas_de_codigo(DEPLOY)
    medicoes = [
        (numero, linha)
        for numero, linha in linhas
        if "psql -U postgres -tAc" in linha or linha.strip().startswith("SAIDA_DO_DF=")
    ]
    assert len(medicoes) >= 3, (
        "esperava pelo menos três medições (a base existe, o tamanho da base, o "
        f"espaço livre), achei {len(medicoes)}"
    )
    for numero, linha in medicoes:
        assert "|" not in linha.replace("||", ""), (
            f"a medição da linha {numero} vem de dentro de um pipe:\n"
            f"    {linha.strip()}\n"
            "Guarde a saída numa variável e leia o estado do COMANDO"
        )


def test_toda_medicao_do_postgres_trata_a_falha_explicitamente():
    """"Não consegui medir" nunca vira "pode seguir" (INV-CI01)."""
    texto = DEPLOY.read_text(encoding="utf-8")
    for alvo in ("EXISTE_A_BASE=", "TAMANHO_DA_BASE=", "SAIDA_DO_DF="):
        trecho = texto.split(alvo, 1)[1][:400]
        assert "parar_o_deploy" in trecho, (
            f"a atribuição de {alvo} não é seguida de um `|| parar_o_deploy`: uma "
            "falha de medição seguiria como se fosse resposta"
        )


# ---------------------------------------------------------------------------
# (c) A SENTINELA CONTINUA SENDO A ÚLTIMA PALAVRA
# ---------------------------------------------------------------------------
def test_entrega_concluida_e_a_ultima_linha_do_deploy():
    """O workflow exige esta linha na saída; sem ela, reprova a entrega.

    Ela existe porque um passo que não executa nada devolve 0 (28/08/2026, o
    `script_file` em vez de `script_path`), e ela só vale alguma coisa se for a
    ÚLTIMA: impressa no meio, ela declararia entregue o que ainda não subiu.
    """
    linhas = linhas_de_codigo(DEPLOY)
    _, ultima = linhas[-1]
    assert "ENTREGA-CONCLUIDA:" in ultima, (
        "a última linha de código do script deixou de ser a sentinela "
        f"ENTREGA-CONCLUIDA. Hoje ela é:\n    {ultima.strip()}"
    )
    assert ultima.isascii(), (
        "a sentinela precisa ser ASCII pura: acento nela é um jeito barato de o "
        "grep do workflow falhar por codificação e a trava virar decoração"
    )


def test_a_sentinela_sai_depois_da_subida_dos_conteineres():
    linhas = linhas_de_codigo(DEPLOY)
    i_up = indice_unico(linhas, r"docker compose up -d", "o docker compose up -d")
    i_sentinela = indice_unico(linhas, r"ENTREGA-CONCLUIDA:", "a sentinela da entrega")
    assert i_up < i_sentinela


# ---------------------------------------------------------------------------
# (d) O QUE JÁ ERA VERDADE CONTINUA VERDADE
# ---------------------------------------------------------------------------
def test_celula_vazia_e_recusada_antes_de_qualquer_comando_docker():
    """Sem CELULA, um `up -d` sem argumento subiria a plataforma inteira."""
    linhas = linhas_de_codigo(DEPLOY)
    i_guarda = indice_unico(
        linhas, r'if \[ -z "\$\{CELULA:-\}" \]', "a recusa de CELULA vazia"
    )
    dockers = [i for i, (_, linha) in enumerate(linhas) if "docker " in linha]
    assert dockers, "o script não chama docker em lugar nenhum — isso não pode estar certo"
    assert i_guarda < min(dockers), (
        f"a recusa de CELULA vazia está na linha {linhas[i_guarda][0]}, depois do "
        f"primeiro comando docker (linha {linhas[min(dockers)][0]})"
    )


def test_cada_execucao_escreve_um_arquivo_novo():
    """Idempotência: repetir a entrega (armadilhas/127) não pode sobrescrever nada."""
    texto = DEPLOY.read_text(encoding="utf-8")
    assert re.search(r"CARIMBO=\$\(date -u \+", texto), (
        "o nome do dump deixou de carregar um carimbo de tempo próprio. Sem ele, "
        "duas execuções na mesma entrega escreveriam no mesmo arquivo — e a "
        "repetição do deploy (armadilhas/127) apagaria a cópia da primeira"
    )
    assert "$CARIMBO" in texto.split("ARQUIVO_FINAL=", 1)[1][:200], (
        "o nome final do dump não usa o carimbo de tempo"
    )


def test_nenhum_rm_toca_fora_da_pasta_dos_dumps():
    """Este script ganhou o poder de apagar arquivos. Que ele o use só ali."""
    for numero, linha in linhas_de_codigo(DEPLOY):
        despida = linha.strip()
        if not re.match(r"^(rm|.*\brm) ", despida):
            continue
        permitidos = ("PASTA_DOS_DUMPS", "$velho", "ARQUIVO_PARCIAL")
        assert any(alvo in linha for alvo in permitidos), (
            f"a linha {numero} apaga algo fora da pasta de dumps:\n    {despida}"
        )


def test_a_pasta_dos_dumps_copia_dono_e_modo_de_um_vizinho():
    """`armadilhas/091`: quem escolhe permissão à mão acerta na sua máquina."""
    texto = DEPLOY.read_text(encoding="utf-8")
    assert "chmod --reference=" in texto and "chown --reference=" in texto, (
        "a pasta dos dumps precisa herdar dono e modo por --reference de algo que "
        "já funciona na máquina (armadilhas/091). Um dump é dado pessoal em texto "
        "puro: ele não pode nascer mais aberto que os segredos ao lado dele"
    )
    assert re.search(r'chmod --reference="\$REFERENCIA_DE_PERMISSAO"', texto), (
        "o chmod da pasta de dumps deixou de sair da referência"
    )


def test_o_deploy_para_quando_o_backup_falha():
    """A funcionalidade inteira: backup que tenta e segue é backup que não existe."""
    texto = DEPLOY.read_text(encoding="utf-8")
    assert "parar_o_deploy()" in texto, "sumiu a função que interrompe o deploy"
    corpo = texto.split("parar_o_deploy()", 1)[1][:900]
    assert "exit 1" in corpo, (
        "a função parar_o_deploy não termina em `exit 1` — ela virou um aviso, e "
        "um aviso deixa a migração rodar sem cópia de segurança"
    )
    assert texto.count("parar_o_deploy ") >= 8, (
        "o número de caminhos de falha que param o deploy caiu: alguém trocou uma "
        "parada por um seguir-adiante"
    )


# ---------------------------------------------------------------------------
# NADA DE SEGREDO
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("arquivo", [DEPLOY, RESTAURADOR])
def test_nenhum_segredo_passa_perto(arquivo: Path):
    """O pg_dump roda dentro do contêiner, pelo socket local, como superusuário.

    Não há senha em linha de comando, nem em variável, nem no nome do arquivo — e
    a forma de garantir isso é o script nunca precisar de uma.
    """
    texto = "\n".join(linha for _, linha in linhas_de_codigo(arquivo))
    for proibido in ("PGPASSWORD", "POSTGRES_PASSWORD", "DATABASE_URL", "POSTGRES_SUPER_PASSWORD"):
        assert proibido not in texto, (
            f"{arquivo.name} menciona {proibido}. A cópia de segurança não precisa "
            "de senha nenhuma: o pg_dump roda dentro do contêiner do Postgres, "
            "pelo socket local. Se ela passou a precisar, o desenho regrediu"
        )
    assert not re.search(r"env/[a-z]+\.env", texto), (
        f"{arquivo.name} lê um arquivo de env. O nome da base sai da convenção "
        "`<celula>_db` e é conferido no próprio Postgres, justamente para este "
        "script nunca abrir um arquivo que contém senha"
    )


# ---------------------------------------------------------------------------
# O CAMINHO DE VOLTA
# ---------------------------------------------------------------------------
def test_o_restaurador_existe_e_exige_confirmacao_explicita():
    """Um backup sem caminho de volta não é um backup."""
    assert RESTAURADOR.exists(), "sumiu infra/restaurar-backup.sh"
    texto = RESTAURADOR.read_text(encoding="utf-8")
    assert "--sim-eu-quero-sobrescrever" in texto, (
        "o restaurador deixou de exigir uma confirmação explícita. Ele sobrescreve "
        "o banco inteiro de uma célula e não dá para desfazer"
    )
    assert 'CONFIRMADO" -ne 1' in texto or 'CONFIRMADO" != "1"' in texto, (
        "o restaurador não tem mais o caminho de ENSAIO: rodar sem a confirmação "
        "precisa conferir tudo, mostrar o que faria e NÃO mudar nada"
    )


def test_o_restaurador_avisa_o_leigo_do_que_e_irreversivel():
    """O mantenedor é leigo em terminal. Um aviso que ele não entende não é aviso."""
    texto = RESTAURADOR.read_text(encoding="utf-8").upper()
    for aviso in ("SOBRESCREVE", "NAO DA PARA DESFAZER", "FORA DO AR"):
        assert aviso in texto, (
            f"o restaurador não avisa mais que {aviso.lower()}. Quem vai rodá-lo "
            "está no pior dia do projeto e não lê código"
        )


def test_o_restaurador_deriva_a_base_do_nome_do_arquivo():
    """Restaurar o dump de uma célula em cima do banco de outra é o pior erro daqui."""
    texto = RESTAURADOR.read_text(encoding="utf-8")
    assert "basename" in texto and "[0-9]{8}-[0-9]{6}Z" in texto, (
        "o restaurador deixou de derivar a base do NOME do arquivo. Um parâmetro "
        "digitado à mão abriria a porta de restaurar no banco errado"
    )


def test_o_restaurador_para_a_celula_antes_de_trocar_o_banco():
    linhas = linhas_de_codigo(RESTAURADOR)
    i_stop = indice_unico(linhas, r"\$COMPOSE stop", "a parada dos serviços")
    i_restore = indice_unico(linhas, r"pg_restore -U postgres", "o pg_restore")
    assert i_stop < i_restore, (
        "o banco está sendo restaurado com a célula ainda escrevendo nele: o "
        "resultado sairia misturado"
    )


# ---------------------------------------------------------------------------
# A PREMISSA DO DESENHO — o alarme que dispara se ela mudar
# ---------------------------------------------------------------------------
def test_o_workflow_ainda_envia_este_arquivo_e_nao_copia_outros():
    """Se o deploy passar a copiar arquivos, o backup pode virar um `.sh` próprio.

    Hoje ele não copia: a `appleboy/ssh-action` manda o CONTEÚDO de
    `infra/deploy-celula-na-vps.sh` e nada mais chega a `/opt/plataforma`. É por
    isso, e só por isso, que a cópia de segurança mora dentro do script de
    deploy. Este teste não proíbe a mudança — ele garante que quem a fizer leia
    esta explicação em vez de descobrir o acoplamento pelo deploy vermelho.
    """
    texto = WORKFLOW.read_text(encoding="utf-8")
    assert "script_path: infra/deploy-celula-na-vps.sh" in texto, (
        "o deploy-celula não envia mais infra/deploy-celula-na-vps.sh por "
        "script_path — reveja onde a cópia de segurança do banco deve morar"
    )
    assert "scp-action" not in texto, (
        "o deploy-celula ganhou um passo de cópia de arquivos para a VPS.\n"
        "Isso muda a premissa do desenho da TAR-003: com arquivos chegando em "
        "/opt/plataforma, a cópia de segurança PODE virar um script próprio "
        "(infra/backup-antes-da-migracao.sh), que é o desenho preferível.\n"
        "Se foi isso que você fez de propósito, mova o bloco, atualize estes "
        "guardas e apague esta asserção — mas faça a mudança inteira, e não pela "
        "metade: um backup fail-closed que aponta para um arquivo ausente para "
        "TODA entrega da plataforma."
    )
