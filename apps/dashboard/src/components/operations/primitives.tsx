"use client";

import { useEffect, useRef, useState } from "react";
import {
  Search,
  ChevronLeft,
  ChevronRight,
  ArrowUpDown,
  X,
  Inbox,
  AlertTriangle,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export function Badge({ value }: { value: string | undefined }) {
  const text = value ?? "Unknown";
  const kind =
    /succeed|healthy|ready|running|delivered|resolved|connected/i.test(text) &&
    !/unhealthy|not.?ready/i.test(text)
      ? "success"
      : /fail|critical|rejected|crash|error|hold/i.test(text)
        ? "danger"
        : /await|warning|pending|unavailable|stale|dry|rollback|rolledback/i.test(
              text,
            )
          ? "warning"
          : "neutral";
  return (
    <span className={`badge ${kind}`}>
      <span className="badge-dot" />
      {text.replaceAll(/([a-z])([A-Z])/g, "$1 $2")}
    </span>
  );
}
export function Empty({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="empty-state">
      <Inbox size={28} aria-hidden="true" />
      <h3>{title}</h3>
      <p>{detail}</p>
    </div>
  );
}
export function ErrorState({
  message,
  retry,
}: {
  message: string;
  retry?: () => void;
}) {
  return (
    <div className="notice error" role="alert">
      <AlertTriangle size={18} aria-hidden="true" />
      <div>
        <strong>Unable to load this view</strong>
        <p>{message}</p>
        {retry && (
          <Button variant="outline" onClick={retry}>
            Try again
          </Button>
        )}
      </div>
    </div>
  );
}
export function Skeleton() {
  return (
    <div
      role="status"
      aria-label="Loading operations data"
      className="loading-grid"
    >
      {Array.from({ length: 6 }, (_, i) => (
        <div className="glass skeleton" key={i} />
      ))}
    </div>
  );
}
export function Dialog({
  title,
  children,
  close,
}: {
  title: string;
  children: React.ReactNode;
  close: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
    const dialog = ref.current;
    return () => dialog?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className="ops-dialog"
      aria-label={title}
      onCancel={(e) => {
        e.preventDefault();
        close();
      }}
    >
      <div className="dialog-heading">
        <h2>{title}</h2>
        <button
          aria-label="Close dialog"
          className="icon-button"
          onClick={close}
        >
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}

export function DataTable<T>({
  rows,
  columns,
  keyFor,
  empty = "No records found",
  dense = false,
}: {
  rows: T[];
  columns: {
    key: string;
    title: string;
    text: (r: T) => string;
    cell?: (r: T) => React.ReactNode;
  }[];
  keyFor: (r: T) => string;
  empty?: string;
  dense?: boolean;
}) {
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState(columns[0]?.key ?? "");
  const [descending, setDescending] = useState(false);
  const [page, setPage] = useState(0);
  const active = columns.find((c) => c.key === sort) ?? columns[0];
  const visible = rows
    .filter((row) =>
      columns.some((c) =>
        c.text(row).toLowerCase().includes(search.toLowerCase()),
      ),
    )
    .sort(
      (a, b) =>
        active
          .text(a)
          .localeCompare(active.text(b), undefined, { numeric: true }) *
        (descending ? -1 : 1),
    );
  const current = Math.min(
    page,
    Math.max(0, Math.ceil(visible.length / 10) - 1),
  );
  return (
    <div className={`data-table ${dense ? "dense" : ""}`}>
      <div className="table-toolbar">
        <label className="search-field">
          <Search size={16} aria-hidden="true" />
          <span className="sr-only">Search table</span>
          <input
            placeholder="Search records…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
          />
        </label>
        <span className="tiny-label">{visible.length} records</span>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {columns.map((c) => (
                <th
                  key={c.key}
                  aria-sort={
                    c.key === sort
                      ? descending
                        ? "descending"
                        : "ascending"
                      : "none"
                  }
                >
                  <button
                    onClick={() => {
                      setSort(c.key);
                      setDescending(c.key === sort ? !descending : false);
                      setPage(0);
                    }}
                  >
                    {c.title}
                    <ArrowUpDown size={12} aria-hidden="true" />
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.slice(current * 10, current * 10 + 10).map((row) => (
              <tr key={keyFor(row)}>
                {columns.map((c) => (
                  <td key={c.key}>{c.cell ? c.cell(row) : c.text(row)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!visible.length && (
        <Empty
          title={empty}
          detail="Adjust the search or namespace filter, or connect the relevant data source."
        />
      )}
      <div className="pagination">
        <span>
          {visible.length ? current * 10 + 1 : 0}–
          {Math.min((current + 1) * 10, visible.length)} of {visible.length}
        </span>
        <div>
          <button
            className="icon-button"
            aria-label="Previous page"
            disabled={current === 0}
            onClick={() => setPage(current - 1)}
          >
            <ChevronLeft size={16} />
          </button>
          <span>Page {current + 1}</span>
          <button
            className="icon-button"
            aria-label="Next page"
            disabled={(current + 1) * 10 >= visible.length}
            onClick={() => setPage(current + 1)}
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
