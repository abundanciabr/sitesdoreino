# Motor determinístico e nascimento independente

ChangeSpec aprovado: `https://meshcraft.top/admin/documentos/revisor-modelos-3d-changespec-20261014`.

Rota pretendida: `https://meshcraft.top/ferramentas/revisor-de-modelos-3d/`.
Ordem mais recente: nasce acessível a alunos; não criar prévia administrativa.
Até liberação expressa do endereço, não acrescentar a menus, categoria, avisos
ou mensagens para alunos. Documentos administrativos continuam privados.

## Escolha inicial

Trimesh é adequado a métricas trianguladas, mas seu conjunto de formatos não
oferece sozinho o importador FBX exigido: `https://trimesh.org/formats.html`.
A leitura OBJ triangula polígonos: `https://github.com/mikedh/trimesh/blob/main/trimesh/exchange/obj.py`.
O GLB não preserva topologia autoral: `https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html`.

O ensaio de 14/10 encontrou uma face duplicada que o importador GLB do Blender
removeu silenciosamente. Usar leitor GLB próprio para medir posições/índices
antes de qualquer limpeza e Blender headless para FBX, ambos em isolamento.
O núcleo de medições é determinístico e compartilhado pelos dois adaptadores.
Não carregar bpy no Django. Isso preserva a evidência do GLB; não prova que o
importador FBX preserva todos os defeitos. Ainda não é aprovação do runtime.

O extrator é testável com o Blender instalado neste PC, versão 3.6.23; esta
versão histórica não é a referência de produção. A imagem Linux e a versão
suportada de Blender precisam ser fixadas e comprovadas na VPS antes de uso.
O pacote bpy é pesado e depende da versão exata de Python; preferir binário
headless com Python empacotado até essa prova operacional.

## Cobertura explícita

Medir orientação geométrica e componentes fechados. Normais fornecidas podem
ser alteradas pelo importador: não certificá-las ainda. Sem escala declarada
da importação para Studio não inferir studs. Sem orientação de attachment não
certificar dimensões de acessório rígido. Rig/cages estão fora desta lista.
Essas ausências deixam a cobertura incompleta, nunca aprovação total.

O catálogo pedagógico, aulas e os quinze erros continuam pendentes da Lívia.
Nenhuma aprovação dela foi simulada. A narrativa por IA está especificada na
API, mas não está implementada nesta primeira entrega de motor/contrato.
Ela terá limites próprios e não poderá alterar achados ou valores medidos.

## Escada e condição atual

Esta entrega prepara motor, contrato e ensaios; não instala rota, banco,
pares de identidade ou rede. O degrau seguinte reservado ao dono é autorizar
banco próprio `revisor`, com role própria sem permissões em bancos alheios.
Depois, autorização da rede em entrega própria. A divulgação do link é outro
ato explícito; a falta dessa divulgação não vira allowlist de alunos/admins.

Nenhum arquivo congelado do Mercado Pago será modificado. Não integrar esta
célula ao registry da aplicação compartilhada nem reutilizar credenciais de
outros consumidores. O instalador/rollback concretos dependerão da topologia
autorizada; não apresentar um script preparado como instalação concluída.
