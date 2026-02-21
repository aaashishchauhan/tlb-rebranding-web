import os
import io
import shutil
import logging
import argparse
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader

# ===========================
# 🔧 Configuration
# ===========================
# Default paths if not provided via arguments
DEFAULT_INPUT_FOLDER = "input_pdfs"
DEFAULT_OUTPUT_FOLDER = "branded_pdfs"

# Branding assets (assumed to be in the same directory as the script)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COVER_IMAGE = os.path.join(SCRIPT_DIR, "firstpage.png")
LEFT_LOGO = os.path.join(SCRIPT_DIR, "toplabslogo.png")
RIGHT_LOGO = os.path.join(SCRIPT_DIR, "lab_thyrocare.png")

# ===========================
# 🪵 Logging
# ===========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("RebrandScript")

# ===========================
# 🎨 Branding Helpers
# ===========================
def create_cover_page(image_path):
    """Creates a PDF page with the given image as the full page content."""
    try:
        if not os.path.exists(image_path):
            logger.error(f"Cover image not found: {image_path}")
            return None
            
        packet = io.BytesIO()
        # A4 dimensions: 595.27563 x 841.8898 points
        c = canvas.Canvas(packet, pagesize=A4)
        width, height = A4
        
        # Draw image to fill the page
        c.drawImage(image_path, 0, 0, width=width, height=height)
        c.save()
        packet.seek(0)
        return PdfReader(packet).pages[0]
    except Exception as e:
        logger.error(f"Error creating cover page: {e}")
        return None

def create_header_overlay(left_image_path, right_image_path):
    """Creates a PDF page with a white header and two logos."""
    try:
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=A4)
        width, height = A4
        
        # Header height - approx 15% of page or fixed points
        header_height = 100 
        
        # Draw white rectangle at the top
        c.setFillColorRGB(1, 1, 1) # White
        c.rect(0, height - header_height, width, header_height, fill=1, stroke=0)
        
        # --- Left Logo ---
        if os.path.exists(left_image_path):
            try:
                img_left = ImageReader(left_image_path)
                iw_l, ih_l = img_left.getSize()
                aspect_l = ih_l / float(iw_l)
                target_h = header_height * 0.5
                target_w_l = target_h / aspect_l
                
                # Position: Left padded
                padding = 20
                x_l = padding
                y_l = height - (header_height / 2) - (target_h / 2)
                c.drawImage(left_image_path, x_l, y_l, width=target_w_l, height=target_h, mask='auto')
            except Exception as e:
                logger.warning(f"Failed to process left logo: {e}")
        
        # --- Right Logo ---
        if os.path.exists(right_image_path):
            try:
                img_right = ImageReader(right_image_path)
                iw_r, ih_r = img_right.getSize()
                aspect_r = ih_r / float(iw_r)
                target_h = header_height * 0.8 
                target_w_r = target_h / aspect_r
                
                # Position: Right padded
                padding = 20
                x_r = width - target_w_r - padding
                y_r = height - (header_height / 2) - (target_h / 2)
                c.drawImage(right_image_path, x_r, y_r, width=target_w_r, height=target_h, mask='auto')
            except Exception as e:
                logger.warning(f"Failed to process right logo: {e}")
        
        c.save()
        packet.seek(0)
        return PdfReader(packet).pages[0]
    except Exception as e:
        logger.error(f"Error creating header overlay: {e}")
        return None

def apply_branding_to_pdf(input_path, output_path):
    """
    Applies branding: New cover page, header on intermediate pages.
    """
    # Check for cover image existence
    if not os.path.exists(COVER_IMAGE):
        logger.warning(f"Branding missing: {COVER_IMAGE}. Copying original.")
        try:
            shutil.copy(input_path, output_path)
        except Exception as e:
            logger.error(f"Failed to copy original: {e}")
        return False

    try:
        writer = PdfWriter()
        reader = PdfReader(input_path)
        total_pages = len(reader.pages)
        
        if total_pages == 0:
            logger.warning(f"Skipping empty PDF: {input_path}")
            return False

        # 1. Add new Cover Page
        cover_page = create_cover_page(COVER_IMAGE)
        if cover_page:
           writer.add_page(cover_page)
        
        # 2. Process remaining pages
        header_overlay = create_header_overlay(LEFT_LOGO, RIGHT_LOGO)
        
        # Start from page 1 (skip original cover page 0 if it exists)
        # Requirement: "Removing the first page of existing PDFs"
        # If the PDF has only 1 page, we probably shouldn't remove it or maybe we remove it and add our cover only?
        # Typically "remove first page" implies the original report has a cover we want to replace.
        
        start_page_index = 1 if total_pages > 1 else 0
        
        for i in range(start_page_index, total_pages):
            original_page = reader.pages[i]
            
            # Check if it is the last page
            if i == total_pages - 1:
                # Do not brand the last page? Logic from new_reports.py:
                # "if i == total_pages - 1: writer.add_page(original_page)"
                writer.add_page(original_page)
            else:
                if header_overlay:
                    original_page.merge_page(header_overlay)
                writer.add_page(original_page)
            
        with open(output_path, "wb") as f:
            writer.write(f)
        
        logger.info(f"✨ Branded PDF saved to {output_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to apply branding to {input_path}: {e}")
        # Fallback
        try:
            shutil.copy(input_path, output_path)
            logger.info(f"⚠️ Copied original file due to error.")
        except:
            pass
        return False

def process_folder(input_folder, output_folder):
    """
    Process all PDFs in input_folder and save branded versions to output_folder.
    """
    if not os.path.exists(input_folder):
        logger.error(f"Input folder does not exist: {input_folder}")
        return

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        logger.info(f"Created output folder: {output_folder}")

    files = [f for f in os.listdir(input_folder) if f.lower().endswith(".pdf")]
    
    if not files:
        logger.warning(f"No PDF files found in {input_folder}")
        return

    logger.info(f"Found {len(files)} PDFs to process in {input_folder}")

    success_count = 0
    for filename in files:
        input_path = os.path.join(input_folder, filename)
        output_path = os.path.join(output_folder, filename)
        
        logger.info(f"Processing: {filename}")
        if apply_branding_to_pdf(input_path, output_path):
            success_count += 1
            
    logger.info(f"✅ Completed! Successfully branded {success_count}/{len(files)} files.")

def main():
    parser = argparse.ArgumentParser(description="Rebrand PDF reports in a folder.")
    parser.add_argument("--input", "-i", type=str, default=DEFAULT_INPUT_FOLDER, help="Input folder containing PDFs")
    parser.add_argument("--output", "-o", type=str, default=DEFAULT_OUTPUT_FOLDER, help="Output folder for branded PDFs")
    
    args = parser.parse_args()
    
    input_folder = os.path.abspath(args.input)
    output_folder = os.path.abspath(args.output)
    
    logger.info(f"Input Folder: {input_folder}")
    logger.info(f"Output Folder: {output_folder}")
    
    process_folder(input_folder, output_folder)

if __name__ == "__main__":
    main()
