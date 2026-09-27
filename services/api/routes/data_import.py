"""CSV import routes for manual data import."""

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
import pandas as pd
from datetime import datetime
import io

from api.dependencies import session_factory
from database.models import Product, PriceObservation
from sqlalchemy import select

router = APIRouter(prefix="/import", tags=["import"])

class ImportResponse(BaseModel):
    success: bool
    message: str
    products_imported: int = 0
    observations_imported: int = 0
    errors: list[str] = []

@router.post("/csv", response_model=ImportResponse)
async def import_csv(file: UploadFile = File(...)):
    """Import price data from CSV file.
    
    Expected CSV format:
    product_name,retailer,price,currency,observed_at,availability
    "Sony WH-1000XM6","Amazon",29999,"INR","2024-01-15T10:30:00Z","in_stock"
    """
    try:
        # Read CSV file
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
        
        # Validate required columns
        required_columns = ['product_name', 'retailer', 'price', 'currency', 'observed_at']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {', '.join(missing_columns)}"
            )
        
        async with session_factory() as session:
            products_imported = 0
            observations_imported = 0
            errors = []
            
            for _, row in df.iterrows():
                try:
                    # Parse datetime
                    observed_at = pd.to_datetime(row['observed_at'])
                    if pd.isna(observed_at):
                        errors.append(f"Invalid datetime in row: {row.to_dict()}")
                        continue
                    
                    # Find or create product
                    product_name = str(row['product_name']).strip()
                    retailer = str(row['retailer']).strip()
                    
                    result = await session.execute(
                        select(Product).where(
                            Product.name == product_name,
                            Product.retailer == retailer
                        )
                    )
                    product = result.scalar_one_or_none()
                    
                    if not product:
                        product = Product(
                            name=product_name,
                            retailer=retailer,
                            category=row.get('category', 'Electronics'),
                            brand=row.get('brand', 'Unknown'),
                            url=row.get('url', ''),
                            image_url=row.get('image_url', '')
                        )
                        session.add(product)
                        await session.flush()
                        products_imported += 1
                    
                    # Create price observation
                    observation = PriceObservation(
                        product_id=product.id,
                        retailer=retailer,
                        price=float(row['price']),
                        currency=str(row['currency']),
                        observed_at=observed_at,
                        availability=str(row.get('availability', 'unknown')),
                        is_trusted=True  # Manual imports are trusted by default
                    )
                    session.add(observation)
                    observations_imported += 1
                    
                except Exception as e:
                    errors.append(f"Error processing row: {str(e)}")
                    continue
            
            await session.commit()
            
            return ImportResponse(
                success=True,
                message=f"Imported {products_imported} products and {observations_imported} price observations",
                products_imported=products_imported,
                observations_imported=observations_imported,
                errors=errors
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

@router.get("/template")
async def get_import_template():
    """Get CSV import template format."""
    template = """product_name,retailer,price,currency,observed_at,availability,category,brand,url
"Sony WH-1000XM6","Amazon",29999,"INR","2024-01-15T10:30:00Z","in_stock","Electronics","Sony","https://amazon.in/sony-wh1000xm6"
"Sony WH-1000XM6","Flipkart",28999,"INR","2024-01-15T11:00:00Z","in_stock","Electronics","Sony","https://flipkart.com/sony-wh1000xm6"
"""
    return {"template": template, "description": "CSV format for importing price data"}