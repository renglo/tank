import React, { useState, useEffect } from 'react';
import io from 'socket.io-client';

const ChatComponent = () => {
    const [socket, setSocket] = useState(null);
    const [message, setMessage] = useState('');
    const [messages, setMessages] = useState([]);

    useEffect(() => {
        // Initialize socket connection
        const newSocket = io('http://localhost:5000', {
            path: '/_chat',
            transports: ['websocket']
        });

        // Set up event listeners
        newSocket.on('connect', () => {
            console.log('Connected to chat server');
        });

        newSocket.on('chat_response', (data) => {
            setMessages(prev => [...prev, data.message]);
        });

        setSocket(newSocket);

        // Cleanup on unmount
        return () => newSocket.close();
    }, []);

    const sendMessage = (e) => {
        e.preventDefault();
        if (socket && message.trim()) {
            socket.emit('chat_message', message);
            setMessage('');
        }
    };

    return (
        <div style={{ padding: '20px', maxWidth: '600px', margin: '0 auto' }}>
            <div style={{ 
                height: '300px', 
                border: '1px solid #ccc', 
                overflowY: 'auto', 
                padding: '10px',
                marginBottom: '10px'
            }}>
                {messages.map((msg, index) => (
                    <div key={index} style={{ marginBottom: '5px' }}>
                        {msg}
                    </div>
                ))}
            </div>
            <form onSubmit={sendMessage}>
                <input
                    type="text"
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    placeholder="Type a message..."
                    style={{ width: '80%', padding: '8px' }}
                />
                <button type="submit" style={{ padding: '8px 15px', marginLeft: '10px' }}>
                    Send
                </button>
            </form>
        </div>
    );
};

export default ChatComponent; 