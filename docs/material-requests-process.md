# Processo de Solicitacao de Materiais (Etapa 1)

## Objetivo
Definir regras de negocio e fluxo para solicitacao de materiais antes da implementacao tecnica.

## Atores
- `solicitante`: funcionario que monta e envia a solicitacao.
- `chefe_secao`: responsavel por aprovar/rejeitar solicitacoes da sua secao.
- `almoxarifado`: equipe que atende solicitacoes aprovadas e gera saida de materiais.

## Estados da Solicitacao
- `rascunho`: solicitacao em edicao, ainda nao enviada.
- `enviada`: aguardando decisao do chefe da secao.
- `aprovada`: autorizada para atendimento pelo almoxarifado.
- `rejeitada`: negada pelo chefe, com motivo obrigatorio.
- `atendida`: convertida em saida de materiais no almoxarifado.
- `cancelada`: cancelada pelo solicitante antes de atendimento.

## Fluxo Principal
1. Solicitante cria rascunho e adiciona itens consultando materiais disponiveis.
2. Solicitante envia para aprovacao.
3. Chefe da secao aprova ou rejeita.
4. Se aprovada, almoxarifado atende e registra a saida.
5. Solicitação passa para atendida e fica auditavel.

## Regras de Negocio (MVP)
- Uma solicitacao deve ter pelo menos 1 item.
- Quantidade de item deve ser maior que zero.
- Nao permitir material duplicado na mesma solicitacao.
- Apenas solicitacoes `enviada` podem ser aprovadas/rejeitadas.
- Apenas o `chefe_secao` do solicitante pode aprovar/rejeitar.
- Rejeicao exige motivo.
- Solicitacao `aprovada` nao pode voltar para `rascunho`.
- Solicitacao `atendida` nao pode ser editada/cancelada.
- O atendimento deve gerar um vinculo com a saida de materiais ja existente no sistema.

## Permissoes Basicas
- Solicitante:
  - cria/edita/cancela apenas suas solicitacoes em `rascunho` ou `enviada` (cancelamento).
  - visualiza historico das suas solicitacoes.
- Chefe de secao:
  - visualiza solicitacoes `enviada` da secao.
  - aprova/rejeita solicitacoes da secao.
- Almoxarifado:
  - visualiza solicitacoes `aprovada`.
  - atende solicitacao e gera saida.

## Auditoria Minima
- registrar `created_at`, `updated_at`, `created_by`, `updated_by`.
- registrar `submitted_at`, `approved_at`, `approved_by`, `rejected_at`, `rejected_by`, `rejection_reason`.
- manter historico de mudancas de status.

## Escopo da Proxima Etapa
Etapa 2: modelagem de dados (`MaterialRequest`, `MaterialRequestItem`, status, campos de aprovacao e vinculo com saida).
