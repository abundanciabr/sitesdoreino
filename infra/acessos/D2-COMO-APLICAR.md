# D2 — acesso de robôs por operações (preparado; nada aplicado)

Estado lido da VPS em 09/10/2026: `deploy` é uid 1000 e pertence a `docker`, equivalente a poder de root. Seu sudo listado permite só `/usr/local/sbin/provisionar-usuario-ponte`, mas o socket Docker já basta para escapar do isolamento. `/home/deploy/.ssh/authorized_keys` contém três chaves válidas:

| Linha | Fingerprint SHA256 | Comentário | Identificação |
| --- | --- | --- | --- |
| 1 | `SHA256:0Lf5N3Voeus7tCpnqyjA8FQb9dApsCkOI5GhEQKd69g` | `deploy_ci@sitesdoreino` | dono não comprovado |
| 2 | `SHA256:+eKOcjlz6oewBUEzrJcLy/jDsNI9j3aOrT0B8WyrBu0` | `deploy-vps-environment-20260919` | chave pública também existe neste PC; dono exclusivo não comprovado |
| 3 | — | `COLE_AQUI` | texto inválido, não é chave |
| 4 | `SHA256:zFrc09cWN0Ysy2X/5uj8W21wEuDW/ESxMRFiWO0dUAY` | `robos-locais-20261001` | corresponde a `C:\Users\davia\.ssh\sitesdoreino-vps.pub`; o alias usado agora por Codex entra como deploy |

Manter a linha 4 em `deploy` anula D2, mesmo criando a conta `robo`. Também é preciso confirmar se as linhas 1 e 2 são usadas por Codex, Claude, automações ou pelo mantenedor. O console da hospedagem é uma via de emergência, mas sua disponibilidade e titularidade não foram comprovadas daqui. Antes da retirada de qualquer chave, o mantenedor precisa identificar e testar um acesso independente que não seja compartilhado com robôs. Não há prova de recuperação independente ainda.

## Instalação preparada

Arquivos somente neste PC: `C:\Users\davia\.codex\worktrees\entregas-retomada-20261009\sitesdoreino-limpo-20260923\infra\acessos\D2-usuario-robo.sh`, `C:\Users\davia\.codex\worktrees\entregas-retomada-20261009\sitesdoreino-limpo-20260923\infra\acessos\robo_comando.py`, `C:\Users\davia\.codex\worktrees\entregas-retomada-20261009\sitesdoreino-limpo-20260923\infra\acessos\robo_broker.py` e `C:\Users\davia\.codex\worktrees\entregas-retomada-20261009\sitesdoreino-limpo-20260923\infra\acessos\D2-trocar-chave.py`.

O instalador copia `entregas.py` e `entregas_migracoes.py` do diretório pai para `/usr/local/lib/meshcraft-integrador/`, sob dono root. Cria `integrador` sem login, Docker, sudo ou grupo compartilhado e com dados próprios em `/var/lib/meshcraft-integrador/{codigo/repo.git,entregas}`. Cria `robo` sem docker/sudo/adm, chave SSH nova com comando forçado e arquivos SSH sob dono root. O socket `/run/meshcraft-robo.sock` aceita só `robo`; o serviço roda como `integrador` e executa apenas `entregar`, `consultar`, `estado`. O robô não grava o espelho Git nem o registro diretamente. A ponte separada `/run/meshcraft-entregas-publicador.sock` leva pedidos tipados ao publicador confiável; este instalador não cria a ponte nem dá ao integrador acesso a Docker/configurações privadas. O instalador recebe caminho da chave pública nova e imprime apenas seu fingerprint.

Sequência após decisão: preparar a ponte tipada e o publicador confiável; gerar chave **nova** no PC para o robô e guardar a privada fora da VPS; copiar os arquivos de `infra/acessos/`, `infra/entregas.py`, `infra/entregas_migracoes.py` e a pública à VPS; executar como root `bash D2-usuario-robo.sh /caminho/da/chave-robo.pub`; testar `ssh -i <privada-nova> robo@<host> estado` e `consultar`; provar que `ls`, `integrar`, `promover`, Docker e shell são recusados; trocar as entradas de Codex/Claude/automações para a chave nova; comprovar recuperação independente do mantenedor; só então retirar de `deploy` cada chave conhecida como robô.

`D2-trocar-chave.py retirar SHA256:...` simula a retirada; `--aplicar` faz backup privado de `authorized_keys` em `/var/backups/meshcraft-acessos/` e retira só a linha da fingerprint. Para recuperar pelo console do mantenedor: `D2-trocar-chave.py restaurar SHA256:... --backup /var/backups/meshcraft-acessos/deploy-authorized_keys-<instante> --aplicar`. O script não remove a conta nem os dados. Se o socket novo falhar, a chave antiga pode ser restaurada pelo acesso independente. Sem esse acesso, a retirada não deve começar.

As operações fechadas de atendimento de `ci/operacoes_vps.py` incluem estado de serviço/infra, espaço em disco, versão do compose, configuração do quiz e observações Appmax. Elas dependem do canal de medição já existente, que usa Docker e valida serviço, operação e formato da saída. D2 não transfere esse Docker ao usuário `robo`. Antes de migrar qualquer automação de atendimento, identificar sua entrada efetiva e mantê-la no serviço confiável ou criar um adaptador tipado separado; os três comandos de entrega não substituem o catálogo de atendimento.

Executor de ensaio (F2-04): a ponte/publicador confiável, fora das contas `robo` e `integrador`, controla preparação, execução e verificação usando o Docker já existente. O código candidato roda como UID 65532, com `no-new-privileges`, sistema de arquivos somente leitura, sem rede, socket Docker ou credenciais. O integrador não recebe Docker; o robô não acessa a ponte. Não há outro daemon Docker.

## Preparação conferida nesta retomada de 09/10/2026

O mantenedor respondeu que ainda não dispõe de recuperação independente. Não foi criada conta, retirada chave, encerrada sessão nem aplicado privilégio. O material continua preparado para decisão futura.

A instalação corrigida usa `/home/robo/.ssh` com dono `root:robo` e modo `0750`, e `/home/robo/.ssh/authorized_keys` com dono `root:robo` e modo `0640`: o usuário pode ler a chave pública, mas não alterar o comando forçado nem trocar o arquivo. O OpenSSH abre essa lista temporariamente sob o UID do usuário: fonte `https://github.com/openssh/openssh-portable/blob/master/auth2-pubkey.c`. Chaves privadas não ficam nesse diretório.

A consulta preparada devolve separadamente o estado da entrega Git e a fase de ativação, inclusive aplicação/funil parcialmente ativados. Motivos privados e credenciais do worker não são expostos.

Antes da transição efetiva, falta conferir no acesso independente do mantenedor: console da hospedagem funcionando; administração de `https://github.com/abundanciabr/sitesdoreino`; titularidade das chaves 1 e 2; lista de sessões/serviços que ainda usam deploy; substituição da credencial administrativa GitHub no PC. Esses são os itens D1/D2 já previstos pelo plano, não uma nova autorização por entrega.
