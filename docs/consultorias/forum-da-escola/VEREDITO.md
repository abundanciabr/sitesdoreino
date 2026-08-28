# VEREDITO — o fórum da escola

**Fechado em 28/08/2026**, com dois pareceres externos (`resposta-consultor-1.txt`
e `resposta-consultor-2.txt`, nesta pasta) e uma exigência do mantenedor que
apareceu durante a análise e acabou decidindo mais que os dois consultores
juntos.

---

## A decisão, em uma frase

**Construir o fórum na casa, como célula `services/forum`, em `meshcraft.top/forum`.**
Nenhum fórum de prateleira entra — e o motivo principal não é técnico, é um
requisito do dono.

---

## O que decidiu: o login único

Durante a análise o mantenedor disse o que quer, com todas as letras:

> *"Eu quero que o usuário já esteja logado uma única vez e possa acessar o site
> todo em qualquer parte sem necessidade de qualquer tipo de login. Assim como,
> uma vez logado no Facebook eu posso usar o Marketplace, o Messenger..."*

**Isso já existe e já funciona.** O crachá da sessão vale no site inteiro —
`SESSION_COOKIE_PATH = "/"`, com o comentário do próprio código explicando:
*"alcance de CAMINHO (um host, todas as páginas)"*. Três células já consomem
isso hoje: `funil`, `sugestoes` e `admin`.

**Uma célula construída na casa herda esse login de graça.** Um fórum de fora,
não: ele não sabe ler o crachá e pediria um segundo login — exatamente o que o
mantenedor não quer. A única forma de evitar isso seria construir uma ponte de
login padrão de mercado, e **em 28/08/2026 ele descartou essa ponte de vez**.

Isso, sozinho, elimina o Misago — cuja única via de integração documentada é
justamente OAuth2, a ponte descartada.

**E gera um requisito duro, confirmado por ele na mesma conversa:** o fórum mora
em `meshcraft.top/forum` — **caminho, nunca subdomínio**. O cookie é de host: em
`forum.meshcraft.top` ele não viaja, e o login único quebra.

---

## Onde os dois consultores concordaram

Eles discordam de quase tudo no *como*, mas convergem em cinco pontos — e a
convergência de dois analistas independentes vale mais que a preferência de
qualquer um deles:

1. **O `django-machina` não se escolhe como está.** O consultor 1 o considera
   morto; o 2 o aceita só mediante prova de compatibilidade. **Nenhum dos dois o
   recomenda.** Conferido na fonte: última versão estável **1.3.1, de 17/10/2023**;
   o ramo principal está em `1.3.2.dev` e aceita Django 5 pelo instalador
   (`django = "^3.2 || >=4.0"`), mas **nada em lugar nenhum declara suporte a
   Django 5** e os classificadores param no Python 3.11. A plataforma roda
   Django 5.1.4.
2. **O Misago está vivo** (0.39.6, atualizada em 18/08/2026) — **o mapa desta
   pasta o subestimou, e os dois corrigiram isso.**
3. **O Discourse não deve dividir a máquina atual.** A formulação certa é do
   consultor 2: não é *"não serve para a arquitetura"*, é *"não deve compartilhar
   este KVM 1"*.
4. **O fórum é célula com contrato próprio, e o motor tem que ser trocável por
   baixo.** O resto da plataforma nunca deve depender diretamente de um motor.
5. **Modelo de dados no formato normal de fórum** — área → tópico → mensagem —
   para a escolha continuar reversível.

## Onde eles brigaram

| | Consultor 1 | Consultor 2 |
|---|---|---|
| O que fazer agora | Decidir já: construir na casa | Não decidir: três provas curtas com critério de morte |
| O que mata o Discourse | A atualização pelo terminal | Isso é exagero — o que mata é o processador |
| Construir na casa | Mais barato do que o mapa dizia | Risco de reinventar o Discourse aos poucos |

**Sobre o Discourse eles convergem mais do que parece:** o consultor 2 admite que
o terminal continua necessário *"como saída de emergência e em atualizações de
infraestrutura"* — que **é** o argumento do consultor 1, na sua forma mais dura:
o dia ruim (fórum fora do ar, aluno reclamando) só se resolve de dentro da
máquina, e ninguém aqui entra lá.

---

## Por que cada candidato caiu

| Candidato | Por que não |
|---|---|
| **Misago** | Precisa de OAuth2 — exatamente a ponte de login que o mantenedor descartou em 28/08. Também traz painel administrativo e noção de usuário próprios: a escola ficaria com dois painéis e duas ideias de quem é aluno |
| **django-machina** | Sem versão estável desde outubro de 2023 e sem nenhuma declaração de suporte a Django 5. Os dois consultores o recusam. A "busca inclusa" que o justificava nem é dele — vem do `django-haystack` |
| **Discourse** | Um núcleo de processador já a 50%; o resgate no dia ruim exige entrar no servidor; segunda linguagem dentro de casa; e risco de segundo login sem uma ponte feita à mão. **Não cai por memória — nisso o mapa estava errado, e o mantenedor tinha razão** |
| **Flarum, NodeBB, phpBB, Vanilla, Lemmy, XenForo** | Já descartados no mapa, sem contestação de nenhum consultor |

---

## As sete condições que a construção carrega

Não são enfeite: cinco vieram dos consultores, duas do próprio projeto. Quem for
construir precisa tratá-las como parte do escopo.

1. **Endereço por caminho** — `meshcraft.top/forum`. Subdomínio quebra o login
   único. Requisito do dono, confirmado por ele em 28/08/2026.
2. **Modelo de dados no formato normal** (área → tópico → mensagem). É o seguro
   que mantém a porta do Discourse aberta para o dia em que a escola crescer:
   migrar é caminho batido, com ferramenta de importação pronta. Só vira porta de
   mão única se inventarmos um formato esquisito.
3. **A marca de leitura feita certo** — uma marca por pessoa por área ("li até
   aqui") mais uma pequena tabela de exceções, que é como o Discourse faz.
   **Nunca uma linha por pessoa por mensagem**: com 200 alunos e 20 mil mensagens
   isso fabrica milhões de linhas para responder uma pergunta boba, e a lista de
   tópicos fica lenta. Foi o achado mais afiado da rodada.
4. **Busca do PostgreSQL em português desde o primeiro dia**, em coluna indexada —
   nunca calculada na hora da consulta. É o único item caro de instalar depois:
   vira migração na maior tabela do sistema.
5. **Anexos com lista branca** de tipos e limite de tamanho, servidos sem deixar
   ninguém subir coisa executável. O "mostre seu trabalho" é a parte mais exposta.
6. **Moderação em volume**: fila de aprovação, mover, juntar duplicatas, dividir
   conversa, trancar, fixar, apagar sem perder histórico.
7. **Critérios de morte** (do consultor 2, e valem contra o entusiasmo): se a
   construção começar a recriar do zero um **motor de busca**, um **editor
   sofisticado**, **resposta por e-mail** ou um **framework de reputação**, pare —
   a partir dali estaríamos reinventando o Discourse, e mal.

---

## O que a rodada NÃO respondeu

Honestidade sobre o buraco: **os dois consultores ignoraram duas das oito
perguntas** — e uma é justamente a que o mantenedor apontou como a que mais o
preocupa:

- **O salão vazio** — como um fórum sem ninguém não nasce morto. Silêncio total,
  dos dois.
- **Menores de idade, moderação e lei brasileira.** Nenhum tocou.

**Não é falha deles: é falha do prompt.** A seção de arquitetura é tão densa que
consumiu a resposta inteira. Isso pede **uma rodada própria, só sobre comunidade
e segurança de menores**, antes de o fórum abrir ao público — não antes de
começar a construir.

**Também ficou em aberto um detalhe do produto:** nas áreas públicas, quem
escreve? Só aluno, ou também quem tem cadastro sem ter comprado? O consultor 1
supôs "fórum fechado" e por isso concluiu que anti-spam é custo imaginário — o
que só vale se ninguém de fora escrever.

---

## Duas correções que a rodada fez neste projeto

Ficam registradas porque custaram, e porque a próxima sessão precisa saber:

1. **O mapa desta pasta recomendou o `django-machina` marcando "é preciso
   conferir se está vivo" — e recomendou antes de conferir.** Estava errado. A
   recomendação foi corrigida neste mesmo PR.
2. **O consultor 2 propôs colocar papel e matrícula dentro do login** como
   informação assinada. **Isso viola a lei escrita da célula de identidade** —
   *"reconhecer não é autorizar"*, *"não use `papel` como autorização"*. Quem sabe
   se alguém é aluno é a célula `alunos`; quem sabe se é administrador é a
   `admin`. A identidade só reconhece. O prompt não dizia isso, e por isso o
   consultor tropeçou.

E uma alfinetada justa do consultor 1, que vale além do fórum: **"um passo seu no
servidor" já apareceu quatro vezes.** Cinco vezes não é exceção, é rotina não
automatizada — criar o banco de uma célula nova deveria ser coisa que a esteira
faz sozinha.

---

## O que falta para começar

**A palavra do mantenedor reabrindo o congelamento arquitetural.** Célula nova só
nasce assim — foi assim nas quatro anteriores (sugestões, identidade,
notificações, admin). Depois disso a escada já é conhecida: gênese da célula com
botão de desfazer → contrato → o passo dele no servidor → a configuração de rede
sozinha numa entrega própria → o site linkando o fórum.
