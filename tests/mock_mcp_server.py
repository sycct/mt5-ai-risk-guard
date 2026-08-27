"""Dependency-free mock MCP server: python tests/mock_mcp_server.py --port 22346"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOOLS = [
    {"name": "get_account_info", "description": "balance equity margin account", "inputSchema": {"type": "object"}},
    {"name": "list_open_positions", "description": "open positions", "inputSchema": {"type": "object"}},
    {"name": "list_pending_orders", "description": "pending orders", "inputSchema": {"type": "object"}},
    {"name": "get_symbol_tick", "description": "symbol quote spread", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string"}}}},
    {"name": "deal_history", "description": "closed trade history", "inputSchema": {"type": "object"}},
]
DATA = {
    "get_account_info": {"balance": 55000, "equity": 52500, "margin": 1000, "free_margin": 51500, "margin_level": 2100, "currency": "USC"},
    "list_open_positions": {"positions": [{"ticket": 1, "symbol": "XAUUSD", "type": "buy", "volume": 1.1, "profit": -2500, "magic": 9527}]},
    "list_pending_orders": {"orders": [{"ticket": 2, "symbol": "XAUUSD", "type": "buy_limit", "volume": .1, "magic": 9527}]},
    "get_symbol_tick": {"symbol": "XAUUSD", "bid": 2500, "ask": 2500.2, "point": .01, "digits": 2},
    "deal_history": {"deals": [{"profit": 100}, {"profit": -50}]},
}

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0)); request = json.loads(self.rfile.read(length)); method = request["method"]
        if method == "notifications/initialized": self.send_response(202); self.end_headers(); return
        result = ({"protocolVersion": "2025-03-26", "capabilities": {"tools": {}, "resources": {}}, "serverInfo": {"name": "mock", "version": "1"}}
                  if method == "initialize" else {"tools": TOOLS} if method == "tools/list" else {"resources": []} if method == "resources/list"
                  else {"content": [{"type": "text", "text": json.dumps(DATA[request["params"]["name"]])}]})
        body = json.dumps({"jsonrpc": "2.0", "id": request.get("id"), "result": result}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body)))
        self.send_header("Mcp-Session-Id", "mock-session"); self.end_headers(); self.wfile.write(body)
    def log_message(self, *_): pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--port", type=int, default=22346); args = parser.parse_args()
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
