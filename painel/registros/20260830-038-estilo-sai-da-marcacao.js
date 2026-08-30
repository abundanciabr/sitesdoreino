(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-038-estilo-sai-da-marcacao",
  tipo: "entrega",
  quando: "2026-08-30",
  titulo: "Os últimos 39 retoques que não chegavam à sua tela agora chegam",
  detalhe: "Fecha a ponta solta que sobrou do conserto do estilo de hoje de manhã.\n\nO que era: dentro das telas da administração havia 39 ajustes finos de espaçamento e cor escritos direto na marcação de cada página, em vez de na folha de estilo. Pela regra de segurança do site, ajuste escrito assim é recusado pelo navegador — então nenhum deles chegava até você. As páginas tinham desenho, mas com margens erradas em uns pontos e uma barrinha sem largura em outro.\n\nO que fiz: cada ajuste virou uma regra na folha, com o MESMO valor de antes. Nada foi arredondado nem uniformizado — houve a tentação de juntar sete espaçamentos quase iguais em três, mas isso seria mudar o desenho, e eu só mudei de lugar onde a regra mora.\n\nUm caso era diferente: a barrinha que mostra quantas pessoas esperam por uma ideia tinha a largura calculada na hora. Ela passou a usar passos de 10%. A precisão fina não faz falta ali, porque o número exato está escrito ao lado — e hoje ela estava pior do que isso: sem largura nenhuma.\n\nE ficou uma trava: se algum robô escrever um ajuste na marcação de novo, o teste reprova antes de a mudança entrar, explicando por que aquilo não chegaria à sua tela. Sem a trava, a regra voltaria a se perder — foi assim que 39 se acumularam sem ninguém notar.",
  autoridade: "github",
  evidencia: "PR #595 (https://github.com/abundanciabr/sitesdoreino/pull/595), completando o #579. Vermelho->verde: com os templates de antes, os 3 guardas novos reprovam; com a troca, 375 testes verdes na célula inteira e black limpo. Contagem medida antes: 39 atributos style= em 15 templates; depois: zero.",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "site",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
