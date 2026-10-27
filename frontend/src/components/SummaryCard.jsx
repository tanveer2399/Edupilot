import Icon from "./Icon.jsx";

export default function SummaryCard({
  icon,
  label,
  value,
  detail,
  accent,
  progress,
}) {
  return (
    <article className="summary-card">
      <div className="summary-card-top">
        <span className={`summary-icon ${accent}`}>
          <Icon name={icon} size={20} />
        </span>
        <span className="summary-period">This semester</span>
      </div>
      <p className="summary-label">{label}</p>
      <div className="summary-value-row">
        <strong className="summary-value">{value}</strong>
        {progress !== undefined && progress !== null && (
          <span className="summary-progress">{progress}</span>
        )}
      </div>
      <p className="summary-detail">{detail}</p>
      {progress !== undefined && progress !== null && (
        <div
          className="progress-track"
          role="progressbar"
          aria-label={label}
          aria-valuenow={progress}
          aria-valuemin="0"
          aria-valuemax="100"
        >
          <span style={{ width: `${Math.min(progress, 100)}%` }} />
        </div>
      )}
    </article>
  );
}
