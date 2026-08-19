import client from "./client"
import type { SkillMetadata, ApiResponse } from "@/types"

/**
 * Skill API module.
 * Handles skill listing, detail, and execution.
 */
export const skillApi = {
  /**
   * List all available skills.
   */
  listSkills(): Promise<ApiResponse<SkillMetadata[]>> {
    return client.get("/skills")
  },

  /**
   * Get detail for a single skill.
   */
  getSkillDetail(skillName: string): Promise<ApiResponse<SkillMetadata>> {
    return client.get(`/skills/${skillName}`)
  },

  /**
   * Execute a skill with parameters.
   */
  executeSkill(
    skillName: string,
    params: Record<string, any>,
  ): Promise<ApiResponse<any>> {
    return client.post("/skills/execute", { skill_name: skillName, params })
  },
}
