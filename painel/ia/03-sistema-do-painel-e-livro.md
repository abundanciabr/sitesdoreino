# painel/ia — 03. O Sistema do Painel e o Livro de Registros

> Parte do [Mapa para IA](INDICE.md) do sitesdoreino. Resumo curado — a fonte
> de verdade é `painel/LEIA-ME.md`, `painel/logica.js` e os arquivos reais em
> `painel/registros/`. **Este próprio documento (`painel/ia/`) segue a
> mesma lei anti-duplicação descrita aqui: ele não guarda nenhum veredito
> próprio sobre o estado do projeto, só mapeia mecanismo e arquitetura.**

## Arquitetura em uma frase

`painel/` é um livro de ocorrências (event sourcing) mais um renderizador
100% puro. Regra central, repetida literalmente no código-fonte e na lei do
projeto: **"acontecimento se acrescenta; estado se calcula."** Nenhum arquivo
em `painel/` guarda estado — toda vista é `f(registros[], agora)`.

| Arquivo/pasta | Papel | Quem mexe |
|---|---|---|
| `painel/registros/*.js` | O livro. Um arquivo por acontecimento, cada um empurra **exatamente 1** objeto para `window.REGISTROS`. Nunca editado depois de criado. | Toda sessão relevante, ao terminar trabalho |
| `painel/logica.js` | Regras de cálculo puras (sem DOM/rede/relógio — quem chama passa `agora`). Roda idêntica em Node (gerador) e no navegador (página). | PR + teste-guarda |
| `painel/gerar_manifesto.js` | Valida TODOS os registros com a mesma `logica.js` e MONTA a página: injeta as regras e o resumo em `painel.template.html`, e empacota o passado em um `livro-AAAAMM.js` por mês. `--conferir` só audita (usado pela CI). O nome é herança de quando ele só escrevia um manifesto. | Só o gerador, nunca à mão |
| `painel/painel.template.html` | A FONTE da página — é este que se edita. Tem o marcador `__DADOS_DO_PAINEL__` onde o gerador injeta regras e resumo. | PR |
| `painel/painel.html` | **GERADO.** A página que o mantenedor abre — HTML+CSS+JS+dados num arquivo só, fail-closed total. **Abrir custa UM pedido**, com 90 registros ou com 90 mil. | Só o gerador, nunca à mão |
| `painel/livro-AAAAMM.js` | **GERADO**, um por mês: o conteúdo daquele mês, buscado só quando a Memória é aberta. Mês fechado nunca mais é reescrito. | Só o gerador, nunca à mão |
| `painel/testes/` | `teste_logica.js` (~50 casos, cada regra provada nos dois sentidos) e `teste_gerador.js` (roda o gerador como subprocesso real, prova os 3 estados de saída) | PR |
| `ci/muralha-do-painel.sh` | Roda os testes acima em todo PR (exit 0/1/2 — ERROR nunca vira PASS) | — |
| `ci/divida_do_livro.py` | Segunda trava, na porta de merge: PR mergeado sem nenhum registro citando seu número vira "dívida" que bloqueia o **próximo** merge | — |

## Schema do registro, campo a campo

Molde oficial em `painel/LEIA-ME.md`, validado por `validarRegistros()` em
`logica.js` — a mesma função roda no gerador e na página ("um validador só,
imposto dos dois lados").

| Campo | Tipo/enum | Obrigatório | Regra |
|---|---|---|---|
| `arquivo` | string | sim | Igual ao nome do arquivo sem `.js`; padrão `AAAAMMDD-NNN-slug`; único |
| `tipo` | `decisao \| pendencia \| resposta \| entrega \| incidente \| medicao \| frente \| rumo \| nota` | sim | — |
| `quando` | data ISO | sim | Quando o FATO aconteceu, não quando foi escrito |
| `titulo` | string | sim | Texto puro — `<` no valor reprova (nunca HTML) |
| `detalhe` | string | sim | Idem; `\n\n` separa parágrafos |
| `autoridade` | `mantenedor \| github \| sonda \| rito \| sessao` | sim | Quem tem o DIREITO de declarar o fato |
| `evidencia` | string ou `null` | não | Se presente, não pode ser vazio |
| `verificado_em` | data ISO ou `null` | não | Quando a evidência foi CONFERIDA (≠ `quando`) |
| `precisa_do_dono` | **boolean literal** | sim | `true`/`false` sem aspas — string `"true"` ou campo ausente reprova |
| `responde_a` | string (arquivo de outro registro) ou `null` | não | Deve apontar para registro existente; nunca para si mesmo |
| `gravidade` | `vermelho \| ambar \| info \| verde` | sim | `verde` exige `evidencia` **e** `verificado_em` |
| `frente` | `site \| comunidade \| curso \| vender \| fabrica` ou `null` | condicional | Obrigatória se `tipo` é `frente`/`rumo`; opcional no resto |
| `vence_em_dias` | número ou `null` | não | Comparado com `quando` para marcar "vencido" |

Regra extra: `tipo: "rumo"` nunca pode ter `gravidade: "verde"` — "verde é
prova conferida, e o futuro não se prova". Não existe um 5º valor de
`gravidade` para "não sei" — isso é um *selo* renderizado por cima
("não comprovado", "sem registro", "vencido"), não um valor de enum: o dado
tem 4 estados, a tela mostra efetivamente 5.

## Como cada vista é calculada (a regra exata, não só o nome)

Tudo em `painel/logica.js`:

- **Caixa de entrada** — `precisa_do_dono === true` sem nenhum outro
  registro com `responde_a` apontando para ele; ordenada do pedido mais
  velho para o mais novo. É a lista que não consegue esquecer: fechar um
  pedido exige um registro novo de resposta, nunca apagar/editar o antigo.
- **Problemas abertos** — `gravidade` vermelho/âmbar sem resposta, excluindo
  `tipo` pendência/frente/rumo (cada um já mora em outro bloco da capa —
  repetir seria fadiga de alarme).
- **Mudanças recentes** — últimos 7 dias, **incluindo datas no futuro** de
  propósito (um typo de data não pode fazer um fato sumir da capa).
- **Estado das frentes** — para cada uma das 5 frentes (`fabrica`, `site`,
  `comunidade`, `curso`, `vender`), o registro `tipo: "frente"` mais
  recente; nada é "mantido", é sempre o último. Frente sem registro renderiza
  "não sei" explícito, nunca uma seção vazia.
- **Meu Mapa** — por frente, na ordem fixa fábrica→site→comunidade→
  curso→vender (a narrativa: fundação → produto → venda por último): estado
  + rumos ainda sem resposta + pendências daquela frente + últimas 4
  entregas/decisões/incidentes/medições. Capítulo sem rumo mostra a frase
  "não sei para onde esta frente vai" — nunca inventa.
- **Frescor** — `vencidos` (passou do `vence_em_dias`) e "livro parado há N
  dias" (idade do registro mais recente do livro inteiro).
- **Não comprovados** — `entrega`/`medicao` sem `evidencia`+`verificado_em`.
- **Capa** — monta até 6 blocos em ordem fixa (caixa → problemas → mudanças
  → frentes → frescor → não-comprovado). Se passar de **6 blocos**, a função
  se recusa a renderizar em vez de estourar a tela — "gerador que quebra,
  segura".

## A lei anti-duplicação — o que já quebrou antes (por que ela é dura)

Nasceu de `docs/paineis/VEREDITO-DAS-CONSULTORIAS.html` (25-26/08/2026): 5
consultorias de IA independentes, rodadas em 2 turnos, convergindo no mesmo
diagnóstico antes de se falarem entre si: **"o problema não é ter vários
painéis, é ter várias verdades."**

Provas concretas já medidas neste repositório:
- Uma linha "precisa de você" pediu 3 passos já executados e sobreviveu a
  **5 merges seguidos** antes de alguém notar.
- Um painel antigo chegou a ter 154 caixas de checklist, todas `true`, zero
  `false` — um "checklist" que só sabe dizer 100%.
- Contagens divergentes no mesmo dia, em painéis diferentes, todos
  "atualizados" (nº de serviços, nº de lições, nº de golpes de red-team).
- Um experimento natural: dentro do MESMO arquivo, meio-migrado, a metade
  com dado próprio ficou correta e a metade cravada em HTML apodreceu no
  lugar — prova de que o problema é arquitetura, não disciplina do agente.

**A formulação importante da lei, para quem for construir algo "irmão" deste
painel — como este próprio mapa para IA:** não é "não crie painéis novos", é
"**não crie fatos novos fora do livro**". Uma vista nova que só *lê*
`painel/registros/` (ou `painel/logica.js`) é permitida; qualquer superfície
que guarde seu próprio veredito sobre o mesmo tipo de fato — mesmo "só um
HTML rapidinho" — não é.

## Como o painel vivo em produção se conecta

`services/admin/apps/core/painel.py` **serve os mesmos bytes** do repositório
— não reimplementa nada. Procura, em ordem, a pasta copiada para dentro da
imagem de produção pelo workflow de deploy, depois o checkout local. Se
nenhum existir, responde **500** explícito — nunca 404 silencioso. Como o
`<script>` da página é embutido, a view calcula o hash SHA-256 real do bloco
a cada resposta e injeta na Content-Security-Policy (nunca `'unsafe-inline'`,
nunca hash cravado à mão). Toda resposta é `Cache-Control: no-store`. A rota
fica atrás da porta de autenticação da célula admin: sem sessão → redireciona
para login; sessão de conta que não é a do dono → 404.

Um endpoint irmão (`/painel/divida.json`) faz uma segunda checagem *ao vivo*
do navegador, reusando o mesmo `ci/divida_do_livro.py` para perguntar à API
pública do GitHub quais PRs mergeados ainda não foram citados por nenhum
registro — e nunca colapsa falha de medição em "0 pendências": devolve erro
explícito e a tela mostra "não consegui medir".

## Contagem de referência (fotografia de 27/08/2026 — o livro cresce a cada sessão, não confie neste número, conte de novo)

56 registros no total. Por `tipo`: `pendencia` 14 · `entrega` 12 · `nota` 7 ·
`rumo` 6 · `frente` 5 · `incidente` 5 · `decisao` 3 · `resposta` 3 ·
`medicao` 1. Por `frente`: `fabrica` 19 · `comunidade` 8 · `vender` 5 ·
`site` 3 · `curso` 2 · sem etiqueta 19.

## Armadilhas e regras sutis específicas de `painel/`

1. **Corrida de numeração entre sessões paralelas** já aconteceu de verdade
   (4 vezes num único dia) — duas sessões leem a pasta no mesmo minuto, veem
   o mesmo `NNN` livre, colidem. A validação hoje reprova um 3º registro no
   mesmo número; o nome completo do arquivo (não o número) é o identificador
   estável para `responde_a`.
2. **CRLF no Windows produz um "modificado" falso nos gerados** —
   é só normalização de fim de linha do checkout, `gerar_manifesto.js
   --conferir` já normaliza os dois lados antes de comparar.
3. **`precisa_do_dono` e `vence_em_dias` têm que ser literais, não texto** —
   `"true"` entre aspas passava despercebido antes de uma auditoria; o
   pedido sumia da caixa em silêncio.
4. **Nunca editar um registro existente**, nem para corrigir um typo —
   sempre um registro novo com `responde_a` apontando para o antigo.
5. **O teto de 6 blocos na capa é proposital e testado reprovando** — a
   ideia de "adicionar mais um bloco" exige primeiro decidir o que sai.
6. **Texto é sempre inserido como texto puro, nunca como HTML** — `<` em
   `titulo`/`detalhe` reprova na validação, exatamente para não virar vetor
   de injeção.
7. **Para qualquer superfície nova "irmã" deste painel** (dashboards,
   relatórios, outro `painel/ia/`-like): se ela relata um veredito sobre algo
   que já é fato no livro, ela precisa **ler** `painel/registros/`/`logica.js`,
   nunca guardar seu próprio veredito.
