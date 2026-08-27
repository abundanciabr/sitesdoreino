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
| `ia/` | **Mapa técnico do projeto para IA** (`ia/INDICE.md` é a porta) — infraestrutura, arquitetura de células, CI/CD, decisões de produto, escrito para uma IA sem contexto prévio auditar o sistema e sugerir melhorias. Segue a mesma lei deste diretório: não guarda veredito próprio sobre o estado do projeto, só mapeia mecanismo — quem quiser saber "o que está pendente" continua lendo `registros/`, nunca `ia/`. | Por PR, junto com a mudança que descreve. |

## Como registrar um acontecimento (o gesto de toda sessão)

1. Crie **um arquivo novo** em `registros/`, nome
   `AAAAMMDD-NNN-slug.js` (data de hoje · sequência livre do dia · slug curto).
   **Nunca edite um registro existente** — atualização é um registro NOVO
   (se ele fecha um pedido, aponte `responde_a`). Se outra sessão pegou o
   mesmo `NNN` ao mesmo tempo (é corrida, não erro seu), não precisa checar a
   pasta à mão antes de gravar — o passo 3 abaixo reprova e já diz para qual
   número renomear.
2. Conteúdo — exatamente este molde (copie de um registro existente):

```js
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-001-exemplo",      // = nome do arquivo sem .js (o gerador confere)
  tipo: "entrega",                      // decisao | pendencia | resposta | entrega | incidente | medicao | frente | rumo | nota
  quando: "2026-08-26",                 // quando o FATO aconteceu (não quando você escreveu)
  titulo: "Uma linha, para leigo, sem sigla",
  detalhe: "Texto simples, sem HTML. Parágrafos separados por \\n\\n.",
  autoridade: "github",                 // quem tem o DIREITO de declarar isto: mantenedor | github | sonda | rito | sessao
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/999",  // ou null
  verificado_em: "2026-08-26",          // quando a EVIDÊNCIA foi conferida — ou null (vira "não comprovado")
  precisa_do_dono: false,               // true = entra na caixa de entrada até existir resposta
  responde_a: null,                     // arquivo de outro registro que este fecha — ou null
  gravidade: "info",                    // vermelho | ambar | info | verde
  frente: null,                         // etiqueta do capítulo do "Meu mapa": site | comunidade | curso | vender | fabrica
                                        // (obrigatória em "frente" e em "rumo"; opcional e recomendada no resto)
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
- **Número do dia é único — a trava é mecânica, não combinado:** duas sessões
  podem ler a pasta no mesmo minuto e escolher o mesmo `NNN` — aconteceu de
  verdade em 26/08/2026, quatro vezes num único dia (registro
  `20260826-041-o-livro-passou-a-recusar-numero-repetido`). `validarRegistros`
  (`painel/logica.js`) reprova (FAIL) qualquer `AAAAMMDD-NNN` usado por mais de
  um registro — a mesma família de trava que `ci/indice_de_armadilhas.py` já
  tem para `armadilhas/` (`armadilhas/085`), rodando em todo PR pela
  `muralhas`. Colidiu? A mensagem de erro já traz o próximo número livre:
  renomeie o arquivo E o campo `arquivo` (os dois têm de bater) e rode
  `node painel/gerar_manifesto.js` de novo. As duas colisões de 26/08 ficam
  congeladas de propósito (registro mergeado não se edita); um terceiro
  registro *nesses* números, porém, ainda reprova — a tolerância guarda o
  tamanho do par herdado, não uma licença permanente.
- **Dois relógios:** `quando` (o fato) ≠ `verificado_em` (a prova). A página
  mostra os dois; o segundo é o que importa.
- **Frescor computado:** a página compara as datas com o relógio dela ao abrir.
  Seção velha se desbota sozinha e diz há quantos dias. Ninguém escreve "atualizado".
- **Teto da capa:** a capa recusa construir com mais blocos que o teto — em vez
  de crescer, ela quebra visivelmente e diz o que precisa sair.
- **Autoridade:** cada tipo de fato tem quem pode declará-lo. Painel nenhum é
  origem de fato — todo painel é espelho.
- **O mapa não inventa futuro:** a vista "Meu mapa" mostra os cinco capítulos
  sempre, cada um com o rumo registrado daquela frente. Frente sem `rumo` diz
  *"não sei para onde esta frente vai"* — nunca uma tela vazia, que se leria
  como "nada planejado". E **`rumo` nunca é verde**: verde é prova conferida, e
  o futuro não se prova. Quando um rumo vira realidade, quem o fecha é um
  registro novo com `responde_a` apontando para ele — a mesma mecânica da caixa.

## O que NÃO fazer

- ❌ Editar um registro existente (nem "só para corrigir um typo" — registro
  novo com `responde_a`).
- ❌ Editar `manifesto.js` à mão.
- ❌ Escrever HTML dentro de `titulo`/`detalhe` (a página insere como texto).
- ❌ Criar lista/estado em qualquer outro lugar e "sincronizar depois" — é
  exatamente a doença que este diretório existe para curar.
