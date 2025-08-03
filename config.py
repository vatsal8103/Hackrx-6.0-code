# API_URL = "http://127.0.0.1:8000"  # Change this when deploying
# config.py
import os
from dotenv import load_dotenv
API_URL="https://ragbot-2-0.onrender.com"

load_dotenv()

class Config:
    # Your existing config
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    
    # Add these for hackathon compatibility
    FAISS_INDEX_PATH = "data/faiss_index"
    VECTOR_DIMENSION = 384  # for sentence-transformers all-MiniLM-L6-v2
    
    # Hackathon specific
    HACKATHON_AUTH_TOKEN = "dff81943d931bfe9808c81bf6ce2103840caf6471f72691913883e6e15435f78"
