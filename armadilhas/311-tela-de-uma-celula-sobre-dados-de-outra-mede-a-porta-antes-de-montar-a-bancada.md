---
schema_version: 2
armadilha: 311
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: o que falta é uma LEITURA no primeiro minuto do despacho, e ela não tem onde ser cobrada mecanicamente; os portões que existem (mapa_de_celulas, contract_freeze, cerca-de-celula) só falam depois que alguém escreveu código, que é justamente tarde demais. Enquanto isso, o gesto de quatro comandos abaixo custa trinta segundos e responde
sinal:
  - "célula ainda em esqueleto"
  - "declara consumir"
  - "e não há sinal disso"
---

# Tela de uma célula sobre dados de outra: meça a porta ANTES de montar a bancada

**Sintoma.** O despacho manda construir uma tela (no `admin`, quase sempre) que
mostra dados que vivem em outra célula. Você cria o worktree, pega a tarefa no
balcão, lê o plano, abre o `models.py` da provedora para saber o que a tela vai
ler, e só então descobre que **não existe caminho nenhum entre as duas
células**: o `config/urls.py` da provedora tem uma rota só, `/healthz`, não há
`contracts/<provedora>.openapi.yaml`, e o `consome:` da consumidora em
`celulas.yml` não a cita.

Nada ficou vermelho. Nenhum portão reclamou. A tarefa simplesmente não tem como
ser feita, e a descoberta chega depois da bancada montada e da tarefa travada no
seu nome.

**Causa.** A escada de PRs do plano põe o degrau do motor numa célula e o degrau
da tela em outra, **sem um degrau de PORTA explícito entre os dois**. Para quem
escreve o plano isso parece detalhe de implementação da tela. Não é: a porta é
três trabalhos que o agente da tela não pode fazer, e dois deles nem são de
robô.

1. `config/api.py` + `export_openapi` + os testes de 401, dentro da célula
   provedora, que costuma estar fora do escopo do despacho da tela.
2. O contrato, que é Rito (RITOS §3): PR separado, etiqueta `contrato`, e
   sessão com o mantenedor presente. A cerca (`ci/cerca-de-celula.sh`) recusa
   `contracts/` mudando junto com `services/`, então nem juntando os dois PRs
   se escapa.
3. As variáveis de ambiente do par (`<PROVEDORA>_API_URL` e o Bearer dos dois
   lados) na VPS, que são da Lei 5 e só o mantenedor põe.

E o caminho de baixo, "então leio o banco dela", **não existe nem como
gambiarra**: cada célula tem papel próprio no Postgres, e o `admin_user` recebe
`permission denied` no banco alheio (Lei 3, pecado 2, imposto pelo banco e não
por regra escrita).

**Solução.** No PRIMEIRO minuto do despacho, antes do `worktree add`, quatro
comandos contra a `origin/main` (nunca contra o clone principal, que envelhece
em silêncio: `armadilhas/148`):

```bash
git show origin/main:services/<provedora>/config/urls.py     # 1. tem porta?
git ls-tree --name-only origin/main contracts/               # 2. tem contrato?
git show origin/main:celulas.yml | grep -A2 "^  <consumidora>:"   # 3. declara o consumo?
python -c "import json;print(json.load(open('ci/manifesto-de-contratos.json'))['celulas']['<provedora>'])"
```

O quarto costuma responder sozinho: o `reason` do manifesto é escrito à mão e
diz, em português, se a célula ainda é esqueleto. Faltando qualquer um dos
quatro, **a tarefa está bloqueada por um degrau que ninguém construiu** e o
conserto é enfileirar a porta (`ci/fila.py criar`), escrever o evento
`bloqueada` e devolver, nunca atravessar a cerca.

**E a ordem entre porta e contrato importa:** porta primeiro, contrato depois.
Contrato em disco obriga a linha do manifesto a virar `required`, e `required`
sem `export_openapi` deixa o `make ci` da célula em ERROR no PR seguinte, longe
de quem causou (`armadilhas/228`).

**Para quem ESCREVE plano:** todo par de degraus vizinhos em células diferentes
ganha um degrau de porta explícito entre eles, com o Rito nomeado. Um plano que
não o escreve não está errado por opinião: ele agenda uma tarefa que vai parar.

**Origem:** TAR-078 (a tela `/admin/escola/jornadas/` das sequências de
mensagens), 04/09/2026. O `PLANO-SEQUENCIAS-DE-MENSAGENS.md` tinha os degraus 2
a 6 na `mensageria` e o degrau 7 na `admin`, sem nada entre eles; a correção
está no §7 do próprio plano, como degraus 6c e 6d. Parente de
`armadilhas/228` e `armadilhas/224` (a mesma família: **a célula nova exige
registro em lugares que o despacho dela não pode tocar**).
