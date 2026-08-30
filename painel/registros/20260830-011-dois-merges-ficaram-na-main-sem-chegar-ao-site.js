(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-011-dois-merges-ficaram-na-main-sem-chegar-ao-site",
  tipo: "incidente",
  quando: "2026-08-30",
  titulo: "Dois trabalhos prontos ficaram sem chegar ao site — e o robô ia fechar a tarefa achando que estava tudo certo",
  detalhe: "Ao publicar a sua decisão sobre a aba \"Os robôs\", a publicação foi CANCELADA. Fui conferir e o problema era maior do que a minha entrega: a última publicação bem-sucedida era de doze minutos antes, e DOIS trabalhos já aprovados estavam parados no meio do caminho — prontos no projeto, ausentes do site.\n\nO site nunca saiu do ar. Quando uma publicação falha, o servidor continua servindo a versão anterior; ninguém fica sem nada. O risco é outro e é pior: é silencioso. O robô mergeia, vê que o site responde, e vai embora achando que entregou.\n\nDuas causas diferentes se somaram na mesma janela. Uma foi a queda de rede entre o GitHub e o servidor, que já tem nome e remédio nesta casa. A outra é nova: o GitHub guarda UMA vaga de publicação pendente por vez, e quando outra chega, a que estava esperando é expulsa — sem erro, sem log, sem aviso. E a ferramenta que cuida disso aqui dizia, para esse caso, 'não há nada a fazer' — conselho certo para uma situação parecida, errado para esta.\n\nConsertei: conferi que republicar a minha versão não voltaria nada (ela já continha o outro trabalho parado e vinha depois do que estava no ar), republiquei, e as duas entregas subiram juntas. Publicação verde, site em 200, painel no ar com a sua decisão dentro.\n\nE a lição virou defesa em vez de história: entrou no catálogo de armadilhas como a 187, com a tabela que separa os três casos parecidos, e a correção da ferramenta virou a tarefa TAR-017 na fila. O buraco ficou DECLARADO — a regra desta casa é que buraco assumido é gerenciável, buraco silencioso não.\n\nNada aqui espera por você.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/562 — a armadilha 187 e a TAR-017 (`python ci/indice_de_armadilhas.py` PASS com 168 entradas; `python ci/fila.py validar` com 17 tarefas). O incidente em si, lido por --json e nunca por cano: run 33286390331 (deploy do PR 558) terminou 'cancelled'; run 33286302573 (deploy do PR 559) terminou 'failure' no `dial tcp ***:22: i/o timeout`; o último verde antes disso era o run 33285964121, de 01:33:58 UTC. Depois do rerun, o run 33286390331 terminou 'success' às 01:51. Prova de fora, medida em seguida: meshcraft.top/healthz e a raiz em 200, /admin/painel/ em 302 para o login. A porta 22 medida do PC durante a janela devolveu `SSH-2.0-OpenSSH_9.6p1 Ubuntu-3` — era queda passageira, não a armadilha 017.",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: null,

  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
