import axios, { type AxiosRequestConfig } from "axios"

import { handleUnauthorized } from "@/lib/api/errors"
import type { ApiResponse } from "@/types"

/**
 * Base URL for API requests.
 * Uses Next.js rewrite proxy (/api -> http://localhost:8000/api) in development.
 */
export const baseURL = process.env.NEXT_PUBLIC_API_BASE_URL || "/api"

/**
 * Typed facade over the axios instance.
 *
 * axios 的 `get()` 返回 `Promise<AxiosResponse<any>>`——`any` 的实例化让
 * TypeScript 认为它可以赋给任何类型，因此 `client.get(url)` 直接被当成
 * `Promise<ApiResponse<任意类型>>` 时，编译器**一个字段都不检查**。
 * 这里把边界收紧成显式泛型，调用方必须写出期望的类型。
 */
export type ApiClient = {
  get<T>(url: string, config?: AxiosRequestConfig): Promise<ApiResponse<T>>
  post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<ApiResponse<T>>
  put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<ApiResponse<T>>
  delete<T>(url: string, config?: AxiosRequestConfig): Promise<ApiResponse<T>>
}

const instance = axios.create({
  baseURL,
  timeout: 30000,
})

// Request interceptor: attach JWT
instance.interceptors.request.use(
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
instance.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (typeof window !== "undefined" && error.response?.status === 401) {
      handleUnauthorized()
    }
    return Promise.reject(error)
  },
)

/**
 * The response interceptor unwraps `response.data`, so what callers receive is
 * the `{code, message, data}` envelope rather than an AxiosResponse.
 */
const client = instance as unknown as ApiClient

export default client
