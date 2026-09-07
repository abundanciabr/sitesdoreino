# A obra do mantenedor fica fora da lei do travessão

**Decidido por ele em 06/09/2026**, em pergunta estruturada, com o número na
mesa. Esta página existe porque o `CLAUDE.md` só carrega a lei; o porquê mora
aqui.

## O que mudou, em uma frase

O texto das aulas e o do livro saem como ele escreveu, com travessão, e nenhuma
tela do site pede reescrita nem conta riscas.

## O que aconteceu

Em 06/09/2026 o importador de capítulo entrou no ar e ele mandou o primeiro
capítulo de verdade, a Encomenda 08. As 16 peças entraram. E a tela do editor
abriu com um bloco amarelo listando **67 frases com travessão**, uma a uma, com
o nome da peça e a linha, dizendo que "antes de publicar vale reescrever cada
uma".

A medição no arquivo dele: **88 riscas** (82 travessões longos e 6 meia-riscas),
em 78 linhas, num capítulo só. Nos 34 capítulos, por volta de **3.000**.

## As opções que ele teve, e a que ele escolheu

Foram quatro, com a consequência de cada uma escrita:

1. uma IA reescrever e ele aprovar frase a frase (a recomendada pelo agente);
2. **a lei deixar de valer para o texto do curso** (a escolhida);
3. ele mesmo reescrever, aos poucos, antes de publicar cada capítulo;
4. publicar assim e decidir depois.

Ele escolheu a 2.

## Por que a escolha dele é coerente, e não uma exceção de conveniência

A lei do travessão nasceu para o texto que a CASA escreve: as telas, os rótulos,
os avisos, os documentos. Ali a risca é quase sempre preguiça de pontuação, e a
regra melhora a escrita.

O livro é outra coisa. É **obra autoral não lançada**, com voz própria, e o
travessão nela é escolha de estilo de quem escreve, não descuido. Aplicar a
regra da casa à obra do autor seria a casa editando o livro dele, que é
exatamente o que nenhuma ferramenta deveria fazer sozinha.

É a mesma razão que já valia na Biblioteca do Livro desde 04/09/2026, onde o
travessão sempre avisou em vez de recusar. O que mudou hoje é que a incoerência
acabou: antes o site guardava a obra intacta e, na tela seguinte, mandava
reescrevê-la.

## O que NÃO mudou

Nada afrouxou fora da obra. `templates/`, `traducoes/`, `documentos/`,
`management/commands/` e o rótulo de todo `TextChoices` continuam sob a lei, com
os mesmos portões. O `ci/travessao.py` não foi tocado: ele vigia arquivos, e a
obra nunca esteve em arquivo (o repositório é público, e o texto das aulas mora
só no banco).

## O que foi removido, e por quê

O bloco de aviso do editor de encomendas, a função que contava as riscas e a
menção a elas no registro de auditoria. Depois desta decisão, contar riscas na
obra não serve a ninguém: ele veria a mesma parede amarela 34 vezes, sobre uma
regra que não vale ali. O guarda que ficou no lugar afirma a AUSÊNCIA do aviso,
para que nenhuma sessão futura o traga de volta achando que corrige um
esquecimento.

## O que isto muda no plano da célula de cursos

O `PLANO-CELULA-CURSOS.md` §7 previa que o Revisor de coerência (degrau 3.1)
apontasse "o travessão que voltar" para a pessoa reescrever. Essa linha morre:
o Revisor de coerência continua conferindo remissões, nomes canônicos e números
repetidos, e não olha risca nenhuma.
