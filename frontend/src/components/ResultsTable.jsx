import { useState } from "react";

export default function ResultsTable({ columns, rows }) {
  const [sortCol, setSortCol] = useState(null);
  const [sortAsc, setSortAsc] = useState(true);

  if (!columns || !rows || rows.length === 0) {
    return null;
  }

  const handleSort = (colIndex) => {
    if (sortCol === colIndex) {
      setSortAsc(!sortAsc);
    } else {
      setSortCol(colIndex);
      setSortAsc(true);
    }
  };

  const sortedRows = [...rows];
  if (sortCol !== null) {
    sortedRows.sort((a, b) => {
      const valA = a[sortCol];
      const valB = b[sortCol];
      if (typeof valA === "number" && typeof valB === "number") {
        return sortAsc ? valA - valB : valB - valA;
      }
      const strA = String(valA);
      const strB = String(valB);
      return sortAsc ? strA.localeCompare(strB) : strB.localeCompare(strA);
    });
  }

  return (
    <div className="results-table-container">
      <table className="results-table">
        <thead>
          <tr>
            {columns.map((col, i) => (
              <th key={i} onClick={() => handleSort(i)} style={{ cursor: "pointer" }}>
                {col}
                {sortCol === i ? (sortAsc ? " ▲" : " ▼") : ""}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortedRows.map((row, rowIdx) => (
            <tr key={rowIdx}>
              {row.map((cell, cellIdx) => (
                <td key={cellIdx}>
                  {typeof cell === "number"
                    ? Number.isInteger(cell)
                      ? cell.toLocaleString()
                      : cell.toFixed(2)
                    : cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="table-info">{rows.length} row{rows.length !== 1 ? "s" : ""}</div>
    </div>
  );
}
