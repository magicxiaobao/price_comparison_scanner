import { useCallback, useEffect, useRef, useState } from "react";
import type { RuleTestResult } from "../../types/rule";
import { useRuleStore } from "../../stores/rule-store";

export function RuleTestPanel() {
  const { testRule } = useRuleStore();
  const [input, setInput] = useState("");
  const [result, setResult] = useState<RuleTestResult | null>(null);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const runTest = useCallback(
    async (columnName: string) => {
      if (!columnName.trim()) {
        setResult(null);
        return;
      }
      setTesting(true);
      setError(null);
      try {
        const res = await testRule(columnName.trim());
        setResult(res);
      } catch (e) {
        setError(e instanceof Error ? e.message : "测试失败");
      } finally {
        setTesting(false);
      }
    },
    [testRule],
  );

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (!input.trim()) {
      setResult(null);
      return;
    }
    timerRef.current = setTimeout(() => {
      runTest(input);
    }, 300);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [input, runTest]);

  return (
    <div className="flex h-full flex-col px-4 py-4">
      <h3 className="mb-3 text-sm font-semibold text-gray-900">规则测试</h3>
      <p className="mb-3 text-xs text-gray-500">输入列名测试匹配结果（300ms 防抖）</p>

      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="如：报价含税"
        className="mb-4 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      />

      {testing && <p className="text-xs text-gray-500">测试中...</p>}

      {error && <p className="text-xs text-red-600">{error}</p>}

      {result && !testing && (
        <div className="rounded-md border border-gray-200 bg-gray-50 p-3">
          {result.matched ? (
            <>
              <p className="text-sm font-medium text-green-700">
                匹配成功 &rarr; {result.targetField}
              </p>
              {result.matchedRule && (
                <p className="mt-1 text-xs text-gray-600">
                  命中规则: {JSON.stringify(result.matchedRule)}
                </p>
              )}
              {result.conflicts.length > 0 && (
                <div className="mt-2">
                  <p className="text-xs font-medium text-amber-700">
                    冲突规则 ({result.conflicts.length}):
                  </p>
                  <ul className="mt-1 space-y-1">
                    {result.conflicts.map((c, i) => (
                      <li key={i} className="text-xs text-gray-600">
                        {JSON.stringify(c)}
                      </li>
                    ))}
                  </ul>
                  {result.resolution && (
                    <p className="mt-1 text-xs text-gray-500">裁决: {result.resolution}</p>
                  )}
                </div>
              )}
            </>
          ) : (
            <p className="text-sm text-gray-500">未匹配任何规则</p>
          )}
        </div>
      )}
    </div>
  );
}
