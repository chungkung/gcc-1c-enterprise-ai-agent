// --- DOM Elements ---
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');
const fileUploadButton = document.getElementById('file-upload-button');
const imageUploadButton = document.getElementById('image-upload-button');
const audioUploadButton = document.getElementById('audio-upload-button');
const fileInputGeneric = document.getElementById('file-input-generic');
const fileInputImage = document.getElementById('file-input-image');
const fileInputAudio = document.getElementById('file-input-audio');
const historyList = document.getElementById('history-list');
const newChatButton = document.getElementById('new-chat-button');
const collapseSidebarButton = document.getElementById('collapse-sidebar-button');
const appLayout = document.querySelector('.app-layout');

// --- State Variables ---
let currentSessionId = null; // Track the active session
let lastUploadedFilename = null;
let fileContextIndicator = null; // To show which file is active
let isLoadingHistory = false; // Prevent spamming load requests

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Function to update UI indicating a file is ready for query
function showFileContextIndicator(filename) {
    // Remove previous indicator if exists
    if (fileContextIndicator) {
        fileContextIndicator.remove();
    }
    const indicator = document.createElement('div');
    indicator.className = 'file-context-indicator';
    indicator.innerHTML = `
        <span>讨论文件 / Обсуждаемый файл: ${filename}</span>
        <button title="清除文件上下文 / Очистить контекст файла">&times;</button>
    `;
    indicator.querySelector('button').addEventListener('click', () => {
        lastUploadedFilename = null;
        indicator.remove();
        fileContextIndicator = null;
        userInput.placeholder = "请输入您的问题... / Введите ваш вопрос..."; // Reset placeholder
    });

    // Insert indicator before the textarea
    userInput.parentNode.insertBefore(indicator, userInput);
    fileContextIndicator = indicator;
    userInput.placeholder = "针对文件提问... / Задать вопрос по файлу..."; // Change placeholder
}

function addMessage(content, isUser = false, messageType = 'text') {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user-message' : 'assistant-message'}`;

    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';

    // 判断是否为代码内容（简单检测，后续可用更智能的判断）
    if (messageType === 'fileInfo') {
        messageContent.innerHTML = `<i>已选择文件 / Selected file: ${content}</i>`;
    } else if (/```[\s\S]*?```/.test(content)) {
        // 多行代码块 markdown
        const code = content.match(/```[\s\S]*?```/g).map(block => {
            const codeText = block.replace(/```/g, '').trim();
            return `<pre class='code-block'><button class='copy-btn' title='复制代码'>复制</button>${codeText}</pre>`;
        }).join('');
        messageContent.innerHTML = content.replace(/```[\s\S]*?```/g, code);
    } else if (/^\s*Процедура|КонецПроцедуры|Функция|КонецФункции|If|For|While|Return|Var|Let|const|function|def|class/m.test(content)) {
        // 以常见代码关键字开头的内容，自动用代码框
        messageContent.innerHTML = `<pre class='code-block'><button class='copy-btn' title='复制代码'>复制</button>${content}</pre>`;
    } else if (/<pre.*?>[\s\S]*?<\/pre>/.test(content)) {
        // 已经是 pre 标签的内容
        messageContent.innerHTML = content;
    } else {
        // 普通文本
        messageContent.innerHTML = content.replace(/\n/g, '<br>');
    }

    messageDiv.appendChild(messageContent);
    chatMessages.appendChild(messageDiv);
    // 增加动画（已由CSS实现 fadeInUp）
    setTimeout(() => { messageDiv.classList.add('show'); }, 10);
    scrollToBottom();

    // 复制按钮功能
    messageDiv.querySelectorAll('.copy-btn').forEach(btn => {
        btn.onclick = function(e) {
            e.stopPropagation();
            const code = btn.parentElement.innerText.replace(/^复制/, '').trim();
            if (navigator.clipboard) {
                navigator.clipboard.writeText(code);
                btn.textContent = '已复制';
                setTimeout(() => { btn.textContent = '复制'; }, 1200);
            } else {
                // fallback
                const textarea = document.createElement('textarea');
                textarea.value = code;
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
                btn.textContent = '已复制';
                setTimeout(() => { btn.textContent = '复制'; }, 1200);
            }
        };
    });
}

function clearChatDisplay() {
    chatMessages.innerHTML = ''; // Clear messages
    // Clear file context if any
    if (fileContextIndicator) {
        fileContextIndicator.remove();
        fileContextIndicator = null;
    }
    lastUploadedFilename = null;
    userInput.placeholder = "请输入您的问题... / Введите ваш вопрос...";
}

// --- History Functions ---

async function loadHistoryList() {
    try {
        const response = await fetch('/history');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const sessionIds = await response.json();
        historyList.innerHTML = ''; // Clear existing list

        sessionIds.forEach(sessionId => {
            const li = document.createElement('li');
            // Try to parse timestamp from filename for display
            let displayName = sessionId.replace('session_', '').replace('.json', '');
            try {
                 const parts = displayName.split('_');
                 const datePart = parts[0];
                 const timePart = parts[1];
                 displayName = `${datePart.substring(0,4)}-${datePart.substring(4,6)}-${datePart.substring(6,8)} ${timePart.substring(0,2)}:${timePart.substring(2,4)}:${timePart.substring(4,6)}`;
            } catch (e) { /* Ignore parsing error, use raw name */ }

            li.textContent = displayName;
            li.dataset.sessionId = sessionId; // Store ID in data attribute

            // Add delete button
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'delete-session-button';
            deleteBtn.innerHTML = '&times;'; // Multiplication sign X
            deleteBtn.title = '删除此会话 / Удалить этот чат';
            deleteBtn.addEventListener('click', (event) => {
                event.stopPropagation(); // Prevent li click event
                deleteSession(sessionId);
            });
            li.appendChild(deleteBtn);


            li.addEventListener('click', () => {
                if (isLoadingHistory || currentSessionId === sessionId) return; // Prevent reloading same session
                loadSession(sessionId);
            });

            if (sessionId === currentSessionId) {
                li.classList.add('active'); // Highlight active session
            }
            historyList.appendChild(li);
        });
    } catch (error) {
        console.error('Error loading history list:', error);
        // Optionally display error to user in the sidebar
    }
}

async function loadSession(sessionId) {
    if (isLoadingHistory) return;
    isLoadingHistory = true;
    console.log(`Loading session: ${sessionId}`);
    clearChatDisplay(); // Clear current messages first
    // Visually indicate loading maybe?

    try {
        const response = await fetch(`/history/${sessionId}`);
        if (!response.ok) {
             if (response.status === 404) {
                 addMessage(`错误：找不到会话 ${sessionId} / Error: Session ${sessionId} not found`);
             } else {
                 const errorData = await response.json();
                 throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
             }
             currentSessionId = null; // Reset if load fails
             loadHistoryList(); // Refresh list
             return; // Exit function
        }
        const messages = await response.json();
        currentSessionId = sessionId; // Set the current session ID

        // Render loaded messages
        messages.forEach(msg => {
             // Simple check: assume system message is file context for now
             const msgType = msg.role === 'system' ? 'fileInfo' : 'text';
             addMessage(msg.content, msg.role === 'user', msgType);
        });

         // Update active class in sidebar
         document.querySelectorAll('#history-list li').forEach(item => {
             item.classList.toggle('active', item.dataset.sessionId === sessionId);
         });


    } catch (error) {
        console.error(`Error loading session ${sessionId}:`, error);
        addMessage(`加载会话时出错: ${error.message}\nError loading session: ${error.message}`);
        currentSessionId = null; // Reset session ID on error
        loadHistoryList(); // Refresh list
    } finally {
         isLoadingHistory = false;
         userInput.focus(); // Focus input after loading
    }
}

async function deleteSession(sessionId) {
    if (!confirm(`确定要删除此会话吗？\nВы уверены, что хотите удалить этот чат?\n(${sessionId})`)) {
        return;
    }
    console.log(`Deleting session: ${sessionId}`);
    try {
        const response = await fetch(`/history/${sessionId}`, { method: 'DELETE' });
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || `HTTP error! status: ${response.status}`);
        }

        console.log(data.message);
        // If the deleted session was the active one, switch to new chat mode
        if (currentSessionId === sessionId) {
            startNewChat();
        }
        loadHistoryList(); // Refresh the list

    } catch (error) {
        console.error(`Error deleting session ${sessionId}:`, error);
        alert(`删除会话时出错: ${error.message}\nError deleting session: ${error.message}`);
    }
}

function startNewChat() {
    console.log("--- startNewChat called ---");
    console.log("Document readyState:", document.readyState);

    // --- NEW: Refresh history list if switching from an existing chat ---
    if (currentSessionId) {
        console.log(`Switching from session ${currentSessionId}, refreshing list.`);
        loadHistoryList(); // Refresh list to show the session we just left
    }
    // --- END NEW ---

    currentSessionId = null;
    clearChatDisplay(); // Clear current chat content

    // The variable initialAssistantMessage should now be globally available 
    // from the inline script in index.html
    console.log("Value of initialAssistantMessage (from inline script):", 
        (typeof initialAssistantMessage !== 'undefined') ? initialAssistantMessage : 'Variable not found!');

    if (typeof initialAssistantMessage !== 'undefined' && initialAssistantMessage) { 
        console.log("Attempting to add initial message...");
        try {
            // Add initial message again for new chat
            addMessage(initialAssistantMessage);
            console.log("Initial message added successfully.");
        } catch (error) {
             console.error("Error adding initial message:", error);
             // Display error in chat maybe?
             addMessage("Error displaying initial message.", false);
        }
    } else {
         console.warn("initialAssistantMessage is undefined or empty. Skipping initial message.");
         // Optionally add a default greeting if the initial message fails to load
         // addMessage("你好！有什么可以帮您的吗？");
    }
    // --- End Debugging ---

    // Update active class in sidebar (remove from all)
    try {
        document.querySelectorAll('#history-list li').forEach(item => {
            item.classList.remove('active');
        });
        console.log("Sidebar active class cleared.");
    } catch(error) {
         console.error("Error clearing sidebar active class:", error);
    }

    try {
        userInput.focus();
        console.log("User input focused.");
    } catch (error) {
         console.error("Error focusing user input:", error);
    }
    console.log("--- startNewChat finished ---");
}

// --- Core Chat Functions (Modified) ---

async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    userInput.disabled = true;
    sendButton.disabled = true;
    // Disable upload buttons too? Maybe not, allow upload then send.
    sendButton.textContent = '发送中...';

    addMessage(message, true); // Add user text message

    const payload = {
        message: message,
        session_id: currentSessionId // <-- Include current session ID
    };
    if (lastUploadedFilename) {
        payload.uploaded_file = lastUploadedFilename;
        console.log(`Sending message with file context: ${lastUploadedFilename}`);
    }

    // --- Clear input and context AFTER preparing payload ---
    userInput.value = '';
    userInput.style.height = 'auto';
    userInput.style.height = (userInput.scrollHeight) + 'px';
    if (fileContextIndicator) {
        fileContextIndicator.remove();
        fileContextIndicator = null;
    }
    lastUploadedFilename = null;
    userInput.placeholder = "请输入您的问题... / Введите ваш вопрос...";


    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
             let errorMsg = `HTTP error! status: ${response.status}`;
             try { const errorData = await response.json(); errorMsg = `错误: ${errorData.error || response.statusText}`; } catch (e) { /* Ignore */ }
             throw new Error(errorMsg);
        }

        const data = await response.json();

        if (data.error) {
            addMessage('错误: ' + data.error);
        } else if (data.response) {
            addMessage(data.response); // Add assistant response

            // --- Handle Session ID Update ---
            if (data.session_id && currentSessionId !== data.session_id) {
                // This means a new session was created OR backend confirmed the ID
                console.log(`Session ID confirmed/updated: ${data.session_id}`);
                currentSessionId = data.session_id;
                // Refresh history list to show the new session and mark it active
                loadHistoryList();
            } else if (currentSessionId) {
                 // Update active class in sidebar if needed (though loadList should handle it)
                 document.querySelectorAll('#history-list li').forEach(item => {
                     item.classList.toggle('active', item.dataset.sessionId === currentSessionId);
                 });
            }

        } else {
             addMessage('收到空响应');
        }
    } catch (error) {
         console.error('Fetch Error:', error);
         addMessage(`发送消息时出错: ${error.message}`);
    } finally {
        userInput.disabled = false;
        sendButton.disabled = false;
        sendButton.textContent = '发送';
        userInput.focus();
    }
}

async function uploadFile(file) {
     // ... (keep existing uploadFile logic, it doesn't need session ID) ...
     // Make sure it re-enables sendButton in finally block
      if (!file) return;
     addMessage(file.name, true, 'fileInfo');
     const formData = new FormData();
     formData.append('file', file);
     fileUploadButton.disabled = true;
     imageUploadButton.disabled = true;
     audioUploadButton.disabled = true;
     sendButton.disabled = true; // Disable send during upload
     try {
         const response = await fetch('/upload', { method: 'POST', body: formData });
         const data = await response.json();
         if (!response.ok) throw new Error(data.error || `HTTP error! status: ${response.status}`);
         if (data.success) {
             addMessage(`文件 "${data.filename}" 上传成功。现在可以在下方提问。\nФайл "${data.filename}" успешно загружен. Теперь вы можете задать вопрос ниже.`);
             lastUploadedFilename = data.filename;
             showFileContextIndicator(data.filename);
         } else {
             addMessage(`文件上传失败: ${data.error}\nFile upload failed: ${data.error}`);
         }
     } catch (error) { /* ... error handling ... */
          console.error('Upload Error:', error);
          addMessage(`上传出错: ${error.message}\nUpload error: ${error.message}`);
     } finally { /* ... re-enable buttons ... */
         fileUploadButton.disabled = false;
         imageUploadButton.disabled = false;
         audioUploadButton.disabled = false;
         sendButton.disabled = false; // Re-enable send button
         fileInputGeneric.value = null; fileInputImage.value = null; fileInputAudio.value = null;
     }
}

// --- Event Listeners ---
sendButton.addEventListener('click', sendMessage);
userInput.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
userInput.addEventListener('input', () => { userInput.style.height = 'auto'; userInput.style.height = (userInput.scrollHeight) + 'px'; });
fileUploadButton.addEventListener('click', () => fileInputGeneric.click());
imageUploadButton.addEventListener('click', () => fileInputImage.click());
audioUploadButton.addEventListener('click', () => fileInputAudio.click());
fileInputGeneric.addEventListener('change', (e) => { if (e.target.files.length > 0) uploadFile(e.target.files[0]); });
fileInputImage.addEventListener('change', (e) => { if (e.target.files.length > 0) uploadFile(e.target.files[0]); });
fileInputAudio.addEventListener('change', (e) => { if (e.target.files.length > 0) uploadFile(e.target.files[0]); });
newChatButton.addEventListener('click', startNewChat);
collapseSidebarButton.addEventListener('click', () => {
    console.log("Collapse button clicked!");
    if (appLayout) {
         appLayout.classList.toggle('sidebar-collapsed');
         console.log("Toggled sidebar-collapsed class. Current classes:", appLayout.className);
    } else {
        console.error("appLayout element not found!");
    }
});


// --- Initial Load Logic (Attached to window.onload) ---
window.onload = () => {
    console.log("--- window.onload triggered ---");
    // Check attribute again here, just before calling startNewChat
    const bodyElementForCheck = document.body;
    const rawAttributeCheck = bodyElementForCheck ? bodyElementForCheck.getAttribute('data-initial-message') : 'Body not found!';
    console.log("Raw data-initial-message attribute at window.onload:", rawAttributeCheck);

    startNewChat(); // Start with a clean slate and initial message
    loadHistoryList(); // Load the history list
}; 