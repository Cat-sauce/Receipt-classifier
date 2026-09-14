# Edge-AI Receipt Understanding System

A privacy-preserving Edge-AI system for extracting structured information from real-world receipts using Computer Vision, OCR, deterministic text normalization, and a locally hosted Large Language Model.

The system is designed for deployment on a **Raspberry Pi 4**, with computationally intensive LLM inference offloaded to a **local workstation over LAN** using Ollama and Llama 3.2 3B.

---

## 1. Project Overview

Receipts are semi-structured documents containing product descriptions, quantities, prices, taxes, discounts, payment information, and final totals.

Real-world receipt images introduce several challenges:

- Low-contrast thermal printing
- Uneven illumination
- Colored pen markings
- Multi-line item descriptions
- OCR decimal-point loss
- OCR character substitutions
- Receipt content touching image boundaries
- Combo meals containing unpriced modifier items
- Confusion between tendered cash and final payable amount

To address these issues, the project uses a multi-stage hybrid architecture:

```text
Receipt Image
     │
     ▼
OpenCV Preprocessing
     │
     ├── Red-channel isolation
     ├── 40 px boundary padding
     ├── 2× bicubic upscaling
     ├── CLAHE
     ├── Otsu thresholding
     └── Morphological opening
     │
     ▼
Tesseract OCR
     │
     ▼
Deterministic OCR Normalization
     │
     ▼
Clean Receipt Text
     │
     ▼
Llama 3.2 3B
     │
     ├── Structured entity extraction
     │
     ▼
Python validation
     │
     ▼
Deterministic English summary
     │
     ▼
Llama 3.2 3B
     │
     └── Hindi translation
     │
     ▼
SQLite + gTTS
     │
     ▼
Final User Output
