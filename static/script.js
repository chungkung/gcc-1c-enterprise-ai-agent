document.addEventListener('DOMContentLoaded', function() {
    const chatMessages = document.getElementById('chat-messages');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function addMessage(content, isUser = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user' : 'assistant'}`;
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        messageContent.textContent = content;
        
        messageDiv.appendChild(messageContent);
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
    }

    async function sendMessage() {
        const message = userInput.value.trim();
        if (!message) return;

        // 禁用输入和发送按钮
        userInput.disabled = true;
        sendButton.disabled = true;

        // 添加用户消息
        addMessage(message, true);
        userInput.value = '';

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message })
            });

            const data = await response.json();
            
            if (data.error) {
                addMessage('错误: ' + data.error);
            } else {
                addMessage(data.response);
            }
        } catch (error) {
            addMessage('发送消息时出错: ' + error.message);
        } finally {
            // 重新启用输入和发送按钮
            userInput.disabled = false;
            sendButton.disabled = false;
            userInput.focus();
        }
    }

    // 发送按钮点击事件
    sendButton.addEventListener('click', sendMessage);

    // 输入框回车事件（Shift+Enter换行）
    userInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // 自动调整输入框高度
    userInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });
}); 