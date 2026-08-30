(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-122-o-processo-que-entrega-as-cartas-esta-no-ar",
  tipo: "entrega",
  quando: "2026-08-29",
  titulo: "O processo que entrega as cartas subiu, e o comando de ligar o aviso ficou pronto para voce",
  detalhe: "A ULTIMA PECA DE CODIGO do aviso de liberacao, e ela e a rede de seguranca.\n\nO QUE SUBIU: um processo auxiliar da parte que guarda os alunos, irmao identico do que a Caixa ja tinha. A carta e publicada NA HORA pelo proprio site quando voce libera alguem — e e isso que da a entrega em segundos. ESTE processo e o que republica o que aquele nao conseguiu: se a peca de mensagens estiver fora do ar no instante exato da liberacao, a carta ficaria pendente para sempre, e a promessa falharia em silencio justamente no caso raro em que mais importa.\n\nVEIO JUNTO o script que voce rodou logo depois — o de uma linha que liga as senhas dos dois lados —, e os dois arquivos de exemplo passaram a documentar as chaves novas, dizendo em ambos que a ausencia delas e um caminho NORMAL: sem elas a liberacao acontece do mesmo jeito e so o aviso nao sai.\n\nO deploy da infraestrutura terminou verde, e a plataforma foi conferida de fora logo depois.",
  autoridade: "github",
  evidencia: "PR #531, mergeado em 29/08/2026. Conferido antes do merge: `bash -n` no script de provisionamento (sintaxe OK), o docker-compose parseia e declara os tres servicos da alunos (alunos, alunos-consumer, alunos-relay), e ci/ci.py --apenas muralhas PASS nos 9. Depois do merge: o run do deploy-infra terminou 'success' (conferido por ci/esperar.py --run, nunca pelo exit de um pipe), e a medicao de fora deu GET meshcraft.top = 200, /forms/sugestoes/entrar = 200, /admin/healthz = 200, e /alunos/api/alunos/pre-matriculas sem credencial = 401. TOCOU infra/ (CODEOWNERS), anunciado nominalmente ao mantenedor no relatorio.",
  verificado_em: "2026-08-29",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "curso",
  vence_em_dias: null
});})();
