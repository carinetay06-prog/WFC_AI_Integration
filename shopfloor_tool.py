
"""
ShopfloorGraphTool — Minimal Python wrapper for executing operations defined in shopfloor_tool_contract.json

Usage (CLI):
  export NEO4J_URI=neo4j+s://c4c021e8.databases.neo4j.io
  export NEO4J_USER=neo4j
  export NEO4J_PASSWORD=erqwOAV4kn4cLkktYx1tCv4M-h1piA5ay64o0Gyls48
  python shopfloor_tool.py call highVibrationMachines '{"threshold": 7.5, "unit": "mm/s"}'

This script expects the Neo4j Python driver to be installed:
  pip install neo4j
"""
import json, os, sys
from dataclasses import dataclass
from typing import Any, Dict

# Lazy import to avoid import error if driver isn't installed in the current env
try:
    from neo4j import GraphDatabase
except Exception:
    GraphDatabase = None

CONTRACT_PATH = os.environ.get('SHOPFLOOR_CONTRACT', 'shopfloor_tool_contract.json')

@dataclass
class ToolOperation:
    name: str
    cypher: str
    inputs: Dict[str, Any]

class ShopfloorGraphTool:
    def __init__(self, uri: str, user: str, password: str, contract_path: str = CONTRACT_PATH):
        if GraphDatabase is None:
            raise RuntimeError('neo4j driver not available. Install with `pip install neo4j`.')
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        with open(contract_path) as f:
            self.contract = json.load(f)
        self.operations = self.contract.get('operations', {})

    def close(self):
        self.driver.close()

    def call(self, op_name: str, params: Dict[str, Any]):
        if op_name not in self.operations:
            raise ValueError(f'Unknown operation: {op_name}')
        op = self.operations[op_name]
        # Input validation (minimal)
        required = {k for k, v in op.get('inputs', {}).items() if v.get('required')}
        missing = [k for k in required if k not in params]
        if missing:
            raise ValueError(f'Missing required inputs: {missing}')

        # Guard: unit whitelist (example)
        if 'unit' in params:
            allowed_units = {'mm/s', 'C', 'dB'}
            if params['unit'] not in allowed_units:
                raise ValueError(f"unit must be one of {sorted(allowed_units)}")

        cypher = op['cypher']
        with self.driver.session() as session:
            res = session.run(cypher, params)
            return [r.data() for r in res]

# Simple CLI
if __name__ == '__main__':
    if len(sys.argv) < 3 or sys.argv[1] != 'call':
        print('Usage: python shopfloor_tool.py call <operationName> <jsonInputs>')
        sys.exit(1)
    op = sys.argv[2]
    inputs = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    uri = os.environ.get('NEO4J_URI', 'neo4j+s://c4c021e8.databases.neo4j.io')
    user = os.environ.get('NEO4J_USER', 'neo4j')
    pwd  = os.environ.get('NEO4J_PASSWORD', 'erqwOAV4kn4cLkktYx1tCv4M-h1piA5ay64o0Gyls48')
    tool = ShopfloorGraphTool(uri, user, pwd)
    try:
        out = tool.call(op, inputs)
        print(json.dumps(out, indent=2, default=str))
    finally:
        tool.close()
