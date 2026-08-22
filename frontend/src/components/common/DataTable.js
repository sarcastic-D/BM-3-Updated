import React from "react";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ChevronLeft, ChevronRight, ArrowUpDown, Inbox } from "lucide-react";

export const DataTable = ({
  columns, rows, loading, total = 0, page = 1, pageSize = 25, onPageChange,
  sortBy, sortDir, onSort, onRowClick, emptyText = "No results for current filters", testid = "data-table",
}) => {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="rounded-[var(--radius)] border border-border bg-card shadow-[0_1px_0_rgba(15,23,42,0.04)]">
      <div className="overflow-x-auto">
        <Table data-testid={testid}>
          <TableHeader>
            <TableRow className="bg-[hsl(var(--surface-2))] hover:bg-[hsl(var(--surface-2))]">
              {columns.map((c) => (
                <TableHead key={c.key} className={`h-10 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground ${c.className || ""}`}>
                  {c.sortable && onSort ? (
                    <button className="inline-flex items-center gap-1 hover:text-foreground" onClick={() => onSort(c.key)}>
                      {c.label} <ArrowUpDown className={`h-3 w-3 ${sortBy === c.key ? "text-[hsl(var(--primary))]" : ""}`} />
                    </button>
                  ) : c.label}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              Array.from({ length: 8 }).map((_, i) => (
                <TableRow key={i}>
                  {columns.map((c) => <TableCell key={c.key} className="py-2.5"><Skeleton className="h-4 w-full max-w-[160px]" /></TableCell>)}
                </TableRow>
              ))
            ) : rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={columns.length} className="py-16 text-center">
                  <div className="flex flex-col items-center gap-2 text-muted-foreground">
                    <Inbox className="h-8 w-8" />
                    <span className="text-[13px]">{emptyText}</span>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              rows.map((row, ri) => (
                <TableRow
                  key={row.id || ri}
                  data-testid={`${testid}-row`}
                  onClick={() => onRowClick && onRowClick(row)}
                  className={`transition-colors duration-150 ${onRowClick ? "cursor-pointer" : ""} hover:bg-[hsl(var(--accent)/0.35)]`}
                >
                  {columns.map((c) => (
                    <TableCell key={c.key} className={`py-2.5 text-[13px] ${c.cellClassName || ""}`}>
                      {c.render ? c.render(row) : row[c.key]}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
      {onPageChange && (
        <div className="flex items-center justify-between border-t border-border px-3 py-2.5">
          <span className="text-[12px] text-muted-foreground tabular-nums">
            {total === 0 ? "0" : `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)}`} of {total}
          </span>
          <div className="flex items-center gap-1.5">
            <span className="text-[12px] text-muted-foreground tabular-nums">Page {page} / {pages}</span>
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)} data-testid="table-prev-page"><ChevronLeft className="h-4 w-4" /></Button>
            <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => onPageChange(page + 1)} data-testid="table-next-page"><ChevronRight className="h-4 w-4" /></Button>
          </div>
        </div>
      )}
    </div>
  );
};
