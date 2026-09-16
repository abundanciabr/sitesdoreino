# Dublê que aceita tudo esconde o comando que não existe

Teste que troca o programa de verdade por um dublê prova que o seu código reage
certo ao que o dublê diz, nunca que o comando existe ou que os argumentos são
aceitos. Quando a ferramenta real muda de contrato, o dublê continua verde e o
defeito só aparece em produção.

Dois casos no mesmo dia, 15/09/2026. `ci/esperar.py --e-pousar` chamava
`ci/mergear.py N --pousar`, opção que já tinha saído do portão: o pouso
automático falhava em TODO PR com `unrecognized arguments: --pousar`, e os oito
testes que cobriam esse caminho usavam um portão de mentira que engole qualquer
argumento. No mesmo dia, os nove testes da entrada privada do Traefik liam o
resultado de `yaml.safe_load`, que descarta comentários, enquanto o Traefik lê o
texto cru: a bomba da armadilha 478 passou verde por todos eles.

O dublê mede a reação. Junto dele, meça o contrato contra a coisa real: as
flags contra o `--help` do programa, o arquivo contra o parser que vai lê-lo.

gatilho: ci/tests/
licao: Onde há dublê, acrescente uma medição contra a ferramenta de verdade.
  O dublê nunca reprova um comando que deixou de existir.
