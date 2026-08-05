import { useEffect, useState } from 'react';
import AdminNav from '../components/AdminNav';
import { agentApi } from '../api/client';
import { useGameStore } from '../store/gameStore';

type Tab = 'prompts' | 'skills' | 'variables';

interface SkillItem {
  name: string;
  description: string;
  default_version: string;
  active_version: string;
  tools: string[];
  versions: string[];
}

interface VersionDetail {
  name: string;
  version: string;
  system_prompt?: string;
  user_prompt?: string;
  skill_md?: string;
  config?: Record<string, unknown>;
}

function NewVersionModal({
  title,
  existing,
  onClose,
  onCreate,
}: {
  title: string;
  existing: string[];
  onClose: () => void;
  onCreate: (arg: { new_version: string; from_version: string }) => void;
}) {
  const [newVersion, setNewVersion] = useState('');
  const [fromVersion, setFromVersion] = useState(existing[0] ?? '');
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newVersion.trim()) return;
    onCreate({ new_version: newVersion.trim(), from_version: fromVersion });
  };
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <h3>{title}</h3>
        <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <label className="form-group" style={{ marginBottom: 0 }}>
            <span>新版本号</span>
            <input
              required
              placeholder="例：1.2.0 / alpha / hotfix-char"
              value={newVersion}
              onChange={(e) => setNewVersion(e.target.value)}
            />
          </label>
          <label className="form-group" style={{ marginBottom: 0 }}>
            <span>基于哪个版本（留空则新建空版本）</span>
            <select value={fromVersion} onChange={(e) => setFromVersion(e.target.value)}>
              <option value="">（新建空版本）</option>
              {existing.map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
          </label>
          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>取消</button>
            <button type="submit" className="btn-primary">创建新版本</button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function ModelPage() {
  const setNotification = useGameStore((s) => s.setNotification);
  const setError = useGameStore((s) => s.setError);

  const [tab, setTab] = useState<Tab>('prompts');

  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [selectedSkill, setSelectedSkill] = useState<string | null>(null);
  const [skillVersions, setSkillVersions] = useState<string[]>([]);
  const [selectedSkillVersion, setSelectedSkillVersion] = useState<string | null>(null);
  const [skillVersionDetail, setSkillVersionDetail] = useState<VersionDetail | null>(null);
  const [skillDraft, setSkillDraft] = useState<{ skill_md: string; system_prompt?: string }>({ skill_md: '' });
  const [skillDirty, setSkillDirty] = useState(false);

  const [prompts, setPrompts] = useState<string[]>([]);
  const [selectedPrompt, setSelectedPrompt] = useState<string | null>(null);
  const [promptVersions, setPromptVersions] = useState<string[]>([]);
  const [selectedPromptVersion, setSelectedPromptVersion] = useState<string | null>(null);
  const [promptVersionDetail, setPromptVersionDetail] = useState<VersionDetail | null>(null);
  const [promptDraft, setPromptDraft] = useState<{ system_prompt: string; user_prompt: string }>({
    system_prompt: '', user_prompt: '',
  });
  const [promptDirty, setPromptDirty] = useState(false);

  const [variables, setVariables] = useState<Record<string, { description?: string; value?: unknown; source?: string }> | null>(null);

  const [loading, setLoading] = useState(false);
  const [showNewPromptVersion, setShowNewPromptVersion] = useState(false);
  const [showNewSkillVersion, setShowNewSkillVersion] = useState(false);
  const [saving, setSaving] = useState(false);

  const refreshSkills = async () => {
    setLoading(true);
    try {
      const r = await agentApi.listSkills();
      const items: SkillItem[] = r.items || r.skills || [];
      setSkills(items);
      if (items.length > 0 && !selectedSkill) setSelectedSkill(items[0].name);
    } catch (e: unknown) {
      setError(`加载 skills 失败：${e instanceof Error ? e.message : e}`);
    } finally {
      setLoading(false);
    }
  };

  const refreshPrompts = async () => {
    setLoading(true);
    try {
      const r = await agentApi.listPrompts();
      const arr: string[] = r.items || r.prompts || [];
      setPrompts(arr);
      if (arr.length > 0 && !selectedPrompt) setSelectedPrompt(arr[0]);
    } catch (e: unknown) {
      setError(`加载 prompts 失败：${e instanceof Error ? e.message : e}`);
    } finally {
      setLoading(false);
    }
  };

  const refreshVariables = async () => {
    setLoading(true);
    try {
      const r = await agentApi.variables();
      setVariables((r.variables || r) as typeof variables);
    } catch (e: unknown) {
      setError(`加载 variables 失败：${e instanceof Error ? e.message : e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (tab === 'prompts' && prompts.length === 0) void refreshPrompts();
    if (tab === 'skills' && skills.length === 0) void refreshSkills();
    if (tab === 'variables' && variables === null) void refreshVariables();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  // Skill version list on selection
  useEffect(() => {
    if (!selectedSkill) return;
    (async () => {
      try {
        const r = await agentApi.listSkillVersions(selectedSkill);
        const arr: string[] = r.versions || [];
        setSkillVersions(arr);
        const active = skills.find((s) => s.name === selectedSkill)?.active_version
          ?? skills.find((s) => s.name === selectedSkill)?.default_version;
        const def = active && arr.includes(active) ? active : arr[arr.length - 1] ?? null;
        setSelectedSkillVersion(def);
      } catch (e: unknown) {
        setError(`加载 skill 版本失败：${e instanceof Error ? e.message : e}`);
      }
    })();
  }, [selectedSkill, skills, setError]);

  useEffect(() => {
    if (!selectedSkill || !selectedSkillVersion) return;
    (async () => {
      try {
        const r: VersionDetail = await agentApi.getSkillVersion(selectedSkill, selectedSkillVersion);
        setSkillVersionDetail(r);
        setSkillDraft({
          skill_md: r.skill_md ?? '',
          system_prompt: r.system_prompt ?? '',
        });
        setSkillDirty(false);
      } catch (e: unknown) {
        setError(`加载 skill 版本详情失败：${e instanceof Error ? e.message : e}`);
      }
    })();
  }, [selectedSkill, selectedSkillVersion, setError]);

  useEffect(() => {
    if (!selectedPrompt) return;
    (async () => {
      try {
        const r = await agentApi.listPromptVersions(selectedPrompt);
        const arr: string[] = r.versions || [];
        setPromptVersions(arr);
        const def = arr[arr.length - 1] ?? null;
        setSelectedPromptVersion(def);
      } catch (e: unknown) {
        setError(`加载 prompt 版本失败：${e instanceof Error ? e.message : e}`);
      }
    })();
  }, [selectedPrompt, setError]);

  useEffect(() => {
    if (!selectedPrompt || !selectedPromptVersion) return;
    (async () => {
      try {
        const r: VersionDetail = await agentApi.getPromptVersion(selectedPrompt, selectedPromptVersion);
        setPromptVersionDetail(r);
        setPromptDraft({
          system_prompt: r.system_prompt ?? '',
          user_prompt: r.user_prompt ?? '',
        });
        setPromptDirty(false);
      } catch (e: unknown) {
        setError(`加载 prompt 版本详情失败：${e instanceof Error ? e.message : e}`);
      }
    })();
  }, [selectedPrompt, selectedPromptVersion, setError]);

  const handleSetActiveSkill = async (version: string) => {
    if (!selectedSkill) return;
    try {
      await agentApi.setSkillActive(selectedSkill, version);
      setNotification(`已将 ${selectedSkill} 激活版本设为 ${version}`);
      await refreshSkills();
    } catch (e: unknown) {
      setError(`设置失败：${e instanceof Error ? e.message : e}`);
    }
  };

  const handleSetActivePrompt = async (version: string) => {
    if (!selectedPrompt) return;
    try {
      await agentApi.setPromptActive(selectedPrompt, version);
      setNotification(`已将 ${selectedPrompt} 激活版本设为 ${version}`);
      await refreshPrompts();
    } catch (e: unknown) {
      setError(`设置失败：${e instanceof Error ? e.message : e}`);
    }
  };

  const saveSkill = async () => {
    if (!selectedSkill || !selectedSkillVersion) return;
    setSaving(true);
    try {
      await agentApi.updateSkillVersion(selectedSkill, selectedSkillVersion, skillDraft);
      setSkillDirty(false);
      setNotification('skill.md 已保存');
    } catch (e: unknown) {
      setError(`保存失败：${e instanceof Error ? e.message : e}`);
    } finally {
      setSaving(false);
    }
  };

  const deleteSkillVersion = async () => {
    if (!selectedSkill || !selectedSkillVersion) return;
    if (skillVersions.length <= 1) {
      setError('至少保留一个版本');
      return;
    }
    if (!confirm(`确认删除 skill 版本 ${selectedSkillVersion}？`)) return;
    try {
      await agentApi.deleteSkillVersion(selectedSkill, selectedSkillVersion);
      setNotification('版本已删除');
      const idx = skillVersions.indexOf(selectedSkillVersion);
      const next = skillVersions[idx === 0 ? 1 : idx - 1];
      const remaining = skillVersions.filter((v) => v !== selectedSkillVersion);
      setSkillVersions(remaining);
      setSelectedSkillVersion(next ?? null);
    } catch (e: unknown) {
      setError(`删除失败：${e instanceof Error ? e.message : e}`);
    }
  };

  const savePrompt = async () => {
    if (!selectedPrompt || !selectedPromptVersion) return;
    setSaving(true);
    try {
      await agentApi.updatePromptVersion(selectedPrompt, selectedPromptVersion, promptDraft);
      setPromptDirty(false);
      setNotification('prompt 版本已保存');
    } catch (e: unknown) {
      setError(`保存失败：${e instanceof Error ? e.message : e}`);
    } finally {
      setSaving(false);
    }
  };

  const deletePromptVersion = async () => {
    if (!selectedPrompt || !selectedPromptVersion) return;
    if (promptVersions.length <= 1) {
      setError('至少保留一个版本');
      return;
    }
    if (!confirm(`确认删除 prompt 版本 ${selectedPromptVersion}？`)) return;
    try {
      await agentApi.deletePromptVersion(selectedPrompt, selectedPromptVersion);
      setNotification('版本已删除');
      const idx = promptVersions.indexOf(selectedPromptVersion);
      const next = promptVersions[idx === 0 ? 1 : idx - 1];
      const remaining = promptVersions.filter((v) => v !== selectedPromptVersion);
      setPromptVersions(remaining);
      setSelectedPromptVersion(next ?? null);
    } catch (e: unknown) {
      setError(`删除失败：${e instanceof Error ? e.message : e}`);
    }
  };

  const activeSkillVersion = skills.find((s) => s.name === selectedSkill)?.active_version
    ?? skills.find((s) => s.name === selectedSkill)?.default_version;

  return (
    <div className="admin-page">
      <AdminNav />
      <div className="admin-content">
        <div className="admin-header">
          <h1>🤖 模型管理</h1>
        </div>

        <div className="tab-bar">
          <button className={tab === 'prompts' ? 'active' : ''} onClick={() => setTab('prompts')}>Prompts</button>
          <button className={tab === 'skills' ? 'active' : ''} onClick={() => setTab('skills')}>Skills</button>
          <button className={tab === 'variables' ? 'active' : ''} onClick={() => setTab('variables')}>Variables</button>
        </div>

        {loading && <div className="loading">加载中...</div>}

        {/* Prompts Tab */}
        {tab === 'prompts' && (
          <div className="three-pane">
            <div className="pane-left">
              <h3>Prompt 列表</h3>
              <ul className="item-list">
                {prompts.map((name) => (
                  <li
                    key={name}
                    className={selectedPrompt === name ? 'active' : ''}
                    onClick={() => setSelectedPrompt(name)}
                  >
                    {name}
                  </li>
                ))}
              </ul>
            </div>
            <div className="pane-middle">
              <h3>版本时间线</h3>
              <button
                className="btn-primary small"
                style={{ marginBottom: 10, width: '100%' }}
                disabled={!selectedPrompt}
                onClick={() => setShowNewPromptVersion(true)}
              >＋ 新建版本（复制快照）</button>
              {!selectedPrompt ? (
                <div className="empty-hint">请选左侧 prompt</div>
              ) : promptVersions.length === 0 ? (
                <div className="empty-hint">无版本</div>
              ) : (
                <ul className="version-list">
                  {promptVersions.map((v) => (
                    <li
                      key={v}
                      className={selectedPromptVersion === v ? 'active' : ''}
                      onClick={() => setSelectedPromptVersion(v)}
                      title={`版本 ${v}`}
                    >
                      {v}
                    </li>
                  ))}
                </ul>
              )}
              <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
                {selectedPromptVersion && (
                  <>
                    <button
                      onClick={() => handleSetActivePrompt(selectedPromptVersion)}
                      className="btn-primary small"
                      style={{ flex: 1 }}
                    >设为激活</button>
                    <button
                      onClick={deletePromptVersion}
                      className="btn-secondary btn-danger small"
                    >删</button>
                  </>
                )}
              </div>
            </div>
            <div className="pane-right">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <h3 style={{ margin: 0 }}>
                  Prompt 编辑器
                  {promptDirty && <span style={{ color: '#e0b060', marginLeft: 8, fontSize: 12 }}>（有未保存修改）</span>}
                </h3>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button
                    className="btn-secondary small"
                    onClick={() => {
                      if (!promptVersionDetail) return;
                      setPromptDraft({
                        system_prompt: promptVersionDetail.system_prompt ?? '',
                        user_prompt: promptVersionDetail.user_prompt ?? '',
                      });
                      setPromptDirty(false);
                    }}
                    disabled={!promptVersionDetail}
                  >↺ 还原</button>
                  <button
                    className="btn-primary small"
                    onClick={savePrompt}
                    disabled={!promptDirty || saving}
                  >
                    {saving ? '保存中…' : '💾 保存版本'}
                  </button>
                </div>
              </div>
              {!promptVersionDetail ? (
                <div className="empty-hint">选择版本查看详情</div>
              ) : (
                <div className="dual-editor">
                  <div className="editor-col">
                    <label>system_prompt.md</label>
                    <textarea
                      value={promptDraft.system_prompt}
                      rows={18}
                      onChange={(e) => { setPromptDraft({ ...promptDraft, system_prompt: e.target.value }); setPromptDirty(true); }}
                    />
                  </div>
                  <div className="editor-col">
                    <label>user_prompt.md</label>
                    <textarea
                      value={promptDraft.user_prompt}
                      rows={18}
                      onChange={(e) => { setPromptDraft({ ...promptDraft, user_prompt: e.target.value }); setPromptDirty(true); }}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Skills Tab */}
        {tab === 'skills' && (
          <div className="three-pane">
            <div className="pane-left">
              <h3>Skill 列表</h3>
              <ul className="item-list">
                {skills.map((s) => (
                  <li
                    key={s.name}
                    className={selectedSkill === s.name ? 'active' : ''}
                    onClick={() => setSelectedSkill(s.name)}
                  >
                    {s.name}
                    <span className="badge">
                      {s.active_version || s.default_version}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="pane-middle">
              <h3>版本时间线</h3>
              <button
                className="btn-primary small"
                style={{ marginBottom: 10, width: '100%' }}
                disabled={!selectedSkill}
                onClick={() => setShowNewSkillVersion(true)}
              >＋ 新建版本（copytree）</button>
              {!selectedSkill ? (
                <div className="empty-hint">请选左侧 skill</div>
              ) : (
                <>
                  <ul className="version-list">
                    {skillVersions.map((v) => (
                      <li
                        key={v}
                        className={selectedSkillVersion === v ? 'active' : ''}
                        onClick={() => setSelectedSkillVersion(v)}
                      >
                        {v}
                        {v === activeSkillVersion && <span className="badge" style={{ marginLeft: 6 }}>激活</span>}
                      </li>
                    ))}
                  </ul>
                  <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
                    {selectedSkillVersion && (
                      <>
                        <button
                          onClick={() => handleSetActiveSkill(selectedSkillVersion)}
                          className="btn-primary small"
                          style={{ flex: 1 }}
                        >设为激活</button>
                        <button
                          onClick={deleteSkillVersion}
                          className="btn-secondary btn-danger small"
                        >删</button>
                      </>
                    )}
                  </div>
                </>
              )}
            </div>
            <div className="pane-right">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <h3 style={{ margin: 0 }}>
                  Skill 编辑器
                  {skillDirty && <span style={{ color: '#e0b060', marginLeft: 8, fontSize: 12 }}>（有未保存修改）</span>}
                </h3>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button
                    className="btn-secondary small"
                    onClick={() => {
                      if (!skillVersionDetail) return;
                      setSkillDraft({
                        skill_md: skillVersionDetail.skill_md ?? '',
                        system_prompt: skillVersionDetail.system_prompt ?? '',
                      });
                      setSkillDirty(false);
                    }}
                    disabled={!skillVersionDetail}
                  >↺ 还原</button>
                  <button
                    className="btn-primary small"
                    onClick={saveSkill}
                    disabled={!skillDirty || saving}
                  >
                    {saving ? '保存中…' : '💾 保存版本'}
                  </button>
                </div>
              </div>
              {!skillVersionDetail ? (
                <div className="empty-hint">选择版本查看 skill.md</div>
              ) : (
                <div>
                  <div className="single-editor">
                    <label>skill.md</label>
                    <textarea
                      value={skillDraft.skill_md}
                      rows={24}
                      onChange={(e) => { setSkillDraft({ ...skillDraft, skill_md: e.target.value }); setSkillDirty(true); }}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Variables Tab */}
        {tab === 'variables' && (
          <div className="variables-tab">
            <h3>variables.json 定义的变量字典</h3>
            {!variables ? (
              <div className="empty-hint">加载中</div>
            ) : Object.keys(variables).length === 0 ? (
              <div className="empty-hint">variables.json 为空</div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ width: 220 }}>变量名</th>
                    <th>含义 / 来源</th>
                    <th style={{ width: 320 }}>当前值</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(variables).map(([k, v]) => {
                    const desc = typeof v === 'object' && v
                      ? ((v as { description?: string }).description ?? '') +
                        ((v as { source?: string }).source ? ` · 来源：${(v as { source: string }).source}` : '')
                      : '';
                    const value = typeof v === 'object' && v
                      ? ((v as { value?: unknown }).value ?? '')
                      : v;
                    return (
                      <tr key={k}>
                        <td><code>${`{${k}}`}</code></td>
                        <td>{desc || '—'}</td>
                        <td>
                          <code style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                            {typeof value === 'object' ? JSON.stringify(value) : String(value ?? '')}
                          </code>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      {showNewPromptVersion && selectedPrompt && (
        <NewVersionModal
          title={`为 Prompt「${selectedPrompt}」创建新版本`}
          existing={promptVersions}
          onClose={() => setShowNewPromptVersion(false)}
          onCreate={async ({ new_version, from_version }) => {
            try {
              await agentApi.createPromptVersion(selectedPrompt, { new_version, from_version });
              setNotification('新版本已创建');
              setShowNewPromptVersion(false);
              const r = await agentApi.listPromptVersions(selectedPrompt);
              setPromptVersions(r.versions || []);
              setSelectedPromptVersion(new_version);
            } catch (e: unknown) {
              setError(`创建失败：${e instanceof Error ? e.message : e}`);
            }
          }}
        />
      )}

      {showNewSkillVersion && selectedSkill && (
        <NewVersionModal
          title={`为 Skill「${selectedSkill}」创建新版本`}
          existing={skillVersions}
          onClose={() => setShowNewSkillVersion(false)}
          onCreate={async ({ new_version, from_version }) => {
            try {
              await agentApi.createSkillVersion(selectedSkill, { new_version, from_version });
              setNotification('新版本已创建');
              setShowNewSkillVersion(false);
              const r = await agentApi.listSkillVersions(selectedSkill);
              setSkillVersions(r.versions || []);
              setSelectedSkillVersion(new_version);
            } catch (e: unknown) {
              setError(`创建失败：${e instanceof Error ? e.message : e}`);
            }
          }}
        />
      )}
    </div>
  );
}
