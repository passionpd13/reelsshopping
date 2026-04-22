from pydantic import BaseModel, ConfigDict


class ProductIn(BaseModel):
    name: str
    brand: str | None = None
    price: str | None = None
    description: str | None = None
    features: list[str] = []
    cta_url: str | None = None
    target_audience: str | None = None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    brand: str | None
    price: str | None
    description: str | None
    features_json: list
    images_json: list
    cta_url: str | None
    target_audience: str | None
