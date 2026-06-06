import React, { createContext, useContext, useState, useEffect } from 'react';
import { apiClient } from '../api/client';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // Check if the user is already logged in by pinging the backend
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const response = await apiClient.get('/status/ping');
        if (response.data && response.data.ok) {
          setUser({ id: response.data.user_id });
        }
      } catch (error) {
        // If 401 Unauthorized, they are not logged in.
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    };

    checkAuth();
  }, []);

  const login = async (email, password) => {
    try {
      const response = await apiClient.post('/login', { email, password });
      if (response.data && response.data.ok) {
        // Re-ping to get user ID
        const pingResponse = await apiClient.get('/status/ping');
        setUser({ id: pingResponse.data.user_id });
        return { success: true };
      }
      return { success: false, error: 'Login failed' };
    } catch (error) {
      return { success: false, error: error.response?.data?.detail || 'An error occurred during login' };
    }
  };

  const signup = async (email, password, github_token) => {
    try {
      const response = await apiClient.post('/signup', { email, password, github_token });
      if (response.data && response.data.ok) {
        const pingResponse = await apiClient.get('/status/ping');
        setUser({ id: pingResponse.data.user_id });
        return { success: true };
      }
      return { success: false, error: 'Signup failed' };
    } catch (error) {
      return { success: false, error: error.response?.data?.detail || 'An error occurred during signup' };
    }
  };

  const logout = async () => {
    try {
      await apiClient.post('/logout');
    } catch (error) {
      console.error('Logout failed:', error);
    } finally {
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
