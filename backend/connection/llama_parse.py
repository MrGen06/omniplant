from llama_parse import LlamaParse
import os
from dotenv import load_dotenv
load_dotenv()




LLAMA_CLOUD_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")

parser = LlamaParse(
    api_key=LLAMA_CLOUD_API_KEY,
    result_type="markdown"
)

#   Function to parse PDF file using LlamaParse
 

def parse_pdf(file_path="connection/sample_50_words (1).pdf"):
    documents = parser.load_data(file_path)
    print(documents[0].text)