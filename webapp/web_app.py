"""
TLB Rebranding Pro — Web App
Flask server that serves a responsive UI and processes PDF uploads.
"""
import os
import sys
import uuid
import shutil
import zipfile
import tempfile
from flask import Flask, request, render_template, send_file, jsonify

# Backend modules are in the same directory
import rebrand_folder_app as app

# ---------------------
# Flask App Setup
# ---------------------
flask_app = Flask(__name__)
flask_app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max upload

TEMP_BASE = os.path.join(tempfile.gettempdir(), "tlb_webapp")


@flask_app.route("/")
def index():
    return render_template("index.html")


@flask_app.route("/process", methods=["POST"])
def process_pdfs():
    """
    Accepts uploaded PDFs + options, processes them, and returns a ZIP.
    """
    files = request.files.getlist("pdfs")
    if not files or files[0].filename == "":
        return jsonify({"error": "No PDF files uploaded"}), 400

    # Read options from form
    header_style = request.form.get("header_style", "branded")
    add_cover = request.form.get("add_cover", "true") == "true"
    remove_first_page = request.form.get("remove_first_page", "true") == "true"
    auto_rename = request.form.get("auto_rename", "true") == "true"
    merge_reports = request.form.get("merge_reports", "false") == "true"

    # Create unique temp directories
    job_id = uuid.uuid4().hex[:10]
    input_dir = os.path.join(TEMP_BASE, job_id, "input")
    output_dir = os.path.join(TEMP_BASE, job_id, "output")
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    try:
        # Save uploaded files
        for f in files:
            if f.filename.lower().endswith(".pdf"):
                safe_name = f.filename.replace("/", "_").replace("\\", "_")
                f.save(os.path.join(input_dir, safe_name))

        # Process using existing backend
        success, total = app.process_folder(
            input_dir,
            output_dir,
            header_style=header_style,
            add_cover=add_cover,
            rename=auto_rename,
            remove_first_page=remove_first_page,
            merge_reports=merge_reports,
        )

        # Check output
        output_files = [f for f in os.listdir(output_dir) if f.lower().endswith(".pdf")]
        if not output_files:
            return jsonify({"error": "Processing failed. No output files generated."}), 500

        # If single file, return it directly
        if len(output_files) == 1:
            output_path = os.path.join(output_dir, output_files[0])
            return send_file(
                output_path,
                as_attachment=True,
                download_name=output_files[0],
                mimetype="application/pdf",
            )

        # Multiple files: create a ZIP
        zip_path = os.path.join(TEMP_BASE, job_id, "TLB_Branded_Reports.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname in output_files:
                zf.write(os.path.join(output_dir, fname), fname)

        return send_file(
            zip_path,
            as_attachment=True,
            download_name="TLB_Branded_Reports.zip",
            mimetype="application/zip",
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        # Schedule cleanup (delay slightly so send_file completes)
        try:
            # We'll clean up old jobs on next request instead
            _cleanup_old_jobs(job_id)
        except Exception:
            pass


def _cleanup_old_jobs(current_job_id):
    """Remove temp folders from previous jobs (not the current one)."""
    if not os.path.exists(TEMP_BASE):
        return
    for d in os.listdir(TEMP_BASE):
        if d != current_job_id:
            try:
                shutil.rmtree(os.path.join(TEMP_BASE, d))
            except Exception:
                pass


if __name__ == "__main__":
    print("=" * 50)
    print("  TLB Rebranding Pro - Web App")
    print("  Open in browser: http://localhost:5000")
    print("  For mobile: http://<your-ip>:5000")
    print("=" * 50)
    flask_app.run(host="0.0.0.0", port=5000, debug=False)
