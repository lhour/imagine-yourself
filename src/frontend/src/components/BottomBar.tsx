// 底部时间控制条
//   第 1 行：快速推进预设（10秒/1分/5分/10分/30分/1小时）
//   第 2 行：自定义跨度（年/月/日/时/分/秒）
//   第 3 行：瞬间动作输入 + 发送
import { useState } from 'react';
import { useGameStore } from '../store/gameStore';

const FAST_PRESETS = [
  { label: '10秒', seconds: 10 },
  { label: '1分', seconds: 60 },
  { label: '5分', seconds: 300 },
  { label: '10分', seconds: 600 },
  { label: '30分', seconds: 1800 },
  { label: '1小时', seconds: 3600 },
];

const SPAN_FIELDS: { key: 'y' | 'mo' | 'd' | 'h' | 'mi' | 's'; label: string; unit: number }[] = [
  { key: 'y', label: '年', unit: 365 * 86400 },
  { key: 'mo', label: '月', unit: 30 * 86400 },
  { key: 'd', label: '日', unit: 86400 },
  { key: 'h', label: '时', unit: 3600 },
  { key: 'mi', label: '分', unit: 60 },
  { key: 's', label: '秒', unit: 1 },
];

export default function BottomBar() {
  const isProcessing = useGameStore((s) => s.isProcessing);
  const runAdvance = useGameStore((s) => s.runAdvance);
  const setError = useGameStore((s) => s.setError);
  const maxActors = useGameStore((s) => s.maxActors);
  const setMaxActors = useGameStore((s) => s.setMaxActors);

  // 自定义跨度
  const [span, setSpan] = useState<Record<string, number>>({ y: 0, mo: 0, d: 0, h: 0, mi: 0, s: 0 });
  // 瞬间动作
  const [actionText, setActionText] = useState('');

  const spanSeconds = SPAN_FIELDS.reduce((acc, f) => acc + (span[f.key] || 0) * f.unit, 0);

  const doAdvance = (seconds: number) => {
    if (seconds <= 0) {
      setError('推进秒数必须大于 0');
      return;
    }
    runAdvance(seconds);
  };

  const submitAction = () => {
    const text = actionText.trim();
    if (!text) return;
    // 由模型判断动作的最短执行时长作为推进跨度
    runAdvance(0, { player_action: text });
    setActionText('');
  };

  return (
    <div className="bottom-bar">
      {/* 第 1 行：快速推进 */}
      <div className="ctl-row">
        <span className="bar-label">推进</span>
        <div className="unit-group">
          {FAST_PRESETS.map((p) => (
            <button
              key={p.label}
              className="unit-btn"
              disabled={isProcessing}
              onClick={() => doAdvance(p.seconds)}
            >
              {p.label}
            </button>
          ))}
        </div>
        {/* E4: 本 tick 关注角色数滑杆 */}
        <div className="max-actors-slider" title="本 tick 参与决策的角色数量（max_actors）">
          <span className="bar-label">角色</span>
          <input
            type="range"
            min={1}
            max={12}
            step={1}
            value={maxActors}
            onChange={(e) => setMaxActors(Number(e.target.value))}
            disabled={isProcessing}
          />
          <span className="max-actors-value">{maxActors}</span>
        </div>
      </div>

      {/* 第 2 行：自定义跨度 */}
      <div className="ctl-row">
        <span className="bar-label">跨度</span>
        <div className="span-fields">
          {SPAN_FIELDS.map((f) => (
            <label key={f.key} className="span-field">
              <input
                type="number"
                min={0}
                value={span[f.key] ?? 0}
                onChange={(e) => setSpan({ ...span, [f.key]: Math.max(0, Number(e.target.value) || 0) })}
                disabled={isProcessing}
              />
              <span>{f.label}</span>
            </label>
          ))}
        </div>
        <button
          className="submit-btn"
          disabled={isProcessing || spanSeconds <= 0}
          onClick={() => doAdvance(spanSeconds)}
        >
          推进 {spanSeconds} 秒
        </button>
      </div>

      {/* 第 3 行：瞬间动作 */}
      <div className="ctl-row">
        <span className="bar-label">动作</span>
        <input
          className="action-input"
          placeholder="输入瞬间动作（由模型判断执行时长并推演）…"
          value={actionText}
          onChange={(e) => setActionText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
              e.preventDefault();
              submitAction();
            }
          }}
          disabled={isProcessing}
        />
        <button className="submit-btn" onClick={submitAction} disabled={isProcessing || !actionText.trim()}>
          {isProcessing ? <span className="spinner" /> : '发送'}
        </button>
      </div>
    </div>
  );
}