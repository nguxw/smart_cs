import {
  BriefcaseBusiness,
  ClipboardList,
  FileSearch,
  Gauge,
  MessageSquare,
  Workflow
} from "lucide-react";

import type { NavItem } from "../types/api";

export const NAV_ITEMS: NavItem[] = [
  { key: "desk", label: "会话处理", icon: <MessageSquare /> },
  { key: "cases", label: "服务案件", icon: <BriefcaseBusiness /> },
  { key: "tickets", label: "工单队列", icon: <ClipboardList /> },
  { key: "kb", label: "知识运营", icon: <FileSearch /> },
  { key: "evals", label: "发布门禁", icon: <Gauge /> },
  { key: "system", label: "AgentOps", icon: <Workflow /> }
];
