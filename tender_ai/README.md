# Tender AI Module

Odoo module for processing tender ZIP files using an AI extraction service.

## Features

- **ZIP File Upload**: Upload ZIP files containing tender.pdf and company folders
- **AI-Powered Extraction**: Uses an AI API to extract structured data from PDFs
- **Background Processing**: Processes files asynchronously in the background
- **Comprehensive Data Extraction**:
  - Tender information (department, reference, dates, etc.)
  - Bidder/company details (PAN, GSTIN, contact info, etc.)
  - Payment records
  - Work experience records
  - Eligibility criteria

## Installation

1. **Install the module in Odoo first:**
   - Go to Apps menu
   - Remove "Apps" filter
   - Search for "Tender AI"
   - Click Install

2. **Install Python dependencies** (after module installation):
   ```bash
   # Install in your Odoo Python environment
   pip install google-genai openpyxl
   ```
   
   Or if using a virtual environment:
   ```bash
   source /path/to/odoo/venv/bin/activate  # or your venv path
   pip install google-genai openpyxl
   ```

3. **Set environment variable:**
   ```bash
   export AI_API_KEY=your_api_key_here
   ```
   
   Or add to your Odoo configuration file:
   ```ini
   [options]
   ai_api_key=your_api_key_here
   ```

## Configuration

Set the following environment variables (optional):
- `AI_API_KEY`: Your AI API key (required)
- `AI_TENDER_MODEL`: Model for tender extraction (optional; provider-specific)
- `AI_COMPANY_MODEL`: Model for company extraction (optional; provider-specific)
- `AI_MAX_CONCURRENCY`: Max concurrent AI calls (default: `8`)
- `COMPANY_WORKERS`: Number of company processing workers (default: `4`)
- `PDF_WORKERS_PER_COMPANY`: Number of PDF workers per company (default: `5`)

Set Odoo system parameter (optional):
- `tende_ai.tmp_dir`: Temporary directory for ZIP extraction (default: `/tmp/tende_ai`)

## Usage

### Via Odoo UI

1. Go to **Tender AI > Tender Processing**
2. Click **Create**
3. Upload a ZIP file containing:
   - `tender.pdf` at the root level
   - Company folders with PDFs inside
4. Click **Process ZIP**
5. Wait for processing to complete
6. View extracted data in the job form

### Via API

#### Upload ZIP File

```bash
curl -X POST http://your-odoo-instance/api/tender/upload \
  -H "Cookie: session_id=your_session_id" \
  -F "zip_file=@tender.zip"
```

Response:
```json
{
  "message": "Tender accepted ✅. Processing started. Please check after some minutes.",
  "job_id": "TENDER_001",
  "status": "processing",
  "status_check": "/api/tender/status?job_id=TENDER_001"
}
```

#### Check Status

```bash
curl "http://your-odoo-instance/api/tender/status?job_id=TENDER_001" \
  -H "Cookie: session_id=your_session_id"
```

Response:
```json
{
  "job_id": "TENDER_001",
  "status": "completed",
  "tender_reference": "REF123",
  "companies_detected": 5,
  "bidders_count": 5,
  "eligibility_criteria_count": 10
}
```

#### List All Jobs

```bash
curl "http://your-odoo-instance/api/tender/list" \
  -H "Cookie: session_id=your_session_id"
```

## ZIP File Structure

Your ZIP file should have the following structure:

```
tender.zip
├── tender.pdf                    # Main tender document
├── CompanyA/                     # Company folder
│   ├── document1.pdf
│   ├── document2.pdf
│   └── ...
├── CompanyB/                     # Another company folder
│   ├── document1.pdf
│   └── ...
└── ...
```

## Models

- **tende_ai.job**: Main processing job
- **tende_ai.tender**: Tender information
- **tende_ai.bidder**: Bidder/company information
- **tende_ai.payment**: Payment records
- **tende_ai.work_experience**: Work experience records
- **tende_ai.eligibility_criteria**: Eligibility criteria

## Security

- ZIP files are safely extracted with path traversal protection
- Symlink detection prevents security issues
- File count and size limits prevent zip-bomb attacks
- All API endpoints require user authentication

## Troubleshooting

### Module won't install
- Ensure `google-genai` and `openpyxl` are installed in your Odoo Python environment
- Check that `AI_API_KEY` is set (or `ai_api_key` is present in `odoo.conf`)

### File size limit error (134MB limit)
If you encounter "file is larger than the maximum allowed file size (134MB)":

**Option 1: Use the API endpoint (Recommended for large files)**
```bash
curl -X POST http://your-odoo-instance/api/tender/upload \
  -H "Cookie: session_id=your_session_id" \
  -F "zip_file=@large_tender.zip"
```

**Option 2: Increase Odoo file upload limit**
Add to your Odoo configuration file (`odoo.conf`):
```ini
[options]
limit_request = 8192
limit_memory_soft = 2147483648
limit_memory_hard = 2684354560
```

**Option 3: Configure web server (if using nginx)**
Add to nginx configuration:
```nginx
client_max_body_size 2048M;
```

**Option 4: Configure web server (if using Apache)**
Add to Apache configuration:
```apache
LimitRequestBody 2147483648
```

### Processing fails
- Check the error message in the job form
- Verify ZIP file structure (must contain tender.pdf)
- Ensure AI API key is valid and has quota

### Slow processing
- Adjust `COMPANY_WORKERS` and `PDF_WORKERS_PER_COMPANY` environment variables
- Check AI API rate limits

## License

LGPL-3

