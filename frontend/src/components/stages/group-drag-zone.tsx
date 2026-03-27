import React from 'react';
import { useDraggable, useDroppable } from '@dnd-kit/core';
import type { CommodityGroup, GroupMemberSummary } from '../../types/grouping';
import { cn } from '../../lib/utils';
import { Card } from '../ui/card';
import { TableRow, TableCell } from '../ui/table';

interface DroppableGroupCardProps {
  group: CommodityGroup;
  children: React.ReactNode;

  className?: string;
  onClick?: () => void;
}

export function DroppableGroupCard({ group, children, className, onClick }: DroppableGroupCardProps) {
  const isDroppable = group.status !== 'confirmed' && group.status !== 'not_comparable';
  const { isOver, setNodeRef } = useDroppable({
    id: group.id,
    data: { type: 'group', status: group.status, isDroppable },
    disabled: !isDroppable,
  });

  return (
    <Card
      ref={setNodeRef}
      onClick={onClick}
      className={cn(
        className,
        isOver && isDroppable ? 'border-blue-500 ring-2 ring-blue-500/30' : ''
      )}
    >
      {children}
    </Card>
  );
}

interface DraggableMemberRowProps {
  member: GroupMemberSummary;
  groupId: string;
  isDragDisabled: boolean;
  children: React.ReactNode;
  className?: string;
}

export function DraggableMemberRow({ member, groupId, isDragDisabled, children, className }: DraggableMemberRowProps) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: member.standardizedRowId,
    data: { type: 'member', member, sourceGroupId: groupId },
    disabled: isDragDisabled,
  });

  return (
    <TableRow
      ref={setNodeRef}
      className={cn(className, isDragging ? 'opacity-30 bg-slate-50' : '')}
    >
      <TableCell className="w-8 px-2 py-2 align-middle">
        <div
          {...listeners}
          {...attributes}
          className={cn(
            "flex items-center justify-center p-1 rounded hover:bg-slate-200 text-slate-400 cursor-grab active:cursor-grabbing",
            isDragDisabled ? "opacity-30 cursor-not-allowed hover:bg-transparent" : ""
          )}
          title={isDragDisabled ? "组内仅剩一项，不可拖出" : "拖拽移动该项"}
        >
          <svg width="15" height="15" viewBox="0 0 15 15" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M5.5 3C4.67157 3 4 3.67157 4 4.5C4 5.32843 4.67157 6 5.5 6C6.32843 6 7 5.32843 7 4.5C7 3.67157 6.32843 3 5.5 3ZM5.5 5C5.22386 5 5 4.77614 5 4.5C5 4.22386 5.22386 4 5.5 4C5.77614 4 6 4.22386 6 4.5C6 4.77614 5.77614 5 5.5 5ZM9.5 3C8.67157 3 8 3.67157 8 4.5C8 5.32843 8.67157 6 9.5 6C10.32843 6 11 5.32843 11 4.5C11 3.67157 10.32843 3 9.5 3ZM9.5 5C9.22386 5 9 4.77614 9 4.5C9 4.22386 9.22386 4 9.5 4C9.77614 4 10 4.22386 10 4.5C10 4.77614 9.77614 5 9.5 5ZM5.5 7.5C4.67157 7.5 4 8.17157 4 9C4 9.82843 4.67157 10.5 5.5 10.5C6.32843 10.5 7 9.82843 7 9C7 8.17157 6.32843 7.5 5.5 7.5ZM5.5 9.5C5.22386 9.5 5 9.27614 5 9C5 8.72386 5.22386 8.5 5.5 8.5C5.77614 8.5 6 8.72386 6 9C6 9.27614 5.77614 9.5 5.5 9.5ZM9.5 7.5C8.67157 7.5 8 8.17157 8 9C8 9.82843 8.67157 10.5 9.5 10.5C10.32843 10.5 11 9.82843 11 9C11 8.17157 10.32843 7.5 9.5 7.5ZM9.5 9.5C9.22386 9.5 9 9.27614 9 9C9 8.72386 9.22386 8.5 9.5 8.5C9.77614 8.5 10 8.72386 10 9C10 9.27614 9.77614 9.5 9.5 9.5ZM5.5 12C4.67157 12 4 12.6716 4 13.5C4 14.3284 4.67157 15 5.5 15C6.32843 15 7 14.3284 7 13.5C7 12.6716 6.32843 12 5.5 12ZM5.5 14C5.22386 14 5 13.7761 5 13.5C5 13.2239 5.22386 13 5.5 13C5.77614 13 6 13.2239 6 13.5C6 13.7761 5.77614 14 5.5 14ZM9.5 12C8.67157 12 8 12.6716 8 13.5C8 14.3284 8.67157 15 9.5 15C10.32843 15 11 14.3284 11 13.5C11 12.6716 10.32843 12 9.5 12ZM9.5 14C9.22386 14 9 13.7761 9 13.5C9 13.2239 9.22386 13 9.5 13C9.77614 13 10 13.2239 10 13.5C10 13.7761 9.77614 14 9.5 14Z" fill="currentColor" fillRule="evenodd" clipRule="evenodd"></path></svg>
        </div>
      </TableCell>
      {children}
    </TableRow>
  );
}
