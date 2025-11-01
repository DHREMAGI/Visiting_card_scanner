import os
import json
from fastapi import FastAPI, UploadFile, File
from dotenv import load_dotenv
import pytesseract
from PIL import Image
import easyocr
import openai

# Load API key
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Setup Tesseract path
pytesseract.pytesseract.tesseract_cmd = r"D:\user\Dhremagi\downloads\tesseract\tesseract.exe"

app = FastAPI()

# Initialize EasyOCR reader
reader = easyocr.Reader(['en'], gpu=False)

def ocr_extract(image_path):
    """Combine EasyOCR + Tesseract for reliable extraction"""
    try:
        easy_text = " ".join([line[1] for line in reader.readtext(image_path)])
        tesseract_text = pytesseract.image_to_string(Image.open(image_path))
        # Prefer EasyOCR if it returns more text
        combined_text = easy_text if len(easy_text) > len(tesseract_text) else tesseract_text
        return combined_text
    except Exception as e:
        return f"OCR Failed: {str(e)}"

def clean_text(text):
    """Clean OCR common errors"""
    replacements = {
        "WWIN": "www",
        "comcom": "com",
        "•": "",
        "\n\n": "\n"
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text

@app.post("/scan-card/")
async def scan_card(file: UploadFile = File(...)):
    temp_path = f"temp_{file.filename}"
    try:
        # Save uploaded file temporarily
        with open(temp_path, "wb") as f:
            f.write(await file.read())

        # OCR Extraction
        raw_text = ocr_extract(temp_path)
        cleaned_text = clean_text(raw_text)

        # OpenAI Prompt
        prompt = f"""
You are an intelligent assistant specialized in extracting structured JSON from business cards.

Instructions:
1. Extract fields: name, designation, company_name, emails, phone_numbers, address, city, country, website, slogan.
2. Each field must be an array, even if one value.
3. Remove irrelevant text like 'Company Logo'.
4. Combine multi-line addresses into one string.
5. Correct common OCR mistakes in emails/websites.
6. Return strictly valid JSON.

Raw OCR Text:
\"\"\"{raw_text}\"\"\"

Cleaned Text:
\"\"\"{cleaned_text}\"\"\"
"""

        # OpenAI Request
        response = openai.responses.create(
            model="gpt-5-mini",
            input=prompt
        )

        # Extract GPT output text safely
        gpt_text = ""
        if hasattr(response, "output_text"):
            gpt_text = response.output_text
        elif hasattr(response, "output") and len(response.output) > 0:
            gpt_text = response.output[0].content[0].text

        # Parse JSON
        try:
            parsed_data = json.loads(gpt_text)
        except:
            parsed_data = {"error": "Failed to parse JSON", "raw": gpt_text}

        return {"raw_text": raw_text, "parsed_data": parsed_data}

    except Exception as e:
        return {"error": str(e)}

    finally:
        # Cleanup temporary file
        if os.path.exists(temp_path):
            os.remove(temp_path)
