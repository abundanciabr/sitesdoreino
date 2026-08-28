(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260828-043-a-consulta-sobre-o-forum-da-escola-esta-pronta",
  tipo: "pendencia",
  quando: "2026-08-28",
  titulo: "A consulta sobre o fórum da escola está pronta para você colar nas outras IAs — e falta medir a memória do servidor",
  detalhe: "Você perguntou como criar um fórum moderno para a escola, se existe algo pronto de instalar, e pediu um texto para consultar outras IAs. Está tudo em docs/consultorias/forum-da-escola/.\n\nA RESPOSTA CURTA, que você já tem sem esperar ninguém: existem três caminhos, não dois. Instalar um fórum pronto como programa separado (Discourse, NodeBB, Flarum, Misago); instalar um motor de fórum pronto DENTRO de uma parte do site que já existe; ou construir na casa. E \"construir\" aqui não é do zero: a Caixa de Sugestões já tem tópicos, comentários, votos, moderação e histórico inviolável funcionando — boa parte de um fórum já foi feita e testada.\n\nO QUE VOCÊ FAZ AGORA: abra o arquivo PROMPT-CONSULTORIA.md, copie tudo o que está abaixo da linha, e cole numa conversa nova de cada IA que quiser ouvir. Salve cada resposta na mesma pasta como resposta-GPT.txt, resposta-Gemini.txt, e assim por diante. Depois é só pedir a um robô: leia as respostas e me diga o veredito.\n\nO QUE FALTA E SÓ VOCÊ PODE FAZER: medir a memória do servidor. Você disse que o Discourse cabe nos nossos 2 GB porque temos poucos usuários. A leitura não é absurda, mas há um detalhe que muda a conta: esses 2 GB são o total da máquina, e ela já roda 24 programas — as 12 partes do site, o roteador, o banco de dados, a fila e mais 9 auxiliares. Os números que se lê sobre o Discourse são para uma máquina dedicada só a ele. Ninguém nunca mediu quanto sobra livre na nossa.\n\nO arquivo MEDIR-A-MEMORIA.md tem um bloco único para você colar DENTRO do servidor (a janela onde a linha começa com deploy@srv). Ele só lê, não instala nem apaga nada, e para sozinho se for colado na janela errada. Copie a saída inteira e me mande.\n\nCom esse número, \"cabe Discourse?\" deixa de ser opinião — nem minha nem sua. A pergunta também foi feita nominalmente às outras IAs, com os fatos na mesa e a instrução de defender o Discourse se ele for defensável.\n\nQuatro coisas você já decidiu e elas entraram na consulta como dadas: o fórum é misto (áreas abertas ao público e áreas trancadas por turma), o papel de professor nasce junto com o fórum, não existe comunidade nenhuma hoje (o fórum nasce em salão vazio, e isso é problema de desenho), e escopo completo, nunca a versão reduzida.\n\nNada do fórum foi construído, de propósito: fórum é uma parte nova do sistema, e parte nova exige a sua palavra para nascer — foi assim nas quatro anteriores.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/382",
  verificado_em: null,
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "info",
  frente: "comunidade",
  vence_em_dias: null,

  se_eu_nao_decidir: "A consulta fica parada na pasta sem ninguém responder, e o fórum não sai do lugar. A parte mais barata de resolver é a medição da memória: sem ela, qualquer recomendação sobre o Discourse continua sendo chute — o meu contra o seu.",
  recomendacao: "Faça a medição da memória primeiro, porque é rápida e é o que trava a discussão do Discourse. Depois cole o prompt em duas ou três IAs diferentes — o valor vem justamente de elas discordarem entre si. Minha aposta, aberta a ser derrubada pela consulta, é o caminho do meio: motor de fórum pronto instalado dentro de uma parte nova do site, que não gasta memória que não temos e se atualiza sozinho pela esteira, sem você entrar no servidor.",
  reversivel: true,
  impacto: "alto"
});})();
