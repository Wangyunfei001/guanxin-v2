import client from "./client"
import type { A2UISchema, ApiResponse } from "@/types"

/**
 * A2UI API module.
 * Handles catalog, templates, preview, and rendering.
 */
export const a2uiApi = {
  /**
   * Get the A2UI component catalog (available component types).
   */
  getCatalog(): Promise<ApiResponse<any[]>> {
    return client.get("/a2ui/catalog")
  },

  /**
   * Get preset templates.
   */
  getTemplates(): Promise<ApiResponse<any[]>> {
    return client.get("/a2ui/templates")
  },

  /**
   * Preview a schema (validate + normalize).
   */
  previewSchema(schema: A2UISchema): Promise<ApiResponse<any>> {
    return client.post("/a2ui/preview", { schema })
  },

  /**
   * Render a template with data.
   */
  renderTemplate(
    templateName: string,
    data: any,
  ): Promise<ApiResponse<A2UISchema>> {
    return client.post("/a2ui/render", { template_name: templateName, data })
  },

  /**
   * Render a dynamic schema.
   */
  renderDynamic(data: {
    component_type: string
    title?: string
    props?: Record<string, any>
    children?: A2UISchema[]
  }): Promise<ApiResponse<A2UISchema>> {
    return client.post("/a2ui/render-dynamic", data)
  },
}
