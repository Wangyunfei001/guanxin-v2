/**
 * 消息编辑框的纯逻辑。
 *
 * 发送失败时草稿必须能被恢复，因此「组装内容」与「长度校验」抽成纯函数，
 * 可以脱离浏览器直接测试。
 */

/** 单次输入的总长度上限（正文 + 附件）。 */
export const MAX_INPUT_CHARS = 100000

export type TextAttachment = { name: string; content: string }

/** 把正文与文本附件组装成一条消息。 */
export function composeMessage(
  text: string,
  attachment: TextAttachment | null,
): string {
  return attachment
    ? `${text}\n\n附件 ${attachment.name}：\n${attachment.content}`
    : text
}

/** 是否超出输入长度上限。 */
export function exceedsInputLimit(
  content: string,
  limit: number = MAX_INPUT_CHARS,
): boolean {
  return content.length > limit
}
