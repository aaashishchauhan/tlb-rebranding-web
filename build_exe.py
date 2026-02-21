import PyInstaller.__main__
import os

# Define paths
entry_point = "gui_app.py"
icon_path = None  # Add an .ico path if you have one

# Build arguments
args = [
    entry_point,
    "--onefile",       # Single EXE
    "--windowed",      # No console window
    "--name=TLB_Rebranding_Pro",
    "--clean",
    # Collect all data for these packages
    "--collect-all", "customtkinter",
    "--collect-all", "spacy",
    "--collect-all", "en_core_web_sm",
    "--collect-all", "pdfplumber",
    # Hidden imports for modules used dynamically
    "--hidden-import=pypdf",
    "--hidden-import=reportlab",
    "--hidden-import=pdfplumber",
    "--hidden-import=name_extractor",
    "--hidden-import=rebrand_folder_app",
    "--hidden-import=queue_db",
    # Include the branding assets
    "--add-data=firstpage.png;.",
    "--add-data=toplabslogo.png;.",
    "--add-data=lab_thyrocare.png;.",
    # Include helper Python modules
    "--add-data=name_extractor.py;.",
    "--add-data=rebrand_folder_app.py;.",
]

if icon_path and os.path.exists(icon_path):
    args.append(f"--icon={icon_path}")

print("[*] Starting build process...")
print("This may take several minutes...")
PyInstaller.__main__.run(args)
print("[OK] Build complete! Check the 'dist' folder for TLB_Rebranding_Pro.exe")
