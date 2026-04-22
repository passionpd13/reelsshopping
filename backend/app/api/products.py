from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.models import Product
from app.schemas.product import ProductIn, ProductOut

router = APIRouter()


@router.get("", response_model=list[ProductOut])
def list_products(session: Session = Depends(get_session)) -> list[Product]:
    return session.query(Product).order_by(Product.id.desc()).all()


@router.post("", response_model=ProductOut, status_code=201)
def create_product(body: ProductIn, session: Session = Depends(get_session)) -> Product:
    p = Product(
        name=body.name,
        brand=body.brand,
        price=body.price,
        description=body.description,
        features_json=body.features,
        cta_url=body.cta_url,
        target_audience=body.target_audience,
    )
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, session: Session = Depends(get_session)) -> Product:
    p = session.get(Product, product_id)
    if not p:
        raise HTTPException(404, "not found")
    return p


@router.patch("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int, body: ProductIn, session: Session = Depends(get_session)
) -> Product:
    p = session.get(Product, product_id)
    if not p:
        raise HTTPException(404, "not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        if k == "features":
            p.features_json = v
        else:
            setattr(p, k, v)
    session.commit()
    session.refresh(p)
    return p
