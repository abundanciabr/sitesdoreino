(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-092-aviso-mede-idade-do-espelho",
  tipo: "entrega",
  quando: "2026-08-30",
  titulo: "A pasta principal agora avisa quando o manual que ela entrega aos robôs está velho",
  detalhe: "Quando um robô começa a trabalhar, ele recebe automaticamente o manual de instruções que está guardado na pasta principal do projeto no seu computador. O problema: essa pasta é um espelho, e espelho não se atualiza sozinho. Hoje ela estava 358 atualizações atrás do projeto de verdade.\n\nO manual velho de lá ainda mandava o robô escolher um número à mão numa hora em que a regra nova manda pedir o número ao sistema. Um robô obedeceu ao manual que recebeu, escolheu o número, esbarrou num número que outro robô já tinha usado e foi reprovado. Ninguém errou: a instrução é que estava velha, e o robô não tinha como saber disso.\n\nO que entrou: o aviso que já aparecia ao abrir uma sessão nessa pasta agora MEDE o quanto ela está atrasada e diz em voz alta, com o número, quando o manual que o robô recebeu pode estar revogado — junto com o comando de conferir o texto atual.\n\nO cuidado que definiu o trabalho: esse aviso aparece em TODA sessão. Aviso que fala à toa é aviso que se aprende a ignorar (foi essa doença que outro robô curou hoje no sininho). Então ele fica calado quando a pasta está em dia, e não grita 'suas ordens estão revogadas' quando o atraso não encostou no manual — ele compara o manual antes de falar. E quando não consegue medir, ele diz que não mediu, em vez de calar como se estivesse tudo bem.\n\nUma coisa que ele NÃO faz de propósito: atualizar a pasta sozinho. Ela é compartilhada e pode ter trabalho de outra sessão dentro. Atualizar continua sendo decisão de quem está na frente do computador.",
  autoridade: "github",
  evidencia: "PR #658 — https://github.com/abundanciabr/sitesdoreino/pull/658 · vermelho→verde por asserção e sem rede, com espelhos montados à mão: 5 testes vermelhos ANTES do conserto (todos morrendo em assert, nenhum na construção — armadilhas/195), e as três saídas cruas DEPOIS coladas no PR: espelho em dia = calou (nenhum parágrafo de idade) · 358 atrás com o CLAUDE.md mexido = 'IDADE DO ESPELHO: 358 commits atrás de origin/main [...] pode estar REVOGADA' · sem origin/main no cache = 'IDADE DO ESPELHO: NÃO MEDIDA [...] Não medir não é estar em dia (INV-CI01)'. A guarda anti-barulho foi falsificada por mutação (commits == 0 virou == -1): ficou vermelha acusando o aviso gritando '0 commits atrás'. Suíte: 43 na muralha, 1345 em ci/tests.",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
