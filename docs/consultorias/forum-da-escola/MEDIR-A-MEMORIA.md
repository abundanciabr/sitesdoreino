# Medir o fôlego do servidor — o que o painel da Hostinger ainda não conta

> **Atualizado em 28/08/2026.** O painel do provedor já respondeu a maior parte
> da pergunta original, e a resposta corrigiu o projeto: **a máquina é o plano
> KVM 1 — 1 núcleo de processador, 4 GB de memória, 50 GB de disco, 4 TB de
> tráfego.** Não são 2 GB, como estava escrito aqui. Estado medido no painel:
> **processador 50%**, **memória 35%**, disco 12 de 50 GB, tráfego quase zerado.
>
> Isso já mudou a conclusão sobre o Discourse: **memória sobra; processador é
> que é escasso** — 50% de um único núcleo, sem fórum nenhum instalado.

**Então por que este arquivo continua aqui?** Porque o painel mostra o retrato de
fora, e três coisas só se veem por dentro:

1. **Quanto cada um dos 24 contêineres consome.** "35% de memória" não diz se são
   24 programas comportados ou um devorando tudo. Se um estiver fora da curva,
   isso é achado de manutenção, não de fórum.
2. **Se existe memória de emergência em disco (swap) configurada.** Muda
   completamente o que acontece quando a máquina aperta: com ela, fica lenta;
   sem ela, o sistema mata um programa no meio.
3. **A memória realmente disponível**, que não é a mesma coisa que "não usada" —
   o Linux empresta memória ociosa para acelerar disco e devolve quando alguém
   precisa. O painel não separa as duas.

Continua valendo a pena, e continua sendo uma colada só. Mas **não é mais
urgente**: já dá para consultar as outras IAs sem ele.

---

## ONDE COLAR — leia esta parte antes

Este comando é para colar **DENTRO DO SERVIDOR**, não no seu PC.

Como saber onde você está, pelo começo da linha:

| O que aparece na frente da linha | Onde você está |
|---|---|
| `PS C:\>` ou `C:\Users\davia>` | No seu **PC**. ❌ **Não é aqui.** |
| `deploy@srv...` ou `root@srv...` | Já está **DENTRO do servidor**. ✅ É aqui. |

Se ainda não estiver dentro do servidor, entre primeiro (o passo de sempre) e
só então cole o bloco abaixo.

## O que vai acontecer

- O comando **só lê** — não instala, não apaga, não reinicia nada. É seguro.
- Se ele perceber que foi colado na janela errada, ele **para sozinho** e avisa,
  em vez de mostrar número errado.
- A parte que mede os contêineres demora **uns 10 a 20 segundos** e fica
  aparentemente parada nesse tempo. É normal — espere.
- No fim ele imprime um resumo. **Copie tudo o que aparecer, do começo ao fim,
  e me mande.**

## O bloco — copie inteiro, de uma vez

```bash
medir_folego_da_maquina() {
  echo "== MEDIÇÃO DE FÔLEGO DA MÁQUINA =="
  if [ ! -d /opt/plataforma ]; then
    echo "PAROU POR SEGURANÇA: não encontrei a pasta /opt/plataforma."
    echo "Isto quase sempre quer dizer que este bloco foi colado no PC, e não"
    echo "dentro do servidor. Confira o começo da linha: precisa ser deploy@srv"
    echo "ou root@srv. Nenhum número foi medido, nada foi alterado."
    return 1
  fi
  if ! command -v docker >/dev/null 2>&1; then
    echo "PAROU POR SEGURANÇA: o comando docker não existe nesta janela."
    echo "Estou no servidor certo? Nenhum número foi medido."
    return 1
  fi
  if ! docker ps >/dev/null 2>&1; then
    echo "PAROU POR SEGURANÇA: o docker existe mas recusou responder."
    echo "Copie esta mensagem inteira e mande para o robô. Nada foi alterado."
    return 1
  fi
  echo
  echo "-- 1. Memória da máquina (em MB) --"
  free -m
  echo
  echo "-- 2. Quantos contêineres estão rodando --"
  docker ps -q | wc -l
  echo
  echo "-- 3. Quanto cada contêiner está usando (leva uns 15 segundos) --"
  docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'
  echo
  echo "-- 4. Carga do processador (a fila de quem espera vez no núcleo) --"
  echo "núcleos disponíveis: $(nproc)"
  uptime
  echo
  echo "-- 5. Espaço em disco --"
  df -h / | tail -n 2
  echo
  echo "-- 6. Resumo em uma linha --"
  free -m | awk '/^Mem:/ {printf "Total: %s MB | Em uso: %s MB | Disponível de verdade: %s MB\n", $2, $3, $7}'
  free -m | awk '/^Swap:/ {printf "Swap (memória de emergência em disco): total %s MB, em uso %s MB\n", $2, $3}'
  echo
  echo "== FIM DA MEDIÇÃO — copie tudo acima e mande para o robô =="
}
medir_folego_da_maquina
```

## Como o robô vai ler isso

Agora que já sabemos o tamanho da máquina pelo painel, o que o robô procura na
saída é outra coisa — são três perguntas:

| O que olhar | O que ela responde |
|---|---|
| A **"Disponível de verdade"** do resumo (a coluna `available` do Linux) | Memória que o sistema entrega a um programa novo **agora**, já descontando o que dá para liberar. É diferente de "não usada": o Linux empresta memória ociosa para acelerar o disco e devolve quando alguém precisa |
| A linha do **swap** | Se existe memória de emergência em disco. **Com ela**, a máquina apertada fica lenta; **sem ela**, o sistema mata um programa no meio, sem avisar. Se vier `0`, isso vira uma tarefa própria — vale ligar mesmo sem fórum nenhum |
| A **carga** do item 4, comparada com o número de núcleos | É a fila de quem espera vez no processador. Com **1 núcleo**, carga acima de `1,00` significa que já tem programa esperando. É o número que decide se o Discourse precisa da máquina maior |

E a lista do item 3, ordenada de olho: se um contêiner sozinho estiver muito
fora da curva dos outros, isso é achado de manutenção — vale consertar
independente de fórum.

O disco (item 5) entra de brinde porque o "mostre seu trabalho" do fórum — aluno
postando print, modelo e vídeo — é a coisa mais capaz de encher disco neste
projeto, e é melhor saber a folga antes de prometer anexos.
