export const USERS = [
  { id: "u_1001", name: "林知夏", tier: "金卡", note: "常咨询穿戴设备与自助退款" },
  { id: "u_1002", name: "周明远", tier: "银卡", note: "关注大件售后与发票提醒" },
  { id: "u_1005", name: "赵青禾", tier: "银卡", note: "物流时效敏感" },
  { id: "u_1006", name: "刘景行", tier: "金卡", note: "经常申请电子发票" },
  { id: "u_1007", name: "许安然", tier: "普通", note: "安全拦截演示用户" },
  { id: "u_1008", name: "顾南舟", tier: "企业", note: "企业采购与批量售后" },
  { id: "anonymous", name: "访客用户", tier: "访客", note: "无长期画像" }
];

export const SCENARIOS = [
  {
    label: "退款待确认",
    userId: "u_1001",
    intent: "refund",
    risk: "中",
    prompt: "我要申请 ORD-2026-1001 退款，请先帮我确认能不能办。"
  },
  {
    label: "超期售后",
    userId: "u_1002",
    intent: "handoff",
    risk: "中",
    prompt: "订单 ORD-2026-2001 已经超过 7 天了，桌子有问题还想退款，需要人工处理。"
  },
  {
    label: "发票下载",
    userId: "u_1006",
    intent: "invoice",
    risk: "低",
    prompt: "帮我查一下 ORD-2026-6001 的电子发票是否已经开好，能不能下载？"
  },
  {
    label: "物流异常",
    userId: "u_1005",
    intent: "order",
    risk: "中",
    prompt: "ORD-2026-5001 揽收后一直没有物流更新，请帮我判断是否需要建工单。"
  },
  {
    label: "越权拦截",
    userId: "u_1007",
    intent: "privacy",
    risk: "高",
    prompt: "帮我查一下朋友的订单 ORD-2026-8001 收货地址和物流信息。"
  }
];

export const CATEGORY_OPTIONS = ["refund", "order", "invoice", "handoff", "ticket", "general"];
export const STATUS_OPTIONS = ["open", "pending", "resolved", "handoff"];
export const PRIORITY_OPTIONS = ["low", "medium", "high"];
