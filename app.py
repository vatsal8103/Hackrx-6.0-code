import streamlit as st
from components.upload import render_uploader
from components.history_download import render_history_download
from components.chatUI import render_chat
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials




security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    expected_token = "dff81943d931bfe9808c81bf6ce2103840caf6471f72691913883e6e15435f78"
    if credentials.credentials != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    return credentials.credentials

# Update your hackrx endpoint
@app.post("/hackrx/run")
async def hackrx_run(
    request: HackrxRequest, 
    token: str = Depends(verify_token)
):
    # Your existing logic here
    pass
st.set_page_config(page_title="RagBot 2.0",layout="wide")
st.title("RAG PDF Chatbot")


render_uploader()
render_chat()
render_history_download()
# Add this to your app.py
