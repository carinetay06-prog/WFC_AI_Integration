from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os
from typing import Any, Dict

# Import your real Neo4j wrapper
from shopfloor_tool import ShopfloorGraphTool

app = FastAPI(title="Shopfloor MCP Server")

# Allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load tool contract
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_FILE = os.path.join(BASE_DIR, "shopfloor_tool_contract.json")

if not os.path.exists(TOOLS_FILE):
    raise FileNotFoundError(f"{TOOLS_FILE} not found!")

with open(TOOLS_FILE, "r") as f:
    TOOL_CONTRACT = json.load(f)

OPERATIONS = TOOL_CONTRACT.get("operations", {})

# Initialize Neo4j tool with env vars
NEO4J_URI = os.environ.get("NEO4J_URI", "neo4j+s://62f9b154.databases.neo4j.io")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "U32P3onr7idgSWbqklVReZQ8BVRH_BWH3_A5Oj83oq0")

try:
    tool = ShopfloorGraphTool(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
except Exception as e:
    raise RuntimeError(f"Failed to initialize ShopfloorGraphTool: {e}")

@app.get("/")
def root():
    return {"message": "Shopfloor MCP Server running 🚀"}

@app.get("/tools/list_operations")
def list_operations():
    """Return a list of available operation names"""
    return {"operations": list(OPERATIONS.keys())}

class ToolRequest(BaseModel):
    operation: str
    inputs: Dict[str, Any] = {}

def cast_input_value(value: Any, type_name: str):
    try:
        if type_name == "number":
            if isinstance(value, (int, float)):
                return value
            if "." in str(value):
                return float(value)
            return int(value)
        elif type_name == "string":
            return str(value)
        else:
            return value
    except Exception:
        raise ValueError(f"Cannot cast value '{value}' to type '{type_name}'")

def validate_and_cast_inputs(op_schema: Dict, inputs: Dict[str, Any]) -> Dict[str, Any]:
    validated = {}
    for key, val_schema in op_schema.get("inputs", {}).items():
        if val_schema.get("required", False) and key not in inputs:
            raise HTTPException(status_code=400, detail=f"Missing required input: '{key}'")
        if key in inputs:
            try:
                validated[key] = cast_input_value(inputs[key], val_schema["type"])
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
    return validated

@app.post("/tools/run")
def run_tool(request: ToolRequest):
    op = OPERATIONS.get(request.operation)
    if not op:
        raise HTTPException(status_code=404, detail=f"Operation '{request.operation}' not found")

    validated_inputs = validate_and_cast_inputs(op, request.inputs)

    try:
        # Call the real Neo4j operation
        result = tool.call(request.operation, validated_inputs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error executing operation: {e}")

    return {
        "operation": request.operation,
        "description": op.get("description"),
        "inputs_received": validated_inputs,
        "outputs": result
    }

# Graceful shutdown to close Neo4j connection
@app.on_event("shutdown")
def shutdown_event():
    tool.close()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"[START] Shopfloor MCP Server running at http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
