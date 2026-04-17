"""Pydantic models for structured tool output.

These models define the response schemas for MCP tools, enabling
automatic JSON schema generation and output validation by MCP clients.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# --- Search Records ---


class SearchResult(BaseModel):
    """Result of a record search operation."""

    records: List[Dict[str, Any]] = Field(description="List of matching records")
    total: int = Field(description="Total number of records matching the domain")
    limit: int = Field(description="Maximum records returned per page")
    offset: int = Field(description="Number of records skipped")
    model: str = Field(description="Odoo model name that was searched")


# --- Get Record ---


class FieldSelectionMetadata(BaseModel):
    """Metadata about which fields were returned and why."""

    fields_returned: int = Field(description="Number of fields in the response")
    field_selection_method: str = Field(
        description="How fields were selected (smart_defaults, explicit, all)"
    )
    total_fields_available: Optional[int] = Field(
        default=None, description="Total fields on the model"
    )
    note: Optional[str] = Field(
        default=None,
        description="Guidance on how to request more fields",
    )


class RecordResult(BaseModel):
    """Result of retrieving a single record by ID."""

    record: Dict[str, Any] = Field(description="Record data with requested fields")
    metadata: Optional[FieldSelectionMetadata] = Field(
        default=None,
        description="Field selection metadata (present when using smart defaults)",
    )


# --- List Models ---


class ModelOperations(BaseModel):
    """Allowed CRUD operations for a model."""

    read: bool = Field(description="Can read records")
    write: bool = Field(description="Can update records")
    create: bool = Field(description="Can create records")
    unlink: bool = Field(description="Can delete records")


class ModelInfo(BaseModel):
    """Information about an MCP-enabled Odoo model."""

    model: str = Field(description="Technical model name (e.g. 'res.partner')")
    name: str = Field(description="Human-readable model name")
    operations: Optional[ModelOperations] = Field(
        default=None, description="Allowed operations (standard mode only)"
    )


class YoloModeInfo(BaseModel):
    """YOLO mode status and configuration."""

    enabled: bool = Field(description="Whether YOLO mode is active")
    level: str = Field(description="YOLO level: 'read' or 'true'")
    description: str = Field(description="Human-readable mode description")
    warning: str = Field(description="Security warning message")
    operations: ModelOperations = Field(description="Global operation permissions in YOLO mode")


class ModelsResult(BaseModel):
    """Result of listing available models."""

    models: List[ModelInfo] = Field(description="List of available models")
    yolo_mode: Optional[YoloModeInfo] = Field(
        default=None, description="YOLO mode info (only present when YOLO is enabled)"
    )
    total: Optional[int] = Field(default=None, description="Total number of models")
    error: Optional[str] = Field(default=None, description="Error message if model listing failed")


# --- List Resource Templates ---


class ResourceTemplateParameter(BaseModel):
    """Parameter definition for a resource template."""

    model: str = Field(description="Odoo model name (e.g., res.partner)")
    record_id: Optional[str] = Field(default=None, description="Record ID (e.g., 10)")


class ResourceTemplateInfo(BaseModel):
    """Information about an available resource URI template."""

    uri_template: str = Field(description="URI template pattern")
    description: str = Field(description="What this resource provides")
    parameters: Dict[str, str] = Field(description="Template parameter descriptions")
    example: str = Field(description="Example URI")
    note: Optional[str] = Field(default=None, description="Additional usage notes")


class ResourceTemplatesResult(BaseModel):
    """Result of listing resource templates."""

    templates: List[ResourceTemplateInfo] = Field(description="Available resource templates")
    enabled_models: List[str] = Field(description="Sample of models usable with these templates")
    total_models: int = Field(description="Total number of enabled models")
    note: str = Field(description="Usage guidance for resources vs tools")


# --- Create Record ---


class CreateResult(BaseModel):
    """Result of creating a new record."""

    success: bool = Field(description="Whether the record was created successfully")
    record: Dict[str, Any] = Field(description="Essential fields of the created record")
    url: str = Field(description="Direct URL to the record in Odoo web interface")
    message: str = Field(description="Human-readable success message")


# --- Update Record ---


class UpdateResult(BaseModel):
    """Result of updating an existing record."""

    success: bool = Field(description="Whether the record was updated successfully")
    record: Dict[str, Any] = Field(description="Essential fields of the updated record")
    url: str = Field(description="Direct URL to the record in Odoo web interface")
    message: str = Field(description="Human-readable success message")


# --- Delete Record ---


class DeleteResult(BaseModel):
    """Result of deleting a record."""

    success: bool = Field(description="Whether the record was deleted successfully")
    deleted_id: int = Field(description="ID of the deleted record")
    deleted_name: str = Field(description="Display name of the deleted record")
    message: str = Field(description="Human-readable success message")


# --- Execute Method ---


class ExecuteMethodResult(BaseModel):
    """Result of calling an arbitrary method on an Odoo model."""

    success: bool = Field(description="Whether the method executed successfully")
    model: str = Field(description="Odoo model the method was called on")
    method: str = Field(description="Method that was called")
    ids: Optional[List[int]] = Field(default=None, description="Record IDs the method was called on")
    result: Any = Field(description="Raw result returned by Odoo (type depends on method)")
    message: str = Field(description="Human-readable summary")


# --- Discover Model Actions ---


class ModelAction(BaseModel):
    """A single action or method available on a model."""

    name: str = Field(description="Technical method/action name to use in execute_method")
    label: str = Field(description="Human-readable label")
    kind: str = Field(description="Type: server_action, window_action, or orm_method")
    binding_model: Optional[str] = Field(
        default=None, description="Model the action is bound to"
    )


class DiscoverActionsResult(BaseModel):
    """Result of discovering available methods/actions for a model."""

    model: str = Field(description="Odoo model that was inspected")
    actions: List[ModelAction] = Field(description="Available methods and actions")
    total: int = Field(description="Total number of actions found")
    note: str = Field(
        description="Hint on how to call these actions via execute_method"
    )


class WebControllerResult(BaseModel):
    """Result of calling an Odoo web controller endpoint."""

    success: bool
    path: str
    result: Any = None
    message: str

