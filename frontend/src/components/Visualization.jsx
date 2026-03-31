import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Label,
} from "recharts";

const COLORS = ["#2563eb", "#059669", "#d97706", "#dc2626", "#7c3aed", "#0891b2"];

function humanize(str) {
  if (!str) return "";
  return str.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatNumber(value) {
  if (typeof value !== "number" || isNaN(value)) return value;
  if (Math.abs(value) >= 1000) return value.toLocaleString(undefined, { maximumFractionDigits: 1 });
  if (Number.isInteger(value)) return value.toString();
  return value.toFixed(2);
}

function formatTick(value) {
  if (typeof value === "number") {
    if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
    if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
    return Number.isInteger(value) ? value : value.toFixed(1);
  }
  if (typeof value === "string" && value.length > 14) return value.slice(0, 12) + "...";
  return value;
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div style={{
      background: "#ffffff",
      border: "1px solid #e2e8f0",
      borderRadius: 10,
      padding: "10px 14px",
      boxShadow: "0 4px 16px rgba(0,0,0,0.1)",
    }}>
      <p style={{ color: "#1e293b", fontWeight: 700, marginBottom: 6, fontSize: 13 }}>
        {label}
      </p>
      {payload.map((entry, i) => (
        <p key={i} style={{ color: entry.color, fontSize: 12, margin: "3px 0" }}>
          {humanize(entry.dataKey)}: <strong>{formatNumber(entry.value)}</strong>
        </p>
      ))}
    </div>
  );
}

export default function Visualization({ config, data }) {
  if (!config || !data || !data.columns || !data.rows || data.rows.length === 0) {
    return null;
  }

  const { chart_type, x_axis, y_axis, title, x_label, y_label } = config;

  const xIdx = data.columns.indexOf(x_axis);
  const chartData = data.rows.map((row) => {
    const point = { [x_axis]: row[xIdx] };
    if (Array.isArray(y_axis)) {
      y_axis.forEach((yCol) => {
        const yIdx = data.columns.indexOf(yCol);
        point[yCol] = yIdx >= 0 ? Number(row[yIdx]) : 0;
      });
    } else {
      const yIdx = data.columns.indexOf(y_axis);
      point[y_axis] = yIdx >= 0 ? Number(row[yIdx]) : 0;
    }
    return point;
  });

  const xAxisLabel = x_label || humanize(x_axis);
  const yAxisLabel = y_label || (Array.isArray(y_axis) ? y_axis.map(humanize).join(" / ") : humanize(y_axis));

  const legendFormatter = (value) => humanize(value);

  const margin = { top: 10, right: 30, left: 20, bottom: 40 };

  const commonXAxis = (
    <XAxis
      dataKey={x_axis}
      stroke="#94a3b8"
      tick={{ fill: "#64748b", fontSize: 11 }}
      tickFormatter={formatTick}
      interval={chartData.length > 10 ? Math.floor(chartData.length / 8) : 0}
      angle={chartData.length > 6 ? -25 : 0}
      textAnchor={chartData.length > 6 ? "end" : "middle"}
      height={50}
      tickLine={false}
      axisLine={{ stroke: "#e2e8f0" }}
    >
      <Label value={xAxisLabel} position="bottom" offset={0} style={{ fill: "#475569", fontSize: 12, fontWeight: 600 }} />
    </XAxis>
  );

  const commonYAxis = (
    <YAxis
      stroke="#94a3b8"
      tick={{ fill: "#64748b", fontSize: 11 }}
      tickFormatter={formatTick}
      width={65}
      tickLine={false}
      axisLine={{ stroke: "#e2e8f0" }}
    >
      <Label value={yAxisLabel} angle={-90} position="insideLeft" offset={-5} style={{ fill: "#475569", fontSize: 12, fontWeight: 600, textAnchor: "middle" }} />
    </YAxis>
  );

  const yColumns = Array.isArray(y_axis) ? y_axis : [y_axis];

  return (
    <div className="visualization-container">
      {title && <h3 className="viz-title">{title}</h3>}
      <ResponsiveContainer width="100%" height={380}>
        {chart_type === "line" ? (
          <LineChart data={chartData} margin={margin}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            {commonXAxis}
            {commonYAxis}
            <Tooltip content={<CustomTooltip />} />
            <Legend formatter={legendFormatter} wrapperStyle={{ paddingTop: 8, fontSize: 12 }} />
            {yColumns.map((yCol, i) => (
              <Line
                key={yCol}
                type="monotone"
                dataKey={yCol}
                stroke={COLORS[i % COLORS.length]}
                strokeWidth={2.5}
                dot={{ r: 4, fill: COLORS[i % COLORS.length], strokeWidth: 2, stroke: "#fff" }}
                activeDot={{ r: 6, strokeWidth: 2, stroke: "#fff" }}
              />
            ))}
          </LineChart>
        ) : (
          <BarChart data={chartData} margin={margin} barCategoryGap="20%">
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
            {commonXAxis}
            {commonYAxis}
            <Tooltip content={<CustomTooltip />} />
            <Legend formatter={legendFormatter} wrapperStyle={{ paddingTop: 8, fontSize: 12 }} />
            {yColumns.map((yCol, i) => (
              <Bar
                key={yCol}
                dataKey={yCol}
                fill={COLORS[i % COLORS.length]}
                radius={[6, 6, 0, 0]}
                maxBarSize={60}
              />
            ))}
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
