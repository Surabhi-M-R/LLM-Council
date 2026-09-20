/**
 * API client for the LLM Council backend.
 */

const API_BASE = 'http://localhost:8001';

const handleFetch = async (url, options) => {
  try {
    const response = await fetch(url, options);
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Server error (${response.status})`);
    }
    return response;
  } catch (err) {
    if (err.message && err.message.includes('Server error')) {
      throw err;
    }
    if (err.name === 'TypeError' || err.message?.includes('Failed to fetch')) {
      throw new Error(
        'Backend server is disconnected (http://localhost:8001). Please start the backend server using: python -m backend.main'
      );
    }
    throw err;
  }
};

export const api = {
  /**
   * List all conversations.
   */
  async listConversations() {
    const response = await handleFetch(`${API_BASE}/api/conversations`);
    return response.json();
  },

  /**
   * Create a new conversation.
   */
  async createConversation() {
    const response = await handleFetch(`${API_BASE}/api/conversations`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    });
    return response.json();
  },

  /**
   * Get a specific conversation.
   */
  async getConversation(conversationId) {
    const response = await handleFetch(
      `${API_BASE}/api/conversations/${conversationId}`
    );
    return response.json();
  },

  /**
   * Send a message in a conversation.
   */
  async sendMessage(conversationId, content) {
    const response = await handleFetch(
      `${API_BASE}/api/conversations/${conversationId}/message`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content }),
      }
    );
    return response.json();
  },

  /**
   * Send a message and receive streaming updates.
   * @param {string} conversationId - The conversation ID
   * @param {string} content - The message content
   * @param {function} onEvent - Callback function for each event: (eventType, data) => void
   * @returns {Promise<void>}
   */
  async sendMessageStream(conversationId, content, onEvent) {
    let response;
    try {
      response = await fetch(
        `${API_BASE}/api/conversations/${conversationId}/message/stream`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ content }),
        }
      );
    } catch (err) {
      throw new Error(
        'Backend server is disconnected (http://localhost:8001). Please start the backend server using: python -m backend.main'
      );
    }

    if (!response.ok) {
      throw new Error('Failed to send message: Server returned ' + response.status);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      // Keep the last (potentially incomplete) line in the buffer
      buffer = lines.pop();

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          try {
            const event = JSON.parse(data);
            onEvent(event.type, event);
          } catch (e) {
            console.error('Failed to parse SSE event:', e);
          }
        }
      }
    }
  },
};

