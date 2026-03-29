import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Separator } from "../components/ui/separator";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Card } from "../components/ui/card";

type NavSection = "general" | "storage";

function AppPreferences() {
  const navigate = useNavigate();
  const [activeSection, setActiveSection] = useState<NavSection>("general");

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
          <Button
            variant={activeSection === "general" ? "secondary" : "ghost"}
            className={`w-full justify-start font-medium ${activeSection === "general" ? "text-blue-700 bg-blue-50 hover:bg-blue-100" : "text-slate-600"}`}
            onClick={() => setActiveSection("general")}
          >
            基础设置
          </Button>

          <div className="px-3 py-2 mt-6 text-xs font-semibold text-slate-500 uppercase tracking-wider">
            数据与隐私
          </div>
          <Button
            variant={activeSection === "storage" ? "secondary" : "ghost"}
            className={`w-full justify-start font-medium ${activeSection === "storage" ? "text-blue-700 bg-blue-50 hover:bg-blue-100" : "text-slate-600"}`}
            onClick={() => setActiveSection("storage")}
          >
            本地存储说明
          </Button>
        </nav>

        <Card className="flex-1 flex flex-col overflow-hidden bg-white border-slate-200">
          {activeSection === "general" && (
            <>
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

                  <div className="pt-8 flex justify-end">
                    <Button>保存更改</Button>
                  </div>
                </div>
              </div>
            </>
          )}

          {activeSection === "storage" && (
            <>
              <div className="flex-none border-b border-slate-100 p-8 pb-5 z-10">
                <h2 className="text-xl font-bold text-slate-900 tracking-tight">本地存储说明</h2>
                <p className="text-sm text-slate-500 mt-1.5 font-medium">了解本工具如何在本地存储和管理您的数据。</p>
              </div>

              <div className="flex-1 overflow-y-auto p-8 pt-6">
                <div className="space-y-8 max-w-2xl">
                  <div className="space-y-4">
                    <label className="block text-sm font-semibold text-slate-900">数据存储方式</label>
                    <div className="bg-slate-50 border border-slate-200 rounded-md p-4 text-sm text-slate-600 leading-relaxed">
                      本工具为纯本地桌面应用程序。所有项目数据、扫描规则和凭证切片均严格存储在您的本地磁盘设备上，<strong>不会</strong>上传至任何外部云端服务器，充分保障数据安全。
                    </div>
                  </div>

                  <Separator />

                  <div className="space-y-4">
                    <label className="block text-sm font-semibold text-slate-900">存储内容</label>
                    <div className="space-y-3">
                      <div className="flex items-start gap-3 bg-slate-50 border border-slate-200 rounded-md p-4">
                        <div className="flex-none w-8 h-8 bg-blue-100 text-blue-600 rounded-md flex items-center justify-center text-sm font-bold">DB</div>
                        <div>
                          <p className="text-sm font-medium text-slate-900">项目数据库</p>
                          <p className="text-xs text-slate-500 mt-0.5">每个项目独立的 SQLite 数据库文件，包含导入记录、标准化结果、归组信息、比价数据等。</p>
                        </div>
                      </div>
                      <div className="flex items-start gap-3 bg-slate-50 border border-slate-200 rounded-md p-4">
                        <div className="flex-none w-8 h-8 bg-emerald-100 text-emerald-600 rounded-md flex items-center justify-center text-sm font-bold">R</div>
                        <div>
                          <p className="text-sm font-medium text-slate-900">扫描规则</p>
                          <p className="text-xs text-slate-500 mt-0.5">用户自定义的字段映射规则、品牌别名表等配置，以 JSON 文件形式存储。</p>
                        </div>
                      </div>
                      <div className="flex items-start gap-3 bg-slate-50 border border-slate-200 rounded-md p-4">
                        <div className="flex-none w-8 h-8 bg-amber-100 text-amber-600 rounded-md flex items-center justify-center text-sm font-bold">F</div>
                        <div>
                          <p className="text-sm font-medium text-slate-900">上传文件</p>
                          <p className="text-xs text-slate-500 mt-0.5">用户上传的供应商报价文件（PDF、Excel、Word），存储在项目目录中。</p>
                        </div>
                      </div>
                    </div>
                  </div>

                  <Separator />

                  <div className="space-y-4">
                    <label className="block text-sm font-semibold text-slate-900">隐私承诺</label>
                    <ul className="space-y-2 text-sm text-slate-600">
                      <li className="flex items-center gap-2">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-emerald-500 flex-none"><path d="M20 6 9 17l-5-5"/></svg>
                        所有数据仅存储在本地磁盘，不上传至任何云端
                      </li>
                      <li className="flex items-center gap-2">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-emerald-500 flex-none"><path d="M20 6 9 17l-5-5"/></svg>
                        应用不包含任何遥测或数据采集功能
                      </li>
                      <li className="flex items-center gap-2">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-emerald-500 flex-none"><path d="M20 6 9 17l-5-5"/></svg>
                        后端服务仅绑定本机地址 (127.0.0.1)，不对外暴露
                      </li>
                      <li className="flex items-center gap-2">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-emerald-500 flex-none"><path d="M20 6 9 17l-5-5"/></svg>
                        删除项目即彻底清除对应的所有本地数据
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
            </>
          )}
        </Card>
      </div>
    </div>
  );
}

export default AppPreferences;
