# Edge-AI Receipt Understanding System
## Technical Presentation and Architectural Specification Report

**Project Domain:** Edge AI, Computer Vision, OCR, Local LLM Inference, Intelligent Document Understanding  
**Primary Objective:** Robust extraction and spoken summarization of information from heterogeneous retail and restaurant receipts  
**Target Deployment:** Raspberry Pi 4 edge client + LAN-connected workstation hosting Ollama/Llama 3.2 3B  
**Document Type:** Academic Minor Project — Technical Architecture and Evaluation Specification

---

## 1. Executive Summary

This project implements a privacy-preserving, edge-oriented receipt understanding pipeline that converts photographs or scans of receipts into structured financial metadata and natural-language summaries.

The system deliberately separates deterministic computer-vision/OCR processing from probabilistic language-model reasoning. OpenCV performs image conditioning, Tesseract performs text recognition, deterministic regular expressions repair recurrent OCR defects, and a local Llama 3.2 3B model performs constrained entity extraction followed by independent Hindi summary generation. Streamlit provides the application interface, SQLite provides persistent structured storage, and gTTS provides audio output with cache management.

The architecture is designed around three engineering principles:

1. **Recover text before interpreting it.**
2. **Apply deterministic corrections before invoking a probabilistic model.**
3. **Constrain the local LLM to extraction/translation tasks rather than allowing it to reconstruct receipt arithmetic or invent missing entities.**

The resulting architecture is suitable for low-cost edge deployment because computationally inexpensive preprocessing and OCR can execute on the Raspberry Pi 4, while the relatively expensive 3B-parameter LLM is offloaded over a trusted local-area network to a workstation running Ollama.

---

# 2. Problem Definition

Receipts are semi-structured documents rather than conventional paragraphs. They contain:

- variable-width item descriptions,
- quantities and unit prices,
- wrapped descriptions,
- tax lines,
- discounts,
- subtotal and grand-total fields,
- tender/payment fields,
- merchant/contact information,
- low-contrast thermal typography,
- background artifacts,
- colored pen annotations,
- OCR-sensitive decimal points.

A conventional OCR-only system may produce text that is visually plausible but semantically incorrect. Typical failures include:

- `6.35` → `635`,
- `.00` → `.0C`,
- omission of the lowest lines of a receipt,
- confusion between tendered cash and payable total,
- treating combo modifiers as independent purchased items,
- failure to recover faint thermal characters.

The project therefore treats receipt understanding as a **multi-stage perception-to-structure problem** rather than as a single LLM prompt.

---

# 3. System Requirements

## 3.1 Functional Requirements

The system shall:

1. Accept a receipt image.
2. Perform image preprocessing.
3. Recover receipt text using Tesseract OCR.
4. Remove irrelevant OCR lines.
5. Deterministically normalize recurrent OCR errors.
6. Extract:
   - merchant,
   - purchased items,
   - item count,
   - total amount,
   - category,
   - date,
   - contact information,
   - return policy.
7. Produce an English summary.
8. Produce a Hindi Devanagari summary.
9. Support receipt-specific question answering.
10. Persist structured receipt data using SQLite.
11. Provide audio output using gTTS.
12. Cache generated audio to avoid unnecessary regeneration.
13. Purge audio when the associated database record is removed.
14. Support deployment with LLM inference on a LAN workstation.

## 3.2 Non-Functional Requirements

The system should prioritize:

- deterministic preprocessing,
- reproducibility,
- local/private inference,
- low deployment cost,
- graceful failure,
- semantic separation of extraction and generation,
- auditable intermediate OCR output,
- compatibility with heterogeneous receipt layouts.

---

# 4. Technology Stack

| Layer | Technology |
|---|---|
| Programming Language | Python |
| Image Processing | OpenCV |
| Numerical Processing | NumPy |
| OCR | Tesseract / PyTesseract |
| LLM Runtime | Ollama |
| Local Model | Llama 3.2 3B (`llama3.2:3b`) |
| HTTP Client | Requests |
| UI | Streamlit |
| Database | SQLite3 |
| Text-to-Speech | gTTS |
| Structured Serialization | JSON |
| Deployment Target | Raspberry Pi 4 |
| LLM Host | Local workstation |
| Network | Local LAN |

The LLM is configured with:

```text
temperature = 0.0
stream = false
format = json
```

for extraction. Temperature zero does not mathematically guarantee identical behavior under every inference/runtime configuration, but it minimizes sampling variability and is appropriate for deterministic-style extraction.

---

# 5. High-Level Architecture

```text
                         EDGE / CLIENT SIDE
┌────────────────────────────────────────────────────────────────────┐
│ Raspberry Pi 4                                                     │
│                                                                    │
│  Camera / Image Upload                                              │
│          │                                                         │
│          ▼                                                         │
│  OpenCV Preprocessing                                               │
│  ├── BGR → Red Channel                                              │
│  ├── 40 px Boundary Padding                                         │
│  ├── 2× Cubic Upscaling                                              │
│  ├── CLAHE (8×8)                                                     │
│  ├── Otsu Thresholding                                              │
│  └── Morphological Opening                                          │
│          │                                                         │
│          ▼                                                         │
│  Tesseract OCR (--oem 3 --psm 4)                                   │
│          │                                                         │
│          ▼                                                         │
│  OCR Line Filtering                                                  │
│          │                                                         │
│          ▼                                                         │
│  Deterministic Regex Normalization                                  │
│          │                                                         │
│          ▼                                                         │
│  Clean Receipt Text                                                  │
└──────────┼─────────────────────────────────────────────────────────┘
           │
           │ HTTP / JSON over trusted local LAN
           ▼
┌────────────────────────────────────────────────────────────────────┐
│ Workstation                                                         │
│                                                                    │
│  Ollama API :11434                                                  │
│          │                                                         │
│          ▼                                                         │
│  Llama 3.2 3B                                                       │
│  ├── Phase 1: Structured Entity Extraction                          │
│  └── Phase 2: Hindi Summary Generation                              │
│                                                                    │
└──────────┼─────────────────────────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────────────────────────────────┐
│ Application / Persistence                                           │
│                                                                    │
│  Streamlit UI                                                       │
│       │                                                            │
│       ├──────────────► SQLite                                       │
│       │                 ├── receipt metadata                         │
│       │                 └── receipt records                          │
│       │                                                            │
│       └──────────────► gTTS                                         │
│                         └── audio cache                              │
│                                  │                                 │
│                                  └── DB-bound purge                 │
└────────────────────────────────────────────────────────────────────┘
```

---

# 6. End-to-End Multi-Stage Pipeline

```text
[Receipt Image]
       │
       ▼
┌──────────────────────┐
│ Image Acquisition    │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Red Channel          │
│ Isolation             │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ +40 px Canvas Margin │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 2× Bicubic Scaling   │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ CLAHE 8×8            │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Otsu Threshold       │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Morphological Open   │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Tesseract OCR        │
│ PSM 4                │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Line Filtering       │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Regex Normalization  │
│ Decimal / OCR Repair │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Clean OCR Text       │
└──────────┬───────────┘
           ▼
┌────────────────────────────┐
│ LLM Phase 1                │
│ Structured Extraction      │
└────────────┬───────────────┘
             ▼
┌────────────────────────────┐
│ Deterministic Postprocess  │
│ Types / Lists / Defaults   │
└────────────┬───────────────┘
             ▼
┌────────────────────────────┐
│ LLM Phase 2                │
│ Hindi Translation/Summary  │
└────────────┬───────────────┘
             ▼
┌────────────────────────────┐
│ SQLite Persistence          │
└────────────┬───────────────┘
             ▼
┌────────────────────────────┐
│ gTTS Generation + Cache     │
└────────────┬───────────────┘
             ▼
       [User Output]
```

---

# 7. Computer Vision Preprocessing Architecture

The preprocessing function is:

```python
def preprocess_image(image_path: str):
    img = cv2.imread(image_path)

    red = img[:, :, 2]

    padded = cv2.copyMakeBorder(
        red, 40, 40, 40, 40,
        cv2.BORDER_CONSTANT,
        value=[255]
    )

    scaled = cv2.resize(
        padded,
        None,
        fx=2.0,
        fy=2.0,
        interpolation=cv2.INTER_CUBIC
    )

    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8)
    )

    enhanced = clahe.apply(scaled)

    _, thresh = cv2.threshold(
        enhanced,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    clean_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (2, 2)
    )

    cleaned = cv2.morphologyEx(
        thresh,
        cv2.MORPH_OPEN,
        clean_kernel
    )

    return cleaned
```

## 7.1 Processing Flow

```text
BGR Image
   │
   ├─────────────── Blue channel
   ├─────────────── Green channel
   └─────────────── Red channel ──────────────┐
                                               ▼
                                      +40 px white border
                                               │
                                               ▼
                                      2× bicubic resize
                                               │
                                               ▼
                                      CLAHE, 8×8 tiles
                                               │
                                               ▼
                                      Otsu global threshold
                                               │
                                               ▼
                                      2×2 morphological opening
                                               │
                                               ▼
                                      OCR-ready binary image
```

---

# 8. Red-Channel Isolation

## 8.1 OpenCV Channel Ordering

OpenCV loads standard color images in **BGR** order:

```text
img[:, :, 0] → Blue
img[:, :, 1] → Green
img[:, :, 2] → Red
```

Therefore:

```python
red = img[:, :, 2]
```

selects the red channel.

## 8.2 Why This Can Improve Thermal Receipt OCR

Thermal receipt text is frequently dark gray/black against a lightly colored or nonuniform substrate. Pen markings, scanner artifacts, and colored annotations may have different spectral responses across RGB channels.

For a pixel:

\[
I(x,y) = [B(x,y),G(x,y),R(x,y)]
\]

the preprocessing selects:

\[
I_R(x,y)=R(x,y)
\]

rather than forming a conventional luminance estimate such as:

\[
Y = 0.299R + 0.587G + 0.114B
\]

This can improve class separability when the unwanted pen/background signal has relatively high response in the red channel while the thermal print remains sufficiently dark.

The practical objective is:

\[
\Delta I_R =
\left|\mu_{background,R}-\mu_{text,R}\right|
\]

being sufficiently large for subsequent contrast enhancement and thresholding.

### Important engineering qualification

Red-channel isolation is **not a universal pen-removal algorithm**. Its success depends on the ink/substrate spectral characteristics and the camera/scanner. It is a deliberately selected channel heuristic for the tested receipt population. A production-generalized system should evaluate channel separability automatically or compare multiple grayscale/channel representations.

---

# 9. 40-Pixel Canvas Boundary Padding

The implementation adds:

```python
cv2.copyMakeBorder(
    red,
    40, 40, 40, 40,
    cv2.BORDER_CONSTANT,
    value=[255]
)
```

The padding creates a white boundary around the document before scaling.

## 9.1 Mathematical Motivation

Let the original image domain be:

\[
\Omega=[0,W)\times[0,H)
\]

After padding by \(p=40\):

\[
\Omega'=[-40,W+40)\times[-40,H+40)
\]

The receipt content is therefore no longer directly adjacent to the image boundary.

OCR segmentation algorithms depend on connected components, whitespace, baselines and local bounding boxes. Characters touching the image boundary have incomplete contextual margins and can be clipped during segmentation or normalization.

The added border supplies an explicit background region:

```text
Before:

|Receipt text starts here
|------------------------

After:

+--------------------------------+
|                                |
|  Receipt text starts here      |
|  --------------------------    |
|                                |
+--------------------------------+
      40 px contextual margin
```

The padding does **not** add information to the receipt. Instead, it changes the segmentation boundary conditions.

## 9.2 Why 40 px?

The value is an empirical engineering parameter selected to provide sufficient whitespace without unnecessarily increasing the image size. It should be regarded as a tunable hyperparameter rather than a universal OCR constant.

In the thermal restaurant benchmark, boundary padding was particularly important for recovering the lower portion of the document and restoring the bottom:

```text
Grand Total ₹ 5348.00
```

field.

---

# 10. 2× Bicubic Upscaling

The image is enlarged by:

```python
fx=2.0
fy=2.0
interpolation=cv2.INTER_CUBIC
```

For a low-resolution source, enlargement increases the number of pixels representing each glyph.

Bicubic interpolation estimates a new pixel using a local neighborhood and a cubic weighting function. Compared with nearest-neighbor interpolation, it produces smoother character contours; compared with simple bilinear interpolation, it can preserve local intensity transitions more effectively.

The goal is not to create new textual information, but to provide Tesseract with a better sampled representation of existing strokes.

---

# 11. CLAHE: Local Contrast Enhancement

The implementation uses:

```python
cv2.createCLAHE(
    clipLimit=2.0,
    tileGridSize=(8, 8)
)
```

CLAHE means **Contrast Limited Adaptive Histogram Equalization**.

## 11.1 Global Histogram Equalization Limitation

Global histogram equalization applies one transformation to the complete image:

\[
s=T(r)
\]

where \(T\) is derived from the global intensity distribution.

For a receipt containing:

- dark printed regions,
- bright paper,
- faint thermal regions,
- shadows,
- illumination gradients,

one global mapping may over-enhance strong regions while leaving weak local text insufficiently separated.

## 11.2 CLAHE Principle

CLAHE partitions the image into local tiles.

With an \(8\times8\) grid, each tile receives its own local histogram transformation:

```text
+-----+-----+-----+-----+-----+-----+-----+-----+
| T11 | T12 | T13 | T14 | T15 | T16 | T17 | T18 |
+-----+-----+-----+-----+-----+-----+-----+-----+
| T21 | T22 | T23 | T24 | T25 | T26 | T27 | T28 |
+-----+-----+-----+-----+-----+-----+-----+-----+
| ...                                              
+--------------------------------------------------+
```

The transformations are interpolated between neighboring tiles, reducing abrupt boundaries.

The contrast limit prevents histogram bins from accumulating excessive mass and amplifying noise uncontrollably.

## 11.3 Why 8×8?

The \(8\times8\) configuration gives a useful compromise:

- larger tiles: stronger local context, less localized enhancement;
- smaller tiles: more localized contrast, greater risk of amplifying noise.

For heterogeneous receipt photographs, \(8\times8\) provides sufficient spatial locality for faint thermal text while retaining neighborhood context.

---

# 12. Otsu Thresholding vs. Fixed/Global Thresholding

The implementation uses:

```python
_, thresh = cv2.threshold(
    enhanced,
    0,
    255,
    cv2.THRESH_BINARY + cv2.THRESH_OTSU
)
```

Otsu's method selects a threshold \(t\) by maximizing between-class variance.

For foreground/background classes \(C_0,C_1\):

\[
\sigma_B^2(t)=
\omega_0(t)\omega_1(t)
[\mu_0(t)-\mu_1(t)]^2
\]

The selected threshold is:

\[
t^*=\arg\max_t \sigma_B^2(t)
\]

This is preferable to hard-coding a threshold such as 127 when image exposure and thermal contrast vary.

### Why CLAHE + Otsu?

The two operations address different problems:

```text
CLAHE
  ↓
Improve local intensity separability
  ↓
Otsu
  ↓
Find a global threshold on the improved distribution
```

CLAHE does not itself binarize the image. Otsu does not locally enhance weak text. Their combination therefore provides complementary functions.

---

# 13. Morphological Opening

The final preprocessing step is:

```python
clean_kernel = cv2.getStructuringElement(
    cv2.MORPH_RECT,
    (2, 2)
)

cleaned = cv2.morphologyEx(
    thresh,
    cv2.MORPH_OPEN,
    clean_kernel
)
```

Morphological opening is:

\[
A\circ B=(A\ominus B)\oplus B
\]

where:

- \(\ominus\) = erosion,
- \(\oplus\) = dilation.

The small \(2\times2\) kernel suppresses isolated binary noise while retaining most connected character strokes.

An excessively large kernel could destroy thin thermal glyph features; hence the intentionally conservative kernel size.

---

# 14. OCR Architecture

Tesseract is configured as:

```text
--oem 3
--psm 4
-c tessedit_char_blacklist=|~_§«»
-c preserve_interword_spaces=1
```

## 14.1 OCR Engine Mode

`--oem 3` requests Tesseract's default automatic OCR engine selection.

## 14.2 Page Segmentation Mode 4

`--psm 4` is selected because receipts commonly behave as a block of text with multiple horizontal lines and variable-width regions rather than as a single uniform paragraph.

Conceptually:

```text
ITEM NAME                 QTY       PRICE
Long item description      1         635
Additional description               120
------------------------------------------
SUB TOTAL                           755
CGST                                37.75
SGST                                37.75
GRAND TOTAL                        830.50
```

A receipt can contain multiple logical columns without having a rigid newspaper-style grid.

PSM 4 therefore provides a practical segmentation strategy for the observed receipt population.

## 14.3 Interword Space Preservation

```text
preserve_interword_spaces=1
```

helps retain horizontal spacing. This is useful because receipt semantics are partially encoded spatially:

```text
Description              Quantity       Amount
```

Spacing can provide additional clues for downstream interpretation.

## 14.4 OCR Line Filtering

The implementation retains only lines containing at least one alphanumeric character:

```python
if re.search(r'[a-zA-Z0-9]', line):
    clean_lines.append(line)
```

This removes empty lines and many punctuation-only OCR artifacts before semantic processing.

---

# 15. Deterministic OCR Normalization

LLMs should not be expected to repair every predictable OCR defect. Recurrent OCR errors are better handled with deterministic transformations.

The normalization stage therefore operates before LLM extraction.

---

# 16. Currency Character Repair

The implementation contains:

```python
line = re.sub(
    r'(\d+\.\d)[Cc€G]',
    r'\g<1>0',
    line
)
```

This targets OCR outputs such as:

```text
5348.0C
```

and converts the trailing character into a zero:

```text
5348.00
```

The underlying observation is that OCR can confuse visually similar glyphs:

```text
0 ↔ O ↔ C
```

especially in low-resolution thermal print.

The repair is deliberately narrow rather than using unrestricted character substitution.

---

# 17. Dropped Decimal Normalization

A recurrent receipt OCR failure is:

```text
6.35 → 635
```

The code detects amount-like fields associated with:

```text
Total
Payable
Amount
Incl
GST
```

and, when no decimal point is present, transforms a three- or four-digit integer-like amount:

\[
x=d_1d_2...d_n
\]

into:

\[
d_1d_2...d_{n-2}.d_{n-1}d_n
\]

For:

```text
635
```

this gives:

```text
6.35
```

For:

```text
534800
```

the same mathematical operation would yield:

```text
5348.00
```

However, the current regex restricts the matched number to 3–4 digits, so it is intentionally conservative and does **not** implement a universal currency parser.

## 17.1 Why Deterministic Repair Is Important

A language model can infer that:

```text
Grand Total 635
```

might mean `6.35`, but that inference is not guaranteed to be correct.

A deterministic rule makes the correction:

- repeatable,
- testable,
- auditable,
- independent of model sampling,
- computationally inexpensive.

---

# 18. Total Estimation Fallback

If no explicit `Grand Total` or `Net Total` is detected, the implementation can derive:

\[
T_{estimated}
=
Subtotal+\sum Tax
\]

when a subtotal and recognizable tax fields exist.

The implementation:

```python
estimated_total = round(
    subtotal_val + (tax_sum if tax_sum > 0 else 0.0),
    2
)
```

and appends:

```text
Grand Total: <estimated_total>
```

This should be interpreted as a **fallback estimate**, not as proof that the merchant's final payable amount equals subtotal plus the detected taxes. Discounts, rounding adjustments, service charges, credits, or other components may exist.

---

# 19. Two-Phase LLM Extraction and Deterministic Summary Architecture

```text
                 CLEAN OCR TEXT
                       │
                       ▼
             ┌─────────────────────┐
             │ LLM PHASE 1         │
             │ Structured Extract  │
             │                     │
             │ merchant            │
             │ items[]             │
             │ total_items         │
             │ total_amount        │
             │ category            │
             │ contact_info        │
             │ return_policy       │
             │ date                │
             └──────────┬──────────┘
                        │
                        ▼
             ┌─────────────────────┐
             │ Deterministic       │
             │ Python Validation   │
             │                     │
             │ type normalization  │
             │ list normalization  │
             │ fallback defaults    │
             │ item-count fallback  │
             └──────────┬──────────┘
                        │
                        ▼
             ┌─────────────────────┐
             │ Deterministic       │
             │ English Sentence    │
             └──────────┬──────────┘
                        │
                        ▼
             ┌─────────────────────┐
             │ LLM PHASE 2         │
             │ Hindi Translation    │
             │ Devanagari Only      │
             └──────────┬──────────┘
                        │
                        ▼
                 FINAL OUTPUT
```

---

# 20. Why Entity Extraction Is Decoupled From Summary Writing

A 3B local model has substantially less representational and reasoning capacity than large server-class models. Combining:

- OCR interpretation,
- arithmetic reasoning,
- entity extraction,
- item deduplication,
- category assignment,
- summary generation,
- translation

into one unconstrained prompt increases the probability of **token hallucination**.

A particularly dangerous failure mode is:

```text
OCR:
Grand Total 5348.00

One-stage LLM:
"The total amount is ₹ 5,348 and the restaurant charged..."
```

The model may add plausible but unsupported context.

The architecture therefore enforces:

```text
Evidence
  ↓
Structured extraction
  ↓
Validated fields
  ↓
Template-generated English sentence
  ↓
Translation only
```

The English summary is constructed deterministically:

```python
english_summary = (
    f"The bill is from {merchant}, the bill states total {count} item(s) were bought, "
    f"the items are as follows: {items_str}, and the total amount is {total}."
)
```

The LLM's second task is then narrowly defined as translation.

This creates a **semantic firewall**:

```text
Receipt evidence ──► extraction model
                         │
                         ▼
                 structured facts
                         │
                         ▼
                deterministic text
                         │
                         ▼
                 translation model
```

The second model invocation cannot independently decide which products or amount should exist; it receives a sentence whose factual content has already been constructed by the application.

---

# 21. Structured Extraction Contract

The LLM is instructed to produce:

```json
{
  "merchant": "Merchant Name",
  "items": ["Item A", "Item B"],
  "total_items": 0,
  "total_amount": 0.0,
  "category": "One Category from the rules",
  "contact_info": "Contact details",
  "return_policy": "Policy or Not stated",
  "date": "Date"
}
```

The extraction prompt explicitly defines six important semantic constraints.

## 21.1 Category Classification

The allowed categories are:

```text
Food & Beverage
Retail & Groceries
Fuel & Transport
Utilities & Services
Healthcare
Other
```

The model is instructed not to default to Food & Beverage.

This is important because the same receipt-processing system must distinguish:

```text
McDonald's      → Food & Beverage
Hardware store  → Retail & Groceries
Petrol pump     → Fuel & Transport
Pharmacy        → Healthcare
```

## 21.2 Parent Item vs Modifier

Combo receipts create a semantic hierarchy:

```text
Parent:
Spicy Deluxe Combo                 ₹ 635

Children / choices:
M Coke
M Fries
```

The child entries may have no independent price.

The extraction policy therefore maps:

```text
Spicy Deluxe Combo
├── M Coke
└── M Fries
```

to one purchased parent item.

This prevents `total_items` from being inflated.

---

# 22. McDonald's Benchmark: Parent vs Modifier Semantics

The fast-food benchmark tests two difficult ambiguities.

### Ambiguity A — Combo hierarchy

```text
Combo Meal
   ├── Burger
   ├── Coke
   └── Fries
```

The Coke and Fries may be printed as selectable components but have no separate amount.

The expected semantic interpretation is:

```text
1 purchased combo
```

rather than:

```text
3 purchased items
```

### Ambiguity B — Tender vs Grand Total

A receipt may contain:

```text
Grand Total       ₹ xxx.xx
Cash              ₹ xxx.xx
Change             ₹ xx.xx
```

The amount of cash tendered is not the purchase total.

The extraction prompt explicitly instructs the model:

```text
Disregard tender/cash paid amounts.
```

Therefore the semantic target is:

```text
purchase_total = Grand/Net/Payable Total
```

not:

```text
purchase_total = Cash Tendered
```

This is an important distinction for financial correctness.

---

# 23. Hardware Receipt Benchmark — Cross Channel Network

The Cross Channel Network receipt tests:

1. multi-line item descriptions,
2. dropped decimal points,
3. separation of tender/payment information.

Representative OCR problem:

```text
ITEM DESCRIPTION             635
```

where the intended monetary representation is:

```text
6.35
```

The deterministic normalization layer repairs the recurrent decimal-loss pattern before the LLM receives the text.

## 23.1 Multi-Line Description

Receipt formatting may produce:

```text
Long hardware component description
additional specification text          6.35
```

The semantic extractor must not automatically treat the second line as a new item.

This demonstrates why raw OCR line segmentation and semantic item segmentation are separate problems.

## 23.2 Tender Isolation

Payment information is treated as transaction metadata rather than an item price.

The model's extraction contract explicitly distinguishes:

```text
Total Payable / Grand Total
```

from:

```text
Cash / Tender / Amount Received
```

This benchmark therefore validates both OCR normalization and semantic financial interpretation.

---

# 24. Thermal Restaurant Benchmark — Rumours / Big Bull Entertainment

The thermal restaurant bill provides a substantially different visual condition:

- faint typography,
- low contrast,
- thermal-print degradation,
- critical information close to the lower image boundary.

The preprocessing chain is particularly important:

```text
Red channel
    ↓
40 px padding
    ↓
2× enlargement
    ↓
CLAHE 8×8
    ↓
Otsu
    ↓
Morphological opening
    ↓
Tesseract
```

The boundary padding addresses a key failure mode: the final lines may be partially clipped or poorly segmented when the receipt terminates immediately at the image boundary.

The benchmark specifically validates recovery of:

```text
Grand Total ₹ 5348.00
```

The significance of this test is greater than simply recovering a single line. The Grand Total is a **high-value semantic field**, so losing the bottom region has a disproportionate impact on system correctness.

---

# 25. Benchmark Matrix

| Test Case | Primary Difficulty | Relevant Pipeline Component | Expected Semantic Outcome |
|---|---|---|---|
| Cross Channel Network | Wrapped descriptions | OCR + LLM item grouping | Preserve parent item identity |
| Cross Channel Network | Dropped decimals | Regex normalization | Recover amount representation such as `635 → 6.35` where rule applies |
| Cross Channel Network | Tender/payment lines | LLM extraction rules | Do not confuse tender with payable total |
| McDonald's | Combo hierarchy | LLM extraction rules | Count parent meals, not unpriced modifiers |
| McDonald's | Coke/Fries modifier lines | Semantic grouping | Treat as combo components |
| McDonald's | Tender vs grand total | Structured extraction | Select final payable amount |
| Rumours / Big Bull Entertainment | Faint thermal text | Red channel + CLAHE | Improve character visibility |
| Rumours / Big Bull Entertainment | Bottom boundary | 40 px padding | Recover lower receipt content |
| Rumours / Big Bull Entertainment | Grand Total | OCR + normalization | Recover `₹ 5348.00` |

### Evaluation note

The supplied project evidence establishes these as real test cases and describes their observed failure/recovery modes. No fabricated latency, accuracy percentage, or OCR-confidence score is reported here because those numerical measurements were not supplied in the project source.

For an academic evaluation, quantitative metrics should be added from a repeatable benchmark run.

---

# 26. Recommended Quantitative Evaluation Protocol

A rigorous evaluation should construct a ground-truth table:

| Receipt | Field | Ground Truth | System Output | Correct? |
|---|---|---|---|---|
| Cross Channel Network | Merchant | Ground truth | Output | Yes/No |
| Cross Channel Network | Total | Ground truth | Output | Yes/No |
| McDonald's | Total items | Ground truth | Output | Yes/No |
| McDonald's | Total amount | Ground truth | Output | Yes/No |
| Rumours | Grand Total | ₹5348.00 | Output | Yes/No |

Recommended metrics:

## 26.1 Field Accuracy

\[
Accuracy_f=
\frac{\text{correct predictions for field }f}
{\text{total test cases}}
\]

## 26.2 Exact Amount Accuracy

\[
Accuracy_{amount}=
\frac{\#\text{exactly correct monetary totals}}
{\#\text{receipts}}
\]

This should use numeric comparison after standardized currency formatting.

## 26.3 Item Precision / Recall

For item extraction:

\[
Precision=\frac{TP}{TP+FP}
\]

\[
Recall=\frac{TP}{TP+FN}
\]

and:

\[
F1=2\frac{Precision\cdot Recall}{Precision+Recall}
\]

## 26.4 End-to-End Success Rate

A strict metric can define success as:

```text
merchant correct
AND
items semantically correct
AND
total amount correct
AND
category correct
```

This is intentionally stricter than per-field accuracy.

---

# 27. Edge Deployment Topology

```text
                    LOCAL LAN
┌───────────────────────────────────────────────────────────────┐
│                                                               │
│  ┌──────────────────────┐          ┌────────────────────────┐ │
│  │ Raspberry Pi 4       │          │ Workstation            │ │
│  │                      │          │                        │ │
│  │ Streamlit / Client   │          │ Ollama                 │ │
│  │ OpenCV               │  HTTP    │ :11434                 │ │
│  │ Tesseract            │─────────►│                        │ │
│  │ Regex normalization  │          │ llama3.2:3b             │ │
│  │ SQLite               │◄─────────│                        │ │
│  │ gTTS/cache*          │          │                        │ │
│  └──────────────────────┘          └────────────────────────┘ │
│                                                               │
└───────────────────────────────────────────────────────────────┘

* Placement of gTTS depends on deployment configuration.
```

## 27.1 Why Offload the LLM?

A Raspberry Pi 4 is appropriate for:

- image acquisition,
- OpenCV,
- OCR,
- lightweight Python services,
- local storage,
- user-interface control.

A 3B-parameter LLM is substantially more computationally demanding.

The architecture therefore follows:

\[
\text{Edge Perception} + \text{LAN LLM Offload}
\]

rather than attempting to run the complete inference workload on the Pi.

This preserves the edge-device advantages while avoiding unnecessary local compute pressure.

---

# 28. Network API Contract

The current source uses:

```python
OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"
```

for a same-machine configuration.

For LAN deployment, the logical endpoint changes to the workstation's LAN address, for example:

```text
http://<WORKSTATION_LAN_IP>:11434/api/generate
```

The application sends JSON such as:

```json
{
  "model": "llama3.2:3b",
  "prompt": "...",
  "format": "json",
  "stream": false,
  "options": {
    "temperature": 0.0
  }
}
```

A LAN deployment should additionally enforce:

- firewall restriction,
- trusted network,
- no exposure of Ollama directly to the public Internet,
- request timeout,
- connection-failure handling.

---

# 29. Failure Handling

The source uses explicit request timeouts:

```python
timeout=45
```

for extraction and:

```python
timeout=30
```

for translation/question answering.

The pipeline therefore avoids indefinite blocking.

If extraction fails:

```python
data = {}
```

and application-level defaults are applied:

```text
merchant → Unknown Store
category → Other
date → N/A
return_policy → Not stated
```

This is preferable to crashing the entire interface, although a production system should expose an explicit processing-error state rather than silently treating a model failure as an ordinary missing field.

---

# 30. JSON Parsing as a Reliability Boundary

The extraction request uses:

```python
"format": "json"
```

and the response is parsed with:

```python
json.loads(raw_resp)
```

This creates a machine-readable contract between the LLM and Python.

The architecture can be represented as:

```text
Natural Language Evidence
          │
          ▼
      LLM reasoning
          │
          ▼
    JSON contract
          │
          ▼
    Python validation
          │
          ▼
      Application
```

The LLM therefore acts as a structured semantic parser rather than as an unrestricted conversational agent.

---

# 31. Post-LLM Deterministic Validation

The application does not blindly trust the returned JSON.

For items:

```python
items = data.get("items", [])

if not isinstance(items, list):
    items = [str(items)]

items = [it.strip() for it in items if it.strip()]
```

For quantity:

```python
raw_qty = data.get("total_items")

try:
    count = (
        int(float(raw_qty))
        if raw_qty is not None and float(raw_qty) > 0
        else len(items)
    )
except (ValueError, TypeError):
    count = len(items) if items else 1
```

This provides type normalization and fallback behavior.

The important architecture principle is:

```text
LLM output ≠ trusted database record
```

Instead:

```text
LLM output
    ↓
type validation
    ↓
normalization
    ↓
fallback handling
    ↓
application object
```

---

# 32. Deterministic Summary Construction

The English summary is intentionally generated by Python rather than the LLM:

```python
english_summary = (
    f"The bill is from {merchant}, the bill states total {count} item(s) were bought, "
    f"the items are as follows: {items_str}, and the total amount is {total}."
)
```

This is a major reliability feature.

Given identical validated fields:

\[
S=f(M,Q,I,T)
\]

where:

- \(M\) = merchant,
- \(Q\) = item count,
- \(I\) = item list,
- \(T\) = total,

the resulting sentence is deterministic.

No language-model sampling is involved in the factual English summary.

---

# 33. Hindi Translation Pipeline

The second LLM call receives only the deterministic English sentence:

```text
Translate this English sentence into natural Hindi in Devanagari script.
Return ONLY the Hindi sentence.
```

The system therefore separates:

```text
FACT GENERATION
```

from:

```text
LANGUAGE REALIZATION
```

This reduces the opportunity for the translation stage to introduce new receipt facts.

The desired transformation is:

\[
S_{English}
\rightarrow
S_{Hindi}
\]

rather than:

\[
Receipt\rightarrow LLM\rightarrow Hindi\ facts
\]

---

# 34. gTTS Cache Architecture

Audio synthesis is an external generation step and should not be repeated unnecessarily.

A practical cache mapping is:

```text
Database Receipt ID
        │
        ▼
Audio Cache Key
        │
        ▼
<receipt_id>.mp3
```

The key principle is **database-bound lifecycle management**.

```text
CREATE RECEIPT
      │
      ├── DB row created
      └── optional audio generated
               │
               ▼
          audio cache

DELETE RECEIPT
      │
      ├── DB row deleted
      └── associated audio file deleted
```

## 34.1 Why Synchronization Matters

Without synchronization:

```text
SQLite:
Receipt #42 → deleted

Filesystem:
receipt_42.mp3 → still exists
```

This creates orphaned files.

Repeated receipt processing can also produce duplicate audio if the application generates audio without checking whether a valid cached artifact already exists.

Therefore:

```text
Database identity
       ↓
Cache identity
       ↓
Lifecycle coupling
```

should be maintained.

## 34.2 Cache Invalidation Principle

A cached audio artifact is valid only if it corresponds to the current summary.

A stronger production design would use:

\[
K = Hash(receipt\_id \parallel summary\_text \parallel language)
\]

so that changing the summary invalidates the old audio automatically.

---

# 35. SQLite Data Layer

SQLite is appropriate for this application because the workload is:

- local,
- low-concurrency,
- structured,
- persistent,
- relational but small.

Conceptually:

```text
Receipt
├── id
├── merchant
├── date
├── total
├── category
├── contact_info
├── return_policy
├── total_items_count
├── items
├── english_summary
└── hindi_summary
```

A normalized production schema could separate receipt and item tables:

```text
receipts
--------
id PK
merchant
date
total
category
contact_info
return_policy
english_summary
hindi_summary

receipt_items
-------------
id PK
receipt_id FK
item_name
quantity
unit_price
```

The current JSON-style extraction can still be persisted as a serialized item list for a minor-project implementation, but a relational item table is preferable for analytical querying.

---

# 36. Security and Privacy Architecture

The design is intentionally local.

```text
Receipt image
    │
    ├── local preprocessing
    ├── local OCR
    ├── local database
    │
    └── local LAN → local Ollama
```

No cloud LLM is required.

This is beneficial for receipts because they may contain:

- addresses,
- telephone numbers,
- transaction identifiers,
- tax identifiers,
- merchant details,
- purchasing behavior.

## LAN Security Requirements

For production deployment:

1. Bind Ollama only to the required LAN interface.
2. Restrict inbound port access using the workstation firewall.
3. Avoid port forwarding.
4. Use a trusted private network.
5. Do not expose the model endpoint directly to the Internet.
6. Consider an authenticated application-layer API if the deployment expands beyond a trusted network.

---

# 37. Computational Distribution

| Workload | Raspberry Pi 4 | Workstation |
|---|---:|---:|
| Image loading | Yes | Optional |
| OpenCV preprocessing | Yes | Optional |
| OCR | Yes | Optional |
| Regex normalization | Yes | Optional |
| SQLite | Yes | Optional |
| Streamlit client | Yes | Optional |
| Llama 3.2 3B | Not preferred | Yes |
| gTTS | Depends on deployment | Depends on deployment |

The architecture minimizes network payload size because the LLM does not need the original image. It receives cleaned OCR text.

Therefore:

\[
Bandwidth_{LLM} \approx O(|OCR\ text|)
\]

rather than:

\[
Bandwidth_{LLM} \approx O(|image|)
\]

This is especially advantageous for constrained LAN/edge systems.

---

# 38. Algorithmic Dataflow

The complete mathematical abstraction is:

\[
I
\xrightarrow{C_R}
R
\xrightarrow{P}
R'
\xrightarrow{S}
R''
\xrightarrow{H}
E
\xrightarrow{T}
O
\xrightarrow{L}
F
\xrightarrow{G}
A
\]

where:

- \(I\) = input image,
- \(C_R\) = red-channel projection,
- \(P\) = padding and resizing,
- \(S\) = CLAHE + thresholding + morphology,
- \(H\) = OCR,
- \(E\) = extracted OCR text,
- \(T\) = deterministic text normalization,
- \(O\) = cleaned OCR evidence,
- \(L\) = LLM structured extraction,
- \(F\) = validated structured facts,
- \(G\) = deterministic summary + translation,
- \(A\) = application output.

The architecture therefore separates the pipeline into:

```text
Perception
   ↓
Recognition
   ↓
Normalization
   ↓
Semantic Extraction
   ↓
Validation
   ↓
Language Generation
   ↓
Persistence / Audio
```

---

# 39. Engineering Trade-offs

## 39.1 Red Channel vs RGB/Luminance

**Advantage:** potentially suppresses colored artifacts and improves thermal-text separation.

**Limitation:** ink colors and lighting conditions vary.

**Future improvement:** automatically evaluate:

```text
R
G
B
Gray
HSV channels
Lab channels
```

and select the representation maximizing text/background separability.

---

## 39.2 CLAHE vs Simple Thresholding

**Advantage:** handles local contrast variation.

**Cost:** additional computation and possible noise amplification.

**Decision:** justified for faint thermal receipts.

---

## 39.3 Regex vs LLM Correction

**Regex advantage:** deterministic and auditable.

**LLM advantage:** handles irregular semantic contexts.

**Decision:** recurrent visual/OCR errors belong in regex; ambiguous semantic interpretation belongs in the LLM.

---

## 39.4 3B LLM vs Larger Model

**3B advantage:**

- lower memory requirement,
- local deployment,
- lower inference cost,
- practical for workstation-hosted LAN architecture.

**3B limitation:**

- weaker reasoning,
- greater hallucination risk,
- weaker handling of long or highly ambiguous OCR text.

The architecture compensates through constrained prompts and deterministic preprocessing.

---

# 40. Current Source Architecture

The provided `pipeline.py` contains four major responsibilities:

```text
pipeline.py
│
├── preprocess_image()
│   └── OpenCV image conditioning
│
├── run_ocr()
│   └── Tesseract recognition
│
├── clean_ocr_text()
│   └── deterministic normalization
│
├── extract_and_summarize()
│   ├── LLM structured extraction
│   ├── Python validation
│   ├── deterministic English summary
│   └── LLM Hindi translation
│
└── ask_receipt_question()
    └── receipt-grounded question answering
```

This is functionally clear for a minor project, although a production architecture should separate these concerns into modules.

Recommended structure:

```text
receipt_ai/
│
├── cv/
│   ├── preprocessing.py
│   └── ocr.py
│
├── normalization/
│   └── receipt_rules.py
│
├── llm/
│   ├── extraction.py
│   ├── translation.py
│   └── qa.py
│
├── persistence/
│   └── database.py
│
├── audio/
│   └── cache.py
│
├── ui/
│   └── streamlit_app.py
│
└── config.py
```

---

# 41. Recommended State Machine

A robust UI can represent processing as:

```text
RECEIPT_SELECTED
      │
      ▼
IMAGE_PREPROCESSED
      │
      ▼
OCR_COMPLETED
      │
      ▼
OCR_NORMALIZED
      │
      ▼
ENTITIES_EXTRACTED
      │
      ▼
FIELDS_VALIDATED
      │
      ▼
SUMMARY_GENERATED
      │
      ▼
DATABASE_COMMITTED
      │
      ▼
AUDIO_CACHED
      │
      ▼
READY
```

Any stage can transition to:

```text
ERROR
```

with a diagnostic message.

This is preferable to allowing an upstream failure to silently propagate into misleading downstream data.

---

# 42. Academic Evaluation: Strengths

The architecture demonstrates several strong engineering decisions.

### 42.1 Hybrid AI Architecture

The system does not rely exclusively on an LLM.

```text
Classical CV
+
OCR
+
Deterministic rules
+
Local LLM
```

This is appropriate for constrained edge-AI systems.

### 42.2 Explainability

The preprocessing stages have interpretable purposes:

```text
Red channel → spectral filtering
Padding → boundary conditioning
CLAHE → local contrast
Otsu → threshold selection
Morphology → noise removal
OCR → transcription
Regex → deterministic repair
LLM → semantic interpretation
```

### 42.3 Privacy

Receipt data remains within the local infrastructure.

### 42.4 Resource Awareness

Expensive LLM inference is offloaded to a workstation instead of requiring a GPU-equipped edge device.

### 42.5 Fault Isolation

The system has separate stages, allowing failures to be inspected at:

```text
Image
→ preprocessed image
→ raw OCR
→ cleaned OCR
→ JSON
→ final summary
```

This is valuable during debugging and academic demonstration.

---

# 43. Academic Evaluation: Limitations

The following limitations should be explicitly acknowledged.

## 43.1 Red-Channel Generalization

The selected channel is receipt-population dependent.

## 43.2 Regex Scope

The decimal repair rule is deliberately narrow. It should not be interpreted as a general monetary parser.

## 43.3 OCR Error Propagation

An unrecovered OCR character can alter semantic extraction.

\[
OCR\ error \rightarrow Evidence\ error \rightarrow LLM\ error
\]

The LLM cannot reliably recover information that is absent from the evidence.

## 43.4 Local 3B Model Capability

The model may struggle with:

- heavily corrupted OCR,
- complex receipt hierarchies,
- unusual currencies,
- multilingual receipts,
- implicit arithmetic,
- ambiguous totals.

## 43.5 Dataset Size

The described benchmark consists of representative real receipts rather than a statistically large corpus. Therefore conclusions should be framed as **prototype validation**, not universal accuracy claims.

---

# 44. Future Engineering Improvements

## 44.1 Multi-Channel Preprocessing Ensemble

Evaluate:

```text
R-channel
Grayscale
HSV-V
Lab-L
```

and select the representation with the highest OCR confidence.

## 44.2 Adaptive Border Detection

Instead of a fixed 40 px margin:

\[
p=f(character\ height,\ image\ resolution)
\]

can determine padding dynamically.

## 44.3 Receipt Geometry Detection

Use contour detection or document perspective correction before OCR:

```text
Camera image
    ↓
Receipt quadrilateral
    ↓
Perspective transform
    ↓
Normalized receipt
    ↓
OCR
```

## 44.4 OCR Confidence Feedback

Use Tesseract confidence scores to trigger alternative preprocessing branches.

```text
OCR confidence high
       │
       └──► accept

OCR confidence low
       │
       ├──► grayscale branch
       ├──► red-channel branch
       └──► adaptive threshold branch
```

## 44.5 Schema Validation

Use a strict schema layer such as:

```text
merchant: string
items: array[string]
total_items: integer
total_amount: number
category: enum
date: string
```

before committing to SQLite.

## 44.6 Arithmetic Consistency Checks

Where receipt fields permit:

\[
Subtotal + Tax - Discount + Charges
\approx GrandTotal
\]

A discrepancy can be flagged rather than silently accepted.

---

# 45. Recommended Demonstration Sequence

For an academic project presentation, the live demonstration should follow this sequence:

```text
1. Select receipt
       ↓
2. Show original image
       ↓
3. Show preprocessed image
       ↓
4. Show raw OCR
       ↓
5. Show normalized OCR
       ↓
6. Show structured JSON
       ↓
7. Show deterministic English summary
       ↓
8. Show Hindi summary
       ↓
9. Show database record
       ↓
10. Generate/play cached audio
```

The three benchmark receipts should be demonstrated in this order:

```text
Cross Channel Network
        ↓
McDonald's
        ↓
Rumours / Big Bull Entertainment
```

This moves from:

```text
text/layout errors
        ↓
semantic hierarchy errors
        ↓
low-contrast thermal recovery
```

and therefore demonstrates progressively different engineering challenges.

---

# 46. Key Design Decisions for Evaluation

| Design Decision | Engineering Justification |
|---|---|
| Red-channel isolation | Empirically improves separation for tested receipt/ink conditions |
| 40 px padding | Prevents text from terminating directly at OCR image boundary |
| 2× bicubic scaling | Improves sampled representation of small glyphs |
| CLAHE 8×8 | Recovers local contrast in faint/nonuniform thermal print |
| Otsu thresholding | Automatically selects global threshold from enhanced histogram |
| 2×2 opening | Removes small binary noise conservatively |
| Tesseract PSM 4 | Practical fit for variable-width multi-line receipt layouts |
| Regex normalization | Deterministic repair of recurrent OCR defects |
| LLM extraction | Handles semantic item/category/total interpretation |
| Temperature 0 | Minimizes sampling variability |
| JSON output | Machine-readable semantic contract |
| Deterministic English summary | Prevents unnecessary factual generation |
| Separate Hindi translation | Reduces factual hallucination in small local model |
| Raspberry Pi client | Low-cost edge interface and preprocessing platform |
| LAN workstation | Offloads computationally expensive 3B LLM |
| SQLite | Lightweight local persistence |
| gTTS cache | Avoids repeated synthesis |
| DB-bound audio purge | Prevents orphaned audio artifacts |

---

# 47. Final Architectural Assessment

The project implements a **hybrid edge-AI document intelligence architecture** rather than a simple OCR application.

Its core innovation is architectural:

```text
                 RECEIPT IMAGE
                      │
                      ▼
             COMPUTER VISION
                      │
                      ▼
                    OCR
                      │
                      ▼
          DETERMINISTIC NORMALIZATION
                      │
                      ▼
              STRUCTURED LLM
                 EXTRACTION
                      │
                      ▼
              PYTHON VALIDATION
                      │
                      ▼
          DETERMINISTIC SUMMARY
                      │
                      ▼
             LLM TRANSLATION
                      │
                      ▼
             DATABASE + AUDIO
```

The system deliberately assigns each class of problem to the most appropriate computational method:

- **pixel-level problems** → OpenCV,
- **character recognition** → Tesseract,
- **recurrent OCR defects** → regex,
- **semantic interpretation** → local LLM,
- **factual sentence construction** → deterministic Python,
- **language conversion** → local LLM,
- **persistence** → SQLite,
- **speech generation** → gTTS.

This division of responsibility is technically defensible for an academic edge-AI project because it minimizes unnecessary model dependence while preserving the flexibility required for heterogeneous receipts.

The three real-world benchmarks collectively validate the principal design objectives:

```text
Cross Channel Network
→ OCR normalization + wrapped-item interpretation

McDonald's
→ hierarchical item semantics + tender/total disambiguation

Rumours / Big Bull Entertainment
→ low-contrast recovery + boundary-safe Grand Total extraction
```

The most important engineering conclusion is that **receipt understanding should not be delegated entirely to a small language model**. The strongest architecture is a staged system in which deterministic image processing and rule-based correction establish a higher-quality evidence layer before the 3B model performs semantic interpretation.

For the current prototype, the next major step toward production-grade evaluation is a quantitatively labeled benchmark with field-level accuracy, item precision/recall, amount exact-match accuracy, OCR confidence, processing latency, memory usage, and LAN LLM inference time measured across a larger and more diverse receipt corpus.

---

# Appendix A — Core Processing Configuration

```text
Tesseract:
  OEM = 3
  PSM = 4
  preserve_interword_spaces = 1
  blacklist = | ~ _ § « »

OpenCV:
  Channel = Red (BGR index 2)
  Padding = 40 px
  Scale = 2.0×
  Interpolation = Bicubic
  CLAHE clipLimit = 2.0
  CLAHE grid = 8×8
  Threshold = Otsu + Binary
  Morphology = Opening
  Kernel = 2×2 rectangle

Ollama:
  Model = llama3.2:3b
  Temperature = 0.0
  Streaming = false
  Extraction format = JSON

Timeouts:
  Extraction = 45 s
  Translation = 30 s
  Question answering = 30 s
```

---

# Appendix B — End-to-End Pseudocode

```text
function process_receipt(image):

    image_bgr = load(image)

    red = image_bgr[:, :, 2]

    padded = add_white_border(red, 40)

    scaled = resize(padded, 2x, bicubic)

    enhanced = CLAHE(
        scaled,
        clip_limit=2.0,
        tiles=8x8
    )

    binary = OTSU(enhanced)

    cleaned = MORPH_OPEN(binary, kernel=2x2)

    raw_ocr = TESSERACT(
        cleaned,
        psm=4
    )

    filtered_ocr = remove_non_alphanumeric_lines(raw_ocr)

    normalized_ocr = deterministic_regex_repair(filtered_ocr)

    extracted_json = LOCAL_LLM_EXTRACT(
        normalized_ocr,
        temperature=0
    )

    validated = validate_and_normalize(extracted_json)

    english_summary = deterministic_template(validated)

    hindi_summary = LOCAL_LLM_TRANSLATE(
        english_summary,
        temperature=0
    )

    persist_to_sqlite(
        validated,
        english_summary,
        hindi_summary
    )

    audio = get_or_create_gtts_cache(
        receipt_id,
        hindi_summary
    )

    return {
        validated,
        english_summary,
        hindi_summary,
        audio
    }
```

---

# Appendix C — Core Design Principle

> **Use deterministic computation wherever the problem is deterministic; use the LLM only where semantic flexibility is required.**

This principle is the central engineering rationale of the project.
