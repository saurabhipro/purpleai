import os
import re
import tempfile
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import qrcode
from odoo import http
from odoo.http import request, content_disposition
import base64
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image, ImageDraw, ImageFont
import logging
import zipfile
import shutil
import time
import traceback
import boto3

_logger = logging.getLogger(__name__)

# Global configuration

# Configuration Settings
class PDFConfig:
    # Font Configuration
    # BASE_EXPORT_DIR = '/home/anjli/Anjli/crm/BharatDDN/pdf'  # Base directory for all PDF exports

    BASE_EXPORT_DIR = '/home/odoo18/odoo/downloaded_pdfs'  # Base directory for all PDF exports
    # BASE_EXPORT_DIR = '/home/anjli/bharat_ddn/bharat_ddn/downloaded_pdfs'
    FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    # FONT_PATH = "C:\\Windows\\Fonts\\arial.ttf"
    IMAGE_QUALITY = 20 # Increased quality for better clarity
    BATCH_SIZE = 5000  # Process 20 properties at a time
    
    # Adjusted for 8x4 plate dimensions
    CENTER_FONT_SIZE = 150  # Increased height to make text taller
    VALUE_FONT_SIZE = 85    # Reduced to fit within boxes (Z14, SDNA, 0002)

    IMAGE_FORMAT = 'JPEG'
    BACKGROUND_COLOR = 'white'  # Added background color setting
   
    # Y positions scaled for 8x4 (4/6 = 0.667 ratio)
    CENTER_TEXT_Y = 380  # Moved down to be closer to the red row table
    VALUE_TEXT_Y = 350   # Scaled from 570
    CENTER_TEXT_RIGHT_MARGIN = 60  # Increase this value to move text further left
    TEXT_OUTLINE_OFFSET = 5
    # Table Cell Positions and Dimensions - moved down and to the right
    TABLE_ROW_Y = 650    # Moved down more to fit in red row (was 550)
    BOX_START_X = 250    # Moved right more for better positioning
    BOX_WIDTH = 250
    BOX_GAP = 280        # Adjusted gap to move locality and unit more to the right
    
    # Individual box X offset adjustments (adjust these to fine-tune positioning)
    ZONE_X_OFFSET = -60   # Move Z14 left (negative = left, positive = right)
    LOCALITY_X_OFFSET = 50  # Move SDNA right (negative = left, positive = right)
    UNIT_NO_X_OFFSET = 150   # Move UNIT text right (negative = left, positive = right)
    QR_VERSION = 1
    QR_ERROR_CORRECTION = qrcode.constants.ERROR_CORRECT_H
    QR_BOX_SIZE = 14     # Further reduced for better fit in box
    QR_BORDER = 2        # Increased border for better visibility
   
   
    # QR Code Settings - Adjusted to fit in box for 8x4 plate
    QR_BOX = {
        'x': 90,        # Adjusted position
        'y': 180,        # Moved up slightly
        'width': 320,    # Further reduced for better fit in box
        'height': 320   # Square aspect, reduced for better fit
    }
   
 
# Register the custom font
pdfmetrics.registerFont(TTFont("CustomBold", PDFConfig.FONT_PATH))
 
# Add these global variables at the top of the file, after the imports
class PDFExportStatus:
    _export_status = {}  # Dictionary to store export status for each colony
    _export_folders = {}  # Dictionary to store export folder paths for each colony
    
    @classmethod
    def set_export_status(cls, colony_id, status, folder_path=None):
        cls._export_status[colony_id] = status
        if folder_path:
            cls._export_folders[colony_id] = folder_path
    
    @classmethod
    def get_export_status(cls, colony_id):
        return cls._export_status.get(colony_id, False)
    
    @classmethod
    def get_export_folder(cls, colony_id):
        return cls._export_folders.get(colony_id)

class PdfGeneratorController(http.Controller):
 
    def draw_centered_text(self, x, y, width, text, font, color, x_offset=0):
        """Helper function to draw centered text with optional X offset adjustment"""
        draw = ImageDraw.Draw(self.current_image)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        
        # Center the text and apply X offset
        x_centered = x + (width - text_width) // 2 + x_offset
        draw.text((x_centered, y), text, font=font, fill=color)
 
    def generate_ddn_image(self, property_rec, bg_image_path):
        """
        Generate a complete image with text and QR code using original Python coordinates
        """
        try:
            # Open and convert background image
            background = Image.open(bg_image_path).convert("RGB")
            # Create a new white background image
            final_image = Image.new('RGB', background.size, PDFConfig.BACKGROUND_COLOR)
            # Paste the background image
            final_image.paste(background, (0, 0))
            draw = ImageDraw.Draw(final_image)
 
            # Store the current image for draw_centered_text to use
            self.current_image = final_image
 
            # Fonts
            center_font = ImageFont.truetype(PDFConfig.FONT_PATH, PDFConfig.CENTER_FONT_SIZE)
            value_font = ImageFont.truetype(PDFConfig.FONT_PATH, PDFConfig.VALUE_FONT_SIZE)
 
            # Helper to clean text
            def clean_text_val(val):
                if not val: return "-"
                val = str(val)
                # Remove decimals entirely: 123.77 -> 123
                return re.sub(r'\.\d+', '', val)

            # Property details
            zone = getattr(property_rec.zone_id, 'name', '-') if property_rec.zone_id else '-'
            
            raw_locality = getattr(property_rec.colony_id, 'code', '-') if property_rec.colony_id else '-'
            locality = clean_text_val(raw_locality)
            
            raw_unit_no = property_rec.unit_no or "-"
            # Clean unit no as well
            raw_unit_no = clean_text_val(raw_unit_no)
            
            formatted_unit_no = str(raw_unit_no).zfill(4) if raw_unit_no != "-" else "-"
 
            # Center text (with outline)
            center_text = f"{zone}-{locality}-{formatted_unit_no}"
            bbox = draw.textbbox((0, 0), center_text, font=center_font)
            text_width = bbox[2] - bbox[0]
            right_x = background.width - PDFConfig.CENTER_TEXT_RIGHT_MARGIN - text_width
            center_y = PDFConfig.CENTER_TEXT_Y
 
            # Draw white outline
            for dx, dy in [(-PDFConfig.TEXT_OUTLINE_OFFSET,0), (PDFConfig.TEXT_OUTLINE_OFFSET,0),
                          (0,-PDFConfig.TEXT_OUTLINE_OFFSET), (0,PDFConfig.TEXT_OUTLINE_OFFSET),
                          (-PDFConfig.TEXT_OUTLINE_OFFSET,-PDFConfig.TEXT_OUTLINE_OFFSET),
                          (-PDFConfig.TEXT_OUTLINE_OFFSET,PDFConfig.TEXT_OUTLINE_OFFSET),
                          (PDFConfig.TEXT_OUTLINE_OFFSET,-PDFConfig.TEXT_OUTLINE_OFFSET),
                          (PDFConfig.TEXT_OUTLINE_OFFSET,PDFConfig.TEXT_OUTLINE_OFFSET)]:
                draw.text((right_x + dx, center_y + dy), center_text, font=center_font, fill='white')
           
            # Draw main text
            draw.text((right_x, center_y), center_text, font=center_font, fill='black')
 
            # Calculate X positions for each box
            zone_x = PDFConfig.BOX_START_X
            locality_x = zone_x + PDFConfig.BOX_WIDTH + PDFConfig.BOX_GAP
            unit_no_x = locality_x + PDFConfig.BOX_WIDTH + PDFConfig.BOX_GAP

            # Draw the values in the table with individual X offsets
            self.draw_centered_text(zone_x, PDFConfig.TABLE_ROW_Y, PDFConfig.BOX_WIDTH, zone, value_font, 'white', PDFConfig.ZONE_X_OFFSET)
            self.draw_centered_text(locality_x, PDFConfig.TABLE_ROW_Y, PDFConfig.BOX_WIDTH, locality, value_font, 'white', PDFConfig.LOCALITY_X_OFFSET)
            self.draw_centered_text(unit_no_x, PDFConfig.TABLE_ROW_Y, PDFConfig.BOX_WIDTH, formatted_unit_no, value_font, 'white', PDFConfig.UNIT_NO_X_OFFSET)
 
            # QR code - fit in existing background box (no new border)
            qr = qrcode.QRCode(
                version=PDFConfig.QR_VERSION,
                error_correction=PDFConfig.QR_ERROR_CORRECTION,
                box_size=PDFConfig.QR_BOX_SIZE,
                border=PDFConfig.QR_BORDER
            )
            base_url = property_rec.company_id.website or request.httprequest.host_url
            full_url = f"{base_url}/get/{property_rec.uuid}"
            qr.add_data(full_url)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            
            # Resize QR code to fit within the existing background box with padding
            qr_padding = 10  # Small padding inside the existing box
            qr_actual_width = PDFConfig.QR_BOX['width'] - (qr_padding * 2)
            qr_actual_height = PDFConfig.QR_BOX['height'] - (qr_padding * 2)
            qr_img = qr_img.resize((qr_actual_width, qr_actual_height), Image.LANCZOS)
           
            # Paste QR code directly into the existing background box (no new border)
            qr_paste_x = PDFConfig.QR_BOX['x'] + qr_padding
            qr_paste_y = PDFConfig.QR_BOX['y'] + qr_padding
            final_image.paste(qr_img, (qr_paste_x, qr_paste_y))
 
            return final_image
 
        except Exception as e:
            _logger.error(f"Error generating DDN image for property {getattr(property_rec, 'id', 'unknown')}: {e}", exc_info=True)
            raise
 
    def get_colony_folder(self, colony_id, create_only=False):
        """Create and return colony-specific folder path
        
        Args:
            colony_id: ID of the colony
            create_only: If True, only create folder without deleting existing one (used during batch processing)
        """
        colony = request.env['ddn.colony'].sudo().browse(colony_id)
        if not colony.exists():
            raise ValueError(f"Colony with ID {colony_id} not found")
            
        colony_name = colony.name.replace(" ", "_").lower()
        colony_dir = os.path.join(PDFConfig.BASE_EXPORT_DIR, colony_name)
        
        # Only remove existing folder if create_only is False (first time setup)
        if not create_only and os.path.exists(colony_dir):
            shutil.rmtree(colony_dir)
            _logger.info(f"Cleaned old folder for colony: {colony_name}")
            
        # Create new folder (or ensure it exists)
        os.makedirs(colony_dir, exist_ok=True)
        
        # Update export status only on first call
        if not create_only:
            PDFExportStatus.set_export_status(colony_id, True, colony_dir)
        
        return colony_dir
    
    def cleanup_local_pdfs(self, pdf_paths):
        """Delete local PDF files after successful S3 upload"""
        deleted_count = 0
        for pdf_path in pdf_paths:
            try:
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
                    deleted_count += 1
                    _logger.info(f"Deleted local PDF file: {pdf_path}")
            except Exception as e:
                _logger.warning(f"Could not delete local PDF file {pdf_path}: {e}")
        
        if deleted_count > 0:
            _logger.info(f"Cleaned up {deleted_count} local PDF file(s) after successful S3 upload")

    def cleanup_old_s3_batches(self, colony_id, s3_client, bucket_name, pdf_path_prefix, colony_name):
        """Delete old batch PDF files from S3 for the colony"""
        try:
            # List all objects in the colony's S3 folder
            prefix = f"{pdf_path_prefix}{colony_name}/batch_"
            response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
            
            if 'Contents' in response:
                # Delete all old batch PDFs
                objects_to_delete = [{'Key': obj['Key']} for obj in response['Contents'] if obj['Key'].endswith('.pdf')]
                if objects_to_delete:
                    s3_client.delete_objects(
                        Bucket=bucket_name,
                        Delete={'Objects': objects_to_delete}
                    )
                    _logger.info(f"Deleted {len(objects_to_delete)} old batch PDF(s) from S3 for colony: {colony_name}")
        except Exception as e:
            _logger.warning(f"Could not cleanup old S3 batches for colony {colony_name}: {e}")

    def upload_pdfs_to_s3(self, pdf_paths, colony_id):
        """Upload PDF files to S3 and return the S3 URL"""
        try:
            colony = request.env['ddn.colony'].sudo().browse(colony_id)
            if not colony.exists():
                raise ValueError(f"Colony with ID {colony_id} not found")
            
            company = colony.company_id
            if not company or not company.s3_bucket_name or not company.aws_acsess_key:
                _logger.warning("S3 configuration not found. Skipping S3 upload.")
                return None
            
            # Get S3 configuration
            AWS_ACCESS_KEY = company.aws_acsess_key
            AWS_SECRET_KEY = company.aws_secret_key
            AWS_REGION = company.aws_region or 'ap-south-1'
            S3_BUCKET_NAME = company.s3_bucket_name
            
            # Safely get PDF path prefix (handle case where field doesn't exist in DB yet)
            try:
                PDF_PATH_PREFIX = (company.s3_pdf_path_prefix or 'pdf/').strip()
            except (AttributeError, KeyError):
                PDF_PATH_PREFIX = 'pdf/'
            
            if not PDF_PATH_PREFIX.endswith('/'):
                PDF_PATH_PREFIX += '/'
            
            # Initialize S3 client
            s3_client = boto3.client(
                's3',
                aws_access_key_id=AWS_ACCESS_KEY,
                aws_secret_access_key=AWS_SECRET_KEY,
                region_name=AWS_REGION
            )
            
            # Get colony name for S3 path
            colony_name = colony.name.replace(" ", "_").lower()
            
            # Clean up old batch PDFs from S3 before uploading new ones
            self.cleanup_old_s3_batches(colony_id, s3_client, S3_BUCKET_NAME, PDF_PATH_PREFIX, colony_name)
            
            # Upload all PDFs and collect URLs
            s3_urls = []
            _logger.info(f"Starting S3 upload for {len(pdf_paths)} PDF file(s)")
            for idx, pdf_path in enumerate(pdf_paths, 1):
                if not os.path.exists(pdf_path):
                    _logger.warning(f"Batch {idx}: PDF file does not exist: {pdf_path}")
                    continue
                
                filename = os.path.basename(pdf_path)
                # S3 key: pdf_path_prefix/colony_name/filename
                s3_key = f"{PDF_PATH_PREFIX}{colony_name}/{filename}"
                
                try:
                    # Upload to S3
                    _logger.info(f"Uploading batch {idx} to S3: {s3_key}")
                    with open(pdf_path, 'rb') as pdf_file:
                        pdf_data = pdf_file.read()
                        file_size = len(pdf_data)
                        _logger.info(f"  File size: {file_size} bytes")
                        
                        s3_client.put_object(
                            Bucket=S3_BUCKET_NAME,
                            Key=s3_key,
                            Body=pdf_data,
                            ContentType='application/pdf'
                        )
                    
                    # Generate S3 URL
                    s3_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
                    s3_urls.append(s3_url)
                    _logger.info(f"  ✓ Successfully uploaded batch {idx} to S3: {s3_url}")
                except Exception as e:
                    _logger.error(f"  ✗ Failed to upload batch {idx} ({filename}) to S3: {str(e)}", exc_info=True)
            
            _logger.info(f"S3 upload completed. Successfully uploaded {len(s3_urls)} out of {len(pdf_paths)} file(s)")
            # Return all S3 URLs for all batches
            return s3_urls if s3_urls else None
            
        except Exception as e:
            _logger.error(f"Error uploading PDFs to S3: {str(e)}", exc_info=True)
            return None

    def process_property_batch(self, property_ids, bg_image_path, colony_dir, colony_id=None, batch_number=1):
        processed_count = 0
        error_count = 0
        # Use provided colony_dir - do NOT recreate/delete folder here
        # This ensures PDFs from previous batches are not deleted
        os.makedirs(colony_dir, exist_ok=True)

        # Create a single PDF for this batch with sequential numbering
        batch_pdf_filename = f"batch_{batch_number}.pdf"
        batch_pdf_path = os.path.join(colony_dir, batch_pdf_filename)
        _logger.info(f"Starting batch PDF creation: {batch_pdf_filename}")
        
        # Create canvas for the batch PDF
        c = None
        temp_images = []  # Keep track of temp image files to clean up

        try:
            for property_id in property_ids:
                try:
                    property_rec = request.env['ddn.property.info'].browse(property_id)
                    final_image = self.generate_ddn_image(property_rec, bg_image_path)
                    
                    # Save as temp image
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_img:
                        final_image.save(temp_img.name, PDFConfig.IMAGE_FORMAT, quality=PDFConfig.IMAGE_QUALITY, optimize=True)
                        img_path = temp_img.name
                        temp_images.append(img_path)

                    # If this is the first image, create the canvas
                    if c is None:
                        c = canvas.Canvas(batch_pdf_path, pagesize=final_image.size)

                    # Add image to PDF
                    img = ImageReader(img_path)
                    c.drawImage(img, 0, 0, width=final_image.width, height=final_image.height)
                    c.showPage()  # Add new page for next image
                    
                    property_rec.write({'property_status': 'pdf_downloaded'})
                    processed_count += 1
                    _logger.info(f"Processed Unit No: {property_rec.unit_no}")

                except Exception as e:
                    error_count += 1
                    _logger.error(f"Error processing property {property_id}: {e}", exc_info=True)
                    continue

            # Save and close the PDF
            if c is not None:
                c.save()
                c = None  # Release canvas
                _logger.info(f"Batch PDF generated and saved at: {batch_pdf_path}")

            # Clean up temp images
            for img_path in temp_images:
                try:
                    os.unlink(img_path)
                except Exception as e:
                    _logger.error(f"Error cleaning up temp image {img_path}: {e}")

            _logger.info(f"Memory freed: {len(temp_images)} images and PDF canvas released")
            return processed_count, colony_dir, batch_pdf_path if processed_count > 0 else None

        except Exception as e:
            _logger.error(f"Error in batch processing: {e}", exc_info=True)
            # Clean up resources in case of error
            if c is not None:
                c = None
            for img_path in temp_images:
                try:
                    os.unlink(img_path)
                except:
                    pass
            return processed_count, colony_dir, None

    @http.route(['/download/ward_properties_pdf', '/download/ward_properties_pdf/<string:source>'], type='http', auth='user', methods=['GET'], csrf=True)
    def download_ward_properties_pdf(self, source=None, **kw):
        _logger.info("Starting PDF generation process")
        ward_id = kw.get('ward_id')
        colony_id = kw.get('colony_id')
        property_id = kw.get('property_id')

        _logger.info(f"Parameters - Ward ID: {ward_id}, Colony ID: {colony_id}, Property ID: {property_id}")

        # Validate property_id if provided
        if property_id:
            try:
                property_id = int(property_id)
            except ValueError:
                return request.not_found("Invalid Property ID.")

        # Validate ward_id if provided
        if ward_id:
            try:
                ward_id = int(ward_id)
            except ValueError:
                return request.not_found("Invalid Ward ID.")

        # Validate colony_id if provided
        if colony_id:
            try:
                colony_id = int(colony_id)
            except ValueError:
                return request.not_found("Invalid Colony ID.")

        # Construct search domain
        domain = []
        if property_id:
            domain = [('id', '=', property_id)]
        else:
            if ward_id:
                domain.append(('ward_id', '=', ward_id))
            if colony_id:
                domain.append(('colony_id', '=', colony_id))

        properties = request.env['ddn.property.info'].sudo().search(domain)
        if not properties:
            return request.not_found("No properties found for the given criteria.")

        company = request.env.user.company_id
        if not company or not company.plate_background_image:
            return request.not_found("No background image configured for your company.")

        # Clear old PDF URLs from colony record before starting fresh generation
        if colony_id:
            try:
                colony = request.env['ddn.colony'].sudo().browse(colony_id)
                if colony.exists():
                    colony.write({
                        'pdf_url': False,
                        'pdf_urls': False
                    })
                    _logger.info(f"Cleared old PDF URLs for colony ID: {colony_id}")
            except Exception as e:
                _logger.warning(f"Could not clear old PDF URLs for colony {colony_id}: {e}")

        try:
            # Ensure base export directory exists
            os.makedirs(PDFConfig.BASE_EXPORT_DIR, exist_ok=True)
            _logger.info(f"Base export directory: {PDFConfig.BASE_EXPORT_DIR}")

            bg_image_data = base64.b64decode(company.plate_background_image)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_bg:
                bg_image_path = temp_bg.name
                temp_bg.write(bg_image_data)
                temp_bg.flush()
                os.fsync(temp_bg.fileno())
                _logger.info(f"Background image saved at: {bg_image_path}")

            # Process properties in batches
            property_ids = [rec.id for rec in properties]
            batch_size = PDFConfig.BATCH_SIZE
            
            _logger.info(f"Total properties to process: {len(property_ids)}")
            total_processed = 0
            output_dir = None
            batch_pdf_paths = []

            # Create colony folder ONCE before processing batches
            # This ensures PDFs from previous batches are NOT deleted during processing
            if colony_id:
                output_dir = self.get_colony_folder(colony_id, create_only=False)
                _logger.info(f"Created colony folder: {output_dir}")
            else:
                output_dir = os.path.join(PDFConfig.BASE_EXPORT_DIR, "sudama_nagar")
                os.makedirs(output_dir, exist_ok=True)

            # Process all batches
            for i in range(0, len(property_ids), batch_size):
                batch_ids = property_ids[i:i + batch_size]
                batch_number = (i // batch_size) + 1
                _logger.info(f"Processing batch {batch_number} with {len(batch_ids)} properties")
                
                processed, output_dir, batch_pdf_path = self.process_property_batch(
                    batch_ids, bg_image_path, output_dir, colony_id, batch_number=batch_number)
                total_processed += processed
                
                _logger.info(f"Batch {batch_number} processing result: processed={processed}, path={batch_pdf_path}, exists={os.path.exists(batch_pdf_path) if batch_pdf_path else False}, source={source}")
                
                if not source and batch_pdf_path and os.path.exists(batch_pdf_path):
                    batch_pdf_paths.append(batch_pdf_path)
                    _logger.info(f"✓ Added batch {batch_number} PDF to upload list: {batch_pdf_path}")
                elif source:
                    _logger.info(f"  Skipping batch {batch_number} - source is '{source}' (not adding to S3 upload list)")
                elif not batch_pdf_path:
                    _logger.warning(f"  Batch {batch_number} - No PDF path returned from process_property_batch")
                elif not os.path.exists(batch_pdf_path):
                    _logger.warning(f"  Batch {batch_number} - PDF file does not exist: {batch_pdf_path}")

                if source == 'erp' and batch_pdf_path and os.path.exists(batch_pdf_path):
                        with open(batch_pdf_path, 'rb') as f:
                            pdf_data = f.read()

                        filename = os.path.basename(batch_pdf_path)

                        return request.make_response(
                            pdf_data,
                            headers=[
                                ('Content-Type', 'application/pdf'),
                                ('Content-Disposition', content_disposition(filename)),
                            ]
                        )


            # Update export status to indicate completion
            if colony_id:
                PDFExportStatus.set_export_status(colony_id, True, output_dir)
                _logger.info(f"All batches processed. Total processed: {total_processed}")
                _logger.info(f"PDFs are available in directory: {output_dir}")
                
                # Upload PDFs to S3 if batch PDFs exist
                _logger.info(f"Preparing to upload {len(batch_pdf_paths)} batch PDF(s) to S3")
                for idx, path in enumerate(batch_pdf_paths, 1):
                    _logger.info(f"  Batch {idx}: {path} (exists: {os.path.exists(path)})")
                
                if batch_pdf_paths:
                    s3_urls = self.upload_pdfs_to_s3(batch_pdf_paths, colony_id)
                    if s3_urls and len(s3_urls) == len(batch_pdf_paths):
                        # All batches successfully uploaded to S3
                        _logger.info(f"S3 upload successful. All {len(s3_urls)} batch(es) uploaded.")
                        # Update colony's pdf_url with first S3 URL (for backward compatibility)
                        # Update colony's pdf_urls with all S3 URLs (one per line)
                        colony = request.env['ddn.colony'].sudo().browse(colony_id)
                        all_urls_text = '\n'.join(s3_urls)
                        colony.write({
                            'pdf_url': s3_urls[0] if s3_urls else '',  # First URL for backward compatibility
                            'pdf_urls': all_urls_text  # All URLs, one per line
                        })
                        _logger.info(f"Updated colony PDF URLs. Total batches: {len(s3_urls)}")
                        for idx, url in enumerate(s3_urls, 1):
                            _logger.info(f"  Batch {idx} URL: {url}")
                        
                        # Delete local PDF files only after all batches are successfully uploaded to S3
                        _logger.info("All batches uploaded to S3. Cleaning up local PDF files...")
                        self.cleanup_local_pdfs(batch_pdf_paths)
                    elif s3_urls and len(s3_urls) < len(batch_pdf_paths):
                        # Partial upload - keep local files
                        _logger.warning(f"Only {len(s3_urls)} out of {len(batch_pdf_paths)} batches uploaded to S3. Keeping local files.")
                        colony = request.env['ddn.colony'].sudo().browse(colony_id)
                        all_urls_text = '\n'.join(s3_urls)
                        colony.write({
                            'pdf_url': s3_urls[0] if s3_urls else '',
                            'pdf_urls': all_urls_text
                        })
                        for idx, url in enumerate(s3_urls, 1):
                            _logger.info(f"  Batch {idx} URL: {url}")
                    else:
                        _logger.error("S3 upload failed or returned no URLs. Local PDF files will be kept for manual upload.")
                        _logger.error("Check S3 configuration and logs above for details.")
                else:
                    _logger.warning("No batch PDF paths to upload to S3")
                
                # Return success message with directory information
                return request.make_response(
                    f"PDF generation completed. {total_processed} properties processed. Files are available in: {output_dir}",
                    headers=[('Content-Type', 'text/plain')]
                )
            else:
                return request.not_found("No PDFs were generated successfully")

        except Exception as e:
            _logger.error(f"An error occurred: {str(e)}")
            if colony_id:
                PDFExportStatus.set_export_status(colony_id, False, output_dir)
            return request.not_found(f"An error occurred: {str(e)}")

    @http.route(['/get/export_status'], type='json', auth='user')
    def get_export_status(self, colony_id):
        """Get the export status and folder path for a colony"""
        status = PDFExportStatus.get_export_status(colony_id)
        folder = PDFExportStatus.get_export_folder(colony_id)
        return {
            'status': status,
            'folder': folder
        }

    @http.route(['/get/generated_pdfs/<path:filepath>'], type='http', auth='user')
    def get_generated_pdf(self, filepath, **kw):
        """Serve generated PDF files"""
        try:
            file_path = os.path.join(PDFConfig.BASE_EXPORT_DIR, filepath)
            
            # If it's a directory, list all PDF files in it
            if os.path.isdir(file_path):
                pdf_files = [f for f in os.listdir(file_path) if f.endswith('.pdf')]
                
                html_content = f"""
                <html>
                <body>
                    <h2>PDF Files in {filepath}</h2>
                    <ul>
                """
                
                for pdf_file in pdf_files:
                    pdf_path = os.path.join(filepath, pdf_file)
                    file_url = f"/get/generated_pdfs/{pdf_path}"
                    html_content += f'<li><a href="{file_url}">{pdf_file}</a></li>'
                
                html_content += """
                    </ul>
                </body>
                </html>
                """
                
                return request.make_response(
                    html_content,
                    headers=[('Content-Type', 'text/html')]
                )
            
            # If it's a file, serve it
            elif os.path.isfile(file_path) and file_path.endswith('.pdf'):
                with open(file_path, 'rb') as f:
                    return request.make_response(
                        f.read(),
                        headers=[
                            ('Content-Type', 'application/pdf'),
                            ('Content-Disposition', f'inline; filename={os.path.basename(file_path)}')
                        ]
                    )
                
        except Exception as e:
            _logger.error(f"Error serving file {filepath}: {str(e)}")
        
        return request.not_found("File not found")