// 底部时间控制条 + 玩家动作输入
// 对应 spec：Auto 模式（自动 tick）/ Jump 模式（时间跨越）/ ActionRow（玩家行动）
import { useState } from 'react';
import { useGameStore, AUTO_SPEED_PRESETS, TIME_JUMP_PRESETS, AutoSpeed } from '../store/gameStore';
import { worldApi } from '../api/client';

const SPEED_KEYS: AutoSpeed[] = ['10s', '1m', '5m', '30m', '1h', '4h', '1d'];
const JUMP_KEYS = ['3d', '7d', '30d', '100d', '1y', '3y', '10y', '100y', '1000y'];

const QUICK_ACTIONS = ['观察四周', '前往', '询问', '休息', '战斗', '搜查'];

export default function BottomBar() {
  const timeMode = useGameStore((s) => s.timeMode);
  const autoSpeed = useGameStore((s) => s.autoSpeed);
  const isProcessing = useGameStore((s) => s.isProcessing);
  const meta = useGameStore((s) => s.meta);
  const setTimeMode = useGameStore((s) => s.setTimeMode);
  const setAutoSpeed = useGameStore((s) => s.setAutoSpeed);
  const startAutoTick = useGameStore((s) => s.startAutoTick);
  const stopAutoTick = useGameStore((s) => s.stopAutoTick);
  const runTickOnce = useGameStore((s) => s.runTickOnce);
  const runTimeJump = useGameStore((s) => s.runTimeJump);
  const setNotification = useGameStore((s) => s.setNotification);
  const setError = useGameStore((s) => s.setError);

  const [actionText, setActionText] = useState('');

  const handleAutoToggle = () => {
    if (timeMode === 'auto') {
      stopAutoTick();
      setTimeMode('paused');
    } else {
      startAutoTick();
    }
  };

  const handleTick = () => {
    runTickOnce(60);
  };

  const handleJump = (key: string) => {
    const preset = TIME_JUMP_PRESETS[key];
    if (!preset) return;
    if (!confirm(`${preset.confirm}？时间跨越会跳过中间过程并生成摘要。`)) return;
    runTimeJump(preset.seconds);
  };

  const submitAction = async () => {
    const text = actionText.trim();
    if (!text) return;
    try {
      // 玩家行动作为一条 player_action 事件写入客观层
      await worldApi.createEvent({
        tick_num: meta?.tick_num ?? 0,
        game_time: meta?.game_time ?? '',
        event_type: 'player_action',
        content_raw: text,
        importance: 3,
      });
      setActionText('');
      setNotification('玩家行动已记录，正在推进 LLM 管线…');
      // 推进一个 tick，触发 agent 管线（NPC 决策 / 世界反应 / 事件润色）
      await runTickOnce(60);
    } catch (e) {
      setError(`提交行动失败：${(e as Error).message}`);
    }
  };

  return (
    <div className="bottom-bar">
      <div className="time-control-bar">
        <span className="bar-label">时间控制</span>

        <div className="mode-toggle">
          <button
            className={`mode-btn ${timeMode === 'auto' ? 'active' : ''}`}
            onClick={handleAutoToggle}
            disabled={isProcessing}
            title="自动按间隔推进 tick"
          >
            ▶ 自动
          </button>
          <button
            className={`mode-btn ${timeMode === 'paused' ? 'active' : ''}`}
            onClick={() => { stopAutoTick(); setTimeMode('paused'); }}
            disabled={isProcessing}
            title="暂停自动推进"
          >
            ⏸ 暂停
          </button>
        </div>

        <button
          className="mode-btn tick-btn"
          onClick={handleTick}
          disabled={isProcessing}
          title="手动推进一个 tick（60 秒）"
        >
          {isProcessing ? <span className="spinner" /> : '⏭ 下一 Tick'}
        </button>

        {timeMode === 'auto' && (
          <div className="speed-btn-group">
            {SPEED_KEYS.map((k) => (
              <button
                key={k}
                className={`speed-btn ${autoSpeed === k ? 'active' : ''}`}
                onClick={() => setAutoSpeed(k)}
                title={AUTO_SPEED_PRESETS[k].label}
              >
                {k}
              </button>
            ))}
          </div>
        )}

        <span className="bar-divider" />

        <span className="bar-label">时间跨越</span>
        <div className="jump-btn-group">
          {JUMP_KEYS.map((k) => (
            <button
              key={k}
              className="jump-btn"
              onClick={() => handleJump(k)}
              disabled={isProcessing}
              title={TIME_JUMP_PRESETS[k].confirm}
            >
              {TIME_JUMP_PRESETS[k].label}
            </button>
          ))}
        </div>
      </div>

      <div className="action-row">
        <textarea
          className="action-input"
          placeholder="输入玩家行动（如：前往酒馆 / 询问守卫 / 攻击哥布林）…"
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
        <div className="quick-actions">
          {QUICK_ACTIONS.map((q) => (
            <span
              key={q}
              className="quick-action-chip"
              onClick={() => setActionText((t) => (t ? `${t} ${q}` : q))}
            >
              {q}
            </span>
          ))}
        </div>
        <button className="submit-btn" onClick={submitAction} disabled={isProcessing || !actionText.trim()}>
          提交行动
        </button>
      </div>
    </div>
  );
}