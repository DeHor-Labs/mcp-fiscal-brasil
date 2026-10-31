from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class CNAEActivity(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    código: str = Field(
        validation_alias=AliasChoices("código", "codigo"),
        serialization_alias="codigo",
    )
    descrição: str = Field(
        validation_alias=AliasChoices("descrição", "descricao"),
        serialization_alias="descricao",
    )


class CNAEClass(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    código: str = Field(
        validation_alias=AliasChoices("código", "codigo"),
        serialization_alias="codigo",
    )
    descrição: str = Field(
        validation_alias=AliasChoices("descrição", "descricao"),
        serialization_alias="descricao",
    )
    grupo: str | None = None
    divisao: str | None = None
