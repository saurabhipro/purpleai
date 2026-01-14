# Delete Surveys Wizard - Instructions

## Overview
The **Delete Surveys** action allows you to bulk delete surveys and reset property data using **two convenient methods**:
1. **Upload Excel File** - For large batches with pre-prepared data
2. **Paste UPIC Numbers** - For quick deletions by pasting comma-separated values

## How to Access
1. Navigate to: **Digital Pata → Property Survey**
2. Click on the **Action menu (⚙️)** in the list view
3. Select **"Delete Surveys"**

## Method 1: Paste UPIC Numbers (Quick & Easy) ⚡

### How to Use
1. Select **"Paste UPIC Numbers"** option (default)
2. Paste your UPIC numbers in the text area
3. Click **"Delete Surveys"**

### Supported Formats
You can paste UPIC numbers in any of these formats:

**Comma-separated:**
```
UPIC001, UPIC002, UPIC003, UPIC004
```

**Semicolon-separated:**
```
UPIC001; UPIC002; UPIC003
```

**One per line:**
```
UPIC001
UPIC002
UPIC003
```

**Mixed (automatically handled):**
```
UPIC001, UPIC002
UPIC003; UPIC004
UPIC005
```

### Features
- ✅ Automatically removes duplicates
- ✅ Handles commas, semicolons, tabs, and line breaks
- ✅ Trims whitespace
- ✅ Perfect for copy-paste from Excel, reports, or other sources

## Method 2: Upload Excel File (For Large Batches)

### Required Column
Your Excel file must contain a column with one of these names (case-insensitive):
- `UPICNO`
- `UPIC`
- `UPIC NO`
- `UPIC_NO`

### Example File Structure

| UPICNO      |
|-------------|
| UPIC001     |
| UPIC002     |
| UPIC003     |

### Creating Your Excel File
1. Create a new Excel file (.xlsx or .xls)
2. Add a header row with "UPICNO" in the first column
3. List all UPIC numbers (one per row) that need survey deletion
4. Save the file

## What Happens During Deletion

When you submit the input, for each UPIC number the system will:

1. **Find the property** by UPIC number
2. **Delete all survey records** associated with that property
3. **Reset the property status** to "pdf_downloaded"
4. **Clear the following fields:**
   - Address Line 1
   - Address Line 2
   - Property ID
   - Owner Name
   - Property Type
   - Latitude
   - Longitude
   - DigiPin (automatically cleared when lat/long are cleared)
   - Mobile Number
   - Surveyor

## Result File

After processing, you'll receive a result Excel file with three sheets:

### 1. Success Sheet
Lists all UPIC numbers where surveys were successfully deleted:
- UPIC NO
- Surveys Deleted (count)
- Status

### 2. Failed Sheet
Lists UPIC numbers where deletion failed:
- UPIC NO
- Error (reason for failure)

### 3. Not Found Sheet
Lists UPIC numbers that were not found in the system:
- UPIC NO
- Error

## Statistics

The wizard displays:
- **Total Records**: Total number of UPIC numbers processed
- **Success Count**: Number of successful deletions
- **Failed Count**: Number of failed deletions
- **Not Found Count**: Number of UPIC numbers not found

## Important Notes

⚠️ **WARNING**: This operation cannot be undone. Make sure you have a backup before proceeding.

✅ **Best Practices**:
- Test with a small batch first
- Keep a backup of the Excel file
- Download and review the result file after processing
- Verify the statistics before closing the wizard

## Example Usage

### Quick Method: Paste UPIC Numbers
```
Step 1: Click "Delete Surveys" from Action menu
Step 2: Ensure "Paste UPIC Numbers" is selected (default)
Step 3: Paste your UPIC numbers:
        UPIC001, UPIC002, UPIC003
Step 4: Click "Delete Surveys"
Step 5: Review statistics and download result file
Step 6: Click "Close"
```

### Excel Method: Upload File
```
Step 1: Prepare Excel file with UPICNO column
        UPICNO
        DDN001
        DDN002
        DDN003

Step 2: Click "Delete Surveys" from Action menu
Step 3: Select "Upload Excel File" option
Step 4: Choose your Excel file
Step 5: Click "Delete Surveys"
Step 6: Review statistics and download result file
Step 7: Click "Close"
```

## Troubleshooting

**Issue**: Column not found error
- **Solution**: Ensure your Excel file has a column named "UPICNO", "UPIC", or "UPIC NO"

**Issue**: File format not supported
- **Solution**: Only .xlsx and .xls files are supported. Convert your file if needed.

**Issue**: Some records failed
- **Solution**: Check the "Failed" sheet in the result file for specific error messages

**Issue**: Records not found
- **Solution**: Verify the UPIC numbers exist in the system and are spelled correctly

## Support
For technical support, contact the system administrator or development team.
