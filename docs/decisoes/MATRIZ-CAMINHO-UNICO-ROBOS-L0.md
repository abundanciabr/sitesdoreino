# Matriz L0 - caminho unico de execucao dos robos

Consulta feita em 2026-09-24 na bancada `wt-ci-caminho-unico-robos-l0`, ramo
`agent/ci/caminho-unico-robos-l0`, revisao local
`0348fd31c5828a9ae2d242481c4c374c8f548d99`.

O usuario deste caminho e o mantenedor abrindo uma tarefa nova ou retomando uma
entrega. Ele precisa ver uma orientacao unica, com fonte, limite, proxima acao e
prompt copiavel. A versao mais simples que resolve o problema inteiro e usar
`ci/mapa_de_execucao.py` como porta unica de leitura e `ci/sessao.py` como porta
unica de abertura, sem criar fila, reserva, API ou inventario paralelo. Sai tudo
que apenas repetiria estado ja calculado por fila, eventos, livro e GitHub.

## Matriz R1-R8

| Regra | Diagnostico L0 | Entrega planejada | Aceite | Teste | Evidencia inicial |
|---|---|---|---|---|---|
| R1 - entrada unica | `ci/mapa_de_execucao.py` ja existe como porta de orientacao, mas pedido em portugues amplo ainda vira lista extensa de candidatos e nao uma identidade executavel. | Exigir uma identidade executavel antes de executar: TAR, PR, ramo, caminho fechado ou pedido com aceite e cerca. | Pedido amplo termina em reconciliacao, sem criar tarefa nem executar. Pedido fechado gera comando de abertura. | `python -B ci/mapa_de_execucao.py --pedido "Implementar o caminho unico de execucao dos robos" --snapshot` | `resultado: PASS`, `proximo_passo.id: detalhar_pedido`, `candidatos` extenso, sem cerca de escrita. |
| R2 - fontes autoritativas | O mapa mede fila, eventos, CODEOWNERS, mecanismos `ci/` e regras globais. Em `--snapshot`, GitHub e reservas aparecem como `NAO MEDIDO`. | Manter a distincao entre retrato local e consulta viva. Tela e CLI devem usar o mesmo pacote e obrigar revalidacao antes de agir. | Snapshot valido nunca autoriza execucao; consulta viva mede GitHub ou devolve ERROR. | `python -B ci/mapa_de_execucao.py --tar TAR-663 --mandato ci --mandato .codex/agents/despacho.toml --snapshot` | `resultado: PASS`, `proximo_passo.id: reconciliar_ao_vivo`, fonte `GitHub e reservas` com estado `NAO MEDIDO`. |
| R3 - mandato e cerca | Tarefa que toca `ci` reprova sem mandato explicito, mesmo quando a fila contem origem e aceite. Isso impede documento citado de virar autoridade. | Preservar mandato explicito por caminho protegido e transportar essa exigencia no prompt. | Sem `--mandato`, caminho protegido para em `obter_mandato`; com mandato, vira snapshot ou consulta viva. | `python -B ci/mapa_de_execucao.py --tar TAR-663 --snapshot` | Exit 1, `resultado: FAIL`, `proximo_passo.id: obter_mandato`, `sem_mandato: ["ci"]`. |
| R4 - retomada sem duplicar | A retomada carrega eventos da fila, PR, revisao e arvore; em snapshot a bancada, checks e deploy ficam `NAO MEDIDO`. | Reaproveitar submissao e eventos existentes; proibir recriar identidade quando ha evento terminal. | TAR concluida ou submetida orienta preservar encerramento, retomar fechamento ou reconciliar aceite conforme estado medido. | `python -B ci/mapa_de_execucao.py --tar TAR-663 --mandato ci --mandato .codex/agents/despacho.toml --snapshot` | Pacote inclui `pr: 1993`, evento `submetida`, evento `concluida`, ramo `agent/ci/remover-encaminhamento-maestro`. |
| R5 - seguranca da entrada | Entrada com traversal e segredos e recusada antes de ler fila ou GitHub. | Toda entrada de caminho passa por normalizacao e recusa fail-closed. | Caminho fora da raiz retorna FAIL com acao de corrigir entrada. | `python -B ci/mapa_de_execucao.py --caminho ..\fora --snapshot` | Exit 1, `resultado: FAIL`, `proximo_passo.id: corrigir_entrada`. |
| R6 - perfil economico | O compilador recomenda `gpt-5.6-sol` para diagnostico/escrita, enquanto este despacho recebeu mandato externo para usar `gpt-5.5`. | O caminho unico deve expor o perfil recomendado e aceitar sobrescrita somente quando o mandato da sessao exigir. | Brief mostra `modelo_recomendado` e `esforco_recomendado`; divergencia fica visivel. | `python -B ci/economia_da_fabrica.py brief --tipo diagnostico --objetivo "Implementar o caminho unico de execucao dos robos" --celula ci --alvo ci/mapa_de_execucao.py` | Saida: `modelo_recomendado: gpt-5.6-sol`, `esforco_recomendado: medium`. |
| R7 - reserva e fila sem segunda casa | `ci/reservar.py` oferece `numero`, `intencao`, `listar`, `soltar`; a fila e o mapa reaproveitam reservas e eventos, sem novo servidor. | Qualquer implementacao seguinte deve continuar usando `ci/reservar.py` e `ci/fila.py`, sem banco, segunda fila ou wrapper paralelo. | Nenhum arquivo novo guarda estado de tarefa; estado continua calculado. | `python -B ci/reservar.py --help` | Saida lista apenas `{numero,intencao,listar,soltar}` e descreve o almoxarife. |
| R8 - prova e falha de instrumento | O mapa ja separa `PASS`, `FAIL` e `ERROR`; snapshot local passa com fonte remota nao medida, enquanto entrada invalida falha antes de consulta. | Toda prova da implementacao deve medir comando e saida, e ERROR nao pode virar sucesso. | Testes focais cobrem pedido novo, retomada, path traversal, fonte remota impossivel, snapshot e catalogo. | `python -m pytest ci/tests/test_mapa_de_execucao.py -q` | O comando imprimiu erros em todos os casos e nao entregou resumo em 90s; recorte de um teste tambem marcou `ERROR` e travou sem traceback. |

## Lacunas reproduzidas

1. Pedido amplo demais nao gera execucao segura. O comando com `--pedido`
   retornou `detalhar_pedido` e candidatos demais, portanto a proxima fatia deve
   exigir identidade ou aceite antes de executar.
2. Snapshot local nao mede GitHub, reservas, checks nem runtime. O pacote declara
   isso corretamente, mas qualquer experiencia visual que o esconda cria falso
   verde.
3. Mandato de caminho protegido nao nasce do documento da tarefa. O comando da
   TAR-663 sem `--mandato` parou em `obter_mandato`.
4. O perfil recomendado pelo compilador do projeto diverge do mandato deste
   despacho. A implementacao precisa mostrar a divergencia, nao apaga-la.

## Medicao inicial

| Comando | Resultado observado |
|---|---|
| `python ci/sessao.py --celula ci --tarefa caminho-unico-robos-l0 --sem-container` | Primeira tentativa parou antes de criar bancada por `Permission denied` em `.git/FETCH_HEAD`; repetida com permissao elevada, abriu `C:\Users\davia\abundanciabr\wt-ci-caminho-unico-robos-l0` no ramo `agent/ci/caminho-unico-robos-l0`. |
| `python -B ci/mapa_de_execucao.py --help` | Exit 0; CLI unico aceita `--tar`, `--pedido`, `--pr`, `--ramo`, `--caminho`, `--aceite`, `--sintoma`, `--mandato`, `--snapshot`. |
| `python -B ci/mapa_de_execucao.py --pedido "Implementar o caminho unico de execucao dos robos" --snapshot` | Exit 0; `resultado: PASS`; proximo passo `detalhar_pedido`; fontes locais medidas e GitHub/reservas `NAO MEDIDO`. |
| `python -B ci/mapa_de_execucao.py --tar TAR-663 --snapshot` | Exit 1; `resultado: FAIL`; proximo passo `obter_mandato`. |
| `python -B ci/mapa_de_execucao.py --caminho ..\fora --snapshot` | Exit 1; `resultado: FAIL`; proximo passo `corrigir_entrada`. |
| `python -B ci/reservar.py --help` | Exit 0; comandos existentes do almoxarife sao `numero`, `intencao`, `listar`, `soltar`. |

## Proxima fatia tecnica

1. Consolidar a definicao de identidade executavel para pedido novo: TAR/PR/ramo
   ou pedido com caminho e aceite falsificavel.
2. Garantir que a central visual mostre `NAO MEDIDO` para GitHub, reservas,
   checks e runtime quando o pacote vem de snapshot.
3. Reusar `ci/mapa_de_execucao.py` como unica composicao de pacote para CLI e
   admin; qualquer ajuste de tela deve consumir o catalogo validado.
4. Manter `ci/fila.py` e `ci/reservar.py` como as unicas fontes de estado e
   trava de tarefa.
