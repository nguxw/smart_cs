import {
  ClipboardList,
  FileSearch,
  Gauge,
  MessageSquare,
  Workflow
} from "lucide-react";

import type { NavItem } from "../types/api";

export const NAV_ITEMS: NavItem[] = [
  { key: "desk", label: "坐席工作台", icon: <MessageSquare /> },
  { key: "tickets", label: "工单队列", icon: <ClipboardList /> },
  { key: "kb", label: "知识运营", icon: <FileSearch /> },
  { key: "evals", label: "发布门禁", icon: <Gauge /> },
  { key: "system", label: "AgentOps", icon: <Workflow /> }
];
