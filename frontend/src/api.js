/**
 * API client for the LLM Council backend — AWS Edition.
 */

const API_BASE = 'http://localhost:8001';

// ---------------------------------------------------------------------------
// Auth Token Management
// ---------------------------------------------------------------------------

let authToken = null;

export function setAuthToken(token) {
  authToken = token;
  if (token) {
    localStorage.setItem('llm_council_token', token);
  } else {
    localStorage.removeItem('llm_council_token');
  }
}

export function getAuthToken() {
  if (!authToken) {
    authToken = localStorage.getItem('llm_council_token');
  }
  return authToken;
}

export function clearAuth() {
  authToken = null;
  localStorage.removeItem('llm_council_token');
  localStorage.removeItem('llm_council_user');
}

// ---------------------------------------------------------------------------
// HTTP Helpers
// ---------------------------------------------------------------------------

const getHeaders = () => {
  const headers = { 'Content-Type': 'application/json' };
  const token = getAuthToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
};

const handleFetch = async (url, options = {}) => {
  try {
    const response = await fetch(url, {
      ...options,
      headers: { ...getHeaders(), ...(options.headers || {}) },
    });

    if (response.status === 401) {
      clearAuth();
      throw new Error('Session expired. Please sign in again.');
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Server error (${response.status})`);
    }
    return response;
  } catch (err) {
    if (err.message && err.message.includes('Server error')) {
      throw err;
    }
    if (err.message && err.message.includes('Session expired')) {
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

// ---------------------------------------------------------------------------
// API Methods
// ---------------------------------------------------------------------------

export const api = {
  // ---- System ----

  /**
   * Get system configuration (provider, models, features).
   */
  async getSystemConfig() {
    const response = await handleFetch(`${API_BASE}/api/system/config`);
    return response.json();
  },

  /**
   * Health check.
   */
  async healthCheck() {
    const response = await handleFetch(`${API_BASE}/health`);
    return response.json();
  },

  // ---- Authentication ----

  /**
   * Sign up a new user.
   */
  async signUp(email, username, password) {
    const response = await handleFetch(`${API_BASE}/api/auth/signup`, {
      method: 'POST',
      body: JSON.stringify({ email, username, password }),
    });
    return response.json();
  },

  /**
   * Sign in and get tokens.
   */
  async signIn(username, password) {
    const response = await handleFetch(`${API_BASE}/api/auth/signin`, {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    const data = await response.json();
    if (data.id_token) {
      setAuthToken(data.id_token);
      localStorage.setItem('llm_council_user', username);
    }
    return data;
  },

  /**
   * Confirm sign up with verification code.
   */
  async confirmSignUp(username, confirmationCode) {
    const response = await handleFetch(`${API_BASE}/api/auth/confirm`, {
      method: 'POST',
      body: JSON.stringify({ username, confirmation_code: confirmationCode }),
    });
    return response.json();
  },

  /**
   * Get current user info.
   */
  async getCurrentUser() {
    const response = await handleFetch(`${API_BASE}/api/auth/me`);
    return response.json();
  },

  // ---- Conversations ----

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
   * Delete a conversation.
   */
  async deleteConversation(conversationId) {
    const response = await handleFetch(
      `${API_BASE}/api/conversations/${conversationId}`,
      { method: 'DELETE' }
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
          headers: getHeaders(),
          body: JSON.stringify({ content }),
        }
      );
    } catch (err) {
      throw new Error(
        'Backend server is disconnected (http://localhost:8001). Please start the backend server using: python -m backend.main'
      );
    }

    if (response.status === 401) {
      clearAuth();
      throw new Error('Session expired. Please sign in again.');
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
