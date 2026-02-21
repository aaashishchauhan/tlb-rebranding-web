import os
import io
import shutil
import logging
import argparse
import re
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader

# ===========================
# 🔧 Configuration
# ===========================
DEFAULT_INPUT_FOLDER = "input_pdfs"
DEFAULT_OUTPUT_FOLDER = "branded_pdfs"

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

import pdfplumber
try:
    from name_extractor import extract_patient_name, extract_test_name, extract_age
except ImportError:
    logger.warning("name_extractor.py not found. Using fallback logic.")
    def extract_patient_name(path, original_filename=""): return "UnknownPatient", "fallback"
    def extract_test_name(text): return "REPORT"
    def extract_age(text): return ""

# ===========================
# 🎨 Branding Helpers
# ===========================

def extract_info_from_pdf(pdf_path):
    """
    Extracts Patient Name, Test Name, and Age from the PDF.
    Returns (patient_name, test_name, age)
    """
    try:
        # 1. Extract Patient Name
        patient_name, source = extract_patient_name(pdf_path, os.path.basename(pdf_path))
        
        # 2. Extract text for test name and age
        extracted_text = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    extracted_text += (page.extract_text() or "") + "\n"
        except Exception as e:
            logger.error(f"pdfplumber failed: {e}")
            
        test_name = extract_test_name(extracted_text)
        age = extract_age(extracted_text)
        
        # Clean up names for filesystem
        def clean_filename(name):
            if not name: return ""
            return re.sub(r'[\\/*?:"<>|]', "", name).strip()
            
        return clean_filename(patient_name) or "UnknownPatient", clean_filename(test_name) or "REPORT", age
    except Exception as e:
        logger.error(f"Error extracting info from {pdf_path}: {e}")
        return "UnknownPatient", "REPORT", ""

def create_cover_page(image_path):
    """Creates a PDF page with the given image as the full page content."""
    try:
        if not os.path.exists(image_path):
            logger.error(f"Cover image not found: {image_path}")
            return None
            
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=A4)
        width, height = A4
        c.drawImage(image_path, 0, 0, width=width, height=height)
        c.save()
        packet.seek(0)
        return PdfReader(packet).pages[0]
    except Exception as e:
        logger.error(f"Error creating cover page: {e}")
        return None

def create_header_overlay(left_logo=None, right_logo=None):
    """Creates a PDF page with a white header and optional logos."""
    try:
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=A4)
        width, height = A4
        header_height = 100 
        c.setFillColorRGB(1, 1, 1) # White
        c.rect(0, height - header_height, width, header_height, fill=1, stroke=0)

        # Left Logo
        if left_logo and os.path.exists(left_logo):
            try:
                img_l = ImageReader(left_logo)
                iw, ih = img_l.getSize()
                aspect = ih / float(iw)
                th = header_height * 0.5
                tw = th / aspect
                c.drawImage(left_logo, 20, height - (header_height / 2) - (th / 2),
                            width=tw, height=th, mask='auto')
            except Exception as e:
                logger.warning(f"Failed to draw left logo: {e}")

        # Right Logo
        if right_logo and os.path.exists(right_logo):
            try:
                img_r = ImageReader(right_logo)
                iw, ih = img_r.getSize()
                aspect = ih / float(iw)
                th = header_height * 0.8
                tw = th / aspect
                c.drawImage(right_logo, width - tw - 20,
                            height - (header_height / 2) - (th / 2),
                            width=tw, height=th, mask='auto')
            except Exception as e:
                logger.warning(f"Failed to draw right logo: {e}")

        c.save()
        packet.seek(0)
        return PdfReader(packet).pages[0]
    except Exception as e:
        logger.error(f"Error creating header overlay: {e}")
        return None

def apply_branding_to_pdf(input_path, output_dir, header_style="branded", add_cover=True,
                          rename=True, remove_first_page=True):
    """
    Applies branding and optionally renames the file.
    Options:
      - add_cover: prepend TLB branded cover page
      - header_style: 'none', 'white', or 'branded' (with logos)
      - remove_first_page: remove original first page from the PDF
      - rename: auto-rename to PatientName - TestName.pdf
    """
    try:
        reader = PdfReader(input_path)
        total_pages = len(reader.pages)
        if total_pages == 0:
            return False

        # Extract info for renaming if requested
        if rename:
            p_name, t_name, _ = extract_info_from_pdf(input_path)
            output_filename = f"{p_name} - {t_name}.pdf"
        else:
            output_filename = os.path.basename(input_path)
        
        output_path = os.path.join(output_dir, output_filename)
        writer = PdfWriter()

        # 1. Add Cover Page if requested
        if add_cover:
            cover_page = create_cover_page(COVER_IMAGE)
            if cover_page:
                writer.add_page(cover_page)
        
        # 2. Create Header Overlay based on style
        header_overlay = None
        if header_style == "branded":
            header_overlay = create_header_overlay(LEFT_LOGO, RIGHT_LOGO)
        elif header_style == "white":
            header_overlay = create_header_overlay()  # No logos = blank white
        
        # Determine start page: remove original first page if option toggled and PDF has >1 page
        if remove_first_page and total_pages > 1:
            start_page_index = 1
        else:
            start_page_index = 0
        
        for i in range(start_page_index, total_pages):
            original_page = reader.pages[i]
            # Apply header branding on all pages EXCEPT the last page (Terms & Conditions)
            if i < total_pages - 1:
                if header_overlay:
                    original_page.merge_page(header_overlay)
            
            writer.add_page(original_page)
            
        with open(output_path, "wb") as f:
            writer.write(f)
        
        logger.info(f"✨ Processed: {output_filename}")
        return True

    except Exception as e:
        logger.error(f"Failed to process {input_path}: {e}")
        return False

def process_folder(input_folder, output_folder, header_style="branded", add_cover=True,
                   rename=True, remove_first_page=True, merge_reports=False):
    """Process all PDFs in input_folder."""
    if not os.path.exists(input_folder):
        logger.error(f"Input folder does not exist: {input_folder}")
        return 0, 0

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    files = [f for f in os.listdir(input_folder) if f.lower().endswith(".pdf")]
    if not files:
        logger.warning(f"No PDF files found in {input_folder}")
        return 0, 0

    # Merge mode: group by patient and merge
    if merge_reports:
        return merge_patient_reports(input_folder, output_folder, header_style, add_cover,
                                      remove_first_page)

    # Normal mode: process individually
    success_count = 0
    for filename in files:
        input_path = os.path.join(input_folder, filename)
        if apply_branding_to_pdf(input_path, output_folder, header_style, add_cover,
                                  rename, remove_first_page):
            success_count += 1
            
    return success_count, len(files)

def merge_patient_reports(input_folder, output_folder, header_style="branded", add_cover=True,
                          remove_first_page=True):
    """
    Groups PDFs by patient (name + age), merges same-patient reports into one PDF.
    Cover page appears once. T&C (last page) appears once at the end.
    """
    from collections import defaultdict

    files = [f for f in os.listdir(input_folder) if f.lower().endswith(".pdf")]
    if not files:
        logger.warning(f"No PDF files found in {input_folder}")
        return 0, 0

    # Step 1: Extract info from every PDF and group by (name, age)
    patient_groups = defaultdict(list)  # key: (name_lower, age) -> list of (filepath, test_name)
    for filename in files:
        filepath = os.path.join(input_folder, filename)
        try:
            p_name, t_name, age = extract_info_from_pdf(filepath)
            key = (p_name.strip().lower(), age.strip())
            patient_groups[key].append((filepath, p_name, t_name))
        except Exception as e:
            logger.error(f"Failed to extract info from {filename}: {e}")

    logger.info(f"Found {len(patient_groups)} unique patients from {len(files)} PDFs.")

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    header_overlay = None
    if header_style == "branded":
        header_overlay = create_header_overlay(LEFT_LOGO, RIGHT_LOGO)
    elif header_style == "white":
        header_overlay = create_header_overlay()  # No logos = blank white

    success_count = 0
    total_output = 0

    for (name_key, age_key), group in patient_groups.items():
        total_output += 1

        if len(group) == 1:
            # Single report — process normally
            filepath, p_name, t_name = group[0]
            output_filename = f"{p_name} - {t_name}.pdf"
            output_path = os.path.join(output_folder, output_filename)
            try:
                if apply_branding_to_pdf(filepath, output_folder, header_style, add_cover,
                                          rename=True, remove_first_page=remove_first_page):
                    success_count += 1
            except Exception as e:
                logger.error(f"Failed single report {filepath}: {e}")
            continue

        # Multiple reports for same patient — MERGE
        p_name = group[0][1]  # Use the patient name from first report
        test_names = [g[2] for g in group]
        combined_test = " + ".join(test_names)
        output_filename = f"{p_name} - {combined_test}.pdf"
        output_path = os.path.join(output_folder, output_filename)

        logger.info(f"🔗 Merging {len(group)} reports for patient: {p_name} (Age: {age_key})")

        try:
            writer = PdfWriter()

            # 1. Add single TLB cover page
            if add_cover:
                cover_page = create_cover_page(COVER_IMAGE)
                if cover_page:
                    writer.add_page(cover_page)

            # Collect the T&C page (last page of the last report) to add at the end
            tc_page = None

            for idx, (filepath, _, _) in enumerate(group):
                reader = PdfReader(filepath)
                total_pages = len(reader.pages)
                if total_pages == 0:
                    continue

                # Determine page range for this report
                start_idx = 1 if (remove_first_page and total_pages > 1) else 0
                end_idx = total_pages - 1  # Exclude last page (T&C) from content

                # Save T&C from the last report in the group
                if idx == len(group) - 1 and total_pages > 1:
                    tc_page = reader.pages[total_pages - 1]

                # If the PDF only has 1 page (after removing first), handle edge case
                if start_idx >= total_pages:
                    continue

                # If removing first page and T&C leaves nothing, include all content
                if end_idx <= start_idx:
                    end_idx = total_pages  # Include everything except what we skipped

                for i in range(start_idx, end_idx):
                    page = reader.pages[i]
                    if header_overlay:
                        page.merge_page(header_overlay)
                    writer.add_page(page)

            # 2. Add T&C page once at the very end (no header branding)
            if tc_page:
                writer.add_page(tc_page)

            with open(output_path, "wb") as f:
                writer.write(f)

            logger.info(f"✨ Merged report saved: {output_filename}")
            success_count += 1

        except Exception as e:
            logger.error(f"Failed to merge reports for {p_name}: {e}")

    return success_count, total_output

def main():
    parser = argparse.ArgumentParser(description="Rebrand PDF reports.")
    parser.add_argument("--input", "-i", type=str, default=DEFAULT_INPUT_FOLDER)
    parser.add_argument("--output", "-o", type=str, default=DEFAULT_OUTPUT_FOLDER)
    parser.add_argument("--no-header", action="store_false", dest="header", help="Disable white header")
    parser.add_argument("--no-cover", action="store_false", dest="cover", help="Disable cover page")
    parser.add_argument("--no-rename", action="store_false", dest="rename", help="Disable auto-renaming")
    parser.set_defaults(header=True, cover=True, rename=True)
    
    args = parser.parse_args()
    success, total = process_folder(args.input, args.output, args.header, args.cover, args.rename)
    logger.info(f"✅ Completed: {success}/{total} files processed.")

if __name__ == "__main__":
    main()
