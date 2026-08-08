import { Link, useLocation, useNavigate } from 'react-router-dom';

const NAV_ITEMS = [
  { path: '/', label: '首页', icon: '🏠' },
  { path: '/saves', label: '回忆', icon: '📂' },
  { path: '/dramas', label: '剧本', icon: '📜' },
  { path: '/knowledge', label: '知识库', icon: '📚' },
  { path: '/model', label: '模型', icon: '🤖' },
  { path: '/traces', label: '日志', icon: '📊' },
  { path: '/settings', label: '设置', icon: '⚙' },
];

export default function AdminNav() {
  const location = useLocation();
  const navigate = useNavigate();
  const current = location.pathname;

  return (
    <nav className="admin-nav">
      <div className="admin-nav-inner">
        <div className="admin-nav-brand" onClick={() => navigate('/')}>
          <span className="brand-icon">✦</span>
          <span className="brand-text">Aether Story Engine</span>
        </div>
        <ul className="admin-nav-list">
          {NAV_ITEMS.map((item) => {
            const active = current === item.path || (item.path !== '/' && current.startsWith(item.path));
            return (
              <li key={item.path} className={active ? 'active' : ''}>
                <Link to={item.path}>
                  <span className="nav-icon">{item.icon}</span>
                  <span className="nav-label">{item.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
    </nav>
  );
}
