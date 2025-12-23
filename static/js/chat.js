// static/js/chat.js - Chat Room Class

class ChatRoom {
    constructor(config) {
        this.roomId = config.roomId;
        this.roomType = config.roomType;
        this.currentUserId = config.currentUserId;
        this.isGroupChat = config.isGroupChat;
        this.csrfToken = config.csrfToken;
        
        this.socket = null;
        this.typingTimeout = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 3000;
        
        this.typingUsers = new Set();
        this.unreadMessages = new Set();
        
        this.init();
    }

    init() {
        this.connectWebSocket();
        this.bindEvents();
        this.setupMessageHandlers();
        this.setupNotifications();
        this.scrollToBottom();
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/chat/${this.roomId}/`;
        
        console.log(`Connecting to WebSocket: ${wsUrl}`);
        
        try {
            this.socket = new WebSocket(wsUrl);
            
            this.socket.onopen = () => {
                console.log('WebSocket connected successfully');
                this.reconnectAttempts = 0;
                this.updateConnectionStatus(true);
            };
            
            this.socket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleWebSocketMessage(data);
                } catch (error) {
                    console.error('Error parsing WebSocket message:', error);
                }
            };
            
            this.socket.onclose = (event) => {
                console.log(`WebSocket disconnected: ${event.code} - ${event.reason}`);
                this.updateConnectionStatus(false);
                this.handleReconnection();
            };
            
            this.socket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateConnectionStatus(false);
            };
            
        } catch (error) {
            console.error('Error creating WebSocket:', error);
            this.handleReconnection();
        }
    }

    bindEvents() {
        // Message form submission
        const messageForm = document.getElementById('message-form');
        if (messageForm) {
            messageForm.addEventListener('submit', (e) => this.handleMessageSubmit(e));
        }

        // Typing indicator
        const messageInput = document.getElementById('message-input');
        if (messageInput) {
            messageInput.addEventListener('input', () => this.handleTyping());
            messageInput.addEventListener('blur', () => this.stopTyping());
        }

        // Message status updates
        this.setupMessageStatus();
    }

    setupMessageHandlers() {
        // Message deletion
        document.addEventListener('click', (e) => {
            if (e.target.closest('.message-delete-btn')) {
                const messageId = e.target.closest('.message-item').dataset.messageId;
                this.deleteMessage(messageId);
            }
        });

        // Message reactions
        document.addEventListener('click', (e) => {
            if (e.target.closest('.message-reaction-btn')) {
                const messageId = e.target.closest('.message-item').dataset.messageId;
                this.showReactionPicker(messageId);
            }
        });
    }

    setupNotifications() {
        // Request notification permission
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
    }

    setupMessageStatus() {
        // Update message status indicators
        setInterval(() => {
            this.updateMessageStatus();
        }, 30000); // Every 30 seconds
    }

    handleMessageSubmit(e) {
        e.preventDefault();
        
        const input = document.getElementById('message-input');
        const message = input.value.trim();
        
        if (message && this.socket && this.socket.readyState === WebSocket.OPEN) {
            // Show sending status
            this.showMessageStatus('Sending...', 'info');
            
            // Send message
            this.socket.send(JSON.stringify({
                type: 'chat_message',
                message: message,
                timestamp: new Date().toISOString()
            }));
            
            // Clear input
            input.value = '';
            input.style.height = 'auto';
            
            // Clear typing indicator
            this.stopTyping();
            
            // Update send button
            document.getElementById('send-btn').disabled = true;
            
            // Hide status after delay
            setTimeout(() => {
                this.hideMessageStatus();
            }, 2000);
            
        } else if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
            this.showMessageStatus('Connection lost. Please wait...', 'error');
        }
    }

    handleTyping() {
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return;
        
        clearTimeout(this.typingTimeout);
        
        // Send typing indicator
        this.socket.send(JSON.stringify({
            type: 'typing',
            is_typing: true
        }));
        
        // Set timeout to stop typing indicator
        this.typingTimeout = setTimeout(() => {
            this.stopTyping();
        }, 1000);
    }

    stopTyping() {
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return;
        
        clearTimeout(this.typingTimeout);
        
        this.socket.send(JSON.stringify({
            type: 'typing',
            is_typing: false
        }));
    }

    handleWebSocketMessage(data) {
        switch(data.type) {
            case 'chat_message':
                this.addMessage(data);
                break;
                
            case 'typing':
                this.handleTypingIndicator(data);
                break;
                
            case 'user_status':
                this.updateUserStatus(data);
                break;
                
            case 'read_receipt':
                this.handleReadReceipt(data);
                break;
                
            case 'message_deleted':
                this.handleMessageDeleted(data);
                break;
                
            case 'message_edited':
                this.handleMessageEdited(data);
                break;
                
            case 'connection_status':
                this.handleConnectionStatus(data);
                break;
        }
    }

    addMessage(data) {
        const messagesContainer = document.getElementById('chat-messages');
        if (!messagesContainer) return;

        const isSent = data.sender_id == this.currentUserId;
        
        // Create message element
        const messageElement = this.createMessageElement(data, isSent);
        
        // Add to container
        if (isSent) {
            // Find the last sent message and insert after it
            const lastSent = messagesContainer.querySelector('.message-sent-item:last-child');
            if (lastSent) {
                lastSent.after(messageElement);
            } else {
                messagesContainer.appendChild(messageElement);
            }
        } else {
            messagesContainer.appendChild(messageElement);
            
            // Add to unread messages if not current user
            if (!isSent) {
                this.unreadMessages.add(data.message_id);
                this.updateUnreadCount();
            }
        }
        
        // Scroll to bottom
        this.scrollToBottom();
        
        // Send read receipt if not sent by current user
        if (!isSent) {
            this.sendReadReceipt(data.message_id);
        }
        
        // Show notification for new messages
        if (!isSent && !document.hasFocus()) {
            this.showDesktopNotification(data);
        }
    }

    createMessageElement(data, isSent) {
        const div = document.createElement('div');
        div.className = `message-item ${isSent ? 'message-sent-item' : 'message-received-item'}`;
        div.dataset.messageId = data.message_id;
        div.dataset.senderId = data.sender_id;
        
        let senderHtml = '';
        if (!isSent && this.isGroupChat) {
            senderHtml = `
                <div class="flex items-center space-x-2 mb-1">
                    <div class="w-6 h-6 rounded-full bg-gradient-to-r from-blue-400 to-purple-500 flex items-center justify-center">
                        <span class="text-white text-xs font-bold">
                            ${this.escapeHtml(data.sender.charAt(0).toUpperCase())}
                        </span>
                    </div>
                    <span class="font-semibold text-xs text-gray-700 dark:text-gray-300">
                        ${this.escapeHtml(data.sender)}
                    </span>
                </div>
            `;
        }
        
        const time = new Date(data.timestamp).toLocaleTimeString([], { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        
        div.innerHTML = `
            <div class="flex ${isSent ? 'justify-end' : 'justify-start'}">
                <div class="max-w-[70%] md:max-w-[60%]">
                    ${senderHtml}
                    <div class="message-bubble px-4 py-3 ${isSent ? 'message-sent' : 'message-received'}">
                        <div class="mb-1 whitespace-pre-wrap">${this.escapeHtml(data.content).replace(/\n/g, '<br>')}</div>
                        <div class="flex items-center justify-between mt-2">
                            <span class="text-xs opacity-75">
                                ${time}
                            </span>
                            ${isSent ? 
                                '<div class="flex items-center space-x-1 ml-2">' +
                                    '<i class="fas fa-check text-gray-400" title="Sent"></i>' +
                                '</div>' : 
                                ''
                            }
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        return div;
    }

    handleTypingIndicator(data) {
        const indicator = document.getElementById('typing-indicator');
        if (!indicator) return;

        if (data.is_typing) {
            this.typingUsers.add(data.user_id);
        } else {
            this.typingUsers.delete(data.user_id);
        }

        if (this.typingUsers.size > 0) {
            // Show typing indicator
            indicator.classList.remove('hidden');
            indicator.classList.add('flex');
            
            // Update typing text
            const typingText = indicator.querySelector('.typing-text');
            if (typingText) {
                const names = Array.from(this.typingUsers).map(id => 
                    id === data.user_id ? data.username : 'Someone'
                );
                typingText.textContent = `${names.join(', ')} ${names.length > 1 ? 'are' : 'is'} typing...`;
            }
        } else {
            // Hide typing indicator
            indicator.classList.remove('flex');
            indicator.classList.add('hidden');
        }
    }

    sendReadReceipt(messageId) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({
                type: 'read_receipt',
                message_id: messageId
            }));
            
            // Remove from unread messages
            this.unreadMessages.delete(messageId);
            this.updateUnreadCount();
        }
    }

    handleReadReceipt(data) {
        // Update message read status in UI
        const messageElement = document.querySelector(`[data-message-id="${data.message_id}"]`);
        if (messageElement && data.user_id !== this.currentUserId) {
            const checkIcon = messageElement.querySelector('.fa-check');
            if (checkIcon) {
                checkIcon.className = 'fas fa-check-double text-blue-400';
                checkIcon.title = 'Read by ' + data.username;
            }
        }
    }

    updateUserStatus(data) {
        // Update user online status in sidebar
        const userElement = document.querySelector(`[data-user-id="${data.user_id}"] .status-dot`);
        if (userElement) {
            if (data.online) {
                userElement.className = 'status-dot w-3 h-3 bg-green-500 rounded-full border-2 border-white dark:border-gray-800';
                userElement.title = 'Online';
            } else {
                userElement.className = 'status-dot w-3 h-3 bg-gray-400 rounded-full border-2 border-white dark:border-gray-800';
                userElement.title = 'Offline';
            }
        }
    }

    deleteMessage(messageId) {
        if (confirm('Are you sure you want to delete this message?')) {
            if (this.socket && this.socket.readyState === WebSocket.OPEN) {
                this.socket.send(JSON.stringify({
                    type: 'delete_message',
                    message_id: messageId
                }));
            }
        }
    }

    handleMessageDeleted(data) {
        const messageElement = document.querySelector(`[data-message-id="${data.message_id}"]`);
        if (messageElement) {
            messageElement.innerHTML = `
                <div class="flex justify-center">
                    <div class="px-4 py-2 bg-gray-100 dark:bg-gray-800 rounded-lg text-sm text-gray-500 dark:text-gray-400">
                        <i class="fas fa-trash mr-1"></i>
                        Message deleted
                    </div>
                </div>
            `;
            messageElement.classList.add('opacity-50');
        }
    }

    updateConnectionStatus(connected) {
        const statusElement = document.getElementById('connection-status');
        if (statusElement) {
            if (connected) {
                statusElement.innerHTML = '<i class="fas fa-wifi text-green-500 mr-1"></i> Connected';
                statusElement.className = 'text-xs text-green-600';
            } else {
                statusElement.innerHTML = '<i class="fas fa-wifi-slash text-red-500 mr-1"></i> Connecting...';
                statusElement.className = 'text-xs text-red-600';
            }
        }
    }

    handleReconnection() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Reconnection attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${this.reconnectDelay}ms`);
            
            setTimeout(() => {
                this.connectWebSocket();
            }, this.reconnectDelay);
            
            // Increase delay for next attempt
            this.reconnectDelay *= 1.5;
        } else {
            console.error('Max reconnection attempts reached');
            this.showMessageStatus('Unable to connect. Please refresh the page.', 'error');
        }
    }

    showMessageStatus(text, type = 'info') {
        const statusElement = document.getElementById('message-status');
        const statusText = document.getElementById('status-text');
        
        if (statusElement && statusText) {
            statusText.textContent = text;
            statusElement.className = `mt-2 text-xs ${type === 'error' ? 'text-red-600' : 'text-blue-600'}`;
            statusElement.classList.remove('hidden');
        }
    }

    hideMessageStatus() {
        const statusElement = document.getElementById('message-status');
        if (statusElement) {
            statusElement.classList.add('hidden');
        }
    }

    showDesktopNotification(data) {
        if ('Notification' in window && Notification.permission === 'granted' && !document.hasFocus()) {
            const notification = new Notification(`${data.sender}:`, {
                body: data.content.length > 100 ? data.content.substring(0, 100) + '...' : data.content,
                icon: '/static/images/notification-icon.png',
                tag: 'chat-notification'
            });
            
            notification.onclick = () => {
                window.focus();
                notification.close();
            };
        }
    }

    updateUnreadCount() {
        // Update unread count in tab title
        if (this.unreadMessages.size > 0) {
            document.title = `(${this.unreadMessages.size}) ${document.title.replace(/^\(\d+\)\s*/, '')}`;
        } else {
            document.title = document.title.replace(/^\(\d+\)\s*/, '');
        }
    }

    scrollToBottom() {
        const container = document.getElementById('chat-messages');
        if (container) {
            setTimeout(() => {
                container.scrollTop = container.scrollHeight;
            }, 100);
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Export for global use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ChatRoom;
}