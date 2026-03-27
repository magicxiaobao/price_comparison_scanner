import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "../ui/sheet";
import { Button } from "../ui/button";
import { ScrollArea } from "../ui/scroll-area";

interface EvidenceDrawerShellProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
}

export function EvidenceDrawerShell({ isOpen, onClose, title = "证据详情" }: EvidenceDrawerShellProps) {
  return (
    <Sheet open={isOpen} onOpenChange={onClose}>
      <SheetContent className="w-[800px] sm:max-w-none p-0 flex flex-col gap-0 border-l border-slate-200 shadow-xl">
        <SheetHeader className="px-6 py-4 border-b border-slate-100 bg-white z-10 text-left">
          <SheetTitle className="text-base font-semibold text-slate-900">{title}</SheetTitle>
          <SheetDescription className="sr-only">显示所选证据内容的抽屉弹窗</SheetDescription>
        </SheetHeader>
        
        <ScrollArea className="flex-1 bg-slate-50 p-6">
          <div className="flex flex-col items-center justify-center text-center h-full opacity-60 min-h-[400px]">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 text-slate-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p className="text-sm text-slate-500 font-medium">尚无正在查看的证据来源</p>
            <p className="text-xs text-slate-400 mt-2 max-w-[250px]">
              在此处可以预览原始文件中对应的异常单元格或关联数据的上下文截图。
            </p>
          </div>
        </ScrollArea>
        
        <div className="px-6 py-4 border-t border-slate-100 bg-white">
          <Button variant="outline" className="w-full" onClick={onClose}>
            关闭面板
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
