# Edge AI Receipt Understanding System

An edge-AI based receipt processing system that combines **OpenCV, Tesseract OCR, deterministic text correction, and a local LLM** to extract structured information from receipts and generate Hindi summaries.

## Architecture

```text
Receipt Image
     ↓
OpenCV Preprocessing
     ↓
Tesseract OCR
     ↓
Regex Normalization
     ↓
Llama 3.2 3B
     ↓
Structured JSON
     ↓
Deterministic Summary
     ↓
Hindi Translation
     ↓
SQLite + gTTS
```

## Tech Stack

* Python
* OpenCV
* Tesseract OCR
* Ollama + Llama 3.2 3B
* Streamlit
* SQLite
* gTTS

## Image Preprocessing

```text
Input Image
    ↓
Red Channel Isolation
    ↓
40 px Padding
    ↓
2× Bicubic Scaling
    ↓
CLAHE (8×8)
    ↓
Otsu Thresholding
    ↓
Morphological Cleaning
    ↓
OCR
```

The red channel (`img[:, :, 2]`) improves visibility of low-contrast thermal text.
A **40 px white border** prevents characters near receipt edges from being clipped.

## OCR

Tesseract uses:

```text
OEM 3
PSM 4
preserve_interword_spaces=1
```

PSM 4 is suitable for receipts containing variable-width text and multiple column streams.

## Text Correction

OCR output is normalized before sending it to the LLM.

Examples:

```text
635    → 6.35
.0C    → .00
```

Regex-based correction improves numerical reliability and prevents the LLM from having to guess corrupted values.

## LLM Pipeline

The system uses two separate LLM operations:

```text
OCR Text
   ↓
LLM Extraction
   ↓
JSON
   ↓
Deterministic English Summary
   ↓
LLM Hindi Translation
```

Separating extraction from summarization reduces hallucination, especially with the local **3B parameter model**.

## Receipt Handling

The system distinguishes:

* Parent combo items from unpriced modifiers
* Item prices from tender/cash amounts
* Subtotal, tax and final payable amount

Tested receipt cases include:

* Multi-line restaurant/retail descriptions
* Dropped decimal values
* Faint thermal printing
* Combo meals with unpriced modifiers
* Tender lines vs. Grand Total

## Edge Deployment

```text
┌──────────────────────┐
│   Raspberry Pi 4     │
│      Client          │
│                      │
│ Image + Streamlit    │
└──────────┬───────────┘
           │ LAN
           ▼
┌──────────────────────┐
│     Workstation      │
│                      │
│ Ollama + Llama 3.2   │
└──────────────────────┘
```

The Raspberry Pi acts as the edge client while the workstation hosts the local LLM.

## Audio

Generated gTTS files are cached and linked to database records. Audio files are removed when their corresponding database records are deleted.

## Project Structure

```text
project/
├── pipeline.py
├── app.py
├── database.py
├── audio/
├── uploads/
└── requirements.txt
```

## Core Principle

**Deterministic preprocessing and validation handle accuracy-critical operations; the LLM is used only where semantic understanding and language generation are required.**
