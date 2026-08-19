import axios, { type AxiosInstance } from "axios"

/**
 * Base URL for API requests.
 * Uses Next.js rewrite proxy (/api -> http://localhost:8000/api) in development.
 */
export const baseURL = process.env.NEXT_PUBLIC_API_BASE_URL || "/api"

/**
 * Axios instance with JWT request interceptor and 401 response interceptor.
 *
 * Request interceptor: reads `access_token` from localStorage, sets Authorization header.
 * Response interceptor: returns `response.data` (the ApiResponse object directly).
 * 401 handler: clears localStorage tokens and redirects to /login.
 */
const client: AxiosInstance = axios.create({
  baseURL,
  timeout: 30000,
})

// Request interceptor: attach JWT
client.interceptors.request.use(
  (config) => {
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("access_token")
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
    }
    return config
  },
  (error) => Promise.reject(error),
)

// Response interceptor: unwrap data + handle 401
client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (typeof window !== "undefined" && error.response?.status === 401) {
      localStorage.removeItem("access_token")
      localStorage.removeItem("user_info")
      window.location.href = "/login"
    }
    return Promise.reject(error)
  },
)

export default client
