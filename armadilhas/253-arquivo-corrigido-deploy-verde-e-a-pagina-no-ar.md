---
schema_version: 2
armadilha: 253
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: `o portao vigia ARQUIVOS por construcao, e nunca vera o banco de producao: ele roda no CI, sem credencial e sem dados. Um portao que tentasse comparar arquivo com banco precisaria de acesso ao banco vivo a cada PR, que e exatamente o que a plataforma nega ao robo (Lei 5). A cura e de METODO: conferir a URL publica com curl depois do deploy, e semeador tocado sempre pergunta "isto ja foi semeado?".`
sinal:
  - `get_or_create` em semeador de conteudo
  - `importar_da_pasta`
---

# Arquivo corrigido, deploy VERDE, e a página no ar continua com o texto antigo

**Sintoma.** Você corrige o texto num `.md` (ou num semeador), o PR passa, o
`deploy-celula` termina em `success` conferido por
`gh run view <id> --json conclusion` — e o `curl` na URL pública devolve **a
frase de ontem**. Nada está vermelho. Nenhum portão reclamou. A suíte inteira
está verde.

Medido em 31/08/2026:

```bash
gh run view 33428940804 --json conclusion   # -> "success"
curl -s https://meshcraft.top/docs/como-funciona-a-entrada | grep Reembolsado
# <li><strong>Reembolsado</strong>: você devolveu o dinheiro e <strong>continua entrando</strong>…
```

**Causa.** Aquele conteúdo **não é servido do arquivo**. O arquivo é só a
**semente**, e a semeadura roda **uma vez**, com `get_or_create`, que **por
desenho não altera o que já existe** — para nunca pisar numa edição que o
mantenedor fez pela tela.

Dois casos já aconteceram nesta casa, e o segundo é o pior porque a fonte tinha
acabado de mudar:

| Onde | Fonte real | Semeador |
|---|---|---|
| áreas do fórum | banco | `semear_areas` (`get_or_create` por slug) |
| documentos de `/docs/…` | banco, **desde 31/08/2026** (`DECISAO-o-editor-de-documentos.md`) | `documentos.importar_da_pasta`, chamado só pela migração `0003` |

**Corrigir a receita não muda o bolo que já foi assado.**

**Por que a suíte não avisa, e nunca vai avisar.** O teste roda em banco novo, e
a semeadura o preenche a partir dos arquivos **já corrigidos**. O `UPDATE` de
uma migração de correção não encontra linha nenhuma, e o teste fica verde sem
ter exercitado uma única linha dela. Verde de banco novo é cego para banco
antigo, e banco antigo é o único que existe em produção.

**Solução.**

1. **Depois de todo deploy que muda texto publicado, confira a URL pública**, e
   não o `conclusion` do run. Deploy verde prova que a imagem subiu, nunca que
   o texto mudou:

   ```bash
   curl -s https://meshcraft.top/<caminho> | grep -i "<a frase nova>"
   ```

2. **Ao tocar um semeador, pergunte SEMPRE "isto já foi semeado em produção?"**
   Se foi, o conserto é uma **migração de dados**, e o molde está em
   `services/forum/apps/forum/migrations/0003_travessao_fora_da_descricao_das_areas.py`
   e em `services/admin/apps/core/migrations/0005_o_reembolso_no_texto_que_ja_esta_no_banco.py`.

3. **A migração casa o trecho antigo inteiro e troca só o TRECHO**, nunca o
   corpo: se o mantenedor já reescreveu aquele pedaço, ela não faz nada; se ele
   editou outro ponto do mesmo documento, a edição dele fica. O pior desfecho de
   uma migração de correção de texto é sobrescrever texto melhor.

4. **O teste dela precisa FABRICAR o estado de produção** — criar à mão a linha
   com o texto de ontem — ou ele é um teste que não testa nada
   (`armadilhas/252`, a mesma família).

5. **O reverso é um no-op declarado.** Um `migrate` para trás é coisa que se faz
   às pressas, num rollback, sem ninguém lendo o código: ele não pode
   republicar em silêncio a frase que o mantenedor mandou tirar.

**Origem.** As duas quedas foram achadas por PESSOA olhando o site, nunca por
portão. Em 30/08/2026 o mantenedor viu um travessão sobrevivendo no fórum
depois de eu reportar tudo limpo. Em 31/08/2026, quase de novo, com o texto do
reembolso: dessa vez o `curl` pós-deploy pegou antes de eu fechar o relatório.
Registro: `painel/registros/20260831-091-a-pagina-no-ar-nao-tinha-mudado.js`.
