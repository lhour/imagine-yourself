import React, { useEffect, useMemo, useState } from 'react';
import { CharacterQuest, CharacterAgenda, Character } from '../api/types';
import { entitiesApi } from '../api/client';
import '../styles/QuestAgendaPanel.css';

const QUEST_STATUS_COLOR: Record<string, string> = {
  open: '#3b82f6',
  in_progress: '#f59e0b',
  done: '#10b981',
  failed: '#ef4444',
  blocked: '#94a3b8',
};
const AGENDA_STATUS_COLOR: Record<string, string> = {
  active: '#10b981',
  blocked: '#f59e0b',
  completed: '#3b82f6',
  archived: '#94a3b8',
};

type Tab = 'quests' | 'agendas';

function NewQuestModal({
  chars,
  onClose,
  onCreated,
}: {
  chars: Character[];
  onClose: () => void;
  onCreated: () => void;
}) {
  const [form, setForm] = useState({
    char_id: chars[0]?.id ?? 0,
    title: '',
    desc_raw: '',
    quest_type: 'main',
    priority: 3,
    success_condition_raw: '',
    fail_condition_raw: '',
  });
  const [loading, setLoading] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title || !form.char_id) return;
    setLoading(true);
    try {
      await entitiesApi.create<CharacterQuest>('character_quest', {
        ...form,
        status: 'open',
        start_tick: 0,
      });
      onCreated();
      onClose();
    } finally {
      setLoading(false);
    }
  };
  return (
    <div className="modal-mask" onClick={onClose}>
      <div className="modal-body" onClick={(e) => e.stopPropagation()}>
        <h3>新建任务</h3>
        <form onSubmit={submit} className="modal-form">
          <label>
            <span>所属角色</span>
            <select
              value={form.char_id}
              onChange={(e) => setForm({ ...form, char_id: Number(e.target.value) })}
            >
              {chars.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </label>
          <label>
            <span>任务标题</span>
            <input
              required
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="例：夺回失落的圣物"
            />
          </label>
          <label>
            <span>类型</span>
            <select
              value={form.quest_type}
              onChange={(e) => setForm({ ...form, quest_type: e.target.value })}
            >
              <option value="main">主线</option>
              <option value="side">支线</option>
              <option value="character">角色</option>
              <option value="world">世界</option>
              <option value="daily">日常</option>
            </select>
          </label>
          <label>
            <span>优先级（1~5）</span>
            <input
              type="number"
              min={1} max={5}
              value={form.priority}
              onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })}
            />
          </label>
          <label>
            <span>任务描述（结构化）</span>
            <textarea
              rows={3}
              value={form.desc_raw}
              onChange={(e) => setForm({ ...form, desc_raw: e.target.value })}
              placeholder="事件链关键节点 + 触发条件"
            />
          </label>
          <div className="row-2">
            <label>
              <span>成功条件</span>
              <textarea
                rows={2}
                value={form.success_condition_raw}
                onChange={(e) => setForm({ ...form, success_condition_raw: e.target.value })}
              />
            </label>
            <label>
              <span>失败条件</span>
              <textarea
                rows={2}
                value={form.fail_condition_raw}
                onChange={(e) => setForm({ ...form, fail_condition_raw: e.target.value })}
              />
            </label>
          </div>
          <div className="modal-actions">
            <button type="button" onClick={onClose}>取消</button>
            <button type="submit" disabled={loading}>{loading ? '创建中…' : '创建任务'}</button>
          </div>
        </form>
      </div>
    </div>
  );
}

function NewAgendaModal({
  chars,
  onClose,
  onCreated,
}: {
  chars: Character[];
  onClose: () => void;
  onCreated: () => void;
}) {
  const [form, setForm] = useState({
    char_id: chars[0]?.id ?? 0,
    title: '',
    principle_raw: '',
    priority: 3,
  });
  const [loading, setLoading] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title || !form.principle_raw || !form.char_id) return;
    setLoading(true);
    try {
      await entitiesApi.create<CharacterAgenda>('character_agenda', {
        ...form,
        status: 'active',
        start_tick: 0,
      });
      onCreated();
      onClose();
    } finally {
      setLoading(false);
    }
  };
  return (
    <div className="modal-mask" onClick={onClose}>
      <div className="modal-body" onClick={(e) => e.stopPropagation()}>
        <h3>新建纲领</h3>
        <form onSubmit={submit} className="modal-form">
          <label>
            <span>所属角色</span>
            <select
              value={form.char_id}
              onChange={(e) => setForm({ ...form, char_id: Number(e.target.value) })}
            >
              {chars.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </label>
          <label>
            <span>纲领标题</span>
            <input
              required
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="例：绝不背叛家族"
            />
          </label>
          <label>
            <span>优先级（1~5）</span>
            <input
              type="number" min={1} max={5}
              value={form.priority}
              onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })}
            />
          </label>
          <label>
            <span>行为准则（结构化 raw）</span>
            <textarea
              rows={4}
              required
              value={form.principle_raw}
              onChange={(e) => setForm({ ...form, principle_raw: e.target.value })}
              placeholder="触发场景、代价、违背会发生什么、何时让位给其他纲领"
            />
          </label>
          <div className="modal-actions">
            <button type="button" onClick={onClose}>取消</button>
            <button type="submit" disabled={loading}>{loading ? '创建中…' : '创建纲领'}</button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function QuestAgendaPanel() {
  const [tab, setTab] = useState<Tab>('quests');
  const [quests, setQuests] = useState<CharacterQuest[]>([]);
  const [agendas, setAgendas] = useState<CharacterAgenda[]>([]);
  const [chars, setChars] = useState<Character[]>([]);
  const [showQuestModal, setShowQuestModal] = useState(false);
  const [showAgendaModal, setShowAgendaModal] = useState(false);
  const [filterChar, setFilterChar] = useState<number | 'all'>('all');

  const refresh = async () => {
    const [qs, ags, cs] = await Promise.all([
      entitiesApi.list<CharacterQuest>('character_quest'),
      entitiesApi.list<CharacterAgenda>('character_agenda'),
      entitiesApi.list<Character>('character'),
    ]);
    setQuests(Array.isArray(qs) ? qs : []);
    setAgendas(Array.isArray(ags) ? ags : []);
    setChars(Array.isArray(cs) ? cs : []);
  };

  useEffect(() => { void refresh(); }, []);

  const charMap = useMemo(() => {
    const m = new Map<number, Character>();
    chars.forEach((c) => m.set(c.id, c));
    return m;
  }, [chars]);

  const qs = useMemo(
    () => quests.filter((q) => filterChar === 'all' || q.char_id === filterChar),
    [quests, filterChar]
  );
  const ags = useMemo(
    () => agendas.filter((a) => filterChar === 'all' || a.char_id === filterChar),
    [agendas, filterChar]
  );

  return (
    <div className="qa-panel">
      <div className="qa-header">
        <div className="qa-tabs">
          <button
            className={tab === 'quests' ? 'qa-tab qa-tab-active' : 'qa-tab'}
            onClick={() => setTab('quests')}
          >任务 ({quests.length})</button>
          <button
            className={tab === 'agendas' ? 'qa-tab qa-tab-active' : 'qa-tab'}
            onClick={() => setTab('agendas')}
          >纲领 ({agendas.length})</button>
        </div>
        <select
          className="qa-filter"
          value={filterChar}
          onChange={(e) => setFilterChar(e.target.value === 'all' ? 'all' : Number(e.target.value))}
        >
          <option value="all">全部角色</option>
          {chars.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
        <div className="qa-newbtns">
          {tab === 'quests' ? (
            <button className="qa-new" onClick={() => setShowQuestModal(true)}>+ 新建任务</button>
          ) : (
            <button className="qa-new" onClick={() => setShowAgendaModal(true)}>+ 新建纲领</button>
          )}
        </div>
      </div>

      <div className="qa-list">
        {tab === 'quests' && qs.length === 0 && (
          <div className="qa-empty">暂无任务；点右上角"新建任务"开始规划。</div>
        )}
        {tab === 'quests' && qs.map((q) => (
          <div key={q.id} className={`qa-card qa-card-status-${q.status}`}>
            <div className="qa-card-top">
              <span
                className="qa-dot"
                style={{ background: QUEST_STATUS_COLOR[q.status] ?? '#aaa' }}
              />
              <span className="qa-ctype">{q.quest_type}</span>
              <span className="qa-title">{q.title}</span>
              <span className="qa-prio">P{q.priority}</span>
            </div>
            <div className="qa-card-meta">
              <span className="qa-char">{charMap.get(q.char_id)?.name ?? `#${q.char_id}`}</span>
              <span className="qa-status">{q.status}</span>
              <span className="qa-tick">tick {q.start_tick}</span>
            </div>
            <div className="qa-card-body">{q.desc_polished || q.desc_raw || '（未填写描述）'}</div>
            {(q.success_condition_raw || q.fail_condition_raw || q.blocked_reason_raw) && (
              <div className="qa-card-cond">
                {q.success_condition_raw && (
                  <div><b>成功：</b>{q.success_condition_raw}</div>
                )}
                {q.fail_condition_raw && (
                  <div><b>失败：</b>{q.fail_condition_raw}</div>
                )}
                {q.blocked_reason_raw && (
                  <div className="qa-blocked"><b>阻碍：</b>{q.blocked_reason_raw}</div>
                )}
              </div>
            )}
          </div>
        ))}

        {tab === 'agendas' && ags.length === 0 && (
          <div className="qa-empty">暂无纲领；点右上角"新建纲领"定义角色的长期行为准则。</div>
        )}
        {tab === 'agendas' && ags.map((a) => (
          <div key={a.id} className={`qa-card qa-card-agenda qa-card-status-${a.status}`}>
            <div className="qa-card-top">
              <span
                className="qa-dot"
                style={{ background: AGENDA_STATUS_COLOR[a.status] ?? '#aaa' }}
              />
              <span className="qa-title">{a.title}</span>
              <span className="qa-prio">P{a.priority}</span>
            </div>
            <div className="qa-card-meta">
              <span className="qa-char">{charMap.get(a.char_id)?.name ?? `#${a.char_id}`}</span>
              <span className="qa-status">{a.status}</span>
            </div>
            <div className="qa-card-body">
              {a.principle_polished || a.principle_raw || '（未填写准则）'}
            </div>
            {(a.conflict_with || a.blocked_reason_raw) && (
              <div className="qa-card-cond">
                {a.conflict_with && <div><b>冲突：</b>{a.conflict_with}</div>}
                {a.blocked_reason_raw && (
                  <div className="qa-blocked"><b>阻碍：</b>{a.blocked_reason_raw}</div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {showQuestModal && (
        <NewQuestModal
          chars={chars}
          onClose={() => setShowQuestModal(false)}
          onCreated={refresh}
        />
      )}
      {showAgendaModal && (
        <NewAgendaModal
          chars={chars}
          onClose={() => setShowAgendaModal(false)}
          onCreated={refresh}
        />
      )}
    </div>
  );
}
