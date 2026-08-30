(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-040-a-sonda-nova-deu-um-diagnostico-categorico-e-errado",
  tipo: "incidente",
  quando: "2026-08-30",
  titulo: "A pecinha que nasceu hoje para salvar publicacoes deu um diagnostico errado — e do tipo que faz desistir",
  detalhe: "UM ROBO PEGOU O ERRO DE OUTRO ROBO, NO MESMO DIA, SEM TER NADA A VER COM ELE. Vale contar porque foi assim que o problema apareceu.\n\nO QUE NASCEU HOJE: a publicacao do site cai com alguma frequencia por soluco de rede — e a licao dizia, ha dias, para MEDIR se o servidor esta vivo antes de repetir. Essa medicao nunca tinha sido construida: ela morava so no texto da licao. Hoje virou peca de verdade, e ela sabe dar tres respostas: 'servidor vivo, foi solucinho, repita' · 'servidor morto, e defeito de configuracao, nao adianta repetir' · 'nao consegui medir'.\n\nO QUE DEU ERRADO: horas depois, um robo diferente estava publicando outra coisa. A publicacao falhou, e a peca nova respondeu a SEGUNDA das tres: falha permanente, nao adianta repetir. Esse robo nao acreditou. Ele mediu o servidor do proprio computador, no MESMO minuto, e o servidor respondeu na hora. Estava vivo. Ele repetiu a publicacao e ela subiu em pouco mais de um minuto.\n\nPOR QUE ISSO E SERIO, e nao um detalhe. Das tres respostas, 'falha permanente' e a UNICA que manda o sistema DESISTIR. Um diagnostico desses, quando errado, transforma a peca no oposto do que ela existe para fazer: em vez de salvar uma entrega de um solucinho, ela abandona uma entrega que teria subido na tentativa seguinte. E a mensagem e CATEGORICA — ela nao diz 'talvez', diz 'e permanente'. Um robo (ou uma pessoa) que ler isso vai acreditar e parar.\n\nESTE PROJETO JA TEM NOME PARA O PRIMO DISSO: o falso-verde, quando o sistema diz que deu certo sem ter dado. Este e o irmao: o falso-vermelho CATEGORICO. E pior de um jeito, porque parece diagnostico em vez de duvida.\n\nO QUE EU FIZ: abri a tarefa TAR-026 com a ordem de descobrir a causa medindo (sem escolher a hipotese favorita antes), e com uma regra escrita dentro: 'falha permanente' passa a exigir mais de UMA medicao concordando, e na duvida a resposta certa e 'nao consegui medir' — que deixa o sistema continuar tentando. O raciocinio e de custo: repetir a toa custa 45 segundos; desistir a toa custa uma entrega que nunca chega ao site, em silencio.\n\nNADA DISSO DERRUBOU O SITE, e a publicacao daquele robo subiu normalmente depois. O que ficou foi uma peca nova com a regua torta, achada no primeiro dia — que e o melhor momento possivel para achar.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/598 — este PR, com a TAR-026 e este registro. MEDIDO em 30/08/2026 pelo robo da TAR-023, durante o deploy do PR 589 (celula admin): ci/sonda_da_vps.py devolveu o veredito 'permanente' (o que cita a armadilhas/017) enquanto a porta 22 da VPS, sondada do PC na MESMA janela, devolveu o banner 'SSH-2.0-OpenSSH_9.6p1'. O 'gh run rerun --failed' subiu em 1min02s, confirmando que era a armadilhas/127 (intermitente) e nao a 017 (permanente). A peca havia entrado no ar horas antes, pelo PR 584 (TAR-013), com run real de prova (33311814021).",
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
