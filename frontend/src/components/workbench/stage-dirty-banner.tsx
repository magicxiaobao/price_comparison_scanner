import { Card } from "../ui/card";
import { Button } from "../ui/button";

interface StageDirtyBannerProps {
  stageName: string;
  dirtyReason?: string;
  onRecalculate?: () => void;
}

export function StageDirtyBanner({
  stageName,
  dirtyReason,
  onRecalculate,
}: StageDirtyBannerProps) {
  return (
    <Card className="rounded-md bg-orange-50/50 p-4 border-orange-200 mb-4 shadow-sm">
      <div className="flex items-center">
        <div className="flex-shrink-0">
          <span className="text-orange-500 text-lg">⚠</span>
        </div>
        <div className="ml-3 flex-1 flex items-center justify-between">
          <p className="text-sm text-orange-800">
            <strong>上游数据已变更。</strong> 当前 {stageName} 结果可能已失效，建议重新计算。
            {dirtyReason && <span className="block mt-1 text-orange-700 text-xs">{dirtyReason}</span>}
          </p>
          {onRecalculate && (
            <Button
              variant="outline"
              size="sm"
              onClick={onRecalculate}
              className="ml-6 text-orange-700 bg-orange-50 border-orange-300 hover:bg-orange-100 hover:text-orange-800"
            >
              重新计算
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
