# Registros históricos do placar

Os arquivos `.js` desta pasta são o acervo original. A migração `0041_placar_persistente` copia cada registro para o banco, preserva seu texto original e usa o identificador `arquivo` para impedir importação duplicada.

O painel lê e edita exclusivamente a cópia no banco em `/admin/placar/editar/`. Alterar ou acrescentar arquivos aqui não altera o site em execução. Medições, compromissos e decisões novos são criados no formulário do painel; registros existentes podem ser corrigidos ali.

Os campos `responde_a`, `foto`, `portao`, `evidencia` e `verificado_em` continuam disponíveis às leituras de direção, histórico, laboratório e fechamento.
