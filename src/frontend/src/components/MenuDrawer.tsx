// 菜单栏抽屉（右上角弹出）— 对应 spec 5.6
// 菜单项：角色 / 群体 / 地图 / 物品 / 设定 / 记忆宫殿 / 管理员模式
import { useGameStore } from '../store/gameStore';
import { RightPanelTab } from '../store/gameStore';

interface MenuItem {
  icon: string;
  label: string;
  desc: string;
  action: () => void;
}

export default function MenuDrawer({ onClose }: { onClose: () => void }) {
  const setRightTab = useGameStore((s) => s.setRightTab);
  const openMapBrowser = useGameStore((s) => s.openMapBrowser);
  const maps = useGameStore((s) => s.maps);

  const goTab = (tab: RightPanelTab) => {
    setRightTab(tab);
    onClose();
  };

  const openMap = () => {
    // 默认打开第一张根地图（无 parent_map_id），否则第一张
    const root = maps.find((m) => m.parent_map_id == null) ?? maps[0] ?? null;
    openMapBrowser(root?.id ?? null);
    onClose();
  };

  const items: MenuItem[] = [
    { icon: '🧍', label: '角色', desc: '全部角色卡 · 属性/位置/任务', action: () => goTab('characters') },
    { icon: '👥', label: '群体', desc: '群体树 + 热力图预览', action: () => goTab('groups') },
    { icon: '🗺', label: '地图', desc: '地图浏览器（地形 + 热力图 + 测距）', action: openMap },
    { icon: '🎒', label: '物品', desc: '按类型/稀有度筛选', action: () => goTab('items') },
    { icon: '📜', label: '设定', desc: '世界/时代/文化/超自然', action: () => onClose() },
    { icon: '🧠', label: '记忆宫殿', desc: '主角视角记忆分层树', action: () => goTab('memory') },
    { icon: '⚙', label: '管理员模式', desc: '全局配置临时修改', action: () => onClose() },
  ];

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer-card" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <span>菜单</span>
          <button className="drawer-close" onClick={onClose}>✕</button>
        </div>
        <div className="drawer-list">
          {items.map((it) => (
            <button key={it.label} className="drawer-item" onClick={it.action}>
              <span className="drawer-icon">{it.icon}</span>
              <span className="drawer-text">
                <span className="drawer-label">{it.label}</span>
                <span className="drawer-desc">{it.desc}</span>
              </span>
              <span className="drawer-arrow">›</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
