"""Explicit allowlisted action contracts. Demo identity is NOT authentication."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal

class IncidentAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,32}$")
    summary: str = Field(min_length=8, max_length=200)
    priority: Literal["1", "2", "3", "4"] = "3"

class ActionPolicy:
    ALLOWED = {"servicenow.create_incident": IncidentAction, "jira.create_followup": None}
    @classmethod
    def validate(cls, tool: str, args: dict) -> dict:
        if tool not in cls.ALLOWED:
            raise ValueError("Tool not permitted")
        if tool == "jira.create_followup":
            if set(args) != {"account_id", "summary"} or not all(isinstance(v,str) and 0<len(v)<=200 for v in args.values()):
                raise ValueError("Invalid action arguments")
            return args
        return IncidentAction.model_validate(args).model_dump()
