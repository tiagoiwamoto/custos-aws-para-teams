# Guia — Power App `Custos AWSp → Teams`

O app é a camada de administração: cadastra contas/donos/horários/limiares,
mostra KPIs e histórico e dispara envio manual de relatório.

Dois caminhos para montar:

1. **Manual no Studio** (recomendado, ~30 min) — siga as fórmulas de
   `src/*.yaml` como referência exata de cada propriedade.
2. **Colar YAML** — o Studio aceita colar código-fonte de controles
   (selecione a tela → cole). O YAML em `src/` pode precisar de ajustes
   finos de nome de controle conforme a versão do Studio.

## Estrutura

| Tela | Função |
|------|--------|
| `scrDashboard` | KPIs (contas, alertas no mês, total acumulado no mês), lista de contas com semáforo de status, últimos envios, botão "Enviar agora" |
| `scrContas` | CRUD da lista `ContasAWS` (galeria + formulário de edição) |
| `scrRelatorio` | Escolhe a conta → roda o fluxo `CustosAWSEnvioManual` → exibe top 10 com flags de alerta |

## Fontes de dados (Dados → Adicionar dados)

- `ContasAWS` (SharePoint)
- `RelatoriosCustos` (SharePoint)
- `CustosAWSEnvioManual` (Power Automate — aparece após criar o Fluxo 2)

## App.OnStart

```powerfx
ClearCollect(colContas, Filter(ContasAWS, Ativo = true));
ClearCollect(colRelatorios, SortByColumns(RelatoriosCustos, "DataEnvio", Descending))
```

## Pontos de atenção

- **Semáforo da conta** (`dotStatus.Fill`): faz `LookUp` no último relatório
  da conta — verde `Controlado`, vermelho `Atencao`, cinza sem histórico.
- **Botão Enviar agora** (`btnGerar.OnSelect`): `CustosAWSEnvioManual.Run(<ID>)`
  devolve o JSON da Function; `varRelatorio.items` popula a galeria do top 10.
- **Flags de alerta no app** usam a mesma regra do fluxo
  (`LimiteItemUSD` / `CrescimentoMaxPct`), para o usuário ver o mesmo que vai ao Teams.
- Se `Status` for coluna de escolha no SharePoint, compare com
  `Status.Value = "Atencao"` — se preferir texto puro, troque para `Status = "Atencao"`.
- O envio é **diário às 09:00** para todas as contas ativas, com os dados do
  **dia anterior (00:00–23:59)**. `HorarioEnvio` ficou reservado para um
  futuro agendamento por conta — pode remover o card do formulário.

## Publicação

Publique o app e compartilhe com os donos de conta (permissão de leitura em
`RelatoriosCustos` e escrita em `ContasAWS` apenas para administradores —
use permissões de item ou duas listas se precisar isolar).
