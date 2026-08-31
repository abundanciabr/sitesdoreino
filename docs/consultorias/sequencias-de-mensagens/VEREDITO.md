# VEREDITO — a consultoria externa sobre o plano das sequências de mensagens

**Data:** 31/08/2026 · **Quem consultou:** o mantenedor, por conta própria ·
**Consultores:** Gemini, GPT e Fable · **Quem sintetizou:** a sessão que escreveu
o plano.

> **Para dar este documento a uma IA**, use o endereço `raw` do GitHub. A marca
> `publico-para-ia` NÃO vale aqui: a área `/mapa-ia/planos/` serve
> `docs/decisoes/`, e este arquivo mora em `docs/consultorias/`. Pôr a marca
> assim mesmo seria deixar uma mentira esperando alguém acreditar nela.

> **O que este documento é:** a síntese dos três pareceres, com o resultado da
> **conferência de cada afirmação contra o código**, e o que virou correção no
> `PLANO-SEQUENCIAS-DE-MENSAGENS.md`.
>
> **O que ele NÃO é:** a transcrição dos pareceres. Cada achado está aqui
> atribuído a quem o fez e com o veredito da medição — que é o que um leitor
> futuro precisa. Dizer isto é melhor do que dar a entender que os textos
> integrais estão preservados.

## Como a consultoria aconteceu, e por que isso importa para ler o resultado

O mantenedor mandou o plano aos três por conta própria. **Não houve prompt de
consultoria escrito para provocar objeção** — foi o documento e a pergunta dele.
Isso explica o placar, e a explicação vale mais que o placar:

| | achados reais | achados que só ele fez |
|---|---|---|
| **GPT** | 8 | versionamento sem mecanismo · onde mora o texto · preferências sem tabela · ausência não é gatilho |
| **Fable** | 4 | **a trava que impede a jornada repetir** · piso de horário · ordem determinística |
| **Gemini** | 0 | — |

**O Gemini não errou: ele parafraseou.** Devolveu um resumo fiel (conferido: só
um deslize, dizer que `Passo` é versionado quando só `Jornada` tinha `versao`),
sem uma objeção. Num plano deste tamanho isso diz mais sobre a pergunta do que
sobre o plano — **um documento que se explica bem convida a ser parafraseado.**
Quem quiser crítica de um consultor precisa pedir discordância com todas as
letras, como o `docs/consultorias/gamificacao/PROMPT-CONSULTORIA.md` já fazia.

**E parecer de robô foi conferido, não repassado.** Todas as afirmações abaixo
foram medidas contra `origin/main` antes de virarem correção — a lição de
30/08/2026 (`feedback_nao_repassar_achado_de_robo_sem_conferir`) aplicada à
própria consultoria. Uma delas **não** sobreviveu à conferência, e está na §4.

---

## §1 — As dez correções que entraram

Todas verificadas. A coluna "quem viu" existe para dar crédito, e para mostrar
onde um consultor sozinho teria bastado e onde não.

### 1.1 A jornada "sumiu" só rodaria UMA VEZ na vida de cada aluno · *Fable*

**O melhor achado dos três, e nenhum dos outros viu.** `Inscricao` tinha
`unique(jornada, destinatario_id, site_id)` **sem condição**. Quem sumiu em
março, voltou e sumiu de novo em julho bate na trava na segunda vez — e
"sumiu há alguns dias" é uma das quatro sequências que o mantenedor escolheu
(§8.6 do plano). O defeito **bloqueava uma decisão dele.**

**O efeito de segunda ordem, que o Fable também viu:** reaproveitar a linha
antiga (resetar `passo_atual`) não salva. A `Entrega` tem `unique(inscricao,
passo)`, então o passo 1 do segundo episódio colidiria com o do primeiro — e,
pior, o `order_id` sintético (`jornada:<inscricao_id>:<passo_id>`) se repetiria
e o segundo episódio seria **descartado como "já enviado", em silêncio**, pela
trava do pagamento que o plano reusa de propósito.

**A saída, dele:** trava **parcial**, valendo só enquanto a inscrição está
andando (`condition=Q(estado="andando")`). Continua no banco (`armadilhas/023`
atendida), continua impedindo o evento reentregue de inscrever em dobro, e cada
episódio vira uma `Inscricao` nova — o que mantém o `order_id` distinto por
episódio, sem tocar na constraint do pagamento.

### 1.2 O versionamento era promessa, não mecanismo · *GPT*

O plano dizia que mudar uma jornada não afeta quem está no meio dela. O modelo
não garantia isso: `Inscricao → Jornada`, e editar as linhas de `Passo` mudaria
o texto de quem já estava andando.

**Isto é a categoria "garantia sem mecanismo"**, um dos oito padrões que este
projeto catalogou em `docs/decisoes/RETROSPECTIVA-FASE-D.md` como causa dos
próprios erros caros. O plano escorregou na classe que a casa já conhece.

**Correção:** `JornadaVersao` imutável; `Passo` pertence a uma versão;
`Inscricao` aponta para a **versão**. Publicar é criar versão nova. Quem entrou
na v1 termina a v1 — por construção, não por disciplina.

### 1.3 Não havia onde guardar o texto que o mantenedor edita · *GPT*

O plano prometia (§4.2, §8.3) que ele troca a frase pela área administrativa, e
o **contrato congelado no mesmo dia** (`jornada.passo`, PR #688) diz que o texto
vem da tela dele. O §5 não tinha campo de texto, nem por idioma — e a escola
serve três.

**Correção:** `TextoDoPasso`, um por idioma, preso ao `Passo` imutável.

**O que ficou mais enxuto que a proposta do GPT, e por quê:** ele propôs três
tabelas (`MensagemTemplate`, `…Versao`, `…Traducao`). Com o passo já imutável
por versão, o passo **é** o portador do template — uma tabela de tradução basta,
e as três garantias (versionado, traduzível, editável sem PR) continuam de pé.

### 1.4 Não havia onde guardar as preferências · *GPT*

O §5 dizia "quatro tabelas, nem uma a mais"; a régua do §6 e o degrau 3
dependiam de preferências sem casa.

**Correção:** `Preferencia`, por pessoa · canal · **classe** — e não um
`receber_email` booleano. O argumento dele foi aceito por inteiro: o booleano
funciona três meses e vira dívida quando for preciso distinguir segurança de
progresso de comunidade.

### 1.5 A trava de `Entrega` não comportava os canais · *GPT e Fable*

`Passo.canais` é lista (`sino` · `email` · `whatsapp`), e `Entrega` tinha
`unique(inscricao, passo)`: uma linha por passo. Sino entregue + e-mail
devolvido + WhatsApp barrado são três resultados e não cabiam em um.

**Correção:** `unique(inscricao, passo, canal)`. O Fable ofereceu uma
alternativa igualmente válida (a `Entrega` registra a **decisão** do passo e o
destino por canal fica no `EnvioRegistrado`); escolhida a primeira porque a
pergunta "por que o aluno X não recebeu **no e-mail**?" é a que a tela do §7 vai
ter de responder, e ela não deve precisar de duas tabelas para isso.

### 1.6 O teto diário barraria "sua matrícula foi liberada" · *GPT e Fable*

**Cenário testado contra o texto da régua, e ele acontece:** o §6 isentava o
transacional de ser *silenciado* (item 1) mas **não** do teto diário (item 2).
Aluno ganha medalha às 10h; às 18h a matrícula é liberada; a régua barra.
Mensagem de serviço barrada por uma de incentivo.

**Correção:** nasce a **classe de entrega** (`critica` · `transacional` ·
`relacional` · `engajamento`), e as duas primeiras passam **por fora da régua
inteira** — não só do teto. É a formulação do Fable, mais precisa que a do GPT.

### 1.7 Faltavam hora de abrir e ordem determinística · *Fable*

"Nunca depois das 20h" **sem piso** permite reagendar para as 6h da manhã. E
quando duas jornadas disputam a vaga do dia, sem ordem definida o teste do teto
não tem o que afirmar — **guarda que não pode afirmar é guarda decorativo.**

**Correção:** a janela ganha hora de abrir, e o desempate é a inscrição mais
antiga primeiro.

### 1.8 "Sumiu" não é evento e não cabia no campo `gatilho` · *GPT*

O §2 do plano dizia, com todas as letras, que ausência não é acontecimento — e o
§5 definia `Jornada.gatilho` como "o evento que inscreve". O plano se contradizia
a uma página de distância.

**Correção:** nasce o evento derivado **`aluno.inatividade-detectada.v1`**,
publicado por quem varre. É a segunda alternativa do próprio GPT, e ele estava
certo sobre por que ela é melhor que um `tipo_de_entrada` no modelo: preserva a
forma do sistema (detector → evento → jornada) em vez de abrir uma exceção
dentro da jornada. **Exige Rito de Contrato** — entra como degrau próprio.

### 1.9 Faltava dizer de onde as condições leem · *GPT e Fable*

"Já entrou em aula?", "postou no fórum?" — nenhum desses fatos mora na
`mensageria`. Sem definir, cada condição vira chamada síncrona a outra célula, o
`consome:` cresce a cada condição nova, e a varredura vira N×M.

**Correção:** uma projeção (`EstadoDoAluno`) dentro de `jornadas`, alimentada
por eventos, declarada como superfície **calculada** — não fonte da verdade, que
continua na origem (Lei 7 atendida do jeito que o próprio GPT apontou).

**A terceira via do Fable foi considerada e recusada com medição:** ele sugeriu
usar a `leads`, que já monta trilha por pessoa — seria um `consome` em vez de N.
Conferido: a `leads` indexa por **`(site_id, email)`**, não pelo id de
plataforma, e escuta só cinco eventos de pagamento e quiz — não sabe de aula nem
de fórum. Adaptá-la seria mudança maior em outra célula do que construir a
projeção onde ela é usada. **A ideia era boa; o encaixe não é direto.**

### 1.10 O sininho ganhou uma dependência não declarada · *nenhum dos três*

Achado na conferência, e é da sessão que escreveu o plano. O contrato congelado
hoje manda o sininho buscar o texto na `mensageria` na hora de ler. Mas
`celulas.yml` declara `notificacoes: consome: []` — e a célula foi desenhada
para ser **burra e barata de propósito** (`services/notificacoes/…/models.py`:
*"Esta célula é BURRA de propósito, e é isso que a mantém barata"*).

A dependência precisa ser declarada, e o custo dela precisa estar escrito: o
sino aparece em toda página, e passar a consultar outra célula na leitura não é
grátis.

---

## §2 — A decisão do mantenedor que a consultoria provocou

O GPT dedicou dois pontos (11 e 12) à maior ambição: deixar de perguntar só
*"quem recebe o quê e quando"* e passar a perguntar *"qual mensagem está
produzindo qual comportamento"*, com variantes e grupo de controle.

**A análise não foi descartada por custo** — a lei do projeto
(`DECISAO-filosofia-de-escopo.md`) proíbe recomendar escopo menor por ser mais
barato. Foi levada ao mantenedor com as duas consequências que são dele:

- **grupo de controle** significa deliberadamente **não ajudar** parte dos
  alunos, para medir a diferença;
- **medir abertura e clique** significa **rastrear** o aluno, o que colide com a
  disciplina de privacidade que este projeto vem seguindo.

**Decisão dele, em 31/08/2026: medir o efeito, SEM grupo de controle e SEM
rastreio de abertura ou clique.** O sistema passa a saber se quem recebeu voltou
e fez aula — comportamento dentro da plataforma, que ela já observa —, e ninguém
deixa de receber ajuda para servir de régua.

---

## §3 — O que a consultoria NÃO mudou

- **A escada do §7 fica de pé.** As dez correções mexem no modelo de dados e na
  régua; a ordem de construção não muda. Foi a conclusão dos três.
- **O motor continua dentro da `mensageria`** (decisão dele, §8.2). Nenhum
  consultor a contestou; o Fable e o GPT trataram o acoplamento como dado e
  discutiram o isolamento interno, que é a pergunta certa.
- **O `order_id` sintético continua** — os três o elogiaram, e o Fable mostrou
  por que ele exige a trava parcial da §1.1 para continuar correto.

---

## §4 — A afirmação que NÃO sobreviveu à conferência

O Gemini, ao explicar por que não conseguiu ler o plano pelo link do GitHub,
afirmou que *"a interface web do GitHub carrega o conteúdo dos arquivos
dinamicamente via JavaScript"* e que por isso o texto não chegava a ele.

**Medido: falso.** O texto **está** no HTML estático da página — a palavra
`jornadas` aparece 14 vezes nele. Ele apenas não conseguiu extrair; tanto que o
GPT leu o mesmo endereço sem dificuldade.

Fica registrado porque é o exemplo dentro da própria consultoria: **um
consultor pode estar certo no veredito e errado na causa.** Repassar a causa sem
conferir teria posto uma explicação falsa dentro de um documento de arquitetura.
