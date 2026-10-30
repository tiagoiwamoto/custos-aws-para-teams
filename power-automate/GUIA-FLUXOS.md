# Guia — Fluxos no Power Automate

Dois fluxos. O agendado dispara **todos os dias às 09:00 (Brasília)** e envia,
para cada conta ativa, o relatório com os dados do **dia anterior (00:00–23:59)**.
O manual é chamado pelo botão **Enviar agora** do Power App e usa o mesmo período.

> Os arquivos em `definitions/` são o mesmo fluxo no formato de definição
> (Logic Apps WDL) — úteis como referência ou para importação em Azure Logic
> Apps. No Power Automate, monte pelos passos abaixo (~15 min).

---

## Fluxo 1 — `CustosAWS-EnvioAgendado`

### 1. Gatilho
**Recorrência** — Intervalo `1`, Frequência `Dia`, Fuso `(UTC-03:00) Brasília`,
em `Às estas horas` = `9` e `Às estes minutos` = `00`.

### 2. `Obter_contas_ativas` — Obter itens (SharePoint)
- Site: o site das listas · Lista: `ContasAWS`
- Filtro OData: `Ativo eq 1`

### 3. Loop — `Para_cada_conta` (Aplicar a cada)
Sobre `value` da ação anterior. Dentro do loop:

#### 3.1 `Chamar_Function_AWS` — HTTP
- Método `POST`, URI `https://<function-app>.azurewebsites.net/api/top-costs?code=<function-key>`
- Corpo:
  ```json
  {
    "roleArn": "@{items('Para_cada_conta')?['RoleArn']}",
    "externalId": "@{items('Para_cada_conta')?['ExternalId']}",
    "accountName": "@{items('Para_cada_conta')?['Title']}",
    "topN": 10
  }
  ```

#### 3.2 `Filtrar_itens_em_alerta` — Filtrar matriz
- De: `body('Chamar_Function_AWS')?['items']`
- Condição (modo avançado):
  ```
  @or(greater(item()?['cost'], items('Para_cada_conta')?['LimiteItemUSD']), greater(coalesce(item()?['deltaPct'], 0), items('Para_cada_conta')?['CrescimentoMaxPct']))
  ```

#### 3.3 `Select_linhas` — Selecionar
- De: `body('Chamar_Function_AWS')?['items']`
- Mapear conforme `adaptive-cards/modelo-linha.json` (um `ColumnSet` por serviço)

#### 3.4 `varLinhasItens` — Inicializar/definir variável (string→JSON)
```
json(concat('[', join(body('Select_linhas'), ','), ']'))
```

#### 3.5 `varTextoAlertas` — Selecionar + join
- De: `body('Filtrar_itens_em_alerta')` → texto `concat('• ', item()?['service'], ...)`
- Depois `join(... , '\n')` para texto multi-linha.

#### 3.6 `Se_houver_alertas` — Condição
`length(body('Filtrar_itens_em_alerta'))` é maior que `0`

- **Se SIM:**
  1. `Token_mencao_dono` — ação **Obter um token de @menção para um usuário**
     (conector Teams), Usuário = `items('Para_cada_conta')?['Dono']?['Email']`
  2. **Postar cartão adaptável em um chat ou canal** — Postar como *Flow bot*,
     em *Canal*, Time/Canal = `TeamId`/`ChannelId` do item (ou padrão do grupo),
     Cartão adaptável = conteúdo de `adaptive-cards/relatorio-custos.json`.
     O token de menção entra no campo de texto indicado — isso gera a @menção
     real no Teams.
- **Se NÃO:** postar `adaptive-cards/parabens.json` no mesmo canal.

#### 3.7 `Registrar_relatorio` — Criar item (SharePoint)
Lista `RelatoriosCustos` com os campos do passo `Registrar_relatorio` na
definição (`TotalUSD`, `ItensEmAlerta`, `Status` = `Atencao`/`Controlado`, etc.).

---

## Fluxo 2 — `CustosAWS-EnvioManual` (botão do app)

1. Gatilho **PowerApps (V2)** — entrada `itemId` (número).
2. **Obter item** (SharePoint, lista `ContasAWS`) com `itemId`.
3. **HTTP** → mesma chamada da Function (passo 3.1, usando o item obtido).
4. **Condição** de alerta + mesma lógica de postagem (opcional postar também).
5. **Responder a um PowerApp ou fluxo** — corpo = `body('Chamar_Function_AWS')`.
   O app recebe o JSON e mostra o top 10 na tela `scrRelatorio`.

No app: `CustosAWSEnvioManual.Run(galContas.Selected.ID)`

---

## Regra de alerta (o que é "potencial de gasto elevado")

Um item é flagado quando **qualquer** uma das condições é verdadeira:

| Regra | Coluna na conta | Exemplo |
|-------|-----------------|---------|
| Custo do serviço no dia anterior acima do limite diário | `LimiteItemUSD` | EC2 > US$ 20/dia |
| Crescimento vs. o dia imediatamente anterior | `CrescimentoMaxPct` | +45% |

Ajuste por conta — contas pequenas têm limiares menores. Em alerta, o dono é
mencionado; sem alertas, o card de parabéns é postado.

> A coluna `HorarioEnvio` ficou reservada: hoje o envio é único às 9h para todas
> as contas. Se quiser voltar a ter horários por conta, use o filtro
> `HorarioEnvio eq <hora>` em um gatilho de hora em hora.
