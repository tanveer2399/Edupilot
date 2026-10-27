import Icon from "./Icon.jsx";

const navigation = [
  { label: "Dashboard", page: "Dashboard", icon: "dashboard" },
  { label: "Attendance", page: "Attendance", icon: "attendance" },
  { label: "Marks", page: "Marks", icon: "marks" },
  { label: "Assignments", page: "Assignments", icon: "assignments" },
  { label: "Timetable", page: "Timetable", icon: "planner" },
];

const studyTools = [
  { label: "Study Assistant", page: "Study Assistant", icon: "assistant" },
  { label: "Study Planner", page: "Study Planner", icon: "planner" },
];

function NavGroup({ items, activePage, onNavigate }) {
  return (
    <ul className="nav-list">
      {items.map((item) => {
        const isCurrent = item.label === activePage;
        const isEnabled = Boolean(item.page);
        return (
          <li key={item.label}>
            <button
              className={`nav-item${isCurrent ? " active" : ""}`}
              type="button"
              disabled={!isEnabled}
              onClick={() => isEnabled && onNavigate(item.page)}
              aria-current={isCurrent ? "page" : undefined}
              title={isEnabled ? undefined : "Coming in a future milestone"}
            >
              <Icon name={item.icon} size={19} />
              <span>{item.label}</span>
              {!isEnabled && <span className="nav-soon">Soon</span>}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export default function Sidebar({ activePage, onNavigate }) {
  return (
    <aside className="sidebar">
      <a className="brand" href="/" aria-label="EduPilot home">
        <span className="brand-mark">
          <Icon name="cap" size={22} />
        </span>
        <span>
          <strong>EduPilot</strong>
          <small>STUDENT PORTAL</small>
        </span>
      </a>

      <nav aria-label="Main navigation">
        <p className="nav-heading">MENU</p>
        <NavGroup
          items={navigation}
          activePage={activePage}
          onNavigate={onNavigate}
        />
        <p className="nav-heading study-heading">YOUR LEARNING</p>
        <NavGroup items={studyTools} activePage={activePage} onNavigate={onNavigate} />
      </nav>

      <div className="sidebar-help">
        <div className="help-icon">
          <Icon name="book" size={19} />
        </div>
        <strong>Keep your momentum</strong>
        <p>Small steps every day add up to big progress.</p>
        <span className="help-progress"><i /></span>
        <small>You're doing great!</small>
      </div>

      <div className="sidebar-footer">
        <span className="avatar avatar-small">EP</span>
        <span>
          <strong>Student portal</strong>
          <small>Academic year 2026–27</small>
        </span>
      </div>
    </aside>
  );
}
