// Chat Application JavaScript

class ChatApp {
    constructor() {
        this.socket = null;
        this.currentRoom = null;
        this.typingTimeout = null;
        this.init();
    }

    init() {
        this.initEventListeners();
        this.initWebSocket();
        this.initNotifications();
    }

    initEventListeners() {
        // Message form submission
        const messageForm = document.getElementById('message-form');
        if (messageForm) {
            messageForm.addEventListener('submit', (e) => this.handleMessageSubmit(e));
        }

        // Typing indicator
        const messageInput = document.getElementById('message-input');
        if (messageInput) {
            messageInput.addEventListener('input', () => this.handleTyping());
        }

        // Theme toggle
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => this.toggleTheme());
        }

        // Language switcher
        const languageSelect = document.getElementById('language-select');
        if (languageSelect) {
            languageSelect.addEventListener('change', (e) => this.changeLanguage(e.target.value));
        }

        // Mobile menu toggle
        const mobileMenuButton = document.getElementById('mobile-menu-button');
        if (mobileMenuButton) {
            mobileMenuButton.addEventListener('click', () => this.toggleMobileMenu());
        }
    }

    initWebSocket() {
        const roomId = document.currentScript?.getAttribute('data-room-id');
        if (!roomId) return;

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/chat/${roomId}/`;

        this.socket = new WebSocket(wsUrl);
        this.currentRoom = roomId;

        this.socket.onopen = () => {
            console.log('WebSocket connected');
            this.updateUserStatus(true);
        };

        this.socket.onmessage = (event) => {
            this.handleWebSocketMessage(JSON.parse(event.data));
        };

        this.socket.onclose = () => {
            console.log('WebSocket disconnected. Reconnecting...');
            setTimeout(() => this.initWebSocket(), 3000);
            this.updateUserStatus(false);
        };

        this.socket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    initNotifications() {
        // Request notification permission
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }

        // Connect to notification WebSocket
        this.connectNotificationSocket();
    }

    connectNotificationSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/notifications/`;

        const notificationSocket = new WebSocket(wsUrl);

        notificationSocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.showNotification(data);
        };
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'chat_message':
                this.addMessage(data);
                break;
            case 'typing':
                this.showTypingIndicator(data);
                break;
            case 'user_status':
                this.updateUserStatusDisplay(data);
                break;
            case 'read_receipt':
                this.updateReadReceipt(data);
                break;
            case 'notification':
                this.showNotification(data);
                break;
        }
    }

    addMessage(data) {
        const messagesContainer = document.getElementById('chat-messages');
        if (!messagesContainer) return;

        const messageElement = this.createMessageElement(data);
        messagesContainer.appendChild(messageElement);
        this.scrollToBottom();

        // Mark as read if not sent by current user
        if (data.sender_id != this.getCurrentUserId()) {
            this.sendReadReceipt(data.message_id);
        }

        // Show notification for new messages when not focused
        if (data.sender_id != this.getCurrentUserId() && !document.hasFocus()) {
            this.showDesktopNotification(data);
        }
    }

    createMessageElement(data) {
        const isSent = data.sender_id == this.getCurrentUserId();
        const isGroup = document.currentScript?.getAttribute('data-room-type') === 'group';
        
        const div = document.createElement('div');
        div.className = `flex ${isSent ? 'justify-end' : 'justify-start'}`;
        
        div.innerHTML = `
            <div class="message-bubble px-4 py-3 ${isSent ? 'message-sent' : 'message-received'}">
                ${!isSent && isGroup ? `
                    <div class="font-semibold text-xs mb-1 opacity-75">
                        ${data.sender}
                    </div>
                ` : ''}
                <div class="mb-1">${this.escapeHtml(data.content).replace(/\n/g, '<br>')}</div>
                <div class="text-xs opacity-75 flex items-center space-x-2">
                    <span>${new Date(data.timestamp).toLocaleTimeString()}</span>
                    ${isSent ? '<i class="fas fa-check text-gray-400"></i>' : ''}
                </div>
            </div>
        `;
        
        return div;
    }

    showTypingIndicator(data) {
        const indicator = document.getElementById('typing-indicator');
        if (!indicator) return;

        if (data.is_typing && data.user_id != this.getCurrentUserId()) {
            indicator.classList.remove('hidden');
            indicator.classList.add('flex');
        } else {
            indicator.classList.remove('flex');
            indicator.classList.add('hidden');
        }
        
        this.scrollToBottom();
    }

    handleMessageSubmit(e) {
        e.preventDefault();
        
        const input = document.getElementById('message-input');
        const message = input.value.trim();
        
        if (message && this.socket) {
            this.socket.send(JSON.stringify({
                type: 'chat_message',
                message: message
            }));
            
            input.value = '';
            
            // Clear typing indicator
            clearTimeout(this.typingTimeout);
            this.socket.send(JSON.stringify({
                type: 'typing',
                is_typing: false
            }));
        }
    }

    handleTyping() {
        if (!this.socket) return;
        
        clearTimeout(this.typingTimeout);
        
        this.socket.send(JSON.stringify({
            type: 'typing',
            is_typing: true
        }));
        
        this.typingTimeout = setTimeout(() => {
            this.socket.send(JSON.stringify({
                type: 'typing',
                is_typing: false
            }));
        }, 1000);
    }

    sendReadReceipt(messageId) {
        if (this.socket) {
            this.socket.send(JSON.stringify({
                type: 'read_receipt',
                message_id: messageId
            }));
        }
    }

    updateUserStatus(online) {
        // Update status via API
        fetch('/api/user/status/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken(),
            },
            body: JSON.stringify({ online: online })
        });
    }

    updateUserStatusDisplay(data) {
        // Update user status in UI
        const userElements = document.querySelectorAll(`[data-user-id="${data.user_id}"] .status-indicator`);
        userElements.forEach(element => {
            if (data.online) {
                element.className = 'status-indicator w-3 h-3 bg-green-500 rounded-full';
            } else {
                element.className = 'status-indicator w-3 h-3 bg-gray-400 rounded-full';
            }
        });
    }

    updateReadReceipt(data) {
        // Update message read status
        const messageElement = document.querySelector(`[data-message-id="${data.message_id}"] .read-status`);
        if (messageElement) {
            messageElement.innerHTML = '<i class="fas fa-check-double text-blue-300"></i>';
        }
    }

    showNotification(data) {
        // Show browser notification
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification(data.title || 'New Message', {
                body: data.message,
                icon: data.icon || '/static/images/logo.png'
            });
        }

        // Show in-app notification
        this.showInAppNotification(data);
    }

    showInAppNotification(data) {
        const container = document.getElementById('notification-container');
        if (!container) return;

        const notification = document.createElement('div');
        notification.className = 'notification bg-white dark:bg-gray-800 rounded-lg shadow-lg p-4 mb-2 border-l-4 border-primary-500';
        notification.innerHTML = `
            <div class="flex items-center">
                <div class="flex-shrink-0">
                    <img src="${data.avatar || 'https://via.placeholder.com/40'}" 
                         class="w-10 h-10 rounded-full" alt="${data.sender}">
                </div>
                <div class="ml-3">
                    <p class="text-sm font-medium text-gray-900 dark:text-white">${data.sender}</p>
                    <p class="text-sm text-gray-500 dark:text-gray-400">${data.message}</p>
                </div>
            </div>
        `;

        container.appendChild(notification);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            notification.remove();
        }, 5000);
    }

    showDesktopNotification(data) {
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification(`${data.sender}:`, {
                body: data.content,
                icon: '/static/images/notification-icon.png',
                tag: 'chat-notification'
            });
        }
    }

    toggleTheme() {
        const html = document.documentElement;
        html.classList.toggle('dark');
        
        // Save preference
        fetch('/api/user/theme/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken(),
            },
            body: JSON.stringify({
                theme: html.classList.contains('dark') ? 'dark' : 'light'
            })
        });
    }

    changeLanguage(lang) {
        fetch('/i18n/setlang/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': this.getCsrfToken(),
            },
            body: `language=${lang}`
        }).then(() => {
            window.location.reload();
        });
    }

    toggleMobileMenu() {
        const menu = document.getElementById('mobile-menu');
        menu.classList.toggle('hidden');
    }

    scrollToBottom() {
        const container = document.getElementById('chat-messages');
        if (container) {
            container.scrollTop = container.scrollHeight;
        }
    }

    getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    }

    getCurrentUserId() {
        return parseInt(document.currentScript?.getAttribute('data-user-id') || '0');
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Utility functions
    formatTime(date) {
        return new Date(date).toLocaleTimeString([], { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
    }

    formatDate(date) {
        const now = new Date();
        const messageDate = new Date(date);
        
        if (now.toDateString() === messageDate.toDateString()) {
            return 'Today';
        }
        
        const yesterday = new Date(now);
        yesterday.setDate(yesterday.getDate() - 1);
        if (yesterday.toDateString() === messageDate.toDateString()) {
            return 'Yesterday';
        }
        
        return messageDate.toLocaleDateString();
    }
}

// Initialize the chat app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.chatApp = new ChatApp();
});