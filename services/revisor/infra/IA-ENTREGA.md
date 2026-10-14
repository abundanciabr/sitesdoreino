# Conexão autorizada em 14/10/2026

Provedor OpenAI, modelo `gpt-6-luna`, `POST https://api.openai.com/v1/responses`,
`store: false`, esforço `none`, sem ferramentas. Por orientação posterior do
mantenedor, reutiliza o executor e cofre da Super Equipe já usados pela Trilha.
O Revisor chama somente o contrato HTTP próprio; não importa outra célula,
não recebe a chave OpenAI e não lê o banco administrativo. O provedor registra
o consumo em seu próprio banco, com origem `revisor`, sob o teto existente.

O gateway continua sem acesso externo: encaminha uma única operação para a
aplicação, na porta e IP já permitidos. Autenticação por par, remetente de rede
conferido e campos fechados. Nenhum arquivo, imagem, nome livre ou identidade
de aluno é enviado. `ai_client.py` prepara os campos do boletim; o provedor
revalida os dados. Até quinze verificações são explicadas; o total omitido é
explícito e o boletim completo continua determinístico. A lista de quinze erros
prioritários, tom e aulas da Lívia continuam pendentes; nenhuma aula é inventada.

Limites: corpo final de até 5.000 bytes UTF-8 mais margem de enquadramento para
o orçamento conservador de 6.000 tokens; saída máxima 2.000 tokens. Esta versão
faz uma tentativa, sem retry automático. Reserva US$ 0,001750 antes da chamada.
Ao responder, usa o consumo informado pela API e estima conservadoramente
US$ 0,125/milhão de entrada e US$ 0,50/milhão de saída, sem desconto de cache.
Isso é estimativa com tokens medidos, não fatura do provedor. Falhas preservam
o boletim; a integração final das telas e quota diária pertence ao worker.

Preço consultado: `https://developers.openai.com/api/docs/models/gpt-6-luna`.
Retenção: `https://developers.openai.com/api/docs/guides/your-data`.
`store: false` não equivale a retenção zero. Mantida ciência do mantenedor.

Operação: entregar pela esteira existente, preparar backup/configuração com
`deploy_ai.py prepare`, recarregar o provedor pela esteira e ativar com
`deploy_ai.py activate`. O preparo é retomável por registro persistente; não
repete rotação. `prove_ai.py` usa três exemplos sintéticos, registra tokens,
estimativa e isolamento; na falha fecha a operação de IA, sem restaurar banco.
O caminho HTTP do produto e sua divulgação não são criados por esta entrega.
Nenhuma alteração em pagamentos, execução compartilhada ou dependências.

Estado ao preparar este documento: testes locais, instalação ainda pendente.
O mantenedor determinou execução exclusivamente por SSH; não usar console.
O canal restrito consultado ainda não expõe preparação/ativação desta conexão.
Não declarar chamada real ou custo medido antes da prova na VPS.
