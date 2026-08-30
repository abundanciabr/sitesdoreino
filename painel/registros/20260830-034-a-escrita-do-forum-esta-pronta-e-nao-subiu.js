(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-034-a-escrita-do-forum-esta-pronta-e-nao-subiu",
  tipo: "incidente",
  quando: "2026-08-30",
  titulo: "A escrita do forum esta pronta, mas nao chegou ao site ainda",
  detalhe: "LEIA ISTO ANTES DE ABRIR O FORUM PARA CONFERIR. A escrita do forum ficou pronta e ja esta guardada no projeto — mas ela NAO chegou ao site. Se voce abrir meshcraft.top/forum agora, vai ver o forum de ontem, sem botao de escrever e com as areas ainda abertas ao mundo.\n\nPOR QUE NAO SUBIU, E NAO E CULPA DESTA ENTREGA. Hoje de manha, poucos minutos ANTES da minha entrega entrar, uma outra melhoria entrou no projeto e deixou a esteira de publicacao vermelha. Existe uma trava na casa que diz: com a esteira vermelha, NADA sobe para o servidor. A trava funcionou como devia — ela e o motivo de o site nunca ter ido ao ar quebrado. So que, enquanto ela estiver acesa, nenhuma entrega de ninguem publica, nem a minha.\n\nO QUE ISSO SIGNIFICA NA PRATICA: (1) a escrita do forum esta feita, conferida e guardada — nao ha trabalho a refazer; (2) o site continua exatamente como estava; (3) assim que a esteira voltar ao verde, a publicacao acontece sozinha, sem ninguem precisar refazer nada. Nem voce, nem eu.\n\nO QUE JA FOI FEITO SOBRE ISSO: o defeito esta identificado com precisao (foi um arquivo de apoio que deixou de viajar junto com o projeto e que ninguem passou a gerar na hora da conferencia), e a tarefa de conserto ja esta na fila de trabalho como TAR-025, com o diagnostico inteiro escrito dentro dela. Nao precisa de nada seu.\n\nUM DETALHE QUE VALE VIGIAR: o alarme automatico da casa, ao ver a esteira vermelha, tentou desfazer a entrega ERRADA — a minha, que so entrou depois e nao tem relacao com o defeito. Ele nao conseguiu (faltou permissao), entao nada foi desfeito. Mas isso quer dizer que o socorro automatico da casa nao esta funcionando de verdade hoje, e as duas coisas estao anotadas dentro da TAR-025.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/586 — o PR que traz este registro e a TAR-025. O deploy barrado: run 33311082333 (deploy-celula do commit 86a5f59, a escrita do forum) concluiu 'failure' no job portao-de-deploy, com a linha crua 'alarme-main FAIL run concluiu failure' e o job de deploy 'skipped'. A main ja estava vermelha ANTES: o alarme-main do commit caaeb2e8 (PR #580, mergeado as 12:13 UTC) concluiu 'failure', e o do commit anterior 1dfce1a4 concluiu 'success' — conferido por gh run list --workflow alarme-main.yml. A causa medida: ci/tests/test_guarda_declarada_e_sino.py estoura com JSONDecodeError porque armadilhas/SINAIS.json saiu do Git no PR #580 e nenhum workflow o gera (grep -rn 'indice_de_armadilhas' .github/ nao devolve nada). A tentativa de reversao do commit errado falhou com 'Permission to abundanciabr/sitesdoreino.git denied to github-actions[bot]', HTTP 403.",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: 2,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
