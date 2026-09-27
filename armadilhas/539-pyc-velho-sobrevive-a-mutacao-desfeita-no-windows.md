---
schema_version: 2
armadilha: 539
estado: documentada
degrau: 2
confianca: media
custo_por_queda: medio
gatilho:
  - "__pycache__/"
sinal:
  - "vermelho nao aparece depois da sabotagem"
guarda:
  tipo: nenhum
  motivo: "o bytecode fica fora do controle de versao; ensinar o rito a limpar __pycache__ sozinho e mudanca de ambiente/CI, fora do alcance de uma entrada de licao"
licao: "Mutacao feita reescrevendo o arquivo .py no Windows pode deixar um .pyc velho em __pycache__ carregado depois de a sabotagem ser desfeita (ou mesmo durante ela, se o interpretador ja tinha compilado a versao anterior). Rode a prova por mutacao com PYTHONDONTWRITEBYTECODE=1 e apague __pycache__ antes de cada rodada, para o teste ler sempre o .py atual, nunca um bytecode desatualizado."
---

# 539: `.pyc` velho sobrevive à mutação desfeita no Windows

**Data:** 27/09/2026 · **Onde:** prova por mutação (Lei 6), TAR-847, obra
Comunidade · **Custo evitado:** um veredito de mutação (vermelho ou verde)
calculado sobre bytecode antigo, não sobre o arquivo `.py` que estava de
fato no disco na hora do teste.

## Sintoma

Depois de sabotar um arquivo `.py` para a prova vermelho→verde e depois
desfazer a sabotagem, uma rodada seguinte de testes no Windows por vezes lê
comportamento que não corresponde ao conteúdo atual do arquivo: o
`__pycache__/*.cpython-*.pyc` gerado durante a sabotagem (ou antes dela)
continua no disco e é reaproveitado pelo interpretador se o carimbo de
modificação do `.py` não muda de um jeito que o Python detecte, mascarando o
vermelho esperado ou reintroduzindo o comportamento sabotado depois do
"desfaz".

## Causa

O CPython grava `.pyc` em `__pycache__/` como cache de bytecode, validado
por metadados do arquivo fonte (tamanho e hora de modificação, por padrão).
Reescrever o arquivo rapidamente durante um ciclo de sabotagem e restauração
no Windows pode preservar metadados que o cache considera válidos, ou o
`.pyc` antigo simplesmente não é invalidado a tempo entre a escrita da
sabotagem e a leitura do teste. O bytecode não é rastreado pelo Git nem
listado no `git status`, então nada avisa que ele existe ou que está
desatualizado.

## Solução

1. Rode a prova por mutação com a variável de ambiente
   `PYTHONDONTWRITEBYTECODE=1`, para o interpretador nunca escrever `.pyc`
   durante o ciclo.
2. Apague `__pycache__/` (do módulo sabotado, ou de toda a árvore da
   bancada) antes de cada rodada de mutação, garantindo que o teste sempre
   compile o `.py` atual do zero.
3. Se o vermelho esperado não aparecer, confira primeiro se existe
   `__pycache__` residual antes de suspeitar do guarda ou do teste.

## Origem

Relatório da TAR-847, obra Comunidade, 27/09/2026.
