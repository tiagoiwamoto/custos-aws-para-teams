# Custos AWS → Teams (Power Platform)

Solução em **Microsoft Power Apps + Power Automate** que:

- coleta os **10 maiores gastos** (por serviço) de cada conta AWS cadastrada,
  referentes ao **dia anterior (00:00–23:59)**, com **conversão USD→BRL**
  (AwesomeAPI; fallback via `USD_BRL_RATE`);
- envia o relatório para um **grupo/canal do Teams todos os dias às 09:00**;
- **@menciona o dono da conta** quando algum item tem potencial de gasto elevado
  (acima do limite diário em US$ ou crescimento percentual vs. o dia anterior);
- **parabeniza** no card quando os gastos se mantêm controlados.

## Arquitetura

```mermaid
flowchart LR
    subgraph PowerPlatform["Power Platform"]
        PA[Power App<br/>Admin + Dashboard] -->|botão "Enviar agora"| F2[Fluxo manual<br/>CustosAWSEnvioManual]
        F1[Fluxo agendado<br/>diário 09:00] --> TEAMS[(Canal/Grupo Teams)]
        F2 --> TEAMS
        F1 --> SP[(SharePoint<br/>ContasAWS · RelatoriosCustos)]
        PA --> SP
    end
    F1 -->|HTTPS + function key| FN
    F2 -->|HTTPS + function key| FN
    subgraph Azure["Azure"]
        FN[Function App<br/>GetTopAwsCosts]
    end
    subgraph AWS["AWS"]
        FN -->|sts:AssumeRole| R1[Role PowerAutomateCostReader<br/>conta A]
        FN -->|sts:AssumeRole| R2[Role ...<br/>conta B]
        R1 --> CE[Cost Explorer<br/>GetCostAndUsage]
        R2 --> CE
    end
```

**Por que a Azure Function?** O conector HTTP do Power Automate não assina
requisições AWS SigV4. A Function recebe o `RoleArn` da conta-alvo, assume a
role e consulta o Cost Explorer — as credenciais AWS ficam fora do fluxo.

## Estrutura do repositório

```
docs/
  PUBLICACAO.md      runbook completo de publicação (passo a passo)
function-app/        Azure Function Python (proxy Cost Explorer)
  function_app.py    endpoint POST /api/top-costs → top N serviços do dia
                     anterior (USD + BRL) + delta vs. anteontem
  iam-policy.json    políticas e trust policy para configurar na AWS
sharepoint/          schema das listas + script PnP de criação
power-automate/
  GUIA-FLUXOS.md     passo a passo para montar os 2 fluxos
  definitions/       mesma lógica em JSON (referência / import Logic Apps)
  adaptive-cards/    cards do relatório (alerta) e de parabéns
power-apps/
  POWER-APP.md       guia de montagem do canvas app
  src/               telas em YAML com todas as fórmulas
```

## Setup passo a passo

> **Runbook detalhado com critérios de pronto e troubleshooting:**
> [`docs/PUBLICACAO.md`](docs/PUBLICACAO.md)

### 1. AWS — roles de leitura
Em **cada conta-alvo**, crie a role `PowerAutomateCostReader` com permissão
`ce:GetCostAndUsage` e trust apontando para o usuário/role da Function
(exemplos prontos em `function-app/iam-policy.json`). Ative o Cost Explorer
nas contas.

### 2. Azure Function
```bash
cd function-app
func init . --python   # se ainda não inicializado (modelo v2 já está no código)
func azure functionapp publish <function-app>
```
Configure `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` e `AWS_DEFAULT_REGION`
nas Application Settings (usuário AWS com `sts:AssumeRole`). Teste:

```bash
curl -X POST "https://<function-app>.azurewebsites.net/api/top-costs?code=<key>" \
  -H "Content-Type: application/json" \
  -d '{"roleArn":"arn:aws:iam::<id>:role/PowerAutomateCostReader","accountName":"Prod","topN":10}'
```

### 3. SharePoint
Rode `sharepoint/criar-listas.ps1` ou crie as listas `ContasAWS` e
`RelatoriosCustos` conforme `sharepoint/LISTAS.md`. Cadastre as contas.

### 4. Power Automate
Monte os dois fluxos seguindo `power-automate/GUIA-FLUXOS.md`
(agendado diário às 9h + manual para o botão do app). Cole os cards de
`power-automate/adaptive-cards/`.

### 5. Power App
Crie o canvas app conforme `power-apps/POWER-APP.md` com as telas/fórmulas
de `power-apps/src/`.

## Regras de negócio

| Situação | Critério | Resultado no Teams |
|----------|----------|--------------------|
| Alerta | `item.cost > LimiteItemUSD` **ou** `deltaPct > CrescimentoMaxPct` | Card ⚠️ com itens + **@menção ao dono** |
| Controlado | nenhum item flagado | Card 🎉 de parabéns |

- Envio **diário às 09:00** (fuso Brasília) para todas as contas com `Ativo = Sim`.
- Período: **dia anterior completo (00:00–23:59)** vs. o dia imediatamente
  anterior (delta % por serviço). Limiares (`LimiteItemUSD`) são valores/dia.
- Canal por conta: `TeamId`/`ChannelId` na lista; vazio = grupo padrão do fluxo.
- Para horários diferentes por conta no futuro: `HorarioEnvio` está reservado
  — basta trocar o gatilho para horário e filtrar `HorarioEnvio eq <hora>`.

## Licenças necessárias

- Power Apps/Power Automate com conectores padrão (SharePoint, Teams, HTTP).
  HTTP para endpoint próprio é conector **premium** — alternativa: registrar a
  Function como **custom connector** (também premium) ou usar Logic Apps.
- Azure Function em plano Consumption ≈ custo zero nesse volume.
