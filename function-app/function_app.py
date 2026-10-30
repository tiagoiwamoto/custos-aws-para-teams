"""
Azure Function: GetTopAwsCosts

Proxy entre Power Automate e AWS Cost Explorer.
O Power Automate nao consegue assinar requisicoes AWS SigV4, entao esta
Function recebe o Role ARN da conta-alvo, assume a role via STS e retorna
os TOP N servicos por custo do DIA ANTERIOR (00:00 ate 23:59) comparado
ao dia imediatamente anterior.

Autenticacao da chamada HTTP: function key (?code=...).
Credenciais AWS base (quem assume as roles): variaveis de ambiente
AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_DEFAULT_REGION.

POST /api/top-costs
{
  "roleArn": "arn:aws:iam::123456789012:role/PowerAutomateCostReader",
  "externalId": "opcional",
  "accountName": "opcional (rotulo)",
  "topN": 10
}
"""

import json
import os
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone

import azure.functions as func
import boto3
from botocore.exceptions import ClientError

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

GRANULARITY = "DAILY"
METRIC = "UnblendedCost"
DEFAULT_TOP_N = 10
FX_API_URL = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
FX_CACHE_TTL_SEC = 3600  # 1h
_fx_cache: dict = {"rate": None, "ts": 0.0}


def _daily_windows(today: date):
    """Retorna (inicio_atual, fim, inicio_anterior, fim_anterior).

    Cost Explorer usa intervalo [start, end) - end exclusivo.
    Atual = dia anterior completo (00:00 ate 23:59) -> end = hoje 00:00.
    Anterior = o dia imediatamente antes, mesma duracao.
    """
    cur_start = today - timedelta(days=1)
    end = today
    prev_start = today - timedelta(days=2)
    prev_end = cur_start
    return (
        cur_start.isoformat(),
        end.isoformat(),
        prev_start.isoformat(),
        prev_end.isoformat(),
    )


def _usd_brl_rate() -> tuple[float, str]:
    """Cotacao USD->BRL. Tenta AwesomeAPI (gratuita, sem chave), com cache de
    1h por instancia; fallback: env USD_BRL_RATE; ultimo recurso: 5.00."""
    now = time.time()
    if _fx_cache["rate"] and now - _fx_cache["ts"] < FX_CACHE_TTL_SEC:
        return _fx_cache["rate"], "cache"
    try:
        with urllib.request.urlopen(FX_API_URL, timeout=5) as resp:
            rate = float(json.loads(resp.read())["USDBRL"]["bid"])
        if rate > 0:
            _fx_cache.update(rate=rate, ts=now)
            return rate, "awesomeapi"
    except Exception:
        pass
    return float(os.environ.get("USD_BRL_RATE", "5.00")), "fallback"


def _assume_ce_client(role_arn: str, external_id: str | None, session_name: str):
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    if role_arn:
        sts = boto3.client("sts", region_name=region)
        params = {"RoleArn": role_arn, "RoleSessionName": session_name[:64]}
        if external_id:
            params["ExternalId"] = external_id
        creds = sts.assume_role(**params)["Credentials"]
        return boto3.client(
            "ce",
            region_name=region,
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
        )
    return boto3.client("ce", region_name=region)


def _costs_by_service(ce, start: str, end: str) -> dict:
    """{service: cost} agregado por servico para o periodo."""
    result = {}
    kwargs = {
        "TimePeriod": {"Start": start, "End": end},
        "Granularity": GRANULARITY,
        "Metrics": [METRIC],
        "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}],
    }
    while True:
        resp = ce.get_cost_and_usage(**kwargs)
        for period in resp.get("ResultsByTime", []):
            for group in period.get("Groups", []):
                service = group["Keys"][0]
                amount = float(group["Metrics"][METRIC]["Amount"])
                result[service] = result.get(service, 0.0) + amount
        token = resp.get("NextPageToken")
        if not token:
            break
        kwargs["NextPageToken"] = token
    return result


@app.route(route="top-costs", methods=["POST"])
def top_costs(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "corpo da requisicao nao e JSON valido"}),
            status_code=400,
            mimetype="application/json",
        )

    role_arn = body.get("roleArn", "")
    external_id = body.get("externalId") or None
    account_name = body.get("accountName") or role_arn.split(":")[4] or "conta"
    top_n = int(body.get("topN", DEFAULT_TOP_N))

    today = date.today()
    cur_start, end, prev_start, prev_end = _daily_windows(today)

    try:
        ce = _assume_ce_client(role_arn, external_id, f"pa-costs-{account_name}")
        current = _costs_by_service(ce, cur_start, end)
        previous = _costs_by_service(ce, prev_start, prev_end)
    except ClientError as e:
        return func.HttpResponse(
            json.dumps(
                {
                    "error": f"falha AWS: {e.response['Error'].get('Code')}",
                    "detail": e.response["Error"].get("Message", ""),
                }
            ),
            status_code=502,
            mimetype="application/json",
        )

    rate, rate_source = _usd_brl_rate()

    items = []
    for service, cost in current.items():
        prev = previous.get(service, 0.0)
        delta_pct = ((cost - prev) / prev * 100.0) if prev > 0 else None
        items.append(
            {
                "service": service,
                "cost": round(cost, 2),
                "costBrl": round(cost * rate, 2),
                "previousCost": round(prev, 2),
                "previousCostBrl": round(prev * rate, 2),
                "deltaPct": round(delta_pct, 1) if delta_pct is not None else None,
            }
        )

    items.sort(key=lambda i: i["cost"], reverse=True)
    items = items[:top_n]

    total = sum(current.values())
    total_prev = sum(previous.values())
    payload = {
        "account": account_name,
        "period": {
            "currentStart": cur_start,
            "currentEnd": end,
            "previousStart": prev_start,
            "previousEnd": prev_end,
        },
        "totalCost": round(total, 2),
        "totalCostBrl": round(total * rate, 2),
        "totalPrevious": round(total_prev, 2),
        "totalPreviousBrl": round(total_prev * rate, 2),
        "fx": {
            "usdBrl": round(rate, 4),
            "source": rate_source,
            "at": datetime.now(timezone.utc).isoformat(),
        },
        "items": items,
    }
    return func.HttpResponse(
        json.dumps(payload), status_code=200, mimetype="application/json"
    )
