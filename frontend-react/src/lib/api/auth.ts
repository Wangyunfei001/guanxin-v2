import client from "./client"
import type { LoginResult, User, ApiResponse } from "@/types"

/**
 * Authentication API module.
 */
export const authApi = {
  /**
   * Login with username/password.
   * Returns ApiResponse<LoginResult> with access_token and user.
   */
  login(
    username: string,
    password: string,
    tenant_id = "",
  ): Promise<ApiResponse<LoginResult>> {
    return client.post("/auth/login", { username, password, tenant_id })
  },

  /**
   * Get current user info.
   */
  getMe(): Promise<ApiResponse<User>> {
    return client.get("/auth/me")
  },
}
