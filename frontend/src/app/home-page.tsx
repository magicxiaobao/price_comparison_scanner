function HomePage() {
  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <h1 className="text-2xl font-bold mb-6">三方比价支出依据扫描工具</h1>
      <div className="flex gap-4 mb-8">
        <button className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
          + 新建项目
        </button>
        <a href="#/rules" className="px-4 py-2 border rounded hover:bg-gray-100">
          规则管理
        </a>
      </div>
      <h2 className="text-lg font-semibold mb-4">最近项目</h2>
      <p className="text-gray-500">暂无项目</p>
    </div>
  );
}

export default HomePage;
