"""Inject failures into mocks in an isolated deployed Python process; no exchange I/O."""
import json
import shlex
import subprocess
from pathlib import Path

OUT = Path('.tmp/exchange-containment-20261030')
code = r'''
import asyncio,importlib.metadata,json,time
from unittest.mock import AsyncMock
from ccxt.base.errors import DDoSProtection,RequestTimeout
from src.config import BinanceConfig
from src.exchange.binance import BinanceExchange
from src.exchange.base import ExchangeAPIError
from src.exchange import request_backoff
from src.models import OrderRequest
from decimal import Decimal

def adapter():
    config=BinanceConfig(api_key='',api_secret='',testnet_api_key='',testnet_api_secret='',market_type='futures')
    instance=BinanceExchange(config,testnet=True)
    instance._client=AsyncMock()
    instance._client.last_response_headers=None
    return instance

async def main():
    first,second=adapter(),adapter()
    first._client.fetch_ohlcv.side_effect=DDoSProtection('synthetic HTTP418 banned until '+str(int((time.time()+600)*1000)))
    try: await first.get_ohlcv('BTC/USDT','1h')
    except ExchangeAPIError as exc:
        assert exc.code=='RATE_LIMIT' and 590 < exc.retry_after_seconds <= 600
    else: raise AssertionError('DDoS escaped normalization')
    for request in (lambda:second.get_ticker('BTC/USDT'),lambda:second.get_funding_rate('BTC/USDT')):
        try: await request()
        except ExchangeAPIError as exc: assert exc.code in ('RATE_LIMIT','rate_limited')
        else: raise AssertionError('cooldown bypass')
    assert first._client.fetch_ohlcv.await_count==1
    assert second._client.fetch_ticker.await_count==0
    assert second._client.fetch_funding_rate.await_count==0
    # Only this standalone process's in-memory registry is reset.
    request_backoff._deadlines.clear()
    second._client.create_market_order.side_effect=RequestTimeout('synthetic timeout')
    try: await second.create_order(OrderRequest(symbol='BTC/USDT',side='buy',type='market',quantity=Decimal('1')))
    except ExchangeAPIError as exc: assert exc.code=='NETWORK_ERROR'
    else: raise AssertionError('timeout treated as fill')
    assert second._client.create_market_order.await_count==1
    print(json.dumps({'ccxt_version':importlib.metadata.version('ccxt'),'checks':{'ddos_normalized':True,'ban_deadline_honored':True,'sibling_ticker_suppressed':True,'derivatives_suppressed':True,'order_timeout_no_retry':True},'exchange_network_calls':0}))

asyncio.run(main())
'''
command='env PYTHONDONTWRITEBYTECODE=1 python -c '+shlex.quote(code)
result=subprocess.run(['fly','ssh','console','--app','crypto-master','--machine','6835752b711958','--quiet','--command',command],capture_output=True,text=True,timeout=60)
(OUT/'runtime-fault-smoke.stderr').write_text(result.stderr)
if result.returncode:
    print(result.stderr[-1500:])
    raise SystemExit(result.returncode)
payload=json.loads(result.stdout)
(OUT/'runtime-fault-smoke.json').write_text(json.dumps(payload,indent=2)+'\n')
print(json.dumps(payload,indent=2))
