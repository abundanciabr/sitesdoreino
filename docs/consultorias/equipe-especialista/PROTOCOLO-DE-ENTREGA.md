# Protocolo de entrega completa para robôs

Este protocolo reconstrói o caminho usado na [TAR-455](../../../fila/tarefas/455-compreender-o-sistema-e-formar-a-equipe-especialista-do-proj.json) e no [PR 1720](https://github.com/abundanciabr/sitesdoreino/pull/1720). Ele serve para missões amplas que exigem compreender o projeto, produzir uma entrega durável, provar a mudança, integrar e conferir o resultado na superfície usada pelo mantenedor.

A velocidade veio de quatro decisões: trabalhar em bancada isolada, dividir leituras independentes, costurar somente fatos rastreáveis e transformar a validação final em comandos repetíveis. Nenhuma etapa crítica foi substituída por promessa.

## Resultado que o robô precisa produzir

Uma entrega completa tem cinco estados distintos:

1. **Compreendido:** fontes canônicas, código e limites foram lidos.
2. **Construído:** o artefato final existe na bancada isolada.
3. **Validado:** comandos executáveis passaram na revisão examinada.
4. **Integrado:** o GitHub confirma o merge do SHA conferido.
5. **Publicado e relido:** a superfície destinada ao mantenedor mostra o resultado final.

Um estado não prova o seguinte. PR aberto não prova integração. Merge não prova deploy. Deploy não prova que a página certa está legível. Mensagem enviada não prova que outro robô começou a trabalhar.

## 1. Traduzir a missão em experiência e aceite

Antes de editar, responda:

- quem vai usar a entrega;
- o que essa pessoa precisa conseguir ver ou fazer;
- qual é o menor artefato que resolve o pedido inteiro;
- qual prova encerra cada parte;
- quais decisões continuam exclusivas do mantenedor.

No caso da TAR-455, o mantenedor precisava de uma visão integral do sistema e de uma equipe especialista reutilizável. O núcleo escolhido foi um relatório versionado em dez partes, uma síntese privada no editor e tarefas canônicas para riscos descobertos.

Corte opções, automações e novos papéis que não mudem essa experiência.

## 2. Ler a autoridade antes do código

Leia primeiro:

- [CLAUDE.md](../../../CLAUDE.md);
- [CONSTITUICAO.md](../../../CONSTITUICAO.md);
- [RITOS.md](../../../RITOS.md);
- [guia do mantenedor](../../guia-mantenedor.md);
- instruções do caminho afetado.

Essas fontes decidem bancada, fila, CODEOWNERS, contratos, integração, publicação e prestação de contas. Documentos históricos ajudam a explicar decisões, mas não substituem a lei vigente.

Se duas instruções divergem, registre a divergência como fato. Siga a autoridade atual e encaminhe a correção em tarefa própria. No caso observado, fichas antigas ainda falavam em atestado e pouso manual, enquanto a lei vigente determina integração automática sem ambos.

## 3. Abrir uma bancada isolada

Use o bootstrap canônico:

```powershell
python ci/sessao.py --celula <celula> --tarefa <slug> --sem-container
```

Retire `--sem-container` quando a mudança exige serviço, banco ou baseline real. O comando cria worktree, ramo e intenção sem editar o clone principal.

Leia o boletim da abertura. Se a base estiver atrasada, confronte `origin/main` antes de inferir estado. Nunca use uma cópia velha como prova de que uma capacidade existe ou falta.

## 4. Registrar o trabalho na fila

Uma missão nova precisa de tarefa canônica com:

- título compreensível;
- caminhos tocados;
- cartão movido;
- responsabilidade;
- evidência de encerramento;
- explicação para gente;
- despacho executável;
- origem do pedido.

Crie pelo balcão:

```powershell
python ci/fila.py criar <campos obrigatorios>
python ci/fila.py pegar TAR-NNN --quem <identidade-da-bancada>
```

O número vem do almoxarife. O arquivo da tarefa nunca é renomeado nem editado depois de criado. Se o Rádio falhar, preserve os eventos já gravados e registre a falha; não repita a mudança de estado.

## 5. Dividir a investigação por perguntas independentes

Paralelize somente leituras que podem terminar sem depender umas das outras. Na TAR-455, três frentes funcionaram bem:

- produto, jornadas e experiência;
- arquitetura, fábrica e operação;
- entrega, fila, validação e publicação.

Cada frente recebeu perguntas fechadas, caminhos somente leitura e formato de resposta. O agente principal continuou a investigar as fontes compartilhadas e depois fez a costura.

Evite dois robôs editando o mesmo arquivo. Um único executor deve possuir o artefato final.

## 6. Construir um mapa de fontes

Para cada afirmação, marque uma destas naturezas:

- **Fato:** observado em código, configuração, tarefa, registro ou comando.
- **Inferência:** conclusão derivada de mais de um fato.
- **Hipótese:** explicação ainda sem prova suficiente.
- **Proposta:** mudança recomendada, ainda não executada.

Associe fonte e limite. Exemplos do caso:

- 18 células e 39 consumos HTTP vieram do mapa canônico;
- 273 rotas vieram do mapa do site;
- quatro usos de Anthropic vieram dos únicos imports encontrados no runtime;
- compra real, ponte ativa e jornada completa não foram exercitadas;
- riscos encontrados não foram chamados de incidentes sem prova de impacto.

Essa disciplina torna a síntese rápida porque elimina discussões baseadas em memória.

## 7. Escrever o artefato principal antes da página

O arquivo versionado é a fonte integral. A página privada é a porta de leitura do mantenedor.

Na TAR-455:

- o [relatório integral](RELATORIO.md) preservou arquitetura, fontes, equipe, riscos e próxima rodada;
- o editor recebeu uma síntese curta com link permanente para o merge;
- tabelas e Mermaid ficaram no Git, porque o renderer do editor não os suporta;
- a página nasceu privada e não foi publicada ao público.

O documento do site não deve duplicar centenas de linhas difíceis de manter. Ele precisa orientar a leitura e apontar para a fonte permanente.

## 8. Converter descobertas em tarefas estreitas

Quando a investigação descobre trabalho novo, não esconda o achado em uma seção de riscos. Crie tarefa separada com fronteira, responsável e prova.

O caso gerou:

- TAR-456 para recuperação de eventos mortos;
- TAR-457 para detectar fatos arquiteturais envelhecidos;
- TAR-458 para diagnosticar a fronteira do bearer do checkout.

Nenhuma foi anunciada como execução iniciada. Registrar uma tarefa não é começar a construir.

Quando a descoberta toca CODEOWNERS, contrato congelado, pagamento, produção ou gasto, deixe a execução condicionada ao mandato específico do mantenedor.

## 9. Pedir uma revisão adversarial antes do PR

Entregue ao revisor:

- worktree exato;
- arquivos alterados;
- critérios de aceite;
- limites do mandato;
- provas já executadas.

Peça achados por prioridade, arquivo e linha. O revisor deve somente ler.

A primeira revisão da TAR-455 reprovou três pontos:

1. risco alto do checkout sem tarefa canônica;
2. promessa de página privada sem criação nem dívida;
3. resultados descritos sem prova executável ligada à revisão.

O executor corrigiu os três. A segunda revisão aprovou sem achados. A revisão acelerou a entrega porque encontrou lacunas antes do custo do PR e da CI.

## 10. Transformar a prova em comandos repetíveis

A validação final precisa poder rodar em checkout isolado e no SHA final. Na TAR-455, o JSON de validação continha seis comandos:

1. mapa de células;
2. mapa do site;
3. estrutura do relatório, links, caracteres e padrões de segredo;
4. validação da fila;
5. conferência do manifesto do painel;
6. verificação do painel.

Exemplo:

```powershell
python ci/mapa_de_celulas.py --verificar
python ci/mapa_do_site.py --verificar
python ci/fila.py validar
node painel/gerar_manifesto.js --conferir
python ci/verificar_painel.py
```

A máquina não tinha PyYAML no Python padrão. A correção foi criar um ambiente temporário com a dependência e apontar os dois mapas para esse interpretador. Nenhuma dependência foi adicionada ao projeto.

Antes do PR, execute os mesmos comandos pelo mecanismo usado por `ci/pr.py`. Isso revela diferenças de `PYTHONPATH`, arquivos não rastreados e dependências acidentais.

## 11. Abrir o PR pela ferramenta canônica

Use [ci/pr.py](../../../ci/pr.py) com:

- tarefa reivindicada;
- título em PT-BR;
- descrição concreta;
- JSON de validação;
- resultado ou dívida de publicação;
- caminhos CODEOWNERS e mandato, quando aplicável.

A ferramenta:

1. cria o commit da mudança;
2. valida em revisão isolada;
3. abre o PR;
4. embarca eventos e recibo;
5. repete a validação no SHA final.

No caso, os seis comandos passaram na revisão isolada, no SHA final e novamente depois da atualização automática da base.

## 12. Acompanhar a integração sem restaurar rito antigo

A decisão vigente está em [merge sem rito de pouso](../../decisoes/DECISAO-merge-sem-rito-de-pouso.md). PR pronto integra automaticamente quando `muralhas` e `ci-celula-gate` ficam verdes no SHA atual.

Não publique atestado, etiqueta ou comando manual de pouso.

No caso, `ci/esperar.py --entrega` devolveu uma mensagem antiga sobre atestado. O executor não obedeceu ao diagnóstico obsoleto. Ele confrontou a lei, consultou os checks reais e confirmou que a passagem seguinte do workflow integrou o PR automaticamente.

Confirme sempre:

- estado remoto do PR;
- SHA da cabeça;
- conclusão de todos os checks;
- SHA do merge;
- horário da integração.

## 13. Medir deploy e publicação separadamente

Depois do merge, confira o workflow de deploy. O caso só foi declarado publicado quando o run confirmou:

- portão de deploy verde;
- dados do painel e da fila ativados;
- imagem da célula admin enviada;
- ativação na VPS;
- prova de que a entrega rodou.

O [run 35394708892](https://github.com/abundanciabr/sitesdoreino/actions/runs/35394708892) terminou com sucesso. O [recibo integrado](../../../painel/registros/20260918-008-docs-formar-equipe-especialista-tar-455.js) preserva o estado anterior à criação da página privada.

## 14. Criar a página privada com confirmação no gesto final

A operação no editor ocorreu assim:

1. abrir `/admin/documentos/` e conferir autenticação;
2. abrir “Escrever um documento novo”;
3. preparar título, slug e corpo;
4. pedir confirmação imediatamente antes do envio;
5. criar o documento;
6. reler a página salva;
7. voltar à lista e conferir que aparece em “Só administradores”;
8. confirmar que a ação “Publicar no site” continua separada.

A confirmação é exigida porque o clique grava conteúdo em uma aplicação externa representando o mantenedor. Prepare tudo antes de interrompê-lo.

Página criada: [Sistema e equipe especialista do projeto](https://meshcraft.top/admin/documentos/sistema-e-equipe-especialista-do-projeto).

## 15. Fechar com fatos e próximos responsáveis

O fecho precisa mostrar:

- checklist final;
- o que mudou;
- comandos e resultados;
- integração e publicação medidas;
- pendências reais;
- veredito PRONTO ou NÃO PRONTO.

Quando houver tarefas futuras, declare quem executa, qual prova fecha e se a execução começou. Não atribua trabalho em segundo plano sem executor verificável.

## Sequência resumida

```text
pedido
  -> experiência e aceite
  -> leis e fontes
  -> bancada isolada
  -> tarefa e reivindicação
  -> leituras paralelas
  -> mapa de fatos
  -> artefato versionado
  -> tarefas dos achados
  -> revisão adversarial
  -> validação executável
  -> ci/pr.py
  -> checks e integração automática
  -> deploy medido
  -> confirmação do mantenedor
  -> documento privado criado e relido
  -> prestação de contas
```

## Critérios de parada

Pare e registre dívida ou bloqueio quando:

- falta mandato para CODEOWNERS, contrato, pagamento ou produção;
- uma prova depende de credencial ou serviço indisponível;
- o resultado remoto diverge da lei vigente;
- o artefato não pode ser relido na superfície final;
- um passo exigiria declarar como feito algo que não foi medido.

Não pare por escolha técnica rotineira. Resolva-a no menor escopo compatível com o mandato.

## Por que este caso foi rápido

- a leitura foi dividida em perguntas independentes;
- todos trabalharam sobre as mesmas fontes canônicas;
- fatos, hipóteses e propostas não se misturaram;
- o artefato principal teve um único dono;
- a revisão aconteceu antes do PR;
- a validação foi reutilizada em três revisões do código;
- a página privada recebeu síntese, não uma cópia frágil;
- confirmação humana ficou restrita ao gesto externo que realmente precisava dela.

Velocidade aqui significa reduzir espera e retrabalho mantendo cada transição comprovada.

