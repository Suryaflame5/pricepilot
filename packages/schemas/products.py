"""Product / variant / retailer / listing API schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    variant_name: str | None
    color: str | None
    storage: str | None
    size: str | None
    condition: str | None
    gtin: str | None
    sku: str | None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    brand: str | None
    model: str | None
    canonical_name: str
    category: str | None
    subcategory: str | None
    description: str | None
    launched_at: datetime | None


class ProductDetailOut(ProductOut):
    variants: list[VariantOut] = []


class VariantWithProductOut(VariantOut):
    product: ProductOut | None = None


class RetailerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    domain: str | None
    country: str | None
    currency: str | None


class ListingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_variant_id: uuid.UUID
    retailer: RetailerOut | None = None
    seller_name: str | None
    url: str | None
    listing_title: str | None
    active: bool
