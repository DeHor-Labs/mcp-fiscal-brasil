from pydantic import BaseModel, ConfigDict, Field


class CNAEActivity(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    código: str = Field(serialization_alias="codigo")
    descrição: str = Field(serialization_alias="descricao")


class CNAEClass(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    código: str = Field(serialization_alias="codigo")
    descrição: str = Field(serialization_alias="descricao")
    grupo: str | None = None
    divisao: str | None = None
