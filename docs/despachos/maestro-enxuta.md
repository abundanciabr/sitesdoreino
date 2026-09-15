# Regência com preparo no executor

A Maestro recebe uma decisão preparada; o Codex faz o levantamento e a
montagem dos arquivos. O mantenedor recebe o trabalho executável sem pagar
pela mesma investigação nas duas conversas. A Maestro continua responsável
pelo julgamento e pelo atestado da revisão independente.

## Começar um lote da fila

No PowerShell, dentro de uma bancada atualizada, o executor roda:

```powershell
git fetch origin
python ci/preparar_regencia.py TAR-374 TAR-377 TAR-379 --saida "$env:TEMP/regencia-triade"
```

O resumo organiza tarefas já despachadas. Uma decisão nova ainda exige
conferir o aceite e os riscos no despacho completo.

Os números acima são um exemplo concreto de seleção, não uma autorização
para executar essas tarefas. O resumo informa a revisão consultada e o
estado registrado nela. Reservas e PRs posteriores precisam ser conferidos
na aquisição pela fila; o resumo não reserva trabalho nem autoriza pouso.

O executor entrega à Maestro o resumo gerado. Os despachos completos ficam
nos arquivos indicados para o Codex executar. A Maestro abre um despacho
somente quando a decisão depende de seu conteúdo; os caminhos e a revisão
permitem conferir a fonte sem colar todos os arquivos na conversa.

## Pedido novo

O Codex prepara, sob o mandato do pedido: evidências, recorte dos arquivos,
dependências, proposta de aceite e rascunho do despacho. A Maestro recebe
esse preparo, decide o escopo e as questões de arquitetura ou produto e
devolve apenas as alterações necessárias. O Codex compila o despacho
aprovado com `ci/economia_da_fabrica.py brief`, registra a tarefa e executa.
Não é preciso a Maestro reescrever o arquivo inteiro para aprovar uma frase.

O preparo não autoriza decidir lei, contrato, dinheiro ou acesso. Uma lacuna
que impeça decisão volta ao executor como uma pergunta técnica delimitada;
uma decisão exclusiva do mantenedor continua sendo apresentada a ele.

## Texto para a sessão da Maestro

> Conduza este pedido com o preparo técnico no Codex. Receba o resumo e as
> evidências; confira as fontes necessárias à decisão, preserve as leis e
> decida o recorte e o aceite. Para tarefas já cadastradas, o executor usa
> `ci/preparar_regencia.py` e entrega o resumo, com os despachos completos em
> arquivos. Para trabalho novo, ele prepara o rascunho para sua decisão.
> Devolva mudanças pontuais, sem reescrever material aprovado. Faça uma
> passagem de decisão por lote; investigação, montagem e correção ficam
> com o executor. Um achado novo relevante exige nova decisão explícita.
> Revisão independente, atestado e portão de pouso continuam obrigatórios.
> Não espere a execução nem os checks. Registre apenas a decisão nova e
> encerre com o próximo responsável e a evidência que ele precisa devolver.

## Como comprovar a meta

O pedido do mantenedor é reduzir custo **e** tempo a no máximo 10%.
Os totais relatados de 11,2 milhões de tokens-peso e 227 minutos implicam
limites absolutos de 1.120.000 tokens-peso e 22,7 minutos para sete sessões.
Esses números são a referência do pedido, não uma medição validada.
O relatório anterior mistura espera humana e durações paralelas; os
transcripts continuaram mudando depois dele. Não se reconstrói a medição
original apenas somando os arquivos atuais.

O tamanho do resumo mede somente a redução de texto deste preparo. Não mede
tokens faturados, preço da assinatura, tempo de raciocínio, revisão nem o
ciclo completo. Este comando não impõe um teto de gasto ao Claude Code.

Compare sete entregas de escopo e qualidade equivalentes. Congele uma cópia
local dos transcripts, com SHA256, antes de calcular: sessões em andamento
mudam o total durante a leitura. Preserve os identificadores das sessões e
a revisão de cada entrega. Conte uma vez cada resposta da API, inclusive
quando o mesmo `requestId` aparece em dois arquivos. Use a contagem final de
saída, pois os primeiros blocos de uma resposta podem trazer uso parcial.
Separe entrada, leitura e escrita de cache e saída, usando
os mesmos pesos nos dois lotes. Calcule tempo ativo pela união dos
intervalos, separando espera humana e trabalho paralelo. Apresente também
o tempo entre pedido e entrega e o custo transferido ao Codex e ao
Antigravity, para não chamar transferência de economia total.

Antes de declarar a meta atingida, exija custo e tempo posteriores de até
10% da base congelada, medidos pelo mesmo método, além dos limites absolutos
acima e do aceite das sete entregas. Sem comparação válida dos dois lotes,
o resultado é **meta ainda não comprovada**. O relatório anterior usa
tokens-peso, não custo real da conta.

## Conferência pelo Antigravity

Entregue ao Antigravity o PR, o SHA, as provas dos testes, o comando de
preparo e as medições dos dois lotes. Ele deve verificar, contra
`origin/main` após o merge, que os despachos foram preservados, que o resumo
não oculta bloqueios e que a comparação mantém escopo e qualidade. Os
transcripts permanecem locais; publique apenas os agregados necessários,
sem conteúdo de conversas ou credenciais.

Esse roteiro não aciona a sessão do Antigravity. A participação dele só está
comprovada quando houver uma verificação produzida por ele.
