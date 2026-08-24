# Rota nova no Traefik reprova `test_rotas_sem_forma_de_locale` com "Extra items in the left set"

**Sintoma:** você acrescenta um router a `infra/traefik/dynamic/plataforma.yml` —
um PR que não toca célula nenhuma — e o `muralhas` fica vermelho num teste de
`ci/tests/` que parece não ter nada a ver com a sua mudança:

```
FAILED ci/tests/test_rotas_sem_forma_de_locale.py::test_os_prefixos_de_hoje_sao_os_que_este_guarda_julgou
    assert segmentos == {"", "quiz", "checkout", "alunos", "api"}
E   AssertionError: assert {'', 'alunos'...orms', 'quiz'} == {'', 'alunos'...kout', 'quiz'}
E     Extra items in the left set:
E     'forms'
```

**Causa:** `test_os_prefixos_de_hoje_sao_os_que_este_guarda_julgou` é um
**inventário por igualdade exata** dos primeiros segmentos de todos os
`PathPrefix` reais. Ele não julga se a rota é boa — quem faz isso são os dois
testes vizinhos (regra A: o segmento tem forma de locale? regra B: colide com
idioma declarado em `infra/sites.json`?). O inventário existe para amarrar a prova
adversarial às rotas reais e para **obrigar quem acrescenta rota a passar por
aqui** e olhar as duas regras. Falhar é o comportamento pretendido dele.

Note a assimetria que localiza o diagnóstico: se só o inventário está vermelho e os
outros dois testes estão verdes, a sua rota **passou** nas regras de verdade.

**Solução:** acrescente o segmento novo ao conjunto (e o nome do router ao
subconjunto de nomes logo acima), e acrescente o prefixo à parametrização de
`test_aprova_os_prefixos_legitimos_de_hoje` — assim a rota nova entra na prova, em
vez de só sair do caminho dela.

**O que NUNCA fazer aqui**, porque é a leitura tentadora e errada do vermelho:
trocar o `==` por `<=`, apagar a asserção, ou pôr o segmento em
`RESERVADOS_DE_MAQUINA`. As duas primeiras matam o único mecanismo que força a
revisão; a terceira isenta o segmento da **regra A**, que é justamente a que pega
uma rota `/pt` ou `/ao` nascendo. Atualizar um inventário não é afrouxar um teste
(RITOS §2.3) — trocar o operador de comparação é.

**Se o vermelho for `matcher(s) [...] que este guarda não sabe julgar`**, é outro
assunto: o guarda é fail-closed de instrumentação e reprova matcher desconhecido
em vez de ignorá-lo. A mensagem já diz o caminho (ensinar o guarda, ou usar
`PathPrefix`).

**Origem:** despacho EVO-22 (infra/sugestoes-na-vps), 24/08/2026 — ao acrescentar
`PathPrefix(/forms/sugestoes)` para a Caixa de Sugestões, a primeira rota de
plataforma com dois segmentos.
