# Passo a passo — Publicação completa

Runbook para colocar a solução no ar. Ordem sugerida: AWS → Function →
SharePoint → Power Automate → Power App → testes → compartilhamento.

---

## 0. Pré-requisitos

| Item | Onde conseguir |
|------|----------------|
| Licença Power Apps / Power Automate (com conector premium HTTP) | admin do tenant M365 |
| Site SharePoint (ou permissão para criar listas em um existente) | SharePoint Admin |
| Time/canal no Teams de destino | Teams |
| Assinatura Azure para a Function (Consumption basta) | portal.azure.com |
| Acesso AWS para criar usuário + roles | console.aws.amazon.com |
| Ferramentas locais: Azure Functions Core Tools, Azure CLI, PnP PowerShell | `winget`/`brew`/pip |

---

## 1. AWS — preparar acesso de leitura

1. **Ative o Cost Explorer** em cada conta: *Cost Management → Cost Explorer → Enable*.
   > Pode levar ~24h para popular dados na primeira ativação.
2. **Crie o usuário da Function** na conta de monitoramento:
   - *IAM → Users → Create user* → `power-automate-costs` → Access key.
   - Anexe a política de `function-app/iam-policy.json` (bloco principal).
3. **Em cada conta-alvo**, crie a role `PowerAutomateCostReader`:
   - Política: `ce:GetCostAndUsage` (ver `iam-policy.json` → `TargetAccountRolePolicy`).
   - Trust: principal = ARN do usuário do passo 2; opcionalmente `ExternalId`.
   - Anote o `RoleArn` de cada conta.

**Critério de pronto:** `aws ce get-cost-and-uso` via `sts assume-role` retorna dados.

---

## 2. Azure Function — publicar o proxy

```bash
cd function-app
az login
az group create -n rg-custos-aws -l brazilsouth
az functionapp create \
  -n func-custos-aws-<sufixo> \
  -g rg-custos-aws \
  --consumption-plan-location brazilsouth \
  --runtime python --runtime-version 3.11 \
  --functions-version 4 \
  --storage-account <storage>
```

Configure as credenciais (nunca no código):

```bash
az functionapp config appsettings set \
  -n func-custos-aws-<sufixo> -g rg-custos-aws \
  --settings AWS_ACCESS_KEY_ID=AKIA... AWS_SECRET_ACCESS_KEY=... \
             AWS_DEFAULT_REGION=us-east-1 USD_BRL_RATE=5.00
```

Publique e teste:

```bash
func azure functionapp publish func-custos-aws-<sufixo>
curl -X POST "https://func-custos-aws-<sufixo>.azurewebsites.net/api/top-costs?code=<key>" \
  -H "Content-Type: application/json" \
  -d '{"roleArn":"arn:aws:iam::<id>:role/PowerAutomateCostReader","accountName":"Prod","topN":10}'
```

**Esperado:** JSON com `items[]` (até 10), `totalCost`, `totalCostBrl`, `fx.usdBrl`.
Guarde a URL + `code` — vai no fluxo.

> Dica: restrinja a Function por IP ou mude para `authLevel` mais forte se o
> tráfego permitir; a `function key` é o mínimo.

---

## 3. SharePoint — listas e cadastro

```powershell
./sharepoint/criar-listas.ps1 -SiteUrl "https://<tenant>.sharepoint.com/sites/<site>"
```

Ou crie manualmente conforme `sharepoint/LISTAS.md`.

Cadastre cada conta em **ContasAWS**:

| Campo | Exemplo |
|-------|---------|
| Title | `Prod-BR` |
| AccountId | `123456789012` |
| RoleArn | `arn:aws:iam::123456789012:role/PowerAutomateCostReader` |
| Dono | pessoa do AAD (recebe a @menção) |
| LimiteItemUSD | `20` (US$/dia por serviço) |
| CrescimentoMaxPct | `30` |
| TeamId / ChannelId | vazio = grupo padrão do fluxo |
| Ativo | Sim |

> Pegar IDs do Teams: abra o canal no Teams → ⋯ → *Obter link para o canal* —
> o link contém `groupId=<TeamId>` e `threadId/<ChannelId>`.

---

## 4. Power Automate — fluxo agendado (9h)

Siga `power-automate/GUIA-FLUXOS.md` — resumo:

1. [make.powerautomate.com](https://make.powerautomate.com) → **Meus fluxos → Novo fluxo → Fluxo de nuvem agendado**.
2. Nome `CustosAWS-EnvioAgendado`; recorrência **1 dia, 09:00, fuso Brasília**.
3. **Obter itens** (SharePoint) → lista `ContasAWS`, filtro `Ativo eq 1`.
4. **Aplicar a cada** → **HTTP** POST para a Function → **Filtrar matriz**
   (alertas) → **Selecionar** (linhas) → variáveis → condição:
   - Sim → **Obter token de @menção** (Teams) + **Postar cartão adaptável**
     (corpo = `adaptive-cards/relatorio-custos.json`)
   - Não → postar `adaptive-cards/parabens.json`
5. **Criar item** em `RelatoriosCustos`.
6. Salvar → **Testar → Manualmente** e confira o card no Teams.

## 5. Power Automate — fluxo manual (botão do app)

1. **Novo fluxo → Fluxo de nuvem instantâneo → PowerApps (V2)**.
2. Entrada `itemId` (número).
3. **Obter item** (`ContasAWS`) → **HTTP** → opcionalmente a mesma lógica de postagem →
   **Responder a um PowerApp** com `body('Chamar_Function_AWS')`.
4. Salvar — ele aparecerá como fonte de dados no Studio.

---

## 6. Power App — montar e publicar

1. [make.powerapps.com](https://make.powerapps.com) → **Criar → Aplicativo de tela → em branco** (formato tablet).
2. Nomeie `Custos AWS → Teams`.
3. **Dados → Adicionar dados**: `ContasAWS`, `RelatoriosCustos` (SharePoint) e
   o fluxo `CustosAWSEnvioManual` (aba Power Automate).
4. Crie as 3 telas conforme `power-apps/src/*.yaml` + `power-apps/POWER-APP.md`:
   - `scrDashboard` (KPIs + contas + histórico)
   - `scrContas` (galeria + formulário CRUD)
   - `scrRelatorio` (dropdown conta + botão + galeria top 10)
5. **App → OnStart**: cole a fórmula de `src/App.yaml`.
6. **Salvar** (Ctrl+S) → **Publicar** → *Publicar esta versão*.
7. **Compartilhar**: botão *Compartilhar* → adicione usuários/grupos do AAD
   (donos de conta = *Usuário*; administradores = *Coproprietário*).
   Garanta permissão no SharePoint: leitura para usuários em
   `RelatoriosCustos` e `ContasAWS` (escrita só para admins).

---

## 7. Validação ponta a ponta

- [ ] `curl` na Function retorna `items` + `costBrl` + `fx.usdBrl`
- [ ] Fluxo agendado (Teste manual) posta card no canal certo
- [ ] Item acima do limite gera card ⚠️ **com @menção** ao dono
- [ ] Conta sem alerta gera card 🎉
- [ ] Item criado em `RelatoriosCustos` com `Status` correto
- [ ] App abre, KPIs carregam, "Enviar agora" preenche a galeria
- [ ] Às 09:00 do dia seguinte chega relatório automático

## 8. Troubleshooting rápido

| Sintoma | Causa provável |
|---------|----------------|
| Function 502 `AccessDenied` | trust da role ou `ce:` na política |
| `items` vazio | Cost Explorer não ativado / conta nova sem custo |
| Card não menciona | `Dono` vazio ou e-mail não resolve no AAD |
| Fluxo falha no filtro | nome interno da coluna diferente (veja Lista → Configurações → coluna) |
| `costBrl` zerado | `fx.source=fallback` — AwesomeAPI bloqueada; ajuste `USD_BRL_RATE` |
