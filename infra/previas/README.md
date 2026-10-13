# Canal de prévias administrativas instalado na VPS

Autorização expressa do mantenedor em 13/10/2026: atualizar código não protegido e executar testes em prévias administrativas isoladas, sem shell livre, acesso a segredos ou restauração automática de banco. Esta referência descreve a capacidade instalada; não cria nova regra ou autorização.

Painel privado: `https://meshcraft.top/admin/previas-operacionais/`.
Relatório privado: `https://meshcraft.top/admin/documentos/operacao-site-contexto-retomada-20261013`.
Código versionado: `https://github.com/abundanciabr/sitesdoreino/tree/codex/operacao-contexto-20261013/infra/acessos`.
Esta cópia de trabalho está somente neste PC: `C:\Users\davia\.codex\worktrees\operacao-site\sitesdoreino-limpo-20260923\infra\previas\README.md`.

## Uso disponível

`ssh sitesdoreino-robo contexto` mostra o catálogo geral. `ssh sitesdoreino-robo previas ajuda` descreve o formato aceito. `ssh sitesdoreino-robo previas listar` mostra operações recentes e IDs das versões atuais.

O robô prepara um manifesto no repositório, envia seu commit ao GitHub e executa `ssh sitesdoreino-robo previas aplicar NOME COMMIT BASE`. COMMIT é o SHA completo já enviado. BASE é o ID atual mostrado por listar, ou `nova` para um nome ainda inexistente. O nome tem 3 a 40 caracteres: letras minúsculas, números e hífens, começando por letra.

Manifesto de exemplo: `https://github.com/abundanciabr/sitesdoreino/blob/codex/operacao-contexto-20261013/infra/previas/candidatas/operacao.json`.

O manifesto contém `runtime` (`node` ou `python`), `files` (mapa de destino na cópia para origem no commit), `test` (arquivo sob `tests/`) e `page` (HTML presente no mapa). As origens aceitas são código de serviços e pacotes não protegidos, ou exemplos deste canal. Árvores congeladas do Mercado Pago, caminhos de configuração, migrações, segredos, satisfação protegida, travessia de diretório e argumentos de shell são recusados. Não há extração de arquivos compactados nem links simbólicos.

Os testes usam Node com `node --test` ou Python com `unittest`, bibliotecas dos runtimes fixados na instalação e fontes selecionadas no manifesto. Não instalam dependências, não usam credenciais nem serviços/bancos existentes. A página HTML pode incluir CSS e JavaScript embutidos; é apresentada em iframe sem acesso à origem autenticada ou rede. Isto não hospeda servidores Django/Node arbitrários com acesso aos bancos do site.

Para acompanhar após qualquer desconexão: `ssh sitesdoreino-robo previas consultar ID` ou `ssh sitesdoreino-robo previas retomar ID`. O ID tem 24 caracteres; também pode ser calculado como os 24 primeiros caracteres de SHA256 de `aplicar\nNOME\nCOMMIT\nBASE`. Reenviar os mesmos argumentos devolve o mesmo registro, sem executar de novo. Uma base antiga é recusada. A operação continua na VPS; a sessão SSH não a sustenta.

Cada alteração preserva uma cópia do código anterior, muda uma referência própria e executa o teste. Se falhar, a referência volta automaticamente. Se o processo do canal reiniciar durante ativação/teste, ele recupera a referência anterior antes de aceitar outra alteração. Falhas ficam registradas; uma nova candidata usa novo commit. Os contadores e classes de falha são publicados sem texto bruto de logs. Os arquivos candidatos e backups são mantidos. Nenhum banco é restaurado ou alterado por este canal.

As prévias antigas, inclusive a Trilha com configurações privadas, não foram migradas nem registradas como destinos. Os nomes deste canal apontam apenas para cópias próprias. Isso preserva os trabalhos em andamento e impede que a capacidade nova seja usada para executar código com as credenciais daqueles ambientes.

## Comprovação realizada

- Operação `1153d33074a70c78004f71cc`: sucesso depois de encerrar a conexão e consultar por outra sessão; interação HTML conferida no site.
- Operação `bc96a2d1c4bcf9866a0d5cb5`: teste deliberadamente falho; código anterior recuperado, backup preservado.
- Operação `4446aeaf40fd5282b25e4a03`: teste Python concluído sem root, segredos ou escrita no código.
- Operação `7dd91badf49260ba8703e411`: 20 testes reais do cliente da Trilha passaram em cópia isolada.
- Operação `b0c7582c4dcd0ee63a74f3ef`: serviço novo interrompido durante teste e reiniciado; recuperação persistente conferida por SSH.

Não foi necessário reiniciar a VPS nem os serviços anteriores. A instalação conferiu 33 referências preservadas e 23 contêineres existentes sem alteração. Anônimo recebeu HTTP 403; administrador autenticado viu e usou a prévia.
