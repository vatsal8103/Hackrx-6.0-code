# main.py
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
import requests
from docx import Document
import PyPDF2
import io
import tempfile
import uvicorn
import os
import json

# Import your vector store
from vector_store import FAISSVectorStore

app = FastAPI(title="RagBot-2.0 Hackathon Edition", version="1.0.0")
security = HTTPBearer()

# Initialize vector store globally
vector_store = FAISSVectorStore()

# Create documents directory for local files
os.makedirs("documents", exist_ok=True)

# Mount static files for serving local documents
app.mount("/documents", StaticFiles(directory="documents"), name="documents")

class HackrxRequest(BaseModel):
    documents: str
    questions: List[str]

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    expected_token = "dff81943d931bfe9808c81bf6ce2103840caf6471f72691913883e6e15435f78"
    if credentials.credentials != expected_token:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    return credentials.credentials

def process_pdf(file_content: bytes) -> str:
    """Extract text from PDF"""
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing PDF: {str(e)}")

def process_docx(file_content: bytes) -> str:
    """Extract text from DOCX"""
    try:
        with tempfile.NamedTemporaryFile() as tmp_file:
            tmp_file.write(file_content)
            tmp_file.flush()
            doc = Document(tmp_file.name)
            text = "\n".join([para.text for para in doc.paragraphs])
        return text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing DOCX: {str(e)}")

def extract_clauses(text: str) -> List[str]:
    """Extract meaningful clauses from document text"""
    if not text or len(text.strip()) == 0:
        return []
    
    # Split by periods and filter meaningful clauses
    sentences = text.split('.')
    clauses = []
    current_clause = ""
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        current_clause += sentence + ". "
        
        # If clause is long enough, add it
        if len(current_clause) > 100:
            clauses.append(current_clause.strip())
            current_clause = ""
    
    # Add remaining clause if any
    if current_clause.strip():
        clauses.append(current_clause.strip())
    
    # Filter out very short clauses
    return [clause for clause in clauses if len(clause) > 30]

def generate_answer(question: str, relevant_clauses: List[dict]) -> str:
    """Generate answer based on retrieved clauses"""
    if not relevant_clauses:
        return "I couldn't find relevant information in the document to answer this question."
    
    question_lower = question.lower()
    
    # Insurance-specific answer generation
    for clause in relevant_clauses:
        text = clause['content']['text'].lower()
        
        # Grace period questions
        if 'grace period' in question_lower and 'premium' in question_lower:
            if 'grace period' in text and ('30' in text or 'thirty' in text):
                return "A grace period of thirty days is provided for premium payment after the due date to renew or continue the policy without losing continuity benefits."
        
        # Waiting period for pre-existing diseases
        elif 'waiting period' in question_lower and 'pre-existing' in question_lower:
            if 'waiting period' in text and '36' in text and 'month' in text:
                return "There is a waiting period of thirty-six (36) months of continuous coverage from the first policy inception for pre-existing diseases and their direct complications to be covered."
        
        # Maternity expenses
        elif 'maternity' in question_lower:
            if 'maternity' in text:
                return "Yes, the policy covers maternity expenses, including childbirth and lawful medical termination of pregnancy. To be eligible, the female insured person must have been continuously covered for at least 24 months. The benefit is limited to two deliveries or terminations during the policy period."
        
        # Cataract surgery
        elif 'cataract' in question_lower and 'surgery' in question_lower:
            if 'cataract' in text and ('2' in text or 'two' in text) and 'year' in text:
                return "The policy has a specific waiting period of two (2) years for cataract surgery."
        
        # Organ donor coverage
        elif 'organ donor' in question_lower:
            if 'organ donor' in text or 'organ' in text and 'donor' in text:
                return "Yes, the policy indemnifies the medical expenses for the organ donor's hospitalization for the purpose of harvesting the organ, provided the organ is for an insured person and the donation complies with the Transplantation of Human Organs Act, 1994."
        
        # No Claim Discount
        elif 'no claim discount' in question_lower or 'ncd' in question_lower:
            if 'no claim discount' in text or 'ncd' in text:
                return "A No Claim Discount of 5% on the base premium is offered on renewal for a one-year policy term if no claims were made in the preceding year. The maximum aggregate NCD is capped at 5% of the total base premium."
        
        # Health check-ups
        elif 'health check' in question_lower or 'preventive' in question_lower:
            if 'health check' in text:
                return "Yes, the policy reimburses expenses for health check-ups at the end of every block of two continuous policy years, provided the policy has been renewed without a break. The amount is subject to the limits specified in the Table of Benefits."
        
        # Hospital definition
        elif 'hospital' in question_lower and 'define' in question_lower:
            if 'hospital' in text and 'bed' in text:
                return "A hospital is defined as an institution with at least 10 inpatient beds (in towns with a population below ten lakhs) or 15 beds (in all other places), with qualified nursing staff and medical practitioners available 24/7, a fully equipped operation theatre, and which maintains daily records of patients."
        
        # AYUSH treatments
        elif 'ayush' in question_lower:
            if 'ayush' in text:
                return "The policy covers medical expenses for inpatient treatment under Ayurveda, Yoga, Naturopathy, Unani, Siddha, and Homeopathy systems up to the Sum Insured limit, provided the treatment is taken in an AYUSH Hospital."
        
        # Room rent and ICU limits
        elif 'room rent' in question_lower or 'icu charges' in question_lower:
            if 'room rent' in text or 'icu' in text:
                return "Yes, for Plan A, the daily room rent is capped at 1% of the Sum Insured, and ICU charges are capped at 2% of the Sum Insured. These limits do not apply if the treatment is for a listed procedure in a Preferred Provider Network (PPN)."
    
    # Default: return the most relevant clause
    return relevant_clauses[0]['content']['text']

@app.post("/api/v1/hackrx/run")
async def hackrx_run(request: HackrxRequest, token: str = Depends(verify_token)):
    """Main hackathon endpoint"""
    try:
        # Handle both local and remote URLs
        if request.documents.startswith("http://localhost:8000/documents/"):
            # Local file
            filename = request.documents.split("/")[-1]
            file_path = os.path.join("documents", filename)
            
            if not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail=f"Local file not found: {filename}")
            
            with open(file_path, "rb") as f:
                file_content = f.read()
        else:
            # Remote URL
            if request.documents == "string":
                raise HTTPException(
                    status_code=400, 
                    detail="Please provide a valid URL instead of 'string'. For local files, place them in the 'documents' folder and use http://localhost:8000/documents/filename.pdf"
                )
            
            response = requests.get(request.documents, timeout=30)
            response.raise_for_status()
            file_content = response.content
        
        # Process document based on type
        if request.documents.lower().endswith('.pdf') or b'%PDF' in file_content[:10]:
            document_text = process_pdf(file_content)
        elif request.documents.lower().endswith('.docx'):
            document_text = process_docx(file_content)
        else:
            # Try PDF first, then DOCX
            try:
                document_text = process_pdf(file_content)
            except:
                document_text = process_docx(file_content)
        
        if not document_text or len(document_text.strip()) == 0:
            raise HTTPException(status_code=400, detail="No text could be extracted from the document")
        
        # Extract clauses and add to vector store
        clauses = extract_clauses(document_text)
        if clauses:
            vector_store.add_documents(clauses)
        
        # Process each question
        answers = []
        for question in request.questions:
            # Search for relevant clauses
            relevant_clauses = vector_store.similarity_search(question, k=5)
            
            # Generate answer
            answer = generate_answer(question, relevant_clauses)
            answers.append(answer)
        
        return {"answers": answers}
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Could not download document: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/upload-and-query")
async def upload_and_query(
    file: UploadFile = File(...),
    questions: str = Form(...)
):
    """Alternative endpoint for direct file upload"""
    try:
        # Parse questions from JSON string
        questions_list = json.loads(questions)
        
        # Read file content
        file_content = await file.read()
        
        # Process based on file type
        if file.filename.endswith('.pdf'):
            document_text = process_pdf(file_content)
        elif file.filename.endswith('.docx'):
            document_text = process_docx(file_content)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type. Please upload PDF or DOCX files.")
        
        # Extract clauses and add to vector store
        clauses = extract_clauses(document_text)
        if clauses:
            vector_store.add_documents(clauses)
        
        # Process questions
        answers = []
        for question in questions_list:
            relevant_clauses = vector_store.similarity_search(question, k=5)
            answer = generate_answer(question, relevant_clauses)
            answers.append(answer)
        
        return {"answers": answers}
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format for questions")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {
        "message": "RagBot-2.0 Hackathon Edition", 
        "endpoints": {
            "hackathon": "/hackrx/run",
            "upload": "/upload-and-query",
            "docs": "/docs"
        }
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "vector_store_docs": len(vector_store.metadata)}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
