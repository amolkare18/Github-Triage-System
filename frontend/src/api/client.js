import axios from 'axios';

// When running locally via Vite dev server, this will be empty, 
// and requests will hit the Vite proxy (which forwards to localhost:8001).
// In production, you might want this to point to the actual backend URL if they are hosted separately,
// or if they are hosted together, leave it empty.
// We check if it's production and a specific backend URL is provided via env var.
const baseURL = import.meta.env.VITE_API_URL || '';

export const apiClient = axios.create({
  baseURL,
  withCredentials: true, // Crucial: This ensures cookies are sent with every request
  headers: {
    'Content-Type': 'application/json',
  },
});
