import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Separator } from "../components/ui/separator";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Card } from "../components/ui/card";

function AppPreferences() {
  const navigate = useNavigate();

  return (
    <div className="flex flex-col h-screen bg-slate-50 font-sans overflow-hidden min-w-[1280px]">
      <header className="flex-none h-14 bg-white border-b border-slate-200 flex items-center px-6 shadow-sm z-10 transition-colors">
        <Button variant="ghost" size="sm" className="gap-2 text-slate-500" onClick={() => navigate("/")}>
          <span aria-hidden="true">&larr;</span> 返回首页
        </Button>
        <Separator orientation="vertical" className="mx-4 h-4" />
        <h1 className="text-sm font-semibold text-slate-900 tracking-wide flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-slate-400"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"></path><circle cx="12" cy="12" r="3"></circle></svg>
          应用偏好设置
        </h1>
      </header>

      <div className="flex flex-1 overflow-hidden max-w-[1600px] w-full mx-auto p-6 gap-6">
        <nav className="w-64 flex-none space-y-1">
          <div className="px-3 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
            通用
          </div>
          <Button variant="secondary" className="w-full justify-start font-medium text-blue-700 bg-blue-50 hover:bg-blue-100">
            基础设置
          </Button>
          
          <div className="px-3 py-2 mt-6 text-xs font-semibold text-slate-500 uppercase tracking-wider">
            数据与隐私
          </div>
          <Button variant="ghost" className="w-full justify-start font-medium text-slate-600">
            本地存储说明
          </Button>
        </nav>

        <Card className="flex-1 flex flex-col overflow-hidden bg-white border-slate-200">
          <div className="flex-none border-b border-slate-100 p-8 pb-5 z-10">
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">基础设置</h2>
            <p className="text-sm text-slate-500 mt-1.5 font-medium">管理应用的全局通用配置行为，更改立即生效。</p>
          </div>

          <div className="flex-1 overflow-y-auto p-8 pt-6">
            <div className="space-y-8 max-w-2xl">
              <div className="space-y-4">
                <label className="block text-sm font-semibold text-slate-900">默认导出格式</label>
                <Select defaultValue="xlsx">
                  <SelectTrigger className="w-full max-w-xs">
                    <SelectValue placeholder="选择格式" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="xlsx">Excel 工作簿 (.xlsx)</SelectItem>
                    <SelectItem value="csv">逗号分隔值 (.csv)</SelectItem>
                  </SelectContent>
               </Select>
                <p className="text-xs text-slate-500">此选项决定在"比价导出"阶段，默认选中的格式。</p>
              </div>

              <Separator />

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <label className="block text-sm font-semibold text-slate-900">更新通知</label>
                    <p className="text-xs text-slate-500 mt-0.5">自动检测应用新版本并在启动时通知。</p>
                  </div>
                  <button className="relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent bg-blue-600 transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-600 focus:ring-offset-2">
                    <span className="translate-x-5 pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out"></span>
                  </button>
                </div>
              </div>

              <Separator />

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <label className="block text-sm font-semibold text-slate-900">自动清理临时文件</label>
                    <p className="text-xs text-slate-500 mt-0.5">退出项目工作区时，自动清理上传阶段生成的切片文件。</p>
                  </div>
                  <button className="relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent bg-slate-200 transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-600 focus:ring-offset-2">
                    <span className="translate-x-0 pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out"></span>
                  </button>
                </div>
              </div>

              <Separator />

              <div className="space-y-4">
                <label className="block text-sm font-semibold text-slate-900">本地桌面工具声明</label>
                <div className="bg-slate-50 border border-slate-200 rounded-md p-4 text-sm text-slate-600 leading-relaxed">
                  本工具为纯本地桌面应用程序。所有项目数据、扫描规则和凭证切片均严格存储在您的本地磁盘设备上，<strong>不会</strong>上传至任何外部云端服务器，充分保障数据安全。
                </div>
              </div>

              <div className="pt-8 flex justify-end">
                <Button>保存更改</Button>
              </div>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}

export default AppPreferences;
