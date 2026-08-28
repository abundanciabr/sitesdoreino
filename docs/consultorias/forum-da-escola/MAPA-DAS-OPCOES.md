# Mapa das opções — como um fórum entraria neste site

> # ⚠️ ESTE ARQUIVO FOI SUPERADO — leia o `VEREDITO.md`
>
> **A recomendação deste mapa estava ERRADA, e a rodada de consultoria a
> derrubou em 28/08/2026.** Ele recomendava a Família B (`django-machina`)
> anotando que *"é preciso conferir se o projeto está vivo"* — **e recomendou
> antes de conferir.** Ao conferir: última versão estável de **outubro de 2023**,
> sem nenhuma declaração de suporte a Django 5, numa plataforma que roda Django
> 5.1.4. **Os dois consultores externos recusaram esse motor.**
>
> **O que ficou decidido está no [`VEREDITO.md`](VEREDITO.md): construir na casa,
> como célula `services/forum`, em `meshcraft.top/forum`.**
>
> Este arquivo fica como está — não se apaga o erro, registra-se. Ele continua
> útil pelo levantamento das opções e pelos descartes justificados; **só a
> recomendação final não vale.** Duas outras coisas nele também foram corrigidas
> pela rodada: o Misago está **vivo** (0.39.6, agosto de 2026) e foi subestimado
> aqui; e o argumento contra o Discourse estava mal calibrado — ele não cai por
> memória, cai por processador e por operação.
>
> ---
>
> **Para que serve este arquivo:** você perguntou "existe fórum pronto de
> instalar ou temos que criar do zero?". Esta era a resposta que a sessão tinha
> **antes** de as outras IAs responderem — para você não ficar esperando, e para
> os consultores terem algo concreto de que discordar. Nessa segunda função ele
> funcionou: os dois atacaram justamente a tese fraca dele.

## A pergunta por trás da pergunta

"Instalar pronto" e "criar do zero" parecem as duas únicas opções. Não são —
existe uma terceira, e é provavelmente a certa: **instalar um motor de fórum
pronto DENTRO de uma das nossas células**. Nem programa separado, nem código
escrito do nada.

E "do zero", aqui, é uma palavra enganosa: a Caixa de Sugestões já está no ar com
tópicos, votos, **comentários**, moderação, limite contra abuso, histórico
inviolável e avisos no sininho. Boa parte de um fórum já foi construída e
testada nesta casa.

## As três famílias

### Família A — fórum pronto, rodando ao lado, como programa separado

| Candidato | Tecnologia | Banco | O problema aqui |
|---|---|---|---|
| **Discourse** | Ruby on Rails | PostgreSQL ✔ | O melhor produto da lista. Mas a memória residente é grande **mesmo com 5 usuários**, e a forma normal de atualizá-lo é rodar o instalador dele **dentro do servidor** — e nenhum robô entra lá (Lei 5) |
| **NodeBB** | Node.js | PostgreSQL ✔ | Moderno e em tempo real. Login único exigiria transformar a nossa identidade num provedor OAuth2 inteiro — a maior ponte da lista |
| **Flarum** | PHP | **MySQL** ✘ | Leve e bonito, mas PostgreSQL não é suportado oficialmente. Quebra "um banco por célula, tudo em PostgreSQL" |
| **Misago** | **Python/Django** ✔ | PostgreSQL ✔ | Mesma tecnologia da casa — e por isso o mais simpático da família. Mas é um projeto inteiro (não uma peça encaixável), a comunidade é pequena e ele passou por uma reescrita longa |

**Descartados sem hesitar:** phpBB (visual e código datados), Vanilla (mesmo
problema do Flarum), XenForo (licença paga), Lemmy (federado — ótimo para rede
social aberta, sem sentido para uma escola com turmas fechadas), Zulip e
Mattermost (são **bate-papo**, não fórum: a conversa rola e some, que é
exatamente o que queremos evitar), Circle e Mighty Networks (mensalidade).

**O preço comum da família A**, em uma frase: você ganha um produto maduro de
graça e paga em **memória**, numa **segunda tecnologia dentro de casa** (alguém
precisa saber Ruby ou Node para consertar) e numa **ponte de login construída à
mão**, porque nenhum deles sabe conversar com o nosso login sozinho.

### Família B — motor de fórum instalado DENTRO de uma célula Django

O **`django-machina`** é uma biblioteca que se instala com um comando e já traz
fóruns, tópicos, respostas, permissões por grupo, moderação, anexos e busca.
Ela roda **no mesmo processo, no mesmo banco e na mesma esteira de publicação**
que todo o resto do site.

O que isso significa na prática:

- **Peso na máquina:** custa o mesmo que qualquer outra célula do site — nem
  memória nem processador a mais do que já é rotina aqui. **Não exige trocar de
  plano**, e essa é a diferença prática mais concreta para o seu bolso.
- **Atualizar:** pela esteira automática, como tudo aqui. Ninguém entra no
  servidor.
- **Login único:** é a menor ponte das três famílias. A célula precisa de um
  adaptador que pega o cookie, pergunta à identidade quem é a pessoa e espelha
  ela numa linha local. **Esse adaptador já existe e está em produção** — é o
  que a Caixa de Sugestões faz, em `services/sugestoes/apps/core/sessao.py`.
- **A ressalva honesta:** é preciso conferir se o projeto está sendo mantido
  ativamente antes de apostar nele. É a pergunta que eu mandei para os
  consultores.

### Família C — construir a célula `services/forum` na casa

Copiando o molde da Caixa de Sugestões. Controle total, encaixe perfeito com o
login, com as 5 categorias de pessoa e com o sininho. O preço é reconstruir
coisas que o mundo já resolveu bem: busca de qualidade, editor de texto,
anti-spam, resposta por e-mail.

## O que já está pronto e serve a qualquer caminho

Isto é o ativo do projeto, e vale mencionar porque muda a conta:

- **O login único do site já funciona** — cookie que vale no site inteiro, mais
  uma API interna contratada que responde "quem é o dono desta sessão", com
  e-mail para quem tem permissão extra.
- **As 5 categorias de pessoa são lei**, com uma porta única que responde se
  alguém é aluno.
- **O sininho de avisos** já existe e qualquer célula pode usar.
- **O molde de discussão** da Caixa de Sugestões, testado em produção.

E a armadilha que nenhum fórum de prateleira sabe: **a nossa identidade não é um
provedor de login padrão de mercado.** Não é OIDC, não é OAuth2, não é SAML. É
uma API interna caseira. Todo fórum de fora precisa de uma ponte feita à mão — e
o tamanho dessa ponte é o que separa o Discourse (ponte pequena, o mecanismo
DiscourseConnect é simples) do NodeBB (ponte grande, exigiria virar provedor
OAuth2 inteiro).

## Sobre o Discourse, com franqueza

**Corrigido em 28/08/2026 — e a correção é a seu favor.** Eu escrevi aqui que a
máquina tinha 2 GB no total. **Tem 4 GB**, e o painel da Hostinger confirmou:
plano KVM 1 — 1 núcleo de processador, 4 GB de memória, 50 GB de disco, 4 TB de
tráfego. Mais importante: **a memória está em 35% de uso**, ou seja, sobra folga
de verdade.

Então o argumento que eu usei contra o Discourse — *"não cabe por falta de
memória"* — **ficou bem mais fraco. Nessa parte você estava mais certo do que
eu**, e o registro fica.

**Mas a mesma tela mostrou um gargalo que nenhum de nós dois tinha olhado: o
processador.** O KVM 1 tem **um único núcleo**, e ele já está em **50% de uso
sustentado**, sem nenhum fórum instalado. O Discourse traz servidor web em Ruby
mais uma fila de tarefas em segundo plano, e os dois disputam processador — que
é justamente o recurso escasso aqui, não a memória.

E como você já disse que **sobe para o KVM 2 quando for necessário** (2 núcleos,
8 GB, 100 GB de disco), a pergunta deixou de ser *"cabe?"* e virou outra, melhor:
**"vale a pena pagar mais por mês para rodar o Discourse, comparado com uma
solução que roda no que já existe?"** É essa a pergunta que foi para a banca.

**O que dinheiro nenhum resolve:** a forma canônica de atualizar o Discourse é
rodar o instalador dele **dentro do servidor**. Nenhum robô entra lá — a única
via é a esteira automática. Trocar de plano não muda isso: manter o Discourse
seria tarefa recorrente **sua**, no terminal, para sempre. Este continua sendo o
argumento mais forte contra ele, e agora é o único que sobrou de pé.

> **Correção da rodada (28/08/2026):** este parágrafo está forte demais. O
> Discourse **tem** uma tela de atualização pelo navegador, e o dia a dia se
> resolve por ela. O que continua verdade — e é o que importa — é que o terminal
> segue necessário como **saída de emergência** e em atualizações de
> infraestrutura: quando a atualização pelo navegador falha, o fórum cai, e
> levantar de volta só se faz de dentro da máquina. Os dois consultores
> convergiram nisso. Detalhe em [`VEREDITO.md`](VEREDITO.md).

O disco, esse, está tranquilo: 12 GB usados de 50. Boa notícia para o "mostre seu
trabalho" do fórum, que é a parte mais capaz de encher disco.

## A minha recomendação, hoje — ❌ DERRUBADA PELA RODADA

> **Esta recomendação está ERRADA. Ela foi mantida aqui de propósito, para o erro
> ficar registrado em vez de apagado.** O que vale é o
> [`VEREDITO.md`](VEREDITO.md): **construir na casa (Família C)**, como célula
> `services/forum` em `meshcraft.top/forum`.
>
> **Por que caiu:** o `django-machina` não tem versão estável desde **outubro de
> 2023** e não declara suporte a Django 5 em lugar nenhum — e a plataforma roda
> Django 5.1.4. Os dois consultores externos o recusaram. Pior: a "busca
> inclusa" que era o principal argumento a favor dele **nem é dele** — vem do
> `django-haystack`, e teria que ser resolvida de qualquer jeito.
>
> **A lição, que é a parte cara:** este texto anotou *"é preciso conferir se o
> projeto está vivo"* — **e recomendou antes de conferir.** Marcar uma dúvida não
> substitui responder a dúvida.
>
> **E o fator que decidiu de verdade nem estava nesta análise:** o mantenedor quer
> um login só para o site inteiro, e uma célula da casa herda isso de graça —
> qualquer fórum de fora pediria um segundo login.

**Família B, dentro de uma célula nova `services/forum`** — motor pronto onde ele
resolve (fóruns, permissões, anexos, moderação), colado no que já temos (login,
categorias de pessoa, sininho), com a Família C como plano B se o motor não
estiver saudável. É o único caminho que entrega um fórum completo **sem** gastar
memória que não temos, **sem** trazer uma segunda tecnologia para dentro de casa
e **sem** depender de você entrar no servidor para atualizar.

Não é a versão reduzida de nada: é o caminho que sobra depois de respeitar as
leis do projeto, e ele comporta o escopo inteiro do "super fórum" — áreas mistas,
professor com autoridade, "mostre seu trabalho", busca, SEO, celular, três
idiomas.

**Esta recomendação está explicitamente aberta a ser derrubada pela rodada de
consultoria.** É para isso que ela existe.

## O que vem depois do veredito

Um fórum é **célula nova**, e célula nova neste projeto exige que você reabra
nominalmente o congelamento arquitetural — foi assim nas quatro anteriores
(sugestões, identidade, notificações, admin). Depois da sua palavra, a escada já
é conhecida e tem 5 degraus: nascimento da célula já com botão de desfazer →
contrato de API → **um passo seu no servidor** (criar o banco, uma linha só) →
a configuração de rede sozinha numa entrega própria → o site linkando o fórum.
