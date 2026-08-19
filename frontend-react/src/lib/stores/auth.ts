"use client"

import { create } from "zustand"
import { authApi } from "@/lib/api/auth"
import type { User, ApiResponse, LoginResult } from "@/types"

interface AuthState {
  token: string
  user: User | null
  isLoggedIn: boolean
  isAdmin: boolean
  login: (username: string, password: string) => Promise<ApiResponse<LoginResult>>
  logout: () => void
  fetchMe: () => Promise<void>
}

/**
 * Initialize auth state from localStorage.
 * Reads access_token and user_info on module load (client-side only).
 */
function getInitialToken(): string {
  if (typeof window !== "undefined") {
    return localStorage.getItem("access_token") || ""
  }
  return ""
}

function getInitialUser(): User | null {
  if (typeof window !== "undefined") {
    const info = localStorage.getItem("user_info")
    if (info) {
      try {
        return JSON.parse(info)
      } catch {
        return null
      }
    }
  }
  return null
}

export const useAuthStore = create<AuthState>()((set) => ({
  token: getInitialToken(),
  user: getInitialUser(),
  isLoggedIn: !!getInitialToken(),
  isAdmin: getInitialUser()?.role === "admin",

  login: async (username: string, password: string) => {
    const res = await authApi.login(username, password)
    if (res.code === 0 && res.data) {
      const token = res.data.access_token
      const user = res.data.user
      set({
        token,
        user,
        isLoggedIn: true,
        isAdmin: user.role === "admin",
      })
      if (typeof window !== "undefined") {
        localStorage.setItem("access_token", token)
        localStorage.setItem("user_info", JSON.stringify(user))
      }
    }
    return res
  },

  logout: () => {
    set({
      token: "",
      user: null,
      isLoggedIn: false,
      isAdmin: false,
    })
    if (typeof window !== "undefined") {
      localStorage.removeItem("access_token")
      localStorage.removeItem("user_info")
    }
  },

  fetchMe: async () => {
    try {
      const res = await authApi.getMe()
      if (res.code === 0 && res.data) {
        set({
          user: res.data,
          isAdmin: res.data.role === "admin",
        })
        if (typeof window !== "undefined") {
          localStorage.setItem("user_info", JSON.stringify(res.data))
        }
      }
    } catch {
      set({
        token: "",
        user: null,
        isLoggedIn: false,
        isAdmin: false,
      })
      if (typeof window !== "undefined") {
        localStorage.removeItem("access_token")
        localStorage.removeItem("user_info")
      }
    }
  },
}))
