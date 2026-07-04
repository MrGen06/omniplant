import os
from llama_parse import LlamaParse
from dotenv import load_dotenv

# 1. DYNAMIC CONFIGURATION PATH LOOKUP
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_env_path = os.path.join(current_dir, "..", ".env")
load_dotenv(dotenv_path=backend_env_path)

LLAMA_CLOUD_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")

# Pre-initialize parser instance safely
if LLAMA_CLOUD_API_KEY:
    parser = LlamaParse(
        api_key=LLAMA_CLOUD_API_KEY,
        result_type="markdown"
    )
else:
    parser = None

def parse_pdf(file_path=None):
    """
    Parses an incoming asset manual path cleanly using LlamaParse.
    Fails gracefully to prevent boot exceptions if file tracking boundaries fail.
    """
    global parser
    if not parser:
        print("LlamaParse skipped: LLAMA_CLOUD_API_KEY missing from environment context.")
        return

    # If no path is provided, dynamically target his sample file location safely
    if file_path is None:
        file_path = "sample_50_words (1).pdf"

    # Guard clause: Check if file physically exists before calling remote service
    if not os.path.exists(file_path):
        print(f"LlamaParse execution halted: Target payload file not found at: {file_path}")
        return

    try:
        print(f"Analyzing data streams inside: {os.path.basename(file_path)}...")
        documents = parser.load_data(file_path)
        if documents and len(documents) > 0:
            print("Extraction Complete. Sample Preview:")
            print(documents[0].text[:500]) # Safe bounds limit preview print
        else:
            print("LlamaParse returned an empty node tree.")
    except Exception as e:
        print(f"Critical exception encountered during processing: {e}")