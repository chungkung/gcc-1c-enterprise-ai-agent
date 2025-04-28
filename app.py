import os
import json
from flask import Flask, request, jsonify, render_template, send_from_directory
from zhipuai import ZhipuAI
import werkzeug
import pathlib
import PyPDF2
import datetime
import glob
import shutil
import random
import requests
import time
from transformers import pipeline, RobertaTokenizer, RobertaForMaskedLM
from inference import OneCAgent

# --- Configuration ---
UPLOAD_FOLDER = 'uploads'
HISTORY_DIR = "chat_history"
MAX_HISTORY_TURNS = 5
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'mp3', 'wav', 'm4a'}

CLEAN_DIR = "data/clean_bsl"
SPLIT_DIR = "data/split"
os.makedirs(SPLIT_DIR, exist_ok=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

pathlib.Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)
pathlib.Path(HISTORY_DIR).mkdir(parents=True, exist_ok=True)

agent = OneCAgent("model/codebert-1c-finetuned")

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

try:
    api_key = os.environ["ZHIPUAI_API_KEY"]
    client = ZhipuAI(api_key=api_key)
except KeyError:
    print("错误：ZHIPUAI_API_KEY 环境变量未设置。")
    client = None

# --- Predefined Q&A --- (Copied from main.py)
PREDEFINED_QA = {
    "gcc是什么": """GCC项目，是本公司-(中国化学工程第七建设有限公司)承建的俄罗斯波罗的海化工综合体GCC项目，该项目总投资120亿欧元，预计工期5年，工签一年一签，可续签，预计在2026年完工。""",
    "cc7是什么": """是本公司的英文，我们的中文叫中国化学工程第七建设有限公司，简称"七化建"(CC7)，是隶属于国务院国有资产监督管理委员会管理的中国化学工程集团有限公司。在上市与定位上，本公司于2010年随集团在上交所上市，总部位于成渝双城经济圈的龙泉驿区，是中央在四川的重要骨干企业。自1964年成立以来，本公司一直致力于在国际舞台上展现其作为工程承包商的卓越能力。此外，本公司近年来在国际市场上取得了显著的成绩。本公司在2020年ENR全球最大250家工程承包商排名中列第22位，同时在美国《化学周刊》公布的全球油气相关行业工程建设公司排名中居全球第2位。此外，公司荣获2021年度对外承包工程企业100强第15名和欧洲地区30强第2名的殊荣，这些成绩彰显了公司在行业中的领先地位。""",
    "北海分公司的职责是什么": """七化建北海分公司的业务领域广泛，比如GCC就是北海分公司负责的噢。另外还主要包括石油化工、房屋建筑、水利水电、市政公用、道路桥梁等EPC总承包、技术开发、实业投资和贸易等领域。自2010年进入相关国别以来，北海分公司相继签约了10余个大型、超大型项目，形成了化肥、炼化、炼油、天然气处理和基础设施五大板块的合理布局，致力于打造世界一流的工程承包商‌。""",
    "罗文豪爱梁仁璐吗": """爱不释手，love renlu forever ! ! !""",

    # --- 更新和新增的问答对 ---
    "你是谁制作的": """我是由七化建罗文豪开发制作的，我是一个专门服务GCC项目的人工智能助手，旨在帮助各位同事解答问题和提供信息。""",
    "你是谁": """我是由七化建罗文豪开发制作的，我是一个专门服务GCC项目的人工智能助手，旨在帮助各位同事解答问题和提供信息。""", # Add a similar key
    "罗文豪是谁": """罗文豪是一名优秀的算法工程师，是它在10个小时之内开发了我，他是名牌大学毕业的硕士研究生，手上拥有3个发明专利和6个软件著作。SCI也收录了他的三篇论文噢！！！""",
    "罗文豪": """罗文豪是一名优秀的算法工程师，是它在10个小时之内开发了我，他是名牌大学毕业的硕士研究生，手上拥有3个发明专利和6个软件著作。SCI也收录了他的三篇论文噢！！！""",
    # --- 中国化学相关问答 ... ---
    "中国化学是什么样的企业": """中国化学即中国化学工程股份有限公司，是国务院国资委监管的超大型中央企业，由中国化学工程集团公司联合神华集团有限责任公司、中国中化集团公司于 2008 年 9 月发起设立 ，2010 年 1 月在上海证券交易所上市。它集研发、投资、建造、运营于一体，是我国工业工程领域资质最为齐全、功能最为完备、业务链最为完整、知识技术密集的工程公司 。业务涵盖建筑工程、化工、石油、医药等工业工程承包，工程咨询、勘察、设计、施工及项目管理服务，环境治理，技术研发及成果推广，进出口等。它是我国石油和化学工业体系的奠基人，为解决 "穿衣吃饭" 问题而生，也是工程行业体制机制改革先行者、"一带一路" 共建排头兵、清洁能源工程领军者、建设美丽中国实践者 。其中七化建是当之无愧的NO.1。且目前正加快打造工业工程领域综合解决方案服务商、高端化学品和先进材料供应商，朝着世界一流企业迈进 。""",
    "中国化学工程是什么样的企业": """中国化学即中国化学工程股份有限公司，是国务院国资委监管的超大型中央企业，由中国化学工程集团公司联合神华集团有限责任公司、中国中化集团公司于 2008 年 9 月发起设立 ，2010 年 1 月在上海证券交易所上市。它集研发、投资、建造、运营于一体，是我国工业工程领域资质最为齐全、功能最为完备、业务链最为完整、知识技术密集的工程公司 。业务涵盖建筑工程、化工、石油、医药等工业工程承包，工程咨询、勘察、设计、施工及项目管理服务，环境治理，技术研发及成果推广，进出口等。它是我国石油和化学工业体系的奠基人，为解决 "穿衣吃饭" 问题而生，也是工程行业体制机制改革先行者、"一带一路" 共建排头兵、清洁能源工程领军者、建设美丽中国实践者 。其中七化建是当之无愧的NO.1。且目前正加快打造工业工程领域综合解决方案服务商、高端化学品和先进材料供应商，朝着世界一流企业迈进 。""",
    "中国化学工程公司是什么样的企业": """中国化学即中国化学工程股份有限公司，是国务院国资委监管的超大型中央企业，由中国化学工程集团公司联合神华集团有限责任公司、中国中化集团公司于 2008 年 9 月发起设立 ，2010 年 1 月在上海证券交易所上市。它集研发、投资、建造、运营于一体，是我国工业工程领域资质最为齐全、功能最为完备、业务链最为完整、知识技术密集的工程公司 。业务涵盖建筑工程、化工、石油、医药等工业工程承包，工程咨询、勘察、设计、施工及项目管理服务，环境治理，技术研发及成果推广，进出口等。它是我国石油和化学工业体系的奠基人，为解决 "穿衣吃饭" 问题而生，也是工程行业体制机制改革先行者、"一带一路" 共建排头兵、清洁能源工程领军者、建设美丽中国实践者 。其中七化建是当之无愧的NO.1。且目前正加快打造工业工程领域综合解决方案服务商、高端化学品和先进材料供应商，朝着世界一流企业迈进 。""",
    "it管理部的职责": """IT 管理部负责GCC的IT设施的统筹规划、建设、维护及优化企业信息技术系统，保障业务高效稳定开展。需依据企业战略拟定信息化规划，涵盖硬件、软件、网络等基础设施的选型、部署与升级；管理 IT 预算和成本，合理分配资源并评估投资效益；建立并执行安全策略，防控网络攻击、数据泄露等风险，确保合规；持续监控系统性能，及时处理故障以保障可用性和稳定性；为GCC员工提供技术支持，解答疑问并处理设备、系统问题；推进新技术引入与应用，组织技术研究、测试和落地；负责项目全流程管理，确保按时按质交付；对 IT 资产进行登记、盘点、维护和报废处理；开展团队建设与人员培训，提升成员专业能力和团队协作水平。""",
    "it管理部的工作分配": """IT 管理部负责GCC的IT设施的统筹规划、建设、维护及优化企业信息技术系统，保障业务高效稳定开展。需依据企业战略拟定信息化规划，涵盖硬件、软件、网络等基础设施的选型、部署与升级；管理 IT 预算和成本，合理分配资源并评估投资效益；建立并执行安全策略，防控网络攻击、数据泄露等风险，确保合规；持续监控系统性能，及时处理故障以保障可用性和稳定性；为GCC员工提供技术支持，解答疑问并处理设备、系统问题；推进新技术引入与应用，组织技术研究、测试和落地；负责项目全流程管理，确保按时按质交付；对 IT 资产进行登记、盘点、维护和报废处理；开展团队建设与人员培训，提升成员专业能力和团队协作水平。""",
    "it管理部的领导是谁": """李俊威，它是目前GCCIT管理部老大噢！！！""",
    "开网盘找谁": """IT管理部的罗文豪噢！""",
    "开网盘权限找谁": """IT管理部的罗文豪噢！""",
    "开office找谁": """叶延廷老师。""",
    "开excel找谁": """叶延廷老师。""",
    "开word找谁": """叶延廷老师。""",
    "开teams找谁": """叶延廷老师。""",
    "网络设施相关问题找谁": """IT管理部的周志鹏老师噢！！""",
    "it管理部成员都有谁": """李俊威，肖翔，罗文豪，周志鹏，叶延廷，高登洋， 陈良， 曹一凡，毛耀华， 宋美衡 ，李兴侠， 韩云峰。""",
    "it部成员都有谁": """李俊威，肖翔，罗文豪，周志鹏，叶延廷，高登洋， 陈良， 曹一凡，毛耀华， 宋美衡 ，李兴侠， 韩云峰。""",
}

def normalize_question(text):
    """Helper to normalize question for matching."""
    return text.lower().replace("？", "").replace("?", "").strip()

# --- Helper Function to Generate Session ID ---
def generate_session_id():
    now = datetime.datetime.now()
    return f"session_{now.strftime('%Y%m%d_%H%M%S')}.json"

# --- Helper Function to Read/Write History ---
def read_history(session_id):
    filepath = os.path.join(HISTORY_DIR, session_id)
    if not os.path.exists(filepath):
        return [] # Return empty list if file not found
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            history = json.load(f)
            # Basic validation: ensure it's a list
            return history if isinstance(history, list) else []
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error reading history file {session_id}: {e}")
        return [] # Return empty on error

def write_history(session_id, history):
    filepath = os.path.join(HISTORY_DIR, session_id)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2) # Use indent for readability
    except IOError as e:
        print(f"Error writing history file {session_id}: {e}")

# --- Flask App Initialization ---
app = Flask(__name__) # Flask will look for templates in a 'templates' folder
                      # and static files in a 'static' folder by default.

# --- Routes ---

@app.route('/static/manifest.json')
def serve_manifest():
    return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')

@app.route('/static/service-worker.js')
def serve_sw():
    return send_from_directory('static', 'service-worker.js', mimetype='application/javascript')

@app.route('/')
def index():
    """Serves the main HTML page."""
    initial_message = (
        "你好👋！我是GCC的人工智能助手小G，可以叫我小G，很高兴见到你，欢迎问我任何问题。\n"
        "@版权所有: 中国化学工程第七建设有限公司北海分公司IT管理部(罗文豪)\n"
        "@Авторские права: Отдел ИТ филиала Бэйхай Китайской национальной химико-инженерной седьмой строительной компании (Ло Вэньхао)"
    )
    print(f"--- [Index] Rendering index.html with initial_message: '{initial_message[:50]}...' ---") # Log snippet
    return render_template('index.html', initial_message=initial_message)

@app.route('/chat', methods=['POST'])
def chat():
    # --- 1. 基础检查 ---
    if not client:
        print("Error: ZhipuAI client not initialized!")
        return jsonify({"error": "AI 服务未初始化 / AI service not initialized."}), 500

    try:
        # --- 2. 获取请求数据 ---
        data = request.get_json()
        if not data:
            return jsonify({"error": "无效的请求数据 / Invalid request data"}), 400

        user_message = data.get('message', '').strip()
        uploaded_filename = data.get('uploaded_file')
        session_id = data.get('session_id')

        # --- 3. 初始化变量 (关键修复!) ---
        file_content = None
        processing_error = None # 确保在这里初始化!
        new_session_id = None

        if not user_message:
            return jsonify({"response": "请输入消息。 / Please enter a message."}) # 早点返回空消息

        # --- 4. 文件处理 (如果提供了文件名) ---
        if uploaded_filename:
            print(f"--- [Chat] Received request with file context: {uploaded_filename} ---")
            safe_filename = werkzeug.utils.secure_filename(uploaded_filename)
            filepath = os.path.join(UPLOAD_FOLDER, safe_filename) # 使用全局 UPLOAD_FOLDER

            if not os.path.exists(filepath):
                processing_error = f"错误：找不到引用的文件 / Error: Referenced file not found ({safe_filename})"
                print(f"--- [Chat] Error: File not found at {filepath} ---")
            else:
                try:
                    file_extension = safe_filename.rsplit('.', 1)[1].lower()
                    print(f"--- [Chat] Processing file type: {file_extension} ---")

                    if file_extension == 'txt':
                        with open(filepath, 'r', encoding='utf-8') as f:
                            file_content = f.read()
                    elif file_extension == 'pdf':
                        text = ""
                        try:
                            with open(filepath, 'rb') as f:
                                reader = PyPDF2.PdfReader(f)
                                if reader.is_encrypted:
                                     processing_error = "错误：PDF 文件已加密 / Error: PDF file is encrypted"
                                else:
                                     for page in reader.pages:
                                         page_text = page.extract_text()
                                         if page_text: # Check if text extraction returned something
                                              text += page_text + "\n"
                            if not text and not processing_error: # Handle cases where PDF has no extractable text
                                 processing_error = "错误：无法从 PDF 提取文本 / Error: Could not extract text from PDF"
                            else:
                                 file_content = text
                        except Exception as pdf_error:
                             print(f"--- [Chat] Error reading PDF {safe_filename}: {pdf_error} ---")
                             processing_error = f"读取 PDF 时出错 / Error reading PDF: {pdf_error}"
                    elif file_extension in {'png', 'jpg', 'jpeg', 'gif'}:
                         processing_error = "图片处理功能尚未实现 / Image processing not yet implemented."
                    elif file_extension in {'mp3', 'wav', 'm4a'}:
                         processing_error = "音频处理功能尚未实现 / Audio processing not yet implemented."
                    else:
                        processing_error = f"不支持的文件类型 / Unsupported file type: {file_extension}"

                    # Optional: Limit content size
                    if file_content and len(file_content) > 15000: # Increased limit slightly
                        file_content = file_content[:15000] + "\n... [内容已截断 / Content truncated]"
                        print(f"--- [Chat] File content truncated for {safe_filename} ---")

                except Exception as e:
                    print(f"--- [Chat] Error processing file {safe_filename}: {e} ---")
                    import traceback
                    traceback.print_exc()
                    processing_error = f"处理文件时内部出错 / Internal error processing file: {e}"

        # --- 添加这行诊断日志 ---
        print(f"--- [Chat] Value of processing_error before check: {repr(processing_error)} ---")
        # --- 诊断日志结束 ---

        # --- 5. 处理文件处理错误 ---
        if processing_error:
            print(f"--- [Chat] Returning file processing error: {processing_error} ---")
            # 即便文件处理出错，也需要保存历史记录（标记错误）并返回 session_id
            current_history = []
            response_session_id = session_id
            if session_id:
                 current_history = read_history(session_id)
            else:
                 response_session_id = generate_session_id()
                 print(f"--- [Chat] Starting new session due to file processing error: {response_session_id} ---")

            current_history.append({"role": "user", "content": user_message}) # Save user msg
            current_history.append({"role": "assistant", "content": processing_error}) # Save error as response
            if response_session_id: # Only write if we have a valid session ID
                 write_history(response_session_id, current_history)

            return jsonify({"response": processing_error, "session_id": response_session_id})


        # --- 6. 加载或初始化聊天历史 ---
        history = []
        if session_id:
            if ".." in session_id or "/" in session_id or "\\" in session_id:
                 return jsonify({"error": "Invalid session ID"}), 400
            history = read_history(session_id)
            print(f"--- [Chat] Loaded history for session: {session_id}, length: {len(history)} ---")
        else:
            session_id = generate_session_id()
            new_session_id = session_id # Flag new session
            print(f"--- [Chat] Starting new session: {session_id} ---")

        # --- 7. 检查预定义问答 (仅当无文件内容时) ---
        if not file_content:
             user_message_normalized = normalize_question(user_message)
             predefined_answer = PREDEFINED_QA.get(user_message_normalized) # Simpler lookup
             if predefined_answer:
                 print(f"--- [Chat] Predefined answer triggered for: {user_message} ---")
                 history.append({"role": "user", "content": user_message})
                 history.append({"role": "assistant", "content": predefined_answer})
                 write_history(session_id, history)
                 return jsonify({"response": predefined_answer, "session_id": session_id})

        # --- 8. 准备最终提示和历史 ---
        final_prompt = user_message
        if file_content:
            final_prompt = f"根据以下文件内容:\n---\n{file_content}\n---\n\n请回答用户的问题: {user_message}"
            # Consider adding a system message about the file instead of modifying user prompt?
            # history.append({"role": "system", "content": f"[File Content Provided: {uploaded_filename}]"})

        # Append current user message to history *before* limiting for API
        history.append({"role": "user", "content": user_message}) # Store original user message

        # Limit history turns for API call
        api_messages = history[-(MAX_HISTORY_TURNS * 2):]
        print(f"--- [Chat] Sending request to AI. Session: {session_id}. History Turns for API: {len(api_messages)//2}. Prompt starts with: {final_prompt[:100]}... ---")

        # --- 9. 调用 AI API ---
        try:
            response = client.chat.completions.create(
                model="glm-4", # Use glm-4v later for images
                messages=api_messages,
                temperature=0.7,
            )
            assistant_response = response.choices[0].message.content
            print(f"--- [Chat] API response received. Session: {session_id} ---")

            # --- 10. 保存并返回结果 ---
            history.append({"role": "assistant", "content": assistant_response})
            write_history(session_id, history)

            return jsonify({"response": assistant_response, "session_id": session_id})

        except Exception as api_error:
            print(f"--- [Chat] API Call Error! Session: {session_id}. Error: {api_error} ---")
            # Don't save history if API call fails? Or save user message only?
            # For now, just return error without saving API failure to history.
            return jsonify({"error": f"AI API 调用出错 / AI API Call Error: {api_error}"}), 500

    except Exception as e:
        # --- 11. 通用错误处理 ---
        print(f"--- [Chat] UNEXPECTED ERROR in /chat route: {e} ---")
        import traceback
        traceback.print_exc() # Print full traceback for any unexpected error
        return jsonify({"error": "服务器内部错误 / Internal Server Error"}), 500

# --- New File Upload Route ---
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "请求中未找到文件部分 / No file part in the request"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "未选择文件 / No selected file"}), 400

    if file and allowed_file(file.filename):
        try:
            filename = werkzeug.utils.secure_filename(file.filename)

            filepath = os.path.join(UPLOAD_FOLDER, filename) # Use global variable directly

            file.save(filepath)
            print(f"--- File saved: {filepath} ---")
            return jsonify({
                "success": True,
                "message": "文件上传成功 / File uploaded successfully",
                "filename": filename,
             }), 200
        except Exception as e:
             # Keep the detailed error printing for now
             print(f"Error saving file: Type={type(e)}, Message={e}")
             import traceback
             traceback.print_exc()

             # Return a generic error type for now if using global variable works
             error_type_name = type(e).__name__
             return jsonify({"error": f"保存文件时出错 ({error_type_name}) / Error saving file ({error_type_name})"}), 500
    else:
        return jsonify({"error": "文件类型不允许 / File type not allowed"}), 400

# --- NEW History API Routes ---

@app.route('/history', methods=['GET'])
def get_history_list():
    """Returns a list of available session IDs, sorted by modification time."""
    try:
        history_files = glob.glob(os.path.join(HISTORY_DIR, "session_*.json"))
        # Sort by modification time, newest first
        sessions = sorted(history_files, key=os.path.getmtime, reverse=True)
        # Extract just the filename (session ID)
        session_ids = [os.path.basename(f) for f in sessions]
        return jsonify(session_ids)
    except Exception as e:
        print(f"Error listing history files: {e}")
        return jsonify({"error": "无法获取历史记录列表 / Could not retrieve history list"}), 500

@app.route('/history/<session_id>', methods=['GET'])
def get_session_history(session_id):
    """Returns the message list for a specific session."""
    # Basic validation
    if ".." in session_id or "/" in session_id or "\\" in session_id or not session_id.startswith("session_") or not session_id.endswith(".json"):
        return jsonify({"error": "无效的会话 ID / Invalid session ID"}), 400

    history = read_history(session_id)
    if not history and not os.path.exists(os.path.join(HISTORY_DIR, session_id)):
         return jsonify({"error": "未找到会话 / Session not found"}), 404
    return jsonify(history)

@app.route('/history/<session_id>', methods=['DELETE'])
def delete_session_history(session_id):
    """Deletes a specific session file."""
     # Basic validation
    if ".." in session_id or "/" in session_id or "\\" in session_id or not session_id.startswith("session_") or not session_id.endswith(".json"):
        return jsonify({"error": "无效的会话 ID / Invalid session ID"}), 400

    filepath = os.path.join(HISTORY_DIR, session_id)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            # shutil.move(filepath, os.path.join(HISTORY_DIR, ".trash", session_id)) # Alternative: move to trash
            print(f"--- Deleted history file: {session_id} ---")
            return jsonify({"success": True, "message": "会话已删除 / Session deleted"})
        except OSError as e:
            print(f"Error deleting history file {session_id}: {e}")
            return jsonify({"error": f"删除会话时出错 / Error deleting session: {e}"}), 500
    else:
        return jsonify({"error": "未找到会话 / Session not found"}), 404

@app.route("/api/complete", methods=["POST"])
def complete():
    data = request.json
    prompt = data.get("prompt", "")
    results = agent.code_completion(prompt)
    return jsonify({"completions": results})

@app.route("/api/syntax", methods=["POST"])
def syntax():
    data = request.json
    code = data.get("code", "")
    errors = agent.check_syntax(code)
    return jsonify({"errors": errors})

@app.route("/api/ask", methods=["POST"])
def ask():
    data = request.json
    question = data.get("question", "")
    context = data.get("context", None)
    answer = agent.answer_question(question, context)
    return jsonify({"answer": answer})

# --- Run the App ---
if __name__ == '__main__':
    # Runs the development server. 
    # For deployment, use a production WSGI server like Gunicorn or Waitress.
    # Use host='0.0.0.0' to make it accessible on your network
    app.run(host='0.0.0.0', port=5000, debug=True) # debug=True is helpful for development, disable for production 