
import os, time, threading
from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel, Field
from binance.client import Client
from binance.enums import *

BINANCE_KEY = os.getenv("BINANCE_API_KEY","")
BINANCE_SECRET = os.getenv("BINANCE_API_SECRET","")
PAPER = os.getenv("PAPER","true").lower() == "true"
SYMBOL = os.getenv("SYMBOL_DEFAULT","BTCUSDT")

app = FastAPI(title="Spot Executor (OCO-safe)")

if not PAPER and (not BINANCE_KEY or not BINANCE_SECRET):
    raise RuntimeError("Set BINANCE_API_KEY and BINANCE_API_SECRET for LIVE mode")

client = None if PAPER else Client(api_key=BINANCE_KEY, api_secret=BINANCE_SECRET)

class RiskBlock(BaseModel):
    mode: str = Field("OCO_TP_SL", description="OCO mode")
    tpPrice: float
    slStopPrice: float
    slLimitPrice: float
    makerMaxWaitSec: int = 60

class OrderIn(BaseModel):
    symbol: str = SYMBOL
    side: str = "BUY"
    type: str = "LIMIT_MAKER"
    price: float
    quantity: float
    clientTag: Optional[str] = "n8n-spot-oco-safe"
    risk: RiskBlock

class OrderOut(BaseModel):
    status: str
    detail: str
    orderId: Optional[str] = None

def _place_oco_after_fill(symbol, orderId, qty, tpPrice, slStop, slLimit, waitSec=60):
    if PAPER:
        print(f"[PAPER] Would monitor {symbol} order {orderId} and then OCO qty={qty}, TP={tpPrice}, SL={slStop}/{slLimit}")
        return
    # monitor fill
    t0 = time.time()
    executed_qty = 0.0
    while time.time() - t0 < waitSec:
        try:
            o = client.get_order(symbol=symbol, orderId=orderId)
            status = o.get("status")
            executed_qty = float(o.get("executedQty","0"))
            if status == "FILLED" and executed_qty > 0:
                break
        except Exception as e:
            print("get_order error:", e)
        time.sleep(1.5)

    if executed_qty <= 0:
        # cancel unfilled maker
        try:
            client.cancel_order(symbol=symbol, orderId=orderId)
        except Exception as e:
            print("cancel error:", e)
        print("Order not filled within timeout; cancelled.")
        return

    # place OCO (SELL)
    try:
        res = client.create_oco_order(
            symbol=symbol,
            side=SIDE_SELL,
            quantity=round(executed_qty, 5),
            price=str(tpPrice),
            stopPrice=str(slStop),
            stopLimitPrice=str(slLimit),
            stopLimitTimeInForce=TIME_IN_FORCE_GTC
        )
        print("OCO placed:", res)
    except Exception as e:
        print("create_oco_order error:", e)

@app.post("/order", response_model=OrderOut)
def place_order(o: OrderIn):
    if o.side != "BUY" or o.type not in ("LIMIT_MAKER","LIMIT"):
        return OrderOut(status="REJECT", detail="Only BUY LIMIT_MAKER supported in this executor")

    if PAPER:
        # Simulated path
        print(f"[PAPER] BUY {o.symbol} {o.quantity} @ {o.price} (LIMIT_MAKER)")
        print(f"[PAPER] Plan OCO → TP {o.risk.tpPrice} ; SL {o.risk.slStopPrice}/{o.risk.slLimitPrice}")
        return OrderOut(status="OK", detail="Paper order accepted (no live trading)")

    try:
        res = client.create_order(
            symbol=o.symbol,
            side=SIDE_BUY,
            type=ORDER_TYPE_LIMIT_MAKER,
            quantity=str(o.quantity),
            price=str(o.price),
            newClientOrderId=o.clientTag
        )
        order_id = res.get("orderId")
    except Exception as e:
        return OrderOut(status="ERROR", detail=f"create_order failed: {e}")

    # spawn watcher to place OCO after fill
    th = threading.Thread(
        target=_place_oco_after_fill,
        args=(o.symbol, order_id, o.quantity, o.risk.tpPrice, o.risk.slStopPrice, o.risk.slLimitPrice, o.risk.makerMaxWaitSec),
        daemon=True
    )
    th.start()

    return OrderOut(status="OK", detail="Order placed, OCO will be placed after fill", orderId=str(order_id))
