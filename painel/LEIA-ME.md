# painel/ — o livro de ocorrências e o painel do dono

> Nascido em 26/08/2026 da reforma dos painéis — decisão do mantenedor após 8
> rodadas de consultoria externa (5 IAs), análise completa em
> `docs/paineis/VEREDITO-DAS-CONSULTORIAS.html`. A lei que este diretório impõe:
> **nenhum fato do projeto mora em dois lugares; acontecimento se acrescenta;
> estado se calcula.**

## O que mora aqui

| Arquivo | O que é | Quem mexe |
|---|---|---|
| `painel.html` | **A porta.** O painel que o mantenedor abre (duplo clique). Não guarda NENHUM dado próprio — toda vista é calculada dos registros. | Muda raramente, por PR, como código. |
| `registros/*.js` | **O livro de ocorrências.** Um arquivo pequeno por acontecimento. Só se ACRESCENTA — nunca se edita nem se apaga um registro existente. | Toda sessão, ao terminar trabalho relevante. |
| `manifesto.js` | **GERADO** por `gerar_manifesto.js`. Lista os registros para a página (em `file://` o Chrome não deixa a página descobrir arquivos sozinha). | Só o gerador. Nunca à mão. |
| `logica.js` | As regras que calculam as vistas (caixa de entrada, frescor, capa). Pura, roda em Node e no navegador. | Por PR, com teste-guarda. |
| `gerar_manifesto.js` | Valida TODOS os registros (fail-closed, com a MESMA `logica.js` da página — um validador só) e regenera o manifesto. `--conferir` só confere (para CI). | Por PR. |
| `testes/` | Testes-guarda da lógica e do gerador — incluindo os casos em que devem REPROVAR. | Por PR. |

## Como registrar um acontecimento (o gesto de toda sessão)

1. Crie **um arquivo novo** em `registros/`, nome
   `AAAAMMDD-NNN-slug.js` (data de hoje · sequência livre do dia · slug curto).
   **Nunca edite um registro existente** — atualização é um registro NOVO
   (se ele fecha um pedido, aponte `responde_a`).
2. Conteúdo — exatamente este molde (copie de um registro existente):

```js
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-001-exemplo",      // = nome do arquivo sem .js (o gerador confere)
  tipo: "entrega",                      // decisao | pendencia | resposta | entrega | incidente | medicao | frente | nota
  quando: "2026-08-26",                 // quando o FATO aconteceu (não quando você escreveu)
  titulo: "Uma linha, para leigo, sem sigla",
  detalhe: "Texto simples, sem HTML. Parágrafos separados por \\n\\n.",
  autoridade: "github",                 // quem tem o DIREITO de declarar isto: mantenedor | github | sonda | rito | sessao
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/999",  // ou null
  verificado_em: "2026-08-26",          // quando a EVIDÊNCIA foi conferida — ou null (vira "não comprovado")
  precisa_do_dono: false,               // true = entra na caixa de entrada até existir resposta
  responde_a: null,                     // arquivo de outro registro que este fecha — ou null
  gravidade: "info",                    // vermelho | ambar | info | verde
  frente: null,                         // só p/ tipo "frente": site | comunidade | curso | vender | fabrica
  vence_em_dias: null                   // depois de N dias sem registro novo, isto conta como velho — ou null (não vence)
});})();
```

3. Rode `node painel/gerar_manifesto.js` (da raiz). Ele valida tudo e
   regenera `manifesto.js`. **Se ele reprovar, o registro está errado — conserte;
   não contorne.**
4. Confira abrindo `painel/painel.html` (ou o teste: `node painel/testes/teste_logica.js`).

## As regras que a lógica impõe (não são convenção — são código com teste)

- **Caixa de entrada calculada:** pendência = registro `precisa_do_dono: true`
  sem nenhum outro registro com `responde_a` apontando para ele. Uma lista
  calculada não consegue esquecer um pedido.
- **Verde é conquistado:** `gravidade: "verde"` exige `evidencia` E
  `verificado_em`. Sem prova conferida, o gerador reprova. Relato sem evidência
  aparece como "não comprovado", nunca como verde.
- **Dois relógios:** `quando` (o fato) ≠ `verificado_em` (a prova). A página
  mostra os dois; o segundo é o que importa.
- **Frescor computado:** a página compara as datas com o relógio dela ao abrir.
  Seção velha se desbota sozinha e diz há quantos dias. Ninguém escreve "atualizado".
- **Teto da capa:** a capa recusa construir com mais blocos que o teto — em vez
  de crescer, ela quebra visivelmente e diz o que precisa sair.
- **Autoridade:** cada tipo de fato tem quem pode declará-lo. Painel nenhum é
  origem de fato — todo painel é espelho.

## O que NÃO fazer

- ❌ Editar um registro existente (nem "só para corrigir um typo" — registro
  novo com `responde_a`).
- ❌ Editar `manifesto.js` à mão.
- ❌ Escrever HTML dentro de `titulo`/`detalhe` (a página insere como texto).
- ❌ Criar lista/estado em qualquer outro lugar e "sincronizar depois" — é
  exatamente a doença que este diretório existe para curar.
