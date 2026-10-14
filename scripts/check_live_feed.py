"""Verify public Coinbase feed reachability without credentials or orders."""
import asyncio
import json

import websockets


async def check():
    async with asyncio.timeout(25):
        async with websockets.connect("wss://ws-feed.exchange.coinbase.com", open_timeout=10) as socket:
            await socket.send(json.dumps(dict(type="subscribe", product_ids=["BTC-USD"], channels=["ticker_batch", "heartbeat"])))
            async for raw in socket:
                message = json.loads(raw)
                if message.get("type") == "error":
                    raise RuntimeError("Coinbase rejected the subscription.")
                if message.get("type") == "ticker" and message.get("product_id") == "BTC-USD":
                    assert float(message["price"]) > 0
                    print("Received a real BTC-USD ticker from the public Coinbase feed.")
                    return


if __name__ == "__main__":
    asyncio.run(check())
