# O prompt da consultoria de gamificação

Colado pelo mantenedor em 6 IAs em 30/08/2026. A **versão 2 (corrigida)** é a
que valeu: a versão 1 descrevia a escola errado ("ensina a criar jogos") e foi
corrigida pelo mantenedor antes do envio — a Meshcraft ensina MODELAGEM 3D
para Roblox (UGC), do Blender ao primeiro dólar.

---

## Versão 2 — a enviada às IAs

```
Você é consultor(a) sênior de design de gamificação. Preciso do seu melhor
parecer para a gamificação completa de uma escola online.

O PRODUTO: Meshcraft Academy (meshcraft.top) — escola brasileira, 100% em
português, que ensina crianças e adolescentes a ganharem seus primeiros
dólares como MODELADORES 3D para Roblox. O curso principal, "Primeiros Dólares
no Roblox", vai do Blender do zero até o primeiro cliente: modelagem 3D dos
itens que mais vendem (cabelos, acessórios, roupas, armas, carros),
texturização, rigging, exportação para o Roblox Studio, portfólio, como
encontrar clientes (Fiverr, grupos, oferta), loja UGC (renda passiva: publica
uma vez e continua vendendo) e como receber em dólar. Há bônus de animação,
comunidade de alunos (onde um pode contratar o outro para projetos) e mentoria
com o professor. Está em desenvolvimento a formação profissional "Profissão de
Modelador 3D Roblox". A escola NÃO ensina criação de jogos (esse tipo de curso
virá no futuro). Acabou de inaugurar. Hoje, no site, o aluno pode: participar
do fórum da escola (perguntar, responder, mostrar suas criações — professores
podem marcar uma resposta como "aceita"), completar quizzes, enviar ideias na
Caixa de Sugestões e votar nas dos colegas, e entrar todo dia para acompanhar.
Em breve terá trilhas de aulas estruturadas (o sistema já nasce com a tomada
pronta para "aula concluída" dar XP também).

O QUE VAMOS CONSTRUIR (decisões já tomadas — critique se discordar, mas
proponha em cima delas): sistema completo estilo Duolingo — XP e níveis com
títulos ("Aprendiz de Modelador" → "Modelador Profissional"), ofensiva/streak
diária com escudo protetor, ligas semanais com promoção e rebaixamento
(proteções para criança: grupos de ~15, só apelido/primeiro nome, sem expor
quem está mal, direito de sair do ranking), missões diárias e semanais,
medalhas/conquistas (inclusive secretas, a medalha de Fundador da primeira
turma, e medalhas de MARCO REAL de carreira validadas por professor: Primeiro
Modelo Publicado, Portfólio no Ar, Primeiro Cliente, Primeira Venda na Loja
UGC, Primeiro Dólar Recebido), moeda virtual "Cristais"
APENAS ganhável — nada é comprável com dinheiro real, restrição inegociável —
para itens cosméticos de perfil (títulos, molduras, temas), celebrações
visuais de subida de nível, itens sazonais de disponibilidade limitada.

Base teórica: Octalysis Framework (Yu-kai Chou) — queremos os 8 núcleos
cobertos, com chapéu branco (significado épico, realização, criatividade)
dominante e chapéu preto (escassez, perda) em dose mínima, por ser público
infantil. O XP mais alto fica onde há validação humana (resposta aceita por
professor, ideia implementada) — não em volume de atividade.

RESTRIÇÕES TÉCNICAS (contexto, não precisa resolver): microsserviços
orientados a eventos; a gamificação é um serviço separado que consome eventos
das outras partes e nunca lê banco alheio; toda pontuação é calculada no
servidor; tetos diários anti-farm por tipo de atividade.

O QUE EU QUERO DE VOCÊ:
1. As 10–20 recomendações mais valiosas para este sistema — numeradas,
   autossuficientes, cada uma com: o quê, por quê (qual núcleo do Octalysis
   serve), e prioridade P0/P1/P2.
2. O que o Duolingo faz que NÃO devemos copiar (e por quê).
3. O que os melhores jogos (o próprio Roblox, Fortnite, Zelda, Mario, WoW…)
   fazem de gamificação que caberia numa escola — em especial mecânicas que
   celebram CRIAÇÃO e OBRA, já que nossos alunos criam e vendem modelos 3D.
4. Riscos psicológicos e éticos com crianças: efeito de sobrejustificação
   (recompensa externa matando a motivação natural de aprender), ansiedade de
   streak, comparação social — e como mitigar cada um no desenho.
5. Anti-fraude: como alunos tentarão "farmar" XP e as defesas clássicas.
6. Vocabulário em português para crianças: melhore ou valide nossos nomes
   (XP, Nível, Ofensiva, Escudo de Ofensiva, Missões, Medalhas, Ligas
   Bronze/Prata/Ouro/Diamante, Cristais, Títulos).
7. As 5 métricas que dirão se a gamificação está funcionando — e o sinal de
   alerta de quando ela estiver fazendo MAL.
8. Uma lista explícita de "NÃO FAÇA" — os erros clássicos de gamificação de
   escolas que matam o produto.
9. Nosso diferencial: os alunos têm MARCOS REAIS de carreira (primeiro modelo
   publicado, portfólio no ar, primeiro cliente, primeira venda, primeiro
   dólar). Como celebrar isso dentro do sistema do melhor jeito — validação,
   vitrine, recompensa — sem constranger quem ainda não chegou lá?

Formato: seções numeradas conforme acima; recomendações curtas e acionáveis;
sem código. Se alguma premissa minha estiver errada, diga diretamente.
```

---

## Versão 1 — descartada (premissa errada, guardada por honestidade)

Diferia da versão 2 em um ponto central: descrevia a escola como *"que ensina
crianças e adolescentes a criarem seus próprios jogos no Roblox"*, com títulos
"Explorador → Mestre Criador" e a pergunta 3 pedindo mecânicas que celebram
criação "já que nossos alunos criam jogos". O mantenedor corrigiu antes do
envio; nenhum consultor recebeu a versão 1. Fica registrada porque a correção
mudou o coração do desenho: os marcos reais de carreira (modelo publicado →
portfólio → cliente → venda → dólar) só existem na versão corrigida.
