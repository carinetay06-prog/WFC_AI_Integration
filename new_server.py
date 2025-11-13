from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os
from typing import Any, Dict

# Import your ShopfloorGraphTool wrapper
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
TOOLS_FILE = os.path.join(BASE_DIR, "shopfloor_tool_contract.json")  # adjust path if needed

if not os.path.exists(TOOLS_FILE):
    raise FileNotFoundError(f"{TOOLS_FILE} not found!")

with open(TOOLS_FILE, "r") as f:
    TOOL_CONTRACT = json.load(f)

OPERATIONS = TOOL_CONTRACT.get("operations", {})

# Neo4j credentials from environment variables
NEO4J_URI = os.environ.get("NEO4J_URI")
NEO4J_USER = os.environ.get("NEO4J_USER")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD")

if not (NEO4J_URI and NEO4J_USER and NEO4J_PASSWORD):
    raise RuntimeError("Neo4j credentials missing in environment variables!")

# Initialize the Neo4j wrapper
neo4j_tool = ShopfloorGraphTool(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, TOOLS_FILE)


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


def validate_and_cast_inputs(op_schema: Dict, inputs: Dict[str, Any]) -> Dict[str, Any]:
    validated = {}
    for key, val_schema in op_schema.get("inputs", {}).items():
        if val_schema.get("required", False) and key not in inputs:
            raise HTTPException(status_code=400, detail=f"Missing required input: '{key}'")
        if key in inputs:
            # Simple type casting
            try:
                if val_schema["type"] == "number":
                    validated[key] = float(inputs[key])
                elif val_schema["type"] == "string":
                    validated[key] = str(inputs[key])
                else:
                    validated[key] = inputs[key]
            except Exception:
                raise HTTPException(status_code=400, detail=f"Cannot cast '{key}' to {val_schema['type']}")
    return validated


@app.post("/tools/run")
def run_tool(request: ToolRequest):
    op = OPERATIONS.get(request.operation)
    if not op:
        raise HTTPException(status_code=404, detail=f"Operation '{request.operation}' not found")

    # Validate inputs
    validated_inputs = validate_and_cast_inputs(op, request.inputs)

    # Call Neo4j via ShopfloorGraphTool
    try:
        results = neo4j_tool.call(request.operation, validated_inputs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Neo4j query failed: {str(e)}")

    return {
        "operation": request.operation,
        "description": op.get("description"),
        "inputs_received": validated_inputs,
        "outputs": results
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"[START] Shopfloor MCP Server running at http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
