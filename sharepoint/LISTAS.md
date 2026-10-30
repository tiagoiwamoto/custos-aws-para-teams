# Listas SharePoint

Duas listas em um site SharePoint do tenant. Rode `criar-listas.ps1` (PnP PowerShell)
ou crie manualmente conforme os schemas abaixo.

## 1. `ContasAWS` — configuração das contas monitoradas

| Coluna (interno)  | Tipo            | Obrigatório | Descrição |
|-------------------|-----------------|-------------|-----------|
| Title             | Texto (1 linha) | sim         | Nome amigável da conta (ex.: "Prod-BR") |
| AccountId         | Texto (1 linha) | sim         | ID de 12 dígitos da conta AWS |
| RoleArn           | Texto (1 linha) | sim         | `arn:aws:iam::<id>:role/PowerAutomateCostReader` |
| ExternalId        | Texto (1 linha) | não         | External ID do trust da role (se usado) |
| Dono              | Pessoa          | sim         | Dono da conta — recebe a @menção no Teams |
| LimiteItemUSD     | Número          | sim         | Limite por item de serviço **por dia** (US$) para flag de risco |
| CrescimentoMaxPct | Número          | sim         | % máximo de crescimento vs. o dia imediatamente anterior (ex.: 30) |
| HorarioEnvio      | Número (0–23)   | não         | Reservado — hoje o envio é diário às 09:00 para todas as contas |
| TeamId            | Texto (1 linha) | não         | ID do time no Teams (vazio = usa grupo padrão do fluxo) |
| ChannelId         | Texto (1 linha) | não         | ID do canal (vazio = canal padrão do fluxo) |
| Ativo             | Sim/Não         | sim         | Desligar sem excluir o cadastro |

> Envio **diário às 09:00 (Brasília)** com os dados do dia anterior (00:00–23:59),
> para todas as contas com `Ativo = Sim`. `HorarioEnvio` fica reservado caso se
> queira voltar a ter horários distintos por conta.

## 2. `RelatoriosCustos` — histórico dos envios

| Coluna (interno)  | Tipo            | Descrição |
|-------------------|-----------------|-----------|
| Title             | Texto (1 linha) | `<Conta> — <data>` |
| Conta             | Texto (1 linha) | Nome da conta |
| AccountId         | Texto (1 linha) | ID AWS |
| DataEnvio         | Data/Hora       | Quando o relatório foi postado |
| TotalUSD          | Número          | Custo total do dia anterior |
| TotalAnteriorUSD  | Número          | Custo do dia imediatamente anterior |
| ItensEmAlerta     | Número          | Quantidade de itens flagados |
| Status            | Escolha         | `Controlado` / `Atencao` / `Erro` |
| ResumoJson        | Texto (múltiplas linhas) | Payload retornado pela Function (auditoria) |

## Permissões

- Donos das contas: leitura em `RelatoriosCustos` (transparência).
- App/fluxo: leitura+escrita nas duas.
- A coluna `Dono` (Pessoa) precisa resolver no AAD — é dela que sai o e-mail
  para o token de @menção.
