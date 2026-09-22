# Prompt curto de execução de tarefa

O endereço foi preservado para links existentes. Para um pedido já definido,
cole o bloco abaixo numa sessão do repositório e acrescente a tarefa no fim.
O roteiro completo está em [Prompt de execução](PROMPT-PADRAO-DO-MAESTRO.md).

```text
Execute a tarefa abaixo no sitesdoreino dentro do escopo autorizado.
Leia CLAUDE.md, CONSTITUICAO.md, RITOS.md e instruções dos caminhos envolvidos.
Abra o plano em caixinhas, prepare a bancada pelo ci/sessao.py, confira o
baseline e use contexto direcionado. Escolha competências pela tarefa.

Implemente, rode a validação, revise o diff e publique pelo make pr.
Preserve as leis gerais e as alterações alheias. Declare apenas resultados
medidos. Bloqueio exige fato, impacto, responsável e ação para destravar.
Ao concluir etapa, diga Onde estou: passo N de M. Próximo passo: ação concreta.
Feche com checklist, O que mudou, O que foi verificado, Pendências, Veredito
PRONTO ou NÃO PRONTO e Instruções. Separe validação, integração e publicação.

TAREFA:
```
