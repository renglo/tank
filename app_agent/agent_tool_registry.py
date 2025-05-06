import json
from typing import List, Dict, Any, Callable, Optional, Union, Annotated, Type
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
import boto3
from botocore.exceptions import ClientError
import re
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
import importlib
import gc


'''
This Tool Registry needs to provide the following features:

1. Support for different types of tools:
a) internal function tools
b) local class tools
c) API based tools
d) MCP tools
e) Agent powered tools

2. Seamless management of tool Credentials
- User based credentials
- Secret management
- Token management

3. Standard request and response format
- The agent should use the same input and output schemas for all tools



'''

class ToolCredentials(BaseModel):
    credentials: Dict[str, Any] = Field(default_factory=dict)
    secrets_manager: Any = Field(default_factory=lambda: boto3.client('secretsmanager'), exclude=True)
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def get_secret(self, secret_name: str) -> str:
        try:
            response = self.secrets_manager.get_secret_value(SecretId=secret_name)
            return response['SecretString']
        except ClientError as e:
            raise Exception(f"Failed to get secret: {str(e)}")

class ToolParams(BaseModel):
    """Base class for tool parameters"""
    model_config = ConfigDict(extra='forbid')  # Prevent extra fields

class ToolResult(BaseModel):
    """Base class for tool results"""
    success: bool
    result: Any
    error: Optional[str] = None

class BaseTool(BaseModel, ABC):
    credentials: Optional[ToolCredentials] = None
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Execute the tool with given parameters"""
        pass
    
    @abstractmethod
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate the input parameters"""
        pass

class InternalFunctionTool(BaseTool):
    func: Callable
    param_schema: Dict[str, Any]
    
    def execute(self, params: Dict[str, Any]) -> ToolResult:
        if not self.validate_params(params):
            return ToolResult(success=False, result=None, error="Invalid parameters")
        try:
            result = self.func(**params)
            return ToolResult(success=True, result=result)
        except Exception as e:
            return ToolResult(success=False, result=None, error=str(e))
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        try:
            # Create a dynamic Pydantic model based on the schema
            fields = {}
            for param_name, schema in self.param_schema.items():
                field_type = self._get_pydantic_type(schema.get("type", "string"))
                fields[param_name] = (field_type, ...)
            
            DynamicModel = type('DynamicModel', (BaseModel,), fields)
            DynamicModel(**params)
            return True
        except Exception:
            return False
    
    @staticmethod
    def _get_pydantic_type(schema_type: str) -> type:
        type_map = {
            "string": str,
            "number": Union[int, float],
            "boolean": bool,
            "integer": int,
            "array": List,
            "object": Dict
        }
        return type_map.get(schema_type, Any)



class ToolRegistry(BaseModel):
    tools: Dict[str, BaseTool] = Field(default_factory=dict, exclude=True)
    credentials: ToolCredentials = Field(default_factory=ToolCredentials)
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def register_tool(self, name: str, tool: BaseTool) -> None:
        """Register a new tool"""
        self.tools[name] = tool
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name"""
        return self.tools.get(name)
    
    def list_tools(self) -> Dict[str, Dict[str, Any]]:
        """List all registered tools and their capabilities"""
        return {
            name: {
                "type": tool.__class__.__name__,
                "requires_credentials": tool.credentials is not None
            }
            for name, tool in self.tools.items()
        }
    
    def execute_tool(self, name: str, params: Dict[str, Any]) -> ToolResult:
        """Execute a tool by name with given parameters"""
        tool = self.get_tool(name)
        if not tool:
            return ToolResult(success=False, result=None, error=f"Tool '{name}' not found")
        return tool.execute(params)
    
    
class RequestScopedToolRegistry(ToolRegistry): 
    '''
    Thread safe Tool Registry
    - It creates the registry, registers the function, executes function and deletes the registry in the same run
    - It works similar to schd_loader
    '''
    
    '''# EXAMPLE Usage in Lambda handler
    def lambda_handler(event, context):
        registry = RequestScopedToolRegistry()
        try:
            # Register and use tools
            search_tool = SearchTool(
                index_path="/path/to/search/index",
                max_results=20
            )
            registry.register_tool("search_documents", search_tool)
            
            # Execute tool
            result = registry.execute_tool("search_documents", params)
            
            return result
        finally:
            # Clean up
            registry.cleanup()
    '''

    def __init__(self):
        super().__init__()
        self._request_tools = {}
    
    def register_tool(self, name: str, tool: BaseTool) -> None:
        """Register a tool for the current request"""
        self._request_tools[name] = tool
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool for the current request"""
        return self._request_tools.get(name)
    
    def cleanup(self):
        """Clean up tools after request completion"""
        self._request_tools.clear()
        gc.collect()






def load_tool_class(module_path: str, class_name: str) -> Type[BaseTool]:
    """Dynamically load a tool class from a module"""
    try:
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        raise ImportError(f"Failed to load tool class {class_name} from {module_path}: {str(e)}")

def register_tools_from_manifest(registry: ToolRegistry, manifest_path: str) -> None:
    """Register tools from a JSON manifest file
    
    The manifest should be a JSON file with the following structure:
    {
        "tools": [
            {
                "name": "tool_name",
                "module": "path.to.module",
                "class": "ToolClassName",
                "config": {
                    // Tool-specific configuration
                }
            }
        ]
    }
    """
    try:
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        raise ValueError(f"Failed to load tool manifest from {manifest_path}: {str(e)}")

    for tool_info in manifest.get("tools", []):
        try:
            # Extract tool information
            name = tool_info["name"]
            module_path = tool_info["module"]
            class_name = tool_info["class"]
            config = tool_info.get("config", {})

            # Load the tool class
            tool_class = load_tool_class(module_path, class_name)
            
            # Create and register the tool
            tool = tool_class(**config)
            registry.register_tool(name, tool)
            
        except KeyError as e:
            print(f"Warning: Missing required field in tool manifest: {str(e)}")
            continue
        except Exception as e:
            print(f"Warning: Failed to register tool {name}: {str(e)}")
            continue

def register_all_tools(registry: ToolRegistry, manifest_path: str = None) -> None:
    """Register all available tools
    
    Args:
        registry: The tool registry to register tools with
        manifest_path: Optional path to a tool manifest JSON file
    """
    # Register tools from manifest if provided
    if manifest_path:
        register_tools_from_manifest(registry, manifest_path)

# Example usage:
if __name__ == "__main__":
    # Create registry
    registry = ToolRegistry()
    
    # Example 1: Register internal function tool
    def normalize_date(date_str: str) -> str:
        if date_str.lower() == "tomorrow":
            return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        return date_str
    
    date_tool = InternalFunctionTool(
        func=normalize_date,
        param_schema={"date_str": {"type": "string"}}
    )
    registry.register_tool("normalize_date", date_tool)
    
    # Example 2: Register tools from manifest
    manifest_path = "tools_manifest.json"
    register_all_tools(registry, manifest_path)

    # Example of executing the Internal Function tool
    result = registry.execute_tool("normalize_date", {
        "date_str": "tomorrow"
    })
    print(f"Search result: {result}")

# Example manifest.json:
"""
{
    "tools": [
        {
            "name": "search_documents",
            "module": "tank.app_agent.tools.search",
            "class": "SearchTool",
            "config": {
                "index_path": "/path/to/index",
                "max_results": 10
            }
        },
        {
            "name": "process_image",
            "module": "tank.app_agent.tools.image",
            "class": "ImageProcessor",
            "config": {
                "output_dir": "/path/to/output",
                "formats": ["jpg", "png"]
            }
        }
    ]
}
"""





