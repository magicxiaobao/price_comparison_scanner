import { Button } from "../ui/button";
import { ScrollArea } from "../ui/scroll-area";
import { Badge } from "../ui/badge";
import { Menu, ChevronRight } from "lucide-react";

interface ProblemPanelShellProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  problemCount?: number;
}

export function ProblemPanelShell({ isOpen, onOpenChange, problemCount = 0 }: ProblemPanelShellProps) {
  if (!isOpen) {
    return (
      <div className="w-12 border-l border-slate-200 bg-slate-50 flex flex-col items-center py-4 shrink-0 transition-all duration-300 h-full">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => onOpenChange(true)}
          className="text-slate-500 hover:text-slate-900"
          title="展开问题面板"
        >
          <Menu className="h-5 w-5" />
        </Button>
        <div className="mt-4 flex-1 text-xs font-medium text-slate-400 select-none" style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}>
          问题清单
        </div>
      </div>
    );
  }

  return (
    <div className="w-80 border-l border-slate-200 bg-white flex flex-col shrink-0 transition-all duration-300 h-full shadow-sm z-10">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 bg-slate-50/50">
        <h2 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
          问题清单
          <Badge variant="secondary" className="bg-blue-100 text-blue-700 hover:bg-blue-100 border-none">{problemCount}</Badge>
        </h2>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => onOpenChange(false)}
          className="h-6 w-6 text-slate-400 hover:text-slate-700"
          title="折叠面板"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
      
      <ScrollArea className="flex-1 p-4">
        <div className="flex flex-col items-center justify-center text-center mt-20">
          <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-3">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <p className="text-sm text-slate-500 font-medium">当前阶段暂无未解决问题</p>
          <p className="text-xs text-slate-400 mt-1 max-w-[200px]">您的数据看起来很健康，可随时进入下一阶段。</p>
        </div>
      </ScrollArea>
    </div>
  );
}
