from sqlalchemy.orm import Session
from model.tableModel import UploadedPDF
from typing import List, Optional, Dict

def insert_uploaded_pdf(db: Session, filename: str, vector_path: str):
    """
    Insert uploaded PDF metadata into the database.
    
    Args:
        db (Session): SQLAlchemy session.
        filename (str): Name of the uploaded PDF file.
        vector_path (str): Path to the vector file.
    
    Returns:
        UploadedPDF: The newly created UploadedPDF object.
    """
    new_pdf = UploadedPDF(filename=filename, vector_path=vector_path)
    db.add(new_pdf)
    db.commit()
    db.refresh(new_pdf)
    return new_pdf


def fetch_all_uploaded_pdfs(db: Session) -> List[Dict]:
    """
    Fetch all uploaded PDFs from the database.
    
    Args:
        db (Session): SQLAlchemy session.
    
    Returns:
        List[Dict]: List of PDFs with id, filename, vector_path, and created_at.
    """
    pdfs = db.query(UploadedPDF).all()
    return [
        {
            "id": pdf.id,
            "filename": pdf.filename,
            "vector_path": pdf.vector_path,
            "created_at": pdf.created_at
        }
        for pdf in pdfs
    ]


def get_all_vector_paths(db: Session) -> List[str]:
    """
    Return all vector paths from uploaded PDFs.
    
    Args:
        db (Session): SQLAlchemy session.
    
    Returns:
        List[str]: List of vector paths.
    """
    paths = db.query(UploadedPDF.vector_path).all()
    return [p[0] for p in paths]


def get_document_vector_path(db: Session, doc_id: int) -> Optional[str]:
    """
    Fetch the vector path for a given document ID.
    
    Args:
        db (Session): SQLAlchemy session.
        doc_id (int): ID of the PDF document.
    
    Returns:
        Optional[str]: Vector path if exists, otherwise None.
    """
    pdf = db.query(UploadedPDF).filter(UploadedPDF.id == doc_id).first()
    return pdf.vector_path if pdf else None


def delete_document_from_db(db: Session, doc_id: int) -> bool:
    """
    Delete a document from the database by its ID.
    
    Args:
        db (Session): SQLAlchemy session.
        doc_id (int): ID of the PDF document.
    
    Returns:
        bool: True if deleted, False if not found.
    """
    pdf = db.query(UploadedPDF).filter(UploadedPDF.id == doc_id).first()
    if pdf:
        db.delete(pdf)
        db.commit()
        return True
    return False
