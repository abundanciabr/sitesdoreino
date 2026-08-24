<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §5 — Portões mecânicos do CI (eles reprovam de verdade)
     ID historico: §5.7  ·  referencias antigas "ARMADILHAS §5.7" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 5.7 O freeze passa verde e a mudança de API é real

**Sintoma:** `contrato/<celula>  PASS`, e mesmo assim o comportamento público mudou.
**Causa:** a comparação documental só enxerga o que o exportador da célula emite. Duas
perdas conhecidas, ambas medidas:

1. **`auth=None` some do documento.** O django-ninja 1.3 **omite** a chave `security`
   das operações com `auth=None`, em vez de emitir `security: []`. Pela especificação,
   operação sem `security` **herda** a do documento — então o schema descreve uma rota
   pública como se fosse autenticada.
2. **Os exportadores apagam o resto.** `catalogo`, `checkout`, `alunos` e `leads` fazem
   `operation.pop("security", None)` sem condição em `export_openapi.py` (`pagamentos`
   já faz o certo: só remove quando é igual à global).

Somadas, tornar `/sites/by-host/{host}` público em catalogo produziu **zero diferença**
no contrato exportado — freeze verde.
**Solução (já no lugar):** `ci/contract_freeze.py` mede a autenticação na **fonte**
(`op.auth_callbacks` do ninja), não no documento, e reprova divergência — linha
`seguranca/<celula>` do relatório.
**Se você mexer em `export_openapi.py`:** qualquer campo que você remova ali deixa de
ser protegido pelo freeze. Remova só ruído do gerador (ex.: `title` do pydantic), nunca
informação contratual — e escreva o porquê no comentário.
**Origem:** PR #22.
