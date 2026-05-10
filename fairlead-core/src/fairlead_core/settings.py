from typing import List

from pydantic import Field, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(secrets_dir='.', env_prefix='fairlead_')

    cors_origins: List[str] = Field(default_factory=lambda: [
        "http://localhost",
        "http://localhost:8080",
        "http://localhost:5173"
    ])

    unit_resolution_uri: str = Field(default="https://www.qudt.org/fuseki/qudt/query")


class OptimizationSettings(BaseModel):
    prevent_enhancement: bool = Field(False, alias='preventEnhancement')
    prevent_structural_enhancement: bool = Field(False, alias='preventStructuralEnhancement')
    prevent_optimization: bool = Field(False, alias='preventOptimization')
    prevent_automatic_optimization: bool = Field(False, alias='preventAutomaticOptimization')
    prevent_user_optimization: bool = Field(False, alias='preventUserOptimization')
    generate_inverse_relations: bool = Field(False, alias='generateInverseRelations')
