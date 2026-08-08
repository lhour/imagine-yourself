import { useEffect, useState } from 'react';
import AdminNav from '../components/AdminNav';
import { knowledgeApi, KnowledgeCategory, KnowledgeItem } from '../api/client';
import { useGameStore } from '../store/gameStore';
import './KnowledgePage.css';

type ViewMode = 'browse' | 'search' | 'manage';

export default function KnowledgePage() {
  const setNotification = useGameStore((s) => s.setNotification);
  const setError = useGameStore((s) => s.setError);

  const [categories, setCategories] = useState<KnowledgeCategory[]>([]);
  const [items, setItems] = useState<KnowledgeItem[]>([]);
  const [stats, setStats] = useState<{ total_items: number; total_categories: number; total_searches: number; db_size_bytes: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<ViewMode>('browse');
  const [selectedCategory, setSelectedCategory] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<KnowledgeItem[]>([]);
  const [showItemModal, setShowItemModal] = useState(false);
  const [editingItem, setEditingItem] = useState<KnowledgeItem | null>(null);
  const [showCategoryModal, setShowCategoryModal] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState('');
  const [newCategoryDesc, setNewCategoryDesc] = useState('');

  // 表单状态
  const [formTitle, setFormTitle] = useState('');
  const [formContent, setFormContent] = useState('');
  const [formCategoryId, setFormCategoryId] = useState(0);
  const [formKeywords, setFormKeywords] = useState('');
  const [formTags, setFormTags] = useState('');
  const [formImportance, setFormImportance] = useState(3);

  const loadItems = async (catId?: number, pg?: number) => {
    try {
      const effectiveCatId = catId ?? selectedCategory;
      const effectivePage = pg ?? page;
      const resp = await knowledgeApi.listItems(effectiveCatId, effectivePage, 20);
      setItems(resp.items || []);
      setTotalPages(resp.total_pages || 1);
    } catch (e: unknown) {
      setError(`加载条目失败：${e instanceof Error ? e.message : e}`);
    }
  };

  const refresh = async () => {
    setLoading(true);
    try {
      const [cats, statsResp] = await Promise.all([
        knowledgeApi.listCategories(),
        knowledgeApi.getStats(),
      ]);
      setCategories(cats);
      setStats(statsResp);
      await loadItems(0, 1);
    } catch (e: unknown) {
      setError(`加载知识库失败：${e instanceof Error ? e.message : e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!loading) {
      loadItems(selectedCategory, page);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCategory, page]);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    try {
      const resp = await knowledgeApi.search(searchQuery, selectedCategory || 0, 20);
      setSearchResults(resp.results);
      setViewMode('search');
    } catch (e: unknown) {
      setError(`检索失败：${e instanceof Error ? e.message : e}`);
    }
  };

  const openCreateModal = () => {
    setEditingItem(null);
    setFormTitle('');
    setFormContent('');
    setFormCategoryId(selectedCategory);
    setFormKeywords('');
    setFormTags('');
    setFormImportance(3);
    setShowItemModal(true);
  };

  const openEditModal = (item: KnowledgeItem) => {
    setEditingItem(item);
    setFormTitle(item.title);
    setFormContent(item.content);
    setFormCategoryId(item.category_id || 0);
    setFormKeywords(item.keywords.join(', '));
    setFormTags(item.tags.join(', '));
    setFormImportance(item.importance);
    setShowItemModal(true);
  };

  const handleSaveItem = async () => {
    if (!formTitle.trim() || !formContent.trim()) {
      setError('标题和内容不能为空');
      return;
    }
    try {
      const keywords = formKeywords.split(/[,，]/).map((k) => k.trim()).filter(Boolean);
      const tags = formTags.split(/[,，]/).map((t) => t.trim()).filter(Boolean);

      if (editingItem) {
        await knowledgeApi.updateItem(editingItem.id, {
          title: formTitle,
          content: formContent,
          category_id: formCategoryId,
          keywords,
          tags,
          importance: formImportance,
        });
        setShowItemModal(false);
        await refresh();
        setNotification('条目已更新');
      } else {
        await knowledgeApi.createItem({
          title: formTitle,
          content: formContent,
          category_id: formCategoryId,
          keywords,
          tags,
          importance: formImportance,
        });
        setShowItemModal(false);
        await refresh();
        setNotification('条目已创建');
      }
    } catch (e: unknown) {
      setError(`保存失败：${e instanceof Error ? e.message : e}`);
    }
  };

  const handleDeleteItem = async (id: number) => {
    if (!window.confirm('确定删除此条目？')) return;
    try {
      await knowledgeApi.deleteItem(id);
      await refresh();
      setNotification('条目已删除');
    } catch (e: unknown) {
      setError(`删除失败：${e instanceof Error ? e.message : e}`);
    }
  };

  const handleCreateCategory = async () => {
    if (!newCategoryName.trim()) return;
    try {
      await knowledgeApi.createCategory(newCategoryName, newCategoryDesc);
      setNewCategoryName('');
      setNewCategoryDesc('');
      setShowCategoryModal(false);
      await refresh();
      setNotification('分类已创建');
    } catch (e: unknown) {
      setError(`创建分类失败：${e instanceof Error ? e.message : e}`);
    }
  };

  const handleDeleteCategory = async (id: number, name: string) => {
    if (!window.confirm(`确定删除分类「${name}」及其所有条目？`)) return;
    try {
      await knowledgeApi.deleteCategory(id);
      if (selectedCategory === id) {
        setSelectedCategory(0);
        setPage(1);
      }
      await refresh();
      setNotification('分类已删除');
    } catch (e: unknown) {
      setError(`删除失败：${e instanceof Error ? e.message : e}`);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  return (
    <div className="admin-page">
      <AdminNav />
      <div className="admin-content knowledge-page">
        <div className="admin-header">
          <h1>📚 知识库</h1>
          <div className="header-actions">
            <button onClick={() => setShowCategoryModal(true)} className="btn-secondary">+ 新分类</button>
            <button onClick={openCreateModal} className="btn-primary">+ 新条目</button>
          </div>
        </div>

        {/* 统计卡片 */}
        {stats && (
          <div className="kb-stats">
            <div className="kb-stat-card">
              <span className="kb-stat-value">{stats.total_items}</span>
              <span className="kb-stat-label">条目总数</span>
            </div>
            <div className="kb-stat-card">
              <span className="kb-stat-value">{stats.total_categories}</span>
              <span className="kb-stat-label">分类数</span>
            </div>
            <div className="kb-stat-card">
              <span className="kb-stat-value">{stats.total_searches}</span>
              <span className="kb-stat-label">检索次数</span>
            </div>
            <div className="kb-stat-card">
              <span className="kb-stat-value">{formatSize(stats.db_size_bytes)}</span>
              <span className="kb-stat-label">数据库大小</span>
            </div>
          </div>
        )}

        {/* 视图切换 */}
        <div className="kb-view-tabs">
          <button
            className={`kb-tab ${viewMode === 'browse' ? 'active' : ''}`}
            onClick={() => setViewMode('browse')}
          >浏览</button>
          <button
            className={`kb-tab ${viewMode === 'search' ? 'active' : ''}`}
            onClick={() => setViewMode('search')}
          >检索</button>
          <button
            className={`kb-tab ${viewMode === 'manage' ? 'active' : ''}`}
            onClick={() => setViewMode('manage')}
          >管理</button>
        </div>

        {/* 分类筛选器 */}
        <div className="kb-category-filter">
          <button
            className={`kb-cat-chip ${selectedCategory === 0 ? 'active' : ''}`}
            onClick={() => { setSelectedCategory(0); setPage(1); }}
          >全部分类</button>
          {categories.map((cat) => (
            <button
              key={cat.id}
              className={`kb-cat-chip ${selectedCategory === cat.id ? 'active' : ''}`}
              onClick={() => { setSelectedCategory(cat.id); setPage(1); }}
            >
              {cat.name} ({cat.item_count})
            </button>
          ))}
        </div>

        {loading ? (
          <div className="loading">加载中...</div>
        ) : (
          <>
            {/* 浏览模式 */}
            {viewMode === 'browse' && (
              <div className="kb-content">
                <div className="kb-item-grid">
                  {items.map((item) => (
                    <div key={item.id} className="kb-item-card" onClick={() => openEditModal(item)}>
                      <div className="kb-item-header">
                        <span className="kb-item-title">{item.title}</span>
                        <div className="kb-item-header-right">
                          <span className="kb-item-importance">
                            {'★'.repeat(item.importance)}
                          </span>
                          <button
                            className="kb-delete-btn"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteItem(item.id);
                            }}
                            title="删除"
                          >🗑</button>
                        </div>
                      </div>
                      <div className="kb-item-preview">{item.content.slice(0, 150)}...</div>
                      {item.keywords.length > 0 && (
                        <div className="kb-item-tags">
                          {item.keywords.slice(0, 4).map((kw, i) => (
                            <span key={i} className="kb-tag">{kw}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                {totalPages > 1 && (
                  <div className="kb-pagination">
                    <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>上一页</button>
                    <span>{page} / {totalPages}</span>
                    <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>下一页</button>
                  </div>
                )}
                {items.length === 0 && <div className="empty-state">暂无条目，点击「+ 新条目」添加</div>}
              </div>
            )}

            {/* 检索模式 */}
            {viewMode === 'search' && (
              <div className="kb-content">
                <div className="kb-search-bar">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                    placeholder="输入关键词（如：仙侠 武器）..."
                    className="kb-search-input"
                  />
                  <button onClick={handleSearch} className="btn-primary">🔍 检索</button>
                  <button
                    onClick={async () => {
                      try {
                        const resp = await knowledgeApi.getRandom(selectedCategory || 0, 10);
                        setSearchResults(resp.items);
                      } catch (e) {
                        setError(String(e));
                      }
                    }}
                    className="btn-secondary"
                  >🎲 随机</button>
                </div>
                {searchResults.length > 0 && (
                  <div className="kb-search-results">
                    {searchResults.map((item) => (
                      <div key={item.id} className="kb-search-result-item" onClick={() => openEditModal(item)}>
                        <div className="kb-result-header">
                          <span className="kb-result-title">{item.title}</span>
                          <div className="kb-result-header-right">
                            {item.score !== undefined && (
                              <span className="kb-result-score">匹配度: {item.score}</span>
                            )}
                            <button
                              className="kb-delete-btn"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDeleteItem(item.id);
                              }}
                              title="删除"
                            >🗑</button>
                          </div>
                        </div>
                        <div className="kb-result-content">{item.content}</div>
                      </div>
                    ))}
                  </div>
                )}
                {searchResults.length === 0 && searchQuery && (
                  <div className="empty-state">未找到匹配结果</div>
                )}
              </div>
            )}

            {/* 管理模式 */}
            {viewMode === 'manage' && (
              <div className="kb-content">
                <div className="kb-manage-section">
                  <h3>分类管理</h3>
                  <div className="kb-category-list">
                    {categories.map((cat) => (
                      <div key={cat.id} className="kb-category-item">
                        <div className="kb-category-info">
                          <span className="kb-category-name">{cat.name}</span>
                          <span className="kb-category-count">{cat.item_count} 条</span>
                        </div>
                        <button
                          onClick={() => handleDeleteCategory(cat.id, cat.name)}
                          className="btn-danger-small"
                        >删除</button>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="kb-manage-section">
                  <h3>条目管理</h3>
                  <div className="kb-items-manage">
                    {items.map((item) => (
                      <div key={item.id} className="kb-manage-item">
                        <div className="kb-manage-info" onClick={() => openEditModal(item)}>
                          <span className="kb-manage-title">{item.title}</span>
                          <span className="kb-manage-meta">
                            {item.source} · 重要度 {item.importance}
                          </span>
                        </div>
                        <div className="kb-manage-actions">
                          <button onClick={() => openEditModal(item)} className="btn-secondary-small">编辑</button>
                          <button onClick={() => handleDeleteItem(item.id)} className="btn-danger-small">删除</button>
                        </div>
                      </div>
                    ))}
                  </div>
                  {totalPages > 1 && (
                    <div className="kb-pagination">
                      <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>上一页</button>
                      <span>{page} / {totalPages}</span>
                      <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>下一页</button>
                    </div>
                  )}
                </div>
              </div>
            )}
          </>
        )}

        {/* 条目编辑弹窗 */}
        {showItemModal && (
          <div className="modal-overlay" onClick={() => setShowItemModal(false)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <h2>{editingItem ? '编辑条目' : '创建新条目'}</h2>
              <div className="form-group">
                <label>标题</label>
                <input type="text" value={formTitle} onChange={(e) => setFormTitle(e.target.value)} />
              </div>
              <div className="form-group">
                <label>内容</label>
                <textarea
                  value={formContent}
                  onChange={(e) => setFormContent(e.target.value)}
                  rows={8}
                  placeholder="详细描述设定内容..."
                />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>分类</label>
                  <select value={formCategoryId} onChange={(e) => setFormCategoryId(Number(e.target.value))}>
                    <option value={0}>未分类</option>
                    {categories.map((cat) => (
                      <option key={cat.id} value={cat.id}>{cat.name}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label>重要度 (0-5)</label>
                  <input
                    type="number"
                    min={0}
                    max={5}
                    value={formImportance}
                    onChange={(e) => setFormImportance(Number(e.target.value))}
                  />
                </div>
              </div>
              <div className="form-group">
                <label>关键词（逗号分隔）</label>
                <input
                  type="text"
                  value={formKeywords}
                  onChange={(e) => setFormKeywords(e.target.value)}
                  placeholder="如：仙侠, 武器, 长剑"
                />
              </div>
              <div className="form-group">
                <label>标签（逗号分隔）</label>
                <input
                  type="text"
                  value={formTags}
                  onChange={(e) => setFormTags(e.target.value)}
                  placeholder="如：近战, 神兵"
                />
              </div>
              <div className="modal-actions">
                <button onClick={() => setShowItemModal(false)} className="btn-secondary">取消</button>
                <button onClick={handleSaveItem} className="btn-primary">保存</button>
              </div>
            </div>
          </div>
        )}

        {/* 创建分类弹窗 */}
        {showCategoryModal && (
          <div className="modal-overlay" onClick={() => setShowCategoryModal(false)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <h2>创建新分类</h2>
              <div className="form-group">
                <label>分类名称</label>
                <input type="text" value={newCategoryName} onChange={(e) => setNewCategoryName(e.target.value)} />
              </div>
              <div className="form-group">
                <label>描述</label>
                <textarea
                  value={newCategoryDesc}
                  onChange={(e) => setNewCategoryDesc(e.target.value)}
                  rows={3}
                />
              </div>
              <div className="modal-actions">
                <button onClick={() => setShowCategoryModal(false)} className="btn-secondary">取消</button>
                <button onClick={handleCreateCategory} className="btn-primary">创建</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
