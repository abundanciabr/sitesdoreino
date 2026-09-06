---
schema_version: 2
armadilha: 347
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: teste
  dono: services/admin/tests/test_relatorio_da_fundacao_no_banco.py
sinal:
  - arquivo novo em `documentos/`, deploy-celula `success`, e `curl https://meshcraft.top/docs/<nome>` devolve 404
  - `importar_da_pasta` só na migração `0003`
gatilho:
  - documentos/*
licao: criar o arquivo em `documentos/` NÃO publica a página: a semeadura da pasta roda uma vez só. Documento novo exige a migração de dados que o importa, no mesmo PR.
---

# Documento NOVO em `documentos/` não vira página: a semeadura da pasta roda uma vez

**Sintoma.** Você cria `documentos/<nome>.md` com `publico: true`, a suíte da
`admin` fica verde (inclusive `test_todo_documento_do_repositorio_tem_titulo_e_renderiza`,
que abre o seu arquivo e o desenha), o PR pousa, o `deploy-celula` termina em
`success` conferido por `gh run view <id> --json conclusion`, e
`https://meshcraft.top/docs/<nome>` responde **404**. A lista em `/docs/`
não mostra o documento. Nada está vermelho.

**Causa.** Desde 31/08/2026 (`DECISAO-o-editor-de-documentos.md`) a fonte de
`/docs/…` é o **banco**, e a pasta é SEMENTE: quem a lê é a migração `0003`,
`get_or_create` por nome, e **migração tem memória de já ter rodado**. No banco
de produção ela rodou em 31/08/2026 e nunca mais. Um arquivo que nasce depois
disso é lido por ninguém em produção.

A suíte não avisa, e nunca vai avisar: no banco de teste a `0003` roda do zero
a cada sessão e semeia a pasta inteira, **inclusive o seu arquivo novo**. É a
irmã da `armadilhas/253` (texto CORRIGIDO no arquivo não muda o banco); esta é
a versão para texto NOVO, e ela engana mais, porque o teste que abre o arquivo
fica verde de verdade.

**Solução.** Documento novo entra por **migração própria**, que semeia SÓ ele:

```python
from apps.core.documentos import semear_documento

def semear(apps, schema_editor):
    semear_documento(apps.get_model("core", "Documento"), "<nome>")
```

Molde completo: `services/admin/apps/core/migrations/0007_semear_o_relatorio_da_fundacao.py`.
Três regras que o molde carrega, e o porquê de cada uma:

1. **Só o nome pedido, nunca `importar_da_pasta` de novo.** A pasta inteira é
   da `0003`, que roda uma vez por desenho; uma segunda passagem teria de
   decidir o que fazer com cada documento que já existe.
2. **`get_or_create`, nunca `update`.** Se o mantenedor já criou ou editou
   aquele nome pela tela, a migração não encosta.
3. **Sem a pasta, sem o arquivo: não faz nada.** Falhar derrubaria a célula
   inteira no `migrate` por um passo de conteúdo (H18).

E o teste da migração **fabrica o estado de produção**: apaga a linha que a
`0003` criou no banco de teste e só então chama a função da migração. Sem isso
o teste fica verde sem exercitar uma linha dela (molde:
`test_relatorio_da_fundacao_no_banco.py`, mesmo desenho de
`test_reembolso_no_banco.py`).

**Depois do deploy, confira a URL, não o run:**

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://meshcraft.top/docs/<nome>   # 200
```
