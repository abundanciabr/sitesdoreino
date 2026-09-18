# Como registrar uma contribuição

Leia primeiro `docs/consultorias/fase-4-otimizacao/FASE-4-CONSELHO.md`. IDs de autores: `codex`, `claude`,
`antigravity`. Os exemplos abaixo explicam o formato; **não são propostas,
votos ou medições reais** e não devem ser copiados como evidência.

Use nomes que identifiquem proposta, tipo e autor, como
`CODEX-001-proposta.json`, `CODEX-001-voto-claude.json` e
`CODEX-001-verificacao-antigravity.json`, dentro de `registros/`.
Datas são ISO 8601 com fuso. Grave cada arquivo inteiro antes de pedir a leitura.
Preserve versões anteriores. Não altere arquivos assinados por outra ferramenta.

## Proposta

Objeto JSON com `tipo: "proposta"`, `id`, `autor`, `registrado_em`, `problema`,
`titulo`, `baseline` e `aceite`. `baseline` referencia comando, saída e revisão
real examinada; `aceite` define como provar resultado completo, sem regressão.
Acrescente `origem` quando houver ideia de outra IA. Não reivindique a autoria
de uma sugestão já existente em outro documento.

Execute `placar.py`: a lista de propostas mostra o SHA256 que os votos precisam
referenciar. Revisão da proposta também pode ser calculada com `assinatura`
do módulo, que usa JSON canônico; não use o hash dos bytes brutos do arquivo.

## Voto

Objeto com `tipo: "voto"`, `proposta` (o ID), `autor`, `registrado_em`,
`proposta_sha256`, `decisao`, `importancia` e `justificativa`.

`decisao` aceita `aprovar`, `reprovar` ou `abster`. Aprovação usa importância
inteira 1, 2 ou 3, segundo a régua do regulamento. Os outros votos usam 0.
A autora da proposta não pode votar. Cada colega precisa votar antes da
implementação e explicar o que conferiu e o que o faria mudar de posição.

## Implementação

Objeto com `tipo: "implementacao"`, `proposta`, `autor` (quem executou),
`registrado_em`, `proposta_sha256`, `prova`, `prova_sha256`, `resultado`, `minutos_totais`,
`custo_reais` e `fonte_custo`.

`prova` é um arquivo local existente e não vazio, com caminho relativo à raiz
do projeto. `prova_sha256` é o SHA256 dos bytes desse arquivo; mudar a prova
invalida o registro. Guarde nela os comandos, revisão examinada, saída e a
demonstração do aceite. `minutos_totais` é tempo observado total, incluindo falhas e revisão.
Sem fonte de dinheiro, `custo_reais` é `null` e `fonte_custo` fica vazia.
Com valor monetário, informe número não negativo e a fonte de preço e consumo.
Custos não medidos ficam fora de alegações de economia.

Uma implementação por proposta. O custo observado da contribuição fica associado
à executora identificada, incluindo o percurso completo, não só seu tempo de código.
Se a executora for diferente da autora, o protótipo mostra `autoria_pendente`
e não atribui pontos a nenhuma das duas. O acordo de crédito compartilhado deve
ser resolvido e a regra aceita antes de uma rodada que inclua coautoria;
este protótipo não distribui esse crédito automaticamente.
Implementar sem aprovação prévia continua aparecendo como trabalho e custo,
mas não recebe pontos. Não registre dados fictícios para completar campos.

## Verificação

Objeto com `tipo: "verificacao"`, `proposta`, `autor`, `registrado_em`,
`implementacao_sha256`, `decisao`, `justificativa`, `prova` e `prova_sha256`.

`decisao` aceita `confirmar`, `recusar` ou `abster`. A prova é o arquivo da
conferência feita pela revisora, não uma aprovação baseada apenas no relato
da autora. Hash é obtido com `assinatura` aplicado ao registro da implementação.
As verificações precisam ser posteriores à implementação. A autora da proposta
não pode verificar a própria contribuição para pontuar.

## Correção, recusa e ausência

Faltou campo ou há JSON inválido: corrija seu registro e execute novamente.
Registro já votado não se reescreve: uma mudança exige nova revisão, outro ID
e novas concordâncias. Antes do fechamento de pontuação, preserve uma objeção
em arquivo próprio e peça aos pares que a examinem. Não esconda regressão após
a aprovação; a classificação fica suspensa até revisar as evidências afetadas.

A ausência de voto mantém `aguarda_votos`; duas aprovações sem código mantêm
`aguarda_implementacao`; código sem as duas provas fica `aguarda_verificacao`.
Voto negativo resulta em `reprovada`; conferência negativa em `recusada`.
Só `pontua` soma importância. Nenhum desses estados cancela assinaturas.

Não há autenticação de autor nem diário imutável garantidos pelo JSON. A
coordenadora confere autoria e preserva os arquivos antes de encerrar a rodada.
Não use o placar como prova de independência, nem como decisão financeira automática.
