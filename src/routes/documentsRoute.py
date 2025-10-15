from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from config.database import get_db
from controllers.documentController import upload_pdf,get_all_documents,delete_document_by_id
from services.documentService import insert_uploaded_pdf, fetch_all_uploaded_pdfs

documentsRouter = APIRouter()

@documentsRouter.post("/upload")
async def upload_pdfs(files: UploadFile = File(...),db: Session = Depends(get_db)):
    if not files:
        raise HTTPException(status_code=400, detail="No file uploaded")
    # process files ...
    if not isinstance(files, list):
        files = [files]

    return await upload_pdf(files,db)

@documentsRouter.get("/all")
async def get_pdfs(db: Session = Depends(get_db)):
    return await get_all_documents(db)

@documentsRouter.delete("/delete/{doc_id}")
async def delete_document(doc_id: int, db: Session = Depends(get_db)):
    return await delete_document_by_id(doc_id, db)


