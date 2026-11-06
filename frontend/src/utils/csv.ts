export type CsvCell = string | number | boolean | null | undefined;

export function buildCsv(rows: readonly (readonly CsvCell[])[]): string {
  return rows.map(row => row.map(cell => {
    let text = cell == null ? "" : String(cell);
    // Quoting alone does not prevent spreadsheet formulas from untrusted metadata.
    if (typeof cell === "string" && /^[\s\p{Cc}]*[=+\-@]/u.test(text)) text = `'${text}`;
    return /[",\r\n]/u.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
  }).join(",")).join("\n");
}

export function downloadCsv(filename: string, rows: readonly (readonly CsvCell[])[]): void {
  const url = URL.createObjectURL(new Blob([buildCsv(rows)], { type: "text/csv;charset=utf-8;" }));
  try {
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
  } finally {
    URL.revokeObjectURL(url);
  }
}
