# Prompt para consultoria externa — PAINÉIS DE ACOMPANHAMENTO
### (copie tudo o que estiver abaixo da linha e cole na outra IA)

---

Preciso de uma segunda opinião honesta sobre **como acompanhar visualmente um
projeto de software** — especificamente sobre a reforma dos painéis que eu já
planejei. Quero que você **questione minhas premissas**, não que me elogie. Se
achar que a reforma que eu descrevo abaixo está errada, diga com todas as
letras e proponha outra coisa.

## Quem sou eu neste projeto

Sou o dono e **não sou programador**. Todo o código é escrito por agentes de IA
(Claude Code) que eu despacho com instruções escritas — eles constroem, testam,
mergeiam e me reportam. Eu não leio código; eu leio **painéis**. Os painéis são,
literalmente, o meu único instrumento de navegação do projeto: é por eles que eu
sei o que está pronto, o que quebrou e o que espera uma decisão minha.

Isso torna a qualidade dos painéis um problema de primeira ordem para mim, não
cosmético.

## O projeto, em cinco linhas

Uma plataforma de cursos online (escola de criação 3D para Roblox) construída
como **11 serviços isolados** que se comunicam por API e eventos. Está no ar,
com deploy automático, site em 3 idiomas, login próprio e uma ferramenta de
comunidade. É tocado quase inteiramente por agentes de IA, com um aparato de
governança pesado (constituição, invariantes, ritos, testes-guarda, catálogo de
lições aprendidas com 107 entradas).

Ritmo relevante para você calibrar conselhos: num único dia recente saíram **5
frentes de trabalho em paralelo, 7 merges e 4 publicações**, sem reversão. O
tempo aqui não se mede em sprints de duas semanas.

## O problema que quero resolver

Eu criei painéis conforme a necessidade aparecia. Hoje são **6**. E o resultado
foi o oposto do pretendido: nas minhas palavras, *"criei vários painéis para não
me perder, e me perdi do mesmo jeito"*.

Os 6 painéis de hoje:

1. **Painel da Fundação** — o checklist "vivo", atualizado a cada tarefa. ~140
   itens marcáveis, registro histórico de episódios, caixa "precisa de você".
2. **Roadmap do Dono** — o meu mapa: 5 capítulos, ✅/⬜, zero sigla. É o que eu
   mais uso.
3. **Painel de Retomada** — um raio-X técnico completo, datado, com medições
   reais do site feitas da internet. Excelente no dia em que nasceu.
4. **Painel 10X** — o plano de aceleração em cartões de despacho. **Envelheceu
   e passou a mentir**: ninguém escreveu nele por dias e ele continuou com cara
   de atual, até uma leitura manual descobrir.
5. e 6. **Dois painéis de fases antigas** (cartões de prompt de etapas já
   encerradas) — hoje são história, mas continuam soltos na pasta parecendo
   atuais.

**O sintoma mais grave que eu detectei:** a lista *"precisa de você"* — o que
espera uma decisão minha — existe hoje em **três painéis diferentes** ao mesmo
tempo. Basta um dos três não ser atualizado para um pedido se perder, e quem
decide se eu fico sabendo é qual painel eu abri naquele dia.

## RESTRIÇÕES DURAS — leia antes de recomendar qualquer coisa

Estas restrições invalidam a maior parte dos conselhos genéricos sobre painéis.
Se a sua recomendação violar alguma delas, ela é inútil para mim:

1. **Não existe servidor, banco de dados, build ou instalação.** Os painéis são
   arquivos `.html` que eu abro com **duplo clique no Windows**, direto do disco
   (`file://`), no Chrome. Sem npm, sem React, sem compilar nada. Um agente
   escreve HTML/CSS/JavaScript puro num arquivo e acabou.
2. **Não recomende ferramentas prontas** (Grafana, Notion, Linear, Jira,
   Trello, Metabase, Power BI, planilhas). Já foi decidido: a informação tem
   que morar junto do projeto, offline, sem conta, sem mensalidade, sem eu
   aprender ferramenta nova. Se você acha que essa decisão está errada, pode
   argumentar — mas argumente, não a ignore.
3. **Quem atualiza os painéis são os agentes de IA**, editando um arquivo de
   dados. Eu nunca preencho formulário nem arrasto cartão. Qualquer desenho que
   dependa de disciplina humana diária minha vai falhar.
4. **Os painéis ficam fora do controle de versão** (na pasta ignorada) — não há
   histórico automático deles. O que precisa sobreviver ao tempo tem que ser
   deliberadamente registrado em outro lugar.
5. **Eu leio somente português** e não entendo jargão técnico. Sigla sem
   tradução, para mim, é ruído.
6. **NÃO recomende "comece pequeno" ou "faça uma versão mínima para economizar
   tempo".** Esta é uma regra firme e informada do projeto: entre a opção
   completa e a reduzida, escolho a completa, mesmo custando mais tempo — outros
   projetos meus falharam justamente por seguir o conselho de "comece
   simples". Fatiar a construção em etapas seguras é bem-vindo; **cortar escopo
   por pressa, não.** Se algo for genuinamente inviável ou perigoso, diga que é
   inviável — isso é fato, não é o conselho que estou recusando.
7. **Pagamento/cobrança está deliberadamente pausado** por decisão minha e não
   é assunto desta consulta. Não sugira nada sobre vender, cobrar ou métricas
   de receita.

## O que eu JÁ decidi adotar (não repita isto — complemente)

Um estudo interno já selecionou 13 ideias do padrão-ouro da indústria. **Não
gaste sua resposta re-explicando estas** — assuma que estão contratadas:

- Roadmap **Agora / Em seguida / Depois** (sem datas)
- **Hill Chart** do Basecamp (a colina: "subindo = descobrindo, descendo = só executando")
- **Farol por frente** (verde/âmbar/vermelho) com seta de tendência e critério escrito
- **Caixa de entrada única** para tudo que espera decisão minha, com contador
- **Changelog em linguagem de usuário** ("o que mudou nos últimos 7 dias")
- **Kanban** com limite de trabalho simultâneo, para a fila dos agentes
- **As 4 métricas DORA**, traduzidas para português leigo
- **Status page** com sondas reais medidas de fora, carimbadas com data/hora
- **Burn-up chart** (gráfico de subida) para mostrar ritmo, não só percentual
- **Selo de frescor** (staleness indicator): cada seção se autodenuncia quando
  fica velha — o antídoto para o painel que "mentiu"
- **Postmortem sem culpado**, com cada incidente ligado à lição que gerou
- **Registro de decisões (ADR)** visível, uma linha por decisão
- **Relatórios datados imutáveis** ("fotografias" que nunca se editam)

E foram **recusados**, com justificativa: gráfico de Gantt (datas viram mentira
neste ritmo), velocity/story points (métrica de time humano estável, que não é
o meu caso) e OKRs formais (cerimônia demais para um dono solo).

## A reforma que eu planejei — critique-a

**Um painel único** (um arquivo, um endereço) com **três andares por público**:

- **Andar 1 — A capa (minha vista, abre por padrão):** placar de uma frase ·
  caixa de entrada única com contador · capítulos em Agora/Em seguida/Depois com
  a colina · "o que mudou" · gráfico de subida. Zero sigla.
- **Andar 2 — A sala de máquinas (vista dos agentes):** faróis por frente ·
  quadro kanban da fila · sondas reais com carimbo de hora · as 4 métricas.
- **Andar 3 — A memória (a história):** registro completo de episódios ·
  incidentes ligados às lições · decisões · prateleira de fotografias datadas.

Sustentado por: **uma fonte de dados única** (um arquivo de dados que alimenta
os três andares), **aposentadoria dos 6 painéis antigos** com faixa e link (nada
é apagado — atalhos antigos continuam funcionando e levam ao hub) e uma **lei
anti-proliferação** escrita nas regras do projeto: *"painel novo é proibido por
padrão; quem precisar de superfície nova cria uma seção no hub"*.

## As perguntas que quero que você responda

Responda na ordem, com franqueza:

1. **A premissa está certa?** Consolidar tudo num painel único é mesmo a
   resposta — ou eu estaria trocando "seis painéis dispersos" por "um painel
   gigante que ninguém termina de ler"? Existe um terceiro caminho que eu não
   enxerguei (por exemplo: manter painéis separados e criar apenas um índice
   com regras claras de dono)? Defenda a sua posição.

2. **O corte por público é o melhor eixo de organização?** Dividi em
   dono/máquinas/memória. Alternativas possíveis seriam por horizonte de tempo
   (agora/histórico/futuro), por pergunta respondida ("o que está quebrado?",
   "o que falta?"), ou por frequência de consulta. Qual eixo você usaria, e por
   quê?

3. **Qual é o modo de falha desta reforma?** Descreva concretamente como este
   hub único vai apodrecer daqui a três meses, e que mecanismo — não que boa
   intenção — impediria isso. Já sei que promessa de disciplina não funciona
   aqui: foi exatamente assim que o painel 10X morreu.

4. **Como manter honesto um painel escrito pelos próprios agentes que ele
   avalia?** Este é o meu medo mais fundo. Quem preenche o painel é a mesma
   inteligência cujo trabalho o painel reporta — e um agente sob pressão tende
   a relatar sucesso. Já exijo evidência crua (saída de comando colada, nunca
   descrição) e auditoria por uma sessão diferente da que executou. **Isso é
   suficiente? Que mecanismos de verificação independente você acrescentaria?**

5. **O que falta nas 13 ideias?** Considerando tudo acima — um dono não-técnico,
   executores de IA, ritmo de dias e não de sprints — que padrão de
   acompanhamento você usaria que não está na minha lista? Prefiro uma
   recomendação forte e justificada a cinco fracas.

6. **Quanto mostrar de uma vez?** Sou leigo e me perco com excesso de
   informação — mas também não quero um painel que esconda problema. Como você
   dosaria a profundidade na capa sem cair em nenhum dos dois extremos?

7. **O que você vê que eu não perguntei?** Pontos cegos, riscos, ou coisas que
   costumam derrubar sistemas de acompanhamento como este.

## Como quero a resposta

- **Em português**, direta e priorizada.
- **Discorde explicitamente** onde discordar — eu quero contraponto, não
  validação. Uma crítica bem fundamentada vale mais para mim que uma
  confirmação.
- Toda recomendação precisa ser **executável por um agente de IA escrevendo um
  arquivo HTML/CSS/JS** — se depender de servidor, ferramenta paga ou
  disciplina humana diária, diga isso na hora, para eu já descartar.
- **Nada de plano por fases com prazos em semanas.** Diga o que fazer e em que
  ordem; o tempo aqui é medido em dias.
- Se citar um método, diga **quem o usa na prática** e o que ele custa quando
  aplicado errado.
