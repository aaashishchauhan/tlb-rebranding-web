import customtkinter as ctk
import os
import threading
import time
import logging
from tkinter import filedialog, messagebox
from PIL import Image
import rebrand_folder_app as app

# ---------------- Logging ----------------
logging.basicConfig(
    filename="log.txt",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# --- Design Tokens ---
COLOR_PRIMARY = "#00C896"
COLOR_BG = "#0E1117"
COLOR_SURFACE = "#161B22"
COLOR_CARD = "#1F2630"
COLOR_TEXT = "#E6EDF3"
COLOR_MUTED = "#8B949E"

APP_NAME = "TLB Rebranding Pro"
LOGO_PATH = "logo.png"


class RebrandApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(APP_NAME)
        self.geometry("720x620")
        self.minsize(680, 580)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

        self.configure(fg_color=COLOR_BG)

        # State
        self.input_folder = ctk.StringVar(value="")
        self.output_folder = ctk.StringVar(value="")
        self.header_style = ctk.StringVar(value="Branded Header")
        self.add_cover = ctk.BooleanVar(value=True)
        self.auto_rename = ctk.BooleanVar(value=True)
        self.remove_first_page = ctk.BooleanVar(value=True)
        self.merge_reports = ctk.BooleanVar(value=False)
        self.print_after_process = ctk.BooleanVar(value=False)
        self.dark_mode = True

        self._setup_ui()

    # ---------------- UI ----------------
    def _setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(self, width=220, fg_color=COLOR_SURFACE)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)

        if os.path.exists(LOGO_PATH):
            logo_img = ctk.CTkImage(Image.open(LOGO_PATH), size=(60, 60))
            ctk.CTkLabel(sidebar, image=logo_img, text="").pack(pady=(30, 10))

        ctk.CTkLabel(
            sidebar,
            text=APP_NAME,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_TEXT,
            wraplength=180,
            justify="center"
        ).pack(pady=(0, 30))

        main_container = ctk.CTkFrame(self, fg_color=COLOR_BG)
        main_container.grid(row=0, column=1, sticky="nsew")
        main_container.grid_columnconfigure(0, weight=1)
        main_container.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(main_container)
        scroll.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        scroll.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            scroll,
            text="Rebranding Dashboard",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=COLOR_PRIMARY
        ).grid(row=0, column=0, sticky="w", pady=(10, 20))

        # Stats
        stats_card = ctk.CTkFrame(scroll, fg_color=COLOR_CARD)
        stats_card.grid(row=1, column=0, sticky="ew", pady=(0, 20))
        stats_card.grid_columnconfigure((0, 1, 2), weight=1)

        self.stat_input = ctk.CTkLabel(stats_card, text="Input: 0")
        self.stat_input.grid(row=0, column=0, pady=20)

        self.stat_output = ctk.CTkLabel(stats_card, text="Output: 0")
        self.stat_output.grid(row=0, column=1, pady=20)

        self.stat_status = ctk.CTkLabel(stats_card, text="Status: Idle")
        self.stat_status.grid(row=0, column=2, pady=20)

        # Folder
        folder_card = ctk.CTkFrame(scroll, fg_color=COLOR_CARD)
        folder_card.grid(row=2, column=0, sticky="ew", pady=15)
        folder_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(folder_card, text="Input Folder", text_color=COLOR_MUTED).grid(row=0, column=0, sticky="w", padx=25, pady=(20, 5))

        input_row = ctk.CTkFrame(folder_card, fg_color="transparent")
        input_row.grid(row=1, column=0, sticky="ew", padx=25)
        input_row.grid_columnconfigure(0, weight=1)

        ctk.CTkEntry(input_row, textvariable=self.input_folder, height=42).grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ctk.CTkButton(input_row, text="Browse", width=110, height=42, fg_color=COLOR_PRIMARY, command=self._browse_input).grid(row=0, column=1)

        ctk.CTkLabel(folder_card, text="Output Folder (Base)", text_color=COLOR_MUTED).grid(row=2, column=0, sticky="w", padx=25, pady=(20, 5))

        output_row = ctk.CTkFrame(folder_card, fg_color="transparent")
        output_row.grid(row=3, column=0, sticky="ew", padx=25, pady=(0, 20))
        output_row.grid_columnconfigure(0, weight=1)

        ctk.CTkEntry(output_row, textvariable=self.output_folder, height=42).grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ctk.CTkButton(output_row, text="Browse", width=110, height=42, fg_color=COLOR_PRIMARY, command=self._browse_output).grid(row=0, column=1)

        # Options
        options_card = ctk.CTkFrame(scroll, fg_color=COLOR_CARD)
        options_card.grid(row=3, column=0, sticky="ew", pady=15)
        options_card.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(options_card, text="Header Style", text_color=COLOR_MUTED).grid(row=0, column=0, padx=25, pady=(20, 5), sticky="w")
        ctk.CTkOptionMenu(options_card, variable=self.header_style,
                          values=["No Header", "White Header", "Branded Header"],
                          width=180, height=36, fg_color=COLOR_SURFACE
                          ).grid(row=0, column=0, padx=25, pady=(45, 10), sticky="w")
        ctk.CTkSwitch(options_card, text="Add Cover Page", variable=self.add_cover).grid(row=0, column=1, padx=25, pady=(20, 10), sticky="w")
        ctk.CTkSwitch(options_card, text="Auto Rename Files", variable=self.auto_rename).grid(row=1, column=0, padx=25, pady=(10, 10), sticky="w")
        ctk.CTkSwitch(options_card, text="Remove First Page", variable=self.remove_first_page).grid(row=1, column=1, padx=25, pady=(10, 10), sticky="w")
        ctk.CTkSwitch(options_card, text="Merge Patient Reports", variable=self.merge_reports).grid(row=2, column=0, padx=25, pady=(10, 10), sticky="w")
        ctk.CTkSwitch(options_card, text="Print After Process", variable=self.print_after_process).grid(row=2, column=1, padx=25, pady=(10, 20), sticky="w")

        # Action
        action_card = ctk.CTkFrame(scroll, fg_color=COLOR_CARD)
        action_card.grid(row=4, column=0, sticky="ew", pady=20)
        action_card.grid_columnconfigure(0, weight=1)

        self.process_btn = ctk.CTkButton(
            action_card,
            text="START REBRANDING",
            height=55,
            font=ctk.CTkFont(size=18, weight="bold"),
            fg_color=COLOR_PRIMARY,
            command=self._start_processing
        )
        self.process_btn.grid(row=0, column=0, padx=25, pady=(25, 15), sticky="ew")

        self.status_label = ctk.CTkLabel(action_card, text="Ready", text_color=COLOR_MUTED)
        self.status_label.grid(row=1, column=0)

        self.progress_percent = ctk.CTkLabel(action_card, text="0%")
        self.progress_percent.grid(row=2, column=0, pady=(5, 0))

        self.progress_bar = ctk.CTkProgressBar(action_card)
        self.progress_bar.grid(row=3, column=0, sticky="ew", padx=40, pady=10)
        self.progress_bar.set(0)

        self.open_output_btn = ctk.CTkButton(
            action_card,
            text="Open Rebranded Folder",
            state="disabled",
            command=self._open_output
        )
        self.open_output_btn.grid(row=4, column=0, pady=(10, 25))

    # ---------------- Logic ----------------

    def _browse_input(self):
        path = filedialog.askdirectory()
        if path:
            self.input_folder.set(path)
            self.output_folder.set(path)

    def _browse_output(self):
        path = filedialog.askdirectory()
        if path:
            self.output_folder.set(path)

    def _open_output(self):
        path = self.output_folder.get()
        new_folder = os.path.join(path, "TLB_Rebranded_Output")
        if os.path.exists(new_folder):
            os.startfile(new_folder)

    def _start_processing(self):
        in_p = self.input_folder.get()
        base_out = self.output_folder.get()

        if not in_p or not base_out:
            messagebox.showwarning("Warning", "Please select input folder.")
            return

        if not os.path.exists(in_p):
            messagebox.showerror("Error", "Input folder does not exist.")
            return

        final_output = os.path.join(base_out, "TLB_Rebranded_Output")
        os.makedirs(final_output, exist_ok=True)

        try:
            total_files = len([f for f in os.listdir(in_p) if f.lower().endswith(".pdf")])
        except Exception as e:
            logging.exception("Folder read error")
            messagebox.showerror("Error", str(e))
            return

        self.stat_input.configure(text=f"Input: {total_files}")
        self.stat_status.configure(text="Status: Processing")

        self.process_btn.configure(state="disabled")
        self.status_label.configure(text="Processing...", text_color=COLOR_PRIMARY)
        self.progress_bar.set(0)
        self.progress_percent.configure(text="0%")

        threading.Thread(
            target=self._run_logic,
            args=(in_p, final_output, total_files),
            daemon=True
        ).start()

    def _run_logic(self, input_path, output_path, total_files):
        try:
            # Map dropdown label to backend value
            style_map = {"No Header": "none", "White Header": "white", "Branded Header": "branded"}
            header_val = style_map.get(self.header_style.get(), "branded")

            success, total = app.process_folder(
                input_path,
                output_path,
                header_style=header_val,
                add_cover=self.add_cover.get(),
                rename=self.auto_rename.get(),
                remove_first_page=self.remove_first_page.get(),
                merge_reports=self.merge_reports.get()
            )

            percent = 100 if total_files == 0 else int((success / total_files) * 100)
            self.after(0, lambda: self._on_finish(success, total, output_path, percent))

        except Exception as e:
            logging.exception("Processing error")
            self.after(0, lambda: self._on_error(str(e)))

    def _on_finish(self, success, total, output_path, percent):
        self.progress_bar.set(1)
        self.progress_percent.configure(text=f"{percent}%")
        self.process_btn.configure(state="normal")

        self.status_label.configure(
            text=f"Completed: {success}/{total} files processed.",
            text_color=COLOR_PRIMARY
        )

        self.stat_output.configure(text=f"Output: {success}")
        self.stat_status.configure(text="Status: Completed")

        self.open_output_btn.configure(state="normal")
        self.output_folder.set(os.path.dirname(output_path))

        messagebox.showinfo(APP_NAME, f"Done! {success} files processed successfully.")

        if self.print_after_process.get():
            self._print_files_one_by_one(output_path)

    def _on_error(self, error):
        self.progress_bar.set(0)
        self.progress_percent.configure(text="0%")
        self.process_btn.configure(state="normal")
        self.stat_status.configure(text="Status: Error")
        self.status_label.configure(text=f"Error: {error}", text_color="red")
        messagebox.showerror(APP_NAME, f"An error occurred:\n{error}")

    def _print_files_one_by_one(self, folder_path):
        try:
            files = [f for f in os.listdir(folder_path) if f.lower().endswith(".pdf")]
        except Exception as e:
            logging.exception("Print folder read error")
            messagebox.showerror("Print Error", str(e))
            return

        total = len(files)
        printed = 0

        for index, file in enumerate(files, start=1):
            full_path = os.path.join(folder_path, file)

            answer = messagebox.askyesno(
                "Print File",
                f"Print file {index}/{total}?\n{file}"
            )

            if answer:
                try:
                    os.startfile(full_path, "print")
                    printed += 1
                    self.stat_status.configure(text=f"Printing {index}/{total}")
                    time.sleep(2)
                except Exception as e:
                    logging.exception(f"Print failed for {file}")
                    messagebox.showerror(
                        "Print Error",
                        f"Failed to print {file}\n{str(e)}"
                    )

        self.stat_status.configure(text=f"Printed {printed}/{total}")


if __name__ == "__main__":
    app_window = RebrandApp()
    app_window.mainloop()
