# DA IDEIA A OBRA — o caminho inteiro de uma sugestão, em sete estações

> **Para a sessão que acabou de receber "o aluno pediu X, faça acontecer".**
> Nascido em 01/09/2026, depois que a sugestão do Ricardo ("guias de portfólio
> com check-list") custou quarenta comandos de leitura antes da primeira linha
> de plano — e nenhuma dessas leituras era sobre o portfólio: eram sobre o
> projeto, e vão se repetir idênticas na próxima sugestão.

## O que este documento é, e o que ele NÃO é

É o **mapa das estações**: o que existe entre a frase de um aluno e a obra no
ar, em que ordem, e qual documento manda em cada trecho.

Não é a repetição de nenhum deles. Cada estação aponta para a lei que já existe
e para de falar — copiar aqui o formato do ChangeSpec, o molde do despacho ou as
sete regras do lote criaria uma segunda verdade que envelheceria em silêncio, e
essa é a doença que a lei anti-duplicação do `CLAUDE.md` existe para curar.

| Estação | O que acontece | Quem manda |
|---|---|---|
| 0 | A ideia chega, o aluno escreve | a Caixa |
| 1 | **Reconhecimento**: o que a casa já tem | `ci/reconhecer.py` |
| 2 | **Estudo de viabilidade**: o que falta, o que custa | [`MODELO-ESTUDO-DE-VIABILIDADE.md`](MODELO-ESTUDO-DE-VIABILIDADE.md) |
| 3 | **As bifurcações voltam ao mantenedor**, numa pergunta só | `CLAUDE.md` |
| 4 | **O corredor da Caixa**: avaliar, planejar, assinar | [`FORMATO-CHANGESPEC.md`](FORMATO-CHANGESPEC.md) |
| 5 | **A escada vira fila**: uma TAR por degrau | `RITOS.md` §5 |
| 6 | **Os lotes rodam**: paralelo por célula, pouso serial | `RUNBOOK-LOTES.md` |
| 7 | **O fechamento**: o aluno fica sabendo | `painel/LEIA-ME.md` |

---

## Estação 1 — Reconhecimento (antes de planejar, meça)

```bash
python ci/reconhecer.py portfolio portifolio estudio
```

Devolve, lendo do `origin/main` e nunca do disco: onde o tema já aparece por
frente (células, contratos, infra, decisões, constituições), quantas armadilhas
e tarefas casam, que endereços do site já existem, e **o que a casa sabe
fazer** — guardar arquivo, gerar PDF, mandar e-mail, servir vídeo — com o
caminho do molde quando a resposta é sim.

**Por que isto é comando e não checklist:** a resposta que mais muda um plano é
uma AUSÊNCIA, e ausência não se documenta. Em 01/09/2026 a descoberta que
reescreveu o plano do portfólio foi "nenhuma tela desta plataforma recebe
arquivo" — um fato sobre a inexistência de todos os arquivos, que nenhum
documento poderia guardar sem começar a mentir no dia seguinte. O script guarda
a PERGUNTA e mede na hora.

Ele erra fail-closed: `git` mudo, ref inexistente ou mapa do site ausente viram
"NÃO MEDI" com saída 2. Dossiê vazio por instrumento quebrado seria o
falso-verde mais convincente que existe, porque parece uma resposta.

## Estação 2 — O estudo de viabilidade

Um documento por sugestão grande, no molde de
[`MODELO-ESTUDO-DE-VIABILIDADE.md`](MODELO-ESTUDO-DE-VIABILIDADE.md), guardado
em `docs/decisoes/PLANO-<assunto>.md`. Ele responde seis perguntas, nesta
ordem, e **nenhuma delas é "como implementar"**:

1. o que o aluno pediu, traduzido em partes;
2. o que já existe (estação 1, colado);
3. o que não existe, e o que essa ausência custa;
4. **onde a coisa mora** — célula nova ou célula existente, com a recomendação
   e o preço de cada lado;
5. a escada de entregas, degrau por degrau, com o que muda para o aluno;
6. o que fica na mão do mantenedor.

Escopo reduzido não é resposta aceitável aqui (`DECISAO-filosofia-de-escopo.md`):
o estudo entrega o completo, fatiado. Fatiar é a forma responsável de construir
grande; cortar é outra coisa.

O exemplo real e completo: [`docs/decisoes/PLANO-PORTFOLIO-DO-ALUNO.md`](../decisoes/PLANO-PORTFOLIO-DO-ALUNO.md).

## Estação 3 — O que só o mantenedor decide

O estudo termina com bifurcações, e elas voltam para ele **numa pergunta
estruturada só, na hora** (`CLAUDE.md`; em lote, quem pergunta é a maestro).
As três que aparecem quase sempre:

- **a fronteira**: célula nova ou dentro de uma existente. É decisão de
  arquitetura, e o `RUNBOOK-LOTES.md` §7 proíbe que um lote a tome sozinho;
- **o que custa dinheiro ou credencial**: armazenamento pago, provedor de
  e-mail, serviço externo;
- **o que muda o produto**: o que a escola promete ao aluno, e o que ela não
  vai prometer.

Enquanto elas não voltam, o resto anda: escreva o estudo inteiro sob a hipótese
declarada, nunca fique parado esperando.

## Estação 4 — O corredor da Caixa

A ideia só entra em construção com o corredor formado, e a tranca é do banco,
não da tela: `avaliar` → `planejado` → **ChangeSpec assinado** →
`em_desenvolvimento`. Formato e regras de validade em
[`FORMATO-CHANGESPEC.md`](FORMATO-CHANGESPEC.md); os corredores já assinados em
`docs/changespecs/`; as telas em `/admin/caixa/`.

Duas coisas que a sessão precisa saber e costumam surpreender:

- **quem assina é só quem está em `SUGESTOES_APROVADORES`** (variável da VPS), e
  lista vazia é fail-closed: ninguém aprova, nada entra
  (`DECISAO-EVO-40-quem-aprova-e-quem-e-avisado.md`);
- **o ChangeSpec cita o `suggestion_id` real**, e o número se lê na URL da
  ideia. Um corredor sem origem é um plano que ninguém pediu.

## Estação 5 — A escada vira fila

Cada degrau da escada do estudo vira **uma tarefa no balcão**, encadeada:

```bash
python ci/fila.py criar --titulo "..." --toca <celulas> --move <cartao|manutencao> \
  --evidencia-exigida "..." --despacho "..." --depende-de TAR-NNN
```

Regras que já são lei e não se reinventam aqui: tarefa se pega no balcão e
nunca de memória (`RITOS.md` §5), a bancada vem antes do balcão, e o brief de
cada agente sai do [`MODELO-DESPACHO.md`](MODELO-DESPACHO.md) — com as
armadilhas daquela tarefa injetadas, não o catálogo inteiro.

## Estação 6 — Os lotes

Regência inteira no `RUNBOOK-LOTES.md`. O que a experiência do portfólio
acrescentou, e que vale para toda sugestão que nasce numa célula nova:

> **Uma obra concentrada numa célula só tem lote estreito, e isso não se
> conserta com mais robôs.** Duas tarefas da mesma célula viram fila interna
> (§1), então a largura do lote vem das células VIZINHAS: o texto que o
> mantenedor edita, a mensagem que convida o aluno, o menu que aponta, a célula
> que escuta o evento. Monte os lotes misturando a fila principal com esses
> vizinhos, e diga o número honesto de frentes ao mantenedor — prometer seis
> bancadas onde a arquitetura permite duas é promessa que o §1 vai quebrar.

## Estação 7 — O fechamento

A obra no ar não fecha a ideia: fecha quem escreveu. Mova a sugestão para
`entregue` (o aluno recebe a carta no sininho), registre no livro com evidência
conferida, e **acrescente a armadilha do que doeu** — arquivo novo em
`armadilhas/`, número pedido ao almoxarife.

---

## As três lições que este caminho já cobrou

1. **Meça antes de planejar.** Duas horas de plano sobre uma capacidade
   inexistente valem zero, e o erro só aparece no meio da construção.
2. **A fronteira é do dono, não do agente.** "Célula nova ou dentro da que
   existe" muda custo, passo manual e o dia em que a coisa pode ser desligada.
   Um agente que decide isso sozinho está legislando.
3. **O aluno é a última estação, não a primeira.** Ele escreveu porque
   acreditou que alguém leria. Uma obra entregue com a ideia esquecida em
   "em análise" ensina o contrário para todo mundo que estava olhando.
