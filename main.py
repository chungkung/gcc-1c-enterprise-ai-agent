import customtkinter
import zhipuai
import os
import sys
import threading
import queue
import json
import datetime # For timestamped history files
import pathlib # For directory handling
from tkinter import messagebox, filedialog # For delete confirmation & file dialogs
from PIL import Image, ImageFilter # Import ImageFilter for blur

# --- Configuration ---
MAX_HISTORY_TURNS = 5
WINDOW_TITLE = "GCC - CC7 AI Agent"
INITIAL_MODE = "general"
MODES = ["通用 / General", "devops", "blog"] # Added Chinese prefix
HISTORY_DIR = "chat_history"
ICON_FILE = "logo.ico"
BACKGROUND_IMAGE_FILE = None
CLEAN_DIR = "data/clean_bsl"
SPLIT_DIR = "data/split"

if os.path.exists("background.jpg"):
    BACKGROUND_IMAGE_FILE = "background.jpg"
elif os.path.exists("background.png"):
    BACKGROUND_IMAGE_FILE = "background.png"
else:
    print("警告: 未找到背景图片 'background.jpg' 或 'background.png'")
print(f"--- Using background image: {BACKGROUND_IMAGE_FILE} ---") # Debug Print

# Adjust keywords if needed, keys in SYSTEM_PROMPTS must match lower() of first part
DEVOP_KEYWORDS = ["linux", "服务器", "运维", "docker", "kubernetes", "nginx", "网络", "命令", "报错"]
BLOG_KEYWORDS = ["博客", "写作", "文章", "撰写", "构思", "草稿", "润色", "大纲"]
SYSTEM_PROMPTS = {
    "通用 / general": "你是一个乐于助人的人工智能助手，名叫小G (GCC)。", # Key updated
    "devops": "你是一个经验丰富的运维工程师和 Linux 系统管理员，名叫小G (GCC)。请专业、准确、详细地回答以下运维相关问题，并在适当时提供命令示例或配置建议。",
    "blog": "你是一位优秀的技术作家和博主，名叫小G (GCC)。请根据用户的要求，在博客文章的构思、草稿撰写、内容组织、语言润色等方面提供帮助。"
}
# Derive API keys from the MODES list
MODE_API_KEYS = [m.lower() for m in MODES]
if "通用 / general" in MODE_API_KEYS:
     MODE_API_KEYS[MODE_API_KEYS.index("通用 / general")] = "general" # Use simple key for API mapping

# --- Predefined Q&A --- Added (Using triple quotes for values)
PREDEFINED_QA = {
    "gcc是什么": """GCC项目，是本公司-(中国化学工程第七建设有限公司)承建的俄罗斯波罗的海化工综合体GCC项目，该项目总投资120亿欧元，预计工期5年，工签一年一签，可续签，预计在2026年完工。""",
    "cc7是什么": """是本公司的英文，我们的中文叫中国化学工程第七建设有限公司，简称"七化建"(CC7)，是隶属于国务院国有资产监督管理委员会管理的中国化学工程集团有限公司。在上市与定位上，本公司于2010年随集团在上交所上市，总部位于成渝双城经济圈的龙泉驿区，是中央在四川的重要骨干企业。自1964年成立以来，本公司一直致力于在国际舞台上展现其作为工程承包商的卓越能力。此外，本公司近年来在国际市场上取得了显著的成绩。本公司在2020年ENR全球最大250家工程承包商排名中列第22位，同时在美国《化学周刊》公布的全球油气相关行业工程建设公司排名中居全球第2位。此外，公司荣获2021年度对外承包工程企业100强第15名和欧洲地区30强第2名的殊荣，这些成绩彰显了公司在行业中的领先地位。""",
    "北海分公司的职责是什么": """七化建北海分公司的业务领域广泛，比如GCC就是北海分公司负责的噢。另外还主要包括石油化工、房屋建筑、水利水电、市政公用、道路桥梁等EPC总承包、技术开发、实业投资和贸易等领域。自2010年进入相关国别以来，北海分公司相继签约了10余个大型、超大型项目，形成了化肥、炼化、炼油、天然气处理和基础设施五大板块的合理布局，致力于打造世界一流的工程承包商‌。""",
    "罗文豪爱梁仁璐吗": """爱不释手，love renlu forever ! ! !"""
}

def normalize_question(text):
    """Helper to normalize question for matching."""
    return text.lower().replace("？", "").replace("?", "").strip()

try:
    api_key = os.environ["ZHIPUAI_API_KEY"]
except KeyError:
    print("错误：未找到 ZHIPUAI_API_KEY 环境变量。请设置后重试。")
    sys.exit(1)

try:
    client = zhipuai.ZhipuAI(api_key=api_key)
except Exception as e:
    print(f"初始化 ZhipuAI 客户端时出错: {e}")
    sys.exit(1)

pathlib.Path(HISTORY_DIR).mkdir(parents=True, exist_ok=True)
os.makedirs(SPLIT_DIR, exist_ok=True)


# --- History Window Class --- <--- Added Selection Highlighting
class HistoryWindow(customtkinter.CTkToplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.geometry("900x600")
        self.title("历史记录 / История")
        self.transient(master)
        self.grab_set()

        self.selected_filepath = None
        self.session_buttons = {} # Map button object to filepath
        self.selected_button = None # Keep track of selected button
        # Define selection color (adjust as needed)
        self.selected_color = "#555555" # Greyish selection
        # Get default color dynamically, check if available
        try:
            self.default_button_color = customtkinter.ThemeManager.theme["CTkButton"]["fg_color"]
        except KeyError:
            # Fallback if theme data structure changes
            self.default_button_color = ("#3B8ED0", "#1F6AA5") # Default blue theme colors

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        # --- Session List Frame ---
        self.session_list_frame = customtkinter.CTkScrollableFrame(self, label_text="会话记录")
        self.session_list_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.populate_session_list()

        # --- Session Content Display ---
        self.session_display = customtkinter.CTkTextbox(self, wrap="word", state="disabled")
        self.session_display.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        self.session_display.tag_config("user_tag", foreground="#5DADE2")
        self.session_display.tag_config("assistant_tag", foreground="#58D68D")
        self.session_display.tag_config("system_tag", foreground="#AEAEAE")

        # --- Buttons --- (Border width already added)
        self.button_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.button_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        self.delete_button = customtkinter.CTkButton(self.button_frame, text="删除选中记录", command=self.delete_selected_session, border_width=1)
        self.delete_button.pack(side="left", padx=5)
        self.close_button = customtkinter.CTkButton(self.button_frame, text="关闭", command=self.destroy, border_width=1)
        self.close_button.pack(side="right", padx=5)

    def populate_session_list(self):
        # ... (Clear existing buttons - same as before)
        for widget in self.session_list_frame.winfo_children():
            widget.destroy()
        self.session_buttons.clear()
        self.selected_filepath = None
        self.selected_button = None

        try:
            session_files = sorted(pathlib.Path(HISTORY_DIR).glob("session_*.json"), key=os.path.getmtime, reverse=True)
            if not session_files:
                no_history_label = customtkinter.CTkLabel(self.session_list_frame, text="(无历史记录)")
                no_history_label.pack(pady=10)
            else:
                for file_path in session_files:
                    try:
                        ts_str = file_path.stem.split('_')[1] + "_" + file_path.stem.split('_')[2]
                        dt_obj = datetime.datetime.strptime(ts_str, '%Y%m%d_%H%M%S')
                        display_name = dt_obj.strftime('%Y-%m-%d %H:%M:%S')
                    except (IndexError, ValueError):
                        display_name = file_path.name

                    session_button = customtkinter.CTkButton(
                        self.session_list_frame,
                        text=display_name,
                        # Pass button itself to the command
                        command=lambda fp=file_path, btn=None: self.select_session(fp, btn),
                        anchor="w",
                        border_width=1 # Give session buttons a border too?
                    )
                    # Assign the button to the lambda after creation
                    session_button.configure(command=lambda fp=file_path, btn=session_button: self.select_session(fp, btn))
                    session_button.pack(fill="x", padx=5, pady=2)
                    self.session_buttons[session_button] = file_path

        except Exception as e:
            messagebox.showerror("错误", f"无法读取历史记录目录: {e}", parent=self)
            error_label = customtkinter.CTkLabel(self.session_list_frame, text="(读取错误)")
            error_label.pack(pady=10)

    def select_session(self, filepath, button):
        """Highlights the selected button and loads the session."""
        # Reset previous button color if one was selected
        if self.selected_button and self.selected_button in self.session_buttons:
            # Check if the button still exists before configuring
            if self.selected_button.winfo_exists():
                self.selected_button.configure(fg_color=self.default_button_color)

        # Set new selection
        self.selected_filepath = filepath
        self.selected_button = button
        # Check if the new button exists before configuring
        if self.selected_button.winfo_exists():
            self.selected_button.configure(fg_color=self.selected_color) # Highlight selected

        self.load_selected_session()

    def load_selected_session(self):
        # ... (Loading logic remains the same) ...
        if not self.selected_filepath:
            return
        filepath = self.selected_filepath
        self.session_display.configure(state="normal")
        self.session_display.delete("1.0", "end")
        try:
            with open(filepath, 'r', encoding='utf-8') as f: messages = json.load(f)
            if isinstance(messages, list):
                for msg in messages:
                    role, content = msg.get("role"), msg.get("content", "")
                    if role == "user": self.session_display.insert("end", f"你: {content}\n", "user_tag")
                    elif role == "assistant": self.session_display.insert("end", f"小G: {content}\n", "assistant_tag")
            else: self.session_display.insert("end", "错误: 文件格式无效。")
        except (json.JSONDecodeError, IOError, Exception) as e: self.session_display.insert("end", f"无法加载会话: {e}")
        finally: self.session_display.configure(state="disabled")

    def delete_selected_session(self):
        # ... (Deletion logic remains the same) ...
        if not self.selected_filepath: messagebox.showwarning("警告", "请先点击选择一个会话记录。", parent=self); return
        filepath = self.selected_filepath
        confirm = messagebox.askyesno("确认删除", f"确定要永久删除选中的历史记录吗？\n({filepath.name})", parent=self)
        if confirm:
            try:
                os.remove(filepath)
                self.populate_session_list() # Also clears selection variables
                self.session_display.configure(state="normal"); self.session_display.delete("1.0", "end"); self.session_display.configure(state="disabled")
            except OSError as e: messagebox.showerror("错误", f"无法删除文件: {e}", parent=self)

# --- Main GUI Application Class --- <--- Changed Layout Strategy
class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        self.title(WINDOW_TITLE)
        self.geometry("800x600")
        if os.path.exists(ICON_FILE):
            try:
                self.iconbitmap(ICON_FILE)
            except Exception as e: print(f"加载图标失败: {e}")
        else: print(f"警告: 图标文件 '{ICON_FILE}' 未找到。")

        customtkinter.set_appearance_mode("dark")
        customtkinter.set_default_color_theme("blue")

        self.current_mode = "general" # Set initial mode to the simple key
        self.messages = []
        self.response_queue = queue.Queue()
        self.is_generating = False
        self.bg_image_tk = None
        self.history_window = None
        self.tooltip_window = None # For tooltips
        self.tooltip_hide_after_id = None # ID for scheduled tooltip hide

        # --- Configure Main Grid --- (Directly on self)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0) # Top controls row
        self.grid_rowconfigure(1, weight=1) # Chat display row (expands)
        self.grid_rowconfigure(2, weight=0) # Input frame row
        self.grid_rowconfigure(3, weight=0) # Send button row

        # --- Background Label --- (Placed first)
        if BACKGROUND_IMAGE_FILE:
            try:
                print(f"--- Attempting Image.open: {BACKGROUND_IMAGE_FILE} ---")
                raw_image = Image.open(BACKGROUND_IMAGE_FILE)
                print(f"--- Image opened, size: {raw_image.size} ---")
                # --- >>> Apply Gaussian Blur <<< ---
                blurred_image = raw_image.filter(ImageFilter.GaussianBlur(radius=15)) # Adjust radius as needed
                print(f"--- Image blurred --- ")
                # --- Use blurred image for resizing --- 
                win_w, win_h = 800, 600 # Initial size
                self.bg_image_tk = self.resize_and_prepare_image(blurred_image, win_w, win_h)
                if self.bg_image_tk:
                    print(f"--- CTkImage created: {self.bg_image_tk} --- ")
                    self.bg_label = customtkinter.CTkLabel(self, image=self.bg_image_tk, text="")
                    # Place behind everything, covering the whole window
                    self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
                    self.bg_label.lower()
                    print("--- Background label placed and lowered ---")
                else:
                    print("--- Background CTkImage is None after resize --- ")
            except FileNotFoundError:
                 print(f"--- ERROR: Background file not found at path: {os.path.abspath(BACKGROUND_IMAGE_FILE)} ---")
            except Exception as e:
                print(f"加载或处理背景图片失败: {e}")
                self.bg_image_tk = None
        else:
             print("--- No background image file specified --- ")

        # --- Widgets Placed Directly on Main Window Grid --- #

        # --- Top Frame for Controls ---
        self.top_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.top_frame.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")
        self.top_frame.grid_columnconfigure(1, weight=1) # Allow combobox to expand
        self.mode_var = customtkinter.StringVar(value=self.get_display_mode(self.current_mode))
        self.mode_menu = customtkinter.CTkOptionMenu(self.top_frame, values=MODES, command=self.change_mode_manual, variable=self.mode_var, width=150)
        self.mode_menu.grid(row=0, column=0, padx=(0, 5), sticky="w")
        self.history_button = customtkinter.CTkButton(self.top_frame, text="历史 / History", command=self.open_history_window, border_width=1)
        self.history_button.grid(row=0, column=1, padx=(5, 0), sticky="e")

        # --- Chat Display Textbox ---
        self.chat_display = customtkinter.CTkTextbox(self, wrap="word", state="disabled", fg_color="#EEEEEE", border_width=0)
        self.chat_display.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.chat_display.tag_config("user_tag", foreground="#007ACC")
        self.chat_display.tag_config("assistant_tag", foreground="#4CAF50")
        self.chat_display.tag_config("system_tag", foreground="#888888")
        self.chat_display.configure(text_color="#000000")

        # --- Input Frame ---
        self.input_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.input_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        self.input_frame.grid_columnconfigure(3, weight=1) # Input entry expands

        # Define a larger font for icon buttons
        icon_font = ("Segoe UI Emoji", 20) # Adjust font/size as needed

        # Connect buttons to actual functions
        self.attach_button = customtkinter.CTkButton(self.input_frame, text="📎", width=40, font=icon_font, command=self.select_attachment) 
        self.attach_button.grid(row=0, column=0, padx=(5, 2))
        self.create_tooltip(self.attach_button, "选择文件 / Выбрать файл")

        self.image_button = customtkinter.CTkButton(self.input_frame, text="🖼️", width=40, font=icon_font, command=self.select_image) 
        self.image_button.grid(row=0, column=1, padx=2)
        self.create_tooltip(self.image_button, "选择图片 / Выбрать изображение")

        self.mic_button = customtkinter.CTkButton(self.input_frame, text="🎤", width=40, font=icon_font, command=self.select_audio) 
        self.mic_button.grid(row=0, column=2, padx=(2, 5))
        self.create_tooltip(self.mic_button, "选择音频 / Выбрать аудио")

        # Input Entry
        self.input_entry = customtkinter.CTkEntry(self.input_frame, placeholder_text="在此输入消息...", fg_color="#EEEEEE", border_width=0)
        self.input_entry.configure(text_color="#000000")
        self.input_entry.grid(row=0, column=3, sticky="ew")
        self.input_entry.bind("<Return>", self.send_message_event)

        # --- Send Button ---
        self.send_button = customtkinter.CTkButton(self, text="发送 / Отправить", command=self.send_message_event, font=("Arial", 14), border_width=1)
        self.send_button.grid(row=3, column=0, padx=10, pady=(5, 10), sticky="ew")

        # --- Initial Welcome & Queue & Focus ---
        # Add copyright info to welcome message
        welcome_text = "你好👋！我是CC7罗文豪的人工智能助手GCC，可以叫我小G，很高兴见到你，欢迎问我任何问题。\n\n@版权所有: 中国化学工程第七建设有限公司北海分公司IT管理部(罗文豪)\n"
        self.add_message_to_display(welcome_text, "system_tag") 
        self.update_mode_display()
        self.after(100, self.process_response_queue)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.after(100, self.set_initial_focus) # Set focus after init

    def set_initial_focus(self):
        """Sets focus away from input initially."""
        self.focus_set() # Set focus to the main window

    def placeholder_action(self):
        """Placeholder for unimplemented button actions."""
        print("功能暂未实现 / Feature not implemented yet.")

    # --- Tooltip Methods --- # Added
    def create_tooltip(self, widget, text):
        widget.bind("<Enter>", lambda event, txt=text: self.show_tooltip(event, txt))
        # Schedule hide_tooltip with delay on Leave, store ID
        widget.bind("<Leave>", lambda event: self.schedule_hide_tooltip()) 

    def show_tooltip(self, event, text):
        # Cancel any pending hide operations
        if self.tooltip_hide_after_id:
            self.after_cancel(self.tooltip_hide_after_id)
            self.tooltip_hide_after_id = None
        
        # Destroy any existing tooltip immediately
        if self.tooltip_window and self.tooltip_window.winfo_exists():
            self.tooltip_window.destroy()
        self.tooltip_window = None

        # Create and show the new tooltip
        x = self.winfo_pointerx() + 15; y = self.winfo_pointery() + 10
        self.tooltip_window = customtkinter.CTkToplevel(self); self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        label = customtkinter.CTkLabel(self.tooltip_window, text=text, corner_radius=5, fg_color=("#444444", "#DDDDDD"), text_color=("#FFFFFF", "#111111")); label.pack()
        # No longer need bindings on the tooltip window itself with this logic

    def schedule_hide_tooltip(self):
        # Schedule hide after 50ms if not already scheduled
        if not self.tooltip_hide_after_id:
             self.tooltip_hide_after_id = self.after(50, self.hide_tooltip) # 50ms delay

    def hide_tooltip(self):
        # Clear the scheduled ID
        self.tooltip_hide_after_id = None
        # Destroy the window if it exists
        widget = self.tooltip_window
        self.tooltip_window = None
        if widget and widget.winfo_exists():
            widget.destroy()

    # --- Utility to get display mode name --- # Added
    def get_display_mode(self, internal_mode_key):
        for mode in MODES:
            if mode.lower().startswith(internal_mode_key):
                return mode
        # Correct fallback if initial mode itself has prefix
        for mode in MODES: 
             if mode.lower().startswith(INITIAL_MODE): return mode 
        return INITIAL_MODE.capitalize()

    # --- Utility to get internal mode key --- # Added
    def get_internal_mode_key(self, display_mode_name):
         if display_mode_name == "通用 / General":
              return "general"
         else:
              return display_mode_name.lower()

    # --- Background Image Resizing Helper --- # Added
    def resize_and_prepare_image(self, img, target_w, target_h):
        try:
            img_w, img_h = img.size
            scale = max(target_w / img_w, target_h / img_h)
            new_w, new_h = int(img_w * scale), int(img_h * scale)
            resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            # Use CTkImage now
            return customtkinter.CTkImage(light_image=resized, dark_image=resized, size=(new_w, new_h))
        except Exception as e:
            print(f"Error resizing image: {e}")
            return None

    # --- File Selection Methods --- # Added
    def select_attachment(self):
        filepath = filedialog.askopenfilename(title="选择附件 (上传附件)")
        if filepath:
            filename = os.path.basename(filepath)
            print(f"Selected attachment: {filepath}")
            content_preview = f"[附件已选择: {filename}]"
            # Try reading simple text files
            if filename.lower().endswith('.txt'):
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        preview = f.read(200) # Read first 200 chars
                        content_preview += f"\n内容预览:\n{preview}..."
                except Exception as e:
                    print(f"Could not read txt file: {e}")
            self.add_message_to_display(content_preview + "\n", "system_tag")
            # Future: Process content_preview or filepath before sending next message

    def select_image(self):
        filepath = filedialog.askopenfilename(title="选择图片 (上传图片)", filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif"), ("All files", "*.*")] )
        if filepath:
            filename = os.path.basename(filepath)
            print(f"Selected image: {filepath}")
            self.add_message_to_display(f"[图片已选择: {filename}]\n", "system_tag")
            # Future: Integrate with multi-modal model (e.g., glm-4v)

    def select_audio(self):
        filepath = filedialog.askopenfilename(title="选择音频 (上传音频)", filetypes=[("Audio files", "*.wav *.mp3 *.ogg"), ("All files", "*.*")] )
        if filepath:
            filename = os.path.basename(filepath)
            print(f"Selected audio: {filepath}")
            self.add_message_to_display(f"[音频已选择: {filename}]\n", "system_tag")
            # Future: Integrate with speech-to-text

    # --- Other Methods --- # Adjusted for internal/display mode keys

    def add_message_to_display(self, message, tag):
        # ... (same)
        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", message, tag)
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")

    def update_mode_display(self):
        self.mode_var.set(self.get_display_mode(self.current_mode))

    def change_mode_manual(self, selected_display_mode):
        new_internal_mode = self.get_internal_mode_key(selected_display_mode)
        if new_internal_mode != self.current_mode:
            self.current_mode = new_internal_mode
            self.add_message_to_display(f"\n模式已切换到 {self.get_display_mode(self.current_mode)} 。(手动)\n", "system_tag")
            # Keep history on manual change

    def detect_and_switch_mode(self, text_lower):
        # Use internal key "general" for check
        if self.current_mode == "general":
            detected_mode_key = None
            if any(keyword in text_lower for keyword in DEVOP_KEYWORDS):
                detected_mode_key = "devops"
            elif any(keyword in text_lower for keyword in BLOG_KEYWORDS):
                detected_mode_key = "blog"

            if detected_mode_key:
                self.current_mode = detected_mode_key
                display_mode = self.get_display_mode(self.current_mode)
                self.add_message_to_display(f"\n模式已切换到 {display_mode} 。(自动)\n", "system_tag")
                self.update_mode_display() # Update dropdown

    def send_message_event(self, event=None):
        if self.is_generating: return
        user_input_raw = self.input_entry.get().strip()
        if not user_input_raw: return

        # --- Check for predefined questions --- Added Check
        user_input_normalized = normalize_question(user_input_raw)
        predefined_answer = None
        for question, answer in PREDEFINED_QA.items():
            if normalize_question(question) == user_input_normalized:
                predefined_answer = answer
                break
        
        if predefined_answer:
            print(f"--- Predefined answer triggered for: {user_input_raw} ---")
            # Display user message
            self.add_message_to_display(f"你: {user_input_raw}\n", "user_tag")
            # Add to history
            self.messages.append({"role": "user", "content": user_input_raw})

            # Display predefined answer
            self.add_message_to_display(f"小G: {predefined_answer}\n", "assistant_tag")
            # Add to history
            self.messages.append({"role": "assistant", "content": predefined_answer})

            # Clear input immediately (safe as no API call follows)
            self.input_entry.delete(0, "end") 
            self.input_entry.focus_set()
            return # Skip API call and rest of the function

        # --- If not predefined, proceed with API call --- (Original logic follows)
        self.is_generating = True
        self.send_button.configure(state="disabled", text="生成中...")
        self.input_entry.configure(state="disabled") # Disable here for API call path
        self.attach_button.configure(state="disabled")
        self.image_button.configure(state="disabled")
        self.mic_button.configure(state="disabled")

        # Add user message to display and history *only* if sending to API
        self.add_message_to_display(f"你: {user_input_raw}\n", "user_tag") 
        self.messages.append({"role": "user", "content": user_input_raw}) 

        # Schedule clearing and focus for the next idle cycle (for API path)
        self.after(0, self.clear_and_refocus_input)

        self.detect_and_switch_mode(user_input_raw.lower())

        api_thread = threading.Thread(target=self.call_api_stream, args=(user_input_raw,), daemon=True)
        api_thread.start()

    def call_api_stream(self, user_input):
        # Use the correct fallback key "通用 / general"
        system_prompt = SYSTEM_PROMPTS.get(self.current_mode, SYSTEM_PROMPTS["通用 / general"]) # Fixed fallback
        try:
            api_messages = [{"role": "system", "content": system_prompt}]
            history_for_context = self.messages[-(MAX_HISTORY_TURNS*2):]
            if history_for_context and history_for_context[-1]["role"] == "user":
                 api_messages.extend(history_for_context[:-1])
            else:
                 api_messages.extend(history_for_context)
            api_messages.append({"role": "user", "content": user_input})
            response = client.chat.completions.create(model="glm-4", messages=api_messages, temperature=0.7, stream=True,)
            full_agent_response = ""
            self.response_queue.put(("start_assistant", None))
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    piece = chunk.choices[0].delta.content
                    self.response_queue.put(("piece", piece))
                    full_agent_response += piece
            self.response_queue.put(("end_assistant", full_agent_response))
        except Exception as e:
            self.response_queue.put(("error", f"API 调用出错: {e}"))
        finally:
             self.response_queue.put(("generation_finished", None))

    def clear_and_refocus_input(self):
        """Helper function to clear input and set focus, called via self.after()."""
        self.input_entry.delete(0, "end")
        self.input_entry.focus_set()
        print("--- Input box cleared and refocused (via self.after) ---") # New debug print

    def process_response_queue(self):
        # ... (same as before, handles generation_finished to re-enable buttons)
        try:
            while True:
                message_type, data = self.response_queue.get_nowait()
                if message_type == "start_assistant":
                     self.chat_display.configure(state="normal"); self.chat_display.insert("end", "小G: ", "assistant_tag"); self.chat_display.configure(state="disabled")
                elif message_type == "piece":
                     self.chat_display.configure(state="normal"); self.chat_display.insert("end", data, "assistant_tag"); self.chat_display.see("end"); self.chat_display.configure(state="disabled")
                elif message_type == "end_assistant":
                     self.chat_display.configure(state="normal"); self.chat_display.insert("end", "\n"); self.chat_display.see("end"); self.chat_display.configure(state="disabled")
                     if data: self.messages.append({"role": "assistant", "content": data})
                elif message_type == "error":
                     self.add_message_to_display(f"错误: {data}\n", "system_tag")
                elif message_type == "generation_finished":
                     self.is_generating = False
                     self.send_button.configure(state="normal", text="发送 / Отправить")
                     self.input_entry.configure(state="normal")
                     self.attach_button.configure(state="normal")
                     self.image_button.configure(state="normal")
                     self.mic_button.configure(state="normal")
        except queue.Empty: pass
        finally: self.after(100, self.process_response_queue)

    def open_history_window(self):
        # ... (same)
        if self.history_window is None or not self.history_window.winfo_exists(): self.history_window = HistoryWindow(self)
        else: self.history_window.focus()

    def save_current_session(self):
        # ... (same)
        if not self.messages: return
        now = datetime.datetime.now()
        filename = f"session_{now.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = pathlib.Path(HISTORY_DIR) / filename
        try:
            with open(filepath, 'w', encoding='utf-8') as f: json.dump(self.messages, f, ensure_ascii=False, indent=2)
        except IOError as e: print(f"保存当前会话失败: {e}")

    def on_closing(self):
        # ... (same)
        self.save_current_session()
        self.destroy()

    def clear_input(self, event=None): # Bound to Ctrl+Backspace
        """Clears the input entry box."""
        # Check if Ctrl is pressed along with Backspace
        if event and event.state & 0x0004 and event.keysym == 'BackSpace':
          print("--- Clearing input box (Ctrl+Backspace detected) --- ") # Debug print
          self.input_entry.delete(0, "end")
          # self.input_entry.update() # Force update entry widget - REMOVED
          # print(f"--- Input box content after delete: '{self.input_entry.get()}' ---") # REMOVED
          self.input_entry.focus_set() # Explicitly set focus back
          # print(f"--- Input box content after delete (before next idle): '{self.input_entry.get()}' ---") # Check state right after delete
          # self.update_idletasks() # Try forcing update - REMOVED
          return "break" # Prevent default Backspace behavior after clearing
        return None # Allow normal Backspace otherwise

# --- Main Execution ---
if __name__ == "__main__":
    app = App()
    app.mainloop() 