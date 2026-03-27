/** 通用工具函数 */

/** 拼接 CSS 类名，过滤 falsy 值 */
export function cn(...classes: (string | boolean | undefined | null)[]): string {
  return classes.filter(Boolean).join(" ");
}
