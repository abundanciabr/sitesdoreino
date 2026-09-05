---
titulo: As ferramentas do projeto Meshcraft
publico: false
ordem: 21
---

# As ferramentas do projeto Meshcraft

Tudo o que será construído: o que cada ferramenta é, para quem, o que resolve, como funciona, com exemplo, onde vive e de onde veio.

*Meshcraft · sitesdoreino · 5 de setembro de 2026*

---

*"Ferramenta" aqui é qualquer coisa que alguém usa para fazer, medir, decidir ou conferir, do cartão impresso que o aluno leva à bancada ao portão de CI que reprova um arquivo mal plantado. São 78, em sete famílias. Cada uma com a mesma ficha: o que é · para quem · o problema que resolve · como funciona · um exemplo prático · onde vive no repositório ou na plataforma · a encomenda ou o lote de origem.*

---

## Índice

- **A. Instrumentos do ofício** (itens 1 a 19): o aluno, o Mentor, os pares, e qualquer estúdio que adote o Padrão
- **B. Ferramentas da plataforma do aluno** (itens 20 a 38): o aluno, o Mentor, os responsáveis
- **C. Ferramentas de conteúdo e produção** (itens 39 a 54): a equipe que produz livro, vídeo e arquivos
- **D. Ferramentas de pesquisa** (o Atlas; itens 55 a 61): o mantenedor do Atlas, os codificadores
- **E. Ferramentas de gestão do projeto** (itens 62 a 69): o mantenedor, a equipe de execução
- **F. Ferramentas de lançamento** (itens 70 a 75): o responsável pelo lançamento
- **G. Os agentes** (sessões de IA; itens 76 a 78): a operação inteira

---

# Família A: os instrumentos do ofício

*Os que o livro cria e que sobrevivem ao curso. São a razão do posicionamento: "instrumentos que continuam funcionando depois".*

### 1. Teste STUDS

**O que é.** A régua da malha: cinco letras (Silhueta, Topologia, UV, Densidade, eScala), cada uma de 0 a 5, total de 0 a 25, e uma frase de justificativa por nota.

**Para.** O aluno desde a E01; o Mentor; qualquer modelador.

**Resolve.** "Acho que ficou bom" vira "aqui está o porquê". É o que faz duas pessoas chegarem a notas parecidas.

**Como funciona.** Aplica-se no motor, nunca no viewport. Mínimos: 18 em exercício, 20 em contrato, nenhuma letra abaixo de 3. A partir da E22, a **régua orgânica** troca as perguntas de T e D (os loops seguem a musculatura? a densidade está onde dobra?) sem trocar as letras.

**Exemplo.** Três espadas na E01. A espada C parece a melhor a olho nu (lisa, "detalhada"). O STUDS dá D=1 (4.800 triângulos para uma forma de 300) e eScala=2 (escala não aplicada). A B, feia, tem T=1 (n-gons, normais invertidas). A A, sem graça, faz 22. O aluno descobre que o olho mente e a régua não.

**Vive em.** Cartão 1 (dado em `conteudo/meshcraft/instrumentos/`); formulário na célula `avaliacao` com a validação "nota sem frase não envia"; PDF público em `/padrao/instrumentos`.

**Origem.** E01; régua orgânica E22 e E23; §8 do Padrão.

### 2. Rubrica de Encomenda

**O que é.** A régua do trabalho para um cliente: STUDS (0 a 25) mais Pacote, Comunicação e Prazo (0 a 5 cada), total de 0 a 40.

**Para.** Toda encomenda real; a Banca de Nível 1.

**Resolve.** Cliente não devolve por dois triângulos a mais; devolve, e não volta, por silêncio, atraso sem aviso ou pacote que não sabe abrir. A Rubrica mede isso.

**Como funciona.** Mínimo 32, STUDS maior ou igual a 20, nenhuma letra menor que 3. Em projetos de volume ganha a linha "dentro da política de otimização": "não" reprova.

**Exemplo.** O escudo do Estúdio Norte (E09): STUDS 23, Pacote 5, Comunicação 4 (as perguntas certas, blocagem em 48h), Prazo 3 (a blocagem atrasou 12h sem aviso). 35 de 40, aprovado, com a mudança "avise no dia, não na entrega".

**Vive em.** Cartão 2; `avaliacao`.

**Origem.** E09; §25.

### 3. Rubrica de Produto

**O que é.** A régua do trabalho para o mercado: STUDS mais Vestir & Mover, Apresentação e Conformidade, total de 0 a 40.

**Para.** Todo item que vai à loja; personagens (aplicada ao corpo e à cabeça separadamente).

**Resolve.** Um item pode ter STUDS 24 e não vender: thumbnail escura, nome "Jacket v3 final", atravessa o corpo ao correr.

**Como funciona.** Mínimo 32, novas categorias maior ou igual a 3; **Vestir & Mover igual a 0 reprova o item inteiro**, independente do total.

**Exemplo.** A jaqueta da Nina: STUDS 22, V&M 5 (27 de 27 em três corpos), Apresentação 2 (thumbnail de frente, fundo preto, ilegível em miniatura), Conformidade 5. Total 34, mas Apresentação abaixo de 3: volta para o teste da miniatura antes de publicar.

**Vive em.** Cartão 3; `avaliacao`.

**Origem.** E17; §21.

### 4. Pronto para sair, e Ficha de Sintomas

**O que é.** A checagem de nove itens antes de exportar (nomes, transforms, origem, escala, modificadores, normais, limpeza, triangulação, material) e, no verso, a tabela que liga sintoma no motor à causa provável.

**Para.** O aluno, sozinho, antes de todo envio da E08 em diante.

**Resolve.** O item que chega deitado, gigante, invisível ou cinza: 90% dos erros de exportação em nove checkboxes.

**Como funciona.** Auto-checagem anexada ao envio; o avaliador vê. A Ficha de Sintomas é uso de tabela, não memória: "invisível ou só por dentro, normais para dentro, item 6".

**Exemplo.** O Kit do Aventureiro chega deitado no Studio. O aluno abre a Ficha: "deitado ou girado, eixo Up errado ou rotação não aplicada, exportador −Z/Y, item 2". Dois minutos.

**Vive em.** Cartão 4; anexo de envio em `avaliacao`.

**Origem.** E08; §7.

### 5. Validação no motor (personagem)

**O que é.** Os seis testes que reproduzem o que a moderação faz com um corpo ou cabeça: importar como personagem, animações padrão, roupas de terceiros (mínimo 3), acessórios de terceiros, expressões pelo sistema da plataforma, Prova dos 3 Movimentos vestido.

**Para.** Quem vai publicar personagem (E25).

**Resolve.** A reprovação que custa uma semana: "funciona no meu Blender" e reprova por estrutura ou por cage que só veste a própria roupa.

**Como funciona.** Cada teste exige evidência e, nos de terceiros, os itens nomeados (nome, criador). Precisa de 6 de 6 para abrir.

**Exemplo.** A Bia veste a jaqueta da Nina, e flutua dentro de três roupas de outros criadores. A cage do corpo estava no template. Descoberto antes de submeter.

**Vive em.** Cartão 5; formulário em `avaliacao`.

**Origem.** E25; §15.

### 6. Prova dos 3 Movimentos

**O que é.** O laudo de tudo que acompanha o corpo: idle, corrida, emote, cruzado com atravessar, esticar, descolar. Nove células. Em camadas: vezes três corpos (27) mais empilhamento.

**Para.** Capas, roupas, acessórios presos ao corpo, corpos.

**Resolve.** "A malha parada mente." Pesos automáticos parecem certos até o primeiro passo.

**Como funciona.** Roda-se com o play aberto, no motor; cada célula reprovada vira a região exata a corrigir. Passa só com 9 de 9 (ou 27 de 27).

**Exemplo.** A capa do Téo (E13): idle 3 de 3; corrida com a barra atravessando a coxa no quadro 14 (peso da barra dominado pelo torso) e um vinco duro na cintura (degrau); emote com tremor na ponta (cabo de guerra entre braço esquerdo e perna direita). Total 6 de 9. Três defeitos com nome, três correções conhecidas.

**Vive em.** Cartão 6; grade 3×3 em `avaliacao` com anotação obrigatória por célula reprovada; anexo de vídeo.

**Origem.** E13 (3×3), E14 (3×3×3); §9, §10.

### 7. Prova das 5 Expressões

**O que é.** O laudo do rosto rigado: neutro, sorriso, raiva, surpresa, fala, cruzado com rasgar, atravessar, morrer. Quinze células.

**Para.** Cabeças rigadas (E24); a Banca de Nível 3 ao vivo.

**Resolve.** O rosto que "finge": a boca sobe e os olhos não riem. A terceira coluna (morrer) é defeito de comunicação, não técnico.

**Como funciona.** "Morrer" só se testa com outra pessoa que não sabe os nomes: mostra-se a pose, pergunta-se o que vê. Se ela diz "sorriso" quando é sorriso, passou; se hesita, morreu. O formulário exige nome, data e as cinco respostas.

**Exemplo.** A Bia rigada: a surpresa "morreu", a pessoa disse "raiva… não, espera". As sobrancelhas subiam, a mandíbula não descia. Um controle a mais e a expressão comunica.

**Vive em.** Cartão 7; `avaliacao`.

**Origem.** E24; §14.

### 8. Selo UGC e Selo UGC (Personagem)

**O que é.** O checklist de cinco blocos antes de qualquer submissão à loja: técnico, comportamento, conformidade, apresentação, negócio. O de Personagem tem uma camada a mais por bloco.

**Para.** Todo item publicado.

**Resolve.** Reprovação por metadata, por originalidade, por ponto de equilíbrio nunca calculado: as causas que o aluno não sabia que existiam.

**Como funciona.** O Bloco 3 exige a data da leitura da fonte oficial em até 7 dias; a plataforma invalida a leitura se o Apêndice J mudou depois. Parceria exige as três perguntas por escrito.

**Exemplo.** O cabelo da Bia reprova no próprio Selo, Bloco 3, na primeira passada: o nome tinha uma palavra que a regra de metadata não aceita. Corrigido antes de submeter, o Selo existe para reprovar em casa.

**Vive em.** Cartões 8 e 9; `avaliacao`, com a data de leitura ligada ao apêndice vivo J.

**Origem.** E17, E25; §21, §15.

### 9. Ficha de Série

**O que é.** Os quatro números de uma linha de produção: cadência, tempo médio por item, retrabalho, conformidade, por lote de cinco.

**Para.** Quem produz em série (E27); quem delega, medindo o colaborador (E28); quem coordena, por pessoa e do conjunto (E29); e a própria equipe do projeto, e os agentes.

**Resolve.** Um item se mede com STUDS; uma linha não é a soma dos itens, é um sistema com velocidade, ritmo e taxa de falha.

**Como funciona.** Saudável: cadência subindo, tempo caindo, retrabalho menor que 1 em 5, conformidade maior que 4 em 5. O tempo por etapa opcional aponta o gargalo. Subida de degrau de um colaborador (ou de um agente) só com um lote saudável.

**Exemplo.** Os 25 itens do Téo: lote 1, tempo médio 4h10; lote 3, 2h05, a UV era o gargalo e o template passou a trazê-la pronta. A comparação final: 275h item a item contra 58h em série.

**Vive em.** Cartão 10; `avaliacao` (colaboradores) e `metricas` (a série da produção e dos agentes).

**Origem.** E27; §19, §30, §32.

### 10. Ficha de Delegação

**O que é.** Os oito campos que carregam o que a sua mão decide sem pensar: item, referências, degrau, limites, rubrica, prazo com blocagem, valor em duas partes, canal de dúvida. Teste: "onde quem recebe teria uma pergunta?"

**Para.** Quem entrega trabalho a outra pessoa, e é a Ficha de cada agente.

**Resolve.** "Faz uma boina, estilo dela, você sabe", e o n-gon que volta. O erro de quem recebe é a lacuna de quem enviou.

**Como funciona.** Não envia sem os oito campos e sem o teste; o degrau só sobe pela Ficha de Série do colaborador.

**Exemplo.** A primeira Ficha ao Kai não dizia "zero n-gons" porque era óbvio demais. O n-gon veio. A segunda Ficha nasceu com a linha, e o erro deixou de existir para todos os colaboradores futuros.

**Vive em.** Cartão 11; `avaliacao` ou `encomendas` (decisão pendente); `conteudo/meshcraft/fichas_agentes/` para os agentes.

**Origem.** E28; §30.

### 11. Revisão de Estúdio

**O que é.** O protocolo de avaliar trabalho alheio: rubrica antes de qualquer opinião; três forças e uma mudança por escrito; decisão em 24 horas (aprovado, com ajuste, ou refazer); a lacuna corrige a Ficha.

**Para.** Quem delega, quem coordena, os pares, e quem revisa saída de agente.

**Resolve.** A raiva do n-gon contaminando a avaliação; o trabalho alheio parado na fila, que é como se perde um colaborador.

**Como funciona.** Os campos de texto ficam desabilitados até a rubrica estar completa; o relógio de 24h é visível; "refazer" devolve com a régua ("roda o Select Non-Manifold"), não com a resposta.

**Exemplo.** A entrega do Kai: Rubrica 31 (T em 2). Forças: silhueta, proporção, prazo. Mudança: "rode o protocolo de limpeza, é o da E03". Decisão em 6 horas. O Kai encontra o n-gon sozinho e não o repete.

**Vive em.** Cartão 12; é o formulário-base de `avaliacao`.

**Origem.** E28 (sobre E03); §31.

### 12. Laudo de Banca

**O que é.** O documento que abre ou adia a porta de alguém: rubrica individual antes da comparação, três forças, uma mudança nomeada pela encomenda, decisão com data, e a pergunta obrigatória: "ele sabe o que fazer amanhã de manhã?"

**Para.** As três Bancas; o candidato a Nível 3 na E32.

**Resolve.** "Não está bom, tente de novo": o laudo que faz alguém sair e não voltar.

**Como funciona.** A tela de comparação só abre depois de todas as rubricas individuais; divergência maior ou igual a 10 exige conciliação; nunca a palavra "reprovado" sem data; a nota de membro nunca vai ao aluno.

**Exemplo.** O aluno B da E32, segunda tentativa: melhorou muito a malha; o Pacote continua sem laudo, a mesma mudança da primeira Banca. O laudo anterior não tinha dito o que fazer. O novo diz: "adicione o laudo STUDS ao Pacote, nova Banca em duas semanas, quinta." Ele volta.

**Vive em.** Cartão 13; fluxo de Banca em `avaliacao`.

**Origem.** E32; §33.

### 13. Padrão Meshcraft v3

**O que é.** A especificação aberta de entrega: 33 seções em 5 famílias (Arquivo, Diagnóstico e Movimento, Produção, Mercado, Pessoas), cada uma com regra, origem, instrumento que verifica e adaptação permitida; checklist de conformidade; protocolo de versão.

**Para.** O aluno (a régua de tudo); estúdios que o adotam como constituição; a escola (peça de autoridade).

**Resolve.** Cinco modeladores entregando de cinco jeitos; "funciona no meu Blender" como critério.

**Como funciona.** Publicado aberto com âncoras estáveis por seção, changelog, formulário de propostas (recusas publicadas com motivo) e índice de versões locais de estúdios.

**Exemplo.** O Estúdio Norte adota §Organização e §Pacote na semana 1, STUDS e §Malha na semana 2, e escreve uma regra própria (nomes por jogo) na semana 3. A conformidade vai de 0 de 5 a 4 de 5 em um mês.

**Vive em.** `conteudo/meshcraft/padrao/` (dados) e site estático em `/padrao` no multissítio.

**Origem.** E00 até E32; F5·L1; F7·L1.

### 14. As calculadoras

**O que é.** Cinco contas com campos vivos: **ponto de equilíbrio** (quantas unidades pagam a publicação), **valor por hora real** (o que sobra por hora, tudo incluído), **capacidade** (A menos B, dividido por D, menos 1; recorrência até metade), **custo de operação** (colaboradores mais coordenação, reserva e margem), **projeção de caixa de 60 dias**.

**Para.** O aluno nas E17, E21, E27, E30, e o próprio projeto (a conta aberta do Meshcraft).

**Resolve.** "Vou tentar" com uma conta que não fecha; o preço de modelador vezes gente; a modelagem que é minoria das horas.

**Como funciona.** Puxam do dossiê o que já existe (datas, pagamentos); as taxas vêm do apêndice vivo J; a saída é o número e a barra ("modelagem contra tudo o resto").

**Exemplo.** Valor por hora real na E21: 11h por item, sendo 4h de modelagem, 7h de conversa, revisão, Pacote e apresentação. A barra mostra a modelagem como minoria. O preço muda.

**Vive em.** Modelos G3, L4, P4, P6 (dados) e formulários em `alunos` ou `avaliacao`; a conta do projeto em `docs/meshcraft/`.

**Origem.** E10, E17, E21, E27, E30.

### 15. Os modelos de texto

**O que é.** Onze modelos preenchíveis: leitura de briefing em três colunas mais as 5 perguntas; README de oito linhas; resposta de orçamento em três linhas; oito mensagens de campo; pitch de cinco linhas com três variações; contrato de uma página; folha de família; contrato de colaboração; proposta com conta aberta; contrato de estúdio de três páginas; posicionamento com teste.

**Para.** O aluno em cada momento de relação com cliente, colaborador ou mercado.

**Resolve.** A mensagem-currículo de quinze linhas; o combinado que não existe; o escopo que "vai se definindo".

**Como funciona.** Formulários que exportam PDF; alguns com validação (o pitch exige segunda linha com 60 caracteres ou mais; o contrato exige valor em duas partes; a proposta exige motivo em cada linha).

**Exemplo.** A mudança de escopo na E20: "Entendi o pedido de incluir uma variante. Está fora do combinado, e é boa ideia. Prazo vai de dia 7 para dia 10; valor de X para Y. Alternativa: entrego o combinado no prazo e faço a variante como segunda etapa. Qual prefere?"

**Vive em.** Modelos G1 a Q1 (dados) e formulários; PDF público dos que não são do curso.

**Origem.** E08 até E31; F5·L3.

### 16. Os testes de bancada

**O que é.** Sete testes curtos que o livro nomeia e o aluno repete a vida inteira: **originalidade** ("mudando só a cor, alguém confundiria?"), **miniatura** (reduzido a 128 px, reconhecível em 2 s?), **silhueta a 30 studs**, **prova da silhueta** (a intrusa entre as irmãs), **troca** (qualquer peça substitui qualquer outra?), **dobra preliminar** (as quatro articulações), **loop** (o último quadro é o primeiro?).

**Para.** O aluno, antes de qualquer instrumento maior.

**Resolve.** Decidir por gosto o que se decide por teste.

**Como funciona.** Cada um cabe em uma frase e leva menos de um minuto; aparecem como campos nos Selos, nas Rubricas e nos checkpoints.

**Exemplo.** Teste da miniatura na E18: a thumbnail "bonita" perde para a "feia" na grade de listagem, a bonita virou borrão a 128 px.

**Vive em.** Dentro dos cartões e dos capítulos; campos nos formulários.

**Origem.** E04, E05, E12, E15, E18, E22, EB.

### 17. A política de otimização

**O que é.** O documento de uma página com seis seções (dispositivo-alvo e orçamento, tabela por categoria, atlas da temporada, regime de material, protocolo de verificação, exceção com compensação) que qualquer modelador do projeto segue sem procurar quem a escreveu.

**Para.** Projetos de cinco itens ou mais para a mesma cena (E26).

**Resolve.** Trinta itens individualmente leves derrubando o jogo; otimizar polígono quando o gargalo é troca de material.

**Como funciona.** Nasce de profiling (linha de base, depois isolar por categoria, depois isolar por conta). Testa-se entregando a alguém que não conhece o projeto: se exige explicação oral, não está pronta.

**Exemplo.** O mapa do Téo: 180 props com 40 materiais; o gargalo era troca de material, não triângulo. Quatro atlas em vez de quarenta texturas; o medidor sai do vermelho.

**Vive em.** Modelo P1; anexa-se à Ficha de Delegação e à Rubrica ("dentro da política").

**Origem.** E26; §18.

### 18. Os 45 drills

**O que é.** Exercícios cronometrados de bancada, quinze por Parte, que transformam técnica em reflexo: da limpeza de malha em 5 minutos (Parte I) ao esqueleto canônico em 20 (D37) e à Ficha de Delegação em 10 (D44).

**Para.** O aluno, diariamente; as "provas de escalas" nas E10, E21, E32.

**Resolve.** Saber fazer devagar não é saber fazer.

**Como funciona.** Registro diário com XP; os da Parte III incluem exercícios mensais que duram a carreira (a pergunta da distância, a projeção de caixa, a pergunta do posicionamento).

**Exemplo.** D43: cinco UVs em sequência, 4:10, 3:20, 2:45, 2:20, 2:05. O aluno vê, na própria mão, por que produção por etapa acelera.

**Vive em.** Dados de lição; registro em `alunos`/`gamificacao`.

**Origem.** E01 até E32.

### 19. Os pôsteres e os cartões impressos

**O que é.** Seis pôsteres (os 7 Degraus, o STUDS, o Pipeline em 9 passos, as duas Provas, a Ficha de Série) e treze cartões A5 destacáveis, com QR para a versão viva.

**Para.** A bancada.

**Resolve.** O instrumento que não está à mão não é usado.

**Como funciona.** Impressos no fim do livro em caderno próprio com picote; PDFs abertos sem cadastro.

**Vive em.** `/padrao/instrumentos` (público); caderno do livro impresso.

**Origem.** F5·L2, F5·L7.

---

# Família B: as ferramentas da plataforma do aluno

*O que a Fase 6 especificou, remapeado para as células do sitesdoreino.*

### 20. A fila de avaliação (a célula `avaliacao`)

**O que é.** A única célula nova do projeto: recebe envios, aplica o instrumento cabível, produz laudos com estados e prazo de 24h, atribui pares, conduz Bancas.

**Para.** Aluno, Mentor, pares.

**Resolve.** Trabalho parado sem que ninguém saiba por quê; o laudo que não diz o que fazer.

**Como funciona.** Estados: recebido, em revisão, aberto, aberto com ajuste, ou devolvido (nunca "reprovado"). `POST /laudos` devolve 422 se faltar rubrica completa, nota sem frase, três forças, a mudança com encomenda, decisão, data (se devolvido) ou o checkbox de "amanhã de manhã". Eventos: `laudo.emitido`, `checkpoint.aberto`, `checkpoint.devolvido`, `revisao.prazo_estourado`, `banca.decidida`. Nunca chama outra célula; emite e as outras consomem.

**Exemplo.** Um envio chega às 14h de terça. A fila mostra "prazo até 14h de quarta", verde. Às 2h de quarta fica amarelo. Às 14h05, se ninguém decidiu, fica vermelho: registra o estouro, não alonga o prazo, e o número entra na Ficha de Série do Mentor.

**Vive em.** `services/avaliacao/` (ChangeSpec obrigatório antes).

**Origem.** F6·L1, L6; playbook P42 a P45.

### 21. Os formulários dos instrumentos com validação

**O que é.** Os 13 cartões como formulários cujas regras são da API: nota sem frase bloqueia; Vestir & Mover igual a 0 reprova; "morrer" exige nome, data e cinco respostas de outra pessoa; a Ficha de Delegação exige o teste "onde ele perguntaria?".

**Resolve.** A régua que se pula quando é só instrução.

**Exemplo.** Um par tenta enviar "ficou bonito" como força: a lista bloqueada recusa; ele reescreve "a silhueta lê a 30 studs".

**Vive em.** `avaliacao`, versionados (avaliações em andamento guardam a versão do instrumento).

**Origem.** F6·L1, seção 6.

### 22. O assistente de laudo

**O que é.** Um agente atrás de um endpoint de `avaliacao` que pré-preenche a rubrica com justificativas observáveis, sugere três forças e uma mudança com encomenda, e deixa decisão, data e o checkbox como `[DECISÃO HUMANA]`. Nunca persiste, nunca envia.

**Para.** O Mentor e os pares.

**Resolve.** O gargalo real: 15 a 30 minutos por laudo viram 3 a 5, com a régua intacta.

**Exemplo.** Reenvio: o assistente compara com o laudo anterior e marca `[ALERTA: mudança repetida, o laudo anterior pode não ter dito o que fazer]`. O Mentor lê isso antes de escrever de novo a mesma frase.

**Vive em.** `avaliacao` (endpoint); Ficha em `conteudo/meshcraft/fichas_agentes/`.

**Origem.** Equipe de agentes; alavanca 6.

### 23. O motor de atribuição de pares

**O que é.** Quem avalia quem: elegibilidade por nível, disponibilidade, carga; rotação (nunca o mesmo par duas vezes seguidas); **impedimentos automáticos e bilaterais** (delegação, colaboração, cliente, parentesco, mesma conta de responsável) lidos por contrato de `encomendas` e `identidade`.

**Resolve.** Favor, vício e conflito de interesse na validação por pares.

**Exemplo.** O Kai delegou uma peça a um aluno; o sistema bloqueia qualquer avaliação entre os dois por 180 dias após o fim do vínculo, nos dois sentidos.

**Vive em.** `avaliacao`, consumindo `encomendas` e `identidade`.

**Origem.** F6·L6.

### 24. A revisão de revisões e a calibração trimestral

**O que é.** Duas rotinas: toda segunda, o Mentor recebe 3 ou mais avaliações dadas por pares (as cinco primeiras de um par novo, 100%) e aplica o Cartão 12 à revisão (rubrica antes da opinião? forças específicas? 24h? três correções seguidas leva a co-assinatura). E, por trimestre, o mesmo dossiê anônimo a todos os pares; dispersão maior ou igual a 10 exige sessão obrigatória; dispersão concentrada num descritor faz o instrumento mudar.

**Resolve.** A régua alheia que deriva sem ninguém ver.

**Exemplo.** Na calibração, todos os pares divergem em "Pacote": o problema não é dos pares, é do descritor 3 de 5 do Cartão 2. Reescreve-se o descritor.

**Vive em.** `avaliacao` (seleção, cálculo); `metricas` (as séries).

**Origem.** F6·L6; Guia do Mentor, Parte 6.

### 25. O fluxo de Banca

**O que é.** Agendamento com composição sem impedimentos, dossiês 3 dias antes, rubrica individual (quem não preencheu não entra na mesa), apresentação (ao vivo ou gravada), comparação fora da vista do aluno, laudo único, decisão com data, registro. A Banca em treinamento da E32 informa o avaliado e permite recusa.

**Resolve.** Bancas que viram conversa de impressões; notas de membro vazando ao aluno.

**Exemplo.** Banca de Nível 2: o botão "comparar rubricas" só habilita quando os três membros preencheram e a apresentação terminou. Divergência de 11 pontos no dossiê exige conciliação obrigatória antes do laudo.

**Vive em.** `avaliacao`.

**Origem.** F6·L6; E10, E21, E32.

### 26. A jornada com gating

**O que é.** As 33 lições como caminho com portas: o checkpoint aberto libera a próxima; o Boss libera o bloco; a Banca libera a Parte. Leitura livre; execução com porta.

**Resolve.** O Inferno dos Tutoriais: assistir sem entregar.

**Exemplo.** O aluno pode ler a E09 inteira, mas o "Nós fazemos" da E09 só abre quando o checkpoint da E08 (Marco #1) estiver aberto.

**Vive em.** `alunos` (extensão, se ainda não houver gating por lição), consumindo `checkpoint.aberto` de `avaliacao`.

**Origem.** F6·L2.

### 27. As pausas reais dentro da aula

**O que é.** O player para no fim do bloco do erro produtivo e mostra o formulário de registro; o "retomar" habilita com os campos obrigatórios preenchidos. "Faça agora" para sem validação.

**Resolve.** A aula que se assiste em vez de se fazer.

**Exemplo.** E22, fim do Bloco 1: três observações mais "a malha ao redor da articulação é igual ou diferente?". Sem isso, o Bloco 2 não abre. Registrar dá 10 XP.

**Vive em.** `alunos` (player) com o pacote de integração (timecodes) vindo do conteúdo.

**Origem.** F6·L2, seção 3.2; Guias de Produção.

### 28. XP, Sequência, medalhas, Marcos e degraus

**O que é.** A gamificação do curso: entregar dá XP (aprovar dá porta, nunca XP); a Sequência da escola; 12 medalhas de Boss; 6 Marcos com três estados (bloqueado, validado, ou carimbado com a data do mundo); os 7 Degraus acendendo.

**Resolve.** Recompensar quem acerta de primeira mais do que quem entrega três vezes: o incentivo errado.

**Exemplo.** Marco #3 (primeiro dólar): validado quando o Selo e o protocolo de lançamento estão completos; carimbado meses depois, com a data da primeira venda que o aluno informou e o Mentor confirmou. A jornada nunca travou esperando.

**Vive em.** `gamificacao` (não se reimplementa), consumindo eventos de `avaliacao`.

**Origem.** F6·L2, L7.

### 29. Os 33 quizzes e o Recall

**O que é.** Cinco perguntas por lição, resposta livre curta, com a resposta-modelo ao lado e autoavaliação (acertei, parcial, ou errei), sem nota que bloqueie. O Recall de 2 minutos: quatro perguntas com anel de 6 segundos e "respondi em voz alta".

**Resolve.** Reconhecer não é explicar.

**Exemplo.** Um aluno marca "errei" em três das cinco da E13; a plataforma sugere a seção 13.2 antes do checkpoint. Sugere, não trava.

**Vive em.** `quiz` (os 33 como dados carregados).

**Origem.** F6·L2, seção 6.

### 30. O Meu Estúdio: portfólio, dossiê e vitrines

**O que é.** As 35 Páginas (Página 0 imutável, o cubo com a data; 1 a 32; B; a carta), o dossiê automático por lição (envios, laudos, registros, quiz), e as três vitrines públicas geradas (1.0 na E10, 2.0 na E21, 3.0 na E31).

**Resolve.** Portfólio que ninguém monta; provar o que se sabe.

**Exemplo.** A Vitrine 2.0 abre com o campo "por que este e não outro" e as listagens da loja; um cliente vê as Páginas 12 a 18 e a resposta de orçamento sem entrar na plataforma.

**Vive em.** `alunos` ou `avaliacao` (decisão pendente); exportável em PDF, do aluno para sempre.

**Origem.** F6·L2, seção 7.

### 31. O cliente simulado

**O que é.** Para quem estuda sozinho: uma sequência de mensagens temporizadas que interpreta o Estúdio Norte (E09) e, na E20, executa os quatro desvios (silêncio, mudança de escopo, feedback vago, o erro do aluno) com ramificações conforme a resposta.

**Resolve.** Aprender a conduzir cliente sem cliente.

**Exemplo.** Dia 5: "dá pra incluir uma variante em outra cor?" Se o aluno nomeia custo e devolve a decisão, o cliente aceita e elogia; se aceita de graça, o cliente pede outra mudança no dia 6.

**Vive em.** `mensageria` (sequência), com o roteiro como dado de lição.

**Origem.** F6·L3, L4.

### 32. O painel de lançamento

**O que é.** Onde o aluno registra, semana a semana, impressões, visitas e vendas da própria listagem; calcula as taxas do funil; **bloqueia mais de uma mudança por ciclo**; ao fim, o formulário de decisão (manter, iterar, ou arquivar, com motivo).

**Resolve.** Mudar três coisas de uma vez e não saber qual funcionou; ler um número sozinho.

**Exemplo.** Semana 2: o aluno registra "troquei a thumbnail", os outros campos de mudança travam até a leitura da semana 3.

**Vive em.** `alunos` (ou `funil`, se cobrir); métricas em `metricas`.

**Origem.** F6·L4 (E18).

### 33. O rastreador de pitches e o reconhecimento de campo

**O que é.** O formulário de reconhecimento (três espaços vezes três perguntas) que **bloqueia o pitch antes de existir**; o rastreador com cinco envios mínimos, cada um com alvo, data, texto e estado, e a métrica exibida é **envios**, não respostas.

**Resolve.** Postar antes de entender o lugar; parar depois de três silêncios.

**Exemplo.** O painel diz "5 enviados, 1 respondido" e, embaixo: "o próximo pitch começa antes da resposta do anterior".

**Vive em.** `alunos` ou `leads`.

**Origem.** F6·L4 (E19).

### 34. O companheiro digital por lição

**O que é.** Por lição: os arquivos de prática (com metadado que nunca revela o defeito), o Cartão de 1 página, os modelos anexos, as capturas atuais datadas ("a tela exata muda; o princípio não"), as referências.

**Resolve.** Botões que envelhecem; arquivo que falta e quebra o erro produtivo.

**Exemplo.** Na E08, a captura do exportador FBX tem "Blender 4.x, capturado em 03/2027". Quando o Blender mudar, a captura muda; o capítulo não.

**Vive em.** Assets (armazenamento de objetos) referenciados pelos dados de lição; a célula que serve o curso os exibe.

**Origem.** F6·L2, L3 a L5, L8.

### 35. Os apêndices vivos com cabeçalho e vigia

**O que é.** Seis apêndices (C, H, J, M, N, I) com cabeçalho obrigatório (versão, verificado em, por, próxima verificação, o que mudou), ciclos (mensal N e J; trimestral C, H, M; semestral I), verificação vencida como aviso público, e o **vigia de fontes** que detecta mudança na página oficial e redige o diff.

**Resolve.** O livro que imprime número e fica errado antes de sair da gráfica.

**Exemplo.** O Apêndice N muda; a plataforma avisa quem está em E22 a E25 e quem tem personagem em moderação, marca os arquivos de referência viva "em verificação", insere nota nos capítulos sem editar texto, e invalida leituras do Selo anteriores à versão.

**Vive em.** `conteudo/meshcraft/apendices/` (dados) mais portão de cabeçalho; avisos via `notificacoes`; relato de divergência via `sugestoes`.

**Origem.** F5·L4; F6·L8.

### 36. A conta de responsável e o circuito de menores

**O que é.** A conta que vê (progresso, laudos, contratos, Marcos) e dá ciência onde há dinheiro, contrato ou exposição pública: publicar item, carimbar Marcos #3/#4/#6, contratos, delegar, tornar página pública, prospecção real. Nunca bloqueia checkpoint, crítica ou Banca.

**Resolve.** Proteger sem virar gargalo do aprendizado.

**Exemplo.** Um aluno de 14 anos submete o cabelo à loja: a submissão espera a ciência do responsável; o checkpoint da E17 já abriu, e ele segue para a E18.

**Vive em.** `identidade` (vínculo, papel), com os eventos de `avaliacao`/`gamificacao` consultando a ciência.

**Origem.** Apêndice H; F6·L7.

### 37. Contratos com aceite digital e comprovantes tarjados

**O que é.** Os contratos (L2, P3, P5) gerados com hash, aceitos por link sem conta pelo externo, com segundo aceite do responsável se houver menor; comprovantes de Marco como imagem/PDF com ferramenta de tarja, sem campo de valor, substituíveis por recibo aos 30 dias.

**Resolve.** Registrar que o dinheiro aconteceu sem tocar no dinheiro.

**Exemplo.** Marco #6: o aluno sobe o comprovante do pagamento feito ao Kai, tarja o valor, informa a data; o Mentor confirma em 48h; aos 30 dias a plataforma oferece trocar a imagem por "Marco #6 carimbado em 12/03, conferido por…".

**Vive em.** `encomendas` ou `avaliacao` (decisão pendente); nunca em `pagamentos` como transação.

**Origem.** F6·L7.

### 38. A telemetria anonimizada

**O que é.** As sete métricas da Curva do Aprendiz (tempo por lição com quartis, abertura na primeira tentativa, onde as pessoas param, detecção dos erros produtivos, quiz, mudança repetida, dispersão de rubricas), com n maior ou igual a 20 e opt-out.

**Resolve.** Não saber quanto tempo leva de verdade, e otimizar o curso para a métrica.

**Exemplo.** O relatório de abril: a E13 tem 38% de abertura na primeira tentativa contra dificuldade prevista "alta" (dentro do esperado); a E06 tem 41% contra "média" (fora do esperado): é o ajuste do mês.

**Vive em.** `metricas` (o livro de fatos).

**Origem.** F6·L8; F7·L5.

---

# Família C: as ferramentas de conteúdo e produção

### 39. O cofre: a fonte única com esquema

**O que é.** `conteudo/meshcraft/`: as 33 lições decompostas nas 16 peças (cada passo com seu "Você deve ver"), os instrumentos, o Padrão, os apêndices, o dicionário, como dados versionados, de onde tudo se gera.

**Resolve.** Três cópias (livro, aula, plataforma) conferidas à mão; o conteúdo vivendo num histórico de chat.

**Exemplo.** Uma mudança no passo 7 do "Nós fazemos" da E22 regenera o capítulo, o roteiro, a ficha de preparo e o formulário de checkpoint, e o teste de coerência confirma que os três meios dizem o mesmo.

**Vive em.** `conteudo/meshcraft/` mais `01_esquemas/`.

**Origem.** Alavanca 1; LEIA-ANTES §4.

### 40. Os geradores de derivados

**O que é.** Scripts (e o agente Gerador) que produzem, da fonte: capítulo em Markdown, roteiro anotado, Cartão de 1 página, quiz em JSON, ficha de preparo, formulário de checkpoint, glossário, briefs de figura, resumos leigos.

**Resolve.** Centenas de derivados feitos à mão e dessincronizados.

**Exemplo.** "Gerar quiz E22" produz cinco perguntas com as respostas da seção "Respostas", cada uma com a seção de origem, prontas para a célula `quiz`.

**Vive em.** `ci/` ou `tools/` (conforme o doc 05); a Ficha do agente em `fichas_agentes/`.

**Origem.** Alavanca 8; como criar agentes 5.5.

### 41. Os portões de conteúdo

**O que é.** Testes-guarda com semântica de 4 estados: `guarda-de-conteudo` (esquema: 16 peças, passos com "Você deve ver"); coerência (remissões `E[NN]`, nomes canônicos, arquivos citados existem, "Aceito quando" igual ao formulário); **dado vivo em lição** (reprova número de plataforma em texto corrido); cabeçalho de apêndice vivo; vinculação do companheiro.

**Resolve.** Mecanizar em vez de documentar.

**Exemplo.** Um PR insere "o limite é 1.200 triângulos" num capítulo: FAIL, "número de plataforma em lição; mova ao Apêndice C com remissão".

**Vive em.** `ci/` mais `ci/tests/`.

**Origem.** Alavanca 8; LEIA-ANTES §4.

### 42. Os scripts de plantio e o verificador de higiene

**O que é.** Para cada arquivo de prática, um script Python/Blender que parte da solução limpa e planta os defeitos especificados, determinístico e parametrizado (`duplicar_vertices(n=14)`), mais o script que confere que **só** o plantado está errado.

**Resolve.** 27 arquivos artesanais que se refazem a cada versão do Blender; calibragem que exige remodelar.

**Exemplo.** A detecção do "escala não aplicada" da E02 caiu para 22% (faixa esperada: 40% a 60%). Muda-se `escala=2.5` para `3.0`, reroda-se, reinicia-se a medição. Dois minutos.

**Vive em.** `ci/` (o verificador como portão) e `tools/plantio/`; assets gerados no armazenamento.

**Origem.** Alavanca 7; F6·L3 a L5.

### 43. A cena de render padrão

**O que é.** Um `.blend` da escola com câmera, luz (chave a 45° superior-esquerda, preenchimento fraco), material cinza e fundo cinza-bancada fixos, onde **toda** figura de objeto do livro é renderizada.

**Resolve.** A espada da E01 e o corpo da E22 com luzes diferentes: a comparação entre capítulos que não funciona.

**Exemplo.** Produzir a figura 22.3: importar o corpo, marcar os três loops em laranja, renderizar. Nada de luz "para ficar bonito".

**Vive em.** `tools/figuras/cena_padrao.blend`.

**Origem.** F8·L2, seção 3.

### 44. A biblioteca de primitivas e o gabarito do par

**O que é.** Um arquivo vetorial mestre com as cinco primitivas das figuras de processo (caixa, linha, seta, filete, marca), os quatro formatos de dado (funil, barras, linha temporal, medidor), e o gabarito fixo do par de comparação (filete vertical, legenda em itálico, sem rótulo certo/errado).

**Resolve.** Trinta figuras de processo desenhadas de trinta jeitos; figuras que parecem captura de tela.

**Exemplo.** A fila do Estúdio Norte (E29): cinco colunas de estado, caixas com dois nomes (dono e revisor), e **uma seta em laranja** de "revisão" para "produção": o retrabalho. Sem janela, sem ícone.

**Vive em.** `tools/figuras/primitivas.svg`, `gabarito_par.svg`.

**Origem.** F8·L2.

### 45. A caligrafia técnica

**O que é.** Uma fonte (ou traçado) de escrita à mão usada exclusivamente nos instrumentos preenchidos das figuras, para distinguir "este é o formulário" (o apêndice) de "assim alguém preencheu" (a figura).

**Resolve.** Ensinar, sem dizer, que o cartão é para escrever na bancada.

**Vive em.** `tools/figuras/`; licença registrada.

**Origem.** F8·L2, família D.

### 46. O tema do Blender e os cinco workspaces

**O que é.** Um tema fixo (viewport cinza médio, malha cinza claro, **seleção no laranja do livro**, painéis cinza escuro) e cinco workspaces (modelagem, UV, textura, peso, animação), usados em toda captura das 34 aulas.

**Resolve.** O tema padrão que muda entre versões; "os três loops em laranja" que precisa ser o mesmo laranja no livro e na tela.

**Vive em.** `tools/video/tema_meshcraft.xml`, `workspaces.blend`.

**Origem.** F8·L3, seção 4.

### 47. O kit de vídeo

**O que é.** Projeto-modelo de edição com a linha do tempo pré-estruturada nos blocos da anatomia; biblioteca de cartões (conceito, "Você deve ver", cerimônia, com fade e permanência, sem zoom nem partícula); os três sons funcionais (check, notificação, sendo que a do Mentor é diferente, selo); as três peças musicais nas durações; a LUT única; presets de captura (2560×1440, 60 fps) e exportação.

**Resolve.** A aula 30 não parecer a aula 3.

**Exemplo.** O editor arrasta o cartão "Você deve ver" no fim do passo 7: ele já vem com o filete verde, o congelamento de 2 s e o som de check.

**Vive em.** `tools/video/`.

**Origem.** F8·L3, seção 10.

### 48. A ficha de preparo e a execução em silêncio

**O que é.** Uma ficha por aula (arquivos verificados, cenas, overlays, elementos a produzir, pessoas e set) cujo último bloco é obrigatório: **executar a aula inteira sem gravar**, medir o tempo real, registrar divergências.

**Resolve.** A regravação: o único custo da produção que não estava previsto.

**Exemplo.** Executando a E16 em silêncio, o preparo descobre que o menu de LOD mudou de lugar na versão de referência. O roteiro ganha a nota; a captura do companheiro é refeita; a gravação não é interrompida.

**Vive em.** Modelo R4, gerado da fonte; `docs/meshcraft/producao/`.

**Origem.** F8·L6, seção 3.1; playbook P16.

### 49. O roteiro anotado e o pacote de integração

**O que é.** O roteiro com timecodes previstos, **as pausas marcadas com duração** (a defesa contra o editor que corta silêncio), a lista de cartões, os "Você deve ver", os "faça agora" e as cerimônias, e, após a edição, o pacote que a plataforma consome: timecode de cada bloco, de cada pausa real com o identificador do formulário, dos downloads contextuais.

**Resolve.** A pausa que não para: o defeito que quebra o gating do curso inteiro.

**Exemplo.** "E22: bloco1_fim=04:30, pausa_real=registro_E22_erro_produtivo, cronometro=10:00": o player para ali e só retoma com o registro.

**Vive em.** Dados da lição; gerado pelo Roteirista de edição.

**Origem.** F8·L6, seção 7; playbook P24.

### 50. O acervo de capturas datadas

**O que é.** Cerca de 40 capturas de tela (uma por "botão" citado), cada uma com id, lições que a citam, a frase do capítulo, versão do software e data; estado atual, em verificação, ou substituída.

**Resolve.** Regravar aulas porque um menu mudou.

**Vive em.** Assets mais índice em `conteudo/meshcraft/capturas/`.

**Origem.** F6·L8, seção 3; playbook P66.

### 51. A lista de controle de vocabulário e o script de remissões

**O que é.** Gerados do Dicionário: os nomes canônicos, os defeitos com nome, os personagens, os arquivos, e o script que extrai toda menção `E[NN]` e confere alvo e assunto.

**Resolve.** "O erro da E03" apontando para algo que está na E04.

**Vive em.** `ci/tests/test_conteudo_coerencia.py`.

**Origem.** F8·L5, seção 5.2; playbook P07.

### 52. A matriz de produção do livro e do vídeo

**O que é.** Duas matrizes calculadas dos registros: 12 blocos vezes etapas (figuras, diagramação, 4 passadas, congelado) e 34 aulas vezes 4 frentes (preparo 2 à frente, gravação, edição 1 atrás, integração), com a regra de sequência como bloqueio (bloco não diagrama sem figuras aprovadas).

**Resolve.** Diagramar com caixa vazia e encaixar depois.

**Vive em.** Vistas do `painel/` (F6 remapeada), a partir de registros.

**Origem.** F8·L5, L6; plano do painel, painéis 5 e 6.

### 53. O índice remissivo e o índice de encomendas

**O que é.** Gerados: o remissivo com entradas em inglês ("n-gon", "cage") e a página da definição em negrito; o índice de encomendas com número, título, degrau, instrumento, regra e página.

**Resolve.** A consulta: alguém na E27 achando a régua orgânica da E22 em vinte segundos.

**Vive em.** Gerado da fonte na Fase 8.

**Origem.** F8·L5, seção 6.

### 54. O sistema visual do livro (o manual de estilo e os gabaritos)

**O que é.** Seis cores (com o verde exclusivo de "Você deve ver" e "Aceito quando" e o laranja-loop como único destaque), duas famílias tipográficas, a grade 170×240 com a **margem viva de 34 mm** (onde vivem os "Você deve ver", as remissões e o lápis do leitor), três níveis de marcação das 16 peças, as mestras de página.

**Resolve.** 650 páginas diagramadas por mais de uma pessoa com três grades diferentes.

**Vive em.** `docs/meshcraft/producao/manual_visual.md` mais gabaritos.

**Origem.** F8·L1.

---

# Família D: as ferramentas de pesquisa (o Atlas)

### 55. O método congelado e o livro de códigos

**O que é.** O documento de método (três fontes e o que cada uma sustenta; a limitação central, visível não é igual a vendido; n mínimos; a regra de quando o dado contradiz o livro) e o livro de códigos: cada variável com valores, critério de decisão e exemplo (`contraste_item_fundo` medido com conta-gotas: alto maior ou igual a 50%).

**Resolve.** Opinião com tabela.

**Exemplo.** `legivel_em_miniatura`: reduzida a 128 px, reconhecível em 2 s, cronometrado, decidido em uma passada, sem voltar.

**Vive em.** `docs/meshcraft/atlas/metodo.md`, `livro_de_codigos.md`, congelados com data antes de cada coleta.

**Origem.** F7·L2, L3.

### 56. O coletor cego ao grupo

**O que é.** O script que captura os itens públicos da amostra (325 visíveis mais 325 controle), embaralha, e entrega ao codificador **sem** dizer se o item é visível ou controle.

**Resolve.** A expectativa contaminando a codificação: o que destruiria a comparação que é o coração do estudo.

**Vive em.** `tools/atlas/coletor.py`.

**Origem.** F7·L3, seção 4.3.

### 57. A dupla codificação e o cálculo de concordância

**O que é.** 20% da amostra codificada por um segundo codificador (cego ao primeiro); concordância por variável: 80% ou mais publica; entre 60% e 79% refina e recodifica; abaixo de 60% a variável sai da tabela.

**Resolve.** Publicar como fato uma variável que dois olhos leem diferente.

**Vive em.** `tools/atlas/concordancia.py`; nota em toda tabela publicada.

**Origem.** F7·L2, seção 5.

### 58. O teste do intruso

**O que é.** Para cada família de estilo candidata: um painel de silhuetas do grupo com um intruso de outro grupo, mostrado a três pessoas de fora; se 2 ou mais apontam o intruso, a família se sustenta.

**Resolve.** Inventar famílias que não existem.

**Vive em.** Protocolo em `docs/meshcraft/atlas/`.

**Origem.** F7·L4, seção 3.2.

### 59. As fichas por categoria e o mapeamento inverso

**O que é.** A ficha de cada categoria com a seção obrigatória "o que não difere"; e a tabela que cruza cada afirmação do livro com o que o dado sustenta, com a correção "vendem, leia-se visíveis" e a remoção da "faixa de estúdio" da E30.

**Resolve.** O livro afirmar o que a pesquisa não pode provar.

**Vive em.** O estudo publicado, primeira página: "O que este estudo sustenta, e o que não".

**Origem.** F7·L3, seções 5 e 7.

### 60. O formulário de contribuição ao Atlas

**O que é.** Onde o aluno contribui com os dados da própria loja em três modos (anônimo, creditado, agregado), com verificação de reidentificação (se a combinação de campos isola um criador, sugere agregado) e retirada a qualquer momento.

**Resolve.** O Atlas como pesquisa só da escola; a autoridade de quem forneceu os dados.

**Vive em.** Adiado (célula `atlas` futura); enquanto isso, `sugestoes` ou formulário estático.

**Origem.** F6·L8, seção 4; E31.

### 61. O relatório mensal da Curva do Aprendiz

**O que é.** Uma página, cinco perguntas: onde param, o que está mais duro do que o previsto, qual erro produtivo saiu de calibragem, qual descritor dispersa, **mudanças repetidas** (a métrica que mede a casa), e um campo único, o ajuste do mês.

**Resolve.** Afrouxar réguas para subir a taxa de abertura; três mudanças sem saber qual funcionou.

**Vive em.** Gerado de `metricas`; modelo R6.

**Origem.** F7·L5, seção 5.

---

# Família E: as ferramentas de gestão do projeto

### 62. O manifesto de escopo

**O que é.** O arquivo legível por máquina com a hierarquia fase, lote, etapa, item: id estável, descrição leiga, origem, dono (papel), dependências, tipo, verificação, critérios de aceite. Norma: diz o que deve existir, nunca o que existe.

**Resolve.** Não saber o que falta construir, e o placar escrito à mão.

**Exemplo.** "F6.L1.E2.I3, ChangeSpec de avaliacao aprovado, tipo: codigo_celula, verificação: secao_existe(painel/ia/04, "avaliacao"), depende_de: D2 (dono do portfólio)".

**Vive em.** `painel/meshcraft/manifesto.yaml`.

**Origem.** O prompt da sessão de painel, 3.1.

### 63. Os tipos de registro de fato

**O que é.** A extensão do livro de ocorrências: `item.iniciado`, `item.entregue` (com evidência), `item.aceito` (só humano), `item.devolvido`, `porta.dossie`, `porta.decidida`, `decisao` (o R1), `excecao` (o R3), `lacuna`, `decisao_pendente.resolvida`. Anexados, nunca editados.

**Resolve.** Dois placares; o "concluído" que ninguém sabe quem escreveu.

**Vive em.** `painel/registros/`, no schema do doc 03.

**Origem.** Idem, 3.2.

### 64. As sete vistas calculadas

**O que é.** Estado por item (previsto, em andamento, entregue, aceito, ou auditado; mais bloqueado e devolvido); o checklist vivo por fase/lote/etapa/item com contadores e denominadores; portas; caminho crítico; pendências humanas; **auditoria** (aceito e não conferido, a vista mais importante do fim); lacunas.

**Resolve.** "Em que fase estamos, qual a próxima porta, o que está atrasado", em 60 segundos.

**Vive em.** O gerador de `painel/painel.html`.

**Origem.** Idem, 3.3.

### 65. Os portões de auditoria

**O que é.** `guarda-manifesto` (ids únicos, dependências resolvem, sem ciclos, origens existem, contagens batem); `guarda-registros` (todo registro cita item existente; aceito tem quem conferiu; nunca editado); `auditoria-meshcraft` (para cada item entregue, executa a verificação declarada: arquivo existe, hash confere, esquema válido, teste passa, seção existe; **humano vira SKIP, nunca PASS**; aceito com FAIL reprova a suíte).

**Resolve.** A conferência final feita à mão, e o aceite sem evidência.

**Exemplo.** O item "Cartão 1 em PDF público" foi registrado como entregue com o caminho `/padrao/instrumentos/cartao-01.pdf`; a auditoria faz GET, confere o hash, PASS. O item "6 testadores fizeram o piloto" é `humano`: SKIP com motivo, até um `aceito` humano.

**Vive em.** `ci/`.

**Origem.** Idem, 3.4.

### 66. O playbook e o LEIA-ANTES

**O que é.** O playbook (66 plays com quando, quem, entradas, passos, checklist, saídas, falhas, escalação) como norma ao lado de `RITOS.md`; e o LEIA-ANTES: a ordem de leitura, o mapa do que é o quê, as colisões de vocabulário, a checagem de pré-voo (nove perguntas) e de pós-voo, a lista curta do que nunca se faz, quando parar e chamar o mantenedor.

**Resolve.** Sessões que criam `services/meshcraft/`, duplicam XP, ou escrevem "pronto" à mão.

**Vive em.** `docs/meshcraft/PLAYBOOK.md`, `LEIA-ANTES.md`.

**Origem.** Playbook; Parte B da revisão.

### 67. As portas de decisão (G0 a G8)

**O que é.** Oito portas com critérios escritos antes de existir custo: publicar o Padrão, sistemas fechados, o piloto, plataforma mínima, liberação da Parte I, II e III, tiragem, primeiro relatório, cada uma com dossiê (critério mais evidência) e decisão (passa, passa com condições, ou não passa). Nenhum critério é alterado na reunião.

**Resolve.** Renegociar o critério diante do calendário.

**Vive em.** Manifesto (itens de tipo registro) mais `porta.dossie`/`porta.decidida`.

**Origem.** Roadmap §29.

### 68. A Ficha de Série da produção e dos agentes

**O que é.** O mesmo instrumento nº 9 aplicado à execução: por semana, cadência (blocos, figuras, aulas), tempo médio por artefato, retrabalho (devolvidos), conformidade (aprovados sem correção), para as frentes de produção, para o Mentor e para cada agente. Lida na sexta com **um ajuste**.

**Resolve.** Otimizar o que se sabe otimizar em vez do gargalo (E26); agentes subindo de autonomia por vontade.

**Vive em.** `metricas`; modelo R7.

**Origem.** Playbook P64; equipe de agentes §8.

### 69. O catálogo de armadilhas do Meshcraft

**O que é.** As entradas em `armadilhas/` para cada erro real cometido na execução do Meshcraft: o mecanismo que o sitesdoreino já tem, alimentado por este projeto.

**Resolve.** Repetir o que já deu errado.

**Vive em.** `armadilhas/` (existente).

**Origem.** LEIA-ANTES §9.

---

# Família F: as ferramentas de lançamento

### 70. O Padrão online

**O que é.** Site estático gerado do cofre, em `/padrao`: uma página por família, âncoras estáveis por seção (`#s14-expressao`, que nunca quebram: regra que caiu vira nota com a âncora preservada), os seis blocos por seção, downloads sem cadastro, changelog público, formulário de propostas com fila pública e recusas publicadas, índice de versões locais com mapa de calor. A menção ao curso: três linhas no rodapé, e nada mais.

**Resolve.** Autoridade que não se compra: estúdios adotando sem comprar nada.

**Exemplo.** Um estúdio registra que adaptou §7 (prefixo próprio de Pacote); o mapa de calor mostra que 8 estúdios adaptaram §7 do mesmo jeito, candidata a mudar na revisão anual.

**Vive em.** Deploy multissítio, gerado na CI.

**Origem.** F7·L1.

### 71. O cartão do STUDS e o vídeo de 5 minutos

**O que é.** O Cartão 1 em PDF com rodapé de duas linhas, e um vídeo de cinco minutos: as três espadas, "ordene", 30 segundos de pausa, as cinco letras ao vivo, o laudo, e a chamada final para o trabalho da pessoa ("aplique nas suas três últimas peças"), não para o curso.

**Resolve.** A isca que só faz sentido como degrau de venda, e por isso ninguém usa.

**Vive em.** `/padrao/instrumentos` (público); `funil` se aplicável.

**Origem.** F9·L2.

### 72. A conta gratuita e a Encomenda 00 aberta

**O que é.** O nível de acesso gratuito (e-mail e nome, nada mais) que dá a E00 completa (capítulo, aula com pausa real, arquivos), a Página 0 no Meu Estúdio, as cartas e os cartões. E o único e-mail automático, três dias depois: "você fotografou o cubo?"

**Resolve.** "Vou comprar um curso" (decisão de venda) virando "vou continuar o que comecei" (decisão honesta).

**Vive em.** `identidade` (conta), `alunos` (nível de acesso), `mensageria` (o e-mail).

**Origem.** F9·L2, seções 5 e 7.

### 73. A página de vendas com promessa e prova

**O que é.** Onze seções na ordem: o cubo, os três vilões, o método, os instrumentos (com o índice de estúdios como prova), o percurso, **quanto tempo leva** (admitindo que os números ainda não existem), **para quem não serve** (no meio, seis recusas), **o que acontece se eu parar**, o que recebe e o preço (uma vez, sem ancoragem), a carta do autor por inteiro, perguntas. Cada afirmação com prova ao lado.

**Resolve.** A página que promete renda, prazo e mostra depoimento de quem fez duas encomendas.

**Vive em.** `catalogo`/`funil`; compra em `checkout`/`pagamentos`.

**Origem.** F9·L3.

### 74. A sentinela da véspera e o painel de distribuição

**O que é.** A sentinela: um verificador que detecta em qualquer peça proposta os padrões proibidos (contagem regressiva, "últimas vagas", valor riscado, promessa de renda/prazo, superlativo) e bloqueia com a lista assinada. O painel: envios por grupo, estúdios registrados, downloads, contas gratuitas, **Páginas 0 salvas** (a métrica principal), da Página 0 à compra, e nada de alcance, impressões ou A/B de urgência.

**Resolve.** A pressão da véspera; medir o que não informa decisão.

**Vive em.** Portão de CI sobre `catalogo`/`funil` (a sentinela); `metricas` (o painel).

**Origem.** F9·L1, L4.

### 75. O link de teste do posicionamento

**O que é.** Uma tela única, enviada a alguém de fora: a frase do posicionamento e um campo, "me diga o nome de mais um estúdio que poderia ter escrito exatamente isto". Se vem um nome, o formulário marca `falhou` e sugere reescrever.

**Resolve.** A resposta A ("fazemos tudo bem") que o cliente compara pelo preço.

**Vive em.** Formulário estático ou `sugestoes`; usado pelo aluno na E31 e pela escola na F9·L1.

**Origem.** E31; F6·L5.

---

# Família G: os agentes (sessões de IA com ficha)

### 76. Os agentes de conteúdo e verificação

**O que é.** Sessões com Ficha de Delegação (os oito campos como prompt de sistema): **Extrator** (decompõe a fonte com origem citada), **Guardião de fidelidade** (os sete desvios: invenção, regra virou sugestão, nome trocado, omissão, sentido alterado, decisão simplificada, comparação entre pessoas), **Gerador de derivados**, **Glossarista**, **Vigia de fontes**, **Propagador**, **Redator de propostas ao Padrão**. Autonomia por degrau (A, P ou H), que sobe pela Ficha de Série.

**Resolve.** Semanas de trabalho mecânico; e a invenção que passa por conteúdo.

**Exemplo.** O Guardião recebe a ficha traduzida do P43 e uma versão sabotada em que "não se alonga" virou "tente cumprir": aprova a fiel, devolve a sabotada apontando os dois trechos.

**Vive em.** `conteudo/meshcraft/fichas_agentes/`; entregam por PR; os verificadores mecanizáveis viram portões (nº 41).

**Origem.** Equipe de agentes §4; como criar agentes §5.

### 77. Os agentes de produção

**O que é.** **Briefador de figuras**, **Produtor de figuras (objeto)** (opera a cena padrão por script), **Preparador de aula** (gera a ficha; a execução em silêncio é humana), **Roteirista de edição** (o roteiro anotado e o pacote de integração), **Editor assistido**, **Legendador** (transcreve e corrige termos contra o Dicionário), **Plantador** (nº 42), **Construtor** e **Carregador de seeds** da plataforma.

**Resolve.** O gargalo de produção; a aula 30 diferente da aula 3.

**Exemplo.** O Legendador transcreve "prova dos três movimentos" e corrige para "Prova dos 3 Movimentos" antes de a legenda ir à revisão humana.

**Vive em.** Idem; saídas em P (humano confirma).

**Origem.** Equipe de agentes §4.

### 78. Os agentes de operação

**O que é.** **Assistente de laudo** (nº 22), **Triador da fila** (ordena por prazo, anexa laudo anterior em reenvio, marca estouro, sugere atribuição), **Amostrador de revisões**, **Calibrador**, **Vigia do silêncio** (os 14 e 30 dias), **Preparador de Banca** (composição, dossiês, bloqueio da comparação), **Carimbador** (confere evidência e ciência), **Sentinela da véspera** (nº 74). Todos com o guardrail: **nenhum envia, publica, decide nota, data, título ou carimbo**.

**Resolve.** O Mentor como ponto único de tudo, sem tirar dele o que dá ao produto o seu nome.

**Exemplo.** Um dia: o Vigia detecta que o Apêndice N mudou (7h); a Triagem já ordenou nove envios e o Assistente os pré-preencheu (8h30); a autora aprova o apêndice em dois minutos e faz nove laudos em 40 (9h às 10h); o resto do dia é gravação.

**Vive em.** `avaliacao` (os que operam sobre a fila) e sessões; Fichas versionadas.

**Origem.** Equipe de agentes §4, §14.

---

## O que estas 78 ferramentas têm em comum

Três coisas, e são elas que fazem o projeto ser um só, e não um curso com um monte de anexos:

- **Toda ferramenta tem uma régua.** Cada uma diz como se verifica que foi usada certo, de "nenhuma letra abaixo de 3" a "humano vira SKIP, nunca PASS".
- **As ferramentas do aluno e as da equipe são as mesmas.** A Ficha de Série mede a linha do Téo, o colaborador Kai, a produção do livro e o agente Extrator. A Ficha de Delegação é o que se dá a uma pessoa e o que se dá a um agente. A Revisão de Estúdio avalia a peça do aluno e a saída da sessão de IA. O projeto se opera com o que ensina.
- **Nada é fonte de verdade duas vezes.** O conteúdo vive no cofre; o status, nos registros; os limites, nos apêndices vivos; os fatos, em `metricas`. Cada ferramenta lê de onde deve e escreve onde pode, e um portão reprova quem faz diferente.

---

*As ferramentas do projeto Meshcraft · 5 de setembro de 2026 · Setenta e oito ferramentas, sete famílias, e a constatação de que o aluno que termina o curso sai com as mesmas dezenove que a escola usa para construí-lo.*
