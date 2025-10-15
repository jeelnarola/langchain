from sqlalchemy.orm import Session
from model.tableModel import Product

def save_product_db(db: Session, product: dict) -> bool:
    """
    Insert a product into the database.

    Args:
        db (Session): SQLAlchemy session
        product (dict): Dictionary with product fields (name, description, price, category, created_at)

    Returns:
        bool: True if inserted successfully
    """
    try:
        new_product = Product(
            name=product.get("name"),
            description=product.get("description"),
            price=product.get("price"),
            category=product.get("category", "general"),
        )
        db.add(new_product)
        db.commit()
        db.refresh(new_product)
        print(f"✅ Product saved to DB: {new_product.name}")
        return True
    except Exception as e:
        db.rollback()
        print(f"❌ Error inserting product into DB: {e}")
        raise e
