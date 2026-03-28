import { Card } from "../ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../ui/table";
import { ScrollArea } from "../ui/scroll-area";
import { Badge } from "../ui/badge";
import type { ComplianceMatrix as ComplianceMatrixType, ComplianceMatrixCell } from "../../types/compliance";
import { STATUS_STYLES } from "../../types/compliance";

interface ComplianceMatrixProps {
  matrix: ComplianceMatrixType;
  selectedMatchId: string | null;
  onSelectMatch: (matchId: string | null) => void;
}

function CellBadge({ cell }: { cell: ComplianceMatrixCell }) {
  const style = STATUS_STYLES[cell.status];
  return (
    <div className="relative inline-flex items-center gap-1">
      <span
        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${style.bg} ${style.text} ${style.border}`}
      >
        {style.label}
      </span>
      {cell.needsReview && (
        <span className="absolute -top-1 -right-1 h-2 w-2 bg-orange-400 rounded-full animate-pulse" />
      )}
      {cell.status === "partial" && cell.isAcceptable && (
        <span className="text-[10px] text-green-600 font-medium">OK</span>
      )}
    </div>
  );
}

export function ComplianceMatrix({ matrix, selectedMatchId, onSelectMatch }: ComplianceMatrixProps) {
  const supplierIds = Object.keys(matrix.supplierNames);

  if (matrix.rows.length === 0) {
    return (
      <div className="flex items-center justify-center h-[200px] text-sm text-slate-400">
        暂无符合性匹配数据，请先执行匹配
      </div>
    );
  }

  return (
    <Card className="overflow-hidden border-slate-200">
      <ScrollArea className="max-h-[500px]">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader className="bg-slate-50 sticky top-0 z-10">
              <TableRow className="hover:bg-slate-50">
                <TableHead className="w-[50px] text-center sticky left-0 bg-slate-50 z-20">#</TableHead>
                <TableHead className="w-[200px] sticky left-[50px] bg-slate-50 z-20 font-semibold">需求项</TableHead>
                <TableHead className="w-[60px] text-center font-semibold">必选</TableHead>
                {supplierIds.map((sid) => (
                  <TableHead key={sid} className="min-w-[120px] text-center font-semibold">
                    {matrix.supplierNames[sid]}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {matrix.rows.map((row, idx) => (
                <TableRow key={row.requirement.id} className="hover:bg-slate-50/50">
                  <TableCell className="text-center text-xs text-slate-400 sticky left-0 bg-white">
                    {row.requirement.code || idx + 1}
                  </TableCell>
                  <TableCell className="sticky left-[50px] bg-white">
                    <div className="max-w-[200px]">
                      <p className="text-sm font-medium text-slate-800 truncate">{row.requirement.title}</p>
                      <p className="text-[11px] text-slate-400">{row.requirement.category}</p>
                    </div>
                  </TableCell>
                  <TableCell className="text-center">
                    {row.requirement.isMandatory ? (
                      <Badge variant="default" className="text-[10px] h-5 px-1.5">必选</Badge>
                    ) : (
                      <Badge variant="outline" className="text-[10px] h-5 px-1.5 text-slate-400">可选</Badge>
                    )}
                  </TableCell>
                  {supplierIds.map((sid) => {
                    const cell = row.suppliers[sid];
                    if (!cell) {
                      return (
                        <TableCell key={sid} className="text-center">
                          <span className="text-xs text-slate-300">-</span>
                        </TableCell>
                      );
                    }
                    const isSelected = selectedMatchId === cell.matchId;
                    return (
                      <TableCell
                        key={sid}
                        className={`text-center cursor-pointer transition-colors ${
                          isSelected ? "ring-2 ring-blue-400 ring-inset bg-blue-50/50" : "hover:bg-slate-50"
                        }`}
                        onClick={() => onSelectMatch(isSelected ? null : cell.matchId)}
                      >
                        <CellBadge cell={cell} />
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </ScrollArea>
    </Card>
  );
}
