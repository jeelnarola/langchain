from fastapi import File, UploadFile
from typing import Dict, Any, Optional
import os
import uuid
import asyncio
from dotenv import load_dotenv
from services.documentService import (
    insert_uploaded_pdf,
    fetch_all_uploaded_pdfs,
    get_document_vector_path,
    delete_document_from_db,
)
from fastapi.responses import JSONResponse

from langchain_community.document_loaders import PyMuPDFLoader

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OpenAIEmbeddings

from sqlalchemy.orm import Session
from tools.toolmanager import refresh_vector_database

load_dotenv()  # Load environment variables

sessions: Dict[str, Dict[str, Any]] = {}  # All sessions live here
vectorstores: Dict[str, Any] = {}
default_vectorstore: Optional[Any] = None
global_vectorstore = None

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)

VECTOR_DIR = "./chroma_vectors"  # chroma vectorstore directory
os.makedirs(VECTOR_DIR, exist_ok=True)


# async def upload_pdf(files: list[UploadFile] = File(...)):
#     print("Uploading PDFs...")
#     results = []
#     global global_vectorstore
#     for file in files:
#         try:
#             # Save uploaded file temporarily
#             temp_filename = f"{uuid.uuid4()}.pdf"
#             with open(temp_filename, "wb") as f:
#                 f.write(await file.read())

#             # Load and parse PDF
#             loader = PyMuPDFLoader(temp_filename)
#             documents = loader.load()

#             if not documents or all(not doc.page_content.strip() for doc in documents):
#                 os.remove(temp_filename)
#                 results.append(
#                     {
#                         "filename": file.filename,
#                         "error": "No extractable text found in the PDF.",
#                     }
#                 )
#                 continue

#             os.remove(temp_filename)

#             # Split into chunks
#             splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
#             chunks = splitter.split_documents(documents)

#             for chunk in chunks:
#                 chunk.metadata["source"] = file.filename

#             # Add to global FAISS
#             #     if global_vectorstore is None:
#             #         global_vectorstore = FAISS.from_documents(chunks, embedding=embeddings)
#             #     else:
#             #         global_vectorstore.add_documents(chunks)

#             #     # Create a FAISS index per PDF (NO merging with global one)
#             #     pdf_vectorstore = FAISS.from_documents(chunks, embedding=embeddings)

#             #     # Save FAISS index with unique name
#             #     vector_file_name = f"{uuid.uuid4()}"
#             #     vector_file_path = os.path.join(VECTOR_DIR, vector_file_name)
#             #     pdf_vectorstore.save_local(vector_file_path)

#             #     # Insert into DB
#             #     conn = create_connection(**DB_CONFIG)
#             #     cursor = conn.cursor(dictionary=True)
#             #     cursor.execute(
#             #         "INSERT INTO uploaded_pdfs (filename, vector_path) VALUES (%s, %s)",
#             #         (file.filename, vector_file_path),
#             #     )
#             #     conn.commit()
#             #     cursor.close()
#             #     conn.close()

#             #     results.append({
#             #         "filename": file.filename,
#             #         "chunks_added": len(chunks)
#             #     })

#             # except Exception as e:
#             #     results.append({
#             #         "filename": file.filename,
#             #         "error": str(e)
#             #     })
#             if global_vectorstore is None:
#                 global_vectorstore = Chroma.from_documents(
#                     documents=chunks,
#                     embedding=embeddings,
#                     persist_directory=os.path.join(VECTOR_DIR, "global"),
#                 )
#             else:
#                 global_vectorstore.add_documents(chunks)
#                 global_vectorstore.persist()

#             vector_file_name = f"{uuid.uuid4()}"
#             vector_file_path = os.path.join(VECTOR_DIR, vector_file_name)

#             pdf_vectorstore = Chroma.from_documents(
#                 documents=chunks,
#                 embedding=embeddings,
#                 persist_directory=vector_file_path,
#             )
#             pdf_vectorstore.persist()
#             # Insert into DB
#             insert_uploaded_pdf(file.filename, vector_file_path)

#             results.append({"filename": file.filename, "chunks_added": len(chunks)})
#         except Exception as e:
#             results.append({"filename": file.filename, "error": str(e)})
#     return {"results": results}

async def upload_pdf(files: list[UploadFile], db: Session):
    print("Uploading PDFs...")
    results = []
    global global_vectorstore

    for file in files:
        try:
            temp_filename = f"{uuid.uuid4()}.pdf"
            with open(temp_filename, "wb") as f:
                f.write(await file.read())

            loader = PyMuPDFLoader(temp_filename)
            documents = loader.load()
            os.remove(temp_filename)

            if not documents or all(not doc.page_content.strip() for doc in documents):
                results.append({
                    "filename": file.filename,
                    "error": "No extractable text found in the PDF.",
                })
                continue

            splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
            chunks = splitter.split_documents(documents)
            for chunk in chunks:
                chunk.metadata["source"] = file.filename

            # Update global vectorstore
            if global_vectorstore is None:
                global_vectorstore = Chroma.from_documents(
                    documents=chunks,
                    embedding=embeddings,
                    persist_directory=os.path.join(VECTOR_DIR, "global"),
                )
            else:
                global_vectorstore.add_documents(chunks)
                global_vectorstore.persist()

            # Create per-file vector store
            vector_file_name = f"{uuid.uuid4()}"
            vector_file_path = os.path.join(VECTOR_DIR, vector_file_name)
            pdf_vectorstore = Chroma.from_documents(
                documents=chunks,
                embedding=embeddings,
                persist_directory=vector_file_path,
            )
            pdf_vectorstore.persist()

            # ✅ Insert into DB (now passing db)
            insert_uploaded_pdf(db, file.filename, vector_file_path)

            results.append({"filename": file.filename, "chunks_added": len(chunks)})

        except Exception as e:
            results.append({"filename": file.filename, "error": str(e)})

    # ✅ Refresh vector cache after upload
    refresh_vector_database()
    return {"results": results}


async def get_all_documents(db: Session):
    loop = asyncio.get_event_loop()
    rows = await loop.run_in_executor(None, fetch_all_uploaded_pdfs, db)
    documents = [
        {
            "id": row["id"],
            "filename": row["filename"],
            "vector_path": row["vector_path"],
            "created_at": row["created_at"].isoformat()
            if row["created_at"]
            else None,
        }
        for row in rows
    ]

    return {"documents": documents}


async def delete_document_by_id(doc_id: int, db: Session):
    global global_vectorstore
    try:
        vector_path = get_document_vector_path(db, doc_id)
        if not vector_path:
            return {"message": f"No document found with ID {doc_id}"}

        # Delete from database
        deleted = delete_document_from_db(db, doc_id)
        if not deleted:
            return {"message": f"Failed to delete document ID {doc_id}"}

        # Delete FAISS vector files from disk
        for ext in [".faiss", ".pkl"]:
            path = vector_path + ext
            if os.path.exists(path):
                os.remove(path)

        # Optionally clear in-memory store
        global_vectorstore = None
        
        # ✅ Refresh vector cache after deletion
        refresh_vector_database()

        return {"message": f"Deleted document ID {doc_id} and associated vector files."}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
